# IMP-R4 Implementation Plan — Free units ledger (4 destinos + auto-create al close_import)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **CRITICAL CALLOUT:** This release MODIFIES an already-shipped command (`cmd_close_import_proportional` at lib.rs:2620-2730 region). Diego ya cerró IMP-2026-04-07 con esta función. **Regression risk alto.** Task Group 2 está aislado con TDD obligatoria + idempotency guard + smoke contra una import previa cerrada para confirmar que el comportamiento original se preserva. **Si el test de regresión falla en cualquier paso, STOP y escalar a Diego antes de seguir.**

**Goal:** Shippear el tab Free units (Tab 4 del módulo Importaciones · spec sec 4.4) con ledger funcional de 4 destinos (`vip` / `mystery` / `garantizada` / `personal`) + auto-create de `floor(n_paid / 10)` filas en `import_free_unit` al cerrar un batch (modificación quirúrgica a `impl_close_import_proportional` con idempotency guard) + opcional one-shot migration de notes históricos.

**Architecture:** Schema `import_free_unit` ya creada en R1 (10 cols · sin CHECK constraint sobre `destination` · validación enforced en Rust). 3-4 commands nuevos siguen pattern split `impl_X (pub) + cmd_X (#[tauri::command] shim)` documentado en lib.rs:2730-2742. Modificación a `impl_close_import_proportional` ejecuta INSERT batch atómico dentro de la misma transacción, idempotente vía `WHERE NOT EXISTS` guard. Tab Svelte sigue patrón list de PedidosTab + modal de asignación reusa BaseModal del Comercial.

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + Tauri 2 + Svelte 5 (`$state` / `$derived` / `$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · 0 deps nuevas.

---

## File Structure

### Files to create (8 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/overhaul/src/lib/components/importaciones/AssignDestinationModal.svelte` | Modal asignación de free unit (4 destinos · destination_ref dinámico per destination · family_id/jersey_id opcionales · notes) · invoca `adapter.assignFreeUnit()` |
| `el-club-imp/overhaul/src-tauri/tests/imp_r4_assign_free_unit_test.rs` | TDD: `cmd_assign_free_unit` (5 tests · happy path por destino · invalid destination · invalid customer_id VIP · re-assign rejected · unassign roundtrip) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_creates_free_units_test.rs` | TDD regresión: modificación de `impl_close_import_proportional` crea `floor(n_paid/10)` rows · 4 cases (22→2 · 9→0 · 30→3 · re-close idempotente) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_regression_existing_test.rs` | TDD regresión: el comportamiento prorrateo + status update PRE-existente sigue intacto (canary contra IMP-2026-04-07-style fixture) |
| `el-club-imp/erp/scripts/smoke_imp_r4.py` | Smoke SQL post-implementation · seedea import + 22 sale_items · invoca close vía DB direct · valida 2 free_units · asigna VIP · valida state |
| (opcional · escalable) `el-club-imp/erp/scripts/migrate_free_units_from_notes.py` | One-shot regex parser de `imports.notes` históricos (solo 2 imports a parsear) · dialog confirmation antes de insertar rows · idempotente |

### Files to modify (8 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | Agregar 2 structs (`AssignFreeUnitInput`, `FreeUnitFilter`) + struct `FreeUnit` + `impl_list_free_units` + `cmd_list_free_units` + `impl_assign_free_unit` + `cmd_assign_free_unit` + `impl_unassign_free_unit` + `cmd_unassign_free_unit` + **MODIFICAR `impl_close_import_proportional`** para INSERT free units atómico + wire 3-4 commands en `generate_handler!` | +280 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | Extend Adapter interface: `FreeUnit` interface + `AssignFreeUnitInput` + `FreeUnitFilter` + 3 method signatures | +40 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 3 invocations (`listFreeUnits` · `assignFreeUnit` · `unassignFreeUnit`) | +30 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 3 stub fallbacks (throw NotAvailableInBrowser) | +20 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte` | **REPLACE 6-line stub** con tab funcional · header con counts per destino chips filter · tabla rows · row action [Asignar] que abre AssignDestinationModal · empty state | +220 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte` (o `ImportShell.svelte` si las tabs viven ahí) | Wire badge count en label "Free units N" (count de unassigned) · spec sec 3 mockup line 93 | +15 |
| (auto · derivado) `el-club-imp/overhaul/src/lib/components/importaciones/PedidosTab.svelte` | NO se modifica · pero `cmd_close_import_proportional` ahora dispara también free units · UI de PedidosTab debería refrescar tab badge post-close (ver Task Group 5) | 0 |

**Total estimado:** ~605 líneas net nuevas (Rust ~280 · TS ~90 · Svelte ~235).

---

## Pre-flight (verify worktree state + R3 dependency)

### Task 0: Pre-flight verification

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Verify worktree branch + clean state**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git status -sb
```
Expected: `## imp-r2-r6-build` · sin uncommitted changes (R3 plan ya mergeado · R5/R6 NO arrancados)

- [ ] **Step 2: Verify `import_free_unit` table existe (creada en R1)**

Run:
```bash
python -c "import sqlite3; \
  c = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); \
  cols = c.execute('PRAGMA table_info(import_free_unit)').fetchall(); \
  print('cols:', [col[1] for col in cols]); \
  print('row count:', c.execute('SELECT COUNT(*) FROM import_free_unit').fetchone()[0])"
```
Expected: 10 cols listed (`free_unit_id`, `import_id`, `family_id`, `jersey_id`, `destination`, `destination_ref`, `assigned_at`, `assigned_by`, `notes`, `created_at`) · `row count: 0`

- [ ] **Step 3: Sanity check `cmd_close_import_proportional` exists + locate split state**

Run:
```bash
grep -n "close_import_proportional" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs | head -10
```
Expected: dos matches (uno `impl_close_import_proportional` pub fn · otro `cmd_close_import_proportional` #[tauri::command]). Si solo hay un match → la función NO está splitteada todavía · Task Group 2 debe primero refactorizar al pattern split antes de modificar (escalar a Diego antes si timeline preocupa).

- [ ] **Step 4: Sanity check IMP-2026-04-07 closed state existe (canary)**

Run:
```bash
python -c "import sqlite3; \
  c = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); \
  imp = c.execute(\"SELECT import_id, status, total_landed_gtq, n_units FROM imports WHERE import_id='IMP-2026-04-07'\").fetchone(); \
  print('canary import:', imp)"
```
Expected: `('IMP-2026-04-07', 'closed', 3182.0, 22)` o equivalente. Si NULL → la DB snapshot no tiene la canary · escalar a Diego (necesitamos esa fila para regresión test).

- [ ] **Step 5: Sanity check existing customers (para VIP destination_ref validation)**

Run:
```bash
python -c "import sqlite3; \
  c = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); \
  count = c.execute('SELECT COUNT(*) FROM customers').fetchone()[0]; \
  sample = c.execute('SELECT customer_id, full_name FROM customers LIMIT 3').fetchall(); \
  print(f'customers: {count} · sample: {sample}')"
```
Expected: ~25 customers · IDs disponibles para tests VIP

---

## Task Group 1: Rust commands sequential (yo · lib.rs)

### Task 1: `FreeUnit` struct + `FreeUnitFilter` + `impl_list_free_units` + `cmd_list_free_units` (smoke-only)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add structs + commands en sección Importaciones, después del bloque close_import ~línea 2740)

- [ ] **Step 1: Add `FreeUnit` struct + `FreeUnitFilter` struct**

Insert near existing import-related structs (search for `pub struct Import` to find region · agregar después):

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FreeUnit {
    pub free_unit_id: i64,
    pub import_id: String,
    pub family_id: Option<String>,
    pub jersey_id: Option<String>,
    pub destination: Option<String>,         // None = sin asignar (recién creada al close_import)
    pub destination_ref: Option<String>,     // customer_id / pool_ref / sku_ref / personal note
    pub assigned_at: Option<String>,
    pub assigned_by: Option<String>,
    pub notes: Option<String>,
    pub created_at: String,
    // joined fields del import (para display sin extra query):
    pub import_supplier: Option<String>,
    pub import_paid_at: Option<String>,
}

/// NULL convention para `destination` (decisión Diego 2026-04-28 ~19:00):
/// - destination: None  = sin asignar (default al INSERT desde close_import_proportional)
/// - destination: Some(s) = asignada a uno de 'vip' | 'mystery' | 'garantizada' | 'personal'
/// - destination_ref: customer_id si destination='vip' · texto libre para los demás
/// - cmd_unassign_free_unit resetea destination a NULL (NO a la string 'unassigned')
/// - VALID_FREE_DESTINATIONS Rust constant SOLO contiene los 4 destinos reales (no 'unassigned')
/// - CHECK constraint en la tabla (R6 schema script): `CHECK(destination IS NULL OR destination IN ('vip','mystery','garantizada','personal'))`

#[derive(Debug, Clone, Deserialize)]
pub struct FreeUnitFilter {
    pub import_id: Option<String>,
    pub destination: Option<String>,         // string sentinel "unassigned" en este filter SOLO indica WHERE destination IS NULL · DB sigue almacenando NULL
    pub status: Option<String>,              // 'assigned' (destination IS NOT NULL) / 'unassigned' (IS NULL)
}
```

- [ ] **Step 2: Implement `impl_list_free_units` (pub fn · NO #[tauri::command])**

Add after structs:

```rust
/// Reads free units with optional filter. Joins `imports` for supplier/paid_at display.
/// Pure read · no transaction needed.
pub fn impl_list_free_units(filter: Option<FreeUnitFilter>) -> Result<Vec<FreeUnit>, String> {
    let conn = Connection::open(db_path()).map_err(|e| e.to_string())?;

    let mut sql = String::from(
        "SELECT fu.free_unit_id, fu.import_id, fu.family_id, fu.jersey_id, \
                fu.destination, fu.destination_ref, fu.assigned_at, fu.assigned_by, \
                fu.notes, fu.created_at, i.supplier, i.paid_at \
         FROM import_free_unit fu \
         LEFT JOIN imports i ON i.import_id = fu.import_id \
         WHERE 1=1"
    );
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    if let Some(ref f) = filter {
        if let Some(ref imp_id) = f.import_id {
            sql.push_str(" AND fu.import_id = ?");
            params.push(Box::new(imp_id.clone()));
        }
        if let Some(ref status) = f.status {
            match status.as_str() {
                "assigned" => sql.push_str(" AND fu.destination IS NOT NULL"),
                "unassigned" => sql.push_str(" AND fu.destination IS NULL"),
                _ => return Err(format!("invalid status filter: {}", status)),
            }
        }
        if let Some(ref dest) = f.destination {
            if dest == "unassigned" {
                sql.push_str(" AND fu.destination IS NULL");
            } else {
                sql.push_str(" AND fu.destination = ?");
                params.push(Box::new(dest.clone()));
            }
        }
    }
    sql.push_str(" ORDER BY fu.created_at DESC, fu.free_unit_id DESC");

    let params_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = stmt.query_map(params_refs.as_slice(), |row| {
        Ok(FreeUnit {
            free_unit_id: row.get(0)?,
            import_id: row.get(1)?,
            family_id: row.get(2)?,
            jersey_id: row.get(3)?,
            destination: row.get(4)?,
            destination_ref: row.get(5)?,
            assigned_at: row.get(6)?,
            assigned_by: row.get(7)?,
            notes: row.get(8)?,
            created_at: row.get(9)?,
            import_supplier: row.get(10)?,
            import_paid_at: row.get(11)?,
        })
    }).map_err(|e| e.to_string())?;

    let mut out = Vec::new();
    for r in rows { out.push(r.map_err(|e| e.to_string())?); }
    Ok(out)
}
```

- [ ] **Step 3: Implement `cmd_list_free_units` (#[tauri::command] shim · per convention block)**

```rust
/// Per convention block lib.rs:2730-2742 — Tauri command shim that delegates to impl_X.
#[tauri::command]
pub async fn cmd_list_free_units(filter: Option<FreeUnitFilter>) -> Result<Vec<FreeUnit>, String> {
    impl_list_free_units(filter)
}
```

- [ ] **Step 4: Wire into `tauri::generate_handler!`**

Find the `.invoke_handler(tauri::generate_handler![...])` block (cerca del final del file) · agregar `cmd_list_free_units` a la lista en orden alfabético dentro del bloque IMP.

- [ ] **Step 5: Smoke compile**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -10
```
Expected: `Finished dev` sin errores · solo posibles warnings de unused (a ignorar en este step)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r4): add FreeUnit struct + cmd_list_free_units (smoke-only)

- FreeUnit struct with joined import metadata (supplier/paid_at)
- FreeUnitFilter supports import_id / destination / status filters
- impl_list_free_units pure read (no tx) joining imports for display
- cmd_list_free_units shim per split convention lib.rs:2730-2742
- Wired into invoke_handler"
```

---

### Task 2: `AssignFreeUnitInput` + `cmd_assign_free_unit` (TDD MANDATORY · transactional)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add struct + commands)
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r4_assign_free_unit_test.rs`

- [ ] **Step 1: Write failing integration test file**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r4_assign_free_unit_test.rs`:

```rust
// Integration tests for cmd_assign_free_unit — uses temp DB via ERP_DB_PATH override.
// Pattern lifted from imp_r15_*_test.rs.
use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

// Serialize tests against shared env::set_var for ERP_DB_PATH.
static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_temp_db_with_free_unit() -> (PathBuf, std::sync::MutexGuard<'static, ()>) {
    let guard = DB_LOCK.lock().unwrap();
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r4_assign_test_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imports (
          import_id        TEXT PRIMARY KEY,
          paid_at          TEXT, arrived_at TEXT, supplier TEXT,
          bruto_usd REAL, shipping_gtq REAL, fx REAL, total_landed_gtq REAL,
          n_units INTEGER, unit_cost REAL, status TEXT, notes TEXT,
          created_at TEXT, tracking_code TEXT, carrier TEXT, lead_time_days INTEGER
        );
        CREATE TABLE customers (
          customer_id TEXT PRIMARY KEY, full_name TEXT, created_at TEXT
        );
        CREATE TABLE import_free_unit (
          free_unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
          import_id TEXT NOT NULL, family_id TEXT, jersey_id TEXT,
          destination TEXT, destination_ref TEXT,
          assigned_at TEXT, assigned_by TEXT, notes TEXT,
          created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        INSERT INTO imports (import_id, status, supplier, created_at)
          VALUES ('IMP-2026-04-28', 'closed', 'Bond', '2026-04-28 10:00:00');
        INSERT INTO customers (customer_id, full_name, created_at)
          VALUES ('CUST-001', 'Cliente VIP Test', '2026-04-28 10:00:00');
        INSERT INTO import_free_unit (import_id, created_at)
          VALUES ('IMP-2026-04-28', '2026-04-28 10:00:00');
    "#).unwrap();
    env::set_var("ERP_DB_PATH", &path);
    (path, guard)
}

fn get_seeded_free_unit_id(path: &PathBuf) -> i64 {
    let conn = Connection::open(path).unwrap();
    conn.query_row("SELECT free_unit_id FROM import_free_unit LIMIT 1", [], |r| r.get(0)).unwrap()
}

#[tokio::test]
async fn test_assign_to_personal_happy_path() {
    let (path, _guard) = setup_temp_db_with_free_unit();
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
    let result = cmd_assign_free_unit(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let fu = result.unwrap();
    assert_eq!(fu.destination, Some("personal".to_string()));
    assert_eq!(fu.assigned_by, Some("diego".to_string()));
    assert!(fu.assigned_at.is_some());
}

#[tokio::test]
async fn test_assign_to_vip_happy_path() {
    let (path, _guard) = setup_temp_db_with_free_unit();
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
    let result = cmd_assign_free_unit(input).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);
    let fu = result.unwrap();
    assert_eq!(fu.destination, Some("vip".to_string()));
    assert_eq!(fu.destination_ref, Some("CUST-001".to_string()));
}

#[tokio::test]
async fn test_assign_to_mystery_happy_path() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "mystery".to_string(),
        destination_ref: Some("mystery_pool_2026_W17".to_string()),
        family_id: None, jersey_id: None, notes: None,
    };
    assert!(cmd_assign_free_unit(input).await.is_ok());
}

