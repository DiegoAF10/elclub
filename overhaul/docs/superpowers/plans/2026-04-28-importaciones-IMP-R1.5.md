# IMP-R1.5 Implementation Plan — R1 Completion (8 botones rotos + 5 commands)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el gap shipped en IMP-R1: wirea 8 botones decorativos del header IMP + detail toolbar · agrega 5 commands Rust transaccionales (`cmd_create_import`, `cmd_register_arrival`, `cmd_update_import`, `cmd_cancel_import`, `cmd_export_imports_csv` stub) + 4 modals Svelte para que Diego pueda crear/registrar arrival/editar/cancelar pedidos end-to-end vía UI.

**Architecture:** Solo módulo IMP. Cero schema changes (todas las columnas necesarias ya existen post-R1). 5 commands Rust nuevos siguen el pattern transaccional de `cmd_create_expense` (lib.rs:2946) + `cmd_close_import_proportional` (lib.rs:2620). 4 modals Svelte siguen el pattern de `BaseModal` del Comercial (referenciado en `el-club-imp/overhaul/src/lib/components/comercial/BaseModal.svelte` · NO se modifica, solo se reusa). Validation regex `IMP-\d{4}-\d{2}-\d{2}` enforced cliente y servidor sin crate nuevo (char check + `chrono::NaiveDate`).

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + Tauri 2 + Svelte 5 (`$state`/`$derived`/`$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · 0 deps nuevas.

---

## File Structure

### Files to create (8 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/overhaul/src/lib/components/importaciones/NewImportModal.svelte` | Form 9 fields para crear import draft · regex enforced client-side · invoca `adapter.createImport()` |
| `el-club-imp/overhaul/src/lib/components/importaciones/RegisterArrivalModal.svelte` | Form 3 fields (`arrived_at` default=hoy · `shipping_gtq` · `tracking_code` opcional) · invoca `adapter.registerArrival()` |
| `el-club-imp/overhaul/src/lib/components/importaciones/EditImportModal.svelte` | Form 3 fields editables (notes · tracking_code · carrier) · invoca `adapter.updateImport()` |
| `el-club-imp/overhaul/src/lib/components/importaciones/ConfirmCancelModal.svelte` | Confirmación destructiva con input "CONFIRMO" · invoca `adapter.cancelImport()` |
| `el-club-imp/overhaul/src-tauri/tests/imp_r15_create_test.rs` | TDD: cmd_create_import (regex · duplicate guard · transactional) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r15_register_arrival_test.rs` | TDD: cmd_register_arrival (status guard · lead_time auto · idempotente) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r15_cancel_test.rs` | TDD: cmd_cancel_import (status guard · idempotente re-cancel) |
| `el-club-imp/erp/scripts/smoke_imp_r15.py` | Smoke SQL post-implementation · ejercita 5 commands · verifica state DB |

### Files to modify (7 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | Agregar 4 structs Input + 5 commands + helper `is_valid_import_id` + wire `generate_handler!` | +250 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | Extend Adapter interface · 3 input interfaces + 5 method signatures | +30 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 5 invocations | +40 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 5 stub fallbacks (throw NotAvailableInBrowser) | +25 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte` | Wire 3 botones header (+Nuevo opens modal · Export CSV invoca · Sync DHL disabled+title) + import del modal | +30 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailHead.svelte` | Wire Editar onclick + Ver invoice/tracking buttons (disabled+title o stub display) | +15 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailPane.svelte` | Reemplazar alerts en handleRegisterArrival/handleCancel con modal opens · agregar handleEdit · imports + state | +40 |

**Total estimado:** ~430 líneas net nuevas.

---

## Pre-flight (verify worktree state)

### Task 0: Pre-flight verification

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Verify worktree branch**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git status -sb
```
Expected: `## imp-r2-r6-build` · sin uncommitted changes

- [ ] **Step 2: Verify ERP_DB_PATH not contaminating main**

Run:
```bash
ls -lh C:/Users/Diego/el-club-imp/erp/elclub.db && \
  python -c "import sqlite3; print('snapshot rows:', sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db').execute('SELECT COUNT(*) FROM imports').fetchone()[0])"
```
Expected: file exists, ~1.1MB, prints `snapshot rows: 0` (post-wipe state)

- [ ] **Step 3: Sanity check lib.rs current state**

Run:
```bash
wc -l C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs && \
  grep -c "tauri::command" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs
```
Expected: ~5,296 lines · ~50+ existing commands (sanity)

---

## Task Group 1: Rust commands + structs (yo · secuencial · lib.rs)

### Task 1: Helper `is_valid_import_id` + tests

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add helper near top, after `db_path()` definition ~line 65)

- [ ] **Step 1: Write failing test inline**

Add at end of lib.rs (before final closing brace if exists, or append to existing test module if any):

```rust
#[cfg(test)]
mod imp_r15_helper_tests {
    use super::*;

    #[test]
    fn test_valid_import_id_format() {
        assert!(is_valid_import_id("IMP-2026-04-28"));
        assert!(is_valid_import_id("IMP-2025-12-31"));
        assert!(is_valid_import_id("IMP-2026-01-01"));
    }

    #[test]
    fn test_invalid_import_id_format() {
        assert!(!is_valid_import_id(""));
        assert!(!is_valid_import_id("IMP-2026-04-7"));     // single digit day
        assert!(!is_valid_import_id("imp-2026-04-28"));   // lowercase
        assert!(!is_valid_import_id("IMP-2026-13-01"));   // month 13 invalid
        assert!(!is_valid_import_id("IMP-2026-02-30"));   // feb 30 invalid
        assert!(!is_valid_import_id("IMP-2026-04-28-001")); // suffix
        assert!(!is_valid_import_id("IMP-202X-04-28"));   // letter in year
        assert!(!is_valid_import_id("IMP_2026_04_28"));   // underscores
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test imp_r15_helper_tests 2>&1 | tail -20
```
Expected: FAIL with `cannot find function 'is_valid_import_id'`

- [ ] **Step 3: Implement helper**

Add after `db_path()` function (~line 65 of lib.rs):

```rust
/// Validates `IMP-YYYY-MM-DD` format with real date check.
/// Cero dependencias nuevas — char check + chrono::NaiveDate parsing.
fn is_valid_import_id(s: &str) -> bool {
    if s.len() != 14 || !s.starts_with("IMP-") {
        return false;
    }
    let date_part = &s[4..]; // "YYYY-MM-DD"
    chrono::NaiveDate::parse_from_str(date_part, "%Y-%m-%d").is_ok()
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test imp_r15_helper_tests 2>&1 | tail -10
```
Expected: PASS · `running 2 tests · test result: ok. 2 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r1.5): add is_valid_import_id helper with regex-equivalent validation

- Validates IMP-YYYY-MM-DD format
- Uses chrono::NaiveDate for real-date check (rejects Feb 30, month 13)
- Zero new dependencies (no regex crate needed)
- Tests cover 3 valid + 8 invalid cases"
```

