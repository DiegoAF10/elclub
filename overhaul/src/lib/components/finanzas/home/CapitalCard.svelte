<script lang="ts">
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let { amount }: { amount: number } = $props();
</script>

<button
  type="button"
  class="text-left bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 hover:border-[var(--color-border-strong)] transition-colors"
  title="Drilldown a Importaciones"
>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.10em;">Capital amarrado</div>
  <div class="text-mono text-[26px] font-bold leading-[1.1] tabular-nums text-[var(--color-warning)]">{formatGTQ(amount)}</div>
  <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">imports en estado <code>paid</code></div>
</button>
