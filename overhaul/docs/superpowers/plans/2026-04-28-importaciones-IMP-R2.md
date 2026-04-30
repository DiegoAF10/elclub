# IMP-R2 Implementation Plan — Wishlist + Promote-to-batch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver el blocker actual de Diego ("no hay UI para linkear items a un import") shippeando el tab Wishlist completo: CRUD de pre-pedidos individuales (con D7=B SKU validation contra `catalog.json`) + acción transaccional **Promote-to-batch** que crea un nuevo `imports` row con `status='paid'` por default (toggle "Ya pagué" ON · default; OFF → status='draft' con `paid_at` opcional) y **INSERTa todos los items promovidos a la nueva tabla `import_items`** (assigned + stock-future · single destination · `customer_id` nullable distingue ambos casos). Todo en una sola tx con rollback en cualquier error. Adicional: nuevo `cmd_mark_in_transit` para que Diego pueda marcar manualmente `paid → in_transit` antes de `cmd_register_arrival` (state machine completo: draft → paid → in_transit → arrived → closed). Bonus: el evento `import_promoted` se INSERTa sincrónicamente en `inbox_events` (table verificada en producción) dentro de la misma tx — eventos basados en cron (wishlist > 20 · assigned > 30d) quedan diferidos a R6 + cron infrastructure.

**Architecture:** Solo módulo IMP. **R2 NO crea tabla nueva** — la tabla `import_items` (destino del promote) la crea R6 vía `apply_imp_schema.py`. R2 ASUME que existe (Pre-flight Task 0 verifica). La tabla `import_wishlist` ya fue creada en R1. Decisión Diego (2026-04-28 ~19:00): **single destination table `import_items`** para todos los items promovidos · NO split entre `sale_items`/`jerseys` (peer review encontró schema constraints incompatibles: `sale_items.sale_id NOT NULL`, `sale_items.customer_id` no existe, `jerseys` tiene CHECK constraints estrictos). Distinción assigned vs stock-future se preserva con `import_items.customer_id` nullable (NULL = stock-future · NOT NULL = assigned). El catalog.json sigue siendo source of truth — `import_items` no duplica datos de producto. R3 lee `import_items` para "stock pendiente". Comercial flow futuro UPDATE `import_items.sale_item_id` cuando un item se vende. Inventario futuro UPDATE `import_items.jersey_id_published` cuando un item entra al catálogo público. 6 commands Rust nuevos siguen la convención `impl_X (pub) + cmd_X (#[tauri::command])` documentada en `lib.rs:2730-2742`. 4 componentes Svelte nuevos (1 tab que reemplaza el stub + 3 modals: WishlistItem · PromoteToBatch · MarkInTransit) siguen el pattern de `NewImportModal.svelte` shipped en R1.5. D7=B SKU validation se hace **server-side** en Rust (lee `catalog.json` via helper `catalog_path()` que ya existe en `lib.rs:53`). Promote-to-batch reusa `is_valid_import_id()` (R1.5) para enforce regex `IMP-YYYY-MM-DD` en el target import_id. Inbox events: la tabla `inbox_events` EXISTE en producción (verificado por peer review · Comercial-shipped) — implementamos el evento `import_promoted` como `INSERT INTO inbox_events` sincrónico dentro de la misma tx del promote.

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + serde_json (ya en deps · usado por audit) + Tauri 2 + Svelte 5 (`$state`/`$derived`/`$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · 0 deps nuevas.

---

## File Structure

### Files to create (10 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/overhaul/src/lib/components/importaciones/WishlistItemModal.svelte` | Form 9 fields para create/edit wishlist item · D7=B SKU feedback inline · invoca `adapter.createWishlistItem()` o `updateWishlistItem()` |
| `el-club-imp/overhaul/src/lib/components/importaciones/PromoteToBatchModal.svelte` | Form: import_id (regex enforced) + toggle "Ya pagué" (default ON · status=paid · paid_at=hoy required) + supplier + fx + lista checkbox de items active · invoca `adapter.promoteWishlistToBatch()` con `status` + `paidAt` |
| `el-club-imp/overhaul/src/lib/components/importaciones/MarkInTransitModal.svelte` | Confirm modal con input opcional `tracking_code` · invoca `adapter.markInTransit()` (state guard: solo desde status='paid') |
| `el-club-imp/overhaul/src/lib/data/wishlist.ts` | TypeScript type `WishlistItem` (mirror del struct Rust) + helpers (`statusLabel`, `targetSize`) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r2_create_wishlist_test.rs` | TDD light: D7=B validation rechaza family_id desconocido + happy path |
| `el-club-imp/overhaul/src-tauri/tests/imp_r2_promote_wishlist_test.rs` | TDD MANDATORY: happy path (3 items mixtos · 2 assigned + 1 stock-future) → 3 rows en `import_items` + edge cases (empty · invalid id · duplicate · already promoted · cancelled · status=paid + paid_at required · status=draft + paid_at NULL OK · bruto_usd negative · bonus inbox_events row) |
| `el-club-imp/overhaul/src-tauri/tests/imp_r2_mark_in_transit_test.rs` | Light TDD: state guard (solo desde 'paid') + happy path + tracking_code COALESCE |
| `el-club-imp/erp/scripts/smoke_imp_r2.py` | Smoke SQL: crear 5 items → promote 3 → verificar imports row + 3 rows en `import_items` (assigned + stock-future · single tabla) + wishlist status='promoted' + inbox_events row · cleanup |
| `el-club-imp/overhaul/src-tauri/tests/fixtures/catalog_minimal.json` | Fixture catalog con 3 family_ids para tests TDD (evita hit a catalog real) |
| (no Svelte tab `WishlistTab.svelte` create — ya existe stub a reemplazar) | — |

### Files to modify (8 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | Agregar struct `WishlistItem` + 4 Input structs + 6 commands (impl_X + cmd_X · `cmd_promote_wishlist_to_batch` INSERTa a `import_items` single table + `cmd_mark_in_transit`) + helper `catalog_family_exists` + INSERT a `inbox_events` (sincrónico) + wire `generate_handler!` | +465 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | `WishlistItem` interface + 4 input interfaces + 6 method signatures (`promoteWishlistToBatch` extendido con status+paidAt · `markInTransit` nuevo) | +60 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 6 invocations + imports | +52 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 6 NotAvailableInBrowser stubs + imports | +40 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte` | **REPLACE 6-line stub** con tab funcional ~280 LOC | +275 (del ~6) |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailHead.svelte` | Agregar botón "Marcar en tránsito" (visible cuando `imp.status === 'paid'`) que abre `MarkInTransitModal` | +15 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte` | Pasar `refreshTrigger` a WishlistTab + bumpear cuando promote-to-batch o mark_in_transit dispara | +14 |
| `el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte` | (verificar wiring · probable cero cambios si ya pasa props genéricamente) | +0-5 |
| `el-club-imp/overhaul/src-tauri/Cargo.toml` | (verificar `serde_json` ya está · debería estar por audit) | +0 |

**Total estimado:** ~990 líneas net nuevas (Rust ~465 · TS ~152 · Svelte ~340 · Python ~30). LOC reduction vs split approach: ~80 lines en Rust (single INSERT branch en lugar de if/else con sale_items vs jerseys).

> **⚠️ R6 dependency:** la tabla `import_items` (destino del promote) NO se crea en R2. La crea **R6's `apply_imp_schema.py`**. R2 ASUME que existe — Pre-flight Task 0 verifica la existencia + columnas requeridas (`family_id`, `customer_id`). Si no existe cuando R2 arranca, el executor debe correr `apply_imp_schema.py` primero (manual o vía R6 plan). Build-order dependency explícita: **R6 schema script → R2 commands**.

---

## Pre-flight (verify worktree state · NO assumptions)

### Task 0: Pre-flight verification

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Verify worktree branch + post-R1.5 HEAD**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git status -sb && git log --oneline -1
```
Expected: `## imp-r2-r6-build` · sin uncommitted changes · HEAD `606b121` (or later within R1.5 series)

- [ ] **Step 2: Verify R1 tables exist (no ALTER needed)**

Run:
```bash
sqlite3 C:/Users/Diego/el-club-imp/erp/elclub.db ".schema import_wishlist"
```
Expected: prints CREATE TABLE with 14 columns including `wishlist_item_id INTEGER PRIMARY KEY AUTOINCREMENT`, `family_id TEXT NOT NULL`, `status TEXT DEFAULT 'active'`, `promoted_to_import_id TEXT`. If this errors with "no such table" → STOP and ping Diego (R1 schema not applied to worktree DB).

- [ ] **Step 3: Verify wishlist starts empty**

Run:
```bash
sqlite3 C:/Users/Diego/el-club-imp/erp/elclub.db "SELECT COUNT(*) FROM import_wishlist; SELECT COUNT(*) FROM imports;"
```
Expected: `0` · `0` (clean snapshot)

- [ ] **Step 4: Verify R1.5 helpers + convention block present in lib.rs**

Run:
```bash
grep -n "is_valid_import_id\|read_import_by_id\|impl_create_import\|fn catalog_path" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs | head -10
```
Expected: 4+ matches showing helpers are defined and convention block is in place.

- [ ] **Step 5: Verify catalog.json reachable**

Run:
```bash
ls -lh C:/Users/Diego/elclub-catalogo-priv/data/catalog.json && \
  python -c "import json; c = json.load(open(r'C:/Users/Diego/elclub-catalogo-priv/data/catalog.json')); print('families:', len(c)); print('first:', c[0].get('family_id') if c else None)"
```
Expected: file exists, prints `families: N` (N > 100 typical) and a `family_id` like `ARG-2026-L-FS`.

- [ ] **Step 6: Sanity check Svelte stubs to replace**

Run:
```bash
wc -l C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte
```
Expected: ~6 lines (the "Próximamente" stub)

- [ ] **Step 7: VERIFY `import_items` table exists (R6 dependency · BLOCKING)**

Run:
```bash
python -c "import sqlite3; cols = [c[1] for c in sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db').execute('PRAGMA table_info(import_items)').fetchall()]; print('import_items cols:', cols); assert 'family_id' in cols and 'customer_id' in cols, 'TABLE MISSING — run apply_imp_schema.py first'"
```
Expected: prints column list including `family_id`, `customer_id`, `import_id`, `wishlist_item_id`, `status`, `expected_usd`, `unit_cost_usd`, `unit_cost_gtq`, `sale_item_id`, `jersey_id_published`.

**If this fails with `TABLE MISSING`** → STOP. The executor (or implementer manually) must run R6's `apply_imp_schema.py` first to create the `import_items` table. R2 cannot proceed without it because every promote-to-batch INSERT targets this table. Build-order rule: **R6 schema script → R2 commands**.

- [ ] **Step 8: VERIFY `inbox_events` table exists (Comercial-shipped · for sync events)**

Run:
```bash
sqlite3 C:/Users/Diego/el-club-imp/erp/elclub.db ".schema inbox_events" 2>&1 | head -5
```
Expected: prints CREATE TABLE for inbox_events. If "no such table" → the bonus inbox event INSERT in Task 6 will be skipped (graceful degradation · Diego will see it later post-R6).

---

## Task Group 1: Rust commands (yo · secuencial · lib.rs · TODOS impl_X + cmd_X split)

### Task 1: `WishlistItem` struct + helper `catalog_family_exists` + tests

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add after `read_import_by_id` at ~L2759)
- Create: `el-club-imp/overhaul/src-tauri/tests/fixtures/catalog_minimal.json`

- [ ] **Step 1: Create fixture catalog for tests**

Create `el-club-imp/overhaul/src-tauri/tests/fixtures/catalog_minimal.json`:

```json
[
  {"family_id": "ARG-2026-L-FS", "name": "Argentina 2026 Local Fan", "tier": "A"},
  {"family_id": "FRA-2026-L-FS", "name": "Francia 2026 Local Fan", "tier": "A"},
  {"family_id": "BRA-2026-L-FS", "name": "Brasil 2026 Local Fan", "tier": "B"}
]
```

- [ ] **Step 2: Add `WishlistItem` struct + helper to lib.rs**

In `el-club-imp/overhaul/src-tauri/src/lib.rs`, after `read_import_by_id` function (~L2759), add a new section block:

```rust
// ─── R2: Wishlist + Promote-to-batch ────
//
// Convention (per lib.rs:2730-2742): impl_X (pub testable) + cmd_X (#[tauri::command] shim).
// All 5 R2 commands (list/create/update/cancel/promote) follow this split.
//
// D7=B: catalog_family_exists() reads catalog.json server-side via catalog_path() (L53).
// Tests override catalog path via env var ELCLUB_CATALOG_PATH for fixture isolation.

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WishlistItem {
    pub wishlist_item_id:      i64,
    pub family_id:             String,
    pub jersey_id:             Option<String>,
    pub size:                  Option<String>,
    pub player_name:           Option<String>,
    pub player_number:         Option<i64>,
    pub patch:                 Option<String>,
    pub version:               Option<String>,
    pub customer_id:           Option<String>,
    pub expected_usd:          Option<f64>,
    pub status:                String,
    pub promoted_to_import_id: Option<String>,
    pub created_at:            String,
    pub notes:                 Option<String>,
}

/// D7=B validation: returns true if `family_id` exists in catalog.json.
/// Overridable via ELCLUB_CATALOG_PATH env var (tests use fixtures).
fn catalog_family_exists(family_id: &str) -> Result<bool> {
    let path = std::env::var("ELCLUB_CATALOG_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| catalog_path());

    if !path.exists() {
        return Err(ErpError::Other(format!(
            "catalog.json not found at {:?} · cannot validate family_id (D7=B)",
            path
        )));
    }

    let raw = std::fs::read_to_string(&path).map_err(|e| {
        ErpError::Other(format!("failed reading catalog.json: {}", e))
    })?;
    let catalog: serde_json::Value = serde_json::from_str(&raw).map_err(|e| {
        ErpError::Other(format!("invalid catalog.json: {}", e))
    })?;

    let families = catalog.as_array().ok_or_else(|| {
        ErpError::Other("catalog.json root not an array".into())
    })?;

    Ok(families.iter().any(|f| {
        f.get("family_id")
            .and_then(|v| v.as_str())
            .map(|s| s == family_id)
            .unwrap_or(false)
    }))
}

/// Re-reads canonical WishlistItem row by id. Used post-tx by impl_X commands.
fn read_wishlist_item_by_id(conn: &rusqlite::Connection, wishlist_item_id: i64) -> Result<WishlistItem> {
    conn.query_row(
        "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                created_at, notes
         FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![wishlist_item_id],
        |row| Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        }),
    ).map_err(ErpError::from)
}
```