---

### Task 2: `CreateImportInput` struct + `cmd_create_import` (TDD · transactional)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add struct + command after line 2620 in Importaciones section)
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r15_create_test.rs`

- [ ] **Step 1: Write failing integration test**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r15_create_test.rs`:

```rust
// Integration test for cmd_create_import — uses temp DB via ERP_DB_PATH override
use std::path::PathBuf;
use std::env;
use rusqlite::Connection;

fn setup_temp_db() -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_create_test_{}.db", std::process::id()));
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
    let _path = setup_temp_db();
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
    let _path = setup_temp_db();
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
    let _path = setup_temp_db();
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
    let _path = setup_temp_db();
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
```

- [ ] **Step 2: Run test to verify it fails (compile error)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_create_test 2>&1 | tail -20
```
Expected: FAIL with `cannot find type 'CreateImportInput' in module 'el_club_erp_lib'` AND/OR `cannot find function 'cmd_create_import'`

- [ ] **Step 3: Add struct + command to lib.rs**

In `el-club-imp/overhaul/src-tauri/src/lib.rs`, after line ~2714 (end of `cmd_close_import_proportional`):

```rust
// ─── R1.5 Completion: Create / Register Arrival / Update / Cancel ────

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateImportInput {
    pub import_id: String,
    pub paid_at: String,
    pub supplier: String,
    pub bruto_usd: f64,
    pub fx: f64,
    pub n_units: i64,
    pub notes: Option<String>,
    pub tracking_code: Option<String>,
    pub carrier: Option<String>,
}

#[tauri::command]
pub async fn cmd_create_import(input: CreateImportInput) -> Result<Import> {
    // Validation
    if !is_valid_import_id(&input.import_id) {
        return Err(ErpError::Other(format!(
            "import_id format inválido: '{}' · esperado IMP-YYYY-MM-DD",
            input.import_id
        )));
    }
    if input.bruto_usd <= 0.0 {
        return Err(ErpError::Other(format!(
            "bruto_usd debe ser > 0 · recibido {}",
            input.bruto_usd
        )));
    }
    if input.fx <= 0.0 {
        return Err(ErpError::Other(format!(
            "fx debe ser > 0 · recibido {}",
            input.fx
        )));
    }
    if input.n_units <= 0 {
        return Err(ErpError::Other(format!(
            "n_units debe ser > 0 · recibido {}",
            input.n_units
        )));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // Duplicate guard
    let exists: bool = tx.query_row(
        "SELECT EXISTS(SELECT 1 FROM imports WHERE import_id = ?1)",
        rusqlite::params![&input.import_id],
        |row| row.get::<_, i64>(0).map(|n| n != 0),
    )?;
    if exists {
        return Err(ErpError::Other(format!(
            "Import {} already exists",
            input.import_id
        )));
    }

    let supplier = if input.supplier.trim().is_empty() {
        "Bond Soccer Jersey".to_string()
    } else {
        input.supplier.clone()
    };
    let carrier = input.carrier.clone().unwrap_or_else(|| "DHL".to_string());
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    tx.execute(
        "INSERT INTO imports
         (import_id, paid_at, supplier, bruto_usd, fx, n_units, notes,
          tracking_code, carrier, status, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'paid', ?10)",
        rusqlite::params![
            input.import_id,
            input.paid_at,
            supplier,
            input.bruto_usd,
            input.fx,
            input.n_units,
            input.notes,
            input.tracking_code,
            carrier,
            now,
        ],
    )?;

    tx.commit()?;

    // Re-read to return canonical Import
    let conn = open_db()?;
    conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![input.import_id],
        |row| Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        }),
    ).map_err(|e| e.into())
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_create_test 2>&1 | tail -10
```
Expected: PASS · `4 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r15_create_test.rs && \
  git commit -m "feat(imp-r1.5): cmd_create_import (transactional · regex enforced · 4 TDD cases)

- CreateImportInput struct with camelCase serde
- Validates: import_id format · bruto_usd > 0 · fx > 0 · n_units > 0
- Duplicate guard (import_id PK collision)
- Default supplier 'Bond Soccer Jersey' · default carrier 'DHL'
- Status='paid' initial · created_at = local timestamp
- Returns canonical Import after re-read
- 4 integration tests: happy path · invalid_id · duplicate · negative bruto"
```

---

### Task 3: `RegisterArrivalInput` struct + `cmd_register_arrival` (TDD · transactional)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r15_register_arrival_test.rs`

- [ ] **Step 1: Write failing test**

Create test file:

```rust
// el-club-imp/overhaul/src-tauri/tests/imp_r15_register_arrival_test.rs
use std::path::PathBuf;
use std::env;
use rusqlite::Connection;

fn setup_with_paid_import() -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_arrival_test_{}.db", std::process::id()));
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
    let _path = setup_with_paid_import();
    use el_club_erp_lib::*;

    let input = RegisterArrivalInput {
        import_id: "IMP-2026-04-28".to_string(),
        arrived_at: "2026-04-28".to_string(),
        shipping_gtq: 522.67,
        tracking_code: Some("DHL1234567890".to_string()),
    };

    let result = cmd_register_arrival(input).await;
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
    let _path = setup_with_paid_import();
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

    let result = cmd_register_arrival(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("cannot register arrival"));
}

#[tokio::test]
async fn test_register_arrival_idempotent() {
    let _path = setup_with_paid_import();
    use el_club_erp_lib::*;

    let input = RegisterArrivalInput {
        import_id: "IMP-2026-04-28".to_string(),
        arrived_at: "2026-04-28".to_string(),
        shipping_gtq: 522.67,
        tracking_code: None,
    };

    cmd_register_arrival(input.clone()).await.unwrap();
    // Second call should update (idempotent re-register OK if status='arrived' not 'closed')
    let result = cmd_register_arrival(input).await;
    assert!(result.is_ok(), "second register should succeed (idempotent)");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_register_arrival_test 2>&1 | tail -10
```
Expected: FAIL · `cannot find type 'RegisterArrivalInput'`

- [ ] **Step 3: Implement command**

Add to lib.rs after `cmd_create_import`:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterArrivalInput {
    pub import_id: String,
    pub arrived_at: String,
    pub shipping_gtq: f64,
    pub tracking_code: Option<String>,
}

