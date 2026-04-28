<script lang="ts">
  import type { ImportPulso } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  interface Props {
    activeTab: TabId;
    pulsoCount: ImportPulso | null;
  }

  let { activeTab = $bindable(), pulsoCount }: Props = $props();

  const TABS: Array<{ id: TabId; label: string; countKey?: keyof ImportPulso }> = [
    { id: 'pedidos',  label: 'Pedidos' },
    { id: 'wishlist', label: 'Wishlist',     countKey: 'wishlist_count' },
    { id: 'margen',   label: 'Margen real' },
    { id: 'free',     label: 'Free units',   countKey: 'free_units_unassigned' },
    { id: 'supplier', label: 'Supplier' },
    { id: 'settings', label: 'Settings' },
  ];
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each TABS as tab}
    {@const count = tab.countKey && pulsoCount ? pulsoCount[tab.countKey] : null}
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
      {#if count !== null && count !== undefined && typeof count === 'number' && count > 0}
        <span class="text-[10px] opacity-70">· {count}</span>
      {/if}
    </button>
  {/each}
</div>
