<script lang="ts">
  import type { ProfitSnapshot } from '$lib/data/finanzas';
  import { formatGTQ, profitColor, trendArrow } from '$lib/data/finanzasComputed';

  let { profit }: { profit: ProfitSnapshot } = $props();

  let color = $derived(profitColor(profit.profit_operativo));
  let arrow = $derived(trendArrow(profit.trend_pct ?? null));
  let prevAmt = $derived(
    profit.prev_period_profit !== undefined && profit.prev_period_profit !== null
      ? formatGTQ(profit.prev_period_profit)
      : null
  );

  let heroColorClass = $derived(
    color === 'green' ? 'text-[var(--color-live)]' :
    color === 'red'   ? 'text-[var(--color-danger)]' :
                        'text-[var(--color-text-secondary)]'
  );

  let trendColorClass = $derived(
    color === 'green' ? 'text-[var(--color-live)]' :
    color === 'red'   ? 'text-[var(--color-danger)]' :
                        'text-[var(--color-text-tertiary)]'
  );
</script>

<button
  type="button"
  class="text-left bg-[rgba(74,222,128,0.04)] border border-[rgba(74,222,128,0.35)] rounded-[6px] p-6 hover:translate-y-[-1px] transition-transform"
  title="Drilldown a Estado de Resultados (R2)"
>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-live)]" style="letter-spacing: 0.10em;">
    ▸ Llevás ganado este período · profit operativo
  </div>
  <div class="text-mono text-[48px] font-extrabold leading-[1] tabular-nums {heroColorClass}" style="letter-spacing: -0.02em;">
    {formatGTQ(profit.profit_operativo, { sign: true })}
  </div>
  {#if prevAmt}
    <div class="text-mono text-[12px] text-[var(--color-text-secondary)] mt-2">
      <span class="{trendColorClass}">{arrow}</span>
      &nbsp;vs período anterior {prevAmt}
    </div>
  {:else}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)] mt-2">
      sin período anterior comparable todavía
    </div>
  {/if}
</button>
