"""Thin CLI bridge para que el ERP nuevo (Tauri/Rust) invoque funciones Python del
stack de watermark preservado en `publicados.py` + `local_inpaint.py`.

Uso:
    python scripts/erp_rust_bridge.py < cmd.json
    → JSON result en stdout (una línea), logs en stderr.

Comandos soportados (cmd.cmd):
  - "regen_watermark"  → _regen_watermark(fid, modelo_idx, photo_idx, mode)
  - "restore_backup"   → _restore_r2_from_backup(fid, modelo_idx, photo_idx)
  - "ping"             → {"ok": true, "msg": "pong"} — usado por el Rust side para
                         verificar que el bridge + deps están instaladas.

El cwd debe ser `el-club/erp/` para que los imports resuelvan. El caller (Rust)
es responsable de fijar cwd; acá añadimos `.` al sys.path por las dudas.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

# Force UTF-8 para stdout/stderr. Critical en Windows donde default es cp1252
# y emojis / acentos en error messages (ej. "🎯 Forzar") hacen crashear _reply().
# El subprocess de Tauri lee stdout bytes, no le importa encoding; necesitamos
# que Python no falle al write.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    # Python <3.7 — fallback
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _ensure_cwd():
    """Garantiza que el cwd sea erp/. Si el caller nos invocó desde otro lado,
    corregimos — los módulos usan paths relativos (.env, catalog path, etc.)."""
    here = Path(__file__).resolve().parent.parent  # erp/scripts/ → erp/
    if Path.cwd() != here:
        os.chdir(here)
    sys.path.insert(0, str(here))


def _reply(obj):
    """Escribe una línea JSON en stdout y termina. Logs van por stderr."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_progress(obj):
    """Emite un evento de progreso a stderr como JSONL. Rust lo lee en un thread
    separado y lo reemite como Tauri event hacia el frontend. Las líneas se
    prefixan con __progress__=True para distinguirlas de otros logs."""
    payload = {"__progress__": True, **obj}
    try:
        sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stderr.flush()
    except Exception:
        pass  # progress es best-effort, no bloqueamos si falla


def _err(msg, **extra):
    payload = {"ok": False, "error": msg}
    payload.update(extra)
    _reply(payload)
    sys.exit(1)


def cmd_ping(_args):
    # Check deps — ayuda a debugger desde el Rust side
    status = {"ok": True, "deps": {}}
    try:
        import torch  # type: ignore
        status["deps"]["torch"] = {
            "version": torch.__version__,
            "cuda": bool(torch.cuda.is_available()),
        }
    except Exception as e:
        status["deps"]["torch"] = {"error": str(e)}
    try:
        import iopaint  # noqa: F401
        status["deps"]["iopaint"] = "ok"
    except Exception as e:
        status["deps"]["iopaint"] = {"error": str(e)}
    try:
        import easyocr  # noqa: F401
        status["deps"]["easyocr"] = "ok"
    except Exception as e:
        status["deps"]["easyocr"] = {"error": str(e)}
    try:
        import audit_enrich  # type: ignore
        status["deps"]["gemini_key"] = bool(audit_enrich.GEMINI_KEY)
    except Exception as e:
        status["deps"]["audit_enrich"] = {"error": str(e)}
    _reply(status)


def cmd_regen_watermark(args):
    fid = args.get("fid")
    modelo_idx = args.get("modelo_idx")
    photo_idx = args.get("photo_idx")
    mode = args.get("mode") or "auto"
    if not fid:
        return _err("fid missing")
    if modelo_idx is None or photo_idx is None:
        return _err("modelo_idx / photo_idx missing")
    if mode not in {"auto", "force", "sd", "gemini"}:
        return _err(f"mode inválido: {mode!r} (usar auto/force/sd/gemini)")

    import publicados  # type: ignore

    result = publicados._regen_watermark(
        fid=fid,
        modelo_idx=int(modelo_idx),
        photo_idx=int(photo_idx),
        mode=mode,
    )
    # Publicados devuelve {"ok": True, "new_url": ...} o {"error": ...}.
    # Normalizamos a {"ok": bool, "new_url": ..., "error": ...} para el caller.
    if isinstance(result, dict):
        if "ok" not in result:
            result = {"ok": "error" not in result, **result}
    else:
        result = {"ok": False, "error": f"result inesperado: {result!r}"}
    _reply(result)


def cmd_restore_backup(args):
    fid = args.get("fid")
    modelo_idx = args.get("modelo_idx")
    photo_idx = args.get("photo_idx")
    if not fid or modelo_idx is None or photo_idx is None:
        return _err("fid / modelo_idx / photo_idx missing")

    import publicados  # type: ignore

    if not hasattr(publicados, "_restore_r2_from_backup"):
        return _err("_restore_r2_from_backup no existe en publicados.py")

    result = publicados._restore_r2_from_backup(
        fid=fid, modelo_idx=int(modelo_idx), photo_idx=int(photo_idx)
    )
    if isinstance(result, dict) and "ok" not in result:
        result = {"ok": "error" not in result, **result}
    _reply(result)


def cmd_delete_sku(args):
    """Soft-delete de un SKU: status='deleted', remueve modelo de catalog.json,
    append row en audit_delete_log, commit+push si was_published."""
    sku = args.get("sku")
    motivo = (args.get("motivo") or "").strip()
    if not sku:
        return _err("sku missing")
    if not motivo:
        return _err("motivo requerido (explicá por qué se borra)")

    import audit_db  # type: ignore
    import audit  # type: ignore
    from db import get_conn  # type: ignore

    conn = get_conn()
    try:
        catalog = audit_db.load_catalog()
        sku_idx = audit_db.build_sku_index(catalog)
        resolved = sku_idx.get(sku)
        if not resolved:
            return _err(f"SKU {sku!r} no encontrado en catalog")
        fam, modelo = resolved
        result = audit._delete_sku(conn, sku, fam, modelo, motivo)
        if isinstance(result, dict) and "ok" not in result:
            result = {"ok": "error" not in result, **result}
        _reply(result)
    finally:
        conn.close()