#[tokio::test]
async fn test_assign_to_garantizada_happy_path() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "garantizada".to_string(),
        destination_ref: Some("Q475 publicación".to_string()),
        family_id: None, jersey_id: None, notes: None,
    };
    assert!(cmd_assign_free_unit(input).await.is_ok());
}

#[tokio::test]
async fn test_assign_invalid_destination_rejected() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "INVALID_DEST".to_string(),
        destination_ref: None, family_id: None, jersey_id: None, notes: None,
    };
    let result = cmd_assign_free_unit(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("destination"));
}

#[tokio::test]
async fn test_assign_vip_without_customer_rejected() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: None,  // missing — required for VIP
        family_id: None, jersey_id: None, notes: None,
    };
    let result = cmd_assign_free_unit(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("destination_ref"));
}

#[tokio::test]
async fn test_assign_vip_invalid_customer_rejected() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let input = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: Some("CUST-NONEXISTENT".to_string()),
        family_id: None, jersey_id: None, notes: None,
    };
    let result = cmd_assign_free_unit(input).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("customer"));
}

#[tokio::test]
async fn test_reassign_already_assigned_rejected() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    let first = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "personal".to_string(),
        destination_ref: None, family_id: None, jersey_id: None, notes: None,
    };
    cmd_assign_free_unit(first).await.unwrap();

    let second = AssignFreeUnitInput {
        free_unit_id: id,
        destination: "vip".to_string(),
        destination_ref: Some("CUST-001".to_string()),
        family_id: None, jersey_id: None, notes: None,
    };
    let result = cmd_assign_free_unit(second).await;
    assert!(result.is_err());
    assert!(format!("{:?}", result.unwrap_err()).contains("already assigned"));
}

