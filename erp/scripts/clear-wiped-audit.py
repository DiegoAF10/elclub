"""Clear audit_decisions rows + audit_photo_actions de SKUs wiped del Mundial.

Lee data/mundial-wiped-info.json (generado por wipe-mundial-nonpublished.mjs)
y borra:
  - audit_decisions WHERE family_id IN (wiped_skus)
  - audit_photo_actions WHERE family_id IN (wiped_skus)
  - pending_review WHERE family_id IN (wiped_skus)

Uso:
    python scripts/clear-wiped-audit.py               # dry-run
    python scripts/clear-wiped-audit.py --apply       # ejecuta
"""
import sys
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
ERP_DIR = HERE.parent
sys.path.insert(0, str(ERP_DIR))

import audit_db

APPLY = "--apply" in sys.argv
WIPED_INFO_PATH = ERP_DIR.parent.parent / "elclub-catalogo-priv" / "data" / "mundial-wiped-info.json"

def main():
    print(f"Mode: {'🔴 APPLY' if APPLY else '🔎 DRY-RUN'}")

    if not WIPED_INFO_PATH.exists():
        print(f"❌ No existe {WIPED_INFO_PATH}")
        print("   Correr primero: node scripts/wipe-mundial-nonpublished.mjs --apply")
        return

    info = json.loads(WIPED_INFO_PATH.read_text(encoding="utf-8"))
    skus = info.get("skus") or []
    family_ids = info.get("family_ids") or []
    print(f"Wiped info: {WIPED_INFO_PATH}")
    print(f"  Family IDs: {len(family_ids)}")
    print(f"  SKUs: {len(skus)}")

    if not skus:
        print("Nada que limpiar.")
        return

    conn = audit_db.get_conn()

    # 1. Count affected rows
    sku_placeholders = ",".join(["?"] * len(skus))
    n_decisions = conn.execute(
        f"SELECT COUNT(*) as n FROM audit_decisions WHERE family_id IN ({sku_placeholders})",
        skus,
    ).fetchone()["n"]
    n_actions = conn.execute(
        f"SELECT COUNT(*) as n FROM audit_photo_actions WHERE family_id IN ({sku_placeholders})",
        skus,
    ).fetchone()["n"]
    try:
        n_pending = conn.execute(
            f"SELECT COUNT(*) as n FROM pending_review WHERE family_id IN ({sku_placeholders})",
            skus,
        ).fetchone()["n"]
    except Exception:
        n_pending = 0

    print(f"\nRows a borrar:")
    print(f"  audit_decisions:     {n_decisions}")
    print(f"  audit_photo_actions: {n_actions}")
    print(f"  pending_review:      {n_pending}")

    if not APPLY:
        print("\n💡 Dry-run. Aplicar: python scripts/clear-wiped-audit.py --apply")
        conn.close()
        return

    # 2. Execute deletes
    print("\n🗑 Borrando…")
    conn.execute(
        f"DELETE FROM audit_decisions WHERE family_id IN ({sku_placeholders})",
        skus,
    )
    conn.execute(
        f"DELETE FROM audit_photo_actions WHERE family_id IN ({sku_placeholders})",
        skus,
    )
    try:
        conn.execute(
            f"DELETE FROM pending_review WHERE family_id IN ({sku_placeholders})",
            skus,
        )
    except Exception:
        pass
    conn.commit()

    print(f"✅ Cleared. Audit state de los {len(skus)} SKUs wiped eliminado.")
    conn.close()


if __name__ == "__main__":
    main()
