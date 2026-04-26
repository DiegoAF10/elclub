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


def cmd_list_events(args):
    """Lista eventos de comercial_events con filtros opcionales."""
    import sqlite3, json
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
        # Sales table
        sale = conn.execute("""
            SELECT s.ref, s.fulfillment_status, s.paid_at, s.shipped_at, s.total_gtq,
                   s.payment_method, s.notes,
                   c.name, c.phone, c.handle, c.platform
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE s.ref = ?
        """, (ref,)).fetchone()

        if not sale:
            return {"ok": True, "order": None}

        # Items
        items = conn.execute("""
            SELECT family_id, jersey_sku, size, unit_price_gtq, unit_cost_gtq, personalization_json
            FROM sale_items
            WHERE sale_id = (SELECT sale_id FROM sales WHERE ref = ?)
        """, (ref,)).fetchall()

        order = {
            "ref": sale[0],
            "status": sale[1] or "paid",
            "paidAt": sale[2],
            "shippedAt": sale[3],
            "totalGtq": sale[4],
            "paymentMethod": sale[5] or "recurrente",
            "notes": sale[6],
            "customer": {
                "name": sale[7] or "(sin nombre)",
                "phone": sale[8],
                "handle": sale[9],
                "platform": sale[10] or "web",
            },
            "items": [
                {
                    "familyId": i[0],
                    "jerseySku": i[1],
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
            "SELECT ref, total_gtq, paid_at, fulfillment_status FROM sales WHERE paid_at BETWEEN ? AND ?",
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
            "ad_spend": [{"campaignId": r[0], "spendGtq": r[1], "capturedAt": r[2]} for r in rows]
        }
    finally:
        conn.close()


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
    "list_events": cmd_list_events,
    "set_event_status": cmd_set_event_status,
    "get_order": cmd_get_order,
    "mark_order_shipped": cmd_mark_order_shipped,
    "list_sales_in_range": cmd_list_sales_in_range,
    "list_leads_in_range": cmd_list_leads_in_range,
    "list_ad_spend_in_range": cmd_list_ad_spend_in_range,
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
