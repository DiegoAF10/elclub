# IMP-R3 Implementation Plan — Margen real cross-Comercial (read-only · Wave 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. R3 is **smoke-only** (read-only queries) per master overview · NO TDD required.

**Goal:** Reemplazar el stub "Próximamente" en `MargenRealTab.svelte` con tab funcional · cards per batch closed (revenue Comercial × landed cost · margen bruto · stock pendiente · free units valor) · feed para FIN-Rx vía queries cross-table `import_items × sale_items × sales × imports`. Stock pendiente lee de `import_items WHERE status='pending'` (la nueva tabla creada por R6 que recibe los items promovidos) — fuente única, sin UNION.

**Architecture:** Solo módulo IMP · una sola tabla nueva `import_items` (creada por R6 schema script) recibe TODOS los items promovidos desde wishlist. `customer_id` nullable distingue stock-future (NULL) de assigned (populated). Resto de columnas necesarias existen post-R1: `sale_items.import_id` para revenue tracking · `sale_items.family_id` (NOT `sku`) · `sale_items.variant_label` (NOT `variant`) · `sales.total` (NOT `total_gtq`) · `imports.total_landed_gtq` + `imports.unit_cost` set por close_import_proportional D2=B · `import_free_unit` table.
- **Margen real:** lee `imports` (closed only) joined con `sale_items WHERE import_id=?` (revenue real de items vendidos via Comercial)
- **Stock pendiente:** lee `import_items WHERE import_id=? AND status='pending'` · una sola fuente · clean
- **Free units:** count desde `import_free_unit` (R4 populates)
- **D2=B prorrateo:** `imports.unit_cost` es per-unit landed cost del batch · cuando R4 close run iterará `import_items` y seteará `unit_cost_gtq` per-item · por ahora R3 usa `imports.unit_cost` como proxy para items sin prorrateo finalizado
- 3 read-only Rust commands siguen el pattern de `cmd_get_import_pulso` (lib.rs:2570) · Frontend: 1 tab replace + 1 BatchMarginCard component nuevo + filter chips inline · Cross-module flag (spec sec 11 línea 821): la query expone data que FIN-Rx consume vía `cmd_get_home_snapshot` futuro · NO se modifica FIN en R3.

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + Tauri 2 + Svelte 5 (`$state`/`$derived`/`$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · 0 deps nuevas.

---

## File Structure

### Files to create (3 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/overhaul/src/lib/components/importaciones/BatchMarginCard.svelte` | Card per batch closed · revenue/landed/margen + free units + stock pendiente · footer links |
| `el-club-imp/overhaul/src/lib/components/importaciones/MargenFilters.svelte` | Filter chips (período · supplier · include_pipeline toggle) + sort dropdown |
| `el-club-imp/erp/scripts/smoke_imp_r3.py` | Smoke SQL post-implementation · seed 1 closed import + 3 sale_items linked + 3 sales · verify queries |

### Files to modify (5 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | Agregar 3 structs Output + 3 commands (`cmd_get_margen_real`, `cmd_get_batch_margen_breakdown`, `cmd_get_margen_pulso`) + wire `generate_handler!` · stock pendiente lee de `import_items WHERE status='pending'` (R6 schema · fuente única) | +295 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | Extend Adapter · 4 output interfaces (`BatchMargenSummary`, `BatchMargenDetail`, `MargenFilter`, `MargenPulso`) + 3 method signatures | +60 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 3 invocations | +25 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 3 stub fallbacks (NotAvailableInBrowser) | +18 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte` | REPLACE 6-line stub con tab funcional · loads margen summary · renders BatchMarginCard list · filter state · refreshTrigger pattern | +180 net (replace 6 LOC stub) |

**Total estimado:** ~575 líneas net nuevas (Rust ~295 · TS ~100 · Svelte ~180). Decremento -15 LOC vs versión UNION (queries simplificadas a single-table `import_items` per Diego decisión 2026-04-28 ~19:00).

---

## Pre-flight (verify worktree state · R2 dependency)

### Task 0: Pre-flight verification

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Verify worktree branch + R2 ya shipped**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git status -sb && git log --oneline -10 | grep -E "(imp-r2|imp-r1.5)"
```
Expected: `## imp-r2-r6-build` · sin uncommitted · log muestra commits de R1.5 + R2 (R2 wishlist promote es dependency soft · pero R3 puede shippear con sale_items.import_id existente sin R2)

- [ ] **Step 2: Verify schema columns necesarias existen**

Run:
```bash
python -c "import sqlite3; conn = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); cur = conn.execute('PRAGMA table_info(sale_items)'); cols = [r[1] for r in cur.fetchall()]; print('sale_items cols:', cols); assert 'import_id' in cols, 'MISSING import_id'; assert 'unit_cost' in cols; assert 'unit_price' in cols; print('OK')"
```
Expected: lista incluye `import_id`, `unit_cost`, `unit_price`, `sale_id` · prints `OK`

- [ ] **Step 3: Verify imports table tiene total_landed_gtq + n_units + status**

Run:
```bash
python -c "import sqlite3; conn = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); cur = conn.execute('PRAGMA table_info(imports)'); cols = [r[1] for r in cur.fetchall()]; print(cols); assert 'total_landed_gtq' in cols; assert 'n_units' in cols; assert 'status' in cols; print('OK')"
```
Expected: lista incluye `total_landed_gtq`, `n_units`, `status`, `paid_at`, `arrived_at`, `supplier` · prints `OK`

- [ ] **Step 4: Verify import_free_unit table exists**

Run:
```bash
python -c "import sqlite3; conn = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); print(conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='import_free_unit'\").fetchone())"
```
Expected: `('import_free_unit',)` (creada en R1 schema migration)

- [ ] **Step 4.5: Verify import_items table exists (R6 dependency · created by apply_imp_schema.py)**

Run:
```bash
python -c "import sqlite3; cols = [c[1] for c in sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db').execute('PRAGMA table_info(import_items)').fetchall()]; assert 'family_id' in cols, 'import_items table missing — R6 apply_imp_schema.py must run first'; print('import_items cols:', cols); print('OK')"
```
Expected: lista incluye `import_item_id`, `import_id`, `wishlist_item_id`, `family_id`, `jersey_id`, `size`, `player_name`, `player_number`, `patch`, `version`, `customer_id`, `expected_usd`, `unit_cost_usd`, `unit_cost_gtq`, `status`, `sale_item_id`, `jersey_id_published`, `notes`, `created_at` · prints `OK`. **Si falla:** correr `python C:/Users/Diego/el-club-imp/erp/scripts/apply_imp_schema.py` (R6) primero.

- [ ] **Step 5: Verify existing read commands para reusar patterns**

Run:
```bash
grep -n "cmd_get_import_pulso\|cmd_list_imports\|cmd_get_import_items\|read_import_by_id" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs | head -10
```
Expected: ve los 4 helpers listados con sus líneas (~2443/2480/2515/2570/2732)

- [ ] **Step 6: Verify MargenRealTab stub actual**

Run:
```bash
wc -l C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte && cat C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte
```
Expected: ~6 lines · contenido stub "Próximamente"

---

## Task Group 1: Rust commands (yo · secuencial · lib.rs · smoke-only · no TDD)

### Task 1: Output structs `BatchMargenSummary` + `BatchMargenDetail` + `MargenFilter` + `MargenPulso`

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add structs after line ~2728 · post `cmd_close_import_proportional`)

- [ ] **Step 1: Add structs to lib.rs**

In `el-club-imp/overhaul/src-tauri/src/lib.rs`, after `read_import_by_id` helper (~line 2742) add:

```rust
// ─── R3 Margen Real: cross-Comercial queries ─────────────────────────

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MargenFilter {
    pub period_from: Option<String>,    // YYYY-MM-DD · filter on imports.paid_at >= ?
    pub period_to: Option<String>,      // YYYY-MM-DD · filter on imports.paid_at <= ?
    pub supplier: Option<String>,       // exact match on imports.supplier
    pub include_pipeline: Option<bool>, // default false · si true incluye paid+arrived con margen estimado
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchMargenSummary {
    pub import_id: String,
    pub supplier: String,
    pub paid_at: Option<String>,
    pub arrived_at: Option<String>,
    pub status: String,                 // 'closed' default · 'paid'/'arrived' si include_pipeline
    pub n_units: Option<i64>,
    pub total_landed_gtq: Option<f64>,  // null si pipeline (status != closed)
    pub n_sales_linked: i64,            // count distinct sale_id en sale_items WHERE import_id = X
    pub n_items_linked: i64,            // count sale_items WHERE import_id = X
    pub revenue_total_gtq: f64,         // SUM(sale_items.unit_price) WHERE import_id = X · production col is "total" not "total_gtq"
    pub margen_bruto_gtq: f64,          // revenue - landed (0 si landed null)
    pub margen_pct: Option<f64>,        // (margen / landed) * 100 · null si landed = 0 o null
    pub n_stock_pendiente: i64,         // count import_items WHERE import_id = X AND status = 'pending' (single source post-R6 schema)
    pub valor_stock_pendiente_gtq: f64, // SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) WHERE status='pending' · fallback to imports.unit_cost para items pre-prorrateo
    pub n_free_units: i64,              // count import_free_unit WHERE import_id = X
    pub valor_free_units_gtq: Option<f64>, // null por ahora (asignación pendiente · D-FREE valuation rule por decidir)
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LinkedSale {
    pub sale_id: String,
    pub occurred_at: Option<String>,    // production col: sales.occurred_at (NOT created_at)
    pub customer_id: Option<i64>,       // production col: sales.customer_id is INTEGER
    pub total: f64,                     // production col: sales.total (NOT total_gtq)
    pub n_items_from_batch: i64,        // count sale_items WHERE sale_id=X AND import_id=Y
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PendingItem {
    pub import_item_id: i64,
    pub family_id: String,              // production col (NOT sku)
    pub jersey_id: Option<String>,
    pub size: Option<String>,
    pub player_name: Option<String>,
    pub player_number: Option<i32>,
    pub patch: Option<String>,
    pub version: Option<String>,
    pub customer_id: Option<String>,    // NULL = stock-future · populated = assigned to specific customer
    pub expected_usd: Option<f64>,
    pub unit_cost_gtq: Option<f64>,     // null hasta que close (R4) corra prorrateo
    pub status: String,                 // 'pending' | 'arrived' | 'sold' | 'published' | 'cancelled'
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FreeUnitRow {
    pub free_unit_id: i64,
    pub destination: String,
    pub destination_ref: Option<String>,
    pub assigned_at: Option<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchMargenDetail {
    pub summary: BatchMargenSummary,
    pub linked_sales: Vec<LinkedSale>,
    pub pending_items: Vec<PendingItem>,
    pub free_units: Vec<FreeUnitRow>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MargenPulso {
    pub n_batches_closed: i64,
    pub revenue_total_ytd_gtq: f64,
    pub landed_total_ytd_gtq: f64,
    pub margen_total_ytd_gtq: f64,
    pub margen_pct_avg: Option<f64>,         // average margen_pct across closed batches
    pub best_batch_id: Option<String>,       // import_id with highest margen_pct
    pub best_batch_margen_pct: Option<f64>,
    pub worst_batch_id: Option<String>,
    pub worst_batch_margen_pct: Option<f64>,
    pub capital_amarrado_gtq: f64,           // SUM(valor_stock_pendiente) across closed batches
}
```

