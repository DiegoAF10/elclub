"""Ops s14d+s14i — marca SKUs críticos con qa_priority=1 para QA visual.

Criterios (s14i — ajustado por Diego post-pilot Argentina):

  Scope: SOLO Mundial 2026.
  Whitelist de selecciones: data/wc2026-classified.json (47-48 países).

  Variantes de family válidas: home, away, third, goalkeeper.
  NO: training, special (concept/limited), shorts, vest, jacket, polo,
  sweatshirt, other.

  Tipos de modelo válidos (las formas del jersey):
    fan_adult, player_adult, woman, kid, baby
  NO: retro_adult (Mundial 2026 es presente, no histórico).

  Sleeves válidos: short, long.

Total esperado: ~300-400 SKUs (48 countries × ~8 variantes típicas).

Usage: cd el-club/erp && python scripts/mark-qa-priority.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

WC2026_JSON_PATH = (
    Path(audit_db.CATALOG_PATH).parent / "wc2026-classified.json"
)

# Criterios
ALLOWED_VARIANTS = {"home", "away", "third", "goalkeeper"}
ALLOWED_TYPES = {"fan_adult", "player_adult", "woman", "kid", "baby"}
ALLOWED_SLEEVES = {"short", "long"}
# Categorías de family que siempre excluimos (son "accesorios" no jerseys principales)
EXCLUDED_CATEGORIES = {
    "jacket", "vest", "polo", "sweatshirt", "training", "shorts", "other",
}


def load_wc2026_fid_prefixes():
    """Devuelve set de fid_prefixes válidos según whitelist WC2026."""
    if not WC2026_JSON_PATH.exists():
        print(f"WARNING: {WC2026_JSON_PATH} no encontrado — fallback a NATIONAL_TEAMS_FID (permisivo)")
        return None  # None = no filter (legacy)
    data = json.loads(WC2026_JSON_PATH.read_text(encoding="utf-8"))
    prefixes = set()
    for entry in data.get("classified", []):
        for alias in entry.get("fid_aliases", []):
            prefixes.add(alias)
    return prefixes


def main():
    audit_db.init_audit_schema()
    catalog = audit_db.load_catalog()
    sku_idx = audit_db.build_sku_index(catalog)
    conn = audit_db.get_conn()

    wc2026 = load_wc2026_fid_prefixes()
    print(f"WC2026 whitelist: {len(wc2026) if wc2026 else 'fallback legacy'} prefixes")

    rows = conn.execute(
        "SELECT family_id, tier FROM audit_decisions WHERE status != 'deleted'"
    ).fetchall()

    qa_skus = []
    for r in rows:
        sku = r["family_id"]
        resolved = sku_idx.get(sku)
        if not resolved:
            continue
        fam, modelo = resolved
        if not modelo:
            continue

        # Filter 1: family.variant debe ser home/away/third/goalkeeper
        variant = (fam.get("variant") or "").lower()
        if variant not in ALLOWED_VARIANTS:
            continue

        # Filter 2: family.category no debe ser accesorio
        cat = (fam.get("category") or "adult").lower()
        if cat in EXCLUDED_CATEGORIES:
            continue

        # Filter 3: modelo.type in allowed jerseys
        mtype = modelo.get("type")
        if mtype not in ALLOWED_TYPES:
            continue

        # Filter 4: modelo.sleeve valid
        sleeve = modelo.get("sleeve")
        if sleeve not in ALLOWED_SLEEVES:
            continue

        # Filter 5: fid prefix en WC2026 whitelist
        fid = fam.get("family_id", "")
        fid_prefix = audit_db._fid_prefix(fid)
        if wc2026 is not None:
            if fid_prefix not in wc2026:
                continue
        else:
            # Fallback: usar NATIONAL_TEAMS_FID (más permisivo)
            if not audit_db._fid_prefix_match(fid, audit_db.NATIONAL_TEAMS_FID):
                continue

        qa_skus.append((sku, r["tier"], fam.get("team"), fam.get("season"), variant, mtype, sleeve))

    print(f"\nQA priority SKUs detectados: {len(qa_skus)}")
    # Breakdown
    by_type = {}
    by_country = {}
    for s in qa_skus:
        by_type[s[5]] = by_type.get(s[5], 0) + 1
        by_country[s[2] or "—"] = by_country.get(s[2] or "—", 0) + 1
    print(f"\nBy modelo type:")
    for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    print(f"\nCountries covered: {len(by_country)}")
    # Top 15 by SKU count
    for country, n in sorted(by_country.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {country}: {n}")

    if DRY_RUN:
        print("\n--dry-run: no DB write")
        conn.close()
        return

    conn.execute("UPDATE audit_decisions SET qa_priority = 0")
    for s in qa_skus:
        conn.execute(
            "UPDATE audit_decisions SET qa_priority = 1 WHERE family_id = ?",
            (s[0],),
        )
    conn.commit()
    total = conn.execute(
        "SELECT COUNT(*) FROM audit_decisions WHERE qa_priority = 1"
    ).fetchone()[0]
    print(f"\nDB updated: {total} rows qa_priority=1")
    conn.close()


if __name__ == "__main__":
    main()
