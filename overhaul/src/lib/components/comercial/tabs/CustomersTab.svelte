<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Customer } from '$lib/data/comercial';
  import { Search, UserPlus, Star } from 'lucide-svelte';
  import CustomerProfileModal from '../modals/CustomerProfileModal.svelte';
  import CreateCustomerModal from '../modals/CreateCustomerModal.svelte';

  let customers = $state<Customer[]>([]);
  let loading = $state(true);
  let search = $state('');
  let filterVip = $state(false);
  let filterSource = $state<string>('all');
  let filterLastOrder = $state<'all' | '<30d' | '30-60d' | '60-90d' | '+90d' | 'never'>('all');
  let showBlocked = $state(false);

  type SortKey = 'ltv' | 'lastOrder' | 'totalOrders' | 'firstOrder' | 'source';
  let sortBy = $state<SortKey>('ltv');

  let openProfileId = $state<number | null>(null);
  let openCreate = $state(false);

  async function loadCustomers() {
    loading = true;
    try {
      customers = await adapter.listCustomers();
    } catch (e) {
      console.warn('[customers-tab] load failed', e);
      customers = [];
    } finally {
      loading = false;
    }
  }

  $effect(() => { void loadCustomers(); });

  function isVip(c: Customer): boolean {
    return c.totalRevenueGtq >= 1500;
  }

  function daysAgo(iso: string | null): number | null {
    if (!iso) return null;
    const ms = Date.now() - new Date(iso).getTime();
    return Math.floor(ms / 86400000);
  }

  function lastOrderBucket(c: Customer): 'never' | '<30d' | '30-60d' | '60-90d' | '+90d' {
    const d = daysAgo(c.lastOrderAt);
    if (d === null) return 'never';
    if (d < 30) return '<30d';
    if (d < 60) return '30-60d';
    if (d < 90) return '60-90d';
    return '+90d';
  }

  let filtered = $derived.by(() => {
    let list = customers;
    if (filterVip) list = list.filter(isVip);
    if (filterSource !== 'all') list = list.filter((c) => (c.source || 'manual') === filterSource);
    if (filterLastOrder !== 'all') list = list.filter((c) => lastOrderBucket(c) === filterLastOrder);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((c) =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.phone || '').toLowerCase().includes(q) ||
        (c.email || '').toLowerCase().includes(q)
      );
    }
    return list;
  });

  let sorted = $derived.by(() => {
    const arr = [...filtered];
    switch (sortBy) {
      case 'ltv': return arr.sort((a, b) => b.totalRevenueGtq - a.totalRevenueGtq);
      case 'lastOrder': return arr.sort((a, b) => (b.lastOrderAt ?? '').localeCompare(a.lastOrderAt ?? ''));
      case 'totalOrders': return arr.sort((a, b) => b.totalOrders - a.totalOrders);
      case 'firstOrder': return arr.sort((a, b) => (a.firstOrderAt ?? '').localeCompare(b.firstOrderAt ?? ''));
      case 'source': return arr.sort((a, b) => (a.source ?? '').localeCompare(b.source ?? ''));
    }
  });

  let vipCount = $derived(customers.filter(isVip).length);

  function fmtDays(d: number | null): string {
    if (d === null) return '—';
    if (d === 0) return 'hoy';
    if (d === 1) return 'ayer';
    return `${d}d`;
  }

  const SOURCES = ['all', 'f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-3 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Customers</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {customers.length} totales · {vipCount} VIP
      </span>
    </div>

    <!-- Filters row -->
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onclick={() => (filterVip = !filterVip)}
        class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
        style="
          background: {filterVip ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
          border-color: {filterVip ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
          color: {filterVip ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
        "
      >★ Solo VIP</button>

      <select
        bind:value={filterSource}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        {#each SOURCES as s}
          <option value={s}>Origen: {s}</option>
        {/each}
      </select>

      <select
        bind:value={filterLastOrder}
        class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]"
      >
        <option value="all">Última: All</option>
        <option value="<30d">Última: &lt;30d</option>
        <option value="30-60d">Última: 30-60d</option>
        <option value="60-90d">Última: 60-90d</option>
        <option value="+90d">Última: +90d</option>
        <option value="never">Última: Nunca</option>
      </select>

      <button
        type="button"
        onclick={() => (openCreate = true)}
        class="ml-auto flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1 text-[11px] font-semibold text-black"
      >
        <UserPlus size={12} strokeWidth={2} />
        Crear customer
      </button>
    </div>

    <!-- Search -->
    <div class="relative">
      <Search size={12} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
      <input
        type="text"
        bind:value={search}
        placeholder="Buscar nombre, phone, email..."
        class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1.5 pl-8 pr-3 text-[11.5px] text-[var(--color-text-primary)]"
      />
    </div>

    <!-- Sort pills -->
    <div class="mt-3 flex gap-1.5">
      {#each [['ltv','LTV'],['lastOrder','Última'],['totalOrders','Órdenes'],['firstOrder','Primera'],['source','Origen']] as [key, lbl]}
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
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando customers…</div>
    {:else if sorted.length === 0}
      <div class="px-6 py-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 customers que matchean los filtros</div>
    {:else}
      {#each sorted as c (c.customerId)}
        {@const vip = isVip(c)}
        {@const days = daysAgo(c.lastOrderAt)}
        <button
          type="button"
          onclick={() => (openProfileId = c.customerId)}
          class="flex w-full items-baseline border-b border-[var(--color-border)] px-6 py-2 text-left transition-colors hover:bg-[var(--color-surface-1)]"
        >
          <div class="w-5 flex-shrink-0">
            {#if vip}<Star size={11} fill="var(--color-accent)" stroke="var(--color-accent)" />{/if}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-baseline gap-2">
              <span class="text-[12.5px] font-medium text-[var(--color-text-primary)]">{c.name}</span>
              {#if vip}
                <span class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]" style="background: rgba(74,222,128,0.18); color: var(--color-accent);">
                  VIP
                </span>
              {/if}
            </div>
            <div class="text-[10px] text-[var(--color-text-tertiary)]">
              {c.phone ?? c.email ?? '—'} · {c.source ?? 'manual'}
            </div>
          </div>
          <div class="text-mono flex flex-shrink-0 items-baseline gap-4 text-[10.5px]">
            <span class="text-[var(--color-text-tertiary)]">{c.totalOrders} órd</span>
            <span class="font-semibold" style="color: var(--color-accent);">Q{c.totalRevenueGtq.toFixed(0)}</span>
            <span class="w-12 text-right text-[var(--color-text-muted)]">{fmtDays(days)}</span>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

{#if openProfileId !== null}
  <CustomerProfileModal
    customerId={openProfileId}
    onClose={() => { openProfileId = null; loadCustomers(); }}
  />
{/if}

{#if openCreate}
  <CreateCustomerModal
    onClose={() => { openCreate = false; loadCustomers(); }}
  />
{/if}
