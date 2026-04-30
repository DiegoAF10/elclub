// CANARY · This test asserts the close_import_proportional behavior PRE-R4-modification.
// Must continue to pass AFTER Task 5 modifies the function to also create free units.
// If this fails post-mod · STOP and escalate.
//
// Uses a SYNTHETIC fixture (IMP-CANARY-001) seeded inside a temp DB — worktree DB
// has zero imports (Diego wiped 2026-04-29 09:52). Pattern follows imp_r15_*_test.rs.
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<u32> = Mutex::new(0);

/// Builds a temp DB with the full schema needed by impl_close_import_proportional:
/// imports + sale_items + jerseys + import_free_unit (R4 stage table — already
/// landed in worktree DB). Seeds IMP-CANARY-001 with 22 paid sale_items.
fn setup_canary_db(label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!(
        "imp_r4_canary_{}_{}.db",
        std::process::id(),
        label
    ));
    if path.exists() {
        std::fs::remove_file(&path).unwrap();
    }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(
        r#"
        CREATE TABLE imports (
          import_id TEXT PRIMARY KEY, paid_at TEXT, arrived_at TEXT, supplier TEXT,
          bruto_usd REAL, shipping_gtq REAL, fx REAL DEFAULT 7.73,
          total_landed_gtq REAL, n_units INTEGER, unit_cost REAL,
          status TEXT, notes TEXT, created_at TEXT,
          tracking_code TEXT, carrier TEXT DEFAULT 'DHL', lead_time_days INTEGER
        );
        CREATE TABLE sale_items (
          item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          sale_id TEXT, family_id TEXT, jersey_id TEXT,
          import_id TEXT, unit_cost REAL, unit_cost_usd REAL,
          item_type TEXT DEFAULT 'paid'
        );
        CREATE TABLE jerseys (
          jersey_id TEXT PRIMARY KEY, family_id TEXT,
          import_id TEXT, cost REAL, unit_cost_usd REAL
        );
        CREATE TABLE import_free_unit (
          free_unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
          import_id TEXT NOT NULL, family_id TEXT, jersey_id TEXT,
          destination TEXT, destination_ref TEXT,
          assigned_at TEXT, assigned_by TEXT, notes TEXT,
          created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE import_items (
          import_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
          import_id TEXT NOT NULL, wishlist_item_id INTEGER,
          family_id TEXT NOT NULL, jersey_id TEXT, size TEXT,
          player_name TEXT, player_number INTEGER, patch TEXT, version TEXT,
          customer_id TEXT, expected_usd REAL,
          unit_cost_usd REAL, unit_cost_gtq REAL,
          status TEXT DEFAULT 'pending',
          sale_item_id INTEGER, jersey_id_published TEXT,
          notes TEXT, created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        -- Seed canary fixture: 22 paid items uniform at $5 each.
        -- Expected total_landed = bruto_usd * fx + shipping_gtq = 100 * 7.73 + 200 = 973.0
        -- Expected avg unit_cost = 973 / 22 = 44.227... → rounded = 44
        -- Expected lead_time_days = days(2026-04-09 - 2026-04-01) = 8
        INSERT INTO imports (
          import_id, paid_at, arrived_at, supplier, bruto_usd,
          shipping_gtq, fx, n_units, status, created_at
        ) VALUES (
          'IMP-CANARY-001', '2026-04-01', '2026-04-09', 'Bond',
          100.0, 200.0, 7.73, 22, 'arrived', '2026-04-01 10:00:00'
        );
        "#,
    )
    .unwrap();
    // Insert 22 sale_items with import_id='IMP-CANARY-001'.
    // Mix of unit_cost_usd populated (first 11) and NULL (last 11) — simulates real-world.
    for i in 1..=11 {
        conn.execute(
            "INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type) \
             VALUES (?, 'fam-canary', 'IMP-CANARY-001', 5.0, 'paid')",
            rusqlite::params![format!("S-{}", i)],
        )
        .unwrap();
    }
    for i in 12..=22 {
        conn.execute(
            "INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type) \
             VALUES (?, 'fam-canary', 'IMP-CANARY-001', NULL, 'paid')",
            rusqlite::params![format!("S-{}", i)],
        )
        .unwrap();
    }
    env::set_var("ERP_DB_PATH", &path);
    path
}

#[tokio::test]
async fn canary_close_status_transitions_to_closed() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_canary_db("status");
    use el_club_erp_lib::*;

    let result = impl_close_import_proportional("IMP-CANARY-001".to_string()).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);

    let conn = Connection::open(&path).unwrap();
    let status: String = conn
        .query_row(
            "SELECT status FROM imports WHERE import_id='IMP-CANARY-001'",
            [],
            |r| r.get(0),
        )
        .unwrap();
    assert_eq!(status, "closed", "status must transition to closed");
}

