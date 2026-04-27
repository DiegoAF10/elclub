<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Period, PulsoKPIs } from '$lib/data/comercial';
  import { computePulsoKPIs, resolvePeriod, resolvePreviousRange } from '$lib/data/kpis';
  import PeriodSelector from './PeriodSelector.svelte';

  interface Props {
    period?: Period;
    setPeriod?: (p: Period) => void;
  }
  let { period = '30d', setPeriod }: Props = $props();
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
    {@const tConv = fmtTrend(kpis.trends.conversionRate * 100)}
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Revenue</span>
      <span class="text-mono font-semibold tabular-nums">{fmtMoney(kpis.revenue)}</span>
      <span class="text-[10.5px]" style="color: var(--color-{tRev.cls === 'up' ? 'success' : tRev.cls === 'down' ? 'danger' : 'text-tertiary'});">{tRev.sign}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Órdenes</span>
      <span class="text-mono font-semibold tabular-nums">{kpis.orders}</span>
      <span class="text-[10.5px]" style="color: var(--color-{tOrd.cls === 'up' ? 'success' : tOrd.cls === 'down' ? 'danger' : 'text-tertiary'});">{tOrd.sign}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Leads</span>
      <span class="text-mono font-semibold tabular-nums">{kpis.leads}</span>
      <span class="text-[10.5px]" style="color: var(--color-{tLead.cls === 'up' ? 'success' : tLead.cls === 'down' ? 'danger' : 'text-tertiary'});">{tLead.sign}</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-display text-[9.5px] text-[var(--color-text-muted)]">Conv</span>
      <span class="text-mono font-semibold tabular-nums">{fmtPct(kpis.conversionRate)}</span>
      <span class="text-[10.5px]" style="color: var(--color-{tConv.cls === 'up' ? 'success' : tConv.cls === 'down' ? 'danger' : 'text-tertiary'});">{tConv.sign}</span>
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
    <PeriodSelector value={period} onChange={(p) => setPeriod?.(p)} />
  </div>
</div>
