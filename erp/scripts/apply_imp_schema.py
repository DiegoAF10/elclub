#!/usr/bin/env python3
"""
apply_imp_schema.py — idempotent IMP schema applicator.

Crea (IF NOT EXISTS) las tablas + indexes que IMP necesita en main elclub.db:
- import_wishlist (R2)
- import_free_unit (R4)
- imp_settings (R6) + seed defaults
- import_items (R6 NEW · tabla nueva para promoted items · Diego dec 2026-04-28)
- 8 indexes (4 originales + 4 import_items)

Safe to re-run. Backup obligatorio cuando --apply (no --dry-run).

Usage:
  python apply_imp_schema.py --dry-run                 # preview cambios
  python apply_imp_schema.py --apply                   # apply + backup pre-change
  python apply_imp_schema.py --apply --db-path X.db    # explicit DB
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = os.environ.get(
    "ERP_DB_PATH",
    r"C:/Users/Diego/el-club/erp/elclub.db",
)

# ── Schema definitions (MUST stay in sync with spec sec 7 lines 499-535) ─────

WISHLIST_SCHEMA = """
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
);
"""

FREE_UNIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS import_free_unit (
  free_unit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id        TEXT NOT NULL,
  family_id        TEXT,
  jersey_id        TEXT,
  destination      TEXT
                   CHECK(destination IS NULL OR destination IN ('vip','mystery','garantizada','personal')),
  destination_ref  TEXT,
  assigned_at      TEXT,
  assigned_by      TEXT,
  notes            TEXT,
  created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);
"""
# NOTA: la convención NULL (no string 'unassigned') fue ratificada Diego 2026-04-28 ~19:00.
# La tabla R1 NO se creó con CHECK · este IF NOT EXISTS solo aplica si la tabla aún no existe en main DB.
# Si la tabla ya existe en main DB sin CHECK (como en worktree), NO se altera (SQLite no soporta ADD CHECK
# vía ALTER · requeriría re-create destructivo · skip en v0.4.0 · enforced en Rust via VALID_FREE_DESTINATIONS).

IMPORT_ITEMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS import_items (
  import_item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id           TEXT NOT NULL REFERENCES imports(import_id),
  wishlist_item_id    INTEGER REFERENCES import_wishlist(wishlist_item_id),
  family_id           TEXT NOT NULL,
  jersey_id           TEXT,
  size                TEXT,
  player_name         TEXT,
  player_number       INTEGER,
  patch               TEXT,
  version             TEXT,
  customer_id         TEXT,
  expected_usd        REAL,
  unit_cost_usd       REAL,
  unit_cost_gtq       REAL,
  status              TEXT DEFAULT 'pending'
                      CHECK(status IN ('pending','arrived','sold','published','cancelled')),
  sale_item_id        INTEGER REFERENCES sale_items(item_id),
  jersey_id_published TEXT REFERENCES jerseys(jersey_id),
  notes               TEXT,
  created_at          TEXT DEFAULT (datetime('now', 'localtime'))
);
"""
# customer_id NO se agrega a sale_items · Diego eligió usar import_items (nueva tabla) para tracking
# pre-venta · sale_items se llena solo cuando hay venta real (Comercial flow). Ver Open Question Q6.

IMP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS imp_settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT DEFAULT (datetime('now', 'localtime')),
  updated_by  TEXT
);
"""

INDEXES = [
    ("idx_wishlist_status", "CREATE INDEX IF NOT EXISTS idx_wishlist_status ON import_wishlist(status);"),
    ("idx_wishlist_customer", "CREATE INDEX IF NOT EXISTS idx_wishlist_customer ON import_wishlist(customer_id);"),
    ("idx_free_unit_import", "CREATE INDEX IF NOT EXISTS idx_free_unit_import ON import_free_unit(import_id);"),
    ("idx_free_unit_destination", "CREATE INDEX IF NOT EXISTS idx_free_unit_destination ON import_free_unit(destination);"),
    # import_items indexes (R6 NEW · 4 indexes para query patterns esperados)
    ("idx_import_items_import_id", "CREATE INDEX IF NOT EXISTS idx_import_items_import_id ON import_items(import_id);"),
    ("idx_import_items_family_id", "CREATE INDEX IF NOT EXISTS idx_import_items_family_id ON import_items(family_id);"),
    ("idx_import_items_customer_id", "CREATE INDEX IF NOT EXISTS idx_import_items_customer_id ON import_items(customer_id);"),
    ("idx_import_items_status", "CREATE INDEX IF NOT EXISTS idx_import_items_status ON import_items(status);"),
]

