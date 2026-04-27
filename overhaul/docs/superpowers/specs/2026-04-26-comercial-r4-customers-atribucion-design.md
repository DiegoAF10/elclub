# Comercial R4 — Customers + Atribución (lite)

**Author:** Claude (decisions delegated by Diego: "decidí tú, iteramos al usar")
**Date:** 2026-04-26
**Status:** Approved scope (Diego pre-authorized iterative pragmatic approach)
**Supersedes:** "Release 4 — Customers + Atribución" of `2026-04-26-comercial-design.md`

---

## 1. Goal

Build the Tab Customers full feature + CustomerProfileModal with 4 primary actions (generate coupon · edit traits · block · create manual order). Add VIP detection (computed on-the-fly, LTV ≥ Q1,500) and the "VIP inactivos +60d" detector. Eliminate the provisional `RetentionListModal` from R2-combo (Tab 2 supersedes it).

After R4 ships, Diego knows his customers cold: the 3 VIPs (Raul/Mariana/Juan today) get a deep profile with timeline + traits + manual actions. The 18 f&f customers are sortable/filterable/searchable. Off-platform sales can be registered manually without bypassing the data layer.

**Pragmatic note:** Diego authorized full decision autonomy on design choices. Iteration happens during real use, not during design.

---

## 2. Scope

### Included

| Area | What ships |
|---|---|
| **Tab 2 Customers** | Full feature replacing R1 placeholder. Sortable list (LTV/última/órdenes/primera) + 4 filters (VIP/origen/última compra bucket/búsqueda) + header buttons "+ Crear customer" / "Exportar CSV" |
| **CustomerProfileModal** | Full feature. Header con name + VIP star + LTV. Body 2 cols (timeline left, meta sidebar right). Footer 4 actions. |
| **ManualOrderModal** | Form para registrar venta off-platform. Multi-item, SKU picker desde catálogo published, defaults `transfer`/`paid`. |
| **CreateCustomerModal** | Form chico: name + phone + email + source dropdown. Sólo crea row, no orden. |
| **Schema migration** | `ALTER TABLE customers ADD COLUMN blocked INTEGER DEFAULT 0` |
| **Detector** | "VIP inactivos +60d" — severity `strat`, no push WA |
| **Atribución display** | Sólo lectura desde `customers.source` + lookup en `leads.source_campaign_id` por phone match. Editable manualmente desde el profile. |
| **Cleanup** | Eliminar `RetentionListModal.svelte`. Funnel Retention drilldown navega a Tab 2. |
| **Adapter methods** | ~7 nuevos: `getCustomerProfile`, `updateCustomerTraits`, `setCustomerBlocked`, `updateCustomerSource`, `createCustomer`, `createManualOrder`, `generateCoupon` |

### Deferred to later releases

| Item | Where | Why |
|---|---|---|
| Notas privadas por customer | R5+ con propia tabla `customer_notes` | Decision deferred — pragmatic iteration ("ver si las uso") |
| Bulk import CSV de órdenes | R6+ con sub-spec | Edge case, raro |
| Refunds / cancelaciones | R6+ con sub-spec | Acción inversa con sus propios edge cases |
| Multi-touch attribution real | NUNCA (Diego not at scale) | 19/21 son f&f. Multi-touch es ingeniería sin necesidad de negocio. |
| Tag chips UI para traits | R6 polish si raw JSON edit duele | Empezamos simple |
| Sub-tabs en customer profile | R6 polish | Body actual con 2 cols cubre |

---

## 3. Architecture

### Data flow R4

