// TDD: impl_close_import_proportional must INSERT floor(n_paid/10) rows into import_free_unit.
// Idempotent: re-closing must NOT duplicate.
//
// Uses synthetic temp DB fixtures (per imp_r15_*_test.rs pattern + R4 canary).
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<u32> = Mutex::new(0);

fn setup_db_with_n_items(import_id: &str, n_paid: usize, label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!(
        "imp_r4_free_create_{}_{}.db",
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
        "#,
    )
    .unwrap();
    conn.execute(
        "INSERT INTO imports (import_id, paid_at, arrived_at, supplier, bruto_usd, \
                              shipping_gtq, fx, n_units, status, created_at) \
         VALUES (?, '2026-04-01', '2026-04-09', 'Bond', ?, 0.0, 7.73, ?, 'arrived', '2026-04-01 10:00:00')",
        rusqlite::params![import_id, (n_paid as f64) * 13.0, n_paid as i64],
    )
    .unwrap();
    for i in 1..=n_paid {
        conn.execute(
            "INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type) \
             VALUES (?, 'fam-x', ?, 13.0, 'paid')",
            rusqlite::params![format!("S-{}", i), import_id],
        )
        .unwrap();
    }
    env::set_var("ERP_DB_PATH", &path);
    path
}

fn count_free_units(path: &PathBuf, import_id: &str) -> i64 {
    let conn = Connection::open(path).unwrap();
    conn.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE import_id = ?",
        rusqlite::params![import_id],
        |r| r.get(0),
    )
    .unwrap()
}

#[tokio::test]
async fn close_22_paid_creates_2_free_units() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_db_with_n_items("IMP-22-CANARY", 22, "n22");
    use el_club_erp_lib::*;
    impl_close_import_proportional("IMP-22-CANARY".to_string())
        .await
        .unwrap();
    assert_eq!(count_free_units(&path, "IMP-22-CANARY"), 2, "floor(22/10) = 2");
}

#[tokio::test]
async fn close_9_paid_creates_0_free_units() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_db_with_n_items("IMP-9-CANARY", 9, "n9");
    use el_club_erp_lib::*;
    impl_close_import_proportional("IMP-9-CANARY".to_string())
        .await
        .unwrap();
    assert_eq!(count_free_units(&path, "IMP-9-CANARY"), 0, "floor(9/10) = 0");
}

#[tokio::test]
async fn close_30_paid_creates_3_free_units() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_db_with_n_items("IMP-30-CANARY", 30, "n30");
    use el_club_erp_lib::*;
    impl_close_import_proportional("IMP-30-CANARY".to_string())
        .await
        .unwrap();
    assert_eq!(count_free_units(&path, "IMP-30-CANARY"), 3, "floor(30/10) = 3");
}

#[tokio::test]
async fn close_idempotent_no_duplicate_free_units() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_db_with_n_items("IMP-IDEMP-CANARY", 22, "idemp");
    use el_club_erp_lib::*;
    impl_close_import_proportional("IMP-IDEMP-CANARY".to_string())
        .await
        .unwrap();
    let first = count_free_units(&path, "IMP-IDEMP-CANARY");
    assert_eq!(first, 2);

    // Reset status to allow re-close (simulates Diego's "re-open then close" admin action)
    let conn = Connection::open(&path).unwrap();
    conn.execute(
        "UPDATE imports SET status='arrived' WHERE import_id='IMP-IDEMP-CANARY'",
        [],
    )
    .unwrap();
    drop(conn);

    let result = impl_close_import_proportional("IMP-IDEMP-CANARY".to_string()).await;
    assert!(result.is_ok(), "re-close must succeed");
    let second = count_free_units(&path, "IMP-IDEMP-CANARY");
    assert_eq!(
        second, 2,
        "re-close must NOT create duplicate free units (idempotency guard)"
    );
}
