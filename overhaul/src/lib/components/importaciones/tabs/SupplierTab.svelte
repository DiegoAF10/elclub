<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { SupplierMetrics, SupplierDetail, UnpublishedRequest } from '$lib/adapter/types';
  import SupplierChipBar from '../SupplierChipBar.svelte';
  import SupplierBondCard from '../SupplierBondCard.svelte';

  let metrics = $state<SupplierMetrics[]>([]);
  let activeSupplier = $state<string | null>(null);
  let detail = $state<SupplierDetail | null>(null);
  let loading = $state(true);
  let detailLoading = $state(false);
  let errorMsg = $state<string | null>(null);

  // BONUS widget · más pedidos sin publicar (feedback loop publishing)
  let unpublished = $state<UnpublishedRequest[]>([]);
  let unpublishedLoading = $state(true);

  const BOND_NAME = 'Bond Soccer Jersey';

  // Initial load
  $effect(() => {
    loadMetrics();
    loadUnpublished();
  });

  async function loadMetrics() {
    loading = true;
    errorMsg = null;
    try {
      metrics = await adapter.getSupplierMetrics();
      // Default-select Bond if present, else first supplier
      if (metrics.length > 0) {
        const bond = metrics.find((m) => m.supplier === BOND_NAME);
        const initial = bond?.supplier ?? metrics[0].supplier;
        if (activeSupplier === null) {
          activeSupplier = initial;
          await loadDetail(initial);
        }
      }
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadUnpublished() {
    unpublishedLoading = true;
    try {
      unpublished = await adapter.getMostRequestedUnpublished(5);
    } catch (e) {
      // Silent fail · widget es bonus · no rompe scorecard si falla
      console.warn('[unpublished widget]', e);
      unpublished = [];
    } finally {
      unpublishedLoading = false;
    }
  }

  async function loadDetail(supplier: string) {
    detailLoading = true;
    try {
      detail = await adapter.getSupplierDetail(supplier);
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
      detail = null;
    } finally {
      detailLoading = false;
    }
  }

  function handleSelect(supplier: string) {
    activeSupplier = supplier;
    loadDetail(supplier);
  }
</script>

<div class="flex flex-col flex-1 p-6 overflow-y-auto">
  <!-- BONUS WIDGET: más pedidos sin publicar -->
  <section class="mb-6 border border-[var(--color-border)] rounded-[3px] p-4 bg-[var(--color-surface-1)]">
    <header class="flex items-baseline justify-between mb-3">
      <h3 class="text-mono text-[11px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.10em;">
        Más pedidos sin publicar
      </h3>
      <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">top 5 · feedback loop</span>
    </header>
    {#if unpublishedLoading}
      <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">Cargando…</div>
    {:else if unpublished.length === 0}
      <div class="text-[12px] text-[var(--color-text-secondary)]">
        Todo lo pedido está publicado · 🎉  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">(o sin pedidos todavía)</span>
      </div>
    {:else}
      <ul class="flex flex-col gap-1.5">
        {#each unpublished as u (u.familyId)}
          <li class="flex items-center justify-between text-[12px] gap-3">
            <span class="text-mono text-[var(--color-accent)]">{u.familyId}</span>
            <span class="flex items-center gap-3 text-[var(--color-text-secondary)]">
              <span class="text-mono">×{u.nRequests}</span>
              <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">
                {u.nAssigned}A · {u.nStock}S · {u.nPending}P
              </span>
              <a href="#audit-{u.familyId}" class="text-mono text-[10px] text-[var(--color-accent)] hover:underline">→ Auditar</a>
            </span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  {#if loading}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      <div class="text-mono text-[11px] uppercase" style="letter-spacing: 0.08em;">Cargando supplier metrics…</div>
    </div>
  {:else if errorMsg}
    <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2 mb-4">
      ⚠️ {errorMsg}
    </div>
  {:else if metrics.length === 0}
    <!-- Empty state: zero suppliers means zero batches -->
    <div class="flex flex-1 items-center justify-center">
      <div class="text-center max-w-md">
        <div class="text-mono text-[11px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">Sin batches todavía</div>
        <div class="text-sm text-[var(--color-text-secondary)]">
          Cuando crees el primer pedido (tab Pedidos · botón <span class="text-mono">+ Nuevo</span>), aparece scorecard del supplier acá con métricas reales.
        </div>
      </div>
    </div>
  {:else}
    <!-- Multi-supplier scaffold: chip bar -->
    <SupplierChipBar suppliers={metrics} {activeSupplier} onSelect={handleSelect} />

    {#if detailLoading}
      <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Cargando detail…</div>
    {:else if detail}
      <SupplierBondCard {detail} />
    {/if}
  {/if}
</div>
