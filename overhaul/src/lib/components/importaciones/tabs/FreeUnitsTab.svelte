<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import type { FreeUnit, FreeUnitFilter, FreeUnitDestination } from '$lib/adapter/types';
  import AssignDestinationModal from '../AssignDestinationModal.svelte';

  type FilterKey = 'all' | 'unassigned' | FreeUnitDestination;

  let units = $state<FreeUnit[]>([]);
  let loading = $state(true);
  let errorMsg = $state<string | null>(null);
  let filter = $state<FilterKey>('all');

  // Modal state
  let modalOpen = $state(false);
  let modalUnit = $state<FreeUnit | null>(null);

  async function load() {
    loading = true;
    errorMsg = null;
    try {
      const f: FreeUnitFilter = {};
      if (filter === 'unassigned') f.status = 'unassigned';
      else if (filter !== 'all') f.destination = filter;
      units = await adapter.listFreeUnits(f);
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
      units = [];
    } finally {
      loading = false;
    }
  }

  onMount(load);

  // Re-fetch on filter change
  $effect(() => {
    void filter;
    load();
  });

  // Counts derived from current dataset (filtered)
  // Note: when filter is not 'all', counts reflect server-filtered subset.
  // For full counts we'd need a separate fetch — keeping simple per spec.
  const counts = $derived({
    all: units.length,
    unassigned: units.filter((u) => u.destination === null).length,
    vip: units.filter((u) => u.destination === 'vip').length,
    mystery: units.filter((u) => u.destination === 'mystery').length,
    garantizada: units.filter((u) => u.destination === 'garantizada').length,
    personal: units.filter((u) => u.destination === 'personal').length,
  });

  function openAssign(unit: FreeUnit) {
    modalUnit = unit;
    modalOpen = true;
  }

  function closeAssign() {
    modalOpen = false;
    modalUnit = null;
  }

  function onAssigned(updated: FreeUnit) {
    units = units.map((u) => (u.freeUnitId === updated.freeUnitId ? updated : u));
    // Tell ImportTabs (and any listener) to refresh the [Free units N] badge
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('imp-free-units-refresh'));
    }
  }

  async function handleUnassign(unit: FreeUnit) {
    if (!confirm(`Desasignar free unit #${unit.freeUnitId}?`)) return;
    try {
      const updated = await adapter.unassignFreeUnit(unit.freeUnitId);
      units = units.map((u) => (u.freeUnitId === updated.freeUnitId ? updated : u));
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('imp-free-units-refresh'));
      }
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  const FILTER_CHIPS: Array<{ key: FilterKey; label: string }> = [
    { key: 'all', label: 'Todos' },
    { key: 'unassigned', label: '● Sin asignar' },
    { key: 'vip', label: '● VIP' },
    { key: 'mystery', label: '● Mystery' },
    { key: 'garantizada', label: '● Garantizada' },
    { key: 'personal', label: '● Personal' },
  ];

  function destinationPillClass(dest: string | null): string {
    if (!dest) return 'text-[var(--color-text-tertiary)]';
    switch (dest) {
      case 'vip':         return 'text-[var(--color-accent)]';
      case 'mystery':     return 'text-[#fbbf24]';
      case 'garantizada': return 'text-[#a78bfa]';
      case 'personal':    return 'text-[var(--color-text-secondary)]';
      default:            return 'text-[var(--color-text-secondary)]';
    }
  }
</script>

