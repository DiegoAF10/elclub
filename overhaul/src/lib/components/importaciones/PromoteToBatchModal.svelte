<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { WishlistItem } from '$lib/data/wishlist';
  import type { PromoteWishlistResult } from '$lib/adapter/types';

  interface Props {
    open: boolean;
    activeItems: WishlistItem[];   // pre-filtered status='active' items
    onClose: () => void;
    onPromoted: (result: PromoteWishlistResult) => void;
  }

  let { open, activeItems, onClose, onPromoted }: Props = $props();

  // Form state
  let importId = $state('');
  let alreadyPaid = $state(true);                                          // Diego decision: toggle ON by default
  let paidAt = $state(new Date().toISOString().slice(0, 10));
  let supplier = $state('Bond Soccer Jersey');
  let fx = $state(7.73);
  let brutoUsdManual = $state<number | null>(null);  // user-entered total · null = use auto-sum fallback
  let selectedIds = $state<Set<number>>(new Set());

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Derived status from toggle (Diego decision 2026-04-28)
  let importStatus = $derived<'paid' | 'draft'>(alreadyPaid ? 'paid' : 'draft');

  // Self-clean on close (R1.5 modal pattern)
  $effect(() => {
    if (!open) {
      reset();
    } else {
      // Default: select all active items
      selectedIds = new Set(activeItems.map(i => i.wishlistItemId));
    }
  });

  // Client-side regex enforcement (server is authoritative)
  const idPattern = /^IMP-\d{4}-\d{2}-\d{2}$/;
  let idValid = $derived(idPattern.test(importId));

  let selectedItems = $derived(activeItems.filter(i => selectedIds.has(i.wishlistItemId)));
  let assignedCount = $derived(selectedItems.filter(i => i.customerId).length);
  let stockCount = $derived(selectedItems.filter(i => !i.customerId).length);
  let estimatedBrutoUsd = $derived(
    selectedItems.reduce((sum, i) => sum + (i.expectedUsd ?? 0), 0)
  );
  // Effective bruto_usd sent to backend: manual override > auto-sum > 0
  let effectiveBrutoUsd = $derived(brutoUsdManual ?? estimatedBrutoUsd);
  let nUnits = $derived(selectedItems.length);

  // paid_at only required when status='paid'
  let paidAtValid = $derived(!alreadyPaid || paidAt.length === 10);

  let canSubmit = $derived(
    idValid &&
    paidAtValid &&
    fx > 0 &&
    effectiveBrutoUsd > 0 &&
    selectedIds.size >= 1 &&
    !submitting
  );

  function toggleItem(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }

  function selectAll() {
    selectedIds = new Set(activeItems.map(i => i.wishlistItemId));
  }

  function selectNone() {
    selectedIds = new Set();
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      const result = await adapter.promoteWishlistToBatch({
        wishlistItemIds: Array.from(selectedIds),
        importId,
        status: importStatus,                            // 'paid' or 'draft'
        paidAt: alreadyPaid ? paidAt : undefined,        // only sent when status='paid'
        supplier: supplier.trim() || undefined,
        brutoUsd: effectiveBrutoUsd,                     // user-entered total OR auto-sum fallback
        fx,
      });
      onPromoted(result);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    importId = '';
    alreadyPaid = true;
    paidAt = new Date().toISOString().slice(0, 10);
    supplier = 'Bond Soccer Jersey';
    fx = 7.73;
    brutoUsdManual = null;
    selectedIds = new Set();
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }

  function itemLabel(item: WishlistItem): string {
    const parts: string[] = [item.familyId];
    if (item.playerName) parts.push(item.playerName);
    if (item.playerNumber !== null) parts.push(`#${item.playerNumber}`);
    if (item.size) parts.push(item.size);
    if (item.patch) parts.push(item.patch);
    return parts.join(' · ');
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[600px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">↗ Promover a batch</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        Crea import + INSERTa items en import_items · marca wishlist promoted (atomic)
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- Import ID -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Import ID *
          </label>
          <input
            type="text"
            bind:value={importId}
            placeholder="IMP-2026-04-30"
            disabled={submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            class:border-[var(--color-danger)]={importId.length > 0 && !idValid}
            class:border-[var(--color-border)]={importId.length === 0 || idValid}
            autofocus
          />
          {#if importId.length > 0 && !idValid}
            <p class="text-[10.5px] text-[var(--color-danger)] mt-1">Formato: IMP-YYYY-MM-DD</p>
          {/if}
        </div>

        <!-- Status toggle: "Ya pagué" (Diego decision 2026-04-28 · default ON) -->
        <div class="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px]">
          <input
            type="checkbox"
            id="alreadyPaid"
            bind:checked={alreadyPaid}
            disabled={submitting}
            class="accent-[var(--color-accent)]"
          />
          <label for="alreadyPaid" class="text-mono text-[11px] text-[var(--color-text-primary)] cursor-pointer flex-1">
            Ya pagué al proveedor
          </label>
          <span class="text-mono text-[10px] uppercase" style="letter-spacing: 0.06em;"
            class:text-[var(--color-accent)]={alreadyPaid}
            class:text-[var(--color-text-tertiary)]={!alreadyPaid}>
            {alreadyPaid ? '● status=paid' : '○ status=draft'}
          </span>
        </div>

        <!-- Paid at (only when alreadyPaid) + FX -->
        <div class="grid grid-cols-2 gap-3">
          {#if alreadyPaid}
            <div>
              <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Paid at *</label>
              <input type="date" bind:value={paidAt} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
            </div>
          {:else}
            <div class="flex items-end">
              <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">paid_at queda NULL · marcalo cuando pagues</p>
            </div>
          {/if}
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">FX (USD→GTQ) *</label>
            <input type="number" bind:value={fx} step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Supplier -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Supplier</label>
          <input type="text" bind:value={supplier} disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        <!-- Bruto USD (lo que te cobra el chino · total del batch) -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Bruto USD * <span class="text-[var(--color-text-tertiary)] normal-case" style="letter-spacing: 0;">· lo que te cobra el chino · total del batch</span>
          </label>
          <input
            type="number"
            bind:value={brutoUsdManual}
            step="0.01"
            min="0.01"
            placeholder={estimatedBrutoUsd > 0 ? `auto: ${estimatedBrutoUsd.toFixed(2)} (suma expected_usd) · podés override` : 'p.ej. 372.64'}
            disabled={submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums"
          />
          {#if brutoUsdManual === null && estimatedBrutoUsd > 0}
            <p class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1" style="letter-spacing: 0.04em;">
              ● auto-suma: ${estimatedBrutoUsd.toFixed(2)} · entrá manual si el chino te cobra otro total
            </p>
          {:else if brutoUsdManual === null && estimatedBrutoUsd === 0}
            <p class="text-mono text-[10px] text-[var(--color-warning)] mt-1" style="letter-spacing: 0.04em;">
              ⚠ items sin expected_usd · entrá el bruto USD del chino acá (requerido)
            </p>
          {/if}
        </div>

        <!-- Selection summary -->
        <div class="border border-[var(--color-border)] rounded-[3px] p-3 bg-[var(--color-surface-2)]">
          <div class="mb-1.5">
            <span class="text-mono text-[11px] uppercase text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
              ¿Qué items mandás al chino en este batch?
            </span>
            <p class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-0.5" style="letter-spacing: 0.04em;">
              Marcá los items que van · desmarcá los que dejás para otro batch
            </p>
          </div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-mono text-[11px] text-[var(--color-text-secondary)]">
              <span class="tabular-nums text-[var(--color-accent)] font-semibold">{nUnits}</span> / {activeItems.length} marcados
            </span>
            <div class="flex gap-2">
              <button type="button" onclick={selectAll} disabled={submitting} class="text-mono text-[10px] uppercase text-[var(--color-accent)] hover:underline">marcar todos</button>
              <span class="text-[var(--color-text-tertiary)]">·</span>
              <button type="button" onclick={selectNone} disabled={submitting} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:underline">desmarcar todos</button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 text-mono text-[11px]">
            <div>
              <span class="text-[var(--color-text-tertiary)]">N units:</span>
              <span class="text-[var(--color-text-primary)] tabular-nums ml-1">{nUnits}</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Bruto USD:</span>
              <span class="text-[var(--color-text-primary)] tabular-nums ml-1">${estimatedBrutoUsd.toFixed(2)}</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Asignados:</span>
              <span class="text-[var(--color-accent)] tabular-nums ml-1">{assignedCount}</span>
              <span class="text-[var(--color-text-tertiary)] text-[10px] ml-1">(con cliente)</span>
            </div>
            <div>
              <span class="text-[var(--color-text-tertiary)]">Stock-future:</span>
              <span class="text-[var(--color-accent)] tabular-nums ml-1">{stockCount}</span>
              <span class="text-[var(--color-text-tertiary)] text-[10px] ml-1">(sin cliente)</span>
            </div>
          </div>
          <p class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-2 italic">
            Todos van a import_items (single table) · customer_id distingue ambos casos
          </p>
        </div>

        <!-- Items list (scrollable) -->
        <div class="border border-[var(--color-border)] rounded-[3px] max-h-[240px] overflow-y-auto">
          {#if activeItems.length === 0}
            <p class="text-[11px] text-[var(--color-text-tertiary)] p-3 text-center">
              No hay items active en wishlist. Agregá items primero.
            </p>
          {:else}
            {#each activeItems as item (item.wishlistItemId)}
              <label class="flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-2)] cursor-pointer border-b border-[var(--color-surface-2)] last:border-b-0">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.wishlistItemId)}
                  onchange={() => toggleItem(item.wishlistItemId)}
                  disabled={submitting}
                  class="accent-[var(--color-accent)]"
                />
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] flex-1">
                  {itemLabel(item)}
                </span>
                {#if item.expectedUsd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums">
                    ${item.expectedUsd.toFixed(2)}
                  </span>
                {/if}
                {#if item.customerId}
                  <span class="text-mono text-[10px] text-[var(--color-accent)] uppercase" style="letter-spacing: 0.06em;">
                    {item.customerId}
                  </span>
                {:else}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] uppercase" style="letter-spacing: 0.06em;">
                    stock
                  </span>
                {/if}
              </label>
            {/each}
          {/if}
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Promoviendo...' : `↗ Promover ${nUnits} items a ${importId || 'IMP-...'} (${importStatus})`}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
