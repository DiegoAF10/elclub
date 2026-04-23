"""Ops s14s — force primary_modelo_idx a fan_adult/short cuando existe.

Regla Diego: el Hero de la card family SIEMPRE debe ser foto del fan_adult/short
si ese modelo existe. Si no hay fan_adult/short, cae a:
  player_adult/short > retro_adult/short > fan_adult/long > player_adult/long >
  retro_adult/long > woman > kid > baby > idx 0 fallback

Script one-shot que recorre catalog y corrige primary_modelo_idx en todas las
families unified. Re-syncea fam.gallery + fam.hero_thumbnail desde el new primary.

Usage: cd el-club/erp && python scripts/ensure-primary-fan-short.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db

DRY_RUN = "--dry-run" in sys.argv

# Prioridad de modelo types para ser primary (fan_adult/short siempre primero)
PRIORITY = [
    ("fan_adult", "short"),
    ("player_adult", "short"),
    ("retro_adult", "short"),
    ("fan_adult", "long"),
    ("player_adult", "long"),
    ("retro_adult", "long"),
    ("woman", "short"),
    ("woman", "long"),
    ("kid", "short"),
    ("kid", "long"),
    ("baby", "short"),
]


def pick_primary_idx(modelos):
    """Retorna el idx del modelo que debe ser primary según PRIORITY. Si ninguno
    matchea exactamente, retorna 0 (fallback)."""
    if not modelos:
        return None
    for target_type, target_sleeve in PRIORITY:
        for i, m in enumerate(modelos):
            if m.get("type") == target_type and m.get("sleeve") == target_sleeve:
                return i
    return 0


def main():
    catalog = audit_db.load_catalog()
    changed = 0
    for fam in catalog:
        modelos = fam.get("modelos") or []
        if not modelos:
            continue
        current = fam.get("primary_modelo_idx", 0) or 0
        correct = pick_primary_idx(modelos)
        if correct is None or correct == current:
            continue
        cur_m = modelos[current] if current < len(modelos) else None
        new_m = modelos[correct]
        cur_label = f"{cur_m.get('type')}/{cur_m.get('sleeve')}" if cur_m else "?"
        new_label = f"{new_m.get('type')}/{new_m.get('sleeve')}"
        print(f"[{fam['family_id']}] primary {current} ({cur_label}) -> {correct} ({new_label})")
        if DRY_RUN:
            changed += 1
            continue
        fam["primary_modelo_idx"] = correct
        # Sync top-level gallery + hero desde new primary
        new_gal = new_m.get("gallery") or []
        if new_gal:
            fam["gallery"] = list(new_gal)
            fam["hero_thumbnail"] = new_gal[0]
        changed += 1

    if DRY_RUN:
        print(f"\n--dry-run: {changed} families cambiarían de primary")
        return
    if changed:
        with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\n{changed} families actualizadas. Commit+push recomendado.")
    else:
        print("\nTodas las families ya tienen primary correcto.")


if __name__ == "__main__":
    main()