```
Customer Tab loads → adapter.listCustomers() → SQLite query con totals computados
   ├─ Filter VIP: WHERE total_revenue >= 1500 (no campo is_vip — derived)
   ├─ Filter blocked: AND blocked = 0 por default (toggle para mostrar bloqueados)
   ├─ Filter source: AND source = ?
   ├─ Filter last_order_at: AND last_order_at BETWEEN cutoffs
   └─ Search: AND (name LIKE '%q%' OR phone LIKE '%q%' OR email LIKE '%q%')

Customer click → CustomerProfileModal opens
   ├─ adapter.getCustomerProfile(customerId)
   │     └─ Returns: customer + sales[] + conversations[] (joined by phone) + computed: ltv, isVip, daysInactive
   ├─ Timeline: merge orders + conversations, sort by timestamp DESC
   └─ 4 action buttons → modal-on-modal flows OR adapter writes

Action: Generate coupon
   └─ adapter.generateCoupon({customerId, type, value}) → POST worker /api/coupons/generate
   └─ Toast con coupon code + opciones share

Action: Edit traits
   └─ inline textarea (JSON validate on save)
   └─ adapter.updateCustomerTraits(customerId, traitsJson)

Action: Toggle blocked
   └─ adapter.setCustomerBlocked(customerId, blocked: boolean)
   └─ Refresh modal

Action: Crear orden manual
   └─ ManualOrderModal opens (modal-on-modal — z-index higher)
   └─ Items multi-row form
   └─ adapter.createManualOrder({customerId, items, payment, fulfillment, ...})
   └─ Returns new sale ref → toast + refresh CustomerProfile timeline

Detector loop (existing every 15 min)
   └─ + detectVipInactive60d():
        leads = customers WHERE total_revenue >= 1500 AND last_order_at < (now - 60d)
        if any → DetectedEvent severity=strat, no push WA
```

### Schema additions

**Single migration** (additive, idempotent):

```sql
-- audit_db.py init_audit_schema()
-- Try/except OperationalError pattern (matches R1 Task 10 fix style)
try:
    cur.execute("ALTER TABLE customers ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
except sqlite3.OperationalError:
    pass  # column already exists
```

No new tables. `customer_notes` deferred.

### VIP computation

VIP is **always derived**, never stored:

```sql
-- In query that returns customers:
SELECT
  c.*,
  COALESCE(SUM(s.total), 0) AS total_revenue,
  CASE WHEN COALESCE(SUM(s.total), 0) >= 1500 THEN 1 ELSE 0 END AS is_vip,
  MAX(s.occurred_at) AS last_order_at,
  COUNT(s.sale_id) AS total_orders
FROM customers c
LEFT JOIN sales s ON s.customer_id = c.customer_id
WHERE c.blocked = 0
GROUP BY c.customer_id
```

Threshold `1500` hardcoded as constant in the bridge handler. R6 polish: move to `meta_sync` or new `app_config` table for editability.

### Manual order generation

**Reference generation:** match the bot's existing pattern. Bot generates `CE-XXXX` where XXXX is 4-char random `[A-Z0-9]`. Bridge handler implements:

```python
import secrets, string
def gen_ref():
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"CE-{suffix}"

# Retry on UNIQUE constraint violation (extremely rare)
for _ in range(5):
    ref = gen_ref()
    try:
        # INSERT INTO sales (ref, ...) ...
        break
    except sqlite3.IntegrityError:
        continue
else:
    return {"ok": False, "error": "ref collision (5 retries)"}
```

**Validation in bridge:**
- `customer_id` must exist
- `items[]` non-empty
- Each item has `family_id`, `jersey_id`, `size`, `unit_price > 0`
- `total = subtotal + shipping_fee - discount`
- `payment_method` in enum
- `fulfillment_status` in enum

Returns `{ok: true, ref: "CE-XXXX", saleId: N}`.

---

## 4. Components

### 4.1 New Svelte components

| File | Responsibility |
|---|---|
| `overhaul/src/lib/components/comercial/tabs/CustomersTab.svelte` | Replace R1 placeholder. Filters + sort + table + drilldown to CustomerProfileModal. |
| `overhaul/src/lib/components/comercial/modals/CustomerProfileModal.svelte` | Full profile: header (name + VIP badge + LTV), body 2-col (timeline left, meta sidebar right), footer 4 actions. |
| `overhaul/src/lib/components/comercial/modals/ManualOrderModal.svelte` | Form para crear orden off-platform. Multi-item con SKU picker desde `adapter.listFamilies()`. |
| `overhaul/src/lib/components/comercial/modals/CreateCustomerModal.svelte` | Form chico: name + phone + email + source. Single-row create. |

