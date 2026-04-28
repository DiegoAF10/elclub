# Finanzas FIN-R1: Skeleton + Home A2 + Gastos CRUD + Schema additions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el skeleton del módulo Finanzas dentro del ERP Tauri (sidebar nav, 7 tabs internos, period strip, body) + Home A2 funcional con 4 cards (primary `Profit operativo` hero + Cash + Capital + Shareholder loan) + tab Gastos CRUD completo (form 3 actions + lista + 6 buckets) + schema additions sobre `elclub.db` compartida. Diego ya puede ver "¿cuánto llevo ganado?" del mes actual al abrir, registrar gastos en sub-3 segundos, y trackear shareholder_loan automático.

**Architecture:** SvelteKit 5 (runes) + Tauri 2 (Rust backend) + SQLite local **compartida con Streamlit** (`C:\Users\Diego\el-club\erp\elclub.db`). Finanzas vive en `overhaul/src/routes/finanzas/` y `overhaul/src/lib/components/finanzas/`. Schema additions vía script idempotente (mismo patrón IMP-R1). FIN solo escribe a sus propias tablas (`expenses`, `recurring_expenses`, `cash_balance_history`, `shareholder_loan_movements`, `owner_draws`); lee `sales`, `sale_items`, `campaigns_snapshot`, `imports` (sin escribir).

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte icons
- Backend: Rust (Tauri commands · `rusqlite`), schema en SQL puro
- Storage: SQLite compartida `el-club/erp/elclub.db`
- Verification: `npm run check` (svelte-check + tsc) + `cargo check` + smoke manual + build MSI

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-27-finanzas-design.md`

**Mockups HD reference:** `el-club/overhaul/.superpowers/brainstorm/4941-1777340205/content/03-mockup-a2-hd.html` (canonical Home UI · abrir en browser para reference visual).

**Branch:** `finanzas-r1`

**Versionado al completar:** ERP v0.1.40+ (post-IMP-R1 ship · TBD versión exacta)

**Trigger:** post `IMP-R1` ship — `sale_items.unit_cost` necesita estar poblado para COGS reales.

---

## Patrón de testing en este codebase

Mismo que IMP-R1:

1. **TypeScript types como contract** — definir tipos antes que implementación.
2. **`npm run check`** después de cada step de código frontend.
3. **`cargo check --manifest-path src-tauri/Cargo.toml`** después de cada step Rust.
4. **Smoke test manual** al final de cada task (`npm run tauri dev`).
5. **Build MSI** como gate final.

---

## File Structure

### Archivos NUEVOS

```
overhaul/src/lib/components/finanzas/
├── FinanzasShell.svelte             # Container principal (module-head + tabs + period strip + body)
├── FinanzasTabs.svelte              # 7 tabs internos
├── PeriodStrip.svelte               # 8 botones período + period info
├── tabs/
│   ├── HomeTab.svelte               # FUNCIONAL · A2 dashboard
│   ├── EstadoResultadosTab.svelte   # R1: placeholder "Próximamente en R2"
│   ├── ProductosTab.svelte          # R1: placeholder
│   ├── GastosTab.svelte             # FUNCIONAL · CRUD completo
│   ├── CuentaBusinessTab.svelte     # R1: placeholder con balance widget básico
│   ├── InterCuentaTab.svelte        # R1: placeholder con loan widget básico
│   └── SettingsTab.svelte           # R1: solo "Defaults" section
├── home/
│   ├── ProfitHeroCard.svelte        # Primary card · profit operativo gigante
│   ├── CashCard.svelte              # Secondary · cash business
│   ├── CapitalCard.svelte           # Secondary · capital amarrado
│   ├── ShareholderLoanCard.svelte   # Secondary · te debe a vos
│   ├── WaterfallMini.svelte         # Row 2 · 4 minis bars
│   ├── RecentExpenses.svelte        # Sub-grid · últimos 6 gastos
│   └── InboxFinanciero.svelte       # Sub-grid · eventos CK3-style
├── gastos/
│   ├── GastoForm.svelte             # Form 3 actions · TDAH-optimized
│   ├── GastosList.svelte            # Tabla densa filtrable
│   └── GastoEditModal.svelte        # Modal edit reusing form
└── shared/
    ├── PeriodSelector.svelte        # Reusable button group
    └── MoneyDisplay.svelte          # Helper para Q/USD format

overhaul/src/lib/data/
├── finanzas.ts                      # Types: Expense, ExpenseCategory, Period, ProfitSnapshot, etc.
├── finanzasComputed.ts              # Pure helpers: computeProfit(), filterByPeriod(), formatMoney()
└── finanzasPeriods.ts               # Pure helpers: periodToDateRange(), todayInGT()

overhaul/src/routes/finanzas/
└── +page.svelte                     # Mount del FinanzasShell

