// Integration tests for impl_assign_free_unit / impl_unassign_free_unit
// Pattern lifted from imp_r15_*_test.rs (DB_LOCK + ERP_DB_PATH override).
use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

// Process-wide lock to serialize tests (each test mutates ERP_DB_PATH env var).
static DB_LOCK: Mutex<u32> = Mutex::new(0);

fn setup_temp_db_with_free_unit(label: &str) -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r4_assign_test_{}_{}.db", std::process::id(), label));
    if path.exists() {
        std::fs::remove_file(&path).unwrap();
    }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(
        r#"
        CREATE TABLE imports (
          import_id TEXT PRIMARY KEY,
          paid_at TEXT, arrived_at TEXT, supplier TEXT,
          bruto_usd REAL, shipping_gtq REAL, fx REAL, total_landed_gtq REAL,
          n_units INTEGER, unit_cost REAL, status TEXT, notes TEXT,
          created_at TEXT, tracking_code TEXT, carrier TEXT, lead_time_days INTEGER
        );
        CREATE TABLE customers (
          customer_id TEXT PRIMARY KEY, name TEXT, created_at TEXT
        );
        CREATE TABLE import_free_unit (
          free_unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
          import_id TEXT NOT NULL,
          family_id TEXT, jersey_id TEXT,
          destination TEXT, destination_ref TEXT,
          assigned_at TEXT, assigned_by TEXT, notes TEXT,
          created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
          VALUES ('IMP-2026-04-28', '2026-04-20', 'Bond', 100.0, 7.73, 22, 'closed', '2026-04-20 10:00:00');
        INSERT INTO customers (customer_id, name, created_at)
          VALUES ('CUST-001', 'Cliente VIP Test', '2026-04-28 10:00:00');
        INSERT INTO import_free_unit (import_id, created_at)
          VALUES ('IMP-2026-04-28', '2026-04-28 10:00:00');
        "#,
    )
    .unwrap();
    env::set_var("ERP_DB_PATH", &path);
    path
}

fn get_seeded_free_unit_id(path: &PathBuf) -> i64 {
    let conn = Connection::open(path).unwrap();
    conn.query_row(
        "SELECT free_unit_id FROM import_free_unit LIMIT 1",
        [],
        |r| r.get(0),
    )
    .unwrap()
}

#[tokio::test]
async fn test_assign_to_personal_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("personal_happy");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "personal".to_string(),
        destination_ref: None,
        family_id: None,
        jersey_id: None,
        notes: Some("Diego se la queda".to_string()),
    };
    let result = impl_assign_free_unit(input);
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let fu = result.unwrap();
    assert_eq!(fu.destination, Some("personal".to_string()));
    assert_eq!(fu.assigned_by, Some("diego".to_string()));
    assert!(fu.assigned_at.is_some());
}

#[tokio::test]
async fn test_assign_to_vip_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("vip_happy");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: Some("CUST-001".to_string()),
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    let result = impl_assign_free_unit(input);
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let fu = result.unwrap();
    assert_eq!(fu.destination, Some("vip".to_string()));
    assert_eq!(fu.destination_ref, Some("CUST-001".to_string()));
}

#[tokio::test]
async fn test_assign_to_mystery_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("mystery_happy");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "mystery".to_string(),
        destination_ref: Some("mystery_pool_2026_W17".to_string()),
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    assert!(impl_assign_free_unit(input).is_ok());
}

#[tokio::test]
async fn test_assign_to_garantizada_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("garantizada_happy");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "garantizada".to_string(),
        destination_ref: Some("Q475 publicacion".to_string()),
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    assert!(impl_assign_free_unit(input).is_ok());
}

#[tokio::test]
async fn test_assign_invalid_destination_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("invalid_dest");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "INVALID_DEST".to_string(),
        destination_ref: None,
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    let result = impl_assign_free_unit(input);
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("destination"));
}

#[tokio::test]
async fn test_assign_vip_without_customer_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("vip_no_cust");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: None,
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    let result = impl_assign_free_unit(input);
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("destination_ref"));
}

#[tokio::test]
async fn test_assign_vip_invalid_customer_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("vip_bad_cust");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: Some("CUST-NONEXISTENT".to_string()),
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    let result = impl_assign_free_unit(input);
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("customer"));
}

#[tokio::test]
async fn test_reassign_already_assigned_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("reassign");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let first = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "personal".to_string(),
        destination_ref: None,
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    impl_assign_free_unit(first).unwrap();

    let second = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: Some("CUST-001".to_string()),
        family_id: None,
        jersey_id: None,
        notes: None,
    };
    let result = impl_assign_free_unit(second);
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("already assigned"));
}

#[tokio::test]
async fn test_unassign_roundtrip() {
    let _guard = DB_LOCK.lock().unwrap();
    let path = setup_temp_db_with_free_unit("roundtrip");
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    impl_assign_free_unit(AssignFreeUnitInput {
        free_unit_id: id,
        destination: "personal".to_string(),
        destination_ref: None,
        family_id: None,
        jersey_id: None,
        notes: None,
    })
    .unwrap();

    let result = impl_unassign_free_unit(id);
    assert!(result.is_ok());
    let fu = result.unwrap();
    assert!(fu.destination.is_none());
    assert!(fu.assigned_at.is_none());
    assert!(fu.assigned_by.is_none());
    assert!(fu.destination_ref.is_none());
}
