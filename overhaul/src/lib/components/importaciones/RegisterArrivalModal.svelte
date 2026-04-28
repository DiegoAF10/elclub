<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    open: boolean;
    importId: string | null;
    onClose: () => void;
    onRegistered: (imp: Import) => void;
  }

  let { open, importId, onClose, onRegistered }: Props = $props();

  let arrivedAt = $state(new Date().toISOString().slice(0, 10));
  let shippingGtq = $state<number | null>(null);
  let trackingCode = $state('');
  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Self-clean on close
  $effect(() => {
    if (!open) reset();
  });

  let canSubmit = $derived(
    importId !== null &&
    arrivedAt.length === 10 &&
    shippingGtq !== null && shippingGtq >= 0 &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit || !importId) return;
    submitting = true;
    errorMsg = null;
    try {
      const imp = await adapter.registerArrival({
        importId,
        arrivedAt,
        shippingGtq: shippingGtq!,
        trackingCode: trackingCode.trim() || undefined,
      });
      onRegistered(imp);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    arrivedAt = new Date().toISOString().slice(0, 10);
    shippingGtq = null;
    trackingCode = '';
    errorMsg = null;
  }

  function handleEscape(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting && open) onClose();
  }
</script>

<svelte:window onkeydown={handleEscape} />

{#if open && importId}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
    aria-labelledby="arrival-modal-title"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[440px] shadow-2xl">
      <h2 id="arrival-modal-title" class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">📥 Registrar arrival</h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        {importId} · status → 'arrived' · lead time auto-calculado
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <div>
          <label for="arrival-date" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Arrived at *</label>
          <input id="arrival-date" type="date" bind:value={arrivedAt} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>
        <div>
          <label for="arrival-shipping" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Shipping DHL (GTQ) *</label>
          <input id="arrival-shipping" type="number" bind:value={shippingGtq} placeholder="522.67" step="0.01" min="0" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
        </div>
        <div>
          <label for="arrival-tracking" class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Tracking code (opt)</label>
          <input id="arrival-tracking" type="text" bind:value={trackingCode} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">⚠️ {errorMsg}</div>
        {/if}

        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)]">Cancelar</button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}>
            {submitting ? '⏳ Registrando...' : '📥 Registrar arrival'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