- [ ] **Step 2: Verify cargo check passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors (structs only · no funcs yet)

- [ ] **Step 3: Commit structs**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): add MargenFilter + BatchMargenSummary + BatchMargenDetail + MargenPulso structs

- Output types for cross-Comercial margin queries
- camelCase serde for TS adapter compat
- 6 nested types: LinkedSale (uses production cols occurred_at/total/customer_id INTEGER), PendingItem (reads import_items table · family_id NOT sku), FreeUnitRow
- include_pipeline flag (default false · closed only per spec sec 4.3)
- Stock pendiente single source: import_items WHERE status='pending' (post-R6 schema)"
```

---

### Task 2: Helper `compute_batch_summary` (shared between list + detail commands)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add helper after structs from Task 1)

Justificación: ambos `cmd_get_margen_real` y `cmd_get_batch_margen_breakdown` necesitan calcular el summary per batch. Extraer en helper evita duplicación.

- [ ] **Step 1: Add helper function**

Add after `MargenPulso` struct:

```rust
/// Compute BatchMargenSummary for a single import_id from existing DB rows.
/// Reads imports + aggregates from sale_items + import_items (R6 table) + import_free_unit.
/// Used by cmd_get_margen_real (list) and cmd_get_batch_margen_breakdown (detail).
fn compute_batch_summary(conn: &rusqlite::Connection, import_id: &str) -> Result<BatchMargenSummary> {
    // 1. Read import row (canonical fields · incl unit_cost per-unit landed for stock pendiente fallback proxy)
    let (supplier, paid_at, arrived_at, status, n_units, total_landed, unit_cost_landed): (String, Option<String>, Option<String>, String, Option<i64>, Option<f64>, Option<f64>) = conn.query_row(
        "SELECT supplier, paid_at, arrived_at, status, n_units, total_landed_gtq, unit_cost
         FROM imports WHERE import_id = ?1",
        rusqlite::params![import_id],
        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?, r.get(5)?, r.get(6)?)),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    // 2. Aggregate sales linked: count distinct sale_id, count items, SUM unit_price (revenue from Comercial)
    //    Production schema: sale_items.import_id is FK · sale_id NOT NULL (always linked to a sale row).
    //    Items "promovidos pero no vendidos" viven en import_items (NOT sale_items) post-R6.
    let (n_sales_linked, n_items_linked, revenue_total): (i64, i64, f64) = conn.query_row(
        "SELECT COUNT(DISTINCT sale_id), COUNT(*), COALESCE(SUM(unit_price), 0)
         FROM sale_items
         WHERE import_id = ?1",
        rusqlite::params![import_id],
        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
    ).unwrap_or((0, 0, 0.0));

    // 3. Stock pendiente: count import_items WHERE status='pending' (single source post-R6 schema)
    //    customer_id NULL = stock-future · customer_id populated = assigned to specific customer.
    //    Both flavors count as "pending" until promoted to actual sale (status transitions to 'sold').
    let n_pendiente: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ?1 AND status = 'pending'",
        rusqlite::params![import_id],
        |r| r.get(0),
    ).unwrap_or(0);

    // Valor stock pendiente: SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost))
    // Per-item unit_cost_gtq is set when R4 close runs prorrateo · null otherwise.
    // Fallback to imports.unit_cost (per-unit landed shared across batch · D2=B aggregate proxy).
    let valor_pendiente: f64 = conn.query_row(
        "SELECT COALESCE(SUM(COALESCE(unit_cost_gtq, ?2)), 0)
         FROM import_items WHERE import_id = ?1 AND status = 'pending'",
        rusqlite::params![import_id, unit_cost_landed.unwrap_or(0.0)],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // 4. Free units count (valor diferido · spec ambiguous)
    let n_free: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE import_id = ?1",
        rusqlite::params![import_id],
        |r| r.get(0),
    ).unwrap_or(0);

    // 5. Margen bruto + pct (only meaningful if landed exists)
    let landed = total_landed.unwrap_or(0.0);
    let margen_bruto = revenue_total - landed;
    let margen_pct = if landed > 0.0 {
        Some((margen_bruto / landed) * 100.0)
    } else {
        None
    };

    Ok(BatchMargenSummary {
        import_id: import_id.to_string(),
        supplier,
        paid_at,
        arrived_at,
        status,
        n_units,
        total_landed_gtq: total_landed,
        n_sales_linked,
        n_items_linked,
        revenue_total_gtq: revenue_total,
        margen_bruto_gtq: margen_bruto,
        margen_pct,
        n_stock_pendiente: n_pendiente,
        valor_stock_pendiente_gtq: valor_pendiente,
        n_free_units: n_free,
        valor_free_units_gtq: None, // TBD per spec ambiguity (open question for Diego)
    })
}
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors (helper compiles standalone · warning about unused OK)

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): add compute_batch_summary helper

- Reads imports (incl unit_cost per-unit landed for fallback) + aggregates from sale_items + import_items + import_free_unit
- Revenue: SUM(sale_items.unit_price) WHERE import_id (sale_items always linked to a sale row · production schema)
- Stock pendiente: SELECT FROM import_items WHERE status='pending' · single source post-R6 schema
- valor_stock_pendiente = SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) · per-item if R4 close ran, else batch fallback
- Shared between list (cmd_get_margen_real) and detail (cmd_get_batch_margen_breakdown)
- Computes margen_bruto + margen_pct (null if landed=0)
- valor_free_units_gtq deferred (D-FREE valuation rule pendiente)"
```

---

### Task 3: `cmd_get_margen_real` (list with filter · convention block split impl_X + cmd_X)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

Convention per lib.rs:2730-2742: split en `impl_get_margen_real` (pub helper sin Tauri attr) + `cmd_get_margen_real` (#[tauri::command] shim que llama impl).

- [ ] **Step 1: Add impl + cmd to lib.rs**

Add after `compute_batch_summary` helper:

```rust
/// Returns list of BatchMargenSummary filtered per MargenFilter.
/// Default: closed only (per spec sec 4.3 line 237).
/// include_pipeline=true incluye paid+arrived con margen estimado (revenue real · landed null si no closed).
pub fn impl_get_margen_real(filter: &MargenFilter) -> Result<Vec<BatchMargenSummary>> {
    let conn = open_db()?;

    // Build WHERE clause dynamically per filter
    let include_pipeline = filter.include_pipeline.unwrap_or(false);
    let status_clause = if include_pipeline {
        "status IN ('paid', 'arrived', 'closed')"
    } else {
        "status = 'closed'"
    };

    let mut sql = format!(
        "SELECT import_id FROM imports WHERE {} ", status_clause
    );
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    if let Some(pf) = &filter.period_from {
        sql.push_str("AND paid_at >= ? ");
        params.push(Box::new(pf.clone()));
    }
    if let Some(pt) = &filter.period_to {
        sql.push_str("AND paid_at <= ? ");
        params.push(Box::new(pt.clone()));
    }
    if let Some(sup) = &filter.supplier {
        sql.push_str("AND supplier = ? ");
        params.push(Box::new(sup.clone()));
    }
    sql.push_str("ORDER BY paid_at DESC NULLS LAST, import_id DESC");

    let mut stmt = conn.prepare(&sql)?;
    let param_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|p| p.as_ref() as &dyn rusqlite::ToSql).collect();
    let import_ids: Vec<String> = stmt
        .query_map(rusqlite::params_from_iter(param_refs.iter()), |r| r.get::<_, String>(0))?
        .collect::<std::result::Result<Vec<_>, _>>()?;

    let mut summaries = Vec::with_capacity(import_ids.len());
    for id in import_ids {
        // compute_batch_summary opens its own conn read · thread-safe
        summaries.push(compute_batch_summary(&conn, &id)?);
    }

    Ok(summaries)
}

#[tauri::command]
pub async fn cmd_get_margen_real(filter: MargenFilter) -> Result<Vec<BatchMargenSummary>> {
    impl_get_margen_real(&filter)
}
```

- [ ] **Step 2: Verify cargo check passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): cmd_get_margen_real (list batches con filter · closed default)

- impl_get_margen_real + cmd_get_margen_real split (per convention block lib.rs:2730)
- Filters: period_from/period_to (paid_at), supplier exact, include_pipeline opt-in
- Default 'closed' only (spec sec 4.3 line 237)
- Sorted by paid_at DESC NULLS LAST, import_id DESC
- Reuses compute_batch_summary helper"
```

---

### Task 4: `cmd_get_batch_margen_breakdown` (detail per batch · drilldown)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add impl + cmd**

Add after `cmd_get_margen_real`:

