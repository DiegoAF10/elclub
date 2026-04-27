# Comercial R4: Customers + Atribución (lite) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Tab Customers full feature + CustomerProfileModal + ManualOrderModal + CreateCustomerModal. Add VIP detection (computed) + "VIP inactivos +60d" detector. Eliminate the provisional `RetentionListModal` from R2-combo.

**Architecture:** Customers list reads `customers` JOIN `sales` for computed totals (LTV, total orders, last order). VIP is derived (`LTV >= 1500`). Customer profile modal shows timeline = orders + conversations (joined by phone) chronologically. 4 actions wired: generate coupon (HTTP to worker), edit traits (textarea JSON), block (`ALTER TABLE customers ADD blocked`), create manual order (multi-item form via `sale_items` insert).

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte
- Backend: Rust (Tauri commands), Python bridge (HTTP + SQLite)
- Storage: SQLite local
- Worker: Reuses existing coupon endpoint (R1 Task 17 patterns)
- Verification: `npm run check` + `cargo check` + bridge smoke + manual smoke

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-26-comercial-r4-customers-atribucion-design.md` (commit `173df5f`)

**Branch:** `comercial-design`

**Versionado al completar:** ERP v0.1.29 → v0.1.30

---

## Tasks

### Task 0: Pre-flight — coupon endpoint contract check

**Files:** none (research only)

The spec defers to discovery: confirm the existing coupon endpoint shape (auth secret name, request body, response). Saves rework in Task 3 / Task 6.

- [ ] **Step 1: Find coupon endpoint and its auth secret**

```bash
grep -n "coupons/generate\|COUPON_API_KEY\|requireApiKey.*COUPON" /c/Users/Diego/ventus-system/backoffice/src/index.js | head -20
```

Identify:
1. Path of the endpoint (likely `/api/coupons/generate`)
2. HTTP method (likely POST)
3. Auth helper + secret name (likely `requireApiKey(request, env, 'COUPON_API_KEY')`)
4. Expected request body shape
5. Expected response shape (especially the field that contains the generated code — `code`, `coupon`, `result`)

- [ ] **Step 2: Read the endpoint impl to see exact contract**

```bash
grep -n -A 40 "coupons/generate" /c/Users/Diego/ventus-system/backoffice/src/index.js | head -80
```

Note the:
- Required fields in body (e.g., `customer_id`, `type`, `value`, `code` if Diego provides one or auto-generated server-side)
- Whether brand routing matters (vault vs el-club worker)
- TTL / expiration handling

- [ ] **Step 3: Verify the secret is set**

```bash
cd /c/Users/Diego/ventus-system/backoffice
npx wrangler secret list 2>&1 | grep COUPON_API_KEY
```

If not set, tell Diego to set it before Task 3 (the bridge handler depends on it).

- [ ] **Step 4: Document findings in this plan as a comment**

NO commit needed for this task. Just write the findings here in the plan as inline notes for Tasks 3 / 6. Specifically, replace the `<TODO_COUPON_*>` placeholders in Task 3 (`cmd_generate_coupon`) and Task 6 with actual values.

If the endpoint doesn't exist or has a fundamentally different shape than expected (e.g., it's via a different worker, or requires a brand parameter), STOP and report so the controller can decide whether to:
1. Build the endpoint as part of this plan
2. Defer the "Generate Cupón" action to R5 with a stub UI

---

### Task 1: Schema migration — `customers.blocked` column

**Files:**
- Modify: `el-club/erp/audit_db.py`

- [ ] **Step 1: Locate `init_audit_schema()`**

```bash
grep -n "def init_audit_schema\|ALTER TABLE customers\|ALTER TABLE sales" /c/Users/Diego/el-club/erp/audit_db.py | head -10
```

Find the section where R2-combo (Task 10 fix) added `ALTER TABLE sales ADD COLUMN shipped_at` with `try/except sqlite3.OperationalError`. Place the new ALTER near it.

- [ ] **Step 2: Add ALTER for customers.blocked**

After the existing `sales.shipped_at` ALTER, add:

```python
# Comercial R4: ensure blocked column exists on customers (additive migration).
# Default 0 = not blocked. NOT NULL with default keeps queries simple.
try:
    cur.execute("ALTER TABLE customers ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
except sqlite3.OperationalError:
    pass  # column already exists, safe to ignore
```

- [ ] **Step 3: Verify column exists**

```bash
cd /c/Users/Diego/el-club/erp
python -c "from db import get_conn; conn = get_conn(); cols = [r[1] for r in conn.execute('PRAGMA table_info(customers)').fetchall()]; print(cols); print('blocked' in cols)"
```

Expected output: list of columns INCLUDING `blocked`, then `True`.

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Diego/el-club
git add erp/audit_db.py
git commit -m "feat(comercial): schema R4 — customers.blocked column (additive)"
```

---

### Task 2: Types core — CustomerProfile, TimelineEntry, CreateOrderArgs, etc.

**Files:**
- Modify: `overhaul/src/lib/data/comercial.ts` (append new types at end)

- [ ] **Step 1: Append the 5 new types**

At the END of `overhaul/src/lib/data/comercial.ts`, after the R2-combo section:

```typescript
// ─── R4: Customers + Atribución ────────────────────────────────────

export interface CustomerProfile {
  // Base customer fields (from Customer type, but with R4 additions)
  customerId: number;
  name: string;
  phone: string | null;
  email: string | null;
  source: string | null;
  firstOrderAt: string;
  totalOrders: number;
  totalRevenueGtq: number;
  lastOrderAt: string | null;
  // R4 additions
  isVip: boolean;                        // derived: totalRevenueGtq >= 1500
  daysInactive: number | null;           // null if never ordered; computed from lastOrderAt
  blocked: boolean;
  traitsJson: Record<string, unknown>;
  attribution: {
    customerSource: string | null;
    leadCampaigns: string[];             // unique source_campaign_id from joined leads (by phone)
  };
  timeline: TimelineEntry[];
}

export type TimelineEntry =
  | { kind: 'order'; ref: string; totalGtq: number; status: string; occurredAt: string; itemsCount: number }
  | { kind: 'conversation'; convId: string; platform: string; outcome: string | null; messagesTotal: number; endedAt: string };

export interface CreateCustomerArgs {
  name: string;
  phone?: string | null;
  email?: string | null;
  source?: string | null;
}

export interface CreateOrderArgs {
  customerId: number;
  items: CreateOrderItem[];
  paymentMethod: 'recurrente' | 'transfer' | 'cod' | 'cash';
  fulfillmentStatus: 'pending_payment' | 'paid' | 'awaiting_shipment' | 'shipped' | 'delivered';
  shippingFee?: number;        // default 0
  discount?: number;           // default 0
  notes?: string;
}

export interface CreateOrderItem {
  familyId: string;
  jerseyId: string;
  team: string;
  size: string;
  variantLabel?: string | null;
  version?: string | null;
  personalizationJson?: string | null;
  unitPrice: number;
  unitCost?: number | null;
  itemType?: string | null;
}
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
git add overhaul/src/lib/data/comercial.ts
git commit -m "feat(comercial): types R4 — CustomerProfile, TimelineEntry, CreateOrderArgs"
```

---

### Task 3: Bridge Python — 7 handlers nuevos

**Files:**
- Modify: `el-club/erp/scripts/erp_rust_bridge.py`

Add 7 handlers near the existing comercial section:
1. `cmd_get_customer_profile` — full profile (customer + sales + conversations + computed fields)
2. `cmd_create_customer` — INSERT with name + optional phone/email/source
3. `cmd_update_customer_traits` — UPDATE customers SET tags_json
4. `cmd_set_customer_blocked` — UPDATE customers SET blocked
5. `cmd_update_customer_source` — UPDATE customers SET source
6. `cmd_create_manual_order` — INSERT sale + INSERT sale_items, returns ref
7. `cmd_generate_coupon` — HTTP POST to worker

- [ ] **Step 1: Add `cmd_get_customer_profile`**

```python
def cmd_get_customer_profile(args):
    """Devuelve CustomerProfile completo: customer + computed totals + timeline."""
    import json
    from db import get_conn

    customer_id = args.get("customerId")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}

    conn = get_conn()
    try:
        # Base customer
        c = conn.execute("""
            SELECT customer_id, name, phone, email, source, first_order_at, tags_json,
                   COALESCE(blocked, 0) AS blocked
            FROM customers WHERE customer_id = ?
        """, (customer_id,)).fetchone()
        if not c:
            return {"ok": True, "profile": None}

        # Computed totals from sales
        totals = conn.execute("""
            SELECT COUNT(sale_id), COALESCE(SUM(total), 0), MAX(occurred_at)
            FROM sales WHERE customer_id = ?
        """, (customer_id,)).fetchone()
        total_orders = totals[0]
        total_revenue = totals[1]
        last_order_at = totals[2]

        is_vip = total_revenue >= 1500
        days_inactive = None
        if last_order_at:
            from datetime import datetime
            try:
                last_dt = datetime.fromisoformat(last_order_at.replace('Z', '+00:00').replace(' ', 'T'))
                days_inactive = (datetime.utcnow() - last_dt.replace(tzinfo=None)).days
            except Exception:
                days_inactive = None

        # Attribution: lookup conversations matching customer's phone
        # leads.source_campaign_id is the source per lead; aggregate unique values
        lead_campaigns = []
        if c[2]:  # phone
            rows = conn.execute("""
                SELECT DISTINCT source_campaign_id FROM leads
                WHERE phone = ? AND source_campaign_id IS NOT NULL
            """, (c[2],)).fetchall()
            lead_campaigns = [r[0] for r in rows]

        # Timeline: merge orders + conversations by date DESC
        timeline = []
        sales_rows = conn.execute("""
            SELECT s.ref, s.total, s.fulfillment_status, s.occurred_at,
                   (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id = s.sale_id) AS items_count
            FROM sales s WHERE s.customer_id = ?
            ORDER BY s.occurred_at DESC
        """, (customer_id,)).fetchall()
        for r in sales_rows:
            timeline.append({
                "kind": "order",
                "ref": r[0], "totalGtq": r[1], "status": r[2] or "paid",
                "occurredAt": r[3], "itemsCount": r[4],
            })

        # Conversations: join by phone (best-effort)
        if c[2]:
            conv_rows = conn.execute("""
                SELECT c.conv_id, c.platform, c.outcome, c.messages_total, c.ended_at
                FROM conversations c
                JOIN leads l ON l.platform = c.platform AND l.sender_id = c.sender_id
                WHERE l.phone = ?
                ORDER BY c.ended_at DESC
            """, (c[2],)).fetchall()
            for r in conv_rows:
                timeline.append({
                    "kind": "conversation",
                    "convId": r[0], "platform": r[1], "outcome": r[2],
                    "messagesTotal": r[3], "endedAt": r[4],
                })

        # Re-sort merged timeline by date DESC (sales.occurred_at vs convs.ended_at)
        def get_ts(entry):
            return entry.get("occurredAt") or entry.get("endedAt") or ""
        timeline.sort(key=get_ts, reverse=True)

        try:
            traits = json.loads(c[6] or '{}')
        except Exception:
            traits = {}

        profile = {
            "customerId": c[0],
            "name": c[1] or "(sin nombre)",
            "phone": c[2],
            "email": c[3],
            "source": c[4],
            "firstOrderAt": c[5] or "",
            "totalOrders": total_orders,
            "totalRevenueGtq": total_revenue,
            "lastOrderAt": last_order_at,
            "isVip": is_vip,
            "daysInactive": days_inactive,
            "blocked": bool(c[7]),
            "traitsJson": traits,
            "attribution": {
                "customerSource": c[4],
                "leadCampaigns": lead_campaigns,
            },
            "timeline": timeline,
        }
        return {"ok": True, "profile": profile}
    finally:
        conn.close()
```

- [ ] **Step 2: Add `cmd_create_customer`**

```python
def cmd_create_customer(args):
    """Crea un customer manual (no asociado a sale automático)."""
    from db import get_conn

    name = args.get("name")
    if not name or not name.strip():
        return {"ok": False, "error": "name required"}

    phone = args.get("phone")
    email = args.get("email")
    source = args.get("source") or "manual"

    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO customers (name, phone, email, source, first_order_at, created_at)
            VALUES (?, ?, ?, ?, '', datetime('now'))
        """, (name.strip(), phone, email, source))
        conn.commit()
        return {"ok": True, "customerId": cur.lastrowid}
    finally:
        conn.close()
```

- [ ] **Step 3: Add `cmd_update_customer_traits`**

```python
def cmd_update_customer_traits(args):
    """Actualiza customers.tags_json con un objeto JSON."""
    import json
    from db import get_conn

    customer_id = args.get("customerId")
    traits = args.get("traitsJson")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}
    if traits is None:
        return {"ok": False, "error": "traitsJson required"}

    # Validate it's a valid JSON-serializable dict (already deserialized from input)
    if not isinstance(traits, dict):
        return {"ok": False, "error": "traitsJson must be an object"}

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE customers SET tags_json = ? WHERE customer_id = ?",
            (json.dumps(traits), customer_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
```

- [ ] **Step 4: Add `cmd_set_customer_blocked`**

```python
def cmd_set_customer_blocked(args):
    """Toggle blocked en customers."""
    from db import get_conn

    customer_id = args.get("customerId")
    blocked = args.get("blocked")
    if not customer_id or blocked is None:
        return {"ok": False, "error": "customerId/blocked required"}

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE customers SET blocked = ? WHERE customer_id = ?",
            (1 if blocked else 0, customer_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
```

- [ ] **Step 5: Add `cmd_update_customer_source`**

```python
def cmd_update_customer_source(args):
    """Actualiza customers.source manualmente."""
    from db import get_conn

    customer_id = args.get("customerId")
    source = args.get("source")
    if not customer_id:
        return {"ok": False, "error": "customerId required"}

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE customers SET source = ? WHERE customer_id = ?",
            (source, customer_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
```

- [ ] **Step 6: Add `cmd_create_manual_order`**

```python
def cmd_create_manual_order(args):
    """Crea una venta manual (off-platform). INSERT sale + INSERT sale_items.
    Genera ref CE-XXXX random con retry en caso de colisión.
    """
    import json
    import secrets
    import string
    import sqlite3 as sqlite3_mod
    from db import get_conn

    customer_id = args.get("customerId")
    items = args.get("items") or []
    payment_method = args.get("paymentMethod") or "transfer"
    fulfillment_status = args.get("fulfillmentStatus") or "paid"
    shipping_fee = args.get("shippingFee") or 0
    discount = args.get("discount") or 0
    notes = args.get("notes")

    if not customer_id:
        return {"ok": False, "error": "customerId required"}
    if not items:
        return {"ok": False, "error": "at least 1 item required"}

    # Validate each item
    for i, item in enumerate(items):
        if not item.get("familyId") or not item.get("jerseyId"):
            return {"ok": False, "error": f"item[{i}] missing familyId/jerseyId"}
        if not item.get("size"):
            return {"ok": False, "error": f"item[{i}] missing size"}
        unit_price = item.get("unitPrice")
        if unit_price is None or unit_price <= 0:
            return {"ok": False, "error": f"item[{i}] unitPrice must be > 0"}

    if payment_method not in ("recurrente", "transfer", "cod", "cash"):
        return {"ok": False, "error": "invalid paymentMethod"}
    if fulfillment_status not in ("pending_payment", "paid", "awaiting_shipment", "shipped", "delivered"):
        return {"ok": False, "error": "invalid fulfillmentStatus"}

    subtotal = sum(item["unitPrice"] for item in items)
    total = subtotal + shipping_fee - discount

    if total <= 0:
        return {"ok": False, "error": "total must be > 0"}

    # Validate customer exists
    conn = get_conn()
    try:
        c = conn.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if not c:
            return {"ok": False, "error": f"customer {customer_id} not found"}

        # Generate ref with retry on UNIQUE collision (extremely rare)
        ref = None
        for attempt in range(5):
            candidate = "CE-" + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            try:
                cur = conn.execute("""
                    INSERT INTO sales
                      (ref, occurred_at, modality, origin, customer_id, payment_method,
                       fulfillment_status, shipping_method, tracking_code, subtotal, shipping_fee,
                       discount, total, source_vault_ref, notes, created_at)
                    VALUES (?, datetime('now'), 'manual', 'manual', ?, ?, ?, NULL, NULL,
                            ?, ?, ?, ?, NULL, ?, datetime('now'))
                """, (candidate, customer_id, payment_method, fulfillment_status,
                      subtotal, shipping_fee, discount, total, notes))
                ref = candidate
                sale_id = cur.lastrowid
                break
            except sqlite3_mod.IntegrityError:
                continue

        if ref is None:
            return {"ok": False, "error": "ref collision after 5 retries"}

        # Insert items
        for item in items:
            conn.execute("""
                INSERT INTO sale_items
                  (sale_id, family_id, jersey_id, team, season, variant_label, version, size,
                   personalization_json, unit_price, unit_cost, notes, import_id, item_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """, (
                sale_id,
                item.get("familyId"),
                item.get("jerseyId"),
                item.get("team"),
                None,  # season — not in our R4 form, leave NULL
                item.get("variantLabel"),
                item.get("version"),
                item.get("size"),
                item.get("personalizationJson"),
                item.get("unitPrice"),
                item.get("unitCost"),
                item.get("itemType") or "manual",
            ))

        conn.commit()
        return {"ok": True, "ref": ref, "saleId": sale_id}
    finally:
        conn.close()
```

- [ ] **Step 7: Add `cmd_generate_coupon`** (uses Task 0 findings — adjust placeholders)

```python
def cmd_generate_coupon(args):
    """Genera cupón vía worker. Args: customerId, type ('percent'|'amount'), value, expiresInDays.
    R1 Task 17 wired DASHBOARD_KEY auth pattern; coupons may use COUPON_API_KEY (TBD by Task 0 pre-flight).
    """
    import json
    import urllib.request
    import urllib.error

    customer_id = args.get("customerId")
    coupon_type = args.get("type")
    value = args.get("value")
    expires_in_days = args.get("expiresInDays") or 30

    worker_base = args.get("workerBase") or "https://ventus-backoffice.ventusgt.workers.dev"
    api_key = args.get("apiKey")  # Set by adapter from Task 0 findings

    if not customer_id:
        return {"ok": False, "error": "customerId required"}
    if coupon_type not in ("percent", "amount"):
        return {"ok": False, "error": "type must be 'percent' or 'amount'"}
    if value is None or value <= 0:
        return {"ok": False, "error": "value must be > 0"}
    if not api_key:
        return {"ok": False, "error": "apiKey required"}

    url = f"{worker_base}/api/coupons/generate"
    body = json.dumps({
        "customer_id": customer_id,
        "type": coupon_type,
        "value": value,
        "expires_in_days": expires_in_days,
        "brand": "elclub",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ElClub-ERP/0.1.30",   # bypass Cloudflare 1010
        }, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Worker may return code under 'code', 'coupon_code', or similar — Task 0 confirms
        code = data.get("code") or data.get("coupon_code") or data.get("coupon")
        if not code:
            return {"ok": False, "error": f"worker returned unexpected shape: {data}"}
        return {"ok": True, "code": code}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"worker http {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"fetch failed: {e}"}
```

- [ ] **Step 8: Register all 7 commands in COMMANDS dict**

Append (do NOT replace existing):

```python
    "get_customer_profile": cmd_get_customer_profile,
    "create_customer": cmd_create_customer,
    "update_customer_traits": cmd_update_customer_traits,
    "set_customer_blocked": cmd_set_customer_blocked,
    "update_customer_source": cmd_update_customer_source,
    "create_manual_order": cmd_create_manual_order,
    "generate_coupon": cmd_generate_coupon,
```

- [ ] **Step 9: Smoke test 5 non-network handlers**

Pick a real customer_id (e.g., Raul Ibarguen — find with `SELECT customer_id FROM customers WHERE name LIKE 'Raul%'`):

```bash
cd /c/Users/Diego/el-club/erp

# Pick a real customer_id (likely 1, 2, or 3 — check first):
python -c "from db import get_conn; print([r for r in get_conn().execute('SELECT customer_id, name FROM customers ORDER BY customer_id LIMIT 5').fetchall()])"

# Use a real id (replace 1 below if needed):
echo '{"cmd":"get_customer_profile","customerId":1}' | python scripts/erp_rust_bridge.py | head -c 500
echo
echo '{"cmd":"create_customer","name":"TEST_CUSTOMER","phone":"+50212345678","email":"test@test.com","source":"manual"}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"update_customer_traits","customerId":1,"traitsJson":{"test":"r4"}}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"set_customer_blocked","customerId":1,"blocked":false}' | python scripts/erp_rust_bridge.py
echo '{"cmd":"update_customer_source","customerId":1,"source":"f&f"}' | python scripts/erp_rust_bridge.py
```

Expected:
- `get_customer_profile`: returns `{"ok": true, "profile": {...full profile...}}` with totals + timeline
- `create_customer`: returns `{"ok": true, "customerId": <new_id>}`. Cleanup the test row afterwards: `python -c "from db import get_conn; conn=get_conn(); conn.execute('DELETE FROM customers WHERE name=?', ('TEST_CUSTOMER',)); conn.commit()"`
- The 3 update handlers return `{"ok": true}`

- [ ] **Step 10: Smoke test create_manual_order**

```bash
# Pick a real family_id from catalog (we don't add a real test order — just validate input handling)
echo '{"cmd":"create_manual_order","customerId":1,"items":[],"paymentMethod":"transfer","fulfillmentStatus":"paid"}' | python scripts/erp_rust_bridge.py
```

Expected: `{"ok": false, "error": "at least 1 item required"}` (validation works; we don't insert a real test sale).

- [ ] **Step 11: Smoke test generate_coupon (if Task 0 confirmed endpoint)**

```bash
# Get the API key from .env. Use Task 0's findings for which secret name.
DKEY=$(grep '^COUPON_API_KEY=' /c/Users/Diego/ventus-system/.env 2>/dev/null | cut -d= -f2)
if [ -z "$DKEY" ]; then DKEY=$(grep '^DASHBOARD_KEY=' /c/Users/Diego/ventus-system/.env | cut -d= -f2); fi

echo "{\"cmd\":\"generate_coupon\",\"customerId\":1,\"type\":\"percent\",\"value\":10,\"apiKey\":\"$DKEY\"}" | python scripts/erp_rust_bridge.py
```

Expected: either `{"ok": true, "code": "..."}` (success — generates a real coupon) OR `{"ok": false, "error": "worker http 401: ..."}` (auth issue — Diego fixes secret).

If 401, log it as a known infra issue and proceed; the Tauri layer will surface the same error to the modal at runtime.

- [ ] **Step 12: Commit**

```bash
cd /c/Users/Diego/el-club
git add erp/scripts/erp_rust_bridge.py
git commit -m "feat(comercial): bridge R4 — 7 handlers (customer profile, CRUD, manual order, coupon)"
```

---

### Task 4: Rust Tauri commands — 7 wrappers

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add structs + commands in the existing Comercial section**

After the Comercial R2 section, add:

```rust
// ─── Comercial R4 ──────────────────────────────────────────────────

#[tauri::command]
async fn comercial_get_customer_profile(customer_id: i64) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_customer_profile", "customerId": customer_id });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("profile").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateCustomerArgs {
    pub name: String,
    pub phone: Option<String>,
    pub email: Option<String>,
    pub source: Option<String>,
}

#[tauri::command]
async fn comercial_create_customer(args: CreateCustomerArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "create_customer",
        "name": args.name,
        "phone": args.phone,
        "email": args.email,
        "source": args.source,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateTraitsArgs {
    pub customer_id: i64,
    pub traits_json: Value,
}

#[tauri::command]
async fn comercial_update_customer_traits(args: UpdateTraitsArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "update_customer_traits",
        "customerId": args.customer_id,
        "traitsJson": args.traits_json,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SetBlockedArgs {
    pub customer_id: i64,
    pub blocked: bool,
}

#[tauri::command]
async fn comercial_set_customer_blocked(args: SetBlockedArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "set_customer_blocked",
        "customerId": args.customer_id,
        "blocked": args.blocked,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateSourceArgs {
    pub customer_id: i64,
    pub source: Option<String>,
}

#[tauri::command]
async fn comercial_update_customer_source(args: UpdateSourceArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "update_customer_source",
        "customerId": args.customer_id,
        "source": args.source,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateManualOrderArgs {
    pub customer_id: i64,
    pub items: Vec<Value>,
    pub payment_method: String,
    pub fulfillment_status: String,
    pub shipping_fee: Option<f64>,
    pub discount: Option<f64>,
    pub notes: Option<String>,
}

#[tauri::command]
async fn comercial_create_manual_order(args: CreateManualOrderArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "create_manual_order",
        "customerId": args.customer_id,
        "items": args.items,
        "paymentMethod": args.payment_method,
        "fulfillmentStatus": args.fulfillment_status,
        "shippingFee": args.shipping_fee,
        "discount": args.discount,
        "notes": args.notes,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerateCouponArgs {
    pub customer_id: i64,
    #[serde(rename = "type")]
    pub type_: String,
    pub value: f64,
    pub expires_in_days: Option<i64>,
    pub api_key: String,
    pub worker_base: Option<String>,
}

#[tauri::command]
async fn comercial_generate_coupon(args: GenerateCouponArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "generate_coupon",
        "customerId": args.customer_id,
        "type": args.type_,
        "value": args.value,
        "expiresInDays": args.expires_in_days,
        "apiKey": args.api_key,
        "workerBase": args.worker_base,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}
```

- [ ] **Step 2: Register the 7 commands in `tauri::generate_handler!`**

Add to the macro (next to comercial R2 entries):

```rust
comercial_get_customer_profile,
comercial_create_customer,
comercial_update_customer_traits,
comercial_set_customer_blocked,
comercial_update_customer_source,
comercial_create_manual_order,
comercial_generate_coupon,
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
git commit -m "feat(comercial): Rust commands R4 — 7 wrappers (customer ops, manual order, coupon)"
```

---

### Task 5: Adapter contract — types.ts

**Files:**
- Modify: `overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Extend imports + add 7 method signatures**

In the existing import from `'../data/comercial'`, extend with R4 types:

```typescript
import type {
  ComercialEvent, EventStatus, OrderForModal, PeriodRange,
  Lead, ConversationMeta, ConversationMessage, Customer, MetaSyncStatus,
  CustomerProfile, CreateCustomerArgs, CreateOrderArgs
} from '../data/comercial';
```

In the `interface Adapter`, after the R2-combo section, add:

```typescript
	// ─── Comercial R4 ──────────────────────────────────────────
	getCustomerProfile(customerId: number): Promise<CustomerProfile | null>;
	createCustomer(args: CreateCustomerArgs): Promise<{ ok: boolean; customerId?: number; error?: string }>;
	updateCustomerTraits(customerId: number, traitsJson: Record<string, unknown>): Promise<void>;
	setCustomerBlocked(customerId: number, blocked: boolean): Promise<void>;
	updateCustomerSource(customerId: number, source: string | null): Promise<void>;
	createManualOrder(args: CreateOrderArgs): Promise<{ ok: boolean; ref?: string; saleId?: number; error?: string }>;
	generateCoupon(args: { customerId: number; type: 'percent' | 'amount'; value: number; expiresInDays?: number; apiKey: string; workerBase?: string }): Promise<{ ok: boolean; code?: string; error?: string }>;
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors about missing impls in `tauri.ts` and `browser.ts` (Task 6 fixes).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/adapter/types.ts
git commit -m "feat(comercial): adapter R4 contract — 7 method signatures"
```

---

### Task 6: Adapter Tauri impls + browser stubs

**Files:**
- Modify: `overhaul/src/lib/adapter/tauri.ts`
- Modify: `overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add imports + 7 impls to tauri.ts**

In the existing `import type { ... } from '../data/comercial'` block, extend:

```typescript
import type {
  ComercialEvent, EventStatus, OrderForModal, PeriodRange,
  Lead, ConversationMeta, ConversationMessage, Customer, MetaSyncStatus,
  CustomerProfile, CreateCustomerArgs, CreateOrderArgs
} from '../data/comercial';
```

In the adapter object, after the Comercial R2 section, add:

```typescript
async getCustomerProfile(customerId: number): Promise<CustomerProfile | null> {
  const result = await invoke<unknown>('comercial_get_customer_profile', { customerId });
  return (result as CustomerProfile | null) ?? null;
},

async createCustomer(args: CreateCustomerArgs) {
  return invoke<{ ok: boolean; customerId?: number; error?: string }>(
    'comercial_create_customer',
    { args: { name: args.name, phone: args.phone, email: args.email, source: args.source } }
  );
},

async updateCustomerTraits(customerId: number, traitsJson: Record<string, unknown>): Promise<void> {
  await invoke('comercial_update_customer_traits', {
    args: { customerId, traitsJson },
  });
},

async setCustomerBlocked(customerId: number, blocked: boolean): Promise<void> {
  await invoke('comercial_set_customer_blocked', {
    args: { customerId, blocked },
  });
},

async updateCustomerSource(customerId: number, source: string | null): Promise<void> {
  await invoke('comercial_update_customer_source', {
    args: { customerId, source },
  });
},

async createManualOrder(args: CreateOrderArgs) {
  return invoke<{ ok: boolean; ref?: string; saleId?: number; error?: string }>(
    'comercial_create_manual_order',
    {
      args: {
        customerId: args.customerId,
        items: args.items,
        paymentMethod: args.paymentMethod,
        fulfillmentStatus: args.fulfillmentStatus,
        shippingFee: args.shippingFee,
        discount: args.discount,
        notes: args.notes,
      },
    }
  );
},

async generateCoupon(args) {
  return invoke<{ ok: boolean; code?: string; error?: string }>(
    'comercial_generate_coupon',
    {
      args: {
        customerId: args.customerId,
        type: args.type,
        value: args.value,
        expiresInDays: args.expiresInDays,
        apiKey: args.apiKey,
        workerBase: args.workerBase,
      },
    }
  );
},
```

**IMPORTANT — args wrap pattern:**
- `getCustomerProfile` takes a primitive (`customerId: i64`) → flat invoke `{ customerId }` (no wrap)
- All other 6 take struct args → wrap in `{ args: {...} }` (matches R1 fix `1708b12` pattern)

- [ ] **Step 2: Add 7 stubs to browser.ts**

In the adapter object after Comercial R2 stubs:

```typescript
async getCustomerProfile() {
  return null;
},
async createCustomer() {
  throw new NotAvailableInBrowser('createCustomer');
},
async updateCustomerTraits() {
  throw new NotAvailableInBrowser('updateCustomerTraits');
},
async setCustomerBlocked() {
  throw new NotAvailableInBrowser('setCustomerBlocked');
},
async updateCustomerSource() {
  throw new NotAvailableInBrowser('updateCustomerSource');
},
async createManualOrder() {
  throw new NotAvailableInBrowser('createManualOrder');
},
async generateCoupon() {
  throw new NotAvailableInBrowser('generateCoupon');
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
git commit -m "feat(comercial): adapter R4 impls — Tauri + browser stubs"
```

---

### Task 7: Detector — `detectVipInactive60d`

**Files:**
- Modify: `overhaul/src/lib/data/eventDetector.ts`

- [ ] **Step 1: Add the detector function**

After `detectLeadsUnanswered12h`:

```typescript
/**
 * Detector "VIP inactivos +60d".
 * VIP = totalRevenueGtq >= 1500. Inactivo = lastOrderAt < (now - 60d).
 * severity = strat (no push WA — solo Inbox).
 */
export async function detectVipInactive60d(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 60 * 86400 * 1000).toISOString();

  let customers;
  try {
    customers = await adapter.listCustomers({ minLtvGtq: 1500 });
  } catch (e) {
    console.warn('[detector] listCustomers failed', e);
    return null;
  }

  const inactive = customers.filter((c: any) =>
    c.lastOrderAt && c.lastOrderAt < cutoff
  );

  if (inactive.length === 0) return null;

  return {
    type: 'vip_inactive_60d',
    severity: 'strat',
    title: `${inactive.length} VIP${inactive.length === 1 ? '' : 's'} inactivo${inactive.length === 1 ? '' : 's'} +60d`,
    sub: inactive.slice(0, 3).map((c: any) => `${c.name} (Q${c.totalRevenueGtq})`).join(' · ')
      + (inactive.length > 3 ? ` · +${inactive.length - 3}` : ''),
    itemsAffected: inactive.map((c: any) => ({
      type: 'customer',
      id: String(c.customerId),
      hint: `LTV Q${c.totalRevenueGtq}`,
    })),
  };
}
```

- [ ] **Step 2: Wire into runOnce**

Find `runOnce()`. After `detectLeadsUnanswered12h`:

```typescript
async function runOnce() {
  try {
    const ordersPending = await detectOrdersPending24h();
    if (ordersPending) await persistEvent(ordersPending);

    const leadsUnanswered = await detectLeadsUnanswered12h();
    if (leadsUnanswered) await persistEvent(leadsUnanswered);

    const vipInactive = await detectVipInactive60d();
    if (vipInactive) await persistEvent(vipInactive);
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
git commit -m "feat(comercial): detector — VIP inactivos +60d (severity strat, sin push WA)"
```

---

### Task 8: Cleanup — eliminar `RetentionListModal` + wiring del Funnel

**Files:**
- Delete: `overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte`
- Modify: `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte`
- Modify: `overhaul/src/lib/components/comercial/ComercialShell.svelte`

- [ ] **Step 1: Modify ComercialShell to support tab switch from FunnelTab**

In `overhaul/src/lib/components/comercial/ComercialShell.svelte`, find the `<FunnelTab ... />` element. Add a `onSwitchTab` prop:

```svelte
{:else if activeTab === 'funnel'}
  <FunnelTab
    period={activePeriod}
    {lastSyncResult}
    onSwitchTab={(t) => (activeTab = t)}
  />
```

- [ ] **Step 2: Modify FunnelTab to use the callback for Retention drilldown**

In `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte`:

1. Remove the import of `RetentionListModal`:
```typescript
// REMOVE: import RetentionListModal from '../modals/RetentionListModal.svelte';
```

2. Update `Props` interface:
```typescript
import type { ComercialTab } from '$lib/data/comercial';

interface Props {
  period: Period;
  lastSyncResult?: SyncResult | null;
  onSwitchTab?: (tab: ComercialTab) => void;
}
let { period, lastSyncResult = null, onSwitchTab }: Props = $props();
```

3. Remove the `openRetention` state (no longer needed):
```typescript
// REMOVE: let openRetention = $state(false);
```

4. Update Retention card's "Ver detalle" button:
```svelte
<button
  type="button"
  onclick={() => onSwitchTab?.('customers')}
  class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
>Ver detalle →</button>
```

5. Remove the modal mount at bottom:
```svelte
<!-- REMOVE: {#if openRetention}<RetentionListModal ... />{/if} -->
```

- [ ] **Step 3: Delete `RetentionListModal.svelte`**

```bash
rm /c/Users/Diego/el-club/overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte
```

- [ ] **Step 4: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors about missing CustomersTab impl (Task 9 fixes — but wait, CustomersTab still exists as placeholder from R1, so no error there yet); errors about missing CustomerProfileModal/etc. when CustomersTab tries to import them (Task 9+ fixes). For Task 8 specifically, expect 0 errors related to Funnel/RetentionListModal deletion.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte overhaul/src/lib/components/comercial/ComercialShell.svelte
git rm overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte
git commit -m "refactor(comercial): R4 cleanup — eliminar RetentionListModal, Funnel Retention navega a Tab 2"
```

---

### Task 9: CustomersTab — full implementation

**Files:**
- Modify: `overhaul/src/lib/components/comercial/tabs/CustomersTab.svelte` (replace R1 placeholder)

- [ ] **Step 1: Replace the entire file content**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Customer } from '$lib/data/comercial';
  import { Search, UserPlus, Star } from 'lucide-svelte';
  import CustomerProfileModal from '../modals/CustomerProfileModal.svelte';
  import CreateCustomerModal from '../modals/CreateCustomerModal.svelte';

  let customers = $state<Customer[]>([]);
  let loading = $state(true);
  let search = $state('');
  let filterVip = $state(false);
  let filterSource = $state<string>('all');
  let filterLastOrder = $state<'all' | '<30d' | '30-60d' | '60-90d' | '+90d' | 'never'>('all');
  let showBlocked = $state(false);

  type SortKey = 'ltv' | 'lastOrder' | 'totalOrders' | 'firstOrder' | 'source';
  let sortBy = $state<SortKey>('ltv');

  let openProfileId = $state<number | null>(null);
  let openCreate = $state(false);

  async function loadCustomers() {
    loading = true;
    try {
      customers = await adapter.listCustomers();
    } catch (e) {
      console.warn('[customers-tab] load failed', e);
      customers = [];
    } finally {
      loading = false;
    }
  }

  $effect(() => { void loadCustomers(); });

  function isVip(c: Customer): boolean {
    return c.totalRevenueGtq >= 1500;
  }

  function daysAgo(iso: string | null): number | null {
    if (!iso) return null;
    const ms = Date.now() - new Date(iso).getTime();
    return Math.floor(ms / 86400000);
  }

  function lastOrderBucket(c: Customer): 'never' | '<30d' | '30-60d' | '60-90d' | '+90d' {
    const d = daysAgo(c.lastOrderAt);
    if (d === null) return 'never';
    if (d < 30) return '<30d';
    if (d < 60) return '30-60d';
    if (d < 90) return '60-90d';
    return '+90d';
  }

  let filtered = $derived.by(() => {
    let list = customers;
    if (filterVip) list = list.filter(isVip);
    if (filterSource !== 'all') list = list.filter((c) => (c.source || 'manual') === filterSource);
    if (filterLastOrder !== 'all') list = list.filter((c) => lastOrderBucket(c) === filterLastOrder);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((c) =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.phone || '').toLowerCase().includes(q) ||
        (c.email || '').toLowerCase().includes(q)
      );
    }
    return list;
  });

  let sorted = $derived.by(() => {
    const arr = [...filtered];
    switch (sortBy) {
      case 'ltv': return arr.sort((a, b) => b.totalRevenueGtq - a.totalRevenueGtq);
      case 'lastOrder': return arr.sort((a, b) => (b.lastOrderAt ?? '').localeCompare(a.lastOrderAt ?? ''));
      case 'totalOrders': return arr.sort((a, b) => b.totalOrders - a.totalOrders);
      case 'firstOrder': return arr.sort((a, b) => (a.firstOrderAt ?? '').localeCompare(b.firstOrderAt ?? ''));
      case 'source': return arr.sort((a, b) => (a.source ?? '').localeCompare(b.source ?? ''));
    }
  });

  let vipCount = $derived(customers.filter(isVip).length);

  function fmtDays(d: number | null): string {
    if (d === null) return '—';
    if (d === 0) return 'hoy';
    if (d === 1) return 'ayer';
    return `${d}d`;
  }

  const SOURCES = ['all', 'f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-3 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Customers</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {customers.length} totales · {vipCount} VIP
      </span>
    </div>

    <!-- Filters row -->
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onclick={() => (filterVip = !filterVip)}
        class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
        style="
          background: {filterVip ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
          border-color: {filterVip ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
          color: {filterVip ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
        "
      >★ Solo VIP</button>

      <select
        bind:value={filterSource}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        {#each SOURCES as s}
          <option value={s}>Origen: {s}</option>
        {/each}
      </select>

      <select
        bind:value={filterLastOrder}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        <option value="all">Última: All</option>
        <option value="<30d">Última: &lt;30d</option>
        <option value="30-60d">Última: 30-60d</option>
        <option value="60-90d">Última: 60-90d</option>
        <option value="+90d">Última: +90d</option>
        <option value="never">Última: Nunca</option>
      </select>

      <button
        type="button"
        onclick={() => (openCreate = true)}
        class="ml-auto flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1 text-[11px] font-semibold text-black"
      >
        <UserPlus size={12} strokeWidth={2} />
        Crear customer
      </button>
    </div>

    <!-- Search -->
    <div class="relative">
      <Search size={12} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
      <input
        type="text"
        bind:value={search}
        placeholder="Buscar nombre, phone, email..."
        class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1.5 pl-8 pr-3 text-[11.5px] text-[var(--color-text-primary)]"
      />
    </div>

    <!-- Sort pills -->
    <div class="mt-3 flex gap-1.5">
      {#each [['ltv','LTV'],['lastOrder','Última'],['totalOrders','Órdenes'],['firstOrder','Primera'],['source','Origen']] as [key, lbl]}
        {@const active = sortBy === key}
        <button
          type="button"
          onclick={() => (sortBy = key as SortKey)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px]"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >Sort: {lbl}</button>
      {/each}
    </div>
  </div>

  <!-- List -->
  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando customers…</div>
    {:else if sorted.length === 0}
      <div class="px-6 py-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 customers que matchean los filtros</div>
    {:else}
      {#each sorted as c (c.customerId)}
        {@const vip = isVip(c)}
        {@const days = daysAgo(c.lastOrderAt)}
        <button
          type="button"
          onclick={() => (openProfileId = c.customerId)}
          class="flex w-full items-baseline border-b border-[var(--color-border)] px-6 py-2 text-left transition-colors hover:bg-[var(--color-surface-1)]"
        >
          <div class="w-5 flex-shrink-0">
            {#if vip}<Star size={11} fill="var(--color-accent)" stroke="var(--color-accent)" />{/if}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-baseline gap-2">
              <span class="text-[12.5px] font-medium text-[var(--color-text-primary)]">{c.name}</span>
              {#if vip}
                <span class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]" style="background: rgba(74,222,128,0.18); color: var(--color-accent);">
                  VIP
                </span>
              {/if}
            </div>
            <div class="text-[10px] text-[var(--color-text-tertiary)]">
              {c.phone ?? c.email ?? '—'} · {c.source ?? 'manual'}
            </div>
          </div>
          <div class="text-mono flex flex-shrink-0 items-baseline gap-4 text-[10.5px]">
            <span class="text-[var(--color-text-tertiary)]">{c.totalOrders} órd</span>
            <span class="font-semibold" style="color: var(--color-accent);">Q{c.totalRevenueGtq.toFixed(0)}</span>
            <span class="w-12 text-right text-[var(--color-text-muted)]">{fmtDays(days)}</span>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

{#if openProfileId !== null}
  <CustomerProfileModal
    customerId={openProfileId}
    onClose={() => { openProfileId = null; loadCustomers(); }}
  />
{/if}

{#if openCreate}
  <CreateCustomerModal
    onClose={() => { openCreate = false; loadCustomers(); }}
  />
{/if}
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors about missing CustomerProfileModal + CreateCustomerModal (Tasks 10/11 fix). No errors from CustomersTab itself.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/tabs/CustomersTab.svelte
git commit -m "feat(comercial): CustomersTab full impl — filters + sort + table + drilldowns"
```

---

### Task 10: CreateCustomerModal — formulario simple

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/CreateCustomerModal.svelte`

- [ ] **Step 1: Create the file**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import { UserPlus, Loader2 } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    onClose: () => void;
  }
  let { onClose }: Props = $props();

  let name = $state('');
  let phone = $state('');
  let email = $state('');
  let source = $state('f&f');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const SOURCES = ['f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];

  async function handleSubmit() {
    error = null;
    if (!name.trim()) {
      error = 'Nombre es requerido';
      return;
    }
    saving = true;
    try {
      const result = await adapter.createCustomer({
        name: name.trim(),
        phone: phone.trim() || null,
        email: email.trim() || null,
        source: source || null,
      });
      if (!result.ok) {
        error = result.error ?? 'Error desconocido';
      } else {
        onClose();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
        <UserPlus size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Crear customer manual</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Registro mínimo. Después podés crear orden manual desde el profile.</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    <div class="space-y-3 px-6 py-4">
      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Nombre *</label>
        <input
          type="text"
          bind:value={name}
          placeholder="Pedro García"
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Phone</label>
        <input
          type="text"
          bind:value={phone}
          placeholder="+502 1234-5678"
          class="text-mono w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Email</label>
        <input
          type="email"
          bind:value={email}
          placeholder="pedro@gmail.com"
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Origen</label>
        <select
          bind:value={source}
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        >
          {#each SOURCES as s}
            <option value={s}>{s}</option>
          {/each}
        </select>
      </div>

      {#if error}
        <div class="rounded-[3px] border border-[var(--color-danger)] bg-[var(--color-surface-1)] p-2 text-[10.5px] text-[var(--color-danger)]">
          ⚠ {error}
        </div>
      {/if}
    </div>
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onClose}
        disabled={saving}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
      >Cancelar</button>
      <button
        type="button"
        onclick={handleSubmit}
        disabled={saving || !name.trim()}
        class="ml-auto flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if saving}
          <Loader2 size={12} strokeWidth={2} class="animate-spin" /> Creando…
        {:else}
          Crear
        {/if}
      </button>
    </div>
  {/snippet}
</BaseModal>
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: only CustomerProfileModal error remains (Task 11 fixes).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/CreateCustomerModal.svelte
git commit -m "feat(comercial): CreateCustomerModal — form name+phone+email+source"
```

---

### Task 11: CustomerProfileModal — full feature

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/CustomerProfileModal.svelte`

This is the biggest UI piece in R4. Has: header (name + VIP + LTV + status), body 2-col (timeline left, meta sidebar right), footer 4 actions, plus inline sub-forms for "edit traits" + "generate cupón" + "edit source".

- [ ] **Step 1: Create the file**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CustomerProfile, TimelineEntry } from '$lib/data/comercial';
  import { Star, Loader2, ShoppingCart, Ticket, Pencil, Ban, CheckCircle2, ExternalLink } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import OrderDetailModal from './OrderDetailModal.svelte';
  import ConversationThreadModal from './ConversationThreadModal.svelte';
  import ManualOrderModal from './ManualOrderModal.svelte';
  import { SYNC_CONSTANTS } from '$lib/data/manychatSync';

  interface Props {
    customerId: number;
    onClose: () => void;
  }
  let { customerId, onClose }: Props = $props();

  let profile = $state<CustomerProfile | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Sub-modal triggers
  let openOrderRef = $state<string | null>(null);
  let openConvId = $state<string | null>(null);
  let openManualOrder = $state(false);

  // Inline editor states
  let editingTraits = $state(false);
  let traitsDraft = $state('');
  let traitsError = $state<string | null>(null);

  let editingSource = $state(false);
  let sourceDraft = $state('');

  let editingCoupon = $state(false);
  let couponType = $state<'percent' | 'amount'>('percent');
  let couponValue = $state(10);
  let couponDays = $state(30);
  let couponResult = $state<string | null>(null);
  let couponError = $state<string | null>(null);
  let couponSaving = $state(false);

  let blockedToggling = $state(false);

  const SOURCES = ['f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];

  async function loadProfile() {
    loading = true;
    error = null;
    try {
      profile = await adapter.getCustomerProfile(customerId);
      if (!profile) error = `Customer ${customerId} no encontrado`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { void loadProfile(); });

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }

  function fmtTimelineDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }

  function selectTimelineEntry(entry: TimelineEntry) {
    if (entry.kind === 'order') openOrderRef = entry.ref;
    else if (entry.kind === 'conversation') openConvId = entry.convId;
  }

  // === Edit traits ===
  function startEditTraits() {
    if (!profile) return;
    traitsDraft = JSON.stringify(profile.traitsJson ?? {}, null, 2);
    traitsError = null;
    editingTraits = true;
  }

  async function saveTraits() {
    if (!profile) return;
    try {
      const parsed = JSON.parse(traitsDraft);
      if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
        traitsError = 'Debe ser un objeto JSON';
        return;
      }
      await adapter.updateCustomerTraits(profile.customerId, parsed);
      editingTraits = false;
      await loadProfile();
    } catch (e) {
      if (e instanceof SyntaxError) {
        traitsError = `JSON inválido: ${e.message}`;
      } else {
        traitsError = e instanceof Error ? e.message : String(e);
      }
    }
  }

  // === Edit source ===
  function startEditSource() {
    if (!profile) return;
    sourceDraft = profile.source ?? 'manual';
    editingSource = true;
  }

  async function saveSource() {
    if (!profile) return;
    try {
      await adapter.updateCustomerSource(profile.customerId, sourceDraft || null);
      editingSource = false;
      await loadProfile();
    } catch (e) {
      console.warn('[customer-profile] source update failed', e);
    }
  }

  // === Block / unblock ===
  async function toggleBlocked() {
    if (!profile || blockedToggling) return;
    blockedToggling = true;
    try {
      await adapter.setCustomerBlocked(profile.customerId, !profile.blocked);
      await loadProfile();
    } catch (e) {
      console.warn('[customer-profile] block toggle failed', e);
    } finally {
      blockedToggling = false;
    }
  }

  // === Generate coupon ===
  function startCoupon() {
    if (!profile) return;
    couponType = 'percent';
    couponValue = 10;
    couponDays = 30;
    couponResult = null;
    couponError = null;
    editingCoupon = true;
  }

  async function submitCoupon() {
    if (!profile || couponSaving) return;
    couponError = null;
    couponSaving = true;
    try {
      const result = await adapter.generateCoupon({
        customerId: profile.customerId,
        type: couponType,
        value: couponValue,
        expiresInDays: couponDays,
        apiKey: SYNC_CONSTANTS.DASHBOARD_KEY,    // Task 0 may identify a different secret; if so, adjust
        workerBase: SYNC_CONSTANTS.WORKER_BASE,
      });
      if (result.ok && result.code) {
        couponResult = result.code;
      } else {
        couponError = result.error ?? 'Error desconocido';
      }
    } catch (e) {
      couponError = e instanceof Error ? e.message : String(e);
    } finally {
      couponSaving = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" /> <span class="text-[14px]">Cargando customer…</span>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {:else if profile}
      <div class="flex items-center gap-3">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-[6px]"
          style="background: {profile.isVip ? 'rgba(74,222,128,0.12)' : 'rgba(180,181,184,0.12)'}; border: 1px solid {profile.isVip ? 'rgba(74,222,128,0.3)' : 'rgba(180,181,184,0.3)'};"
        >
          {#if profile.isVip}
            <Star size={18} strokeWidth={1.8} fill="var(--color-accent)" style="color: var(--color-accent);" />
          {:else}
            <span class="text-display text-[12px] text-[var(--color-text-tertiary)]">{profile.name.slice(0, 2).toUpperCase()}</span>
          {/if}
        </div>
        <div>
          <div class="flex items-center gap-2 text-[18px] font-semibold">
            <span>{profile.name}</span>
            {#if profile.isVip}
              <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(74,222,128,0.18); color: var(--color-accent);">★ VIP</span>
            {/if}
            {#if profile.blocked}
              <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(244,63,94,0.18); color: var(--color-danger);">● BLOCKED</span>
            {/if}
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            <span class="text-mono">Q{profile.totalRevenueGtq.toFixed(0)}</span> LTV ·
            {profile.totalOrders} órdenes ·
            {profile.attribution.customerSource ?? 'sin origen'} ·
            últ {fmtDate(profile.lastOrderAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if profile}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px] overflow-hidden">
        <!-- Timeline -->
        <div class="border-r border-[var(--color-border)] overflow-y-auto px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Timeline · {profile.timeline.length} entries</div>
          {#if profile.timeline.length === 0}
            <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">> sin actividad registrada</div>
          {:else}
            <div class="space-y-2">
              {#each profile.timeline as entry, i (i)}
                <button
                  type="button"
                  onclick={() => selectTimelineEntry(entry)}
                  class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 hover:border-[var(--color-accent)]"
                  style="border-left: 3px solid {entry.kind === 'order' ? 'var(--color-accent)' : 'var(--color-warning)'};"
                >
                  <div class="flex items-baseline justify-between gap-2">
                    <div class="flex items-center gap-2">
                      <span class="text-display text-[9px]" style="color: {entry.kind === 'order' ? 'var(--color-accent)' : 'var(--color-warning)'};">
                        [{entry.kind === 'order' ? 'ORDER' : 'CONV'}]
                      </span>
                      {#if entry.kind === 'order'}
                        <span class="text-mono text-[11.5px]">{entry.ref}</span>
                      {:else}
                        <span class="text-mono text-[11px] text-[var(--color-text-secondary)]">{entry.convId}</span>
                      {/if}
                    </div>
                    <span class="text-mono text-[10px] text-[var(--color-text-muted)]">
                      {entry.kind === 'order' ? fmtTimelineDate(entry.occurredAt) : fmtTimelineDate(entry.endedAt)}
                    </span>
                  </div>
                  <div class="mt-1 text-[10.5px] text-[var(--color-text-tertiary)]">
                    {#if entry.kind === 'order'}
                      Q{entry.totalGtq.toFixed(0)} · {entry.status} · {entry.itemsCount} item{entry.itemsCount === 1 ? '' : 's'}
                    {:else}
                      {entry.platform.toUpperCase()} · {entry.outcome ?? 'open'} · {entry.messagesTotal} msgs
                    {/if}
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Meta sidebar -->
        <div class="overflow-y-auto bg-[var(--color-surface-0)] px-4 py-4">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Info</div>
          <div class="mb-4 space-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{profile.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Email</span><span class="truncate" style="max-width: 160px;">{profile.email ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">First</span><span class="text-mono">{fmtDate(profile.firstOrderAt)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Active</span><span class="text-mono">{profile.daysInactive ?? '—'}d</span></div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Atribución</div>
          {#if editingSource}
            <div class="mb-4 space-y-2">
              <select
                bind:value={sourceDraft}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]"
              >
                {#each SOURCES as s}
                  <option value={s}>{s}</option>
                {/each}
              </select>
              <div class="flex gap-2">
                <button onclick={saveSource} class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-0.5 text-[10px] font-semibold text-black">Guardar</button>
                <button onclick={() => (editingSource = false)} class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">Cancelar</button>
              </div>
            </div>
          {:else}
            <div class="mb-4 space-y-1.5 text-[11px]">
              <div class="flex justify-between">
                <span class="text-[var(--color-text-tertiary)]">Source</span>
                <span>
                  {profile.attribution.customerSource ?? '—'}
                  <button onclick={startEditSource} class="ml-1 text-[10px] text-[var(--color-accent)]">[editar]</button>
                </span>
              </div>
              {#if profile.attribution.leadCampaigns.length > 0}
                <div class="text-[10px] text-[var(--color-text-tertiary)]">
                  Lead camps: <span class="text-mono">{profile.attribution.leadCampaigns.join(' · ')}</span>
                </div>
              {/if}
            </div>
          {/if}

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">
            Traits
            {#if !editingTraits}
              <button onclick={startEditTraits} class="ml-1 text-[10px] text-[var(--color-accent)]">[editar]</button>
            {/if}
          </div>
          {#if editingTraits}
            <div class="mb-4 space-y-2">
              <textarea
                bind:value={traitsDraft}
                class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10px]"
                rows="6"
              ></textarea>
              {#if traitsError}<div class="text-[10px] text-[var(--color-danger)]">⚠ {traitsError}</div>{/if}
              <div class="flex gap-2">
                <button onclick={saveTraits} class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-0.5 text-[10px] font-semibold text-black">Guardar</button>
                <button onclick={() => (editingTraits = false)} class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">Cancelar</button>
              </div>
            </div>
          {:else}
            <pre class="text-mono mb-4 rounded-[3px] bg-[var(--color-surface-1)] p-2 text-[10px] text-[var(--color-text-secondary)]" style="white-space: pre-wrap;">{JSON.stringify(profile.traitsJson, null, 2)}</pre>
          {/if}

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Status</div>
          <div class="flex items-center justify-between text-[11px]">
            <span class="{profile.blocked ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'}">
              {profile.blocked ? '● Bloqueado' : '● Activo'}
            </span>
            <button
              onclick={toggleBlocked}
              disabled={blockedToggling}
              class="rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] disabled:opacity-50"
            >
              {profile.blocked ? 'Desbloquear' : 'Bloquear'}
            </button>
          </div>

          {#if editingCoupon}
            <div class="mt-4 rounded-[4px] border border-[var(--color-accent)] bg-[var(--color-surface-1)] p-3">
              <div class="text-display mb-2 text-[9.5px] text-[var(--color-accent)]">Generar cupón</div>
              <div class="space-y-2 text-[10.5px]">
                <div class="flex gap-2">
                  <select bind:value={couponType} class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-1 py-0.5 text-[10px]">
                    <option value="percent">% percent</option>
                    <option value="amount">Q amount</option>
                  </select>
                  <input type="number" bind:value={couponValue} min="1" class="w-16 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px]" />
                </div>
                <div class="flex justify-between">
                  <span>Vence en (días)</span>
                  <input type="number" bind:value={couponDays} min="1" class="w-16 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px]" />
                </div>
                {#if couponResult}
                  <div class="rounded-[3px] bg-[var(--color-surface-0)] p-2 text-mono text-[11px] text-[var(--color-accent)]">
                    ✓ {couponResult}
                  </div>
                {/if}
                {#if couponError}
                  <div class="text-[10px] text-[var(--color-danger)]">⚠ {couponError}</div>
                {/if}
                <div class="flex gap-2">
                  <button onclick={submitCoupon} disabled={couponSaving} class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-0.5 text-[10px] font-semibold text-black disabled:opacity-60">
                    {#if couponSaving}<Loader2 size={10} class="animate-spin" />{:else}Generar{/if}
                  </button>
                  <button onclick={() => (editingCoupon = false)} class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px]">Cerrar</button>
                </div>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if profile}
      <div class="flex items-center gap-2">
        <button
          onclick={() => (openManualOrder = true)}
          class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)]"
        >
          <ShoppingCart size={12} strokeWidth={1.8} /> + Orden manual
        </button>
        <button
          onclick={startCoupon}
          class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)]"
        >
          <Ticket size={12} strokeWidth={1.8} /> Cupón
        </button>
        <button
          onclick={onClose}
          class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
        >Cerrar</button>
      </div>
    {/if}
  {/snippet}
</BaseModal>

{#if openOrderRef}
  <OrderDetailModal orderRef={openOrderRef} onClose={() => { openOrderRef = null; loadProfile(); }} />
{/if}

{#if openConvId && profile}
  {@const conv = profile.timeline.find((e) => e.kind === 'conversation' && e.convId === openConvId)}
  {#if conv && conv.kind === 'conversation'}
    <ConversationThreadModal conversations={[{
      convId: conv.convId, leadId: null, brand: 'elclub', platform: conv.platform as any,
      senderId: '', startedAt: '', endedAt: conv.endedAt, outcome: (conv.outcome as any) ?? null,
      orderId: null, messagesTotal: conv.messagesTotal, tagsJson: [], analyzed: false, syncedAt: ''
    }]} onClose={() => { openConvId = null; }} />
  {/if}
{/if}

{#if openManualOrder && profile}
  <ManualOrderModal
    customer={profile}
    onClose={() => { openManualOrder = false; loadProfile(); }}
  />
{/if}
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: errors only about ManualOrderModal (Task 12 fixes).

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/CustomerProfileModal.svelte
git commit -m "feat(comercial): CustomerProfileModal — header + timeline + 4 actions inline editors"
```

---

### Task 12: ManualOrderModal — form de orden manual

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/ManualOrderModal.svelte`

- [ ] **Step 1: Create the file**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CustomerProfile, CreateOrderItem } from '$lib/data/comercial';
  import { ShoppingCart, Loader2, Plus, X } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    customer: CustomerProfile;
    onClose: () => void;
  }
  let { customer, onClose }: Props = $props();

  type EditableItem = CreateOrderItem & { localId: number };

  let nextId = 1;
  let items = $state<EditableItem[]>([{
    localId: nextId++,
    familyId: '',
    jerseyId: '',
    team: '',
    size: 'M',
    variantLabel: null,
    version: null,
    personalizationJson: null,
    unitPrice: 0,
    unitCost: null,
    itemType: 'manual',
  }]);

  let paymentMethod = $state<'recurrente' | 'transfer' | 'cod' | 'cash'>('transfer');
  let fulfillmentStatus = $state<'pending_payment' | 'paid' | 'awaiting_shipment' | 'shipped' | 'delivered'>('paid');
  let shippingFee = $state(0);
  let discount = $state(0);
  let notes = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  // Catalog: load on mount
  let families = $state<any[]>([]);
  let loadingCatalog = $state(true);

  $effect(() => {
    void (async () => {
      try {
        // listFamilies returns array of Family objects with nested modelos
        const result = await adapter.listFamilies();
        families = result;
      } catch (e) {
        console.warn('[manual-order] catalog load failed', e);
      } finally {
        loadingCatalog = false;
      }
    })();
  });

  // Distinct teams from catalog
  let teams = $derived.by(() => {
    const set = new Set<string>();
    for (const f of families) if (f.team) set.add(f.team);
    return Array.from(set).sort();
  });

  function jerseysForTeam(team: string) {
    return families.filter((f) => f.team === team);
  }

  function jerseySublabel(family: any): string {
    return `${family.season ?? ''} ${family.variant_label ?? family.variant ?? ''}`.trim() || family.id;
  }

  // Auto-fill price when family selected
  function onFamilyChange(item: EditableItem) {
    const fam = families.find((f) => f.id === item.familyId);
    if (fam) {
      item.team = fam.team;
      item.variantLabel = fam.variant_label ?? fam.variant ?? null;
      item.version = fam.season ?? null;
      // Use first modelo's price as default; jerseyId becomes the family id (one model per family in our catalog typically)
      if (fam.modelos && fam.modelos[0]) {
        item.jerseyId = fam.modelos[0].sku || fam.id;
        if (fam.modelos[0].price) item.unitPrice = fam.modelos[0].price;
      } else {
        item.jerseyId = fam.id;
      }
    }
  }

  function addItem() {
    items.push({
      localId: nextId++,
      familyId: '', jerseyId: '', team: '', size: 'M',
      variantLabel: null, version: null, personalizationJson: null,
      unitPrice: 0, unitCost: null, itemType: 'manual',
    });
  }

  function removeItem(localId: number) {
    if (items.length === 1) return;
    items = items.filter((i) => i.localId !== localId);
  }

  let subtotal = $derived(items.reduce((s, i) => s + (i.unitPrice || 0), 0));
  let total = $derived(subtotal + shippingFee - discount);

  async function handleSubmit() {
    error = null;
    if (items.some((i) => !i.familyId || !i.jerseyId || !i.size || !i.unitPrice || i.unitPrice <= 0)) {
      error = 'Cada item necesita: team, jersey, size, unit price > 0';
      return;
    }
    if (total <= 0) {
      error = 'Total debe ser > 0';
      return;
    }
    saving = true;
    try {
      const payload = {
        customerId: customer.customerId,
        items: items.map(({ localId, ...rest }) => rest),
        paymentMethod,
        fulfillmentStatus,
        shippingFee,
        discount,
        notes: notes || undefined,
      };
      const result = await adapter.createManualOrder(payload);
      if (result.ok && result.ref) {
        onClose();
      } else {
        error = result.error ?? 'Error desconocido';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
        <ShoppingCart size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Crear orden manual</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Cliente: {customer.name}</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    {#if loadingCatalog}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando catálogo…</div>
    {:else}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px]">
        <!-- Items column -->
        <div class="overflow-y-auto border-r border-[var(--color-border)] px-6 py-4">
          <div class="mb-3 flex items-baseline justify-between">
            <span class="text-display text-[9.5px] text-[var(--color-text-tertiary)]">Items · {items.length}</span>
            <button onclick={addItem} class="flex items-center gap-1 text-[10px] text-[var(--color-accent)]">
              <Plus size={10} /> Agregar item
            </button>
          </div>

          <div class="space-y-3">
            {#each items as item, idx (item.localId)}
              <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
                <div class="mb-2 flex items-baseline justify-between">
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">item #{idx + 1}</span>
                  {#if items.length > 1}
                    <button onclick={() => removeItem(item.localId)} class="text-[var(--color-danger)]"><X size={12} /></button>
                  {/if}
                </div>

                <div class="space-y-2 text-[10.5px]">
                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Team</span>
                    <select
                      bind:value={item.team}
                      onchange={() => { item.familyId = ''; item.jerseyId = ''; }}
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    >
                      <option value="">— elegir —</option>
                      {#each teams as t}<option value={t}>{t}</option>{/each}
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Jersey</span>
                    <select
                      bind:value={item.familyId}
                      onchange={() => onFamilyChange(item)}
                      disabled={!item.team}
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5 disabled:opacity-50"
                    >
                      <option value="">— elegir —</option>
                      {#each jerseysForTeam(item.team) as fam}
                        <option value={fam.id}>{jerseySublabel(fam)}</option>
                      {/each}
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Size</span>
                    <select bind:value={item.size} class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5">
                      <option value="S">S</option><option value="M">M</option><option value="L">L</option>
                      <option value="XL">XL</option><option value="XXL">XXL</option>
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Pers.</span>
                    <input
                      type="text"
                      bind:value={item.personalizationJson}
                      placeholder="ej. 10 MESSI"
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Q precio</span>
                    <input
                      type="number"
                      bind:value={item.unitPrice}
                      class="text-mono w-24 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                    <span class="ml-2 w-16 text-[var(--color-text-tertiary)]">Q cost</span>
                    <input
                      type="number"
                      bind:value={item.unitCost}
                      placeholder="opt"
                      class="text-mono w-24 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Totals + meta sidebar -->
        <div class="bg-[var(--color-surface-0)] px-4 py-4">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Totales</div>
          <div class="mb-4 space-y-1 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Subtotal</span><span class="text-mono">Q{subtotal.toFixed(0)}</span></div>
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-[var(--color-text-tertiary)]">Shipping</span>
              <input type="number" bind:value={shippingFee} class="text-mono w-20 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-right" />
            </div>
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-[var(--color-text-tertiary)]">Discount</span>
              <input type="number" bind:value={discount} class="text-mono w-20 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-right" />
            </div>
            <div class="border-t border-[var(--color-border)] pt-1.5 flex justify-between">
              <span class="font-semibold">TOTAL</span>
              <span class="text-mono font-semibold" style="color: var(--color-accent);">Q{total.toFixed(0)}</span>
            </div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Pago + entrega</div>
          <div class="mb-4 space-y-2 text-[10.5px]">
            <select bind:value={paymentMethod} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5">
              <option value="transfer">Transfer</option>
              <option value="recurrente">Recurrente</option>
              <option value="cod">COD</option>
              <option value="cash">Cash</option>
            </select>
            <select bind:value={fulfillmentStatus} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5">
              <option value="paid">Paid</option>
              <option value="pending_payment">Pending payment</option>
              <option value="awaiting_shipment">Awaiting shipment</option>
              <option value="shipped">Shipped</option>
              <option value="delivered">Delivered</option>
            </select>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Notes</div>
          <textarea
            bind:value={notes}
            class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10.5px]"
            rows="2"
          ></textarea>

          {#if error}
            <div class="mt-2 rounded-[3px] border border-[var(--color-danger)] p-2 text-[10px] text-[var(--color-danger)]">⚠ {error}</div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onClose}
        disabled={saving}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
      >Cancelar</button>
      <button
        type="button"
        onclick={handleSubmit}
        disabled={saving || total <= 0 || items.some((i) => !i.familyId || !i.unitPrice)}
        class="ml-auto flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if saving}<Loader2 size={12} class="animate-spin" /> Registrando…{:else}Registrar orden{/if}
      </button>
    </div>
  {/snippet}
</BaseModal>
```

- [ ] **Step 2: Type check**

```bash
cd /c/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/ManualOrderModal.svelte
git commit -m "feat(comercial): ManualOrderModal — items multi-row + totales + register"
```

---

### Task 13: Build MSI v0.1.30 + tag + LOG

**Files:**
- Modify: `overhaul/src-tauri/Cargo.toml` (version)
- Modify: `overhaul/src-tauri/tauri.conf.json` (version)

- [ ] **Step 1: Bump version**

Edit BOTH files via Edit tool:
- `overhaul/src-tauri/Cargo.toml`: `version = "0.1.29"` → `version = "0.1.30"`
- `overhaul/src-tauri/tauri.conf.json`: `"version": "0.1.29"` → `"version": "0.1.30"`

Verify:
```bash
grep -E '^version|"version"' /c/Users/Diego/el-club/overhaul/src-tauri/Cargo.toml /c/Users/Diego/el-club/overhaul/src-tauri/tauri.conf.json
```
Both must show 0.1.30.

- [ ] **Step 2: Build MSI** (timeout 600000 ms)

```bash
cd /c/Users/Diego/el-club/overhaul
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build 2>&1 | tail -30
```

Expected: `Finished 1 bundle at: .../El Club ERP_0.1.30_x64_en-US.msi`.

If it fails with Rust errors, paste last 30 lines and STOP.

- [ ] **Step 3: Verify MSI exists**

```bash
ls -la /c/Users/Diego/el-club/overhaul/src-tauri/target/release/bundle/msi/ | head
```

- [ ] **Step 4: Commit + tag**

```bash
cd /c/Users/Diego/el-club
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json
git status -s | grep -q "Cargo.lock" && git add overhaul/src-tauri/Cargo.lock
git commit -m "chore(release): v0.1.30 — Comercial R4 (Customers + Atribución lite)"
git tag v0.1.30
git log --oneline -1 && git tag --list | tail -3
```

- [ ] **Step 5: Update LOG.md de Strategy**

Edit `/c/Users/Diego/elclub-catalogo-priv/docs/LOG.md`. Prepend at the top after R2-combo entry:

```markdown
## 2026-04-26 — R4 SHIPPED: Customers + Atribución lite (v0.1.30)

**Outcome:** Tab Customers full feature funcional. CustomerProfileModal con timeline (orders + conversations) + 4 acciones inline (cupón / traits / bloquear / crear orden manual). VIP detection automática (LTV ≥ Q1,500, computed). Detector "VIP inactivos +60d" infraestructurado. RetentionListModal eliminado (Tab 2 lo reemplaza).

**Tasks shipped (13 total + Task 0 pre-flight):**
- Schema: customers.blocked column (additive)
- Types: CustomerProfile, TimelineEntry, CreateCustomerArgs, CreateOrderArgs, CreateOrderItem
- Bridge: 7 handlers (get_customer_profile, create_customer, update_traits, set_blocked, update_source, create_manual_order, generate_coupon)
- Rust: 7 Tauri command wrappers
- Adapter: contract + Tauri impls + browser stubs (7 methods)
- Detector: detectVipInactive60d (severity strat, no push WA)
- Cleanup: eliminado RetentionListModal, Funnel Retention navega a Tab 2 vía callback
- CustomersTab full impl: 4 filtros (VIP/origen/última/búsqueda) + 5 sorts + drilldown
- CreateCustomerModal: form simple
- CustomerProfileModal: header + timeline 2-col + 4 acciones inline
- ManualOrderModal: items multi-row + totales + payment/fulfillment dropdowns

**Decisiones tomadas (Diego delegó decisorio "decidí tú"):**
- Atribución lite (no `sales_attribution` table) — 19/21 customers son f&f
- VIP computed on-the-fly (no campo is_vip)
- Bloquear = ALTER TABLE customers ADD COLUMN blocked
- Notas privadas DEFER (R5+ con propia tabla customer_notes)
- Tag chips UX DEFER (R6 polish si raw JSON edit duele)

**Métricas:**
- Files: ~12 modified/created, 1 deleted
- Commits: ~15 in branch comercial-design (R4 only)
- Tag: v0.1.30
- Build: MSI exitoso

**Próximo paso (R5):** Ads + Performance. Sync Meta API → campaigns_snapshot. Awareness etapa con data real. CampaignDetailModal con time-series. Detector "Campaign performance ↓ >30%".
```

DON'T commit elclub-catalogo-priv (Diego pushea cuando quiera).

- [ ] **Step 6: Final report**

Report tag `v0.1.30` creado, MSI listo, LOG actualizado pendiente de push manual.

---

## Self-Review

**1. Spec coverage:**

- ✅ Sec 2 Scope: all "incluido" items have tasks (Tab Customers→9, modals→10/11/12, schema→1, detector→7, etc.)
- ✅ Sec 3 Architecture: data flow + VIP computation + ref generation all in Tasks 3 (bridge)
- ✅ Sec 4 Components: every NEW/MODIFIED file has a corresponding task
- ✅ Sec 5 Tab UX: filters + sort + table + drilldown all covered in Task 9
- ✅ Sec 6 Profile UX: timeline + meta sidebar + 4 actions all in Task 11
- ✅ Sec 7 ManualOrder UX: multi-item + totals + payment/fulfillment in Task 12
- ✅ Sec 8 CreateCustomer UX: simple form in Task 10
- ✅ Sec 9 Detector: detectVipInactive60d in Task 7
- ✅ Sec 10 Coupon: handled in Task 0 (pre-flight) + Task 3 (cmd_generate_coupon) + Task 11 (UI)
- ✅ Sec 11 Errors: validations in bridge + try/catch in modals
- ✅ Sec 13 Release: Task 13 covers MSI v0.1.30 + tag + LOG

**2. Placeholder scan:**
- One known gap: `cmd_generate_coupon` uses `apiKey` arg from caller — Task 0 pre-flight identifies the actual secret name. Plan documents this as expected investigation.
- No other "TBD"/"TODO"/"implement later" found.

**3. Type consistency:**
- `CustomerProfile` defined in Task 2, used in Tasks 3 (bridge response), 6 (adapter return), 11 (modal prop) ✓
- `CreateOrderArgs` / `CreateOrderItem` defined Task 2, used Tasks 3, 6, 12 ✓
- `TimelineEntry` defined Task 2, used Tasks 3, 11 ✓
- Bridge handler names ↔ Rust command names ↔ adapter methods all aligned ✓
- `apiKey` parameter pattern flows through Tasks 3 (bridge), 4 (Rust struct), 6 (adapter signature), 11 (modal call). Same name across all layers.

**4. Coverage gaps:** None identified.

---

## Execution Handoff

**Plan complete and saved to `el-club/overhaul/docs/superpowers/plans/2026-04-26-comercial-r4-customers-atribucion.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — Mismo flow que R1 + R2-combo. Despacho un subagent por task, review entre tasks, fast iteration.

**2. Inline Execution** — Ejecutamos tasks en esta sesión usando executing-plans, batch con checkpoints.

**Diego ya autorizó "decidí tú" para el flow de design.** Para ejecución: ¿mantenemos subagent-driven (consistente con R1 y R2) o inline?
