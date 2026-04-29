<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/adapter/types';

  interface Props {
    open: boolean;
    importId: string;          // current import being marked
    currentTrackingCode: string | null;
    onClose: () => void;
    onMarked: (updated: Import) => void;
  }

  let { open, importId, currentTrackingCode, onClose, onMarked }: Props = $props();

  let trackingCode = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  $effect(() => {
    if (!open) {
      reset();
    } else {
      trackingCode = currentTrackingCode ?? '';
    }
  });

  async function handleConfirm() {
    submitting = true;
    errorMsg = null;
    try {
      const updated = await adapter.markInTransit(
        importId,
        trackingCode.trim() || undefined,
      );
      onMarked(updated);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    trackingCode = '';
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
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
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">→ Marcar en tránsito</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {importId} · status: paid → in_transit
      </p>

      <p class="text-[12px] text-[var(--color-text-secondary)] mb-3">
        El proveedor confirmó envío. Marcá este import como <span class="text-mono text-[var(--color-accent)]">in_transit</span>. Después podés registrar la llegada con "Registrar arrival".
      </p>

      <div class="mb-3">
        <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
          Tracking code (opcional)
        </label>
        <input
          type="text"
          bind:value={trackingCode}
          placeholder="DHL-XXXXX (opcional)"
          disabled={submitting}
          class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]"
        />
        {#if currentTrackingCode}
          <p class="text-[10.5px] text-[var(--color-text-tertiary)] mt-1">
            Actual: <span class="text-mono">{currentTrackingCode}</span> · vacío preserva el actual (COALESCE)
          </p>
        {/if}
      </div>

      {#if errorMsg}
        <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2 mb-3">
          ⚠️ {errorMsg}
        </div>
      {/if}

      <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
        <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
          Cancelar
        </button>
        <button type="button" onclick={handleConfirm} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold bg-[var(--color-accent)] text-[var(--color-bg)]">
          {submitting ? '⏳ Marcando...' : '→ Confirmar in_transit'}
        </button>
      </div>
    </div>
  </div>
{/if}