### 4.2 Modified components

| File | Change |
|---|---|
| `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte` | Retention drilldown: cambiar de `openRetention = true` (modal) a `onSwitchTab?.('customers')` callback. Eliminar import RetentionListModal. |
| `overhaul/src/lib/components/comercial/ComercialShell.svelte` | Pasar callback `onSwitchTab` a FunnelTab. Wirea `(tab) => activeTab = tab`. |
| `overhaul/src/lib/data/eventDetector.ts` | Add `detectVipInactive60d()`. Wire en runOnce alongside existing detectors. |
| `overhaul/src/lib/data/comercial.ts` | Add types: `CustomerProfile`, `OrderTimelineEntry`, `ConversationTimelineEntry`, `CreateOrderArgs`, `CreateOrderItem`, `CreateCustomerArgs`. |

### 4.3 Deleted files

- `overhaul/src/lib/components/comercial/modals/RetentionListModal.svelte` (superseded by Tab 2)

### 4.4 Adapter additions

In `overhaul/src/lib/adapter/types.ts` (Comercial R4 section):

```typescript
// ─── Comercial R4 ──────────────────────────────────────────
getCustomerProfile(customerId: number): Promise<CustomerProfile>;
createCustomer(args: CreateCustomerArgs): Promise<{ ok: boolean; customerId?: number; error?: string }>;
updateCustomerTraits(customerId: number, traitsJson: Record<string, unknown>): Promise<void>;
setCustomerBlocked(customerId: number, blocked: boolean): Promise<void>;
updateCustomerSource(customerId: number, source: string): Promise<void>;
createManualOrder(args: CreateOrderArgs): Promise<{ ok: boolean; ref?: string; saleId?: number; error?: string }>;
generateCoupon(args: { customerId: number; type: 'percent' | 'amount'; value: number; expiresInDays?: number }): Promise<{ ok: boolean; code?: string; error?: string }>;
```

`generateCoupon` calls existing worker endpoint `/api/coupons/generate` (R1 Task 17 wired the auth pattern). DASHBOARD_KEY same approach as `manychatSync.ts`.

### 4.5 New types in `comercial.ts`

```typescript
export interface CustomerProfile extends Customer {
  isVip: boolean;
  daysInactive: number | null;       // null if never ordered
  blocked: boolean;
  traitsJson: Record<string, unknown>;
  attribution: {
    customerSource: string | null;
    leadCampaigns: string[];          // unique source_campaign_id from joined leads (by phone)
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

---

## 5. Tab Customers UX

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ Customers · 21                              [+ Crear]    │
├──────────────────────────────────────────────────────────┤
│ Filtros:                                                 │
│  [✓ Solo VIP]  [Origen: All ▼]  [Última: All ▼]         │
│  [🔍 Buscar nombre/phone/email/handle...]                │
├──────────────────────────────────────────────────────────┤
│  Sort: [LTV ▼] [Última] [Órdenes] [Primera] [Origen]     │
├──────────────────────────────────────────────────────────┤
│ ★ Raul Ibarguen      VIP       9 órd  Q3,150 LTV  19d    │
│ ★ Mariana Zapata     VIP       5 órd  Q2,000 LTV   8d    │
│ ★ Juan Zapata        VIP       4 órd  Q1,600 LTV   8d    │
│   Rodrigo Zibara              2 órd    Q800 LTV  19d    │
│   ...                                                    │
└──────────────────────────────────────────────────────────┘
```

### Filters

- **VIP toggle** (chip): when active, `is_vip = 1` filter (LTV ≥ 1500)
- **Origen dropdown**: `All` / `f&f` / `ads_meta` / `organic_wa` / `organic_ig` / `messenger` / `web` / `manual` / `otro`. Shows all distinct sources from current data + the canonical 8 above.
- **Última compra dropdown**: `All` / `<30d` / `30-60d` / `60-90d` / `+90d` / `Nunca`. Computed against `MAX(sales.occurred_at)`.
- **Search**: free-text, debounce 300ms, matches `name LIKE '%q%' OR phone LIKE '%q%' OR email LIKE '%q%'`. Case-insensitive (SQLite default).

