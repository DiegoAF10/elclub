# Comercial R2-combo: Funnel + Pulso + ManyChat sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Funnel tab + Pulso bar fully functional with real data including ManyChat-driven leads/conversations. After ship, Diego sees the whole game in one view: leads in, active threads, orders, repeat rate, and conversion rates between stages.

**Architecture:** Pull-based sync from ventus-backoffice worker (KV-backed conversation store) into local SQLite via 1h interval + manual button. Funnel reads SQLite + computes pure-function KPIs. Pulso bar wires real current+prev range queries for all 6 KPI trends. One new detector ("leads sin responder >12h") extends R1's loop. Awareness etapa stays empty until R5; everything else is real.

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte
- Backend: Rust (Tauri commands), Python bridge (HTTP fetch + SQLite ops)
- Storage: SQLite local (rusqlite via bridge); messages stay in worker KV
- Worker: Cloudflare Workers — `ventus-system/backoffice/src/index.js` (auth via `DASHBOARD_KEY`)
- Verification: `npm run check` + `cargo check` + bridge smoke + manual smoke

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-26-comercial-r2-funnel-pulso-design.md` (commit `30115ff`)

**Branch:** `comercial-design`

**Versionado al completar:** ERP v0.1.28 → v0.1.29

---

## Patrón de testing en este codebase

Mismo que R1:
1. **TypeScript types como contract** — definir tipos antes que implementación.
2. **`npm run check`** debe pasar después de cada step de código (svelte-check + tsc).
3. **`cargo check`** debe pasar después de cambios de Rust.
4. **Bridge smoke tests** — cada handler nuevo se prueba con `echo '{"cmd":...}' | python scripts/erp_rust_bridge.py`.
5. **Smoke test manual** al final (Task 19) — Diego instala MSI y verifica.

---

## Pre-flight: Worker auth

Antes de Task 5 (worker endpoints), confirmar que `DASHBOARD_KEY` está seteado en ventus-backoffice:

```bash
cd /c/Users/Diego/ventus-system/backoffice
npx wrangler secret list 2>&1 | grep DASHBOARD_KEY
```

Si no existe, el implementer pregunta a Diego para que setee el secret antes de continuar Task 5. (En R1 Task 17 se usó `DASHBOARD_KEY` para el endpoint `/api/comercial/notify-diego`; debería estar.)

---

## Tasks

### Task 1: Schema migration — `meta_sync` table

**Files:**
- Modify: `el-club/erp/audit_db.py` (función `init_audit_schema()`)

- [ ] **Step 1: Localizar `init_audit_schema()` y la sección de tablas R1**

```bash
grep -n "def init_audit_schema\|comercial_events\|leads\|campaigns_snapshot" /c/Users/Diego/el-club/erp/audit_db.py | head -10
```

- [ ] **Step 2: Agregar `meta_sync` table al schema**

Después de la creación de `campaigns_snapshot` (o donde encajen las tablas R2), agregar:

```python
cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_sync (
        source TEXT PRIMARY KEY,         -- e.g. 'manychat'
        last_sync_at TEXT NOT NULL,
        last_status TEXT,                -- 'ok' | 'error'
        last_error TEXT
    )
