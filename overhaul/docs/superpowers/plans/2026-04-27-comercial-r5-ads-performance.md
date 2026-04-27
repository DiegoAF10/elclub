# Comercial R5: Ads + Performance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-27-comercial-r5-ads-performance-design.md`

**Branch:** `comercial-design` (continuation from R4 v0.1.30)

**Versionado al completar:** ERP v0.1.30 → v0.1.31

---

## Tasks

### Task 0: Pre-flight — Meta API smoke test

Verify token works + identify exact response shape so Tasks 3+ can use it.

```bash
# 1) Read token + ad account from .env
DKEY=$(grep '^META_ACCESS_TOKEN=' /c/Users/Diego/club-coo/ads/.env | cut -d= -f2-)
ACCT=$(grep '^META_AD_ACCOUNT_ID=' /c/Users/Diego/club-coo/ads/.env | cut -d= -f2-)
echo "Account: $ACCT"

# 2) Smoke: fetch campaigns insights for last_7d
curl -s -G "https://graph.facebook.com/v21.0/$ACCT/insights" \
  --data-urlencode "fields=campaign_id,campaign_name,spend,impressions,clicks,actions" \
  --data-urlencode "level=campaign" \
  --data-urlencode "date_preset=last_7d" \
  --data-urlencode "access_token=$DKEY" | head -c 1000
```

Expected: JSON `{data: [{campaign_id, ...}, ...]}`. If error: STOP, report. Likely fixes:
- `META_AD_ACCOUNT_ID` missing → check .env
- Token expired → tell Diego to refresh
- Permissions missing → ads_read scope required

If smoke test passes, document the exact JSON shape (esp. `actions` array structure) as a comment for Task 3 reference.

NO commit — research only.

---

### Task 1: Schema additive — `campaigns_snapshot.campaign_name`

**File:** `erp/audit_db.py`

After existing CREATE TABLE for campaigns_snapshot (line 154-164), add idempotent ALTER:

```python
# Comercial R5: ensure campaign_name column exists (additive migration).
# Captured separately from raw_json for fast SELECT in lists.
try:
    conn.execute("ALTER TABLE campaigns_snapshot ADD COLUMN campaign_name TEXT")
except sqlite3.OperationalError:
    pass
```

Verify:
```bash
python -c "from db import get_conn; print('campaign_name' in [r[1] for r in get_conn().execute('PRAGMA table_info(campaigns_snapshot)').fetchall()])"
```

Commit: `feat(comercial): schema R5 — campaigns_snapshot.campaign_name (additive)`

---

### Task 2: Types core R5

**File:** `overhaul/src/lib/data/comercial.ts`

Append at the end of the file:

```typescript
// ─── R5: Ads + Performance ────────────────────────────────────

export interface Campaign {
  campaignId: string;
  campaignName: string | null;
  lastSyncAt: string | null;
  // 30-day rollup (most-recent sync per day, summed)
  totalSpendGtq: number;
  totalImpressions: number;
  totalClicks: number;
  totalConversions: number;
  totalRevenueGtq: number;
  costPerConversionGtq: number | null;  // null if conversions == 0
  status: 'active' | 'paused' | 'archived' | 'unknown';  // derived from raw_json or last-known
}

export interface CampaignSnapshot {
  snapshotId: number;
  campaignId: string;
  capturedAt: string;
  impressions: number;
  clicks: number;
  spendGtq: number;
  conversions: number;
  revenueAttributedGtq: number;
}

export interface CampaignTimePoint {
  date: string;          // YYYY-MM-DD
  spendGtq: number;
  conversions: number;
  revenueGtq: number;
  impressions: number;
  clicks: number;
}

export interface CampaignDetail {
  campaign: Campaign;
  daily: CampaignTimePoint[];
  attributedSales: Array<{
    saleId: number;
    ref: string;
    customerName: string | null;
    totalGtq: number;
    occurredAt: string;
  }>;
}

export interface FunnelAwarenessReal {
  periodStart: string;
  periodEnd: string;
  totalCampaigns: number;
  impressions: number;
  clicks: number;
  spendGtq: number;
  conversions: number;
  revenueAttributedGtq: number;
  cpm: number | null;        // cost per 1000 impressions
  cpc: number | null;        // cost per click
  ctr: number | null;        // click-through rate
  byCampaign: Array<{ campaignId: string; campaignName: string | null; spendGtq: number; impressions: number }>;
  lastSyncAt: string | null;
}

export interface MetaSyncResult {
  ok: boolean;
  campaignsSynced: number;
  errors: string[];
  syncedAt: string;
}
```

Type check: `npm run check` should be 0 errors (no callers yet).

Commit: `feat(comercial): types R5 — Campaign, CampaignSnapshot, CampaignDetail, FunnelAwarenessReal`

---

### Task 3: Bridge Python — 5 handlers

**File:** `erp/scripts/erp_rust_bridge.py`

Add 5 handlers near the existing comercial section.

**3.1 `cmd_sync_meta_ads`** — fetches Meta insights, inserts campaigns_snapshot rows.

