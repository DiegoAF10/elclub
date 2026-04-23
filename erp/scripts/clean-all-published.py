"""Ops s14q — pasa LaMa sobre TODAS las fotos de families published=true.

Diferencia con backfill-watermark-inpaint.py:
- backfill: solo fotos con flag_watermark en audit_photo_actions
- clean-all: TODAS las fotos sin cache-bust. OCR auto-detect.
  Si OCR no detecta watermark → skip (no-op). Si detecta → inpaint.

Usage:
  cd el-club/erp
  python scripts/clean-all-published.py [--dry-run] [--family argentina-2026-away]
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import requests
import audit_db
import audit_enrich
import local_inpaint

DRY_RUN = "--dry-run" in sys.argv
SINGLE_FAMILY = None
if "--family" in sys.argv:
    i = sys.argv.index("--family")
    SINGLE_FAMILY = sys.argv[i + 1] if i + 1 < len(sys.argv) else None


def r2_key_from_url(url):
    base = url.split("?")[0]
    if "/families/" not in base:
        return None
    return "families/" + base.split("/families/", 1)[1]


def has_cache_bust(url):
    return "?v=" in url


def main():
    if not local_inpaint.local_inpaint_available():
        print("ERROR: LaMa local no disponible (torch.cuda?)")
        sys.exit(1)
    print("Backend: LaMa local (GPU)")

    catalog = audit_db.load_catalog()
    published = [f for f in catalog if f.get("published") is True]
    if SINGLE_FAMILY:
        published = [f for f in published if f["family_id"] == SINGLE_FAMILY]
    print(f"Published families: {len(published)}")

    # Count dirty photos
    total_dirty = 0
    for fam in published:
        for m in fam.get("modelos") or []:
            for u in m.get("gallery") or []:
                if not has_cache_bust(u):
                    total_dirty += 1
        for u in fam.get("gallery") or []:
            if not has_cache_bust(u):
                total_dirty += 1  # top-level tambien (pero probablemente duplica modelo primary)

    print(f"Total DIRTY photos (sin cache-bust): {total_dirty}")
    if DRY_RUN:
        for fam in published:
            dirty_count = 0
            for m in fam.get("modelos") or []:
                dirty_count += sum(1 for u in (m.get("gallery") or []) if not has_cache_bust(u))
            print(f"  {fam['family_id']}: {dirty_count} dirty")
        print("\n--dry-run: no LaMa calls")
        return

    processed = 0
    skipped_no_wm = 0
    failed = 0
    touched_families = set()

    for fam in published:
        fid = fam["family_id"]
        print(f"\n[{fid}]")
        modelos_changed = False

        for mi, m in enumerate(fam.get("modelos") or []):
            gal = m.get("gallery") or []
            for pi, url in enumerate(gal):
                if has_cache_bust(url):
                    continue  # ya procesada
                base_url = url.split("?")[0]
                key = r2_key_from_url(base_url)
                if not key:
                    continue

                # Download
                try:
                    resp = requests.get(url, timeout=20)
                    if resp.status_code != 200:
                        print(f"  m{mi} idx={pi} DL fail {resp.status_code}")
                        failed += 1
                        continue
                    img_bytes = resp.content
                except Exception as e:
                    print(f"  m{mi} idx={pi} DL exc: {e}")
                    failed += 1
                    continue

                # LaMa with OCR detection
                t0 = time.time()
                result = local_inpaint.watermark_inpaint_bytes(
                    img_bytes, family_id=fid, photo_index=pi,
                )
                dt = time.time() - t0

                if result.get("skipped") == "no_watermark_detected":
                    print(f"  m{mi} idx={pi} SKIP ({dt:.1f}s): no watermark")
                    skipped_no_wm += 1
                    # No marca cache-bust — queda DIRTY (por si después OCR detecta con más data)
                    continue
                if not result.get("ok"):
                    print(f"  m{mi} idx={pi} LaMa FAIL ({dt:.1f}s): {result.get('error')}")
                    failed += 1
                    continue

                # Upload back
                up = audit_enrich.upload_image_to_r2(
                    result["image_bytes"], key,
                    content_type=result.get("mime_type", "image/jpeg"),
                )
                if not up.get("ok"):
                    print(f"  m{mi} idx={pi} R2 fail: {up.get('error')}")
                    failed += 1
                    continue

                # Cache-bust URL in gallery
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                new_url = f"{base_url}?v={ts}"
                gal[pi] = new_url
                modelos_changed = True
                processed += 1
                print(f"  m{mi} idx={pi} OK ({dt:.1f}s)")

            # Sync hero if changed
            if modelos_changed and gal:
                m["hero_thumbnail"] = gal[0]
                m["gallery"] = gal

        # Sync top-level from primary modelo
        if modelos_changed:
            primary_idx = fam.get("primary_modelo_idx", 0) or 0
            modelos = fam.get("modelos") or []
            if primary_idx < len(modelos):
                prim = modelos[primary_idx]
                if prim.get("gallery"):
                    fam["gallery"] = list(prim["gallery"])
                    fam["hero_thumbnail"] = prim["gallery"][0]
            touched_families.add(fid)

            # Save catalog incremental (en caso de kill)
            with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(catalog, f, ensure_ascii=False, indent=2)
                f.write("\n")

    print(f"\n=== SUMMARY ===")
    print(f"Processed OK:        {processed}")
    print(f"Skipped (no watermark): {skipped_no_wm}")
    print(f"Failed:              {failed}")
    print(f"Families touched:    {len(touched_families)}")
    print(f"Catalog saved (incremental).")
    print(f"\nPush manual:")
    print(f"  cd C:/Users/Diego/elclub-catalogo-priv")
    print(f"  git add data/catalog.json && git commit -m 'audit: clean-all-published ({processed} fotos)' && git push")


if __name__ == "__main__":
    main()
