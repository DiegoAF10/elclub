<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { SaleRow } from '$lib/data/comercial';
  import { Search, RefreshCw, Plus } from 'lucide-svelte';
  import OrderDetailModal from '../modals/OrderDetailModal.svelte';
  import SaleFormModal from '../modals/SaleFormModal.svelte';
  import { salesSyncBumper } from '$lib/data/salesSyncBus';
  import { onMount } from 'svelte';

  let sales = $state<SaleRow[]>([]);
  let total = $state(0);
  let totalRevenue = $state(0);
  let loading = $state(true);
  let search = $state('');
  let periodDays = $state<7 | 30 | 90 | 0>(30);  // 0 = all time
  let statusFilter = $state<string>('all');
  let paymentFilter = $state<string>('all');

  let openOrderRef = $state<string | null>(null);
  let openCreate = $state(false);

  type SortKey = 'date' | 'total' | 'customer' | 'status';
  let sortBy = $state<SortKey>('date');

  async function loadSales() {
    loading = true;
    try {
      const result = await adapter.listSales({
        search: search.trim() || undefined,
        status: statusFilter,
        paymentMethod: paymentFilter,
        periodDays: periodDays === 0 ? undefined : periodDays,
        limit: 500,
      });
      sales = result.sales;
      total = result.total;
      totalRevenue = result.totalRevenue;
    } catch (e) {
      console.warn('[sales-tab] load failed', e);
      sales = [];
    } finally {
      loading = false;
    }
  }

  // Debounced search
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  $effect(() => {
    // Track all filter dependencies
    void search; void periodDays; void statusFilter; void paymentFilter;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { void loadSales(); }, 250);
    return () => { if (searchTimer) clearTimeout(searchTimer); };
  });

  // R11: reload when SettingsTab triggers import (via salesSyncBus)
  onMount(() => {
    const unsubscribe = salesSyncBumper.subscribe(() => {
      void loadSales();
    });
    return unsubscribe;
  });

  let sorted = $derived.by(() => {
    const arr = [...sales];
    switch (sortBy) {
      case 'date': return arr.sort((a, b) => (b.occurredAt ?? '').localeCompare(a.occurredAt ?? ''));
      case 'total': return arr.sort((a, b) => b.totalGtq - a.totalGtq);
      case 'customer': return arr.sort((a, b) => (a.customerName ?? '').localeCompare(b.customerName ?? ''));
      case 'status': return arr.sort((a, b) => a.fulfillmentStatus.localeCompare(b.fulfillmentStatus));
    }
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }

  function statusColor(s: string): string {
    if (s === 'delivered') return 'var(--color-accent)';
    if (s === 'shipped') return 'var(--color-accent)';
    if (s === 'cancelled') return 'var(--color-danger)';
    return 'var(--color-warning)';
  }

  function statusLabel(s: string): string {
    const map: Record<string, string> = {
      pending: 'PEND',
      sent_to_supplier: 'SUPLR',
      in_production: 'PROD',
      shipped: 'SHIP',
      delivered: 'DELIV',
      cancelled: 'CANCEL',
    };
    return map[s] ?? s.toUpperCase();
  }

  function paymentLabel(p: string | null): string {
    if (!p) return '—';
    const map: Record<string, string> = {
      recurrente: 'Rec',
      transferencia: 'Trans',
      contra_entrega: 'COD',
      efectivo: 'Cash',
      otro: 'Otro',
    };
    return map[p] ?? p;
  }

  function parseAddress(raw: string | null): { zone?: string; municipality?: string; department?: string } | null {
    if (!raw) return null;
    try {
      const obj = JSON.parse(raw);
      return obj && typeof obj === 'object' ? obj : null;
    } catch {
      return null;
    }
  }

  // Sa4: beautify family_id codes returned by Python query fallback.
  // MB-CLASICA → "Mystery Box · Clásica" · JRS-BARCELONA-201415-H → "Barcelona 2014/15 H" · CUSTOM-* → "Personalizado".
  function beautifyLabel(label: string | null | undefined): string {
    if (!label) return '';
    const raw = label.trim();
    if (!raw) return '';
    if (raw.startsWith('MB-')) {
      const variant = raw.slice(3).toLowerCase();
      const cap = variant.charAt(0).toUpperCase() + variant.slice(1);
      return `Mystery Box · ${cap}`;
    }
    if (raw.startsWith('CUSTOM-')) return 'Personalizado';
    if (raw.startsWith('JRS-')) {
      const parts = raw.slice(4).split('-');
      if (parts.length >= 2) {
        const team = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
        const season = parts[1];
        const variantSuffix = parts.slice(2).join('-');
        const seasonFmt = season.length === 6 ? `${season.slice(0, 4)}/${season.slice(4)}` : season;
        return `${team} ${seasonFmt}${variantSuffix ? ' ' + variantSuffix : ''}`;
      }
    }
    return raw.charAt(0).toUpperCase() + raw.slice(1);
  }

  function joinItems(labels: string[] | null, max = 3): string {
    if (!labels || labels.length === 0) return '';
    const beautified = labels.map(beautifyLabel).filter(Boolean);
    if (beautified.length === 0) return '';
    const head = beautified.slice(0, max).join(' · ');
    return beautified.length > max ? `${head} · +${beautified.length - max} más` : head;
  }

  function modalityLabel(m: string): string {
    if (m === 'mystery') return 'MYS';
    if (m === 'stock') return 'DROP';
    if (m === 'ondemand') return 'VAULT';
    return m.toUpperCase();
  }
  function modalityBg(m: string): string {
    if (m === 'mystery') return 'rgba(168, 85, 247, 0.18)';   // purple
    if (m === 'stock') return 'rgba(56, 189, 248, 0.18)';     // sky-blue
    if (m === 'ondemand') return 'rgba(74, 222, 128, 0.18)';  // accent green
    return 'rgba(180,181,184,0.18)';
  }
  function modalityFg(m: string): string {
    if (m === 'mystery') return '#c084fc';
    if (m === 'stock') return '#7dd3fc';
    if (m === 'ondemand') return 'var(--color-accent)';
    return 'var(--color-text-muted)';
  }
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-3 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Sales</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {total} órden{total === 1 ? '' : 'es'} ·
        <span class="text-mono" style="color: var(--color-accent);">Q{totalRevenue.toFixed(0)}</span> total
      </span>
    </div>

    <!-- Period + filters -->
    <div class="mb-3 flex flex-wrap items-center gap-2">
      {#each [[7,'7d'],[30,'30d'],[90,'90d'],[0,'All']] as [d, lbl]}
        {@const active = periodDays === d}
        <button
          type="button"
          onclick={() => (periodDays = d as 7 | 30 | 90 | 0)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >Período: {lbl}</button>
      {/each}

      <select
        bind:value={statusFilter}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        <option value="all">Status: All</option>
        <option value="pending">Status: Pending</option>
        <option value="sent_to_supplier">Status: Supplier</option>
        <option value="in_production">Status: Production</option>
        <option value="shipped">Status: Shipped</option>
        <option value="delivered">Status: Delivered</option>
        <option value="cancelled">Status: Cancelled</option>
      </select>

      <select
        bind:value={paymentFilter}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        <option value="all">Pago: All</option>
        <option value="recurrente">Pago: Recurrente</option>
        <option value="transferencia">Pago: Transferencia</option>
        <option value="contra_entrega">Pago: COD</option>
        <option value="efectivo">Pago: Efectivo</option>
        <option value="otro">Pago: Otro</option>
      </select>

      <button
        type="button"
        onclick={() => (openCreate = true)}
        class="ml-auto flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1 text-[11px] font-semibold text-black"
      >
        <Plus size={12} strokeWidth={2} /> Nueva venta
      </button>

      <button
        type="button"
        onclick={loadSales}
        disabled={loading}
        class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1 text-[11px] text-[var(--color-text-secondary)]"
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
        placeholder="Buscar ref, cliente, teléfono..."
        class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1.5 pl-8 pr-3 text-[11.5px] text-[var(--color-text-primary)]"
      />
    </div>

    <!-- Sort pills -->
    <div class="flex flex-wrap gap-1.5">
      {#each [['date','Fecha'],['total','Q total'],['customer','Cliente'],['status','Status']] as [key, lbl]}
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

  <!-- Table header -->
  <div class="text-display flex border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-1.5 text-[9px] text-[var(--color-text-tertiary)]">
    <div class="w-28">REF · FECHA</div>
    <div class="flex-1 min-w-0">CLIENTE · ITEM</div>
    <div class="w-52 text-right">STATUS · TOTAL</div>
  </div>

  <!-- List -->
  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando sales…</div>
    {:else if sorted.length === 0}
      <div class="px-6 py-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">
        > 0 sales que matchean los filtros · Importá histórico desde Settings.
      </div>
    {:else}
      {#each sorted as s (s.saleId)}
        <button
          type="button"
          onclick={() => (openOrderRef = s.ref)}
          class="flex w-full items-start gap-3 border-b border-[var(--color-border)] px-6 py-2 text-left transition-colors hover:bg-[var(--color-surface-1)]"
          style="border-left: 3px solid {statusColor(s.fulfillmentStatus)};"
        >
          <!-- LEFT: REF + FECHA stacked -->
          <div class="w-28 flex-shrink-0">
            <div class="text-mono truncate text-[11px] text-[var(--color-text-primary)]" title={s.ref}>{s.ref}</div>
            <div class="text-mono text-[9.5px] text-[var(--color-text-muted)]">{fmtDate(s.occurredAt)}</div>
          </div>

          <!-- CENTER: cliente + items + address -->
          <div class="flex-1 min-w-0">
            <div class="flex items-baseline gap-1.5 truncate">
              <span class="truncate text-[11.5px] font-medium text-[var(--color-text-primary)]">{s.customerName ?? '—'}</span>
              {#if s.customerPhone}
                <span class="text-mono flex-shrink-0 text-[9.5px] text-[var(--color-text-muted)]">{s.customerPhone}</span>
              {/if}
            </div>
            {#if s.itemsAllLabels && s.itemsAllLabels.length > 0}
              <div class="truncate text-[10.5px] text-[var(--color-text-tertiary)]">
                {joinItems(s.itemsAllLabels)}
              </div>
            {:else if s.firstItemLabel}
              <div class="truncate text-[10.5px] text-[var(--color-text-tertiary)]">
                {beautifyLabel(s.firstItemLabel)}{#if s.itemsCount > 1}<span class="text-[var(--color-text-muted)]"> · +{s.itemsCount - 1} más</span>{/if}
              </div>
            {:else}
              <div class="text-[10px] text-[var(--color-text-muted)] italic">sin items</div>
            {/if}
            {#if s.shippingAddress}
              {@const addr = parseAddress(s.shippingAddress)}
              {#if addr && (addr.zone || addr.municipality)}
                <div class="text-[9.5px] text-[var(--color-text-muted)] truncate">
                  📍 {[addr.zone ? `Zona ${addr.zone}` : null, addr.municipality, addr.department].filter(Boolean).join(' · ')}
                </div>
              {/if}
            {/if}
          </div>

          <!-- RIGHT: pills row + total stacked -->
          <div class="w-52 flex-shrink-0 text-right">
            <!-- Pills row -->
            <div class="flex items-center justify-end gap-1 flex-wrap">
              <span class="text-display text-[9px]" style="color: {statusColor(s.fulfillmentStatus)};">
                ● {statusLabel(s.fulfillmentStatus)}
              </span>
              {#if s.modality}
                <span class="text-display rounded-[2px] px-1 py-0.5 text-[8.5px]" style="background: {modalityBg(s.modality)}; color: {modalityFg(s.modality)};">
                  {modalityLabel(s.modality)}
                </span>
              {/if}
              {#if s.paymentMethod}
                <span class="text-mono text-[9px] text-[var(--color-text-muted)]">{paymentLabel(s.paymentMethod)}</span>
              {/if}
              {#if s.origin}
                <span class="text-mono text-[9px] text-[var(--color-text-muted)]">· {s.origin}</span>
              {/if}
            </div>
            <!-- Total row -->
            <div class="mt-1 flex items-baseline justify-end gap-2">
              <span class="text-mono text-[9.5px] text-[var(--color-text-tertiary)]">{s.itemsCount}×</span>
              <span class="text-mono text-[13px] font-semibold" style="color: {s.totalGtq > 0 ? 'var(--color-accent)' : 'var(--color-text-muted)'};">
                Q{s.totalGtq.toFixed(0)}
              </span>
            </div>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

{#if openOrderRef}
  <OrderDetailModal orderRef={openOrderRef} onClose={() => { openOrderRef = null; void loadSales(); }} />
{/if}

{#if openCreate}
  <SaleFormModal mode="create" onClose={() => { openCreate = false; void loadSales(); }} />
{/if}
