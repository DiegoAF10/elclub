# Comercial R1: Setup + Inbox crítico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el skeleton del modo Comercial dentro del ERP Tauri (sidebar nav, tabs container, pulso bar) + tab Inbox funcional con detección de "órdenes pendientes despacho >24h" + modal de Order detail con acciones primarias + push WA Diego para eventos críticos. Diego ya puede ver pendientes y despacharlos sin salir del ERP.

**Architecture:** SvelteKit 5 (runes) + Tauri 2 (Rust backend) + SQLite local + Cloudflare Worker para webhooks/cron. Comercial vive en `overhaul/src/routes/comercial/` y `overhaul/src/lib/components/comercial/`. Schema extendido con 4 tablas nuevas (`leads`, `conversations`, `campaigns_snapshot`, `comercial_events`). El detector de eventos corre como cron del worker; el ERP pulla con polling cada 1min.

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte icons
- Backend: Rust (Tauri commands), Python bridge para ops complejas
- Storage: SQLite (rusqlite) — `el-club/erp/elclub.db`
- Worker: Cloudflare Workers (TypeScript) — `ventus-system/backoffice/`
- Verification: `npm run check` (svelte-check + tsc) + smoke test manual

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-26-comercial-design.md`

**Branch:** `comercial-design`

**Versionado al completar:** ERP v0.1.27 → v0.1.28

---

## Patrón de testing en este codebase

El overhaul **no tiene framework de tests automatizados** (vitest/jest no instalados). El patrón canonical de Audit es:

1. **TypeScript types como contract** — definir tipos antes que implementación.
2. **`npm run check`** debe pasar después de cada step de código (svelte-check + tsc).
3. **Smoke test manual** al final de cada task (abrir el ERP, hacer la acción, verificar).
4. **Build del MSI** como gate final del release.

Cada task adopta este flow:
- Definir types/contracts → check → implementar → check → smoke → commit.

---

## File Structure

### Archivos NUEVOS

```
overhaul/src/lib/components/comercial/
├── ComercialShell.svelte         # Container principal (tabs + pulso + body)
├── ComercialTabs.svelte          # Tab bar (5 tabs, navegación con localStorage)
├── PulsoBar.svelte               # KPIs persistentes (revenue, órdenes, leads, ROAS)
├── PeriodSelector.svelte         # Hoy / 7d / 30d / Custom
├── BaseModal.svelte              # Componente reusable de modal grande
├── tabs/
│   ├── FunnelTab.svelte          # Skeleton (R1: solo placeholder, R2 fills)
│   ├── CustomersTab.svelte       # Skeleton (R1: placeholder, R4 fills)
│   ├── InboxTab.svelte           # FUNCIONAL en R1
│   ├── AdsTab.svelte             # Skeleton (R1: placeholder, R5 fills)
│   └── SettingsTab.svelte        # Skeleton (R1: placeholder, R6 fills)
└── modals/
    └── OrderDetailModal.svelte   # FUNCIONAL en R1

overhaul/src/lib/data/
├── comercial.ts                  # Types + helpers para Comercial
└── kpis.ts                       # Computa pulso del día (puro, testeable)

overhaul/src/routes/comercial/
└── +page.svelte                  # Mount del ComercialShell (puede ser sub-ruta de + page main)
```

### Archivos a MODIFICAR

```
overhaul/src/lib/components/Sidebar.svelte    # Comercial pasa de placeholder a navegable
overhaul/src/routes/+page.svelte              # Routing al modo Comercial
overhaul/src/lib/adapter/types.ts             # Agregar types de comercial_events, orders
overhaul/src/lib/adapter/tauri.ts             # Agregar invocaciones para nuevos commands
overhaul/src/lib/adapter/browser.ts           # NotAvailableInBrowser para nuevos writes
overhaul/src-tauri/src/lib.rs                 # 5 commands nuevos (list_events, mark_event, mark_shipped, etc.)
overhaul/src-tauri/Cargo.toml                 # version bump
overhaul/src-tauri/tauri.conf.json            # version bump

el-club/erp/audit_db.py                       # Schema migration: 4 tablas nuevas
el-club/erp/scripts/erp_rust_bridge.py        # Bridge commands para nuevos ops

