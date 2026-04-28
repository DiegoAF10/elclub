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
  import { adapter } from '$lib/adapter';
  import type { ImportPulso } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  const STORAGE_KEY = 'imp.activeTab';

  let activeTab = $state<TabId>(
    (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY) as TabId) || 'pedidos'
  );
  let pulso = $state<ImportPulso | null>(null);

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
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
        ⇣ Export CSV
      </button>
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]">
        ↻ Sync DHL
      </button>
      <button class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]">
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
      <PedidosTab onPulsoRefresh={refreshPulso} />
    {:else if activeTab === 'wishlist'}
      <WishlistTab />
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