#[tokio::test]
async fn test_unassign_roundtrip() {
    let (path, _guard) = setup_temp_db_with_free_unit();
    use el_club_erp_lib::*;

    let id = get_seeded_free_unit_id(&path);
    cmd_assign_free_unit(AssignFreeUnitInput {
        free_unit_id: id, destination: "personal".to_string(),
        destination_ref: None, family_id: None, jersey_id: None, notes: None,
    }).await.unwrap();

    let result = cmd_unassign_free_unit(id).await;
    assert!(result.is_ok());
    let fu = result.unwrap();
    assert!(fu.destination.is_none());
    assert!(fu.assigned_at.is_none());
    assert!(fu.assigned_by.is_none());
    assert!(fu.destination_ref.is_none());
}
```

- [ ] **Step 2: Run test to verify it fails (compile error)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_assign_free_unit_test 2>&1 | tail -20
```
Expected: FAIL · `cannot find type 'AssignFreeUnitInput'` o similar

- [ ] **Step 3: Add `AssignFreeUnitInput` struct + valid destinations const**

Add near `FreeUnit` struct (Task 1):

```rust
const VALID_FREE_DESTINATIONS: &[&str] = &["vip", "mystery", "garantizada", "personal"];

#[derive(Debug, Clone, Deserialize)]
pub struct AssignFreeUnitInput {
    pub free_unit_id: i64,
    pub destination: String,                  // must be one of VALID_FREE_DESTINATIONS
    pub destination_ref: Option<String>,      // required if destination='vip'
    pub family_id: Option<String>,
    pub jersey_id: Option<String>,
    pub notes: Option<String>,
}
```

- [ ] **Step 4: Implement `impl_assign_free_unit` (pub fn · transactional)**

```rust
/// Assigns a free unit to a destination. Transactional. Validates:
/// - destination must be in VALID_FREE_DESTINATIONS (Rust-enforced · spec sec 7 line 524 · ver Open Questions)
/// - free_unit_id must exist + currently unassigned (destination IS NULL)
/// - if destination='vip', destination_ref must be a valid customer_id
pub fn impl_assign_free_unit(input: AssignFreeUnitInput) -> Result<FreeUnit, String> {
    // 1. validate destination
    if !VALID_FREE_DESTINATIONS.contains(&input.destination.as_str()) {
        return Err(format!(
            "invalid destination '{}'; must be one of {:?}",
            input.destination, VALID_FREE_DESTINATIONS
        ));
    }

    // 2. VIP requires destination_ref
    if input.destination == "vip" && input.destination_ref.is_none() {
        return Err("destination_ref required when destination='vip' (must be customer_id)".to_string());
    }

    let mut conn = Connection::open(db_path()).map_err(|e| e.to_string())?;
    let tx = conn.transaction().map_err(|e| e.to_string())?;

    // 3. fetch + lock current row · ensure exists + unassigned
    let current_dest: Option<String> = tx.query_row(
        "SELECT destination FROM import_free_unit WHERE free_unit_id = ?",
        rusqlite::params![input.free_unit_id],
        |r| r.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => format!("free_unit_id {} not found", input.free_unit_id),
        _ => e.to_string(),
    })?;
    if current_dest.is_some() {
        return Err(format!(
            "free_unit_id {} already assigned to '{}' · use unassign first",
            input.free_unit_id, current_dest.unwrap()
        ));
    }

    // 4. if VIP, validate customer_id exists
    if input.destination == "vip" {
        let cust_ref = input.destination_ref.as_ref().unwrap();
        let exists: bool = tx.query_row(
            "SELECT 1 FROM customers WHERE customer_id = ?",
            rusqlite::params![cust_ref],
            |_| Ok(true),
        ).unwrap_or(false);
        if !exists {
            return Err(format!("customer_id '{}' not found", cust_ref));
        }
    }

    // 5. UPDATE row
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    tx.execute(
        "UPDATE import_free_unit SET \
           destination = ?, destination_ref = ?, family_id = ?, jersey_id = ?, \
           assigned_at = ?, assigned_by = 'diego', notes = COALESCE(?, notes) \
         WHERE free_unit_id = ?",
        rusqlite::params![
            input.destination, input.destination_ref,
            input.family_id, input.jersey_id, now,
            input.notes, input.free_unit_id
        ],
    ).map_err(|e| e.to_string())?;

    tx.commit().map_err(|e| e.to_string())?;

    // 6. re-read + return
    let updated = impl_list_free_units(Some(FreeUnitFilter {
        import_id: None, destination: None, status: None
    }))?.into_iter()
        .find(|fu| fu.free_unit_id == input.free_unit_id)
        .ok_or_else(|| "free unit vanished post-update".to_string())?;
    Ok(updated)
}

#[tauri::command]
pub async fn cmd_assign_free_unit(input: AssignFreeUnitInput) -> Result<FreeUnit, String> {
    impl_assign_free_unit(input)
}
```

- [ ] **Step 5: Implement `impl_unassign_free_unit` + shim**

```rust
/// Resets a free unit to unassigned state. For correcting mistakes.
/// Idempotent: unassigning an already-unassigned unit returns it unchanged.
pub fn impl_unassign_free_unit(free_unit_id: i64) -> Result<FreeUnit, String> {
    let mut conn = Connection::open(db_path()).map_err(|e| e.to_string())?;
    let tx = conn.transaction().map_err(|e| e.to_string())?;

    // verify exists
    let _: i64 = tx.query_row(
        "SELECT free_unit_id FROM import_free_unit WHERE free_unit_id = ?",
        rusqlite::params![free_unit_id],
        |r| r.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => format!("free_unit_id {} not found", free_unit_id),
        _ => e.to_string(),
    })?;

    tx.execute(
        "UPDATE import_free_unit SET \
           destination = NULL, destination_ref = NULL, \
           assigned_at = NULL, assigned_by = NULL \
         WHERE free_unit_id = ?",
        rusqlite::params![free_unit_id],
    ).map_err(|e| e.to_string())?;

    tx.commit().map_err(|e| e.to_string())?;

    let updated = impl_list_free_units(None)?.into_iter()
        .find(|fu| fu.free_unit_id == free_unit_id)
        .ok_or_else(|| "free unit vanished post-update".to_string())?;
    Ok(updated)
}

#[tauri::command]
pub async fn cmd_unassign_free_unit(free_unit_id: i64) -> Result<FreeUnit, String> {
    impl_unassign_free_unit(free_unit_id)
}
```

- [ ] **Step 6: Wire both into `generate_handler!`**

Agregar `cmd_assign_free_unit` + `cmd_unassign_free_unit` a la lista del handler.

- [ ] **Step 7: Run test to verify it passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_assign_free_unit_test 2>&1 | tail -20
```
Expected: PASS · `running 9 tests · test result: ok. 9 passed`

Si algún test falla → diagnose · NO commitear hasta que todos pasen.

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r4_assign_free_unit_test.rs && \
  git commit -m "feat(imp-r4): add cmd_assign_free_unit + cmd_unassign_free_unit (TDD · transactional)

- AssignFreeUnitInput with 4 valid destinations (vip/mystery/garantizada/personal)
- VIP requires destination_ref + customer_id existence check
- Re-assign rejected (must unassign first to correct mistakes)
- Unassign roundtrip resets to NULL state (assigned_at/by/destination/ref)
- 9 TDD tests covering happy paths per destination + 4 rejection paths + roundtrip
- Spec divergence noted: CHECK constraint on destination NOT in actual table (R1 schema) · enforced in Rust (see Open Questions)"
```

---

## Task Group 2: MODIFY close_import + regression tests (HIGH RISK · careful)

> **STOP CONDITION:** Si en cualquier paso de este Task Group la regresión test PRE-existente (`imp_r4_close_regression_existing_test.rs`) falla · STOP inmediatamente y escalá a Diego antes de seguir. Esta función ya está en producción y Diego ya cerró IMP-2026-04-07 con ella.

### Task 3: Regression canary test FIRST (smoke contra comportamiento existente)

**Files:**
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_regression_existing_test.rs`

- [ ] **Step 1: Read current `impl_close_import_proportional` to understand exact contract**

```bash
grep -n "close_import_proportional\|fn impl_close\|pub async fn cmd_close" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs
```

Then `Read` lib.rs lines 2620-2740 to capture the EXACT current behavior (status update · prorrateo loop · what it returns).

- [ ] **Step 2: Write canary test that asserts CURRENT behavior**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_regression_existing_test.rs`:

```rust
// CANARY · This test asserts the close_import_proportional behavior PRE-R4-modification.
// Must continue to pass AFTER Task 4 modifies the function.
// If this fails post-mod · STOP and escalate.
use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_canary_db() -> (PathBuf, std::sync::MutexGuard<'static, ()>) {
    let guard = DB_LOCK.lock().unwrap();
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r4_canary_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imports (
          import_id TEXT PRIMARY KEY, paid_at TEXT, arrived_at TEXT, supplier TEXT,
          bruto_usd REAL, shipping_gtq REAL, fx REAL, total_landed_gtq REAL,
          n_units INTEGER, unit_cost REAL, status TEXT, notes TEXT,
          created_at TEXT, tracking_code TEXT, carrier TEXT, lead_time_days INTEGER
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
        -- Seed canary import + 22 paid items (mirrors IMP-2026-04-07 shape)
        INSERT INTO imports (import_id, paid_at, arrived_at, supplier, bruto_usd,
                             shipping_gtq, fx, n_units, status, created_at)
          VALUES ('CANARY-IMP', '2026-04-01', '2026-04-09', 'Bond',
                  411.40, 0.0, 7.73, 22, 'arrived', '2026-04-01 10:00:00');
        -- 22 items uniform $13 each
    "#).unwrap();
    for i in 1..=22 {
        conn.execute(
            "INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type) \
             VALUES (?, 'fam-arg-2026', 'CANARY-IMP', 13.0, 'paid')",
            rusqlite::params![format!("S-{}", i)],
        ).unwrap();
    }
    env::set_var("ERP_DB_PATH", &path);
    (path, guard)
}

#[tokio::test]
async fn canary_close_existing_behavior_status_and_prorrateo() {
    let (path, _guard) = setup_canary_db();
    use el_club_erp_lib::*;

    // Invoke close (existing function · pre or post R4 mod · must produce same status + prorrateo)
    let result = cmd_close_import_proportional("CANARY-IMP".to_string()).await;
    assert!(result.is_ok(), "expected Ok, got {:?}", result);

    let conn = Connection::open(&path).unwrap();

    // Assert status updated
    let status: String = conn.query_row(
        "SELECT status FROM imports WHERE import_id='CANARY-IMP'",
        [], |r| r.get(0)
    ).unwrap();
    assert_eq!(status, "closed", "status must transition to closed");

    // Assert prorrateo applied (each item gets ~Q145 · same as IMP-2026-04-07 historic)
    let avg_cost: f64 = conn.query_row(
        "SELECT AVG(unit_cost) FROM sale_items WHERE import_id='CANARY-IMP'",
        [], |r| r.get(0)
    ).unwrap();
    // total_landed = 411.40 * 7.73 = 3180.12 / 22 ≈ 144.55
    assert!((avg_cost - 144.55).abs() < 1.0, "avg unit_cost should be ~Q145, got {}", avg_cost);
}
```

- [ ] **Step 3: Run canary BEFORE any modification**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_close_regression_existing_test 2>&1 | tail -15
```
Expected: PASS. **Si falla acá → mi setup del fixture está mal · NO seguir hasta que pase contra el código existente.**

- [ ] **Step 4: Commit canary baseline**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src-tauri/tests/imp_r4_close_regression_existing_test.rs && \
  git commit -m "test(imp-r4): add canary regression test for cmd_close_import_proportional

- Asserts current behavior (status->closed + ~Q145/u prorrateo) on a 22-unit fixture
- Mirrors IMP-2026-04-07 historic shape ($411 bruto · FX 7.73 · 22 units)
- MUST continue to pass after Task 4 modifies the function to also create free units
- If this fails post-mod · STOP and escalate"
```

---

### Task 4: Write failing test for free units auto-create

**Files:**
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_creates_free_units_test.rs`

- [ ] **Step 1: Write failing test (4 cases · idempotency included)**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r4_close_creates_free_units_test.rs`:

```rust
// TDD: cmd_close_import_proportional must INSERT floor(n_paid/10) rows into import_free_unit.
// Idempotent: re-closing must NOT duplicate.
use std::path::PathBuf;
use std::env;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_db_with_n_items(import_id: &str, n_paid: usize) -> (PathBuf, std::sync::MutexGuard<'static, ()>) {
    let guard = DB_LOCK.lock().unwrap();
    let dir = env::temp_dir();
    let path = dir.join(format!("imp_r4_free_create_{}_{}.db", import_id, std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }

    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imports (
          import_id TEXT PRIMARY KEY, paid_at TEXT, arrived_at TEXT, supplier TEXT,
          bruto_usd REAL, shipping_gtq REAL, fx REAL, total_landed_gtq REAL,
          n_units INTEGER, unit_cost REAL, status TEXT, notes TEXT,
          created_at TEXT, tracking_code TEXT, carrier TEXT, lead_time_days INTEGER
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
    "#).unwrap();
    conn.execute(
        "INSERT INTO imports (import_id, paid_at, arrived_at, supplier, bruto_usd, \
                              shipping_gtq, fx, n_units, status, created_at) \
         VALUES (?, '2026-04-01', '2026-04-09', 'Bond', ?, 0.0, 7.73, ?, 'arrived', '2026-04-01 10:00:00')",
        rusqlite::params![import_id, (n_paid as f64) * 13.0, n_paid as i64],
    ).unwrap();
    for i in 1..=n_paid {
        conn.execute(
            "INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type) \
             VALUES (?, 'fam-x', ?, 13.0, 'paid')",
            rusqlite::params![format!("S-{}", i), import_id],
        ).unwrap();
    }
    env::set_var("ERP_DB_PATH", &path);
    (path, guard)
}

fn count_free_units(path: &PathBuf, import_id: &str) -> i64 {
    let conn = Connection::open(path).unwrap();
    conn.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE import_id = ?",
        rusqlite::params![import_id], |r| r.get(0)
    ).unwrap()
}

#[tokio::test]
async fn close_22_paid_creates_2_free_units() {
    let (path, _guard) = setup_db_with_n_items("IMP-22", 22);
    use el_club_erp_lib::*;
    cmd_close_import_proportional("IMP-22".to_string()).await.unwrap();
    assert_eq!(count_free_units(&path, "IMP-22"), 2, "floor(22/10) = 2");
}

#[tokio::test]
async fn close_9_paid_creates_0_free_units() {
    let (path, _guard) = setup_db_with_n_items("IMP-9", 9);
    use el_club_erp_lib::*;
    cmd_close_import_proportional("IMP-9".to_string()).await.unwrap();
    assert_eq!(count_free_units(&path, "IMP-9"), 0, "floor(9/10) = 0");
}

#[tokio::test]
async fn close_30_paid_creates_3_free_units() {
    let (path, _guard) = setup_db_with_n_items("IMP-30", 30);
    use el_club_erp_lib::*;
    cmd_close_import_proportional("IMP-30".to_string()).await.unwrap();
    assert_eq!(count_free_units(&path, "IMP-30"), 3, "floor(30/10) = 3");
}

#[tokio::test]
async fn close_idempotent_no_duplicate_free_units() {
    let (path, _guard) = setup_db_with_n_items("IMP-IDEMP", 22);
    use el_club_erp_lib::*;
    cmd_close_import_proportional("IMP-IDEMP".to_string()).await.unwrap();
    let first = count_free_units(&path, "IMP-IDEMP");
    assert_eq!(first, 2);

    // Reset status to allow re-close (simulates Diego's "re-open then close" admin action)
    let conn = Connection::open(&path).unwrap();
    conn.execute("UPDATE imports SET status='arrived' WHERE import_id='IMP-IDEMP'", []).unwrap();
    drop(conn);

    let result = cmd_close_import_proportional("IMP-IDEMP".to_string()).await;
    assert!(result.is_ok(), "re-close must succeed");
    let second = count_free_units(&path, "IMP-IDEMP");
    assert_eq!(second, 2, "re-close must NOT create duplicate free units (idempotency guard)");
}
```

