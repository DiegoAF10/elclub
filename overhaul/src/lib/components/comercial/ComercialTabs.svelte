<script lang="ts">
  import type { ComercialTab } from '$lib/data/comercial';
  import { TrendingUp, Users, Inbox, DollarSign, Settings } from 'lucide-svelte';

  interface Props {
    activeTab: ComercialTab;
    onSelectTab: (tab: ComercialTab) => void;
    /** Count de eventos críticos (R1) — pasado desde InboxTab via store */
    inboxCount?: number;
  }

  let { activeTab, onSelectTab, inboxCount = 0 }: Props = $props();

  const TABS: { id: ComercialTab; label: string; icon: any }[] = [
    { id: 'funnel', label: 'Funnel', icon: TrendingUp },
    { id: 'customers', label: 'Customers', icon: Users },
    { id: 'inbox', label: 'Inbox', icon: Inbox },
    { id: 'ads', label: 'Ads', icon: DollarSign },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];
</script>

<div
  class="flex items-stretch border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6"
>
  {#each TABS as tab (tab.id)}
    {@const Icon = tab.icon}
    {@const isActive = activeTab === tab.id}
    <button
      type="button"
      onclick={() => onSelectTab(tab.id)}
      class="flex items-center gap-2 px-5 py-3.5 text-[13px] transition-colors"
      style="
        color: {isActive ? 'var(--color-accent)' : 'var(--color-text-tertiary)'};
        border-bottom: 2px solid {isActive ? 'var(--color-accent)' : 'transparent'};
        margin-bottom: -1px;
        font-weight: {isActive ? '600' : '400'};
      "
    >
      <Icon size={13} strokeWidth={1.8} />
      <span>{tab.label}</span>
      {#if tab.id === 'inbox' && inboxCount > 0}
        <span
          class="rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-semibold"
          style="background: rgba(244, 63, 94, 0.18); color: var(--color-danger);"
        >
          {inboxCount}
        </span>
      {/if}
    </button>
  {/each}
</div>
