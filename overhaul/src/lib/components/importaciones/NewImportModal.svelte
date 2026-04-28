<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    onClose: () => void;
    onCreated: (imp: Import) => void;
  }

  let { open, onClose, onCreated }: Props = $props();

  // Form state
  let importId = $state('');
  let paidAt = $state(new Date().toISOString().slice(0, 10));
  let supplier = $state('Bond Soccer Jersey');
  let brutoUsd = $state<number | null>(null);
  let fx = $state(7.73);
  let nUnits = $state<number | null>(null);
  let notes = $state('');
  let trackingCode = $state('');
  let carrier = $state('DHL');

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Client-side regex enforcement (matches server-side is_valid_import_id)
  const idPattern = /^IMP-\d{4}-\d{2}-\d{2}$/;
  let idValid = $derived(idPattern.test(importId));
  let canSubmit = $derived(
    idValid &&
    paidAt.length === 10 &&
    supplier.trim().length > 0 &&
    brutoUsd !== null && brutoUsd > 0 &&
    fx > 0 &&
    nUnits !== null && nUnits > 0 &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      const imp = await adapter.createImport({
        importId,
        paidAt,
        supplier: supplier.trim(),
        brutoUsd: brutoUsd!,
        fx,
        nUnits: nUnits!,
        notes: notes.trim() || undefined,
        trackingCode: trackingCode.trim() || undefined,
        carrier: carrier.trim() || undefined,
      });
      onCreated(imp);
      reset();
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    importId = '';
    paidAt = new Date().toISOString().slice(0, 10);
    supplier = 'Bond Soccer Jersey';
    brutoUsd = null;
    fx = 7.73;
    nUnits = null;
    notes = '';
    trackingCode = '';
    carrier = 'DHL';
    errorMsg = null;
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting && open) onClose();
  }
</script>

<svelte:window onkeydown={handleEscape} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="new-import-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[480px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 id="new-import-title" class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">+ Nuevo pedido</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        Crear import draft · status='paid' · prorrateo proporcional al cierre
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- Import ID -->
        <div>
          <label for="imp-id" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Import ID *
          </label>
          <input
            id="imp-id"
            type="text"
            bind:value={importId}
            placeholder="IMP-2026-04-28"
            disabled={submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            class:border-[var(--color-danger)]={importId.length > 0 && !idValid}
            class:border-[var(--color-border)]={importId.length === 0 || idValid}
          />
          {#if importId.length > 0 && !idValid}
            <p class="text-[10.5px] text-[var(--color-danger)] mt-1">Formato: IMP-YYYY-MM-DD</p>
          {/if}
        </div>

        <!-- Paid at + N units -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="imp-paid" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Paid at *</label>
            <input id="imp-paid" type="date" bind:value={paidAt} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label for="imp-units" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">N units *</label>
            <input id="imp-units" type="number" bind:value={nUnits} placeholder="27" min="1" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Supplier -->
        <div>
          <label for="imp-supplier" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Supplier *</label>
          <input id="imp-supplier" type="text" bind:value={supplier} disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        <!-- Bruto USD + FX -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="imp-bruto" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Bruto USD *</label>
            <input id="imp-bruto" type="number" bind:value={brutoUsd} placeholder="372.64" step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
          <div>
            <label for="imp-fx" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">FX (USD→GTQ) *</label>
            <input id="imp-fx" type="number" bind:value={fx} step="0.01" min="0.01" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Tracking + carrier -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="imp-tracking" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking (opt)</label>
            <input id="imp-tracking" type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label for="imp-carrier" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Carrier</label>
            <input id="imp-carrier" type="text" bind:value={carrier} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label for="imp-notes" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes (opt)</label>
          <textarea id="imp-notes" bind:value={notes} rows="2" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) { reset(); onClose(); } }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Creando...' : '+ Crear pedido'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