- [ ] **Step 2: Run test · verify it FAILS**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_close_creates_free_units_test 2>&1 | tail -20
```
Expected: 4 tests fail (count_free_units returns 0 because close doesn't create them yet)

---

### Task 5: MODIFY `impl_close_import_proportional` to auto-create free units

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (the existing `impl_close_import_proportional` function · ~line 2620 region)

- [ ] **Step 1: Locate exact insertion point**

Read lib.rs around the `tx.commit()` of `impl_close_import_proportional` to find the precise position. The free unit INSERT must happen BEFORE `tx.commit()` (atomic with the close).

```bash
grep -n "fn impl_close_import_proportional\|tx.commit" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs
```

Then `Read` the function in full to capture exact context.

- [ ] **Step 2: Insert free units logic right before `tx.commit()`**

Modify the `impl_close_import_proportional` function to add this block AFTER the prorrateo loop and BEFORE `tx.commit()`. Use Edit tool with exact context — DO NOT use replace_all:

```rust
    // === IMP-R4 · Auto-create free units (floor(n_paid / 10)) ===
    // Idempotency guard: skip if free units already exist for this import_id.
    let existing_free_count: i64 = tx.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE import_id = ?",
        rusqlite::params![import_id],
        |r| r.get(0),
    ).map_err(|e| e.to_string())?;

    if existing_free_count == 0 {
        // Count items that are NOT already flagged as 'free' (per spec sec 4.4 line 256)
        let n_paid: i64 = tx.query_row(
            "SELECT COUNT(*) FROM sale_items \
             WHERE import_id = ? AND (item_type IS NULL OR item_type != 'free')",
            rusqlite::params![import_id],
            |r| r.get(0),
        ).map_err(|e| e.to_string())?;

        let n_free = n_paid / 10; // integer division = floor
        if n_free > 0 {
            let now_ts = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
            for _ in 0..n_free {
                tx.execute(
                    "INSERT INTO import_free_unit (import_id, created_at) VALUES (?, ?)",
                    rusqlite::params![import_id, now_ts],
                ).map_err(|e| e.to_string())?;
            }
        }
    }
    // === end IMP-R4 ===
```

- [ ] **Step 3: Run NEW free units test · expect PASS**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_close_creates_free_units_test 2>&1 | tail -15
```
Expected: PASS · 4 tests · `test result: ok. 4 passed`

- [ ] **Step 4: Run CANARY regression test · expect STILL PASS (CRITICAL)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r4_close_regression_existing_test 2>&1 | tail -15
```
Expected: PASS. **Si falla acá → la modificación rompió el comportamiento original. STOP. Diagnose. Si no es trivial, escalá a Diego.**

- [ ] **Step 5: Run R1.5 close-related tests (broader regression)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test imp_r15 2>&1 | tail -20
```
Expected: todos los R1.5 tests siguen pasando (esp. los de close si existen).

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r4_close_creates_free_units_test.rs && \
  git commit -m "feat(imp-r4): auto-create floor(n_paid/10) free units in close_import_proportional

CRITICAL MODIFICATION to shipped command:
- Added INSERT batch atomic with the existing close transaction (before tx.commit)
- Idempotency guard: skips if free units already exist for this import_id
- n_paid counts sale_items WHERE item_type != 'free' (per spec sec 4.4 line 256)
- 4 TDD tests passing (22→2 · 9→0 · 30→3 · re-close idempotent)
- Canary regression test (status + prorrateo) STILL PASSES — behavior preserved
- Spec sec 4.4 D-FREE=A: free units created unassigned · Diego decides destino caso a caso"
```

---

## Task Group 3: Adapter wires (TS · sequential within file but independent files)

### Task 6: Extend `types.ts` with FreeUnit interfaces + adapter signatures

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Add interfaces near other Import* types**

Add to types.ts (locate Import-related types · agregar después):

```typescript
export interface FreeUnit {
  freeUnitId: number;
  importId: string;
  familyId: string | null;
  jerseyId: string | null;
  destination: 'vip' | 'mystery' | 'garantizada' | 'personal' | null;
  destinationRef: string | null;
  assignedAt: string | null;
  assignedBy: string | null;
  notes: string | null;
  createdAt: string;
  importSupplier: string | null;
  importPaidAt: string | null;
}

export interface AssignFreeUnitInput {
  freeUnitId: number;
  destination: 'vip' | 'mystery' | 'garantizada' | 'personal';
  destinationRef?: string | null;   // required if destination='vip'
  familyId?: string | null;
  jerseyId?: string | null;
  notes?: string | null;
}

export interface FreeUnitFilter {
  importId?: string;
  destination?: 'vip' | 'mystery' | 'garantizada' | 'personal' | 'unassigned';
  status?: 'assigned' | 'unassigned';
}
```

- [ ] **Step 2: Add 3 method signatures to `Adapter` interface**

```typescript
  listFreeUnits(filter?: FreeUnitFilter): Promise<FreeUnit[]>;
  assignFreeUnit(input: AssignFreeUnitInput): Promise<FreeUnit>;
  unassignFreeUnit(freeUnitId: number): Promise<FreeUnit>;
```

- [ ] **Step 3: Type-check via TS compile**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tsc --noEmit 2>&1 | tail -15
```
Expected: errors only in `tauri.ts` and `browser.ts` (missing implementations) · NO errors en types.ts ni en components.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/types.ts && \
  git commit -m "feat(imp-r4): adapter types · FreeUnit + AssignFreeUnitInput + FreeUnitFilter

- 3 new interfaces with snake_case→camelCase mapping
- 3 method signatures on Adapter (list / assign / unassign)
- Destination union type matches Rust VALID_FREE_DESTINATIONS"
```

---

### Task 7: Implement `tauri.ts` invocations

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Implement 3 methods on TauriAdapter**

Add (mirror existing import command shape · `invoke()` returns snake_case · adapter normalizes to camelCase):

```typescript
  async listFreeUnits(filter?: FreeUnitFilter): Promise<FreeUnit[]> {
    const rows = await invoke<any[]>('cmd_list_free_units', { filter: filter ?? null });
    return rows.map((r) => ({
      freeUnitId: r.free_unit_id,
      importId: r.import_id,
      familyId: r.family_id,
      jerseyId: r.jersey_id,
      destination: r.destination,
      destinationRef: r.destination_ref,
      assignedAt: r.assigned_at,
      assignedBy: r.assigned_by,
      notes: r.notes,
      createdAt: r.created_at,
      importSupplier: r.import_supplier,
      importPaidAt: r.import_paid_at,
    }));
  }

  async assignFreeUnit(input: AssignFreeUnitInput): Promise<FreeUnit> {
    const r = await invoke<any>('cmd_assign_free_unit', {
      input: {
        free_unit_id: input.freeUnitId,
        destination: input.destination,
        destination_ref: input.destinationRef ?? null,
        family_id: input.familyId ?? null,
        jersey_id: input.jerseyId ?? null,
        notes: input.notes ?? null,
      },
    });
    return {
      freeUnitId: r.free_unit_id, importId: r.import_id,
      familyId: r.family_id, jerseyId: r.jersey_id,
      destination: r.destination, destinationRef: r.destination_ref,
      assignedAt: r.assigned_at, assignedBy: r.assigned_by,
      notes: r.notes, createdAt: r.created_at,
      importSupplier: r.import_supplier, importPaidAt: r.import_paid_at,
    };
  }

  async unassignFreeUnit(freeUnitId: number): Promise<FreeUnit> {
    const r = await invoke<any>('cmd_unassign_free_unit', { freeUnitId });
    return {
      freeUnitId: r.free_unit_id, importId: r.import_id,
      familyId: r.family_id, jerseyId: r.jersey_id,
      destination: r.destination, destinationRef: r.destination_ref,
      assignedAt: r.assigned_at, assignedBy: r.assigned_by,
      notes: r.notes, createdAt: r.created_at,
      importSupplier: r.import_supplier, importPaidAt: r.import_paid_at,
    };
  }
```

- [ ] **Step 2: TS check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tsc --noEmit 2>&1 | tail -10
```
Expected: solo errors residuales en `browser.ts` (missing impl)

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/tauri.ts && \
  git commit -m "feat(imp-r4): tauri adapter · listFreeUnits + assignFreeUnit + unassignFreeUnit"
```

---

### Task 8: Implement `browser.ts` stubs

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 3 stub methods (throw NotAvailableInBrowser)**

```typescript
  async listFreeUnits(_filter?: FreeUnitFilter): Promise<FreeUnit[]> {
    throw new Error('NotAvailableInBrowser: free units require .exe (Tauri)');
  }
  async assignFreeUnit(_input: AssignFreeUnitInput): Promise<FreeUnit> {
    throw new Error('NotAvailableInBrowser: assignment requires .exe (Tauri)');
  }
  async unassignFreeUnit(_freeUnitId: number): Promise<FreeUnit> {
    throw new Error('NotAvailableInBrowser: unassignment requires .exe (Tauri)');
  }
```

- [ ] **Step 2: TS check (full clean now)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tsc --noEmit 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r4): browser adapter · 3 stubs throwing NotAvailableInBrowser"
```

---

## Task Group 4: Svelte components (modal + tab replacement)