def cmd_edit_modelo_type(args):
    """Cambia modelo.type + modelo.sleeve y migra el SKU asociado.
    Si el SKU nuevo != viejo, migra rows de audit_decisions + audit_photo_actions.
    Si el SKU nuevo colisiona con otro existente, append -Xn como disambiguador.

    Args:
      fid (canonical family_id), modelo_idx, new_type, new_sleeve (opcional, null si
      no aplica), motivo.
    """
    fid = args.get("fid")
    modelo_idx = args.get("modelo_idx")
    new_type = args.get("new_type")
    new_sleeve = args.get("new_sleeve")  # puede ser None
    motivo = (args.get("motivo") or "").strip()
    if not fid or modelo_idx is None or not new_type:
        return _err("fid / modelo_idx / new_type missing")

    import audit_db  # type: ignore
    from db import get_conn  # type: ignore

    VALID_TYPES = {
        "fan_adult", "player_adult", "retro_adult",
        "woman", "kid", "baby", "goalkeeper",
        "polo", "vest", "training", "sweatshirt", "jacket", "shorts", "adult",
    }
    VALID_SLEEVES = {None, "short", "long"}

    if new_type not in VALID_TYPES:
        return _err(f"new_type inválido: {new_type!r}. Opciones: {sorted(VALID_TYPES)}")
    if new_sleeve not in VALID_SLEEVES:
        return _err(f"new_sleeve inválido: {new_sleeve!r}. Opciones: short/long/null")

    catalog = audit_db.load_catalog()
    fam = audit_db.get_family(catalog, fid)
    if not fam:
        return _err(f"family {fid!r} no existe")

    modelos = fam.get("modelos") or []
    if not (0 <= int(modelo_idx) < len(modelos)):
        return _err(f"modelo_idx {modelo_idx} OOB (family tiene {len(modelos)} modelos)")

    modelo = modelos[int(modelo_idx)]
    old_sku = modelo.get("sku")
    old_type = modelo.get("type")
    old_sleeve = modelo.get("sleeve")

    if old_type == new_type and old_sleeve == new_sleeve:
        return _reply({"ok": True, "msg": "no changes", "sku": old_sku})

    # Aplicar cambio
    modelo["type"] = new_type
    modelo["sleeve"] = new_sleeve

    # Regenerar SKUs solo para esta family
    new_skus = audit_db.generate_skus_for_family(fam)
    new_sku = new_skus[int(modelo_idx)]

    # Check cross-family collision
    all_other_skus = set()
    for other in catalog:
        if other.get("family_id") == fid:
            continue
        for m in (other.get("modelos") or []):
            if m.get("sku"):
                all_other_skus.add(m["sku"])
        if other.get("sku"):
            all_other_skus.add(other["sku"])

    if new_sku in all_other_skus and new_sku != old_sku:
        # Cross-family collision — append -X1/-X2/etc
        for suffix_n in range(1, 50):
            candidate = f"{new_sku}-X{suffix_n}"
            if candidate not in all_other_skus:
                new_sku = candidate
                break
        else:
            # Rollback type/sleeve
            modelo["type"] = old_type
            modelo["sleeve"] = old_sleeve
            return _err(f"cross-family collision inresoluble después de 50 intentos")

    # Write SKUs back into this family's modelos
    for i, m in enumerate(modelos):
        m["sku"] = new_skus[i] if i != int(modelo_idx) else new_sku

    # Save catalog
    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Migrate audit_decisions + audit_photo_actions si el SKU cambió
    migrated = {"audit_decisions": 0, "audit_photo_actions": 0}
    if new_sku != old_sku and old_sku:
        conn = get_conn()
        try:
            # Check que no exista ya row para el new_sku (seguridad)
            existing = conn.execute(
                "SELECT 1 FROM audit_decisions WHERE family_id = ?", (new_sku,)
            ).fetchone()
            if existing:
                # Merge conflict — solo migrar si new_sku no tiene row previa
                return _err(
                    f"new_sku {new_sku} ya tiene row en audit_decisions. "
                    f"Resolver manualmente antes de editar (merge conflict)."
                )
            cur = conn.execute(
                "UPDATE audit_decisions SET family_id = ?, notes = COALESCE(notes, '') || ? "
                "WHERE family_id = ?",
                (new_sku, f"\n[SKU migration {old_sku}→{new_sku}] {motivo}", old_sku),
            )
            migrated["audit_decisions"] = cur.rowcount
            cur = conn.execute(
                "UPDATE audit_photo_actions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            migrated["audit_photo_actions"] = cur.rowcount
            conn.commit()
        finally:
            conn.close()

    _reply({
        "ok": True,
        "old_sku": old_sku,
        "new_sku": new_sku,
        "old_type": old_type,
        "new_type": new_type,
        "old_sleeve": old_sleeve,
        "new_sleeve": new_sleeve,
        "migrated": migrated,
    })


def cmd_batch_clean_family(args):
    """Procesa fotos DIRTY del family completo o de un modelo específico.

    Args:
        fid: family_id
        modelo_idx: opcional. Si presente, solo limpia fotos DIRTY de ese modelo.
                    Si ausente, limpia TODAS las fotos DIRTY del family.
    """
    fid = args.get("fid")
    modelo_idx_filter = args.get("modelo_idx")  # None = all modelos
    if not fid:
        return _err("fid missing")

    import audit_db  # type: ignore
    import publicados  # type: ignore

    catalog = audit_db.load_catalog()
    fam = audit_db.get_family(catalog, fid)
    if not fam:
        return _err(f"family {fid!r} no encontrada")

    # Collect dirty photos — optionally filtered by modelo_idx
    dirty = []
    for mi, m in enumerate(fam.get("modelos") or []):
        if modelo_idx_filter is not None and mi != int(modelo_idx_filter):
            continue
        for pi, url in enumerate(m.get("gallery") or []):
            if "?v=" not in url:
                dirty.append((mi, pi))

    total = len(dirty)
    if total == 0:
        _reply({"ok": True, "total": 0, "cleaned": 0, "failed": 0, "skipped": 0, "errors": []})
        return

    cleaned = 0
    failed = 0
    skipped = 0
    errors = []

    _emit_progress({"op": "batch_clean", "stage": "start", "total": total, "fid": fid})

    for i, (mi, pi) in enumerate(dirty, 1):
        _emit_progress({
            "op": "batch_clean", "stage": "processing",
            "current": i, "total": total, "modelo_idx": mi, "photo_idx": pi,
        })
        try:
            result = publicados._regen_watermark(
                fid=fid, modelo_idx=mi, photo_idx=pi, mode="auto"
            )
            if isinstance(result, dict) and result.get("ok"):
                cleaned += 1
            else:
                err_msg = (
                    result.get("error") if isinstance(result, dict) else str(result)
                ) or "unknown"
                # Si OCR+template no detectaron watermark, es 'skip' no 'fail'
                if "no detectaron" in err_msg.lower() or "skipped" in err_msg.lower():
                    skipped += 1
                else:
                    failed += 1
                errors.append(f"m{mi}/{pi}: {err_msg}")
        except Exception as e:
            failed += 1
            errors.append(f"m{mi}/{pi}: {type(e).__name__}: {e}")

    _emit_progress({
        "op": "batch_clean", "stage": "done",
        "total": total, "cleaned": cleaned, "failed": failed, "skipped": skipped,
    })
    _reply({
        "ok": True,
        "total": total,
        "cleaned": cleaned,
        "failed": failed,
        "skipped": skipped,
        "errors": errors[:20],  # cap para no inundar UI
    })


def cmd_delete_r2_objects(args):
    """Borra objetos de R2 por key. Recibe lista de URLs; deriva los keys.
    Args: {urls: [str, ...]}
    Returns: {ok, deleted, failed, errors}
    """
    urls = args.get("urls") or []
    if not urls:
        return _reply({"ok": True, "deleted": 0, "failed": 0, "errors": []})

    import os
    account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
    access_key = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    bucket = os.getenv("R2_BUCKET", "elclub-vault-images").strip()
    if not (account_id and access_key and secret_key):
        return _err("R2 creds no seteados en env")

    try:
        import boto3
    except ImportError:
        return _err("boto3 no instalado")

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    deleted = 0
    failed = 0
    errors = []
    for url in urls:
        # Derivar key del URL público: https://img.elclub.club/<key> o
        # https://<account>.r2.cloudflarestorage.com/<bucket>/<key>
        base_url = url.split("?")[0]
        if "/families/" not in base_url:
            errors.append(f"URL no reconocida (sin /families/): {base_url}")
            failed += 1
            continue
        key = "families/" + base_url.split("/families/", 1)[1]
        try:
            client.delete_object(Bucket=bucket, Key=key)
            deleted += 1
        except Exception as e:
            failed += 1
            errors.append(f"{key}: {type(e).__name__}: {e}")

    _reply({"ok": True, "deleted": deleted, "failed": failed, "errors": errors[:20]})


def cmd_set_modelo_field(args):
    """Set un field simple del modelo (price, sizes, sold_out, notes).
    No regenera SKU — solo modifica el campo.
    """
    fid = args.get("fid")
    modelo_idx = args.get("modelo_idx")
    field = args.get("field")
    value = args.get("value")  # puede ser str, int, bool, None
    if not fid or modelo_idx is None or not field:
        return _err("fid / modelo_idx / field missing")

    ALLOWED = {"price", "sizes", "sold_out", "notes"}
    if field not in ALLOWED:
        return _err(f"field {field!r} no permitido. Usar: {sorted(ALLOWED)}")

    import audit_db  # type: ignore
    catalog = audit_db.load_catalog()
    fam = audit_db.get_family(catalog, fid)
    if not fam:
        return _err(f"family {fid!r} no encontrada")
    modelos = fam.get("modelos") or []
    if not (0 <= int(modelo_idx) < len(modelos)):
        return _err(f"modelo_idx OOB")
    modelo = modelos[int(modelo_idx)]
    old_value = modelo.get(field)
    modelo[field] = value

    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    _reply({"ok": True, "field": field, "old": old_value, "new": value})


def cmd_set_family_variant(args):
    """Cambia family.variant + variant_label, regenera SKUs de todos los modelos
    y migra audit_decisions + audit_photo_actions a los nuevos SKUs."""
    fid = args.get("fid")
    new_variant = (args.get("new_variant") or "").lower().strip()
    new_variant_label = args.get("new_variant_label")  # opcional
    if not fid or not new_variant:
        return _err("fid / new_variant missing")

    VALID_VARIANTS = {"home", "away", "third", "goalkeeper", "special", "training",
                      "fourth", "anniversary", "windbreaker", "retro", "originals",
                      "concept", "limited"}
    if new_variant not in VALID_VARIANTS:
        return _err(f"new_variant inválido: {new_variant!r}")

    # Auto-derive label si no lo pasan
    VARIANT_LABELS = {
        "home": "Local", "away": "Visita", "third": "Tercera",
        "goalkeeper": "Portero", "special": "Especial", "training": "Entrenamiento",
    }
    if not new_variant_label:
        new_variant_label = VARIANT_LABELS.get(new_variant, new_variant.capitalize())

    import audit_db  # type: ignore
    from db import get_conn  # type: ignore

    catalog = audit_db.load_catalog()
    fam = audit_db.get_family(catalog, fid)
    if not fam:
        return _err(f"family {fid!r} no encontrada")

    old_variant = fam.get("variant")
    if old_variant == new_variant:
        return _reply({"ok": True, "msg": "no changes"})

    # Capturar SKUs viejos antes de mutar
    old_skus = [m.get("sku") for m in (fam.get("modelos") or [])]

    fam["variant"] = new_variant
    fam["variant_label"] = new_variant_label

    # Regenerar SKUs de la family
    new_skus = audit_db.generate_skus_for_family(fam)

    # Detectar colisiones cross-family
    all_other_skus = set()
    for other in catalog:
        if other.get("family_id") == fid:
            continue
        for m in (other.get("modelos") or []):
            if m.get("sku"):
                all_other_skus.add(m["sku"])

    # Resolver colisiones con sufijo -X1/-X2/...
    final_new_skus = []
    for sku in new_skus:
        if sku in all_other_skus:
            for n in range(1, 50):
                candidate = f"{sku}-X{n}"
                if candidate not in all_other_skus:
                    sku = candidate
                    break
        final_new_skus.append(sku)
        all_other_skus.add(sku)

    # Apply new SKUs
    for m, new_sku in zip(fam.get("modelos") or [], final_new_skus):
        m["sku"] = new_sku

    # Save catalog
    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Migrate audit DB — solo si hay cambios reales
    migrated = {"audit_decisions": 0, "audit_photo_actions": 0}
    conn = get_conn()
    try:
        for old_sku, new_sku in zip(old_skus, final_new_skus):
            if not old_sku or old_sku == new_sku:
                continue
            # Check no colisión en audit_decisions
            existing = conn.execute(
                "SELECT 1 FROM audit_decisions WHERE family_id = ?", (new_sku,)
            ).fetchone()
            if existing:
                continue  # skip — resolver manualmente
            cur = conn.execute(
                "UPDATE audit_decisions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            migrated["audit_decisions"] += cur.rowcount
            cur = conn.execute(
                "UPDATE audit_photo_actions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            migrated["audit_photo_actions"] += cur.rowcount
        conn.commit()
    finally:
        conn.close()

    _reply({
        "ok": True,
        "old_variant": old_variant,
        "new_variant": new_variant,
        "old_skus": old_skus,
        "new_skus": final_new_skus,
        "migrated": migrated,
    })


def cmd_move_modelo(args):
    """Mueve un modelo de source_fid a target_fid (family existente) o crea una
    new family y mueve el modelo ahí. Regenera SKU, migra audit rows.

    Args:
        source_fid: family_id origen
        source_modelo_idx: índice del modelo en source.modelos[]
        target_fid: si existe — family destino. Si no, se asume create_new.
        new_family: si target_fid no existe, data para crear family nueva:
            {team, season, variant, variant_label, category, meta_country, ...}
        absorb_all: bool — si true, mueve TODOS los modelos de source a target
            (útil cuando source family entera fue mal-nombrada)
    """
    source_fid = args.get("source_fid")
    source_modelo_idx = args.get("source_modelo_idx")
    target_fid = args.get("target_fid")
    new_family_data = args.get("new_family")  # opcional
    absorb_all = bool(args.get("absorb_all", False))

    if not source_fid:
        return _err("source_fid missing")
    if not absorb_all and source_modelo_idx is None:
        return _err("source_modelo_idx missing (unless absorb_all=true)")
    if not target_fid and not new_family_data:
        return _err("target_fid or new_family required")

    import audit_db  # type: ignore
    from db import get_conn  # type: ignore

    catalog = audit_db.load_catalog()
    source_fam = audit_db.get_family(catalog, source_fid)
    if not source_fam:
        return _err(f"source family {source_fid!r} no encontrada")

    source_modelos = source_fam.get("modelos") or []
    if not source_modelos:
        return _err(f"source family {source_fid} sin modelos")

    # Resolver target: usar existing o crear nueva
    if target_fid:
        target_fam = audit_db.get_family(catalog, target_fid)
        if not target_fam:
            return _err(f"target family {target_fid!r} no encontrada")
    else:
        # Crear nueva family
        team = (new_family_data.get("team") or "").strip()
        season = (new_family_data.get("season") or "").strip()
        variant = (new_family_data.get("variant") or "home").lower().strip()
        if not team or not season:
            return _err("new_family requires team + season")

        # Derivar family_id canonical: team slug + season + variant
        import re
        team_slug = re.sub(r"\s+", "-", team.lower())
        team_slug = re.sub(r"[^a-z0-9-]", "", team_slug)
        season_slug = season.replace("/", "-").replace(" ", "-")
        target_fid = f"{team_slug}-{season_slug}-{variant}"

        # Verificar no colisión
        existing = audit_db.get_family(catalog, target_fid)
        if existing:
            return _err(
                f"new_family daría family_id={target_fid!r} que ya existe. "
                f"Usá move a existing en su lugar."
            )

        VARIANT_LABELS = {"home": "Local", "away": "Visita", "third": "Tercera",
                          "goalkeeper": "Portero", "special": "Especial", "training": "Entrenamiento"}
        target_fam = {
            "family_id": target_fid,
            "team": team,
            "season": season,
            "variant": variant,
            "variant_label": new_family_data.get("variant_label") or VARIANT_LABELS.get(variant, variant),
            "category": new_family_data.get("category", "adult"),
            "tier": None,
            "hero_thumbnail": None,
            "gallery": [],
            "primary_modelo_idx": 0,
            "meta_country": new_family_data.get("meta_country"),
            "meta_league": new_family_data.get("meta_league"),
            "meta_confederation": new_family_data.get("meta_confederation"),
            "featured": False,
            "published": False,
            "historia": None,
            "title": None,
            "description": None,
            "sku": None,
            "keywords": [],
            "aliases": [],
            "wc2026_eligible": False,
            "modelos": [],
        }
        catalog.append(target_fam)

    # Decidir qué modelos mover
    if absorb_all:
        modelos_to_move = list(range(len(source_modelos)))
    else:
        if not (0 <= int(source_modelo_idx) < len(source_modelos)):
            return _err(f"source_modelo_idx {source_modelo_idx} OOB")
        modelos_to_move = [int(source_modelo_idx)]

    # Capturar SKUs viejos
    old_skus = [source_modelos[i].get("sku") for i in modelos_to_move]

    # Mover: extract de source (mantener orden original), append a target
    moved_modelos = []
    for idx in sorted(modelos_to_move, reverse=True):  # reverse para no romper indices
        m = source_modelos.pop(idx)
        moved_modelos.append(m)
    moved_modelos.reverse()  # restaurar orden original

    target_modelos = target_fam.get("modelos") or []
    target_modelos.extend(moved_modelos)
    target_fam["modelos"] = target_modelos
    source_fam["modelos"] = source_modelos

    # Regenerar SKUs de target
    new_skus_target = audit_db.generate_skus_for_family(target_fam)

    # Detectar colisiones cross-family (excluyendo source y target)
    all_other_skus = set()
    for other in catalog:
        if other.get("family_id") in (source_fid, target_fid):
            continue
        for m in (other.get("modelos") or []):
            if m.get("sku"):
                all_other_skus.add(m["sku"])

    final_target_skus = []
    for sku in new_skus_target:
        while sku in all_other_skus:
            # Apuntar colisión
            for n in range(1, 50):
                candidate = f"{sku}-X{n}"
                if candidate not in all_other_skus:
                    sku = candidate
                    break
            else:
                return _err(f"collision unresolvable: {sku}")
        final_target_skus.append(sku)
        all_other_skus.add(sku)

    for m, new_sku in zip(target_modelos, final_target_skus):
        m["sku"] = new_sku

    # Si source se quedó vacío y NO es el target, marcar delete-like (dejamos la
    # entrada pero con modelos=[])
    source_left_empty = len(source_modelos) == 0

    # Regenerar SKUs de source si aún tiene modelos
    if not source_left_empty:
        new_source_skus = audit_db.generate_skus_for_family(source_fam)
        for m, new_sku in zip(source_modelos, new_source_skus):
            m["sku"] = new_sku

    # Save catalog
    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Migrar audit DB — SKUs moved get new SKUs
    migrated = {"audit_decisions": 0, "audit_photo_actions": 0}
    # Mapeo: SKUs viejos de modelos movidos → SKUs nuevos en target
    # Los modelos movidos están en target_modelos al final (length len(moved_modelos))
    n_moved = len(moved_modelos)
    moved_new_skus = final_target_skus[-n_moved:] if n_moved > 0 else []

    conn = get_conn()
    try:
        for old_sku, new_sku in zip(old_skus, moved_new_skus):
            if not old_sku or old_sku == new_sku:
                continue
            existing = conn.execute(
                "SELECT 1 FROM audit_decisions WHERE family_id = ?", (new_sku,)
            ).fetchone()
            if existing:
                continue
            cur = conn.execute(
                "UPDATE audit_decisions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            migrated["audit_decisions"] += cur.rowcount
            cur = conn.execute(
                "UPDATE audit_photo_actions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            migrated["audit_photo_actions"] += cur.rowcount
        conn.commit()
    finally:
        conn.close()

    _reply({
        "ok": True,
        "source_fid": source_fid,
        "target_fid": target_fid,
        "source_empty_now": source_left_empty,
        "moved": n_moved,
        "old_skus": old_skus,
        "new_skus": moved_new_skus,
        "migrated": migrated,
    })


def cmd_delete_family(args):
    """Soft-delete family entera: borra todos los SKUs + marca family
    status='deleted' + modelos=[]. Preserva el entry en catalog.json para
    audit trail (mismo pattern que _delete_sku para el último modelo).

    Reglas:
    - published=true → REFUSED (sagrado, requiere unpublish manual primero)
    - audit_decisions: status='deleted' para todos los SKUs (soft)
    - audit_delete_log: insert per-SKU con motivo
    - catalog: fam.status='deleted', fam.modelos=[], fam.published=false
    - commit + push automático (igual que _commit_catalog_delete)

    Args:
      family_id (canonical), motivo (requerido).
    """
    family_id = args.get("family_id")
    motivo = (args.get("motivo") or "").strip()
    if not family_id:
        return _err("family_id missing")
    if not motivo:
        return _err("motivo requerido (explicá por qué se borra la family)")

    import audit_db  # type: ignore
    import audit  # type: ignore
    import os  # type: ignore
    from db import get_conn  # type: ignore

    catalog = audit_db.load_catalog()
    fam = audit_db.get_family(catalog, family_id)
    if not fam:
        return _err(f"family {family_id!r} no existe")

    if fam.get("published") is True:
        return _err(
            f"family {family_id} está publicada (sagrada) — despublicá primero, "
            f"después borrá. Esta guard previene rollback accidental del vault live."
        )

    modelos = fam.get("modelos") or []
    skus = [m.get("sku") for m in modelos if m.get("sku")]
    if not skus and fam.get("sku"):
        skus = [fam["sku"]]

    deleted_skus = []
    delete_log_rows = 0

    conn = get_conn()
    try:
        # Soft-delete cada SKU en audit_decisions + insert audit_delete_log
        for sku in skus:
            cur = conn.execute(
                "UPDATE audit_decisions SET status='deleted', updated_at=datetime('now') "
                "WHERE family_id = ? AND status != 'deleted'",
                (sku,),
            )
            cur = conn.execute(
                "INSERT INTO audit_delete_log (sku, family_id, motivo, deleted_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (sku, family_id, motivo),
            )
            delete_log_rows += cur.rowcount or 0
            deleted_skus.append(sku)
        conn.commit()
    finally:
        conn.close()

    # Marcar family en catalog: status=deleted, modelos vacío, published off
    fam["status"] = "deleted"
    fam["modelos"] = []
    fam["published"] = False
    # Limpiar gallery + hero top-level (UX: family no aparece visualmente)
    fam["gallery"] = []
    fam["hero_thumbnail"] = None

    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Commit + push
    committed = False
    push_error = None
    try:
        repo_dir = os.path.dirname(os.path.dirname(audit_db.CATALOG_PATH))
        msg_motivo = motivo.split("\n")[0][:60]
        commit_msg = f"audit: delete family {family_id} ({len(deleted_skus)} SKUs) — {msg_motivo}"
        subprocess.run(
            ["git", "add", "data/catalog.json"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        push_result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_dir, capture_output=True, timeout=60,
        )
        if push_result.returncode == 0:
            committed = True
        else:
            push_error = push_result.stderr.decode("utf-8", errors="replace")[:200]
    except Exception as e:
        push_error = str(e)[:200]

    _reply({
        "ok": True,
        "family_id": family_id,
        "deleted_skus": deleted_skus,
        "delete_log_rows": delete_log_rows,
        "was_published": False,
        "committed": committed,
        "push_error": push_error,
    })


def cmd_backfill_meta(args):
    """Corre el script backfill_catalog_meta.py para llenar meta_country,
    meta_confederation, wc2026_eligible, primary_modelo_idx, y precios
    default — solo en campos que están null. Idempotente.

    Útil para fixear families recién importadas que aún no recibieron meta,
    o cuando se agregan nuevos aliases a wc2026-classified.json.

    Returns: stats dict con cuántos campos se llenaron.
    """
    import importlib.util  # type: ignore
    import os  # type: ignore

    # Importar el script como módulo (vive en mismo erp/scripts/ folder)
    script_path = os.path.join(os.path.dirname(__file__), "backfill_catalog_meta.py")
    if not os.path.exists(script_path):
        return _err(f"backfill_catalog_meta.py no encontrado en {script_path}")

    spec = importlib.util.spec_from_file_location("backfill_meta", script_path)
    if spec is None or spec.loader is None:
        return _err("no se pudo cargar backfill_catalog_meta.py como módulo")
    mod = importlib.util.module_from_spec(spec)

    # Capturar stdout del script (que printea las stats) y emitirlo limpio
    import io
    import contextlib
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            spec.loader.exec_module(mod)
            mod.main(dry_run=False)
    except Exception as e:
        return _err(f"backfill falló: {e}")

    output = captured.getvalue()
    # Parse las stats del output (formato "  key  N")
    stats = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(("meta_", "wc2026_", "primary_", "prices_", "families_")):
            parts = line.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                stats[parts[0]] = int(parts[-1])

    _reply({
        "ok": True,
        "stats": stats,
        "raw_output": output[-500:],  # last 500 chars para debug si algo raro
    })


def cmd_insert_event(args):
    """Inserta un evento nuevo en comercial_events."""
    import json
    from db import get_conn

    type_ = args.get("type")
    severity = args.get("severity")
    title = args.get("title")
    sub = args.get("sub")
    items = args.get("itemsAffected") or []

    if not type_ or not severity or not title:
        return {"ok": False, "error": "type/severity/title required"}

    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO comercial_events
              (type, severity, title, sub, items_affected_json, detected_at, status)
            VALUES (?, ?, ?, ?, ?, datetime('now'), 'active')
        """, (type_, severity, title, sub, json.dumps(items)))
        conn.commit()
        return {"ok": True, "eventId": cur.lastrowid}
    finally:
        conn.close()


def cmd_list_events(args):
    """Lista eventos de comercial_events con filtros opcionales."""
    import json
    from db import get_conn

    status = args.get("status")          # 'active'|'resolved'|'ignored'|None
    severity = args.get("severity")      # 'crit'|'warn'|'info'|'strat'|None

    conn = get_conn()
    try:
        sql = "SELECT event_id, type, severity, title, sub, items_affected_json, detected_at, status, resolved_at, push_sent FROM comercial_events"
        clauses = []
        params = []
        if status:
            clauses.append("status = ?"); params.append(status)
        if severity:
            clauses.append("severity = ?"); params.append(severity)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE severity WHEN 'crit' THEN 1 WHEN 'warn' THEN 2 WHEN 'info' THEN 3 ELSE 4 END, detected_at DESC"

        rows = conn.execute(sql, params).fetchall()
        events = []
        for r in rows:
            events.append({
                "eventId": r[0],
                "type": r[1],
                "severity": r[2],
                "title": r[3],
                "sub": r[4],
                "itemsAffected": json.loads(r[5] or '[]'),
                "detectedAt": r[6],
                "status": r[7],
                "resolvedAt": r[8],
                "pushSent": bool(r[9]),
            })
        return {"ok": True, "events": events}
    finally:
        conn.close()


def cmd_set_event_status(args):
    """Cambia status de un evento (active/resolved/ignored)."""
    from db import get_conn

    event_id = args.get("eventId")
    status = args.get("status")
    if not event_id or status not in ("active", "resolved", "ignored"):
        return {"ok": False, "error": "eventId/status missing or invalid"}

    conn = get_conn()
    try:
        if status == "resolved":
            conn.execute(
                "UPDATE comercial_events SET status=?, resolved_at=datetime('now') WHERE event_id=?",
                (status, event_id),
            )
        else:
            conn.execute(
                "UPDATE comercial_events SET status=? WHERE event_id=?",
                (status, event_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def cmd_get_order(args):
    """Devuelve OrderForModal para una orden por su ref (CE-XXXX)."""
    from db import get_conn

    ref = args.get("ref")
    if not ref:
        return {"ok": False, "error": "ref missing"}

    conn = get_conn()
    try:
        # NOTA: customers no tiene handle/platform en esta versión del schema.
        # Defaults: handle=null, platform="web". Enriquecimiento desde leads en R6+.
        sale = conn.execute("""
            SELECT s.sale_id, s.ref, s.fulfillment_status, s.occurred_at, s.shipped_at, s.total,
                   s.payment_method, s.notes,
                   c.name, c.phone
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE s.ref = ?
        """, (ref,)).fetchone()

        if not sale:
            return {"ok": True, "order": None}

        sale_id = sale[0]

        # Items
        items = conn.execute("""
            SELECT family_id, jersey_id, size, unit_price, unit_cost, personalization_json
            FROM sale_items
            WHERE sale_id = ?
        """, (sale_id,)).fetchall()

        order = {
            "ref": sale[1],
            "saleId": sale_id,
            "status": sale[2] or "paid",
            "paidAt": sale[3],          # occurred_at = momento del pago
            "shippedAt": sale[4],        # shipped_at = null hasta marcar shipped
            "totalGtq": sale[5],
            "paymentMethod": sale[6] or "recurrente",
            "notes": sale[7],
            "customer": {
                "name": sale[8] or "(sin nombre)",
                "phone": sale[9],
                "handle": None,           # no existe en customers schema (R1)
                "platform": "web",        # default; orden originada via vault/web
            },
            "items": [
                {
                    "familyId": i[0],
                    "jerseySku": i[1],     # jersey_id en DB; jerseySku en API
                    "size": i[2],
                    "unitPriceGtq": i[3],
                    "unitCostGtq": i[4],
                    "personalizationJson": i[5],
                }
                for i in items
            ],
        }
        return {"ok": True, "order": order}
    finally:
        conn.close()


def cmd_mark_order_shipped(args):
    """Marca orden como shipped, opcionalmente con tracking_code."""
    from db import get_conn

    ref = args.get("ref")
    tracking = args.get("trackingCode")
    if not ref:
        return {"ok": False, "error": "ref missing"}

    conn = get_conn()
    try:
        if tracking:
            conn.execute(
                "UPDATE sales SET fulfillment_status='shipped', shipped_at=datetime('now'), tracking_code=? WHERE ref=?",
                (tracking, ref),
            )
        else:
            conn.execute(
                "UPDATE sales SET fulfillment_status='shipped', shipped_at=datetime('now') WHERE ref=?",
                (ref,),
            )

        # También resolver el evento order_pending_24h asociado si existe
        conn.execute("""
            UPDATE comercial_events
            SET status='resolved', resolved_at=datetime('now')
            WHERE type='order_pending_24h' AND status='active'
              AND items_affected_json LIKE '%' || ? || '%'
        """, (ref,))
        conn.commit()
        return {"ok": True, "ref": ref}
    finally:
        conn.close()


def cmd_list_sales_in_range(args):
    """Lista sales con paid_at entre start y end."""
    from db import get_conn
    start = args.get("start")
    end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ref, total, occurred_at, fulfillment_status FROM sales WHERE occurred_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "sales": [{"ref": r[0], "totalGtq": r[1], "paidAt": r[2], "status": r[3]} for r in rows]
        }
    finally:
        conn.close()


def cmd_list_leads_in_range(args):
    """Lista leads con first_contact_at entre start y end."""
    from db import get_conn
    start = args.get("start"); end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT lead_id, first_contact_at FROM leads WHERE first_contact_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "leads": [{"leadId": r[0], "firstContactAt": r[1]} for r in rows]
        }
    finally:
        conn.close()


def cmd_list_ad_spend_in_range(args):
    """Lista ad spend snapshots entre start y end."""
    from db import get_conn
    start = args.get("start"); end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT campaign_id, spend_gtq, captured_at FROM campaigns_snapshot WHERE captured_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "adSpend": [{"campaignId": r[0], "spendGtq": r[1], "capturedAt": r[2]} for r in rows]
        }
    finally:
        conn.close()


def cmd_sync_manychat(args):
    """Pull data desde el worker y upsertea leads + conversations.
    Args:
        since: ISO string o null (full backfill)
        worker_base: URL del worker
        dashboard_key: bearer token
    Returns:
        {ok, leadsUpserted, conversationsUpserted, lastSyncAt}
    """
    import json
    import urllib.request
    from db import get_conn

    since = args.get("since")
    worker_base = args.get("workerBase") or "https://ventus-backoffice.ventusgt.workers.dev"
    dashboard_key = args.get("dashboardKey")

    if not dashboard_key:
        return {"ok": False, "error": "dashboardKey required"}

    qs = f"?since={since}" if since else ""
    url = f"{worker_base}/api/comercial/sync-data{qs}"

    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {dashboard_key}",
            "User-Agent": "ElClub-ERP/0.1.29",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except Exception as e:
        return {"ok": False, "error": f"worker fetch failed: {e}"}

    leads_data = data.get("leads", [])
    convs_data = data.get("conversations", [])
    now_iso = data.get("until") or args.get("now") or ""

    conn = get_conn()
    leads_upserted = 0
    convs_upserted = 0
    try:
        # Upsert leads (UNIQUE composite (platform, sender_id))
        for ld in leads_data:
            try:
                conn.execute("""
                    INSERT INTO leads
                      (name, handle, phone, platform, sender_id, source_campaign_id,
                       first_contact_at, last_activity_at, status, traits_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, sender_id) DO UPDATE SET
                      name = COALESCE(excluded.name, leads.name),
                      handle = COALESCE(excluded.handle, leads.handle),
                      phone = COALESCE(excluded.phone, leads.phone),
                      source_campaign_id = COALESCE(excluded.source_campaign_id, leads.source_campaign_id),
                      first_contact_at = MIN(leads.first_contact_at, excluded.first_contact_at),
                      last_activity_at = MAX(leads.last_activity_at, excluded.last_activity_at),
                      status = excluded.status
                """, (
                    ld.get("name"), ld.get("handle"), ld.get("phone"),
                    ld.get("platform"), ld.get("senderId"),
                    ld.get("sourceCampaignId"),
                    ld.get("firstContactAt"), ld.get("lastActivityAt"),
                    ld.get("status") or "new",
                    json.dumps(ld.get("traitsJson") or {}),
                ))
                leads_upserted += 1
            except Exception as e:
                print(f"[sync_manychat] lead upsert failed: {e}", flush=True)

        # Build (platform, sender_id) -> lead_id lookup
        lead_lookup = {}
        for row in conn.execute("SELECT lead_id, platform, sender_id FROM leads").fetchall():
            lead_lookup[(row[1], row[2])] = row[0]

        # Upsert conversations (PK conv_id)
        for cv in convs_data:
            try:
                conn.execute("""
                    INSERT INTO conversations
                      (conv_id, brand, platform, sender_id, started_at, ended_at,
                       outcome, order_id, messages_total, messages_json, tags_json,
                       analyzed, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, datetime('now'))
                    ON CONFLICT(conv_id) DO UPDATE SET
                      ended_at = excluded.ended_at,
                      outcome = excluded.outcome,
                      order_id = excluded.order_id,
                      messages_total = excluded.messages_total,
                      tags_json = excluded.tags_json,
                      analyzed = excluded.analyzed,
                      synced_at = datetime('now')
                """, (
                    cv.get("convId"), cv.get("brand"), cv.get("platform"),
                    cv.get("senderId"), cv.get("startedAt"), cv.get("endedAt"),
                    cv.get("outcome"), cv.get("orderId"), cv.get("messagesTotal", 0),
                    json.dumps(cv.get("tagsJson") or []),
                    1 if cv.get("analyzed") else 0,
                ))
                convs_upserted += 1
            except Exception as e:
                print(f"[sync_manychat] conv upsert failed: {e}", flush=True)

        # Update meta_sync
        conn.execute("""
            INSERT INTO meta_sync (source, last_sync_at, last_status, last_error)
            VALUES ('manychat', datetime('now'), 'ok', NULL)
            ON CONFLICT(source) DO UPDATE SET
              last_sync_at = datetime('now'),
              last_status = 'ok',
              last_error = NULL
        """)
        conn.commit()
        return {
            "ok": True,
            "leadsUpserted": leads_upserted,
            "conversationsUpserted": convs_upserted,
            "lastSyncAt": now_iso,
        }
    finally:
        conn.close()


def cmd_list_leads(args):
    """Lista leads con filtros opcionales por status y range."""
    import json
    from db import get_conn

    status = args.get("status")
    range_start = args.get("rangeStart")
    range_end = args.get("rangeEnd")

    sql = "SELECT lead_id, name, handle, phone, platform, sender_id, source_campaign_id, first_contact_at, last_activity_at, status, traits_json FROM leads"
    clauses = []
    params = []
    if status:
        clauses.append("status = ?"); params.append(status)
    if range_start and range_end:
        clauses.append("first_contact_at BETWEEN ? AND ?")
        params.extend([range_start, range_end])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY last_activity_at DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        leads = []
        for r in rows:
            try:
                traits = json.loads(r[10] or '{}')
            except Exception:
                traits = {}
            leads.append({
                "leadId": r[0], "name": r[1], "handle": r[2], "phone": r[3],
                "platform": r[4], "senderId": r[5], "sourceCampaignId": r[6],
                "firstContactAt": r[7], "lastActivityAt": r[8], "status": r[9],
                "traitsJson": traits,
            })
        return {"ok": True, "leads": leads}
    finally:
        conn.close()


def cmd_list_conversations(args):
    """Lista conversations con filtros opcionales."""
    import json
    from db import get_conn

    outcome = args.get("outcome")
    range_start = args.get("rangeStart")
    range_end = args.get("rangeEnd")
    lead_id = args.get("leadId")

    sql = """
        SELECT c.conv_id, l.lead_id, c.brand, c.platform, c.sender_id,
               c.started_at, c.ended_at, c.outcome, c.order_id, c.messages_total,
               c.tags_json, c.analyzed, c.synced_at
        FROM conversations c
        LEFT JOIN leads l ON l.platform = c.platform AND l.sender_id = c.sender_id
    """
    clauses = []
    params = []
    if outcome:
        clauses.append("c.outcome = ?"); params.append(outcome)
    if range_start and range_end:
        clauses.append("c.started_at BETWEEN ? AND ?")
        params.extend([range_start, range_end])
    if lead_id:
        clauses.append("l.lead_id = ?"); params.append(lead_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.ended_at DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        convs = []
        for r in rows:
            try:
                tags = json.loads(r[10] or '[]')
            except Exception:
                tags = []
            convs.append({
                "convId": r[0], "leadId": r[1], "brand": r[2], "platform": r[3],
                "senderId": r[4], "startedAt": r[5], "endedAt": r[6],
                "outcome": r[7], "orderId": r[8], "messagesTotal": r[9],
                "tagsJson": tags, "analyzed": bool(r[11]), "syncedAt": r[12],
            })
        return {"ok": True, "conversations": convs}
    finally:
        conn.close()


def cmd_list_customers(args):
    """Lista customers con totals computados (totalOrders, totalRevenueGtq, lastOrderAt)."""
    from db import get_conn

    last_order_before = args.get("lastOrderBefore")
    min_ltv_gtq = args.get("minLtvGtq")

    sql = """
        SELECT c.customer_id, c.name, c.phone, c.email, c.source, c.first_order_at,
               COUNT(s.sale_id) AS total_orders,
               COALESCE(SUM(s.total), 0) AS total_revenue,
               MAX(s.occurred_at) AS last_order_at
        FROM customers c
        LEFT JOIN sales s ON s.customer_id = c.customer_id
        GROUP BY c.customer_id
    """
    having = []
    params = []
    if last_order_before:
        having.append("last_order_at < ?"); params.append(last_order_before)
    if min_ltv_gtq is not None:
        having.append("total_revenue >= ?"); params.append(min_ltv_gtq)
    if having:
        sql += " HAVING " + " AND ".join(having)
    sql += " ORDER BY total_revenue DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        customers = [{
            "customerId": r[0], "name": r[1] or "(sin nombre)", "phone": r[2],
            "email": r[3], "source": r[4], "firstOrderAt": r[5] or "",
            "totalOrders": r[6], "totalRevenueGtq": r[7], "lastOrderAt": r[8],
        } for r in rows]
        return {"ok": True, "customers": customers}
    finally:
        conn.close()


def cmd_get_meta_sync(args):
    """Devuelve el último estado de sync para una source."""
    from db import get_conn

    source = args.get("source") or "manychat"
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT source, last_sync_at, last_status, last_error FROM meta_sync WHERE source = ?",
            (source,)
        ).fetchone()
        if not row:
            return {"ok": True, "metaSync": {"source": source, "lastSyncAt": None, "lastStatus": None, "lastError": None}}
        return {"ok": True, "metaSync": {
            "source": row[0], "lastSyncAt": row[1], "lastStatus": row[2], "lastError": row[3]
        }}
    finally:
        conn.close()


def cmd_get_conversation_messages(args):
    """Lazy fetch de mensajes desde el worker."""
    import json
    import urllib.request
    import urllib.error

    conv_id = args.get("convId")
    worker_base = args.get("workerBase") or "https://ventus-backoffice.ventusgt.workers.dev"
    dashboard_key = args.get("dashboardKey")

    if not conv_id:
        return {"ok": False, "error": "convId required"}
    if not dashboard_key:
        return {"ok": False, "error": "dashboardKey required"}

    url = f"{worker_base}/api/comercial/conversation/{conv_id}/messages"
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {dashboard_key}",
            "User-Agent": "ElClub-ERP/0.1.29",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        return {"ok": True, "messages": data.get("messages", [])}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "messages": [], "note": "purged_or_missing"}
        return {"ok": False, "error": f"worker http {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}


# ──────────────────────────────────────────────────────────────────────────────
# Comercial R4 — Customer CRUD + Manual Order
# ──────────────────────────────────────────────────────────────────────────────

def cmd_get_customer_profile(args):
    """Devuelve CustomerProfile completo: customer + computed totals + timeline."""
    import json
    from db import get_conn

    customer_id = args.get("customerId")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}

    conn = get_conn()
    try:
        # Base customer
        c = conn.execute("""
            SELECT customer_id, name, phone, email, source, first_order_at, tags_json,
                   COALESCE(blocked, 0) AS blocked
            FROM customers WHERE customer_id = ?
        """, (customer_id,)).fetchone()
        if not c:
            return {"ok": True, "profile": None}

        # Computed totals from sales
        totals = conn.execute("""
            SELECT COUNT(sale_id), COALESCE(SUM(total), 0), MAX(occurred_at)
            FROM sales WHERE customer_id = ?
        """, (customer_id,)).fetchone()
        total_orders = totals[0]
        total_revenue = totals[1]
        last_order_at = totals[2]

        is_vip = total_revenue >= 1500
        days_inactive = None
        if last_order_at:
            from datetime import datetime
            try:
                last_dt = datetime.fromisoformat(last_order_at.replace('Z', '+00:00').replace(' ', 'T'))
                days_inactive = (datetime.now() - last_dt.replace(tzinfo=None)).days
            except Exception:
                days_inactive = None

        # Attribution: lookup conversations matching customer's phone
        lead_campaigns = []
        if c[2]:  # phone
            rows = conn.execute("""
                SELECT DISTINCT source_campaign_id FROM leads
                WHERE phone = ? AND source_campaign_id IS NOT NULL
            """, (c[2],)).fetchall()
            lead_campaigns = [r[0] for r in rows]

        # Timeline: orders + conversations merged by date DESC
        timeline = []
        sales_rows = conn.execute("""
            SELECT s.ref, s.total, s.fulfillment_status, s.occurred_at,
                   (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id = s.sale_id) AS items_count
            FROM sales s WHERE s.customer_id = ?
            ORDER BY s.occurred_at DESC
        """, (customer_id,)).fetchall()
        for r in sales_rows:
            timeline.append({
                "kind": "order",
                "ref": r[0], "totalGtq": r[1], "status": r[2] or "pending",
                "occurredAt": r[3], "itemsCount": r[4],
            })

        # Conversations: join by phone (best-effort)
        if c[2]:
            conv_rows = conn.execute("""
                SELECT DISTINCT c.conv_id, c.platform, c.outcome, c.messages_total, c.ended_at
                FROM conversations c
                JOIN leads l ON l.platform = c.platform AND l.sender_id = c.sender_id
                WHERE l.phone = ?
                ORDER BY c.ended_at DESC
            """, (c[2],)).fetchall()
            for r in conv_rows:
                timeline.append({
                    "kind": "conversation",
                    "convId": r[0], "platform": r[1], "outcome": r[2],
                    "messagesTotal": r[3], "endedAt": r[4],
                })

        # Re-sort merged timeline by date DESC
        def get_ts(entry):
            return entry.get("occurredAt") or entry.get("endedAt") or ""
        timeline.sort(key=get_ts, reverse=True)

        try:
            traits = json.loads(c[6] or '{}')
            if not isinstance(traits, dict):
                traits = {}  # normalize legacy '[]' default
        except Exception:
            traits = {}

        profile = {
            "customerId": c[0],
            "name": c[1] or "(sin nombre)",
            "phone": c[2],
            "email": c[3],
            "source": c[4],
            "firstOrderAt": c[5],   # NULLABLE — pass through raw value, do NOT mask with or ''
            "totalOrders": total_orders,
            "totalRevenueGtq": total_revenue,
            "lastOrderAt": last_order_at,
            "isVip": is_vip,
            "daysInactive": days_inactive,
            "blocked": bool(c[7]),
            "traitsJson": traits,
            "attribution": {
                "customerSource": c[4],
                "leadCampaigns": lead_campaigns,
            },
            "timeline": timeline,
        }
        return {"ok": True, "profile": profile}
    finally:
        conn.close()


def cmd_create_customer(args):
    """Crea un customer manual (no asociado a sale automático)."""
    from db import get_conn

    name = args.get("name")
    if not name or not name.strip():
        return {"ok": False, "error": "name required"}

    phone = args.get("phone")
    email = args.get("email")
    source = args.get("source") or "manual"

    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO customers (name, phone, email, source, first_order_at, created_at)
            VALUES (?, ?, ?, ?, NULL, datetime('now', 'localtime'))
        """, (name.strip(), phone, email, source))
        conn.commit()
        return {"ok": True, "customerId": cur.lastrowid}
    finally:
        conn.close()


def cmd_update_customer_traits(args):
    """Actualiza customers.tags_json con un objeto JSON."""
    import json
    from db import get_conn

    customer_id = args.get("customerId")
    traits = args.get("traitsJson")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}
    if traits is None:
        return {"ok": False, "error": "traitsJson required"}

    if not isinstance(traits, dict):
        return {"ok": False, "error": "traitsJson must be an object"}

    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE customers SET tags_json = ? WHERE customer_id = ?",
            (json.dumps(traits), customer_id),
        )
        if cur.rowcount == 0:
            return {"ok": False, "error": f"customer {customer_id} not found"}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def cmd_set_customer_blocked(args):
    """Toggle blocked en customers."""
    from db import get_conn

    customer_id = args.get("customerId")
    blocked = args.get("blocked")
    if not customer_id or blocked is None:
        return {"ok": False, "error": "customerId/blocked required"}

    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE customers SET blocked = ? WHERE customer_id = ?",
            (1 if blocked else 0, customer_id),
        )
        if cur.rowcount == 0:
            return {"ok": False, "error": f"customer {customer_id} not found"}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def cmd_update_customer_source(args):
    """Actualiza customers.source manualmente."""
    from db import get_conn

    customer_id = args.get("customerId")
    source = args.get("source")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}

    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE customers SET source = ? WHERE customer_id = ?",
            (source, customer_id),
        )
        if cur.rowcount == 0:
            return {"ok": False, "error": f"customer {customer_id} not found"}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def cmd_create_manual_order(args):
    """Crea una venta manual (off-platform). INSERT sale + INSERT sale_items.
    Genera ref CE-XXXX random con retry en caso de colisión.

    DB constraints (CHECK):
      modality: 'mystery'|'stock'|'ondemand' — manual orders use 'stock'
      payment_method: 'recurrente'|'transferencia'|'contra_entrega'|'efectivo'|'otro'
      fulfillment_status: 'pending'|'sent_to_supplier'|'in_production'|'shipped'|'delivered'|'cancelled'
    """
    import json
    import secrets
    import string
    import sqlite3 as sqlite3_mod
    from db import get_conn

    customer_id = args.get("customerId")
    items = args.get("items") or []
    payment_method = args.get("paymentMethod") or "transferencia"
    fulfillment_status = args.get("fulfillmentStatus") or "pending"
    shipping_fee = args.get("shippingFee") or 0
    discount = args.get("discount") or 0
    notes = args.get("notes")

    if not customer_id:
        return {"ok": False, "error": "customerId required"}
    if not items:
        return {"ok": False, "error": "at least 1 item required"}

    # Validate each item
    for i, item in enumerate(items):
        if not item.get("familyId") or not item.get("jerseyId"):
            return {"ok": False, "error": f"item[{i}] missing familyId/jerseyId"}
        if not item.get("size"):
            return {"ok": False, "error": f"item[{i}] missing size"}
        unit_price = item.get("unitPrice")
        if unit_price is None or unit_price <= 0:
            return {"ok": False, "error": f"item[{i}] unitPrice must be > 0"}

    # DB-valid enums (CHECK constraints in sales table)
    valid_payment = ("recurrente", "transferencia", "contra_entrega", "efectivo", "otro")
    valid_fulfillment = ("pending", "sent_to_supplier", "in_production", "shipped", "delivered", "cancelled")
    if payment_method not in valid_payment:
        return {"ok": False, "error": f"invalid paymentMethod. Valid: {valid_payment}"}
    if fulfillment_status not in valid_fulfillment:
        return {"ok": False, "error": f"invalid fulfillmentStatus. Valid: {valid_fulfillment}"}

    subtotal = sum(item["unitPrice"] for item in items)
    total = subtotal + shipping_fee - discount

    if total <= 0:
        return {"ok": False, "error": "total must be > 0"}

    conn = get_conn()
    try:
        # Validate customer exists
        c = conn.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if not c:
            return {"ok": False, "error": f"customer {customer_id} not found"}

        # Generate ref with retry on UNIQUE collision (extremely rare)
        ref = None
        sale_id = None
        for attempt in range(5):
            candidate = "CE-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            try:
                cur = conn.execute("""
                    INSERT INTO sales
                      (ref, occurred_at, modality, origin, customer_id, payment_method,
                       fulfillment_status, shipping_method, tracking_code, subtotal, shipping_fee,
                       discount, total, source_vault_ref, notes, created_at)
                    VALUES (?, datetime('now', 'localtime'), 'stock', 'manual', ?, ?, ?, NULL, NULL,
                            ?, ?, ?, ?, NULL, ?, datetime('now', 'localtime'))
                """, (candidate, customer_id, payment_method, fulfillment_status,
                      subtotal, shipping_fee, discount, total, notes))
                ref = candidate
                sale_id = cur.lastrowid
                break
            except sqlite3_mod.IntegrityError:
                continue

        if ref is None:
            return {"ok": False, "error": "ref collision after 5 retries"}

        # Insert items
        for item in items:
            conn.execute("""
                INSERT INTO sale_items
                  (sale_id, family_id, jersey_id, team, season, variant_label, version, size,
                   personalization_json, unit_price, unit_cost, notes, import_id, item_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """, (
                sale_id,
                item.get("familyId"),
                item.get("jerseyId"),
                item.get("team"),
                None,  # season — not in R4 form
                item.get("variantLabel"),
                item.get("version"),
                item.get("size"),
                item.get("personalizationJson"),
                item.get("unitPrice"),
                item.get("unitCost"),
                item.get("itemType") or "manual",
            ))

        conn.commit()

        # R6: auto-attribute via phone → lead.source_campaign_id lookup
        try:
            cust_phone = conn.execute("SELECT phone FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
            if cust_phone and cust_phone[0]:
                lead = conn.execute("""
                    SELECT source_campaign_id FROM leads
                    WHERE phone = ? AND source_campaign_id IS NOT NULL
                    ORDER BY first_contact_at DESC LIMIT 1
                """, (cust_phone[0],)).fetchone()
                if lead:
                    cn_row = conn.execute("""
                        SELECT campaign_name FROM campaigns_snapshot
                        WHERE campaign_id = ? AND campaign_name IS NOT NULL
                        ORDER BY captured_at DESC LIMIT 1
                    """, (lead[0],)).fetchone()
                    campaign_name = cn_row[0] if cn_row else None
                    conn.execute("""
                        INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, created_at)
                        VALUES (?, ?, ?, 'auto_via_lead', datetime('now', 'localtime'))
                    """, (sale_id, lead[0], campaign_name))
                    conn.commit()
        except Exception:
            # Don't fail sale creation on attribution error — attribution is best-effort
            pass

        return {"ok": True, "ref": ref, "saleId": sale_id}
    finally:
        conn.close()


# ─── R6: Sales attribution ────────────────────────────────────────────────────

def cmd_backfill_sales_attribution(args):
    """Backfill retroactivo: for each sale without attribution, lookup phone → lead.source_campaign_id.
    Idempotent — skips sales that already have attribution rows.
    Campaign name fetched from campaigns_snapshot (R5).
    """
    from db import get_conn

    conn = get_conn()
    inserted = 0
    skipped_no_match = 0
    errors = []

    try:
        # Find sales without attribution AND with customer phone
        sales = conn.execute("""
            SELECT s.sale_id, c.phone
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE NOT EXISTS (SELECT 1 FROM sales_attribution sa WHERE sa.sale_id = s.sale_id)
              AND c.phone IS NOT NULL AND c.phone != ''
        """).fetchall()

        for sale_id, phone in sales:
            try:
                # Find most recent lead with source_campaign_id matching this phone
                lead = conn.execute("""
                    SELECT source_campaign_id
                    FROM leads
                    WHERE phone = ? AND source_campaign_id IS NOT NULL
                    ORDER BY first_contact_at DESC
                    LIMIT 1
                """, (phone,)).fetchone()
                if not lead:
                    skipped_no_match += 1
                    continue

                campaign_id = lead[0]

                # Fetch campaign name from campaigns_snapshot (R5 added campaign_name col)
                cn_row = conn.execute("""
                    SELECT campaign_name FROM campaigns_snapshot
                    WHERE campaign_id = ? AND campaign_name IS NOT NULL
                    ORDER BY captured_at DESC LIMIT 1
                """, (campaign_id,)).fetchone()
                campaign_name = cn_row[0] if cn_row else None

                conn.execute("""
                    INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, created_at)
                    VALUES (?, ?, ?, 'auto_via_lead', datetime('now', 'localtime'))
                """, (sale_id, campaign_id, campaign_name))
                inserted += 1
            except Exception as ie:
                errors.append(f"sale {sale_id}: {ie}")

        skipped_already_attributed = conn.execute("""
            SELECT COUNT(*) FROM sales s WHERE EXISTS (
                SELECT 1 FROM sales_attribution sa WHERE sa.sale_id = s.sale_id
            )
        """).fetchone()[0]

        conn.commit()
        return {
            "ok": True,
            "inserted": inserted,
            "skippedNoMatch": skipped_no_match,
            "skippedAlreadyAttributed": skipped_already_attributed,
            "errors": errors
        }
    finally:
        conn.close()


def cmd_get_sale_attribution(args):
    """Returns attribution row for a sale, or null."""
    from db import get_conn

    sale_id = args.get("saleId")
    if not sale_id:
        return {"ok": False, "error": "saleId required"}

    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT id, sale_id, ad_campaign_id, ad_campaign_name, source, note, created_at
            FROM sales_attribution WHERE sale_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (sale_id,)).fetchone()
        if not row:
            return {"ok": True, "attribution": None}
        return {"ok": True, "attribution": {
            "id": row[0],
            "saleId": row[1],
            "adCampaignId": row[2],
            "adCampaignName": row[3],
            "source": row[4],
            "note": row[5],
            "createdAt": row[6],
        }}
    finally:
        conn.close()


