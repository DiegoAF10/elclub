<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { PeriodRange, HomeSnapshot } from '$lib/data/finanzas';
  import { previousPeriodRange } from '$lib/data/finanzasPeriods';
  import ProfitHeroCard from '../home/ProfitHeroCard.svelte';
  import CashCard from '../home/CashCard.svelte';
  import CapitalCard from '../home/CapitalCard.svelte';
  import ShareholderLoanCard from '../home/ShareholderLoanCard.svelte';
  import WaterfallMini from '../home/WaterfallMini.svelte';
  import RecentExpenses from '../home/RecentExpenses.svelte';
  import InboxFinanciero from '../home/InboxFinanciero.svelte';

  let { periodRange }: { periodRange: PeriodRange } = $props();

  let snapshot = $state<HomeSnapshot | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    loadSnapshot(periodRange);
  });

  async function loadSnapshot(range: PeriodRange) {
    loading = true;
    error = null;
    try {
      const prev = previousPeriodRange(range);
      snapshot = await adapter.getHomeSnapshot(
        range.start, range.end, range.label,
        prev.start, prev.end,
      );
    } catch (e) {
      console.error('getHomeSnapshot failed', e);
      error = e instanceof Error ? e.message : String(e);
      snapshot = null;
    } finally {
      loading = false;
    }
  }
</script>

<div class="flex-1 p-6 overflow-y-auto">
  {#if loading || !snapshot}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)]">Cargando snapshot…</div>
  {:else if error}
    <div class="text-mono text-[12px] text-[var(--color-danger)]">⚠ {error}</div>
  {:else}
    <!-- Quadrants: primary card gets 2fr, three secondary each get 1fr -->
    <div class="grid grid-cols-[2fr_1fr_1fr_1fr] gap-3 mb-4">
      <ProfitHeroCard profit={snapshot.profit} />
      <CashCard
        balanceGtq={snapshot.cash_business_gtq}
        syncedAt={snapshot.cash_synced_at}
        staleDays={snapshot.cash_stale_days}
      />
      <CapitalCard amount={snapshot.capital_amarrado_gtq} />
      <ShareholderLoanCard
        balance={snapshot.shareholder_loan_balance}
        trend30d={snapshot.shareholder_loan_trend_30d}
      />
    </div>

    <!-- Waterfall mini: 4 bars (Revenue / COGS / Marketing / Opex) -->
    <div class="mb-4">
      <WaterfallMini profit={snapshot.profit} />
    </div>

    <!-- Sub-grid: Recent expenses + Inbox financiero -->
    <div class="grid grid-cols-2 gap-4">
      <RecentExpenses />
      <InboxFinanciero {snapshot} />
    </div>
  {/if}
</div>
