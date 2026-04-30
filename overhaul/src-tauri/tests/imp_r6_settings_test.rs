// Integration test for cmd_update_imp_setting · validates per-key value types.
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_temp_db() -> PathBuf {
    let path = env::temp_dir().join(format!("imp_r6_settings_test_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }
    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imp_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT,
          updated_by TEXT
        );
    "#).unwrap();
    path
}

fn with_db<F: FnOnce()>(f: F) {
    let _g = DB_LOCK.lock().unwrap();
    let path = setup_temp_db();
    env::set_var("ERP_DB_PATH", &path);
    f();
    let _ = std::fs::remove_file(&path);
}

#[test]
fn test_update_default_fx_happy() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "7.85",
        );
        assert!(result.is_ok(), "Expected OK, got {:?}", result);
        let s = result.unwrap();
        assert_eq!(s.value, "7.85");
    });
}

#[test]
fn test_update_default_fx_rejects_negative() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "-1.0",
        );
        assert!(result.is_err(), "Expected ERR for negative FX");
    });
}

#[test]
fn test_update_default_fx_rejects_non_numeric() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "abc",
        );
        assert!(result.is_err());
    });
}

#[test]
fn test_update_threshold_days_rejects_zero() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "threshold_wishlist_unbatched_days",
            "0",
        );
        assert!(result.is_err(), "Expected ERR for zero threshold");
    });
}

#[test]
fn test_update_unknown_key_rejected() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "made_up_key",
            "1",
        );
        assert!(result.is_err(), "Expected ERR for unknown key");
    });
}