<div class="flex-1 overflow-y-auto p-6 space-y-4">
  <!-- Header + filter chips -->
  <div class="flex items-baseline justify-between gap-4">
    <div>
      <div class="text-[14px] font-semibold text-[var(--color-text-primary)]">Free units ledger</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mt-0.5" style="letter-spacing: 0.05em;">
        regalos auto-creados al cerrar batches · floor(N_paid / 10) por import
      </div>
    </div>
  </div>

  <div class="flex flex-wrap gap-2">
    {#each FILTER_CHIPS as chip}
      <button
        type="button"
        onclick={() => (filter = chip.key)}
        class="text-mono px-3 py-1 border rounded-[3px] text-[11px] uppercase transition-colors"
        class:border-[var(--color-accent)]={filter === chip.key}
        class:!text-[var(--color-accent)]={filter === chip.key}
        class:bg-[var(--color-surface-2)]={filter === chip.key}
        class:border-[var(--color-border)]={filter !== chip.key}
        class:text-[var(--color-text-secondary)]={filter !== chip.key}
        style="letter-spacing: 0.08em;"
      >
        {chip.label} <span class="opacity-70 ml-1">· {counts[chip.key as keyof typeof counts] ?? 0}</span>
      </button>
    {/each}
  </div>

  {#if loading}
    <div class="text-mono text-[11px] text-[var(--color-text-tertiary)] py-8 text-center" style="letter-spacing: 0.05em;">
      ⏳ Cargando free units…
    </div>
  {:else if errorMsg}
    <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
      ⚠️ {errorMsg}
    </div>
  {:else if units.length === 0}
    <div class="border border-[var(--color-border)] rounded-[6px] p-8 text-center bg-[var(--color-surface-1)] space-y-2">
      <div class="text-[13px] text-[var(--color-text-secondary)]">Sin free units todavía.</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] max-w-md mx-auto" style="letter-spacing: 0.05em; line-height: 1.6;">
        Cuando cerrás un batch con N paid units, el sistema crea automáticamente
        <span class="text-[var(--color-accent)]">floor(N/10)</span> free units en este ledger.
        Asignalos a VIP / Mystery / Garantizada / Personal según política.
      </div>
    </div>
  {:else}
    <div class="border border-[var(--color-border)] rounded-[6px] overflow-hidden bg-[var(--color-surface-1)]">
      <table class="w-full text-[12px]">
        <thead class="bg-[var(--color-surface-2)]">
          <tr class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
            <th class="px-3 py-2 text-left font-normal">Import</th>
            <th class="px-3 py-2 text-left font-normal">Family</th>
            <th class="px-3 py-2 text-left font-normal">Created</th>
            <th class="px-3 py-2 text-left font-normal">Destino</th>
            <th class="px-3 py-2 text-left font-normal">Ref</th>
            <th class="px-3 py-2 text-left font-normal">Notes</th>
            <th class="px-3 py-2 text-right font-normal">Acción</th>
          </tr>
        </thead>
        <tbody>
          {#each units as u (u.freeUnitId)}
            <tr class="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]">
              <td class="px-3 py-2 text-mono text-[var(--color-text-primary)]">{u.importId}</td>
              <td class="px-3 py-2 text-mono text-[var(--color-text-secondary)]">{u.familyId ?? '—'}</td>
              <td class="px-3 py-2 text-mono text-[10.5px] text-[var(--color-text-tertiary)] tabular-nums">
                {u.createdAt?.slice(0, 10) ?? '—'}
              </td>
              <td class="px-3 py-2 text-mono uppercase {destinationPillClass(u.destination)}" style="letter-spacing: 0.08em;">
                {#if u.destination}
                  ● {u.destination}
                {:else}
                  ● unassigned
                {/if}
              </td>
              <td class="px-3 py-2 text-mono text-[11px] text-[var(--color-text-secondary)]">
                {u.destinationRef ?? '—'}
              </td>
              <td class="px-3 py-2 text-[11px] text-[var(--color-text-secondary)] truncate max-w-[180px]">
                {u.notes ?? ''}
              </td>
              <td class="px-3 py-2 text-right">
                {#if u.destination}
                  <button
                    type="button"
                    onclick={() => handleUnassign(u)}
                    class="text-mono text-[10.5px] px-2 py-1 rounded-[3px] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-danger)] hover:text-[var(--color-danger)] transition-colors"
                    style="letter-spacing: 0.05em;"
                  >
                    Desasignar
                  </button>
                {:else}
                  <button
                    type="button"
                    onclick={() => openAssign(u)}
                    class="text-mono text-[10.5px] px-3 py-1 rounded-[3px] bg-[var(--color-accent)] text-[var(--color-bg)] font-semibold hover:bg-[var(--color-accent-hover)] transition-colors"
                    style="letter-spacing: 0.05em;"
                  >
                    + Asignar
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<AssignDestinationModal
  open={modalOpen}
  freeUnit={modalUnit}
  onClose={closeAssign}
  onAssigned={onAssigned}
/>
