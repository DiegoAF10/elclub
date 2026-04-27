# Comercial R6: Sales Attribution Loop Closure

**Branch:** `comercial-design` (continuación R5 v0.1.31)
**Target:** ERP v0.1.32

## Goal

Populate `sales_attribution` table automatically. Sin esto, CampaignDetailModal "sales atribuidas" sale siempre vacío y el funnel no cierra el loop ads→conversation→sale.

## Scope

### Incluido
- **Auto-attribute on sale creation**: cuando `cmd_create_manual_order` inserta una sale, lookup customer.phone → leads.source_campaign_id, si match INSERT sales_attribution.
- **Backfill** retroactivo: handler que recorre todas las sales sin attribution + las attributa via lead lookup.
- **Settings button**: "Backfill atribución" + result toast.
- **OrderDetailModal display** (read-only): mostrar campaña atribuida si existe.

### NO incluido (deferred R7+)
- Manual edit/override UI (cambiar attribution post-hoc desde modal)
- Multi-campaign attribution (1 sale → N campaigns)
- Attribution via UTM / referrer (web orders sin lead)
- Worker `/api/coupons/generate` update (out of repo)

## Decisiones

| # | Decisión | Resolución |
|---|----------|------------|
| 1 | Match strategy | phone exact match (customer.phone == lead.phone) |
| 2 | Multi-lead per phone | Toma el lead más reciente con source_campaign_id |
| 3 | Auto vs manual signal | `sales_attribution.source = 'auto_via_lead'` para distinguir |
| 4 | Backfill scope | Solo sales sin attribution previa (idempotente) |
| 5 | Edit UX | Read-only en OrderDetailModal (R7+ lleva edit) |

## Tasks

### Task 1: Bridge handler `cmd_backfill_sales_attribution`

**File:** `erp/scripts/erp_rust_bridge.py`

```python
def cmd_backfill_sales_attribution(args):
    """Backfill retroactivo: for each sale without attribution, lookup phone → lead.source_campaign_id.
    Idempotent — skips sales that already have attribution rows.
    """
    from db import get_conn

    conn = get_conn()
    inserted = 0
    skipped_already_attributed = 0
    skipped_no_match = 0
    errors = []

    try:
        sales = conn.execute("""
            SELECT s.sale_id, c.phone
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE NOT EXISTS (SELECT 1 FROM sales_attribution sa WHERE sa.sale_id = s.sale_id)
              AND c.phone IS NOT NULL AND c.phone != ''
        """).fetchall()

        for sale_id, phone in sales:
            try:
                lead = conn.execute("""
                    SELECT source_campaign_id, source_campaign_name
                    FROM leads
                    WHERE phone = ? AND source_campaign_id IS NOT NULL
                    ORDER BY first_contact_at DESC
                    LIMIT 1
                """, (phone,)).fetchone()
                if not lead:
                    skipped_no_match += 1
                    continue
                conn.execute("""
                    INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, created_at)
                    VALUES (?, ?, ?, 'auto_via_lead', datetime('now', 'localtime'))
                """, (sale_id, lead[0], lead[1]))
                inserted += 1
            except Exception as ie:
                errors.append(f"sale {sale_id}: {ie}")

        # Already-attributed count for reporting
        skipped_already_attributed = conn.execute("""
            SELECT COUNT(*) FROM sales s WHERE EXISTS (
                SELECT 1 FROM sales_attribution sa WHERE sa.sale_id = s.sale_id
            )
        """).fetchone()[0]

        conn.commit()
        return {"ok": True, "inserted": inserted, "skippedNoMatch": skipped_no_match, "skippedAlreadyAttributed": skipped_already_attributed, "errors": errors}
    finally:
        conn.close()
```

NOTE: Verify `leads` schema has `source_campaign_name` column. If not, drop that field.

### Task 2: Modify `cmd_create_manual_order` for auto-attribution

After successful sale INSERT (after `conn.commit()` in existing handler), add inline auto-attribute logic:

```python
# R6: auto-attribute via phone → lead.source_campaign_id lookup
try:
    cust_phone = conn.execute("SELECT phone FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    if cust_phone and cust_phone[0]:
        lead = conn.execute("""
            SELECT source_campaign_id, source_campaign_name
            FROM leads WHERE phone = ? AND source_campaign_id IS NOT NULL
            ORDER BY first_contact_at DESC LIMIT 1
        """, (cust_phone[0],)).fetchone()
        if lead:
            conn.execute("""
                INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, created_at)
                VALUES (?, ?, ?, 'auto_via_lead', datetime('now', 'localtime'))
            """, (sale_id, lead[0], lead[1]))
            conn.commit()
except Exception as e:
    # don't fail sale creation on attribution error
    pass
```

