# Comercial R2-combo — Funnel + Pulso + ManyChat sync

**Author:** Diego (decisions) + Claude (drafting)
**Date:** 2026-04-26
**Status:** Approved scope, pending implementation plan
**Supersedes:** "Release 2 — Funnel + Pulso" + "Release 3 — ManyChat conversaciones" sections of `2026-04-26-comercial-design.md`. Both releases combined here.

---

## 1. Goal

Make the Funnel tab and Pulso bar fully functional with real data — including ManyChat-driven leads and conversations. After R2-combo ships, Diego sees the whole game in one view: how many leads came in this period, how many conversations are open, how many orders, repeat rate, and the conversion drop between each stage. The Pulso bar shows real period-over-period trends, and one new detector ("leads sin responder >12h") surfaces threads that need a reply.

R2-combo absorbs the original R3 (ManyChat sync) because the Funnel's middle stages (Interest/Consideration) are useless without ManyChat data, and shipping them as separate releases would mean either (a) Funnel etapas con zeros indefinidos, or (b) a sync built without funnel context. Combining them is cheaper and cleaner.

---

## 2. Scope

### Included

| Area | What ships |
|---|---|
| **Tab Funnel** | 5 etapas en grid horizontal con conversion arrows. Awareness en zeros con mensaje "esperando R5". Interest/Consideration/Sale/Retention con data real. |
| **Pulso bar trends** | Conexión real de current+previous range para todos los 6 KPIs (revenue, órdenes, leads, conv rate, ad spend, ROAS). El shell de R1 ya está; solo falta wiring. |
| **3 modals nuevos** | `LeadProfileModal` (Interest), `ConversationThreadModal` (Consideration, lazy messages), `RetentionListModal` (lista sortable de customers). |
| **ManyChat sync** | ERP pull cada 1h via worker endpoint nuevo. Botón manual "Sincronizar ahora" en Settings. Idempotente. |
| **1 detector nuevo** | "Leads sin responder >12h" — severity warn (no push WA, solo Inbox). |
| **Worker endpoints** | `GET /api/comercial/sync-data?since=<iso>` + `GET /api/comercial/conversation/:id/messages` (lazy fetch). |

### Deferred to R4 (Customers + Atribución)

- VIP detection automática (LTV ≥ Q1,500)
- Detector "VIP inactivos +60d"
- `CustomerProfileModal` con traits editables, timeline, atribución
- Tab 2 (Customers) full feature

### Deferred to R5 (Ads + Performance)

- Sync Meta Ads API → `campaigns_snapshot`
- Awareness etapa con data real (impressions, clicks, ad spend, CTR)
- Detector "Campaign performance ↓ >30%"

### Deferred to R6 (Polish)

- "Comparar período" split view (hoy vs ayer / mes vs anterior)
- Custom date range picker real (sigue cayendo a 30d hasta R6)
- Tab Settings completo (umbrales editables, notifications config, sync log UI)
- Detectores "Stock bajo" + "Goal mensual"

---

## 3. Architecture

### Data flow

```
┌─────────────────────────────────────────────────┐
│  ManyChat (FB/IG/WA)                            │
│      ↓ webhooks (existentes)                    │
│  ventus-backoffice (Cloudflare Worker)          │
│      ├─ KV: conv_archive:{convId}.messages      │
│      ├─ KV: conv_index:{brand} (last 500)       │
│      └─ NEW endpoints:                          │
│          GET /api/comercial/sync-data?since=    │
│          GET /api/comercial/conversation/:id/messages
│              ↓ (HTTP c/1h + on-demand)          │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│  El Club ERP (Tauri local)                      │
│      ├─ ManychatSyncLoop (en ComercialShell)    │
│      │     setInterval(sync, 3600_000)          │
│      │     → adapter.syncManychatData(since)    │
│      │     → INSERT OR REPLACE leads + conversations
│      ├─ EventDetectorLoop (de R1) extendido     │
│      │     + detectLeadsUnanswered12h()         │
│      └─ FunnelTab consume:                      │
│            ├─ leads (Interest)                  │
│            ├─ conversations (Consideration)     │
│            ├─ sales (Sale, ya existe)           │
│            └─ customers (Retention, ya existe)  │
└─────────────────────────────────────────────────┘
```

### Sync model (pull-based)