def cmd_get_conversation_meta(args):
    """Fetch full ConversationMeta from conversations table by convId."""
    from db import get_conn

    conv_id = args.get("convId")
    if not conv_id:
        return {"ok": False, "error": "convId required"}

    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT conv_id, lead_id, brand, platform, sender_id, started_at, ended_at,
                   outcome, order_id, messages_total, tags_json, analyzed, synced_at
            FROM conversations WHERE conv_id = ?
        """, (conv_id,)).fetchone()
        if not row:
            return {"ok": True, "conversation": None}
        import json as _json
        try:
            tags = _json.loads(row[10] or '[]')
        except Exception:
            tags = []
        return {"ok": True, "conversation": {
            "convId": row[0],
            "leadId": row[1],
            "brand": row[2],
            "platform": row[3],
            "senderId": row[4] or '',
            "startedAt": row[5] or '',
            "endedAt": row[6] or '',
            "outcome": row[7],
            "orderId": row[8],
            "messagesTotal": row[9] or 0,
            "tagsJson": tags,
            "analyzed": bool(row[11]),
            "syncedAt": row[12] or '',
        }}
    finally:
        conn.close()


def cmd_attribute_sale(args):
    """Manual attribution: upsert sales_attribution for a sale + campaign."""
    from db import get_conn

    sale_id = args.get("saleId")
    campaign_id = args.get("campaignId")
    note = args.get("note")
    if not sale_id:
        return {"ok": False, "error": "saleId required"}

    conn = get_conn()
    try:
        # Lookup campaign name from latest snapshot
        campaign_name = None
        if campaign_id:
            cn_row = conn.execute("""
                SELECT campaign_name FROM campaigns_snapshot
                WHERE campaign_id = ? AND campaign_name IS NOT NULL
                ORDER BY captured_at DESC LIMIT 1
            """, (campaign_id,)).fetchone()
            campaign_name = cn_row[0] if cn_row else None

        # Replace any existing attribution (1 sale = 1 attribution by convention)
        conn.execute("DELETE FROM sales_attribution WHERE sale_id = ?", (sale_id,))
        if campaign_id:
            conn.execute("""
                INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, note, created_at)
                VALUES (?, ?, ?, 'manual', ?, datetime('now', 'localtime'))
            """, (sale_id, campaign_id, campaign_name, note))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ─── R5: Meta Ads sync + campaigns + funnel awareness + cupón stub ───────────

def cmd_sync_meta_ads(args):
    """Sync campaigns insights desde Meta Ads API → campaigns_snapshot.
    Reads token + account_id from /c/Users/Diego/club-coo/ads/.env.
    Inserts one row per campaign per sync (history-preserving).
    Account currency is GTQ — no conversion needed.
    Conversions count: purchase + onsite_conversion.total_messaging_connection + lead.
    """
    import json, urllib.request, urllib.parse, urllib.error
    from pathlib import Path
    from datetime import datetime
    from db import get_conn

    env_path = Path(r"C:/Users/Diego/club-coo/ads/.env")
    if not env_path.exists():
        return {"ok": False, "campaignsSynced": 0, "errors": [f".env not found at {env_path}"], "syncedAt": datetime.now().isoformat()}

    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    token = env.get("META_ACCESS_TOKEN")
    account_id = env.get("META_AD_ACCOUNT_ID")
    if not token or not account_id:
        return {"ok": False, "campaignsSynced": 0, "errors": ["META_ACCESS_TOKEN or META_AD_ACCOUNT_ID missing"], "syncedAt": datetime.now().isoformat()}

    days = args.get("days") or 30
    period = args.get("datePreset") or f"last_{days}d"

    url = f"https://graph.facebook.com/v21.0/{account_id}/insights"
    params = {
        "fields": "campaign_id,campaign_name,spend,impressions,clicks,actions,action_values",
        "level": "campaign",
        "date_preset": period,
        "access_token": token,
    }
    qs = urllib.parse.urlencode(params)

    sync_ts = datetime.now().isoformat()
    try:
        req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": "ElClub-ERP/0.1.31"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        if e.code == 429:
            return {"ok": False, "campaignsSynced": 0, "errors": [f"Rate limited (HTTP 429): {body}"], "syncedAt": sync_ts}
        return {"ok": False, "campaignsSynced": 0, "errors": [f"Meta HTTP {e.code}: {body}"], "syncedAt": sync_ts}
    except Exception as e:
        return {"ok": False, "campaignsSynced": 0, "errors": [f"Meta fetch failed: {e}"], "syncedAt": sync_ts}

    rows = data.get("data") or []
    if not rows:
        return {"ok": True, "campaignsSynced": 0, "errors": [], "syncedAt": sync_ts}

    CONVERSION_TYPES = {"purchase", "onsite_conversion.total_messaging_connection", "lead"}
    conn = get_conn()
    synced = 0
    errors = []

    try:
        for row in rows:
            try:
                campaign_id = row.get("campaign_id")
                campaign_name = row.get("campaign_name")
                spend_gtq = float(row.get("spend", 0) or 0)
                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)

                conversions = 0
                revenue_gtq = 0.0
                for a in row.get("actions", []) or []:
                    if a.get("action_type") in CONVERSION_TYPES:
                        conversions += int(a.get("value", 0))
                for av in row.get("action_values", []) or []:
                    if av.get("action_type") == "purchase":
                        revenue_gtq += float(av.get("value", 0))

                conn.execute("""
                    INSERT INTO campaigns_snapshot
                      (campaign_id, campaign_name, captured_at, impressions, clicks,
                       spend_gtq, conversions, revenue_attributed_gtq, raw_json)
                    VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?)
                """, (campaign_id, campaign_name, impressions, clicks,
                      round(spend_gtq, 2), conversions, round(revenue_gtq, 2), json.dumps(row)))
                synced += 1
            except Exception as ie:
                errors.append(f"row {row.get('campaign_id', '?')}: {ie}")
        conn.commit()
        return {"ok": True, "campaignsSynced": synced, "errors": errors, "syncedAt": sync_ts}
    finally:
        conn.close()


def cmd_list_campaigns(args):
    """Lista campañas con rollup últimos N días (default 30)."""
    from db import get_conn

    days = int(args.get("periodDays") or 30)
    conn = get_conn()
    try:
        rows = conn.execute(f"""
            SELECT
                campaign_id,
                MAX(campaign_name) AS campaign_name,
                MAX(captured_at) AS last_sync_at,
                COALESCE(SUM(spend_gtq), 0) AS total_spend,
                COALESCE(SUM(impressions), 0) AS total_impressions,
                COALESCE(SUM(clicks), 0) AS total_clicks,
                COALESCE(SUM(conversions), 0) AS total_conversions,
                COALESCE(SUM(revenue_attributed_gtq), 0) AS total_revenue
            FROM campaigns_snapshot
            WHERE captured_at >= datetime('now', 'localtime', '-{days} days')
            GROUP BY campaign_id
            ORDER BY total_spend DESC
        """).fetchall()
        out = []
        for r in rows:
            cpc = round(r[3] / r[6], 2) if r[6] else None
            out.append({
                "campaignId": r[0],
                "campaignName": r[1],
                "lastSyncAt": r[2],
                "totalSpendGtq": r[3],
                "totalImpressions": r[4],
                "totalClicks": r[5],
                "totalConversions": r[6],
                "totalRevenueGtq": r[7],
                "costPerConversionGtq": cpc,
                "status": "active",
            })
        return {"ok": True, "campaigns": out}
    finally:
        conn.close()


def cmd_get_campaign_detail(args):
    """Campaign detail + daily series + attributed sales (joined via sales_attribution)."""
    from db import get_conn

    campaign_id = args.get("campaignId")
    days = int(args.get("periodDays") or 30)
    if not campaign_id:
        return {"ok": False, "error": "campaignId required"}

    conn = get_conn()
    try:
        agg = conn.execute(f"""
            SELECT
                MAX(campaign_name),
                MAX(captured_at),
                COALESCE(SUM(spend_gtq), 0),
                COALESCE(SUM(impressions), 0),
                COALESCE(SUM(clicks), 0),
                COALESCE(SUM(conversions), 0),
                COALESCE(SUM(revenue_attributed_gtq), 0)
            FROM campaigns_snapshot
            WHERE campaign_id = ?
              AND captured_at >= datetime('now', 'localtime', '-{days} days')
        """, (campaign_id,)).fetchone()

        if agg[1] is None:
            return {"ok": True, "detail": None}

        cpc = round(agg[2] / agg[5], 2) if agg[5] else None
        campaign = {
            "campaignId": campaign_id,
            "campaignName": agg[0],
            "lastSyncAt": agg[1],
            "totalSpendGtq": agg[2],
            "totalImpressions": agg[3],
            "totalClicks": agg[4],
            "totalConversions": agg[5],
            "totalRevenueGtq": agg[6],
            "costPerConversionGtq": cpc,
            "status": "active",
        }

        daily_rows = conn.execute(f"""
            SELECT
                date(captured_at) AS day,
                SUM(spend_gtq), SUM(conversions), SUM(revenue_attributed_gtq),
                SUM(impressions), SUM(clicks)
            FROM campaigns_snapshot
            WHERE campaign_id = ?
              AND captured_at >= datetime('now', 'localtime', '-{days} days')
            GROUP BY day
            ORDER BY day ASC
        """, (campaign_id,)).fetchall()
        daily = [
            {"date": r[0], "spendGtq": r[1], "conversions": r[2], "revenueGtq": r[3],
             "impressions": r[4], "clicks": r[5]}
            for r in daily_rows
        ]

        sales_rows = conn.execute("""
            SELECT s.sale_id, s.ref, c.name, s.total, s.occurred_at
            FROM sales_attribution sa
            JOIN sales s ON s.sale_id = sa.sale_id
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE sa.ad_campaign_id = ?
            ORDER BY s.occurred_at DESC
            LIMIT 50
        """, (campaign_id,)).fetchall()
        attributed = [
            {"saleId": r[0], "ref": r[1], "customerName": r[2], "totalGtq": r[3], "occurredAt": r[4]}
            for r in sales_rows
        ]

        return {"ok": True, "detail": {"campaign": campaign, "daily": daily, "attributedSales": attributed}}
    finally:
        conn.close()


def cmd_get_funnel_awareness_real(args):
    """Funnel Awareness real-data rollup."""
    from db import get_conn
    from datetime import datetime, timedelta

    period_start = args.get("periodStart")
    period_end = args.get("periodEnd")
    if not period_start or not period_end:
        end = datetime.now()
        start = end - timedelta(days=30)
        period_start = start.isoformat()
        period_end = end.isoformat()

    conn = get_conn()
    try:
        agg = conn.execute("""
            SELECT
                COUNT(DISTINCT campaign_id),
                COALESCE(SUM(impressions), 0),
                COALESCE(SUM(clicks), 0),
                COALESCE(SUM(spend_gtq), 0),
                COALESCE(SUM(conversions), 0),
                COALESCE(SUM(revenue_attributed_gtq), 0),
                MAX(captured_at)
            FROM campaigns_snapshot
            WHERE captured_at BETWEEN ? AND ?
        """, (period_start, period_end)).fetchone()

        impressions = agg[1]
        clicks = agg[2]
        spend = agg[3]
        cpm = round(spend / impressions * 1000, 2) if impressions else None
        cpc = round(spend / clicks, 2) if clicks else None
        ctr = round(clicks / impressions * 100, 2) if impressions else None

        by_campaign_rows = conn.execute("""
            SELECT campaign_id, MAX(campaign_name), SUM(spend_gtq), SUM(impressions)
            FROM campaigns_snapshot
            WHERE captured_at BETWEEN ? AND ?
            GROUP BY campaign_id
            ORDER BY SUM(spend_gtq) DESC
        """, (period_start, period_end)).fetchall()
        by_campaign = [
            {"campaignId": r[0], "campaignName": r[1], "spendGtq": r[2], "impressions": r[3]}
            for r in by_campaign_rows
        ]

        return {"ok": True, "awareness": {
            "periodStart": period_start,
            "periodEnd": period_end,
            "totalCampaigns": agg[0],
            "impressions": impressions,
            "clicks": clicks,
            "spendGtq": spend,
            "conversions": agg[4],
            "revenueAttributedGtq": agg[5],
            "cpm": cpm,
            "cpc": cpc,
            "ctr": ctr,
            "byCampaign": by_campaign,
            "lastSyncAt": agg[6],
        }}
    finally:
        conn.close()


def cmd_generate_coupon(args):
    """STUB R5: worker /api/coupons/generate endpoint contract incompatible with R4 plan.
    Returns pending status until separate worker task aligns the contract.
    See spec sec 6 decision 7.
    """
    return {
        "ok": False,
        "error": "Cupón pendiente — worker endpoint /api/coupons/generate requiere actualización (R5 worker task)",
        "pending": True,
    }


COMMANDS = {
    "ping": cmd_ping,
    "regen_watermark": cmd_regen_watermark,
    "restore_backup": cmd_restore_backup,
    "delete_sku": cmd_delete_sku,
    "delete_family": cmd_delete_family,
    "edit_modelo_type": cmd_edit_modelo_type,
    "batch_clean_family": cmd_batch_clean_family,
    "set_modelo_field": cmd_set_modelo_field,
    "set_family_variant": cmd_set_family_variant,
    "move_modelo": cmd_move_modelo,
    "delete_r2_objects": cmd_delete_r2_objects,
    "backfill_meta": cmd_backfill_meta,
    "insert_event": cmd_insert_event,
    "list_events": cmd_list_events,
    "set_event_status": cmd_set_event_status,
    "get_order": cmd_get_order,
    "mark_order_shipped": cmd_mark_order_shipped,
    "list_sales_in_range": cmd_list_sales_in_range,
    "list_leads_in_range": cmd_list_leads_in_range,
    "list_ad_spend_in_range": cmd_list_ad_spend_in_range,
    "sync_manychat": cmd_sync_manychat,
    "list_leads": cmd_list_leads,
    "list_conversations": cmd_list_conversations,
    "list_customers": cmd_list_customers,
    "get_meta_sync": cmd_get_meta_sync,
    "get_conversation_messages": cmd_get_conversation_messages,
    "get_customer_profile": cmd_get_customer_profile,
    "create_customer": cmd_create_customer,
    "update_customer_traits": cmd_update_customer_traits,
    "set_customer_blocked": cmd_set_customer_blocked,
    "update_customer_source": cmd_update_customer_source,
    "create_manual_order": cmd_create_manual_order,
    "sync_meta_ads": cmd_sync_meta_ads,
    "list_campaigns": cmd_list_campaigns,
    "get_campaign_detail": cmd_get_campaign_detail,
    "get_funnel_awareness_real": cmd_get_funnel_awareness_real,
    "generate_coupon": cmd_generate_coupon,
    "backfill_sales_attribution": cmd_backfill_sales_attribution,
    "get_sale_attribution": cmd_get_sale_attribution,
    "get_conversation_meta": cmd_get_conversation_meta,
    "attribute_sale": cmd_attribute_sale,
}


def main():
    _ensure_cwd()
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return _err("stdin vacío — esperaba JSON con {cmd, ...args}")
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        return _err(f"JSON inválido: {e}")

    cmd = payload.get("cmd")
    if cmd not in COMMANDS:
        return _err(f"cmd desconocido: {cmd!r}. Usar: {list(COMMANDS.keys())}")

    try:
        result = COMMANDS[cmd](payload)
        if result is not None:
            _reply(result)
    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        _err(f"{type(e).__name__}: {e}", traceback=tb)


if __name__ == "__main__":
    main()
