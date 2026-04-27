<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import type { ComercialTab, Period } from '$lib/data/comercial';
  import ComercialTabs from './ComercialTabs.svelte';
  import PulsoBar from './PulsoBar.svelte';
  import FunnelTab from './tabs/FunnelTab.svelte';
  import SalesTab from './tabs/SalesTab.svelte';
  import CustomersTab from './tabs/CustomersTab.svelte';
  import InboxTab from './tabs/InboxTab.svelte';
  import AdsTab from './tabs/AdsTab.svelte';
  import SettingsTab from './tabs/SettingsTab.svelte';
  import { startDetectorLoop } from '$lib/data/eventDetector';
  import { startSyncLoop, runSync, type SyncResult } from '$lib/data/manychatSync';
  import { adapter } from '$lib/adapter';

  const TABS: ComercialTab[] = ['funnel', 'sales', 'customers', 'inbox', 'ads', 'settings'];
  const STORAGE_KEY = 'comercial:lastTab';

  let activeTab = $state<ComercialTab>('funnel');
  let stopDetector: (() => void) | null = null;

  // Period state hoisted from PulsoBar (R2-combo)
  let activePeriod = $state<Period>('today');

  // ManyChat sync loop (R2-combo)
  let stopSync: (() => void) | null = null;
  let lastSyncResult = $state<SyncResult | null>(null);

  // Auto-sync cron (R9 Part 2): silent background sync every 15 min
  let autoSyncInterval: ReturnType<typeof setInterval> | null = null;

  async function silentSync() {
    // Best-effort, swallow errors silently. Don't block UI.
    try { await adapter.syncMetaAds({ days: 30 }); } catch {}
    try { await adapter.importOrdersFromWorker(); } catch {}
    try { await runSync(); } catch {}
    console.log('[auto-sync] background sync completed');
  }

  // Restaurar último tab abierto + arrancar detector de eventos
  onMount(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ComercialTab | null;
    if (saved && TABS.includes(saved)) {
      activeTab = saved;
    }
    stopDetector = startDetectorLoop();
    stopSync = startSyncLoop((r) => { lastSyncResult = r; });

    // Initial sync after 5s (let UI render first), then every 15 min
    const initialTimer = setTimeout(() => { void silentSync(); }, 5000);
    autoSyncInterval = setInterval(() => { void silentSync(); }, 15 * 60 * 1000);

    return () => clearTimeout(initialTimer);
  });

  onDestroy(() => {
    stopDetector?.();
    stopSync?.();
    if (autoSyncInterval) clearInterval(autoSyncInterval);
  });

  function selectTab(tab: ComercialTab) {
    activeTab = tab;
    localStorage.setItem(STORAGE_KEY, tab);
  }
</script>

<div class="flex h-full flex-col bg-[var(--color-bg)]">
  <ComercialTabs {activeTab} onSelectTab={selectTab} />
  <PulsoBar period={activePeriod} setPeriod={(p) => (activePeriod = p)} />
  <div class="flex-1 overflow-y-auto">
    {#if activeTab === 'funnel'}
      <FunnelTab period={activePeriod} {lastSyncResult} onSwitchTab={(t) => selectTab(t)} />
    {:else if activeTab === 'sales'}
      <SalesTab />
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