```python
def cmd_sync_meta_ads(args):
    """Sync campaigns insights desde Meta Ads API → campaigns_snapshot.
    Reads token + account_id from /c/Users/Diego/club-coo/ads/.env.
    Inserts one row per campaign per sync (history-preserving).
    """
    import json, os, urllib.request, urllib.parse, urllib.error
    from pathlib import Path
    from datetime import datetime
    from db import get_conn

    env_path = Path(r"C:/Users/Diego/club-coo/ads/.env")
    if not env_path.exists():
        return {"ok": False, "error": f".env not found at {env_path}"}

    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    token = env.get("META_ACCESS_TOKEN")
    account_id = env.get("META_AD_ACCOUNT_ID")
    if not token or not account_id:
        return {"ok": False, "error": "META_ACCESS_TOKEN or META_AD_ACCOUNT_ID missing"}

    days = args.get("days") or 30
    period = args.get("datePreset") or f"last_{days}d"

    url = f"https://graph.facebook.com/v21.0/{account_id}/insights"
    params = {
        "fields": "campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,actions,action_values",
        "level": "campaign",
        "date_preset": period,
        "access_token": token,
    }
    qs = urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": "ElClub-ERP/0.1.31"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        if e.code == 429:
            return {"ok": False, "error": f"Rate limited — retry later. Body: {body}"}
        return {"ok": False, "error": f"Meta HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": f"Meta fetch failed: {e}"}

    rows = data.get("data") or []
    if not rows:
        # Still record a sync so last_sync_at moves forward
        return {"ok": True, "campaignsSynced": 0, "errors": [], "syncedAt": datetime.now().isoformat()}

    USD_TO_GTQ = 7.7
    conn = get_conn()
    synced = 0
    errors = []
    sync_ts = datetime.now().isoformat()

    try:
        for row in rows:
            try:
                campaign_id = row.get("campaign_id")
                campaign_name = row.get("campaign_name")
                spend_usd = float(row.get("spend", 0) or 0)
                spend_gtq = round(spend_usd * USD_TO_GTQ, 2)
                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)

                conversions = 0
                revenue_usd = 0.0
                for a in row.get("actions", []) or []:
                    if a.get("action_type") == "purchase":
                        conversions += int(a.get("value", 0))
                for av in row.get("action_values", []) or []:
                    if av.get("action_type") == "purchase":
                        revenue_usd += float(av.get("value", 0))
                revenue_gtq = round(revenue_usd * USD_TO_GTQ, 2)

                conn.execute("""
                    INSERT INTO campaigns_snapshot
                      (campaign_id, campaign_name, captured_at, impressions, clicks,
                       spend_gtq, conversions, revenue_attributed_gtq, raw_json)
                    VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?)
                """, (campaign_id, campaign_name, impressions, clicks,
                      spend_gtq, conversions, revenue_gtq, json.dumps(row)))
                synced += 1
            except Exception as ie:
                errors.append(f"row {row.get('campaign_id', '?')}: {ie}")
        conn.commit()
        return {"ok": True, "campaignsSynced": synced, "errors": errors, "syncedAt": sync_ts}
    finally:
        conn.close()
```

**3.2 `cmd_list_campaigns`** — last 30d aggregation per campaign.

```python
def cmd_list_campaigns(args):
    """Lista campañas con rollup últimos 30d (o periodDays arg)."""
    from db import get_conn

    days = int(args.get("periodDays") or 30)
    conn = get_conn()
    try:
        rows = conn.execute(f"""
            SELECT
                campaign_id,
                MAX(campaign_name) AS campaign_name,
                MAX(captured_at) AS last_sync_at,
                COALESCE(SUM(spend_gtq), 0) AS total_spend,
                COALESCE(SUM(impressions), 0) AS total_impressions,
                COALESCE(SUM(clicks), 0) AS total_clicks,
                COALESCE(SUM(conversions), 0) AS total_conversions,
                COALESCE(SUM(revenue_attributed_gtq), 0) AS total_revenue
            FROM campaigns_snapshot
            WHERE captured_at >= datetime('now', 'localtime', '-{days} days')
            GROUP BY campaign_id
            ORDER BY total_spend DESC
        """).fetchall()
        out = []
        for r in rows:
            cpc = round(r[3] / r[6], 2) if r[6] else None  # spend / conversions
            out.append({
                "campaignId": r[0],
                "campaignName": r[1],
                "lastSyncAt": r[2],
                "totalSpendGtq": r[3],
                "totalImpressions": r[4],
                "totalClicks": r[5],
                "totalConversions": r[6],
                "totalRevenueGtq": r[7],
                "costPerConversionGtq": cpc,
                "status": "active",  # v1: assume active if recently synced
            })
        return {"ok": True, "campaigns": out}
    finally:
        conn.close()
```

**3.3 `cmd_get_campaign_detail`** — full detail + daily series + attributed sales.