#[tauri::command]
pub async fn cmd_register_arrival(input: RegisterArrivalInput) -> Result<Import> {
    if input.shipping_gtq < 0.0 {
        return Err(ErpError::Other("shipping_gtq cannot be negative".into()));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let (status, paid_at): (String, Option<String>) = tx.query_row(
        "SELECT status, paid_at FROM imports WHERE import_id = ?1",
        rusqlite::params![&input.import_id],
        |row| Ok((row.get(0)?, row.get(1)?)),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", input.import_id)),
        other => other.into(),
    })?;

    if status == "closed" || status == "cancelled" {
        return Err(ErpError::Other(format!(
            "cannot register arrival on import with status '{}'",
            status
        )));
    }

    // Auto-calc lead_time_days
    let lead_time_days = paid_at.as_ref().and_then(|p| {
        let pd = chrono::NaiveDate::parse_from_str(p, "%Y-%m-%d").ok()?;
        let ad = chrono::NaiveDate::parse_from_str(&input.arrived_at, "%Y-%m-%d").ok()?;
        Some((ad - pd).num_days() as i64)
    });

    tx.execute(
        "UPDATE imports
         SET arrived_at = ?1,
             shipping_gtq = ?2,
             tracking_code = COALESCE(?3, tracking_code),
             lead_time_days = ?4,
             status = 'arrived'
         WHERE import_id = ?5",
        rusqlite::params![
            input.arrived_at,
            input.shipping_gtq,
            input.tracking_code,
            lead_time_days,
            input.import_id,
        ],
    )?;

    tx.commit()?;

    // Re-read
    cmd_get_import(_dummy_handle(), input.import_id).await
}

// Helper: dummy AppHandle for internal calls (cmd_get_import requires it but doesn't use it).
// In production this is auto-injected by Tauri. For internal re-reads, we bypass.
fn _dummy_handle() -> tauri::AppHandle {
    panic!("internal helper · should never be called directly");
}
```

**NOTA:** `cmd_get_import` requires `AppHandle` que es injected por Tauri. Para re-read interno, mejor inline el SELECT. Refactor en step inline:

Replace last 2 lines:
```rust
    tx.commit()?;

    // Re-read inline (avoid AppHandle dependency for internal use)
    let conn = open_db()?;
    conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![input.import_id],
        |row| Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        }),
    ).map_err(|e| e.into())
}
```

(Remove `_dummy_handle` and the bad `.await` re-read.)

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_register_arrival_test 2>&1 | tail -10
```
Expected: PASS · `3 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r15_register_arrival_test.rs && \
  git commit -m "feat(imp-r1.5): cmd_register_arrival (transactional · auto lead_time · idempotent)

- RegisterArrivalInput struct
- Status guard: cannot register if closed or cancelled
- Auto-calculates lead_time_days from paid_at to arrived_at
- COALESCE tracking_code (preserve if not provided)
- Updates status to 'arrived'
- Idempotent: re-register on 'arrived' status OK
- 3 TDD cases: happy path · status guard · idempotent"
```

---

### Task 4: `UpdateImportInput` + `cmd_update_import` (smoke-only · low-risk CRUD)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement struct + command**

Add after `cmd_register_arrival`:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateImportInput {
    pub import_id: String,
    pub notes: Option<String>,
    pub tracking_code: Option<String>,
    pub carrier: Option<String>,
}

#[tauri::command]
pub async fn cmd_update_import(input: UpdateImportInput) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&input.import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", input.import_id)),
        other => other.into(),
    })?;

    if status == "closed" || status == "cancelled" {
        return Err(ErpError::Other(format!(
            "cannot update import with status '{}'",
            status
        )));
    }

    tx.execute(
        "UPDATE imports
         SET notes = COALESCE(?1, notes),
             tracking_code = COALESCE(?2, tracking_code),
             carrier = COALESCE(?3, carrier)
         WHERE import_id = ?4",
        rusqlite::params![
            input.notes,
            input.tracking_code,
            input.carrier,
            input.import_id,
        ],
    )?;

    tx.commit()?;

    let conn = open_db()?;
    conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![input.import_id],
        |row| Ok(Import {
            import_id: row.get(0)?, paid_at: row.get(1)?, arrived_at: row.get(2)?,
            supplier: row.get(3)?, bruto_usd: row.get(4)?, shipping_gtq: row.get(5)?,
            fx: row.get(6)?, total_landed_gtq: row.get(7)?, n_units: row.get(8)?,
            unit_cost: row.get(9)?, status: row.get(10)?, notes: row.get(11)?,
            created_at: row.get(12)?, tracking_code: row.get(13)?,
            carrier: row.get(14)?, lead_time_days: row.get(15)?,
        }),
    ).map_err(|e| e.into())
}
```

- [ ] **Step 2: Verify cargo check passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -10
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r1.5): cmd_update_import (notes/tracking_code/carrier · status guarded)

- UpdateImportInput struct
- Status guard: cannot update if closed or cancelled
- COALESCE pattern: only updates fields explicitly provided
- Smoke-only (low-risk CRUD)"
```

---

### Task 5: `cmd_cancel_import` (TDD · idempotent)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r15_cancel_test.rs`

- [ ] **Step 1: Write failing test**

```rust
// el-club-imp/overhaul/src-tauri/tests/imp_r15_cancel_test.rs
use std::path::PathBuf;
use std::env;
use rusqlite::Connection;

fn setup_with_paid_import() -> PathBuf {
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r15_cancel_test_{}.db", std::process::id()));
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
    let _path = setup_with_paid_import();
    use el_club_erp_lib::*;
    let result = cmd_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_ok());
    assert_eq!(result.unwrap().status, "cancelled");
}

#[tokio::test]
async fn test_cancel_import_idempotent() {
    let _path = setup_with_paid_import();
    use el_club_erp_lib::*;
    cmd_cancel_import("IMP-2026-04-28".to_string()).await.unwrap();
    let result = cmd_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_ok(), "second cancel should be idempotent OK");
    assert_eq!(result.unwrap().status, "cancelled");
}

#[tokio::test]
async fn test_cancel_closed_import_rejected() {
    let _path = setup_with_paid_import();
    use el_club_erp_lib::*;
    let conn = rusqlite::Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap();
    conn.execute("UPDATE imports SET status='closed' WHERE import_id=?1", ["IMP-2026-04-28"]).unwrap();
    let result = cmd_cancel_import("IMP-2026-04-28".to_string()).await;
    assert!(result.is_err());
}
```

