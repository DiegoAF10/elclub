<script lang="ts">
  import { onMount } from 'svelte';
  import type { ComercialTab } from '$lib/data/comercial';
  import ComercialTabs from './ComercialTabs.svelte';
  import PulsoBar from './PulsoBar.svelte';
  import FunnelTab from './tabs/FunnelTab.svelte';
  import CustomersTab from './tabs/CustomersTab.svelte';
  import InboxTab from './tabs/InboxTab.svelte';
  import AdsTab from './tabs/AdsTab.svelte';
  import SettingsTab from './tabs/SettingsTab.svelte';

  const TABS: ComercialTab[] = ['funnel', 'customers', 'inbox', 'ads', 'settings'];
  const STORAGE_KEY = 'comercial:lastTab';

  let activeTab = $state<ComercialTab>('funnel');

  // Restaurar último tab abierto
  onMount(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ComercialTab | null;
    if (saved && TABS.includes(saved)) {
      activeTab = saved;
    }
  });

  function selectTab(tab: ComercialTab) {
    activeTab = tab;
    localStorage.setItem(STORAGE_KEY, tab);
  }
</script>

<div class="flex h-full flex-col bg-[var(--color-bg)]">
  <ComercialTabs {activeTab} onSelectTab={selectTab} />
  <PulsoBar />
  <div class="flex-1 overflow-y-auto">
    {#if activeTab === 'funnel'}
      <FunnelTab />
    {:else if activeTab === 'customers'}
      <CustomersTab />
    {:else if activeTab === 'inbox'}
      <InboxTab />
    {:else if activeTab === 'ads'}
      <AdsTab />
    {:else if activeTab === 'settings'}
      <SettingsTab />
    {/if}
  </div>
</div>
