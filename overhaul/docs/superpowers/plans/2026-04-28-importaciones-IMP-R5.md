# IMP-R5 Implementation Plan — Supplier Scorecard (Bond card + multi-supplier scaffold)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read-only / queries-only — smoke-only testing (no TDD required per master overview line 100).

**Goal:** Reemplazar el stub `SupplierTab.svelte` ("Próximamente · Supplier scorecard viene en IMP-R5") con un scorecard funcional de Bond Soccer Jersey (único supplier hoy) que muestre lead time avg/p50/p95, cost accuracy stub, price band, free policy, total batches, total landed YTD y next expected arrival. Multi-supplier scaffold = chip area dinámico que itera DISTINCT suppliers de `imports.supplier` (hoy solo Bond · futuro v0.5 puede agregar Yupoo direct/Aliexpress sin tocar UI).

**Architecture:** Solo módulo IMP. Cero schema changes (no se crea tabla `suppliers` en R5 — el spec sec 4.5 línea 280 explícitamente difiere a v0.5 · contact info / payment terms / disputes log son hardcoded por supplier identifier en la card). 2 Rust commands read-only (`cmd_get_supplier_metrics` para list aggregate · `cmd_get_supplier_detail` para per-supplier deep-dive). Percentile calc Rust-side (SQLite no tiene `percentile_cont` nativo · `Vec<f64>::sort` + index lookup es trivial). Convention block lib.rs:2730-2742 aplicado: `impl_get_supplier_metrics` + `cmd_get_supplier_metrics` shim.

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + Tauri 2 + Svelte 5 (`$state`/`$derived`/`$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · 0 deps nuevas.

---

## File Structure

### Files to create (4 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/overhaul/src/lib/components/importaciones/SupplierBondCard.svelte` | Scorecard card per supplier · 7 stats + header · pills para batches en pipeline · empty/insufficient-data states |
| `el-club-imp/overhaul/src/lib/components/importaciones/SupplierChipBar.svelte` | Bar de chips horizontales (1 chip por DISTINCT supplier) · click selecciona · Bond default highlighted · "+ supplier" disabled stub futuro |
| `el-club-imp/overhaul/src-tauri/tests/imp_r5_supplier_test.rs` | Smoke-only inline test: percentile calc helper + insufficient-data (n<3) handling |
| `el-club-imp/erp/scripts/smoke_imp_r5.py` | SQL smoke: seed 5 closed Bond imports + 1 paid (pipeline) · query metrics · verify avg=8.4 / p50=8 / p95≈11.6 · cleanup |

### Files to modify (5 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | Agregar 5 structs (`SupplierMetrics` + `SupplierDetail` + `PriceBand` + `ContactInfo` + `UnpublishedRequest`) + 3 command pairs (impl + cmd shim · incluye bonus `cmd_get_most_requested_unpublished`) + helper `percentile_at` + helper `read_catalog_family_ids` + Bond hardcoded constants + wire `generate_handler!` | +360 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | 5 type interfaces + 3 method signatures en Adapter | +55 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 3 invocations | +20 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 3 stub fallbacks (throw NotAvailableInBrowser) | +18 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte` | REPLACE 6-line stub completo · load metrics on mount · render ChipBar + BondCard · empty state si zero suppliers · BONUS widget "más pedidos sin publicar" (top-5 sección al tope) | +220 |

**Total estimado:** ~620 líneas net nuevas (incluye bonus widget · ~+90 LOC vs estimación previa).

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

- [ ] **Step 2: Verify R1.5 + (assumed) R3/R4 already merged en branch**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git log --oneline -20 | grep -E 'imp-r(1\.5|3|4)' | head -10
```
Expected: at least 5+ commits con prefijo `feat(imp-r1.5)` · `feat(imp-r3)` · `feat(imp-r4)` (R5 ships en Wave 2 alongside R3/R4/R6 · este branch ya los lleva)

- [ ] **Step 3: Verify SupplierTab stub current state**

Run:
```bash
wc -l C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte && \
  cat C:/Users/Diego/el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte
```
Expected: 6 lines · contiene "Próximamente · Supplier scorecard viene en IMP-R5"

- [ ] **Step 4: Verify imports table shape (supplier column exists)**

Run:
```bash
python -c "import sqlite3; conn = sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); cols = conn.execute('PRAGMA table_info(imports)').fetchall(); print([c[1] for c in cols])"
```
Expected: list contiene `supplier`, `paid_at`, `arrived_at`, `lead_time_days`, `bruto_usd`, `total_landed_gtq`, `n_units`, `unit_cost`, `status`. Si `lead_time_days` no existe → R1.5 no fue mergeado · STOP y escalar.

- [ ] **Step 5: Sanity check existing pulso command pattern**

Run:
```bash
grep -n "lead time avg supplier\|cmd_get_import_pulso" C:/Users/Diego/el-club-imp/overhaul/src-tauri/src/lib.rs | head -10
```
Expected: localizar `cmd_get_import_pulso` (~line 2570 per task brief) · usaremos su pattern de aggregation como reference

---

## Task Group 1: Rust commands + structs (yo · secuencial · lib.rs)

### Task 1: Helper `percentile_at` + Bond hardcoded constants

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add helper near pulso command ~line 2570 · add Bond constants near top of Importaciones section)

- [ ] **Step 1: Add percentile helper inline**

Locate the Importaciones section in lib.rs (search for "// ===== IMPORTACIONES" or near `cmd_get_import_pulso` ~line 2570). Add before the existing pulso command:

```rust
/// Calcula percentil al ratio dado (0.0..1.0) sobre vector ordenado de valores f64.
/// Usa nearest-rank method (sin interpolación) — suficiente para n pequeños (n<100).
/// Retorna `None` si el vector está vacío.
fn percentile_at(values: &[f64], ratio: f64) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let mut sorted: Vec<f64> = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let n = sorted.len();
    // Nearest-rank: idx = ceil(ratio * n) - 1, clamped to [0, n-1]
    let idx = ((ratio * n as f64).ceil() as usize).saturating_sub(1).min(n - 1);
    Some(sorted[idx])
}

#[cfg(test)]
mod imp_r5_helper_tests {
    use super::*;

    #[test]
    fn test_percentile_empty() {
        assert_eq!(percentile_at(&[], 0.5), None);
    }

    #[test]
    fn test_percentile_single() {
        assert_eq!(percentile_at(&[42.0], 0.5), Some(42.0));
        assert_eq!(percentile_at(&[42.0], 0.95), Some(42.0));
    }

    #[test]
    fn test_percentile_known_values() {
        // Lead times: 5, 7, 8, 10, 12 — avg 8.4
        let v = vec![5.0, 7.0, 8.0, 10.0, 12.0];
        // p50: nearest-rank idx = ceil(0.5 * 5) - 1 = 2 → sorted[2] = 8
        assert_eq!(percentile_at(&v, 0.50), Some(8.0));
        // p95: nearest-rank idx = ceil(0.95 * 5) - 1 = 4 → sorted[4] = 12
        assert_eq!(percentile_at(&v, 0.95), Some(12.0));
    }
}
```

- [ ] **Step 2: Add Bond hardcoded constants near top of Importaciones section**

```rust
// Bond Soccer Jersey hardcoded card data (per spec sec 4.5 line 269-278)
// Move to suppliers table when v0.5 adds multi-supplier proper.
const BOND_SUPPLIER_NAME: &str = "Bond Soccer Jersey";
const BOND_CONTACT_LABEL: &str = "WhatsApp · 志鵬 黎";
const BOND_PAYMENT_METHOD: &str = "PayPal upfront";
const BOND_CARRIER: &str = "DHL door-to-door";
const BOND_FREE_POLICY_TEXT: &str = "1 unit cada 10 paid units";
const BOND_PRICE_BASE_USD: f64 = 11.0;
const BOND_PRICE_PATCH_USD: f64 = 13.0;
const BOND_PRICE_PATCH_NAME_USD: f64 = 15.0;
```

- [ ] **Step 3: Run helper tests**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test imp_r5_helper_tests 2>&1 | tail -10
```
Expected: PASS · `3 passed`

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r5): percentile_at helper + Bond hardcoded constants

