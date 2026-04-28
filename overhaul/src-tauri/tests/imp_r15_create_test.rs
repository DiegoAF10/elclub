// Integration test for cmd_create_import — uses temp DB via ERP_DB_PATH override
use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

// Global mutex to serialize tests that mutate ERP_DB_PATH env var
static DB_LOCK: Mutex<u32> = Mutex::new(0);

fn setup_temp_db(label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_create_test_{}_{}.db", std::process::id(), label));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    // Apply minimal schema for testing
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
    env::set_var("ERP_DB_PATH", &path);
    path
}

#[tokio::test]
async fn test_create_import_happy_path() {
    let _lock = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db("happy");
    use el_club_erp_lib::*;

    let input = CreateImportInput {
        import_id: "IMP-2026-04-28".to_string(),
        paid_at: "2026-04-28".to_string(),
        supplier: "Bond Soccer Jersey".to_string(),
        bruto_usd: 372.64,
        fx: 7.73,
        n_units: 27,
        notes: Some("Test import".to_string()),
        tracking_code: None,
        carrier: None,
    };

    let result = cmd_create_import(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let imp = result.unwrap();
    assert_eq!(imp.import_id, "IMP-2026-04-28");
    assert_eq!(imp.status, "paid");
    assert_eq!(imp.fx, 7.73);
    assert_eq!(imp.n_units, Some(27));
    assert_eq!(imp.carrier, "DHL"); // default
}

#[tokio::test]
async fn test_create_import_invalid_id_rejected() {
    let _lock = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db("invalid_id");
    use el_club_erp_lib::*;

    let input = CreateImportInput {
        import_id: "IMP-bad".to_string(),
        paid_at: "2026-04-28".to_string(),
        supplier: "Bond".to_string(),
        bruto_usd: 100.0,
        fx: 7.73,
        n_units: 5,
        notes: None,
        tracking_code: None,
        carrier: None,
    };

    let result = cmd_create_import(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("import_id format"));
}

#[tokio::test]
async fn test_create_import_duplicate_rejected() {
    let _lock = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db("duplicate");
    use el_club_erp_lib::*;

    let input1 = CreateImportInput {
        import_id: "IMP-2026-04-28".to_string(),
        paid_at: "2026-04-28".to_string(),
        supplier: "Bond".to_string(),
        bruto_usd: 100.0, fx: 7.73, n_units: 5,
        notes: None, tracking_code: None, carrier: None,
    };

    cmd_create_import(input1.clone()).await.unwrap();
    let result = cmd_create_import(input1).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("already exists"));
}

#[tokio::test]
async fn test_create_import_negative_bruto_rejected() {
    let _lock = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db("neg_bruto");
    use el_club_erp_lib::*;

    let input = CreateImportInput {
        import_id: "IMP-2026-04-28".to_string(),
        paid_at: "2026-04-28".to_string(),
        supplier: "Bond".to_string(),
        bruto_usd: -50.0,
        fx: 7.73, n_units: 5,
        notes: None, tracking_code: None, carrier: None,
    };

    let result = cmd_create_import(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("bruto_usd"));
}