```rust
/// Returns BatchMargenDetail for a single import_id: summary + linked sales + pending items + free units.
/// Used in drilldown when Diego clicks "Ver ventas linkeadas" or "Ver items pendientes".
pub fn impl_get_batch_margen_breakdown(import_id: &str) -> Result<BatchMargenDetail> {
    let conn = open_db()?;
    let summary = compute_batch_summary(&conn, import_id)?;

    // 1. Linked sales: distinct sale_id from sale_items × sales JOIN.
    //    Production schema cols: sales.occurred_at (NOT created_at), sales.total (NOT total_gtq), sales.customer_id (INTEGER).
    let mut stmt = conn.prepare(
        "SELECT s.sale_id, s.occurred_at, s.customer_id, s.total,
                COUNT(si.item_id) AS n_items
         FROM sales s
         INNER JOIN sale_items si ON si.sale_id = s.sale_id
         WHERE si.import_id = ?1
         GROUP BY s.sale_id, s.occurred_at, s.customer_id, s.total
         ORDER BY s.occurred_at DESC"
    )?;
    let linked_sales: Vec<LinkedSale> = stmt
        .query_map(rusqlite::params![import_id], |r| Ok(LinkedSale {
            sale_id: r.get(0)?,
            occurred_at: r.get(1)?,
            customer_id: r.get(2)?,
            total: r.get(3)?,
            n_items_from_batch: r.get(4)?,
        }))?
        .collect::<std::result::Result<Vec<_>, _>>()?;

    // 2. Pending items: read from import_items WHERE status='pending' (single source post-R6 schema).
    //    customer_id NULL = stock-future · populated = assigned. Both flavors counted as pending.
    let mut stmt = conn.prepare(
        "SELECT import_item_id, family_id, jersey_id, size, player_name, player_number,
                patch, version, customer_id, expected_usd, unit_cost_gtq, status
         FROM import_items
         WHERE import_id = ?1 AND status = 'pending'
         ORDER BY import_item_id"
    )?;
    let pending_items: Vec<PendingItem> = stmt
        .query_map(rusqlite::params![import_id], |r| Ok(PendingItem {
            import_item_id: r.get(0)?,
            family_id: r.get(1)?,
            jersey_id: r.get(2)?,
            size: r.get(3)?,
            player_name: r.get(4)?,
            player_number: r.get(5)?,
            patch: r.get(6)?,
            version: r.get(7)?,
            customer_id: r.get(8)?,
            expected_usd: r.get(9)?,
            unit_cost_gtq: r.get(10)?,
            status: r.get(11)?,
        }))?
        .collect::<std::result::Result<Vec<_>, _>>()?;

    // 3. Free units rows
    let mut stmt = conn.prepare(
        "SELECT free_unit_id, destination, destination_ref, assigned_at, notes
         FROM import_free_unit
         WHERE import_id = ?1
         ORDER BY free_unit_id"
    )?;
    let free_units: Vec<FreeUnitRow> = stmt
        .query_map(rusqlite::params![import_id], |r| Ok(FreeUnitRow {
            free_unit_id: r.get(0)?,
            destination: r.get(1)?,
            destination_ref: r.get(2)?,
            assigned_at: r.get(3)?,
            notes: r.get(4)?,
        }))?
        .collect::<std::result::Result<Vec<_>, _>>()?;

    Ok(BatchMargenDetail {
        summary,
        linked_sales,
        pending_items,
        free_units,
    })
}

#[tauri::command]
pub async fn cmd_get_batch_margen_breakdown(import_id: String) -> Result<BatchMargenDetail> {
    impl_get_batch_margen_breakdown(&import_id)
}
```

**NOTA schema:** Production `sale_items` cols son `family_id` (NOT `sku`) + `variant_label` (NOT `variant`) · `sales` cols son `occurred_at` (NOT `created_at`) + `total` (NOT `total_gtq`) + `customer_id INTEGER`. Schema `import_items` creado por R6 `apply_imp_schema.py` · verificar Pre-flight Task 0 Step 4.5 antes de implementar.

- [ ] **Step 2: Verify cargo check + verify column names match production schema**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && \
  python -c "import sqlite3; conn = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); print('sale_items:', [r[1] for r in conn.execute('PRAGMA table_info(sale_items)').fetchall()]); print('sales:', [r[1] for r in conn.execute('PRAGMA table_info(sales)').fetchall()]); print('import_items:', [r[1] for r in conn.execute('PRAGMA table_info(import_items)').fetchall()])"
```
Expected: `Finished` no errors · sale_items confirma `family_id`/`variant_label` · sales confirma `occurred_at`/`total`/`customer_id` · import_items confirma `import_item_id`/`family_id`/`status`/`customer_id`/`unit_cost_gtq`

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): cmd_get_batch_margen_breakdown (drilldown per batch)

- impl + cmd split per convention block
- Returns summary + linked_sales (distinct sale_id with n_items) + pending_items (import_items table) + free_units
- linked_sales uses production cols (sales.occurred_at NOT created_at · sales.total NOT total_gtq · customer_id INTEGER)
- pending_items reads from import_items WHERE status='pending' (R6 schema · single source · NO UNION)
- 3 sub-queries (sales JOIN sale_items, import_items SELECT, import_free_unit)
- ORDER BY for stable display: sales by occurred_at DESC, items by import_item_id, free by free_unit_id"
```

---

### Task 5: `cmd_get_margen_pulso` (global aggregates · best/worst/avg)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

Esta query es global (todos los closed YTD). El existing `cmd_get_import_pulso` (lib.rs:2570) cubre KPIs operativos generales (capital amarrado, lead time, wishlist count). `cmd_get_margen_pulso` cubre las KPIs de margen específicamente para el header del MargenRealTab. Mantener separado para evitar bloat de ImportPulso struct.

- [ ] **Step 1: Add impl + cmd**

Add after `cmd_get_batch_margen_breakdown`:

```rust
/// Global aggregates of margen across closed batches YTD (current year).
/// Powers the header pulso bar of MargenRealTab.
pub fn impl_get_margen_pulso() -> Result<MargenPulso> {
    let conn = open_db()?;

    // YTD = current year (substr paid_at vs strftime year)
    let n_batches: i64 = conn.query_row(
        "SELECT COUNT(*) FROM imports
         WHERE status = 'closed'
           AND substr(COALESCE(arrived_at, paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0);

    let landed_total: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status = 'closed'
           AND substr(COALESCE(arrived_at, paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let revenue_total: f64 = conn.query_row(
        "SELECT COALESCE(SUM(si.unit_price), 0)
         FROM sale_items si
         INNER JOIN imports i ON i.import_id = si.import_id
         WHERE i.status = 'closed'
           AND substr(COALESCE(i.arrived_at, i.paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    // Capital amarrado: SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) WHERE status='pending'
    // across all closed batches YTD. Single source post-R6 schema (NO UNION needed).
    let capital_amarrado: f64 = conn.query_row(
        "SELECT COALESCE(SUM(COALESCE(ii.unit_cost_gtq, i.unit_cost)), 0)
         FROM import_items ii
         INNER JOIN imports i ON i.import_id = ii.import_id
         WHERE ii.status = 'pending'
           AND i.status = 'closed'
           AND substr(COALESCE(i.arrived_at, i.paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let margen_total = revenue_total - landed_total;

    // Best/worst batch by margen_pct: iterate over all closed batches, compute pct per batch
    // Cheaper than complex SQL with subquery.
    let mut stmt = conn.prepare(
        "SELECT import_id FROM imports WHERE status = 'closed'
           AND substr(COALESCE(arrived_at, paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')"
    )?;
    let import_ids: Vec<String> = stmt
        .query_map([], |r| r.get::<_, String>(0))?
        .collect::<std::result::Result<Vec<_>, _>>()?;

    let mut pcts: Vec<(String, f64)> = vec![];
    for id in &import_ids {
        let s = compute_batch_summary(&conn, id)?;
        if let Some(pct) = s.margen_pct {
            pcts.push((id.clone(), pct));
        }
    }

    let margen_pct_avg = if !pcts.is_empty() {
        Some(pcts.iter().map(|(_, p)| p).sum::<f64>() / pcts.len() as f64)
    } else {
        None
    };

    let best = pcts.iter().max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let worst = pcts.iter().min_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

    Ok(MargenPulso {
        n_batches_closed: n_batches,
        revenue_total_ytd_gtq: revenue_total,
        landed_total_ytd_gtq: landed_total,
        margen_total_ytd_gtq: margen_total,
        margen_pct_avg,
        best_batch_id: best.map(|(id, _)| id.clone()),
        best_batch_margen_pct: best.map(|(_, p)| *p),
        worst_batch_id: worst.map(|(id, _)| id.clone()),
        worst_batch_margen_pct: worst.map(|(_, p)| *p),
        capital_amarrado_gtq: capital_amarrado,
    })
}

#[tauri::command]
pub async fn cmd_get_margen_pulso() -> Result<MargenPulso> {
    impl_get_margen_pulso()
}
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): cmd_get_margen_pulso (YTD aggregates · best/worst/avg)

- Global aggregates for MargenRealTab header pulso bar
- YTD = current year (substr arrived_at/paid_at)
- KPIs: n_batches_closed, revenue/landed/margen totals, margen_pct_avg, best/worst batch, capital_amarrado
- capital_amarrado from import_items WHERE status='pending' (R6 single source · NO UNION)
- Iterates batches in Rust (cheaper than SQL subquery for pct calc)"
```

---

### Task 6: Wire `tauri::generate_handler!` macro (3 new commands)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (line ~5176)

- [ ] **Step 1: Locate generate_handler! and append 3 R3 commands**

In lib.rs find the `generate_handler!` macro invocation (line ~5176). After R1.5/R2 entries append:

```rust
.invoke_handler(tauri::generate_handler![
    // ... existing R1 + R1.5 + R2 commands ...
    cmd_export_imports_csv,
    // R3 additions
    cmd_get_margen_real,
    cmd_get_batch_margen_breakdown,
    cmd_get_margen_pulso,
    // ... rest of existing commands ...
])
```

- [ ] **Step 2: Verify cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: `Finished` no errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r3): wire 3 new margen commands to generate_handler!"
```

---

## Task Group 2: Adapter wires (yo · secuencial)

### Task 7: Adapter types (`types.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Add output interfaces + extend Adapter**

Locate Import-related section (~line 332 · post R1.5 additions) and add:

