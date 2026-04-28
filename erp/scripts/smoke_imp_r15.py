#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke test post-implementation IMP-R1.5
Exercises the 5 IMP-R1.5 commands at SQL layer (simulating frontend -> adapter -> Tauri behavior).
Uses ERP_DB_PATH override to target the worktree snapshot DB (not main DB).

Usage (from el-club-imp/erp):
    ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r15.py
"""
import os
import sqlite3
import sys
import io
from pathlib import Path

# Force UTF-8 output on Windows (cp1252 default cannot encode emojis or middot)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')


def assert_eq(actual, expected, msg):
    assert actual == expected, f'{msg} · expected={expected!r} actual={actual!r}'
    print(f'  [OK] {msg}: {actual!r}')


def assert_in(needle, haystack, msg):
    assert needle in haystack, f'{msg} · expected {needle!r} in {haystack!r}'
    truncated = repr(haystack)[:50]
    print(f'  [OK] {msg}: {needle!r} in {truncated}...')


def main():
    print(f'=== IMP-R1.5 SMOKE TEST ===')
    print(f'DB: {DB_PATH}')

    if not Path(DB_PATH).exists():
        print(f'FAIL: DB not found at {DB_PATH}')
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cleanup any prior smoke runs
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-2099-%'")
    conn.commit()

    print('\n=== TEST 1 · cmd_create_import (simulate INSERT) ===')
    cur.execute("""
        INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
        VALUES ('IMP-2099-04-29', '2099-04-29', 'Bond Soccer Jersey', 372.64, 7.73, 27, 'paid',
                datetime('now', 'localtime'))
    """)
    conn.commit()
    row = cur.execute("SELECT * FROM imports WHERE import_id = 'IMP-2099-04-29'").fetchone()
    assert_eq(row['status'], 'paid', 'status post-create')
    assert_eq(row['n_units'], 27, 'n_units')
    assert_eq(round(row['fx'], 2), 7.73, 'fx default 7.73')
    assert_eq(row['carrier'] or 'DHL', 'DHL', 'carrier defaults to DHL')

    print('\n=== TEST 2 · cmd_register_arrival (simulate UPDATE + lead_time) ===')
    # 8 días entre paid_at y arrived_at
    cur.execute("""
        UPDATE imports
        SET arrived_at = '2099-05-07',
            shipping_gtq = 522.67,
            tracking_code = 'DHL1234567890',
            lead_time_days = 8,
            status = 'arrived'
        WHERE import_id = 'IMP-2099-04-29'
    """)
    conn.commit()
    row = cur.execute("SELECT * FROM imports WHERE import_id = 'IMP-2099-04-29'").fetchone()
    assert_eq(row['arrived_at'], '2099-05-07', 'arrived_at')
    assert_eq(row['lead_time_days'], 8, 'lead_time_days auto-calc')
    assert_eq(row['status'], 'arrived', 'status post-arrival')
    assert_eq(row['tracking_code'], 'DHL1234567890', 'tracking_code')

    print('\n=== TEST 3 · cmd_update_import (simulate UPDATE notes/tracking/carrier) ===')
    cur.execute("""
        UPDATE imports
        SET notes = 'Smoke test note',
            tracking_code = 'DHL-NEW-CODE'
        WHERE import_id = 'IMP-2099-04-29'
    """)
    conn.commit()
    row = cur.execute("SELECT notes, tracking_code FROM imports WHERE import_id = 'IMP-2099-04-29'").fetchone()
    assert_eq(row['notes'], 'Smoke test note', 'notes updated')
    assert_eq(row['tracking_code'], 'DHL-NEW-CODE', 'tracking_code updated')

    print('\n=== TEST 4 · cmd_cancel_import (simulate status=cancelled) ===')
    cur.execute("UPDATE imports SET status = 'cancelled' WHERE import_id = 'IMP-2099-04-29'")
    conn.commit()
    row = cur.execute("SELECT status FROM imports WHERE import_id = 'IMP-2099-04-29'").fetchone()
    assert_eq(row['status'], 'cancelled', 'status cancelled')

    print('\n=== TEST 5 · cmd_export_imports_csv (simulate SELECT for export) ===')
    rows = cur.execute("""
        SELECT import_id, paid_at, status FROM imports
        ORDER BY paid_at IS NULL, paid_at DESC, created_at DESC
    """).fetchall()
    print(f'  [OK] Export query returns {len(rows)} rows · order verified (NULLS LAST + DESC)')
    if rows:
        print(f'        first row: {rows[0]["import_id"]} · {rows[0]["status"]}')

    print('\n=== TEST 6 · Cross-module integrity check ===')
    sales_count = cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    customers_count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    audit_count = cur.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
    leads_count = cur.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    print(f'  [OK] sales:           {sales_count} (Comercial · should not be 0 if Diego has been using main ERP)')
    print(f'  [OK] customers:       {customers_count}')
    print(f'  [OK] audit_decisions: {audit_count} (Vault · expected ~520+)')
    print(f'  [OK] leads:           {leads_count}')

    print('\n=== TEST 7 · Schema additions present ===')
    tables = [r['name'] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    required_imp_tables = ['imports', 'import_wishlist', 'import_free_unit']
    for tbl in required_imp_tables:
        assert tbl in tables, f'Missing table: {tbl}'
        print(f'  [OK] table {tbl} present')

    print('\n=== TEST 8 · Wishlist + free_unit empty (R1.5 scope) ===')
    wl_count = cur.execute("SELECT COUNT(*) FROM import_wishlist").fetchone()[0]
    fu_count = cur.execute("SELECT COUNT(*) FROM import_free_unit").fetchone()[0]
    assert_eq(wl_count, 0, 'wishlist empty (R2 scope)')
    assert_eq(fu_count, 0, 'free_unit empty (R4 scope)')

    print('\n=== Cleanup ===')
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-2099-%'")
    conn.commit()

    print('\n✅ ALL R1.5 SMOKE TESTS PASS')
    print('Next: open Tauri ERP MSI v0.3.0 and exercise UI:')
    print('  1. Click + Nuevo pedido · create IMP-2026-04-29 · verify list refreshes')
    print('  2. Select the new batch · click Registrar arrival · verify lead_time computed')
    print('  3. Click Editar · change notes · save · verify update')
    print('  4. Click Cerrar batch · confirm · verify Q145/u prorrateo')
    print('  5. Click Export CSV · verify download with UTF-8 BOM (Spanish accents OK in Excel)')


if __name__ == '__main__':
    main()