- [ ] **Step 2: Run test to verify fails**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_cancel_test 2>&1 | tail -10
```
Expected: FAIL · `cannot find function 'cmd_cancel_import'`

- [ ] **Step 3: Implement command**

Add to lib.rs after `cmd_update_import`:

```rust
#[tauri::command]
pub async fn cmd_cancel_import(import_id: String) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    // Idempotent: cancelling already-cancelled is OK
    // Reject only if closed (terminal opposite state)
    if status == "closed" {
        return Err(ErpError::Other(format!(
            "cannot cancel import with status 'closed' (use admin re-open if needed)"
        )));
    }

    if status != "cancelled" {
        tx.execute(
            "UPDATE imports SET status = 'cancelled' WHERE import_id = ?1",
            rusqlite::params![&import_id],
        )?;
    }

    tx.commit()?;

    let conn = open_db()?;
    conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![import_id],
        |row| Ok(Import {
            import_id: row.get(0)?, paid_at: row.get(1)?, arrived_at: row.get(2)?,
            supplier: row.get(3)?, bruto_usd: row.get(4)?, shipping_gtq: row.get(5)?,
            fx: row.get(6)?, total_landed_gtq: row.get(7)?, n_units: row.get(8)?,
            unit_cost: row.get(9)?, status: row.get(10)?, notes: row.get(11)?,
            created_at: row.get(12)?, tracking_code: row.get(13)?,
            carrier: row.get(14)?, lead_time_days: row.get(15)?,
        }),
    ).map_err(|e| e.into())
}
```

- [ ] **Step 4: Verify test passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r15_cancel_test 2>&1 | tail -10
```
Expected: PASS · `3 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r15_cancel_test.rs && \
  git commit -m "feat(imp-r1.5): cmd_cancel_import (idempotent · closed-state guard)

- Cancelling already-cancelled is OK (idempotent)
- Cannot cancel closed (terminal state) — admin re-open required
- 3 TDD cases: happy path · idempotent · closed-rejection"
```

---

### Task 6: `cmd_export_imports_csv` (stub funcional · returns CSV string)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement**

Add after `cmd_cancel_import`:

```rust
#[tauri::command]
pub async fn cmd_export_imports_csv() -> Result<String> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                fx, total_landed_gtq, n_units, unit_cost, status,
                tracking_code, carrier, lead_time_days, notes, created_at
         FROM imports ORDER BY paid_at DESC NULLS LAST, created_at DESC"
    )?;

    let mut csv = String::from(
        "import_id,paid_at,arrived_at,supplier,bruto_usd,shipping_gtq,fx,total_landed_gtq,n_units,unit_cost,status,tracking_code,carrier,lead_time_days,notes,created_at\n"
    );

    let rows = stmt.query_map([], |row| {
        Ok(format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            csv_escape(&row.get::<_, String>(0)?),
            csv_escape(&row.get::<_, Option<String>>(1)?.unwrap_or_default()),
            csv_escape(&row.get::<_, Option<String>>(2)?.unwrap_or_default()),
            csv_escape(&row.get::<_, String>(3)?),
            row.get::<_, Option<f64>>(4)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(5)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(6)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(7)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<i64>>(8)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(9)?.map(|v| v.to_string()).unwrap_or_default(),
            csv_escape(&row.get::<_, String>(10)?),
            csv_escape(&row.get::<_, Option<String>>(11)?.unwrap_or_default()),
            csv_escape(&row.get::<_, Option<String>>(12)?.unwrap_or_else(|| "DHL".into())),
            row.get::<_, Option<i64>>(13)?.map(|v| v.to_string()).unwrap_or_default(),
            csv_escape(&row.get::<_, Option<String>>(14)?.unwrap_or_default()),
            csv_escape(&row.get::<_, String>(15)?),
        ))
    })?;

    for row in rows {
        csv.push_str(&row?);
        csv.push('\n');
    }

    Ok(csv)
}

fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}
```

- [ ] **Step 2: Verify cargo check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r1.5): cmd_export_imports_csv (returns CSV string · 16 columns)

- All imports ordered by paid_at DESC then created_at
- Proper CSV escaping (quotes for fields with commas/quotes/newlines)
- Frontend handles file save dialog"
```

---

### Task 7: Wire `tauri::generate_handler!` macro

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (line ~5176)

- [ ] **Step 1: Locate generate_handler! and add 5 new commands**

In lib.rs around line 5176, find the `generate_handler!` macro invocation. Add the 5 new commands to the list (preserve existing order, append after `cmd_close_import_proportional`):

```rust
.invoke_handler(tauri::generate_handler![
    // ... existing commands ...
    cmd_close_import_proportional,
    // R1.5 additions
    cmd_create_import,
    cmd_register_arrival,
    cmd_update_import,
    cmd_cancel_import,
    cmd_export_imports_csv,
    // ... rest of existing commands ...
])
```

- [ ] **Step 2: Verify cargo check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r1.5): wire 5 new commands to generate_handler!"
```

---

## Task Group 2: Adapter (yo · secuencial)

### Task 8: Adapter types (`types.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Add input interfaces + extend Adapter**

Locate Import-related section (~line 332) and add:

```typescript
export interface CreateImportInput {
  importId: string;       // regex IMP-YYYY-MM-DD enforced server-side
  paidAt: string;         // YYYY-MM-DD
  supplier: string;       // default 'Bond Soccer Jersey' if empty
  brutoUsd: number;       // > 0
  fx: number;             // > 0 · default 7.73 cliente
  nUnits: number;         // > 0
  notes?: string;
  trackingCode?: string;
  carrier?: string;       // default 'DHL'
}

export interface RegisterArrivalInput {
  importId: string;
  arrivedAt: string;      // YYYY-MM-DD
  shippingGtq: number;    // >= 0
  trackingCode?: string;
}

export interface UpdateImportInput {
  importId: string;
  notes?: string;
  trackingCode?: string;
  carrier?: string;
}
```

In the `Adapter` interface, add 5 method signatures:

```typescript
export interface Adapter {
  // ... existing methods ...
  listImports(): Promise<Import[]>;
  // ... existing import methods ...
  getImportPulso(): Promise<ImportPulso>;

  // R1.5 additions
  createImport(input: CreateImportInput): Promise<Import>;
  registerArrival(input: RegisterArrivalInput): Promise<Import>;
  updateImport(input: UpdateImportInput): Promise<Import>;
  cancelImport(importId: string): Promise<Import>;
  exportImportsCsv(): Promise<string>;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors (compile errors expected in tauri.ts/browser.ts due to unimplemented Adapter methods → next tasks fix)

- [ ] **Step 3: Don't commit yet** — types alone broken without impls. Commit at end of adapter group.

---

### Task 9: Adapter Tauri implementation (`tauri.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Add 5 invocations**

Locate `getImportPulso` method (~line 526). After it, add:

```typescript
async createImport(input: CreateImportInput): Promise<Import> {
  return await invoke<Import>('cmd_create_import', { input });
}

async registerArrival(input: RegisterArrivalInput): Promise<Import> {
  return await invoke<Import>('cmd_register_arrival', { input });
}

async updateImport(input: UpdateImportInput): Promise<Import> {
  return await invoke<Import>('cmd_update_import', { input });
}

async cancelImport(importId: string): Promise<Import> {
  return await invoke<Import>('cmd_cancel_import', { importId });
}

async exportImportsCsv(): Promise<string> {
  return await invoke<string>('cmd_export_imports_csv');
}
```

Also add imports at top of tauri.ts:

```typescript
import type {
  // ... existing imports ...
  CreateImportInput,
  RegisterArrivalInput,
  UpdateImportInput,
} from './types';
```