### Task 3: Bridge handler `cmd_get_sale_attribution`

```python
def cmd_get_sale_attribution(args):
    """Returns attribution row for a sale, or null."""
    from db import get_conn

    sale_id = args.get("saleId")
    if not sale_id:
        return {"ok": False, "error": "saleId required"}

    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT id, sale_id, ad_campaign_id, ad_campaign_name, source, note, created_at
            FROM sales_attribution WHERE sale_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (sale_id,)).fetchone()
        if not row:
            return {"ok": True, "attribution": None}
        return {"ok": True, "attribution": {
            "id": row[0],
            "saleId": row[1],
            "adCampaignId": row[2],
            "adCampaignName": row[3],
            "source": row[4],
            "note": row[5],
            "createdAt": row[6],
        }}
    finally:
        conn.close()
```

Register all 3 in COMMANDS dict (2 new — backfill + get; cmd_create_manual_order modification doesn't add an entry).

### Task 4: Rust + Adapter

**lib.rs:**

```rust
#[tauri::command]
async fn comercial_backfill_sales_attribution() -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "backfill_sales_attribution" });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[tauri::command]
async fn comercial_get_sale_attribution(sale_id: i64) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_sale_attribution", "saleId": sale_id });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("attribution").cloned().unwrap_or(Value::Null))
}
```

Register in `tauri::generate_handler!`.

**comercial.ts** — add type:
```typescript
export interface SaleAttribution {
  id: number;
  saleId: number;
  adCampaignId: string | null;
  adCampaignName: string | null;
  source: string | null;
  note: string | null;
  createdAt: string;
}

export interface BackfillAttributionResult {
  ok: boolean;
  inserted: number;
  skippedNoMatch: number;
  skippedAlreadyAttributed: number;
  errors: string[];
}
```

**types.ts** — extend interface Adapter:
```typescript
backfillSalesAttribution(): Promise<BackfillAttributionResult>;
getSaleAttribution(saleId: number): Promise<SaleAttribution | null>;
```

**tauri.ts** — impls:
```typescript
async backfillSalesAttribution() {
  return invoke<BackfillAttributionResult>('comercial_backfill_sales_attribution');
},
async getSaleAttribution(saleId: number) {
  const result = await invoke<unknown>('comercial_get_sale_attribution', { saleId });
  return (result as SaleAttribution | null) ?? null;
},
```

**browser.ts**:
```typescript
async backfillSalesAttribution() {
  throw new NotAvailableInBrowser('backfillSalesAttribution');
},
async getSaleAttribution() {
  return null;
},
```

### Task 5: SettingsTab — Backfill button

Add a new section after Meta Ads section:

```svelte
<section class="settings-section mt-6">
  <h2 class="text-display mb-2 text-[10px] text-[var(--color-text-tertiary)]">Atribución de Sales</h2>
  <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
    <div class="flex items-center justify-between gap-3">
      <div class="flex-1">
        <div class="text-[12px] font-medium">Backfill atribución</div>
        <div class="text-[10px] text-[var(--color-text-tertiary)]">Atribuye sales pasadas a campañas via lead.phone match. Idempotente.</div>
        {#if backfillResult}
          <div class="mt-1 text-[10px]" style="color: {backfillResult.ok ? 'var(--color-accent)' : 'var(--color-danger)'};">
            ✓ {backfillResult.inserted} attribuidas · {backfillResult.skippedNoMatch} sin match · {backfillResult.skippedAlreadyAttributed} ya attribuidas
            {#if backfillResult.errors.length > 0}
              <span class="text-[var(--color-warning)]">· {backfillResult.errors.length} errores</span>
            {/if}
          </div>
        {/if}
        {#if backfillError}
          <div class="mt-1 text-[10px] text-[var(--color-danger)]">⚠ {backfillError}</div>
        {/if}
      </div>
      <button
        type="button"
        onclick={runBackfill}
        disabled={backfilling}
        class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if backfilling}<Loader2 size={12} class="animate-spin" /> Backfilling…{:else}<RefreshCw size={12} /> Run{/if}
      </button>
    </div>
  </div>
</section>
```

### Task 6: OrderDetailModal — display attribution (read-only)

In `OrderDetailModal.svelte`, after the existing customer info block, add a new "Atribución" section that loads via `adapter.getSaleAttribution(saleId)` on mount and displays campaign name + source if found, or "—" otherwise. Keep it small (~20 lines).

### Task 7: Build MSI v0.1.32 + tag + LOG + push

Standard release flow.

## Self-review

- ✅ Auto-attribution wired into manual order creation
- ✅ Backfill handler idempotent (NOT EXISTS guard)
- ✅ Read-only display on order detail
- ✅ All 4 layers (bridge → rust → adapter → UI)
- ✅ No breaking changes to existing R5 code
