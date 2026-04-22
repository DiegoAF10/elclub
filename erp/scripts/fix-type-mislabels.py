"""Ops s14f — auto-fix de mis-labels de type en modelos[].

Parecido a fix-sleeve-mislabels pero para modelo.type.

Heurísticas sobre variant_title:
  - "Women" / "Woman"        → type = "woman"
  - "Kids" / "Kid" / "Niño"  → type = "kid"  (si != baby)
  - "Baby" / "Bebé"          → type = "baby"
  - "Player Version"         → type = "player_adult"
  - "Retro"                  → type = "retro_adult"

Uso: cd el-club/erp && python scripts/fix-type-mislabels.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

# Orden de prioridad: el PRIMER match gana. Player y Retro tienen prioridad
# sobre Woman/Kid/Baby (un retro player no es woman aunque tenga "Women" elsewhere).
RULES = [
    ("player_adult", re.compile(r"\bplayer\b", re.IGNORECASE)),
    ("retro_adult", re.compile(r"\bretro\b", re.IGNORECASE)),
    ("baby", re.compile(r"\b(baby|beb[eé])\b", re.IGNORECASE)),
    ("kid", re.compile(r"\b(kids?|ni[nñ]o|ni[nñ]os)\b", re.IGNORECASE)),
    ("woman", re.compile(r"\b(women|woman|mujer)\b", re.IGNORECASE)),
]


def infer_type(title):
    for mtype, regex in RULES:
        if regex.search(title or ""):
            return mtype
    return None


def main():
    catalog_path = audit_db.CATALOG_PATH
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Transiciones SEGURAS — solo las obvias. Schema no soporta "Retro Woman"
    # como type combinado; dejamos esos casos ambiguos para fix manual de Diego.
    SAFE_TRANSITIONS = {
        ("fan_adult", "woman"),
        ("fan_adult", "player_adult"),
        ("fan_adult", "retro_adult"),
        ("fan_adult", "kid"),
        ("fan_adult", "baby"),
    }

    changes = []
    skipped_ambiguous = 0
    for fam in catalog:
        for i, m in enumerate(fam.get("modelos") or []):
            title = m.get("variant_title") or ""
            if not title:
                continue
            current = m.get("type")
            inferred = infer_type(title)
            if not inferred or current == inferred:
                continue
            if (current, inferred) not in SAFE_TRANSITIONS:
                skipped_ambiguous += 1
                continue
            changes.append({
                "family_id": fam["family_id"],
                "modelo_idx": i,
                "sku": m.get("sku"),
                "was": current,
                "becomes": inferred,
                "title": title,
            })

    print(f"Type mis-labels detectados: {len(changes)}")
    # Breakdown
    by_change = {}
    for c in changes:
        k = f"{c['was']}->{c['becomes']}"
        by_change[k] = by_change.get(k, 0) + 1
    print("\nBy transition:")
    for k, v in sorted(by_change.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")

    print(f"Skipped ambiguous (ej. retro+woman): {skipped_ambiguous}")
    print("\nSample (first 20):")
    for c in changes[:20]:
        # Strip non-ASCII para evitar crashes en Windows cp1252
        safe_title = (c['title'] or "").encode("ascii", "ignore").decode("ascii")
        print(f"  {c['sku']:25} {c['was']:15} -> {c['becomes']:15}")
        print(f"    title: {safe_title}")

    if DRY_RUN:
        print("\n--dry-run: no mutation")
        return

    applied = 0
    for c in changes:
        fam = next(f for f in catalog if f["family_id"] == c["family_id"])
        fam["modelos"][c["modelo_idx"]]["type"] = c["becomes"]
        applied += 1

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nApplied: {applied} modelos re-typed")
    print("SKU codes unchanged. Queue UI muestra type desde modelo.type.")


if __name__ == "__main__":
    main()