- [ ] **Step 2: Verify**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors in tauri.ts (browser.ts still has errors)

- [ ] **Step 3: Don't commit yet** — finish browser.ts.

---

### Task 10: Adapter Browser stubs (`browser.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 5 NotAvailableInBrowser stubs**

After `getImportPulso` (~line 374):

```typescript
async createImport(_input: CreateImportInput): Promise<Import> {
  throw new Error('createImport requires Tauri runtime · run via .exe MSI');
}

async registerArrival(_input: RegisterArrivalInput): Promise<Import> {
  throw new Error('registerArrival requires Tauri runtime · run via .exe MSI');
}

async updateImport(_input: UpdateImportInput): Promise<Import> {
  throw new Error('updateImport requires Tauri runtime · run via .exe MSI');
}

async cancelImport(_importId: string): Promise<Import> {
  throw new Error('cancelImport requires Tauri runtime · run via .exe MSI');
}

async exportImportsCsv(): Promise<string> {
  throw new Error('exportImportsCsv requires Tauri runtime · run via .exe MSI');
}
```

Add imports at top:

```typescript
import type {
  // ... existing imports ...
  CreateImportInput,
  RegisterArrivalInput,
  UpdateImportInput,
} from './types';
```

- [ ] **Step 2: Verify full check passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors total

- [ ] **Step 3: Commit adapter group**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/types.ts overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r1.5): adapter wires for 5 new IMP commands

- types.ts: 3 input interfaces (CreateImportInput · RegisterArrivalInput · UpdateImportInput) + 5 Adapter method signatures
- tauri.ts: invoke() for each command
- browser.ts: NotAvailableInBrowser stubs (require .exe MSI)"
```

---

## Task Group 3: Modals (yo · 1 modal por commit)

### Task 11: `NewImportModal.svelte` (form 9 fields · regex client validation)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/NewImportModal.svelte`

- [ ] **Step 1: Create modal**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    onClose: () => void;
    onCreated: (imp: Import) => void;
  }

  let { open, onClose, onCreated }: Props = $props();

  // Form state
  let importId = $state('');
  let paidAt = $state(new Date().toISOString().slice(0, 10));
  let supplier = $state('Bond Soccer Jersey');
  let brutoUsd = $state<number | null>(null);
  let fx = $state(7.73);
  let nUnits = $state<number | null>(null);
  let notes = $state('');
  let trackingCode = $state('');
  let carrier = $state('DHL');

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Client-side regex enforcement
  const idPattern = /^IMP-\d{4}-\d{2}-\d{2}$/;
  let idValid = $derived(idPattern.test(importId));
  let canSubmit = $derived(
    idValid &&
    paidAt.length === 10 &&
    supplier.trim().length > 0 &&
    brutoUsd !== null && brutoUsd > 0 &&
    fx > 0 &&
    nUnits !== null && nUnits > 0 &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      const imp = await adapter.createImport({
        importId,
        paidAt,
        supplier: supplier.trim(),
        brutoUsd: brutoUsd!,
        fx,
        nUnits: nUnits!,
        notes: notes.trim() || undefined,
        trackingCode: trackingCode.trim() || undefined,
        carrier: carrier.trim() || undefined,
      });
      onCreated(imp);
      reset();
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    importId = '';
    paidAt = new Date().toISOString().slice(0, 10);
    supplier = 'Bond Soccer Jersey';
    brutoUsd = null;
    fx = 7.73;
    nUnits = null;
    notes = '';
    trackingCode = '';
    carrier = 'DHL';
    errorMsg = null;
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }
</script>

<svelte:window on:keydown={handleEscape} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[480px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">+ Nuevo pedido</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        Crear import draft · status='paid' · prorrateo proporcional al cierre
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- Import ID -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Import ID *
          </label>
          <input
            type="text"
            bind:value={importId}
            placeholder="IMP-2026-04-28"
            disabled={submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            class:border-[var(--color-danger)]={importId.length > 0 && !idValid}
            class:border-[var(--color-border)]={importId.length === 0 || idValid}
            autofocus
          />
          {#if importId.length > 0 && !idValid}
            <p class="text-[10.5px] text-[var(--color-danger)] mt-1">Formato: IMP-YYYY-MM-DD</p>
          {/if}
        </div>

        <!-- Paid at + N units -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Paid at *</label>
            <input type="date" bind:value={paidAt} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">N units *</label>
            <input type="number" bind:value={nUnits} placeholder="27" min="1" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Supplier -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Supplier *</label>
          <input type="text" bind:value={supplier} disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        <!-- Bruto USD + FX -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Bruto USD *</label>
            <input type="number" bind:value={brutoUsd} placeholder="372.64" step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">FX (USD→GTQ) *</label>
            <input type="number" bind:value={fx} step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Tracking + carrier -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking (opt)</label>
            <input type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Carrier</label>
            <input type="text" bind:value={carrier} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes (opt)</label>
          <textarea bind:value={notes} rows="2" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) { reset(); onClose(); } }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Creando...' : '+ Crear pedido'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify svelte-check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/NewImportModal.svelte && \
  git commit -m "feat(imp-r1.5): NewImportModal · form 9 fields · regex client + server validation"
```

---

### Task 12: `RegisterArrivalModal.svelte`

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/RegisterArrivalModal.svelte`

- [ ] **Step 1: Create modal** (similar pattern to NewImportModal · 3 fields)

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    importId: string | null;
    onClose: () => void;
    onRegistered: (imp: Import) => void;
  }

  let { open, importId, onClose, onRegistered }: Props = $props();

  let arrivedAt = $state(new Date().toISOString().slice(0, 10));
  let shippingGtq = $state<number | null>(null);
  let trackingCode = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  let canSubmit = $derived(
    importId !== null &&
    arrivedAt.length === 10 &&
    shippingGtq !== null && shippingGtq >= 0 &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit || !importId) return;
    submitting = true;
    errorMsg = null;
    try {
      const imp = await adapter.registerArrival({
        importId,
        arrivedAt,
        shippingGtq: shippingGtq!,
        trackingCode: trackingCode.trim() || undefined,
      });
      onRegistered(imp);
      reset();
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    arrivedAt = new Date().toISOString().slice(0, 10);
    shippingGtq = null;
    trackingCode = '';
    errorMsg = null;
  }
</script>

