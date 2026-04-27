# Comercial R5: Ads + Performance — Design Spec

**Date:** 2026-04-27
**Branch:** `comercial-design` (continuation)
**Predecessor:** R4 (v0.1.30, shipped 2026-04-27 con tag).
**Successor target:** v0.1.31

---

## 1. Goal

Surface real ad performance from Meta Ads API in the ERP. Wire Funnel Awareness card to live data (today: zeros + "Esperando sync Meta API (R5)"). Add `CampaignDetailModal` with time-series. Add detector for campaign performance drops. Re-implement the cupón flow deferred from R4 with a stub that documents the worker contract gap.

---

## 2. Scope

### Incluido

- **Meta Ads API sync** — Python handler in bridge that pulls `/insights` for the ad account and upserts rows into `campaigns_snapshot`. Manual trigger from Settings (button) for v1; cron later if needed.
- **Awareness card live data** — Funnel awareness uses last-30-days aggregation from `campaigns_snapshot` instead of mock zeros.
- **CampaignDetailModal** — drilldown from Awareness or campaigns list. Header (campaign name + status + totals), body 2-col (time-series chart LEFT, ranked sales attribution RIGHT), footer (close).
- **Time-series chart** — vanilla SVG line chart for spend/conversions/revenue over period. Custom (no chart library — keeps bundle small, fits retro aesthetic).
- **Detector `detectCampaignPerfDrop`** — flags campaigns with rolling 7d spend ÷ conversions ratio that's >30% worse than the previous 7d window. Severity: `warn`.
- **Settings extension** — "Sincronizar Meta Ads" button with last-sync timestamp + result counts (campaigns updated, errors).
- **Cupón re-implementation (stub)** — adapter signature + Rust command + Python handler that returns `{ok: false, error: "Worker endpoint pending — see R5 task"}`. UI button shows "Próximamente" badge. Real worker endpoint update is OUT of scope (separate worker task).

### NO incluido (deferred)

- Cron-based auto sync (manual only for v1).
- Tab Ads dedicated (CampaignDetailModal opens from Funnel Awareness drilldown — no separate tab).
- Ad creative preview / management (read-only metrics only).
- AdSet-level breakdown (campaign-level only for v1).
- Pinning / archiving campaigns in the UI.
- New schema migrations beyond `campaigns_snapshot.campaign_name` (additive).

---

## 3. Architecture

### Data flow

```
Settings "Sincronizar" button
  ↓
adapter.syncMetaAds() (Tauri)
  ↓
comercial_sync_meta_ads (Rust)
  ↓ run_python_bridge
cmd_sync_meta_ads (Python, urllib → graph.facebook.com)
  ↓
INSERT INTO campaigns_snapshot (one row per campaign per sync)
  ↓
Returns {ok, campaigns_synced, errors[]}

FunnelTab on mount
  ↓
adapter.getFunnelAwarenessReal({period}) (Tauri)
  ↓
comercial_get_funnel_awareness_real (Rust)
  ↓
cmd_get_funnel_awareness_real (Python)
  ↓
SELECT FROM campaigns_snapshot WHERE captured_at BETWEEN ? AND ?
GROUP BY campaign_id
  ↓
Returns {impressions, clicks, spend, conversions, revenueAttributed}

CampaignDetailModal opens (from Awareness card)
  ↓
adapter.getCampaignDetail({campaignId, periodDays}) (Tauri)
  ↓
cmd_get_campaign_detail (Python)
  ↓
JOIN with sales_attribution + customers for orders attributed
  ↓
Returns {meta, dailyTimePoints, attributedSales}

Detector loop (every 15 min)
  ↓
detectCampaignPerfDrop()
  ↓
adapter.listCampaigns() — last 14d aggregated by campaign
  ↓
Compare 7d-vs-7d ratio per campaign
  ↓
If degradation >30% AND spend > Q100 → DetectedEvent{severity:'warn'}
```

### Meta API integration

- **Endpoint:** `https://graph.facebook.com/v21.0/{AD_ACCOUNT_ID}/insights`
- **Auth:** `META_ACCESS_TOKEN` (System User token) from `C:\Users\Diego\club-coo\ads\.env`
- **Required env vars:** `META_AD_ACCOUNT_ID` (format `act_NNNN`), `META_ACCESS_TOKEN`
- **Default fields:** `campaign_id, campaign_name, spend, impressions, clicks, ctr, cpc, actions, action_values`
- **Date param:** `time_range={since:'YYYY-MM-DD',until:'YYYY-MM-DD'}` (default last 30d)
- **Level param:** `level=campaign` (no adset/ad rollup for v1)
- **Pagination:** Single page (Meta defaults to 25/page; account has < 10 active campaigns, so single fetch is fine).
- **Bypass Cloudflare 1010:** `User-Agent: ElClub-ERP/0.1.31` header per R2-combo fix `5b72b65`.