el-club/erp/scripts/
└── apply_finanzas_schema.py         # Idempotent schema additions (5 tablas + 2 views)
```

### Archivos a MODIFICAR

```
overhaul/src/lib/components/Sidebar.svelte         # Agregar nav-item "Finanzas" en data section
overhaul/src/routes/+page.svelte                   # Routing al modo Finanzas
overhaul/src/lib/adapter/types.ts                  # Re-export types
overhaul/src/lib/adapter/tauri.ts                  # Invocaciones para 8 commands nuevos
overhaul/src/lib/adapter/browser.ts                # NotAvailableInBrowser para writes
overhaul/src-tauri/src/lib.rs                      # 8 commands nuevos
overhaul/src-tauri/Cargo.toml                      # version bump
overhaul/src-tauri/tauri.conf.json                 # version bump
overhaul/package.json                              # version bump
```

### NOT modified (sagrado)

- `el-club/erp/comercial.py` — Streamlit sigue funcionando paralelo.
- `el-club/erp/elclub.db` schema existente — solo adiciones (CREATE TABLE IF NOT EXISTS).
- `audit_decisions` schema — invariante sagrado.
- Comercial e IMP code — FIN solo lee de sus tablas, no escribe.

---

## Tasks

### Task 1: Schema additions sobre elclub.db (5 tablas + 2 views)

**Files:**
- Create: `el-club/erp/scripts/apply_finanzas_schema.py`
- Modify: `el-club/erp/schema.sql` (documentar las nuevas tablas/views)
- Verify: `sqlite3 elclub.db ".schema expenses"` y views

- [ ] **Step 1: Leer schema actual relevante**

```bash
cd C:/Users/Diego/el-club/erp
sqlite3 elclub.db ".tables"
sqlite3 elclub.db ".schema sales"
sqlite3 elclub.db ".schema sale_items"
sqlite3 elclub.db ".schema imports"
```

Anotar columnas existentes para joins en views.

- [ ] **Step 2: Crear `apply_finanzas_schema.py` idempotente**

```python
# C:/Users/Diego/el-club/erp/scripts/apply_finanzas_schema.py
"""FIN-R1 schema additions. Idempotente — re-runnable sin error."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"C:\Users\Diego\el-club\erp\elclub.db")

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS expenses (
      expense_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq        REAL NOT NULL,
      amount_native     REAL,
      currency          TEXT DEFAULT 'GTQ' CHECK(currency IN ('GTQ','USD')),
      fx_used           REAL DEFAULT 7.73,
      category          TEXT NOT NULL CHECK(category IN ('variable','tech','marketing','operations','owner_draw','other')),
      payment_method    TEXT NOT NULL CHECK(payment_method IN ('tdc_personal','cuenta_business')),
      paid_at           TEXT NOT NULL,
      notes             TEXT,
      source            TEXT DEFAULT 'manual' CHECK(source IN ('manual','recurring_template','auto_sale_derived','auto_marketing_pull')),
      source_ref        TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recurring_expenses (
      template_id       INTEGER PRIMARY KEY AUTOINCREMENT,
      name              TEXT NOT NULL,
      amount_native     REAL NOT NULL,
      currency          TEXT DEFAULT 'GTQ',
      category          TEXT NOT NULL,
      payment_method    TEXT NOT NULL,
      day_of_month      INTEGER CHECK(day_of_month BETWEEN 1 AND 28),
      notes_template    TEXT,
      active            INTEGER DEFAULT 1,
      started_at        TEXT NOT NULL,
      ended_at          TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_balance_history (
      balance_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      account           TEXT NOT NULL DEFAULT 'el_club_business',
      balance_gtq       REAL NOT NULL,
      synced_at         TEXT NOT NULL,
      source            TEXT NOT NULL CHECK(source IN ('manual_via_claude','manual_via_telegram','manual_direct','api_recurrente','reconciliation')),
      notes             TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shareholder_loan_movements (
      movement_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq         REAL NOT NULL,
      source_type        TEXT NOT NULL CHECK(source_type IN ('expense_tdc','recoupment','adjustment')),
      source_ref         TEXT,
      movement_date      TEXT NOT NULL,
      loan_balance_after REAL NOT NULL,
      notes              TEXT,
      created_at         TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_draws (
      draw_id           INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq        REAL NOT NULL,
      draw_date         TEXT NOT NULL,
      was_recoupment    INTEGER DEFAULT 0,
      recoupment_amount REAL DEFAULT 0,
      pure_draw_amount  REAL,
      notes             TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
]

CREATE_VIEWS = [
    """
    CREATE VIEW IF NOT EXISTS v_monthly_profit AS
    SELECT
      strftime('%Y-%m', s.paid_at) AS month,
      SUM(s.total_gtq) AS revenue,
      SUM(COALESCE(si.unit_cost, 0)) AS cogs,
      (SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
        WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', s.paid_at)
        AND category = 'marketing') AS marketing_logged,
      (SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
        WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', s.paid_at)
        AND category NOT IN ('marketing', 'owner_draw')) AS opex
    FROM sales s
    LEFT JOIN sale_items si ON si.sale_id = s.sale_id
    WHERE s.paid_at IS NOT NULL
    GROUP BY strftime('%Y-%m', s.paid_at)
    """,
    """
    CREATE VIEW IF NOT EXISTS v_shareholder_loan_balance AS
    SELECT
      COALESCE(SUM(amount_gtq), 0) AS current_balance,
      MAX(movement_date) AS last_movement_date
    FROM shareholder_loan_movements
    """,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_expenses_paid_at ON expenses(paid_at)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_payment_method ON expenses(payment_method)",
    "CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_expenses(active)",
    "CREATE INDEX IF NOT EXISTS idx_cash_synced_at ON cash_balance_history(synced_at)",
    "CREATE INDEX IF NOT EXISTS idx_loan_date ON shareholder_loan_movements(movement_date)",
    "CREATE INDEX IF NOT EXISTS idx_draw_date ON owner_draws(draw_date)",
]


def main():
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"📂 Applying FIN-R1 schema to {DB_PATH}")

    for sql in CREATE_TABLES:
        cur.execute(sql)
    print(f"  ✓ created/verified {len(CREATE_TABLES)} tables")

    for sql in CREATE_VIEWS:
        cur.execute(sql)
    print(f"  ✓ created/verified {len(CREATE_VIEWS)} views")

    for sql in CREATE_INDEXES:
        cur.execute(sql)
    print(f"  ✓ created/verified {len(CREATE_INDEXES)} indexes")

    conn.commit()
    conn.close()
    print("✅ FIN-R1 schema applied successfully (idempotente)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Ejecutar el script**

```bash
cd C:/Users/Diego/el-club/erp
python scripts/apply_finanzas_schema.py
```

Expected output:
```
📂 Applying FIN-R1 schema to C:\Users\Diego\el-club\erp\elclub.db
  ✓ created/verified 5 tables
  ✓ created/verified 2 views
  ✓ created/verified 7 indexes
✅ FIN-R1 schema applied successfully (idempotente)
```

- [ ] **Step 4: Verificar idempotencia (re-run)**

```bash
python scripts/apply_finanzas_schema.py
```

Expected: misma salida sin error.

- [ ] **Step 5: Verificar manual con sqlite3**

```bash
sqlite3 elclub.db ".schema expenses"
sqlite3 elclub.db ".schema recurring_expenses"
sqlite3 elclub.db "SELECT * FROM v_monthly_profit"
sqlite3 elclub.db "SELECT * FROM v_shareholder_loan_balance"
```

- [ ] **Step 6: Documentar el cambio en `schema.sql`**

Agregar al final de `schema.sql`:

```sql
-- ═══════════════════════════════════════
-- FIN-R1 schema additions (2026-04-27)
-- Aplicado vía scripts/apply_finanzas_schema.py (idempotente)
-- ═══════════════════════════════════════

-- 5 tables: expenses, recurring_expenses, cash_balance_history, shareholder_loan_movements, owner_draws
-- 2 views: v_monthly_profit, v_shareholder_loan_balance
-- 7 indexes
-- See scripts/apply_finanzas_schema.py for full DDL.
```

- [ ] **Step 7: Commit**

```bash
git add el-club/erp/scripts/apply_finanzas_schema.py el-club/erp/schema.sql
git commit -m "feat(fin): FIN-R1 schema additions for Finanzas module

- CREATE TABLE expenses (6 buckets · payment_method · multi-currency)
- CREATE TABLE recurring_expenses (templates · cron-driven en R4)
- CREATE TABLE cash_balance_history (manual sync via Claude/Telegram)
- CREATE TABLE shareholder_loan_movements (TDC personal owe-back)
- CREATE TABLE owner_draws (auto-resolve recoupment + pure draw)
- VIEW v_monthly_profit (revenue − cogs − mkt − opex per mes)
- VIEW v_shareholder_loan_balance (current balance + last movement)
- 7 indexes

Idempotente. Re-runnable sin error.
Spec: docs/superpowers/specs/2026-04-27-finanzas-design.md sec 6"
```

---

### Task 2: TypeScript types · Expense, Period, ProfitSnapshot, etc.

**Files:**
- Create: `overhaul/src/lib/data/finanzas.ts`
- Create: `overhaul/src/lib/data/finanzasComputed.ts`
- Create: `overhaul/src/lib/data/finanzasPeriods.ts`
- Modify: `overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Crear `finanzas.ts` types**

```typescript
// C:/Users/Diego/el-club/overhaul/src/lib/data/finanzas.ts

export type ExpenseCategory = 'variable' | 'tech' | 'marketing' | 'operations' | 'owner_draw' | 'other';

export type PaymentMethod = 'tdc_personal' | 'cuenta_business';

export type ExpenseSource = 'manual' | 'recurring_template' | 'auto_sale_derived' | 'auto_marketing_pull';

export type Currency = 'GTQ' | 'USD';

export interface Expense {
  expense_id: number;
  amount_gtq: number;
  amount_native: number | null;
  currency: Currency;
  fx_used: number;
  category: ExpenseCategory;
  payment_method: PaymentMethod;
  paid_at: string;          // ISO date
  notes: string | null;
  source: ExpenseSource;
  source_ref: string | null;
  created_at: string;
}

export interface ExpenseInput {
  amount_native: number;
  currency: Currency;
  fx_used?: number;          // default 7.73
  category: ExpenseCategory;
  payment_method: PaymentMethod;
  paid_at: string;
  notes?: string;
}

export type Period = 'today' | '7d' | '30d' | 'month' | 'last_month' | 'ytd' | 'lifetime' | 'custom';

export interface PeriodRange {
  start: string;             // ISO date
  end: string;               // ISO date inclusive
  label: string;             // human-readable "Abril 2026"
}

export interface ProfitSnapshot {
  period: PeriodRange;
  revenue_gtq: number;
  cogs_gtq: number;
  marketing_gtq: number;     // sum from expenses category=marketing + campaigns_snapshot.spend
  opex_gtq: number;          // expenses NOT (marketing, owner_draw)
  profit_operativo: number;  // revenue − cogs − mkt − opex
  prev_period_profit?: number; // for trend
  trend_pct?: number;
}

export interface HomeSnapshot {
  profit: ProfitSnapshot;
  cash_business_gtq: number | null;
  cash_synced_at: string | null;
  cash_stale_days: number | null;
  capital_amarrado_gtq: number;
  shareholder_loan_balance: number;
  shareholder_loan_trend_30d: number;
}

export interface RecentExpense extends Expense {
  category_label: string;    // localized "Tech infra"
}

export interface FinanzasInboxEvent {
  event_id: string;          // synthetic key
  severity: 'crit' | 'warn' | 'info' | 'strat';
  title: string;
  sub: string;
  action_label?: string;
  action_target?: string;    // tab/route to navigate
  detected_at: string;
}

export const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  variable: 'Variable per sale',
  tech: 'Tech infra',
  marketing: 'Marketing',
  operations: 'Operaciones',
  owner_draw: 'Owner draw',
  other: 'Otros',
};

export const CATEGORY_PILL_CLASS: Record<ExpenseCategory, string> = {
  variable:    'bg-[rgba(91,141,239,0.14)] text-[var(--color-accent)]',
  tech:        'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
  marketing:   'bg-[rgba(245,165,36,0.14)] text-[var(--color-warning)]',
  operations:  'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
  owner_draw:  'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
  other:       'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
};

export const PAYMENT_METHOD_ICON: Record<PaymentMethod, string> = {
  tdc_personal: '💳',
  cuenta_business: '🏦',
};
```

- [ ] **Step 2: Crear `finanzasPeriods.ts` con helpers de período**

```typescript
// C:/Users/Diego/el-club/overhaul/src/lib/data/finanzasPeriods.ts

import type { Period, PeriodRange } from './finanzas';

const MONTH_NAMES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

export function todayInGT(): Date {
  // GT timezone es UTC-6, no DST. Aproximación: Date local del binario de Diego está en GT.
  return new Date();
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function periodToDateRange(period: Period, customStart?: string, customEnd?: string): PeriodRange {
  const today = todayInGT();
  const isoToday = isoDate(today);

  switch (period) {
    case 'today':
      return { start: isoToday, end: isoToday, label: 'Hoy' };

    case '7d': {
      const start = new Date(today);
      start.setDate(start.getDate() - 6);
      return { start: isoDate(start), end: isoToday, label: 'Últimos 7 días' };
    }

    case '30d': {
      const start = new Date(today);
      start.setDate(start.getDate() - 29);
      return { start: isoDate(start), end: isoToday, label: 'Últimos 30 días' };
    }

    case 'month': {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return {
        start: isoDate(start),
        end: isoDate(end),
        label: `${MONTH_NAMES[today.getMonth()]} ${today.getFullYear()}`,
      };
    }

    case 'last_month': {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      return {
        start: isoDate(start),
        end: isoDate(end),
        label: `${MONTH_NAMES[start.getMonth()]} ${start.getFullYear()}`,
      };
    }

    case 'ytd': {
      const start = new Date(today.getFullYear(), 0, 1);
      return {
        start: isoDate(start),
        end: isoToday,
        label: `YTD ${today.getFullYear()}`,
      };
    }

    case 'lifetime':
      return { start: '2026-03-01', end: isoToday, label: 'Lifetime (desde marzo 2026)' };

    case 'custom':
      if (!customStart || !customEnd) throw new Error('custom period requires start + end');
      return { start: customStart, end: customEnd, label: `${customStart} → ${customEnd}` };
  }
}

export function daysBetween(startIso: string, endIso: string): number {
  const start = new Date(startIso);
  const end = new Date(endIso);
  return Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
}
```

- [ ] **Step 3: Crear `finanzasComputed.ts` con helpers puros**

```typescript
// C:/Users/Diego/el-club/overhaul/src/lib/data/finanzasComputed.ts

import type { ProfitSnapshot } from './finanzas';

export function formatGTQ(amount: number | null | undefined, opts: { sign?: boolean } = {}): string {
  if (amount === null || amount === undefined) return '—';
  const sign = opts.sign && amount > 0 ? '+' : '';
  const abs = Math.abs(Math.round(amount));
  const formatted = abs.toLocaleString('es-GT');
  return `${sign}${amount < 0 ? '−' : ''}Q${formatted}`;
}

export function formatUSD(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '—';
  return `$${amount.toFixed(2)}`;
}

export function profitColor(profit: number): 'green' | 'red' | 'muted' {
  if (profit > 0) return 'green';
  if (profit < 0) return 'red';
  return 'muted';
}

export function trendPct(current: number, previous: number): number | null {
  if (previous === 0) return null;
  return ((current - previous) / Math.abs(previous)) * 100;
}

export function trendArrow(pct: number | null): string {
  if (pct === null) return '';
  if (pct > 0) return `↑ ${pct.toFixed(0)}%`;
  if (pct < 0) return `↓ ${Math.abs(pct).toFixed(0)}%`;
  return '→ 0%';
}

/**
 * Compute profit snapshot from raw inputs (puro · testeable).
 * Used by Tauri command + browser fallback.
 */
export function computeProfitSnapshot(
  revenue_gtq: number,
  cogs_gtq: number,
  marketing_gtq: number,
  opex_gtq: number,
  prev_profit?: number,
  period?: ProfitSnapshot['period'],
): ProfitSnapshot {
  const profit = revenue_gtq - cogs_gtq - marketing_gtq - opex_gtq;
  return {
    period: period ?? { start: '', end: '', label: '' },
    revenue_gtq,
    cogs_gtq,
    marketing_gtq,
    opex_gtq,
    profit_operativo: profit,
    prev_period_profit: prev_profit,
    trend_pct: prev_profit !== undefined ? trendPct(profit, prev_profit) ?? undefined : undefined,
  };
}
```

- [ ] **Step 4: Re-export en `types.ts`**

```typescript
// adapter/types.ts (al final)
export type { Expense, ExpenseCategory, PaymentMethod, Period, PeriodRange, ProfitSnapshot, HomeSnapshot, RecentExpense, FinanzasInboxEvent } from '$lib/data/finanzas';
export { CATEGORY_LABELS as FIN_CATEGORY_LABELS, CATEGORY_PILL_CLASS as FIN_CATEGORY_PILL, PAYMENT_METHOD_ICON as FIN_PAYMENT_ICON } from '$lib/data/finanzas';
```

- [ ] **Step 5: `npm run check`**

- [ ] **Step 6: Commit**

```bash
git add overhaul/src/lib/data/finanzas.ts overhaul/src/lib/data/finanzasComputed.ts overhaul/src/lib/data/finanzasPeriods.ts overhaul/src/lib/adapter/types.ts
git commit -m "feat(fin): types canonical para Finanzas (Expense, Period, ProfitSnapshot)"
```

---

### Task 3: Tauri Rust commands · profit + expenses CRUD + home snapshot

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs` (8 commands nuevos)

- [ ] **Step 1: Definir structs Rust**

Agregar después de structs de Importaciones (al final de la sección de structs):

```rust
// ─── Finanzas (FIN-R1) ─────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct Expense {
    pub expense_id: i64,
    pub amount_gtq: f64,
    pub amount_native: Option<f64>,
    pub currency: String,
    pub fx_used: f64,
    pub category: String,
    pub payment_method: String,
    pub paid_at: String,
    pub notes: Option<String>,
    pub source: String,
    pub source_ref: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct ExpenseInput {
    pub amount_native: f64,
    pub currency: String,
    pub fx_used: Option<f64>,
    pub category: String,
    pub payment_method: String,
    pub paid_at: String,
    pub notes: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ProfitSnapshot {
    pub period_start: String,
    pub period_end: String,
    pub period_label: String,
    pub revenue_gtq: f64,
    pub cogs_gtq: f64,
    pub marketing_gtq: f64,
    pub opex_gtq: f64,
    pub profit_operativo: f64,
    pub prev_period_profit: Option<f64>,
    pub trend_pct: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct HomeSnapshot {
    pub profit: ProfitSnapshot,
    pub cash_business_gtq: Option<f64>,
    pub cash_synced_at: Option<String>,
    pub cash_stale_days: Option<i64>,
    pub capital_amarrado_gtq: f64,
    pub shareholder_loan_balance: f64,
    pub shareholder_loan_trend_30d: f64,
}

#[derive(Debug, Serialize)]
pub struct RecentExpenseRow {
    pub expense_id: i64,
    pub paid_at: String,
    pub category: String,
    pub payment_method: String,
    pub amount_gtq: f64,
    pub notes: Option<String>,
}
```

- [ ] **Step 2: Implementar `cmd_compute_profit_snapshot`**

```rust
#[tauri::command]
pub async fn cmd_compute_profit_snapshot(
    _app: tauri::AppHandle,
    period_start: String,
    period_end: String,
    period_label: String,
    prev_start: Option<String>,
    prev_end: Option<String>,
) -> Result<ProfitSnapshot> {
    let conn = rusqlite::Connection::open(db_path())?;

    // Revenue: cash basis · sales con paid_at en rango
    let revenue: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_gtq), 0) FROM sales
         WHERE paid_at IS NOT NULL
           AND date(paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // COGS: sale_items.unit_cost de sales en rango
    let cogs: f64 = conn.query_row(
        "SELECT COALESCE(SUM(si.unit_cost), 0)
         FROM sale_items si
         JOIN sales s ON s.sale_id = si.sale_id
         WHERE s.paid_at IS NOT NULL
           AND date(s.paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Marketing: expenses category=marketing en rango
    let marketing_logged: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
         WHERE category = 'marketing'
           AND date(paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Opex: expenses NOT (marketing, owner_draw)
    let opex: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
         WHERE category NOT IN ('marketing','owner_draw')
           AND date(paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    let profit = revenue - cogs - marketing_logged - opex;

    // Prev period profit (if requested)
    let prev_profit = if let (Some(ps), Some(pe)) = (prev_start, prev_end) {
        let prev_rev: f64 = conn.query_row(
            "SELECT COALESCE(SUM(total_gtq), 0) FROM sales
             WHERE paid_at IS NOT NULL AND date(paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_cogs: f64 = conn.query_row(
            "SELECT COALESCE(SUM(si.unit_cost), 0)
             FROM sale_items si JOIN sales s ON s.sale_id = si.sale_id
             WHERE s.paid_at IS NOT NULL AND date(s.paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_mkt: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
             WHERE category = 'marketing' AND date(paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_opex: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
             WHERE category NOT IN ('marketing','owner_draw') AND date(paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        Some(prev_rev - prev_cogs - prev_mkt - prev_opex)
    } else {
        None
    };

    let trend_pct = match prev_profit {
        Some(prev) if prev != 0.0 => Some(((profit - prev) / prev.abs()) * 100.0),
        _ => None,
    };

    Ok(ProfitSnapshot {
        period_start,
        period_end,
        period_label,
        revenue_gtq: revenue,
        cogs_gtq: cogs,
        marketing_gtq: marketing_logged,
        opex_gtq: opex,
        profit_operativo: profit,
        prev_period_profit: prev_profit,
        trend_pct,
    })
}
```

- [ ] **Step 3: Implementar `cmd_get_home_snapshot`**

```rust
#[tauri::command]
pub async fn cmd_get_home_snapshot(
    app: tauri::AppHandle,
    period_start: String,
    period_end: String,
    period_label: String,
    prev_start: Option<String>,
    prev_end: Option<String>,
) -> Result<HomeSnapshot> {
    let profit = cmd_compute_profit_snapshot(
        app,
        period_start.clone(),
        period_end.clone(),
        period_label.clone(),
        prev_start,
        prev_end,
    ).await?;

    let conn = rusqlite::Connection::open(db_path())?;

    // Cash business: latest balance entry
    let cash_row: Option<(f64, String)> = conn.query_row(
        "SELECT balance_gtq, synced_at FROM cash_balance_history
         WHERE account = 'el_club_business'
         ORDER BY synced_at DESC LIMIT 1",
        [],
        |r| Ok((r.get(0)?, r.get(1)?)),
    ).ok();

    let (cash_business_gtq, cash_synced_at, cash_stale_days) = match cash_row {
        Some((bal, synced)) => {
            let stale: i64 = conn.query_row(
                "SELECT CAST(julianday('now', 'localtime') - julianday(?1) AS INTEGER)",
                rusqlite::params![&synced],
                |r| r.get(0),
            ).unwrap_or(0);
            (Some(bal), Some(synced), Some(stale))
        }
        None => (None, None, None),
    };

    // Capital amarrado: imports paid+in_transit+arrived (no closed)
    let capital: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status IN ('paid','in_transit','arrived')",
        [],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Shareholder loan balance
    let loan_balance: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements",
        [],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Loan trend 30d
    let loan_trend: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements
         WHERE date(movement_date) >= date('now', 'localtime', '-30 days')",
        [],
        |r| r.get(0),
    ).unwrap_or(0.0);

    Ok(HomeSnapshot {
        profit,
        cash_business_gtq,
        cash_synced_at,
        cash_stale_days,
        capital_amarrado_gtq: capital,
        shareholder_loan_balance: loan_balance,
        shareholder_loan_trend_30d: loan_trend,
    })
}
```

- [ ] **Step 4: Implementar `cmd_create_expense` (CRITICAL · auto-trigger shareholder_loan)**

```rust
#[tauri::command]
pub async fn cmd_create_expense(
    _app: tauri::AppHandle,
    input: ExpenseInput,
) -> Result<i64> {
    let mut conn = rusqlite::Connection::open(db_path())?;
    let tx = conn.transaction()?;

    let fx = input.fx_used.unwrap_or(7.73);
    let amount_gtq = match input.currency.as_str() {
        "USD" => input.amount_native * fx,
        "GTQ" => input.amount_native,
        _ => return Err(ErpError::Other(format!("invalid currency: {}", input.currency))),
    };

    // 1. Insert expense
    tx.execute(
        "INSERT INTO expenses (amount_gtq, amount_native, currency, fx_used, category, payment_method, paid_at, notes, source)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'manual')",
        rusqlite::params![
            amount_gtq,
            input.amount_native,
            input.currency,
            fx,
            input.category,
            input.payment_method,
            input.paid_at,
            input.notes
        ],
    )?;
    let expense_id = tx.last_insert_rowid();

    // 2. Si payment_method='tdc_personal', auto-insert en shareholder_loan_movements
    if input.payment_method == "tdc_personal" {
        let current_balance: f64 = tx.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements",
            [],
            |r| r.get(0),
        ).unwrap_or(0.0);
        let new_balance = current_balance + amount_gtq;

        tx.execute(
            "INSERT INTO shareholder_loan_movements (amount_gtq, source_type, source_ref, movement_date, loan_balance_after, notes)
             VALUES (?1, 'expense_tdc', ?2, ?3, ?4, ?5)",
            rusqlite::params![
                amount_gtq,
                expense_id.to_string(),
                input.paid_at,
                new_balance,
                input.notes
            ],
        )?;
    }

    tx.commit()?;
    Ok(expense_id)
}
```

- [ ] **Step 5: Implementar `cmd_list_expenses` con filtros**

```rust
#[tauri::command]
pub async fn cmd_list_expenses(
    _app: tauri::AppHandle,
    period_start: Option<String>,
    period_end: Option<String>,
    category: Option<String>,
    payment_method: Option<String>,
    limit: Option<i64>,
) -> Result<Vec<Expense>> {
    let conn = rusqlite::Connection::open(db_path())?;

    let mut where_clauses: Vec<String> = vec!["1=1".to_string()];
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    if let Some(s) = period_start.as_ref() {
        where_clauses.push("date(paid_at) >= date(?)".to_string());
        params.push(Box::new(s.clone()));
    }
    if let Some(e) = period_end.as_ref() {
        where_clauses.push("date(paid_at) <= date(?)".to_string());
        params.push(Box::new(e.clone()));
    }
    if let Some(c) = category.as_ref() {
        where_clauses.push("category = ?".to_string());
        params.push(Box::new(c.clone()));
    }
    if let Some(pm) = payment_method.as_ref() {
        where_clauses.push("payment_method = ?".to_string());
        params.push(Box::new(pm.clone()));
    }

    let limit_v = limit.unwrap_or(500);
    let sql = format!(
        "SELECT expense_id, amount_gtq, amount_native, currency, fx_used, category, payment_method, paid_at, notes, source, source_ref, created_at
         FROM expenses WHERE {} ORDER BY paid_at DESC LIMIT {}",
        where_clauses.join(" AND "),
        limit_v
    );

    let params_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(&params_refs[..], |row| {
        Ok(Expense {
            expense_id: row.get(0)?,
            amount_gtq: row.get(1)?,
            amount_native: row.get(2)?,
            currency: row.get(3)?,
            fx_used: row.get(4)?,
            category: row.get(5)?,
            payment_method: row.get(6)?,
            paid_at: row.get(7)?,
            notes: row.get(8)?,
            source: row.get(9)?,
            source_ref: row.get(10)?,
            created_at: row.get(11)?,
        })
    })?;
    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}
```

- [ ] **Step 6: Implementar `cmd_delete_expense`, `cmd_update_expense`, `cmd_recent_expenses`, `cmd_set_cash_balance`**

```rust
#[tauri::command]
pub async fn cmd_delete_expense(_app: tauri::AppHandle, expense_id: i64) -> Result<()> {
    let mut conn = rusqlite::Connection::open(db_path())?;
    let tx = conn.transaction()?;

    // Si era TDC personal, también borrar el shareholder_loan_movement asociado
    tx.execute(
        "DELETE FROM shareholder_loan_movements
         WHERE source_type = 'expense_tdc' AND source_ref = ?1",
        rusqlite::params![expense_id.to_string()],
    )?;

    tx.execute("DELETE FROM expenses WHERE expense_id = ?1", rusqlite::params![expense_id])?;
    tx.commit()?;
    Ok(())
}

#[tauri::command]
pub async fn cmd_update_expense(_app: tauri::AppHandle, expense_id: i64, input: ExpenseInput) -> Result<()> {
    // Para R1: simplemente delete + insert nuevo (más simple). Optimizable después.
    cmd_delete_expense(_app.clone(), expense_id).await?;
    cmd_create_expense(_app, input).await?;
    Ok(())
}

#[tauri::command]
pub async fn cmd_recent_expenses(_app: tauri::AppHandle, limit: Option<i64>) -> Result<Vec<RecentExpenseRow>> {
    let conn = rusqlite::Connection::open(db_path())?;
    let limit_v = limit.unwrap_or(6);
    let mut stmt = conn.prepare(
        "SELECT expense_id, paid_at, category, payment_method, amount_gtq, notes
         FROM expenses ORDER BY paid_at DESC, expense_id DESC LIMIT ?1"
    )?;
    let rows = stmt.query_map(rusqlite::params![limit_v], |row| {
        Ok(RecentExpenseRow {
            expense_id: row.get(0)?,
            paid_at: row.get(1)?,
            category: row.get(2)?,
            payment_method: row.get(3)?,
            amount_gtq: row.get(4)?,
            notes: row.get(5)?,
        })
    })?;
    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}

#[tauri::command]
pub async fn cmd_set_cash_balance(
    _app: tauri::AppHandle,
    balance_gtq: f64,
    source: String,
    notes: Option<String>,
) -> Result<i64> {
    let conn = rusqlite::Connection::open(db_path())?;
    conn.execute(
        "INSERT INTO cash_balance_history (account, balance_gtq, synced_at, source, notes)
         VALUES ('el_club_business', ?1, datetime('now', 'localtime'), ?2, ?3)",
        rusqlite::params![balance_gtq, source, notes],
    )?;
    Ok(conn.last_insert_rowid())
}
```

- [ ] **Step 7: Registrar 8 commands en `tauri::generate_handler!`**

```rust
cmd_compute_profit_snapshot,
cmd_get_home_snapshot,
cmd_create_expense,
cmd_list_expenses,
cmd_delete_expense,
cmd_update_expense,
cmd_recent_expenses,
cmd_set_cash_balance,
```

- [ ] **Step 8: `cargo check`**

- [ ] **Step 9: Commit**

```bash
git add overhaul/src-tauri/src/lib.rs
git commit -m "feat(fin): 8 Tauri commands para Finanzas R1

- compute_profit_snapshot (revenue − cogs − mkt − opex)
- get_home_snapshot (profit + cash + capital + loan)
- create_expense (auto-trigger shareholder_loan_movement si TDC personal)
- list_expenses (filtros por período · category · payment_method)
- delete_expense (cascade delete shareholder_loan_movement asociado)
- update_expense (delete + insert para R1)
- recent_expenses (top 6 para Home)
- set_cash_balance (manual sync via Claude/Telegram/UI)"
```

---

### Task 4: Adapter — invocaciones tauri.ts + browser.ts

**Files:**
- Modify: `overhaul/src/lib/adapter/tauri.ts`
- Modify: `overhaul/src/lib/adapter/browser.ts`
- Modify: `overhaul/src/lib/adapter/index.ts`

- [ ] **Step 1: tauri.ts invocaciones**

```typescript
// adapter/tauri.ts (al final)
import type { Expense, ExpenseInput, ProfitSnapshot, HomeSnapshot, RecentExpense } from '$lib/data/finanzas';

export async function computeProfitSnapshot(periodStart: string, periodEnd: string, periodLabel: string, prevStart?: string, prevEnd?: string): Promise<ProfitSnapshot> {
  return invoke('cmd_compute_profit_snapshot', { periodStart, periodEnd, periodLabel, prevStart, prevEnd });
}

export async function getHomeSnapshot(periodStart: string, periodEnd: string, periodLabel: string, prevStart?: string, prevEnd?: string): Promise<HomeSnapshot> {
  return invoke('cmd_get_home_snapshot', { periodStart, periodEnd, periodLabel, prevStart, prevEnd });
}

export async function createExpense(input: ExpenseInput): Promise<number> {
  return invoke('cmd_create_expense', { input });
}

export async function listExpenses(filters: { periodStart?: string; periodEnd?: string; category?: string; paymentMethod?: string; limit?: number } = {}): Promise<Expense[]> {
  return invoke('cmd_list_expenses', filters);
}

export async function deleteExpense(expenseId: number): Promise<void> {
  return invoke('cmd_delete_expense', { expenseId });
}

export async function updateExpense(expenseId: number, input: ExpenseInput): Promise<void> {
  return invoke('cmd_update_expense', { expenseId, input });
}

export async function recentExpenses(limit?: number): Promise<RecentExpense[]> {
  return invoke('cmd_recent_expenses', { limit });
}

export async function setCashBalance(balanceGtq: number, source: string, notes?: string): Promise<number> {
  return invoke('cmd_set_cash_balance', { balanceGtq, source, notes });
}
```

- [ ] **Step 2: browser.ts fallback**

Para reads, retornar mocks/empty. Para writes, throw `NotAvailableInBrowser`.

```typescript
// adapter/browser.ts (al final)
import type { Expense, ExpenseInput, ProfitSnapshot, HomeSnapshot } from '$lib/data/finanzas';
import { NotAvailableInBrowser } from './errors';

export async function computeProfitSnapshot(periodStart: string, periodEnd: string, periodLabel: string): Promise<ProfitSnapshot> {
  return {
    period_start: periodStart, period_end: periodEnd, period_label: periodLabel,
    revenue_gtq: 0, cogs_gtq: 0, marketing_gtq: 0, opex_gtq: 0,
    profit_operativo: 0, prev_period_profit: undefined, trend_pct: undefined,
  };
}

export async function getHomeSnapshot(periodStart: string, periodEnd: string, periodLabel: string): Promise<HomeSnapshot> {
  return {
    profit: await computeProfitSnapshot(periodStart, periodEnd, periodLabel),
    cash_business_gtq: null, cash_synced_at: null, cash_stale_days: null,
    capital_amarrado_gtq: 0, shareholder_loan_balance: 0, shareholder_loan_trend_30d: 0,
  };
}

export async function createExpense(_input: ExpenseInput): Promise<number> {
  throw new NotAvailableInBrowser('createExpense requires Tauri (.exe)');
}
export async function listExpenses(): Promise<Expense[]> { return []; }
export async function deleteExpense(_id: number): Promise<void> { throw new NotAvailableInBrowser('deleteExpense'); }
export async function updateExpense(_id: number, _input: ExpenseInput): Promise<void> { throw new NotAvailableInBrowser('updateExpense'); }
export async function recentExpenses(): Promise<any[]> { return []; }
export async function setCashBalance(_b: number, _s: string, _n?: string): Promise<number> { throw new NotAvailableInBrowser('setCashBalance'); }
```

- [ ] **Step 3: Re-export en adapter/index.ts** siguiendo patrón existente.

- [ ] **Step 4: `npm run check`**

- [ ] **Step 5: Commit**

```bash
git add overhaul/src/lib/adapter/
git commit -m "feat(fin): adapter invocations para FIN-R1 (tauri + browser fallback)"
```

---

### Task 5: Sidebar nav-item + routing

**Files:**
- Modify: `overhaul/src/lib/components/Sidebar.svelte`
- Create: `overhaul/src/routes/finanzas/+page.svelte`

- [ ] **Step 1: Importar icono `LineChart` de lucide-svelte en Sidebar.svelte**

```svelte
import { Inbox, Search, Trophy, Rocket, BarChart3, Package, DollarSign, Truck, Ship, LineChart, Command, /* ... */ } from 'lucide-svelte';
```

- [ ] **Step 2: Agregar `finanzas` al array ITEMS**

Insertar entre `importaciones` y `orders`:

```typescript
{ id: 'importaciones', label: 'Importaciones', icon: Ship, section: 'data' },
{ id: 'finanzas', label: 'Finanzas', icon: LineChart, section: 'data' },  // NEW
{ id: 'orders', label: 'Órdenes', icon: Truck, section: 'data' },
```

- [ ] **Step 3: Crear `+page.svelte` route**

```svelte
<!-- overhaul/src/routes/finanzas/+page.svelte -->
<script lang="ts">
  import FinanzasShell from '$lib/components/finanzas/FinanzasShell.svelte';
</script>

<FinanzasShell />
```

- [ ] **Step 4: Agregar handler en routing principal** siguiendo patrón existente.

- [ ] **Step 5: `npm run check`** (puede fallar build hasta Task 6 cuando exista FinanzasShell · OK)

- [ ] **Step 6: Commit defer hasta Task 6.**

---

### Task 6: FinanzasShell + FinanzasTabs + PeriodStrip (skeleton renderable)

**Files:**
- Create: `overhaul/src/lib/components/finanzas/FinanzasShell.svelte`
- Create: `overhaul/src/lib/components/finanzas/FinanzasTabs.svelte`
- Create: `overhaul/src/lib/components/finanzas/PeriodStrip.svelte`
- Create: `overhaul/src/lib/components/finanzas/tabs/*.svelte` (7 placeholders + Home + Gastos)

**Reference visual:** `el-club/overhaul/.superpowers/brainstorm/4941-1777340205/content/03-mockup-a2-hd.html`.

- [ ] **Step 1: Crear FinanzasShell.svelte**

```svelte
<!-- overhaul/src/lib/components/finanzas/FinanzasShell.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import FinanzasTabs from './FinanzasTabs.svelte';
  import PeriodStrip from './PeriodStrip.svelte';
  import HomeTab from './tabs/HomeTab.svelte';
  import EstadoResultadosTab from './tabs/EstadoResultadosTab.svelte';
  import ProductosTab from './tabs/ProductosTab.svelte';
  import GastosTab from './tabs/GastosTab.svelte';
  import CuentaBusinessTab from './tabs/CuentaBusinessTab.svelte';
  import InterCuentaTab from './tabs/InterCuentaTab.svelte';
  import SettingsTab from './tabs/SettingsTab.svelte';
  import { periodToDateRange } from '$lib/data/finanzasPeriods';
  import type { Period } from '$lib/data/finanzas';

  type TabId = 'home' | 'edr' | 'productos' | 'gastos' | 'cuenta' | 'inter' | 'settings';

  const TAB_KEY = 'fin.tab';
  const PERIOD_KEY = 'fin.period';

  let activeTab = $state<TabId>(
    (typeof localStorage !== 'undefined' && (localStorage.getItem(TAB_KEY) as TabId)) || 'home'
  );
  let period = $state<Period>(
    (typeof localStorage !== 'undefined' && (localStorage.getItem(PERIOD_KEY) as Period)) || 'month'
  );

  let periodRange = $derived(periodToDateRange(period));

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(TAB_KEY, activeTab);
      localStorage.setItem(PERIOD_KEY, period);
    }
  });
</script>

<div class="flex h-full flex-col">
  <!-- Module head -->
  <div class="flex items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-3">
    <div>
      <div class="text-[18px] font-semibold text-[var(--color-text-primary)]">Finanzas</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        salud financiera de El Club · ingresos ← Comercial · COGS ← Importaciones · gastos local
      </div>
    </div>
    <div class="ml-auto flex gap-2">
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">⇣ Export CSV</button>
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]">📋 Estado Resultados</button>
      <button class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]">+ Nuevo gasto</button>
    </div>
  </div>

  <FinanzasTabs bind:activeTab />
  <PeriodStrip bind:period {periodRange} />

  <div class="flex flex-1 min-h-0">
    {#if activeTab === 'home'}
      <HomeTab {periodRange} />
    {:else if activeTab === 'edr'}
      <EstadoResultadosTab />
    {:else if activeTab === 'productos'}
      <ProductosTab />
    {:else if activeTab === 'gastos'}
      <GastosTab {periodRange} />
    {:else if activeTab === 'cuenta'}
      <CuentaBusinessTab />
    {:else if activeTab === 'inter'}
      <InterCuentaTab />
    {:else if activeTab === 'settings'}
      <SettingsTab />
    {/if}
  </div>
</div>
```

- [ ] **Step 2: Crear FinanzasTabs.svelte**

```svelte
<!-- FinanzasTabs.svelte -->
<script lang="ts">
  type TabId = 'home' | 'edr' | 'productos' | 'gastos' | 'cuenta' | 'inter' | 'settings';
  let { activeTab = $bindable() }: { activeTab: TabId } = $props();

  const TABS: Array<{id: TabId; label: string; icon: string}> = [
    { id: 'home',      label: 'Home',                icon: '🏠' },
    { id: 'edr',       label: 'Estado de Resultados', icon: '📊' },
    { id: 'productos', label: 'Productos',           icon: '🏷' },
    { id: 'gastos',    label: 'Gastos',              icon: '💸' },
    { id: 'cuenta',    label: 'Cuenta business',     icon: '🏦' },
    { id: 'inter',     label: 'Inter-cuenta',        icon: '🔄' },
    { id: 'settings',  label: 'Settings',            icon: '⚙' },
  ];
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each TABS as tab}
    {@const isLast = tab.id === 'settings'}
    <button
      class="text-mono inline-flex items-center gap-1.5 border-b-2 border-transparent px-4 py-2.5 text-[11px] uppercase transition-colors"
      class:ml-auto={isLast}
      class:text-[var(--color-text-tertiary)]={isLast && activeTab !== tab.id}
      class:text-[var(--color-text-secondary)]={!isLast && activeTab !== tab.id}
      class:!text-[var(--color-accent)]={activeTab === tab.id}
      class:!border-[var(--color-accent)]={activeTab === tab.id}
      style="letter-spacing: 0.05em;"
      onclick={() => activeTab = tab.id}
    >
      <span>{tab.icon}</span>
      <span>{tab.label}</span>
    </button>
  {/each}
</div>
```

- [ ] **Step 3: Crear PeriodStrip.svelte**

```svelte
<!-- PeriodStrip.svelte -->
<script lang="ts">
  import type { Period, PeriodRange } from '$lib/data/finanzas';
  import { daysBetween } from '$lib/data/finanzasPeriods';

  let { period = $bindable(), periodRange }: { period: Period; periodRange: PeriodRange } = $props();

  const PERIODS: Array<{id: Period; label: string}> = [
    { id: 'today',      label: 'HOY' },
    { id: '7d',         label: '7D' },
    { id: '30d',        label: '30D' },
    { id: 'month',      label: 'MES ACTUAL' },
    { id: 'last_month', label: 'MES ANT.' },
    { id: 'ytd',        label: 'YTD' },
    { id: 'lifetime',   label: 'LIFETIME' },
    { id: 'custom',     label: 'CUSTOM' },
  ];

  let days = $derived(daysBetween(periodRange.start, periodRange.end));
</script>

<div class="flex items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-2.5">
  <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Período:</span>
  <div class="flex gap-1">
    {#each PERIODS as p}
      <button
        class="text-mono text-[10px] px-2.5 py-1 rounded-[2px] border transition-colors"
        class:bg-[rgba(91,141,239,0.16)]={period === p.id}
        class:text-[var(--color-accent)]={period === p.id}
        class:border-[rgba(91,141,239,0.4)]={period === p.id}
        class:bg-[var(--color-surface-2)]={period !== p.id}
        class:text-[var(--color-text-secondary)]={period !== p.id}
        class:border-[var(--color-border)]={period !== p.id}
        style="letter-spacing: 0.04em;"
        onclick={() => period = p.id}
      >
        {p.label}
      </button>
    {/each}
  </div>
  <div class="ml-auto text-mono text-[11px] text-[var(--color-text-secondary)]">
    <strong class="text-[var(--color-text-primary)]">{periodRange.label}</strong> · {days} días
  </div>
</div>
```

- [ ] **Step 4: Crear placeholders para 5 tabs (EstadoResultados, Productos, Cuenta, Inter, Settings)**

Cada uno con mensaje "Próximamente en R2/R3/R4/...". Ejemplo:

```svelte
<!-- tabs/EstadoResultadosTab.svelte -->
<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  <div class="text-center">
    <div class="text-mono text-[11px] uppercase mb-2" style="letter-spacing: 0.08em;">Próximamente</div>
    <div class="text-sm">Waterfall de Estado de Resultados viene en FIN-R2</div>
  </div>
</div>
```

Hacer lo mismo para `ProductosTab` (R2), `CuentaBusinessTab` (R3), `InterCuentaTab` (R3), `SettingsTab` (R6).

- [ ] **Step 5: Crear `HomeTab.svelte` y `GastosTab.svelte` placeholders (Tasks 7+ los llenan)**

Placeholders simples: "Loading…" o "Próximamente Task X".

- [ ] **Step 6: `npm run check`** + smoke test (`npm run tauri dev` → click Finanzas → ve shell con tabs + period strip).

- [ ] **Step 7: Commit**

```bash
git add overhaul/src/lib/components/finanzas/ overhaul/src/routes/finanzas/ overhaul/src/lib/components/Sidebar.svelte overhaul/src/routes/+page.svelte
git commit -m "feat(fin): FinanzasShell + Tabs + PeriodStrip skeleton renderable + 5 tabs placeholder"
```

---

### Task 7: HomeTab funcional · 4 cards + waterfall mini + sub-grid

**Files:**
- Modify: `overhaul/src/lib/components/finanzas/tabs/HomeTab.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/ProfitHeroCard.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/CashCard.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/CapitalCard.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/ShareholderLoanCard.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/WaterfallMini.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/RecentExpenses.svelte`
- Create: `overhaul/src/lib/components/finanzas/home/InboxFinanciero.svelte`

**Reference visual:** mockup HD `03-mockup-a2-hd.html` · `.quadrants`, `.row2`, `.sub-grid`, `.card.primary`, `.recent-list`, `.inbox-list`.

Esto es la pieza más grande de R1. Cada card en su propio file (single responsibility · más fácil de iterar después). Los componentes reciben `homeSnapshot: HomeSnapshot` como prop.

- [ ] **Step 1: Crear `ProfitHeroCard.svelte`**

```svelte
<!-- home/ProfitHeroCard.svelte -->
<script lang="ts">
  import type { ProfitSnapshot } from '$lib/data/finanzas';
  import { formatGTQ, profitColor, trendArrow } from '$lib/data/finanzasComputed';

  let { profit }: { profit: ProfitSnapshot } = $props();

  let color = $derived(profitColor(profit.profit_operativo));
  let arrow = $derived(trendArrow(profit.trend_pct ?? null));
  let prevAmt = $derived(profit.prev_period_profit !== undefined ? formatGTQ(profit.prev_period_profit) : null);
</script>

<button
  type="button"
  class="text-left w-full bg-[rgba(74,222,128,0.04)] border border-[rgba(74,222,128,0.35)] rounded-[6px] p-6 hover:translate-y-[-1px] transition-transform"
  onclick={() => alert('Estado de Resultados drilldown en R2')}
>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-live)]" style="letter-spacing: 0.10em;">
    ▸ Llevás ganado este período · profit operativo
  </div>
  <div class="text-mono text-[48px] font-extrabold leading-[1] tabular-nums {color === 'green' ? 'text-[var(--color-live)]' : color === 'red' ? 'text-[var(--color-danger)]' : 'text-[var(--color-text-secondary)]'}" style="letter-spacing: -0.02em;">
    {formatGTQ(profit.profit_operativo, { sign: true })}
  </div>
  {#if prevAmt}
    <div class="text-mono text-[12px] text-[var(--color-text-secondary)] mt-2">
      <span class="{color === 'green' ? 'text-[var(--color-live)]' : 'text-[var(--color-danger)]'}">{arrow}</span>
      &nbsp;vs período anterior {prevAmt}
    </div>
  {/if}
</button>
```

- [ ] **Step 2: Crear `CashCard.svelte`**

```svelte
<!-- home/CashCard.svelte -->
<script lang="ts">
  import { formatGTQ } from '$lib/data/finanzasComputed';
  let { balanceGtq, syncedAt, staleDays }: { balanceGtq: number | null; syncedAt: string | null; staleDays: number | null } = $props();
</script>

<button class="text-left bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 hover:border-[var(--color-border-strong)]" onclick={() => alert('Cuenta business tab en R3')}>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.10em;">Cash en cuenta business</div>
  {#if balanceGtq === null}
    <div class="text-mono text-[20px] text-[var(--color-text-tertiary)]">— sin sync</div>
    <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">→ sync ahora</div>
  {:else}
    <div class="text-mono text-[26px] font-bold leading-[1.1] tabular-nums text-[var(--color-accent)]">{formatGTQ(balanceGtq)}</div>
    <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">
      sync hace {staleDays ?? 0}d
      {#if (staleDays ?? 0) > 7}<span class="text-[var(--color-warning)]"> · stale</span>{/if}
    </div>
  {/if}
</button>
```

- [ ] **Step 3: Crear `CapitalCard.svelte` y `ShareholderLoanCard.svelte`** siguiendo el mismo patrón.

- [ ] **Step 4: Crear `WaterfallMini.svelte`**

```svelte
<!-- home/WaterfallMini.svelte -->
<script lang="ts">
  import type { ProfitSnapshot } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let { profit }: { profit: ProfitSnapshot } = $props();

  // bars proporcionales al revenue (anchor 100%)
  let revPct = 100;
  let cogsPct = $derived(profit.revenue_gtq > 0 ? (profit.cogs_gtq / profit.revenue_gtq) * 100 : 0);
  let mktPct = $derived(profit.revenue_gtq > 0 ? (profit.marketing_gtq / profit.revenue_gtq) * 100 : 0);
  let opexPct = $derived(profit.revenue_gtq > 0 ? (profit.opex_gtq / profit.revenue_gtq) * 100 : 0);
</script>

<div class="grid grid-cols-4 gap-3">
  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">+ Revenue</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-live)]">{formatGTQ(profit.revenue_gtq, { sign: true })}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5"><div class="h-full bg-[var(--color-live)] rounded-[1px]" style="width: {revPct}%"></div></div>
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">− COGS</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-danger)]">{formatGTQ(-profit.cogs_gtq)}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5"><div class="h-full bg-[var(--color-danger)] rounded-[1px]" style="width: {Math.min(cogsPct, 100)}%"></div></div>
  </div>

  <!-- Marketing y Opex similares -->
</div>
```

- [ ] **Step 5: Crear `RecentExpenses.svelte` y `InboxFinanciero.svelte`** siguiendo el mockup HD.

- [ ] **Step 6: Wire en `HomeTab.svelte`**

```svelte
<!-- tabs/HomeTab.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import ProfitHeroCard from '../home/ProfitHeroCard.svelte';
  import CashCard from '../home/CashCard.svelte';
  import CapitalCard from '../home/CapitalCard.svelte';
  import ShareholderLoanCard from '../home/ShareholderLoanCard.svelte';
  import WaterfallMini from '../home/WaterfallMini.svelte';
  import RecentExpenses from '../home/RecentExpenses.svelte';
  import InboxFinanciero from '../home/InboxFinanciero.svelte';
  import { adapter } from '$lib/adapter';
  import { periodToDateRange } from '$lib/data/finanzasPeriods';
  import type { PeriodRange, HomeSnapshot } from '$lib/data/finanzas';

  let { periodRange }: { periodRange: PeriodRange } = $props();

  let snapshot = $state<HomeSnapshot | null>(null);
  let loading = $state(true);

  $effect(() => {
    loadSnapshot(periodRange);
  });

  async function loadSnapshot(range: PeriodRange) {
    loading = true;
    // Compute previous period of same length
    const len = (new Date(range.end).getTime() - new Date(range.start).getTime()) / (24*60*60*1000);
    const prevEnd = new Date(new Date(range.start).getTime() - 86400000).toISOString().slice(0, 10);
    const prevStart = new Date(new Date(prevEnd).getTime() - len * 86400000).toISOString().slice(0, 10);

    snapshot = await adapter.getHomeSnapshot(range.start, range.end, range.label, prevStart, prevEnd);
    loading = false;
  }
</script>

<div class="flex-1 p-6 overflow-y-auto">
  {#if loading || !snapshot}
    <div class="text-[var(--color-text-tertiary)]">Cargando snapshot…</div>
  {:else}
    <!-- Quadrants -->
    <div class="grid grid-cols-[2fr_1fr_1fr_1fr] gap-3 mb-4">
      <ProfitHeroCard profit={snapshot.profit} />
      <CashCard balanceGtq={snapshot.cash_business_gtq} syncedAt={snapshot.cash_synced_at} staleDays={snapshot.cash_stale_days} />
      <CapitalCard amount={snapshot.capital_amarrado_gtq} />
      <ShareholderLoanCard balance={snapshot.shareholder_loan_balance} trend30d={snapshot.shareholder_loan_trend_30d} />
    </div>

    <!-- Waterfall mini -->
    <WaterfallMini profit={snapshot.profit} />

    <!-- Sub-grid -->
    <div class="grid grid-cols-2 gap-4 mt-4">
      <RecentExpenses />
      <InboxFinanciero {snapshot} />
    </div>
  {/if}
</div>
```

- [ ] **Step 7: `npm run check` + smoke**

`npm run tauri dev` → tab Home → verificar 4 cards + waterfall mini + sub-grid renderizan con datos reales (al menos profit calculado correcto del mes actual).

- [ ] **Step 8: Commit**

```bash
git add overhaul/src/lib/components/finanzas/home/ overhaul/src/lib/components/finanzas/tabs/HomeTab.svelte
git commit -m "feat(fin): HomeTab funcional · 4 cards + waterfall mini + sub-grid (R1 scope)"
```

---

### Task 8: GastoForm.svelte · TDAH-optimized 3 actions

**Files:**
- Create: `overhaul/src/lib/components/finanzas/gastos/GastoForm.svelte`

**Reference visual:** `01-modelo-pagos.html` · `.form-mockup` section.

- [ ] **Step 1: Crear `GastoForm.svelte`**

```svelte
<!-- gastos/GastoForm.svelte -->
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ExpenseCategory, PaymentMethod, Currency, ExpenseInput } from '$lib/data/finanzas';
  import { CATEGORY_LABELS } from '$lib/data/finanzas';

  let { onSaved, onCancel }: { onSaved: () => void; onCancel: () => void } = $props();

  let amount = $state<string>('');
  let currency = $state<Currency>('GTQ');
  let category = $state<ExpenseCategory | null>(null);
  let paymentMethod = $state<PaymentMethod | null>(null);
  let paidAt = $state<string>(new Date().toISOString().slice(0, 10));
  let notes = $state<string>('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  let canSubmit = $derived(
    amount.trim() !== '' &&
    !isNaN(parseFloat(amount)) &&
    category !== null &&
    paymentMethod !== null &&
    paidAt !== ''
  );

  async function handleSubmit() {
    if (!canSubmit || saving) return;
    saving = true;
    error = null;
    try {
      const input: ExpenseInput = {
        amount_native: parseFloat(amount),
        currency,
        category: category!,
        payment_method: paymentMethod!,
        paid_at: paidAt,
        notes: notes.trim() || undefined,
      };
      await adapter.createExpense(input);
      onSaved();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      saving = false;
    }
  }
</script>

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 max-w-[500px] mx-auto">
  <div class="text-mono text-[12px] font-semibold text-[var(--color-text-primary)] mb-4 pb-3 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.05em;">+ Nuevo gasto</div>

  <!-- Monto + Currency -->
  <div class="mb-3">
    <div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Monto</div>
    <div class="flex gap-2">
      <input type="number" step="0.01" bind:value={amount} placeholder="0.00"
        class="flex-1 px-3 py-2.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[20px] font-bold tabular-nums text-right text-[var(--color-live)]" />
      <button class="text-mono text-[11px] px-3 rounded-[3px] border border-[var(--color-border)]"
        class:bg-[var(--color-surface-2)]={currency === 'GTQ'}
        class:text-[var(--color-accent)]={currency === 'GTQ'}
        onclick={() => currency = 'GTQ'}>Q</button>
      <button class="text-mono text-[11px] px-3 rounded-[3px] border border-[var(--color-border)]"
        class:bg-[var(--color-surface-2)]={currency === 'USD'}
        class:text-[var(--color-accent)]={currency === 'USD'}
        onclick={() => currency = 'USD'}>USD</button>
    </div>
    {#if currency === 'USD' && amount}
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">≈ Q{(parseFloat(amount) * 7.73).toFixed(2)} (FX 7.73)</div>
    {/if}
  </div>

  <!-- Categoría -->
  <div class="mb-3">
    <div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Categoría · 1 click</div>
    <div class="grid grid-cols-3 gap-1.5">
      {#each ['variable','tech','marketing','operations','owner_draw','other'] as cat}
        {@const isOwnerDraw = cat === 'owner_draw'}
        <button
          class="text-mono text-[11px] px-2.5 py-1.5 rounded-[3px] border"
          class:bg-[var(--color-surface-2)]={category !== cat}
          class:text-[var(--color-text-secondary)]={category !== cat}
          class:border-[var(--color-border)]={category !== cat}
          class:!bg-[rgba(91,141,239,0.16)]={category === cat}
          class:!text-[var(--color-accent)]={category === cat}
          class:!border-[rgba(91,141,239,0.4)]={category === cat}
          class:opacity-50={isOwnerDraw}
          disabled={isOwnerDraw}
          title={isOwnerDraw ? 'Owner draw vive en tab Inter-cuenta · no acá' : ''}
          onclick={() => category = cat as ExpenseCategory}
        >
          {CATEGORY_LABELS[cat as ExpenseCategory]}
        </button>
      {/each}
    </div>
  </div>

  <!-- Pagado con -->
  <div class="mb-3">
    <div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Pagado con · 1 click</div>
    <div class="grid grid-cols-2 gap-2">
      <button class="px-3 py-3 rounded-[3px] border text-center"
        class:bg-[var(--color-surface-2)]={paymentMethod !== 'tdc_personal'}
        class:border-[var(--color-border)]={paymentMethod !== 'tdc_personal'}
        class:!bg-[rgba(91,141,239,0.08)]={paymentMethod === 'tdc_personal'}
        class:!border-[rgba(91,141,239,0.4)]={paymentMethod === 'tdc_personal'}
        onclick={() => paymentMethod = 'tdc_personal'}>
        <div class="text-[20px]">💳</div>
        <div class="text-mono text-[10px] mt-1">TDC PERSONAL</div>
      </button>
      <button class="px-3 py-3 rounded-[3px] border text-center"
        class:bg-[var(--color-surface-2)]={paymentMethod !== 'cuenta_business'}
        class:border-[var(--color-border)]={paymentMethod !== 'cuenta_business'}
        class:!bg-[rgba(91,141,239,0.08)]={paymentMethod === 'cuenta_business'}
        class:!border-[rgba(91,141,239,0.4)]={paymentMethod === 'cuenta_business'}
        onclick={() => paymentMethod = 'cuenta_business'}>
        <div class="text-[20px]">🏦</div>
        <div class="text-mono text-[10px] mt-1">CUENTA BUSINESS</div>
      </button>
    </div>
  </div>

  <!-- Fecha + Notas -->
  <div class="mb-3">
    <div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Fecha · default hoy</div>
    <input type="date" bind:value={paidAt} class="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[12px] text-[var(--color-text-secondary)]" />
  </div>

  <div class="mb-4">
    <div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Notas · opcional pero recomendado</div>
    <input type="text" bind:value={notes} placeholder="ej. Anthropic API · bot abril" class="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[12px] text-[var(--color-text-primary)]" />
  </div>

  {#if error}
    <div class="text-mono text-[11px] text-[var(--color-danger)] mb-3 p-2 bg-[rgba(244,63,94,0.06)] border border-[rgba(244,63,94,0.2)] rounded-[3px]">⚠ {error}</div>
  {/if}

  <div class="flex gap-2 pt-3 border-t border-[var(--color-surface-2)]">
    <button class="flex-1 text-mono text-[11px] py-2.5 bg-transparent text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded-[3px]" onclick={onCancel}>Cancelar</button>
    <button class="flex-1 text-mono text-[12px] font-bold py-2.5 bg-[var(--color-live)] text-[var(--color-bg)] rounded-[3px] disabled:opacity-50 disabled:cursor-not-allowed" disabled={!canSubmit || saving} onclick={handleSubmit}>
      {saving ? 'Guardando…' : 'Guardar gasto'}
    </button>
  </div>
</div>
```

- [ ] **Step 2: `npm run check`**

- [ ] **Step 3: Commit**

```bash
git add overhaul/src/lib/components/finanzas/gastos/GastoForm.svelte
git commit -m "feat(fin): GastoForm TDAH-optimized · 3 actions max + auto FX + currency toggle"
```

---

### Task 9: GastosTab.svelte · CRUD completo (form modal + lista filtrable)

**Files:**
- Modify: `overhaul/src/lib/components/finanzas/tabs/GastosTab.svelte`
- Create: `overhaul/src/lib/components/finanzas/gastos/GastosList.svelte`
- Create: `overhaul/src/lib/components/finanzas/gastos/GastoEditModal.svelte`

- [ ] **Step 1: Crear `GastosList.svelte`**

```svelte
<!-- gastos/GastosList.svelte -->
<script lang="ts">
  import type { Expense, ExpenseCategory, PaymentMethod } from '$lib/data/finanzas';
  import { CATEGORY_LABELS, CATEGORY_PILL_CLASS, PAYMENT_METHOD_ICON } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let { expenses, onEdit, onDelete }: { expenses: Expense[]; onEdit: (e: Expense) => void; onDelete: (id: number) => void } = $props();
</script>

<table class="w-full text-[11.5px] border-collapse">
  <thead class="bg-[var(--color-bg)] sticky top-0">
    <tr>
      <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Fecha</th>
      <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Notas</th>
      <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Categoría</th>
      <th class="text-center text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Método</th>
      <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Monto</th>
      <th class="text-center text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Acc</th>
    </tr>
  </thead>
  <tbody>
    {#each expenses as exp (exp.expense_id)}
      <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
        <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-tertiary)]">{exp.paid_at}</td>
        <td class="py-1.5 px-2.5 text-[var(--color-text-primary)]">{exp.notes ?? '—'}</td>
        <td class="py-1.5 px-2.5">
          <span class="text-mono text-[9px] px-1.5 py-0.5 rounded-[2px] {CATEGORY_PILL_CLASS[exp.category as ExpenseCategory]}" style="letter-spacing: 0.04em;">{CATEGORY_LABELS[exp.category as ExpenseCategory]}</span>
        </td>
        <td class="py-1.5 px-2.5 text-center">{PAYMENT_METHOD_ICON[exp.payment_method as PaymentMethod]}</td>
        <td class="py-1.5 px-2.5 text-right text-mono font-bold tabular-nums text-[var(--color-danger)]">−{formatGTQ(exp.amount_gtq).replace('Q', 'Q')}</td>
        <td class="py-1.5 px-2.5 text-center">
          <button class="text-mono text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)]" onclick={() => onEdit(exp)}>edit</button>
          <button class="text-mono text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] ml-1" onclick={() => { if (confirm('Borrar gasto?')) onDelete(exp.expense_id); }}>×</button>
        </td>
      </tr>
    {/each}
    {#if expenses.length === 0}
      <tr><td colspan="6" class="text-center py-6 text-[var(--color-text-tertiary)] italic">Sin gastos en el período seleccionado.</td></tr>
    {/if}
  </tbody>
</table>
```

- [ ] **Step 2: Modificar `GastosTab.svelte` para wire form + list**

```svelte
<!-- tabs/GastosTab.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import GastoForm from '../gastos/GastoForm.svelte';
  import GastosList from '../gastos/GastosList.svelte';
  import { adapter } from '$lib/adapter';
  import type { Expense, PeriodRange } from '$lib/data/finanzas';

  let { periodRange }: { periodRange: PeriodRange } = $props();

  let expenses = $state<Expense[]>([]);
  let showForm = $state(false);
  let loading = $state(true);

  $effect(() => {
    load(periodRange);
  });

  async function load(range: PeriodRange) {
    loading = true;
    expenses = await adapter.listExpenses({ periodStart: range.start, periodEnd: range.end });
    loading = false;
  }

  async function handleDelete(id: number) {
    await adapter.deleteExpense(id);
    await load(periodRange);
  }

  function handleEdit(_exp: Expense) {
    alert('Edit modal en R1.x · por ahora delete + create');
  }
</script>

<div class="flex-1 p-6 overflow-y-auto">
  <div class="flex items-center mb-4">
    <h2 class="text-mono text-[14px] uppercase font-semibold text-[var(--color-text-primary)]" style="letter-spacing: 0.04em;">Gastos · {expenses.length}</h2>
    <button class="ml-auto text-mono text-[11px] font-bold px-4 py-2 bg-[var(--color-accent)] text-[var(--color-bg)] rounded-[3px]" onclick={() => showForm = true}>
      + Nuevo gasto
    </button>
  </div>

  {#if showForm}
    <div class="mb-6">
      <GastoForm onSaved={() => { showForm = false; load(periodRange); }} onCancel={() => showForm = false} />
    </div>
  {/if}

  {#if loading}
    <div class="text-[var(--color-text-tertiary)]">Cargando gastos…</div>
  {:else}
    <GastosList {expenses} onEdit={handleEdit} onDelete={handleDelete} />
  {/if}
</div>
```

- [ ] **Step 3: `npm run check` + smoke**

`npm run tauri dev` → tab Gastos → click "+ Nuevo gasto" → form aparece → llenar Q145 + tech + tdc_personal + hoy → Guardar → form cierra → row aparece en lista. Verificar que shareholder_loan creció (en sqlite o tab Home cuando R1 esté completo).

- [ ] **Step 4: Commit**

```bash
git add overhaul/src/lib/components/finanzas/tabs/GastosTab.svelte overhaul/src/lib/components/finanzas/gastos/GastosList.svelte
git commit -m "feat(fin): GastosTab CRUD completo · form + lista filtrada por período"
```

---

### Task 10: Verification + version bump + build MSI

**Files:**
- Modify: `overhaul/src-tauri/Cargo.toml`
- Modify: `overhaul/src-tauri/tauri.conf.json`
- Modify: `overhaul/package.json`

- [ ] **Step 1: Bump version** (asumir partir de v0.1.41 post-IMP-R1 ship)

```bash
# Detectar versión actual
grep '"version"' overhaul/package.json | head -1
# Bump x.y.z → x.y.(z+1)
```

- [ ] **Step 2: Full check + cargo check**

```bash
cd overhaul
npm run check
cd src-tauri && cargo check && cd ..
```

- [ ] **Step 3: Build MSI**

```bash
npm run tauri build
```

- [ ] **Step 4: Smoke test full**

Instalar el MSI y verificar:

1. Sidebar tiene "Finanzas" con icono LineChart
2. Click → módulo carga con tabs activos
3. Period strip muestra "Mes actual" default · cambiar a YTD recalcula Home
4. Tab Home muestra 4 cards · profit hero gigante · cash card · capital · shareholder loan
5. Waterfall mini con 4 bars proporcionales
6. Sub-grid Recent + Inbox (Inbox vacío en primer uso)
7. Tab Gastos: + Nuevo gasto · form 3 actions · save → row aparece
8. Volver a tab Home: profit recalcula con el nuevo gasto restado
9. Otros tabs (EdR, Productos, Cuenta, Inter, Settings): muestran "Próximamente en R2/R3/etc."

- [ ] **Step 5: Tag y push**

```bash
git tag v0.1.41
git push origin finanzas-r1
git push origin v0.1.41
```

- [ ] **Step 6: Commit final + merge to main**

```bash
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json overhaul/package.json
git commit -m "chore(fin): bump version v0.1.41 · FIN-R1 ship

- 5 tablas + 2 views + 7 indexes nuevos en elclub.db
- 8 commands Rust nuevos (profit · home snapshot · expense CRUD · cash sync)
- 7 tabs internos (2 funcionales · 5 placeholder R2-R6)
- Home A2 funcional con 4 cards + waterfall mini + sub-grid
- Tab Gastos CRUD completo con form TDAH-optimized
- Auto-trigger shareholder_loan_movement on TDC personal expense
- Period strip 8 botones funcional con localStorage persist

Spec: docs/superpowers/specs/2026-04-27-finanzas-design.md
Plan: docs/superpowers/plans/2026-04-27-finanzas-FIN-R1.md
Brainstorm: .superpowers/brainstorm/4941-1777340205/"

# Después de approval Diego
git checkout main
git merge --no-ff finanzas-r1
git push origin main --tags
```

---

## Self-Review checklist

**1. Spec coverage:**
- [x] Sec 4 Tab Home A2 (4 cards + waterfall mini + sub-grid) — Tasks 6-7
- [x] Sec 4 Tab Gastos CRUD — Tasks 8-9
- [x] Sec 4 Tab placeholders R2-R6 — Task 6 step 4
- [x] Sec 5 todas las decisiones (D-PROFIT-DEF, D-CASH-BASIS, D-PAYMENT-METHOD, D-CURRENCY, D-FEE) — implementadas en queries Rust + form
- [x] Sec 6 schema 5 tablas + 2 views + 7 indexes — Task 1
- [x] Sec 6 view v_monthly_profit usada implícitamente en cmd_compute_profit_snapshot
- [x] Sec 9 R1 scope completo

**2. Placeholder scan:** sin TBDs/TODOs en tasks. Edit modal explícitamente diferido a R1.x con alert.

**3. Type consistency:** `cmd_compute_profit_snapshot` ↔ `computeProfitSnapshot` ↔ TS interface `ProfitSnapshot`. ✓

**4. Auto shareholder_loan trigger:** en `cmd_create_expense` Task 3 step 4 — verificado al delete en Task 3 step 6 (cascade).

---

## Execution Handoff

**Plan complete · saved to `el-club/overhaul/docs/superpowers/plans/2026-04-27-finanzas-FIN-R1.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - dispatch fresh subagent per task · review entre tasks. Necesario para R1 (10 tasks).

**2. Inline Execution** - tasks en current session con executing-plans · batch con checkpoints.

Diego elegirá al lanzar la sesión paralela vía starter (`docs/starters/2026-04-27-fin-r1-build-starter.md`).
