<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { BatchMargenSummary, MargenFilter, MargenPulso } from '$lib/adapter/types';
  import BatchMarginCard from '../BatchMarginCard.svelte';
  import MargenFilters from '../MargenFilters.svelte';

  interface Props {
    refreshTrigger?: number;
  }

  let { refreshTrigger = 0 }: Props = $props();

  let filter = $state<MargenFilter>({});
  let summaries = $state<BatchMargenSummary[]>([]);
  let pulso = $state<MargenPulso | null>(null);
  let loading = $state(false);
  let errorMsg = $state<string | null>(null);
  let sortBy = $state<'paid_desc' | 'margen_desc' | 'margen_asc' | 'revenue_desc'>('paid_desc');

  // Distinct suppliers for filter dropdown (derived from current data)
  let suppliers = $derived(
    Array.from(new Set(summaries.map(s => s.supplier))).sort()
  );

  // Sorted view of summaries
  let sortedSummaries = $derived(
    [...summaries].sort((a, b) => {
      switch (sortBy) {
        case 'paid_desc':
          return (b.paidAt ?? '').localeCompare(a.paidAt ?? '');
        case 'margen_desc':
          return (b.margenPct ?? -Infinity) - (a.margenPct ?? -Infinity);
        case 'margen_asc':
          return (a.margenPct ?? Infinity) - (b.margenPct ?? Infinity);
        case 'revenue_desc':
          return b.revenueTotalGtq - a.revenueTotalGtq;
      }
    })
  );

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      const [list, pulsoData] = await Promise.all([
        adapter.getMargenReal(filter),
        adapter.getMargenPulso(),
      ]);
      summaries = list;
      pulso = pulsoData;
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    // Re-load on mount, on filter change, or on parent refreshTrigger bump
    void refreshTrigger;
    void filter;
    load();
  });

  function handleFilterChange(next: MargenFilter) {
    filter = next;
  }

  function handleViewSales(importId: string) {
    // TODO future: cross-module nav to Comercial filtered by sale_ids from this batch
    // For now, log + alert (open question for Diego per spec ambiguity · R3 Open Questions Q2)
    console.log('TODO: navigate to Comercial filtered by import_id', importId);
    alert(`Cross-module nav a Comercial filtrado por ${importId} pendiente · ver Open questions plan IMP-R3`);
  }

  function handleViewPending(importId: string) {
    // TODO future: open detail subtab in Importaciones with pending items preview (R3 Open Questions Q3)
    console.log('TODO: open detail with pending items for', importId);
    alert(`Drilldown a items pendientes de ${importId} pendiente · ver Open questions plan IMP-R3`);
  }

  function fmtGtq(n: number | null | undefined): string {
    if (n === null || n === undefined) return 'Q—';
    return 'Q' + Math.round(n).toLocaleString('es-GT');
  }

  function fmtPct(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}${n.toFixed(0)}%`;
  }
</script>

<div class="p-4">
  <!-- Header: title + sort dropdown -->
  <header class="flex items-baseline justify-between mb-3">
    <div>
      <h2 class="text-[15px] font-semibold text-[var(--color-text-primary)] mb-0.5">
        Margen real
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        Cross-Comercial · revenue × landed cost per batch closed · feed FIN-Rx
      </p>
    </div>
    <label class="flex items-center gap-2">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Sort
      </span>
      <select
        bind:value={sortBy}
        class="text-mono text-[11px] px-2 py-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[var(--color-text-primary)]"
      >
        <option value="paid_desc">Paid date ↓</option>
        <option value="margen_desc">Margen % ↓</option>
        <option value="margen_asc">Margen % ↑</option>
        <option value="revenue_desc">Revenue ↓</option>
      </select>
    </label>
  </header>

  <!-- Pulso bar: YTD aggregates -->
  {#if pulso}
    <div class="grid grid-cols-5 gap-2 mb-4 p-3 bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px]">
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Batches YTD</div>
        <div class="text-mono text-[16px] tabular-nums text-[var(--color-text-primary)] font-semibold">{pulso.nBatchesClosed}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Revenue YTD</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-text-primary)] font-semibold">{fmtGtq(pulso.revenueTotalYtdGtq)}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Landed YTD</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-text-primary)]">{fmtGtq(pulso.landedTotalYtdGtq)}</div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Margen total</div>
        <div class="text-mono text-[14px] tabular-nums font-semibold"
          style="color: {pulso.margenTotalYtdGtq >= 0 ? 'var(--color-terminal)' : 'var(--color-danger)'};">
          {fmtGtq(pulso.margenTotalYtdGtq)}
          <span class="text-[11px]">({fmtPct(pulso.margenPctAvg)})</span>
        </div>
      </div>
      <div>
        <div class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Capital amarrado</div>
        <div class="text-mono text-[14px] tabular-nums text-[var(--color-warning)]">{fmtGtq(pulso.capitalAmarradoGtq)}</div>
      </div>
    </div>

    <!-- Best/worst batch chips (if any) -->
    {#if pulso.bestBatchId || pulso.worstBatchId}
      <div class="flex gap-3 mb-3 text-[11px]">
        {#if pulso.bestBatchId}
          <span class="text-mono text-[10.5px] px-2 py-1 rounded-[2px] bg-[color-mix(in_srgb,var(--color-terminal)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-terminal)_30%,transparent)] text-[var(--color-terminal)]">
            ● BEST: {pulso.bestBatchId} · {fmtPct(pulso.bestBatchMargenPct)}
          </span>
        {/if}
        {#if pulso.worstBatchId && pulso.worstBatchId !== pulso.bestBatchId}
          <span class="text-mono text-[10.5px] px-2 py-1 rounded-[2px] bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)] text-[var(--color-danger)]">
            ● WORST: {pulso.worstBatchId} · {fmtPct(pulso.worstBatchMargenPct)}
          </span>
        {/if}
      </div>
    {/if}
  {/if}

  <!-- Filter bar -->
  <MargenFilters {filter} {suppliers} onChange={handleFilterChange} />

  <!-- Body: cards list / loading / empty / error -->
  {#if loading}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)] p-8 text-center">
      Cargando margen real...
    </div>
  {:else if errorMsg}
    <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
      ⚠ {errorMsg}
    </div>
  {:else if sortedSummaries.length === 0}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)] p-8 text-center border border-dashed border-[var(--color-border)] rounded-[4px]">
      <div class="mb-2">Sin batches cerrados aún</div>
      <div class="text-[10.5px]">
        Margen real disponible cuando un import pasa a status='closed'.<br/>
        {#if !filter.includePipeline}
          O activá <strong>"Incluir pipeline"</strong> arriba para ver paid/arrived con margen estimado.
        {/if}
      </div>
    </div>
  {:else}
    <div>
      {#each sortedSummaries as summary (summary.importId)}
        <BatchMarginCard
          {summary}
          onViewSales={handleViewSales}
          onViewPending={handleViewPending}
        />
      {/each}
    </div>
  {/if}
</div>