```python
def cmd_get_campaign_detail(args):
    """Campaign + daily time-series + attributed sales (joined via sales_attribution)."""
    from db import get_conn

    campaign_id = args.get("campaignId")
    days = int(args.get("periodDays") or 30)
    if not campaign_id:
        return {"ok": False, "error": "campaignId required"}

    conn = get_conn()
    try:
        # Aggregate campaign
        agg = conn.execute(f"""
            SELECT
                MAX(campaign_name),
                MAX(captured_at),
                COALESCE(SUM(spend_gtq), 0),
                COALESCE(SUM(impressions), 0),
                COALESCE(SUM(clicks), 0),
                COALESCE(SUM(conversions), 0),
                COALESCE(SUM(revenue_attributed_gtq), 0)
            FROM campaigns_snapshot
            WHERE campaign_id = ?
              AND captured_at >= datetime('now', 'localtime', '-{days} days')
        """, (campaign_id,)).fetchone()

        if agg[1] is None:
            return {"ok": True, "detail": None}

        cpc = round(agg[2] / agg[5], 2) if agg[5] else None
        campaign = {
            "campaignId": campaign_id,
            "campaignName": agg[0],
            "lastSyncAt": agg[1],
            "totalSpendGtq": agg[2],
            "totalImpressions": agg[3],
            "totalClicks": agg[4],
            "totalConversions": agg[5],
            "totalRevenueGtq": agg[6],
            "costPerConversionGtq": cpc,
            "status": "active",
        }

        # Daily time-series
        daily_rows = conn.execute(f"""
            SELECT
                date(captured_at) AS day,
                SUM(spend_gtq), SUM(conversions), SUM(revenue_attributed_gtq),
                SUM(impressions), SUM(clicks)
            FROM campaigns_snapshot
            WHERE campaign_id = ?
              AND captured_at >= datetime('now', 'localtime', '-{days} days')
            GROUP BY day
            ORDER BY day ASC
        """, (campaign_id,)).fetchall()
        daily = [
            {"date": r[0], "spendGtq": r[1], "conversions": r[2], "revenueGtq": r[3],
             "impressions": r[4], "clicks": r[5]}
            for r in daily_rows
        ]

        # Attributed sales via sales_attribution
        sales_rows = conn.execute("""
            SELECT s.sale_id, s.ref, c.name, s.total, s.occurred_at
            FROM sales_attribution sa
            JOIN sales s ON s.sale_id = sa.sale_id
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE sa.ad_campaign_id = ?
            ORDER BY s.occurred_at DESC
            LIMIT 50
        """, (campaign_id,)).fetchall()
        attributed = [
            {"saleId": r[0], "ref": r[1], "customerName": r[2], "totalGtq": r[3], "occurredAt": r[4]}
            for r in sales_rows
        ]

        return {"ok": True, "detail": {"campaign": campaign, "daily": daily, "attributedSales": attributed}}
    finally:
        conn.close()
```

**3.4 `cmd_get_funnel_awareness_real`** — replaces mock zeros for Funnel Awareness.

```python
def cmd_get_funnel_awareness_real(args):
    """Funnel Awareness real-data rollup."""
    from db import get_conn
    from datetime import datetime, timedelta

    period_start = args.get("periodStart")
    period_end = args.get("periodEnd")
    if not period_start or not period_end:
        # Default: last 30d
        end = datetime.now()
        start = end - timedelta(days=30)
        period_start = start.isoformat()
        period_end = end.isoformat()

    conn = get_conn()
    try:
        agg = conn.execute("""
            SELECT
                COUNT(DISTINCT campaign_id),
                COALESCE(SUM(impressions), 0),
                COALESCE(SUM(clicks), 0),
                COALESCE(SUM(spend_gtq), 0),
                COALESCE(SUM(conversions), 0),
                COALESCE(SUM(revenue_attributed_gtq), 0),
                MAX(captured_at)
            FROM campaigns_snapshot
            WHERE captured_at BETWEEN ? AND ?
        """, (period_start, period_end)).fetchone()

        impressions = agg[1]
        clicks = agg[2]
        spend = agg[3]
        cpm = round(spend / impressions * 1000, 2) if impressions else None
        cpc = round(spend / clicks, 2) if clicks else None
        ctr = round(clicks / impressions * 100, 2) if impressions else None

        by_campaign_rows = conn.execute("""
            SELECT campaign_id, MAX(campaign_name), SUM(spend_gtq), SUM(impressions)
            FROM campaigns_snapshot
            WHERE captured_at BETWEEN ? AND ?
            GROUP BY campaign_id
            ORDER BY SUM(spend_gtq) DESC
        """, (period_start, period_end)).fetchall()
        by_campaign = [
            {"campaignId": r[0], "campaignName": r[1], "spendGtq": r[2], "impressions": r[3]}
            for r in by_campaign_rows
        ]

        return {"ok": True, "awareness": {
            "periodStart": period_start,
            "periodEnd": period_end,
            "totalCampaigns": agg[0],
            "impressions": impressions,
            "clicks": clicks,
            "spendGtq": spend,
            "conversions": agg[4],
            "revenueAttributedGtq": agg[5],
            "cpm": cpm,
            "cpc": cpc,
            "ctr": ctr,
            "byCampaign": by_campaign,
            "lastSyncAt": agg[6],
        }}
    finally:
        conn.close()
```

**3.5 `cmd_generate_coupon`** — STUB returning pending status.

```python
def cmd_generate_coupon(args):
    """STUB R5: worker /api/coupons/generate endpoint contract incompatible with R4 plan.
    Returns pending status until a separate worker task aligns the contract.
    See spec sec 6 decision 7.
    """
    return {
        "ok": False,
        "error": "Cupón pendiente — worker endpoint /api/coupons/generate requiere actualización separada (R5 task)",
        "pending": True,
    }
```

**3.6 Register in COMMANDS dict:**

```python
    "sync_meta_ads": cmd_sync_meta_ads,
    "list_campaigns": cmd_list_campaigns,
    "get_campaign_detail": cmd_get_campaign_detail,
    "get_funnel_awareness_real": cmd_get_funnel_awareness_real,
    "generate_coupon": cmd_generate_coupon,
```

**3.7 Smoke tests:**

```bash
cd /c/Users/Diego/el-club/erp

# Empty case (no campaigns synced yet)
echo '{"cmd":"list_campaigns"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"get_funnel_awareness_real"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"get_campaign_detail","campaignId":"DOES_NOT_EXIST"}' | python scripts/erp_rust_bridge.py

# Stub coupon
echo '{"cmd":"generate_coupon","customerId":1,"type":"percent","value":10,"apiKey":"x"}' | python scripts/erp_rust_bridge.py

# Real Meta sync (will hit real API — only run if Diego is OK with that)
echo '{"cmd":"sync_meta_ads","days":7}' | python scripts/erp_rust_bridge.py
```

