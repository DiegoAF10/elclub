<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Period, FunnelKPIs, Lead, ConversationMeta, Customer, ComercialTab, FunnelAwarenessReal } from '$lib/data/comercial';
  import { resolvePeriod } from '$lib/data/kpis';
  import { computeFunnelKPIs } from '$lib/data/funnelKpis';
  import LeadProfileModal from '../modals/LeadProfileModal.svelte';
  import ConversationThreadModal from '../modals/ConversationThreadModal.svelte';
  import CampaignDetailModal from '../modals/CampaignDetailModal.svelte';
  import type { SyncResult } from '$lib/data/manychatSync';

  interface Props {
    period: Period;
    lastSyncResult?: SyncResult | null;
    onSwitchTab?: (tab: ComercialTab) => void;
  }
  let { period, lastSyncResult = null, onSwitchTab }: Props = $props();

  let kpis = $state<FunnelKPIs | null>(null);
  let loading = $state(true);
  let leadsList = $state<Lead[]>([]);
  let convsList = $state<ConversationMeta[]>([]);
  let customersList = $state<Customer[]>([]);

  // Awareness real data
  let awarenessReal = $state<FunnelAwarenessReal | null>(null);
  let openCampaignId = $state<string | null>(null);
  let showCampaignPicker = $state(false);

  // Modal triggers
  let openInterest = $state(false);
  let openConsideration = $state(false);
  let openSale = $state<string | null>(null);

  $effect(() => {
    void period;
    void lastSyncResult;  // re-load when sync finishes
    loadAll();
  });

  $effect(() => {
    void (async () => {
      try {
        awarenessReal = await adapter.getFunnelAwarenessReal();
      } catch (e) {
        console.warn('[funnel] awareness load failed', e);
      }
    })();
  });

  async function loadAll() {
    loading = true;
    const range = resolvePeriod(period);
    try {
      const [leads, convs, sales, customers, adSpend] = await Promise.all([
        adapter.listLeads({ range }).catch(() => []),
        adapter.listConversations({ range }).catch(() => []),
        adapter.listSalesInRange?.(range) ?? Promise.resolve([]),
        adapter.listCustomers().catch(() => []),
        adapter.listAdSpendInRange?.(range) ?? Promise.resolve([]),
      ]);
      leadsList = leads;
      convsList = convs;
      customersList = customers;
      const salesAdapted = sales.map((s: any) => ({
        ref: s.ref, totalGtq: s.totalGtq, paidAt: s.paidAt, status: s.status,
      }));
      const adSpendAdapted = adSpend.map((a: any) => ({
        campaignId: a.campaignId, spendGtq: a.spendGtq, capturedAt: a.capturedAt,
      }));
      kpis = computeFunnelKPIs(range, leads, convs, salesAdapted, customers, adSpendAdapted);
    } catch (e) {
      console.warn('[funnel] load failed', e);
      kpis = null;
    } finally {
      loading = false;
    }
  }

  function fmtPct(v: number): string {
    return `${(v * 100).toFixed(0)}%`;
  }

  function convArrowColor(v: number): string {
    if (v >= 0.20) return 'var(--color-accent)';
    if (v >= 0.05) return 'var(--color-warning)';
    return 'var(--color-danger)';
  }
</script>

