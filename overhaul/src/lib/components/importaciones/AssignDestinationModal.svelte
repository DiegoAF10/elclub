<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { FreeUnit, FreeUnitDestination, AssignFreeUnitInput } from '$lib/adapter/types';
  import type { Customer } from '$lib/data/comercial';

  interface Props {
    open: boolean;
    freeUnit: FreeUnit | null;
    onClose: () => void;
    onAssigned: (updated: FreeUnit) => void;
  }

  let { open, freeUnit, onClose, onAssigned }: Props = $props();

  // Form state
  let destination = $state<FreeUnitDestination>('personal');
  let destinationRef = $state('');
  let notes = $state('');
  let familyId = $state('');
  let jerseyId = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Customer search state — only used for VIP destination
  let customers = $state<Customer[]>([]);
  let customerQuery = $state('');
  let customersLoaded = $state(false);

  // Self-clean: reset all form state whenever modal transitions to closed
  $effect(() => {
    if (!open) reset();
  });

  // Lazy-load customers when destination switches to VIP for the first time
  $effect(() => {
    if (open && destination === 'vip' && !customersLoaded) {
      customersLoaded = true;
      adapter
        .listCustomers()
        .then((cs) => {
          customers = cs;
        })
        .catch(() => {
          // Silent — UI shows manual customer_id input fallback
          customers = [];
        });
    }
  });

  const filteredCustomers = $derived(
    customerQuery.trim().length > 0
      ? customers.filter((c) => {
          const q = customerQuery.toLowerCase();
          return (
            (c.name ?? '').toLowerCase().includes(q) ||
            String(c.customerId).includes(q)
          );
        })
      : customers
  );

  const refRequired = $derived(destination === 'vip');
  const refValid = $derived(!refRequired || destinationRef.trim().length > 0);
  const canSubmit = $derived(!submitting && !!freeUnit && refValid);

  async function handleSubmit() {
    if (!canSubmit || !freeUnit) return;
    submitting = true;
    errorMsg = null;
    try {
      const input: AssignFreeUnitInput = {
        freeUnitId: freeUnit.freeUnitId,
        destination,
        destinationRef: destinationRef.trim() || null,
        familyId: familyId.trim() || null,
        jerseyId: jerseyId.trim() || null,
        notes: notes.trim() || null,
      };
      const updated = await adapter.assignFreeUnit(input);
      onAssigned(updated);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    destination = 'personal';
    destinationRef = '';
    notes = '';
    familyId = '';
    jerseyId = '';
    submitting = false;
    errorMsg = null;
    customerQuery = '';
    customersLoaded = false;
    customers = [];
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting && open) onClose();
  }

  function selectDestination(dest: FreeUnitDestination) {
    destination = dest;
    destinationRef = '';
    customerQuery = '';
  }

  function pickCustomer(c: Customer) {
    destinationRef = String(c.customerId);
    customerQuery = c.name ?? String(c.customerId);
  }

  const DESTINATIONS: { key: FreeUnitDestination; label: string }[] = [
    { key: 'vip', label: 'VIP' },
    { key: 'mystery', label: 'Mystery' },
    { key: 'garantizada', label: 'Garantizada' },
    { key: 'personal', label: 'Personal' },
  ];
</script>

<svelte:window onkeydown={handleEscape} />

{#if open && freeUnit}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="assign-destination-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[520px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 id="assign-destination-title" class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">
        Asignar free unit
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        FREE UNIT #{freeUnit.freeUnitId} · {freeUnit.importId}
        {#if freeUnit.familyId}· {freeUnit.familyId}{/if}
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
        <!-- Destination chip-grid -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-2" style="letter-spacing: 0.08em;">
            Destino *
          </label>
          <div class="grid grid-cols-2 gap-2">
            {#each DESTINATIONS as dest}
              <button
                type="button"
                onclick={() => selectDestination(dest.key)}
                disabled={submitting}
                class="text-mono px-3 py-2 border rounded-[3px] text-left text-[11px] uppercase transition-colors"
                class:border-[var(--color-accent)]={destination === dest.key}
                class:!text-[var(--color-accent)]={destination === dest.key}
                class:bg-[var(--color-surface-2)]={destination === dest.key}
                class:border-[var(--color-border)]={destination !== dest.key}
                class:text-[var(--color-text-secondary)]={destination !== dest.key}
                style="letter-spacing: 0.08em;"
              >
                ● {dest.label}
              </button>
            {/each}
          </div>
        </div>

        <!-- Destination-specific ref input -->
        {#if destination === 'vip'}
          <div>
            <label for="vip-search" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Customer (requerido)
            </label>
            <input
              id="vip-search"
              type="text"
              bind:value={customerQuery}
              placeholder="Buscar customer por nombre o ID…"
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
            {#if customerQuery.trim().length > 0 && filteredCustomers.length > 0}
              <div class="mt-1 max-h-32 overflow-y-auto border border-[var(--color-border)] rounded-[3px] bg-[var(--color-surface-2)]">
                {#each filteredCustomers.slice(0, 8) as c}
                  <button
                    type="button"
                    onclick={() => pickCustomer(c)}
                    class="w-full px-3 py-1.5 text-left text-[12px] hover:bg-[var(--color-surface-1)] transition-colors"
                    class:!text-[var(--color-accent)]={destinationRef === String(c.customerId)}
                  >
                    <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">#{c.customerId}</span>
                    <span class="ml-2 text-[var(--color-text-primary)]">{c.name}</span>
                  </button>
                {/each}
              </div>
            {/if}
            <input
              type="text"
              bind:value={destinationRef}
              placeholder="o customer_id manual"
              disabled={submitting}
              class="text-mono w-full mt-2 px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
            {#if !refValid}
              <p class="text-[10.5px] text-[var(--color-danger)] mt-1">customer_id requerido para VIP</p>
            {/if}
          </div>
        {:else if destination === 'mystery'}
          <div>
            <label for="mystery-ref" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Pool ref (opcional · ej. mystery_pool_2026_W17)
            </label>
            <input
              id="mystery-ref"
              type="text"
              bind:value={destinationRef}
              placeholder="opcional"
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
        {:else if destination === 'garantizada'}
          <div>
            <label for="garantizada-ref" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Stock ref (opcional · ej. Q475 publicación)
            </label>
            <input
              id="garantizada-ref"
              type="text"
              bind:value={destinationRef}
              placeholder="opcional"
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
        {:else}
          <div>
            <label for="personal-ref" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Personal · ref opcional
            </label>
            <input
              id="personal-ref"
              type="text"
              bind:value={destinationRef}
              placeholder="opcional"
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
        {/if}

        <!-- Family + Jersey overrides (rare · for cases where free unit was created without metadata) -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="assign-family" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Family ID (opt)
            </label>
            <input
              id="assign-family"
              type="text"
              bind:value={familyId}
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
          <div>
            <label for="assign-jersey" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Jersey ID (opt)
            </label>
            <input
              id="assign-jersey"
              type="text"
              bind:value={jerseyId}
              disabled={submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label for="assign-notes" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Notes (opt)
          </label>
          <textarea
            id="assign-notes"
            bind:value={notes}
            rows="2"
            disabled={submitting}
            class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none focus:outline-none focus:border-[var(--color-accent)]"
          ></textarea>
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button
            type="button"
            onclick={() => { if (!submitting) onClose(); }}
            disabled={submitting}
            class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}
          >
            {submitting ? '⏳ Asignando...' : `Asignar a ${destination.toUpperCase()}`}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
