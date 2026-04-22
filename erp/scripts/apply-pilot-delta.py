"""Ops s14h — aplica el delta del piloto Argentina al ERP audit DB.

Lee `elclub-catalogo-priv/data/argentina-pilot-delta.json` generado por
`scripts/argentina-pilot.mjs`:
  - sku_changes: dict old_sku -> new_sku. Migra rows de audit_decisions
    + audit_photo_actions + audit_telemetry.
  - family_changes: info por family. Para modelos is_new=true, inserta
    nuevas rows en audit_decisions con status='pending' + tier=T1 +
    qa_priority computed.

Usage: cd el-club/erp && python scripts/apply-pilot-delta.py [--dry-run]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ERP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

DRY_RUN = "--dry-run" in sys.argv

# --delta <path> permite aplicar cualquier delta JSON (no solo argentina pilot).
# Default: argentina-pilot-delta.json (legacy compat).
_delta_arg = None
for i, a in enumerate(sys.argv):
    if a == "--delta" and i + 1 < len(sys.argv):
        _delta_arg = sys.argv[i + 1]
        break
if _delta_arg:
    DELTA_PATH = Path(_delta_arg) if Path(_delta_arg).is_absolute() else Path(audit_db.CATALOG_PATH).parent / _delta_arg
else:
    DELTA_PATH = Path(audit_db.CATALOG_PATH).parent / "argentina-pilot-delta.json"


def main():
    if not DELTA_PATH.exists():
        print(f"ERROR: delta not found at {DELTA_PATH}")
        print("Run `node scripts/argentina-pilot.mjs` first")
        sys.exit(1)

    delta = json.loads(DELTA_PATH.read_text(encoding="utf-8"))
    sku_changes = delta.get("sku_changes") or {}
    family_changes = delta.get("family_changes") or []

    audit_db.init_audit_schema()
    conn = audit_db.get_conn()
    now = datetime.now().isoformat(timespec="seconds")

    # 1. SKU renames (old -> new) across audit_decisions, audit_photo_actions, audit_telemetry
    print(f"SKU renames ({len(sku_changes)}):")
    for old_sku, new_sku in sku_changes.items():
        print(f"  {old_sku} -> {new_sku}")
        # Si new_sku ya existe (edge case), lo borramos primero
        existing_new = conn.execute(
            "SELECT 1 FROM audit_decisions WHERE family_id = ?", (new_sku,)
        ).fetchone()
        if existing_new and not DRY_RUN:
            print(f"    warning: {new_sku} ya existía, DELETE antes del rename")
            conn.execute("DELETE FROM audit_decisions WHERE family_id = ?", (new_sku,))
            conn.execute("DELETE FROM audit_photo_actions WHERE family_id = ?", (new_sku,))
            conn.execute("DELETE FROM audit_telemetry WHERE family_id = ?", (new_sku,))
        if not DRY_RUN:
            conn.execute(
                "UPDATE audit_decisions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            conn.execute(
                "UPDATE audit_photo_actions SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )
            conn.execute(
                "UPDATE audit_telemetry SET family_id = ? WHERE family_id = ?",
                (new_sku, old_sku),
            )

    # 2. Insert nuevos SKUs (is_new=true) en audit_decisions
    # Tier para Argentina 2026 = T1 (Mundial). QA priority = 1 si type=fan_adult + variant in (home, away).
    new_inserts = []
    for fc in family_changes:
        fid = fc["family_id"]
        for m in fc.get("modelos") or []:
            if not m.get("is_new"):
                continue
            sku = m["sku"]
            mtype = m["type"]
            sleeve = m["sleeve"]
            # qa_priority: fan_adult short/long en home/away (criterios de mark-qa-priority.py s14f)
            is_qa = (mtype == "fan_adult" and sleeve in ("short", "long"))
            new_inserts.append((sku, fid, mtype, sleeve, is_qa))

    print(f"\nNuevos SKUs a insertar ({len(new_inserts)}):")
    for sku, fid, mtype, sleeve, is_qa in new_inserts:
        print(f"  {sku}: {mtype}/{sleeve} @ {fid} (qa={is_qa})")
        if DRY_RUN:
            continue
        # Check si ya existe (idempotencia)
        existing = conn.execute(
            "SELECT 1 FROM audit_decisions WHERE family_id = ?", (sku,)
        ).fetchone()
        if existing:
            print(f"    already exists, update qa_priority only")
            conn.execute(
                "UPDATE audit_decisions SET qa_priority = ? WHERE family_id = ?",
                (int(is_qa), sku),
            )
        else:
            conn.execute(
                """INSERT INTO audit_decisions
                   (family_id, tier, status, qa_priority, decided_at)
                   VALUES (?, 'T1', 'pending', ?, ?)""",
                (sku, int(is_qa), now),
            )

    if not DRY_RUN:
        conn.commit()
        print("\nDB committed.")
    else:
        print("\n--dry-run: no DB writes")

    # Resumen final: estado argentina post-pilot
    print("\n=== audit_decisions post-pilot para argentina-2026-* ===")
    rows = conn.execute(
        """SELECT family_id, status, tier, qa_priority, final_verified
           FROM audit_decisions
           WHERE family_id LIKE 'ARG-2026-%'
           ORDER BY family_id"""
    ).fetchall()
    for r in rows:
        print(f"  {r['family_id']:20} status={r['status']:15} qa={r['qa_priority']} fv={r['final_verified']}")

    conn.close()


if __name__ == "__main__":
    main()