```typescript
export interface MargenFilter {
  periodFrom?: string;       // YYYY-MM-DD
  periodTo?: string;         // YYYY-MM-DD
  supplier?: string;
  includePipeline?: boolean; // default false (closed only)
}

export interface BatchMargenSummary {
  importId: string;
  supplier: string;
  paidAt: string | null;
  arrivedAt: string | null;
  status: string;
  nUnits: number | null;
  totalLandedGtq: number | null;
  nSalesLinked: number;
  nItemsLinked: number;
  revenueTotalGtq: number;        // SUM(sale_items.unit_price) WHERE import_id=? (sale_items.sale_id always populated in production)
  margenBrutoGtq: number;
  margenPct: number | null;
  nStockPendiente: number;        // count import_items WHERE status='pending' (R6 single source)
  valorStockPendienteGtq: number; // SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) for pending items
  nFreeUnits: number;
  valorFreeUnitsGtq: number | null; // null hasta que se decida D-FREE valuation rule
}

export interface LinkedSale {
  saleId: string;
  occurredAt: string | null;      // production col: sales.occurred_at
  customerId: number | null;      // production col: sales.customer_id is INTEGER
  total: number;                  // production col: sales.total (NOT total_gtq)
  nItemsFromBatch: number;
}

export interface PendingItem {
  importItemId: number;
  familyId: string;               // production col (NOT sku)
  jerseyId: string | null;
  size: string | null;
  playerName: string | null;
  playerNumber: number | null;
  patch: string | null;
  version: string | null;
  customerId: string | null;      // NULL = stock-future · populated = assigned to specific customer
  expectedUsd: number | null;
  unitCostGtq: number | null;     // null hasta que close (R4) corra prorrateo
  status: string;                 // 'pending' | 'arrived' | 'sold' | 'published' | 'cancelled'
}

export interface FreeUnitRow {
  freeUnitId: number;
  destination: string;
  destinationRef: string | null;
  assignedAt: string | null;
  notes: string | null;
}

export interface BatchMargenDetail {
  summary: BatchMargenSummary;
  linkedSales: LinkedSale[];
  pendingItems: PendingItem[];
  freeUnits: FreeUnitRow[];
}

export interface MargenPulso {
  nBatchesClosed: number;
  revenueTotalYtdGtq: number;
  landedTotalYtdGtq: number;
  margenTotalYtdGtq: number;
  margenPctAvg: number | null;
  bestBatchId: string | null;
  bestBatchMargenPct: number | null;
  worstBatchId: string | null;
  worstBatchMargenPct: number | null;
  capitalAmarradoGtq: number;
}
```

In the `Adapter` interface, add 3 method signatures:

```typescript
export interface Adapter {
  // ... existing methods + R1.5 + R2 ...
  exportImportsCsv(): Promise<string>;

  // R3 additions
  getMargenReal(filter: MargenFilter): Promise<BatchMargenSummary[]>;
  getBatchMargenBreakdown(importId: string): Promise<BatchMargenDetail>;
  getMargenPulso(): Promise<MargenPulso>;
}
```

- [ ] **Step 2: Verify TypeScript compiles partially**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: errors only in tauri.ts/browser.ts (Adapter members not impl) · types.ts itself OK

- [ ] **Step 3: Don't commit yet** — types alone broken without impls. Commit at end of adapter group.

---

### Task 8: Adapter Tauri implementation (`tauri.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Add 3 invocations**

Locate `exportImportsCsv` method (~line 530 · R1.5 addition). After it, add:

```typescript
async getMargenReal(filter: MargenFilter): Promise<BatchMargenSummary[]> {
  return await invoke<BatchMargenSummary[]>('cmd_get_margen_real', { filter });
}

async getBatchMargenBreakdown(importId: string): Promise<BatchMargenDetail> {
  return await invoke<BatchMargenDetail>('cmd_get_batch_margen_breakdown', { importId });
}

async getMargenPulso(): Promise<MargenPulso> {
  return await invoke<MargenPulso>('cmd_get_margen_pulso');
}
```

Add imports at top of tauri.ts:

```typescript
import type {
  // ... existing imports ...
  MargenFilter,
  BatchMargenSummary,
  BatchMargenDetail,
  MargenPulso,
} from './types';
```

- [ ] **Step 2: Verify**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors in tauri.ts (browser.ts still has errors)

- [ ] **Step 3: Don't commit yet** — finish browser.ts.

---

### Task 9: Adapter Browser stubs (`browser.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 3 NotAvailableInBrowser stubs**

After `exportImportsCsv` (~line 380 · R1.5 addition):

```typescript
async getMargenReal(_filter: MargenFilter): Promise<BatchMargenSummary[]> {
  throw new Error('getMargenReal requires Tauri runtime · run via .exe MSI');
}

async getBatchMargenBreakdown(_importId: string): Promise<BatchMargenDetail> {
  throw new Error('getBatchMargenBreakdown requires Tauri runtime · run via .exe MSI');
}

async getMargenPulso(): Promise<MargenPulso> {
  throw new Error('getMargenPulso requires Tauri runtime · run via .exe MSI');
}
```

Add imports at top:

```typescript
import type {
  // ... existing imports ...
  MargenFilter,
  BatchMargenSummary,
  BatchMargenDetail,
  MargenPulso,
} from './types';
```

- [ ] **Step 2: Verify full check passes**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors total

- [ ] **Step 3: Commit adapter group**

Run:
```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/types.ts overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r3): adapter wires for 3 new margen commands

- types.ts: 7 output interfaces (MargenFilter + BatchMargenSummary + LinkedSale[occurredAt/total/customerId INTEGER] + PendingItem[reads import_items · familyId NOT sku] + FreeUnitRow + BatchMargenDetail + MargenPulso) + 3 Adapter method signatures
- tauri.ts: invoke() for each command
- browser.ts: NotAvailableInBrowser stubs (require .exe MSI)"
```

---

## Task Group 3: Svelte components (yo · 1 component por commit)

### Task 10: `BatchMarginCard.svelte` (NEW · ~150 LOC)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/BatchMarginCard.svelte`

- [ ] **Step 1: Create card component**

```svelte
<script lang="ts">
  import type { BatchMargenSummary } from '$lib/adapter/types';

  interface Props {
    summary: BatchMargenSummary;
    onViewSales?: (importId: string) => void;
    onViewPending?: (importId: string) => void;
  }

  let { summary, onViewSales, onViewPending }: Props = $props();

  // Format helpers
  function fmtGtq(n: number | null | undefined): string {
    if (n === null || n === undefined) return 'Q—';
    return 'Q' + Math.round(n).toLocaleString('es-GT');
  }

  function fmtPct(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}${n.toFixed(0)}%`;
  }

  // Color logic for margen
  let margenColor = $derived(
    summary.margenPct === null ? 'var(--color-text-tertiary)' :
    summary.margenPct >= 50 ? 'var(--color-terminal)' :
    summary.margenPct >= 20 ? 'var(--color-warning)' :
    summary.margenPct >= 0 ? 'var(--color-text-primary)' :
    'var(--color-danger)'
  );

  let statusColor = $derived(
    summary.status === 'closed' ? 'var(--color-terminal)' :
    summary.status === 'arrived' ? 'var(--color-info)' :
    summary.status === 'paid' ? 'var(--color-warning)' :
    'var(--color-text-tertiary)'
  );
</script>

