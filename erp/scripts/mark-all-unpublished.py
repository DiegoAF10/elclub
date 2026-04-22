"""Ops s14g — marca TODAS las families como published=false excepto las que
Diego ya verificó (final_verified=1 en audit_decisions).

Nueva política: el vault live SOLO muestra lo que Diego autoriza explícitamente
vía publish flow (Pending Review → ✅ PUBLISH). Default hidden.

Este script es one-time. A partir de ahora:
  - families nuevas que el scraper añada → published=false por default
  - _publish_family en audit.py setea target.published=true al publicar

El FRONTEND (Vault UX) necesita filtrar `families.filter(f => f.published === true)`.
Mensaje a Vault UX en BUCKET-OPERACIONES.md mini-s14g.

Usage:
  python scripts/mark-all-unpublished.py --dry-run
  python scripts/mark-all-unpublished.py
"""
import json
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv


def main():
    catalog_path = audit_db.CATALOG_PATH
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # SKUs con final_verified=1 en audit_decisions → sus canonical families
    # quedan published=true. El resto published=false.
    conn = audit_db.get_conn()
    sku_idx = audit_db.build_sku_index(catalog)
    rows = conn.execute(
        "SELECT family_id FROM audit_decisions WHERE final_verified = 1"
    ).fetchall()
    published_canonicals = set()
    for r in rows:
        sku = r["family_id"]
        resolved = sku_idx.get(sku)
        if resolved:
            fam, _ = resolved
            published_canonicals.add(fam["family_id"])
        else:
            # Legacy row family_id tradicional
            published_canonicals.add(sku)
    conn.close()

    print(f"Families actualmente publicadas (final_verified=1): {len(published_canonicals)}")
    for fid in sorted(published_canonicals):
        print(f"  - {fid}")

    # Apply flag
    updated = 0
    to_true = 0
    to_false = 0
    for fam in catalog:
        fid = fam.get("family_id")
        should_be_published = fid in published_canonicals
        current = fam.get("published")
        if current != should_be_published:
            if not DRY_RUN:
                fam["published"] = should_be_published
            updated += 1
            if should_be_published:
                to_true += 1
            else:
                to_false += 1

    print(f"\nTotal families: {len(catalog)}")
    print(f"Changes: {updated} (true: {to_true}, false: {to_false})")

    if DRY_RUN:
        print("\n--dry-run: no mutation")
        return

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Verify
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    pub_count = sum(1 for f in catalog if f.get("published") is True)
    hidden_count = sum(1 for f in catalog if f.get("published") is False)
    print(f"\nPost-write: published=true {pub_count} | published=false {hidden_count}")


if __name__ == "__main__":
    main()
