<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import type { ImportPulso } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  interface Props {
    activeTab: TabId;
    pulsoCount: ImportPulso | null;
  }

  let { activeTab = $bindable(), pulsoCount }: Props = $props();

  // R4: Self-fetched count for the [Free units N] badge.
  // Source-of-truth precedence: live `freeUnitsCount` (post-mount) overrides
  // the pulsoCount value which can lag behind assign/unassign actions.
  let freeUnitsCount = $state<number | null>(null);

  async function refreshFreeCount() {
    try {
      const us = await adapter.listFreeUnits({ status: 'unassigned' });
      freeUnitsCount = us.length;
    } catch {
      // Silent — fall back to pulsoCount.free_units_unassigned (browser dev mode etc.)
    }
  }

  onMount(() => {
    refreshFreeCount();
    if (typeof window !== 'undefined') {
      window.addEventListener('imp-free-units-refresh', refreshFreeCount);
      return () => window.removeEventListener('imp-free-units-refresh', refreshFreeCount);
    }
    return undefined;
  });

  const TABS: Array<{ id: TabId; label: string; countKey?: keyof ImportPulso }> = [
    { id: 'pedidos',  label: 'Pedidos' },
    { id: 'wishlist', label: 'Wishlist',     countKey: 'wishlist_count' },
    { id: 'margen',   label: 'Margen real' },
    { id: 'free',     label: 'Free units',   countKey: 'free_units_unassigned' },
    { id: 'supplier', label: 'Supplier' },
    { id: 'settings', label: 'Settings' },
  ];

  // Resolve the count for a tab — prefer live R4 fetch for 'free' over pulso
  function resolveCount(tab: { id: TabId; countKey?: keyof ImportPulso }): number | null {
    if (tab.id === 'free' && freeUnitsCount !== null) return freeUnitsCount;
    if (tab.countKey && pulsoCount) {
      const v = pulsoCount[tab.countKey];
      return typeof v === 'number' ? v : null;
    }
    return null;
  }
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each TABS as tab}
    {@const count = resolveCount(tab)}
    {@const isLast = tab.id === 'settings'}
    <button
      class="text-mono inline-flex items-baseline gap-1.5 border-b-2 border-transparent px-4 py-2.5 text-[11px] uppercase transition-colors"
      class:ml-auto={isLast}
      class:text-[var(--color-text-secondary)]={activeTab !== tab.id}
      class:!text-[var(--color-accent)]={activeTab === tab.id}
      class:!border-[var(--color-accent)]={activeTab === tab.id}
      style="letter-spacing: 0.05em;"
      onclick={() => activeTab = tab.id}
    >
      {tab.label}
      {#if count !== null && count > 0}
        <span class="text-[10px] opacity-70">· {count}</span>
      {/if}
    </button>
  {/each}
</div>
