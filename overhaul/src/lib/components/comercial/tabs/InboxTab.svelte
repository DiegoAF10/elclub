<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ComercialEvent, EventSeverity } from '$lib/data/comercial';
  import { AlertTriangle, Check, Info, X } from 'lucide-svelte';
  import OrderDetailModal from '../modals/OrderDetailModal.svelte';

  let events = $state<ComercialEvent[]>([]);
  let loading = $state(true);
  let filter = $state<EventSeverity | 'all'>('all');
  let search = $state('');

  // Para abrir el OrderDetailModal cuando el evento es de tipo orden
  let openedOrderRef = $state<string | null>(null);

  // Auto-refresh cada 60s (alineado con polling worker→ERP)
  let refreshTimer: ReturnType<typeof setInterval>;

  $effect(() => {
    loadEvents();
    refreshTimer = setInterval(loadEvents, 60_000);
    return () => clearInterval(refreshTimer);
  });

  async function loadEvents() {
    try {
      const list = await adapter.listEvents({ status: 'active' });
      events = list;
    } catch (e) {
      console.warn('[inbox] load failed', e);
    } finally {
      loading = false;
    }
  }

  let filtered = $derived.by(() => {
    let list = events;
    if (filter !== 'all') list = list.filter((e) => e.severity === filter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((e) => e.title.toLowerCase().includes(q) || (e.sub ?? '').toLowerCase().includes(q));
    }
    return list;
  });

  let grouped = $derived.by(() => {
    const out: Record<EventSeverity, ComercialEvent[]> = { crit: [], warn: [], info: [], strat: [] };
    for (const e of filtered) out[e.severity].push(e);
    return out;
  });

  function severityColor(s: EventSeverity) {
    return s === 'crit' ? 'var(--color-danger)' :
           s === 'warn' ? 'var(--color-warning)' :
           s === 'info' ? 'var(--color-info, #60a5fa)' :
           'var(--color-text-tertiary)';
  }

  function severityLabel(s: EventSeverity) {
    return s === 'crit' ? '🔴 Crítico' :
           s === 'warn' ? '🟡 Atención' :
           s === 'info' ? '🔵 Info' :
           '⚪ Estratégico';
  }

  function fmtAge(iso: string): string {
    const ms = Date.now() - new Date(iso).getTime();
    const h = Math.floor(ms / 3600_000);
    if (h < 1) return `${Math.floor(ms / 60_000)}m`;
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  }

  async function handleEventClick(event: ComercialEvent) {
    if (event.type === 'order_pending_24h' || event.type === 'order_new') {
      // Abrir OrderDetailModal con primer order ref de items_affected
      const orderItem = event.itemsAffected.find((i) => i.type === 'order');
      if (orderItem) openedOrderRef = orderItem.id;
    }
    // R3+ agregará otros tipos (lead, campaign, etc.)
  }

  async function handleIgnore(event: ComercialEvent) {
    await adapter.setEventStatus(event.eventId, 'ignored');
    loadEvents();
  }

  async function handleResolve(event: ComercialEvent) {
    await adapter.setEventStatus(event.eventId, 'resolved');
    loadEvents();
  }
</script>

<div class="flex h-full flex-col">

  <!-- Header con filtros + search -->
  <div class="border-b border-[var(--color-border)] px-6 py-4">
    <div class="mb-2 flex items-baseline justify-between">
      <h1 class="text-[18px] font-semibold">Inbox</h1>
      <span class="text-[11px] text-[var(--color-text-tertiary)]">
        {events.length} eventos · {grouped.crit.length} críticos
      </span>
    </div>

    <div class="mb-3 flex flex-wrap gap-1.5">
      {#each [['all','Todo'],['crit','🔴 Crítico'],['warn','🟡 Atención'],['info','🔵 Info'],['strat','⚪ Estratégico']] as [val, lbl]}
        {@const active = filter === val}
        <button
          type="button"
          onclick={() => (filter = val as any)}
          class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
          style="
            background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
            border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
            color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
          "
        >{lbl}</button>
      {/each}
    </div>

    <input
      type="text"
      bind:value={search}
      placeholder="Buscar evento, ref, cliente..."
      class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
    />
  </div>

  <!-- Lista de eventos -->
  <div class="flex-1 overflow-y-auto px-6 py-4">
    {#if loading}
      <div class="text-[11px] text-[var(--color-text-tertiary)]">Cargando eventos…</div>
    {:else if filtered.length === 0}
      <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">
        &gt; all systems nominal. nothing to worry about.
      </div>
    {:else}
      {#each ['crit','warn','info','strat'] as sev}
        {#if grouped[sev as EventSeverity].length > 0}
          <div class="mb-5">
            <div
              class="text-display mb-2 text-[9.5px]"
              style="color: {severityColor(sev as EventSeverity)};"
            >
              {severityLabel(sev as EventSeverity)} · {grouped[sev as EventSeverity].length}
            </div>

            <div class="flex flex-col gap-2">
              {#each grouped[sev as EventSeverity] as ev (ev.eventId)}
                <button
                  type="button"
                  onclick={() => handleEventClick(ev)}
                  class="w-full text-left transition-colors"
                  style="
                    background: var(--color-surface-1);
                    border: 1px solid var(--color-border);
                    border-left: 3px solid {severityColor(sev as EventSeverity)};
                    border-radius: 4px;
                    padding: 10px 14px;
                  "
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="flex-1 min-w-0">
                      <div class="text-[12.5px] font-medium text-[var(--color-text-primary)]">{ev.title}</div>
                      {#if ev.sub}
                        <div class="text-[10.5px] text-[var(--color-text-tertiary)] mt-0.5">{ev.sub}</div>
                      {/if}
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                      <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtAge(ev.detectedAt)}</span>
                    </div>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</div>

{#if openedOrderRef}
  <OrderDetailModal
    orderRef={openedOrderRef}
    onClose={() => { openedOrderRef = null; loadEvents(); }}
  />
{/if}
