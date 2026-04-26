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