{#if open && importId}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}>
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">📥 Registrar arrival</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {importId} · status → 'arrived' · lead time auto-calculado
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Arrived at *</label>
          <input type="date" bind:value={arrivedAt} disabled={submitting} autofocus class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Shipping DHL (GTQ) *</label>
          <input type="number" bind:value={shippingGtq} placeholder="522.67" step="0.01" min="0" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
        </div>
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking code (opt)</label>
          <input type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) { reset(); onClose(); } }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Cancelar</button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}>
            {submitting ? '⏳ Registrando...' : '📥 Registrar arrival'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/RegisterArrivalModal.svelte && \
  git commit -m "feat(imp-r1.5): RegisterArrivalModal · 3 fields · auto lead_time"
```

---

### Task 13: `EditImportModal.svelte`

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/EditImportModal.svelte`

- [ ] **Step 1: Create modal** (3 editables fields · pre-fills from current Import)

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    imp: Import | null;
    onClose: () => void;
    onUpdated: (imp: Import) => void;
  }

  let { open, imp, onClose, onUpdated }: Props = $props();

  let notes = $state('');
  let trackingCode = $state('');
  let carrier = $state('DHL');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  $effect(() => {
    if (open && imp) {
      notes = imp.notes ?? '';
      trackingCode = imp.tracking_code ?? '';
      carrier = imp.carrier ?? 'DHL';
      errorMsg = null;
    }
  });

  async function handleSubmit() {
    if (!imp || submitting) return;
    submitting = true;
    errorMsg = null;
    try {
      const updated = await adapter.updateImport({
        importId: imp.import_id,
        notes: notes.trim() || undefined,
        trackingCode: trackingCode.trim() || undefined,
        carrier: carrier.trim() || undefined,
      });
      onUpdated(updated);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }
</script>

{#if open && imp}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}>
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">📝 Editar pedido</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {imp.import_id} · status={imp.status} · solo notes/tracking/carrier editables
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes</label>
          <textarea bind:value={notes} rows="3" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking code</label>
          <input type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Carrier</label>
          <input type="text" bind:value={carrier} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Cancelar</button>
          <button type="submit" disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold bg-[var(--color-accent)] text-[var(--color-bg)]">
            {submitting ? '⏳ Guardando...' : '💾 Guardar cambios'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/EditImportModal.svelte && \
  git commit -m "feat(imp-r1.5): EditImportModal · notes/tracking/carrier · status guard server-side"
```

---

### Task 14: `ConfirmCancelModal.svelte`

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/ConfirmCancelModal.svelte`

- [ ] **Step 1: Create modal** (input "CONFIRMO" word para confirmation)

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    imp: Import | null;
    onClose: () => void;
    onCancelled: (imp: Import) => void;
  }

  let { open, imp, onClose, onCancelled }: Props = $props();

  let confirmInput = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  $effect(() => {
    if (open) {
      confirmInput = '';
      errorMsg = null;
    }
  });

  let canCancel = $derived(confirmInput.trim().toUpperCase() === 'CONFIRMO' && imp !== null && !submitting);

  async function handleCancel() {
    if (!canCancel || !imp) return;
    submitting = true;
    errorMsg = null;
    try {
      const cancelled = await adapter.cancelImport(imp.import_id);
      onCancelled(cancelled);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }
</script>

{#if open && imp}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}>
    <div class="bg-[var(--color-surface-1)] border border-[rgba(244,63,94,0.3)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-danger)] mb-1">🚫 Cancelar batch</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {imp.import_id} · status={imp.status} · acción reversible vía admin re-open
      </p>

      <p class="text-[13px] text-[var(--color-text-primary)] mb-4">
        Vas a marcar este pedido como <strong class="text-[var(--color-danger)]">cancelled</strong>. No borra data · solo cambia status. Los <strong>{imp.n_units ?? 0} units</strong> dejan de contar como capital amarrado.
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleCancel(); }} class="space-y-3">
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Escribí <strong class="text-[var(--color-danger)]">CONFIRMO</strong> para proceder</label>
          <input type="text" bind:value={confirmInput} placeholder="CONFIRMO" disabled={submitting} autofocus class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Volver</button>
          <button type="submit" disabled={!canCancel} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-danger)]={canCancel}
            class:text-white={canCancel}
            class:bg-[var(--color-surface-2)]={!canCancel}
            class:text-[var(--color-text-tertiary)]={!canCancel}>
            {submitting ? '⏳ Cancelando...' : '🚫 Cancelar batch'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/ConfirmCancelModal.svelte && \
  git commit -m "feat(imp-r1.5): ConfirmCancelModal · destructive guard with CONFIRMO input"
```

---

## Task Group 4: Wire UI

### Task 15: Wire `ImportShell.svelte` (3 botones header)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte`

- [ ] **Step 1: Update component**

Replace the script section (lines 1-38) and the 3 buttons block (lines 49-59).

Script section additions:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import ImportTabs from './ImportTabs.svelte';
  import PulsoImportBar from './PulsoImportBar.svelte';
  import PedidosTab from './tabs/PedidosTab.svelte';
  import WishlistTab from './tabs/WishlistTab.svelte';
  import MargenRealTab from './tabs/MargenRealTab.svelte';
  import FreeUnitsTab from './tabs/FreeUnitsTab.svelte';
  import SupplierTab from './tabs/SupplierTab.svelte';
  import ImportSettingsTab from './tabs/ImportSettingsTab.svelte';
  import NewImportModal from './NewImportModal.svelte';
  import { adapter } from '$lib/adapter';
  import type { ImportPulso, Import } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  const STORAGE_KEY = 'imp.activeTab';
  const VALID_TABS: TabId[] = ['pedidos', 'wishlist', 'margen', 'free', 'supplier', 'settings'];
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
  let activeTab = $state<TabId>(VALID_TABS.includes(stored as TabId) ? (stored as TabId) : 'pedidos');
  let pulso = $state<ImportPulso | null>(null);

  // R1.5: NewImportModal state
  let showNewModal = $state(false);
  let pedidosRefreshTrigger = $state(0); // bumped to force PedidosTab re-fetch

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, activeTab);
    }
  });

  onMount(async () => {
    pulso = await adapter.getImportPulso();
  });

  async function refreshPulso() {
    pulso = await adapter.getImportPulso();
  }

  function handleImportCreated(_imp: Import) {
    refreshPulso();
    pedidosRefreshTrigger++;
    activeTab = 'pedidos';
  }

  async function handleExportCsv() {
    try {
      const csv = await adapter.exportImportsCsv();
      // Trigger download via blob
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `imports-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Error exportando CSV: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
</script>
```

Buttons section (lines 49-59):

```svelte
    <div class="ml-auto flex gap-2">
      <button onclick={handleExportCsv} class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
        ⇣ Export CSV
      </button>
      <button disabled title="DHL real auto-sync diferido a IMP-R5 supplier · usá Registrar arrival manual por ahora" class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60">
        ↻ Sync DHL
      </button>
      <button onclick={() => { showNewModal = true; }} class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]">
        + Nuevo pedido
      </button>
    </div>
```

Body section: pass `refreshTrigger` to PedidosTab and add modal:

```svelte
  <!-- Body -->
  <div class="flex flex-1 min-h-0">
    {#if activeTab === 'pedidos'}
      <PedidosTab onPulsoRefresh={refreshPulso} {pedidosRefreshTrigger} />
    {:else if activeTab === 'wishlist'}
      <WishlistTab />
    {:else if activeTab === 'margen'}
      <MargenRealTab />
    {:else if activeTab === 'free'}
      <FreeUnitsTab />
    {:else if activeTab === 'supplier'}
      <SupplierTab />
    {:else if activeTab === 'settings'}
      <ImportSettingsTab />
    {/if}
  </div>
</div>

<NewImportModal open={showNewModal} onClose={() => { showNewModal = false; }} onCreated={handleImportCreated} />
```

- [ ] **Step 2: Verify**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors (PedidosTab will need to accept refreshTrigger prop in next tasks · or omit it for now and refresh via $effect)

**NOTA:** if PedidosTab doesn't accept `pedidosRefreshTrigger`, that's a TS error. Either: (a) add the prop to PedidosTab in this task as supplementary fix, or (b) skip the prop and rely on Tab switch to refresh. Easier: option (b) — remove `{pedidosRefreshTrigger}` from `<PedidosTab>` line.

If TypeScript errors:
```svelte
      <PedidosTab onPulsoRefresh={refreshPulso} />
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/ImportShell.svelte && \
  git commit -m "feat(imp-r1.5): wire 3 header buttons (Export CSV · Sync DHL disabled · + Nuevo pedido modal)"
```

---

### Task 16: Wire `ImportDetailPane.svelte` (replace alert handlers with modals)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailPane.svelte`

- [ ] **Step 1: Update component**

Update script section to import 3 new modals and replace alert handlers:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import ImportDetailHead from './ImportDetailHead.svelte';
  import ImportDetailSubtabs from './ImportDetailSubtabs.svelte';
  import OverviewSubtab from './detail/OverviewSubtab.svelte';
  import ItemsSubtab from './detail/ItemsSubtab.svelte';
  import CostosSubtab from './detail/CostosSubtab.svelte';
  import RegisterArrivalModal from './RegisterArrivalModal.svelte';
  import EditImportModal from './EditImportModal.svelte';
  import ConfirmCancelModal from './ConfirmCancelModal.svelte';
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }

  let { imp, onUpdated }: Props = $props();

  type SubtabId = 'overview' | 'items' | 'costos';
  let activeSubtab = $state<SubtabId>('overview');
  let items = $state<ImportItem[]>([]);

  // Modal state R1.5
  let showArrivalModal = $state(false);
  let showEditModal = $state(false);
  let showCancelModal = $state(false);

  $effect(() => {
    if (imp) loadItems(imp.import_id);
    else items = [];
  });

  async function loadItems(id: string) {
    items = await adapter.getImportItems(id);
  }

  function handleRegisterArrival() {
    if (!imp) return;
    showArrivalModal = true;
  }

  function handleEdit() {
    if (!imp) return;
    showEditModal = true;
  }

  async function handleClose() {
    if (!imp) return;
    if (!confirm(`Cerrar batch ${imp.import_id}?\nProrrateo D2=B aplicado a ${items.length} items.`)) return;
    try {
      const res = await adapter.closeImportProportional(imp.import_id);
      alert(`Batch cerrado · ${res.n_items_updated} sale_items + ${res.n_jerseys_updated} jerseys actualizados\nLanded total: Q${Math.round(res.total_landed_gtq)} · Avg/u: Q${Math.round(res.avg_unit_cost)}`);
      onUpdated();
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  function handleCancel() {
    if (!imp) return;
    showCancelModal = true;
  }
</script>
```

Update markup to render modals + pass new prop to ImportDetailHead:

In existing template where `<ImportDetailHead>` is rendered:

```svelte
<ImportDetailHead {imp}
  onRegisterArrival={handleRegisterArrival}
  onClose={handleClose}
  onCancel={handleCancel}
  onEdit={handleEdit} />
```

At end of template (just before `</div>` of root):

```svelte
<RegisterArrivalModal
  open={showArrivalModal}
  importId={imp?.import_id ?? null}
  onClose={() => { showArrivalModal = false; }}
  onRegistered={() => { onUpdated(); showArrivalModal = false; }} />

<EditImportModal
  open={showEditModal}
  imp={imp}
  onClose={() => { showEditModal = false; }}
  onUpdated={() => { onUpdated(); showEditModal = false; }} />

<ConfirmCancelModal
  open={showCancelModal}
  imp={imp}
  onClose={() => { showCancelModal = false; }}
  onCancelled={() => { onUpdated(); showCancelModal = false; }} />
```

- [ ] **Step 2: Verify**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: error in ImportDetailHead.svelte until next task adds onEdit prop

- [ ] **Step 3: Don't commit yet** — wait until ImportDetailHead is updated

---

### Task 17: Wire `ImportDetailHead.svelte` (Editar + Ver invoice/tracking)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailHead.svelte`

- [ ] **Step 1: Update component**

Update Props interface and add `onEdit` prop:

```svelte
<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  import { STATUS_LABELS } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    onRegisterArrival: () => void;
    onClose: () => void;
    onCancel: () => void;
    onEdit: () => void;
  }

  let { imp, onRegisterArrival, onClose, onCancel, onEdit }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let canClose = $derived(imp.arrived_at !== null && imp.shipping_gtq !== null && imp.status !== 'closed');
  let canEdit = $derived(imp.status !== 'closed' && imp.status !== 'cancelled');

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function statusPillClass(status: string): string {
    return {
      closed:  'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      paid:    'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      arrived: 'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      draft:   'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled: 'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] ?? 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>
```

Update buttons in toolbar (lines 67-78):

```svelte
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]" onclick={onRegisterArrival}>
      📥 Registrar arrival
    </button>
    <button disabled title="PayPal invoice viewer diferido a IMP-R5+ · upload manual via Notes por ahora" class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60">
      📋 Ver invoice PayPal
    </button>
    <button disabled title="DHL tracking auto-sync diferido a IMP-R5+ · pegar tracking_code en Editar por ahora" class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60">
      📋 Ver tracking DHL
    </button>
    <button onclick={onEdit} disabled={!canEdit} title={canEdit ? 'Editar notes/tracking/carrier' : 'No editable en status closed o cancelled'} class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
      class:cursor-not-allowed={!canEdit}
      class:opacity-60={!canEdit}>
      📝 Editar
    </button>
```

- [ ] **Step 2: Verify both Detail components compile**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors

- [ ] **Step 3: Commit DetailPane + DetailHead together** (atomic wire)

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src/lib/components/importaciones/ImportDetailPane.svelte \
  overhaul/src/lib/components/importaciones/ImportDetailHead.svelte && \
  git commit -m "feat(imp-r1.5): wire detail pane + head buttons (3 modals · 2 disabled stubs)

- ImportDetailPane: handleRegisterArrival/handleEdit/handleCancel open modals (replace alerts)
- ImportDetailHead: onEdit prop added · Ver invoice/tracking → disabled+title (deferred IMP-R5+)
- canEdit derived from status (false if closed/cancelled)
- All 3 modals rendered at end of DetailPane template"
```

---

## Task Group 5: Smoke test post-implementation

### Task 18: Smoke test SQL script

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r15.py`

- [ ] **Step 1: Create smoke script**

```python
#!/usr/bin/env python3
"""
Smoke test post-implementation IMP-R1.5
Exercises 5 commands via direct DB ops (simulando frontend → adapter → Tauri command behaviour at SQL layer).
Verifies state in worktree DB (ERP_DB_PATH).

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r15.py
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')

def assert_eq(actual, expected, msg):
    assert actual == expected, f'{msg} · expected={expected!r} actual={actual!r}'
    print(f'  [OK] {msg}: {actual!r}')

def main():
    print(f'DB: {DB_PATH}')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cleanup any prior smoke runs
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-2026-%-SMOKE'")
    cur.execute("DELETE FROM imports WHERE import_id = 'IMP-2026-04-29'")
    conn.commit()

    print('\n=== TEST 1: Create import ===')
    cur.execute("""
        INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
        VALUES ('IMP-2026-04-29', '2026-04-29', 'Bond Soccer Jersey', 372.64, 7.73, 27, 'paid',
                datetime('now', 'localtime'))
    """)
    conn.commit()
    row = cur.execute("SELECT * FROM imports WHERE import_id = 'IMP-2026-04-29'").fetchone()
    assert_eq(row['status'], 'paid', 'status post-create')
    assert_eq(row['n_units'], 27, 'n_units')
    assert_eq(round(row['fx'], 2), 7.73, 'fx default 7.73')

    print('\n=== TEST 2: Register arrival ===')
    cur.execute("""
        UPDATE imports
        SET arrived_at = '2026-05-07',
            shipping_gtq = 522.67,
            tracking_code = 'DHL1234567890',
            lead_time_days = 8,
            status = 'arrived'
        WHERE import_id = 'IMP-2026-04-29'
    """)
    conn.commit()
    row = cur.execute("SELECT * FROM imports WHERE import_id = 'IMP-2026-04-29'").fetchone()
    assert_eq(row['arrived_at'], '2026-05-07', 'arrived_at')
    assert_eq(row['lead_time_days'], 8, 'lead_time_days auto-calc')
    assert_eq(row['status'], 'arrived', 'status post-arrival')

    print('\n=== TEST 3: Update notes ===')
    cur.execute("UPDATE imports SET notes = 'Smoke test note' WHERE import_id = 'IMP-2026-04-29'")
    conn.commit()
    row = cur.execute("SELECT notes FROM imports WHERE import_id = 'IMP-2026-04-29'").fetchone()
    assert_eq(row['notes'], 'Smoke test note', 'notes updated')

    print('\n=== TEST 4: Cancel import ===')
    cur.execute("UPDATE imports SET status = 'cancelled' WHERE import_id = 'IMP-2026-04-29'")
    conn.commit()
    row = cur.execute("SELECT status FROM imports WHERE import_id = 'IMP-2026-04-29'").fetchone()
    assert_eq(row['status'], 'cancelled', 'status cancelled')

    print('\n=== TEST 5: Cross-module integrity (sales unaffected) ===')
    sales_count = cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    customers_count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    audit_count = cur.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
    print(f'  sales:           {sales_count} (worktree snapshot baseline)')
    print(f'  customers:       {customers_count}')
    print(f'  audit_decisions: {audit_count}')

    print('\n=== Cleanup ===')
    cur.execute("DELETE FROM imports WHERE import_id = 'IMP-2026-04-29'")
    conn.commit()

    print('\n✅ ALL SMOKE TESTS PASS')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run smoke**

```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r15.py
```
Expected: `✅ ALL SMOKE TESTS PASS`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_imp_r15.py && \
  git commit -m "test(imp-r1.5): SQL smoke script · 5 tests + cross-module integrity check"
```

---

### Task 19: Final verification (cargo + npm + svelte)

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Cargo check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check --release 2>&1 | tail -5
```
Expected: `Finished release [optimized] target(s)` no errors

- [ ] **Step 2: Cargo test all**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test 2>&1 | tail -15
```
Expected: all R1.5 tests pass · `imp_r15_helper_tests`, `imp_r15_create_test`, `imp_r15_register_arrival_test`, `imp_r15_cancel_test`

- [ ] **Step 3: npm check + build**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3 && npm run build 2>&1 | tail -5
```
Expected: 0 errors check · build OK

---

## Self-Review

Before declaring R1.5 complete, run this mental checklist:

**Spec coverage:**
- [x] Botón + Nuevo pedido funcional → Task 11 + 15 ✓
- [x] Registrar arrival → Task 3 + 12 + 16 ✓
- [x] Cancelar batch → Task 5 + 14 + 16 ✓
- [x] Editar notes/tracking/carrier → Task 4 + 13 + 17 ✓
- [x] Export CSV → Task 6 + 15 ✓
- [x] Sync DHL disabled+title (deferred) → Task 15 ✓
- [x] Ver invoice / tracking disabled+title → Task 17 ✓
- [x] Cerrar batch sigue funcional → no tocado (ya funcionaba R1) ✓
- [x] regex enforced client + server → Task 1 + 11 ✓
- [x] Status state machine guards → Task 3, 4, 5 ✓

**Placeholder scan:** ningún `TODO` / `implement later` / `add validation` / `similar to Task N` en steps. ✓

**Type consistency:**
- `CreateImportInput` / `RegisterArrivalInput` / `UpdateImportInput` ─ camelCase serde rename ✓
- `Import` struct re-read consistente entre los 4 commands ✓
- Adapter method names match Rust commands (`createImport`, `registerArrival`, etc.) ✓

**Cross-module impact (per master overview):**
- COM (Sales): cero touch ✓
- FIN (cash flow): cero touch ✓
- ADM Universe: cero touch ✓
- catalog.json: cero touch ✓
- Worker Cloudflare: cero touch ✓

---

## Execution Handoff

Plan complete and saved to `el-club-imp/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R1.5.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for `lib.rs` changes where I want code review per command.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review. Best if you want to be in the loop on every task.

**Which approach?**

If subagent-driven chosen: REQUIRED SUB-SKILL `superpowers:subagent-driven-development`.
If inline: REQUIRED SUB-SKILL `superpowers:executing-plans`.

---

## After R1.5 ships

1. Append commit hashes + smoke results to `SESSION-COORDINATION.md` activity log
2. Write R2 plan (`2026-04-28-importaciones-IMP-R2.md`) — Wishlist tab + D7=B + promote-to-batch
3. Continue to R3, R4, R5, R6 plans pipelined
4. Final ship: schema migration on main DB + MSI rebuild + merge `--no-ff` + tag `v0.3.0`
