<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    imp: Import | null;
    onClose: () => void;
    onCancelled: (imp: Import) => void;
  }

  let { open, imp, onClose, onCancelled }: Props = $props();

  let confirmInput = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Self-clean on close
  $effect(() => {
    if (!open) {
      confirmInput = '';
      errorMsg = null;
    }
  });

  let canCancel = $derived(
    confirmInput.trim().toUpperCase() === 'CONFIRMO' &&
    imp !== null &&
    !submitting
  );

  async function handleCancel() {
    if (!canCancel || !imp) return;
    submitting = true;
    errorMsg = null;
    try {
      const cancelled = await adapter.cancelImport(imp.import_id);
      onCancelled(cancelled);
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
    aria-labelledby="cancel-modal-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[rgba(244,63,94,0.3)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 id="cancel-modal-title" class="text-[16px] font-semibold text-[var(--color-danger)] mb-1">🚫 Cancelar batch</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {imp.import_id} · status={imp.status} · acción reversible vía admin re-open
      </p>

      <p class="text-[13px] text-[var(--color-text-primary)] mb-4">
        Vas a marcar este pedido como <strong class="text-[var(--color-danger)]">cancelled</strong>. No borra data · solo cambia status. Los <strong>{imp.n_units ?? 0} units</strong> dejan de contar como capital amarrado.
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleCancel(); }} class="space-y-3">
        <div>
          <label for="cancel-confirm" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Escribí <strong class="text-[var(--color-danger)]">CONFIRMO</strong> para proceder</label>
          <input id="cancel-confirm" type="text" bind:value={confirmInput} placeholder="CONFIRMO" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Volver</button>
          <button type="submit" disabled={!canCancel} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-danger)]={canCancel}
            class:text-white={canCancel}
            class:bg-[var(--color-surface-2)]={!canCancel}
            class:text-[var(--color-text-tertiary)]={!canCancel}>
            {submitting ? '⏳ Cancelando...' : '🚫 Cancelar batch'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