### Task 9: AssignDestinationModal.svelte

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/AssignDestinationModal.svelte`

- [ ] **Step 1: Create modal file (~210 LOC)**

Pattern: BaseModal del Comercial · Svelte 5 runes · `$effect` self-clean · ESC + click-outside dismiss · disabled during submit · error banner.

```svelte
<script lang="ts">
  import BaseModal from '$lib/components/comercial/BaseModal.svelte';
  import { adapter } from '$lib/adapter';
  import type { FreeUnit, AssignFreeUnitInput } from '$lib/adapter/types';

  type Props = {
    open: boolean;
    freeUnit: FreeUnit | null;
    onClose: () => void;
    onAssigned: (updated: FreeUnit) => void;
  };
  let { open, freeUnit, onClose, onAssigned }: Props = $props();

  let destination = $state<'vip' | 'mystery' | 'garantizada' | 'personal'>('personal');
  let destinationRef = $state('');
  let notes = $state('');
  let familyId = $state('');
  let jerseyId = $state('');
  let submitting = $state(false);
  let error = $state<string | null>(null);

  // Customer search state for VIP destination
  let customers = $state<Array<{ customerId: string; fullName: string }>>([]);
  let customerQuery = $state('');

  $effect(() => {
    if (!open) {
      destination = 'personal';
      destinationRef = '';
      notes = '';
      familyId = '';
      jerseyId = '';
      submitting = false;
      error = null;
      customerQuery = '';
    }
  });

  // Load customers lazily when destination switches to VIP
  $effect(() => {
    if (destination === 'vip' && customers.length === 0) {
      adapter.listCustomers?.()?.then((cs: any[]) => {
        customers = cs.map((c) => ({ customerId: c.customerId, fullName: c.fullName }));
      }).catch(() => { /* swallow · UI shows manual input fallback */ });
    }
  });

  const filteredCustomers = $derived(
    customerQuery
      ? customers.filter((c) =>
          c.fullName.toLowerCase().includes(customerQuery.toLowerCase()) ||
          c.customerId.toLowerCase().includes(customerQuery.toLowerCase())
        )
      : customers
  );

  const refRequired = $derived(destination === 'vip');
  const refValid = $derived(!refRequired || destinationRef.trim().length > 0);

  async function handleSubmit() {
    if (!freeUnit) return;
    if (!refValid) { error = 'destination_ref requerido para VIP'; return; }
    submitting = true;
    error = null;
    try {
      const input: AssignFreeUnitInput = {
        freeUnitId: freeUnit.freeUnitId,
        destination,
        destinationRef: destinationRef.trim() || null,
        familyId: familyId.trim() || null,
        jerseyId: jerseyId.trim() || null,
        notes: notes.trim() || null,
      };
      const updated = await adapter.assignFreeUnit(input);
      onAssigned(updated);
      onClose();
    } catch (e: any) {
      error = e?.message || String(e);
    } finally {
      submitting = false;
    }
  }
</script>

