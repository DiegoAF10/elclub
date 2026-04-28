<script lang="ts">
  // Narrowed to match ImportDetailPane (Pagos/Timeline deferred to IMP-R5+ supplier scorecard build).
  type SubtabId = 'overview' | 'items' | 'costos';

  interface Props {
    activeSubtab: SubtabId;
    itemsCount: number;
  }

  let { activeSubtab = $bindable(), itemsCount }: Props = $props();

  let SUBTABS = $derived([
    { id: 'overview' as SubtabId, label: 'Overview',  count: undefined },
    { id: 'items'    as SubtabId, label: 'Items',     count: itemsCount },
    { id: 'costos'   as SubtabId, label: 'Costos',    count: undefined },
  ]);
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each SUBTABS as st}
    <button
      class="text-mono inline-flex items-baseline gap-1.5 border-b-2 border-transparent px-3.5 py-2.5 text-[10.5px] uppercase transition-colors"
      class:!text-[var(--color-accent)]={activeSubtab === st.id}
      class:!border-[var(--color-accent)]={activeSubtab === st.id}
      class:text-[var(--color-text-secondary)]={activeSubtab !== st.id}
      style="letter-spacing: 0.05em;"
      onclick={() => activeSubtab = st.id}
    >
      {st.label}
      {#if st.count !== undefined && st.count > 0}
        <span class="text-[9.5px] opacity-70">{st.count}</span>
      {/if}
    </button>
  {/each}
</div>
