<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  import { STATUS_LABELS, STATUS_PROGRESS } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    isActive: boolean;
    onSelect: (id: string) => void;
  }

  let { imp, isActive, onSelect }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let costLabel = $derived(computeCostLabel(imp));
  // cancelled batches: progressTicks = 0 (empty bar). Spec acknowledges this is acceptable until a real cancelled batch exists.
  let progressTicks = $derived(STATUS_PROGRESS[imp.status as keyof typeof STATUS_PROGRESS] || 0);

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function computeCostLabel(i: Import): {text: string; color: 'green' | 'amber' | 'muted'} {
    if (i.status === 'closed' && i.unit_cost) {
      return { text: `Q${Math.round(i.unit_cost)}/u`, color: 'green' };
    }
    if (i.status === 'paid' || i.status === 'in_transit' || i.status === 'arrived') {
      return { text: '~Q145?', color: 'amber' };
    }
    return { text: 'acumulando', color: 'muted' };
  }

  function statusPillClass(status: string): string {
    return {
      closed:     'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      arrived:    'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      paid:       'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      draft:      'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled:  'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] || 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>

<button
  type="button"
  class="block w-full border-b border-[var(--color-surface-2)] px-3.5 py-2.5 text-left transition-colors hover:bg-[var(--color-surface-1)]"
  class:bg-[var(--color-surface-2)]={isActive}
  class:border-l-2={isActive}
  class:border-l-[var(--color-accent)]={isActive}
  class:!pl-3={isActive}
  onclick={() => onSelect(imp.import_id)}
>
  <!-- Top row: ID + cost label -->
  <div class="flex items-baseline justify-between mb-1">
    <span class="text-mono text-[12px] font-semibold text-[var(--color-text-primary)]">{imp.import_id}</span>
    <span class="text-mono text-[11px] font-semibold tabular-nums {
      costLabel.color === 'green'
        ? 'text-[var(--color-live)]'
        : costLabel.color === 'amber'
          ? 'text-[var(--color-warning)]'
          : 'text-[var(--color-text-tertiary)]'
    }">{costLabel.text}</span>
  </div>

  <!-- Meta row: supplier · usd · units + status pill -->
  <div class="flex justify-between items-center gap-2 mb-1">
    <span class="text-[11px] text-[var(--color-text-secondary)] truncate">
      {imp.supplier} · ${imp.bruto_usd?.toFixed(0) ?? '—'} · {imp.n_units ?? 0}u
    </span>
    <span class="text-mono text-[9px] uppercase tracking-wider rounded-[2px] px-1.5 py-0.5 inline-flex items-center gap-1 {statusPillClass(imp.status)}">
      <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
      {STATUS_LABELS[imp.status as keyof typeof STATUS_LABELS]}
    </span>
  </div>

  <!-- Bottom: mini-progress + lead time -->
  <div class="flex items-center gap-2">
    <div class="flex gap-0.5 flex-1">
      {#each [1,2,3,4,5] as i}
        <div class="h-[3px] flex-1 rounded-[1px] {
          i < progressTicks ? 'bg-[var(--color-live)]' :
          i === progressTicks ? 'bg-[var(--color-warning)]' :
          'bg-[var(--color-surface-2)]'
        }"></div>
      {/each}
    </div>
    {#if leadDays !== null}
      <span class="text-mono text-[9.5px] {
        imp.status === 'closed' ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'
      }">
        {leadDays}d{imp.status === 'closed' ? ' ✓' : ''}
      </span>
    {/if}
  </div>
</button>