Expected outputs:
- list_campaigns: `{"ok":true, "campaigns":[]}` (empty initially)
- get_funnel_awareness_real: `{"ok":true,"awareness":{...all zeros...}}`
- get_campaign_detail: `{"ok":true, "detail":null}`
- generate_coupon: `{"ok":false, "error":"...pendiente...", "pending":true}`
- sync_meta_ads: `{"ok":true,"campaignsSynced":N,...}` if API works, or `{"ok":false,"error":"..."}` if token issue.

Commit: `feat(comercial): bridge R5 — 5 handlers (Meta sync, campaigns, awareness, cupón stub)`

---

### Task 4: Rust commands — 5 wrappers

**File:** `overhaul/src-tauri/src/lib.rs`

After the R4 section, add:

```rust
// ─── Comercial R5 ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SyncMetaAdsArgs {
    pub days: Option<i64>,
    pub date_preset: Option<String>,
}

#[tauri::command]
async fn comercial_sync_meta_ads(args: SyncMetaAdsArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "sync_meta_ads",
        "days": args.days,
        "datePreset": args.date_preset,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListCampaignsArgs {
    pub period_days: Option<i64>,
}

#[tauri::command]
async fn comercial_list_campaigns(args: ListCampaignsArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "list_campaigns",
        "periodDays": args.period_days,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("campaigns").cloned().unwrap_or(Value::Array(vec![])))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetCampaignDetailArgs {
    pub campaign_id: String,
    pub period_days: Option<i64>,
}

#[tauri::command]
async fn comercial_get_campaign_detail(args: GetCampaignDetailArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "get_campaign_detail",
        "campaignId": args.campaign_id,
        "periodDays": args.period_days,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("detail").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetFunnelAwarenessRealArgs {
    pub period_start: Option<String>,
    pub period_end: Option<String>,
}

#[tauri::command]
async fn comercial_get_funnel_awareness_real(args: GetFunnelAwarenessRealArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "get_funnel_awareness_real",
        "periodStart": args.period_start,
        "periodEnd": args.period_end,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("awareness").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerateCouponArgs {
    pub customer_id: i64,
    #[serde(rename = "type")]
    pub type_: String,
    pub value: f64,
    pub expires_in_days: Option<i64>,
}

#[tauri::command]
async fn comercial_generate_coupon(args: GenerateCouponArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "generate_coupon",
        "customerId": args.customer_id,
        "type": args.type_,
        "value": args.value,
        "expiresInDays": args.expires_in_days,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}
```

Register in `tauri::generate_handler!`:

```rust
comercial_sync_meta_ads,
comercial_list_campaigns,
comercial_get_campaign_detail,
comercial_get_funnel_awareness_real,
comercial_generate_coupon,
```

Verify cargo check 0 errors.

Commit: `feat(comercial): Rust commands R5 — 5 wrappers (Meta sync, campaigns, cupón stub)`

---

### Task 5: Adapter contract — 5 method signatures

**File:** `overhaul/src/lib/adapter/types.ts`

Extend imports:
```typescript
import type {
  // ...existing R1+R2+R4 imports
  Campaign, CampaignDetail, FunnelAwarenessReal, MetaSyncResult
} from '../data/comercial';
```

Add to `interface Adapter` after R4 section:

```typescript
	// ─── Comercial R5 ──────────────────────────────────────────
	syncMetaAds(args?: { days?: number; datePreset?: string }): Promise<MetaSyncResult>;
	listCampaigns(args?: { periodDays?: number }): Promise<Campaign[]>;
	getCampaignDetail(campaignId: string, periodDays?: number): Promise<CampaignDetail | null>;
	getFunnelAwarenessReal(args?: { periodStart?: string; periodEnd?: string }): Promise<FunnelAwarenessReal | null>;
	generateCoupon(args: { customerId: number; type: 'percent' | 'amount'; value: number; expiresInDays?: number }): Promise<{ ok: boolean; code?: string; error?: string; pending?: boolean }>;
```

Type check: errors only about missing impls in tauri.ts/browser.ts (Task 6 will fix).

Commit: `feat(comercial): adapter R5 contract — 5 method signatures`

---

### Task 6: Adapter Tauri impls + browser stubs

**File:** `overhaul/src/lib/adapter/tauri.ts`

Extend imports + add 5 impls:

```typescript
async syncMetaAds(args = {}) {
  return invoke<MetaSyncResult>('comercial_sync_meta_ads', { args: { days: args.days, datePreset: args.datePreset } });
},

async listCampaigns(args = {}) {
  const result = await invoke<unknown>('comercial_list_campaigns', { args: { periodDays: args.periodDays } });
  return (result as Campaign[]) ?? [];
},

async getCampaignDetail(campaignId: string, periodDays?: number) {
  const result = await invoke<unknown>('comercial_get_campaign_detail', { args: { campaignId, periodDays } });
  return (result as CampaignDetail | null) ?? null;
},

async getFunnelAwarenessReal(args = {}) {
  const result = await invoke<unknown>('comercial_get_funnel_awareness_real', { args: { periodStart: args.periodStart, periodEnd: args.periodEnd } });
  return (result as FunnelAwarenessReal | null) ?? null;
},

async generateCoupon(args) {
  return invoke<{ ok: boolean; code?: string; error?: string; pending?: boolean }>(
    'comercial_generate_coupon',
    { args: { customerId: args.customerId, type: args.type, value: args.value, expiresInDays: args.expiresInDays } }
  );
},
```

