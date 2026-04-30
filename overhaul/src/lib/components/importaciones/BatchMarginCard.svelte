<script lang="ts">
  import type { BatchMargenSummary } from '$lib/adapter/types';

  interface Props {
    summary: BatchMargenSummary;
    onViewSales?: (importId: string) => void;
    onViewPending?: (importId: string) => void;
  }

  let { summary, onViewSales, onViewPending }: Props = $props();

  // Format helpers
  function fmtGtq(n: number | null | undefined): string {
    if (n === null || n === undefined) return 'Q—';
    return 'Q' + Math.round(n).toLocaleString('es-GT');
  }

  function fmtPct(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}${n.toFixed(0)}%`;
  }

  // Color logic for margen
  let margenColor = $derived(
    summary.margenPct === null ? 'var(--color-text-tertiary)' :
    summary.margenPct >= 50 ? 'var(--color-terminal)' :
    summary.margenPct >= 20 ? 'var(--color-warning)' :
    summary.margenPct >= 0 ? 'var(--color-text-primary)' :
    'var(--color-danger)'
  );

  let statusColor = $derived(
    summary.status === 'closed' ? 'var(--color-terminal)' :
    summary.status === 'arrived' ? 'var(--color-info)' :
    summary.status === 'paid' ? 'var(--color-warning)' :
    'var(--color-text-tertiary)'
  );
</script>

<article class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 mb-3 hover:border-[var(--color-border-strong)] transition-colors">
  <!-- Header: import_id + n_units + status pill -->
  <header class="flex items-center justify-between mb-3 pb-2 border-b border-[var(--color-surface-2)]">
    <div class="flex items-baseline gap-3">
      <h3 class="text-mono text-[13px] font-semibold text-[var(--color-text-primary)] tabular-nums">
        {summary.importId}
      </h3>
      <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        {summary.nUnits ?? '—'}u · {summary.supplier}
      </span>
    </div>
    <span class="text-mono text-[9.5px] uppercase font-semibold px-2 py-0.5 rounded-[2px]"
      style="letter-spacing: 0.08em; color: {statusColor}; background: color-mix(in srgb, {statusColor} 12%, transparent); border: 1px solid color-mix(in srgb, {statusColor} 30%, transparent);">
      ● {summary.status}
    </span>
  </header>

  <!-- Body: 3 main rows + secondary 2 rows -->
  <div class="space-y-1.5 text-[12px]">
    <!-- Revenue -->
    <div class="flex items-center justify-between">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Revenue Comercial
      </span>
      <div class="flex items-baseline gap-2">
        <span class="text-mono text-[13px] tabular-nums text-[var(--color-text-primary)] font-semibold">
          {fmtGtq(summary.revenueTotalGtq)}
        </span>
        <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums">
          ({summary.nSalesLinked} ventas · {summary.nItemsLinked} items)
        </span>
      </div>
    </div>

    <!-- Landed total -->
    <div class="flex items-center justify-between">
      <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
        Landed total
      </span>
      <span class="text-mono text-[13px] tabular-nums text-[var(--color-text-primary)]">
        {fmtGtq(summary.totalLandedGtq)}
      </span>
    </div>

    <!-- Margen bruto -->
    <div class="flex items-center justify-between pt-1.5 border-t border-[var(--color-surface-2)]">
      <span class="text-mono text-[10px] uppercase font-semibold" style="letter-spacing: 0.08em; color: {margenColor};">
        Margen bruto
      </span>
      <div class="flex items-baseline gap-2">
        <span class="text-mono text-[14px] tabular-nums font-bold" style="color: {margenColor};">
          {fmtGtq(summary.margenBrutoGtq)}
        </span>
        <span class="text-mono text-[11px] tabular-nums" style="color: {margenColor};">
          {fmtPct(summary.margenPct)}
        </span>
      </div>
    </div>
  </div>

  <!-- Secondary: free units + stock pendiente -->
  <div class="mt-3 pt-2 border-t border-[var(--color-surface-2)] space-y-1 text-[11px]">
    {#if summary.nFreeUnits > 0}
      <div class="flex items-center justify-between">
        <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
          Free units ({summary.nFreeUnits})
        </span>
        <span class="text-mono text-[11px] tabular-nums text-[var(--color-text-secondary)]" title="Valor pendiente cuando se asigne destino">
          {fmtGtq(summary.valorFreeUnitsGtq)}
        </span>
      </div>
    {/if}

    {#if summary.nStockPendiente > 0}
      <!-- nStockPendiente = COUNT FROM import_items WHERE status='pending' (R6 single-source schema) -->
      <!-- valorStockPendienteGtq = SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) -->
      <div class="flex items-center justify-between" title="Items promovidos a este batch con status=pending (no vendidos aún · stock-future + assigned-to-customer)">
        <span class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
          Stock pendiente ({summary.nStockPendiente}u)
        </span>
        <span class="text-mono text-[11px] tabular-nums text-[var(--color-warning)]">
          {fmtGtq(summary.valorStockPendienteGtq)} amarrado
        </span>
      </div>
    {/if}
  </div>

  <!-- Footer: action links · TODO stubs per R3 Open Questions Q2/Q3 (cross-module nav pending decision) -->
  <footer class="mt-3 pt-2 border-t border-[var(--color-surface-2)] flex gap-3 text-[11px]">
    {#if onViewSales && summary.nSalesLinked > 0}
      <button
        onclick={() => onViewSales?.(summary.importId)}
        class="text-mono text-[10.5px] text-[var(--color-accent)] hover:underline"
        style="letter-spacing: 0.04em;"
      >
        → Ver ventas linkeadas ({summary.nSalesLinked})
      </button>
    {/if}
    {#if onViewPending && summary.nStockPendiente > 0}
      <button
        onclick={() => onViewPending?.(summary.importId)}
        class="text-mono text-[10.5px] text-[var(--color-accent)] hover:underline"
        style="letter-spacing: 0.04em;"
      >
        → Ver items pendientes ({summary.nStockPendiente})
      </button>
    {/if}
  </footer>
</article>
