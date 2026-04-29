<script lang="ts">
  import { onMount } from 'svelte';
  import ImportTabs from './ImportTabs.svelte';
  import PulsoImportBar from './PulsoImportBar.svelte';
  import PedidosTab from './tabs/PedidosTab.svelte';
  import WishlistTab from './tabs/WishlistTab.svelte';
  import MargenRealTab from './tabs/MargenRealTab.svelte';
  import FreeUnitsTab from './tabs/FreeUnitsTab.svelte';
  import SupplierTab from './tabs/SupplierTab.svelte';
  import ImportSettingsTab from './tabs/ImportSettingsTab.svelte';
  import NewImportModal from './NewImportModal.svelte';
  import { adapter } from '$lib/adapter';
  import type { ImportPulso, Import } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  const STORAGE_KEY = 'imp.activeTab';
  const VALID_TABS: TabId[] = ['pedidos', 'wishlist', 'margen', 'free', 'supplier', 'settings'];
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
  let activeTab = $state<TabId>(
    VALID_TABS.includes(stored as TabId) ? (stored as TabId) : 'pedidos'
  );
  let pulso = $state<ImportPulso | null>(null);

  // R1.5: NewImportModal state
  let showNewModal = $state(false);
  let exportingCsv = $state(false);
  // Bumped on handleImportCreated · PedidosTab listens via $effect to force re-fetch
  let pedidosRefreshTrigger = $state(0);
  // R2: bumped on wishlist CRUD + promote-to-batch
  let wishlistRefreshTrigger = $state(0);

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, activeTab);
    }
  });

  onMount(async () => {
    pulso = await adapter.getImportPulso();
  });

  async function refreshPulso() {
    pulso = await adapter.getImportPulso();
  }

  // R2: when wishlist promotes to batch, both Pedidos AND Wishlist need re-fetch
  function handleWishlistPulsoRefresh() {
    refreshPulso();
    pedidosRefreshTrigger++;
    wishlistRefreshTrigger++;
  }

  function handleImportCreated(_imp: Import) {
    refreshPulso();
    activeTab = 'pedidos';
    pedidosRefreshTrigger++;
  }

  async function handleExportCsv() {
    if (exportingCsv) return;
    exportingCsv = true;
    try {
      const csv = await adapter.exportImportsCsv();
      // Trigger Blob download
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `imports-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Error exportando CSV: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      exportingCsv = false;
    }
  }
</script>

<div class="flex h-full flex-col">
  <!-- Module head -->
  <div class="flex items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-3">
    <div>
      <div class="text-[18px] font-semibold text-[var(--color-text-primary)]">Importaciones</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        módulo de costeo · seguimiento de pedidos al supplier · alimenta FIN-Rx
      </div>
    </div>
    <div class="ml-auto flex gap-2">
      <button
        onclick={handleExportCsv}
        disabled={exportingCsv}
        class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
        class:cursor-not-allowed={exportingCsv}
        class:opacity-60={exportingCsv}
      >
        {exportingCsv ? '⏳ Exportando...' : '⇣ Export CSV'}
      </button>
      <button
        disabled
        title="DHL real auto-sync diferido a IMP-R5 supplier · usá Registrar arrival manual por ahora"
        class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60"
      >
        ↻ Sync DHL
      </button>
      <button
        onclick={() => { showNewModal = true; }}
        class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]"
      >
        + Nuevo pedido
      </button>
    </div>
  </div>

  <!-- Tabs -->
  <ImportTabs bind:activeTab pulsoCount={pulso} />

  <!-- Pulso bar -->
  {#if pulso}
    <PulsoImportBar {pulso} />
  {/if}

  <!-- Body -->
  <div class="flex flex-1 min-h-0">
    {#if activeTab === 'pedidos'}
      <PedidosTab onPulsoRefresh={refreshPulso} refreshTrigger={pedidosRefreshTrigger} />
    {:else if activeTab === 'wishlist'}
      <WishlistTab onPulsoRefresh={handleWishlistPulsoRefresh} refreshTrigger={wishlistRefreshTrigger} />
    {:else if activeTab === 'margen'}
      <MargenRealTab />
    {:else if activeTab === 'free'}
      <FreeUnitsTab />
    {:else if activeTab === 'supplier'}
      <SupplierTab />
    {:else if activeTab === 'settings'}
      <ImportSettingsTab />
    {/if}
  </div>
</div>

<NewImportModal
  open={showNewModal}
  onClose={() => { showNewModal = false; }}
  onCreated={handleImportCreated}
/>