**File:** `overhaul/src/lib/adapter/browser.ts`

```typescript
async syncMetaAds() {
  throw new NotAvailableInBrowser('syncMetaAds');
},
async listCampaigns() {
  return [];
},
async getCampaignDetail() {
  return null;
},
async getFunnelAwarenessReal() {
  return null;
},
async generateCoupon() {
  return { ok: false, error: 'Not available in browser', pending: true };
},
```

Verify npm check 0 errors.

Commit: `feat(comercial): adapter R5 impls — Tauri + browser stubs (5 methods)`

---

### Task 7: Detector — `detectCampaignPerfDrop`

**File:** `overhaul/src/lib/data/eventDetector.ts`

Add after `detectVipInactive60d`:

```typescript
/**
 * Detector "Campaign performance drop +30%".
 * Compares cost-per-conversion last 7d vs prior 7d. Triggers if degradation > 30% AND total spend > Q100.
 * severity: warn (actionable but not blocking).
 */
export async function detectCampaignPerfDrop(): Promise<DetectedEvent | null> {
  let campaigns;
  try {
    campaigns = await adapter.listCampaigns({ periodDays: 14 });
  } catch (e) {
    console.warn('[detector] listCampaigns failed', e);
    return null;
  }

  // For each campaign, compute split: last 7d vs prior 7d
  // Since listCampaigns returns 14d aggregates, we need finer detail.
  // Simplest: filter by 14d total spend > Q100 first, then fetch detail for time-split.
  const candidates = campaigns.filter((c: any) => c.totalSpendGtq > 100 && c.totalConversions > 0);
  if (candidates.length === 0) return null;

  const dropping: { c: any; deg: number }[] = [];
  for (const c of candidates) {
    try {
      const detail = await adapter.getCampaignDetail(c.campaignId, 14);
      if (!detail || !detail.daily || detail.daily.length < 8) continue;

      // Sort daily ASC
      const daily = [...detail.daily].sort((a, b) => a.date.localeCompare(b.date));
      const half = Math.floor(daily.length / 2);
      const prior = daily.slice(0, half);
      const recent = daily.slice(half);

      const priorSpend = prior.reduce((s, d) => s + d.spendGtq, 0);
      const priorConv = prior.reduce((s, d) => s + d.conversions, 0);
      const recentSpend = recent.reduce((s, d) => s + d.spendGtq, 0);
      const recentConv = recent.reduce((s, d) => s + d.conversions, 0);

      if (priorConv === 0 || recentConv === 0) continue;
      const priorCpc = priorSpend / priorConv;
      const recentCpc = recentSpend / recentConv;
      const ratio = recentCpc / priorCpc;

      if (ratio > 1.30) {
        dropping.push({ c, deg: Math.round((ratio - 1) * 100) });
      }
    } catch (e) {
      console.warn(`[detector] detail fetch failed for ${c.campaignId}`, e);
    }
  }

  if (dropping.length === 0) return null;

  return {
    type: 'campaign_perf_drop',
    severity: 'warn',
    title: `${dropping.length} campaña${dropping.length === 1 ? '' : 's'} con CPC ↑ +30%`,
    sub: dropping.slice(0, 3).map(d => `${d.c.campaignName ?? d.c.campaignId} (+${d.deg}%)`).join(' · ')
      + (dropping.length > 3 ? ` · +${dropping.length - 3}` : ''),
    itemsAffected: dropping.map(d => ({
      type: 'campaign',
      id: String(d.c.campaignId),
      hint: `+${d.deg}% CPC vs 7d previo`,
    })),
  };
}
```

Wire into `runOnce()`:

```typescript
const campaignDrop = await detectCampaignPerfDrop();
if (campaignDrop) await persistEvent(campaignDrop);
```

If `EventType` union doesn't include `'campaign_perf_drop'`, extend it in comercial.ts.

Commit: `feat(comercial): detector R5 — campaign perf drop +30% (severity warn)`

---

### Task 8: TimeSeriesChart — vanilla SVG component

**File:** `overhaul/src/lib/components/comercial/charts/TimeSeriesChart.svelte` (NEW)