### Storage strategy

- **Table:** `campaigns_snapshot` (already exists). Additive: `campaign_name TEXT` column.
- **Insert per sync:** new row per campaign per sync. Allows time-series queries.
- **No upsert** — sync history is preserved (every "Sincronizar" click adds a snapshot batch).
- **Conversions field:** populated from `actions.purchase.value` if present, else 0.
- **Revenue field:** populated from `action_values.purchase.value` (peso-converted; we assume Meta returns USD, multiply by Q7.7).

### Time-series chart

- **Format:** vanilla SVG `<polyline>` + `<circle>` per data point.
- **Layout:** 280x140px viewBox, left axis = spend GTQ, x axis = day index.
- **Data:** daily aggregation from `campaigns_snapshot` rows (group by `date(captured_at)`).
- **Colors:** terminal-green polyline, accent-amber dot for VIP days (>median spend).
- **Hover:** simple `<title>` tooltips (native browser).
- **No library** — keeps bundle ~10KB lighter than chart.js.

---

## 4. Components

### NEW files

- `overhaul/src/lib/components/comercial/modals/CampaignDetailModal.svelte` — main modal
- `overhaul/src/lib/components/comercial/charts/TimeSeriesChart.svelte` — vanilla SVG chart

### MODIFIED files

- `erp/audit_db.py` — additive ALTER TABLE (campaign_name column)
- `erp/scripts/erp_rust_bridge.py` — 5 new handlers (sync, list, detail, awareness, coupon stub)
- `overhaul/src-tauri/src/lib.rs` — 5 Tauri commands + 4 structs
- `overhaul/src/lib/data/comercial.ts` — 4 new types (Campaign, CampaignSnapshot, CampaignTimePoint, FunnelAwarenessReal)
- `overhaul/src/lib/adapter/types.ts` — 5 method signatures
- `overhaul/src/lib/adapter/tauri.ts` — 5 impls
- `overhaul/src/lib/adapter/browser.ts` — 5 stubs
- `overhaul/src/lib/data/eventDetector.ts` — `detectCampaignPerfDrop` + wire into runOnce
- `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte` — Awareness card uses real data + click → CampaignDetailModal
- `overhaul/src/lib/components/comercial/tabs/SettingsTab.svelte` — "Sincronizar Meta Ads" button + last-sync display

### DELETED files

None.

---

## 5. UX flows

### Sync flow

1. User opens Settings.
2. Clicks "Sincronizar Meta Ads" button.
3. Spinner shows. Button disabled.
4. Backend hits Meta API for last 30d insights.
5. Inserts N rows in `campaigns_snapshot` (N = active campaigns).
6. Result toast: `✓ {N} campañas sincronizadas` or `⚠ Error: {message}`.
7. Last-sync timestamp updates.
8. Funnel Awareness card auto-refreshes on next mount.

### Awareness drilldown flow

1. User on Funnel tab sees Awareness card with real data (impressions, clicks, spend).
2. Clicks "Ver detalle →" on the card.
3. **Two options designed:** v1 → opens a campaigns picker if multiple, or directly opens CampaignDetailModal if single. For multi-campaign, picker is a small inline list above the modal.
4. CampaignDetailModal opens for selected campaign.
5. Modal shows: header (name + period totals), body 2-col (line chart left, attributed sales table right).
6. Click on a sales row → opens OrderDetailModal (existing).

### Campaign performance alert flow

1. Detector runs every 15 min.
2. For each campaign with > Q100 spend in last 14d, computes `cost_per_conversion = spend ÷ conversions` for last 7d AND prior 7d.
3. If `(last_7d / prior_7d) > 1.30` (30% worse), emit DetectedEvent with severity `warn`, type `campaign_perf_drop`.
4. Inbox surfaces it as actionable item.
5. Click event → opens CampaignDetailModal scoped to that campaign.

---

## 6. Decisions delegated to controller

Diego pre-authorized for R5 + posteriores. Decisions baked in:

