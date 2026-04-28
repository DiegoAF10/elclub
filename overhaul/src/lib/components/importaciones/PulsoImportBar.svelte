<script lang="ts">
  import type { ImportPulso } from '$lib/data/importaciones';

  interface Props { pulso: ImportPulso; }
  let { pulso }: Props = $props();

  function fmtQ(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `Q${Math.round(n).toLocaleString('es-GT')}`;
  }
  function fmtDays(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `${Math.round(n)} días`;
  }
</script>

<div class="flex items-stretch gap-0 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-2.5">
  <!-- Capital amarrado -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Capital amarrado
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-warning)]">
      ~{fmtQ(pulso.capital_amarrado_gtq)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">paid · sin cerrar</div>
  </div>

  <!-- Closed YTD landed -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Closed YTD landed
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-live)]">
      {fmtQ(pulso.closed_ytd_landed_gtq)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">batches cerrados {new Date().getFullYear()}</div>
  </div>

  <!-- Avg landed -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Avg landed/u
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-primary)]">
      {fmtQ(pulso.avg_landed_unit)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">de batches closed</div>
  </div>

  <!-- Lead time avg -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Lead time avg
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-accent)]">
      {fmtDays(pulso.lead_time_avg_days)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">paid → arrived</div>
  </div>

  <!-- Wishlist -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Wishlist activa
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-secondary)]">
      {pulso.wishlist_count}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">items pre-pedido</div>
  </div>

  <!-- Free units -->
  <div class="flex-1 px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Free disponibles
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-primary)]">
      {pulso.free_units_unassigned}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">sin asignar destino</div>
  </div>
</div>