```svelte
<script lang="ts">
  interface DataPoint {
    date: string;
    value: number;
    label?: string;
  }

  interface Props {
    data: DataPoint[];
    width?: number;
    height?: number;
    strokeColor?: string;
    fillColor?: string;
    yAxisLabel?: string;
  }

  let {
    data,
    width = 280,
    height = 140,
    strokeColor = 'var(--color-accent)',
    fillColor = 'rgba(74,222,128,0.12)',
    yAxisLabel = ''
  }: Props = $props();

  const PADDING = { top: 10, right: 10, bottom: 24, left: 36 };

  let innerWidth = $derived(width - PADDING.left - PADDING.right);
  let innerHeight = $derived(height - PADDING.top - PADDING.bottom);

  let maxVal = $derived(Math.max(...data.map(d => d.value), 1));
  let minVal = 0;

  function xPos(i: number): number {
    if (data.length <= 1) return PADDING.left + innerWidth / 2;
    return PADDING.left + (i / (data.length - 1)) * innerWidth;
  }

  function yPos(v: number): number {
    return PADDING.top + (1 - (v - minVal) / (maxVal - minVal || 1)) * innerHeight;
  }

  let polylinePoints = $derived(data.map((d, i) => `${xPos(i)},${yPos(d.value)}`).join(' '));
  let areaPath = $derived(
    data.length > 0
      ? `M ${xPos(0)} ${PADDING.top + innerHeight} L ${data.map((d, i) => `${xPos(i)} ${yPos(d.value)}`).join(' L ')} L ${xPos(data.length - 1)} ${PADDING.top + innerHeight} Z`
      : ''
  );

  // Y-axis ticks (4)
  let yTicks = $derived(
    [0, 0.25, 0.5, 0.75, 1].map(p => ({
      value: minVal + (maxVal - minVal) * p,
      y: PADDING.top + (1 - p) * innerHeight,
    }))
  );

  // X-axis ticks (every Nth, max 6)
  let xTickInterval = $derived(Math.max(1, Math.ceil(data.length / 6)));
</script>

<svg {width} {height} viewBox="0 0 {width} {height}" class="block">
  <!-- Y axis grid -->
  {#each yTicks as tick}
    <line
      x1={PADDING.left} y1={tick.y}
      x2={width - PADDING.right} y2={tick.y}
      stroke="var(--color-border)" stroke-width="0.5" stroke-dasharray="2,3"
    />
    <text
      x={PADDING.left - 4} y={tick.y + 3}
      text-anchor="end" font-size="8" fill="var(--color-text-muted)"
      font-family="monospace"
    >{Math.round(tick.value)}</text>
  {/each}

  <!-- X axis labels -->
  {#each data as d, i}
    {#if i % xTickInterval === 0 || i === data.length - 1}
      <text
        x={xPos(i)} y={height - PADDING.bottom + 12}
        text-anchor="middle" font-size="8" fill="var(--color-text-muted)"
        font-family="monospace"
      >{d.date.slice(5)}</text>
    {/if}
  {/each}

  <!-- Y axis label -->
  {#if yAxisLabel}
    <text
      x={PADDING.left - 28} y={PADDING.top + innerHeight / 2}
      transform="rotate(-90 {PADDING.left - 28} {PADDING.top + innerHeight / 2})"
      text-anchor="middle" font-size="8" fill="var(--color-text-tertiary)"
    >{yAxisLabel}</text>
  {/if}

  <!-- Filled area -->
  {#if areaPath}
    <path d={areaPath} fill={fillColor} />
  {/if}

  <!-- Polyline -->
  {#if data.length > 1}
    <polyline points={polylinePoints} fill="none" stroke={strokeColor} stroke-width="1.5" />
  {/if}

  <!-- Dots -->
  {#each data as d, i}
    <circle
      cx={xPos(i)} cy={yPos(d.value)} r="2"
      fill={strokeColor}
    >
      <title>{d.date}: {d.value}{d.label ? ` (${d.label})` : ''}</title>
    </circle>
  {/each}
</svg>
```

Verify npm check 0 errors.

Commit: `feat(comercial): chart R5 — TimeSeriesChart (vanilla SVG)`

---

### Task 9: CampaignDetailModal

