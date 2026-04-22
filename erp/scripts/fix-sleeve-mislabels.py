"""Ops s14e — auto-fix de mis-labels de sleeve en modelos[].

El unify-families.mjs original no detectaba "Long-Sleeve" en variant_title y
dejaba sleeve='short' como default. Resultado: modelos con fotos de manga
larga etiquetados como fan_adult/short. Ejemplo real: ARG-2026-L-FS-2.

Heurística: regex sobre variant_title — si matchea patrón long-sleeve,
actualiza modelo.sleeve = 'long'.

Usage:
  python scripts/fix-sleeve-mislabels.py --dry-run
  python scripts/fix-sleeve-mislabels.py
"""
import json
import re
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

# Regex para detectar long-sleeve en variant_title.
# Casos cubiertos: "Long-Sleeve", "Long Sleeve", "LongSleeve", "LS" (sufijo),
# "Manga Larga", "Manga-Larga".
LONG_SLEEVE_RE = re.compile(
    r"(long[-\s]?sleeve|manga[-\s]?larga|\bLS\b)",
    re.IGNORECASE,
)


def main():
    catalog_path = audit_db.CATALOG_PATH
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    changes = []
    for fam in catalog:
        modelos = fam.get("modelos") or []
        for i, m in enumerate(modelos):
            title = m.get("variant_title") or ""
            if not title:
                continue
            current_sleeve = m.get("sleeve")
            is_long = bool(LONG_SLEEVE_RE.search(title))
            if is_long and current_sleeve != "long":
                changes.append({
                    "family_id": fam["family_id"],
                    "modelo_idx": i,
                    "sku": m.get("sku"),
                    "type": m.get("type"),
                    "was": current_sleeve,
                    "becomes": "long",
                    "title": title,
                })

    print(f"Mis-labels de sleeve detectados: {len(changes)}")
    print("\nSample (first 20):")
    for c in changes[:20]:
        print(f"  {c['sku']:20} ({c['type']}): {c['was']} -> long")
        print(f"    title: {c['title']}")

    if DRY_RUN:
        print("\n--dry-run: no mutation")
        return

    # Apply: solo cambiar sleeve. NO regeneramos SKUs para evitar side effects
    # cross-family (resolve_catalog_skus detecta colisiones a nivel global y
    # puede reshufflear SKUs no afectados por este fix). El SKU code queda
    # mis-aligned (ej. ARG-2026-L-FS-2 con sleeve=long), pero el queue muestra
    # el label correcto desde modelo.sleeve. SKU regenerate opcional en otro pass.
    applied = 0
    for c in changes:
        fam = next(f for f in catalog if f["family_id"] == c["family_id"])
        fam["modelos"][c["modelo_idx"]]["sleeve"] = "long"
        applied += 1

    # Write catalog
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nApplied: {applied} modelos re-labeled sleeve=long")
    print("SKU codes unchanged (ej. -FS-2 code preserved even if sleeve is now long).")
    print("Queue UI muestra el sleeve actualizado desde modelo.sleeve.")


if __name__ == "__main__":
    main()
