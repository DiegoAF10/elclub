// Integration test for cmd_mark_in_transit — state guard (paid → in_transit only)
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_db_with_import(status: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r2_mark_in_transit_test_{}_{}.db", std::process::id(), status));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imports (
          import_id        TEXT PRIMARY KEY,
          paid_at          TEXT,
          arrived_at       TEXT,
          supplier         TEXT DEFAULT 'Bond Soccer Jersey',
          bruto_usd        REAL,
          shipping_gtq     REAL,
          fx               REAL DEFAULT 7.73,
          total_landed_gtq REAL,
          n_units          INTEGER,
          unit_cost        REAL,
          status           TEXT,
          notes            TEXT,
          created_at       TEXT,
          tracking_code    TEXT,
          carrier          TEXT DEFAULT 'DHL',
          lead_time_days   INTEGER
        );
    "#).unwrap();
    conn.execute(
        "INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
         VALUES ('IMP-2026-04-30', '2026-04-30', 'Bond', 100.0, 7.73, 5, ?1, '2026-04-30 10:00:00')",
        rusqlite::params![status],
    ).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    path
}

#[tokio::test]
async fn test_mark_in_transit_happy_path_from_paid() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_db_with_import("paid");
    use el_club_erp_lib::*;

    let result = impl_mark_in_transit(
        "IMP-2026-04-30".to_string(),
        Some("DHL-TRACK-12345".to_string()),
    ).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let imp = result.unwrap();
    assert_eq!(imp.status, "in_transit");
    assert_eq!(imp.tracking_code.as_deref(), Some("DHL-TRACK-12345"));
}

#[tokio::test]
async fn test_mark_in_transit_from_draft_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_db_with_import("draft");
    use el_club_erp_lib::*;

    let result = impl_mark_in_transit("IMP-2026-04-30".to_string(), None).await;
    assert!(result.is_err());
    let err = format!("{:?}", result.unwrap_err());
    assert!(err.contains("'paid'") && err.contains("draft"),
            "expected 'must be paid' rejection, got: {}", err);
}

#[tokio::test]
async fn test_mark_in_transit_from_in_transit_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_db_with_import("in_transit");
    use el_club_erp_lib::*;

    let result = impl_mark_in_transit("IMP-2026-04-30".to_string(), None).await;
    assert!(result.is_err());
    let err = format!("{:?}", result.unwrap_err());
    assert!(err.contains("already") || err.contains("in_transit"),
            "expected already-in-transit rejection, got: {}", err);
}

#[tokio::test]
async fn test_mark_in_transit_tracking_code_coalesce() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_db_with_import("paid");
    use el_club_erp_lib::*;

    // Pre-set a tracking_code · then call with None · should preserve existing
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute(
        "UPDATE imports SET tracking_code='OLD-TRACK-999' WHERE import_id='IMP-2026-04-30'",
        [],
    ).unwrap();

    let result = impl_mark_in_transit("IMP-2026-04-30".to_string(), None).await;
    assert!(result.is_ok());
    let imp = result.unwrap();
    assert_eq!(imp.tracking_code.as_deref(), Some("OLD-TRACK-999"),
               "tracking_code should be preserved when input is None (COALESCE)");
}
