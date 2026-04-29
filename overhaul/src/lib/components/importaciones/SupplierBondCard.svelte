<script lang="ts">
  import type { SupplierDetail, PriceBand } from '$lib/adapter/types';

  interface Props {
    detail: SupplierDetail;
  }

  let { detail }: Props = $props();

  let m = $derived(detail.metrics);
  let pb = $derived(detail.priceBand);
  let c = $derived(detail.contact);

  // Helpers
  function fmtAvg(v: number | null, n: number): string {
    if (v === null) return 'sin datos';
    return `${v.toFixed(1)} días avg (n=${n})`;
  }
  function fmtPct(v: number | null, closedCount: number): string {
    // Per spec ambiguity: cost_accuracy_pct comes back null until disputes log exists.
    // Display "Datos insuficientes" with sample-size hint.
    if (v === null) return closedCount > 0
      ? `Datos insuficientes (${closedCount} closed · sin disputes log)`
      : 'sin datos';
    return `±${v.toFixed(1)}%`;
  }
  function fmtPriceBand(pb: PriceBand): string {
    if (pb.source === 'tbd' || pb.baseUsd === null) return 'Datos pendientes';
    const parts: string[] = [];
    if (pb.baseUsd !== null) parts.push(`$${pb.baseUsd} base`);
    if (pb.patchUsd !== null) parts.push(`$${pb.patchUsd} +patch`);
    if (pb.patchNameUsd !== null) parts.push(`$${pb.patchNameUsd} +patch+name`);
    return parts.join(' · ');
  }
  function fmtTotalLanded(v: number): string {
    if (v === 0) return 'Q0 (sin batches closed)';
    return `Q${Math.round(v).toLocaleString('es-GT')}`;
  }
  function fmtNext(v: string | null, pipeline: number): string {
    if (v === null) {
      return pipeline > 0
        ? 'sin avg_lead (precisás 1 batch closed para ETA)'
        : 'n/a (sin batches en pipeline)';
    }
    // Format YYYY-MM-DD → DD-MMM
    const d = new Date(v);
    if (isNaN(d.getTime())) return v;
    const months = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
    return `${String(d.getDate()).padStart(2, '0')}-${months[d.getMonth()]}`;
  }

  // Status pill helper for batches in pipeline
  function statusPillClass(status: string): string {
    return {
      closed:  'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      paid:    'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      arrived: 'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      draft:   'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled: 'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] ?? 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6">
  <!-- Header -->
  <div class="border-b border-[var(--color-surface-2)] pb-3 mb-4">
    <h2 class="text-[18px] font-semibold text-[var(--color-text-primary)]">{m.supplier}</h2>
    <p class="text-mono text-[11px] text-[var(--color-text-tertiary)] mt-1" style="letter-spacing: 0.04em;">
      {c.label} · {c.paymentMethod} · {c.carrier}
    </p>
  </div>

  <!-- 7 stat rows · spec sec 4.5 line 267-278 layout -->
  <dl class="space-y-2.5">
    <!-- LEAD TIME -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">LEAD TIME</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtAvg(m.leadTimeAvgDays, m.leadTimeN)}
        {#if m.leadTimeP50Days !== null && m.leadTimeP95Days !== null}
          <span class="text-[var(--color-text-tertiary)] ml-2">
            · p50 {m.leadTimeP50Days.toFixed(1)} · p95 {m.leadTimeP95Days.toFixed(1)}
          </span>
        {/if}
      </dd>
    </div>

    <!-- COST ACCURACY -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">COST ACCURACY</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtPct(m.costAccuracyPct, m.closedBatches)}
      </dd>
    </div>

    <!-- PRICE BAND -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">PRICE BAND</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtPriceBand(pb)}
      </dd>
    </div>

    <!-- FREE POLICY -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">FREE POLICY</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)]">
        {detail.freePolicyText}
      </dd>
    </div>

    <!-- TOTAL BATCHES -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">TOTAL BATCHES</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {m.totalBatches}
        <span class="text-[var(--color-text-tertiary)] ml-1">
          ({m.closedBatches} closed · {m.pipelineBatches} pipeline)
        </span>
      </dd>
    </div>

    <!-- TOTAL LANDED YTD -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">TOTAL LANDED YTD</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtTotalLanded(m.totalLandedGtqYtd)}
      </dd>
    </div>

    <!-- NEXT EXPECTED -->
    <div class="flex items-baseline gap-4">
      <dt class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] w-[140px] shrink-0" style="letter-spacing: 0.08em;">NEXT EXPECTED</dt>
      <dd class="text-mono text-[12.5px] text-[var(--color-text-primary)] tabular-nums">
        {fmtNext(m.nextExpectedArrival, m.pipelineBatches)}
      </dd>
    </div>
  </dl>

  <!-- Batches list (collapsed default · always visible if any) -->
  {#if detail.batches.length > 0}
    <div class="mt-5 pt-4 border-t border-[var(--color-surface-2)]">
      <div class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
        Batches ({detail.batches.length})
      </div>
      <ul class="space-y-1.5">
        {#each detail.batches as b (b.importId)}
          <li class="flex items-center gap-3 text-mono text-[11px] tabular-nums">
            <span class="text-[var(--color-text-primary)] w-[140px]">{b.importId}</span>
            <span class={`px-1.5 py-0.5 rounded-[2px] text-[9.5px] uppercase ${statusPillClass(b.status)}`} style="letter-spacing: 0.06em;">
              ● {b.status}
            </span>
            <span class="text-[var(--color-text-tertiary)]">
              {b.paidAt ?? 'sin paid_at'}
              {#if b.leadTimeDays !== null} · {b.leadTimeDays}d{/if}
              {#if b.nUnits !== null} · {b.nUnits}u{/if}
              {#if b.totalLandedGtq !== null} · Q{Math.round(b.totalLandedGtq).toLocaleString('es-GT')}{/if}
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>
