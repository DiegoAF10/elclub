#!/usr/bin/env python3
"""Ops s13+ — agrega campo `sku` a cada modelo (o al top-level si legacy) en
catalog.json. El SKU es derivado automáticamente vía audit_db.generate_skus_for_family.

Uso:
  python scripts/add_skus_to_catalog.py              # dry-run
  python scripts/add_skus_to_catalog.py --apply
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ERP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP_DIR))
import audit_db  # noqa

CATALOG_PATH = ERP_DIR.parent.parent / "elclub-catalogo-priv" / "data" / "catalog.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Asigna SKUs resolviendo colisiones intra + cross family
    per_family = audit_db.resolve_catalog_skus(catalog)

    stats = {
        "total_families": len(catalog),
        "unified_with_modelos": 0,
        "legacy": 0,
        "total_skus": 0,
        "intra_collisions": 0,     # sufijo -2, -3
        "cross_collisions": 0,      # sufijo -X1, -X2
        "samples": [],
    }
    seen_skus = set()

    for fam in catalog:
        skus = per_family[fam["family_id"]]
        modelos = fam.get("modelos") or []
        if modelos:
            stats["unified_with_modelos"] += 1
        else:
            stats["legacy"] += 1
        for s in skus:
            stats["total_skus"] += 1
            seen_skus.add(s)
            if "-X" in s:
                stats["cross_collisions"] += 1
            elif s.count("-") >= 4 and s.rsplit("-", 1)[-1].isdigit():
                stats["intra_collisions"] += 1

        if len(stats["samples"]) < 5 and len(skus) >= 3:
            stats["samples"].append({"family_id": fam["family_id"], "skus": skus})

    # Reporte
    print("=== add_skus_to_catalog.py ===")
    print(f"Total families:        {stats['total_families']}")
    print(f"  Unified (modelos[]): {stats['unified_with_modelos']}")
    print(f"  Legacy:              {stats['legacy']}")
    print(f"Total SKUs:            {stats['total_skus']}")
    print(f"SKUs únicos globales:  {len(seen_skus)}")
    print(f"Intra-family collisions (sufijo -N): {stats['intra_collisions']}")
    print(f"Cross-family collisions (sufijo -Xn): {stats['cross_collisions']}")
    unique_ok = len(seen_skus) == stats['total_skus']
    print(f"\n{'✅' if unique_ok else '❌'} Unique invariant: {unique_ok}")

    print("\nSamples (families con ≥3 modelos):")
    for s in stats["samples"]:
        print(f"  {s['family_id']}:")
        for sk in s["skus"]:
            print(f"    {sk}")

    if not args.apply:
        print("\n[DRY RUN] Use --apply para escribir catalog.json")
        return

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n✅ Escrito {CATALOG_PATH}")


if __name__ == "__main__":
    main()