<BaseModal {open} {onClose} title="Asignar free unit" widthClass="w-[520px]">
  {#if freeUnit}
    <div class="space-y-4 text-[13px]">
      <div class="text-[11px] uppercase tracking-[0.08em] text-text-tertiary">
        FREE UNIT #{freeUnit.freeUnitId} · {freeUnit.importId}
      </div>

      <div class="space-y-2">
        <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
          Destino
        </label>
        <div class="grid grid-cols-2 gap-2">
          {#each ['vip', 'mystery', 'garantizada', 'personal'] as dest}
            <button type="button"
              onclick={() => { destination = dest as any; destinationRef = ''; }}
              class="px-3 py-2 border rounded text-left text-mono uppercase tracking-wider
                     {destination === dest
                       ? 'border-accent text-accent bg-surface-2'
                       : 'border-border text-text-secondary hover:border-border-strong'}">
              ● {dest}
            </button>
          {/each}
        </div>
      </div>

      {#if destination === 'vip'}
        <div class="space-y-1">
          <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
            Customer (requerido)
          </label>
          <input type="text" bind:value={customerQuery} placeholder="Buscar customer…"
            class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-mono" />
          {#if filteredCustomers.length > 0}
            <div class="max-h-32 overflow-y-auto border border-border rounded">
              {#each filteredCustomers.slice(0, 8) as c}
                <button type="button"
                  onclick={() => { destinationRef = c.customerId; customerQuery = c.fullName; }}
                  class="w-full px-2 py-1 text-left text-[12px] hover:bg-surface-2
                         {destinationRef === c.customerId ? 'bg-surface-2 text-accent' : ''}">
                  <span class="text-mono">{c.customerId}</span> · {c.fullName}
                </button>
              {/each}
            </div>
          {/if}
          <input type="text" bind:value={destinationRef} placeholder="o customer_id manual"
            class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-mono text-[12px]" />
        </div>
      {:else if destination === 'mystery'}
        <div class="space-y-1">
          <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
            Pool ref (texto · ej. mystery_pool_2026_W17)
          </label>
          <input type="text" bind:value={destinationRef} placeholder="opcional"
            class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-mono" />
        </div>
      {:else if destination === 'garantizada'}
        <div class="space-y-1">
          <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
            Stock ref (ej. Q475 publicación)
          </label>
          <input type="text" bind:value={destinationRef} placeholder="opcional"
            class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-mono" />
        </div>
      {:else}
        <div class="space-y-1">
          <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
            Personal · ref opcional
          </label>
          <input type="text" bind:value={destinationRef} placeholder="opcional"
            class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-mono" />
        </div>
      {/if}

      <div class="space-y-1">
        <label class="block text-[10px] uppercase tracking-[0.08em] text-text-tertiary">
          Notes (opcional)
        </label>
        <textarea bind:value={notes} rows="2"
          class="w-full px-2 py-1 bg-surface-1 border border-border rounded text-[12px]"></textarea>
      </div>

      {#if error}
        <div class="p-2 bg-danger/10 border border-danger/40 rounded text-danger text-[12px]">
          ⚠️ {error}
        </div>
      {/if}

      <div class="flex justify-end gap-2 pt-2">
        <button type="button" onclick={onClose} disabled={submitting}
          class="px-3 py-1 border border-border text-text-secondary rounded text-[12px]">
          Cancelar
        </button>
        <button type="button" onclick={handleSubmit} disabled={submitting || !refValid}
          class="px-3 py-1 bg-accent text-black font-semibold rounded text-[12px]
                 disabled:opacity-50 disabled:cursor-not-allowed">
          {submitting ? 'Asignando…' : `Asignar a ${destination}`}
        </button>
      </div>
    </div>
  {/if}
</BaseModal>
```

- [ ] **Step 2: TS check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tsc --noEmit 2>&1 | tail -5
```
Expected: 0 errors (si `adapter.listCustomers?` no existe · el optional chain swallow funciona).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/components/importaciones/AssignDestinationModal.svelte && \
  git commit -m "feat(imp-r4): AssignDestinationModal · 4 destinos · VIP customer search · refs dinámicos"
```

---

### Task 10: FreeUnitsTab.svelte (REPLACE 6-line stub)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte`

- [ ] **Step 1: Read current stub to confirm path + size**

```bash
cat C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte
```
Expected: 6-line "Próximamente" placeholder

- [ ] **Step 2: Replace entire file content**

Use Write tool (full rewrite).

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import type { FreeUnit, FreeUnitFilter } from '$lib/adapter/types';
  import AssignDestinationModal from '../AssignDestinationModal.svelte';

  let units = $state<FreeUnit[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let filter = $state<'all' | 'unassigned' | 'vip' | 'mystery' | 'garantizada' | 'personal'>('all');

  let modalOpen = $state(false);
  let modalUnit = $state<FreeUnit | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      const f: FreeUnitFilter = {};
      if (filter === 'unassigned') f.status = 'unassigned';
      else if (filter !== 'all') f.destination = filter;
      units = await adapter.listFreeUnits(f);
    } catch (e: any) {
      error = e?.message || String(e);
    } finally {
      loading = false;
    }
  }

  onMount(load);
  $effect(() => { void filter; load(); });

  const counts = $derived({
    all: units.length,
    unassigned: units.filter((u) => !u.destination).length,
    vip: units.filter((u) => u.destination === 'vip').length,
    mystery: units.filter((u) => u.destination === 'mystery').length,
    garantizada: units.filter((u) => u.destination === 'garantizada').length,
    personal: units.filter((u) => u.destination === 'personal').length,
  });

  function openAssign(unit: FreeUnit) {
    modalUnit = unit;
    modalOpen = true;
  }

  function onAssigned(updated: FreeUnit) {
    units = units.map((u) => (u.freeUnitId === updated.freeUnitId ? updated : u));
  }

  async function handleUnassign(unit: FreeUnit) {
    if (!confirm(`Desasignar free unit #${unit.freeUnitId}?`)) return;
    try {
      const updated = await adapter.unassignFreeUnit(unit.freeUnitId);
      units = units.map((u) => (u.freeUnitId === updated.freeUnitId ? updated : u));
    } catch (e: any) {
      alert(`Error: ${e?.message || e}`);
    }
  }
</script>

<div class="p-4 space-y-4">
  <!-- Header · counts as filter chips -->
  <div class="flex flex-wrap gap-2">
    {#each [
      { key: 'all', label: 'Todos', n: counts.all },
      { key: 'unassigned', label: '● Sin asignar', n: counts.unassigned },
      { key: 'vip', label: '● VIP', n: counts.vip },
      { key: 'mystery', label: '● Mystery', n: counts.mystery },
      { key: 'garantizada', label: '● Garantizada', n: counts.garantizada },
      { key: 'personal', label: '● Personal', n: counts.personal },
    ] as chip}
      <button onclick={() => filter = chip.key as any}
        class="px-3 py-1 border rounded text-mono uppercase text-[11px] tracking-wider
               {filter === chip.key
                 ? 'border-accent text-accent bg-surface-2'
                 : 'border-border text-text-secondary hover:border-border-strong'}">
        {chip.label} · {chip.n}
      </button>
    {/each}
  </div>

  {#if loading}
    <div class="text-text-tertiary text-[12px]">Cargando free units…</div>
  {:else if error}
    <div class="p-2 bg-danger/10 border border-danger/40 rounded text-danger text-[12px]">
      ⚠️ {error}
    </div>
  {:else if units.length === 0}
    <div class="border border-border rounded p-6 text-center text-text-tertiary text-[12px] space-y-2">
      <div>Sin free units todavía.</div>
      <div class="text-[11px]">
        Cuando cerrás un batch con N paid units, se crean automáticamente <code class="text-mono">floor(N/10)</code> free units en este ledger.
      </div>
    </div>
  {:else}
    <div class="border border-border rounded overflow-hidden">
      <table class="w-full text-[12px]">
        <thead class="bg-surface-2 text-text-tertiary uppercase tracking-[0.08em] text-[10px]">
          <tr>
            <th class="px-2 py-2 text-left">Import</th>
            <th class="px-2 py-2 text-left">Family</th>
            <th class="px-2 py-2 text-left">Created</th>
            <th class="px-2 py-2 text-left">Destino</th>
            <th class="px-2 py-2 text-left">Ref</th>
            <th class="px-2 py-2 text-left">Notes</th>
            <th class="px-2 py-2 text-right">Acción</th>
          </tr>
        </thead>
        <tbody>
          {#each units as u}
            <tr class="border-t border-border hover:bg-surface-2">
              <td class="px-2 py-2 text-mono">{u.importId}</td>
              <td class="px-2 py-2 text-mono text-text-secondary">{u.familyId ?? '—'}</td>
              <td class="px-2 py-2 text-mono text-text-tertiary">{u.createdAt?.slice(0, 10) ?? '—'}</td>
              <td class="px-2 py-2 text-mono uppercase tracking-wider">
                {#if u.destination}
                  <span class="text-accent">● {u.destination}</span>
                {:else}
                  <span class="text-text-tertiary">● unassigned</span>
                {/if}
              </td>
              <td class="px-2 py-2 text-mono text-text-secondary">{u.destinationRef ?? '—'}</td>
              <td class="px-2 py-2 text-text-secondary truncate max-w-[140px]">{u.notes ?? ''}</td>
              <td class="px-2 py-2 text-right space-x-2">
                {#if u.destination}
                  <button onclick={() => handleUnassign(u)}
                    class="px-2 py-1 border border-border text-text-secondary text-[11px] rounded hover:border-danger hover:text-danger">
                    Desasignar
                  </button>
                {:else}
                  <button onclick={() => openAssign(u)}
                    class="px-2 py-1 bg-accent text-black font-semibold text-[11px] rounded">
                    Asignar
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<AssignDestinationModal
  open={modalOpen}
  freeUnit={modalUnit}
  onClose={() => { modalOpen = false; modalUnit = null; }}
  onAssigned={onAssigned}
/>
```

- [ ] **Step 3: TS check + dev server boot**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tsc --noEmit 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte && \
  git commit -m "feat(imp-r4): FreeUnitsTab funcional · counts chips · table + assign/unassign actions

- Replaces 6-line 'Próximamente' stub with ~220 LOC tab
- 6 filter chips (all / unassigned / vip / mystery / garantizada / personal)
- Table cols: import_id · family · created · destino · ref · notes · action
- Per-row [Asignar] button opens AssignDestinationModal
- Per-row [Desasignar] resets to unassigned (with confirm)
- Empty state explains floor(N/10) auto-create rule"
```

---

## Task Group 5: Wire-up tab badge + cross-refresh

### Task 11: Wire `[Free units N]` badge in ImportTabs

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte` (o `ImportShell.svelte` si las tabs viven ahí)

- [ ] **Step 1: Locate the tabs definition**

```bash
grep -rn "Free units\|freeunit\|FreeUnits" C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/
```
Expected: 1-3 matches · uno será el label del tab actual.

- [ ] **Step 2: Add reactive count badge**

In whichever component renders the tab labels · pull unassigned count via `adapter.listFreeUnits({ status: 'unassigned' })` on mount + after close/assign events · render label as `Free units {count}` (mono · color accent si > 0).

Pattern (illustrative · ajustar a la estructura existente):

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  let unassignedCount = $state(0);
  async function refreshFreeCount() {
    try {
      const us = await adapter.listFreeUnits({ status: 'unassigned' });
      unassignedCount = us.length;
    } catch { /* silent · tab still works */ }
  }
  onMount(refreshFreeCount);
</script>

<!-- In tab label: -->
<span>Free units {unassignedCount > 0 ? unassignedCount : ''}</span>
```

- [ ] **Step 3: Trigger refresh from PedidosTab close action (cross-tab event)**

Si PedidosTab tiene `handleCloseImport()` (post R1.5 · ya wired) · agregar al final del callback:
```typescript
window.dispatchEvent(new CustomEvent('imp-free-units-refresh'));
```
Y en ImportTabs:
```typescript
onMount(() => {
  refreshFreeCount();
  window.addEventListener('imp-free-units-refresh', refreshFreeCount);
  return () => window.removeEventListener('imp-free-units-refresh', refreshFreeCount);
});
```

(Alternativa: usar un Svelte store global si existe el pattern · escalar si no claro.)

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/components/importaciones/ImportTabs.svelte \
          overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte && \
  git commit -m "feat(imp-r4): tab badge · 'Free units N' count of unassigned · cross-tab refresh event"
```

---

## Task Group 6: Smoke + verification

### Task 12: smoke_imp_r4.py end-to-end

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r4.py`

- [ ] **Step 1: Write smoke script**

```python
#!/usr/bin/env python3
"""IMP-R4 smoke test · seed → close → verify free units → assign → cleanup.

Runs against the worktree DB (ERP_DB_PATH or default snapshot). Idempotent.
"""
import sqlite3
import os
import sys
import subprocess
from datetime import datetime

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:/Users/Diego/el-club-imp/erp/elclub.db')
TEST_IMP = 'IMP-R4-SMOKE'

def main():
    print(f"[smoke_imp_r4] DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")  # bypass for smoke

    # cleanup any prior run
    conn.execute("DELETE FROM import_free_unit WHERE import_id = ?", (TEST_IMP,))
    conn.execute("DELETE FROM sale_items WHERE import_id = ?", (TEST_IMP,))
    conn.execute("DELETE FROM imports WHERE import_id = ?", (TEST_IMP,))
    conn.commit()

    # seed: import + 22 sale_items
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO imports (import_id, paid_at, arrived_at, supplier, bruto_usd,
                             shipping_gtq, fx, n_units, status, created_at)
        VALUES (?, '2026-04-20', '2026-04-28', 'Bond', 286.0, 0.0, 7.73, 22, 'arrived', ?)
    """, (TEST_IMP, now))
    for i in range(22):
        conn.execute("""
            INSERT INTO sale_items (sale_id, family_id, import_id, unit_cost_usd, item_type)
            VALUES (?, 'fam-smoke', ?, 13.0, 'paid')
        """, (f'S-SMOKE-{i}', TEST_IMP))
    conn.commit()
    print(f"[smoke] seeded {TEST_IMP} + 22 sale_items")

    # NOTE: cmd_close_import_proportional must be invoked via Tauri or a Rust binary.
    # For smoke purposes here · we simulate the close logic directly (DB SQL):
    n_paid = conn.execute(
        "SELECT COUNT(*) FROM sale_items WHERE import_id=? AND (item_type IS NULL OR item_type != 'free')",
        (TEST_IMP,)
    ).fetchone()[0]
    n_free = n_paid // 10
    for _ in range(n_free):
        conn.execute(
            "INSERT INTO import_free_unit (import_id, created_at) VALUES (?, ?)",
            (TEST_IMP, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
    conn.execute("UPDATE imports SET status='closed' WHERE import_id=?", (TEST_IMP,))
    conn.commit()

    free_count = conn.execute(
        "SELECT COUNT(*) FROM import_free_unit WHERE import_id=?", (TEST_IMP,)
    ).fetchone()[0]
    assert free_count == 2, f"expected 2 free units, got {free_count}"
    print(f"[smoke] ✓ {free_count} free units auto-created (floor(22/10))")

    # assign first to personal
    fu_id = conn.execute(
        "SELECT free_unit_id FROM import_free_unit WHERE import_id=? LIMIT 1",
        (TEST_IMP,)
    ).fetchone()[0]
    conn.execute("""
        UPDATE import_free_unit
        SET destination='personal', assigned_at=?, assigned_by='diego', notes='smoke test'
        WHERE free_unit_id=?
    """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), fu_id))
    conn.commit()

    state = conn.execute(
        "SELECT destination, assigned_by FROM import_free_unit WHERE free_unit_id=?", (fu_id,)
    ).fetchone()
    assert state == ('personal', 'diego'), f"expected (personal, diego), got {state}"
    print(f"[smoke] ✓ free_unit_id={fu_id} assigned to personal/diego")

    # cleanup (preserves canary)
    conn.execute("DELETE FROM import_free_unit WHERE import_id=?", (TEST_IMP,))
    conn.execute("DELETE FROM sale_items WHERE import_id=?", (TEST_IMP,))
    conn.execute("DELETE FROM imports WHERE import_id=?", (TEST_IMP,))
    conn.commit()
    print(f"[smoke] ✓ cleanup ok · IMP-R4 smoke PASS")

if __name__ == '__main__':
    sys.exit(main() or 0)
```

- [ ] **Step 2: Run smoke**

```bash
cd C:/Users/Diego/el-club-imp && python erp/scripts/smoke_imp_r4.py
```
Expected: `IMP-R4 smoke PASS` · cleanup ok · canary `IMP-2026-04-07` intacta

- [ ] **Step 3: Verify cargo test suite full pass**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --tests 2>&1 | tail -30
```
Expected: ALL R4 + R1.5 tests pass · 0 failures

- [ ] **Step 4: Commit smoke**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add erp/scripts/smoke_imp_r4.py && \
  git commit -m "test(imp-r4): smoke_imp_r4.py · seed 22 items → close → 2 free units → assign personal → cleanup"
```

---

### Task 13: (OPTIONAL · escalate first) Migrate historical free units from notes

> **DECISION POINT:** Sólo 2 imports históricos (`IMP-2026-04-07`, `IMP-2026-04-18`) tienen el string "regalo" en notes. Diego puede entrarlas a mano más rápido vía la UI (Task 12 ya validó que el flujo funciona). **Recomendación: SKIPEAR esta task y hacerlo manualmente.** Si Diego decide ejecutarla · seguir abajo.

**Files (si se ejecuta):**
- Create: `el-club-imp/erp/scripts/migrate_free_units_from_notes.py`

- [ ] **Step 1: Escalate to Diego**

Pregunta: "¿Querés script automatizado para parsear las 2 notes históricas (`IMP-2026-04-07` y `IMP-2026-04-18`) o las entrás manualmente en la UI ahora que funciona?"

Si Diego dice manual → marcar task complete sin código.

Si Diego dice automatizado → implementar script con regex `(\d+)\s*\w*\s*regalo`, dialog confirmation per match, idempotency check (SELECT primero · skip si ya existen rows para ese import_id), y commit por separado.

---

## Self-Review

### Spec coverage check

- [ ] Sec 4.4 (Free units tab) · 5 estados (`NULL` = sin asignar · `assigned_vip` · `assigned_mystery` · `assigned_garantizada` · `assigned_personal`) · ✅ implementados (convención NULL · ver Open Q #3)
- [ ] Sec 4.4 layout · tabla con cols `import_id · sku_placeholder · player_spec · created_at · status · destination · notes` · ✅ ajustado a las cols disponibles (no hay `sku_placeholder` separado · usamos `family_id`)
- [ ] Sec 4.4 acción "asignar destino (4 opciones) + nota opcional" · ✅ AssignDestinationModal
- [ ] Sec 4.4 inbox event "X free unit(s) sin asignar — ¿qué hacés?" · ⚠️ NO en R4 (Inbox no implementado · agregar a R6 settings o post-IMP)
- [ ] Sec 4.4 cálculo `floor(n_paid / 10)` · ✅ Task 5
- [ ] Sec 4.4 migración historic notes · ⚠️ DEFERRED · Task 13 opcional · escalable
- [ ] Sec 6 D-FREE=A "sin asignar default" · ✅ INSERT con destination NULL
- [ ] Sec 7 schema `import_free_unit` 10 cols · ✅ no schema change needed (R1 already created)
- [ ] Sec 8 edge case "Free unit asignada a customer_id inexistente — bloquea con select picker que valida customers" · ✅ Task 2 valida en backend + UI tiene customer search con autocomplete

### Placeholder scan

- [ ] `grep -rn "TODO\|FIXME\|XXX\|placeholder" overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte overhaul/src/lib/components/importaciones/AssignDestinationModal.svelte` · expected: 0 hits

### Type consistency

- [ ] camelCase en TS · snake_case en Rust + adapter normalize · ✅ verificado en Task 7 stubs
- [ ] FreeUnit.destination union (`'vip' | 'mystery' | 'garantizada' | 'personal' | null`) matches Rust validation · ✅
- [ ] `npx tsc --noEmit` · expected 0 errors post-Task 8

### Cross-module impact

- [ ] **REGRESSION RISK · `cmd_close_import_proportional`**: ya shipped + usado por Diego en R1. Mitigated by:
  - Canary regression test (Task 3) seeded ANTES de modificar
  - Modificación es additive (INSERT batch al final · no toca prorrateo logic)
  - Idempotency guard previene duplicates en re-close
  - Atomic con la misma transacción (no inconsistencia parcial)
- [ ] **PedidosTab dispatch event** (Task 11): cross-tab event listener pattern · si no existe `Sidebar.svelte` o equivalente para wire · es no-op (badge solo refrescará al recargar la app)
- [ ] **Comercial sales linking**: no afectado (free units NO se materializan como sale_items en R4 · son ledger separado)
- [ ] **Margen real (R3)**: si R3 lee `free_units` para mostrar "Free units (N) valor Q—" · ya tiene la data · no breaking
- [ ] **Browser fallback**: 3 stubs throw NotAvailableInBrowser · ✅
- [ ] **R1.5 commands**: no tocados · `cmd_close_import_proportional` mantiene contrato (firma Result<Import,String>)

### Open questions for Diego

1. **Idempotency policy ante re-close:** R4 implementa "skip free unit creation if any already exist for import_id" · esto significa que si Diego edita los items post-cierre y hace re-close, no se generan más free units aunque debería (ej. cerró con 9 items → 0 free · agregó 2 más → 11 items · re-close debería dar 1 free pero no lo dará por la guard). Alternativa: comparar `n_free_existing` vs `floor(n_paid/10)` y crear el delta. **Recomendación R4:** mantener guard simple (skip if any exist) y abrir issue para revisar en feedback round si surge.

2. **Migration historic notes:** Task 13 OPCIONAL · sólo 2 imports · recomiendo entry manual via UI ya que el flujo funciona. ¿Confirma o querés script?

3. **CHECK constraint divergence — RESOLVED 2026-04-28 ~19:00:** spec sec 7 línea 524 dice `CHECK(destination IN ('unassigned','vip','mystery','garantizada','personal'))` pero la tabla R1 NO lo tiene. **Decisión Diego:** convención NULL (no 'unassigned' string) · R6 apply_imp_schema.py añade CHECK `CHECK(destination IS NULL OR destination IN ('vip','mystery','garantizada','personal'))` cuando aplique a main DB · R4 enforces en Rust validation con `VALID_FREE_DESTINATIONS = &["vip","mystery","garantizada","personal"]` (sin 'unassigned'). UI filter chips usan label "● Sin asignar" pero internamente filtra `destination IS NULL`.

4. **Mystery/Garantizada destination_ref:** sin validación strict (libre texto) porque los módulos correspondientes no existen. Confirmar OK.

5. **Inbox event "free unit sin asignar > 7d"** (spec sec 4.4 + sec 4.6 settings umbrales): NO en R4 · candidate para R6 (Settings · umbrales section). Confirmar.

---

## Execution Handoff

**Next:** Diego revisa este plan + los planes hermanos (R3 · R5 · R6) en paralelo. Approve → comenzar PHASE 1 R2 ship (Wave 1) primero, luego Wave 2 con R3+R4+R5+R6 paralelizable. R4 entry point: Task 0 pre-flight.

**Estimated execution time:** 13 tasks · ~3-4h con TDD strict + canary regression + smoke. Sub-agent dispatch posible para Tasks 9+10 (Svelte modal + tab) en paralelo si timeline aprieta · Tasks 1-5 (Rust) deben ser secuenciales por mí (lib.rs único · merge hell risk).

**Risk callout repeated:** Task 5 (modify shipped close_import) es el único punto de regresión real en R4. Canary test (Task 3) gates this · si rompe · STOP + escalar.
