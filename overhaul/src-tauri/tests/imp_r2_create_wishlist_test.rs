// Integration test for cmd_create_wishlist_item — D7=B validation
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

// Serialize all tests in this binary that mutate ERP_DB_PATH / ELCLUB_CATALOG_PATH
static DB_LOCK: Mutex<()> = Mutex::new(());

fn fixture_catalog() -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("tests/fixtures/catalog_minimal.json");
    p
}

fn setup_temp_db() -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r2_create_wl_test_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE import_wishlist (
          wishlist_item_id  INTEGER PRIMARY KEY AUTOINCREMENT,
          family_id         TEXT NOT NULL,
          jersey_id         TEXT,
          size              TEXT,
          player_name       TEXT,
          player_number     INTEGER,
          patch             TEXT,
          version           TEXT,
          customer_id       TEXT,
          expected_usd      REAL,
          status            TEXT DEFAULT 'active'
                            CHECK(status IN ('active','promoted','cancelled')),
          promoted_to_import_id TEXT,
          created_at        TEXT DEFAULT (datetime('now', 'localtime')),
          notes             TEXT
        );
    "#).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    env::set_var("ELCLUB_CATALOG_PATH", fixture_catalog());
    path
}

#[tokio::test]
async fn test_create_wishlist_happy_path() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db();
    use el_club_erp_lib::*;

    let input = CreateWishlistItemInput {
        family_id: "ARG-2026-L-FS".to_string(),
        jersey_id: None,
        size: Some("L".to_string()),
        player_name: Some("Messi".to_string()),
        player_number: Some(10),
        patch: Some("WC".to_string()),
        version: Some("fan".to_string()),
        customer_id: None,
        expected_usd: Some(15.0),
        notes: Some("VIP request".to_string()),
    };

    let result = impl_create_wishlist_item(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let item = result.unwrap();
    assert_eq!(item.family_id, "ARG-2026-L-FS");
    assert_eq!(item.status, "active");
    assert_eq!(item.player_name.as_deref(), Some("Messi"));
    assert_eq!(item.player_number, Some(10));
}

#[tokio::test]
async fn test_create_wishlist_unknown_family_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db();
    use el_club_erp_lib::*;

    let input = CreateWishlistItemInput {
        family_id: "FAKE-XXXX-X-XX".to_string(),
        jersey_id: None, size: None, player_name: None, player_number: None,
        patch: None, version: None, customer_id: None, expected_usd: None, notes: None,
    };

    let result = impl_create_wishlist_item(input).await;
    assert!(result.is_err());
    let err = format!("{:?}", result.unwrap_err());
    assert!(err.contains("FAKE-XXXX-X-XX") || err.contains("not in catalog"),
            "expected D7=B rejection, got: {}", err);
}

#[tokio::test]
async fn test_create_wishlist_empty_family_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_temp_db();
    use el_club_erp_lib::*;

    let input = CreateWishlistItemInput {
        family_id: "".to_string(),
        jersey_id: None, size: None, player_name: None, player_number: None,
        patch: None, version: None, customer_id: None, expected_usd: None, notes: None,
    };

    let result = impl_create_wishlist_item(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("family_id"));
}