### Sort

5 sort modes (chips like RetentionListModal): LTV (desc), última (desc), órdenes (desc), primera (asc), origen (alphabetical).

### Row visual

```
[★]  Name                   [VIP]?  N órd   Q LTV   Nd último
     phone · email · source
```

- `★` only when `isVip`
- Row hover → border accent
- Click → opens CustomerProfileModal
- Blocked customers shown in tertiary-color text (visible but de-emphasized) WHEN blocked filter toggle active. Hidden by default.

### Header actions

- **+ Crear customer** → CreateCustomerModal
- **Exportar CSV** → defer to R6 (low priority for 21 customers)

---

## 6. CustomerProfileModal UX

### Header

```
[Avatar/icon]   Raul Ibarguen   ★ VIP                    ✕
                Q3,150 LTV · 9 órdenes · llegó por f&f · últ 2026-04-07
```

- Avatar = icon (Users from lucide) in green-accent box if VIP, gray box if regular
- VIP star badge only if isVip
- Subtitle: LTV + count + source + last order date
- Block badge if `blocked === true`: red `● BLOCKED` pill

### Body (2-col grid `[1fr_280px]`)

**Left — Timeline:**
```
TIMELINE · 14 entries

[order]   CE-A1B2 · Q450 · paid          2026-04-07
          1 item: Argentina Home L

[order]   CE-CD3E · Q800 · paid          2026-03-15
          2 items: Real Madrid Away M, Brazil Away L

[conv]    conv-2026-03-14-elclub-... · WA · sale  2026-03-14
          12 mensajes
```

Timeline = orders + conversations merged by date DESC. Each entry kind-tagged with color:
- `[order]` — green left-border
- `[conv]` — amber left-border

Click an order → opens existing `OrderDetailModal` (R1).
Click a conv → opens existing `ConversationThreadModal` (R2-combo, with lazy fetch).

**Right — Meta sidebar:**

```
INFO
  Phone     +502...
  Email     ...@gmail.com
  First     2026-01-12
  Last      2026-04-07
  Active    19d ago

ATTRIBUTION
  Source    f&f                   [editar]
  Lead camp:  MSG-MYSTERY-A  ·  MSG-FOLLOW-B

TRAITS                            [editar]
  { vip_tier: "core",
    referrer: "rodrigo" }

STATUS
  Active                          [bloquear]
```

- Each section has small `text-display` header (terminal style)
- Source has `[editar]` inline → opens prompt or inline edit
- Traits has `[editar]` → opens textarea sub-modal with JSON editor + validation
- Status has `[bloquear]` toggle button. If blocked: shows `[desbloquear]` instead

### Footer (4 action buttons + Cerrar)

```
[+ Orden manual]  [🎫 Cupón]  [✏ Traits]  [🚫 Bloquear]                [Cerrar]
```

- **+ Orden manual** → opens ManualOrderModal (modal-on-modal, z-index higher)
- **🎫 Cupón** → opens small inline form (type/value/expires) → POST worker → toast
- **✏ Traits** → opens JSON editor sub-modal
- **🚫 Bloquear / 🟢 Desbloquear** → confirms dialog → adapter call → refresh

---

