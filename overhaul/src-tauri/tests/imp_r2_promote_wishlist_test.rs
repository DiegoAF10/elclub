// Integration test for cmd_promote_wishlist_to_batch — TDD MANDATORY (transactional)
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn fixture_catalog() -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("tests/fixtures/catalog_minimal.json");
    p
}

fn setup_with_wishlist_items() -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r2_promote_test_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    // NOTE: import_items mirrors R6's apply_imp_schema.py · in production R2 ASSUMES this exists.
    // Test fixture re-creates it standalone for hermetic isolation.
    // inbox_events schema matches REAL production schema (verified 2026-04-28).
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
        CREATE TABLE import_items (
          import_item_id     INTEGER PRIMARY KEY AUTOINCREMENT,
          import_id          TEXT NOT NULL REFERENCES imports(import_id),
          wishlist_item_id   INTEGER REFERENCES import_wishlist(wishlist_item_id),
          family_id          TEXT NOT NULL,
          jersey_id          TEXT,
          size               TEXT,
          player_name        TEXT,
          player_number      INTEGER,
          patch              TEXT,
          version            TEXT,
          customer_id        TEXT,
          expected_usd       REAL,
          unit_cost_usd      REAL,
          unit_cost_gtq      REAL,
          status             TEXT DEFAULT 'pending'
                             CHECK(status IN ('pending','arrived','sold','published','cancelled')),
          sale_item_id       INTEGER,
          jersey_id_published TEXT,
          notes              TEXT,
          created_at         TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE inbox_events (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          type          TEXT NOT NULL,
          severity      TEXT NOT NULL CHECK (severity IN ('critical', 'important', 'info')),
          title         TEXT NOT NULL,
          description   TEXT,
          action_label  TEXT,
          action_target TEXT,
          module        TEXT NOT NULL,
          metadata      TEXT,
          created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
          dismissed_at  INTEGER,
          resolved_at   INTEGER,
          expires_at    INTEGER
        );

        INSERT INTO import_wishlist (wishlist_item_id, family_id, size, player_name, player_number, version, customer_id, expected_usd, status)
        VALUES
          (1, 'ARG-2026-L-FS', 'L', 'Messi', 10, 'fan', 'cust-pedro', 15.0, 'active'),
          (2, 'FRA-2026-L-FS', 'M', 'Mbappe', 10, 'fan-w', 'cust-andres', 15.0, 'active'),
          (3, 'BRA-2026-L-FS', 'L', 'Vinicius', 7, 'fan', NULL, 11.0, 'active'),
          (4, 'ARG-2026-L-FS', 'XL', NULL, NULL, 'player', NULL, 13.0, 'active'),
          (5, 'FRA-2026-L-FS', 'S', 'Griezmann', 7, 'fan', 'cust-juan', 13.0, 'cancelled');
    "#).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    env::set_var("ELCLUB_CATALOG_PATH", fixture_catalog());
    path
}

#[tokio::test]
async fn test_promote_happy_path_paid_mixed_items() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // 3 items mixed: items 1+2 have customer_id (assigned) · item 3 has NULL (stock-future)
    // ALL 3 go into single import_items table · customer_id nullable column distinguishes them.
    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1, 2, 3],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: Some("Bond Soccer Jersey".to_string()),
        bruto_usd: 41.0,                 // sum of expected_usd: 15+15+11
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let summary = result.unwrap();
    assert_eq!(summary.import.import_id, "IMP-2026-04-30");
    assert_eq!(summary.import.status, "paid");
    assert_eq!(summary.import_items_count, 3);
    assert!((summary.import.bruto_usd.unwrap_or(0.0) - 41.0).abs() < 0.01);
    assert_eq!(summary.import.n_units, Some(3));

    // Verify wishlist rows updated
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    let promoted_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_wishlist WHERE status='promoted' AND promoted_to_import_id='IMP-2026-04-30'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(promoted_count, 3);

    // Verify SINGLE TABLE: ALL 3 items in import_items (Diego decision 2026-04-28 ~19:00)
    let import_items_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(import_items_count, 3, "expected 3 rows in import_items (single destination)");

    // Verify all rows status='pending' (will become 'arrived' on close_import in R4)
    let pending_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30' AND status='pending'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(pending_count, 3);

    // Verify customer_id distinguishes assigned vs stock-future within single table
    let assigned_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30' AND customer_id IS NOT NULL",
        [], |r| r.get(0)
    ).unwrap();
    let stock_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30' AND customer_id IS NULL",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(assigned_count, 2, "items 1+2 with customer_id");
    assert_eq!(stock_count, 1, "item 3 without customer_id (stock-future)");

    // Verify cust-pedro preserved
    let pedro: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE customer_id='cust-pedro' AND import_id='IMP-2026-04-30'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(pedro, 1);

    // BONUS: verify inbox_events row created (real schema · type='import_promoted')
    let event_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM inbox_events WHERE type='import_promoted'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(event_count, 1, "expected 1 inbox_events row for import_promoted");
}

