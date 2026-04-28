<script lang="ts">
  import type { Period, PeriodRange } from '$lib/data/finanzas';
  import { daysBetween } from '$lib/data/finanzasPeriods';

  let {
    period = $bindable<Period>(),
    periodRange,
  }: { period: Period; periodRange: PeriodRange } = $props();

  const PERIODS: Array<{ id: Period; label: string }> = [
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
    {#each PERIODS as p (p.id)}
      {@const isActive = period === p.id}
      <button
        type="button"
        class="text-mono text-[10px] px-2.5 py-1 rounded-[2px] border transition-colors"
        class:bg-[rgba(91,141,239,0.16)]={isActive}
        class:text-[var(--color-accent)]={isActive}
        class:border-[rgba(91,141,239,0.4)]={isActive}
        class:bg-[var(--color-surface-2)]={!isActive}
        class:text-[var(--color-text-secondary)]={!isActive}
        class:border-[var(--color-border)]={!isActive}
        style="letter-spacing: 0.04em;"
        onclick={() => period = p.id}
        disabled={p.id === 'custom'}
        title={p.id === 'custom' ? 'Custom range en R2' : ''}
      >
        {p.label}
      </button>
    {/each}
  </div>
  <div class="ml-auto text-mono text-[11px] text-[var(--color-text-secondary)]">
    <strong class="text-[var(--color-text-primary)]">{periodRange.label}</strong> · {days} días
  </div>
</div>
