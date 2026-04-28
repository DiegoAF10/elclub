import type { ProfitSnapshot, PeriodRange } from './finanzas';

export function formatGTQ(amount: number | null | undefined, opts: { sign?: boolean } = {}): string {
  if (amount === null || amount === undefined) return '—';
  const rounded = Math.round(amount);
  const sign = opts.sign && rounded > 0 ? '+' : '';
  const abs = Math.abs(rounded);
  const formatted = abs.toLocaleString('es-GT');
  const prefix = rounded < 0 ? '−' : '';
  return `${sign}${prefix}Q${formatted}`;
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

export function computeProfitSnapshot(
  revenue_gtq: number,
  cogs_gtq: number,
  marketing_gtq: number,
  opex_gtq: number,
  prev_profit?: number,
  period?: PeriodRange,
): ProfitSnapshot {
  const profit = revenue_gtq - cogs_gtq - marketing_gtq - opex_gtq;
  const trend = prev_profit !== undefined ? trendPct(profit, prev_profit) : null;
  const p = period ?? { start: '', end: '', label: '' };
  return {
    period_start: p.start,
    period_end: p.end,
    period_label: p.label,
    revenue_gtq,
    cogs_gtq,
    marketing_gtq,
    opex_gtq,
    profit_operativo: profit,
    prev_period_profit: prev_profit,
    trend_pct: trend ?? undefined,
  };
}
