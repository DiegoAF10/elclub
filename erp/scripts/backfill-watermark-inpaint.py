"""Ops s14n — backfill Gemini watermark inpaint sobre flag_watermark rows
con processed_url=NULL.

Post-fix s14m6 (effective_fid bug), todas las flag_watermark del audit pasado
quedaron sin procesar. Este script corre Gemini sobre cada una y actualiza
catalog URLs con cache-bust.

Usage:
  cd el-club/erp
  python scripts/backfill-watermark-inpaint.py --dry-run    # lista sin ejecutar
  python scripts/backfill-watermark-inpaint.py              # corre Gemini
  python scripts/backfill-watermark-inpaint.py --family ARG-2026-V-FL   # solo 1 SKU
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import requests
import audit_db
import audit_enrich

DRY_RUN = "--dry-run" in sys.argv
SINGLE = None
PREFIX = None
if "--family" in sys.argv:
    i = sys.argv.index("--family")
    SINGLE = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
if "--prefix" in sys.argv:
    i = sys.argv.index("--prefix")
    PREFIX = sys.argv[i + 1] if i + 1 < len(sys.argv) else None


def download_r2(url, timeout=30):
    resp = requests.get(url, timeout=timeout)
    if resp.status_code != 200:
        return None, f"http_{resp.status_code}"
    return resp.content, None


def r2_key_from_url(url):
    base = url.split("?")[0]
    if "/families/" not in base:
        return None
    return "families/" + base.split("/families/", 1)[1]


def main():
    # Prefer LaMa local (free, fast, preserves image). Fallback to Gemini.
    import local_inpaint
    use_lama = local_inpaint.local_inpaint_available()
    if use_lama:
        print("Backend: LaMa local (GPU)")
    elif audit_enrich.gemini_available():
        print("Backend: Gemini API (LaMa no disponible — sin torch.cuda o iopaint)")
    else:
        print("ERROR: ni LaMa local ni Gemini API disponibles")
        sys.exit(1)

    conn = audit_db.get_conn()
    catalog = audit_db.load_catalog()
    sku_idx = audit_db.build_sku_index(catalog)

    # Query pending flag_watermark por SKU
    q = """SELECT family_id, original_index, original_url
           FROM audit_photo_actions
           WHERE action='flag_watermark' AND processed_url IS NULL"""
    params = []
    if SINGLE:
        q += " AND family_id = ?"
        params.append(SINGLE)
    elif PREFIX:
        q += " AND family_id LIKE ?"
        params.append(f"{PREFIX}%")
    q += " ORDER BY family_id, original_index"
    rows = conn.execute(q, params).fetchall()
    total = len(rows)
    print(f"Pending flag_watermark (processed_url=NULL): {total}")
    if SINGLE:
        print(f"Filter: family={SINGLE}")
    elif PREFIX:
        print(f"Filter: prefix={PREFIX}")

    if total == 0:
        print("Nothing to do.")
        return

    # Group por SKU
    by_sku = {}
    for r in rows:
        by_sku.setdefault(r["family_id"], []).append(
            {"original_index": r["original_index"], "original_url": r["original_url"]}
        )

    print(f"SKUs afectados: {len(by_sku)}")
    for sku, items in by_sku.items():
        print(f"  {sku}: {len(items)} fotos")

    if DRY_RUN:
        print("\n--dry-run: no Gemini calls, no catalog mutations")
        return

    processed_total = 0
    failed_total = 0
    updated_skus = set()
    touched_canonicals = set()

    for sku, items in by_sku.items():
        # Resolve SKU → canonical fam + modelo
        resolved = sku_idx.get(sku)
        if not resolved:
            print(f"\n[{sku}] SKIP — no se resuelve en catalog")
            failed_total += len(items)
            continue
        fam, modelo = resolved
        canonical_fid = fam["family_id"]
        if not modelo:
            # Legacy — gallery at family level
            gallery_source = fam.get("gallery") or []
            is_primary_mod = True  # legacy implícito primary
            modelo_idx = None
        else:
            gallery_source = modelo.get("gallery") or []
            primary_idx = fam.get("primary_modelo_idx", 0) or 0
            # Find modelo's idx in family (sku_idx retorna el modelo ref, necesito idx)
            modelo_idx = None
            for i, m in enumerate(fam.get("modelos") or []):
                if m is modelo:
                    modelo_idx = i
                    break
            is_primary_mod = (modelo_idx == primary_idx)

        print(f"\n[{sku}] canonical={canonical_fid} modelo_idx={modelo_idx} gallery_len={len(gallery_source)}")

        for it in items:
            idx = it["original_index"]
            # URL actual del catalog (no trust en original_url legacy — puede estar desactualizado)
            if idx >= len(gallery_source):
                print(f"  idx={idx} — SKIP (out of range gallery_len={len(gallery_source)})")
                failed_total += 1
                continue
            cur_url = gallery_source[idx]
            base_url = cur_url.split("?")[0]
            r2_key = r2_key_from_url(base_url)
            if not r2_key:
                print(f"  idx={idx} — SKIP (URL no R2: {base_url[:60]})")
                failed_total += 1
                continue

            # Download
            print(f"  idx={idx} fetching {base_url[-50:]}...", end="", flush=True)
            img_bytes, err = download_r2(cur_url)
            if err:
                print(f" FAIL download: {err}")
                failed_total += 1
                continue

            # Inpaint — LaMa local preferido, Gemini fallback
            t0 = time.time()
            if use_lama:
                gem = local_inpaint.watermark_inpaint_bytes(
                    img_bytes, mime_type="image/jpeg",
                    family_id=sku, photo_index=idx,
                )
                if gem.get("skipped") == "no_watermark_detected":
                    elapsed = time.time() - t0
                    print(f" SKIP ({elapsed:.1f}s): no watermark detectado")
                    # Mark processed (para no re-intentar) con el URL original
                    conn.execute(
                        """UPDATE audit_photo_actions SET processed_url = ?
                           WHERE family_id = ? AND original_index = ?""",
                        (cur_url, sku, idx),
                    )
                    conn.commit()
                    continue
            else:
                gem = audit_enrich.gemini_regen_image(
                    img_bytes, mime_type="image/jpeg", prompt_variant="watermark",
                    family_id=sku, photo_index=idx,
                )
            elapsed = time.time() - t0
            if not gem.get("ok"):
                print(f" FAIL inpaint ({elapsed:.1f}s): {gem.get('error')}")
                failed_total += 1
                continue

            # Upload back
            out_bytes = gem["image_bytes"]
            out_mime = gem.get("mime_type", "image/jpeg")
            up = audit_enrich.upload_image_to_r2(out_bytes, r2_key, content_type=out_mime)
            if not up.get("ok"):
                print(f" FAIL upload: {up.get('error')}")
                failed_total += 1
                continue

            # Cache-bust URL
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_url = f"{base_url}?v={ts}"
            gallery_source[idx] = new_url

            # Update audit_photo_actions.processed_url + commit incremental
            # (commit per-row evita locks largos que tumban Streamlit si está abierto).
            conn.execute(
                """UPDATE audit_photo_actions
                   SET processed_url = ?
                   WHERE family_id = ? AND original_index = ?""",
                (new_url, sku, idx),
            )
            conn.commit()

            print(f" OK ({elapsed:.1f}s, {len(out_bytes)//1024}KB {out_mime})")
            processed_total += 1

        # Mutate catalog for this SKU
        if modelo is not None:
            modelo["gallery"] = gallery_source
            # Update hero if gallery[0] changed
            if gallery_source:
                modelo["hero_thumbnail"] = gallery_source[0]
            # Sync top-level if primary
            if is_primary_mod:
                fam["gallery"] = list(gallery_source)
                if gallery_source:
                    fam["hero_thumbnail"] = gallery_source[0]
        else:
            # Legacy
            fam["gallery"] = gallery_source
            if gallery_source:
                fam["hero_thumbnail"] = gallery_source[0]
        updated_skus.add(sku)
        touched_canonicals.add(canonical_fid)

        # Save catalog incremental — después de cada SKU. Si el script se
        # muere mid-way, los SKUs ya completados quedan persistidos.
        with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  [SKU {sku} done · catalog saved · {processed_total} total processed so far]")

    conn.commit()

    print(f"\n=== SUMMARY ===")
    print(f"Processed OK:   {processed_total}")
    print(f"Failed:         {failed_total}")
    print(f"SKUs updated:   {len(updated_skus)}")
    print(f"Canonicals touched: {len(touched_canonicals)}")
    print(f"\nCatalog actualizado: {audit_db.CATALOG_PATH}")
    print("Commit+push manualmente cuando termines (no lo hago automático para que revises):")
    print("  cd C:/Users/Diego/elclub-catalogo-priv")
    print("  git add data/catalog.json")
    print(f"  git commit -m 'audit: backfill watermark inpaint ({processed_total} fotos, {len(touched_canonicals)} families)'")
    print("  git push")

    conn.close()


if __name__ == "__main__":
    main()