<article class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 mb-3 hover:border-[var(--color-border-strong)] transition-colors">
  <!-- Header: import_id + n_units + status pill -->
  <header class="flex items-center justify-between mb-3 pb-2 border-b border-[var(--color-surface-2)]">
    <div class="flex items-baseline gap-3">
      <h3 class="text-mono text-[13px] font-semibold text-[var(--color-text-primary)] tabular-nums">
        {summary.importId}
      </h3>
      <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        {summary.nUnits ?? '—'}u · {summary.supplier}
      </span>
    </div>
    <span class="text-mono text-[9.5px] uppercase font-semibold px-2 py-0.5 rounded-[2px]"
      style="letter-spacing: 0.08em; color: {statusColor}; background: color-mix(in srgb, {statusColor} 12%, transparent); border: 1px solid color-mix(in srgb, {statusColor} 30%, transparent);">
      ● {summary.status}
    </span>
  </header>

  <!-- Body: 3 main rows + secondary 2 rows -->
  <div class="space-y-1.5 text-[12px]">
    <!-- Revenue -->
    <div class="flex items-center justify-between">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Revenue Comercial
      </span>
      <div class="flex items-baseline gap-2">
        <span class="text-mono text-[13px] tabular-nums text-[var(--color-text-primary)] font-semibold">
          {fmtGtq(summary.revenueTotalGtq)}
        </span>
        <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums">
          ({summary.nSalesLinked} ventas · {summary.nItemsLinked} items)
        </span>
      </div>
    </div>

    <!-- Landed total -->
    <div class="flex items-center justify-between">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Landed total
      </span>
      <span class="text-mono text-[13px] tabular-nums text-[var(--color-text-primary)]">
        {fmtGtq(summary.totalLandedGtq)}
      </span>
    </div>

    <!-- Margen bruto -->
    <div class="flex items-center justify-between pt-1.5 border-t border-[var(--color-surface-2)]">
      <span class="text-mono text-[10px] uppercase font-semibold" style="letter-spacing: 0.08em; color: {margenColor};">
        Margen bruto
      </span>
      <div class="flex items-baseline gap-2">
        <span class="text-mono text-[14px] tabular-nums font-bold" style="color: {margenColor};">
          {fmtGtq(summary.margenBrutoGtq)}
        </span>
        <span class="text-mono text-[11px] tabular-nums" style="color: {margenColor};">
          {fmtPct(summary.margenPct)}
        </span>
      </div>
    </div>
  </div>

  <!-- Secondary: free units + stock pendiente -->
  <div class="mt-3 pt-2 border-t border-[var(--color-surface-2)] space-y-1 text-[11px]">
    {#if summary.nFreeUnits > 0}
      <div class="flex items-center justify-between">
        <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
          🎁 Free units ({summary.nFreeUnits})
        </span>
        <span class="text-mono text-[11px] tabular-nums text-[var(--color-text-secondary)]" title="Valor pendiente cuando se asigne destino">
          {fmtGtq(summary.valorFreeUnitsGtq)}
        </span>
      </div>
    {/if}

    {#if summary.nStockPendiente > 0}
      <!-- nStockPendiente = COUNT FROM import_items WHERE status='pending' (R6 single-source schema) -->
      <!-- valorStockPendienteGtq = SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) -->
      <div class="flex items-center justify-between" title="Items promovidos a este batch con status=pending (no vendidos aún · stock-future + assigned-to-customer)">
        <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
          📦 Stock pendiente ({summary.nStockPendiente}u)
        </span>
        <span class="text-mono text-[11px] tabular-nums text-[var(--color-warning)]">
          {fmtGtq(summary.valorStockPendienteGtq)} amarrado
        </span>
      </div>
    {/if}
  </div>

  <!-- Footer: action links -->
  <footer class="mt-3 pt-2 border-t border-[var(--color-surface-2)] flex gap-3 text-[11px]">
    {#if onViewSales && summary.nSalesLinked > 0}
      <button
        onclick={() => onViewSales?.(summary.importId)}
        class="text-mono text-[10.5px] text-[var(--color-accent)] hover:underline"
        style="letter-spacing: 0.04em;"
      >
        → Ver ventas linkeadas ({summary.nSalesLinked})
      </button>
    {/if}
    {#if onViewPending && summary.nStockPendiente > 0}
      <button
        onclick={() => onViewPending?.(summary.importId)}
        class="text-mono text-[10.5px] text-[var(--color-accent)] hover:underline"
        style="letter-spacing: 0.04em;"
      >
        → Ver items pendientes ({summary.nStockPendiente})
      </button>
    {/if}
  </footer>
</article>
```

- [ ] **Step 2: Verify svelte-check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/BatchMarginCard.svelte && \
  git commit -m "feat(imp-r3): BatchMarginCard component (per spec sec 4.3 line 219-227 mockup)

- Header: import_id + n_units + supplier + status pill (● UPPERCASE dot prefix)
- Body: revenue (with sales/items count) · landed · margen bruto + pct (color-coded)
- Secondary: free units + stock pendiente (import_items WHERE status='pending' · only shown if > 0)
- Footer: action buttons (→ Ver ventas linkeadas / → Ver items pendientes)
- Color logic: terminal green for margen >= 50%, warning amber 20-49%, danger red < 0%
- Mono numbers · uppercase labels with letter-spacing 0.08em · CSS variables
- Stock pendiente tooltip clarifies single source (import_items table · R6 schema)"
```

---

### Task 11: `MargenFilters.svelte` (NEW · ~80 LOC)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/MargenFilters.svelte`

- [ ] **Step 1: Create filter component**

```svelte
<script lang="ts">
  import type { MargenFilter } from '$lib/adapter/types';

  interface Props {
    filter: MargenFilter;
    suppliers: string[];      // distinct values from data, populated by parent
    onChange: (next: MargenFilter) => void;
  }

  let { filter, suppliers, onChange }: Props = $props();

  // Local state mirrors filter (sync via $effect)
  let periodFrom = $state(filter.periodFrom ?? '');
  let periodTo = $state(filter.periodTo ?? '');
  let supplier = $state(filter.supplier ?? '');
  let includePipeline = $state(filter.includePipeline ?? false);

  function applyFilter() {
    onChange({
      periodFrom: periodFrom || undefined,
      periodTo: periodTo || undefined,
      supplier: supplier || undefined,
      includePipeline,
    });
  }

  function clearFilter() {
    periodFrom = '';
    periodTo = '';
    supplier = '';
    includePipeline = false;
    applyFilter();
  }

  let isActive = $derived(
    periodFrom !== '' || periodTo !== '' || supplier !== '' || includePipeline
  );
</script>

<div class="flex items-center gap-3 mb-4 p-3 bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px]">
  <!-- Period from -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Desde
    </span>
    <input
      type="date"
      bind:value={periodFrom}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    />
  </label>

  <!-- Period to -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Hasta
    </span>
    <input
      type="date"
      bind:value={periodTo}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    />
  </label>

  <!-- Supplier -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Supplier
    </span>
    <select
      bind:value={supplier}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    >
      <option value="">Todos</option>
      {#each suppliers as s}
        <option value={s}>{s}</option>
      {/each}
    </select>
  </label>

  <!-- Include pipeline toggle -->
  <label class="flex items-center gap-1.5 cursor-pointer ml-2">
    <input
      type="checkbox"
      bind:checked={includePipeline}
      onchange={applyFilter}
      class="accent-[var(--color-accent)]"
    />
    <span class="text-mono text-[10.5px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.06em;">
      Incluir pipeline (paid/arrived · margen estimado)
    </span>
  </label>

  <!-- Clear button -->
  {#if isActive}
    <button
      onclick={clearFilter}
      class="ml-auto text-mono text-[10px] px-2 py-1 rounded-[2px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]"
      style="letter-spacing: 0.06em;"
    >
      ✕ LIMPIAR
    </button>
  {/if}
</div>
```

- [ ] **Step 2: Verify**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/MargenFilters.svelte && \
  git commit -m "feat(imp-r3): MargenFilters component (period · supplier · include_pipeline toggle)

- 4 filter inputs: from/to dates, supplier dropdown (populated by parent), pipeline checkbox
- onChange callback (debounce-free · onchange triggers immediately)
- Clear button visible only when any filter active
- Mono uppercase labels · CSS variables · responsive flex layout"
```

---

### Task 12: REPLACE `MargenRealTab.svelte` (stub → funcional · ~180 LOC)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte` (REPLACE 6-line stub)

- [ ] **Step 1: Replace stub with functional tab**

Overwrite contents of `el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte`:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { BatchMargenSummary, MargenFilter, MargenPulso } from '$lib/adapter/types';
  import BatchMarginCard from '../BatchMarginCard.svelte';
  import MargenFilters from '../MargenFilters.svelte';

  interface Props {
    refreshTrigger?: number;
  }

  let { refreshTrigger = 0 }: Props = $props();

  let filter = $state<MargenFilter>({});
  let summaries = $state<BatchMargenSummary[]>([]);
  let pulso = $state<MargenPulso | null>(null);
  let loading = $state(false);
  let errorMsg = $state<string | null>(null);
  let sortBy = $state<'paid_desc' | 'margen_desc' | 'margen_asc' | 'revenue_desc'>('paid_desc');

  // Distinct suppliers for filter dropdown (derived from current data)
  let suppliers = $derived(
    Array.from(new Set(summaries.map(s => s.supplier))).sort()
  );

  // Sorted view of summaries
  let sortedSummaries = $derived(
    [...summaries].sort((a, b) => {
      switch (sortBy) {
        case 'paid_desc':
          return (b.paidAt ?? '').localeCompare(a.paidAt ?? '');
        case 'margen_desc':
          return (b.margenPct ?? -Infinity) - (a.margenPct ?? -Infinity);
        case 'margen_asc':
          return (a.margenPct ?? Infinity) - (b.margenPct ?? Infinity);
        case 'revenue_desc':
          return b.revenueTotalGtq - a.revenueTotalGtq;
      }
    })
  );

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      const [list, pulsoData] = await Promise.all([
        adapter.getMargenReal(filter),
        adapter.getMargenPulso(),
      ]);
      summaries = list;
      pulso = pulsoData;
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    // Re-load on mount, on filter change, or on parent refreshTrigger bump
    void refreshTrigger;
    load();
  });

  function handleFilterChange(next: MargenFilter) {
    filter = next;
  }

  function handleViewSales(importId: string) {
    // TODO future: cross-module nav to Comercial filtered by sale_ids from this batch
    // For now, log + alert (open question for Diego per spec ambiguity)
    console.log('TODO: navigate to Comercial filtered by import_id', importId);
    alert(`Cross-module nav a Comercial filtrado por ${importId} pendiente · ver Open questions plan IMP-R3`);
  }

  function handleViewPending(importId: string) {
    // TODO future: open detail subtab in Importaciones with pending items preview
    console.log('TODO: open detail with pending items for', importId);
    alert(`Drilldown a items pendientes de ${importId} pendiente · ver Open questions plan IMP-R3`);
  }

  function fmtGtq(n: number | null | undefined): string {
    if (n === null || n === undefined) return 'Q—';
    return 'Q' + Math.round(n).toLocaleString('es-GT');
  }

  function fmtPct(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}${n.toFixed(0)}%`;
  }
</script>

<div class="p-4">
  <!-- Header: title + sort dropdown -->
  <header class="flex items-baseline justify-between mb-3">
    <div>
      <h2 class="text-[15px] font-semibold text-[var(--color-text-primary)] mb-0.5">
        Margen real
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        Cross-Comercial · revenue × landed cost per batch closed · feed FIN-Rx
      </p>
    </div>
    <label class="flex items-center gap-2">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Sort
      </span>
      <select
        bind:value={sortBy}
        class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
      >
        <option value="paid_desc">Paid date ↓</option>
        <option value="margen_desc">Margen % ↓</option>
        <option value="margen_asc">Margen % ↑</option>
        <option value="revenue_desc">Revenue ↓</option>
      </select>
    </label>
  </header>

  <!-- Pulso bar: YTD aggregates -->
  {#if pulso}
    <div class="grid grid-cols-5 gap-2 mb-4 p-3 bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px]">
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Batches YTD</div>
        <div class="text-mono text-[16px] tabular-nums text-[var(--color-text-primary)] font-semibold">{pulso.nBatchesClosed}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Revenue YTD</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-text-primary)] font-semibold">{fmtGtq(pulso.revenueTotalYtdGtq)}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Landed YTD</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-text-primary)]">{fmtGtq(pulso.landedTotalYtdGtq)}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Margen total</div>
        <div class="text-mono text-[14px] tabular-nums font-semibold"
          style="color: {pulso.margenTotalYtdGtq >= 0 ? 'var(--color-terminal)' : 'var(--color-danger)'};">
          {fmtGtq(pulso.margenTotalYtdGtq)}
          <span class="text-[11px]">({fmtPct(pulso.margenPctAvg)})</span>
        </div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Capital amarrado</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-warning)]">{fmtGtq(pulso.capitalAmarradoGtq)}</div>
      </div>
    </div>

    <!-- Best/worst batch chips (if any) -->
    {#if pulso.bestBatchId || pulso.worstBatchId}
      <div class="flex gap-3 mb-3 text-[11px]">
        {#if pulso.bestBatchId}
          <span class="text-mono text-[10.5px] px-2 py-1 rounded-[2px] bg-[color-mix(in_srgb,var(--color-terminal)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-terminal)_30%,transparent)] text-[var(--color-terminal)]">
            🏆 BEST: {pulso.bestBatchId} · {fmtPct(pulso.bestBatchMargenPct)}
          </span>
        {/if}
        {#if pulso.worstBatchId && pulso.worstBatchId !== pulso.bestBatchId}
          <span class="text-mono text-[10.5px] px-2 py-1 rounded-[2px] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)] text-[var(--color-danger)]">
            ⚠️ WORST: {pulso.worstBatchId} · {fmtPct(pulso.worstBatchMargenPct)}
          </span>
        {/if}
      </div>
    {/if}
  {/if}

  <!-- Filter bar -->
  <MargenFilters {filter} {suppliers} onChange={handleFilterChange} />

  <!-- Body: cards list / loading / empty / error -->
  {#if loading}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)] p-8 text-center">
      ⏳ Cargando margen real...
    </div>
  {:else if errorMsg}
    <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
      ⚠️ {errorMsg}
    </div>
  {:else if sortedSummaries.length === 0}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)] p-8 text-center border border-dashed border-[var(--color-border)] rounded-[4px]">
      <div class="mb-2">📊 Sin batches cerrados aún</div>
      <div class="text-[10.5px]">
        Margen real disponible cuando un import pasa a status='closed'.<br/>
        {#if !filter.includePipeline}
          O activá <strong>"Incluir pipeline"</strong> arriba para ver paid/arrived con margen estimado.
        {/if}
      </div>
    </div>
  {:else}
    <div>
      {#each sortedSummaries as summary (summary.importId)}
        <BatchMarginCard
          {summary}
          onViewSales={handleViewSales}
          onViewPending={handleViewPending}
        />
      {/each}
    </div>
  {/if}
</div>
```

- [ ] **Step 2: Verify svelte-check + build**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte && \
  git commit -m "feat(imp-r3): MargenRealTab funcional (replace 6-line stub)

- Loads BatchMargenSummary[] + MargenPulso via adapter
- Pulso bar: 5 KPIs YTD (batches, revenue, landed, margen, capital amarrado)
- Best/worst batch chips with import_id + margen_pct
- MargenFilters integration (period/supplier/include_pipeline)
- Sort dropdown: paid date / margen pct / revenue
- Empty state with hint to enable include_pipeline
- refreshTrigger pattern for parent-driven reloads
- TODO stubs for cross-module nav (open question for Diego)"
```

---

## Task Group 4: Wire-up to ImportShell/ImportTabs (verify integration · NO modifications expected)

### Task 13: Verify MargenRealTab is already routed in ImportTabs

**Files:**
- Read-only verification: `el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte` + `ImportTabs.svelte`

R1 ya creó el routing de tabs · MargenRealTab.svelte ya está importado y mapeado al tab key `margen`. R3 solo reemplaza el contenido del componente · NO toca routing.

- [ ] **Step 1: Verify tab routing exists**

Run:
```bash
grep -n "MargenRealTab\|margen" C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportShell.svelte C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte 2>&1 | head -20
```
Expected: ve referencia a MargenRealTab importado y al tab key `margen` ya configurado en ImportTabs (creado en R1)

- [ ] **Step 2: Verify refreshTrigger pattern es prop opcional**

Si MargenRealTab es invocado en ImportShell sin pasar refreshTrigger, el default `= 0` aplica · sin errores. Si se quisiera triggear refresh desde ImportShell post mutación, agregar `refreshTrigger={refreshKey}` (donde refreshKey es state en ImportShell que se incrementa post create/close). Esto YA está hecho para los otros tabs (PedidosTab) · verificar que MargenRealTab también lo recibe.

Run:
```bash
grep -A 2 "MargenRealTab" C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/ImportTabs.svelte
```
Expected: si NO hay `refreshTrigger={...}` prop pasado, agregar en próximo step (no es bloqueador para R3 ship · default 0 OK)

- [ ] **Step 3: (Conditional) Wire refreshTrigger if missing**

Si el grep arriba muestra `<MargenRealTab />` sin refreshTrigger prop, edit ImportTabs.svelte para pasarlo:

```svelte
<!-- Antes -->
{:else if activeTab === 'margen'}
  <MargenRealTab />

<!-- Después -->
{:else if activeTab === 'margen'}
  <MargenRealTab {refreshTrigger} />
```

Asume `refreshTrigger` ya es state en ImportTabs (lo es para los otros tabs · pattern establecido en R1).

Si change applied:
```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/ImportTabs.svelte && \
  git commit -m "feat(imp-r3): wire refreshTrigger prop to MargenRealTab"
```

Si NO change needed (ya wired en R1): skip commit · seguir a Task 14.

---

## Task Group 5: Smoke + verification

### Task 14: Smoke test SQL script

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r3.py`

- [ ] **Step 1: Create smoke script**

```python
#!/usr/bin/env python3
"""
Smoke test post-implementation IMP-R3
Seeds: 1 closed import + 3 sales + 3 sale_items linked (sold) + 5 import_items (mix: 3 sold + 5 pending; 2 stock-future + 3 assigned among pending).
Stock pendiente: 5 import_items WHERE status='pending' (single source post-R6 schema).
Exercises: cmd_get_margen_real query logic + cmd_get_batch_margen_breakdown logic + cmd_get_margen_pulso logic
via direct SQL (simulating the Rust commands at SQL layer).
Reflects Diego decision (2026-04-28 ~19:00): tabla nueva import_items (R6 schema) recibe TODOS los promoted items.
Production schema cols used: sale_items.family_id (NOT sku), sale_items.variant_label (NOT variant), sales.total (NOT total_gtq), sales.occurred_at (NOT created_at), sales.customer_id (INTEGER).

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r3.py
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')

SMOKE_IMPORT_ID = 'IMP-2026-04-29-R3SMOKE'
SMOKE_SALE_PREFIX = 'CE-R3SMOKE-'

def assert_eq(actual, expected, msg):
    assert actual == expected, f'{msg} · expected={expected!r} actual={actual!r}'
    print(f'  [OK] {msg}: {actual!r}')

def assert_close(actual, expected, msg, tol=0.5):
    assert abs(actual - expected) < tol, f'{msg} · expected~{expected} actual={actual} (tol={tol})'
    print(f'  [OK] {msg}: {actual!r} (~{expected})')

def cleanup(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM sale_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_items WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM sales WHERE sale_id LIKE ?", (SMOKE_SALE_PREFIX + '%',))
    cur.execute("DELETE FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    cur.execute("DELETE FROM import_free_unit WHERE import_id = ?", (SMOKE_IMPORT_ID,))
    conn.commit()

def main():
    print(f'DB: {DB_PATH}')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cleanup any prior smoke runs
    cleanup(conn)

    print('\n=== SEED: 1 closed import + 3 sales + 3 linked sale_items (sold) + 8 import_items (3 sold · 5 pending mix stock-future + assigned) ===')

    # Seed import (closed status · total_landed_gtq pre-set por close_import_proportional simulado)
    # bruto=$372.64 · fx=7.73 · shipping=Q522.67 → total_landed = 372.64*7.73 + 522.67 = Q3,403.07
    # n_units=8 (3 sold + 5 pending) · unit_cost=Q425.38 (3403.07/8)
    cur.execute("""
        INSERT INTO imports (import_id, paid_at, arrived_at, supplier,
                             bruto_usd, shipping_gtq, fx, total_landed_gtq,
                             n_units, unit_cost, status, created_at)
        VALUES (?, '2026-04-15', '2026-04-23', 'Bond Soccer Jersey',
                372.64, 522.67, 7.73, 3403.07,
                8, 425.38, 'closed', datetime('now', 'localtime'))
    """, (SMOKE_IMPORT_ID,))

    # Seed 3 sales — production cols: sales.occurred_at (NOT created_at), sales.total (NOT total_gtq), sales.customer_id (INTEGER)
    for i in range(1, 4):
        sale_id = f'{SMOKE_SALE_PREFIX}{i:03d}'
        cur.execute("""
            INSERT INTO sales (sale_id, ref, occurred_at, modality, customer_id, total)
            VALUES (?, ?, datetime('now', 'localtime'), 'mystery_box', ?, ?)
        """, (sale_id, f'REF-{i:03d}', 9000 + i, 500.0 + i * 50))

    # Seed 3 sale_items linked to sales (sold from batch) — production cols: family_id (NOT sku), variant_label (NOT variant)
    for i in range(1, 4):
        sale_id = f'{SMOKE_SALE_PREFIX}{i:03d}'
        cur.execute("""
            INSERT INTO sale_items (sale_id, import_id, family_id, variant_label,
                                    unit_cost, unit_price)
            VALUES (?, ?, ?, ?, 425.38, ?)
        """, (sale_id, SMOKE_IMPORT_ID, f'FAM-{i:03d}', 'M', 500.0 + i * 50))

    # Seed 8 import_items (R6 schema · single source for stock pendiente):
    #   - 3 sold (status='sold' · customer_id populated · linked back via sale_item_id)
    #   - 3 pending stock-future (status='pending' · customer_id NULL)
    #   - 2 pending assigned (status='pending' · customer_id populated)
    # 3 sold items
    for i in range(1, 4):
        cur.execute("""
            INSERT INTO import_items (import_id, family_id, size, customer_id,
                                      expected_usd, unit_cost_gtq, status)
            VALUES (?, ?, 'M', ?, 45.0, 425.38, 'sold')
        """, (SMOKE_IMPORT_ID, f'FAM-{i:03d}', f'CUST-{i}'))

    # 3 pending stock-future (customer_id NULL)
    for i in range(4, 7):
        cur.execute("""
            INSERT INTO import_items (import_id, family_id, size, customer_id,
                                      expected_usd, unit_cost_gtq, status)
            VALUES (?, ?, 'L', NULL, 45.0, NULL, 'pending')
        """, (SMOKE_IMPORT_ID, f'FAM-FUT-{i:03d}'))

    # 2 pending assigned (customer_id populated · waiting for sale)
    for i in range(7, 9):
        cur.execute("""
            INSERT INTO import_items (import_id, family_id, size, customer_id,
                                      expected_usd, unit_cost_gtq, status)
            VALUES (?, ?, 'XL', ?, 45.0, NULL, 'pending')
        """, (SMOKE_IMPORT_ID, f'FAM-ASN-{i:03d}', f'CUST-PEND-{i}'))

    conn.commit()

    print('\n=== TEST 1: Margen summary aggregates ===')
    # Equivalente a compute_batch_summary(conn, SMOKE_IMPORT_ID)
    # Revenue = SUM(unit_price) WHERE import_id = X (sale_items.sale_id always populated in production)
    revenue = cur.execute("""
        SELECT COALESCE(SUM(unit_price), 0)
        FROM sale_items WHERE import_id = ?
    """, (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(revenue, 550.0 + 600.0 + 650.0, 'revenue_total_gtq (3 sold items)')

    n_sales = cur.execute("""
        SELECT COUNT(DISTINCT sale_id) FROM sale_items
        WHERE import_id = ?
    """, (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(n_sales, 3, 'n_sales_linked')

    n_items = cur.execute("""
        SELECT COUNT(*) FROM sale_items
        WHERE import_id = ?
    """, (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(n_items, 3, 'n_items_linked')

    landed = cur.execute("SELECT total_landed_gtq FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()[0]
    margen = revenue - landed
    margen_pct = (margen / landed) * 100
    print(f'  revenue={revenue} landed={landed} margen={margen:.2f} pct={margen_pct:.2f}%')
    # margen = 1800 - 3403.07 = -1603.07 → -47% (this batch is in the red because 3 items sold doesn't cover landed cost)
    # NOTE: Diego may seed different prices to verify positive margin · purpose here is logic correctness

    print('\n=== TEST 2: Stock pendiente from import_items (single source · R6 schema) ===')
    # Equivalente a compute_batch_summary stock pendiente query
    n_pendiente = cur.execute("""
        SELECT COUNT(*) FROM import_items
        WHERE import_id = ? AND status = 'pending'
    """, (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(n_pendiente, 5, 'n_stock_pendiente (5 import_items WHERE status=pending: 3 stock-future + 2 assigned)')

    # Valor: SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost))
    unit_cost_landed = cur.execute(
        "SELECT unit_cost FROM imports WHERE import_id = ?", (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    valor_pendiente = cur.execute("""
        SELECT COALESCE(SUM(COALESCE(unit_cost_gtq, ?)), 0)
        FROM import_items WHERE import_id = ? AND status = 'pending'
    """, (unit_cost_landed, SMOKE_IMPORT_ID)).fetchone()[0]
    expected_valor = 425.38 * 5  # all pending items have unit_cost_gtq=NULL · fallback to imports.unit_cost
    assert_close(valor_pendiente, expected_valor, 'valor_stock_pendiente_gtq (5 × imports.unit_cost fallback)', tol=0.01)

    # Sanity: breakdown stock-future vs assigned (for drilldown UI render)
    n_stock_future = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND status='pending' AND customer_id IS NULL",
        (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    n_assigned_pending = cur.execute(
        "SELECT COUNT(*) FROM import_items WHERE import_id = ? AND status='pending' AND customer_id IS NOT NULL",
        (SMOKE_IMPORT_ID,)
    ).fetchone()[0]
    assert_eq(n_stock_future, 3, '  breakdown: stock-future (customer_id NULL)')
    assert_eq(n_assigned_pending, 2, '  breakdown: assigned-pending (customer_id populated)')

    print('\n=== TEST 3: Linked sales JOIN (production cols: sales.total · sales.occurred_at · customer_id INTEGER) ===')
    rows = cur.execute("""
        SELECT s.sale_id, s.total, s.occurred_at, s.customer_id, COUNT(si.item_id) AS n
        FROM sales s
        INNER JOIN sale_items si ON si.sale_id = s.sale_id
        WHERE si.import_id = ?
        GROUP BY s.sale_id, s.total, s.occurred_at, s.customer_id
        ORDER BY s.sale_id
    """, (SMOKE_IMPORT_ID,)).fetchall()
    assert_eq(len(rows), 3, 'distinct sales linked')
    for r in rows:
        print(f'    {r["sale_id"]} → total={r["total"]} · occurred_at={r["occurred_at"]} · customer_id={r["customer_id"]} · n_items={r["n"]}')

    print('\n=== TEST 4: Free units count (0 expected · no inserts) ===')
    n_free = cur.execute("SELECT COUNT(*) FROM import_free_unit WHERE import_id = ?", (SMOKE_IMPORT_ID,)).fetchone()[0]
    assert_eq(n_free, 0, 'n_free_units (no inserts in seed)')

    print('\n=== TEST 5: Pulso aggregate query (YTD) ===')
    # Simulates impl_get_margen_pulso revenue_total query
    pulso_revenue = cur.execute("""
        SELECT COALESCE(SUM(si.unit_price), 0)
        FROM sale_items si
        INNER JOIN imports i ON i.import_id = si.import_id
        WHERE i.status = 'closed'
          AND substr(COALESCE(i.arrived_at, i.paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')
    """).fetchone()[0]
    print(f'  pulso revenue YTD (incl smoke seed): {pulso_revenue}')
    assert pulso_revenue >= 1800.0, f'pulso revenue should include smoke {1800.0} · got {pulso_revenue}'
    print(f'  [OK] pulso revenue includes smoke contribution')

    # Capital amarrado: simulates impl_get_margen_pulso single-source query (import_items WHERE status='pending')
    pulso_capital = cur.execute("""
        SELECT COALESCE(SUM(COALESCE(ii.unit_cost_gtq, i.unit_cost)), 0)
        FROM import_items ii
        INNER JOIN imports i ON i.import_id = ii.import_id
        WHERE ii.status = 'pending'
          AND i.status = 'closed'
          AND substr(COALESCE(i.arrived_at, i.paid_at), 1, 4) = strftime('%Y', 'now', 'localtime')
    """).fetchone()[0]
    print(f'  pulso capital_amarrado YTD (incl smoke seed): {pulso_capital}')
    assert pulso_capital >= 425.38 * 5 - 0.5, f'pulso capital should include smoke 5×{425.38} · got {pulso_capital}'
    print(f'  [OK] pulso capital_amarrado includes smoke (import_items single source)')

    print('\n=== TEST 6: Edge case · import without sale_items linked (margen=0-landed) ===')
    # Insert closed import with no sale_items + no import_items
    edge_id = SMOKE_IMPORT_ID + '-EDGE'
    cur.execute("""
        INSERT INTO imports (import_id, paid_at, arrived_at, supplier,
                             bruto_usd, shipping_gtq, fx, total_landed_gtq,
                             n_units, status, created_at)
        VALUES (?, '2026-04-10', '2026-04-18', 'Bond',
                100.0, 100.0, 7.73, 873.0, 5, 'closed',
                datetime('now', 'localtime'))
    """, (edge_id,))
    conn.commit()
    edge_revenue = cur.execute("""
        SELECT COALESCE(SUM(unit_price), 0) FROM sale_items
        WHERE import_id = ?
    """, (edge_id,)).fetchone()[0]
    edge_landed = cur.execute("SELECT total_landed_gtq FROM imports WHERE import_id = ?", (edge_id,)).fetchone()[0]
    edge_margen = edge_revenue - edge_landed
    print(f'  edge: revenue={edge_revenue} landed={edge_landed} margen={edge_margen} (expect negative · all stock pending)')
    cur.execute("DELETE FROM imports WHERE import_id = ?", (edge_id,))
    conn.commit()

    print('\n=== Cleanup ===')
    cleanup(conn)

    print('\n[PASS] ALL R3 SMOKE TESTS')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run smoke**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r3.py
```
Expected: `[PASS] ALL R3 SMOKE TESTS` · todos los assert_eq pasan

- [ ] **Step 3: Commit**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_imp_r3.py && \
  git commit -m "test(imp-r3): SQL smoke script · 6 tests + edge case (no sales linked)

- Seeds 1 closed import + 3 sales + 3 linked sale_items + 8 import_items (3 sold + 3 stock-future pending + 2 assigned-pending)
- Reflects Diego decision (2026-04-28 ~19:00): import_items table single source for promoted items (R6 schema)
- Uses production cols: sale_items.family_id (NOT sku), variant_label (NOT variant), sales.total (NOT total_gtq), occurred_at, customer_id INTEGER
- Test 1: revenue/n_sales/n_items aggregates (sale_items.sale_id always populated)
- Test 2: stock pendiente from import_items WHERE status='pending' (5 total: 3 stock-future + 2 assigned)
- Test 3: linked sales JOIN with n_items per sale (uses production cols)
- Test 4: free units count (0 baseline)
- Test 5: pulso YTD aggregates include smoke contribution (revenue + capital_amarrado from import_items single source)
- Test 6: edge case · import sin sale_items linked (margen = -landed)
- Cleanup at start + end (idempotent · incl import_items)"
```

---

### Task 15: Final verification (cargo + npm + manual smoke)

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Cargo check release**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check --release 2>&1 | tail -5
```
Expected: `Finished release [optimized] target(s)` no errors

- [ ] **Step 2: Cargo test (existing R1.5/R2 tests still pass · no R3 tests added)**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test 2>&1 | tail -15
```
Expected: all existing tests pass · `imp_r15_*` y `imp_r2_*` tests verde · zero regressions

- [ ] **Step 3: npm check + build**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3 && npm run build 2>&1 | tail -5
```
Expected: 0 errors check · build OK

- [ ] **Step 4: Smoke script final run**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r3.py
```
Expected: `[PASS] ALL R3 SMOKE TESTS`

---

## Self-Review

Before declaring R3 complete, run this mental checklist:

**Spec coverage (sec 4.3 + sec 7 + sec 11):**
- [x] Tab Margen real renders cards per batch closed → Task 12 + 10 ✓
- [x] Card shows Revenue Comercial + n_sales_linked → Task 10 ✓ (lee de sale_items joined a sales linked via import_id)
- [x] Card shows Landed total → Task 10 ✓
- [x] Card shows Margen bruto + pct color-coded → Task 10 ✓
- [x] Card shows Free units count + valor (Q— por valor pendiente) → Task 10 ✓
- [x] Card shows Stock pendiente (N) Q amarrado → Task 10 ✓ (lee de **import_items WHERE status='pending'** · NO de sale_items + jerseys UNION · single source post-R6 schema)
- [x] Footer links "→ Ver ventas linkeadas / → Ver items pendientes" → Task 10 (TODO stubs · open question) ⚠️
- [x] Filtros período · supplier · include_pipeline → Task 11 ✓
- [x] Default closed only · include_pipeline opt-in → Task 3 + 11 ✓
- [x] Pulso bar global (YTD aggregates · best/worst/avg) → Task 5 + 12 ✓
- [x] Cross-link a FIN-Rx (queries documentadas para FIN consumir) → Task 3 + 5 (data exposed via cmd_get_margen_real / cmd_get_margen_pulso) ✓
- [x] Empty state pulido → Task 12 ✓

**Placeholder scan:** ningún `TODO` / `implement later` / `add validation` / `similar to Task N` en steps. EXCEPCIÓN: handleViewSales/handleViewPending son TODO stubs deliberados por spec ambiguity (cross-module nav). Marcadas como Open question. ✓

**Type consistency:**
- `MargenFilter` / `BatchMargenSummary` / `BatchMargenDetail` / `MargenPulso` ─ camelCase serde rename ✓
- Adapter method names match Rust commands (`getMargenReal`, `getBatchMargenBreakdown`, `getMargenPulso`) ✓
- `nSalesLinked` / `nStockPendiente` / `valorStockPendienteGtq` snake_case → camelCase consistente ✓

**Cross-module impact (per master overview + sec 11 línea 821):**
- COM (Sales): cero touch · solo READS de `sales` y `sale_items` (production cols `total`, `occurred_at`, `family_id`, `variant_label`) ✓
- FIN: cero touch · expone data via `cmd_get_margen_real` y `cmd_get_margen_pulso` para FIN-Rx consumption futuro ✓
- ADM Universe: cero touch ✓
- catalog.json: cero touch ✓
- Worker Cloudflare: cero touch ✓
- Schema: **R3 depende de R6 schema script** (`apply_imp_schema.py` crea `import_items` table) · sin R6, R3 falla en queries de stock pendiente. R3 también depende de R2 promote populando `import_items` y futuro R4 close updating status to 'arrived' + futuro Comercial flow updating status to 'sold' linkeando a `sale_items.item_id` via `import_items.sale_item_id`. Pre-flight Task 0 Step 4.5 verifica que `import_items` table exists ✓

**Read-only safety:**
- Todos los commands son `SELECT` only · sin `INSERT`/`UPDATE`/`DELETE`/`ALTER` ✓
- `compute_batch_summary` toma `&Connection` (immutable borrow) ✓
- impl_get_margen_real construye SQL dinámico con params bound · NO string concat de user input → cero SQL injection ✓

**Convention compliance (lib.rs:2730-2742):**
- Split `impl_X` (pub) + `cmd_X` (#[tauri::command]) aplicado a los 3 commands ✓
- Re-uso de `read_import_by_id` no necesario aquí (compute_batch_summary tiene su propio SELECT enriquecido) · OK ✓

---

## Open questions for Diego

Estas ambigüedades del spec quedaron sin resolver durante write-plan · agregar al ping de acceptance gate post-ship:

### Q0 · Stock pendiente data source — SUPERSEDED 2026-04-28 ~19:00

Decisión previa (UNION sale_items + jerseys) inejecutable por schema constraints (sale_items.sale_id NOT NULL en producción · jerseys sin import_id pop-by-promote ruta). Diego eligió Opción 1 mejorada: tabla nueva `import_items` (R6 schema script crea via `apply_imp_schema.py`) recibe TODOS los promoted items.

R3 stock pendiente query es ahora `SELECT * FROM import_items WHERE status='pending' AND import_id=?` · una sola fuente · clean. `customer_id` nullable distingue stock-future (NULL) de assigned (populated) pero ambos cuentan como pending.

Valor = `SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost))` · per-item si R4 close ya seteó prorrateo · fallback a batch-level imports.unit_cost.

Drilldown `pending_items` ahora retorna lista de `import_items` rows directamente (con todas las columnas: family_id, jersey_id, size, player_name, etc.) · NO necesita `source` field discriminator.

---

1. **Free units valor cuando closed pero sin destino asignado:** ¿debería mostrar Q— (default actual · `valor_free_units_gtq=null`) o calcular `unit_cost × n_free_units` con flag "valor estimado · sin destino real"? Default actual: Q— con tooltip "valor pendiente cuando se asigne destino". Diego decide post-Wave 2 ship (D-FREE valuation rule).

2. **Cross-module nav "→ Ver ventas linkeadas":** ¿debería abrir Comercial filtrado por `sale_ids` del batch (require nuevo routing infra cross-módulo · no existe hoy en ERP) o abrir un drilldown subtab dentro de Importaciones con sales preview? Default actual: alert TODO · escalar para decisión.

3. **Cross-module nav "→ Ver items pendientes":** ¿abrir el detail subtab actual de Importaciones (Pedidos > batch detail > items sub-tab filtered by status='pending') o crear nuevo drilldown standalone? Default actual: alert TODO.

4. **Comercial integration con import_items:** Cuando Comercial vende un jersey de un batch, el flujo full sería: insert sale_items row (con import_id) + UPDATE import_items SET status='sold', sale_item_id=? WHERE import_item_id=?. Esto lo implementa una future Comercial integration · OUT OF SCOPE de R3. R3 actual lee revenue de sale_items directamente (no requiere el link reverso desde import_items para contar revenue · solo para drilldown "qué items específicos se vendieron").

5. **Pulso "best/worst" tie handling:** si dos batches tienen el mismo margen_pct, actualmente el primero encontrado en iteration order gana. ¿OK o debería desempatar por revenue/landed/paid_at? Default OK por simplicidad.

6. **Decimal precision:** revenue/landed/margen actualmente redondeados a integer en display (`Math.round(n)`). Si Diego quiere ver decimals (e.g. Q1,234.56) cambiar `fmtGtq` en BatchMarginCard.svelte y MargenRealTab.svelte. Default integer per consistency con resto del ERP.

---

## Cross-release dependencies

**Depende de R6 (HARD):** R3 lee de `import_items` table que NO existe sin `apply_imp_schema.py` (R6 schema script). Pre-flight Task 0 Step 4.5 verifica esto.

**Depende de R2 (soft):** R3 lee `sale_items.import_id` (revenue) Y `import_items.import_id` (stock pendiente) que son escritos por:
- R1 historical migration (51 sale_items existentes con `import_id` set por migración Streamlit→Tauri linkeados a IMP-2026-04-07 · funciona standalone para revenue tracking)
- R2 promote-to-batch (futuro flow Wishlist→Promote): INSERT en `import_items` con `customer_id` (NULL=stock-future, populated=assigned) · `status='pending'`. Por ahora R2 NO ha shipped.
- R1.5 close_import_proportional (escribe `imports.total_landed_gtq` + `imports.unit_cost` per-unit landed · R4 close lo extenderá para iterar `import_items` y setear per-item `unit_cost_gtq`)

R3 funciona end-to-end con SOLO R6 + R1 historical data (revenue de los 51 sale_items existentes · stock pendiente vacío hasta R2 promote). Una vez R2 + R4 shipped, el flujo full Wishlist→import_items→Close→Comercial sale link es completable.

**Future Comercial integration (out of scope R3):** Cuando Comercial venda un jersey de un batch, el flow será: INSERT sale_items con import_id + UPDATE import_items SET status='sold', sale_item_id=? · esto cierra el loop. R3 lee revenue de sale_items independientemente del estado de import_items, así que no bloquea ship.

**Habilita FIN-Rx:** R3 expone:
- `cmd_get_margen_real` con filter (FIN puede pullear closed YTD para hero "¿cuánto llevo ganado?")
- `cmd_get_margen_pulso` con totals revenue/landed/margen YTD
- FIN consumirá vía `cmd_get_home_snapshot` extendido (lib.rs:3295) · NO en R3 (out of scope)

---

## Execution Handoff

Plan complete and saved to `el-club-imp/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R3.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — Diego dispatches a fresh subagent per task, reviews between tasks. Best for `lib.rs` queries where pattern review per command catches bugs early.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review. Best if Diego wants to be in the loop on every task.