- **Owner of truth:** `conv_archive:{convId}` (KV, 90d TTL) for messages; `conv_index:{brand}` for metadata.
- **ERP local mirror:** `conversations` and `leads` tables in SQLite.
- **Cadence:** automatic c/1h while ERP is open + manual button. If ERP is closed, no sync runs — next open does a full backfill via `since=<lastSyncAt>`.
- **Idempotency:**
  - `conversations`: PK is `conv_id` (TEXT). Sync uses `INSERT OR REPLACE` keyed on `conv_id`.
  - `leads`: UNIQUE composite `(platform, sender_id)`. Sync uses `INSERT OR REPLACE`.
  - `since` filter: worker returns only entries where `ended_at >= since` (closed conversations) and `last_activity_at >= since` (open ones tracked in `ai_hist:*` keys).
- **First sync (no `since`):** worker returns everything in `conv_index:elclub` (last 500). That's enough for the Funnel's working set; older history stays in KV.
- **Storage:** `conversations.messages_json` is `'[]'` (empty array satisfies NOT NULL). Messages are lazy-fetched on modal open.

### Lead extraction

ManyChat tracks `sender_id` per platform but doesn't have a "lead" concept. Each unique `(brand, platform, sender_id)` in `conv_index` is one lead. The sync derives leads:

```
For each conv_index entry (filtered by since):
  upsert lead by (platform, sender_id)
    - first_contact_at = MIN(existing.first_contact_at, entry.started_at)
    - last_activity_at = MAX(existing.last_activity_at, entry.ended_at)
    - status: derive from outcomes ('converted' if any conv has order_id, else 'new')
  upsert conversation by conv_id
    - lead_id = (foreign key to lead, looked up after lead upsert)
    - all metadata fields from entry
    - messages_json = '[]'  (lazy)
```

The lead's `name` and `phone` are not in `conv_index` directly. The ManyChat subscriber API has them but is rate-limited. **R2-combo decision:** leave `name` NULL for sender-id-only leads; populate via `phone` if Diego clicks "Convert to customer" (manual path). Full name enrichment via subscriber API is R4 polish.

### Attribution (`source_campaign_id`)

ManyChat captures `last_input_text`, `entry_action`, and tags. Some flows tag the user with the source campaign (e.g., "MSG-MYSTERY-A"). The sync looks at the most recent message's metadata for hints. Best-effort: if a `source_campaign:XYZ` tag exists in `conv_index.tags`, we set `leads.source_campaign_id = 'XYZ'`. Otherwise NULL. Full attribution comes in R5.

---

## 4. Schema (no changes)

The schema for `conversations`, `leads`, and `campaigns_snapshot` was created in R1 Task 1. No new migrations.

Confirmation of relevant columns (verified from live DB):

**`conversations`:**
- `conv_id TEXT` (PK), `brand`, `platform`, `sender_id`, `started_at`, `ended_at`, `outcome`, `order_id`, `messages_total`, `messages_json TEXT NOT NULL` (default `'[]'`), `tags_json`, `analyzed`, `synced_at`

**`leads`:**
- `lead_id INTEGER` (PK auto), `name`, `handle`, `phone`, `platform NOT NULL`, `sender_id NOT NULL`, `source_campaign_id`, `first_contact_at NOT NULL`, `last_activity_at NOT NULL`, `status` (default `'new'`), `traits_json`. UNIQUE `(platform, sender_id)`.

**`campaigns_snapshot`:** untouched in R2-combo; stays empty until R5.

**One small migration:** add `meta_sync` table for tracking `last_sync_at` per source. Trivial, additive.

```sql
CREATE TABLE IF NOT EXISTS meta_sync (
  source TEXT PRIMARY KEY,         -- 'manychat'
  last_sync_at TEXT NOT NULL,
  last_status TEXT,                -- 'ok' | 'error'
  last_error TEXT
);
```

This goes in `audit_db.py`'s `init_audit_schema()`. Same idempotent ALTER-style pattern as Task 10's `shipped_at` fix.

---

## 5. Components

### 5.1 New Svelte components

| File | Responsibility |
|---|---|
| `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte` | Replace R1 placeholder. Renders 5-stage grid + conversion arrows + drilldown triggers. Period-aware (reads from ComercialShell context). |
| `overhaul/src/lib/components/comercial/modals/LeadProfileModal.svelte` | Lead detail (name, handle, platform, status, source) + lista de conversations relacionadas (clickable → ConversationThreadModal). |
| `overhaul/src/lib/components/comercial/modals/ConversationThreadModal.svelte` | Header con lead info. Body: lista de mensajes (lazy fetched). Footer: "Responder en WA" (`wa.me/{phone}`), "Marcar resuelto". |
| `overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte` | Tabla de customers ordenable por (LTV / última compra / total orders / canal de origen). Sin profile pleno individual (eso es R4). |

