<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { WishlistItem } from '$lib/data/wishlist';

  interface Props {
    open: boolean;
    mode: 'create' | 'edit';
    item: WishlistItem | null;     // null when mode='create'
    onClose: () => void;
    onSaved: (item: WishlistItem) => void;
  }

  let { open, mode, item, onClose, onSaved }: Props = $props();

  // Form state — initialized from item on open in edit mode
  let familyId = $state('');
  let jerseyId = $state('');
  let size = $state('');
  let playerName = $state('');
  let playerNumber = $state<number | null>(null);
  let patch = $state('');
  let version = $state<'' | 'fan' | 'fan-w' | 'player'>('');
  let customerId = $state('');
  let expectedUsd = $state<number | null>(null);
  let notes = $state('');

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  // Self-clean on close (R1.5 modal pattern)
  $effect(() => {
    if (!open) {
      reset();
    } else if (mode === 'edit' && item) {
      familyId = item.family_id;
      jerseyId = item.jersey_id ?? '';
      size = item.size ?? '';
      playerName = item.player_name ?? '';
      playerNumber = item.player_number;
      patch = item.patch ?? '';
      version = (item.version as typeof version) ?? '';
      customerId = item.customer_id ?? '';
      expectedUsd = item.expected_usd;
      notes = item.notes ?? '';
    }
  });

  // Loose family_id pattern check (server enforces D7=B authoritatively)
  // Pattern matches catalog SKU format: e.g. ARG-2026-L-FS, FRA-2026-L-FS
  const familyIdPattern = /^[A-Z]{2,5}-\d{4}-[A-Z]-[A-Z]{1,3}$/;
  let familyIdLooksValid = $derived(familyIdPattern.test(familyId.trim()));

  let canSubmit = $derived(
    familyId.trim().length > 0 &&
    (expectedUsd === null || expectedUsd >= 0) &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit) return;
    submitting = true;
    errorMsg = null;
    try {
      let saved: WishlistItem;
      if (mode === 'create') {
        saved = await adapter.createWishlistItem({
          familyId: familyId.trim(),
          jerseyId: jerseyId.trim() || undefined,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      } else {
        if (!item) throw new Error('edit mode requires item prop');
        saved = await adapter.updateWishlistItem({
          wishlistItemId: item.wishlist_item_id,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      }
      onSaved(saved);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    familyId = '';
    jerseyId = '';
    size = '';
    playerName = '';
    playerNumber = null;
    patch = '';
    version = '';
    customerId = '';
    expectedUsd = null;
    notes = '';
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
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[480px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">
        {mode === 'create' ? '+ Nuevo wishlist item' : 'Editar wishlist item'}
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        D7=B · SKU debe existir en catalog.json
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- Family ID (D7=B validated server-side) -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
            Family ID (SKU) *
          </label>
          <input
            type="text"
            bind:value={familyId}
            placeholder="ARG-2026-L-FS"
            disabled={mode === 'edit' || submitting}
            class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
            class:border-[var(--color-warning)]={familyId.length > 0 && !familyIdLooksValid}
            class:border-[var(--color-border)]={familyId.length === 0 || familyIdLooksValid}
          />
          {#if mode === 'create' && familyId.length > 0 && !familyIdLooksValid}
            <p class="text-[10.5px] text-[var(--color-warning)] mt-1">⚠️ Patrón inusual · servidor validará contra catalog.json</p>
          {/if}
          {#if mode === 'edit'}
            <p class="text-[10.5px] text-[var(--color-text-tertiary)] mt-1">family_id no editable post-create</p>
          {/if}
        </div>

        <!-- Player name + number -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Player name</label>
            <input type="text" bind:value={playerName} placeholder="Messi" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Number</label>
            <input type="number" bind:value={playerNumber} placeholder="10" min="0" max="99" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Size + Version -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Size</label>
            <select bind:value={size} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">—</option>
              <option value="S">S</option>
              <option value="M">M</option>
              <option value="L">L</option>
              <option value="XL">XL</option>
              <option value="XXL">XXL</option>
            </select>
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Version</label>
            <select bind:value={version} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">—</option>
              <option value="fan">fan</option>
              <option value="fan-w">fan-w</option>
              <option value="player">player</option>
            </select>
          </div>
        </div>

        <!-- Patch + Expected USD -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Patch</label>
            <select bind:value={patch} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">— sin patch</option>
              <option value="WC">WC (World Cup)</option>
              <option value="Champions">Champions</option>
            </select>
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Expected USD</label>
            <input type="number" bind:value={expectedUsd} placeholder="15.00" step="0.01" min="0" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Customer + Jersey ID -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Customer ID</label>
            <input type="text" bind:value={customerId} placeholder="cust-xyz (vacío = stock)" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Jersey ID (variant)</label>
            <input type="text" bind:value={jerseyId} placeholder="opcional" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes</label>
          <textarea bind:value={notes} rows="2" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
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
            {submitting ? '⏳ Guardando...' : (mode === 'create' ? '+ Crear item' : '💾 Guardar')}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