- [ ] **Step 3: Add inline test for `catalog_family_exists`**

Append to existing test module at end of `lib.rs`:

```rust
#[cfg(test)]
mod imp_r2_helper_tests {
    use super::*;

    fn fixture_path() -> std::path::PathBuf {
        let mut p = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        p.push("tests/fixtures/catalog_minimal.json");
        p
    }

    #[test]
    fn test_catalog_family_exists_known() {
        std::env::set_var("ELCLUB_CATALOG_PATH", fixture_path());
        assert!(catalog_family_exists("ARG-2026-L-FS").unwrap());
        assert!(catalog_family_exists("FRA-2026-L-FS").unwrap());
    }

    #[test]
    fn test_catalog_family_exists_unknown() {
        std::env::set_var("ELCLUB_CATALOG_PATH", fixture_path());
        assert!(!catalog_family_exists("FAKE-XXXX-X-XX").unwrap());
        assert!(!catalog_family_exists("").unwrap());
    }

    #[test]
    fn test_catalog_family_exists_missing_file() {
        std::env::set_var("ELCLUB_CATALOG_PATH", "/nonexistent/path.json");
        let result = catalog_family_exists("ARG-2026-L-FS");
        assert!(result.is_err());
        assert!(format!("{:?}", result.unwrap_err()).contains("not found"));
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test imp_r2_helper_tests 2>&1 | tail -10
```
Expected: PASS · `3 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src-tauri/src/lib.rs \
  overhaul/src-tauri/tests/fixtures/catalog_minimal.json && \
  git commit -m "feat(imp-r2): WishlistItem struct + catalog_family_exists helper (D7=B)

- WishlistItem struct mirrors import_wishlist schema (14 cols)
- read_wishlist_item_by_id helper (re-read post-tx)
- catalog_family_exists: server-side D7=B validation against catalog.json
- ELCLUB_CATALOG_PATH env override for fixture-based tests
- 3 inline tests: known/unknown family_id + missing file"
```

---

### Task 2: `cmd_list_wishlist` (smoke-only · simple SELECT with status filter)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add struct + impl + cmd**

Append to lib.rs after Task 1 additions:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListWishlistInput {
    pub status: Option<String>,  // 'active' | 'promoted' | 'cancelled' | None (all)
}

/// List wishlist items, optionally filtered by status. Default: all items, ordered by created_at DESC.
pub async fn impl_list_wishlist(input: ListWishlistInput) -> Result<Vec<WishlistItem>> {
    let conn = open_db()?;
    let (sql, params): (&str, Vec<Box<dyn rusqlite::ToSql>>) = match input.status.as_deref() {
        Some(s) if !s.is_empty() => (
            "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                    patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                    created_at, notes
             FROM import_wishlist WHERE status = ?1
             ORDER BY created_at DESC, wishlist_item_id DESC",
            vec![Box::new(s.to_string())],
        ),
        _ => (
            "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                    patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                    created_at, notes
             FROM import_wishlist
             ORDER BY created_at DESC, wishlist_item_id DESC",
            vec![],
        ),
    };

    let mut stmt = conn.prepare(sql)?;
    let param_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let rows = stmt.query_map(&param_refs[..], |row| {
        Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        })
    })?;

    let mut items = Vec::new();
    for r in rows {
        items.push(r?);
    }
    Ok(items)
}

#[tauri::command]
async fn cmd_list_wishlist(input: ListWishlistInput) -> Result<Vec<WishlistItem>> {
    impl_list_wishlist(input).await
}
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r2): cmd_list_wishlist (status filter optional · ORDER BY created_at DESC)

- impl_list_wishlist + cmd_list_wishlist (convention split)
- Status filter ('active' | 'promoted' | 'cancelled' | None=all)
- Smoke-only (read-only · validated end-to-end via UI smoke later)"
```

---

### Task 3: `cmd_create_wishlist_item` (TDD light · D7=B server-side)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r2_create_wishlist_test.rs`

- [ ] **Step 1: Write failing integration test**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r2_create_wishlist_test.rs`:

```rust
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
```

- [ ] **Step 2: Run test to verify it fails (compile error)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_create_wishlist_test 2>&1 | tail -15
```
Expected: FAIL with `cannot find type 'CreateWishlistItemInput'` AND/OR `cannot find function 'impl_create_wishlist_item'`.

- [ ] **Step 3: Implement struct + command in lib.rs**

Append after `cmd_list_wishlist`:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateWishlistItemInput {
    pub family_id:     String,
    pub jersey_id:     Option<String>,
    pub size:          Option<String>,
    pub player_name:   Option<String>,
    pub player_number: Option<i64>,
    pub patch:         Option<String>,
    pub version:       Option<String>,
    pub customer_id:   Option<String>,
    pub expected_usd:  Option<f64>,
    pub notes:         Option<String>,
}

/// D7=B: family_id must exist in catalog.json. Validates server-side before INSERT.
pub async fn impl_create_wishlist_item(input: CreateWishlistItemInput) -> Result<WishlistItem> {
    if input.family_id.trim().is_empty() {
        return Err(ErpError::Other("family_id is required".into()));
    }

    // D7=B validation
    if !catalog_family_exists(&input.family_id)? {
        return Err(ErpError::Other(format!(
            "family_id '{}' not in catalog (D7=B) · audit/scrape it first via Vault",
            input.family_id
        )));
    }

    // Validate version if provided
    if let Some(v) = &input.version {
        if !["fan", "fan-w", "player"].contains(&v.as_str()) {
            return Err(ErpError::Other(format!(
                "version must be one of: fan, fan-w, player (got '{}')",
                v
            )));
        }
    }

    // Validate expected_usd if provided
    if let Some(usd) = input.expected_usd {
        if usd < 0.0 {
            return Err(ErpError::Other("expected_usd cannot be negative".into()));
        }
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    tx.execute(
        "INSERT INTO import_wishlist
         (family_id, jersey_id, size, player_name, player_number, patch, version,
          customer_id, expected_usd, status, notes)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'active', ?10)",
        rusqlite::params![
            input.family_id,
            input.jersey_id,
            input.size,
            input.player_name,
            input.player_number,
            input.patch,
            input.version,
            input.customer_id,
            input.expected_usd,
            input.notes,
        ],
    )?;

    let new_id = tx.last_insert_rowid();
    tx.commit()?;

    read_wishlist_item_by_id(&conn, new_id)
}