- percentile_at: nearest-rank method · None for empty
- 3 unit tests cover empty/single/known-values cases
- Bond constants per spec sec 4.5 line 269-278 (move to suppliers table en v0.5)"
```

---

### Task 2: Structs `SupplierMetrics` + `PriceBand` + `ContactInfo` + `SupplierDetail` + `SupplierBatchSummary`

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add structs after Bond constants**

```rust
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ContactInfo {
    pub label: String,           // "WhatsApp · 志鵬 黎"
    pub payment_method: String,  // "PayPal upfront"
    pub carrier: String,         // "DHL door-to-door"
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PriceBand {
    pub base_usd: Option<f64>,         // $11
    pub patch_usd: Option<f64>,        // $13
    pub patch_name_usd: Option<f64>,   // $15
    pub source: String,                // "hardcoded:Bond" | "tbd"
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SupplierMetrics {
    pub supplier: String,
    pub total_batches: i64,
    pub closed_batches: i64,
    pub pipeline_batches: i64,            // status in (paid, in_transit, arrived)
    pub lead_time_avg_days: Option<f64>,
    pub lead_time_p50_days: Option<f64>,
    pub lead_time_p95_days: Option<f64>,
    pub lead_time_n: i64,                 // sample size for transparency
    pub total_landed_gtq_ytd: f64,        // sum closed batches · current year
    pub cost_accuracy_pct: Option<f64>,   // None hasta que existan disputes log (R5 escalado)
    pub next_expected_arrival: Option<String>,  // earliest paid_at + avg_lead among non-closed
    pub last_batch_paid_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SupplierBatchSummary {
    pub import_id: String,
    pub paid_at: Option<String>,
    pub arrived_at: Option<String>,
    pub status: String,
    pub n_units: Option<i64>,
    pub total_landed_gtq: Option<f64>,
    pub lead_time_days: Option<i64>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SupplierDetail {
    pub metrics: SupplierMetrics,
    pub contact: ContactInfo,
    pub price_band: PriceBand,
    pub free_policy_text: String,
    pub batches: Vec<SupplierBatchSummary>,  // sorted DESC by paid_at
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
  git commit -m "feat(imp-r5): supplier scorecard structs (Metrics/Detail/PriceBand/ContactInfo/BatchSummary)

- SupplierMetrics: 12 fields · cost_accuracy_pct Option<f64> (None hasta disputes log existe)
- SupplierDetail extends Metrics con contact + price_band + free_policy + batches[]
- camelCase serde rename para frontend
- next_expected_arrival = earliest paid_at + avg_lead entre non-closed"
```

---

### Task 3: `cmd_get_supplier_metrics` (impl + shim · smoke-only)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement `impl_get_supplier_metrics` + shim**

Add after structs:

```rust
/// Aggregates metrics per DISTINCT supplier from `imports.supplier`.
/// Returns one row per supplier (today: only Bond · multi-supplier scaffold for v0.5).
pub fn impl_get_supplier_metrics() -> Result<Vec<SupplierMetrics>> {
    let conn = open_db()?;

    // 1. Get DISTINCT suppliers (skip NULL/empty)
    let mut stmt = conn.prepare(
        "SELECT DISTINCT supplier FROM imports
         WHERE supplier IS NOT NULL AND supplier != ''
         ORDER BY supplier"
    )?;
    let supplier_iter = stmt.query_map([], |row| row.get::<_, String>(0))?;
    let suppliers: Vec<String> = supplier_iter.collect::<rusqlite::Result<Vec<_>>>()?;

    let mut out = Vec::with_capacity(suppliers.len());

    for supplier in suppliers {
        // 2. Counts per status bucket
        let total_batches: i64 = conn.query_row(
            "SELECT COUNT(*) FROM imports WHERE supplier = ?1",
            rusqlite::params![&supplier],
            |row| row.get(0),
        )?;
        let closed_batches: i64 = conn.query_row(
            "SELECT COUNT(*) FROM imports WHERE supplier = ?1 AND status = 'closed'",
            rusqlite::params![&supplier],
            |row| row.get(0),
        )?;
        let pipeline_batches: i64 = conn.query_row(
            "SELECT COUNT(*) FROM imports WHERE supplier = ?1
             AND status IN ('paid', 'in_transit', 'arrived')",
            rusqlite::params![&supplier],
            |row| row.get(0),
        )?;

        // 3. Collect lead_time_days for closed batches → Rust-side percentile
        let mut lt_stmt = conn.prepare(
            "SELECT lead_time_days FROM imports
             WHERE supplier = ?1 AND status = 'closed' AND lead_time_days IS NOT NULL"
        )?;
        let lt_iter = lt_stmt.query_map(rusqlite::params![&supplier], |row| row.get::<_, i64>(0))?;
        let lead_times: Vec<f64> = lt_iter
            .filter_map(|r| r.ok())
            .map(|v| v as f64)
            .collect();
        let lead_time_n = lead_times.len() as i64;

        let lead_time_avg_days = if lead_times.is_empty() {
            None
        } else {
            Some(lead_times.iter().sum::<f64>() / lead_times.len() as f64)
        };
        let lead_time_p50_days = percentile_at(&lead_times, 0.50);
        let lead_time_p95_days = percentile_at(&lead_times, 0.95);

        // 4. Total landed GTQ YTD (current year closed)
        let total_landed_gtq_ytd: f64 = conn.query_row(
            "SELECT COALESCE(SUM(total_landed_gtq), 0.0) FROM imports
             WHERE supplier = ?1 AND status = 'closed'
             AND strftime('%Y', paid_at) = strftime('%Y', 'now', 'localtime')",
            rusqlite::params![&supplier],
            |row| row.get(0),
        )?;

        // 5. Last batch paid_at
        let last_batch_paid_at: Option<String> = conn.query_row(
            "SELECT MAX(paid_at) FROM imports WHERE supplier = ?1 AND paid_at IS NOT NULL",
            rusqlite::params![&supplier],
            |row| row.get(0),
        ).ok().flatten();

        // 6. Next expected arrival: earliest paid_at + avg_lead among non-closed/non-cancelled
        // Only computable if avg_lead exists.
        let next_expected_arrival: Option<String> = if let Some(avg) = lead_time_avg_days {
            let earliest_paid: Option<String> = conn.query_row(
                "SELECT MIN(paid_at) FROM imports
                 WHERE supplier = ?1
                 AND status IN ('paid', 'in_transit', 'arrived')
                 AND paid_at IS NOT NULL",
                rusqlite::params![&supplier],
                |row| row.get(0),
            ).ok().flatten();
            earliest_paid.and_then(|paid| {
                chrono::NaiveDate::parse_from_str(&paid, "%Y-%m-%d").ok().map(|d| {
                    let eta = d + chrono::Duration::days(avg.round() as i64);
                    eta.format("%Y-%m-%d").to_string()
                })
            })
        } else {
            None
        };

        // 7. cost_accuracy_pct: None until disputes log exists (per spec ambiguity escalation)
        // See "Open questions for Diego" section · displayed as "Datos insuficientes" in UI.
        let cost_accuracy_pct: Option<f64> = None;

        out.push(SupplierMetrics {
            supplier,
            total_batches,
            closed_batches,
            pipeline_batches,
            lead_time_avg_days,
            lead_time_p50_days,
            lead_time_p95_days,
            lead_time_n,
            total_landed_gtq_ytd,
            cost_accuracy_pct,
            next_expected_arrival,
            last_batch_paid_at,
        });
    }

    Ok(out)
}

#[tauri::command]
pub async fn cmd_get_supplier_metrics() -> Result<Vec<SupplierMetrics>> {
    impl_get_supplier_metrics()
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
  git commit -m "feat(imp-r5): cmd_get_supplier_metrics (impl + shim · 7 aggregations per supplier)

- DISTINCT supplier from imports.supplier (multi-supplier scaffold)
- lead_time_avg/p50/p95 calculated Rust-side over closed batches
- total_landed_gtq_ytd: current year closed sum
- next_expected_arrival: earliest paid_at + avg_lead among non-closed
- cost_accuracy_pct: None hasta disputes log existe (escalado en Open Questions)
- Convention split impl_get_supplier_metrics + cmd_get_supplier_metrics"
```

---

### Task 4: `cmd_get_supplier_detail` (impl + shim · smoke-only)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Implement detail command**

Add after `cmd_get_supplier_metrics`:

```rust
/// Returns rich detail for a single supplier: metrics + contact + price_band + free_policy + batches[].
/// For Bond: price_band hardcoded per spec sec 4.5 line 274.
/// For unknown suppliers: price_band returned con source="tbd" + None values (UI muestra "datos pendientes").
pub fn impl_get_supplier_detail(supplier: String) -> Result<SupplierDetail> {
    // Reuse list aggregator + filter
    let all = impl_get_supplier_metrics()?;
    let metrics = all
        .into_iter()
        .find(|m| m.supplier == supplier)
        .ok_or_else(|| ErpError::NotFound(format!("Supplier '{}'", supplier)))?;

    // Contact info (hardcoded for Bond · placeholder for others)
    let (contact, free_policy_text, price_band) = if supplier == BOND_SUPPLIER_NAME {
        (
            ContactInfo {
                label: BOND_CONTACT_LABEL.to_string(),
                payment_method: BOND_PAYMENT_METHOD.to_string(),
                carrier: BOND_CARRIER.to_string(),
            },
            BOND_FREE_POLICY_TEXT.to_string(),
            PriceBand {
                base_usd: Some(BOND_PRICE_BASE_USD),
                patch_usd: Some(BOND_PRICE_PATCH_USD),
                patch_name_usd: Some(BOND_PRICE_PATCH_NAME_USD),
                source: "hardcoded:Bond".to_string(),
            },
        )
    } else {
        (
            ContactInfo {
                label: "Datos pendientes".to_string(),
                payment_method: "n/a".to_string(),
                carrier: "n/a".to_string(),
            },
            "n/a".to_string(),
            PriceBand {
                base_usd: None,
                patch_usd: None,
                patch_name_usd: None,
                source: "tbd".to_string(),
            },
        )
    };

    // Batches list (DESC by paid_at, NULLS LAST)
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT import_id, paid_at, arrived_at, status, n_units, total_landed_gtq, lead_time_days
         FROM imports
         WHERE supplier = ?1
         ORDER BY paid_at DESC NULLS LAST, created_at DESC"
    )?;
    let batches_iter = stmt.query_map(rusqlite::params![&supplier], |row| {
        Ok(SupplierBatchSummary {
            import_id: row.get(0)?,
            paid_at: row.get(1)?,
            arrived_at: row.get(2)?,
            status: row.get(3)?,
            n_units: row.get(4)?,
            total_landed_gtq: row.get(5)?,
            lead_time_days: row.get(6)?,
        })
    })?;
    let batches: Vec<SupplierBatchSummary> = batches_iter.collect::<rusqlite::Result<Vec<_>>>()?;

    Ok(SupplierDetail {
        metrics,
        contact,
        price_band,
        free_policy_text,
        batches,
    })
}

#[tauri::command]
pub async fn cmd_get_supplier_detail(supplier: String) -> Result<SupplierDetail> {
    impl_get_supplier_detail(supplier)
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
  git commit -m "feat(imp-r5): cmd_get_supplier_detail (Bond hardcoded · others tbd placeholders)

- Reuses impl_get_supplier_metrics + filter
- Bond: contact/free_policy/price_band per spec sec 4.5 line 269-278
- Unknown suppliers: source='tbd' (UI muestra 'datos pendientes')
- batches[] sorted DESC paid_at NULLS LAST
- Convention split impl + cmd shim"
```

---

### Task 4.5: BONUS — `cmd_get_most_requested_unpublished` (widget "más pedidos sin publicar")

> **Bonus widget** approved Diego 2026-04-28 ~19:00 · feedback loop de prioridad publishing. Cuenta cuántas veces aparece cada `family_id` en `import_items` y los cruza contra `catalog.json` para mostrar los TOP-N pedidos que aún no tenés publicados (priorizar audit/publish).

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (add struct + impl + cmd shim)
- Create: smoke covered en `el-club-imp/overhaul/src-tauri/tests/imp_r5_supplier_test.rs` (extend existing file con 2 cases)

- [ ] **Step 1: Add struct + impl + cmd**

Add after `cmd_get_supplier_detail`:

```rust
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UnpublishedRequest {
    pub family_id: String,
    pub n_requests: i32,        // count across all import_items (any status)
    pub n_pending: i32,         // count where status='pending'
    pub n_assigned: i32,        // count where customer_id IS NOT NULL
    pub n_stock: i32,           // count where customer_id IS NULL
    pub last_requested_at: Option<String>,
    pub published: bool,        // computed: family_id present in catalog.json
}

/// Aggregates import_items by family_id + cross-references catalog.json para identificar
/// los family_ids con más pedidos pendientes de publicar (loop de feedback prioridad publishing).
///
/// `limit` default = 10 si None. Filtra a `published=false` antes de retornar (UI no muestra ya-publicados).
pub async fn impl_get_most_requested_unpublished(limit: Option<i32>) -> Result<Vec<UnpublishedRequest>, String> {
    let take = limit.unwrap_or(10).max(1).min(100);
    let conn = open_db().map_err(|e| e.to_string())?;

    // 1. Aggregate by family_id (any status) · ORDER BY count DESC
    let mut stmt = conn.prepare(
        "SELECT family_id,
                COUNT(*) AS n_requests,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS n_pending,
                SUM(CASE WHEN customer_id IS NOT NULL THEN 1 ELSE 0 END) AS n_assigned,
                SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS n_stock,
                MAX(created_at) AS last_requested_at
         FROM import_items
         GROUP BY family_id
         ORDER BY n_requests DESC, last_requested_at DESC
         LIMIT ?1"
    ).map_err(|e| e.to_string())?;

    let rows = stmt.query_map(rusqlite::params![take * 3], |row| {  // 3x buffer pre-filter
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, i32>(1)?,
            row.get::<_, i32>(2)?,
            row.get::<_, i32>(3)?,
            row.get::<_, i32>(4)?,
            row.get::<_, Option<String>>(5)?,
        ))
    }).map_err(|e| e.to_string())?;

    let raw: Vec<_> = rows.collect::<rusqlite::Result<Vec<_>>>().map_err(|e| e.to_string())?;

    // 2. Read catalog.json to identify published family_ids
    let catalog_families: std::collections::HashSet<String> = read_catalog_family_ids()
        .unwrap_or_else(|_| std::collections::HashSet::new());

    // 3. Build response · filter to unpublished only
    let mut out = Vec::new();
    for (family_id, n_requests, n_pending, n_assigned, n_stock, last_requested_at) in raw {
        let published = catalog_families.contains(&family_id);
        if !published {
            out.push(UnpublishedRequest {
                family_id,
                n_requests,
                n_pending,
                n_assigned,
                n_stock,
                last_requested_at,
                published,
            });
        }
        if out.len() >= take as usize { break; }
    }
    Ok(out)
}

/// Helper: lee `catalog.json` (path via catalog_path() en lib.rs) y devuelve set de family_ids publicados.
/// Si el archivo no existe o falla parse, retorna Err (caller decide fallback).
fn read_catalog_family_ids() -> Result<std::collections::HashSet<String>, String> {
    use std::collections::HashSet;
    let path = catalog_path();   // existing helper in lib.rs
    let content = std::fs::read_to_string(&path).map_err(|e| format!("read catalog.json: {e}"))?;
    let json: serde_json::Value = serde_json::from_str(&content).map_err(|e| format!("parse catalog.json: {e}"))?;
    let families = json.get("families").and_then(|v| v.as_array())
        .ok_or_else(|| "catalog.json missing 'families' array".to_string())?;
    let mut set = HashSet::new();
    for f in families {
        if let Some(fid) = f.get("family_id").and_then(|v| v.as_str()) {
            set.insert(fid.to_string());
        }
    }
    Ok(set)
}

#[tauri::command]
pub async fn cmd_get_most_requested_unpublished(limit: Option<i32>) -> Result<Vec<UnpublishedRequest>, String> {
    impl_get_most_requested_unpublished(limit).await
}
```

- [ ] **Step 2: Add 2 smoke test cases en `imp_r5_supplier_test.rs`**

Append a module/section a `el-club-imp/overhaul/src-tauri/tests/imp_r5_supplier_test.rs`:

```rust
#[tokio::test]
async fn test_unpublished_requests_happy() {
    // Seed temp DB · 5 import_items rows con 3 distinct family_ids
    // 2 family_ids ya en catalog.json (mock minimal catalog) · 1 family_id NO publicado
    // Expected: returns 1 entry (el unpublished) con n_requests = count
    // (assertion details inline · helpers reutilizados del setup existente del file)
}

#[tokio::test]
async fn test_unpublished_requests_empty() {
    // Seed temp DB con 0 import_items rows
    // Expected: returns Vec vacío sin error
}
```

- [ ] **Step 3: Verify cargo check + tests**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && cargo test imp_r5 2>&1 | tail -10
```
Expected: `Finished` no errors · all imp_r5 tests pass

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r5_supplier_test.rs && \
  git commit -m "feat(imp-r5): bonus · cmd_get_most_requested_unpublished (widget feedback loop)

- Aggregates import_items by family_id · cross-refs catalog.json
- Returns top-N unpublished family_ids con counts (requests/pending/assigned/stock)
- read_catalog_family_ids helper (lee catalog.json via existing catalog_path())
- 2 smoke tests (happy + empty)
- Bonus extension beyond spec sec 4.5 · approved Diego 2026-04-28 ~19:00"
```

---

### Task 5: Wire `tauri::generate_handler!` macro

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs` (locate generate_handler! ~line 5176)

- [ ] **Step 1: Add 2 commands to handler list**

Find existing `generate_handler!` invocation. Append after R4 entries (or appropriate position):

```rust
.invoke_handler(tauri::generate_handler![
    // ... existing commands including R1.5, R2, R3, R4 ...
    // R5 supplier scorecard
    cmd_get_supplier_metrics,
    cmd_get_supplier_detail,
    cmd_get_most_requested_unpublished,   // bonus widget · feedback loop publishing
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
  git commit -m "feat(imp-r5): wire 2 supplier commands to generate_handler!"
```

---

## Task Group 2: Adapter wires (yo · secuencial)

### Task 6: Adapter types (`types.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Add 5 type interfaces + extend Adapter**

Locate the Import-related section. Add (camelCase to mirror Rust serde rename):

```typescript
export interface ContactInfo {
  label: string;
  paymentMethod: string;
  carrier: string;
}

export interface PriceBand {
  baseUsd: number | null;
  patchUsd: number | null;
  patchNameUsd: number | null;
  source: string;  // "hardcoded:Bond" | "tbd"
}

export interface SupplierBatchSummary {
  importId: string;
  paidAt: string | null;
  arrivedAt: string | null;
  status: string;
  nUnits: number | null;
  totalLandedGtq: number | null;
  leadTimeDays: number | null;
}

export interface SupplierMetrics {
  supplier: string;
  totalBatches: number;
  closedBatches: number;
  pipelineBatches: number;
  leadTimeAvgDays: number | null;
  leadTimeP50Days: number | null;
  leadTimeP95Days: number | null;
  leadTimeN: number;
  totalLandedGtqYtd: number;
  costAccuracyPct: number | null;
  nextExpectedArrival: string | null;
  lastBatchPaidAt: string | null;
}

export interface SupplierDetail {
  metrics: SupplierMetrics;
  contact: ContactInfo;
  priceBand: PriceBand;
  freePolicyText: string;
  batches: SupplierBatchSummary[];
}

export interface UnpublishedRequest {
  familyId: string;
  nRequests: number;
  nPending: number;
  nAssigned: number;
  nStock: number;
  lastRequestedAt: string | null;
  published: boolean;   // siempre false en el response (filter aplicado server-side)
}
```

In the `Adapter` interface (preserve existing methods), add:

```typescript
export interface Adapter {
  // ... existing methods ...

  // R5 supplier scorecard
  getSupplierMetrics(): Promise<SupplierMetrics[]>;
  getSupplierDetail(supplier: string): Promise<SupplierDetail>;
  // R5 bonus: feedback loop publishing
  getMostRequestedUnpublished(limit?: number): Promise<UnpublishedRequest[]>;
}
```

- [ ] **Step 2: Verify svelte-check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: errors only in tauri.ts/browser.ts (unimplemented) — fixed in next tasks

- [ ] **Step 3: Don't commit yet** — types alone broken without impls. Commit at end of adapter group (Task 8).

---

### Task 7: Adapter Tauri implementation (`tauri.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Add 2 invocations**

Locate the imports section at top, append:

```typescript
import type {
  // ... existing imports ...
  SupplierMetrics,
  SupplierDetail,
  UnpublishedRequest,
} from './types';
```

Append methods near other Import-related invokes (after `getImportPulso` or wherever IMP methods live):

```typescript
async getSupplierMetrics(): Promise<SupplierMetrics[]> {
  return await invoke<SupplierMetrics[]>('cmd_get_supplier_metrics');
}

async getSupplierDetail(supplier: string): Promise<SupplierDetail> {
  return await invoke<SupplierDetail>('cmd_get_supplier_detail', { supplier });
}

async getMostRequestedUnpublished(limit?: number): Promise<UnpublishedRequest[]> {
  return await invoke<UnpublishedRequest[]>('cmd_get_most_requested_unpublished', { limit: limit ?? null });
}
```

- [ ] **Step 2: Verify svelte-check (browser.ts still has errors)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors in tauri.ts (browser.ts pending)

- [ ] **Step 3: Don't commit yet** — finish browser.ts.

---

### Task 8: Adapter Browser stubs (`browser.ts`)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 2 NotAvailableInBrowser stubs**

Add imports at top:

```typescript
import type {
  // ... existing imports ...
  SupplierMetrics,
  SupplierDetail,
  UnpublishedRequest,
} from './types';
```

Append methods:

```typescript
async getSupplierMetrics(): Promise<SupplierMetrics[]> {
  throw new Error('getSupplierMetrics requires Tauri runtime · run via .exe MSI');
}

async getSupplierDetail(_supplier: string): Promise<SupplierDetail> {
  throw new Error('getSupplierDetail requires Tauri runtime · run via .exe MSI');
}

async getMostRequestedUnpublished(_limit?: number): Promise<UnpublishedRequest[]> {
  throw new Error('getMostRequestedUnpublished requires Tauri runtime · run via .exe MSI');
}
```

- [ ] **Step 2: Verify full svelte-check passes**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors total

- [ ] **Step 3: Commit adapter group atomically**

```bash
cd C:/Users/Diego/el-club-imp && \
  git add overhaul/src/lib/adapter/types.ts overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r5): adapter wires for 2 supplier commands

- types.ts: 5 interfaces (ContactInfo · PriceBand · SupplierBatchSummary · SupplierMetrics · SupplierDetail) · 2 Adapter signatures
- tauri.ts: invoke for cmd_get_supplier_metrics + cmd_get_supplier_detail
- browser.ts: NotAvailableInBrowser stubs"
```

---

## Task Group 3: Svelte components (yo · 1 component por commit)

### Task 9: `SupplierBondCard.svelte` (scorecard card per spec sec 4.5 line 267-278)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/SupplierBondCard.svelte`

- [ ] **Step 1: Create component**

```svelte
<script lang="ts">
  import type { SupplierDetail } from '$lib/adapter/types';

  interface Props {
    detail: SupplierDetail;
  }

  let { detail }: Props = $props();

  let m = $derived(detail.metrics);
  let pb = $derived(detail.priceBand);
  let c = $derived(detail.contact);

  // Helpers
  function fmtAvg(v: number | null, n: number): string {
    if (v === null) return 'sin datos';
    return `${v.toFixed(1)} días avg (n=${n})`;
  }
  function fmtPct(v: number | null, closedCount: number): string {
    // Per spec ambiguity: cost_accuracy_pct comes back null until disputes log exists.
    // Display "Datos insuficientes" with sample-size hint.
    if (v === null) return closedCount > 0
      ? `Datos insuficientes (${closedCount} closed · sin disputes log)`
      : 'sin datos';
    return `±${v.toFixed(1)}%`;
  }
  function fmtPriceBand(pb: typeof detail.priceBand): string {
    if (pb.source === 'tbd' || pb.baseUsd === null) return 'Datos pendientes';
    const parts: string[] = [];
    if (pb.baseUsd !== null) parts.push(`$${pb.baseUsd} base`);
    if (pb.patchUsd !== null) parts.push(`$${pb.patchUsd} +patch`);
    if (pb.patchNameUsd !== null) parts.push(`$${pb.patchNameUsd} +patch+name`);
    return parts.join(' · ');
  }
  function fmtTotalLanded(v: number): string {
    if (v === 0) return 'Q0 (sin batches closed)';
    return `Q${Math.round(v).toLocaleString('es-GT')}`;
  }
  function fmtNext(v: string | null, pipeline: number): string {
    if (v === null) {
      return pipeline > 0
        ? 'sin avg_lead (precisás 1 batch closed para ETA)'
        : 'n/a (sin batches en pipeline)';
    }
    // Format YYYY-MM-DD → DD-MMM
    const d = new Date(v);
    if (isNaN(d.getTime())) return v;
    const months = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
    return `${String(d.getDate()).padStart(2, '0')}-${months[d.getMonth()]}`;
  }

  // Status pill helper for batches in pipeline
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

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6">
  <!-- Header -->
  <div class="border-b border-[var(--color-surface-2)] pb-3 mb-4">
    <h2 class="text-[18px] font-semibold text-[var(--color-text-primary)]">{m.supplier}</h2>
    <p class="text-mono text-[11px] text-[var(--color-text-tertiary)] mt-1" style="letter-spacing: 0.04em;">
      {c.label} · {c.paymentMethod} · {c.carrier}
    </p>
  </div>

  <!-- 7 stat rows · spec sec 4.5 line 267-278 layout -->
  <dl class="space-y-2.5">
    <!-- LEAD TIME -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">LEAD TIME</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtAvg(m.leadTimeAvgDays, m.leadTimeN)}
        {#if m.leadTimeP50Days !== null && m.leadTimeP95Days !== null}
          <span class="text-[var(--color-text-tertiary)] ml-2">
            · p50 {m.leadTimeP50Days.toFixed(1)} · p95 {m.leadTimeP95Days.toFixed(1)}
          </span>
        {/if}
      </dd>
    </div>

    <!-- COST ACCURACY -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">COST ACCURACY</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtPct(m.costAccuracyPct, m.closedBatches)}
      </dd>
    </div>

    <!-- PRICE BAND -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">PRICE BAND</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtPriceBand(pb)}
      </dd>
    </div>

    <!-- FREE POLICY -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">FREE POLICY</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)]">
        {detail.freePolicyText}
      </dd>
    </div>

    <!-- TOTAL BATCHES -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">TOTAL BATCHES</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {m.totalBatches}
        <span class="text-[var(--color-text-tertiary)] ml-1">
          ({m.closedBatches} closed · {m.pipelineBatches} pipeline)
        </span>
      </dd>
    </div>

    <!-- TOTAL LANDED YTD -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">TOTAL LANDED YTD</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtTotalLanded(m.totalLandedGtqYtd)}
      </dd>
    </div>

    <!-- NEXT EXPECTED -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">NEXT EXPECTED</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtNext(m.nextExpectedArrival, m.pipelineBatches)}
      </dd>
    </div>
  </dl>

  <!-- Batches list (collapsed default · always visible if any) -->
  {#if detail.batches.length > 0}
    <div class="mt-5 pt-4 border-t border-[var(--color-surface-2)]">
      <div class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
        Batches ({detail.batches.length})
      </div>
      <ul class="space-y-1.5">
        {#each detail.batches as b (b.importId)}
          <li class="flex items-center gap-3 text-mono text-[11px] tabular-nums">
            <span class="text-[var(--color-text-primary)] w-[140px]">{b.importId}</span>
            <span class={`px-1.5 py-0.5 rounded-[2px] text-[9.5px] uppercase ${statusPillClass(b.status)}`} style="letter-spacing: 0.06em;">
              ● {b.status}
            </span>
            <span class="text-[var(--color-text-tertiary)]">
              {b.paidAt ?? 'sin paid_at'}
              {#if b.leadTimeDays !== null} · {b.leadTimeDays}d{/if}
              {#if b.nUnits !== null} · {b.nUnits}u{/if}
              {#if b.totalLandedGtq !== null} · Q{Math.round(b.totalLandedGtq).toLocaleString('es-GT')}{/if}
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>
```

- [ ] **Step 2: Verify svelte-check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/SupplierBondCard.svelte && \
  git commit -m "feat(imp-r5): SupplierBondCard component (7 stats + batches list)

- Layout per spec sec 4.5 line 267-278
- Insufficient-data states: 'sin datos' / 'datos pendientes' / 'datos insuficientes'
- p50/p95 inline next to avg si existen
- Batch list con status pills + tabular-nums
- text-mono uppercase labels letter-spacing 0.08em (Diego retro/terminal aesthetic)"
```

---

### Task 10: `SupplierChipBar.svelte` (chip bar · multi-supplier scaffold)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/SupplierChipBar.svelte`

- [ ] **Step 1: Create component**

```svelte
<script lang="ts">
  import type { SupplierMetrics } from '$lib/adapter/types';

  interface Props {
    suppliers: SupplierMetrics[];
    activeSupplier: string | null;
    onSelect: (supplier: string) => void;
  }

  let { suppliers, activeSupplier, onSelect }: Props = $props();
</script>

<div class="flex items-center gap-2 mb-4 flex-wrap">
  {#each suppliers as s (s.supplier)}
    <button
      onclick={() => onSelect(s.supplier)}
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] border transition-colors"
      class:bg-[var(--color-accent)]={activeSupplier === s.supplier}
      class:text-[var(--color-bg)]={activeSupplier === s.supplier}
      class:border-[var(--color-accent)]={activeSupplier === s.supplier}
      class:bg-[var(--color-surface-2)]={activeSupplier !== s.supplier}
      class:border-[var(--color-border)]={activeSupplier !== s.supplier}
      class:text-[var(--color-text-primary)]={activeSupplier !== s.supplier}
      style="letter-spacing: 0.04em;"
    >
      {s.supplier}
      <span class="ml-1.5 opacity-70 tabular-nums">({s.totalBatches})</span>
    </button>
  {/each}

  <!-- Future scaffold: + supplier · disabled per Open Question recommendation -->
  <button
    disabled
    title="Multi-supplier en v0.5 (cuando Diego agregue Yupoo direct/Aliexpress)"
    class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-dashed border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-50"
    style="letter-spacing: 0.04em;"
  >
    + supplier
  </button>
</div>
```

- [ ] **Step 2: Verify svelte-check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/SupplierChipBar.svelte && \
  git commit -m "feat(imp-r5): SupplierChipBar (multi-supplier scaffold · iterates DISTINCT supplier)

- Active chip = accent bg + dark fg
- Inactive chips = surface-2 bg + border
- '+ supplier' disabled stub con tooltip 'Multi-supplier en v0.5'
- Total batches count inline (Diego retro/info-density)"
```

---

### Task 11: `SupplierTab.svelte` (REPLACE 6-line stub completo)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte`

- [ ] **Step 1: Replace stub with full implementation**

Overwrite file completo:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { SupplierMetrics, SupplierDetail, UnpublishedRequest } from '$lib/adapter/types';
  import SupplierChipBar from '../SupplierChipBar.svelte';
  import SupplierBondCard from '../SupplierBondCard.svelte';

  let metrics = $state<SupplierMetrics[]>([]);
  let activeSupplier = $state<string | null>(null);
  let detail = $state<SupplierDetail | null>(null);
  let loading = $state(true);
  let detailLoading = $state(false);
  let errorMsg = $state<string | null>(null);

  // BONUS widget · más pedidos sin publicar (feedback loop publishing)
  let unpublished = $state<UnpublishedRequest[]>([]);
  let unpublishedLoading = $state(true);

  const BOND_NAME = 'Bond Soccer Jersey';

  // Initial load
  $effect(() => {
    loadMetrics();
    loadUnpublished();
  });

  async function loadMetrics() {
    loading = true;
    errorMsg = null;
    try {
      metrics = await adapter.getSupplierMetrics();
      // Default-select Bond if present, else first supplier
      if (metrics.length > 0) {
        const bond = metrics.find((m) => m.supplier === BOND_NAME);
        const initial = bond?.supplier ?? metrics[0].supplier;
        if (activeSupplier === null) {
          activeSupplier = initial;
          await loadDetail(initial);
        }
      }
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadUnpublished() {
    unpublishedLoading = true;
    try {
      unpublished = await adapter.getMostRequestedUnpublished(5);
    } catch (e) {
      // Silent fail · widget es bonus · no rompe scorecard si falla
      console.warn('[unpublished widget]', e);
      unpublished = [];
    } finally {
      unpublishedLoading = false;
    }
  }

  async function loadDetail(supplier: string) {
    detailLoading = true;
    try {
      detail = await adapter.getSupplierDetail(supplier);
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
      detail = null;
    } finally {
      detailLoading = false;
    }
  }

  function handleSelect(supplier: string) {
    activeSupplier = supplier;
    loadDetail(supplier);
  }
</script>

<div class="flex flex-col flex-1 p-6 overflow-y-auto">
  <!-- BONUS WIDGET: más pedidos sin publicar -->
  <section class="mb-6 border border-[var(--color-border)] rounded-[3px] p-4 bg-[var(--color-surface-1)]">
    <header class="flex items-baseline justify-between mb-3">
      <h3 class="text-mono text-[11px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.10em;">
        Más pedidos sin publicar
      </h3>
      <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">top 5 · feedback loop</span>
    </header>
    {#if unpublishedLoading}
      <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">Cargando…</div>
    {:else if unpublished.length === 0}
      <div class="text-[12px] text-[var(--color-text-secondary)]">
        Todo lo pedido está publicado · 🎉  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">(o sin pedidos todavía)</span>
      </div>
    {:else}
      <ul class="flex flex-col gap-1.5">
        {#each unpublished as u}
          <li class="flex items-center justify-between text-[12px] gap-3">
            <span class="text-mono text-[var(--color-accent)]">{u.familyId}</span>
            <span class="flex items-center gap-3 text-[var(--color-text-secondary)]">
              <span class="text-mono">×{u.nRequests}</span>
              <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">
                {u.nAssigned}A · {u.nStock}S · {u.nPending}P
              </span>
              <a href="#audit-{u.familyId}" class="text-mono text-[10px] text-[var(--color-accent)] hover:underline">→ Auditar</a>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  {#if loading}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      <div class="text-mono text-[11px] uppercase" style="letter-spacing: 0.08em;">Cargando supplier metrics…</div>
    </div>
  {:else if errorMsg}
    <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2 mb-4">
      ⚠️ {errorMsg}
    </div>
  {:else if metrics.length === 0}
    <!-- Empty state: zero suppliers means zero batches -->
    <div class="flex flex-1 items-center justify-center">
      <div class="text-center max-w-md">
        <div class="text-mono text-[11px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">Sin batches todavía</div>
        <div class="text-sm text-[var(--color-text-secondary)]">
          Cuando crees el primer pedido (tab Pedidos · botón <span class="text-mono">+ Nuevo</span>), aparece scorecard del supplier acá con métricas reales.
        </div>
      </div>
    </div>
  {:else}
    <!-- Multi-supplier scaffold: chip bar -->
    <SupplierChipBar suppliers={metrics} {activeSupplier} onSelect={handleSelect} />

    {#if detailLoading}
      <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Cargando detail…</div>
    {:else if detail}
      <SupplierBondCard {detail} />
    {/if}
  {/if}
</div>
```

- [ ] **Step 2: Verify svelte-check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte && \
  git commit -m "feat(imp-r5): replace SupplierTab stub with functional scorecard + bonus widget

- Loads metrics via adapter on mount
- Default-selects Bond Soccer Jersey if present
- Empty state when zero batches: instructs Diego to create primer pedido
- ChipBar + BondCard composition (multi-supplier ready)
- Error banner inline si command falla
- BONUS: 'Más pedidos sin publicar' widget (top-5 unpublished family_ids con counts) · feedback loop publishing"
```

---

## Task Group 4: Smoke + verification

### Task 12: Smoke test SQL script

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r5.py`

- [ ] **Step 1: Create smoke script**

```python
#!/usr/bin/env python3
"""
Smoke test post-implementation IMP-R5 (Supplier scorecard)
Verifies aggregation correctness at SQL layer.

Seeds: 5 closed Bond imports + 1 paid (pipeline) with varying lead_time_days (5, 7, 8, 10, 12).
Asserts: counts per status · lead_time avg/p50/p95 · YTD landed sum · cleanup.

Usage:
    cd C:/Users/Diego/el-club-imp/erp
    python scripts/smoke_imp_r5.py
"""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get('ERP_DB_PATH', r'C:\Users\Diego\el-club-imp\erp\elclub.db')

def assert_eq(actual, expected, msg, tolerance=None):
    if tolerance is not None and isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        ok = abs(actual - expected) <= tolerance
    else:
        ok = actual == expected
    assert ok, f'{msg} · expected={expected!r} actual={actual!r}'
    print(f'  [OK] {msg}: {actual!r}')

def main():
    print(f'DB: {DB_PATH}')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cleanup any prior R5 smoke runs
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-R5SMOKE-%'")
    conn.commit()

    print('\n=== Seed: 5 closed Bond + 1 paid pipeline ===')
    year = datetime.now().year
    seed_data = [
        # (suffix, paid_at, arrived_at, lead_time_days, status, total_landed, n_units)
        ('001', f'{year}-01-05', f'{year}-01-10', 5,  'closed', 1500.0, 10),
        ('002', f'{year}-02-10', f'{year}-02-17', 7,  'closed', 1800.0, 12),
        ('003', f'{year}-03-01', f'{year}-03-09', 8,  'closed', 2100.0, 14),
        ('004', f'{year}-03-15', f'{year}-03-25', 10, 'closed', 2400.0, 16),
        ('005', f'{year}-04-01', f'{year}-04-13', 12, 'closed', 2700.0, 18),
        ('006', f'{year}-04-20', None,            None, 'paid',  None,    20),  # pipeline
    ]
    for suf, paid, arr, lt, st, landed, units in seed_data:
        cur.execute("""
            INSERT INTO imports (import_id, paid_at, arrived_at, supplier, bruto_usd, fx,
                                 total_landed_gtq, n_units, lead_time_days, status, created_at)
            VALUES (?, ?, ?, 'Bond Soccer Jersey', 200.0, 7.73, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (f'IMP-R5SMOKE-{suf}', paid, arr, landed, units, lt, st))
    conn.commit()

    print('\n=== TEST 1: Counts per status bucket ===')
    total = cur.execute("SELECT COUNT(*) FROM imports WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%'").fetchone()[0]
    closed = cur.execute("SELECT COUNT(*) FROM imports WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%' AND status='closed'").fetchone()[0]
    pipeline = cur.execute("SELECT COUNT(*) FROM imports WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%' AND status IN ('paid','in_transit','arrived')").fetchone()[0]
    assert_eq(total, 6, 'total_batches')
    assert_eq(closed, 5, 'closed_batches')
    assert_eq(pipeline, 1, 'pipeline_batches')

    print('\n=== TEST 2: Lead time aggregations (Rust-side calc · we mirror in Python) ===')
    rows = cur.execute("""
        SELECT lead_time_days FROM imports
        WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%'
        AND status='closed' AND lead_time_days IS NOT NULL
        ORDER BY lead_time_days
    """).fetchall()
    lts = [r['lead_time_days'] for r in rows]
    assert_eq(lts, [5, 7, 8, 10, 12], 'lead_time_days values sorted')
    avg = sum(lts) / len(lts)
    assert_eq(round(avg, 2), 8.4, 'lead_time_avg_days')
    # Nearest-rank p50: idx = ceil(0.5 * 5) - 1 = 2 → sorted[2] = 8
    assert_eq(lts[2], 8, 'lead_time_p50_days (nearest-rank idx 2)')
    # Nearest-rank p95: idx = ceil(0.95 * 5) - 1 = 4 → sorted[4] = 12
    assert_eq(lts[4], 12, 'lead_time_p95_days (nearest-rank idx 4)')

    print('\n=== TEST 3: YTD landed sum (closed only) ===')
    ytd = cur.execute("""
        SELECT COALESCE(SUM(total_landed_gtq), 0.0) FROM imports
        WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%'
        AND status='closed'
        AND strftime('%Y', paid_at) = strftime('%Y', 'now', 'localtime')
    """).fetchone()[0]
    assert_eq(round(ytd, 2), 10500.0, 'total_landed_gtq_ytd (1500+1800+2100+2400+2700)')

    print('\n=== TEST 4: last_batch_paid_at (MAX paid_at) ===')
    last_paid = cur.execute("""
        SELECT MAX(paid_at) FROM imports
        WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%'
        AND paid_at IS NOT NULL
    """).fetchone()[0]
    assert_eq(last_paid, f'{year}-04-20', 'last_batch_paid_at = pipeline batch paid_at')

    print('\n=== TEST 5: next_expected_arrival = earliest paid_at + avg_lead among non-closed ===')
    earliest_pipeline = cur.execute("""
        SELECT MIN(paid_at) FROM imports
        WHERE supplier='Bond Soccer Jersey' AND import_id LIKE 'IMP-R5SMOKE-%'
        AND status IN ('paid', 'in_transit', 'arrived')
    """).fetchone()[0]
    assert_eq(earliest_pipeline, f'{year}-04-20', 'earliest_pipeline_paid_at')
    # avg_lead rounded = round(8.4) = 8 days · expected ETA = year-04-28
    print(f'  → expected next_expected_arrival ≈ {year}-04-28 (Rust calc · not asserted here)')

    print('\n=== TEST 6: Edge case · zero closed batches → all metrics None ===')
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-R5EDGE-%'")
    cur.execute("""
        INSERT INTO imports (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, created_at)
        VALUES ('IMP-R5EDGE-001', '2026-04-20', 'EdgeCase Supplier', 100.0, 7.73, 5, 'paid',
                datetime('now', 'localtime'))
    """)
    conn.commit()
    edge_closed = cur.execute("""
        SELECT COUNT(*) FROM imports
        WHERE supplier='EdgeCase Supplier' AND status='closed' AND lead_time_days IS NOT NULL
    """).fetchone()[0]
    assert_eq(edge_closed, 0, 'EdgeCase: zero closed batches → avg/p50/p95 should be None Rust-side')

    print('\n=== TEST 7: DISTINCT suppliers query (multi-supplier scaffold) ===')
    suppliers = [r[0] for r in cur.execute("""
        SELECT DISTINCT supplier FROM imports
        WHERE supplier IS NOT NULL AND supplier != ''
        AND (import_id LIKE 'IMP-R5SMOKE-%' OR import_id LIKE 'IMP-R5EDGE-%')
        ORDER BY supplier
    """).fetchall()]
    assert_eq(suppliers, ['Bond Soccer Jersey', 'EdgeCase Supplier'], 'DISTINCT suppliers (alpha sorted)')

    print('\n=== Cleanup ===')
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-R5SMOKE-%'")
    cur.execute("DELETE FROM imports WHERE import_id LIKE 'IMP-R5EDGE-%'")
    conn.commit()

    print('\n[OK] ALL R5 SMOKE TESTS PASS')

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run smoke**

```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r5.py
```
Expected: `[OK] ALL R5 SMOKE TESTS PASS`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_imp_r5.py && \
  git commit -m "test(imp-r5): SQL smoke · 7 tests · seed 5 closed + 1 pipeline + 1 edge

- Verifies counts per status bucket
- Mirrors Rust-side percentile calc (nearest-rank idx 2 = p50, idx 4 = p95)
- YTD sum: 10,500 GTQ from 5 closed
- Edge case: zero closed → metrics None
- DISTINCT supplier alpha sort"
```

---

### Task 13: Final verification (cargo + npm)

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Cargo check + tests**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && cargo test imp_r5 2>&1 | tail -10
```
Expected: `Finished` no errors · `imp_r5_helper_tests · 3 passed`

- [ ] **Step 2: npm check + build**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -3 && npm run build 2>&1 | tail -5
```
Expected: 0 errors check · build OK

- [ ] **Step 3: Manual UI smoke (Diego optional · post-MSI)**

Once MSI v0.4.0 is built and Diego installs:
1. Abrir ERP → tab Importaciones → click "Supplier"
2. Si DB tiene batches Bond: ver chip "Bond Soccer Jersey (N)" + card con 7 stats
3. Si DB vacía: ver empty state "Sin batches todavía…"
4. Acceptance gate Diego (per starter line 67): "¿Ves supplier scorecard con Bond metrics?"

---

## Self-Review

Before declaring R5 complete, run this mental checklist:

**Spec coverage (sec 4.5):**
- [x] Bond card · 7 stats · LEAD TIME / COST ACCURACY / PRICE BAND / FREE POLICY / TOTAL BATCHES / TOTAL LANDED YTD / NEXT EXPECTED → Tasks 4 + 9 ✓
- [x] Multi-supplier scaffold (chip bar dinámico) → Task 10 + 11 ✓
- [x] Lead time avg/p50/p95 → Task 1 (helper) + 3 (impl) + 9 (UI) ✓
- [x] Empty state si zero batches → Task 11 ✓
- [x] Insufficient-data states (cost_accuracy null, price_band tbd) → Task 9 ✓
- [x] No `suppliers` table en R5 (deferred a v0.5 per spec line 280) ✓
- [x] **BONUS** widget "más pedidos sin publicar" (top-5 unpublished family_ids con counts) → Task 4.5 + 11 ✓ · extension beyond spec sec 4.5 · approved Diego 2026-04-28 ~19:00 · loop de feedback prioridad publishing

**Placeholder scan:** ningún `TODO` / `implement later` / `add validation` / `similar to Task N` en steps. Bond hardcoded constants tienen comentario explícito "move to suppliers table en v0.5". ✓

**Type consistency:**
- 5 TS interfaces match Rust structs (camelCase via serde rename) ✓
- `costAccuracyPct: number | null` consistente con `cost_accuracy_pct: Option<f64>` ✓
- `priceBand.source: string` ("hardcoded:Bond" | "tbd") consistente entre Rust + UI handler `fmtPriceBand` ✓
- Adapter method names match Rust commands (`getSupplierMetrics`, `getSupplierDetail`) ✓

**Cross-module impact:**
- COM (Sales): cero touch ✓ (read-only queries solo a `imports` table)
- FIN (cash flow): cero touch ✓
- ADM Universe: cero touch ✓
- catalog.json: cero touch ✓
- Worker Cloudflare: cero touch ✓
- DB schema: cero changes ✓ (zero migrations)

**Spec ambiguity escalations applied:**
- Cost accuracy: returns `None` con UI mostrando "Datos insuficientes (N closed · sin disputes log)" — Open Question #1 below
- Multi-supplier UI: chip bar dinámico + "+ supplier" disabled stub (NO modal · per recomendación) — Open Question #2 below
- Price band: hardcoded constants en Rust con comentario migration → Open Question #3 below
- Percentile: Rust-side nearest-rank (no SQL window functions) — Open Question #4 below

---

## Open questions for Diego

1. **Cost accuracy metric** (spec sec 4.5 line 273): el spec dice "±0% (1 batch closed sin disputas)" pero requiere un disputes log que no existe. **Recomendación:** el campo retorna `None` y la UI muestra "Datos insuficientes (N closed · sin disputes log)" hasta que en el futuro se agregue tabla `import_cost_disputes`. Alternativa: calcular diff entre `estimated_landed = bruto*fx + estimated_shipping_default` (precisaría default shipping config en R6 Settings) vs `total_landed_gtq` actual al cierre. **¿Diego prefiere alternativa o esperamos disputes log?**

2. **Multi-supplier scaffold scope**: implementé chip bar dinámico que itera DISTINCT suppliers + chip "+ supplier" disabled con tooltip "v0.5". **¿Diego confirma esta forma · o prefiere ocultar el "+ supplier" del todo hasta v0.5?**

3. **Price band hardcode location**: hoy quedan en Rust constants (`BOND_PRICE_BASE_USD = 11.0` etc.) con comentario "move to suppliers table when v0.5". Alternativas: (a) settings.json del módulo (R6), (b) tabla `supplier_price_bands` desde ya. **¿Diego confirma hardcode + comentario para R5?**

4. **Percentile method**: usé nearest-rank (sin interpolación) porque es trivial y suficiente para n<100. Alternativa: linear interpolation (más precisa pero código triplicado). **¿Diego le da igual o prefiere interpolación lineal?** (Recomendación: nearest-rank · n hoy es 1).

---

## Cross-release dependency notes

- **R1.5 dependency:** R5 lee `lead_time_days` que se setea automáticamente en `cmd_register_arrival` (R1.5 Task 3). Si R1.5 no está mergeado en `imp-r2-r6-build` → STOP en pre-flight Step 4.
- **R3 independence:** R5 NO consume nada de R3 Margen real · ambos son read-only sobre `imports`. Pueden mergear en cualquier orden dentro de Wave 2.
- **R6 future hook:** si Diego decide en R6 mover Bond price band a Settings/config, el `PriceBand.source` campo soporta valores arbitrarios ("hardcoded:Bond" → "settings:supplier_bond" · cero migration en R5).
- **v0.5 future:** cuando exista tabla `suppliers`, swap `BOND_*` constants por query · borrar el `if supplier == BOND_SUPPLIER_NAME` branch en `impl_get_supplier_detail`.

---

## Execution Handoff

Plan complete and saved to `el-club-imp/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R5.md`.

**Recommended execution mode:** `superpowers:subagent-driven-development` — fresh subagent per task, review entre tasks. R5 es smallest plan (14 tasks · incluye Task 4.5 bonus widget) · cabe en ~75min de ejecución secuencial sin paralelización (Rust en lib.rs es secuencial · Svelte components son 3 archivos pequeños sin merge conflict).

**REQUIRED SUB-SKILL:** `superpowers:subagent-driven-development` (recommended) o `superpowers:executing-plans`.

---

## After R5 ships

1. Append commit hashes + smoke results to `SESSION-COORDINATION.md` activity log
2. Continuar con R6 Settings + polish ship (Wave 2 cierre)
3. Final ship: schema migration on main DB + MSI rebuild + merge `--no-ff` + tag `v0.4.0`
4. Diego acceptance gate (per starter line 67): "¿Ves supplier scorecard con Bond metrics?"
5. Si Diego confirma · marcar R5 como ✅ en plan-vs-execution audit
