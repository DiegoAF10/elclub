<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    imp: Import | null;
    onClose: () => void;
    onUpdated: (imp: Import) => void;
  }

  let { open, imp, onClose, onUpdated }: Props = $props();

  let notes = $state('');
  let trackingCode = $state('');
  let carrier = $state('DHL');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Pre-fill from imp when modal opens · self-clean errors when modal closes
  $effect(() => {
    if (open && imp) {
      notes = imp.notes ?? '';
      trackingCode = imp.tracking_code ?? '';
      carrier = imp.carrier ?? 'DHL';
      errorMsg = null;
    } else if (!open) {
      errorMsg = null;
    }
  });

  async function handleSubmit() {
    if (!imp || submitting) return;
    submitting = true;
    errorMsg = null;
    try {
      const updated = await adapter.updateImport({
        importId: imp.import_id,
        notes: notes.trim() || undefined,
        trackingCode: trackingCode.trim() || undefined,
        carrier: carrier.trim() || undefined,
      });
      onUpdated(updated);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting && open) onClose();
  }
</script>

<svelte:window onkeydown={handleEscape} />

{#if open && imp}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="edit-modal-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 id="edit-modal-title" class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">📝 Editar pedido</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {imp.import_id} · status={imp.status} · solo notes/tracking/carrier editables
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <div>
          <label for="edit-notes" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes</label>
          <textarea id="edit-notes" bind:value={notes} rows="3" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>
        <div>
          <label for="edit-tracking" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking code</label>
          <input id="edit-tracking" type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>
        <div>
          <label for="edit-carrier" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Carrier</label>
          <input id="edit-carrier" type="text" bind:value={carrier} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Cancelar</button>
          <button type="submit" disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold bg-[var(--color-accent)] text-[var(--color-bg)]">
            {submitting ? '⏳ Guardando...' : '💾 Guardar cambios'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
