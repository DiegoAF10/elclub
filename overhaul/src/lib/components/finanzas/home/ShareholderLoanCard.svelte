<script lang="ts">
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let {
    balance,
    trend30d,
  }: {
    balance: number;
    trend30d: number;
  } = $props();
</script>

<button
  type="button"
  class="text-left bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 hover:border-[var(--color-border-strong)] transition-colors"
  title="Drilldown a Inter-cuenta (R3)"
>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.10em;">Te debe a vos</div>
  <div class="text-mono text-[26px] font-bold leading-[1.1] tabular-nums text-[var(--color-text-secondary)]">{formatGTQ(balance)}</div>
  <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">
    {#if trend30d > 0}
      <span class="text-[var(--color-warning)]">+{formatGTQ(trend30d)}</span> últimos 30d
    {:else if trend30d < 0}
      <span class="text-[var(--color-live)]">{formatGTQ(trend30d)}</span> recoupment 30d
    {:else}
      sin movimientos 30d
    {/if}
  </div>
</button>