DEFAULT_SETTINGS = [
    ("default_fx", "7.73"),
    ("default_free_ratio", "10"),
    ("default_wishlist_target", "20"),
    ("threshold_wishlist_unbatched_days", "30"),
    ("threshold_paid_unarrived_days", "14"),
    ("threshold_cost_overrun_pct", "30"),
    ("threshold_free_unit_unassigned_days", "7"),
]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def index_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def setting_exists(conn: sqlite3.Connection, key: str) -> bool:
    if not table_exists(conn, "imp_settings"):
        return False
    cur = conn.execute("SELECT 1 FROM imp_settings WHERE key=?", (key,))
    return cur.fetchone() is not None


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.backup-pre-imp-r6-schema-{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_schema(db_path: Path, dry_run: bool) -> dict:
    summary = {
        "tables_created": [],
        "tables_skipped": [],
        "indexes_created": [],
        "indexes_skipped": [],
        "settings_inserted": [],
        "settings_skipped": [],
        "alters_applied": [],
        "alters_skipped": [],
    }

    conn = sqlite3.connect(str(db_path))
    try:
        # Tables
        for name, schema in [
            ("import_wishlist", WISHLIST_SCHEMA),
            ("import_free_unit", FREE_UNIT_SCHEMA),
            ("imp_settings", IMP_SETTINGS_SCHEMA),
            ("import_items", IMPORT_ITEMS_SCHEMA),  # R6 NEW · tabla nueva para promoted items (Diego dec 2026-04-28)
        ]:
            if table_exists(conn, name):
                summary["tables_skipped"].append(name)
            else:
                if not dry_run:
                    conn.executescript(schema)
                summary["tables_created"].append(name)

        # Indexes
        for idx_name, idx_sql in INDEXES:
            if index_exists(conn, idx_name):
                summary["indexes_skipped"].append(idx_name)
            else:
                if not dry_run:
                    conn.execute(idx_sql)
                summary["indexes_created"].append(idx_name)

        # Settings seed (requires imp_settings table to exist · in dry-run we still report what WOULD insert)
        for key, value in DEFAULT_SETTINGS:
            already = setting_exists(conn, key) if not dry_run else False
            # In dry-run if table didn't exist before, treat all as would-insert
            if already:
                summary["settings_skipped"].append(key)
            else:
                if not dry_run:
                    conn.execute(
                        "INSERT OR IGNORE INTO imp_settings (key, value, updated_by) VALUES (?, ?, 'apply_imp_schema')",
                        (key, value),
                    )
                summary["settings_inserted"].append(key)

        # Optional ALTER (notes_extra) · DEFERRED v0.5 (master overview line 70 mentions; spec doesn't require)
        # Skipping to avoid noise. If needed, uncomment:
        # try:
        #     if not dry_run:
        #         conn.execute("ALTER TABLE imports ADD COLUMN notes_extra TEXT")
        #     summary["alters_applied"].append("imports.notes_extra")
        # except sqlite3.OperationalError as e:
        #     if "duplicate column" in str(e).lower():
        #         summary["alters_skipped"].append("imports.notes_extra (already exists)")
        #     else:
        #         raise

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    return summary


def print_summary(summary: dict, dry_run: bool):
    label = "[DRY-RUN · would do]" if dry_run else "[APPLIED]"
    print(f"\n{label} schema apply summary:")
    print(f"  Tables created:    {summary['tables_created'] or '(none)'}")
    print(f"  Tables skipped:    {summary['tables_skipped'] or '(none)'}")
    print(f"  Indexes created:   {summary['indexes_created'] or '(none)'}")
    print(f"  Indexes skipped:   {summary['indexes_skipped'] or '(none)'}")
    print(f"  Settings seeded:   {summary['settings_inserted'] or '(none)'}")
    print(f"  Settings skipped:  {summary['settings_skipped'] or '(none)'}")


MAIN_DB_PATH = r"C:/Users/Diego/el-club/erp/elclub.db"  # PRODUCTION main DB


def confirm_main_db_safety(db_path: Path, default_used: bool):
    """
    Safety prompt cuando --apply va a tocar la main DB de produccion.
    Bypassed si DB resuelta es claramente una worktree/temp/test (ej. el-club-imp).
    """
    db_str = str(db_path).replace("\\", "/").lower()
    is_main = ("el-club/erp" in db_str) and ("el-club-imp" not in db_str)
    if not is_main:
        return  # safe path · skip prompt

    if default_used:
        warn = f"WARN  About to apply schema to MAIN DB ({db_path}). This is the production database. Confirm? (yes/no): "
    else:
        warn = f"WARN  --db-path resolves to MAIN DB ({db_path}). Confirm? (yes/no): "
    if input(warn).strip().lower() != "yes":
        print("Aborted by user.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without changes")
    group.add_argument("--apply", action="store_true", help="Apply changes (with backup)")
    parser.add_argument("--db-path", default=DEFAULT_DB, help=f"DB path (default: {DEFAULT_DB})")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        sys.exit(2)

    print(f"DB: {db_path}")

    # Safety prompt before any --apply against MAIN production DB
    if args.apply:
        default_used = (args.db_path == DEFAULT_DB)
        confirm_main_db_safety(db_path, default_used)

    # Backup MANDATORY when --apply (even if user says yes a la safety prompt)
    if args.apply:
        backup = backup_db(db_path)
        print(f"Backup written: {backup}")

    summary = apply_schema(db_path, dry_run=args.dry_run)
    print_summary(summary, dry_run=args.dry_run)

    print("\nOK." if not args.dry_run else "\nDry-run complete · re-run with --apply to commit.")


if __name__ == "__main__":
    main()
