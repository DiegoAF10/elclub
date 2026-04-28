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
  let activePeriod = $state<Period>('30d');

  // ManyChat sync loop (R2-combo)
  let stopSync: (() => void) | null = null;
  let lastSyncResult = $state<SyncResult | null>(null);

  // Auto-sync cron (R9 Part 2): silent background sync every 15 min
  // R14: sync immediately on mount (no 5s delay) + visual indicator
  let autoSyncInterval: ReturnType<typeof setInterval> | null = null;
  let tickInterval: ReturnType<typeof setInterval> | null = null;
  let syncing = $state(false);
  let lastSyncAt = $state<Date | null>(null);
  let nowTick = $state(Date.now());

  async function silentSync() {
    if (syncing) return;
    syncing = true;
    try { await adapter.syncMetaAds({ days: 30 }); } catch {}
    try { await adapter.importOrdersFromWorker(); } catch {}
    try { await runSync(); } catch {}
    lastSyncAt = new Date();
    syncing = false;
    console.log('[auto-sync] background sync completed');
  }

  function fmtSince(d: Date | null): string {
    if (!d) return '—';
    void nowTick; // reactive dependency
    const ms = Date.now() - d.getTime();
    const min = Math.floor(ms / 60000);
    if (min < 1) return 'recién';
    if (min === 1) return 'hace 1 min';
    if (min < 60) return `hace ${min} min`;
    const hr = Math.floor(min / 60);
    return `hace ${hr}h`;
  }

  // Restaurar último tab abierto + arrancar detector de eventos
  onMount(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ComercialTab | null;
    if (saved && TABS.includes(saved)) {
      activeTab = saved;
    }
    stopDetector = startDetectorLoop();
    stopSync = startSyncLoop((r) => { lastSyncResult = r; });

    // R14: sync immediately on launch (was 5s delay), then every 15 min
    void silentSync();
    autoSyncInterval = setInterval(() => { void silentSync(); }, 15 * 60 * 1000);

    // Tick every minute to refresh "hace X min" label
    tickInterval = setInterval(() => { nowTick = Date.now(); }, 60_000);
  });

  onDestroy(() => {
    stopDetector?.();
    stopSync?.();
    if (autoSyncInterval) clearInterval(autoSyncInterval);
    if (tickInterval) clearInterval(tickInterval);
  });

  async function manualSyncNow() {
    void silentSync();
  }

  function selectTab(tab: ComercialTab) {
    activeTab = tab;
    localStorage.setItem(STORAGE_KEY, tab);
  }
</script>

<div class="flex h-full flex-col bg-[var(--color-bg)]">
  <ComercialTabs {activeTab} onSelectTab={selectTab} />
  <PulsoBar period={activePeriod} setPeriod={(p) => (activePeriod = p)} />

  <!-- R14: sync status indicator strip -->
  <div class="flex items-center justify-end gap-2 border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-1 text-[9.5px]">
    {#if syncing}
      <span class="text-[var(--color-warning)] animate-pulse">● Sincronizando…</span>
    {:else if lastSyncAt}
      <span class="text-[var(--color-text-muted)]">● Sync {fmtSince(lastSyncAt)}</span>
      <button
        type="button"
        onclick={manualSyncNow}
        class="text-[var(--color-accent)] hover:underline"
        title="Forzar sync ahora"
      >[refresh]</button>
    {:else}
      <span class="text-[var(--color-text-muted)]">● Sync pendiente…</span>
    {/if}
  </div>

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
