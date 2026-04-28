<script lang="ts">
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let {
    balanceGtq,
    syncedAt,
    staleDays,
  }: {
    balanceGtq: number | null;
    syncedAt: string | null;
    staleDays: number | null;
  } = $props();

  let stalePill = $derived(
    staleDays === null ? null :
    staleDays > 14 ? 'crit' :
    staleDays > 7  ? 'warn' :
                     'fresh'
  );
</script>

<button
  type="button"
  class="text-left bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 hover:border-[var(--color-border-strong)] transition-colors"
  title="Drilldown a Cuenta business (R3)"
>
  <div class="text-mono text-[9.5px] uppercase mb-2 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.10em;">Cash en cuenta business</div>
  {#if balanceGtq === null}
    <div class="text-mono text-[20px] text-[var(--color-text-tertiary)]">— sin sync</div>
    <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">→ sync ahora (R3)</div>
  {:else}
    <div class="text-mono text-[26px] font-bold leading-[1.1] tabular-nums text-[var(--color-accent)]">{formatGTQ(balanceGtq)}</div>
    <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">
      sync hace {staleDays ?? 0}d
      {#if stalePill === 'warn'}<span class="text-[var(--color-warning)]"> · stale</span>{/if}
      {#if stalePill === 'crit'}<span class="text-[var(--color-danger)]"> · muy stale</span>{/if}
    </div>
  {/if}
</button>