| # | Question | Resolution | Why |
|---|----------|------------|-----|
| 1 | Sync cadence | Manual button in Settings (v1). Cron deferred. | Simpler, fewer moving parts. Diego wants visible agency. |
| 2 | Tab Ads dedicated | NO — drilldown from Funnel Awareness card | Keeps R5 scope tight. Existing pattern (modal drilldown) suffices. |
| 3 | Chart library | Vanilla SVG (custom component) | Bundle weight, retro aesthetic, full control of look. |
| 4 | Storage strategy | Append-only snapshots (no upsert) | Time-series requires history. Cheap on disk. |
| 5 | Pesos conversion | Hardcoded Q7.7/USD on the bridge side | Meta returns USD. Diego prices in GTQ. Static rate is fine for v1; FX module out of scope. |
| 6 | Detector threshold | 30% degradation in cost-per-conversion, requires Q100+ spend | Avoids false positives on tiny campaigns. Specific number per Diego's verbal cue. |
| 7 | Cupón re-implementation | Stub that returns "pending worker update" — adapter is wired, button shows in modal but disabled | Unblocks downstream work. Real worker endpoint is separate task. |
| 8 | Schema additivity | Add `campaign_name TEXT` column only — keep `raw_json` for everything else | Minimal migration. Future fields go via `raw_json` parse. |
| 9 | Multi-campaign awareness | Single aggregate display in Awareness card (sum across all campaigns) + inline picker for drilldown | Simple, dense, gamey — fits Diego's mental model. |
| 10 | Time-series period | 30 days default (configurable later) | Matches Meta API default, enough for trend without UI clutter. |
| 11 | "Pesos display" | All Q values formatted as `Q{integer}` (no decimals, since Meta returns small dollar amounts that round to GTQ ints anyway after conversion) | Matches existing comercial display patterns. |
| 12 | Detector wiring | Add `detectCampaignPerfDrop` after the 3 existing detectors in `runOnce()` | Same pattern as Task 7 R4. |

---

## 7. Errors + edge cases

- **Meta API 401:** Token expired. Bridge returns `{ok: false, error: "Meta token invalid — refresh in club-coo/ads/.env"}`. UI surfaces as toast.
- **Meta API rate limit (HTTP 429):** Retry-After header parsed. Bridge waits and retries once. If still fails, surfaces as `{ok: false, error: "Rate limit — try again in N min"}`.
- **Empty insights response:** No active campaigns. Bridge returns `{ok: true, campaigns_synced: 0}`. Awareness card shows zeros (not "no data" — distinguishable from never-synced state via `last_sync_at`).
- **Network unavailable:** urllib raises URLError. Bridge returns `{ok: false, error: "Network error: {e}"}`.
- **Empty `actions` field:** Some campaigns have no purchase events. `conversions = 0` and `revenue_attributed = 0`. Detector skips campaigns with `< Q100 spend` to avoid noise.
- **Time-series with sparse data:** If only 3 days have snapshots, chart shows 3 dots + 2 line segments. No interpolation.
- **Campaign exists in DB but not in latest sync:** Probably paused/archived in Meta. Show in list as `● PAUSED` (using last-known-status from raw_json).

---

## 8. Schema deltas

Single additive ALTER (idempotent):

```sql
ALTER TABLE campaigns_snapshot ADD COLUMN campaign_name TEXT;
```

Existing columns unchanged: `snapshot_id, campaign_id, captured_at, impressions, clicks, spend_gtq, conversions, revenue_attributed_gtq, raw_json`.

Existing index `idx_camp_id_time` (campaign_id, captured_at) — unchanged.

No new tables.

---

## 9. Release plan

- **Tag:** `v0.1.31`
- **Build artifact:** `El Club ERP_0.1.31_x64_en-US.msi`
- **LOG entry:** Update `elclub-catalogo-priv/docs/LOG.md` with R5 summary.
- **Commit message convention:** `feat(comercial): R5 ...` for features, `fix(comercial): R5 ...` for fixes, `chore(release): v0.1.31` for the version bump.
- **Push:** `comercial-design` branch + `v0.1.31` tag to `origin`.

---

## 10. Self-review

Spec covers:
- ✅ Goal + scope clear with deferrals listed
- ✅ Data flow diagrammed
- ✅ Files-to-modify list complete
- ✅ UX flows + edge cases
- ✅ Schema delta minimal + idempotent
- ✅ All decisions delegated and resolved
- ✅ Cupón re-implementation strategy clarified

Ready for plan derivation.
