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
  paid_at: string;
  notes: string | null;
  source: ExpenseSource;
  source_ref: string | null;
  created_at: string;
}

export interface ExpenseInput {
  amount_native: number;
  currency: Currency;
  fx_used?: number;
  category: ExpenseCategory;
  payment_method: PaymentMethod;
  paid_at: string;
  notes?: string;
}

export type Period = 'today' | '7d' | '30d' | 'month' | 'last_month' | 'ytd' | 'lifetime' | 'custom';

export interface PeriodRange {
  start: string;
  end: string;
  label: string;
}

export interface ProfitSnapshot {
  period: PeriodRange;
  revenue_gtq: number;
  cogs_gtq: number;
  marketing_gtq: number;
  opex_gtq: number;
  profit_operativo: number;
  prev_period_profit?: number;
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

export interface RecentExpense {
  expense_id: number;
  paid_at: string;
  category: ExpenseCategory;
  payment_method: PaymentMethod;
  amount_gtq: number;
  notes: string | null;
}

export type InboxSeverity = 'crit' | 'warn' | 'info' | 'strat';

export interface FinanzasInboxEvent {
  event_id: string;
  severity: InboxSeverity;
  title: string;
  sub: string;
  action_label?: string;
  action_target?: string;
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

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  tdc_personal: 'TDC personal',
  cuenta_business: 'Cuenta business',
};
