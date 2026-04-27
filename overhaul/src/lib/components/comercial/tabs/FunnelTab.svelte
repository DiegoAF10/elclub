<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Period, FunnelKPIs, Lead, ConversationMeta, Customer, ComercialTab } from '$lib/data/comercial';
  import { resolvePeriod } from '$lib/data/kpis';
  import { computeFunnelKPIs } from '$lib/data/funnelKpis';
  import LeadProfileModal from '../modals/LeadProfileModal.svelte';
  import ConversationThreadModal from '../modals/ConversationThreadModal.svelte';
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

  // Modal triggers
  let openInterest = $state(false);
  let openConsideration = $state(false);
  let openSale = $state<string | null>(null);

  $effect(() => {
    void period;
    void lastSyncResult;  // re-load when sync finishes
    loadAll();
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
        <div class="space-y-1 text-[10.5px] text-[var(--color-text-tertiary)]">
          <div class="flex justify-between"><span>Impressions</span><span class="text-mono">{kpis.awareness.impressions}</span></div>
          <div class="flex justify-between"><span>Clicks</span><span class="text-mono">{kpis.awareness.clicks}</span></div>
          <div class="flex justify-between"><span>Spend</span><span class="text-mono">Q{kpis.awareness.spendGtq.toFixed(0)}</span></div>
        </div>
        <div class="mt-3 text-[10px] italic text-[var(--color-text-muted)]">Esperando sync Meta API (R5)</div>
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