### 5.2 Modified Svelte components

| File | Change |
|---|---|
| `overhaul/src/lib/components/comercial/PulsoBar.svelte` | Wire real trends: pasar `prevSales` / `prevLeads` / `prevAdSpend` a `computePulsoKPIs`. Render trend pills para cada KPI (no solo revenue). |
| `overhaul/src/lib/components/comercial/ComercialShell.svelte` | Add `manychatSyncLoop` start/stop alongside the existing `eventDetectorLoop`. Hoist period state to share with FunnelTab. |
| `overhaul/src/lib/components/comercial/tabs/SettingsTab.svelte` | Add temporary "Sincronizar ahora" button (full Settings tab still R6). |

### 5.3 New data layer

| File | Responsibility |
|---|---|
| `overhaul/src/lib/data/funnelKpis.ts` | Pure functions to compute funnel stage counts and conversion rates from raw data arrays. Mirrors the pattern of `kpis.ts` from R1. |
| `overhaul/src/lib/data/manychatSync.ts` | Sync loop: fetch from worker, write to SQLite via adapter, update `meta_sync.last_sync_at`. Returns count of new/updated rows. |

### 5.4 Adapter additions

In `overhaul/src/lib/adapter/types.ts`:

```typescript
// Comercial R2-combo
syncManychatData(since: string | null): Promise<{ leadsUpserted: number; conversationsUpserted: number }>;
listLeads(filter?: { status?: string; range?: PeriodRange }): Promise<Lead[]>;
listConversations(filter?: { outcome?: string; range?: PeriodRange; leadId?: number }): Promise<ConversationMeta[]>;
getConversationMessages(convId: string): Promise<ConversationMessage[]>;  // lazy from worker
listCustomers(filter?: { lastOrderBefore?: string; minLtvGtq?: number }): Promise<Customer[]>;
getMetaSync(source: string): Promise<{ lastSyncAt: string | null; lastStatus: string | null }>;
```

Tauri impls call new Rust commands `comercial_sync_manychat`, `comercial_list_leads`, `comercial_list_conversations`, `comercial_get_conversation_messages`, `comercial_list_customers`, `comercial_get_meta_sync`. Browser stubs return empty/null.

Rust commands wrap Python bridge handlers (`cmd_sync_manychat`, `cmd_list_leads`, etc.). The `messages` lazy fetch is special: instead of going to SQLite, the bridge calls **the worker** via `urllib.request` (or the Rust command does directly) to fetch fresh from KV. **R2-combo decision:** the messages lazy fetch is implemented in Rust (not Python) — `comercial_get_conversation_messages` makes the HTTP call directly using `reqwest` (already in Cargo.toml). Avoids round-tripping through Python for a pure HTTP call.

### 5.5 New types in `data/comercial.ts`

```typescript
export interface Lead {
  leadId: number;
  name: string | null;
  handle: string | null;
  phone: string | null;
  platform: 'wa' | 'ig' | 'messenger' | 'web';
  senderId: string;
  sourceCampaignId: string | null;
  firstContactAt: string;
  lastActivityAt: string;
  status: 'new' | 'qualified' | 'converted' | 'lost';
  traitsJson: Record<string, unknown>;
}

export interface ConversationMeta {
  convId: string;
  leadId: number | null;
  brand: string;
  platform: 'wa' | 'ig' | 'messenger' | 'web';
  senderId: string;
  startedAt: string;
  endedAt: string;
  outcome: 'sale' | 'no_sale' | 'objection' | 'pending' | null;
  orderId: string | null;
  messagesTotal: number;
  tagsJson: string[];
  analyzed: boolean;
  syncedAt: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;       // ISO, may be approximate
}

export interface Customer {
  customerId: number;
  name: string;
  phone: string | null;
  email: string | null;
  source: string | null;
  firstOrderAt: string;
  totalOrders: number;
  totalRevenueGtq: number;   // computed (no stored column, derived in query)
  lastOrderAt: string | null;
}

export interface FunnelKPIs {
  awareness: { impressions: number; clicks: number; spendGtq: number; ctr: number };
  interest: { totalLeads: number; byPlatform: { wa: number; ig: number; messenger: number; web: number } };
  consideration: { activeConversations: number; pending: number; objection: number };
  sale: { ordersToday: number; awaitingPayment: number; awaitingShipment: number };
  retention: { totalCustomers: number; repeatRate: number; vipInactive60d: number; ltvAvgGtq: number };
  conversion: { awarenessToInterest: number; interestToConsideration: number; considerationToSale: number; saleToRetention: number };  // 0-1 ratios
}
```

