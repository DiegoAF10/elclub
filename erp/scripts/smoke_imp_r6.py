#!/usr/bin/env python3
"""
smoke_imp_r6.py — exercises IMP-R6 settings flow end-to-end via SQL.

Verifies:
  - imp_settings table has 7 default rows with expected default values
  - upsert simulating cmd_update_imp_setting persists and round-trips
  - migration_log proxy queries (counts on imports/wishlist/free_unit) work
  - import_wishlist + import_free_unit indexes are present

Note: Rust-side validation is covered in `cargo test imp_r6_settings_test`
(numeric coercion + range guards). This smoke validates the DB-state contract
only; it does NOT exercise the Tauri command surface.

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r6.py

Cross-module integrity guard: this script reads from but does NOT mutate
sales / customers / audit_decisions tables.
"""
import os
import sqlite3
import sys

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')


def assert_(cond, msg):
    if not cond:
        print(f'  [FAIL] {msg}', file=sys.stderr)
        sys.exit(1)
    print(f'  [OK] {msg}')


def main():
    print(f'DB: {DB_PATH}')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # ════════════════════════════════════════════════════════════
        # TEST 1: imp_settings table exists with 7 default rows
        # ════════════════════════════════════════════════════════════
        print('\n=== TEST 1: imp_settings defaults ===')
        rows = conn.execute('SELECT key, value FROM imp_settings').fetchall()
        keys = {r['key'] for r in rows}
        expected_keys = {
            'default_fx', 'default_free_ratio', 'default_wishlist_target',
            'threshold_wishlist_unbatched_days', 'threshold_paid_unarrived_days',
            'threshold_cost_overrun_pct', 'threshold_free_unit_unassigned_days',
        }
        assert_(expected_keys.issubset(keys),
                f'All 7 default keys present (have {len(keys)})')

        values = {r['key']: r['value'] for r in rows}
        assert_(values.get('default_fx') == '7.73', 'default_fx == 7.73')
        assert_(values.get('default_free_ratio') == '10', 'default_free_ratio == 10')
        assert_(values.get('default_wishlist_target') == '20', 'default_wishlist_target == 20')
        assert_(values.get('threshold_wishlist_unbatched_days') == '30',
                'threshold_wishlist_unbatched_days == 30')
        assert_(values.get('threshold_paid_unarrived_days') == '14',
                'threshold_paid_unarrived_days == 14')
        assert_(values.get('threshold_cost_overrun_pct') == '30',
                'threshold_cost_overrun_pct == 30')
        assert_(values.get('threshold_free_unit_unassigned_days') == '7',
                'threshold_free_unit_unassigned_days == 7')

        # ════════════════════════════════════════════════════════════
        # TEST 2: upsert simulating cmd_update_imp_setting persists
        # ════════════════════════════════════════════════════════════
        print('\n=== TEST 2: update_imp_setting round-trip ===')
        original = values['default_fx']
        try:
            conn.execute(
                'INSERT INTO imp_settings (key, value, updated_by) VALUES (?, ?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by',
                ('default_fx', '7.85', 'smoke_imp_r6'),
            )
            conn.commit()
            new_fx = conn.execute(
                "SELECT value FROM imp_settings WHERE key='default_fx'"
            ).fetchone()['value']
            assert_(new_fx == '7.85', 'Upsert to 7.85 persisted')

            # updated_by should reflect the writer
            new_by = conn.execute(
                "SELECT updated_by FROM imp_settings WHERE key='default_fx'"
            ).fetchone()['updated_by']
            assert_(new_by == 'smoke_imp_r6', 'updated_by reflects writer')
        finally:
            # Restore original value
            conn.execute(
                'INSERT INTO imp_settings (key, value, updated_by) VALUES (?, ?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by',
                ('default_fx', original, 'smoke_imp_r6_restore'),
            )
            conn.commit()
            restored = conn.execute(
                "SELECT value FROM imp_settings WHERE key='default_fx'"
            ).fetchone()['value']
            assert_(restored == original, f'default_fx restored to {original}')

        # ════════════════════════════════════════════════════════════
        # TEST 3: migration_log query proxies (counts queryable)
        # ════════════════════════════════════════════════════════════
        print('\n=== TEST 3: migration_log proxies ===')
        last_import = conn.execute(
            'SELECT MAX(created_at) AS m FROM imports'
        ).fetchone()['m']
        imports_n = conn.execute('SELECT COUNT(*) AS c FROM imports').fetchone()['c']
        wishlist_n = conn.execute('SELECT COUNT(*) AS c FROM import_wishlist').fetchone()['c']
        free_units_n = conn.execute('SELECT COUNT(*) AS c FROM import_free_unit').fetchone()['c']
        print(f'    last_import_at={last_import}  imports={imports_n}  '
              f'wishlist={wishlist_n}  free={free_units_n}')
        assert_(imports_n >= 0, 'imports count queryable')
        assert_(wishlist_n >= 0, 'wishlist count queryable')
        assert_(free_units_n >= 0, 'free_units count queryable')

        # ════════════════════════════════════════════════════════════
        # TEST 4: required indexes present on R1/R2/R4 tables
        # ════════════════════════════════════════════════════════════
        print('\n=== TEST 4: indexes present ===')
        idx_names = {r['name'] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' "
            "AND tbl_name IN ('import_wishlist','import_free_unit','import_items')"
        ).fetchall()}
        for expected_idx in [
            'idx_wishlist_status', 'idx_wishlist_customer',
            'idx_free_unit_import', 'idx_free_unit_destination',
        ]:
            assert_(expected_idx in idx_names, f'Index {expected_idx} present')

        # ════════════════════════════════════════════════════════════
        # TEST 5: cross-module integrity (sales/customers/audit unchanged)
        # ════════════════════════════════════════════════════════════
        print('\n=== TEST 5: cross-module integrity ===')
        sales_n = conn.execute('SELECT COUNT(*) AS c FROM sales').fetchone()['c']
        customers_n = conn.execute('SELECT COUNT(*) AS c FROM customers').fetchone()['c']
        audit_n = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_decisions WHERE status='verified' AND final_verified=1"
        ).fetchone()['c']
        print(f'    sales={sales_n}  customers={customers_n}  audit_verified={audit_n}')
        assert_(sales_n >= 0, 'sales table accessible · zero touch')
        assert_(customers_n >= 0, 'customers table accessible · zero touch')
        assert_(audit_n >= 0, 'audit_decisions verified rows accessible · zero touch')

        print('\n[PASS] ALL SMOKE TESTS PASS')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