<div class="px-6 py-4">
  <h1 class="mb-4 text-[18px] font-semibold">Funnel · {period}</h1>

  {#if loading}
    <div class="text-[12px] text-[var(--color-text-tertiary)]">Cargando funnel…</div>
  {:else if !kpis}
    <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin data</div>
  {:else}
    <div class="grid grid-cols-5 gap-3">
      <!-- Stage 1: Awareness -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid #60a5fa;">
        <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Awareness</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums text-[var(--color-text-tertiary)]">—</div>
        {#if awarenessReal && awarenessReal.totalCampaigns > 0}
          <div class="mt-2 space-y-1 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Imp</span><span class="text-mono">{awarenessReal.impressions.toLocaleString()}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Clicks</span><span class="text-mono">{awarenessReal.clicks.toLocaleString()}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Spend</span><span class="text-mono" style="color: var(--color-accent);">Q{awarenessReal.spendGtq.toFixed(0)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">CTR</span><span class="text-mono">{awarenessReal.ctr ? `${awarenessReal.ctr.toFixed(2)}%` : '—'}</span></div>
          </div>
          <button
            type="button"
            onclick={() => {
              if (awarenessReal!.byCampaign.length === 1) {
                openCampaignId = awarenessReal!.byCampaign[0].campaignId;
              } else {
                showCampaignPicker = true;
              }
            }}
            class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
          >Ver detalle ({awarenessReal.totalCampaigns} camp.) →</button>
        {:else}
          <div class="mt-2 text-[11px] text-[var(--color-text-tertiary)]">
            Sin sync de Meta Ads aún.
            <button type="button" onclick={() => onSwitchTab?.('settings')} class="text-[var(--color-accent)] hover:underline">Configurar →</button>
          </div>
        {/if}
      </div>

      <!-- Stage 2: Interest -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid #60a5fa;">
        <div class="text-display mb-1 text-[9.5px]" style="color: #60a5fa;">Interest</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: #60a5fa;">{kpis.interest.totalLeads}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>WhatsApp</span><span class="text-mono">{kpis.interest.byPlatform.wa}</span></div>
          <div class="flex justify-between"><span>Instagram</span><span class="text-mono">{kpis.interest.byPlatform.ig}</span></div>
          <div class="flex justify-between"><span>Messenger</span><span class="text-mono">{kpis.interest.byPlatform.messenger}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openInterest = true)}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 3: Consideration -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-warning);">
        <div class="text-display mb-1 text-[9.5px]" style="color: var(--color-warning);">Consideration</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: var(--color-warning);">{kpis.consideration.activeConversations}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Pendientes</span><span class="text-mono">{kpis.consideration.pending}</span></div>
          <div class="flex justify-between"><span>Objections</span><span class="text-mono">{kpis.consideration.objection}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openConsideration = true)}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 4: Sale -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-accent);">
        <div class="text-display mb-1 text-[9.5px]" style="color: var(--color-accent);">Sale</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums" style="color: var(--color-accent);">{kpis.sale.ordersToday}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Esperando pago</span><span class="text-mono">{kpis.sale.awaitingPayment}</span></div>
          <div class="flex justify-between"><span>Esperando desp.</span><span class="text-mono">{kpis.sale.awaitingShipment}</span></div>
        </div>
        <button
          type="button"
          onclick={() => (openSale = '__list__')}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>

      <!-- Stage 5: Retention -->
      <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4" style="border-top: 3px solid var(--color-text-tertiary);">
        <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Retention</div>
        <div class="text-mono mb-2 text-[28px] font-semibold tabular-nums">{kpis.retention.totalCustomers}</div>
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Repeat rate</span><span class="text-mono">{fmtPct(kpis.retention.repeatRate)}</span></div>
          <div class="flex justify-between"><span>LTV avg</span><span class="text-mono">Q{kpis.retention.ltvAvgGtq.toFixed(0)}</span></div>
          <div class="flex justify-between"><span>VIP inactivos</span><span class="text-mono">{kpis.retention.vipInactive60d}</span></div>
        </div>
        <button
          type="button"
          onclick={() => onSwitchTab?.('customers')}
          class="mt-3 text-[10px] text-[var(--color-accent)] hover:underline"
        >Ver detalle →</button>
      </div>
    </div>

    <!-- Conversion arrows row -->
    <div class="mt-3 grid grid-cols-5 gap-3">
      <div></div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.awarenessToInterest)};">→ {fmtPct(kpis.conversion.awarenessToInterest)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.interestToConsideration)};">→ {fmtPct(kpis.conversion.interestToConsideration)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.considerationToSale)};">→ {fmtPct(kpis.conversion.considerationToSale)} conv</span>
      </div>
      <div class="text-center text-[10px]">
        <span style="color: {convArrowColor(kpis.conversion.saleToRetention)};">→ {fmtPct(kpis.conversion.saleToRetention)} conv</span>
      </div>
    </div>

    {#if lastSyncResult}
      <div class="mt-4 text-[10px] text-[var(--color-text-muted)]">
        {#if lastSyncResult.ok}
          Última sync ManyChat: {lastSyncResult.leadsUpserted} leads, {lastSyncResult.conversationsUpserted} convs · {lastSyncResult.lastSyncAt}
        {:else}
          ⚠ Sync falló: {lastSyncResult.error ?? 'desconocido'}
        {/if}
      </div>
    {/if}
  {/if}
</div>

{#if openInterest}
  <LeadProfileModal leads={leadsList} onClose={() => { openInterest = false; loadAll(); }} />
{/if}

{#if openConsideration}
  <ConversationThreadModal conversations={convsList} onClose={() => { openConsideration = false; loadAll(); }} />
{/if}

{#if openSale === '__list__'}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onclick={() => (openSale = null)}>
    <div class="rounded-lg bg-[var(--color-surface-1)] p-6 text-[12px] text-[var(--color-text-secondary)]">
      Para ver órdenes específicas, andá al tab Inbox.
      <button class="ml-2 text-[var(--color-accent)] underline" onclick={() => (openSale = null)}>OK</button>
    </div>
  </div>
{/if}

{#if showCampaignPicker && awarenessReal}
  <div
    role="dialog"
    aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
    onclick={() => (showCampaignPicker = false)}
    onkeydown={(e) => { if (e.key === 'Escape') showCampaignPicker = false; }}
    tabindex="-1"
  >
    <div
      role="document"
      class="rounded-[6px] border border-[var(--color-border)] bg-[var(--color-surface-0)] p-4 max-w-[400px] w-full"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="text-display mb-2 text-[10px] text-[var(--color-text-tertiary)]">Elegí una campaña</div>
      {#each awarenessReal.byCampaign as bc}
        <button
          type="button"
          onclick={() => { openCampaignId = bc.campaignId; showCampaignPicker = false; }}
          class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 mb-1 text-[11px] hover:border-[var(--color-accent)]"
        >
          <div class="flex items-baseline justify-between">
            <span>{bc.campaignName ?? bc.campaignId}</span>
            <span class="text-mono" style="color: var(--color-accent);">Q{bc.spendGtq.toFixed(0)}</span>
          </div>
        </button>
      {/each}
    </div>
  </div>
{/if}

{#if openCampaignId}
  <CampaignDetailModal campaignId={openCampaignId} onClose={() => (openCampaignId = null)} />
{/if}
