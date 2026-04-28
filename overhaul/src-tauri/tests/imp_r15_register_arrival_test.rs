use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

// Process-wide lock to serialize tests (each test mutates ERP_DB_PATH env var)
static DB_LOCK: Mutex<u32> = Mutex::new(0);

fn setup_with_paid_import(label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_arrival_test_{}_{}.db", std::process::id(), label));
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
        VALUES ('IMP-2026-04-28', '2026-04-20', 'Bond', 372.64, 7.73, 27, 'paid', '2026-04-20 10:00:00');
    "#).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    path
}

#[tokio::test]
async fn test_register_arrival_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("happy");
    use el_club_erp_lib::*;

    let input = RegisterArrivalInput {
        import_id: "IMP-2026-04-28".to_string(),
        arrived_at: "2026-04-28".to_string(),
        shipping_gtq: 522.67,
        tracking_code: Some("DHL1234567890".to_string()),
    };

    let result = impl_register_arrival(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let imp = result.unwrap();
    assert_eq!(imp.arrived_at.as_deref(), Some("2026-04-28"));
    assert_eq!(imp.shipping_gtq, Some(522.67));
    assert_eq!(imp.status, "arrived");
    assert_eq!(imp.lead_time_days, Some(8)); // 2026-04-20 → 2026-04-28
    assert_eq!(imp.tracking_code.as_deref(), Some("DHL1234567890"));
}

#[tokio::test]
async fn test_register_arrival_status_guard() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("status_guard");
    use el_club_erp_lib::*;

    // Force status='closed'
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute("UPDATE imports SET status='closed' WHERE import_id=?1", ["IMP-2026-04-28"]).unwrap();

    let input = RegisterArrivalInput {
        import_id: "IMP-2026-04-28".to_string(),
        arrived_at: "2026-04-28".to_string(),
        shipping_gtq: 522.67,
        tracking_code: None,
    };

    let result = impl_register_arrival(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("cannot register arrival"));
}

#[tokio::test]
async fn test_register_arrival_idempotent() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_paid_import("idempotent");
    use el_club_erp_lib::*;

    let input = RegisterArrivalInput {
        import_id: "IMP-2026-04-28".to_string(),
        arrived_at: "2026-04-28".to_string(),
        shipping_gtq: 522.67,
        tracking_code: None,
    };

    impl_register_arrival(input.clone()).await.unwrap();
    // Second call should succeed (idempotent re-register OK on 'arrived' status, not 'closed')
    let result = impl_register_arrival(input).await;
    assert!(result.is_ok(), "second register should succeed (idempotent)");
}