**File:** `overhaul/src/lib/components/comercial/modals/CampaignDetailModal.svelte` (NEW)

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CampaignDetail } from '$lib/data/comercial';
  import { Loader2, TrendingUp } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import TimeSeriesChart from '../charts/TimeSeriesChart.svelte';
  import OrderDetailModal from './OrderDetailModal.svelte';

  interface Props {
    campaignId: string;
    onClose: () => void;
  }
  let { campaignId, onClose }: Props = $props();

  let detail = $state<CampaignDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let openOrderRef = $state<string | null>(null);
  let chartMetric = $state<'spendGtq' | 'conversions' | 'revenueGtq'>('spendGtq');

  async function load() {
    loading = true;
    error = null;
    try {
      detail = await adapter.getCampaignDetail(campaignId, 30);
      if (!detail) error = `Campaña ${campaignId} sin datos en últimos 30d`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { void load(); });

  function fmtDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }

  let chartData = $derived.by(() => {
    if (!detail) return [];
    return detail.daily.map(d => ({
      date: d.date,
      value: chartMetric === 'spendGtq' ? d.spendGtq
           : chartMetric === 'conversions' ? d.conversions
           : d.revenueGtq,
      label: chartMetric === 'spendGtq' ? `Q${d.spendGtq.toFixed(0)}`
           : chartMetric === 'conversions' ? `${d.conversions} conv`
           : `Q${d.revenueGtq.toFixed(0)} rev`,
    }));
  });
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" /> <span class="text-[14px]">Cargando campaña…</span>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {:else if detail}
      {@const c = detail.campaign}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
          <TrendingUp size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">{c.campaignName ?? c.campaignId}</div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            <span class="text-mono">Q{c.totalSpendGtq.toFixed(0)}</span> spend ·
            {c.totalImpressions.toLocaleString()} imp ·
            {c.totalClicks} clicks ·
            {c.totalConversions} conv
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if detail}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px] overflow-hidden">
        <!-- Chart + metric switcher -->
        <div class="border-r border-[var(--color-border)] overflow-y-auto px-6 py-4">
          <div class="mb-3 flex items-center gap-2">
            {#each [['spendGtq','Spend'],['conversions','Conv'],['revenueGtq','Revenue']] as [key, lbl]}
              {@const active = chartMetric === key}
              <button
                type="button"
                onclick={() => (chartMetric = key as any)}
                class="rounded-[3px] border px-2.5 py-0.5 text-[10px]"
                style="
                  background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
                  border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
                  color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
                "
              >{lbl}</button>
            {/each}
          </div>

          {#if detail.daily.length === 0}
            <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">> sin data en período</div>
          {:else}
            <TimeSeriesChart data={chartData} width={520} height={200} yAxisLabel={chartMetric} />
            <div class="mt-2 text-[10px] text-[var(--color-text-muted)]">
              {detail.daily.length} días · click un punto en el chart para ver fecha exacta (hover)
            </div>
          {/if}
        </div>

        <!-- Sidebar: KPIs + attributed sales -->
        <div class="overflow-y-auto bg-[var(--color-surface-0)] px-4 py-4">
          {@const c = detail.campaign}
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">KPIs</div>
          <div class="mb-4 space-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CTR</span><span class="text-mono">{c.totalImpressions ? ((c.totalClicks / c.totalImpressions) * 100).toFixed(2) : '—'}%</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CPC</span><span class="text-mono">{c.totalClicks ? `Q${(c.totalSpendGtq / c.totalClicks).toFixed(2)}` : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Cost/Conv</span><span class="text-mono">{c.costPerConversionGtq !== null ? `Q${c.costPerConversionGtq.toFixed(0)}` : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">ROAS</span><span class="text-mono">{c.totalSpendGtq ? (c.totalRevenueGtq / c.totalSpendGtq).toFixed(2) + 'x' : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Last sync</span><span class="text-mono text-[10px]">{c.lastSyncAt ? fmtDate(c.lastSyncAt) : '—'}</span></div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Sales atribuidas · {detail.attributedSales.length}</div>
          {#if detail.attributedSales.length === 0}
            <div class="text-mono text-[10px] text-[var(--color-text-tertiary)]">> sin sales atribuidas</div>
          {:else}
            <div class="space-y-1.5">
              {#each detail.attributedSales.slice(0, 20) as s}
                <button
                  type="button"
                  onclick={() => (openOrderRef = s.ref)}
                  class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10.5px] hover:border-[var(--color-accent)]"
                >
                  <div class="flex items-baseline justify-between">
                    <span class="text-mono">{s.ref}</span>
                    <span class="text-mono font-semibold" style="color: var(--color-accent);">Q{s.totalGtq.toFixed(0)}</span>
                  </div>
                  <div class="text-[9.5px] text-[var(--color-text-tertiary)]">
                    {s.customerName ?? '—'} · {fmtDate(s.occurredAt)}
                  </div>
                </button>
              {/each}
              {#if detail.attributedSales.length > 20}
                <div class="text-[10px] text-[var(--color-text-muted)]">+{detail.attributedSales.length - 20} más</div>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
    >Cerrar</button>
  {/snippet}
</BaseModal>

{#if openOrderRef}
  <OrderDetailModal orderRef={openOrderRef} onClose={() => { openOrderRef = null; }} />
{/if}
```

Verify npm check 0 errors.

Commit: `feat(comercial): CampaignDetailModal R5 — header + chart + sales attribuidas`

---

### Task 10: FunnelTab — wire Awareness card to real data

**File:** `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte`

Steps:

1. **Add state for awareness real data and selected campaign:**

```typescript
import CampaignDetailModal from '../modals/CampaignDetailModal.svelte';
// (other imports unchanged)

let awarenessReal = $state<FunnelAwarenessReal | null>(null);
let openCampaignId = $state<string | null>(null);
let showCampaignPicker = $state(false);
```

2. **Add to FunnelAwarenessReal type import** at top.

3. **Load on mount** (within existing $effect or new):

```typescript
$effect(() => {
  void (async () => {
    try {
      awarenessReal = await adapter.getFunnelAwarenessReal();
    } catch (e) {
      console.warn('[funnel] awareness load failed', e);
    }
  })();
});
```

4. **Replace Awareness card body** (lines 84-93 per Explore agent's findings):

```svelte
<div class="awareness-card">
  <div class="text-display text-[10px] text-[var(--color-text-tertiary)]">Awareness</div>
  {#if awarenessReal && awarenessReal.totalCampaigns > 0}
    <div class="mt-2 space-y-1 text-[11.5px]">
      <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Imp</span><span class="text-mono">{awarenessReal.impressions.toLocaleString()}</span></div>
      <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Clicks</span><span class="text-mono">{awarenessReal.clicks.toLocaleString()}</span></div>
      <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Spend</span><span class="text-mono" style="color: var(--color-accent);">Q{awarenessReal.spendGtq.toFixed(0)}</span></div>
      <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CTR</span><span class="text-mono">{awarenessReal.ctr ? `${awarenessReal.ctr.toFixed(2)}%` : '—'}</span></div>
    </div>
    <button
      type="button"
      onclick={() => {
        if (awarenessReal!.byCampaign.length === 1) {
          openCampaignId = awarenessReal!.byCampaign[0].campaignId;
        } else {
          showCampaignPicker = true;
        }
      }}
      class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
    >Ver detalle ({awarenessReal.totalCampaigns} camp.) →</button>
  {:else}
    <div class="mt-2 text-[11.5px] text-[var(--color-text-tertiary)]">
      Sin sync de Meta Ads aún.
      <button type="button" onclick={() => onSwitchTab?.('settings')} class="text-[var(--color-accent)] hover:underline">Configurar →</button>
    </div>
  {/if}
</div>
```

5. **Add campaign picker** (small inline list when multiple):

```svelte
{#if showCampaignPicker && awarenessReal}
  <div class="picker-backdrop" onclick={() => (showCampaignPicker = false)}>
    <div class="picker-card" onclick={(e) => e.stopPropagation()}>
      <div class="text-display mb-2 text-[10px] text-[var(--color-text-tertiary)]">Elegí una campaña</div>
      {#each awarenessReal.byCampaign as bc}
        <button
          type="button"
          onclick={() => { openCampaignId = bc.campaignId; showCampaignPicker = false; }}
          class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 mb-1 text-[11px] hover:border-[var(--color-accent)]"
        >
          <div class="flex items-baseline justify-between">
            <span>{bc.campaignName ?? bc.campaignId}</span>
            <span class="text-mono" style="color: var(--color-accent);">Q{bc.spendGtq.toFixed(0)}</span>
          </div>
        </button>
      {/each}
    </div>
  </div>
{/if}

{#if openCampaignId}
  <CampaignDetailModal campaignId={openCampaignId} onClose={() => (openCampaignId = null)} />
{/if}
```

6. **Add CSS for picker-backdrop / picker-card** (or use Tailwind inline). Keep style consistent with BaseModal aesthetic.

Verify npm check 0 errors.

Commit: `feat(comercial): FunnelTab R5 — Awareness real data + CampaignDetailModal drilldown`

---

### Task 11: SettingsTab — Sync Meta Ads button

**File:** `overhaul/src/lib/components/comercial/tabs/SettingsTab.svelte`

Add a new "Meta Ads sync" section. Pattern after the existing ManyChat sync section (R2-combo).

```svelte
<script lang="ts">
  // Add to existing imports:
  import { RefreshCw, ExternalLink as ExtLink, AlertCircle } from 'lucide-svelte';
  // ... existing imports

  let metaSyncing = $state(false);
  let metaResult = $state<MetaSyncResult | null>(null);
  let metaError = $state<string | null>(null);

  async function syncMetaAds() {
    if (metaSyncing) return;
    metaSyncing = true;
    metaError = null;
    try {
      const result = await adapter.syncMetaAds({ days: 30 });
      metaResult = result;
      if (!result.ok) metaError = result.errors.join('; ') || 'Error desconocido';
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e);
    } finally {
      metaSyncing = false;
    }
  }
</script>

<!-- In the body, after ManyChat section: -->
<section class="settings-section">
  <h2 class="text-display text-[10px] text-[var(--color-text-tertiary)]">Meta Ads</h2>
  <div class="mt-2 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
    <div class="flex items-center justify-between">
      <div>
        <div class="text-[12px] font-medium">Sincronizar Meta Ads</div>
        <div class="text-[10px] text-[var(--color-text-tertiary)]">Pull insights últimos 30d → campaigns_snapshot</div>
        {#if metaResult}
          <div class="mt-1 text-[10px]" style="color: {metaResult.ok ? 'var(--color-accent)' : 'var(--color-danger)'};">
            ✓ {metaResult.campaignsSynced} campañas · {metaResult.syncedAt}
            {#if metaResult.errors.length > 0}
              <span class="text-[var(--color-warning)]">· {metaResult.errors.length} errores</span>
            {/if}
          </div>
        {/if}
        {#if metaError}
          <div class="mt-1 text-[10px] text-[var(--color-danger)]">⚠ {metaError}</div>
        {/if}
      </div>
      <button
        type="button"
        onclick={syncMetaAds}
        disabled={metaSyncing}
        class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if metaSyncing}
          <Loader2 size={12} class="animate-spin" /> Sincronizando…
        {:else}
          <RefreshCw size={12} strokeWidth={2} /> Sincronizar
        {/if}
      </button>
    </div>
  </div>
</section>
```

Verify npm check 0 errors.

Commit: `feat(comercial): SettingsTab R5 — Meta Ads sync button + last-sync display`

---

### Task 12: Build MSI v0.1.31 + tag + LOG + push

1. **Bump version** in `overhaul/src-tauri/Cargo.toml` and `overhaul/src-tauri/tauri.conf.json` from `0.1.30` → `0.1.31`.

2. **Build:**
```bash
cd /c/Users/Diego/el-club/overhaul
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build 2>&1 | tail -30
```

3. **Verify MSI:**
```bash
ls -la "/c/Users/Diego/el-club/overhaul/src-tauri/target/release/bundle/msi/El Club ERP_0.1.31_x64_en-US.msi"
```

4. **Commit + tag:**
```bash
cd /c/Users/Diego/el-club
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json overhaul/src-tauri/Cargo.lock
git commit -m "chore(release): v0.1.31 — Comercial R5 (Ads + Performance)"
git tag v0.1.31
```

5. **Update LOG** at `elclub-catalogo-priv/docs/LOG.md` (prepend at top with R5 summary).

6. **Push:**
```bash
git push origin comercial-design
git push origin v0.1.31
```

---

## Self-review

Spec coverage:
- ✅ Sec 2: in-scope (Meta sync, awareness real data, CampaignDetailModal, time-series chart, detector, settings button, cupón stub) all have tasks
- ✅ Sec 3: data flow + Meta API integration + storage strategy all in Task 3
- ✅ Sec 4: every NEW/MODIFIED file has a corresponding task
- ✅ Sec 5: UX flows (sync, drilldown, alert) covered in Tasks 7+9+10+11
- ✅ Sec 6: 12 decisions baked in
- ✅ Sec 7: errors + edge cases handled in handlers
- ✅ Sec 8: schema delta is one ALTER (Task 1)
- ✅ Sec 9: release in Task 12

Placeholder scan: cupón is explicit STUB, documented in Task 3.5. No other TBD/TODO/placeholder fields.

Coverage gaps: None identified.