## 7. ManualOrderModal UX

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ Crear orden manual · cliente Raul Ibarguen           ✕ │
├─────────────────────────────────────────────────────────┤
│ ITEMS · 2                          [+ Agregar item]     │
│                                                         │
│ ┌─────────────────────────────────┐  TOTALES             │
│ │ Team:     Argentina ▼           │  Subtotal: Q800      │
│ │ Jersey:   Home 24-25 ▼          │  Shipping:    Q0     │
│ │ Size:     L ▼                   │  Discount:    Q0     │
│ │ Personalizar: 10 MESSI          │  ─────────           │
│ │ Unit price: Q450  [auto-fill]   │  TOTAL:    Q800      │
│ │ Unit cost:  (opt)               │                      │
│ │                          [✕]    │  PAGO + ENTREGA      │
│ └─────────────────────────────────┘  Método: transfer ▼  │
│                                       Status: paid    ▼  │
│ ┌─────────────────────────────────┐                      │
│ │ Team:     Brazil ▼              │  Notes:              │
│ │ ...                             │  ┌─────────────┐    │
│ └─────────────────────────────────┘  │             │    │
│                                       └─────────────┘    │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                          [Cancelar]   [Registrar orden] │
└─────────────────────────────────────────────────────────┘
```

### Item row interactions

- **Team dropdown**: populated from distinct `family.team` values in catalog (`adapter.listFamilies()`)
- **Jersey dropdown**: filtered by selected team. Shows `family.season + variant_label`
- **Size dropdown**: hardcoded `S | M | L | XL | XXL` (the canonical sizes for el-club catalog)
- **Personalización**: optional text input, free-form (`"10 MESSI"`)
- **Unit price**: auto-filled from `family.modelos[i].price` when jersey selected. Editable (Diego puede dar descuento por item).
- **Unit cost**: optional. Empty = NULL in DB.
- **[✕]**: removes the row (only visible when 2+ rows exist)

### Totals computation

Reactive (`$derived`):
- `subtotal = sum(items.unitPrice)`
- `total = subtotal + shippingFee - discount`

### Validation (client + server)

**Client (before submit):**
- At least 1 item
- Each item has: team, jersey, size, unit_price > 0
- Total > 0

Server-side (bridge handler) re-validates everything.

### On submit

```
adapter.createManualOrder({
  customerId,
  items: [...],
  paymentMethod: 'transfer',
  fulfillmentStatus: 'paid',
  shippingFee: 0,
  discount: 0,
  notes: 'cliente off-platform',
})
```

→ Returns `{ok: true, ref: 'CE-XXXX', saleId: 42}` → toast → close modal → refresh CustomerProfileModal timeline.

On error: alert + keep modal open.

---

## 8. CreateCustomerModal UX

Simple. 4 fields:

```
[Crear customer manual]                          ✕
─────────────────────────────────────
Nombre*    Pedro García
Phone      +502 1234-5678
Email      pedro@gmail.com
Source     [f&f ▼]
─────────────────────────────────────
            [Cancelar]   [Crear]
```

- Only `name` required
- Source dropdown: same options as Tab Customers filter
- On submit: `adapter.createCustomer({...})` → returns `customerId` → toast + refresh Tab Customers list

---

## 9. Detector additions

Add to `eventDetector.ts`:

```typescript
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

Wire in `runOnce()` alongside existing detectors. Severity `strat` means no push WA — purely Inbox event for strategic awareness.

---

## 10. Worker integration: generate coupon

**No new endpoint needed** — existing endpoint at ventus-backoffice (or the el-club worker, whichever has coupons): `POST /api/coupons/generate`.

**R1 Task 17 already wired DASHBOARD_KEY pattern.** R4 reuses it.

The bridge does NOT call the coupon endpoint directly. Instead, the Svelte modal handler calls the Tauri command `comercial_generate_coupon` which calls the bridge handler `cmd_generate_coupon` which makes the HTTP call (with `User-Agent: ElClub-ERP/0.1.30` to avoid Cloudflare 1010, lesson learned from R2-combo Task 6 fix).

Coupon endpoint expected response: `{ok: true, code: 'CE-2026-XYZ123'}`.

If the coupon system requires customer details, the bridge passes them. If the worker system requires `COUPON_API_KEY` instead of `DASHBOARD_KEY`, adjust.

**Investigation step** before implementation: confirm exact endpoint, auth, request shape. Add to plan as Task 0 (pre-flight worker contract check).

---

## 11. Errors

### Block customer

- DB integrity: `blocked` column has DEFAULT 0, NOT NULL. ALTER TABLE migration with try/except for re-run safety.
- Filter behavior: `WHERE blocked = 0` is the default. Toggle "show blocked" adds `OR blocked = 1` (or removes the filter entirely).

