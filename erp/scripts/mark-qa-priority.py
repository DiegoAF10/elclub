"""Ops s14d — marca SKUs críticos con qa_priority=1 para QA visual post-refetch.

Criterios:
  T1 — TODAS las selecciones Mundial 2026 × variant ∈ {home, away} × fan_adult/short
       (~96 SKUs: 48 selecciones × 2 variants)
  T2 — Top-20 clubes Europa temporada 25/26 o 26/27 × variant ∈ {home, away} × fan_adult/short
       (~40 SKUs: 20 clubs × 2 variants × typical 1 fan_short modelo per canonical)

Total esperado: ~136 SKUs.

Estos son los SKUs de MAYOR prioridad comercial — si alguno tiene mis-labeling
(ej. sleeve, type, variant) o fotos equivocadas, bloqueará launch.

Uso: cd el-club/erp && python scripts/mark-qa-priority.py [--dry-run]
"""
import sys
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

# Top-20 clubes Europa canonical prefixes (kebab-case)
TOP_20_CLUBS = {
    "barcelona", "real-madrid", "bayern-munich", "paris-saint-germain",
    "arsenal", "chelsea", "liverpool", "manchester-united", "manchester-city",
    "ac-milan", "inter-milan", "juventus", "napoli", "borussia-dortmund",
    "atletico-madrid", "tottenham", "bayer-leverkusen", "leverkusen",
    "ajax", "benfica", "porto", "sporting-lisbon",  # incluye variantes
}

# Seasons TOP prioridad (current + upcoming)
TOP_SEASONS = {"25/26", "26/27", "2025", "2026"}


def fid_prefix(fid):
    """Reusa _fid_prefix de audit_db."""
    return audit_db._fid_prefix(fid or "")


def is_national_team(fid):
    return audit_db._fid_prefix_match(fid, audit_db.NATIONAL_TEAMS_FID)


def is_top_20_club(fid):
    prefix = fid_prefix(fid)
    return prefix in TOP_20_CLUBS


def season_is_current(season):
    if not season:
        return False
    s = season.strip().replace("/", "-")
    return s in {"25-26", "26-27"} or season in TOP_SEASONS


def main():
    audit_db.init_audit_schema()  # ensures qa_priority column exists
    catalog = audit_db.load_catalog()
    sku_idx = audit_db.build_sku_index(catalog)
    conn = audit_db.get_conn()

    rows = conn.execute(
        "SELECT family_id, tier FROM audit_decisions WHERE status != 'deleted'"
    ).fetchall()

    qa_skus = []
    for r in rows:
        sku = r["family_id"]
        tier = r["tier"]
        resolved = sku_idx.get(sku)
        if not resolved:
            continue
        fam, modelo = resolved
        if not modelo:
            continue  # legacy families skipped

        # Criterio base: fan_adult + short + home/away
        mtype = modelo.get("type")
        sleeve = modelo.get("sleeve")
        variant = (fam.get("variant") or "").lower()
        if mtype != "fan_adult":
            continue
        if sleeve != "short":
            continue
        if variant not in ("home", "away"):
            continue

        fid = fam.get("family_id", "")

        # T1 Mundial: selección nacional + season 2026/2027 o cualquier año en 2026/2027
        if tier == "T1" and is_national_team(fid):
            qa_skus.append((sku, tier, fam.get("team"), fam.get("season"), variant, mtype, sleeve))
            continue

        # T2 Top-20 clubs: club en TOP_20 + season current
        if tier == "T2" and is_top_20_club(fid) and season_is_current(fam.get("season")):
            qa_skus.append((sku, tier, fam.get("team"), fam.get("season"), variant, mtype, sleeve))
            continue

    print(f"QA priority SKUs detectados: {len(qa_skus)}")
    t1_count = sum(1 for q in qa_skus if q[1] == "T1")
    t2_count = sum(1 for q in qa_skus if q[1] == "T2")
    print(f"  T1 (Mundial): {t1_count}")
    print(f"  T2 (Top-20 clubs): {t2_count}")

    print("\nSample (first 15):")
    for s in qa_skus[:15]:
        print(f"  [{s[1]}] {s[0]}: {s[2]} {s[3]} {s[4]}")

    if DRY_RUN:
        print("\n--dry-run: no DB write")
        conn.close()
        return

    # First unset all, then set selected → idempotent
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
    print(f"\nDB updated: {total} rows marked qa_priority=1")
    conn.close()


if __name__ == "__main__":
    main()