#[tokio::test]
async fn canary_close_total_landed_and_n_units_match_formula() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_canary_db("totals");
    use el_club_erp_lib::*;

    let result = impl_close_import_proportional("IMP-CANARY-001".to_string()).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let r = result.unwrap();
    assert_eq!(r.n_items_updated, 22, "should update 22 sale_items");
    assert_eq!(r.n_jerseys_updated, 0, "no jerseys in canary fixture");
    assert!(
        (r.total_landed_gtq - 973.0).abs() < 0.01,
        "total_landed_gtq = bruto*fx + shipping = 100*7.73 + 200 = 973.0 · got {}",
        r.total_landed_gtq
    );

    let conn = Connection::open(&path).unwrap();
    let (total_landed, n_units, unit_cost, lead_time): (f64, i64, f64, Option<i64>) = conn
        .query_row(
            "SELECT total_landed_gtq, n_units, unit_cost, lead_time_days \
             FROM imports WHERE import_id='IMP-CANARY-001'",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )
        .unwrap();
    assert!((total_landed - 973.0).abs() < 0.01, "total_landed_gtq stored = 973.0 · got {}", total_landed);
    assert_eq!(n_units, 22, "n_units stored = 22");
    // avg = 973/22 = 44.227... rounded = 44
    assert!((unit_cost - 44.0).abs() < 0.5, "avg unit_cost ~= 44 · got {}", unit_cost);
    assert_eq!(lead_time, Some(8), "lead_time_days = days(2026-04-09 - 2026-04-01) = 8");
}

#[tokio::test]
async fn canary_close_prorrateo_sets_unit_cost_on_all_sale_items() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_canary_db("prorrateo");
    use el_club_erp_lib::*;

    impl_close_import_proportional("IMP-CANARY-001".to_string()).await.unwrap();

    let conn = Connection::open(&path).unwrap();
    let (count_set, count_total, avg_cost, sum_cost): (i64, i64, f64, f64) = conn
        .query_row(
            "SELECT \
                SUM(CASE WHEN unit_cost IS NOT NULL THEN 1 ELSE 0 END) as count_set, \
                COUNT(*) as count_total, \
                AVG(unit_cost) as avg_cost, \
                SUM(unit_cost) as sum_cost \
             FROM sale_items WHERE import_id='IMP-CANARY-001'",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )
        .unwrap();
    assert_eq!(count_set, 22, "all 22 sale_items must have unit_cost set");
    assert_eq!(count_total, 22);
    // total_landed = 973 · sum should be ~973 (rounding noise possible)
    assert!(
        (sum_cost - 973.0).abs() < 22.0,
        "sum of unit_costs ≈ total_landed (973 · ±rounding) · got {}",
        sum_cost
    );
    // avg ≈ 44 GTQ per item
    assert!(
        (avg_cost - 44.0).abs() < 1.0,
        "avg unit_cost ≈ 44 GTQ · got {}",
        avg_cost
    );
}