#[tauri::command]
async fn cmd_create_wishlist_item(input: CreateWishlistItemInput) -> Result<WishlistItem> {
    impl_create_wishlist_item(input).await
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_create_wishlist_test 2>&1 | tail -10
```
Expected: PASS · `3 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src-tauri/src/lib.rs \
  overhaul/src-tauri/tests/imp_r2_create_wishlist_test.rs && \
  git commit -m "feat(imp-r2): cmd_create_wishlist_item (D7=B server-side · 3 TDD cases)

- CreateWishlistItemInput struct (camelCase serde)
- D7=B: validates family_id against catalog.json before INSERT
- Validates version in {fan, fan-w, player}
- Validates expected_usd >= 0 if provided
- Status defaults to 'active'
- 3 TDD cases: happy path · unknown family rejected · empty family rejected"
```

---

### Task 4: `cmd_update_wishlist_item` (smoke-only · COALESCE pattern · status guard)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement struct + command**

Append after `cmd_create_wishlist_item`:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateWishlistItemInput {
    pub wishlist_item_id: i64,
    pub size:             Option<String>,
    pub player_name:      Option<String>,
    pub player_number:    Option<i64>,
    pub patch:            Option<String>,
    pub version:          Option<String>,
    pub customer_id:      Option<String>,
    pub expected_usd:     Option<f64>,
    pub notes:            Option<String>,
    // Note: family_id NOT editable post-create (would require re-validation + status implications)
}

/// Edit a wishlist item. Status guard: only 'active' items can be edited.
pub async fn impl_update_wishlist_item(input: UpdateWishlistItemInput) -> Result<WishlistItem> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![input.wishlist_item_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ErpError::NotFound(format!("Wishlist item {}", input.wishlist_item_id))
        }
        other => other.into(),
    })?;

    if status != "active" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot update wishlist item with status '{}' (only 'active' is editable)",
            status
        )));
    }

    if let Some(v) = &input.version {
        if !["fan", "fan-w", "player"].contains(&v.as_str()) {
            tx.rollback()?;
            return Err(ErpError::Other(format!(
                "version must be one of: fan, fan-w, player (got '{}')",
                v
            )));
        }
    }
    if let Some(usd) = input.expected_usd {
        if usd < 0.0 {
            tx.rollback()?;
            return Err(ErpError::Other("expected_usd cannot be negative".into()));
        }
    }

    tx.execute(
        "UPDATE import_wishlist
         SET size          = COALESCE(?1, size),
             player_name   = COALESCE(?2, player_name),
             player_number = COALESCE(?3, player_number),
             patch         = COALESCE(?4, patch),
             version       = COALESCE(?5, version),
             customer_id   = COALESCE(?6, customer_id),
             expected_usd  = COALESCE(?7, expected_usd),
             notes         = COALESCE(?8, notes)
         WHERE wishlist_item_id = ?9",
        rusqlite::params![
            input.size,
            input.player_name,
            input.player_number,
            input.patch,
            input.version,
            input.customer_id,
            input.expected_usd,
            input.notes,
            input.wishlist_item_id,
        ],
    )?;

    tx.commit()?;

    read_wishlist_item_by_id(&conn, input.wishlist_item_id)
}

#[tauri::command]
async fn cmd_update_wishlist_item(input: UpdateWishlistItemInput) -> Result<WishlistItem> {
    impl_update_wishlist_item(input).await
}
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r2): cmd_update_wishlist_item (COALESCE pattern · active-only guard)

- UpdateWishlistItemInput struct
- Status guard: only 'active' items can be edited (promoted/cancelled are immutable)
- family_id NOT editable post-create (would invalidate D7=B + status semantics)
- COALESCE pattern: only updates fields explicitly provided
- Re-validates version + expected_usd if changed
- Smoke-only (low-risk CRUD)"
```

---

### Task 5: `cmd_cancel_wishlist_item` (smoke-only · soft delete · idempotent)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement command**

Append after `cmd_update_wishlist_item`:

```rust
/// Soft-delete a wishlist item by setting status='cancelled'.
/// Idempotent: cancelling already-cancelled is OK.
/// Cannot cancel a 'promoted' item (would orphan the linked import row).
pub async fn impl_cancel_wishlist_item(wishlist_item_id: i64) -> Result<WishlistItem> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![wishlist_item_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ErpError::NotFound(format!("Wishlist item {}", wishlist_item_id))
        }
        other => other.into(),
    })?;

    if status == "promoted" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot cancel wishlist item already promoted to a batch (use the batch's cancel flow)"
        )));
    }

    if status != "cancelled" {
        tx.execute(
            "UPDATE import_wishlist SET status = 'cancelled' WHERE wishlist_item_id = ?1",
            rusqlite::params![wishlist_item_id],
        )?;
    }

    tx.commit()?;

    read_wishlist_item_by_id(&conn, wishlist_item_id)
}

#[tauri::command]
async fn cmd_cancel_wishlist_item(wishlist_item_id: i64) -> Result<WishlistItem> {
    impl_cancel_wishlist_item(wishlist_item_id).await
}
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r2): cmd_cancel_wishlist_item (soft delete · idempotent · promoted-guard)

- Sets status='cancelled' (soft delete, preserves history)
- Idempotent: cancelling already-cancelled returns OK
- Rejects cancelling 'promoted' items (would orphan linked import)
- NotFound error if wishlist_item_id doesn't exist"
```

---

### Task 6: `cmd_promote_wishlist_to_batch` (TDD MANDATORY · transactional · CORE COMMAND)

This is the most critical command of R2 — it bridges Wishlist → Imports → **`import_items`** (single destination table · created by R6) in one atomic tx. Bonus: INSERTs an `import_promoted` row into `inbox_events` (table verified in production).

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r2_promote_wishlist_test.rs`

- [ ] **Step 1: Write failing integration test (happy path + 5 edge cases)**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r2_promote_wishlist_test.rs`:

```rust
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
          event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
          kind         TEXT NOT NULL,
          payload_json TEXT,
          created_at   TEXT DEFAULT (datetime('now', 'localtime')),
          read_at      TEXT
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

    // BONUS: verify inbox_events row created
    let event_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM inbox_events WHERE kind='import_promoted'",
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
```

- [ ] **Step 2: Run tests to verify they fail (compile errors)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_promote_wishlist_test 2>&1 | tail -15
```
Expected: FAIL with `cannot find type 'PromoteWishlistInput'` and/or `cannot find function 'impl_promote_wishlist_to_batch'`.

- [ ] **Step 3: Implement struct + command in lib.rs**

Append after `cmd_cancel_wishlist_item`:

```rust
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PromoteWishlistInput {
    pub wishlist_item_ids: Vec<i64>,
    pub import_id:         String,
    pub status:            String,            // 'paid' (default UI · paid_at required) or 'draft' (paid_at optional)
    pub paid_at:           Option<String>,    // required iff status='paid'
    pub supplier:          Option<String>,
    pub bruto_usd:         f64,               // sum of expected_usd OR manual override (must be > 0)
    pub fx:                f64,
    pub notes:             Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PromoteWishlistResult {
    pub import:             Import,
    pub import_items_count: i64,
}

/// Promote a set of wishlist items to a new import.
///
/// DESTINATION (Diego decision 2026-04-28 ~19:00 · supersedes earlier split):
/// - ALL items go into single table `import_items` (created by R6 apply_imp_schema.py)
/// - customer_id nullable column distinguishes: NULL = stock-future · NOT NULL = assigned
/// - Status defaults to 'pending' on insert (will become 'arrived' on close_import in R4)
/// - sale_item_id and jersey_id_published populated later by Comercial / Inventario flows (v0.5+)
///
/// REASON for single-table redesign: peer review found the earlier split (sale_items vs jerseys)
/// inejecutable due to schema constraints — sale_items.sale_id NOT NULL · sale_items.customer_id
/// doesn't exist · jerseys CHECK constraints (variant in {home,away,third,special}) incompatible.
///
/// STATUS handling (Diego decision 2026-04-28 ~18:30):
/// - Default UI: status='paid' + paid_at=today (Diego pays supplier the moment he promotes most of the time)
/// - Toggle OFF: status='draft' + paid_at=NULL (rare · queue without committing to payment yet)
/// - After 'paid', Diego can manually call `cmd_mark_in_transit` (paid → in_transit) before arrival.
///
/// EVENTS (peer review 2026-04-28 ~19:00): inbox_events table EXISTS in production (Comercial-shipped).
/// We INSERT a synchronous "import_promoted" row inside the same tx · graceful degradation if the
/// table is missing (logged, not raised). Time-based events (wishlist > 20 · assigned > 30d) need
/// cron infrastructure → deferred to post-R6.
///
/// Atomic: either all items get linked + import created + wishlist rows updated + event logged, or nothing.
///
/// Validations:
/// - At least 1 wishlist_item_id provided
/// - import_id format valid (IMP-YYYY-MM-DD)
/// - import_id does not already exist
/// - status in {'paid', 'draft'}
/// - if status='paid' → paid_at REQUIRED (YYYY-MM-DD)
/// - if status='draft' → paid_at can be None
/// - All wishlist items exist AND status='active'
/// - bruto_usd > 0 · fx > 0
///
/// On success:
/// - Inserts imports row (status=input.status, bruto_usd=input.bruto_usd, n_units=count)
/// - Inserts N rows into import_items (one per promoted wishlist item, status='pending')
/// - Updates wishlist rows (status='promoted', promoted_to_import_id=new_id)
/// - Inserts 1 row into inbox_events (kind='import_promoted', payload_json=summary) · best-effort
pub async fn impl_promote_wishlist_to_batch(input: PromoteWishlistInput) -> Result<PromoteWishlistResult> {
    // Validations BEFORE opening tx
    if input.wishlist_item_ids.is_empty() {
        return Err(ErpError::Other("must select at least 1 wishlist item to promote".into()));
    }
    if !is_valid_import_id(&input.import_id) {
        return Err(ErpError::Other(format!(
            "import_id format inválido: '{}' · esperado IMP-YYYY-MM-DD",
            input.import_id
        )));
    }
    if !["paid", "draft"].contains(&input.status.as_str()) {
        return Err(ErpError::Other(format!(
            "status must be 'paid' or 'draft' · got '{}'",
            input.status
        )));
    }
    if input.status == "paid" {
        match &input.paid_at {
            None => return Err(ErpError::Other(
                "paid_at required when status='paid' (Diego confirmed default toggle ON)".into()
            )),
            Some(d) if chrono::NaiveDate::parse_from_str(d, "%Y-%m-%d").is_err() => {
                return Err(ErpError::Other(format!(
                    "paid_at format inválido: '{}' · esperado YYYY-MM-DD",
                    d
                )));
            }
            _ => {}
        }
    }
    if let Some(d) = &input.paid_at {
        // Even when status='draft', if user provided paid_at it must parse
        if chrono::NaiveDate::parse_from_str(d, "%Y-%m-%d").is_err() {
            return Err(ErpError::Other(format!(
                "paid_at format inválido: '{}' · esperado YYYY-MM-DD",
                d
            )));
        }
    }
    if input.fx <= 0.0 {
        return Err(ErpError::Other(format!("fx must be > 0 · got {}", input.fx)));
    }
    if input.bruto_usd <= 0.0 {
        return Err(ErpError::Other(format!("bruto_usd must be > 0 · got {}", input.bruto_usd)));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // Duplicate import_id guard
    let import_exists: bool = tx.query_row(
        "SELECT EXISTS(SELECT 1 FROM imports WHERE import_id = ?1)",
        rusqlite::params![&input.import_id],
        |row| row.get::<_, i64>(0).map(|n| n != 0),
    )?;
    if import_exists {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "Import {} already exists · choose a different import_id",
            input.import_id
        )));
    }

    // Fetch all wishlist items in one query (Vec<WishlistItem>)
    // Build placeholders for IN clause
    let placeholders: String = (0..input.wishlist_item_ids.len())
        .map(|i| format!("?{}", i + 1))
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                created_at, notes
         FROM import_wishlist
         WHERE wishlist_item_id IN ({})",
        placeholders
    );
    let mut stmt = tx.prepare(&sql)?;
    let params_vec: Vec<Box<dyn rusqlite::ToSql>> = input
        .wishlist_item_ids
        .iter()
        .map(|id| Box::new(*id) as Box<dyn rusqlite::ToSql>)
        .collect();
    let param_refs: Vec<&dyn rusqlite::ToSql> = params_vec.iter().map(|b| b.as_ref()).collect();
    let rows = stmt.query_map(&param_refs[..], |row| {
        Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        })
    })?;

    let mut items: Vec<WishlistItem> = Vec::new();
    for r in rows {
        items.push(r?);
    }
    drop(stmt);

    // Verify ALL requested IDs were found
    if items.len() != input.wishlist_item_ids.len() {
        let found_ids: std::collections::HashSet<i64> =
            items.iter().map(|i| i.wishlist_item_id).collect();
        let missing: Vec<i64> = input
            .wishlist_item_ids
            .iter()
            .filter(|id| !found_ids.contains(id))
            .copied()
            .collect();
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "wishlist items not found: {:?}",
            missing
        )));
    }

    // Verify ALL items have status='active'
    let non_active: Vec<(i64, String)> = items
        .iter()
        .filter(|i| i.status != "active")
        .map(|i| (i.wishlist_item_id, i.status.clone()))
        .collect();
    if !non_active.is_empty() {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot promote items not active: {:?} (only 'active' items can be promoted)",
            non_active
        )));
    }

    // Compute aggregate stats
    let n_units: i64 = items.len() as i64;
    let supplier = input
        .supplier
        .as_ref()
        .filter(|s| !s.trim().is_empty())
        .cloned()
        .unwrap_or_else(|| "Bond Soccer Jersey".to_string());
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    // INSERT imports row · status + bruto_usd come from input (Diego decision: default 'paid', toggle for 'draft')
    tx.execute(
        "INSERT INTO imports
         (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, notes, created_at, carrier)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'DHL')",
        rusqlite::params![
            input.import_id,
            input.paid_at,             // Option<String> — NULL if status='draft' and toggle OFF
            supplier,
            input.bruto_usd,
            input.fx,
            n_units,
            input.status,              // 'paid' or 'draft'
            input.notes,
            now,
        ],
    )?;

    // INSERT all items into single destination table import_items (Diego decision 2026-04-28 ~19:00):
    // - Single table for ALL promoted items (assigned + stock-future)
    // - customer_id nullable column distinguishes them (NULL = stock-future · NOT NULL = assigned)
    // - status='pending' on insert · close_import (R4) flips to 'arrived' + sets unit_cost_usd/gtq
    // - sale_item_id and jersey_id_published get populated by Comercial / Inventario flows later
    let mut import_items_count: i64 = 0;
    for item in &items {
        tx.execute(
            "INSERT INTO import_items
             (import_id, wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
              patch, version, customer_id, expected_usd, status, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 'pending', ?12)",
            rusqlite::params![
                input.import_id,
                item.wishlist_item_id,
                item.family_id,
                item.jersey_id,
                item.size,
                item.player_name,
                item.player_number,
                item.patch,
                item.version,
                item.customer_id,        // nullable: NULL = stock-future · NOT NULL = assigned
                item.expected_usd,
                item.notes,
            ],
        )?;
        import_items_count += 1;

        // UPDATE wishlist row · status='promoted' · promoted_to_import_id=new_id
        tx.execute(
            "UPDATE import_wishlist
             SET status = 'promoted',
                 promoted_to_import_id = ?1
             WHERE wishlist_item_id = ?2",
            rusqlite::params![input.import_id, item.wishlist_item_id],
        )?;
    }

    // BONUS: log inbox_events row (kind='import_promoted'). Best-effort: if the table doesn't exist
    // (older deployment), we silently skip rather than failing the entire promote.
    let event_payload = serde_json::json!({
        "kind":      "import_promoted",
        "import_id": &input.import_id,
        "n_items":   import_items_count,
        "supplier":  &supplier,
        "status":    &input.status,
    }).to_string();
    let _ = tx.execute(
        "INSERT INTO inbox_events (kind, payload_json) VALUES ('import_promoted', ?1)",
        rusqlite::params![event_payload],
    ); // intentionally swallow error — graceful degradation if inbox_events missing

    tx.commit()?;

    // Re-read canonical Import using same connection
    let import = read_import_by_id(&conn, &input.import_id)?;

    Ok(PromoteWishlistResult {
        import,
        import_items_count,
    })
}

#[tauri::command]
async fn cmd_promote_wishlist_to_batch(input: PromoteWishlistInput) -> Result<PromoteWishlistResult> {
    impl_promote_wishlist_to_batch(input).await
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_promote_wishlist_test 2>&1 | tail -15
```
Expected: PASS · `9 passed` (happy mixed → import_items + inbox_events · draft+null paid_at · paid without paid_at rejected · empty · invalid id · duplicate · already promoted · cancelled · nonexistent · negative bruto_usd).

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src-tauri/src/lib.rs \
  overhaul/src-tauri/tests/imp_r2_promote_wishlist_test.rs && \
  git commit -m "feat(imp-r2): cmd_promote_wishlist_to_batch (transactional · single import_items table · 9 TDD cases)

- PromoteWishlistInput (status + paid_at:Option<String> + bruto_usd + notes) + PromoteWishlistResult structs
- Status default UI='paid' (toggle ON · paid_at=today required) or 'draft' (paid_at NULL OK)
- Transactional: wishlist + imports + import_items + inbox_events in single tx (atomic rollback)
- DESTINATION (Diego decision 2026-04-28 ~19:00): single table import_items for ALL promoted items
  · customer_id nullable column distinguishes stock-future (NULL) from assigned (NOT NULL)
  · supersedes earlier sale_items/jerseys split (peer review found schema constraints incompatible)
  · table created by R6 apply_imp_schema.py (R2 ASSUMES it exists · pre-flight verifies)
- Validations BEFORE tx: non-empty · import_id format · status in {paid,draft} · paid_at required iff status=paid · fx > 0 · bruto_usd > 0
- Validations IN tx: import_id duplicate · all items exist · all items 'active'
- Creates imports row (status from input · bruto_usd from input · n_units=count · DHL default)
- import_items rows created with status='pending' (R4 close_import flips to 'arrived' + sets unit_cost)
- Updates wishlist rows (status='promoted' · promoted_to_import_id=new_id)
- BONUS: inbox_events row inserted synchronously (kind='import_promoted') · graceful degradation if table missing
- 10 TDD cases: happy mixed (3 items + verify import_items + inbox_events) · draft+null · paid+missing-paid_at · empty · invalid id · duplicate · already promoted · cancelled · nonexistent · negative bruto_usd"
```

---

### Task 7: `cmd_mark_in_transit` (state guard · paid → in_transit · light TDD)

Diego wants to manually mark an import as `in_transit` (when supplier confirms shipment) BEFORE arrival. Closes the gap between `cmd_promote_wishlist_to_batch` (creates 'paid') and `cmd_register_arrival` (which currently accepts paid OR in_transit).

State machine (full): `draft → paid → in_transit → arrived → closed`. `cancelled` available from any active state.

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r2_mark_in_transit_test.rs`

- [ ] **Step 1: Write failing integration test**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r2_mark_in_transit_test.rs`:

```rust
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
```

- [ ] **Step 2: Run tests to verify failure (compile error)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_mark_in_transit_test 2>&1 | tail -15
```
Expected: FAIL with `cannot find function 'impl_mark_in_transit'`.

- [ ] **Step 3: Implement command in lib.rs**

Append after `cmd_promote_wishlist_to_batch` (and BEFORE the generate_handler! wire task):

```rust
/// Mark an import as in_transit (state guard: only allowed from 'paid').
/// Optional `tracking_code` overwrites existing only if Some (COALESCE semantics).
///
/// State machine (full): draft → paid → in_transit → arrived → closed
/// (cancelled available from any active state via cmd_cancel_import).
///
/// Diego decision (2026-04-28): "después del paid puedo manualmente marcar in_transit
/// cuando el chino confirme el envío, antes que registre arrival."
pub async fn impl_mark_in_transit(
    import_id: String,
    tracking_code: Option<String>,
) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // 1. Fetch current status (assert exists)
    let current_status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    // 2. State guard: only 'paid' → 'in_transit' allowed
    if current_status != "paid" {
        tx.rollback()?;
        if current_status == "in_transit" {
            return Err(ErpError::Other(format!(
                "Import {} is already in_transit · this is a one-way state transition",
                import_id
            )));
        }
        return Err(ErpError::Other(format!(
            "Import {} has status '{}' · must be 'paid' to mark in_transit (state machine: draft → paid → in_transit → arrived → closed)",
            import_id, current_status
        )));
    }

    // 3. UPDATE — COALESCE preserves existing tracking_code if input is None
    tx.execute(
        "UPDATE imports
         SET status = 'in_transit',
             tracking_code = COALESCE(?1, tracking_code)
         WHERE import_id = ?2",
        rusqlite::params![tracking_code, import_id],
    )?;

    tx.commit()?;

    // 4. Re-read canonical Import
    read_import_by_id(&conn, &import_id)
}

