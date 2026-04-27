<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CampaignDetail } from '$lib/data/comercial';
  import { Loader2, TrendingUp } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import TimeSeriesChart from '../charts/TimeSeriesChart.svelte';
  import OrderDetailModal from './OrderDetailModal.svelte';

  interface Props {
    campaignId: string;
    onClose: () => void;
  }
  let { campaignId, onClose }: Props = $props();

  let detail = $state<CampaignDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let openOrderRef = $state<string | null>(null);
  let chartMetric = $state<'spendGtq' | 'conversions' | 'revenueGtq'>('spendGtq');

  async function load() {
    loading = true;
    error = null;
    try {
      detail = await adapter.getCampaignDetail(campaignId, 30);
      if (!detail) error = `Campaña ${campaignId} sin datos en últimos 30d`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { void load(); });

  function fmtDate(iso: string): string {
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }

  let chartData = $derived.by(() => {
    if (!detail) return [];
    return detail.daily.map(d => ({
      date: d.date,
      value: chartMetric === 'spendGtq' ? d.spendGtq
           : chartMetric === 'conversions' ? d.conversions
           : d.revenueGtq,
      label: chartMetric === 'spendGtq' ? `Q${d.spendGtq.toFixed(0)}`
           : chartMetric === 'conversions' ? `${d.conversions} conv`
           : `Q${d.revenueGtq.toFixed(0)} rev`,
    }));
  });
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" /> <span class="text-[14px]">Cargando campaña…</span>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {:else if detail}
      {@const c = detail.campaign}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
          <TrendingUp size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">{c.campaignName ?? c.campaignId}</div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            <span class="text-mono">Q{c.totalSpendGtq.toFixed(0)}</span> spend ·
            {c.totalImpressions.toLocaleString()} imp ·
            {c.totalClicks} clicks ·
            {c.totalConversions} conv
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if detail}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px] overflow-hidden">
        <!-- Chart + metric switcher -->
        <div class="border-r border-[var(--color-border)] overflow-y-auto px-6 py-4">
          <div class="mb-3 flex items-center gap-2">
            {#each [['spendGtq','Spend'],['conversions','Conv'],['revenueGtq','Revenue']] as [key, lbl]}
              {@const active = chartMetric === key}
              <button
                type="button"
                onclick={() => (chartMetric = key as 'spendGtq' | 'conversions' | 'revenueGtq')}
                class="rounded-[3px] border px-2.5 py-0.5 text-[10px]"
                style="
                  background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
                  border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
                  color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
                "
              >{lbl}</button>
            {/each}
          </div>

          {#if detail.daily.length === 0}
            <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">> sin data en período</div>
          {:else}
            <TimeSeriesChart data={chartData} width={520} height={200} yAxisLabel={chartMetric} />
            <div class="mt-2 text-[10px] text-[var(--color-text-muted)]">
              {detail.daily.length} días · hover sobre puntos para fecha exacta
            </div>
          {/if}
        </div>

        <!-- Sidebar: KPIs + attributed sales -->
        <div class="overflow-y-auto bg-[var(--color-surface-0)] px-4 py-4">
          {#if detail}
          {@const c = detail.campaign}
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">KPIs</div>
          <div class="mb-4 space-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CTR</span><span class="text-mono">{c.totalImpressions ? ((c.totalClicks / c.totalImpressions) * 100).toFixed(2) : '—'}%</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CPC</span><span class="text-mono">{c.totalClicks ? `Q${(c.totalSpendGtq / c.totalClicks).toFixed(2)}` : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Cost/Conv</span><span class="text-mono">{c.costPerConversionGtq !== null ? `Q${c.costPerConversionGtq.toFixed(0)}` : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">ROAS</span><span class="text-mono">{c.totalSpendGtq ? (c.totalRevenueGtq / c.totalSpendGtq).toFixed(2) + 'x' : '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Last sync</span><span class="text-mono text-[10px]">{c.lastSyncAt ? fmtDate(c.lastSyncAt) : '—'}</span></div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Sales atribuidas · {detail.attributedSales.length}</div>
          {#if detail.attributedSales.length === 0}
            <div class="text-mono text-[10px] text-[var(--color-text-tertiary)]">> sin sales atribuidas</div>
          {:else}
            <div class="space-y-1.5">
              {#each detail.attributedSales.slice(0, 20) as s}
                <button
                  type="button"
                  onclick={() => (openOrderRef = s.ref)}
                  class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10.5px] hover:border-[var(--color-accent)]"
                >
                  <div class="flex items-baseline justify-between">
                    <span class="text-mono">{s.ref}</span>
                    <span class="text-mono font-semibold" style="color: var(--color-accent);">Q{s.totalGtq.toFixed(0)}</span>
                  </div>
                  <div class="text-[9.5px] text-[var(--color-text-tertiary)]">
                    {s.customerName ?? '—'} · {fmtDate(s.occurredAt)}
                  </div>
                </button>
              {/each}
              {#if detail.attributedSales.length > 20}
                <div class="text-[10px] text-[var(--color-text-muted)]">+{detail.attributedSales.length - 20} más</div>
              {/if}
            </div>
          {/if}
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
    >Cerrar</button>
  {/snippet}
</BaseModal>

{#if openOrderRef}
  <OrderDetailModal orderRef={openOrderRef} onClose={() => (openOrderRef = null)} />
{/if}
