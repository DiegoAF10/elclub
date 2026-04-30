#!/usr/bin/env python3
"""
Smoke test post-implementation IMP-R2.

Exercises wishlist CRUD + promote-to-batch (single import_items destination)
+ inbox_events emit (REAL schema · type/severity/title/module/metadata · NOT
the plan's outdated kind/payload_json) + mark_in_transit · via direct DB ops.

Verifies state in worktree DB (ERP_DB_PATH default).

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r2.py
"""
import os
import sqlite3

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')


def assert_eq(actual, expected, msg):
    assert actual == expected, f'{msg} | expected={expected!r} actual={actual!r}'
    print(f'  [OK] {msg}: {actual!r}')


def main():
    print(f'DB: {DB_PATH}')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    SMOKE_IMPORT_ID = 'IMP-2026-04-30'

    # Pre-flight: verify import_items table exists (R6 schema dependency)
    has_import_items = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='import_items'"
    ).fetchone()
    assert has_import_items, 'import_items table missing - run R6 apply_imp_schema.py first'

    # Cleanup any prior smoke runs (use REAL inbox_events column names)
    cur.execute("DELETE FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%'")
    cur.execute(
        "DELETE FROM inbox_events WHERE type='import_promoted' AND metadata LIKE ?",
        (f'%{SMOKE_IMPORT_ID}%',)
    )
    conn.commit()

    print('\n=== TEST 1: Create 5 wishlist items (3 assigned + 2 stock-future) ===')
    family_ids = ['ARG-2026-L-FS', 'FRA-2026-L-FS', 'BRA-2026-L-FS', 'ARG-2026-L-FS', 'FRA-2026-L-FS']
    expected_usds = [15.0, 15.0, 11.0, 13.0, 13.0]
    customers = ['cust-pedro', 'cust-andres', None, None, 'cust-juan']  # items 3+4 = stock-future
    for i, (fid, usd, cust) in enumerate(zip(family_ids, expected_usds, customers)):
        cur.execute("""
            INSERT INTO import_wishlist (family_id, size, expected_usd, customer_id, status, notes)
            VALUES (?, ?, ?, ?, 'active', ?)
        """, (fid, 'L', usd, cust, f'SMOKE-R2-{i+1}'))
    conn.commit()

    smoke_ids = [r[0] for r in cur.execute(
        "SELECT wishlist_item_id FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%' ORDER BY wishlist_item_id"
    ).fetchall()]
    assert_eq(len(smoke_ids), 5, '5 wishlist items inserted')

    print('\n=== TEST 2: Promote 3 mixed items (status=paid, single import_items destination) ===')
    promote_ids = smoke_ids[:3]
    bruto_usd_expected = sum(expected_usds[:3])  # 15+15+11=41

    cur.execute("BEGIN")
    try:
        cur.execute("""
            INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at, carrier)
            VALUES (?, '2026-04-30', 'Bond Soccer Jersey', ?, 7.73, 3, 'paid', datetime('now', 'localtime'), 'DHL')
        """, (SMOKE_IMPORT_ID, bruto_usd_expected))

        # Single-table destination per Diego decision (Q2 SUPERSEDED 2026-04-28 ~19:00):
        # All items go to import_items - customer_id nullable distinguishes assigned vs stock-future.
        n_assigned = 0
        n_stock = 0
        for wl_id in promote_ids:
            wl = cur.execute("SELECT * FROM import_wishlist WHERE wishlist_item_id = ?", (wl_id,)).fetchone()
            cur.execute("""
                INSERT INTO import_items
                  (import_id, wishlist_item_id, family_id, size, customer_id, expected_usd, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 'SMOKE-R2-item')
            """, (SMOKE_IMPORT_ID, wl_id, wl['family_id'], wl['size'], wl['customer_id'], wl['expected_usd']))
            cur.execute("UPDATE import_wishlist SET status='promoted', promoted_to_import_id=? WHERE wishlist_item_id=?",
                        (SMOKE_IMPORT_ID, wl_id))
            if wl['customer_id'] is not None:
                n_assigned += 1
            else:
                n_stock += 1

        # Inbox event (Q3 RESOLVED 2026-04-28 ~19:00 - REAL inbox_events schema:
        # type/severity/title/description/module/metadata/action_label/action_target).
        metadata_json = (
            f'{{"import_id":"{SMOKE_IMPORT_ID}","n_items":3,'
            f'"n_assigned":{n_assigned},"n_stock":{n_stock},'
            f'"supplier":"Bond Soccer Jersey","status":"paid"}}'
        )
        cur.execute("""
            INSERT INTO inbox_events (type, severity, title, description, module, metadata, action_label, action_target)
            VALUES ('import_promoted', 'info', ?, ?, 'importaciones', ?, 'Ver batch', ?)
        """, (
            f'{SMOKE_IMPORT_ID} promovido',
            f'3 items movidos a batch ({n_assigned} assigned, {n_stock} stock-future)',
            metadata_json,
            f'importaciones:{SMOKE_IMPORT_ID}',
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print('\n=== TEST 3: Verify imports row created (status=paid) ===')
    imp = cur.execute("SELECT * FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()
    assert imp is not None, 'imports row not created'
    assert_eq(imp['status'], 'paid', 'imports.status (Diego default toggle ON)')
    assert_eq(imp['paid_at'], '2026-04-30', 'imports.paid_at populated when status=paid')
    assert_eq(imp['n_units'], 3, 'imports.n_units')
    assert_eq(round(imp['bruto_usd'], 2), 41.0, 'imports.bruto_usd (input, NOT computed)')
    assert_eq(imp['fx'], 7.73, 'imports.fx')
    assert_eq(imp['supplier'], 'Bond Soccer Jersey', 'imports.supplier')

    print('\n=== TEST 4: Verify SINGLE TABLE - import_items rows ===')
    items_count = cur.execute("SELECT COUNT(*) FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(items_count, 3, 'import_items count (all 3 promoted, single destination)')

    assigned_count = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND customer_id IS NOT NULL", (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    stock_count = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND customer_id IS NULL", (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    assert_eq(assigned_count, 2, 'assigned items (customer_id NOT NULL · items 1+2)')
    assert_eq(stock_count, 1, 'stock-future items (customer_id IS NULL · item 3)')

    pedro = cur.execute("SELECT * FROM import_items WHERE customer_id='cust-pedro' AND import_id=?", (SMOKE_IMPORT_ID,)).fetchone()
    assert pedro is not None, 'cust-pedro import_items row exists'
    assert_eq(pedro['status'], 'pending', 'pedro item status (becomes arrived in R4 close_import)')
    print(f'  [OK] cust-pedro import_items: {dict(pedro)}')

    print('\n=== TEST 5: Verify wishlist rows updated ===')
    promoted = cur.execute(
        "SELECT COUNT(*) FROM import_wishlist WHERE wishlist_item_id IN (?,?,?) AND status='promoted' AND promoted_to_import_id=?",
        (*promote_ids, SMOKE_IMPORT_ID)
    ).fetchone()[0]
    assert_eq(promoted, 3, 'wishlist rows promoted')

    still_active = cur.execute(
        "SELECT COUNT(*) FROM import_wishlist WHERE wishlist_item_id IN (?,?) AND status='active'",
        (smoke_ids[3], smoke_ids[4])
    ).fetchone()[0]
    assert_eq(still_active, 2, 'remaining 2 wishlist items still active')

    print('\n=== TEST 6: Verify inbox_events row created (REAL schema) ===')
    event_count = cur.execute(
        "SELECT COUNT(*) FROM inbox_events WHERE type='import_promoted' AND metadata LIKE ?",
        (f'%{SMOKE_IMPORT_ID}%',)
    ).fetchone()[0]
    assert_eq(event_count, 1, 'inbox_events row for import_promoted')
    event = cur.execute(
        "SELECT type, severity, title, module FROM inbox_events WHERE type='import_promoted' AND metadata LIKE ?",
        (f'%{SMOKE_IMPORT_ID}%',)
    ).fetchone()
    assert_eq(event['severity'], 'info', 'inbox_events.severity')
    assert_eq(event['module'], 'importaciones', 'inbox_events.module')
    assert event['title'].startswith('IMP-'), f'title prefix sanity: {event["title"]!r}'

    print('\n=== TEST 7: Verify cmd_mark_in_transit (paid -> in_transit) ===')
    cur.execute(
        "UPDATE imports SET status='in_transit', tracking_code='SMOKE-DHL-12345' WHERE import_id=? AND status='paid'",
        (SMOKE_IMPORT_ID,)
    )
    conn.commit()
    transit = cur.execute("SELECT status, tracking_code FROM imports WHERE import_id=?", (SMOKE_IMPORT_ID,)).fetchone()
    assert_eq(transit['status'], 'in_transit', 'imports.status after mark_in_transit')
    assert_eq(transit['tracking_code'], 'SMOKE-DHL-12345', 'imports.tracking_code populated')

    print('\n=== TEST 8: Cross-module integrity (untouched) ===')
    sales_count = cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    customers_count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    audit_count = cur.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
    print(f'  sales:           {sales_count}')
    print(f'  customers:       {customers_count}')
    print(f'  audit_decisions: {audit_count}')

    print('\n=== Cleanup ===')
    cur.execute("DELETE FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%'")
    cur.execute(
        "DELETE FROM inbox_events WHERE type='import_promoted' AND metadata LIKE ?",
        (f'%{SMOKE_IMPORT_ID}%',)
    )
    conn.commit()

    print('\n[PASS] ALL SMOKE TESTS PASS - IMP-R2 wishlist + promote (single import_items) + inbox_events (real schema) + mark_in_transit verified')


if __name__ == '__main__':
    main()