#[tauri::command]
async fn cmd_mark_in_transit(
    import_id: String,
    tracking_code: Option<String>,
) -> Result<Import> {
    impl_mark_in_transit(import_id, tracking_code).await
}
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r2_mark_in_transit_test 2>&1 | tail -10
```
Expected: PASS · `4 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src-tauri/src/lib.rs \
  overhaul/src-tauri/tests/imp_r2_mark_in_transit_test.rs && \
  git commit -m "feat(imp-r2): cmd_mark_in_transit (paid → in_transit state guard · 4 TDD cases)

- impl_mark_in_transit + cmd_mark_in_transit (convention split)
- State guard: only allowed from status='paid' (rejects draft, in_transit, arrived, closed)
- tracking_code Optional · COALESCE preserves existing if None
- Closes the gap: promote('paid') → mark_in_transit → register_arrival (Diego decision 2026-04-28)
- 4 TDD cases: happy from paid · rejected from draft · rejected from in_transit · COALESCE preservation"
```

---

### Task 8: Wire `tauri::generate_handler!` macro for 6 new commands

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Locate generate_handler! and add 6 new commands**

In lib.rs, locate the `generate_handler!` macro invocation (post-R1.5 it includes `cmd_create_import`, `cmd_register_arrival`, `cmd_update_import`, `cmd_cancel_import`, `cmd_export_imports_csv`). Add the 6 R2 commands AFTER `cmd_export_imports_csv`:

```rust
.invoke_handler(tauri::generate_handler![
    // ... existing commands incl R1.5 ...
    cmd_export_imports_csv,
    // R2 additions (Wishlist + Promote-to-batch + state machine)
    cmd_list_wishlist,
    cmd_create_wishlist_item,
    cmd_update_wishlist_item,
    cmd_cancel_wishlist_item,
    cmd_promote_wishlist_to_batch,
    cmd_mark_in_transit,
    // ... rest of existing commands ...
])
```

- [ ] **Step 2: Verify cargo check + full test suite**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && \
  cargo test 2>&1 | tail -15
```
Expected: `Finished` · all R1.5 + R2 tests pass.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r2): wire 6 R2 commands to generate_handler!"
```

---

## Task Group 2: Adapter wires (yo · secuencial)

### Task 9: Adapter types (`types.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`
- Create: `el-club-imp/overhaul/src/lib/data/wishlist.ts`

- [ ] **Step 1: Create `wishlist.ts` data module**

Create `el-club-imp/overhaul/src/lib/data/wishlist.ts`:

```typescript
// Mirror of Rust WishlistItem struct (lib.rs · R2 section)
export interface WishlistItem {
  wishlist_item_id:      number;
  family_id:             string;
  jersey_id:             string | null;
  size:                  string | null;
  player_name:           string | null;
  player_number:         number | null;
  patch:                 string | null;
  version:               string | null;
  customer_id:           string | null;
  expected_usd:          number | null;
  status:                'active' | 'promoted' | 'cancelled';
  promoted_to_import_id: string | null;
  created_at:            string;
  notes:                 string | null;
}

export const WISHLIST_TARGET_SIZE = 20; // D-Settings default per spec sec 4.6

export function statusLabel(status: WishlistItem['status']): string {
  switch (status) {
    case 'active':    return '● ACTIVE';
    case 'promoted':  return '● PROMOTED';
    case 'cancelled': return '● CANCELLED';
  }
}

export function isAssigned(item: WishlistItem): boolean {
  return item.customer_id !== null && item.customer_id !== '';
}
```

- [ ] **Step 2: Add inputs + Adapter method signatures to `types.ts`**

Locate the import-related section of `types.ts` (post-R1.5 it has `CreateImportInput`, `RegisterArrivalInput`, `UpdateImportInput` near L332). After the existing R1.5 inputs, add:

```typescript
// ─── R2: Wishlist ───
import type { WishlistItem } from '$lib/data/wishlist';

export interface ListWishlistInput {
  status?: 'active' | 'promoted' | 'cancelled';  // omitted = all
}

export interface CreateWishlistItemInput {
  familyId:      string;          // D7=B: must exist in catalog.json
  jerseyId?:     string;
  size?:         string;
  playerName?:   string;
  playerNumber?: number;
  patch?:        string;          // 'WC' | 'Champions' | undefined
  version?:      'fan' | 'fan-w' | 'player';
  customerId?:   string;
  expectedUsd?:  number;          // >= 0
  notes?:        string;
}

export interface UpdateWishlistItemInput {
  wishlistItemId: number;
  size?:          string;
  playerName?:    string;
  playerNumber?:  number;
  patch?:         string;
  version?:       'fan' | 'fan-w' | 'player';
  customerId?:    string;
  expectedUsd?:   number;
  notes?:         string;
  // Note: familyId NOT editable post-create
}

export interface PromoteWishlistInput {
  wishlistItemIds: number[];      // length >= 1
  importId:        string;        // regex IMP-YYYY-MM-DD enforced server-side
  status:          'paid' | 'draft';  // Diego decision 2026-04-28: default UI = 'paid'
  paidAt?:         string;        // YYYY-MM-DD · REQUIRED iff status='paid'
  supplier?:       string;        // default 'Bond Soccer Jersey' if empty
  brutoUsd:        number;        // > 0 · sum of expected_usd OR manual override
  fx:              number;        // > 0 · default 7.73 cliente
  notes?:          string;
}

export interface PromoteWishlistResult {
  import:            Import;
  importItemsCount:  number;       // count of import_items rows inserted (= wishlistItemIds.length)
}
```

In the `Adapter` interface, add 6 method signatures:

```typescript
export interface Adapter {
  // ... existing methods incl R1.5 ...
  exportImportsCsv(): Promise<string>;

  // R2 additions
  listWishlist(input: ListWishlistInput): Promise<WishlistItem[]>;
  createWishlistItem(input: CreateWishlistItemInput): Promise<WishlistItem>;
  updateWishlistItem(input: UpdateWishlistItemInput): Promise<WishlistItem>;
  cancelWishlistItem(wishlistItemId: number): Promise<WishlistItem>;
  promoteWishlistToBatch(input: PromoteWishlistInput): Promise<PromoteWishlistResult>;
  markInTransit(importId: string, trackingCode?: string): Promise<Import>;
}
```

- [ ] **Step 3: Verify TypeScript types compile (will error in tauri/browser until next tasks)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: errors only in `tauri.ts` and `browser.ts` (missing impls) · types.ts itself is clean.

- [ ] **Step 4: DON'T commit yet** — types alone broken without impls. Commit at end of Task 10.

---

### Task 10: Adapter Tauri implementation (`tauri.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Add 5 invocations**

Locate `exportImportsCsv` method (post-R1.5). After it, add:

```typescript
async listWishlist(input: ListWishlistInput): Promise<WishlistItem[]> {
  return await invoke<WishlistItem[]>('cmd_list_wishlist', { input });
}

async createWishlistItem(input: CreateWishlistItemInput): Promise<WishlistItem> {
  return await invoke<WishlistItem>('cmd_create_wishlist_item', { input });
}

async updateWishlistItem(input: UpdateWishlistItemInput): Promise<WishlistItem> {
  return await invoke<WishlistItem>('cmd_update_wishlist_item', { input });
}

async cancelWishlistItem(wishlistItemId: number): Promise<WishlistItem> {
  return await invoke<WishlistItem>('cmd_cancel_wishlist_item', { wishlistItemId });
}

async promoteWishlistToBatch(input: PromoteWishlistInput): Promise<PromoteWishlistResult> {
  return await invoke<PromoteWishlistResult>('cmd_promote_wishlist_to_batch', { input });
}

async markInTransit(importId: string, trackingCode?: string): Promise<Import> {
  return await invoke<Import>('cmd_mark_in_transit', { importId, trackingCode });
}
```

Also add imports at top of `tauri.ts`:

```typescript
import type {
  // ... existing imports ...
  ListWishlistInput,
  CreateWishlistItemInput,
  UpdateWishlistItemInput,
  PromoteWishlistInput,
  PromoteWishlistResult,
} from './types';
import type { WishlistItem } from '$lib/data/wishlist';
```

- [ ] **Step 2: Verify**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors in `tauri.ts` (browser.ts still errors).

- [ ] **Step 3: DON'T commit yet** — finish browser.ts.

---

### Task 11: Adapter Browser stubs (`browser.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 5 NotAvailableInBrowser stubs**

After `exportImportsCsv` stub (post-R1.5), add:

```typescript
async listWishlist(_input: ListWishlistInput): Promise<WishlistItem[]> {
  throw new Error('listWishlist requires Tauri runtime · run via .exe MSI');
}

async createWishlistItem(_input: CreateWishlistItemInput): Promise<WishlistItem> {
  throw new Error('createWishlistItem requires Tauri runtime · run via .exe MSI');
}

async updateWishlistItem(_input: UpdateWishlistItemInput): Promise<WishlistItem> {
  throw new Error('updateWishlistItem requires Tauri runtime · run via .exe MSI');
}

async cancelWishlistItem(_wishlistItemId: number): Promise<WishlistItem> {
  throw new Error('cancelWishlistItem requires Tauri runtime · run via .exe MSI');
}

async promoteWishlistToBatch(_input: PromoteWishlistInput): Promise<PromoteWishlistResult> {
  throw new Error('promoteWishlistToBatch requires Tauri runtime · run via .exe MSI');
}

async markInTransit(_importId: string, _trackingCode?: string): Promise<Import> {
  throw new Error('markInTransit requires Tauri runtime · run via .exe MSI');
}
```

Add imports at top:

```typescript
import type {
  // ... existing imports ...
  ListWishlistInput,
  CreateWishlistItemInput,
  UpdateWishlistItemInput,
  PromoteWishlistInput,
  PromoteWishlistResult,
} from './types';
import type { WishlistItem } from '$lib/data/wishlist';
```

- [ ] **Step 2: Verify full check passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors total.

- [ ] **Step 3: Commit adapter group**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src/lib/data/wishlist.ts \
  overhaul/src/lib/adapter/types.ts \
  overhaul/src/lib/adapter/tauri.ts \
  overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r2): adapter wires for 6 R2 commands (wishlist + mark_in_transit)

- data/wishlist.ts: WishlistItem interface (mirror of Rust struct) + helpers (statusLabel, isAssigned, WISHLIST_TARGET_SIZE)
- types.ts: 4 input interfaces + PromoteWishlistResult + 6 Adapter signatures
  · PromoteWishlistInput now includes status:'paid'|'draft' + paidAt:string? (Diego decision 2026-04-28)
  · markInTransit(importId, trackingCode?) — new state-machine command
- tauri.ts: invoke() for each command
- browser.ts: NotAvailableInBrowser stubs (require .exe MSI)"
```

---

## Task Group 3: Svelte components (yo o subagent · 1 component por commit)

### Task 12: `WishlistItemModal.svelte` (form 9 fields · D7=B feedback)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/WishlistItemModal.svelte`

- [ ] **Step 1: Create modal**

