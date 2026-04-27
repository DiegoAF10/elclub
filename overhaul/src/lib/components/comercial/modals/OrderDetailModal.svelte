<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { OrderForModal, SaleAttribution } from '$lib/data/comercial';
  import { Package, MessageCircle, Truck, Phone, Loader2, TrendingUp } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    orderRef: string;
    onClose: () => void;
  }

  let { orderRef, onClose }: Props = $props();

  let order = $state<OrderForModal | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let action = $state<'idle' | 'shipping'>('idle');
  let attribution = $state<SaleAttribution | null>(null);

  $effect(() => {
    loadOrder();
  });

  $effect(() => {
    if (order) {
      void (async () => {
        try {
          attribution = await adapter.getSaleAttribution(order.saleId);
        } catch (e) {
          console.warn('[order-detail] attribution load failed', e);
        }
      })();
    }
  });

  async function loadOrder() {
    loading = true;
    error = null;
    try {
      order = await adapter.getOrderForModal(orderRef);
      if (!order) error = `Orden ${orderRef} no encontrada`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Error desconocido';
    } finally {
      loading = false;
    }
  }

  async function handleMarkShipped() {
    if (!order || action === 'shipping') return;
    const tracking = window.prompt('Tracking code (opcional, ej. Forza ABC123):', '');
    action = 'shipping';
    try {
      await adapter.markOrderShipped(order.ref, tracking?.trim() || undefined);
      // Recargar para reflejar cambio
      await loadOrder();
    } catch (e) {
      alert(`Falló: ${e instanceof Error ? e.message : e}`);
    } finally {
      action = 'idle';
    }
  }

  function handleContact() {
    if (!order?.customer.phone) return;
    const cleanPhone = order.customer.phone.replace(/\D/g, '');
    window.open(`https://wa.me/${cleanPhone}?text=Hola%20${encodeURIComponent(order.customer.name)}!`, '_blank');
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" />
        <span class="text-[14px]">Cargando orden…</span>
      </div>
    {:else if order}
      <div class="flex items-center gap-3">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-[6px]"
          style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);"
        >
          <Package size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
        </div>
        <div>
          <div class="flex items-center gap-2 text-[18px] font-semibold">
            <span class="text-mono">{order.ref}</span>
            <span
              class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]"
              style="
                background: {order.status === 'shipped' ? 'rgba(74,222,128,0.18)' : order.status === 'paid' ? 'rgba(251,191,36,0.18)' : 'rgba(107,110,117,0.2)'};
                color: {order.status === 'shipped' ? 'var(--color-accent)' : order.status === 'paid' ? 'var(--color-warning)' : 'var(--color-text-secondary)'};
              "
            >● {order.status.toUpperCase()}</span>
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            {order.customer.name} · {order.customer.platform.toUpperCase()} · {fmtDate(order.paidAt)}
          </div>
        </div>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if order}
      <div class="grid grid-cols-[1fr_280px] gap-0 h-full">
        <!-- Items -->
        <div class="border-r border-[var(--color-border)] px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Items · {order.items.length}</div>
          {#each order.items as item}
            <div class="mb-3 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
              <div class="text-mono text-[11.5px] text-[var(--color-text-primary)]">{item.familyId}</div>
              <div class="mt-1 flex items-center gap-3 text-[10.5px] text-[var(--color-text-tertiary)]">
                <span>SKU: {item.jerseySku ?? '—'}</span>
                <span>·</span>
                <span>Talla: {item.size}</span>
                <span>·</span>
                <span class="text-mono">Q{item.unitPriceGtq}</span>
              </div>
              {#if item.personalizationJson}
                <div class="mt-1 text-[10.5px] text-[var(--color-text-secondary)]">
                  Personalización: {item.personalizationJson}
                </div>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Sidebar customer -->
        <div class="px-4 py-4 bg-[var(--color-surface-0)]">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Cliente</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Nombre</span><span>{order.customer.name}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{order.customer.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Handle</span><span>{order.customer.handle ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Plataforma</span><span class="uppercase">{order.customer.platform}</span></div>
          </div>

          <div class="text-display mt-5 mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Pago</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Método</span><span>{order.paymentMethod}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Total</span><span class="text-mono font-semibold" style="color: var(--color-accent);">Q{order.totalGtq}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Pagado</span><span>{fmtDate(order.paidAt)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Despachado</span><span>{fmtDate(order.shippedAt)}</span></div>
          </div>

          {#if order.notes}
            <div class="text-display mt-5 mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Notas</div>
            <div class="rounded-[3px] bg-[var(--color-surface-1)] p-2 text-[11px] text-[var(--color-text-secondary)]">
              {order.notes}
            </div>
          {/if}

          {#if attribution}
            <div class="mt-5 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
              <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Atribución</div>
              <div class="flex items-center gap-2 text-[11px]">
                <TrendingUp size={12} strokeWidth={1.8} style="color: var(--color-accent);" />
                <span class="font-medium">{attribution.adCampaignName ?? attribution.adCampaignId ?? '—'}</span>
                {#if attribution.source}
                  <span class="text-[9px] text-[var(--color-text-muted)]">· {attribution.source}</span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if order}
      <div class="flex items-center justify-between gap-2">
        <div class="flex gap-2">
          <button
            type="button"
            onclick={handleContact}
            disabled={!order.customer.phone}
            class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)] disabled:opacity-40 hover:border-[var(--color-border-strong)]"
          >
            <MessageCircle size={12} strokeWidth={1.8} />
            Mensaje WA
          </button>
          {#if order.status !== 'shipped'}
            <button
              type="button"
              onclick={handleMarkShipped}
              disabled={action === 'shipping'}
              class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
            >
              {#if action === 'shipping'}
                <Loader2 size={12} class="animate-spin" />
                Marcando…
              {:else}
                <Truck size={12} strokeWidth={2.2} />
                Marcar despachado
              {/if}
            </button>
          {/if}
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        >Cerrar</button>
      </div>
    {/if}
  {/snippet}
</BaseModal>
