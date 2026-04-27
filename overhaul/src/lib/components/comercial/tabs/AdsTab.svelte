<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Campaign } from '$lib/data/comercial';
  import { Search, TrendingUp, RefreshCw } from 'lucide-svelte';
  import CampaignDetailModal from '../modals/CampaignDetailModal.svelte';

  let campaigns = $state<Campaign[]>([]);
  let loading = $state(true);
  let search = $state('');
  let periodDays = $state<7 | 30 | 90>(30);

  type SortKey = 'spend' | 'impressions' | 'clicks' | 'conversions' | 'costPerConversion' | 'lastSync';
  let sortBy = $state<SortKey>('spend');

  let openCampaignId = $state<string | null>(null);

  async function loadCampaigns() {
    loading = true;
    try {
      campaigns = await adapter.listCampaigns({ periodDays });
    } catch (e) {
      console.warn('[ads-tab] load failed', e);
      campaigns = [];
    } finally {
      loading = false;
    }
  }

  $effect(() => { void loadCampaigns(); });

  // KPIs — derived from current dataset
  let totals = $derived.by(() => {
    return campaigns.reduce((acc, c) => ({
      spend: acc.spend + c.totalSpendGtq,
      impressions: acc.impressions + c.totalImpressions,
      clicks: acc.clicks + c.totalClicks,
      conversions: acc.conversions + c.totalConversions,
      revenue: acc.revenue + c.totalRevenueGtq,
    }), { spend: 0, impressions: 0, clicks: 0, conversions: 0, revenue: 0 });
  });

  function daysSinceSync(c: Campaign): number | null {
    if (!c.lastSyncAt) return null;
    const ms = Date.now() - new Date(c.lastSyncAt).getTime();
    return Math.floor(ms / 86400000);
  }

  function syncFreshness(c: Campaign): 'fresh' | 'stale' | 'never' {
    const d = daysSinceSync(c);
    if (d === null) return 'never';
    return d <= 7 ? 'fresh' : 'stale';
  }

  let filtered = $derived.by(() => {
    let list = campaigns;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((c) =>
        (c.campaignName || '').toLowerCase().includes(q) ||
        c.campaignId.toLowerCase().includes(q)
      );
    }
    return list;
  });

  let sorted = $derived.by(() => {
    const arr = [...filtered];
    switch (sortBy) {
      case 'spend': return arr.sort((a, b) => b.totalSpendGtq - a.totalSpendGtq);
      case 'impressions': return arr.sort((a, b) => b.totalImpressions - a.totalImpressions);
      case 'clicks': return arr.sort((a, b) => b.totalClicks - a.totalClicks);
      case 'conversions': return arr.sort((a, b) => b.totalConversions - a.totalConversions);
      case 'costPerConversion': return arr.sort((a, b) => {
        const av = a.costPerConversionGtq ?? Infinity;
        const bv = b.costPerConversionGtq ?? Infinity;
        return av - bv;
      });
      case 'lastSync': return arr.sort((a, b) => (b.lastSyncAt ?? '').localeCompare(a.lastSyncAt ?? ''));
    }
  });

  function fmtSyncDays(d: number | null): string {
    if (d === null) return '—';
    if (d === 0) return 'hoy';
    if (d === 1) return 'ayer';
    return `${d}d`;
  }
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-3 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Ads</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {campaigns.length} campaña{campaigns.length === 1 ? '' : 's'} ·
        <span class="text-mono" style="color: var(--color-accent);">Q{totals.spend.toFixed(0)}</span> spend ·
        {totals.conversions} conv
      </span>
    </div>

    <!-- Period + refresh row -->
    <div class="mb-3 flex flex-wrap items-center gap-2">
      {#each [[7,'7d'],[30,'30d'],[90,'90d']] as [days, lbl]}
        {@const active = periodDays === days}
        <button
          type="button"
          onclick={() => (periodDays = days as 7 | 30 | 90)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >Período: {lbl}</button>
      {/each}

      <button
        type="button"
        onclick={loadCampaigns}
        disabled={loading}
        class="ml-auto flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1 text-[11px] text-[var(--color-text-secondary)]"
      >
        <RefreshCw size={12} strokeWidth={2} /> Refresh
      </button>
    </div>

    <!-- Search -->
    <div class="relative mb-3">
      <Search size={12} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
      <input
        type="text"
        bind:value={search}
        placeholder="Buscar nombre o ID de campaña..."
        class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1.5 pl-8 pr-3 text-[11.5px] text-[var(--color-text-primary)]"
      />
    </div>

    <!-- Sort pills -->
    <div class="flex flex-wrap gap-1.5">
      {#each [['spend','Spend'],['conversions','Conv'],['clicks','Clicks'],['impressions','Imp'],['costPerConversion','Cost/Conv'],['lastSync','Sync']] as [key, lbl]}
        {@const active = sortBy === key}
        <button
          type="button"
          onclick={() => (sortBy = key as SortKey)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px]"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >Sort: {lbl}</button>
      {/each}
    </div>
  </div>

  <!-- List -->
  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando campañas…</div>
    {:else if sorted.length === 0}
      <div class="px-6 py-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">
        {#if campaigns.length === 0}
          > Sin campañas sincronizadas. Configurar Meta sync en Settings.
        {:else}
          > 0 campañas que matchean los filtros
        {/if}
      </div>
    {:else}
      {#each sorted as c (c.campaignId)}
        {@const fresh = syncFreshness(c)}
        {@const days = daysSinceSync(c)}
        <button
          type="button"
          onclick={() => (openCampaignId = c.campaignId)}
          class="flex w-full items-baseline border-b border-[var(--color-border)] px-6 py-2 text-left transition-colors hover:bg-[var(--color-surface-1)]"
          style="border-left: 3px solid {fresh === 'fresh' ? 'var(--color-accent)' : fresh === 'stale' ? 'var(--color-warning)' : 'var(--color-border)'};"
        >
          <div class="w-5 flex-shrink-0">
            <TrendingUp size={11} strokeWidth={1.8} style="color: {fresh === 'fresh' ? 'var(--color-accent)' : 'var(--color-text-muted)'};" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline gap-2">
              <span class="text-[12.5px] font-medium text-[var(--color-text-primary)]">{c.campaignName ?? c.campaignId}</span>
              {#if fresh === 'never'}
                <span class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]" style="background: rgba(180,181,184,0.2); color: var(--color-text-muted);">SIN SYNC</span>
              {/if}
            </div>
            <div class="text-[10px] text-[var(--color-text-tertiary)]">
              <span class="text-mono">{c.campaignId}</span> · sync {fmtSyncDays(days)}
            </div>
          </div>
          <div class="text-mono flex flex-shrink-0 items-baseline gap-3 text-[10.5px]">
            <span class="text-[var(--color-text-tertiary)]">{c.totalImpressions.toLocaleString()}</span>
            <span class="text-[var(--color-text-tertiary)]">{c.totalClicks}c</span>
            <span class="font-semibold" style="color: var(--color-accent);">{c.totalConversions}cv</span>
            <span class="w-16 text-right font-semibold" style="color: var(--color-accent);">Q{c.totalSpendGtq.toFixed(0)}</span>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

{#if openCampaignId}
  <CampaignDetailModal campaignId={openCampaignId} onClose={() => (openCampaignId = null)} />
{/if}