### Manual order creation

- Ref collision: 5 retries (random `[A-Z0-9]^4` = 1.6M space — collision practically impossible at 21 customers + 49 sales).
- Item validation failure: bridge returns `{ok: false, error: '...'}` with specific reason. Modal shows alert, keeps form open.
- Customer not found: `customer_id` validated server-side. Returns error.

### Generate coupon

- Worker 401: token issue. Same pattern as R1 — surface error in toast.
- Worker 5xx: caught, generic error message.
- Worker offline: timeout 15s, error message "Worker no responde — intentá de nuevo".

### Edit traits

- JSON parse error client-side: validate before submit, show `Invalid JSON` warning.
- Bridge accepts string (re-parses to validate, stores as raw text).

---

## 12. Testing & verification

Same pattern as R1/R2:
1. `npm run check` (svelte-check + tsc) → 0 errors
2. `cargo check` for Rust → 0 errors
3. Bridge smoke test for each new handler
4. Manual smoke at the end (Diego instala MSI v0.1.30, prueba el flow completo)

---

## 13. Releases

R4 ships as ONE release. Tag: `v0.1.30`. Estimated time: ~3 days.

Compared to spec original (3 días), R4 lite is right-sized — same time, lighter scope (no `sales_attribution` table) gives room for ManualOrderModal full design.

---

## 14. Decisions log

13 decisions taken without back-and-forth (Diego pre-authorized):

| # | Decision | Rationale |
|---|---|---|
| 1 | Atribución mínima (A) — no `sales_attribution` table | 19/21 customers son f&f, multi-touch is overkill |
| 2 | 4 acciones del CustomerProfileModal en R4 | All 4 ship: cupón, traits, bloquear, crear orden manual |
| 3 | RetentionListModal eliminado, Funnel Retention navega a Tab 2 | Single canonical view of customers list |
| 4 | VIP computed on-the-fly (no `is_vip` column) | LTV ≥ 1500 derived from sales totals. Threshold hardcoded `1500` constant. |
| 5 | 4 filtros: VIP, origen, última, búsqueda | All 4 ship. Tag/traits filter deferred to R6. |
| 6 | Detector "VIP inactivos +60d" ships infra | severity `strat`. Will not fire today (no VIP inactive yet) but ready. |
| 7 | Edit traits = textarea JSON raw | Simple. R6 polish to chips if friction. |
| 8 | Bloquear = `ALTER TABLE customers ADD COLUMN blocked` | Default filter excludes blocked. Toggle to show. |
| 9 | Timeline = orders + conversations chronological | Notas privadas deferred. |
| 10 | "+ Crear customer manual" en header Tab Customers | Form chico (name + phone + email + source). Required for "create order to non-existent customer" flow. |
| 11 | Atribución display = `customers.source` + lead lookup | Editable manually from profile. |
| 12 | Modal layout 2-col (timeline left + meta sidebar right) | Matches BaseModal pattern from R1 OrderDetail / ConversationThread. |
| 13 | ManualOrderModal design (item rows, defaults transfer/paid, ref auto-gen) | Off-platform sales need a clean path. SKU picker from `adapter.listFamilies()`. |

---

## 15. Self-review

- ✅ Scope: focused on Customers + 4 actions. No drift into ads/settings.
- ✅ All 13 decisions documented and reflected in components/data/etc.
- ✅ Schema: 1 minimal additive migration (`blocked` column).
- ✅ Reuses R1/R2 patterns: BaseModal, detector loop, optional-chaining adapter, struct args wrap, User-Agent for HTTP, snake_case Rust names.
- ✅ Defers cleanly: notas (R5), bulk import (R6), refunds (R6), tag chips (R6).
- ✅ Errors handled at every layer.
- ✅ Pragmatic note: Diego's "decidí tú" mandate respected — no back-and-forth on details.
- ✅ One ambiguity flagged for plan: coupon endpoint contract (worker side) needs confirmation before implementation. Plan Task 0 = pre-flight check.
- ✅ No "TBD" or "TODO" placeholders.
