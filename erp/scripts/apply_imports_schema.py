# C:/Users/Diego/el-club/erp/scripts/apply_imports_schema.py
"""IMP-R1 schema additions. Idempotente — re-runnable sin error."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"C:\Users\Diego\el-club\erp\elclub.db")

ALTERS = [
    # imports
    ("imports", "tracking_code", "TEXT"),
    ("imports", "carrier", "TEXT DEFAULT 'DHL'"),
    ("imports", "lead_time_days", "INTEGER"),
    # sale_items
    ("sale_items", "unit_cost_usd", "REAL"),
    # jerseys
    ("jerseys", "unit_cost_usd", "REAL"),
]

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS import_wishlist (
        wishlist_item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id             TEXT NOT NULL,
        jersey_id             TEXT,
        size                  TEXT,
        player_name           TEXT,
        player_number         INTEGER,
        patch                 TEXT,
        version               TEXT,
        customer_id           TEXT,
        expected_usd          REAL,
        status                TEXT DEFAULT 'active'
                              CHECK(status IN ('active','promoted','cancelled')),
        promoted_to_import_id TEXT,
        created_at            TEXT DEFAULT (datetime('now', 'localtime')),
        notes                 TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_free_unit (
        free_unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id         TEXT NOT NULL,
        family_id         TEXT,
        jersey_id         TEXT,
        destination       TEXT
                          CHECK(destination IN ('unassigned','vip','mystery','garantizada','personal')),
        destination_ref   TEXT,
        assigned_at       TEXT,
        assigned_by       TEXT,
        notes             TEXT,
        created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_wishlist_status ON import_wishlist(status)",
    "CREATE INDEX IF NOT EXISTS idx_wishlist_customer ON import_wishlist(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_free_unit_import ON import_free_unit(import_id)",
    "CREATE INDEX IF NOT EXISTS idx_free_unit_destination ON import_free_unit(destination)",
]


def column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def main():
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"📂 Applying schema to {DB_PATH}")

    # ALTERs idempotentes
    for table, col, decl in ALTERS:
        if column_exists(cur, table, col):
            print(f"  ↪ {table}.{col} already exists, skip")
        else:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            print(f"  ✓ added {table}.{col}")

    # Default FX → 7.73 (D-FX)
    # NOTA: SQLite no permite ALTER COLUMN para cambiar default. Documentamos el nuevo
    # default en código Rust (close_import_proportional usa 7.73 si fx is null).
    # Imports históricos quedan con fx=7.70.
    print("  ℹ FX default 7.73 enforced en Rust commands, no a nivel schema (SQLite limit)")

    # CREATE TABLEs
    for sql in CREATE_TABLES:
        cur.execute(sql)
    for sql in CREATE_INDEXES:
        cur.execute(sql)
    print(f"  ✓ created/verified {len(CREATE_TABLES)} tables + {len(CREATE_INDEXES)} indexes")

    conn.commit()
    conn.close()

    print("✅ Schema applied successfully (idempotente)")


if __name__ == "__main__":
    main()