---

## 6. Trend computation (Pulso bar wiring)

### Current state (R1 shell)

`PulsoBar.svelte` calls `computePulsoKPIs(sales, leads, adSpend, range)` with empty `prevSales`/`prevLeads`/`prevAdSpend` (defaults to `[]`). Result: trends are always `0%`. Not visible because the UI only shows the trend pill for revenue, but the math is wrong.

### R2-combo wiring

```typescript
async function loadKPIs(p: Period) {
  const range = resolvePeriod(p);
  const prevRange = resolvePreviousRange(range);  // new helper in kpis.ts

  const [sales, leads, adSpend, prevSales, prevLeads, prevAdSpend] = await Promise.all([
    adapter.listSalesInRange(range),
    adapter.listLeadsInRange(range),
    adapter.listAdSpendInRange(range),
    adapter.listSalesInRange(prevRange),
    adapter.listLeadsInRange(prevRange),
    adapter.listAdSpendInRange(prevRange),
  ]);

  kpis = computePulsoKPIs(sales, leads, adSpend, range, prevSales, prevLeads, prevAdSpend);
}
```

`resolvePreviousRange(range)` returns the same-length window immediately preceding `range.start`. For `'today'`, that's yesterday 00:00 → 24:00. For `'7d'`, that's the 7 days before the current 7. Etc.

### Trend pills for all 6 KPIs

Currently only revenue shows a trend. R2-combo extends to órdenes, leads, conv rate. Ad spend and ROAS get trends only when Meta data exists (R5); until then, those pills are hidden.

The `kpis.PulsoKPIs.trends` shape already supports revenue/orders/leads/conversionRate. R2-combo just renders them all.

---

## 7. Funnel tab rendering

### Layout

5-column grid, equal width, separated by conversion-arrow badges. Each stage card has:

```
┌──────────────────────────────┐
│ STAGE NAME (display caps)    │
│                              │
│ 1,247                        │  ← number grande, mono, tabular-nums
│ ↑ 12% vs período anterior    │  ← trend (color-coded)
│                              │
│ 3 metric detail rows:        │
│ ─ metric 1: value            │
│ ─ metric 2: value            │
│ ─ metric 3: value            │
│                              │
│ [Ver detalle →]              │  ← drilldown trigger
└──────────────────────────────┘
```

### Stage colors

- **Awareness (1)** & **Interest (2)** — cold blue (`#60a5fa`)
- **Consideration (3)** — warm amber (`var(--color-warning)`)
- **Sale (4)** — terminal green (`var(--color-accent)`)
- **Retention (5)** — neutral gray (`var(--color-text-tertiary)`)
- **Border red** if the stage has any active critical event (e.g., "Sale" turns red border if order-pending events exist)

### Conversion arrows

Between stages, render a small chip: `→ 23% conv`. Color:
- ≥ 20% green
- 5-20% amber
- < 5% red

The math:
- `awarenessToInterest = leads / clicks` (when Awareness exists; else N/A)
- `interestToConsideration = activeConversations / leads`
- `considerationToSale = sales_period / total_conversations_period`
- `saleToRetention = repeat_customers_period / new_customers_period`

(All ratios are best-effort given available data; refined in later releases.)

### Awareness etapa with R5 placeholder

```
┌──────────────────────────────┐
│ AWARENESS                    │
│                              │
│ —                            │  ← em-dash, no number
│                              │
│ Esperando sync Meta API      │
│ (R5)                         │
│                              │
│ [Ver detalle →] (disabled)   │
└──────────────────────────────┘
```

Consistent with R1's "all systems nominal" empty-state aesthetic.

### Drilldown

Each stage's "Ver detalle" opens its modal:
- Awareness → no-op (button disabled)
- Interest → `LeadProfileModal` initially showing list, click row → individual lead view (same modal, just different state)
- Consideration → `ConversationThreadModal` (initially list, click → thread view)
- Sale → existing `OrderDetailModal` from R1 (opens for the most recent pending order, or shows a list)
- Retention → `RetentionListModal`