#[tokio::test]
async fn test_promote_draft_status_paid_at_optional() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // status='draft' → paid_at can be None
    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![3],   // stock-future only
        import_id: "IMP-2026-04-30".to_string(),
        status: "draft".to_string(),
        paid_at: None,
        supplier: None,
        bruto_usd: 11.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let summary = result.unwrap();
    assert_eq!(summary.import.status, "draft");
    assert!(summary.import.paid_at.is_none(), "paid_at should be NULL for draft");

    // Verify item 3 went to import_items (single table, regardless of customer_id NULL)
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    let import_items_count: i64 = conn.query_row("SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30'", [], |r| r.get(0)).unwrap();
    assert_eq!(import_items_count, 1);

    // Verify it's customer_id NULL (stock-future)
    let stock_row: Option<String> = conn.query_row(
        "SELECT customer_id FROM import_items WHERE import_id='IMP-2026-04-30'",
        [], |r| r.get(0)
    ).ok().flatten();
    assert!(stock_row.is_none(), "expected customer_id NULL for stock-future");
}

#[tokio::test]
async fn test_promote_paid_without_paid_at_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // status='paid' REQUIRES paid_at
    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: None,  // missing!
        supplier: None,
        bruto_usd: 15.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    let err = format!("{:?}", result.unwrap_err());
    assert!(err.contains("paid_at") && err.contains("required"),
            "expected paid_at required error, got: {}", err);
}

#[tokio::test]
async fn test_promote_empty_selection_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 0.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("at least 1"));
}

#[tokio::test]
async fn test_promote_invalid_import_id_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1],
        import_id: "BATCH-001".to_string(),  // wrong format
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 15.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("import_id format"));
}

#[tokio::test]
async fn test_promote_duplicate_import_id_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // Pre-insert a conflicting import row
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute("INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
                  VALUES ('IMP-2026-04-30', '2026-04-30', 'Bond', 100.0, 7.73, 5, 'paid', '2026-04-30 10:00:00')",
                 []).unwrap();

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 15.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("already exists"));

    // Verify atomicity: wishlist items should NOT be marked promoted (rollback worked)
    // and import_items should have NO new rows (only the pre-existing import has none)
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    let active_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_wishlist WHERE wishlist_item_id=1 AND status='active'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(active_count, 1, "wishlist item 1 should still be 'active' after failed promote");
    let item_count: i64 = conn.query_row("SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30'", [], |r| r.get(0)).unwrap();
    assert_eq!(item_count, 0, "no import_items rows should exist after rollback");
}

#[tokio::test]
async fn test_promote_already_promoted_item_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // Pre-promote item 1
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute("UPDATE import_wishlist SET status='promoted', promoted_to_import_id='IMP-2026-04-29' WHERE wishlist_item_id=1",
                 []).unwrap();

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1, 2],  // 1 is already promoted
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 30.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    let err = format!("{:?}", result.unwrap_err());
    assert!(err.contains("not active") || err.contains("status 'promoted'"),
            "expected non-active rejection, got: {}", err);

    // Atomicity check: no import created · no import_items rows
    let imports_count: i64 = conn.query_row("SELECT COUNT(*) FROM imports WHERE import_id='IMP-2026-04-30'", [], |r| r.get(0)).unwrap();
    assert_eq!(imports_count, 0);
    let item_count: i64 = conn.query_row("SELECT COUNT(*) FROM import_items WHERE import_id='IMP-2026-04-30'", [], |r| r.get(0)).unwrap();
    assert_eq!(item_count, 0);
}

#[tokio::test]
async fn test_promote_cancelled_item_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    // Item 5 is pre-seeded as cancelled
    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![5],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 13.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("not active"));
}

#[tokio::test]
async fn test_promote_nonexistent_item_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![999],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: 10.0,
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("999"));
}

#[tokio::test]
async fn test_promote_negative_bruto_usd_rejected() {
    let _guard = DB_LOCK.lock().unwrap();
    let _path = setup_with_wishlist_items();
    use el_club_erp_lib::*;

    let input = PromoteWishlistInput {
        wishlist_item_ids: vec![1],
        import_id: "IMP-2026-04-30".to_string(),
        status: "paid".to_string(),
        paid_at: Some("2026-04-30".to_string()),
        supplier: None,
        bruto_usd: -10.0,  // invalid
        fx: 7.73,
        notes: None,
    };

    let result = impl_promote_wishlist_to_batch(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("bruto_usd"));
}