Create `el-club-imp/overhaul/src/lib/components/importaciones/WishlistItemModal.svelte`:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { WishlistItem } from '$lib/data/wishlist';

  interface Props {
    open: boolean;
    mode: 'create' | 'edit';
    item: WishlistItem | null;     // null when mode='create'
    onClose: () => void;
    onSaved: (item: WishlistItem) => void;
  }

  let { open, mode, item, onClose, onSaved }: Props = $props();

  // Form state — initialized from item on open in edit mode
  let familyId = $state('');
  let jerseyId = $state('');
  let size = $state('');
  let playerName = $state('');
  let playerNumber = $state<number | null>(null);
  let patch = $state('');
  let version = $state<'' | 'fan' | 'fan-w' | 'player'>('');
  let customerId = $state('');
  let expectedUsd = $state<number | null>(null);
  let notes = $state('');

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Self-clean on close (R1.5 modal pattern)
  $effect(() => {
    if (!open) {
      reset();
    } else if (mode === 'edit' && item) {
      familyId = item.family_id;
      jerseyId = item.jersey_id ?? '';
      size = item.size ?? '';
      playerName = item.player_name ?? '';
      playerNumber = item.player_number;
      patch = item.patch ?? '';
      version = (item.version as typeof version) ?? '';
      customerId = item.customer_id ?? '';
      expectedUsd = item.expected_usd;
      notes = item.notes ?? '';
    }
  });

  // Loose family_id pattern check (server enforces D7=B authoritatively)
  // Pattern matches catalog SKU format: e.g. ARG-2026-L-FS, FRA-2026-L-FS
  const familyIdPattern = /^[A-Z]{2,5}-\d{4}-[A-Z]-[A-Z]{1,3}$/;
  let familyIdLooksValid = $derived(familyIdPattern.test(familyId.trim()));

  let canSubmit = $derived(
    familyId.trim().length > 0 &&
    (expectedUsd === null || expectedUsd >= 0) &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      let saved: WishlistItem;
      if (mode === 'create') {
        saved = await adapter.createWishlistItem({
          familyId: familyId.trim(),
          jerseyId: jerseyId.trim() || undefined,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      } else {
        if (!item) throw new Error('edit mode requires item prop');
        saved = await adapter.updateWishlistItem({
          wishlistItemId: item.wishlist_item_id,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      }
      onSaved(saved);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    familyId = '';
    jerseyId = '';
    size = '';
    playerName = '';
    playerNumber = null;
    patch = '';
    version = '';
    customerId = '';
    expectedUsd = null;
    notes = '';
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[480px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">
        {mode === 'create' ? '+ Nuevo wishlist item' : 'Editar wishlist item'}
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        D7=B · SKU debe existir en catalog.json
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- Family ID (D7=B validated server-side) -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Family ID (SKU) *
          </label>
          <input
            type="text"
            bind:value={familyId}
            placeholder="ARG-2026-L-FS"
            disabled={mode === 'edit' || submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            class:border-[var(--color-warning)]={familyId.length > 0 && !familyIdLooksValid}
            class:border-[var(--color-border)]={familyId.length === 0 || familyIdLooksValid}
          />
          {#if mode === 'create' && familyId.length > 0 && !familyIdLooksValid}
            <p class="text-[10.5px] text-[var(--color-warning)] mt-1">⚠️ Patrón inusual · servidor validará contra catalog.json</p>
          {/if}
          {#if mode === 'edit'}
            <p class="text-[10.5px] text-[var(--color-text-tertiary)] mt-1">family_id no editable post-create</p>
          {/if}
        </div>

        <!-- Player name + number -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Player name</label>
            <input type="text" bind:value={playerName} placeholder="Messi" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Number</label>
            <input type="number" bind:value={playerNumber} placeholder="10" min="0" max="99" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Size + Version -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Size</label>
            <select bind:value={size} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">—</option>
              <option value="S">S</option>
              <option value="M">M</option>
              <option value="L">L</option>
              <option value="XL">XL</option>
              <option value="XXL">XXL</option>
            </select>
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Version</label>
            <select bind:value={version} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">—</option>
              <option value="fan">fan</option>
              <option value="fan-w">fan-w</option>
              <option value="player">player</option>
            </select>
          </div>
        </div>

        <!-- Patch + Expected USD -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Patch</label>
            <select bind:value={patch} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">— sin patch</option>
              <option value="WC">WC (World Cup)</option>
              <option value="Champions">Champions</option>
            </select>
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Expected USD</label>
            <input type="number" bind:value={expectedUsd} placeholder="15.00" step="0.01" min="0" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Customer + Jersey ID -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Customer ID</label>
            <input type="text" bind:value={customerId} placeholder="cust-xyz (vacío = stock)" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Jersey ID (variant)</label>
            <input type="text" bind:value={jerseyId} placeholder="opcional" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes</label>
          <textarea bind:value={notes} rows="2" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Guardando...' : (mode === 'create' ? '+ Crear item' : '💾 Guardar')}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify svelte-check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/WishlistItemModal.svelte && \
  git commit -m "feat(imp-r2): WishlistItemModal · create + edit modes · D7=B feedback inline

- 9 fields: family_id (locked in edit) · player_name/number · size · version · patch · expected_usd · customer_id · jersey_id · notes
- Server-side D7=B authoritative · client shows loose pattern warning
- Edit mode pre-populates from item prop · self-clean on close
- Modal pattern: ESC + click-outside dismiss · disabled during submitting · error banner with ⚠️"
```

---

### Task 13: `PromoteToBatchModal.svelte` (form + checkbox list of items + status toggle)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/PromoteToBatchModal.svelte`

- [ ] **Step 1: Create modal**

Create `el-club-imp/overhaul/src/lib/components/importaciones/PromoteToBatchModal.svelte`:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { WishlistItem } from '$lib/data/wishlist';
  import type { PromoteWishlistResult } from '$lib/adapter/types';

  interface Props {
    open: boolean;
    activeItems: WishlistItem[];   // pre-filtered status='active' items
    onClose: () => void;
    onPromoted: (result: PromoteWishlistResult) => void;
  }

  let { open, activeItems, onClose, onPromoted }: Props = $props();

  // Form state
  let importId = $state('');
  let alreadyPaid = $state(true);                                          // Diego decision: toggle ON by default
  let paidAt = $state(new Date().toISOString().slice(0, 10));
  let supplier = $state('Bond Soccer Jersey');
  let fx = $state(7.73);
  let selectedIds = $state<Set<number>>(new Set());

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Derived status from toggle (Diego decision 2026-04-28)
  let importStatus = $derived(alreadyPaid ? 'paid' : 'draft');

  // Self-clean on close (R1.5 modal pattern)
  $effect(() => {
    if (!open) {
      reset();
    } else {
      // Default: select all active items
      selectedIds = new Set(activeItems.map(i => i.wishlist_item_id));
    }
  });

  // Client-side regex enforcement (server is authoritative)
  const idPattern = /^IMP-\d{4}-\d{2}-\d{2}$/;
  let idValid = $derived(idPattern.test(importId));

  let selectedItems = $derived(activeItems.filter(i => selectedIds.has(i.wishlist_item_id)));
  let assignedCount = $derived(selectedItems.filter(i => i.customer_id).length);
  let stockCount = $derived(selectedItems.filter(i => !i.customer_id).length);
  let estimatedBrutoUsd = $derived(
    selectedItems.reduce((sum, i) => sum + (i.expected_usd ?? 0), 0)
  );
  let nUnits = $derived(selectedItems.length);

  // paid_at only required when status='paid'
  let paidAtValid = $derived(!alreadyPaid || paidAt.length === 10);

  let canSubmit = $derived(
    idValid &&
    paidAtValid &&
    fx > 0 &&
    selectedIds.size >= 1 &&
    !submitting
  );

  function toggleItem(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }

  function selectAll() {
    selectedIds = new Set(activeItems.map(i => i.wishlist_item_id));
  }

  function selectNone() {
    selectedIds = new Set();
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      const result = await adapter.promoteWishlistToBatch({
        wishlistItemIds: Array.from(selectedIds),
        importId,
        status: importStatus,                            // 'paid' or 'draft'
        paidAt: alreadyPaid ? paidAt : undefined,        // only sent when status='paid'
        supplier: supplier.trim() || undefined,
        brutoUsd: estimatedBrutoUsd,                     // sum of expected_usd of selected items
        fx,
      });
      onPromoted(result);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    importId = '';
    alreadyPaid = true;
    paidAt = new Date().toISOString().slice(0, 10);
    supplier = 'Bond Soccer Jersey';
    fx = 7.73;
    selectedIds = new Set();
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }

  function itemLabel(item: WishlistItem): string {
    const parts: string[] = [item.family_id];
    if (item.player_name) parts.push(item.player_name);
    if (item.player_number !== null) parts.push(`#${item.player_number}`);
    if (item.size) parts.push(item.size);
    if (item.patch) parts.push(item.patch);
    return parts.join(' · ');
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[600px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">↗ Promover a batch</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        Crea import + INSERTa items en import_items · marca wishlist promoted (atomic)
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
            placeholder="IMP-2026-04-30"
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

        <!-- Status toggle: "Ya pagué" (Diego decision 2026-04-28 · default ON) -->
        <div class="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px]">
          <input
            type="checkbox"
            id="alreadyPaid"
            bind:checked={alreadyPaid}
            disabled={submitting}
            class="accent-[var(--color-accent)]"
          />
          <label for="alreadyPaid" class="text-mono text-[11px] text-[var(--color-text-primary)] cursor-pointer flex-1">
            Ya pagué al proveedor
          </label>
          <span class="text-mono text-[10px] uppercase" style="letter-spacing: 0.06em;"
            class:text-[var(--color-accent)]={alreadyPaid}
            class:text-[var(--color-text-tertiary)]={!alreadyPaid}>
            {alreadyPaid ? '● status=paid' : '○ status=draft'}
          </span>
        </div>

        <!-- Paid at (only when alreadyPaid) + FX -->
        <div class="grid grid-cols-2 gap-3">
          {#if alreadyPaid}
            <div>
              <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Paid at *</label>
              <input type="date" bind:value={paidAt} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
            </div>
          {:else}
            <div class="flex items-end">
              <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">paid_at queda NULL · marcalo cuando pagues</p>
            </div>
          {/if}
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">FX (USD→GTQ) *</label>
            <input type="number" bind:value={fx} step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Supplier -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Supplier</label>
          <input type="text" bind:value={supplier} disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        <!-- Selection summary -->
        <div class="border border-[var(--color-border)] rounded-[3px] p-3 bg-[var(--color-surface-2)]">
          <div class="flex items-center justify-between mb-2">
            <span class="text-mono text-[11px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
              Items seleccionados · {nUnits} / {activeItems.length}
            </span>
            <div class="flex gap-2">
              <button type="button" onclick={selectAll} disabled={submitting} class="text-mono text-[10px] uppercase text-[var(--color-accent)] hover:underline">todos</button>
              <span class="text-[var(--color-text-tertiary)]">·</span>
              <button type="button" onclick={selectNone} disabled={submitting} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:underline">ninguno</button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 text-mono text-[11px]">
            <div>
              <span class="text-[var(--color-text-tertiary)]">N units:</span>
              <span class="text-[var(--color-text-primary)] tabular-nums ml-1">{nUnits}</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Bruto USD:</span>
              <span class="text-[var(--color-text-primary)] tabular-nums ml-1">${estimatedBrutoUsd.toFixed(2)}</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Asignados:</span>
              <span class="text-[var(--color-accent)] tabular-nums ml-1">{assignedCount}</span>
              <span class="text-[var(--color-text-tertiary)] text-[10px] ml-1">(con cliente)</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Stock-future:</span>
              <span class="text-[var(--color-accent)] tabular-nums ml-1">{stockCount}</span>
              <span class="text-[var(--color-text-tertiary)] text-[10px] ml-1">(sin cliente)</span>
            </div>
          </div>
          <p class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-2 italic">
            Todos van a import_items (single table) · customer_id distingue ambos casos
          </p>
        </div>

        <!-- Items list (scrollable) -->
        <div class="border border-[var(--color-border)] rounded-[3px] max-h-[240px] overflow-y-auto">
          {#if activeItems.length === 0}
            <p class="text-[11px] text-[var(--color-text-tertiary)] p-3 text-center">
              No hay items active en wishlist. Agregá items primero.
            </p>
          {:else}
            {#each activeItems as item (item.wishlist_item_id)}
              <label class="flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-2)] cursor-pointer border-b border-[var(--color-surface-2)] last:border-b-0">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.wishlist_item_id)}
                  onchange={() => toggleItem(item.wishlist_item_id)}
                  disabled={submitting}
                  class="accent-[var(--color-accent)]"
                />
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] flex-1">
                  {itemLabel(item)}
                </span>
                {#if item.expected_usd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums">
                    ${item.expected_usd.toFixed(2)}
                  </span>
                {/if}
                {#if item.customer_id}
                  <span class="text-mono text-[10px] text-[var(--color-accent)] uppercase" style="letter-spacing: 0.06em;">
                    {item.customer_id}
                  </span>
                {:else}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] uppercase" style="letter-spacing: 0.06em;">
                    stock
                  </span>
                {/if}
              </label>
            {/each}
          {/if}
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Promoviendo...' : `↗ Promover ${nUnits} items a ${importId || 'IMP-...'} (${importStatus})`}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify svelte-check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/PromoteToBatchModal.svelte && \
  git commit -m "feat(imp-r2): PromoteToBatchModal · status toggle + assigned/stock counts + checkbox selector

- import_id field with regex enforced client-side (server authoritative)
- 'Ya pagué' toggle (default ON · Diego decision 2026-04-28): controls status='paid' vs 'draft'
  · ON  → paid_at field shown + required (default = today)
  · OFF → paid_at hidden, sent as undefined (status='draft')
- supplier default 'Bond Soccer Jersey' · fx default 7.73
- Live counts summary: assignedCount + stockCount (todos van a single import_items table)
- Checkbox list of active items with select all/none shortcuts
- Live computed: N units + estimated bruto USD (sum of expected_usd · sent as input.brutoUsd)
- Default: all active items pre-selected on open
- Submit button text reflects target import_id + status: '↗ Promover N items a IMP-... (paid)'
- Self-clean on close · ESC + click-outside dismiss · error banner"
```

---

### Task 14: `WishlistTab.svelte` (REPLACE 6-line stub · ~280 LOC)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte`

- [ ] **Step 1: Read current stub to confirm replacement target**

Run:
```bash
cat C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte
```
Expected: ~6 lines with "Próximamente" placeholder.

- [ ] **Step 2: Replace stub with full tab implementation**

Replace the entire content of `el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte` with:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import {
    WISHLIST_TARGET_SIZE,
    isAssigned,
    type WishlistItem,
  } from '$lib/data/wishlist';
  import WishlistItemModal from '../WishlistItemModal.svelte';
  import PromoteToBatchModal from '../PromoteToBatchModal.svelte';

  interface Props {
    onPulsoRefresh: () => void;
    refreshTrigger?: number;
  }
  let { onPulsoRefresh, refreshTrigger = 0 }: Props = $props();

  // Filter state
  let statusFilter = $state<'active' | 'promoted' | 'cancelled'>('active');

  // Data
  let items = $state<WishlistItem[]>([]);
  let loading = $state(true);

  // Modal state
  let itemModalOpen = $state(false);
  let itemModalMode = $state<'create' | 'edit'>('create');
  let itemModalTarget = $state<WishlistItem | null>(null);

  let promoteModalOpen = $state(false);

  onMount(load);

  // Re-fetch when parent bumps the trigger or filter changes
  $effect(() => {
    if (refreshTrigger > 0) {
      load();
    }
  });

  $effect(() => {
    // Re-load when statusFilter changes
    statusFilter;
    load();
  });

  async function load() {
    loading = true;
    try {
      items = await adapter.listWishlist({ status: statusFilter });
    } finally {
      loading = false;
    }
  }

  // Derived sections (only when status='active')
  let assignedItems = $derived(items.filter(isAssigned));
  let stockItems = $derived(items.filter(i => !isAssigned(i)));
  let activeCount = $derived(statusFilter === 'active' ? items.length : 0);

  function openCreate() {
    itemModalMode = 'create';
    itemModalTarget = null;
    itemModalOpen = true;
  }

  function openEdit(item: WishlistItem) {
    itemModalMode = 'edit';
    itemModalTarget = item;
    itemModalOpen = true;
  }

  async function handleCancelItem(item: WishlistItem) {
    const confirmed = confirm(`¿Quitar "${item.family_id}${item.player_name ? ' · ' + item.player_name : ''}" del wishlist?`);
    if (!confirmed) return;
    try {
      await adapter.cancelWishlistItem(item.wishlist_item_id);
      await load();
      onPulsoRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  function openPromote() {
    if (assignedItems.length + stockItems.length === 0) return;
    promoteModalOpen = true;
  }

  async function handleItemSaved() {
    await load();
    onPulsoRefresh();
  }

  function handlePromoted(result: { import: { import_id: string }; importItemsCount: number }) {
    // Switch to status='active' filter so user can see remaining items
    statusFilter = 'active';
    load();
    onPulsoRefresh();
    alert(`✅ ${result.importItemsCount} items promovidos a ${result.import.import_id}\n\nVer el batch en tab Pedidos.`);
  }

  function rowLabel(item: WishlistItem): string {
    const parts: string[] = [];
    if (item.player_name) parts.push(item.player_name);
    if (item.player_number !== null) parts.push(`#${item.player_number}`);
    if (item.patch) parts.push(item.patch);
    if (item.version) parts.push(item.version);
    if (item.size) parts.push(item.size);
    return parts.join(' · ') || '—';
  }
</script>

<div class="flex flex-col flex-1 min-h-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)]">
    <div class="flex items-center gap-3">
      <h2 class="text-mono text-[11px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.08em;">
        Wishlist {statusFilter}
      </h2>
      <span class="text-mono text-[11px] text-[var(--color-text-primary)] tabular-nums">
        {items.length} {statusFilter === 'active' ? `/ ${WISHLIST_TARGET_SIZE} target` : ''}
      </span>
      {#if statusFilter === 'active' && items.length >= WISHLIST_TARGET_SIZE}
        <span class="text-mono text-[10px] uppercase text-[var(--color-warning)] bg-[rgba(245,165,36,0.15)] border border-[rgba(245,165,36,0.3)] px-2 py-0.5 rounded-[3px]" style="letter-spacing: 0.06em;">
          ● HORA DE CONSOLIDAR BATCH
        </span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <!-- Status filter chips -->
      <div class="flex gap-1">
        {#each ['active', 'promoted', 'cancelled'] as s (s)}
          <button
            class="text-mono text-[10px] uppercase px-2 py-1 rounded-[3px] border"
            class:bg-[var(--color-accent)]={statusFilter === s}
            class:text-[var(--color-bg)]={statusFilter === s}
            class:border-[var(--color-accent)]={statusFilter === s}
            class:bg-transparent={statusFilter !== s}
            class:text-[var(--color-text-tertiary)]={statusFilter !== s}
            class:border-[var(--color-border)]={statusFilter !== s}
            style="letter-spacing: 0.06em;"
            onclick={() => statusFilter = s as typeof statusFilter}
          >
            {s}
          </button>
        {/each}
      </div>
      <button
        onclick={openCreate}
        class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]"
      >
        + Nuevo item
      </button>
      <button
        onclick={openPromote}
        disabled={statusFilter !== 'active' || activeCount === 0}
        title={statusFilter !== 'active' ? 'Solo items active pueden promoverse' : (activeCount === 0 ? 'Sin items activos' : 'Promover items active a un nuevo batch')}
        class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] font-semibold"
        class:bg-[var(--color-accent)]={statusFilter === 'active' && activeCount > 0}
        class:text-[var(--color-bg)]={statusFilter === 'active' && activeCount > 0}
        class:bg-[var(--color-surface-2)]={statusFilter !== 'active' || activeCount === 0}
        class:text-[var(--color-text-tertiary)]={statusFilter !== 'active' || activeCount === 0}
        class:cursor-not-allowed={statusFilter !== 'active' || activeCount === 0}
      >
        ↗ Promover a batch
      </button>
    </div>
  </div>

  <!-- Body -->
  <div class="flex-1 overflow-y-auto p-4">
    {#if loading}
      <div class="flex items-center justify-center text-[var(--color-text-tertiary)] py-8">
        Cargando wishlist…
      </div>
    {:else if items.length === 0}
      <div class="flex flex-col items-center justify-center text-center py-12 text-[var(--color-text-tertiary)] text-[12px]">
        {#if statusFilter === 'active'}
          <p class="mb-2">Sin pre-pedidos activos.</p>
          <p class="text-[11px]">Cuando un cliente pida algo, agregá item acá.</p>
          <p class="text-[10.5px] text-[var(--color-text-muted)] mt-3">Recordatorio: D7=B · SKU debe existir en catalog.</p>
        {:else if statusFilter === 'promoted'}
          <p>Sin items promovidos todavía.</p>
        {:else}
          <p>Sin items cancelados.</p>
        {/if}
      </div>
    {:else if statusFilter === 'active'}
      <!-- ASSIGNED section -->
      {#if assignedItems.length > 0}
        <div class="mb-6">
          <h3 class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
            [ASSIGNED · {assignedItems.length}]
          </h3>
          <div class="border border-[var(--color-border)] rounded-[3px]">
            {#each assignedItems as item (item.wishlist_item_id)}
              <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
                <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
                <span class="text-mono text-[10px] uppercase text-[var(--color-accent)] w-[100px] text-right" style="letter-spacing: 0.06em;">
                  {item.customer_id}
                </span>
                {#if item.expected_usd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums w-[60px] text-right">
                    ${item.expected_usd.toFixed(2)}
                  </span>
                {:else}
                  <span class="w-[60px]"></span>
                {/if}
                <div class="flex gap-1">
                  <button onclick={() => openEdit(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] px-2">editar</button>
                  <button onclick={() => handleCancelItem(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] px-2">quitar</button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- STOCK FUTURO section -->
      {#if stockItems.length > 0}
        <div>
          <h3 class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
            [STOCK FUTURO · {stockItems.length}]
          </h3>
          <div class="border border-[var(--color-border)] rounded-[3px]">
            {#each stockItems as item (item.wishlist_item_id)}
              <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
                <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
                <span class="w-[100px]"></span>
                {#if item.expected_usd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums w-[60px] text-right">
                    ${item.expected_usd.toFixed(2)}
                  </span>
                {:else}
                  <span class="w-[60px]"></span>
                {/if}
                <div class="flex gap-1">
                  <button onclick={() => openEdit(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] px-2">editar</button>
                  <button onclick={() => handleCancelItem(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] px-2">quitar</button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {:else}
      <!-- promoted / cancelled · simple flat list -->
      <div class="border border-[var(--color-border)] rounded-[3px]">
        {#each items as item (item.wishlist_item_id)}
          <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
            <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
            <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
            {#if item.promoted_to_import_id}
              <span class="text-mono text-[10px] uppercase text-[var(--color-accent)]" style="letter-spacing: 0.06em;">
                → {item.promoted_to_import_id}
              </span>
            {/if}
            <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">{item.created_at.slice(0, 10)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Modals -->
  <WishlistItemModal
    open={itemModalOpen}
    mode={itemModalMode}
    item={itemModalTarget}
    onClose={() => itemModalOpen = false}
    onSaved={handleItemSaved}
  />

  <PromoteToBatchModal
    open={promoteModalOpen}
    activeItems={statusFilter === 'active' ? items : []}
    onClose={() => promoteModalOpen = false}
    onPromoted={handlePromoted}
  />
</div>
```

- [ ] **Step 3: Verify svelte-check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte && \
  git commit -m "feat(imp-r2): WishlistTab · CRUD + Promote-to-batch UI (replaces stub)

- Header: status filter chips (active/promoted/cancelled) + N/target counter + warning when >= target
- Action toolbar: + Nuevo item · ↗ Promover a batch (disabled if !active or empty)
- Body sections (active filter only): [ASSIGNED · N] + [STOCK FUTURO · N] split by isAssigned()
- Per row: family_id mono · player spec · customer (if assigned) · expected_usd · [editar][quitar]
- Empty states per spec sec 8 (D7=B reminder included)
- Modals: WishlistItemModal (create/edit) + PromoteToBatchModal
- onPulsoRefresh wires to parent for KPI refresh"
```

---

### Task 15: `MarkInTransitModal.svelte` (confirm + optional tracking_code)

Tiny confirm-style modal for the new `cmd_mark_in_transit` flow. Diego clicks "Marcar en tránsito" from the Detail toolbar (Task 16) and gets this modal — optional tracking_code input + confirm button.

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/MarkInTransitModal.svelte`

- [ ] **Step 1: Create modal**

Create `el-club-imp/overhaul/src/lib/components/importaciones/MarkInTransitModal.svelte`:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/adapter/types';

  interface Props {
    open: boolean;
    importId: string;          // current import being marked
    currentTrackingCode: string | null;
    onClose: () => void;
    onMarked: (updated: Import) => void;
  }

  let { open, importId, currentTrackingCode, onClose, onMarked }: Props = $props();

  let trackingCode = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  $effect(() => {
    if (!open) {
      reset();
    } else {
      trackingCode = currentTrackingCode ?? '';
    }
  });

  async function handleConfirm() {
    submitting = true;
    errorMsg = null;
    try {
      const updated = await adapter.markInTransit(
        importId,
        trackingCode.trim() || undefined,
      );
      onMarked(updated);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    trackingCode = '';
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">→ Marcar en tránsito</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {importId} · status: paid → in_transit
      </p>

      <p class="text-[12px] text-[var(--color-text-secondary)] mb-3">
        El proveedor confirmó envío. Marcá este import como <span class="text-mono text-[var(--color-accent)]">in_transit</span>. Después podés registrar la llegada con "Registrar arrival".
      </p>

      <div class="mb-3">
        <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
          Tracking code (opcional)
        </label>
        <input
          type="text"
          bind:value={trackingCode}
          placeholder="DHL-XXXXX (opcional)"
          disabled={submitting}
          class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]"
        />
        {#if currentTrackingCode}
          <p class="text-[10.5px] text-[var(--color-text-tertiary)] mt-1">
            Actual: <span class="text-mono">{currentTrackingCode}</span> · vacío preserva el actual (COALESCE)
          </p>
        {/if}
      </div>

      {#if errorMsg}
        <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2 mb-3">
          ⚠️ {errorMsg}
        </div>
      {/if}

      <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
        <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
          Cancelar
        </button>
        <button type="button" onclick={handleConfirm} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold bg-[var(--color-accent)] text-[var(--color-bg)]">
          {submitting ? '⏳ Marcando...' : '→ Confirmar in_transit'}
        </button>
      </div>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Verify svelte-check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/MarkInTransitModal.svelte && \
  git commit -m "feat(imp-r2): MarkInTransitModal · confirm + optional tracking_code

- Triggered from ImportDetailHead toolbar when status='paid'
- Optional tracking_code input · COALESCE preserves existing if empty
- Self-clean on close · ESC + click-outside dismiss · error banner
- Wires to adapter.markInTransit() → cmd_mark_in_transit (paid → in_transit guard)"
```

---

### Task 16: Wire "Marcar en tránsito" button in ImportDetailHead toolbar

Add a new action button in the Detail toolbar that's visible when `imp.status === 'paid'`. Clicking it opens `MarkInTransitModal` (Task 15).

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailHead.svelte`

- [ ] **Step 1: Inspect current toolbar to find insertion point**

Run:
```bash
grep -n "Registrar arrival\|status\|toolbar\|action" C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportDetailHead.svelte | head -20
```
Expected: locate where "Registrar arrival" button is rendered conditionally on `imp.status`.

- [ ] **Step 2: Add MarkInTransit button + modal wiring**

In `ImportDetailHead.svelte`, add the import + state:

```svelte
<script lang="ts">
  // ... existing imports ...
  import MarkInTransitModal from './MarkInTransitModal.svelte';

  // ... existing props ...

  // R2 addition
  let markInTransitModalOpen = $state(false);

  function handleInTransitMarked(updated: Import) {
    // Trigger parent refresh (mirrors handleArrivalRegistered pattern)
    onRefresh?.();
  }
</script>
```

Add the new button alongside "Registrar arrival" (visible only when `imp.status === 'paid'`):

```svelte
{#if imp.status === 'paid'}
  <button
    onclick={() => markInTransitModalOpen = true}
    class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]"
    title="Proveedor confirmó envío · marcar como in_transit"
  >
    → Marcar en tránsito
  </button>
{/if}

<!-- ... existing 'Registrar arrival' button (which already accepts paid OR in_transit) ... -->
```

Add the modal at the end of the template (alongside any existing modals):

```svelte
<MarkInTransitModal
  open={markInTransitModalOpen}
  importId={imp.import_id}
  currentTrackingCode={imp.tracking_code}
  onClose={() => markInTransitModalOpen = false}
  onMarked={handleInTransitMarked}
/>
```

- [ ] **Step 3: Verify svelte-check + build**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/ImportDetailHead.svelte && \
  git commit -m "feat(imp-r2): ImportDetailHead · add 'Marcar en tránsito' button (paid status)

- Visible only when imp.status === 'paid'
- Opens MarkInTransitModal on click
- Triggers onRefresh after mark to update detail header pill + parent list
- Sits alongside 'Registrar arrival' (which still works for both paid + in_transit per R1.5 logic)"
```

---

## Task Group 4: Wire-up + integration (yo · secuencial)

### Task 17: Wire WishlistTab into ImportShell + ImportTabs (refreshTrigger plumbing)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte`
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte` (only if needed)

- [ ] **Step 1: Read current ImportShell + ImportTabs to assess wiring**

Run:
```bash
wc -l C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte \
       C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte && \
  grep -n "PedidosTab\|WishlistTab\|refreshTrigger" \
       C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte \
       C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte
```
Expected: see how PedidosTab is currently wired with `refreshTrigger` and `onPulsoRefresh`. Mirror the same wiring for WishlistTab.

- [ ] **Step 2: Update ImportShell.svelte** to pass `refreshTrigger` to WishlistTab and bump it on promote-to-batch

In `ImportShell.svelte`, locate where `PedidosTab` is rendered conditionally (e.g., `{#if activeTab === 'pedidos'}`). Add (or update existing) the WishlistTab rendering. The pattern (mirrors PedidosTab wiring):

```svelte
<script lang="ts">
  // ... existing imports + state ...

  // refreshTrigger bumped when wishlist items change OR promote creates a new import
  let pedidosRefreshTrigger = $state(0);
  let wishlistRefreshTrigger = $state(0);

  function handlePulsoRefresh() {
    // Existing pulso refresh logic
    pulsoRefreshTrigger++;
    // When wishlist promotes to batch, both Pedidos AND Wishlist need re-fetch
    pedidosRefreshTrigger++;
    wishlistRefreshTrigger++;
  }
</script>

<!-- ... -->

{#if activeTab === 'wishlist'}
  <WishlistTab
    refreshTrigger={wishlistRefreshTrigger}
    onPulsoRefresh={handlePulsoRefresh}
  />
{/if}
```

Add the import at the top of ImportShell.svelte:

```svelte
import WishlistTab from './tabs/WishlistTab.svelte';
```

- [ ] **Step 3: Verify ImportTabs.svelte already has 'wishlist' tab definition**

Run:
```bash
grep -n "wishlist" C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte
```
Expected: existing reference (the tab was created as a stub in R1). If missing, add it. If present, no change needed.

- [ ] **Step 4: Verify svelte-check + build**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
Expected: 0 errors check · build OK.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add \
  overhaul/src/lib/components/importaciones/ImportShell.svelte \
  overhaul/src/lib/components/importaciones/ImportTabs.svelte && \
  git commit -m "feat(imp-r2): wire WishlistTab into ImportShell · refreshTrigger plumbing

- WishlistTab receives refreshTrigger prop (bumped on promote-to-batch)
- Promote-to-batch bumps BOTH pedidosRefreshTrigger + wishlistRefreshTrigger (cross-tab refresh)
- Pulso bar refreshes via existing onPulsoRefresh callback (will reflect new wishlist count + new import)"
```

---

## Task Group 5: Smoke test + final verification

### Task 18: Smoke test SQL script

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r2.py`

- [ ] **Step 1: Create smoke script**

Create `el-club-imp/erp/scripts/smoke_imp_r2.py`:

```python
#!/usr/bin/env python3
"""
Smoke test post-implementation IMP-R2
Exercises wishlist CRUD + promote-to-batch via direct DB ops.
Verifies state in worktree DB (ERP_DB_PATH).

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r2.py
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

    SMOKE_IMPORT_ID = 'IMP-2026-04-30'

    # Pre-flight: verify import_items table exists (R6 schema dependency)
    has_import_items = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='import_items'"
    ).fetchone()
    assert has_import_items, 'import_items table missing — run R6 apply_imp_schema.py first'

    # Cleanup any prior smoke runs
    cur.execute("DELETE FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%'")
    cur.execute("DELETE FROM inbox_events WHERE kind='import_promoted' AND payload_json LIKE ?", (f'%{SMOKE_IMPORT_ID}%',))
    conn.commit()

    print('\n=== TEST 1: Create 5 wishlist items (3 assigned · 2 stock-future) ===')
    family_ids = ['ARG-2026-L-FS', 'FRA-2026-L-FS', 'BRA-2026-L-FS', 'ARG-2026-L-FS', 'FRA-2026-L-FS']
    expected_usds = [15.0, 15.0, 11.0, 13.0, 13.0]
    customers = ['cust-pedro', 'cust-andres', None, None, 'cust-juan']  # items 3+4 = stock-future
    for i, (fid, usd, cust) in enumerate(zip(family_ids, expected_usds, customers)):
        cur.execute("""
            INSERT INTO import_wishlist (family_id, size, expected_usd, customer_id, status, notes)
            VALUES (?, ?, ?, ?, 'active', ?)
        """, (fid, 'L', usd, cust, f'SMOKE-R2-{i+1}'))
    conn.commit()

    smoke_ids = [r[0] for r in cur.execute(
        "SELECT wishlist_item_id FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%' ORDER BY wishlist_item_id"
    ).fetchall()]
    assert_eq(len(smoke_ids), 5, '5 wishlist items inserted')

    print('\n=== TEST 2: Promote 3 mixed items (status=paid · single import_items destination) ===')
    # Promote items 1 (assigned), 2 (assigned), 3 (stock-future) → 3 rows in import_items
    promote_ids = smoke_ids[:3]
    bruto_usd_expected = sum(expected_usds[:3])  # 15+15+11=41

    # Simulate promote-to-batch transaction (Diego decisions 2026-04-28: status='paid' default + single table)
    cur.execute("BEGIN")
    try:
        # Insert imports row · status='paid' (Diego Q1 default toggle ON)
        cur.execute("""
            INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at, carrier)
            VALUES (?, '2026-04-30', 'Bond Soccer Jersey', ?, 7.73, 3, 'paid', datetime('now', 'localtime'), 'DHL')
        """, (SMOKE_IMPORT_ID, bruto_usd_expected))

        # SINGLE TABLE destination (Diego Q2 SUPERSEDED 2026-04-28 ~19:00):
        # All items go to import_items · customer_id nullable distinguishes assigned vs stock-future.
        for wl_id in promote_ids:
            wl = cur.execute("SELECT * FROM import_wishlist WHERE wishlist_item_id = ?", (wl_id,)).fetchone()
            cur.execute("""
                INSERT INTO import_items
                  (import_id, wishlist_item_id, family_id, size, customer_id, expected_usd, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 'SMOKE-R2-item')
            """, (SMOKE_IMPORT_ID, wl_id, wl['family_id'], wl['size'], wl['customer_id'], wl['expected_usd']))
            cur.execute("UPDATE import_wishlist SET status='promoted', promoted_to_import_id=? WHERE wishlist_item_id=?",
                        (SMOKE_IMPORT_ID, wl_id))

        # Inbox event (Q3 RESOLVED 2026-04-28 ~19:00 · table verified in production)
        cur.execute("""
            INSERT INTO inbox_events (kind, payload_json)
            VALUES ('import_promoted', ?)
        """, (f'{{"import_id":"{SMOKE_IMPORT_ID}","n_items":3,"supplier":"Bond Soccer Jersey","status":"paid"}}',))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise

    print('\n=== TEST 3: Verify imports row created (status=paid) ===')
    imp = cur.execute("SELECT * FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()
    assert imp is not None, 'imports row not created'
    assert_eq(imp['status'], 'paid', 'imports.status (Diego default · toggle ON)')
    assert_eq(imp['paid_at'], '2026-04-30', 'imports.paid_at populated when status=paid')
    assert_eq(imp['n_units'], 3, 'imports.n_units')
    assert_eq(round(imp['bruto_usd'], 2), 41.0, 'imports.bruto_usd (input · NOT computed)')
    assert_eq(imp['fx'], 7.73, 'imports.fx')
    assert_eq(imp['supplier'], 'Bond Soccer Jersey', 'imports.supplier')

    print('\n=== TEST 4: Verify SINGLE TABLE — import_items rows ===')
    items_count = cur.execute("SELECT COUNT(*) FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(items_count, 3, 'import_items count (all 3 promoted items, single destination)')

    assigned_count = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND customer_id IS NOT NULL", (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    stock_count = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND customer_id IS NULL", (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    assert_eq(assigned_count, 2, 'assigned items (customer_id NOT NULL · items 1+2)')
    assert_eq(stock_count, 1, 'stock-future items (customer_id IS NULL · item 3)')

    pedro = cur.execute("SELECT * FROM import_items WHERE customer_id='cust-pedro' AND import_id=?", (SMOKE_IMPORT_ID,)).fetchone()
    assert pedro is not None, 'cust-pedro import_items row exists'
    assert_eq(pedro['status'], 'pending', 'pedro item status (will become arrived in R4 close_import)')
    print(f'  [OK] cust-pedro import_items: {dict(pedro)}')

    print('\n=== TEST 5: Verify wishlist rows updated ===')
    promoted = cur.execute(
        "SELECT COUNT(*) FROM import_wishlist WHERE wishlist_item_id IN (?,?,?) AND status='promoted' AND promoted_to_import_id=?",
        (*promote_ids, SMOKE_IMPORT_ID)
    ).fetchone()[0]
    assert_eq(promoted, 3, 'wishlist rows promoted')

    still_active = cur.execute(
        "SELECT COUNT(*) FROM import_wishlist WHERE wishlist_item_id IN (?,?) AND status='active'",
        (smoke_ids[3], smoke_ids[4])
    ).fetchone()[0]
    assert_eq(still_active, 2, 'remaining 2 wishlist items still active')

    print('\n=== TEST 6: Verify inbox_events row created ===')
    has_events_table = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='inbox_events'"
    ).fetchone()
    if has_events_table:
        event_count = cur.execute(
            "SELECT COUNT(*) FROM inbox_events WHERE kind='import_promoted' AND payload_json LIKE ?",
            (f'%{SMOKE_IMPORT_ID}%',)
        ).fetchone()[0]
        assert_eq(event_count, 1, 'inbox_events row for import_promoted')
    else:
        print('  [SKIP] inbox_events table missing — graceful degradation OK')

    print('\n=== TEST 7: Verify cmd_mark_in_transit (paid → in_transit) ===')
    cur.execute("UPDATE imports SET status='in_transit', tracking_code='SMOKE-DHL-12345' WHERE import_id=? AND status='paid'", (SMOKE_IMPORT_ID,))
    conn.commit()
    transit = cur.execute("SELECT status, tracking_code FROM imports WHERE import_id=?", (SMOKE_IMPORT_ID,)).fetchone()
    assert_eq(transit['status'], 'in_transit', 'imports.status after mark_in_transit')
    assert_eq(transit['tracking_code'], 'SMOKE-DHL-12345', 'imports.tracking_code populated')

    print('\n=== TEST 8: Cross-module integrity ===')
    sales_count = cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    customers_count = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    audit_count = cur.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
    print(f'  sales:           {sales_count}')
    print(f'  customers:       {customers_count}')
    print(f'  audit_decisions: {audit_count}')

    print('\n=== Cleanup ===')
    cur.execute("DELETE FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_wishlist WHERE notes LIKE 'SMOKE-R2-%'")
    cur.execute("DELETE FROM inbox_events WHERE kind='import_promoted' AND payload_json LIKE ?", (f'%{SMOKE_IMPORT_ID}%',))
    conn.commit()

    print('\n[PASS] ALL SMOKE TESTS PASS · IMP-R2 wishlist + promote (single import_items) + inbox_events + mark_in_transit verified')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run smoke**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r2.py
```
Expected: `[PASS] ALL SMOKE TESTS PASS · IMP-R2 wishlist + promote (single import_items) + inbox_events + mark_in_transit verified`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_imp_r2.py && \
  git commit -m "test(imp-r2): SQL smoke script · CRUD + promote (single import_items table) + inbox_events + mark_in_transit + cross-module"
```

---

### Task 19: Final verification (cargo + npm + svelte + tests)

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check --release 2>&1 | tail -5
```
Expected: `Finished release [optimized] target(s)` no errors.

- [ ] **Step 2: Cargo test all R1.5 + R2 tests**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test 2>&1 | tail -25
```
Expected: all tests pass · `imp_r15_*`, `imp_r2_helper_tests`, `imp_r2_create_wishlist_test`, `imp_r2_promote_wishlist_test` (10 cases · single import_items destination), `imp_r2_mark_in_transit_test` (4 cases).

- [ ] **Step 3: npm check + build**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
Expected: 0 errors check · build OK.

- [ ] **Step 4: Run all 3 smoke scripts (R1.5 sanity + R2)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r15.py && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r2.py
```
Expected: both PASS.

---

## Self-Review

Before declaring R2 complete, run this mental checklist:

**Spec coverage (sec 4.2 Wishlist):**
- [x] Tab Wishlist con lista de items (active/promoted/cancelled filter) → Task 14 ✓
- [x] D7=B SKU validation contra catalog.json → Task 1 + 3 (server-side) ✓
- [x] Items assigned vs stock futuro split (UI) → Task 14 (assignedItems / stockItems derived) ✓
- [x] Header: "Wishlist activa · N / 20 target" → Task 14 ✓
- [x] Promover a batch botón (disabled si 0 items active) → Task 14 + 13 ✓
- [x] Edit player spec (Name/Number/Size/Patch/Version) → Task 12 ✓
- [x] Asignar a customer existente → Task 12 (customer_id field) ✓
- [x] Quitar del wishlist (soft delete) → Task 5 + 14 ✓
- [x] Promover a batch crea imports row con status='paid' default (toggle 'Ya pagué' ON) o 'draft' (OFF) → Task 6 + Task 13 ✓ **(Diego decision Q1 2026-04-28)**
- [x] Wishlist promote INSERTa todos los items en `import_items` (single table · created by R6) · customer_id nullable distingue assigned (NOT NULL) de stock-future (NULL) · status='pending' inicial → Task 6 ✓ **(Diego decision Q2 SUPERSEDED 2026-04-28 ~19:00)**
- [x] Wishlist rows status='promoted' + promoted_to_import_id → Task 6 ✓
- [x] Atomicity (transactional rollback) → Task 6 + 10 TDD cases ✓
- [x] cmd_mark_in_transit (paid → in_transit state guard) + UI button en ImportDetailHead → Task 7 + 15 + 16 ✓ **(Diego addendum 2026-04-28)**
- [x] State machine completo: draft → paid → in_transit → arrived → closed (cancelled cross-cutting) ✓
- [x] Inbox event sincrónico `import_promoted` INSERTado en `inbox_events` (table existe en producción · verified peer review) · graceful degradation si missing → Task 6 ✓ **(Q3 RESOLVED 2026-04-28 ~19:00)**
- [x] Empty state "Sin pre-pedidos. ... D7=B" → Task 14 ✓
- [x] is_valid_import_id reused → Task 6 ✓

**Spec sec 8 errors / edge cases (Wishlist):**
- [x] Wishlist promote con 0 items → bloqueado (Task 6 test + Task 14 button disabled) ✓
- [x] Wishlist promote con SKU inexistente race condition → server-side guard (D7=B en CREATE, no en promote · ya validado al insert) ✓
- [x] Empty wishlist empty state → Task 14 ✓
- [x] mark_in_transit desde estado != 'paid' → bloqueado (Task 7 TDD cases: draft + in_transit rechazados) ✓

**Inbox events partial:** spec sec 4.2 menciona 3 eventos (`wishlist > 20`, `SKU missing`, `assigned > 30d`). El primero se implementa visualmente como badge "HORA DE CONSOLIDAR BATCH" en WishlistTab header (Task 14). Adicionalmente, el evento `import_promoted` se INSERTa sincrónicamente en `inbox_events` durante el promote (Task 6). Los 2 eventos basados en cron (`wishlist > 20 evento`, `assigned > 30d`) requieren cron infrastructure → deferred a post-R6.

**Placeholder scan:** ningún `TODO` / `implement later` / `add validation` / `similar to Task N` en steps. ✓

**Type consistency:**
- `WishlistItem` Rust struct fields snake_case · serde rename camelCase for Input structs · TS interface uses snake_case fields (mirrors DB) ✓
- 6 Adapter method names match Rust commands (camelCase: `listWishlist`, `createWishlistItem`, `updateWishlistItem`, `cancelWishlistItem`, `promoteWishlistToBatch`, `markInTransit`) ✓
- Status enum values wishlist: `'active' | 'promoted' | 'cancelled'` consistent across DB CHECK constraint, Rust struct, TS interface ✓
- Status enum values imports: `'draft' | 'paid' | 'in_transit' | 'arrived' | 'closed' | 'cancelled'` ✓

**Cross-module impact (per master overview):**
- IMP (Imports): R2 creates the `import_items` row lifecycle. R6 schema script creates the table. R4 close_import will iterate import_items to set unit_cost_usd / unit_cost_gtq (D2=B prorrateo). All future modules read from import_items.
- COM (Sales · v0.5+): when a customer eventually buys an assigned-and-promoted item, the Comercial flow will (a) create the sale + sale_items row, (b) UPDATE the corresponding `import_items.sale_item_id` to link them, and (c) UPDATE `import_items.status='sold'`. R2 leaves the column nullable for this future linkage. ⚠️ Flagged below.
- INV (Inventory · post-R6): when a stock-future item enters the public catalog (gets a real jersey_id), the Inventario module will INSERT a `jerseys` row + UPDATE `import_items.jersey_id_published` + `import_items.status='published'`. R2 leaves these columns nullable. ⚠️ NEW dependency.
- FIN (cash flow): cero touch (FIN reads `imports.total_landed_gtq` only after `close_import`, which doesn't change in R2). ✓
- ADM Universe: cero touch ✓
- catalog.json: READ-only via `catalog_family_exists()` (D7=B). Zero writes. ✓
- Worker Cloudflare: cero touch ✓
- inbox_events: WRITE (1 row per promote · `kind='import_promoted'`) · graceful degradation if table missing.

**Cross-release dependencies:**
- **R6 (Schema apply)** is a HARD prerequisite for R2. The `import_items` table must exist before any R2 promote-to-batch runs. Pre-flight Task 0 verifies. Build-order: **R6 schema script → R2 commands**.
- **R3 (Margen real)** reads `import_items` for stock pendiente queries: `WHERE status='pending'` (en camino), `WHERE status='arrived' AND sale_item_id IS NULL` (recibido sin vender). Confirm R3 plan reads import_items (single source of truth) instead of attempting to JOIN sale_items + jerseys.
- **R4 (Free units / close_import)** must iterate `import_items WHERE import_id=?` and update each row: `status='arrived'`, `unit_cost_usd = bruto / N`, `unit_cost_gtq = (bruto + shipping) * fx / N` (D2=B prorrateo). Confirm R4 plan reflects this scope expansion vs the original "imports only" close.
- **Comercial Sales Attribution loop:** v0.5+ feature. When an assigned `import_items` row gets sold, Comercial UPDATE `import_items.sale_item_id`. When a stock-future row gets sold, same pattern (regardless of customer_id NULL state). Decision deferred to Comercial bucket. ⚠️ Flagged below.

---

## Open questions for Diego

These ambiguities surfaced while writing the plan. **Did NOT improvise resolutions** — escalating per starter doc rule "Si emerge ambigüedad NO en spec · pausar + ping Diego · NO improvisar."

### Q1 · Promote-to-batch status — RESOLVED 2026-04-28 ~18:30

Diego: opción **B** + addendum. Modal incluye toggle "Ya pagué" (default ON → status='paid', paid_at=today required; OFF → status='draft', paid_at NULL OK). Después del paid, Diego puede manualmente marcar in_transit via nuevo `cmd_mark_in_transit` antes de `cmd_register_arrival`.

State machine completo: draft → paid → in_transit → arrived → closed (cancelled disponible desde cualquier estado activo).

Implementación reflejada en:
- Task 6 (`cmd_promote_wishlist_to_batch`): struct `PromoteWishlistInput` lleva `status: String` + `paid_at: Option<String>`. Validación: `status='paid'` → `paid_at` requerido. Tests cubren ambos flujos.
- Task 7 (NUEVO): `cmd_mark_in_transit` con state guard (solo transición `paid → in_transit`, COALESCE preserva tracking_code existente).
- Task 13 (PromoteToBatchModal): toggle "Ya pagué" + paid_at condicional + status pill visible en submit button.
- Task 15 (NUEVO): `MarkInTransitModal.svelte` — confirm modal con tracking_code opcional.
- Task 16 (NUEVO): botón "Marcar en tránsito" en `ImportDetailHead.svelte` (visible cuando `imp.status === 'paid'`).

### Q2 · Stock-future destination — SUPERSEDED 2026-04-28 ~19:00

Decisión original (split sale_items/jerseys según customer_id) **inejecutable** por schema constraints encontrados en peer review:
- `sale_items.sale_id` es NOT NULL → no se puede insertar sin un sale real
- `sale_items.customer_id` NO existe como columna (verificado contra DB real)
- `jerseys` tiene CHECK constraints estrictos: `variant IN ('home','away','third','special')` + `status IN ('available','reserved','sold')` + `team_id NOT NULL FK` — los datos de wishlist no satisfacen estos constraints

**Diego eligió Opción 1 mejorada (final 2026-04-28 ~19:00):** nueva tabla `import_items` (creada por R6 `apply_imp_schema.py`) que recibe TODOS los items promovidos. `customer_id` nullable en la tabla distingue stock-future (NULL) de assigned (NOT NULL). El `catalog.json` sigue siendo source of truth de los datos del producto (D7=B garantiza family_id existe) — `import_items` NO duplica esos datos · solo guarda lo necesario para tracking del lote en tránsito y futura linkage a sale_items / jerseys publicados.

**Status semantics import_items:**
- `pending` = recién promovido, en camino con el proveedor
- `arrived` = batch cerrado (R4 `close_import` lo flippea + setea unit_cost), físicamente en inventario
- `sold` = vendido a cliente vía Comercial (sale_item_id populated · v0.5+)
- `published` = entró al catálogo público como jersey (jersey_id_published populated · post-R6)
- `cancelled` = anulado por Diego

**Build-order rule:** R6 schema script DEBE correr antes de R2 commands. Pre-flight Task 0 step 7 verifica.

Implementación reflejada en:
- Task 6 (`cmd_promote_wishlist_to_batch`): single loop con `INSERT INTO import_items` (sin branch · customer_id nullable column).
- Tests Task 6: 10 casos · happy path inserta 3 rows mixed (2 assigned + 1 stock-future) en single table · valida customer_id NULL/NOT NULL distinction · valida inbox_events row · negative bruto_usd guard.
- Task 13 (PromoteToBatchModal): summary block muestra counts assigned/stock + nota "todos van a import_items (single table) · customer_id distingue".
- Smoke script Task 18: actualizado para verificar 3 rows en import_items + counts por customer_id NULL/NOT NULL.

### Q3 · Inbox events de R2 — RESOLVED 2026-04-28 ~19:00

Peer review verificó que `inbox_events` table EXISTS en producción (Comercial-shipped). El deferral original tenía pretexto incorrecto ("no hay tabla").

**Decisión Diego (2026-04-28 ~19:00):** implementar el evento `import_promoted` sincrónicamente como `INSERT INTO inbox_events` dentro de la misma tx del promote · graceful degradation (swallowed error) si la tabla no existe en runtime.

Spec sec 4.2 menciona 3 Inbox events:
1. `import_promoted` (al promover) → ✅ IMPLEMENTADO en R2 (sync, en tx)
2. `wishlist > 20 items` (visual + event) → visual badge ✅ implementado en Task 14 · evento async deferred a R6 + cron
3. `wishlist item asignado > 30d` → DEFERRED a post-R6 (requiere cron infrastructure)

Implementación reflejada en:
- Task 6: `INSERT INTO inbox_events (kind='import_promoted', payload_json='{...}')` antes del commit · error swallowed.
- Smoke script TEST 6 verifica el INSERT · skips graciosamente si la tabla missing.

### Q4 · Cross-module: Comercial sales linking a import_items

Cuando un cliente eventualmente compra un item promovido vía wishlist (en Comercial v0.5+), el flujo debe **UPDATE el `import_items.sale_item_id`** (linkear a la sale recién creada) + UPDATE `import_items.status='sold'`. Esto requiere un cambio en Comercial (no en R2).

**Pregunta a Diego (still open):** ¿OK identificar este follow-up como un task post-R2 en Comercial bucket? El R2 actual NO toca Comercial · solo deja `import_items` rows con sale_item_id=NULL listos para ser linkeados cuando la sale se materialice.

---

## Execution Handoff

Plan complete and saved to `el-club-imp/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R2.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks. Best for `lib.rs` changes where I want code review per command. Especially recommended for Task 6 (promote-to-batch · core transactional command).

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach?**

If subagent-driven chosen: REQUIRED SUB-SKILL `superpowers:subagent-driven-development`.
If inline: REQUIRED SUB-SKILL `superpowers:executing-plans`.

---

## After R2 ships

1. Append commit hashes + smoke results to `SESSION-COORDINATION.md` activity log
2. **PAUSE for Wave 1 acceptance gate:** ping Diego to install MSI v0.3.5 (intermediate) and confirm acceptance criteria #1: *"¿Podés acumular pre-pedidos en Wishlist + Promote-to-batch crea import + linkea items?"*
3. If Diego signs off ✅ → arranca Wave 2 (R3, R4, R5, R6 plans + execute)
4. If Diego flags issue → fix in R2.x patch before Wave 2

**MSI v0.3.5 build (optional intermediate):**
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npx tauri build --bundles msi
# Move to archive: bundle/msi/El Club ERP_0.3.5_x64_en-US.msi
```
