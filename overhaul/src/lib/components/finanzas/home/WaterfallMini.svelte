<script lang="ts">
  import type { ProfitSnapshot } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let { profit }: { profit: ProfitSnapshot } = $props();

  function pct(part: number, whole: number): number {
    if (whole <= 0) return 0;
    return Math.min(100, Math.round((Math.abs(part) / whole) * 100));
  }

  let revPct = 100;
  let cogsPct = $derived(pct(profit.cogs_gtq, profit.revenue_gtq));
  let mktPct = $derived(pct(profit.marketing_gtq, profit.revenue_gtq));
  let opexPct = $derived(pct(profit.opex_gtq, profit.revenue_gtq));
</script>

<div class="grid grid-cols-4 gap-3">
  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">+ Revenue</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-live)]">{formatGTQ(profit.revenue_gtq, { sign: true })}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5">
      <div class="h-full bg-[var(--color-live)] rounded-[1px]" style="width: {revPct}%"></div>
    </div>
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">− COGS</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-danger)]">{formatGTQ(-profit.cogs_gtq)}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5">
      <div class="h-full bg-[var(--color-danger)] rounded-[1px]" style="width: {cogsPct}%"></div>
    </div>
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">− Marketing</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-warning)]">{formatGTQ(-profit.marketing_gtq)}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5">
      <div class="h-full bg-[var(--color-warning)] rounded-[1px]" style="width: {mktPct}%"></div>
    </div>
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-3">
    <div class="flex justify-between items-baseline">
      <span class="text-mono text-[9px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.06em;">− Opex</span>
      <span class="text-mono text-[14px] font-bold tabular-nums text-[var(--color-accent)]">{formatGTQ(-profit.opex_gtq)}</span>
    </div>
    <div class="h-[3px] bg-[var(--color-surface-2)] rounded-[1px] mt-1.5">
      <div class="h-full bg-[var(--color-accent)] rounded-[1px]" style="width: {opexPct}%"></div>
    </div>
  </div>
</div>
