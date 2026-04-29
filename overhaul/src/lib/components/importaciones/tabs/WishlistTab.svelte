<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import {
    WISHLIST_TARGET_SIZE,
    isAssigned,
    type WishlistItem,
  } from '$lib/data/wishlist';
  import WishlistItemModal from '../WishlistItemModal.svelte';
  import PromoteToBatchModal from '../PromoteToBatchModal.svelte';

  interface Props {
    onPulsoRefresh: () => void;
    refreshTrigger?: number;
  }
  let { onPulsoRefresh, refreshTrigger = 0 }: Props = $props();

  // Filter state
  let statusFilter = $state<'active' | 'promoted' | 'cancelled'>('active');

  // Data
  let items = $state<WishlistItem[]>([]);
  let loading = $state(true);

  // Modal state
  let itemModalOpen = $state(false);
  let itemModalMode = $state<'create' | 'edit'>('create');
  let itemModalTarget = $state<WishlistItem | null>(null);

  let promoteModalOpen = $state(false);

  onMount(load);

  // Re-fetch when parent bumps the trigger or filter changes
  $effect(() => {
    if (refreshTrigger > 0) {
      load();
    }
  });

  $effect(() => {
    // Re-load when statusFilter changes
    statusFilter;
    load();
  });

  async function load() {
    loading = true;
    try {
      items = await adapter.listWishlist({ status: statusFilter });
    } finally {
      loading = false;
    }
  }

  // Derived sections (only when status='active')
  let assignedItems = $derived(items.filter(isAssigned));
  let stockItems = $derived(items.filter(i => !isAssigned(i)));
  let activeCount = $derived(statusFilter === 'active' ? items.length : 0);

  function openCreate() {
    itemModalMode = 'create';
    itemModalTarget = null;
    itemModalOpen = true;
  }

  function openEdit(item: WishlistItem) {
    itemModalMode = 'edit';
    itemModalTarget = item;
    itemModalOpen = true;
  }

  async function handleCancelItem(item: WishlistItem) {
    const confirmed = confirm(`¿Quitar "${item.family_id}${item.player_name ? ' · ' + item.player_name : ''}" del wishlist?`);
    if (!confirmed) return;
    try {
      await adapter.cancelWishlistItem(item.wishlist_item_id);
      await load();
      onPulsoRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  function openPromote() {
    if (assignedItems.length + stockItems.length === 0) return;
    promoteModalOpen = true;
  }

  async function handleItemSaved() {
    await load();
    onPulsoRefresh();
  }

  function handlePromoted(result: { import: { import_id: string }; importItemsCount: number }) {
    // Switch to status='active' filter so user can see remaining items
    statusFilter = 'active';
    load();
    onPulsoRefresh();
    alert(`✅ ${result.importItemsCount} items promovidos a ${result.import.import_id}\n\nVer el batch en tab Pedidos.`);
  }

  function rowLabel(item: WishlistItem): string {
    const parts: string[] = [];
    if (item.player_name) parts.push(item.player_name);
    if (item.player_number !== null) parts.push(`#${item.player_number}`);
    if (item.patch) parts.push(item.patch);
    if (item.version) parts.push(item.version);
    if (item.size) parts.push(item.size);
    return parts.join(' · ') || '—';
  }
</script>

<div class="flex flex-col flex-1 min-h-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)]">
    <div class="flex items-center gap-3">
      <h2 class="text-mono text-[11px] uppercase text-[var(--color-text-secondary)]" style="letter-spacing: 0.08em;">
        Wishlist {statusFilter}
      </h2>
      <span class="text-mono text-[11px] text-[var(--color-text-primary)] tabular-nums">
        {items.length} {statusFilter === 'active' ? `/ ${WISHLIST_TARGET_SIZE} target` : ''}
      </span>
      {#if statusFilter === 'active' && items.length >= WISHLIST_TARGET_SIZE}
        <span class="text-mono text-[10px] uppercase text-[var(--color-warning)] bg-[rgba(245,165,36,0.15)] border border-[rgba(245,165,36,0.3)] px-2 py-0.5 rounded-[3px]" style="letter-spacing: 0.06em;">
          ● HORA DE CONSOLIDAR BATCH
        </span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <!-- Status filter chips -->
      <div class="flex gap-1">
        {#each ['active', 'promoted', 'cancelled'] as s (s)}
          <button
            class="text-mono text-[10px] uppercase px-2 py-1 rounded-[3px] border"
            class:bg-[var(--color-accent)]={statusFilter === s}
            class:text-[var(--color-bg)]={statusFilter === s}
            class:border-[var(--color-accent)]={statusFilter === s}
            class:bg-transparent={statusFilter !== s}
            class:text-[var(--color-text-tertiary)]={statusFilter !== s}
            class:border-[var(--color-border)]={statusFilter !== s}
            style="letter-spacing: 0.06em;"
            onclick={() => statusFilter = s as typeof statusFilter}
          >
            {s}
          </button>
        {/each}
      </div>
      <button
        onclick={openCreate}
        class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]"
      >
        + Nuevo item
      </button>
      <button
        onclick={openPromote}
        disabled={statusFilter !== 'active' || activeCount === 0}
        title={statusFilter !== 'active' ? 'Solo items active pueden promoverse' : (activeCount === 0 ? 'Sin items activos' : 'Promover items active a un nuevo batch')}
        class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] font-semibold"
        class:bg-[var(--color-accent)]={statusFilter === 'active' && activeCount > 0}
        class:text-[var(--color-bg)]={statusFilter === 'active' && activeCount > 0}
        class:bg-[var(--color-surface-2)]={statusFilter !== 'active' || activeCount === 0}
        class:text-[var(--color-text-tertiary)]={statusFilter !== 'active' || activeCount === 0}
        class:cursor-not-allowed={statusFilter !== 'active' || activeCount === 0}
      >
        ↗ Promover a batch
      </button>
    </div>
  </div>

  <!-- Body -->
  <div class="flex-1 overflow-y-auto p-4">
    {#if loading}
      <div class="flex items-center justify-center text-[var(--color-text-tertiary)] py-8">
        Cargando wishlist…
      </div>
    {:else if items.length === 0}
      <div class="flex flex-col items-center justify-center text-center py-12 text-[var(--color-text-tertiary)] text-[12px]">
        {#if statusFilter === 'active'}
          <p class="mb-2">Sin pre-pedidos activos.</p>
          <p class="text-[11px]">Cuando un cliente pida algo, agregá item acá.</p>
          <p class="text-[10.5px] text-[var(--color-text-muted)] mt-3">Recordatorio: D7=B · SKU debe existir en catalog.</p>
        {:else if statusFilter === 'promoted'}
          <p>Sin items promovidos todavía.</p>
        {:else}
          <p>Sin items cancelados.</p>
        {/if}
      </div>
    {:else if statusFilter === 'active'}
      <!-- ASSIGNED section -->
      {#if assignedItems.length > 0}
        <div class="mb-6">
          <h3 class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
            [ASSIGNED · {assignedItems.length}]
          </h3>
          <div class="border border-[var(--color-border)] rounded-[3px]">
            {#each assignedItems as item (item.wishlist_item_id)}
              <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
                <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
                <span class="text-mono text-[10px] uppercase text-[var(--color-accent)] w-[100px] text-right" style="letter-spacing: 0.06em;">
                  {item.customer_id}
                </span>
                {#if item.expected_usd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums w-[60px] text-right">
                    ${item.expected_usd.toFixed(2)}
                  </span>
                {:else}
                  <span class="w-[60px]"></span>
                {/if}
                <div class="flex gap-1">
                  <button onclick={() => openEdit(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] px-2">editar</button>
                  <button onclick={() => handleCancelItem(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] px-2">quitar</button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- STOCK FUTURO section -->
      {#if stockItems.length > 0}
        <div>
          <h3 class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] mb-2" style="letter-spacing: 0.08em;">
            [STOCK FUTURO · {stockItems.length}]
          </h3>
          <div class="border border-[var(--color-border)] rounded-[3px]">
            {#each stockItems as item (item.wishlist_item_id)}
              <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
                <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
                <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
                <span class="w-[100px]"></span>
                {#if item.expected_usd}
                  <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] tabular-nums w-[60px] text-right">
                    ${item.expected_usd.toFixed(2)}
                  </span>
                {:else}
                  <span class="w-[60px]"></span>
                {/if}
                <div class="flex gap-1">
                  <button onclick={() => openEdit(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] px-2">editar</button>
                  <button onclick={() => handleCancelItem(item)} class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] px-2">quitar</button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {:else}
      <!-- promoted / cancelled · simple flat list -->
      <div class="border border-[var(--color-border)] rounded-[3px]">
        {#each items as item (item.wishlist_item_id)}
          <div class="flex items-center gap-3 px-3 py-2 border-b border-[var(--color-surface-2)] last:border-b-0 hover:bg-[var(--color-surface-2)]">
            <span class="text-mono text-[11px] text-[var(--color-text-primary)] w-[120px]">{item.family_id}</span>
            <span class="text-mono text-[11px] text-[var(--color-text-secondary)] flex-1">{rowLabel(item)}</span>
            {#if item.promoted_to_import_id}
              <span class="text-mono text-[10px] uppercase text-[var(--color-accent)]" style="letter-spacing: 0.06em;">
                → {item.promoted_to_import_id}
              </span>
            {/if}
            <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">{item.created_at.slice(0, 10)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Modals -->
  <WishlistItemModal
    open={itemModalOpen}
    mode={itemModalMode}
    item={itemModalTarget}
    onClose={() => itemModalOpen = false}
    onSaved={handleItemSaved}
  />

  <PromoteToBatchModal
    open={promoteModalOpen}
    activeItems={statusFilter === 'active' ? items : []}
    onClose={() => promoteModalOpen = false}
    onPromoted={handlePromoted}
  />
</div>
