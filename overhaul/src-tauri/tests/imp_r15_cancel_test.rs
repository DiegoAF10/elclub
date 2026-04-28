use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<u32> = Mutex::new(0);

fn setup_with_paid_import(label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_cancel_test_{}_{}.db", std::process::id(), label));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }
    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imports (
          import_id TEXT PRIMARY KEY, paid_at TEXT, arrived_at TEXT,
          supplier TEXT, bruto_usd REAL, shipping_gtq REAL,
          fx REAL DEFAULT 7.73, total_landed_gtq REAL, n_units INTEGER,
          unit_cost REAL, status TEXT, notes TEXT, created_at TEXT,
          tracking_code TEXT, carrier TEXT DEFAULT 'DHL', lead_time_days INTEGER
        );
        INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
        VALUES ('IMP-2026-04-28', '2026-04-28', 'Bond', 100.0, 7.73, 5, 'paid', '2026-04-28 10:00:00');
    "#).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    path
}

#[tokio::test]
async fn test_cancel_import_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("happy");
    use el_club_erp_lib::*;

    let result = impl_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    assert_eq!(result.unwrap().status, "cancelled");
}

#[tokio::test]
async fn test_cancel_import_idempotent() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("idempotent");
    use el_club_erp_lib::*;

    impl_cancel_import("IMP-2026-04-28".to_string()).await.unwrap();
    let result = impl_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_ok(), "second cancel should be idempotent OK");
    assert_eq!(result.unwrap().status, "cancelled");
}

#[tokio::test]
async fn test_cancel_closed_import_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("closed_rejected");
    use el_club_erp_lib::*;

    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute("UPDATE imports SET status='closed' WHERE import_id=?1", ["IMP-2026-04-28"]).unwrap();

    let result = impl_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("closed"));
}