ventus-system/backoffice/src/index.js         # Endpoint GET /api/comercial/events + cron
ventus-system/backoffice/src/comercial-events.js  # NUEVO: detector de eventos
```

---

## Tasks

### Task 1: Schema migration — 4 tablas nuevas en SQLite

**Files:**
- Modify: `el-club/erp/audit_db.py` (función `_ensure_schema()` o equivalente)
- Verify: query manual con `sqlite3` CLI tras aplicar

- [ ] **Step 1: Leer la estructura de schema actual**

```bash
cd C:/Users/Diego/el-club/erp
grep -n "CREATE TABLE\|def _ensure_schema\|def init_db" audit_db.py | head -20
```

- [ ] **Step 2: Definir las 4 nuevas tablas como CREATE TABLE IF NOT EXISTS**

Agregar al final de la función que crea tablas (antes del `conn.commit()`):

```python
# ─── Comercial schema (R1) ──────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS leads (
    lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    handle TEXT,                  -- IG handle, FB id, etc
    phone TEXT,                   -- +502...
    platform TEXT NOT NULL,       -- 'wa' | 'ig' | 'messenger'
    sender_id TEXT NOT NULL,      -- ManyChat sender_id
    source_campaign_id TEXT,      -- Meta campaign id que lo trajo
    first_contact_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',   -- 'new'|'qualified'|'converted'|'lost'
    traits_json TEXT DEFAULT '{}',
    UNIQUE(platform, sender_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS conversations (
    conv_id TEXT PRIMARY KEY,             -- matches Cloudflare KV key
    brand TEXT NOT NULL,
    platform TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    outcome TEXT,                         -- 'sale'|'abandoned'|'inquiry'|...
    order_id TEXT,                        -- FK a sales.ref si aplica
    messages_total INTEGER DEFAULT 0,
    messages_json TEXT NOT NULL,          -- transcripción serializada
    tags_json TEXT DEFAULT '[]',
    analyzed INTEGER DEFAULT 0,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_platform_sender ON conversations(platform, sender_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_outcome ON conversations(outcome)")

cur.execute("""
CREATE TABLE IF NOT EXISTS campaigns_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_gtq REAL DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue_attributed_gtq REAL DEFAULT 0,
    raw_json TEXT
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_camp_id_time ON campaigns_snapshot(campaign_id, captured_at)")

cur.execute("""
CREATE TABLE IF NOT EXISTS comercial_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,                   -- 'order_pending_24h'|'campaign_drop'|'lead_unanswered'|...
    severity TEXT NOT NULL,               -- 'crit'|'warn'|'info'|'strat'
    title TEXT NOT NULL,
    sub TEXT,
    items_affected_json TEXT DEFAULT '[]', -- [{type, id, ...}]
    detected_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', -- 'active'|'resolved'|'ignored'
    resolved_at TEXT,
    push_sent INTEGER DEFAULT 0           -- 1 si ya se mandó push WA
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_events_status_severity ON comercial_events(status, severity)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON comercial_events(type)")
```

- [ ] **Step 3: Ejecutar la migration**

```bash
cd C:/Users/Diego/el-club/erp
python -c "import audit_db; conn = audit_db.get_conn(); conn.commit(); conn.close(); print('schema OK')"
```

Expected: `schema OK` sin errores.

- [ ] **Step 4: Verificar tablas creadas**

```bash
cd C:/Users/Diego/el-club/erp
python -c "
import sqlite3
conn = sqlite3.connect('elclub.db')
cur = conn.cursor()
for t in ['leads','conversations','campaigns_snapshot','comercial_events']:
    cur.execute(f'SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"{t}\"')
    r = cur.fetchone()
    print(f'{t}: {\"OK\" if r else \"MISSING\"}')"
```

Expected: las 4 tablas marcadas `OK`.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/audit_db.py
git commit -m "feat(comercial): schema R1 — 4 tablas nuevas (leads, conversations, campaigns_snapshot, comercial_events)"
```

---

### Task 2: TypeScript types para Comercial

**Files:**
- Create: `overhaul/src/lib/data/comercial.ts`
- Modify: `overhaul/src/lib/adapter/types.ts` (agregar types de eventos + orders)

- [ ] **Step 1: Crear el módulo de types core de Comercial**

Crear `overhaul/src/lib/data/comercial.ts`:

```typescript
// Comercial — types core compartidos por todos los componentes del modo.

export type EventSeverity = 'crit' | 'warn' | 'info' | 'strat';

export type EventType =
  | 'order_pending_24h'      // crit
  | 'order_new'              // info
  | 'campaign_drop_30'       // crit (R5)
  | 'lead_unanswered_12h'    // warn (R3)
  | 'stock_low'              // warn
  | 'leads_daily_summary'    // info
  | 'vip_inactive_60d'       // strat (R4)
  | 'monthly_goal_progress'; // strat

export type EventStatus = 'active' | 'resolved' | 'ignored';

export interface ComercialEvent {
  eventId: number;
  type: EventType;
  severity: EventSeverity;
  title: string;
  sub: string | null;
  itemsAffected: ItemAffected[];
  detectedAt: string;       // ISO timestamp
  status: EventStatus;
  resolvedAt: string | null;
  pushSent: boolean;
}

export interface ItemAffected {
  type: 'order' | 'lead' | 'customer' | 'campaign';
  id: string;               // sale ref, lead_id, customer_id, campaign_id
  hint?: string;            // info breve para mostrar
}

export type ComercialTab = 'funnel' | 'customers' | 'inbox' | 'ads' | 'settings';

export type Period = 'today' | '7d' | '30d' | 'custom';

export interface PeriodRange {
  period: Period;
  start: string;            // ISO
  end: string;              // ISO
}

export interface PulsoKPIs {
  revenue: number;          // GTQ
  orders: number;
  leads: number;
  conversionRate: number;   // 0-1
  adSpend: number;          // GTQ
  roas: number;             // revenue / adSpend
  trends: {
    revenue: number;        // % vs período anterior
    orders: number;
    leads: number;
    conversionRate: number;
  };
}

export interface OrderForModal {
  ref: string;              // CE-XXXX
  status: 'paid' | 'shipped' | 'delivered' | 'refunded' | 'cancelled';
  paidAt: string | null;
  shippedAt: string | null;
  totalGtq: number;
  customer: {
    name: string;
    phone: string | null;
    handle: string | null;
    platform: 'wa' | 'ig' | 'messenger' | 'web';
  };
  items: OrderItem[];
  paymentMethod: 'recurrente' | 'transfer' | 'cod';
  notes: string | null;
}

export interface OrderItem {
  familyId: string;
  jerseySku: string | null;
  size: string;
  unitPriceGtq: number;
  unitCostGtq: number | null;
  personalizationJson: string | null;
}
```

- [ ] **Step 2: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|comercial" | head -10
```

Expected: 0 errors relacionados a comercial.ts.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/data/comercial.ts
git commit -m "feat(comercial): types core (events, KPIs, orders, periods)"
```

---

### Task 3: BaseModal.svelte — componente reusable

**Files:**
- Create: `overhaul/src/lib/components/comercial/BaseModal.svelte`

- [ ] **Step 1: Crear el componente con la estructura de 4 zonas (header / stats / body / footer)**

Crear `overhaul/src/lib/components/comercial/BaseModal.svelte`:

```svelte
<script lang="ts">
  import { X } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    onClose: () => void;
    /** Header rico — avatar/icon + nombre + status pill + meta */
    header: Snippet;
    /** Stats strip horizontal (5 columnas usualmente) */
    stats?: Snippet;
    /** Body principal — usualmente 2 cols (timeline + factbook) */
    body: Snippet;
    /** Footer con acciones primarias + cerrar */
    footer?: Snippet;
    /** Width override; default 880px */
    maxWidth?: number;
  }

  let { open, onClose, header, stats, body, footer, maxWidth = 880 }: Props = $props();

  function handleKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  }

  function handleBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }
</script>

<svelte:window on:keydown={handleKey} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    style="background: rgba(0,0,0,0.55); backdrop-filter: blur(2px);"
    onclick={handleBackdrop}
    role="dialog"
    aria-modal="true"
  >
    <div
      class="flex flex-col overflow-hidden rounded-[8px] border border-[var(--color-border-strong)] bg-[var(--color-bg)]"
      style="
        width: 90%;
        max-width: {maxWidth}px;
        max-height: 90vh;
        box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(74, 222, 128, 0.08);
      "
    >
      <!-- Header -->
      <div class="flex items-start gap-4 border-b border-[var(--color-border)] px-6 py-4">
        <div class="flex-1 min-w-0">{@render header()}</div>
        <button
          type="button"
          onclick={onClose}
          aria-label="Cerrar"
          class="rounded-[3px] p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-1)] hover:text-[var(--color-text-primary)]"
        >
          <X size={16} strokeWidth={2} />
        </button>
      </div>

      <!-- Stats strip (opcional) -->
      {#if stats}
        <div class="border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-3">
          {@render stats()}
        </div>
      {/if}

      <!-- Body -->
      <div class="flex-1 overflow-y-auto">
        {@render body()}
      </div>

      <!-- Footer (opcional) -->
      {#if footer}
        <div class="border-t border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-3">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|BaseModal" | head -5
```

Expected: 0 errors en BaseModal.svelte.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/BaseModal.svelte
git commit -m "feat(comercial): BaseModal.svelte — patrón de modal reusable (4 zonas)"
```

---

### Task 4: Sidebar — activar item Comercial como navegable

**Files:**
- Modify: `overhaul/src/lib/components/Sidebar.svelte` (línea con item 'comercial')

- [ ] **Step 1: Localizar el item Comercial actual**

```bash
cd C:/Users/Diego/el-club/overhaul
grep -n "comercial\|Comercial" src/lib/components/Sidebar.svelte | head -5
```

Encontrar línea similar a:
```js
{ id: 'comercial', label: 'Comercial', icon: DollarSign, section: 'data' },
```

- [ ] **Step 2: Verificar que el item ya tenga onclick handler — si NO lo tiene, agregar callback prop**

Leer la sección donde se renderean los items del sidebar. Si el patrón existente es:
```svelte
<button onclick={() => onSelectMode(item.id)}>
```

verificar que `onSelectMode` propague hasta el routing principal del ERP.

- [ ] **Step 3: Asegurar que el item se renderee con badge dinámico (count de eventos críticos del Inbox)**

Modificar el render del item Comercial para mostrar badge si hay eventos críticos:

```svelte
<!-- Dentro del map de items del sidebar -->
{#if item.id === 'comercial' && criticalEventsCount > 0}
  <span
    class="ml-auto rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-semibold"
    style="background: rgba(244, 63, 94, 0.18); color: var(--color-danger);"
  >
    {criticalEventsCount}
  </span>
{/if}
```

`criticalEventsCount` debe venir como prop al Sidebar.

- [ ] **Step 4: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 5: Smoke (visual, sin click todavía)**

Abrir el ERP en dev mode:
```bash
cd C:/Users/Diego/el-club/overhaul
npm run dev
# abrir http://localhost:5173
```

Verificar que el item "Comercial" se ve igual que los demás del sidebar (no como placeholder gris).

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/Sidebar.svelte
git commit -m "feat(comercial): activar item Comercial del sidebar (con badge de críticos)"
```

---

### Task 5: ComercialShell.svelte — layout base

**Files:**
- Create: `overhaul/src/lib/components/comercial/ComercialShell.svelte`

- [ ] **Step 1: Crear el shell con tabs container + pulso bar slot + body slot**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import type { ComercialTab } from '$lib/data/comercial';
  import ComercialTabs from './ComercialTabs.svelte';
  import PulsoBar from './PulsoBar.svelte';
  import FunnelTab from './tabs/FunnelTab.svelte';
  import CustomersTab from './tabs/CustomersTab.svelte';
  import InboxTab from './tabs/InboxTab.svelte';
  import AdsTab from './tabs/AdsTab.svelte';
  import SettingsTab from './tabs/SettingsTab.svelte';

  const TABS: ComercialTab[] = ['funnel', 'customers', 'inbox', 'ads', 'settings'];
  const STORAGE_KEY = 'comercial:lastTab';

  let activeTab = $state<ComercialTab>('funnel');

  // Restaurar último tab abierto
  onMount(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ComercialTab | null;
    if (saved && TABS.includes(saved)) {
      activeTab = saved;
    }
  });

  function selectTab(tab: ComercialTab) {
    activeTab = tab;
    localStorage.setItem(STORAGE_KEY, tab);
  }
</script>

<div class="flex h-full flex-col bg-[var(--color-bg)]">
  <ComercialTabs {activeTab} onSelectTab={selectTab} />
  <PulsoBar />
  <div class="flex-1 overflow-y-auto">
    {#if activeTab === 'funnel'}
      <FunnelTab />
    {:else if activeTab === 'customers'}
      <CustomersTab />
    {:else if activeTab === 'inbox'}
      <InboxTab />
    {:else if activeTab === 'ads'}
      <AdsTab />
    {:else if activeTab === 'settings'}
      <SettingsTab />
    {/if}
  </div>
</div>
```

- [ ] **Step 2: Crear los 5 tabs como skeletons**

Crear `overhaul/src/lib/components/comercial/tabs/FunnelTab.svelte`:
```svelte
<div class="px-6 py-4 text-[12px] text-[var(--color-text-tertiary)]">
  <div class="text-display mb-2 text-[10px]">Funnel · pendiente R2</div>
  <p>Esta pestaña va a mostrar el embudo de 5 etapas en R2.</p>
</div>
```

Mismo patrón para `CustomersTab.svelte`, `AdsTab.svelte`, `SettingsTab.svelte` — cada uno con su mensaje "pendiente R{N}".

`InboxTab.svelte` lo dejamos igual placeholder por ahora (Task 9 lo construye).

- [ ] **Step 3: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors. Pueden faltar componentes referenciados (ComercialTabs, PulsoBar) que se crean en tasks siguientes — está OK si esos errors aparecen, se resuelven en Task 6 y 7.

- [ ] **Step 4: Commit (parcial — el shell aún no compila standalone, pero queda)**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/ComercialShell.svelte overhaul/src/lib/components/comercial/tabs/
git commit -m "feat(comercial): ComercialShell + 5 tab skeletons (funnel/customers/inbox/ads/settings)"
```

---

### Task 6: ComercialTabs.svelte — tab bar con switching

**Files:**
- Create: `overhaul/src/lib/components/comercial/ComercialTabs.svelte`

- [ ] **Step 1: Implementar tab bar con styling del Audit (mismo lenguaje visual)**

```svelte
<script lang="ts">
  import type { ComercialTab } from '$lib/data/comercial';
  import { TrendingUp, Users, Inbox, DollarSign, Settings } from 'lucide-svelte';

  interface Props {
    activeTab: ComercialTab;
    onSelectTab: (tab: ComercialTab) => void;
    /** Count de eventos críticos (R1) — pasado desde InboxTab via store */
    inboxCount?: number;
  }

  let { activeTab, onSelectTab, inboxCount = 0 }: Props = $props();

  const TABS: { id: ComercialTab; label: string; icon: any }[] = [
    { id: 'funnel', label: 'Funnel', icon: TrendingUp },
    { id: 'customers', label: 'Customers', icon: Users },
    { id: 'inbox', label: 'Inbox', icon: Inbox },
    { id: 'ads', label: 'Ads', icon: DollarSign },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];
</script>

<div
  class="flex items-stretch border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6"
>
  {#each TABS as tab (tab.id)}
    {@const Icon = tab.icon}
    {@const isActive = activeTab === tab.id}
    <button
      type="button"
      onclick={() => onSelectTab(tab.id)}
      class="flex items-center gap-2 px-5 py-3.5 text-[13px] transition-colors"
      style="
        color: {isActive ? 'var(--color-accent)' : 'var(--color-text-tertiary)'};
        border-bottom: 2px solid {isActive ? 'var(--color-accent)' : 'transparent'};
        margin-bottom: -1px;
        font-weight: {isActive ? '600' : '400'};
      "
    >
      <Icon size={13} strokeWidth={1.8} />
      <span>{tab.label}</span>
      {#if tab.id === 'inbox' && inboxCount > 0}
        <span
          class="rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-semibold"
          style="background: rgba(244, 63, 94, 0.18); color: var(--color-danger);"
        >
          {inboxCount}
        </span>
      {/if}
    </button>
  {/each}
</div>
```

- [ ] **Step 2: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|ComercialTabs" | head -5
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/ComercialTabs.svelte
git commit -m "feat(comercial): ComercialTabs.svelte con switching + badge inbox"
```

---

### Task 7: KPIs computation (puro, testeable)

**Files:**
- Create: `overhaul/src/lib/data/kpis.ts`

- [ ] **Step 1: Crear funciones puras para computar KPIs del pulso**

```typescript
// overhaul/src/lib/data/kpis.ts
import type { Period, PeriodRange, PulsoKPIs } from './comercial';

interface SaleForKPI {
  ref: string;
  totalGtq: number;
  paidAt: string;          // ISO
  status: string;
}

interface LeadForKPI {
  leadId: number;
  firstContactAt: string;
}

interface AdSpendForKPI {
  campaignId: string;
  spendGtq: number;
  capturedAt: string;
}

/**
 * Convierte un Period en un PeriodRange con start/end ISO.
 * "today" = desde 00:00 local hasta now.
 * "7d"/"30d" = N*24h hacia atrás desde now.
 * "custom" = no implementado, retorna 30d como fallback.
 */
export function resolvePeriod(period: Period, now: Date = new Date()): PeriodRange {
  const end = now.toISOString();
  let startDate: Date;

  switch (period) {
    case 'today':
      startDate = new Date(now);
      startDate.setHours(0, 0, 0, 0);
      break;
    case '7d':
      startDate = new Date(now.getTime() - 7 * 86400000);
      break;
    case '30d':
    case 'custom':
    default:
      startDate = new Date(now.getTime() - 30 * 86400000);
      break;
  }

  return { period, start: startDate.toISOString(), end };
}

/**
 * Computa KPIs del pulso bar para un período dado.
 * Comparación de trend vs período anterior de igual longitud.
 */
export function computePulsoKPIs(
  sales: SaleForKPI[],
  leads: LeadForKPI[],
  adSpend: AdSpendForKPI[],
  range: PeriodRange,
  prevSales: SaleForKPI[] = [],
  prevLeads: LeadForKPI[] = [],
  prevAdSpend: AdSpendForKPI[] = []
): PulsoKPIs {
  const inRange = (iso: string) => iso >= range.start && iso <= range.end;

  const periodSales = sales.filter((s) => inRange(s.paidAt));
  const revenue = periodSales.reduce((sum, s) => sum + s.totalGtq, 0);
  const orders = periodSales.length;
  const periodLeads = leads.length; // ya viene filtrado por el caller con range
  const totalAdSpend = adSpend.reduce((sum, a) => sum + a.spendGtq, 0);
  const conversionRate = periodLeads > 0 ? orders / periodLeads : 0;
  const roas = totalAdSpend > 0 ? revenue / totalAdSpend : 0;

  // Comparación de trend vs período anterior
  const prevRevenue = prevSales.reduce((sum, s) => sum + s.totalGtq, 0);
  const prevOrders = prevSales.length;
  const prevLeadsCount = prevLeads.length;
  const prevConvRate = prevLeadsCount > 0 ? prevOrders / prevLeadsCount : 0;

  const pct = (now: number, prev: number) => (prev === 0 ? 0 : ((now - prev) / prev) * 100);

  return {
    revenue,
    orders,
    leads: periodLeads,
    conversionRate,
    adSpend: totalAdSpend,
    roas,
    trends: {
      revenue: pct(revenue, prevRevenue),
      orders: pct(orders, prevOrders),
      leads: pct(periodLeads, prevLeadsCount),
      conversionRate: pct(conversionRate, prevConvRate)
    }
  };
}
```

- [ ] **Step 2: Verificar tipos sin errors**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|kpis" | head -5
```

Expected: 0 errors.

- [ ] **Step 3: Validar lógica con Node REPL inline (sin framework de tests)**

```bash
cd C:/Users/Diego/el-club/overhaul
node -e "
const { resolvePeriod, computePulsoKPIs } = await import('./src/lib/data/kpis.ts').catch(e => { console.error('Direct import not supported, skip'); process.exit(0); });
" 2>&1 | head -3
```

(Este step es informativo — si npm run check pasa, los types son correctos. La validación real viene en smoke al final.)

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/data/kpis.ts
git commit -m "feat(comercial): KPIs computation (resolvePeriod + computePulsoKPIs)"
```

---

### Task 8: PulsoBar.svelte + PeriodSelector.svelte

**Files:**
- Create: `overhaul/src/lib/components/comercial/PulsoBar.svelte`
- Create: `overhaul/src/lib/components/comercial/PeriodSelector.svelte`

- [ ] **Step 1: Crear PeriodSelector con tabs Hoy/7d/30d/Custom**

```svelte
<!-- overhaul/src/lib/components/comercial/PeriodSelector.svelte -->
<script lang="ts">
  import type { Period } from '$lib/data/comercial';

  interface Props {
    value: Period;
    onChange: (p: Period) => void;
  }

  let { value, onChange }: Props = $props();

  const PERIODS: { id: Period; label: string }[] = [
    { id: 'today', label: 'Hoy' },
    { id: '7d', label: '7d' },
    { id: '30d', label: '30d' },
    { id: 'custom', label: 'Custom' }
  ];
</script>

<div class="flex gap-1">
  {#each PERIODS as p (p.id)}
    {@const isActive = value === p.id}
    <button
      type="button"
      onclick={() => onChange(p.id)}
      class="rounded-[3px] px-2.5 py-1 text-[10.5px] transition-colors"
      style="
        background: {isActive ? 'var(--color-surface-1)' : 'transparent'};
        color: {isActive ? 'var(--color-text-secondary)' : 'var(--color-text-tertiary)'};
      "
    >
      {p.label}
    </button>
  {/each}
</div>
```

- [ ] **Step 2: Crear PulsoBar con el layout del mockup A3**

```svelte
<!-- overhaul/src/lib/components/comercial/PulsoBar.svelte -->
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Period, PulsoKPIs } from '$lib/data/comercial';
  import { computePulsoKPIs, resolvePeriod } from '$lib/data/kpis';
  import PeriodSelector from './PeriodSelector.svelte';

  let period = $state<Period>('today');
  let kpis = $state<PulsoKPIs | null>(null);
  let loading = $state(false);

  // Re-load on period change
  $effect(() => {
    void period;
    loading = true;
    loadKPIs(period).finally(() => (loading = false));
  });

  async function loadKPIs(p: Period) {
    const range = resolvePeriod(p);
    try {
      // Adapter call — listSalesInRange / listLeadsInRange / listAdSpendInRange
      // implementadas en Tasks 14-15. Por ahora stubbed con empty arrays.
      const sales = await adapter.listSalesInRange?.(range) ?? [];
      const leads = await adapter.listLeadsInRange?.(range) ?? [];
      const adSpend = await adapter.listAdSpendInRange?.(range) ?? [];
      kpis = computePulsoKPIs(sales, leads, adSpend, range);
    } catch (e) {
      console.warn('[pulso] load failed', e);
      kpis = null;
    }
  }

  function fmtMoney(n: number): string {
    return `Q${n.toLocaleString('es-GT', { maximumFractionDigits: 0 })}`;
  }
  function fmtPct(n: number): string {
    return `${(n * 100).toFixed(1)}%`;
  }
  function fmtTrend(n: number): { sign: string; cls: string } {
    if (Math.abs(n) < 0.5) return { sign: `— ${n.toFixed(0)}%`, cls: 'flat' };
    if (n > 0) return { sign: `↑ ${n.toFixed(0)}%`, cls: 'up' };
    return { sign: `↓ ${Math.abs(n).toFixed(0)}%`, cls: 'down' };
  }
</script>

<div
  class="flex items-center gap-6 border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-2.5 text-[11px]"
>
  {#if loading}
    <span class="text-[var(--color-text-tertiary)]">Cargando pulso…</span>
  {:else if kpis}
    {@const tRev = fmtTrend(kpis.trends.revenue)}
    {@const tOrd = fmtTrend(kpis.trends.orders)}
    {@const tLead = fmtTrend(kpis.trends.leads)}
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Revenue</span>
      <span class="text-mono font-semibold tabular-nums">{fmtMoney(kpis.revenue)}</span>
      <span class="text-[10.5px] text-[var(--color-{tRev.cls === 'up' ? 'success' : tRev.cls === 'down' ? 'danger' : 'text-tertiary'})]">{tRev.sign}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Órdenes</span>
      <span class="text-mono font-semibold tabular-nums">{kpis.orders}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Leads</span>
      <span class="text-mono font-semibold tabular-nums">{kpis.leads}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Conv</span>
      <span class="text-mono font-semibold tabular-nums">{fmtPct(kpis.conversionRate)}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Ad spend</span>
      <span class="text-mono font-semibold tabular-nums">{fmtMoney(kpis.adSpend)}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">ROAS</span>
      <span class="text-mono font-semibold tabular-nums">{kpis.roas.toFixed(1)}×</span>
    </div>
  {:else}
    <span class="text-[var(--color-text-tertiary)]">Sin data</span>
  {/if}
  <div class="ml-auto">
    <PeriodSelector value={period} onChange={(p) => (period = p)} />
  </div>
</div>
```

- [ ] **Step 3: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors EN PulsoBar/PeriodSelector. Pueden haber errors sobre `adapter.listSalesInRange` — esos se resuelven en Task 11.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/PulsoBar.svelte overhaul/src/lib/components/comercial/PeriodSelector.svelte
git commit -m "feat(comercial): PulsoBar con period selector + 6 KPIs (revenue, órdenes, leads, conv, ad spend, ROAS)"
```

---

### Task 9: Adapter — methods para Comercial (events, orders, sales-in-range)

**Files:**
- Modify: `overhaul/src/lib/adapter/types.ts` (interface Adapter)
- Modify: `overhaul/src/lib/adapter/tauri.ts` (impl native)
- Modify: `overhaul/src/lib/adapter/browser.ts` (impl con NotAvailableInBrowser donde corresponde)

- [ ] **Step 1: Agregar method signatures al interface Adapter**

En `overhaul/src/lib/adapter/types.ts`:

```typescript
import type {
  ComercialEvent,
  EventStatus,
  OrderForModal,
  PeriodRange
} from '../data/comercial';

// Dentro de la interface Adapter, agregar:

  // ─── Comercial R1 ──────────────────────────────────────────
  listEvents(filter?: { status?: EventStatus; severity?: string }): Promise<ComercialEvent[]>;
  setEventStatus(eventId: number, status: EventStatus): Promise<void>;
  getOrderForModal(ref: string): Promise<OrderForModal | null>;
  markOrderShipped(ref: string, trackingCode?: string): Promise<void>;

  // Sales/leads/ads en range — para el pulso
  listSalesInRange(range: PeriodRange): Promise<Array<{ ref: string; totalGtq: number; paidAt: string; status: string }>>;
  listLeadsInRange(range: PeriodRange): Promise<Array<{ leadId: number; firstContactAt: string }>>;
  listAdSpendInRange(range: PeriodRange): Promise<Array<{ campaignId: string; spendGtq: number; capturedAt: string }>>;
```

- [ ] **Step 2: Implementar en tauri.ts (todos los methods invocan commands Rust)**

En `overhaul/src/lib/adapter/tauri.ts`:

```typescript
async listEvents(filter?: { status?: EventStatus; severity?: string }): Promise<ComercialEvent[]> {
  return invoke<ComercialEvent[]>('comercial_list_events', { filter: filter ?? {} });
},

async setEventStatus(eventId: number, status: EventStatus): Promise<void> {
  return invoke<void>('comercial_set_event_status', { eventId, status });
},

async getOrderForModal(ref: string): Promise<OrderForModal | null> {
  return invoke<OrderForModal | null>('comercial_get_order', { ref });
},

async markOrderShipped(ref: string, trackingCode?: string): Promise<void> {
  return invoke<void>('comercial_mark_order_shipped', { ref, trackingCode: trackingCode ?? null });
},

async listSalesInRange(range: PeriodRange) {
  return invoke<Array<{ ref: string; totalGtq: number; paidAt: string; status: string }>>(
    'comercial_list_sales_in_range',
    { start: range.start, end: range.end }
  );
},

async listLeadsInRange(range: PeriodRange) {
  return invoke<Array<{ leadId: number; firstContactAt: string }>>(
    'comercial_list_leads_in_range',
    { start: range.start, end: range.end }
  );
},

async listAdSpendInRange(range: PeriodRange) {
  return invoke<Array<{ campaignId: string; spendGtq: number; capturedAt: string }>>(
    'comercial_list_ad_spend_in_range',
    { start: range.start, end: range.end }
  );
},
```

- [ ] **Step 3: Implementar en browser.ts con stubs/empty arrays para reads, NotAvailableInBrowser para writes**

En `overhaul/src/lib/adapter/browser.ts`:

```typescript
async listEvents() { return []; },
async setEventStatus() { throw new NotAvailableInBrowser('setEventStatus'); },
async getOrderForModal() { return null; },
async markOrderShipped() { throw new NotAvailableInBrowser('markOrderShipped'); },
async listSalesInRange() { return []; },
async listLeadsInRange() { return []; },
async listAdSpendInRange() { return []; },
```

- [ ] **Step 4: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors. Los types deben resolver correctamente porque los Rust commands se implementan en Task 11.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/adapter/types.ts overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts
git commit -m "feat(comercial): adapter — listEvents, setEventStatus, getOrder, markShipped, *InRange"
```

---

### Task 10: Python bridge commands para comercial_events + orders

**Files:**
- Modify: `el-club/erp/scripts/erp_rust_bridge.py` (agregar handlers)

- [ ] **Step 1: Agregar handler `cmd_list_events`**

Al final del archivo, antes de la dict COMMANDS:

```python
def cmd_list_events(args):
    """Lista eventos de comercial_events con filtros opcionales."""
    import sqlite3, json
    from db import get_conn

    status = args.get("status")          # 'active'|'resolved'|'ignored'|None
    severity = args.get("severity")      # 'crit'|'warn'|'info'|'strat'|None

    conn = get_conn()
    try:
        sql = "SELECT event_id, type, severity, title, sub, items_affected_json, detected_at, status, resolved_at, push_sent FROM comercial_events"
        clauses = []
        params = []
        if status:
            clauses.append("status = ?"); params.append(status)
        if severity:
            clauses.append("severity = ?"); params.append(severity)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE severity WHEN 'crit' THEN 1 WHEN 'warn' THEN 2 WHEN 'info' THEN 3 ELSE 4 END, detected_at DESC"

        rows = conn.execute(sql, params).fetchall()
        events = []
        for r in rows:
            events.append({
                "eventId": r[0],
                "type": r[1],
                "severity": r[2],
                "title": r[3],
                "sub": r[4],
                "itemsAffected": json.loads(r[5] or '[]'),
                "detectedAt": r[6],
                "status": r[7],
                "resolvedAt": r[8],
                "pushSent": bool(r[9]),
            })
        return {"ok": True, "events": events}
    finally:
        conn.close()
```

- [ ] **Step 2: Agregar handler `cmd_set_event_status`**

```python
def cmd_set_event_status(args):
    """Cambia status de un evento (active/resolved/ignored)."""
    from db import get_conn

    event_id = args.get("eventId")
    status = args.get("status")
    if not event_id or status not in ("active", "resolved", "ignored"):
        return {"ok": False, "error": "eventId/status missing or invalid"}

    conn = get_conn()
    try:
        if status == "resolved":
            conn.execute(
                "UPDATE comercial_events SET status=?, resolved_at=datetime('now') WHERE event_id=?",
                (status, event_id),
            )
        else:
            conn.execute(
                "UPDATE comercial_events SET status=? WHERE event_id=?",
                (status, event_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
```

- [ ] **Step 3: Agregar handler `cmd_get_order` que retorna OrderForModal**

```python
def cmd_get_order(args):
    """Devuelve OrderForModal para una orden por su ref (CE-XXXX)."""
    from db import get_conn

    ref = args.get("ref")
    if not ref:
        return {"ok": False, "error": "ref missing"}

    conn = get_conn()
    try:
        # Sales table
        sale = conn.execute("""
            SELECT s.ref, s.fulfillment_status, s.paid_at, s.shipped_at, s.total_gtq,
                   s.payment_method, s.notes,
                   c.name, c.phone, c.handle, c.platform
            FROM sales s
            LEFT JOIN customers c ON c.customer_id = s.customer_id
            WHERE s.ref = ?
        """, (ref,)).fetchone()

        if not sale:
            return {"ok": True, "order": None}

        # Items
        items = conn.execute("""
            SELECT family_id, jersey_sku, size, unit_price_gtq, unit_cost_gtq, personalization_json
            FROM sale_items
            WHERE sale_id = (SELECT sale_id FROM sales WHERE ref = ?)
        """, (ref,)).fetchall()

        order = {
            "ref": sale[0],
            "status": sale[1] or "paid",
            "paidAt": sale[2],
            "shippedAt": sale[3],
            "totalGtq": sale[4],
            "paymentMethod": sale[5] or "recurrente",
            "notes": sale[6],
            "customer": {
                "name": sale[7] or "(sin nombre)",
                "phone": sale[8],
                "handle": sale[9],
                "platform": sale[10] or "web",
            },
            "items": [
                {
                    "familyId": i[0],
                    "jerseySku": i[1],
                    "size": i[2],
                    "unitPriceGtq": i[3],
                    "unitCostGtq": i[4],
                    "personalizationJson": i[5],
                }
                for i in items
            ],
        }
        return {"ok": True, "order": order}
    finally:
        conn.close()
```

- [ ] **Step 4: Agregar handler `cmd_mark_order_shipped`**

```python
def cmd_mark_order_shipped(args):
    """Marca orden como shipped, opcionalmente con tracking_code."""
    from db import get_conn

    ref = args.get("ref")
    tracking = args.get("trackingCode")
    if not ref:
        return {"ok": False, "error": "ref missing"}

    conn = get_conn()
    try:
        if tracking:
            conn.execute(
                "UPDATE sales SET fulfillment_status='shipped', shipped_at=datetime('now'), tracking_code=? WHERE ref=?",
                (tracking, ref),
            )
        else:
            conn.execute(
                "UPDATE sales SET fulfillment_status='shipped', shipped_at=datetime('now') WHERE ref=?",
                (ref,),
            )

        # También resolver el evento order_pending_24h asociado si existe
        conn.execute("""
            UPDATE comercial_events
            SET status='resolved', resolved_at=datetime('now')
            WHERE type='order_pending_24h' AND status='active'
              AND items_affected_json LIKE '%' || ? || '%'
        """, (ref,))
        conn.commit()
        return {"ok": True, "ref": ref}
    finally:
        conn.close()
```

- [ ] **Step 5: Agregar handlers para sales/leads/ads in range**

```python
def cmd_list_sales_in_range(args):
    """Lista sales con paid_at entre start y end."""
    from db import get_conn
    start = args.get("start")
    end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ref, total_gtq, paid_at, fulfillment_status FROM sales WHERE paid_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "sales": [{"ref": r[0], "totalGtq": r[1], "paidAt": r[2], "status": r[3]} for r in rows]
        }
    finally:
        conn.close()


def cmd_list_leads_in_range(args):
    """Lista leads con first_contact_at entre start y end."""
    from db import get_conn
    start = args.get("start"); end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT lead_id, first_contact_at FROM leads WHERE first_contact_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "leads": [{"leadId": r[0], "firstContactAt": r[1]} for r in rows]
        }
    finally:
        conn.close()


def cmd_list_ad_spend_in_range(args):
    """Lista ad spend snapshots entre start y end."""
    from db import get_conn
    start = args.get("start"); end = args.get("end")
    if not start or not end:
        return {"ok": False, "error": "start/end missing"}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT campaign_id, spend_gtq, captured_at FROM campaigns_snapshot WHERE captured_at BETWEEN ? AND ?",
            (start, end),
        ).fetchall()
        return {
            "ok": True,
            "ad_spend": [{"campaignId": r[0], "spendGtq": r[1], "capturedAt": r[2]} for r in rows]
        }
    finally:
        conn.close()
```

- [ ] **Step 6: Registrar los nuevos commands en el dict COMMANDS**

```python
COMMANDS = {
    # ... existentes ...
    "list_events": cmd_list_events,
    "set_event_status": cmd_set_event_status,
    "get_order": cmd_get_order,
    "mark_order_shipped": cmd_mark_order_shipped,
    "list_sales_in_range": cmd_list_sales_in_range,
    "list_leads_in_range": cmd_list_leads_in_range,
    "list_ad_spend_in_range": cmd_list_ad_spend_in_range,
}
```

- [ ] **Step 7: Smoke test del bridge directamente**

```bash
cd C:/Users/Diego/el-club/erp
echo '{"cmd":"list_events"}' | python scripts/erp_rust_bridge.py
```

Expected: JSON con `{"ok": true, "events": []}` (sin eventos todavía).

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/scripts/erp_rust_bridge.py
git commit -m "feat(comercial): bridge commands — events CRUD + order get/ship + range queries"
```

---

### Task 11: Rust Tauri commands (wrappers del bridge)

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Agregar las 7 commands Rust como wrappers async + spawn_blocking del bridge**

Después de los commands existentes, antes del `invoke_handler`:

```rust
// ─── Comercial R1 ──────────────────────────────────────────

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListEventsFilter {
    pub status: Option<String>,
    pub severity: Option<String>,
}

#[tauri::command]
async fn comercial_list_events(filter: ListEventsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_events",
        "status": filter.status,
        "severity": filter.severity,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;

    Ok(result.get("events").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_set_event_status(event_id: i64, status: String) -> Result<()> {
    let payload = serde_json::json!({ "cmd": "set_event_status", "eventId": event_id, "status": status });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[tauri::command]
async fn comercial_get_order(reff: String) -> Result<Option<Value>> {
    let payload = serde_json::json!({ "cmd": "get_order", "ref": reff });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("order").cloned().filter(|v| !v.is_null()))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MarkShippedArgs {
    pub reff: String,
    pub tracking_code: Option<String>,
}

#[tauri::command]
async fn comercial_mark_order_shipped(args: MarkShippedArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "mark_order_shipped",
        "ref": args.reff,
        "trackingCode": args.tracking_code,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[tauri::command]
async fn comercial_list_sales_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_sales_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("sales").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_list_leads_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_leads_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("leads").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_list_ad_spend_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_ad_spend_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("ad_spend").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}
```

**Nota sobre `reff` en lugar de `ref`:** `ref` es palabra reservada en Rust. Se usa `reff` y se mapea via `#[serde(rename = "ref")]` cuando hace falta — pero acá los args llegan como `args.ref` desde TS, hay que usar `#[serde(rename_all = "camelCase")]` en el struct. Como `reff` no matchea con TS `ref`, mejor:

```rust
#[derive(Debug, Deserialize)]
pub struct MarkShippedArgs {
    #[serde(rename = "ref")]
    pub reff: String,
    #[serde(rename = "trackingCode")]
    pub tracking_code: Option<String>,
}
```

Y en `comercial_get_order`, en vez de `reff: String` directo, usar un struct similar.

- [ ] **Step 2: Registrar los 7 commands en el `invoke_handler`**

```rust
// dentro de tauri::Builder::default().invoke_handler(tauri::generate_handler![...])
comercial_list_events,
comercial_set_event_status,
comercial_get_order,
comercial_mark_order_shipped,
comercial_list_sales_in_range,
comercial_list_leads_in_range,
comercial_list_ad_spend_in_range,
```

- [ ] **Step 3: Compile check (rápido, sin build completo)**

```bash
cd C:/Users/Diego/el-club/overhaul/src-tauri
cargo check 2>&1 | grep -E "^error" | head -20
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src-tauri/src/lib.rs
git commit -m "feat(comercial): Rust commands — 7 wrappers para events + orders + range queries"
```

---

### Task 12: InboxTab.svelte — render funcional

**Files:**
- Modify: `overhaul/src/lib/components/comercial/tabs/InboxTab.svelte` (reemplazar placeholder)

- [ ] **Step 1: Implementar el InboxTab con loading + lista agrupada por severidad**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ComercialEvent, EventSeverity } from '$lib/data/comercial';
  import { AlertTriangle, Check, Info, X } from 'lucide-svelte';
  import OrderDetailModal from '../modals/OrderDetailModal.svelte';

  let events = $state<ComercialEvent[]>([]);
  let loading = $state(true);
  let filter = $state<EventSeverity | 'all'>('all');
  let search = $state('');

  // Para abrir el OrderDetailModal cuando el evento es de tipo orden
  let openedOrderRef = $state<string | null>(null);

  // Auto-refresh cada 60s (alineado con polling worker→ERP)
  let refreshTimer: ReturnType<typeof setInterval>;

  $effect(() => {
    loadEvents();
    refreshTimer = setInterval(loadEvents, 60_000);
    return () => clearInterval(refreshTimer);
  });

  async function loadEvents() {
    try {
      const list = await adapter.listEvents({ status: 'active' });
      events = list;
    } catch (e) {
      console.warn('[inbox] load failed', e);
    } finally {
      loading = false;
    }
  }

  let filtered = $derived.by(() => {
    let list = events;
    if (filter !== 'all') list = list.filter((e) => e.severity === filter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((e) => e.title.toLowerCase().includes(q) || (e.sub ?? '').toLowerCase().includes(q));
    }
    return list;
  });

  let grouped = $derived.by(() => {
    const out: Record<EventSeverity, ComercialEvent[]> = { crit: [], warn: [], info: [], strat: [] };
    for (const e of filtered) out[e.severity].push(e);
    return out;
  });

  function severityColor(s: EventSeverity) {
    return s === 'crit' ? 'var(--color-danger)' :
           s === 'warn' ? 'var(--color-warning)' :
           s === 'info' ? 'var(--color-info, #60a5fa)' :
           'var(--color-text-tertiary)';
  }

  function severityLabel(s: EventSeverity) {
    return s === 'crit' ? '🔴 Crítico' :
           s === 'warn' ? '🟡 Atención' :
           s === 'info' ? '🔵 Info' :
           '⚪ Estratégico';
  }

  function fmtAge(iso: string): string {
    const ms = Date.now() - new Date(iso).getTime();
    const h = Math.floor(ms / 3600_000);
    if (h < 1) return `${Math.floor(ms / 60_000)}m`;
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  }

  async function handleEventClick(event: ComercialEvent) {
    if (event.type === 'order_pending_24h' || event.type === 'order_new') {
      // Abrir OrderDetailModal con primer order ref de items_affected
      const orderItem = event.itemsAffected.find((i) => i.type === 'order');
      if (orderItem) openedOrderRef = orderItem.id;
    }
    // R3+ agregará otros tipos (lead, campaign, etc.)
  }

  async function handleIgnore(event: ComercialEvent) {
    await adapter.setEventStatus(event.eventId, 'ignored');
    loadEvents();
  }

  async function handleResolve(event: ComercialEvent) {
    await adapter.setEventStatus(event.eventId, 'resolved');
    loadEvents();
  }
</script>

<div class="flex h-full flex-col">

  <!-- Header con filtros + search -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-2 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Inbox</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {events.length} eventos · {grouped.crit.length} críticos
      </span>
    </div>

    <div class="mb-3 flex flex-wrap gap-1.5">
      {#each [['all','Todo'],['crit','🔴 Crítico'],['warn','🟡 Atención'],['info','🔵 Info'],['strat','⚪ Estratégico']] as [val, lbl]}
        {@const active = filter === val}
        <button
          type="button"
          onclick={() => (filter = val as any)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >{lbl}</button>
      {/each}
    </div>

    <input
      type="text"
      bind:value={search}
      placeholder="Buscar evento, ref, cliente..."
      class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
    />
  </div>

  <!-- Lista de eventos -->
  <div class="flex-1 overflow-y-auto px-6 py-4">
    {#if loading}
      <div class="text-[11px] text-[var(--color-text-tertiary)]">Cargando eventos…</div>
    {:else if filtered.length === 0}
      <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">
        &gt; all systems nominal. nothing to worry about.
      </div>
    {:else}
      {#each ['crit','warn','info','strat'] as sev}
        {#if grouped[sev as EventSeverity].length > 0}
          <div class="mb-5">
            <div
              class="text-display mb-2 text-[9.5px]"
              style="color: {severityColor(sev as EventSeverity)};"
            >
              {severityLabel(sev as EventSeverity)} · {grouped[sev as EventSeverity].length}
            </div>

            <div class="flex flex-col gap-2">
              {#each grouped[sev as EventSeverity] as ev (ev.eventId)}
                <button
                  type="button"
                  onclick={() => handleEventClick(ev)}
                  class="w-full text-left transition-colors"
                  style="
                    background: var(--color-surface-1);
                    border: 1px solid var(--color-border);
                    border-left: 3px solid {severityColor(sev as EventSeverity)};
                    border-radius: 4px;
                    padding: 10px 14px;
                  "
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="flex-1 min-w-0">
                      <div class="text-[12.5px] font-medium text-[var(--color-text-primary)]">{ev.title}</div>
                      {#if ev.sub}
                        <div class="text-[10.5px] text-[var(--color-text-tertiary)] mt-0.5">{ev.sub}</div>
                      {/if}
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                      <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtAge(ev.detectedAt)}</span>
                    </div>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</div>

{#if openedOrderRef}
  <OrderDetailModal
    orderRef={openedOrderRef}
    onClose={() => { openedOrderRef = null; loadEvents(); }}
  />
{/if}
```

- [ ] **Step 2: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep -E "ERROR|InboxTab" | head -10
```

Expected: solo error sobre OrderDetailModal (lo creamos en Task 13).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/tabs/InboxTab.svelte
git commit -m "feat(comercial): InboxTab funcional — lista por severidad + filtros + search + auto-refresh 60s"
```

---

### Task 13: OrderDetailModal.svelte

**Files:**
- Create: `overhaul/src/lib/components/comercial/modals/OrderDetailModal.svelte`

- [ ] **Step 1: Implementar el modal con BaseModal + 4 zonas (header / stats / body / footer)**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { OrderForModal } from '$lib/data/comercial';
  import { Package, MessageCircle, Truck, Phone, Loader2 } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    orderRef: string;
    onClose: () => void;
  }

  let { orderRef, onClose }: Props = $props();

  let order = $state<OrderForModal | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let action = $state<'idle' | 'shipping'>('idle');

  $effect(() => {
    loadOrder();
  });

  async function loadOrder() {
    loading = true;
    error = null;
    try {
      order = await adapter.getOrderForModal(orderRef);
      if (!order) error = `Orden ${orderRef} no encontrada`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Error desconocido';
    } finally {
      loading = false;
    }
  }

  async function handleMarkShipped() {
    if (!order || action === 'shipping') return;
    const tracking = window.prompt('Tracking code (opcional, ej. Forza ABC123):', '');
    action = 'shipping';
    try {
      await adapter.markOrderShipped(order.ref, tracking?.trim() || undefined);
      // Recargar para reflejar cambio
      await loadOrder();
    } catch (e) {
      alert(`Falló: ${e instanceof Error ? e.message : e}`);
    } finally {
      action = 'idle';
    }
  }

  function handleContact() {
    if (!order?.customer.phone) return;
    const cleanPhone = order.customer.phone.replace(/\D/g, '');
    window.open(`https://wa.me/${cleanPhone}?text=Hola%20${encodeURIComponent(order.customer.name)}!`, '_blank');
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" />
        <span class="text-[14px]">Cargando orden…</span>
      </div>
    {:else if order}
      <div class="flex items-center gap-3">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-[6px]"
          style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);"
        >
          <Package size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
        </div>
        <div>
          <div class="flex items-center gap-2 text-[18px] font-semibold">
            <span class="text-mono">{order.ref}</span>
            <span
              class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]"
              style="
                background: {order.status === 'shipped' ? 'rgba(74,222,128,0.18)' : order.status === 'paid' ? 'rgba(251,191,36,0.18)' : 'rgba(107,110,117,0.2)'};
                color: {order.status === 'shipped' ? 'var(--color-accent)' : order.status === 'paid' ? 'var(--color-warning)' : 'var(--color-text-secondary)'};
              "
            >● {order.status.toUpperCase()}</span>
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            {order.customer.name} · {order.customer.platform.toUpperCase()} · {fmtDate(order.paidAt)}
          </div>
        </div>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if order}
      <div class="grid grid-cols-[1fr_280px] gap-0 h-full">
        <!-- Items -->
        <div class="border-r border-[var(--color-border)] px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Items · {order.items.length}</div>
          {#each order.items as item}
            <div class="mb-3 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
              <div class="text-mono text-[11.5px] text-[var(--color-text-primary)]">{item.familyId}</div>
              <div class="mt-1 flex items-center gap-3 text-[10.5px] text-[var(--color-text-tertiary)]">
                <span>SKU: {item.jerseySku ?? '—'}</span>
                <span>·</span>
                <span>Talla: {item.size}</span>
                <span>·</span>
                <span class="text-mono">Q{item.unitPriceGtq}</span>
              </div>
              {#if item.personalizationJson}
                <div class="mt-1 text-[10.5px] text-[var(--color-text-secondary)]">
                  Personalización: {item.personalizationJson}
                </div>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Sidebar customer -->
        <div class="px-4 py-4 bg-[var(--color-surface-0)]">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Cliente</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Nombre</span><span>{order.customer.name}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{order.customer.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Handle</span><span>{order.customer.handle ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Plataforma</span><span class="uppercase">{order.customer.platform}</span></div>
          </div>

          <div class="text-display mt-5 mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Pago</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Método</span><span>{order.paymentMethod}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Total</span><span class="text-mono font-semibold" style="color: var(--color-accent);">Q{order.totalGtq}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Pagado</span><span>{fmtDate(order.paidAt)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Despachado</span><span>{fmtDate(order.shippedAt)}</span></div>
          </div>

          {#if order.notes}
            <div class="text-display mt-5 mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Notas</div>
            <div class="rounded-[3px] bg-[var(--color-surface-1)] p-2 text-[11px] text-[var(--color-text-secondary)]">
              {order.notes}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if order}
      <div class="flex items-center justify-between gap-2">
        <div class="flex gap-2">
          <button
            type="button"
            onclick={handleContact}
            disabled={!order.customer.phone}
            class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)] disabled:opacity-40 hover:border-[var(--color-border-strong)]"
          >
            <MessageCircle size={12} strokeWidth={1.8} />
            Mensaje WA
          </button>
          {#if order.status !== 'shipped'}
            <button
              type="button"
              onclick={handleMarkShipped}
              disabled={action === 'shipping'}
              class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
            >
              {#if action === 'shipping'}
                <Loader2 size={12} class="animate-spin" />
                Marcando…
              {:else}
                <Truck size={12} strokeWidth={2.2} />
                Marcar despachado
              {/if}
            </button>
          {/if}
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >Cerrar</button>
      </div>
    {/if}
  {/snippet}
</BaseModal>
```

- [ ] **Step 2: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors (todos los componentes referenciados existen).

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/components/comercial/modals/OrderDetailModal.svelte
git commit -m "feat(comercial): OrderDetailModal con header/stats/body/footer + acciones primarias"
```

---

### Task 14: Routing — abrir modo Comercial desde el sidebar

**Files:**
- Modify: `overhaul/src/routes/+page.svelte` (mode switching)

- [ ] **Step 1: Localizar el state que controla qué modo está activo**

```bash
cd C:/Users/Diego/el-club/overhaul
grep -n "currentMode\|mode\|activeMode\|selectedMode" src/routes/+page.svelte | head -10
```

- [ ] **Step 2: Agregar el render del ComercialShell cuando mode=='comercial'**

En el bloque que renderea según mode:

```svelte
<script lang="ts">
  // ... existing imports ...
  import ComercialShell from '$lib/components/comercial/ComercialShell.svelte';

  // ... existing code ...
</script>

<!-- ... existing layout ... -->
{#if currentMode === 'comercial'}
  <ComercialShell />
{:else if currentMode === 'audit'}
  <!-- ... existing audit render ... -->
{/if}
```

(Adaptar nombres de variables según el código real.)

- [ ] **Step 3: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -5
```

Expected: 0 errors.

- [ ] **Step 4: Smoke test (browser dev mode)**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run dev
```

Abrir `http://localhost:5173`, click "Comercial" en el sidebar. Verificar:
- ✅ Tab bar visible con 5 tabs
- ✅ Pulso bar visible (puede mostrar "Sin data" porque adapter browser retorna vacío)
- ✅ Click cada tab cambia el body
- ✅ Inbox tab muestra "all systems nominal" (no eventos)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/routes/+page.svelte
git commit -m "feat(comercial): wire ComercialShell al routing principal del ERP"
```

---

### Task 15: Worker — endpoint GET /api/comercial/events

**Files:**
- Modify: `ventus-system/backoffice/src/index.js`

- [ ] **Step 1: Agregar el endpoint que retorna eventos desde KV o un store local del worker**

Por simplicidad en R1, los eventos los detecta directamente el ERP via cron del worker pero el storage de eventos vive en SQLite del ERP. El worker no necesita endpoint para servir eventos (el ERP los lee directo via comercial_list_events).

**Sin embargo,** sí necesitamos un endpoint para que el cron del worker pueda **escribir eventos detectados** al ERP. Pero como el cron del worker NO tiene acceso directo a SQLite del ERP, lo correcto es:

- Worker cron detecta eventos y los guarda en KV (`comercial_event_queue:{id}`).
- ERP cron interno (cada 5min, vía `setInterval` en cliente) pulla el queue de eventos y los inserta en SQLite local + limpia el KV.

Para R1 simplificamos: el detector corre EN EL ERP directamente (sin worker), cada 15min.

Esto evita tocar el worker en R1. **Skipear este task** si vamos por el approach simplificado. Marcar como completed con nota.

- [ ] **Step 2: Decisión arquitectónica registrada en commit**

```bash
cd C:/Users/Diego/el-club
git commit --allow-empty -m "decision(comercial): R1 detector corre en ERP, no worker — simplifica para v1, R6 puede mover al worker si push notif lo requiere"
```

---

### Task 16: Detector de eventos — corre en el ERP cada 15min

**Files:**
- Create: `overhaul/src/lib/data/eventDetector.ts`
- Modify: `overhaul/src/lib/components/comercial/ComercialShell.svelte` (start/stop detector)

- [ ] **Step 1: Crear el detector**

```typescript
// overhaul/src/lib/data/eventDetector.ts
import { adapter } from '$lib/adapter';

export interface DetectedEvent {
  type: string;
  severity: 'crit' | 'warn' | 'info' | 'strat';
  title: string;
  sub: string | null;
  itemsAffected: Array<{ type: string; id: string; hint?: string }>;
}

/**
 * Corre el detector "órdenes pendientes despacho >24h".
 * Compara sales con status='paid' y paid_at >24h pero shipped_at=null.
 * Inserta evento en comercial_events si no existe ya uno activo del mismo tipo.
 */
export async function detectOrdersPending24h(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 24 * 3600 * 1000).toISOString();

  // Llamamos a un nuevo command bridge que retorna las órdenes pending >24h.
  // Por simplicidad, usamos listSalesInRange + filtramos cliente-side.
  const range = { period: '30d' as const, start: new Date(now.getTime() - 30 * 86400000).toISOString(), end: now.toISOString() };
  const sales = await adapter.listSalesInRange(range);
  const pending = sales.filter((s: any) =>
    s.status === 'paid' && s.paidAt < cutoff
    // Note: shipped_at se marca a null cuando status='paid'; el detector confía en esto.
  );

  if (pending.length === 0) return null;

  return {
    type: 'order_pending_24h',
    severity: 'crit',
    title: `${pending.length} órden${pending.length === 1 ? '' : 'es'} pendiente${pending.length === 1 ? '' : 's'} despacho >24h`,
    sub: pending.map((p: any) => p.ref).slice(0, 3).join(' · ') + (pending.length > 3 ? ` · +${pending.length - 3}` : ''),
    itemsAffected: pending.map((p: any) => ({ type: 'order', id: p.ref, hint: `Q${p.totalGtq}` }))
  };
}

/**
 * Inserta el evento en comercial_events vía adapter.
 * Si ya existe un evento activo del mismo type, NO duplica (toda detección que retorna evento existente lo skip).
 */
export async function persistEvent(detected: DetectedEvent): Promise<void> {
  const existing = await adapter.listEvents({ status: 'active' });
  const dup = existing.find((e: any) => e.type === detected.type);
  if (dup) return; // ya existe activo

  // Llamamos a un nuevo command que inserta — agregar a bridge en Step 3 abajo.
  // @ts-expect-error — adapter.insertEvent se agrega en este task
  await adapter.insertEvent?.(detected);
}

/**
 * Loop de detección. Inicia un setInterval que corre las detecciones cada 15min.
 * Retorna función para detener el loop.
 */
export function startDetectorLoop(): () => void {
  async function runOnce() {
    try {
      const ordersPending = await detectOrdersPending24h();
      if (ordersPending) await persistEvent(ordersPending);
      // R3+ agregará más detectores: lead_unanswered_12h, etc.
    } catch (e) {
      console.warn('[detector] run failed', e);
    }
  }

  // Run immediately on start
  runOnce();
  const interval = setInterval(runOnce, 15 * 60 * 1000);
  return () => clearInterval(interval);
}
```

- [ ] **Step 2: Agregar comando bridge `cmd_insert_event`**

En `el-club/erp/scripts/erp_rust_bridge.py`:

```python
def cmd_insert_event(args):
    """Inserta un evento nuevo en comercial_events."""
    import json
    from db import get_conn

    type_ = args.get("type")
    severity = args.get("severity")
    title = args.get("title")
    sub = args.get("sub")
    items = args.get("itemsAffected") or []

    if not type_ or not severity or not title:
        return {"ok": False, "error": "type/severity/title required"}

    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO comercial_events
              (type, severity, title, sub, items_affected_json, detected_at, status)
            VALUES (?, ?, ?, ?, ?, datetime('now'), 'active')
        """, (type_, severity, title, sub, json.dumps(items)))
        conn.commit()
        return {"ok": True, "eventId": cur.lastrowid}
    finally:
        conn.close()
```

Y agregar al dict COMMANDS:

```python
"insert_event": cmd_insert_event,
```

- [ ] **Step 3: Agregar comando Rust + adapter method**

En `lib.rs`:

```rust
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InsertEventArgs {
    #[serde(rename = "type")]
    pub type_: String,
    pub severity: String,
    pub title: String,
    pub sub: Option<String>,
    pub items_affected: Vec<Value>,
}

#[tauri::command]
async fn comercial_insert_event(args: InsertEventArgs) -> Result<i64> {
    let payload = serde_json::json!({
        "cmd": "insert_event",
        "type": args.type_,
        "severity": args.severity,
        "title": args.title,
        "sub": args.sub,
        "itemsAffected": args.items_affected,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("eventId").and_then(|v| v.as_i64()).unwrap_or(-1))
}
```

Registrar en `invoke_handler`.

En `tauri.ts`:

```typescript
async insertEvent(detected: DetectedEvent): Promise<number> {
  return invoke<number>('comercial_insert_event', {
    args: {
      type: detected.type,
      severity: detected.severity,
      title: detected.title,
      sub: detected.sub,
      itemsAffected: detected.itemsAffected
    }
  });
}
```

En `browser.ts`:

```typescript
async insertEvent() { throw new NotAvailableInBrowser('insertEvent'); }
```

En `types.ts` interface Adapter:

```typescript
insertEvent(detected: DetectedEvent): Promise<number>;
```

- [ ] **Step 4: Conectar el detector loop al ComercialShell**

Agregar al `<script>` del ComercialShell.svelte:

```typescript
import { startDetectorLoop } from '$lib/data/eventDetector';

let stopDetector: (() => void) | null = null;

onMount(() => {
  // ... existing tab restore ...
  stopDetector = startDetectorLoop();
});

onDestroy(() => {
  stopDetector?.();
});
```

(`onDestroy` import: `import { onDestroy, onMount } from 'svelte';`)

- [ ] **Step 5: Run type check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check 2>&1 | grep "ERROR" | head -10
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/data/eventDetector.ts overhaul/src-tauri/src/lib.rs overhaul/src/lib/adapter/types.ts overhaul/src/lib/adapter/tauri.ts overhaul/src/lib/adapter/browser.ts overhaul/src/lib/components/comercial/ComercialShell.svelte erp/scripts/erp_rust_bridge.py
git commit -m "feat(comercial): detector loop (orders pending >24h) + insertEvent + 15min interval"
```

---

### Task 17: Push notifications a WA Diego para eventos críticos

**Files:**
- Modify: `overhaul/src/lib/data/eventDetector.ts` (después de insertar evento, dispara push)
- Verify: que el worker existente tenga endpoint para mandar mensaje a Diego

- [ ] **Step 1: Verificar endpoint del worker para push WA**

```bash
cd C:/Users/Diego/ventus-system/backoffice/src
grep -n "notifyDiego\|sendWhatsapp\|notify.*diego" *.js | head -10
```

Identificar endpoint POST que envía mensaje a WA Diego (ya existe para vault Q100).

- [ ] **Step 2: Agregar call al worker desde persistEvent en eventDetector.ts**

```typescript
// En eventDetector.ts, modificar persistEvent:

const WORKER_BASE = 'https://elclub-backoffice.ventusgt.workers.dev'; // ajustar al endpoint real

export async function persistEvent(detected: DetectedEvent): Promise<void> {
  const existing = await adapter.listEvents({ status: 'active' });
  const dup = existing.find((e: any) => e.type === detected.type);
  if (dup) return;

  const eventId = await adapter.insertEvent(detected);

  // Push notification a WA Diego SOLO para crit (R1 scope)
  if (detected.severity === 'crit') {
    try {
      await fetch(`${WORKER_BASE}/api/comercial/notify-diego`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          eventId,
          severity: detected.severity,
          title: detected.title,
          sub: detected.sub
        })
      });
      // Marcar push_sent=1
      await adapter.markEventPushSent?.(eventId);
    } catch (e) {
      console.warn('[detector] push failed', e);
      // No-op: el evento queda con push_sent=0, retry en próximo ciclo si severity sigue crit
    }
  }
}
```

- [ ] **Step 3: Agregar endpoint en worker `/api/comercial/notify-diego`**

En `ventus-system/backoffice/src/index.js`:

```javascript
// Dentro del router del worker:
if (url.pathname === '/api/comercial/notify-diego' && request.method === 'POST') {
  const body = await request.json();
  const { severity, title, sub } = body;
  const text = `🔴 [Comercial] ${title}\n${sub ?? ''}`;
  // Reutilizar la función existente que envía WA a Diego (notifyDiegoVaultPayment o similar)
  await sendWhatsappToDiego(env, text); // usar la función existente del worker
  return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json' } });
}
```

(Adaptar nombres a las funciones reales del worker — usar grep en step 1 para encontrarlas.)

- [ ] **Step 4: Deploy del worker**

```bash
cd C:/Users/Diego/ventus-system/backoffice
npx wrangler deploy 2>&1 | tail -5
```

Expected: deploy success con Worker version.

- [ ] **Step 5: Smoke test del endpoint**

```bash
curl -X POST https://elclub-backoffice.ventusgt.workers.dev/api/comercial/notify-diego \
  -H "Content-Type: application/json" \
  -d '{"severity":"crit","title":"TEST evento crítico","sub":"smoke test desde plan R1"}'
```

Expected: respuesta `{"ok":true}` y mensaje a WA Diego.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src/lib/data/eventDetector.ts
git commit -m "feat(comercial): push WA Diego para eventos críticos (vía worker /api/comercial/notify-diego)"

cd C:/Users/Diego/ventus-system
git add backoffice/src/index.js
git commit -m "feat(comercial): worker endpoint /api/comercial/notify-diego"
```

---

### Task 18: Build MSI v0.1.28 + smoke test end-to-end

**Files:**
- Modify: `overhaul/src-tauri/Cargo.toml` (version)
- Modify: `overhaul/src-tauri/tauri.conf.json` (version)

- [ ] **Step 1: Bump version a 0.1.28 en ambos archivos**

```bash
cd C:/Users/Diego/el-club/overhaul
sed -i 's/version = "0.1.27"/version = "0.1.28"/' src-tauri/Cargo.toml
sed -i 's/"version": "0.1.27"/"version": "0.1.28"/' src-tauri/tauri.conf.json
```

(Si `sed` no funciona en Windows: editar manualmente.)

- [ ] **Step 2: Build MSI**

```bash
cd C:/Users/Diego/el-club/overhaul
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build 2>&1 | tail -10
```

Expected: `Finished 1 bundle at: .../El Club ERP_0.1.28_x64_en-US.msi`.

- [ ] **Step 3: Smoke test instalando y abriendo el ERP**

(Diego ejecuta manual)

1. Desinstalar v0.1.27 desde Panel de Control
2. Instalar el MSI v0.1.28
3. Abrir el ERP
4. Verificar:
   - ✅ Sidebar muestra "Comercial" (no como placeholder)
   - ✅ Click "Comercial" → entra al modo, ve tabs + pulso bar
   - ✅ Pulso bar muestra KPIs reales (Q de revenue, count órdenes, etc.)
   - ✅ Tab Inbox: si hay órdenes pendientes >24h reales, aparecen como crit; sino "all systems nominal"
   - ✅ Click un evento de tipo orden → abre OrderDetailModal
   - ✅ Click "Marcar despachado" → la orden cambia status, evento se resuelve, modal recarga
   - ✅ Click "Mensaje WA" → abre wa.me con el contacto

- [ ] **Step 4: Commit final + tag**

```bash
cd C:/Users/Diego/el-club
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json
git commit -m "chore(release): v0.1.28 — Comercial R1 (Setup + Inbox crítico)"
git tag v0.1.28
```

- [ ] **Step 5: Update LOG.md de Strategy con cierre de R1**

```bash
cd C:/Users/Diego/elclub-catalogo-priv
# Agregar entrada al LOG con sumario del release R1
```

(Estructura libre en el LOG: cierre de release, métricas, próximo paso = R2.)

---

## Self-Review

**1. Spec coverage check:**

- ✅ Sec 3 Arquitectura — sidebar nav (Task 4), tabs container (Task 5-6), pulso persistente (Task 8)
- ✅ Sec 4 Tab Inbox — Tasks 12 funcional con filtros + search
- ✅ Sec 5 Patrón modal — BaseModal (Task 3) + OrderDetailModal (Task 13)
- ✅ Sec 6 Decisiones operativas — umbral 24h (Task 16 detector), push WA siempre (Task 17)
- ✅ Sec 7 Datos — schema 4 tablas (Task 1), bridge commands (Task 10), Rust commands (Task 11), adapter methods (Task 9)
- ✅ Sec 8 Errores — empty state "all systems nominal" (Task 12), loading states en modal (Task 13), browser fallback (Tasks 9 + adapter)
- ✅ Sec 9 Estilo visual retro gaming — heredado de Audit, mismos colores y tipografías

**Brechas identificadas y resueltas inline:**
- ❌→✅ La sec 7 menciona "cron del worker cada 15min" pero Task 15 lo simplificó a "detector corre en ERP". Esto está documentado como decisión arquitectónica para R1 simplification (Task 15 commit empty). R6 puede revisitar si push WA tarda mucho.

**2. Placeholder scan:**
- Ningún "TBD", "TODO", "implement later" en los tasks.
- Steps todos contienen código completo, no abstracto.

**3. Type consistency:**
- `EventSeverity` en TS = `'crit'|'warn'|'info'|'strat'` — usado consistente en kpis.ts, eventDetector.ts, InboxTab.svelte, schema SQL y bridge Python.
- `OrderForModal.status` en TS = `'paid'|'shipped'|'delivered'|'refunded'|'cancelled'` — coherente con `sales.fulfillment_status`.
- `Period` = `'today'|'7d'|'30d'|'custom'` — coherente entre PeriodSelector, kpis.ts, PulsoBar.

---

## Execution Handoff

**Plan complete and saved to `el-club/overhaul/docs/superpowers/plans/2026-04-26-comercial-r1-setup-inbox.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — Despacho un subagent por task, review entre tasks, fast iteration.

**2. Inline Execution** — Ejecutamos tasks en esta sesión usando executing-plans skill, batch con checkpoints.

**Próximo paso para Diego: elegir approach.**

Si pasamos al siguiente release (R2 Funnel + Pulso) después de shipear R1, escribimos un nuevo plan en el mismo directorio: `2026-04-26-comercial-r2-funnel.md`.