**Which approach?**

If subagent-driven chosen: REQUIRED SUB-SKILL `superpowers:subagent-driven-development`.
If inline: REQUIRED SUB-SKILL `superpowers:executing-plans`.

**Parallel-safe with R4 + R5 + R6** (Wave 2 paralelización per master overview):
- R3 lib.rs additions: 3 commands · 1 helper · 8 structs · ~280 LOC sequential append
- R4 lib.rs additions: independent commands · sub-agent paralelo OK
- Frontend Svelte: R3 BatchMarginCard + MargenFilters + MargenRealTab.svelte son archivos separados de R4/R5/R6 components · cero conflict

**Sub-agent dispatch hint para Wave 2:**
- 1 sesión Rust (yo) ejecuta R3 + R4 + R5 + R6 commands secuencial en lib.rs
- 4 sub-agents Svelte paralelos: R3 components / R4 components / R5 components / R6 components

---

## After R3 ships

1. Append commit hashes + smoke results to `SESSION-COORDINATION.md` activity log
2. Diego acceptance gate (Wave 2 check #2): "¿Ves margen real per batch closed con revenue/landed/margen calculado?"
3. Si Diego dice "sí" · seguir a R4/R5/R6 plans en paralelo
4. Resolver Open questions 1-6 antes de FIN-Rx empezar (FIN consumirá los queries de R3 · necesita semantics estables)
5. Final ship Wave 2: schema migration on main DB + MSI rebuild + merge `--no-ff` + tag `v0.4.0`
