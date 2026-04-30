#!/usr/bin/env python3
"""
apply_supplier_tracking.py — idempotent ALTER for IMP supplier WA mini-feature.

Adds 2 columns to import_items:
- sent_to_supplier_at  TEXT  (ISO 8601 timestamp · NULL = no enviado)
- sent_to_supplier_via TEXT  ('china' | 'hk' | NULL)

Safe to re-run · uses PRAGMA table_info to check existence before ALTER.
Backup obligatorio cuando --apply (no --dry-run).

Usage:
  python apply_supplier_tracking.py --dry-run                 # preview
  python apply_supplier_tracking.py --apply                   # apply + backup
  python apply_supplier_tracking.py --apply --db-path X.db    # explicit DB
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

# Columns to add (name → SQL ADD clause)
NEW_COLUMNS = [
    ("sent_to_supplier_at",  "ALTER TABLE import_items ADD COLUMN sent_to_supplier_at TEXT"),
    ("sent_to_supplier_via", "ALTER TABLE import_items ADD COLUMN sent_to_supplier_via TEXT"),
]


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{db_path.stem}.backup-before-supplier-tracking-{timestamp}{db_path.suffix}"
    backup_path = db_path.parent / backup_name
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply(db_path: Path, dry_run: bool) -> dict:
    summary = {
        "alters_applied": [],
        "alters_skipped": [],
        "errors": [],
    }

    conn = sqlite3.connect(str(db_path))
    try:
        if not table_exists(conn, "import_items"):
            summary["errors"].append(
                "import_items table does not exist · run apply_imp_schema.py first"
            )
            return summary

        for column, alter_sql in NEW_COLUMNS:
            if column_exists(conn, "import_items", column):
                summary["alters_skipped"].append(f"import_items.{column} (already exists)")
            else:
                if not dry_run:
                    conn.execute(alter_sql)
                summary["alters_applied"].append(f"import_items.{column}")

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    return summary


def print_summary(summary: dict, dry_run: bool):
    label = "[DRY-RUN · would do]" if dry_run else "[APPLIED]"
    print(f"\n{label} supplier tracking schema:")
    print(f"  Alters applied:  {summary['alters_applied'] or '(none)'}")
    print(f"  Alters skipped:  {summary['alters_skipped'] or '(none)'}")
    if summary["errors"]:
        print(f"  ERRORS:          {summary['errors']}")


MAIN_DB_PATH = r"C:/Users/Diego/el-club/erp/elclub.db"


def confirm_main_db_safety(db_path: Path, default_used: bool):
    db_str = str(db_path).replace("\\", "/").lower()
    is_main = ("el-club/erp" in db_str) and ("el-club-imp" not in db_str)
    if not is_main:
        return

    if default_used:
        warn = f"WARN  About to apply schema to MAIN DB ({db_path}). Confirm? (yes/no): "
    else:
        warn = f"WARN  --db-path resolves to MAIN DB ({db_path}). Confirm? (yes/no): "
    response = input(warn).strip().lower()
    if response != "yes":
        print("Aborted.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without applying")
    parser.add_argument("--apply", action="store_true", help="apply changes (with backup)")
    parser.add_argument("--db-path", default=None, help=f"DB path (default: {DEFAULT_DB})")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("must specify --dry-run or --apply")

    default_used = args.db_path is None
    db_path = Path(args.db_path or DEFAULT_DB)

    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}")
        sys.exit(1)

    if args.apply:
        confirm_main_db_safety(db_path, default_used)
        backup_path = backup_db(db_path)
        print(f"[backup] {backup_path}")

    summary = apply(db_path, dry_run=args.dry_run)
    print_summary(summary, args.dry_run)

    if summary["errors"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