**Implementation note:** the "list within modal" pattern is new. R1's modals were single-entity (one order). For R2-combo, modals can show either a list or a single entity. Use `mode: 'list' | 'detail'` state inside each modal.

---

## 8. Detector additions

R1's detector loop (`eventDetector.ts`) gets one new function:

```typescript
async function detectLeadsUnanswered12h(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 12 * 3600 * 1000).toISOString();

  const conversations = await adapter.listConversations({ outcome: 'pending' });  // open threads
  const stale = conversations.filter(c =>
    c.endedAt < cutoff &&  // last activity > 12h ago
    !c.outcome              // still open
  );

  if (stale.length === 0) return null;

  return {
    type: 'leads_unanswered_12h',
    severity: 'warn',                    // not crit (no push WA)
    title: `${stale.length} lead${stale.length === 1 ? '' : 's'} sin responder >12h`,
    sub: stale.slice(0, 3).map(c => `${c.platform}:${c.senderId}`).join(' · ') + (stale.length > 3 ? ` · +${stale.length - 3}` : ''),
    itemsAffected: stale.map(c => ({ type: 'conversation', id: c.convId, hint: c.platform }))
  };
}
```

`startDetectorLoop()` (R1) is extended to call this detector alongside `detectOrdersPending24h`. No new commits to push WA — `severity: 'warn'` skips the push gate (only `crit` triggers push in R1's Task 17).

---

## 9. Worker endpoints (ventus-backoffice)

### `GET /api/comercial/sync-data?since=<iso>`

**Auth:** `DASHBOARD_KEY` bearer token (same as existing admin endpoints).

**Logic:**
1. Read `conv_index:elclub` from KV.
2. Filter entries by `ended_at >= since` (or all if `since` is null).
3. For each entry, derive lead identity `(platform, sender_id)`.
4. Aggregate leads (collapse multiple convs per sender into one lead with derived `first_contact_at` / `last_activity_at` / `status`).
5. Return:

```json
{
  "since": "<provided>",
  "until": "<now ISO>",
  "leads": [{ leadId: null, name, phone, handle, platform, senderId, sourceCampaignId, firstContactAt, lastActivityAt, status, traitsJson }, ...],
  "conversations": [{ convId, brand, platform, senderId, startedAt, endedAt, outcome, orderId, messagesTotal, tagsJson, analyzed, syncedAt }, ...]
}
```

`leadId` is null in the response — the ERP assigns it on insert. The ERP maps each conversation's `senderId+platform` back to its inserted/existing lead by composite key.

### `GET /api/comercial/conversation/:convId/messages`

**Auth:** `DASHBOARD_KEY` bearer token.

**Logic:**
1. Read `conv_archive:{convId}` from KV.
2. If not found, return 404.
3. Return `{ convId, messages: history }` where `history` is the array stored in `conv_archive.messages`.

Both endpoints reuse the existing `requireDashboardAuth` middleware (already in `index.js`).

---

## 10. UX / interactions

### Period selector hoisting

Currently `PulsoBar.svelte` owns `period: $state<Period>`. R2-combo hoists this to `ComercialShell.svelte` and passes it down to PulsoBar AND FunnelTab. Both components re-render when period changes. This is a small refactor (one prop drilling level).

### Sync trigger UX

- **Auto:** `setInterval(syncManychatData, 3600_000)` runs while ComercialShell is mounted (added alongside detector loop).
- **First sync on mount:** runs immediately (same pattern as detector — `runOnce()` on mount).
- **Manual button:** in SettingsTab, a single button "Sincronizar ahora". Click triggers the same sync function. Shows status:
  - Idle: "Última sync: hace 23 min · [Sincronizar ahora]"
  - Busy: "Sincronizando…" with spinner
  - Success: "✓ 3 leads · 5 conversations actualizadas"
  - Error: "⚠ Error sincronizando: <message>" — keep the error visible until next attempt.
- **Status persistence:** `meta_sync.last_sync_at`, `last_status`, `last_error`. Read on mount via `adapter.getMetaSync('manychat')`.

### Loading states

- Funnel cards: skeleton numbers (`---`) until first load completes.
- ConversationThreadModal: spinner in body until messages fetched.
- LeadProfileModal: lead info immediate (from already-loaded list); related conversations spinner.

### Empty states

- Funnel with zero leads: stage card says "0 leads — verificá tus campaigns en Ads o el bot está caído."
- Conversation thread with zero messages: "Esta conversación no tiene mensajes guardados (>90d antiguos o purgados)."
- Retention list empty: "0 customers — todavía no hay compradores recurrentes."

---

## 11. Errors

### Sync failures

- Network error: caught, written to `meta_sync.last_error`, surfaced in Settings UI. Auto-retry on next interval (no exponential backoff in R2-combo — keep it simple; R6 polish).
- Worker 401 (auth): same as above. Diego sees error, fixes secret, manual sync button works after.
- Worker 5xx: same; logged.
- Partial failure (e.g., one lead row fails INSERT): catch per-row, log, continue. The endpoint returns count of `leadsUpserted` and `conversationsUpserted` reflecting actual successes.

### Lazy message fetch failures

- 404 from worker (KV TTL expired): show empty state "mensajes >90d fueron purgados".
- Network error: show retry button "Reintentar".
- 401: surface "Sesión expirada — refrescá DASHBOARD_KEY".

### Funnel data inconsistency

- If `conversations.lead_id` is null (lead not found at sync time), skip in conversion-rate calc. Don't crash.
- If `customers.first_order_at` is null but row exists (anomalous data), include in totalCustomers but skip from repeat-rate calc.

---

## 12. Testing & verification

Same pattern as R1:

1. **Type checks:** `npm run check` (svelte-check + tsc) must show 0 errors after each task. `cargo check` for Rust changes.
2. **Bridge smoke tests:** every new Python handler gets a one-line smoke test verifying `{"ok": true, ...}`.
3. **Worker smoke tests:** `curl` against the new endpoints with `DASHBOARD_KEY` bearer.
4. **End-to-end smoke:** Diego installs the new MSI, opens Comercial → Funnel, sees real leads/conversations after first sync, opens a thread modal, replies via WA.

No automated test framework added in R2-combo (deferred to R6 if/when test infra lands).

---

## 13. Releases (this is one)

R2-combo is one release. Planned tag: `v0.1.29`.

Estimated time: 3-4 days. Compared to R2 (2-3d) + R3 (2-3d) sequential = ~5d, the combination saves ~1d via shared sync infra and avoids a "throwaway" Funnel state.

---

## 14. Open questions / R6 polish notes

- **Trend window for "today" period:** "Hoy" trend compares to "ayer". For "7d", it's "previous 7d". Simple, but "today" has fewer data points so trends jump around. Consider in R6 a "smoothed" mode toggle.
- **VIP detection in R4:** Once VIP threshold is automated, the Retention etapa shows VIP-specific count and the RetentionListModal can highlight VIPs. R2-combo's RetentionListModal renders all customers — VIPs are not visually distinct yet.
- **ConversationThreadModal "Marcar resuelto" action:** in R2-combo, clicking sets `conversations.outcome = 'no_sale'` (or asks Diego which outcome). Simpler: just close the dialog and don't touch outcome — that field is owned by the bot's `closeConversation()` call. R2-combo decision: button is **read-only** (no "marcar resuelto"); only "Responder en WA" exists. Detector "leads sin responder >12h" auto-resolves when `last_activity_at` updates.
- **Sync window:** R2-combo always asks `since=<lastSyncAt>`. If lastSyncAt is more than ~14 days old, the worker returns at most last 500 from `conv_index`. Older threads beyond that window are lost (acceptable — they're 90d+ in KV anyway).

---

## 15. Self-review

- ✅ Scope: focused on Funnel + Pulso + ManyChat sync. No drift into Customers tab, Ads tab, Settings full feature.
- ✅ All 5 brainstorming decisions reflected: scope C, sync arch A, lazy messages, drilldowns A, full scope confirmed.
- ✅ Schema: confirmed against live DB. One additive migration (`meta_sync` table). Zero changes to `conversations`/`leads`/`campaigns_snapshot` columns.
- ✅ Reuses R1 patterns: detector loop, BaseModal, optional-chaining adapter calls, snake_case Rust commands wrapped in `args` struct.
- ✅ Defers cleanly: VIP/Customer profile to R4, Meta sync to R5, polish to R6. Each deferred item has a clear "what comes when".
- ✅ Errors handled at every layer (sync, lazy fetch, funnel inconsistency).
- ✅ No "TBD" placeholders. No internal contradictions. Ambiguities resolved (e.g., Marcar resuelto button decision).
- ✅ Testing: same as R1 (type check + smoke + manual). No new infra.