""")
```

`IF NOT EXISTS` hace la migración idempotente (re-run safe).

- [ ] **Step 3: Verify schema applied**

```bash
cd /c/Users/Diego/el-club/erp
python -c "from db import get_conn; conn = get_conn(); print([r[1] for r in conn.execute('PRAGMA table_info(meta_sync)').fetchall()])"
```

Expected output: `['source', 'last_sync_at', 'last_status', 'last_error']`

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add erp/audit_db.py
git commit -m "feat(comercial): schema R2 — meta_sync table para tracking de syncs"
```

---

### Task 2: Types core — Lead, ConversationMeta, Customer, FunnelKPIs

**Files:**
- Modify: `overhaul/src/lib/data/comercial.ts` (agregar 5 interfaces)

- [ ] **Step 1: Leer la estructura actual de comercial.ts**

```bash
grep -n "^export" /c/Users/Diego/el-club/overhaul/src/lib/data/comercial.ts | head -20
```

- [ ] **Step 2: Agregar los 5 nuevos types al final del archivo**

```typescript
// ─── R2-combo: ManyChat sync + Funnel ──────────────────────────────

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
  totalRevenueGtq: number;   // computed in query, not stored
  lastOrderAt: string | null;
}

export interface FunnelKPIs {
  awareness: { impressions: number; clicks: number; spendGtq: number; ctr: number };
  interest: {
    totalLeads: number;
    byPlatform: { wa: number; ig: number; messenger: number; web: number };
  };
  consideration: { activeConversations: number; pending: number; objection: number };
  sale: { ordersToday: number; awaitingPayment: number; awaitingShipment: number };
  retention: {
    totalCustomers: number;
    repeatRate: number;        // 0-1
    vipInactive60d: number;    // R4 will populate; R2-combo returns 0
    ltvAvgGtq: number;
  };
  conversion: {
    awarenessToInterest: number;     // 0-1
    interestToConsideration: number;
    considerationToSale: number;
    saleToRetention: number;
  };
}

export interface MetaSyncStatus {
  source: string;
  lastSyncAt: string | null;
  lastStatus: 'ok' | 'error' | null;
  lastError: string | null;
}
```

- [ ] **Step 3: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/data/comercial.ts
git commit -m "feat(comercial): types R2 — Lead, ConversationMeta, Customer, FunnelKPIs, MetaSyncStatus"
```

---

### Task 3: `resolvePreviousRange` helper en kpis.ts

**Files:**
- Modify: `overhaul/src/lib/data/kpis.ts` (agregar función exportada)

- [ ] **Step 1: Agregar la función después de `resolvePeriod`**

En `overhaul/src/lib/data/kpis.ts`, después de la función `resolvePeriod`:

```typescript
/**
 * Devuelve el rango inmediatamente anterior al `range` dado, con la misma duración.
 * Ejemplo: si range = hoy 00:00 → ahora, prev = ayer 00:00 → ayer-23:59.
 */
export function resolvePreviousRange(range: PeriodRange): PeriodRange {
  const startMs = new Date(range.start).getTime();
  const endMs = new Date(range.end).getTime();
  const duration = endMs - startMs;

  const prevEnd = new Date(startMs);
  const prevStart = new Date(startMs - duration);

  return {
    period: range.period,  // semánticamente "el período anterior del mismo tipo"
    start: prevStart.toISOString(),
    end: prevEnd.toISOString(),
  };
}
```

- [ ] **Step 2: Verify type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|kpis" | head -5
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/data/kpis.ts
git commit -m "feat(comercial): kpis — resolvePreviousRange helper para trend computation"
```

---

### Task 4: `funnelKpis.ts` — pure functions para Funnel

**Files:**
- Create: `overhaul/src/lib/data/funnelKpis.ts`

- [ ] **Step 1: Crear el archivo**

```typescript
// overhaul/src/lib/data/funnelKpis.ts
import type {
  FunnelKPIs,
  Lead,
  ConversationMeta,
  Customer,
  PeriodRange,
} from './comercial';

interface SaleForFunnel {
  ref: string;
  totalGtq: number;
  paidAt: string;          // ISO; sales.occurred_at as paidAt
  status: string;          // fulfillment_status
}

interface AdSpendForFunnel {
  campaignId: string;
  spendGtq: number;
  capturedAt: string;
  impressions?: number;
  clicks?: number;
}

const inRange = (iso: string, range: PeriodRange) =>
  iso >= range.start && iso <= range.end;

/**
 * Computa todos los KPIs del Funnel para un range dado.
 * Las sub-métricas siguen las definiciones del spec sec 5.5.
 *
 * Notas:
 * - Awareness viene de adSpend (vacío en R2-combo; R5 lo populiza).
 * - Retention.vipInactive60d retorna 0 hasta R4 (no hay VIP detection automática).
 * - Conversion rates se calculan best-effort sobre el período actual.
 */
export function computeFunnelKPIs(
  range: PeriodRange,
  leads: Lead[],
  conversations: ConversationMeta[],
  sales: SaleForFunnel[],
  customers: Customer[],
  adSpend: AdSpendForFunnel[]
): FunnelKPIs {
  // === Awareness ===
  const periodAdSpend = adSpend.filter((a) => inRange(a.capturedAt, range));
  const impressions = periodAdSpend.reduce((s, a) => s + (a.impressions ?? 0), 0);
  const clicks = periodAdSpend.reduce((s, a) => s + (a.clicks ?? 0), 0);
  const spendGtq = periodAdSpend.reduce((s, a) => s + a.spendGtq, 0);
  const ctr = impressions > 0 ? clicks / impressions : 0;

  // === Interest (leads) ===
  const periodLeads = leads.filter((l) => inRange(l.firstContactAt, range));
  const byPlatform = { wa: 0, ig: 0, messenger: 0, web: 0 };
  for (const l of periodLeads) {
    if (l.platform in byPlatform) byPlatform[l.platform]++;
  }
  const totalLeads = periodLeads.length;

  // === Consideration (conversations) ===
  const periodConvs = conversations.filter((c) => inRange(c.startedAt, range));
  const activeConversations = periodConvs.filter((c) => !c.outcome).length;
  const pending = periodConvs.filter((c) => c.outcome === 'pending').length;
  const objection = periodConvs.filter((c) => c.outcome === 'objection').length;

  // === Sale ===
  const periodSales = sales.filter((s) => inRange(s.paidAt, range));
  const ordersToday = periodSales.length;
  const awaitingPayment = periodSales.filter((s) => s.status === 'pending_payment').length;
  const awaitingShipment = periodSales.filter(
    (s) => s.status === 'paid' || s.status === 'awaiting_shipment'
  ).length;

  // === Retention ===
  const totalCustomers = customers.length;
  const repeatCustomers = customers.filter((c) => c.totalOrders > 1).length;
  const repeatRate = totalCustomers > 0 ? repeatCustomers / totalCustomers : 0;
  const vipInactive60d = 0; // R4 populará
  const ltvAvgGtq =
    totalCustomers > 0
      ? customers.reduce((s, c) => s + c.totalRevenueGtq, 0) / totalCustomers
      : 0;

  // === Conversion rates ===
  const awarenessToInterest = clicks > 0 ? totalLeads / clicks : 0;
  const interestToConsideration = totalLeads > 0 ? activeConversations / totalLeads : 0;
  const considerationToSale =
    periodConvs.length > 0
      ? periodConvs.filter((c) => c.outcome === 'sale').length / periodConvs.length
      : 0;
  const saleToRetention = ordersToday > 0 ? repeatCustomers / ordersToday : 0;

  return {
    awareness: { impressions, clicks, spendGtq, ctr },
    interest: { totalLeads, byPlatform },
    consideration: { activeConversations, pending, objection },
    sale: { ordersToday, awaitingPayment, awaitingShipment },
    retention: { totalCustomers, repeatRate, vipInactive60d, ltvAvgGtq },
    conversion: {
      awarenessToInterest,
      interestToConsideration,
      considerationToSale,
      saleToRetention,
    },
  };
}
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|funnelKpis" | head -10
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/data/funnelKpis.ts
git commit -m "feat(comercial): funnelKpis.ts — computeFunnelKPIs pure function"
```

---

### Task 5: Worker — endpoints `/api/comercial/sync-data` + `/api/comercial/conversation/:convId/messages`

**Files:**
- Modify: `ventus-system/backoffice/src/index.js`

- [ ] **Step 0: Verificar que `DASHBOARD_KEY` está seteado en el worker**

```bash
cd /c/Users/Diego/ventus-system/backoffice
npx wrangler secret list 2>&1 | grep DASHBOARD_KEY
```

Si no aparece, STOP — pedir a Diego que lo setee con `wrangler secret put DASHBOARD_KEY` antes de continuar.

- [ ] **Step 1: Localizar el patrón de routing y de auth en index.js**

```bash
grep -n "DASHBOARD_KEY\|requireDashboardAuth\|/api/comercial/" /c/Users/Diego/ventus-system/backoffice/src/index.js | head -20
```

Expected: encontrar la función auth (e.g., `requireDashboardAuth(request, env)` o similar) y el endpoint `/api/comercial/notify-diego` de R1.

- [ ] **Step 2: Agregar endpoint `/api/comercial/sync-data` después del existente `/api/comercial/notify-diego`**

```javascript
// GET /api/comercial/sync-data?since=<iso> — pull leads + conversations para ERP
if (path === '/api/comercial/sync-data' && method === 'GET') {
  const authErr = requireDashboardAuth(request, env);  // (or whatever the existing helper is)
  if (authErr) return authErr;

  const sinceParam = url.searchParams.get('since');
  const since = sinceParam || null;

  // Get conv_index for elclub brand
  const index = await env.DATA.get('conv_index:elclub', { type: 'json' }) || [];

  // Filter by since (ended_at >= since)
  const filtered = since
    ? index.filter((e) => (e.ended_at || e.started_at || '') >= since)
    : index;

  // Aggregate leads from index entries
  const leadsMap = new Map();
  const conversations = [];

  for (const entry of filtered) {
    const platform = entry.platform || 'web';
    const senderId = entry.sender_id || 'unknown';
    const leadKey = `${platform}:${senderId}`;

    // Lead aggregation
    if (!leadsMap.has(leadKey)) {
      leadsMap.set(leadKey, {
        leadId: null,             // ERP assigns
        name: entry.name || null,
        handle: entry.handle || null,
        phone: entry.phone || null,
        platform,
        senderId,
        sourceCampaignId: extractSourceCampaign(entry.tags || []),
        firstContactAt: entry.started_at,
        lastActivityAt: entry.ended_at,
        status: entry.outcome === 'sale' ? 'converted' : 'new',
        traitsJson: {},
      });
    } else {
      const existing = leadsMap.get(leadKey);
      if (entry.started_at < existing.firstContactAt) existing.firstContactAt = entry.started_at;
      if (entry.ended_at > existing.lastActivityAt) existing.lastActivityAt = entry.ended_at;
      if (entry.outcome === 'sale') existing.status = 'converted';
    }

    // Conversation
    conversations.push({
      convId: entry.id,
      leadId: null,             // ERP populates after lead upsert
      brand: entry.brand || 'elclub',
      platform,
      senderId,
      startedAt: entry.started_at,
      endedAt: entry.ended_at,
      outcome: entry.outcome || null,
      orderId: entry.order_id || null,
      messagesTotal: entry.messages_total || 0,
      tagsJson: entry.tags || [],
      analyzed: !!entry.analyzed,
      syncedAt: new Date().toISOString(),
    });
  }

  return new Response(
    JSON.stringify({
      since,
      until: new Date().toISOString(),
      leads: Array.from(leadsMap.values()),
      conversations,
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
}

// Helper (place at top of index.js or in a separate import)
function extractSourceCampaign(tags) {
  for (const tag of tags) {
    if (typeof tag === 'string' && tag.startsWith('source_campaign:')) {
      return tag.slice('source_campaign:'.length);
    }
  }
  return null;
}
```

**Important:** check the actual name of the auth helper before pasting. If it's not `requireDashboardAuth`, adjust. Look at how `/api/comercial/notify-diego` from R1 does auth and copy that pattern.

- [ ] **Step 3: Agregar endpoint `/api/comercial/conversation/:convId/messages`**

```javascript
// GET /api/comercial/conversation/:convId/messages — lazy fetch de transcript
const convMessagesMatch = path.match(/^\/api\/comercial\/conversation\/([^\/]+)\/messages$/);
if (convMessagesMatch && method === 'GET') {
  const authErr = requireDashboardAuth(request, env);
  if (authErr) return authErr;

  const convId = convMessagesMatch[1];
  const archive = await env.DATA.get(`conv_archive:${convId}`, { type: 'json' });

  if (!archive) {
    return new Response(JSON.stringify({ error: 'not_found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(
    JSON.stringify({ convId, messages: archive.messages || [] }),
    { headers: { 'Content-Type': 'application/json' } }
  );
}
```

- [ ] **Step 4: Deploy worker**

```bash
cd /c/Users/Diego/ventus-system/backoffice
npx wrangler deploy 2>&1 | tail -10
```

Expected: deploy success con Worker version.

- [ ] **Step 5: Smoke test ambos endpoints**

```bash
# Sync data sin since (full backfill)
curl -s -H "Authorization: Bearer $DASHBOARD_KEY" \
  "https://ventus-backoffice.ventusgt.workers.dev/api/comercial/sync-data" | head -c 500

# Sync data con since reciente
curl -s -H "Authorization: Bearer $DASHBOARD_KEY" \
  "https://ventus-backoffice.ventusgt.workers.dev/api/comercial/sync-data?since=2026-04-25T00:00:00Z" | head -c 500

# Lazy fetch (ID que no existe)
curl -s -H "Authorization: Bearer $DASHBOARD_KEY" \
  "https://ventus-backoffice.ventusgt.workers.dev/api/comercial/conversation/conv-fake-123/messages"
```

Expected:
- Primer call: JSON con `leads` + `conversations` (puede ser arrays vacíos si no hay data, eso es OK).
- Segundo: similar pero filtered.
- Tercer: `{"error":"not_found"}` con 404.

(Diego puede pasar `DASHBOARD_KEY` como env var temporal: `export DASHBOARD_KEY="OLf8SI13Qfc1h_Enw--tTBbG8yQQT_kd"`.)

- [ ] **Step 6: Commit (en repo ventus-system, NO push automático)**

```bash
cd /c/Users/Diego/ventus-system
git add backoffice/src/index.js
git commit -m "feat(comercial): worker endpoints — /sync-data + /conversation/:id/messages"
```

Reportar el SHA al controlador. Diego pushea cuando él decida.

---

### Task 6: Bridge Python — 5 handlers nuevos

**Files:**
- Modify: `el-club/erp/scripts/erp_rust_bridge.py`

- [ ] **Step 1: Agregar handlers al final, antes del dict COMMANDS**

```python
def cmd_sync_manychat(args):
    """Pull data desde el worker y upsertea leads + conversations.
    Args:
        since: ISO string o null (full backfill)
        worker_base: URL del worker
        dashboard_key: bearer token
    Returns:
        {ok, leadsUpserted, conversationsUpserted, lastSyncAt}
    """
    import json
    import urllib.request
    from db import get_conn

    since = args.get("since")
    worker_base = args.get("workerBase") or "https://ventus-backoffice.ventusgt.workers.dev"
    dashboard_key = args.get("dashboardKey")

    if not dashboard_key:
        return {"ok": False, "error": "dashboardKey required"}

    # Build URL
    qs = f"?since={since}" if since else ""
    url = f"{worker_base}/api/comercial/sync-data{qs}"

    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {dashboard_key}",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except Exception as e:
        return {"ok": False, "error": f"worker fetch failed: {e}"}

    leads_data = data.get("leads", [])
    convs_data = data.get("conversations", [])
    now_iso = data.get("until") or args.get("now") or ""

    conn = get_conn()
    leads_upserted = 0
    convs_upserted = 0
    try:
        # Upsert leads (UNIQUE composite (platform, sender_id))
        for ld in leads_data:
            try:
                conn.execute("""
                    INSERT INTO leads
                      (name, handle, phone, platform, sender_id, source_campaign_id,
                       first_contact_at, last_activity_at, status, traits_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, sender_id) DO UPDATE SET
                      name = COALESCE(excluded.name, leads.name),
                      handle = COALESCE(excluded.handle, leads.handle),
                      phone = COALESCE(excluded.phone, leads.phone),
                      source_campaign_id = COALESCE(excluded.source_campaign_id, leads.source_campaign_id),
                      first_contact_at = MIN(leads.first_contact_at, excluded.first_contact_at),
                      last_activity_at = MAX(leads.last_activity_at, excluded.last_activity_at),
                      status = excluded.status
                """, (
                    ld.get("name"), ld.get("handle"), ld.get("phone"),
                    ld.get("platform"), ld.get("senderId"),
                    ld.get("sourceCampaignId"),
                    ld.get("firstContactAt"), ld.get("lastActivityAt"),
                    ld.get("status") or "new",
                    json.dumps(ld.get("traitsJson") or {}),
                ))
                leads_upserted += 1
            except Exception as e:
                # Log per-row failure, continue
                print(f"[sync_manychat] lead upsert failed: {e}", flush=True)

        # Upsert conversations (PK conv_id)
        # First, build a lookup (platform, sender_id) -> lead_id from current state
        lead_lookup = {}
        for row in conn.execute("SELECT lead_id, platform, sender_id FROM leads").fetchall():
            lead_lookup[(row[1], row[2])] = row[0]

        for cv in convs_data:
            try:
                lead_id = lead_lookup.get((cv.get("platform"), cv.get("senderId")))
                conn.execute("""
                    INSERT INTO conversations
                      (conv_id, brand, platform, sender_id, started_at, ended_at,
                       outcome, order_id, messages_total, messages_json, tags_json,
                       analyzed, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, datetime('now'))
                    ON CONFLICT(conv_id) DO UPDATE SET
                      ended_at = excluded.ended_at,
                      outcome = excluded.outcome,
                      order_id = excluded.order_id,
                      messages_total = excluded.messages_total,
                      tags_json = excluded.tags_json,
                      analyzed = excluded.analyzed,
                      synced_at = datetime('now')
                """, (
                    cv.get("convId"), cv.get("brand"), cv.get("platform"),
                    cv.get("senderId"), cv.get("startedAt"), cv.get("endedAt"),
                    cv.get("outcome"), cv.get("orderId"), cv.get("messagesTotal", 0),
                    json.dumps(cv.get("tagsJson") or []),
                    1 if cv.get("analyzed") else 0,
                ))
                convs_upserted += 1
            except Exception as e:
                print(f"[sync_manychat] conv upsert failed: {e}", flush=True)

        # Update meta_sync
        conn.execute("""
            INSERT INTO meta_sync (source, last_sync_at, last_status, last_error)
            VALUES ('manychat', datetime('now'), 'ok', NULL)
            ON CONFLICT(source) DO UPDATE SET
              last_sync_at = datetime('now'),
              last_status = 'ok',
              last_error = NULL
        """)
        conn.commit()
        return {
            "ok": True,
            "leadsUpserted": leads_upserted,
            "conversationsUpserted": convs_upserted,
            "lastSyncAt": now_iso,
        }
    finally:
        conn.close()


def cmd_list_leads(args):
    """Lista leads con filtros opcionales por status y range."""
    import json
    from db import get_conn

    status = args.get("status")
    range_start = args.get("rangeStart")
    range_end = args.get("rangeEnd")

    sql = "SELECT lead_id, name, handle, phone, platform, sender_id, source_campaign_id, first_contact_at, last_activity_at, status, traits_json FROM leads"
    clauses = []
    params = []
    if status:
        clauses.append("status = ?"); params.append(status)
    if range_start and range_end:
        clauses.append("first_contact_at BETWEEN ? AND ?")
        params.extend([range_start, range_end])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY last_activity_at DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        leads = []
        for r in rows:
            try:
                traits = json.loads(r[10] or '{}')
            except Exception:
                traits = {}
            leads.append({
                "leadId": r[0], "name": r[1], "handle": r[2], "phone": r[3],
                "platform": r[4], "senderId": r[5], "sourceCampaignId": r[6],
                "firstContactAt": r[7], "lastActivityAt": r[8], "status": r[9],
                "traitsJson": traits,
            })
        return {"ok": True, "leads": leads}
    finally:
        conn.close()


def cmd_list_conversations(args):
    """Lista conversations con filtros opcionales."""
    import json
    from db import get_conn

    outcome = args.get("outcome")
    range_start = args.get("rangeStart")
    range_end = args.get("rangeEnd")
    lead_id = args.get("leadId")

    sql = """
        SELECT c.conv_id, l.lead_id, c.brand, c.platform, c.sender_id,
               c.started_at, c.ended_at, c.outcome, c.order_id, c.messages_total,
               c.tags_json, c.analyzed, c.synced_at
        FROM conversations c
        LEFT JOIN leads l ON l.platform = c.platform AND l.sender_id = c.sender_id
    """
    clauses = []
    params = []
    if outcome:
        clauses.append("c.outcome = ?"); params.append(outcome)
    if range_start and range_end:
        clauses.append("c.started_at BETWEEN ? AND ?")
        params.extend([range_start, range_end])
    if lead_id:
        clauses.append("l.lead_id = ?"); params.append(lead_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.ended_at DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        convs = []
        for r in rows:
            try:
                tags = json.loads(r[10] or '[]')
            except Exception:
                tags = []
            convs.append({
                "convId": r[0], "leadId": r[1], "brand": r[2], "platform": r[3],
                "senderId": r[4], "startedAt": r[5], "endedAt": r[6],
                "outcome": r[7], "orderId": r[8], "messagesTotal": r[9],
                "tagsJson": tags, "analyzed": bool(r[11]), "syncedAt": r[12],
            })
        return {"ok": True, "conversations": convs}
    finally:
        conn.close()


def cmd_list_customers(args):
    """Lista customers con totals computados (totalOrders, totalRevenueGtq, lastOrderAt)."""
    from db import get_conn

    last_order_before = args.get("lastOrderBefore")
    min_ltv_gtq = args.get("minLtvGtq")

    # Compute totals via LEFT JOIN sales
    sql = """
        SELECT c.customer_id, c.name, c.phone, c.email, c.source, c.first_order_at,
               COUNT(s.sale_id) AS total_orders,
               COALESCE(SUM(s.total), 0) AS total_revenue,
               MAX(s.occurred_at) AS last_order_at
        FROM customers c
        LEFT JOIN sales s ON s.customer_id = c.customer_id
        GROUP BY c.customer_id
    """
    having = []
    params = []
    if last_order_before:
        having.append("last_order_at < ?"); params.append(last_order_before)
    if min_ltv_gtq is not None:
        having.append("total_revenue >= ?"); params.append(min_ltv_gtq)
    if having:
        sql += " HAVING " + " AND ".join(having)
    sql += " ORDER BY total_revenue DESC LIMIT 500"

    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        customers = [{
            "customerId": r[0], "name": r[1] or "(sin nombre)", "phone": r[2],
            "email": r[3], "source": r[4], "firstOrderAt": r[5] or "",
            "totalOrders": r[6], "totalRevenueGtq": r[7], "lastOrderAt": r[8],
        } for r in rows]
        return {"ok": True, "customers": customers}
    finally:
        conn.close()


def cmd_get_meta_sync(args):
    """Devuelve el último estado de sync para una source."""
    from db import get_conn

    source = args.get("source") or "manychat"
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT source, last_sync_at, last_status, last_error FROM meta_sync WHERE source = ?",
            (source,)
        ).fetchone()
        if not row:
            return {"ok": True, "metaSync": {"source": source, "lastSyncAt": None, "lastStatus": None, "lastError": None}}
        return {"ok": True, "metaSync": {
            "source": row[0], "lastSyncAt": row[1], "lastStatus": row[2], "lastError": row[3]
        }}
    finally:
        conn.close()


def cmd_get_conversation_messages(args):
    """Lazy fetch de mensajes desde el worker."""
    import json
    import urllib.request

    conv_id = args.get("convId")
    worker_base = args.get("workerBase") or "https://ventus-backoffice.ventusgt.workers.dev"
    dashboard_key = args.get("dashboardKey")

    if not conv_id:
        return {"ok": False, "error": "convId required"}
    if not dashboard_key:
        return {"ok": False, "error": "dashboardKey required"}

    url = f"{worker_base}/api/comercial/conversation/{conv_id}/messages"
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {dashboard_key}",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        return {"ok": True, "messages": data.get("messages", [])}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "messages": [], "note": "purged_or_missing"}
        return {"ok": False, "error": f"worker http {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}
```

- [ ] **Step 2: Registrar los 6 nuevos commands en COMMANDS dict**

Agregar al dict (NO reemplazar — APPEND):

```python
    "sync_manychat": cmd_sync_manychat,
    "list_leads": cmd_list_leads,
    "list_conversations": cmd_list_conversations,
    "list_customers": cmd_list_customers,
    "get_meta_sync": cmd_get_meta_sync,
    "get_conversation_messages": cmd_get_conversation_messages,
```

- [ ] **Step 3: Smoke test los 4 que no requieren auth/network**

```bash
cd /c/Users/Diego/el-club/erp

echo '{"cmd":"list_leads"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"list_conversations"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"list_customers"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"get_meta_sync"}' | python scripts/erp_rust_bridge.py
```

Expected: cada uno retorna `{"ok": true, ...}` con arrays vacíos (no hay leads/convs todavía) o data real (customers existirán de sales).

- [ ] **Step 4: Smoke test sync_manychat con dashboardKey**

```bash
echo '{"cmd":"sync_manychat","dashboardKey":"OLf8SI13Qfc1h_Enw--tTBbG8yQQT_kd"}' | python scripts/erp_rust_bridge.py
```

(Usar el DASHBOARD_KEY actual de ventus-backoffice — Diego puede confirmarlo.)

Expected: `{"ok": true, "leadsUpserted": N, "conversationsUpserted": M, "lastSyncAt": "..."}`. Si DASHBOARD_KEY equivocado, retorna `{"ok": false, "error": "worker fetch failed: ..."}`.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Diego/el-club
git add erp/scripts/erp_rust_bridge.py
git commit -m "feat(comercial): bridge R2 — sync_manychat + list/get handlers (leads/convs/customers/meta/messages)"
```

---

### Task 7: Rust Tauri commands — 6 wrappers

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Agregar structs + commands en la sección Comercial R1 existente**

Después de los commands existentes de Comercial R1:

```rust
// ─── Comercial R2-combo ────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SyncManychatArgs {
    pub since: Option<String>,
    pub worker_base: Option<String>,
    pub dashboard_key: String,
}

#[tauri::command]
async fn comercial_sync_manychat(args: SyncManychatArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "sync_manychat",
        "since": args.since,
        "workerBase": args.worker_base,
        "dashboardKey": args.dashboard_key,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListLeadsFilter {
    pub status: Option<String>,
    pub range_start: Option<String>,
    pub range_end: Option<String>,
}

#[tauri::command]
async fn comercial_list_leads(filter: ListLeadsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_leads",
        "status": filter.status,
        "rangeStart": filter.range_start,
        "rangeEnd": filter.range_end,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("leads").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListConvsFilter {
    pub outcome: Option<String>,
    pub range_start: Option<String>,
    pub range_end: Option<String>,
    pub lead_id: Option<i64>,
}

#[tauri::command]
async fn comercial_list_conversations(filter: ListConvsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_conversations",
        "outcome": filter.outcome,
        "rangeStart": filter.range_start,
        "rangeEnd": filter.range_end,
        "leadId": filter.lead_id,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("conversations").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListCustomersFilter {
    pub last_order_before: Option<String>,
    pub min_ltv_gtq: Option<f64>,
}

#[tauri::command]
async fn comercial_list_customers(filter: ListCustomersFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_customers",
        "lastOrderBefore": filter.last_order_before,
        "minLtvGtq": filter.min_ltv_gtq,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("customers").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_get_meta_sync(source: String) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_meta_sync", "source": source });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("metaSync").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetConvMessagesArgs {
    pub conv_id: String,
    pub worker_base: Option<String>,
    pub dashboard_key: String,
}

#[tauri::command]
async fn comercial_get_conversation_messages(args: GetConvMessagesArgs) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "get_conversation_messages",
        "convId": args.conv_id,
        "workerBase": args.worker_base,
        "dashboardKey": args.dashboard_key,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("messages").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}
```

- [ ] **Step 2: Registrar los 6 commands en `tauri::generate_handler!`**

En el macro de generate_handler (junto a los comercial R1 commands), agregar:

```rust
comercial_sync_manychat,
comercial_list_leads,
comercial_list_conversations,
comercial_list_customers,
comercial_get_meta_sync,
comercial_get_conversation_messages,
```

- [ ] **Step 3: cargo check**

```bash
cd /c/Users/Diego/el-club/overhaul/src-tauri
export PATH="$HOME/.cargo/bin:$PATH"
cargo check 2>&1 | grep "^error" | head -10
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src-tauri/src/lib.rs
git commit -m "feat(comercial): Rust commands R2 — 6 wrappers para sync + lists + meta + messages"
```

---

### Task 8: Adapter contract — types.ts (interface signatures)

**Files:**
- Modify: `overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Agregar imports nuevos al top**

Localizar el `import type { ... } from '../data/comercial'` existente y extenderlo:

```typescript
import type {
  ComercialEvent, EventStatus, OrderForModal, PeriodRange,
  Lead, ConversationMeta, ConversationMessage, Customer, MetaSyncStatus,
  DetectedEvent
} from '../data/comercial';
```

(Si `DetectedEvent` aún no está en comercial.ts y se importa de eventDetector, mantener ese import separado.)

- [ ] **Step 2: Agregar 6 method signatures en interface Adapter**

Después de la sección `// ─── Comercial R1 ────`:

```typescript
	// ─── Comercial R2-combo ────────────────────────────────────
	syncManychatData(args: { since: string | null; workerBase?: string; dashboardKey: string }): Promise<{ ok: boolean; leadsUpserted: number; conversationsUpserted: number; lastSyncAt: string; error?: string }>;
	listLeads(filter?: { status?: string; range?: PeriodRange }): Promise<Lead[]>;
	listConversations(filter?: { outcome?: string; range?: PeriodRange; leadId?: number }): Promise<ConversationMeta[]>;
	listCustomers(filter?: { lastOrderBefore?: string; minLtvGtq?: number }): Promise<Customer[]>;
	getMetaSync(source: string): Promise<MetaSyncStatus>;
	getConversationMessages(args: { convId: string; workerBase?: string; dashboardKey: string }): Promise<ConversationMessage[]>;
```

- [ ] **Step 3: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors sobre métodos faltantes en tauri.ts y browser.ts (Task 9 y 10 los resuelven).

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/adapter/types.ts
git commit -m "feat(comercial): adapter R2 contract — sync, list/get methods en types.ts"
```

---

### Task 9: Adapter Tauri impls + browser stubs

**Files:**
- Modify: `overhaul/src/lib/adapter/tauri.ts`
- Modify: `overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Agregar imports + 6 impls a tauri.ts**

En la sección de imports type al top, extender:

```typescript
import type {
  ComercialEvent, EventStatus, OrderForModal, PeriodRange,
  Lead, ConversationMeta, ConversationMessage, Customer, MetaSyncStatus
} from '../data/comercial';
```

En la sección Comercial R1 del object adapter, después de los métodos existentes:

```typescript
async syncManychatData(args) {
  return invoke<{ ok: boolean; leadsUpserted: number; conversationsUpserted: number; lastSyncAt: string; error?: string }>(
    'comercial_sync_manychat',
    { args: { since: args.since, workerBase: args.workerBase, dashboardKey: args.dashboardKey } }
  );
},

async listLeads(filter?: { status?: string; range?: PeriodRange }): Promise<Lead[]> {
  const f = filter ?? {};
  const result = await invoke<unknown[]>('comercial_list_leads', {
    filter: {
      status: f.status,
      rangeStart: f.range?.start,
      rangeEnd: f.range?.end,
    },
  });
  return result as Lead[];
},

async listConversations(filter?: { outcome?: string; range?: PeriodRange; leadId?: number }): Promise<ConversationMeta[]> {
  const f = filter ?? {};
  const result = await invoke<unknown[]>('comercial_list_conversations', {
    filter: {
      outcome: f.outcome,
      rangeStart: f.range?.start,
      rangeEnd: f.range?.end,
      leadId: f.leadId,
    },
  });
  return result as ConversationMeta[];
},

async listCustomers(filter?: { lastOrderBefore?: string; minLtvGtq?: number }): Promise<Customer[]> {
  const f = filter ?? {};
  const result = await invoke<unknown[]>('comercial_list_customers', {
    filter: { lastOrderBefore: f.lastOrderBefore, minLtvGtq: f.minLtvGtq },
  });
  return result as Customer[];
},

async getMetaSync(source: string): Promise<MetaSyncStatus> {
  const result = await invoke<unknown>('comercial_get_meta_sync', { source });
  if (!result) return { source, lastSyncAt: null, lastStatus: null, lastError: null };
  return result as MetaSyncStatus;
},

async getConversationMessages(args): Promise<ConversationMessage[]> {
  return invoke<ConversationMessage[]>('comercial_get_conversation_messages', {
    args: {
      convId: args.convId,
      workerBase: args.workerBase,
      dashboardKey: args.dashboardKey,
    },
  });
},
```

**Important:** comands con args struct (sync_manychat, get_conversation_messages) wrapean en `{ args: {...} }`. Los con primitive/struct flat (list_leads, list_conversations, list_customers, get_meta_sync) usan el filter / source directo (no wrap). Esto matchea el patrón de R1 + el fix de Task 9 R1 (commit `1708b12`).

- [ ] **Step 2: Agregar 6 stubs a browser.ts**

En el object adapter de browser.ts, después de Comercial R1 stubs:

```typescript
async syncManychatData() {
  throw new NotAvailableInBrowser('syncManychatData');
},
async listLeads() { return []; },
async listConversations() { return []; },
async listCustomers() { return []; },
async getMetaSync(source: string) {
  return { source, lastSyncAt: null, lastStatus: null, lastError: null };
},
async getConversationMessages() {
  throw new NotAvailableInBrowser('getConversationMessages');
},
```

- [ ] **Step 3: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts
git commit -m "feat(comercial): adapter R2 impls — Tauri invoke + browser stubs"
```

---

### Task 10: `manychatSync.ts` — sync orchestrator

**Files:**
- Create: `overhaul/src/lib/data/manychatSync.ts`

- [ ] **Step 1: Crear el archivo**

```typescript
// overhaul/src/lib/data/manychatSync.ts
import { adapter } from '$lib/adapter';
import type { MetaSyncStatus } from './comercial';

const SOURCE = 'manychat';
const WORKER_BASE = 'https://ventus-backoffice.ventusgt.workers.dev';

// IMPORTANT: hardcoded for R2-combo. R6 polish: load from a config file.
// This is the same DASHBOARD_KEY that the worker validates.
const DASHBOARD_KEY = 'OLf8SI13Qfc1h_Enw--tTBbG8yQQT_kd';

export interface SyncResult {
  ok: boolean;
  leadsUpserted: number;
  conversationsUpserted: number;
  lastSyncAt: string;
  error?: string;
}

/**
 * Hace UN sync inmediato: lee el last_sync_at de meta_sync, llama al worker desde ese punto,
 * upsertea leads + conversations, actualiza meta_sync.
 */
export async function runSync(): Promise<SyncResult> {
  let since: string | null = null;
  try {
    const meta = await adapter.getMetaSync(SOURCE);
    since = meta.lastSyncAt;
  } catch (e) {
    console.warn('[manychat-sync] failed to read meta_sync, doing full backfill', e);
  }

  try {
    const result = await adapter.syncManychatData({
      since,
      workerBase: WORKER_BASE,
      dashboardKey: DASHBOARD_KEY,
    });
    return result;
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      leadsUpserted: 0,
      conversationsUpserted: 0,
      lastSyncAt: since ?? '',
      error: err,
    };
  }
}

/**
 * Inicia el loop de sync c/1h. Retorna función para detener el loop.
 * El sync corre INMEDIATAMENTE en mount, luego cada hora.
 */
export function startSyncLoop(onResult?: (result: SyncResult) => void): () => void {
  async function runOnce() {
    const r = await runSync();
    if (onResult) onResult(r);
    if (!r.ok) console.warn('[manychat-sync] failed:', r.error);
  }
  void runOnce();
  const interval = setInterval(runOnce, 60 * 60 * 1000);
  return () => clearInterval(interval);
}

export const SYNC_CONSTANTS = { WORKER_BASE, DASHBOARD_KEY, SOURCE };
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|manychat" | head -10
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/data/manychatSync.ts
git commit -m "feat(comercial): manychatSync.ts — runSync + startSyncLoop (1h interval)"
```

---

### Task 11: PulsoBar — wire trends reales (current vs prev range)

**Files:**
- Modify: `overhaul/src/lib/components/comercial/PulsoBar.svelte`

- [ ] **Step 1: Reemplazar el `loadKPIs` para incluir prev range queries**

Localizar la función `loadKPIs(p: Period)`. Actualizar imports si falta `resolvePreviousRange`:

```typescript
import { computePulsoKPIs, resolvePeriod, resolvePreviousRange } from '$lib/data/kpis';
```

Reemplazar el cuerpo de loadKPIs con:

```typescript
async function loadKPIs(p: Period) {
  const range = resolvePeriod(p);
  const prevRange = resolvePreviousRange(range);
  try {
    const [sales, leads, adSpend, prevSales, prevLeads, prevAdSpend] = await Promise.all([
      adapter.listSalesInRange?.(range) ?? Promise.resolve([]),
      adapter.listLeadsInRange?.(range) ?? Promise.resolve([]),
      adapter.listAdSpendInRange?.(range) ?? Promise.resolve([]),
      adapter.listSalesInRange?.(prevRange) ?? Promise.resolve([]),
      adapter.listLeadsInRange?.(prevRange) ?? Promise.resolve([]),
      adapter.listAdSpendInRange?.(prevRange) ?? Promise.resolve([]),
    ]);
    kpis = computePulsoKPIs(sales, leads, adSpend, range, prevSales, prevLeads, prevAdSpend);
  } catch (e) {
    console.warn('[pulso] load failed', e);
    kpis = null;
  }
}
```

- [ ] **Step 2: Renderizar trend pills en TODAS las KPIs (no solo revenue)**

Agregar trend pills a Órdenes, Leads, Conv. (Ad spend y ROAS no muestran trend hasta R5 — ad data está vacío.)

Localizar el bloque de Órdenes (donde se muestra `{kpis.orders}`):

```svelte
<div class="flex items-baseline gap-2">
  <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Órdenes</span>
  <span class="text-mono font-semibold tabular-nums">{kpis.orders}</span>
  {@const tOrd = fmtTrend(kpis.trends.orders)}
  <span class="text-[10.5px]" style="color: var(--color-{tOrd.cls === 'up' ? 'success' : tOrd.cls === 'down' ? 'danger' : 'text-tertiary'});">{tOrd.sign}</span>
</div>
```

Mismo patrón para Leads y Conv:

```svelte
<!-- Leads -->
<div class="flex items-baseline gap-2">
  <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Leads</span>
  <span class="text-mono font-semibold tabular-nums">{kpis.leads}</span>
  {@const tLead = fmtTrend(kpis.trends.leads)}
  <span class="text-[10.5px]" style="color: var(--color-{tLead.cls === 'up' ? 'success' : tLead.cls === 'down' ? 'danger' : 'text-tertiary'});">{tLead.sign}</span>
</div>

<!-- Conv -->
<div class="flex items-baseline gap-2">
  <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Conv</span>
  <span class="text-mono font-semibold tabular-nums">{fmtPct(kpis.conversionRate)}</span>
  {@const tConv = fmtTrend(kpis.trends.conversionRate * 100)}
  <span class="text-[10.5px]" style="color: var(--color-{tConv.cls === 'up' ? 'success' : tConv.cls === 'down' ? 'danger' : 'text-tertiary'});">{tConv.sign}</span>
</div>
```

**Important:** Cambio del trend de Revenue del R1 — usar `style=` inline para color (en R1 estaba `text-[var(--color-{...})]` que Tailwind v4 JIT no resuelve). Hacer mismo cambio para Revenue para consistencia:

Localizar el bloque de Revenue actual y cambiar la línea del trend de:
```svelte
<span class="text-[10.5px] text-[var(--color-{tRev.cls === 'up' ? 'success' : tRev.cls === 'down' ? 'danger' : 'text-tertiary'})]">{tRev.sign}</span>
```

a:
```svelte
<span class="text-[10.5px]" style="color: var(--color-{tRev.cls === 'up' ? 'success' : tRev.cls === 'down' ? 'danger' : 'text-tertiary'});">{tRev.sign}</span>
```

(Los `@const tOrd` / `tLead` que estaban en R1 sin uso ahora SÍ se usan.)

- [ ] **Step 3: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/PulsoBar.svelte
git commit -m "feat(comercial): PulsoBar — trends reales con prev range + trend pills en órdenes/leads/conv"
```

---

### Task 12: eventDetector — `detectLeadsUnanswered12h`

**Files:**
- Modify: `overhaul/src/lib/data/eventDetector.ts`

- [ ] **Step 1: Agregar la función después de `detectOrdersPending24h`**

```typescript
/**
 * Detector "leads sin responder >12h".
 * Considera conversations donde outcome es null o 'pending' y last_activity (ended_at)
 * es más viejo que 12h. severity = warn (NO push WA — solo Inbox).
 */
export async function detectLeadsUnanswered12h(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 12 * 3600 * 1000).toISOString();

  let convs;
  try {
    convs = await adapter.listConversations({ outcome: 'pending' });
  } catch (e) {
    console.warn('[detector] listConversations failed', e);
    return null;
  }

  // Considerar también las que tienen outcome=null
  const stale = convs.filter((c: any) =>
    c.endedAt < cutoff && (c.outcome === null || c.outcome === 'pending')
  );

  if (stale.length === 0) return null;

  return {
    type: 'leads_unanswered_12h',
    severity: 'warn',
    title: `${stale.length} lead${stale.length === 1 ? '' : 's'} sin responder >12h`,
    sub: stale.slice(0, 3).map((c: any) => `${c.platform}:${c.senderId}`).join(' · ')
      + (stale.length > 3 ? ` · +${stale.length - 3}` : ''),
    itemsAffected: stale.map((c: any) => ({
      type: 'conversation',
      id: c.convId,
      hint: c.platform,
    })),
  };
}
```

- [ ] **Step 2: Llamarla en `runOnce()` del `startDetectorLoop`**

Localizar `runOnce()` adentro de `startDetectorLoop`. Después del existente `detectOrdersPending24h`:

```typescript
async function runOnce() {
  try {
    const ordersPending = await detectOrdersPending24h();
    if (ordersPending) await persistEvent(ordersPending);

    const leadsUnanswered = await detectLeadsUnanswered12h();
    if (leadsUnanswered) await persistEvent(leadsUnanswered);
  } catch (e) {
    console.warn('[detector] run failed', e);
  }
}
```

- [ ] **Step 3: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/data/eventDetector.ts
git commit -m "feat(comercial): detector — leads sin responder >12h (severity warn, sin push WA)"
```

---

### Task 13: ComercialShell — hoist period state + add sync loop

**Files:**
- Modify: `overhaul/src/lib/components/comercial/ComercialShell.svelte`

- [ ] **Step 1: Agregar imports + state para period y sync loop**

En el `<script lang="ts">`, agregar:

```typescript
import { onDestroy, onMount } from 'svelte';
import type { Period } from '$lib/data/comercial';
import { startSyncLoop, runSync, type SyncResult } from '$lib/data/manychatSync';

// Period state hoisted from PulsoBar
let activePeriod = $state<Period>('today');

// Sync loop
let stopSync: (() => void) | null = null;
let lastSyncResult = $state<SyncResult | null>(null);
```

(Los imports `onDestroy`/`onMount`/`startDetectorLoop` ya están del R1; ajustar si es necesario.)

- [ ] **Step 2: Iniciar el sync loop en `onMount` (después del detector loop existente)**

Modificar el `onMount` existente:

```typescript
onMount(() => {
  const saved = localStorage.getItem(STORAGE_KEY) as ComercialTab | null;
  if (saved && TABS.includes(saved)) {
    activeTab = saved;
  }
  stopDetector = startDetectorLoop();
  stopSync = startSyncLoop((r) => { lastSyncResult = r; });
});

onDestroy(() => {
  stopDetector?.();
  stopSync?.();
});
```

- [ ] **Step 3: Pasar `activePeriod` como prop a PulsoBar y FunnelTab**

Localizar el `<PulsoBar />` en el template. Cambiarlo:

```svelte
<PulsoBar bind:period={activePeriod} />
```

Localizar el bloque de FunnelTab. Cambiarlo:

```svelte
{:else if activeTab === 'funnel'}
  <FunnelTab period={activePeriod} {lastSyncResult} />
```

- [ ] **Step 4: Modificar PulsoBar.svelte para aceptar `period` como `bindable` prop**

En `PulsoBar.svelte`, cambiar la declaración de state:

```typescript
// Antes (R1):
let period = $state<Period>('today');

// Ahora (R2):
let { period = $bindable('today') }: { period?: Period } = $props();
```

(Si la sintaxis de bindable no compila, alternativa: agregar `onPeriodChange` callback prop.)

- [ ] **Step 5: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors sobre FunnelTab `period` / `lastSyncResult` props (Task 14 los resuelve).

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/ComercialShell.svelte overhaul/src/lib/components/comercial/PulsoBar.svelte
git commit -m "feat(comercial): ComercialShell — hoist period + arranca sync loop (1h)"
```

---

### Task 14: FunnelTab — full implementation (replace placeholder)

**Files:**
- Modify: `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte`

- [ ] **Step 1: Reemplazar el contenido del placeholder con la implementación completa**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Period, FunnelKPIs, Lead, ConversationMeta, Customer } from '$lib/data/comercial';
  import { resolvePeriod } from '$lib/data/kpis';
  import { computeFunnelKPIs } from '$lib/data/funnelKpis';
  import LeadProfileModal from '../modals/LeadProfileModal.svelte';
  import ConversationThreadModal from '../modals/ConversationThreadModal.svelte';
  import RetentionListModal from '../modals/RetentionListModal.svelte';
  import OrderDetailModal from '../modals/OrderDetailModal.svelte';
  import type { SyncResult } from '$lib/data/manychatSync';

  interface Props {
    period: Period;
    lastSyncResult?: SyncResult | null;
  }
  let { period, lastSyncResult = null }: Props = $props();

  let kpis = $state<FunnelKPIs | null>(null);
  let loading = $state(true);
  let leadsList = $state<Lead[]>([]);
  let convsList = $state<ConversationMeta[]>([]);
  let customersList = $state<Customer[]>([]);

  // Modal triggers
  let openInterest = $state(false);
  let openConsideration = $state(false);
  let openSale = $state<string | null>(null);   // ref string when opening order modal
  let openRetention = $state(false);

  $effect(() => {
    void period;
    void lastSyncResult;  // re-load when sync finishes
    loadAll();
  });

  async function loadAll() {
    loading = true;
    const range = resolvePeriod(period);
    try {
      const [leads, convs, sales, customers, adSpend] = await Promise.all([
        adapter.listLeads({ range }).catch(() => []),
        adapter.listConversations({ range }).catch(() => []),
        adapter.listSalesInRange?.(range) ?? Promise.resolve([]),
        adapter.listCustomers().catch(() => []),
        adapter.listAdSpendInRange?.(range) ?? Promise.resolve([]),
      ]);
      leadsList = leads;
      convsList = convs;
      customersList = customers;
      const salesAdapted = sales.map((s: any) => ({
        ref: s.ref, totalGtq: s.totalGtq, paidAt: s.paidAt, status: s.status,
      }));
      const adSpendAdapted = adSpend.map((a: any) => ({
        campaignId: a.campaignId, spendGtq: a.spendGtq, capturedAt: a.capturedAt,
      }));
      kpis = computeFunnelKPIs(range, leads, convs, salesAdapted, customers, adSpendAdapted);
    } catch (e) {
      console.warn('[funnel] load failed', e);
      kpis = null;
    } finally {
      loading = false;
    }
  }

  function fmtPct(v: number): string {
    return `${(v * 100).toFixed(0)}%`;
  }

  function convArrowColor(v: number): string {
    if (v >= 0.20) return 'var(--color-accent)';
    if (v >= 0.05) return 'var(--color-warning)';
    return 'var(--color-danger)';
  }
</script>

<div class="px-6 py-4">
  <h1 class="mb-4 text-[18px] font-semibold">Funnel · {period}</h1>

  {#if loading}
    <div class="text-[12px] text-[var(--color-text-tertiary)]">Cargando funnel…</div>
  {:else if !kpis}
    <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin data</div>
  {:else}
    <div class="grid grid-cols-5 gap-3">
      <!-- Stage 1: Awareness -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid #60a5fa;">
        <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Awareness</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums text-[var(--color-text-tertiary)]">—</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Impressions</span><span class="text-mono">{kpis.awareness.impressions}</span></div>
          <div class="flex justify-between"><span>Clicks</span><span class="text-mono">{kpis.awareness.clicks}</span></div>
          <div class="flex justify-between"><span>Spend</span><span class="text-mono">Q{kpis.awareness.spendGtq.toFixed(0)}</span></div>
        </div>
        <div class="mt-3 text-[10px] italic text-[var(--color-text-muted)]">Esperando sync Meta API (R5)</div>
      </div>

      <!-- Stage 2: Interest -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid #60a5fa;">
        <div class="text-display mb-1 text-[9.5px]" style="color: #60a5fa;">Interest</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: #60a5fa;">{kpis.interest.totalLeads}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>WhatsApp</span><span class="text-mono">{kpis.interest.byPlatform.wa}</span></div>
          <div class="flex justify-between"><span>Instagram</span><span class="text-mono">{kpis.interest.byPlatform.ig}</span></div>
          <div class="flex justify-between"><span>Messenger</span><span class="text-mono">{kpis.interest.byPlatform.messenger}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openInterest = true)}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 3: Consideration -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-warning);">
        <div class="text-display mb-1 text-[9.5px]" style="color: var(--color-warning);">Consideration</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: var(--color-warning);">{kpis.consideration.activeConversations}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Pendientes</span><span class="text-mono">{kpis.consideration.pending}</span></div>
          <div class="flex justify-between"><span>Objections</span><span class="text-mono">{kpis.consideration.objection}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openConsideration = true)}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 4: Sale -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-accent);">
        <div class="text-display mb-1 text-[9.5px]" style="color: var(--color-accent);">Sale</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: var(--color-accent);">{kpis.sale.ordersToday}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Esperando pago</span><span class="text-mono">{kpis.sale.awaitingPayment}</span></div>
          <div class="flex justify-between"><span>Esperando desp.</span><span class="text-mono">{kpis.sale.awaitingShipment}</span></div>
        </div>
        <button
          type="button"
          onclick={() => {
            // Pick most recent pending order, if any; placeholder for v1
            const ref = leadsList.length > 0 ? null : null;
            // R6 polish: show list. R2-combo: just navigate to Inbox or Order via existing flow.
            openSale = '__list__';
          }}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 5: Retention -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-text-tertiary);">
        <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Retention</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums">{kpis.retention.totalCustomers}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Repeat rate</span><span class="text-mono">{fmtPct(kpis.retention.repeatRate)}</span></div>
          <div class="flex justify-between"><span>LTV avg</span><span class="text-mono">Q{kpis.retention.ltvAvgGtq.toFixed(0)}</span></div>
          <div class="flex justify-between"><span>VIP inactivos</span><span class="text-mono">{kpis.retention.vipInactive60d}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openRetention = true)}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>
    </div>

    <!-- Conversion arrows row -->
    <div class="mt-3 grid grid-cols-5 gap-3">
      <div></div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.awarenessToInterest)};">→ {fmtPct(kpis.conversion.awarenessToInterest)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.interestToConsideration)};">→ {fmtPct(kpis.conversion.interestToConsideration)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.considerationToSale)};">→ {fmtPct(kpis.conversion.considerationToSale)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.saleToRetention)};">→ {fmtPct(kpis.conversion.saleToRetention)} conv</span>
      </div>
    </div>

    {#if lastSyncResult}
      <div class="mt-4 text-[10px] text-[var(--color-text-muted)]">
        {#if lastSyncResult.ok}
          Última sync ManyChat: {lastSyncResult.leadsUpserted} leads, {lastSyncResult.conversationsUpserted} convs · {lastSyncResult.lastSyncAt}
        {:else}
          ⚠ Sync falló: {lastSyncResult.error ?? 'desconocido'}
        {/if}
      </div>
    {/if}
  {/if}
</div>

{#if openInterest}
  <LeadProfileModal leads={leadsList} onClose={() => { openInterest = false; loadAll(); }} />
{/if}

{#if openConsideration}
  <ConversationThreadModal conversations={convsList} onClose={() => { openConsideration = false; loadAll(); }} />
{/if}

{#if openRetention}
  <RetentionListModal customers={customersList} onClose={() => (openRetention = false)} />
{/if}

{#if openSale === '__list__'}
  <!-- Placeholder: en R2-combo, click Sale lleva a Inbox tab. R6 polish puede agregar SalesListModal -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onclick={() => (openSale = null)}>
    <div class="rounded-lg bg-[var(--color-surface-1)] p-6 text-[12px] text-[var(--color-text-secondary)]">
      Para ver órdenes específicas, andá al tab Inbox.
      <button class="ml-2 text-[var(--color-accent)] underline" onclick={() => (openSale = null)}>OK</button>
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors sobre LeadProfileModal/ConversationThreadModal/RetentionListModal (Tasks 15/16/17 los resuelven).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte
git commit -m "feat(comercial): FunnelTab full impl — 5 etapas + conv arrows + drilldowns"
```

---

### Task 15: LeadProfileModal

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/LeadProfileModal.svelte`

- [ ] **Step 1: Crear el modal con BaseModal + dual-mode (list / detail)**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Lead, ConversationMeta } from '$lib/data/comercial';
  import { Users, MessageCircle } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import ConversationThreadModal from './ConversationThreadModal.svelte';

  interface Props {
    leads: Lead[];
    onClose: () => void;
  }
  let { leads, onClose }: Props = $props();

  let mode = $state<'list' | 'detail'>('list');
  let selectedLead = $state<Lead | null>(null);
  let leadConvs = $state<ConversationMeta[]>([]);
  let loadingConvs = $state(false);
  let showConvModal = $state(false);

  async function selectLead(lead: Lead) {
    selectedLead = lead;
    mode = 'detail';
    loadingConvs = true;
    try {
      leadConvs = await adapter.listConversations({ leadId: lead.leadId });
    } catch (e) {
      console.warn('[lead-profile] load convs failed', e);
      leadConvs = [];
    } finally {
      loadingConvs = false;
    }
  }

  function backToList() {
    mode = 'list';
    selectedLead = null;
    leadConvs = [];
  }

  function fmtPlatform(p: string) {
    return ({ wa: 'WhatsApp', ig: 'Instagram', messenger: 'Messenger', web: 'Web' } as Record<string, string>)[p] ?? p;
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if mode === 'list'}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.3);">
          <Users size={18} strokeWidth={1.8} style="color: #60a5fa;" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">Leads · {leads.length}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Click un lead para ver su perfil + conversations</div>
        </div>
      </div>
    {:else if selectedLead}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.3);">
          <Users size={18} strokeWidth={1.8} style="color: #60a5fa;" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">{selectedLead.name ?? selectedLead.handle ?? selectedLead.senderId}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">
            {fmtPlatform(selectedLead.platform)} · {selectedLead.status} · llegó {fmtDate(selectedLead.firstContactAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if mode === 'list'}
      <div class="px-6 py-4">
        {#if leads.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 leads en este período</div>
        {:else}
          <div class="space-y-2">
            {#each leads as lead (lead.leadId)}
              <button
                type="button"
                onclick={() => selectLead(lead)}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="flex items-baseline justify-between">
                  <span class="text-[12.5px] font-medium">{lead.name ?? lead.handle ?? lead.senderId}</span>
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtPlatform(lead.platform)}</span>
                </div>
                <div class="text-[10.5px] text-[var(--color-text-tertiary)]">
                  {lead.phone ?? '—'} · status: {lead.status}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else if selectedLead}
      <div class="grid grid-cols-[1fr_280px] gap-0">
        <div class="border-r border-[var(--color-border)] px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Conversations · {leadConvs.length}</div>
          {#if loadingConvs}
            <div class="text-[11px] text-[var(--color-text-tertiary)]">Cargando…</div>
          {:else if leadConvs.length === 0}
            <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin conversations</div>
          {:else}
            {#each leadConvs as conv (conv.convId)}
              <button
                type="button"
                onclick={() => (showConvModal = true)}
                class="mb-2 w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="text-mono text-[11px]">{conv.convId}</div>
                <div class="text-[10px] text-[var(--color-text-tertiary)]">
                  {fmtDate(conv.startedAt)} → {fmtDate(conv.endedAt)} · {conv.outcome ?? 'open'} · {conv.messagesTotal} msgs
                </div>
              </button>
            {/each}
          {/if}
        </div>
        <div class="px-4 py-4 bg-[var(--color-surface-0)]">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Lead</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Nombre</span><span>{selectedLead.name ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Handle</span><span>{selectedLead.handle ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{selectedLead.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Plataforma</span><span>{fmtPlatform(selectedLead.platform)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Status</span><span>{selectedLead.status}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Source camp.</span><span class="text-mono">{selectedLead.sourceCampaignId ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Sender ID</span><span class="text-mono text-[10px]">{selectedLead.senderId}</span></div>
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if mode === 'detail'}
      <button
        type="button"
        onclick={backToList}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
      >← Volver a lista</button>
    {/if}
    <div class="ml-auto">
      <button
        type="button"
        onclick={onClose}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
      >Cerrar</button>
    </div>
  {/snippet}
</BaseModal>

{#if showConvModal && selectedLead}
  <ConversationThreadModal conversations={leadConvs} onClose={() => (showConvModal = false)} />
{/if}
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors solo sobre ConversationThreadModal (Task 16).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/LeadProfileModal.svelte
git commit -m "feat(comercial): LeadProfileModal — list + detail modes con conversations"
```

---

### Task 16: ConversationThreadModal (with lazy fetch)

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/ConversationThreadModal.svelte`

- [ ] **Step 1: Crear el modal**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ConversationMeta, ConversationMessage } from '$lib/data/comercial';
  import { MessageCircle, Loader2, ExternalLink } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import { SYNC_CONSTANTS } from '$lib/data/manychatSync';

  interface Props {
    conversations: ConversationMeta[];
    onClose: () => void;
  }
  let { conversations, onClose }: Props = $props();

  let mode = $state<'list' | 'detail'>('list');
  let selectedConv = $state<ConversationMeta | null>(null);
  let messages = $state<ConversationMessage[]>([]);
  let loadingMsgs = $state(false);
  let messagesError = $state<string | null>(null);

  async function selectConv(conv: ConversationMeta) {
    selectedConv = conv;
    mode = 'detail';
    loadingMsgs = true;
    messagesError = null;
    try {
      messages = await adapter.getConversationMessages({
        convId: conv.convId,
        workerBase: SYNC_CONSTANTS.WORKER_BASE,
        dashboardKey: SYNC_CONSTANTS.DASHBOARD_KEY,
      });
    } catch (e) {
      messagesError = e instanceof Error ? e.message : String(e);
      messages = [];
    } finally {
      loadingMsgs = false;
    }
  }

  function backToList() {
    mode = 'list';
    selectedConv = null;
    messages = [];
    messagesError = null;
  }

  function handleResponderWA() {
    if (!selectedConv) return;
    // Phone may not be in conv directly — best-effort: use senderId for non-WA platforms
    const phone = selectedConv.platform === 'wa' ? selectedConv.senderId.replace(/\D/g, '') : null;
    if (!phone) {
      alert('Sin teléfono — esta conversation es de IG/Messenger. Respondé desde la app.');
      return;
    }
    window.open(`https://wa.me/${phone}`, '_blank');
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }

  function fmtPlatform(p: string) {
    return ({ wa: 'WA', ig: 'IG', messenger: 'Messenger', web: 'Web' } as Record<string, string>)[p] ?? p;
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if mode === 'list'}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3);">
          <MessageCircle size={18} strokeWidth={1.8} style="color: var(--color-warning);" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">Conversations · {conversations.length}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Click una conversation para ver el thread</div>
        </div>
      </div>
    {:else if selectedConv}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3);">
          <MessageCircle size={18} strokeWidth={1.8} style="color: var(--color-warning);" />
        </div>
        <div>
          <div class="flex items-center gap-2 text-[16px] font-semibold">
            <span class="text-mono text-[14px]">{selectedConv.convId}</span>
            <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(107,110,117,0.2); color: var(--color-text-secondary);">
              ● {(selectedConv.outcome ?? 'OPEN').toUpperCase()}
            </span>
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            {fmtPlatform(selectedConv.platform)} · {selectedConv.messagesTotal} msgs · {fmtDate(selectedConv.startedAt)} → {fmtDate(selectedConv.endedAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if mode === 'list'}
      <div class="px-6 py-4">
        {#if conversations.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin conversations en este período</div>
        {:else}
          <div class="space-y-2">
            {#each conversations as conv (conv.convId)}
              <button
                type="button"
                onclick={() => selectConv(conv)}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="flex items-baseline justify-between">
                  <span class="text-mono text-[12px]">{conv.convId}</span>
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtPlatform(conv.platform)}</span>
                </div>
                <div class="text-[10.5px] text-[var(--color-text-tertiary)]">
                  {conv.outcome ?? 'open'} · {conv.messagesTotal} msgs · {fmtDate(conv.endedAt)}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else if selectedConv}
      <div class="px-6 py-4">
        {#if loadingMsgs}
          <div class="flex items-center gap-2 text-[11.5px] text-[var(--color-text-tertiary)]">
            <Loader2 size={14} class="animate-spin" /> Cargando mensajes…
          </div>
        {:else if messagesError}
          <div class="text-[11.5px] text-[var(--color-danger)]">⚠ {messagesError}</div>
        {:else if messages.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> mensajes >90d fueron purgados</div>
        {:else}
          <div class="space-y-2 max-h-[450px] overflow-y-auto">
            {#each messages as msg}
              <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2.5">
                <div class="text-display mb-1 text-[9.5px]" style="color: {msg.role === 'user' ? 'var(--color-warning)' : msg.role === 'assistant' ? 'var(--color-accent)' : 'var(--color-text-tertiary)'};">
                  {msg.role.toUpperCase()}
                </div>
                <div class="text-[11.5px] whitespace-pre-wrap text-[var(--color-text-primary)]">{msg.text}</div>
                <div class="text-mono mt-1 text-[9.5px] text-[var(--color-text-muted)]">{fmtDate(msg.timestamp)}</div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center justify-between gap-2">
      {#if mode === 'detail'}
        <button
          type="button"
          onclick={backToList}
          class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
        >← Volver</button>
        <button
          type="button"
          onclick={handleResponderWA}
          class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black"
        >
          <ExternalLink size={12} strokeWidth={2.2} />
          Responder en WA
        </button>
      {/if}
      <button
        type="button"
        onclick={onClose}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] ml-auto"
      >Cerrar</button>
    </div>
  {/snippet}
</BaseModal>
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors (LeadProfileModal ya existe de Task 15).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/ConversationThreadModal.svelte
git commit -m "feat(comercial): ConversationThreadModal — list + detail con lazy fetch de mensajes"
```

---

### Task 17: RetentionListModal

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte`

- [ ] **Step 1: Crear el modal con lista sortable**

```svelte
<script lang="ts">
  import type { Customer } from '$lib/data/comercial';
  import { Users } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    customers: Customer[];
    onClose: () => void;
  }
  let { customers, onClose }: Props = $props();

  type SortKey = 'ltv' | 'lastOrder' | 'totalOrders' | 'firstOrder';
  let sortBy = $state<SortKey>('ltv');

  let sorted = $derived.by(() => {
    const arr = [...customers];
    switch (sortBy) {
      case 'ltv':
        return arr.sort((a, b) => b.totalRevenueGtq - a.totalRevenueGtq);
      case 'lastOrder':
        return arr.sort((a, b) => (b.lastOrderAt ?? '').localeCompare(a.lastOrderAt ?? ''));
      case 'totalOrders':
        return arr.sort((a, b) => b.totalOrders - a.totalOrders);
      case 'firstOrder':
        return arr.sort((a, b) => (a.firstOrderAt ?? '').localeCompare(b.firstOrderAt ?? ''));
    }
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(180,181,184,0.12); border: 1px solid rgba(180,181,184,0.3);">
        <Users size={18} strokeWidth={1.8} style="color: var(--color-text-tertiary);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Customers · {customers.length}</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Vista simple — profile completo en R4</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    <div class="px-6 py-4">
      <div class="mb-3 flex gap-1.5">
        {#each [['ltv','LTV'],['lastOrder','Última'],['totalOrders','Órdenes'],['firstOrder','Primera']] as [key, lbl]}
          {@const active = sortBy === key}
          <button
            type="button"
            onclick={() => (sortBy = key as SortKey)}
            class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
            style="
              background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
              border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
              color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
            "
          >Sort: {lbl}</button>
        {/each}
      </div>

      <table class="w-full text-[11.5px]">
        <thead>
          <tr class="text-display border-b border-[var(--color-border)] text-[9.5px] text-[var(--color-text-tertiary)]">
            <th class="px-2 py-1 text-left">Cliente</th>
            <th class="px-2 py-1 text-right">Órdenes</th>
            <th class="px-2 py-1 text-right">LTV</th>
            <th class="px-2 py-1 text-right">Primera</th>
            <th class="px-2 py-1 text-right">Última</th>
          </tr>
        </thead>
        <tbody>
          {#each sorted as c (c.customerId)}
            <tr class="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-1)]">
              <td class="px-2 py-1.5">
                <div class="text-[12px]">{c.name}</div>
                <div class="text-[10px] text-[var(--color-text-muted)]">{c.phone ?? c.email ?? '—'}</div>
              </td>
              <td class="text-mono px-2 py-1.5 text-right">{c.totalOrders}</td>
              <td class="text-mono px-2 py-1.5 text-right" style="color: var(--color-accent);">Q{c.totalRevenueGtq.toFixed(0)}</td>
              <td class="text-mono px-2 py-1.5 text-right text-[var(--color-text-tertiary)]">{fmtDate(c.firstOrderAt)}</td>
              <td class="text-mono px-2 py-1.5 text-right text-[var(--color-text-tertiary)]">{fmtDate(c.lastOrderAt)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      {#if customers.length === 0}
        <div class="mt-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 customers — todavía no hay compradores recurrentes</div>
      {/if}
    </div>
  {/snippet}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
    >Cerrar</button>
  {/snippet}
</BaseModal>
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte
git commit -m "feat(comercial): RetentionListModal — tabla sortable de customers (sin profile pleno)"
```

---

### Task 18: SettingsTab — botón "Sincronizar ahora"

**Files:**
- Modify: `overhaul/src/lib/components/comercial/tabs/SettingsTab.svelte`

- [ ] **Step 1: Reemplazar el placeholder con el botón + status display**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import { runSync, type SyncResult } from '$lib/data/manychatSync';
  import type { MetaSyncStatus } from '$lib/data/comercial';
  import { RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-svelte';

  let metaSync = $state<MetaSyncStatus | null>(null);
  let syncing = $state(false);
  let lastResult = $state<SyncResult | null>(null);

  async function loadMeta() {
    try {
      metaSync = await adapter.getMetaSync('manychat');
    } catch (e) {
      console.warn('[settings] meta load failed', e);
    }
  }

  async function handleSync() {
    if (syncing) return;
    syncing = true;
    try {
      lastResult = await runSync();
      await loadMeta();
    } finally {
      syncing = false;
    }
  }

  $effect(() => {
    void loadMeta();
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return 'nunca';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<div class="px-6 py-4">
  <h1 class="mb-4 text-[18px] font-semibold">Settings</h1>

  <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4">
    <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">ManyChat sync</div>

    <div class="mb-3 space-y-1 text-[11.5px]">
      <div class="flex justify-between">
        <span class="text-[var(--color-text-tertiary)]">Última sync</span>
        <span class="text-mono">{fmtDate(metaSync?.lastSyncAt ?? null)}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-[var(--color-text-tertiary)]">Status</span>
        <span class="text-mono">
          {#if metaSync?.lastStatus === 'ok'}
            <span style="color: var(--color-accent);">● OK</span>
          {:else if metaSync?.lastStatus === 'error'}
            <span style="color: var(--color-danger);">● ERROR</span>
          {:else}
            <span style="color: var(--color-text-muted);">—</span>
          {/if}
        </span>
      </div>
      {#if metaSync?.lastError}
        <div class="text-[10.5px] text-[var(--color-danger)]">⚠ {metaSync.lastError}</div>
      {/if}
    </div>

    <button
      type="button"
      onclick={handleSync}
      disabled={syncing}
      class="flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
    >
      {#if syncing}
        <RefreshCw size={12} strokeWidth={2} class="animate-spin" /> Sincronizando…
      {:else}
        <RefreshCw size={12} strokeWidth={2} /> Sincronizar ahora
      {/if}
    </button>

    {#if lastResult}
      <div class="mt-3 text-[10.5px]">
        {#if lastResult.ok}
          <span style="color: var(--color-accent);">✓ {lastResult.leadsUpserted} leads · {lastResult.conversationsUpserted} conversations actualizadas</span>
        {:else}
          <span style="color: var(--color-danger);">⚠ Falló: {lastResult.error}</span>
        {/if}
      </div>
    {/if}
  </div>

  <div class="mt-4 text-[10.5px] text-[var(--color-text-muted)]">
    Más settings (umbrales, notifications, integrations) en R6.
  </div>
</div>
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/tabs/SettingsTab.svelte
git commit -m "feat(comercial): SettingsTab — botón Sincronizar ahora + status display"
```

---

### Task 19: Build MSI v0.1.29 + tag

**Files:**
- Modify: `overhaul/src-tauri/Cargo.toml` (version)
- Modify: `overhaul/src-tauri/tauri.conf.json` (version)

- [ ] **Step 1: Bump version a 0.1.29 en ambos archivos**

Editar manualmente con el Edit tool:
- `overhaul/src-tauri/Cargo.toml` — `version = "0.1.28"` → `version = "0.1.29"`
- `overhaul/src-tauri/tauri.conf.json` — `"version": "0.1.28"` → `"version": "0.1.29"`

Verificar:
```bash
grep -E '^version|"version"' /c/Users/Diego/el-club/overhaul/src-tauri/Cargo.toml /c/Users/Diego/el-club/overhaul/src-tauri/tauri.conf.json
```

Should show 0.1.29 in both.

- [ ] **Step 2: Build MSI** (5-10 min, set timeout 600000ms)

```bash
cd /c/Users/Diego/el-club/overhaul
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build 2>&1 | tail -30
```

Expected: `Finished 1 bundle at: .../El Club ERP_0.1.29_x64_en-US.msi`.

- [ ] **Step 3: Verify MSI exists**

```bash
ls -la /c/Users/Diego/el-club/overhaul/src-tauri/target/release/bundle/msi/ | head
```

- [ ] **Step 4: Commit + tag**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json
# include Cargo.lock if updated by build
git status -s | grep Cargo.lock && git add overhaul/src-tauri/Cargo.lock
git commit -m "chore(release): v0.1.29 — Comercial R2-combo (Funnel + Pulso + ManyChat sync)"
git tag v0.1.29
git log --oneline -1 && git tag --list | tail -3
```

- [ ] **Step 5: Update LOG.md de Strategy con cierre de R2-combo**

Editar `/c/Users/Diego/elclub-catalogo-priv/docs/LOG.md`. Agregar al top (después del entry de R1):

```markdown
## 2026-04-26 — R2-combo SHIPPED: Funnel + Pulso + ManyChat sync (v0.1.29)

**Outcome:** Funnel tab funcional con 4 etapas reales (Awareness queda en zeros hasta R5), Pulso bar con trends reales current vs prev range, ManyChat sync c/1h pull-based, 1 detector nuevo "leads sin responder >12h".

**Tasks shipped (19 totales — combinó R2 + R3 originales):**
- Schema migration meta_sync, types core
- funnelKpis pure functions + resolvePreviousRange helper
- Worker endpoints sync-data + lazy fetch messages
- 5 bridge handlers Python + 6 Rust commands + adapter contract + impls
- manychatSync orchestrator (1h loop)
- PulsoBar wiring trends + new trend pills (órdenes, leads, conv)
- detector leads_unanswered_12h (severity warn)
- ComercialShell hoist period state + sync loop
- FunnelTab full impl
- 3 modals nuevos: LeadProfileModal, ConversationThreadModal (lazy), RetentionListModal
- SettingsTab botón Sincronizar ahora

**Métricas:**
- Files: ~15 modified/created
- Commits: ~20 in branch comercial-design (incluye R1 + R2)
- Tag: v0.1.29
- Build: MSI exitoso

**Próximo paso (R4):** Customers + Atribución (VIP detection automática, CustomerProfileModal completo, atribución leads ↔ campaigns).
```

(NO commit en elclub-catalogo-priv automático — Diego pushea manual.)

- [ ] **Step 6: Reportar al controller**

Reportar tag `v0.1.29` creado, MSI listo, LOG actualizado pendiente de push manual.

---

## Self-Review

**1. Spec coverage check:**

- ✅ Sec 2 Scope incluido — Tasks 1-19 cubren todo lo "incluido"
- ✅ Sec 3 Architecture — sync pull (Tasks 5+6+10+13), idempotency (Task 6 ON CONFLICT), lead extraction (Task 5 worker), attribution best-effort (Task 5 extractSourceCampaign helper)
- ✅ Sec 4 Schema — Task 1 (meta_sync); confirmación que conversations/leads/campaigns_snapshot ya están del R1 está en el spec, no se re-crean
- ✅ Sec 5 Components — todos los archivos NEW/MODIFIED tienen tasks correspondientes
- ✅ Sec 6 Trends — Task 11 wirea PulsoBar
- ✅ Sec 7 Funnel — Task 14 con layout, colores, conv arrows, awareness placeholder
- ✅ Sec 8 Detector — Task 12
- ✅ Sec 9 Worker endpoints — Task 5
- ✅ Sec 10 UX — period hoisting (Task 13), sync trigger (Task 18), loading/empty states (Tasks 14-17 incluyen)
- ✅ Sec 11 Errors — try/catch en sync (Task 6), lazy fetch errors (Task 16), funnel inconsistency (Task 14)
- ✅ Sec 13 Release — Task 19 con tag v0.1.29

**2. Placeholder scan:** No "TBD"/"TODO"/"implement later". Cada step tiene código completo.

**3. Type consistency:** 
- `DetectedEvent` se importa desde comercial.ts (Task 2 lo agregaría... actually no — DetectedEvent ya está en comercial.ts del R1 (lo agregamos en Task 16 R1). Confirmado.
- `MetaSyncStatus` definido Task 2, usado Tasks 8/9/18.
- `SyncResult` definido Task 10, usado Tasks 13/14/18.
- `Lead`/`ConversationMeta`/`Customer`/`FunnelKPIs`: definidos Task 2, usados Tasks 4/14/15/16/17.
- Adapter signatures Task 8 ↔ impls Task 9 ↔ Rust commands Task 7 ↔ bridge handlers Task 6: signatures matchean en cada layer.
- `WORKER_BASE` y `DASHBOARD_KEY` constants en manychatSync.ts (Task 10) y referenciados en Task 16 (ConversationThreadModal) — OK, exportados via `SYNC_CONSTANTS`.

**4. Scope check:** Una sola release. 19 tasks, similar a R1 (18). Tiempo estimado 3-4 días.

**5. Ambiguity check:**
- "Marcar resuelto" button — el spec dice read-only en R2-combo. ConversationThreadModal solo tiene "Responder en WA" y "Cerrar" / "Volver". No hay "Marcar resuelto". ✓ Resuelto.
- Sale drilldown — el FunnelTab muestra mensaje "andá al tab Inbox" en lugar de modal complejo. ✓ Decisión documentada.
- DASHBOARD_KEY hardcoded vs config — Task 10 lo hardcodea con comment "R6 polish: load from config". ✓ Resuelto.

---

## Execution Handoff

**Plan complete and saved to `el-club/overhaul/docs/superpowers/plans/2026-04-26-comercial-r2-funnel-pulso.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — Despacho un subagent por task, review entre tasks, fast iteration. Mismo flow que ejecutamos R1.

**2. Inline Execution** — Ejecutamos tasks en esta sesión usando executing-plans, batch con checkpoints.

**Próximo paso para Diego: elegir approach.**
