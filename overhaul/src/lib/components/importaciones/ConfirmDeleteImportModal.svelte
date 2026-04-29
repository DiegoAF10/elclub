<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    imp: Import | null;
    onClose: () => void;
    onDeleted: () => void;
  }

  let { open, imp, onClose, onDeleted }: Props = $props();

  let confirmInput = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  $effect(() => {
    if (!open) {
      confirmInput = '';
      errorMsg = null;
    }
  });

  let canDelete = $derived(
    imp !== null &&
    confirmInput.trim() === imp.import_id &&
    !submitting
  );

  async function handleDelete() {
    if (!canDelete || !imp) return;
    submitting = true;
    errorMsg = null;
    try {
      await adapter.deleteImport(imp.import_id);
      onDeleted();
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
    aria-labelledby="delete-modal-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[rgba(244,63,94,0.5)] rounded-[6px] p-6 w-[480px] shadow-2xl">
      <h2 id="delete-modal-title" class="text-[16px] font-semibold text-[var(--color-danger)] mb-1">⚠️ Eliminar permanentemente</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {imp.import_id} · status={imp.status} · acción IRREVERSIBLE
      </p>

      <div class="text-[13px] text-[var(--color-text-primary)] mb-3 space-y-2">
        <p>Vas a <strong class="text-[var(--color-danger)]">borrar</strong> este batch + todos sus child rows:</p>
        <ul class="text-mono text-[11.5px] text-[var(--color-text-secondary)] list-disc pl-5 space-y-0.5">
          <li>DELETE import_items + import_free_unit (cascade)</li>
          <li>RESTAURA import_wishlist promoted → status='active'</li>
          <li>DECOUPLE sale_items.import_id + jerseys.import_id (preserva ventas + catálogo)</li>
          <li>DELETE imports row</li>
        </ul>
      </div>

      <form onsubmit={(e) => { e.preventDefault(); handleDelete(); }} class="space-y-3">
        <div>
          <label for="delete-confirm" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Escribí <strong class="text-mono text-[var(--color-danger)]">{imp.import_id}</strong> para proceder</label>
          <input id="delete-confirm" type="text" bind:value={confirmInput} placeholder={imp.import_id} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Volver</button>
          <button type="submit" disabled={!canDelete} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-danger)]={canDelete}
            class:text-white={canDelete}
            class:bg-[var(--color-surface-2)]={!canDelete}
            class:text-[var(--color-text-tertiary)]={!canDelete}>
            {submitting ? '⏳ Eliminando...' : '🗑️ Eliminar permanentemente'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
