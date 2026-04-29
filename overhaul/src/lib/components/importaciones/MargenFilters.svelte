<script lang="ts">
  import type { MargenFilter } from '$lib/adapter/types';

  interface Props {
    filter: MargenFilter;
    suppliers: string[];      // distinct values from data, populated by parent
    onChange: (next: MargenFilter) => void;
  }

  let { filter, suppliers, onChange }: Props = $props();

  // Local state mirrors filter (sync via $effect)
  let periodFrom = $state(filter.periodFrom ?? '');
  let periodTo = $state(filter.periodTo ?? '');
  let supplier = $state(filter.supplier ?? '');
  let includePipeline = $state(filter.includePipeline ?? false);

  function applyFilter() {
    onChange({
      periodFrom: periodFrom || undefined,
      periodTo: periodTo || undefined,
      supplier: supplier || undefined,
      includePipeline,
    });
  }

  function clearFilter() {
    periodFrom = '';
    periodTo = '';
    supplier = '';
    includePipeline = false;
    applyFilter();
  }

  let isActive = $derived(
    periodFrom !== '' || periodTo !== '' || supplier !== '' || includePipeline
  );
</script>

<div class="flex items-center gap-3 mb-4 p-3 bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px]">
  <!-- Period from -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Desde
    </span>
    <input
      type="date"
      bind:value={periodFrom}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    />
  </label>

  <!-- Period to -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Hasta
    </span>
    <input
      type="date"
      bind:value={periodTo}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    />
  </label>

  <!-- Supplier -->
  <label class="flex items-center gap-1.5">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Supplier
    </span>
    <select
      bind:value={supplier}
      onchange={applyFilter}
      class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
    >
      <option value="">Todos</option>
      {#each suppliers as s}
        <option value={s}>{s}</option>
      {/each}
    </select>
  </label>

  <!-- Include pipeline toggle -->
  <label class="flex items-center gap-1.5 cursor-pointer ml-2">
    <input
      type="checkbox"
      bind:checked={includePipeline}
      onchange={applyFilter}
      class="accent-[var(--color-accent)]"
    />
    <span class="text-mono text-[10.5px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.06em;">
      Incluir pipeline (paid/arrived · margen estimado)
    </span>
  </label>

  <!-- Clear button -->
  {#if isActive}
    <button
      onclick={clearFilter}
      class="ml-auto text-mono text-[10px] px-2 py-1 rounded-[2px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]"
      style="letter-spacing: 0.06em;"
    >
      ✕ LIMPIAR
    </button>
  {/if}
</div>
