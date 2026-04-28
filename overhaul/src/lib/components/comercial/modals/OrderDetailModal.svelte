<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { OrderForModal, SaleAttribution, Campaign } from '$lib/data/comercial';
  import { Package, MessageCircle, Truck, Loader2, TrendingUp, Pencil } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import SaleFormModal from './SaleFormModal.svelte';

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
  let attributionError = $state<string | null>(null);

  // Edit modal state
  let openEdit = $state(false);

  // Attribution editor state
  let editingAttribution = $state(false);
  let campaigns = $state<Campaign[]>([]);
  let selectedCampaignId = $state<string | null>(null);
  let savingAttr = $state(false);
  let attrSaveError = $state<string | null>(null);

  $effect(() => {
    loadOrder();
  });

  $effect(() => {
    if (order) {
      void (async () => {
        attributionError = null;
        try {
          attribution = await adapter.getSaleAttribution(order.saleId);
        } catch (e) {
          attributionError = e instanceof Error ? e.message : String(e);
          console.warn('[order-detail] attribution load failed', e);
        }
      })();
    }
  });

  async function loadCampaigns() {
    try {
      campaigns = await adapter.listCampaigns({ periodDays: 90 });
    } catch (e) {
      console.warn('[order-detail] campaigns load failed', e);
    }
  }

  function startEditAttr() {
    selectedCampaignId = attribution?.adCampaignId ?? null;
    attrSaveError = null;
    editingAttribution = true;
    if (campaigns.length === 0) void loadCampaigns();
  }

  async function saveAttribution() {
    if (!order) return;
    savingAttr = true;
    attrSaveError = null;
    try {
      const result = await adapter.attributeSale({
        saleId: order.saleId,
        campaignId: selectedCampaignId,
      });
      if (!result.ok) {
        attrSaveError = result.error ?? 'Error desconocido';
        return;
      }
      editingAttribution = false;
      attribution = await adapter.getSaleAttribution(order.saleId);
    } catch (e) {
      attrSaveError = e instanceof Error ? e.message : String(e);
    } finally {
      savingAttr = false;
    }
  }

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

  function fmtQ(n: number | null | undefined): string {
    if (n == null) return '—';
    return `Q${n.toFixed(0)}`;
  }

  function modalityLabel(m: string): string {
    if (m === 'mystery') return 'MYSTERY';
    if (m === 'stock') return 'DROP';
    if (m === 'ondemand') return 'VAULT';
    return m.toUpperCase();
  }
  function modalityBg(m: string): string {
    if (m === 'mystery') return 'rgba(168, 85, 247, 0.18)';
    if (m === 'stock') return 'rgba(56, 189, 248, 0.18)';
    if (m === 'ondemand') return 'rgba(74, 222, 128, 0.18)';
    return 'rgba(180,181,184,0.18)';
  }
  function modalityFg(m: string): string {
    if (m === 'mystery') return '#c084fc';
    if (m === 'stock') return '#7dd3fc';
    if (m === 'ondemand') return 'var(--color-accent)';
    return 'var(--color-text-muted)';
  }
  function paymentLabel(p: string | null): string {
    const map: Record<string, string> = {
      recurrente: 'Recurrente (tarjeta)',
      transferencia: 'Transferencia',
      contra_entrega: 'Contra entrega',
      efectivo: 'Efectivo',
      otro: 'Otro',
    };
    return p ? (map[p] ?? p) : '—';
  }
  function statusLabel(s: string): string {
    const map: Record<string, string> = {
      pending: 'PENDIENTE',
      sent_to_supplier: 'EN CHINO',
      in_production: 'EN PRODUCCIÓN',
      shipped: 'DESPACHADO',
      delivered: 'ENTREGADO',
      cancelled: 'CANCELADO',
    };
    return map[s] ?? s.toUpperCase();
  }
  function statusColor(s: string): string {
    if (s === 'delivered' || s === 'shipped') return 'var(--color-accent)';
    if (s === 'cancelled') return 'var(--color-danger)';
    return 'var(--color-warning)';
  }
  function originLabel(o: string): string {
    const map: Record<string, string> = {
      web: 'Web',
      instagram: 'Instagram',
      ig: 'Instagram',
      messenger: 'Messenger',
      whatsapp: 'WhatsApp',
      wa: 'WhatsApp',
      manual: 'Manual',
      'walk-in': 'Walk-in',
    };
    return map[o.toLowerCase()] ?? o;
  }
  function shippingMethodLabel(s: string | null): string {
    if (!s) return '—';
    const map: Record<string, string> = {
      forza: 'Forza Logistics',
      personal: 'Entrega personal',
      otro: 'Otro',
    };
    return map[s.toLowerCase()] ?? s;
  }
  function itemHeadline(item: OrderForModal['items'][0]): string {
    const parts = [item.team, item.variantLabel, item.version].filter(Boolean);
    return parts.length > 0 ? parts.join(' · ') : item.familyId;
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
      <div class="flex items-center gap-3 flex-wrap">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-[6px] flex-shrink-0"
          style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);"
        >
          <Package size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap text-[18px] font-semibold">
            <span class="text-mono">{order.ref}</span>
            <!-- Status pill -->
            <span
              class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]"
              style="background: {statusColor(order.status)}22; color: {statusColor(order.status)};"
            >● {statusLabel(order.status)}</span>
            <!-- Modality badge -->
            <span
              class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]"
              style="background: {modalityBg(order.modality)}; color: {modalityFg(order.modality)};"
            >{modalityLabel(order.modality)}</span>
          </div>
          <div class="mt-0.5 text-[11px] text-[var(--color-text-tertiary)]">
            {order.customer.name} · {originLabel(order.origin)} · {fmtDate(order.paidAt)}
          </div>
        </div>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if order}
      <div class="grid grid-cols-[1fr_300px] gap-0 h-full">

        <!-- ── LEFT: items + address + notes ──────────────────────── -->
        <div class="border-r border-[var(--color-border)] px-5 py-4 overflow-y-auto">

          <!-- Items section -->
          <div class="pb-1.5 border-b border-[var(--color-border)] mb-3">
            <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">
              ITEMS · {order.items.length}
            </span>
          </div>
          {#each order.items as item}
            <div class="mb-3 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
              <!-- Headline: Team · Variant · Version -->
              <div class="text-[12px] font-medium text-[var(--color-text-primary)]">{itemHeadline(item)}</div>
              <!-- SKU + size row -->
              <div class="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-[var(--color-text-tertiary)]">
                {#if item.jerseySku}
                  <span class="text-mono">{item.jerseySku}</span>
                  <span>·</span>
                {/if}
                <span>Talla <strong class="text-[var(--color-text-secondary)]">{item.size}</strong></span>
                {#if item.season}
                  <span>· {item.season}</span>
                {/if}
                {#if item.itemType}
                  <span class="text-display rounded-[2px] px-1 py-0.5 text-[8.5px]"
                    style="background: rgba(180,181,184,0.15); color: var(--color-text-muted);"
                  >{item.itemType.toUpperCase()}</span>
                {/if}
              </div>
              <!-- Price + cost -->
              <div class="mt-1.5 flex items-center gap-3 text-[10.5px]">
                <span class="text-mono font-semibold" style="color: var(--color-accent);">{fmtQ(item.unitPriceGtq)}</span>
                {#if item.unitCostGtq != null}
                  <span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">costo {fmtQ(item.unitCostGtq)}</span>
                {/if}
              </div>
              {#if item.personalizationJson}
                <div class="mt-1.5 rounded-[3px] bg-[var(--color-surface-0)] px-2 py-1 text-[10px] text-[var(--color-text-secondary)]">
                  <span class="text-[var(--color-text-muted)]">Personalización:</span> {item.personalizationJson}
                </div>
              {/if}
            </div>
          {/each}

          <!-- Address section (only if shippingAddress present) -->
          {#if order.shippingAddress}
            {@const addr = order.shippingAddress}
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-3 mt-5">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">
                DIRECCIÓN DE ENVÍO
              </span>
            </div>
            <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 space-y-1.5 text-[10.5px]">
              {#if addr.name}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Destinatario</span>
                  <span class="text-[var(--color-text-primary)]">{addr.name}</span>
                </div>
              {/if}
              {#if addr.phone}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Teléfono</span>
                  <span class="text-mono text-[var(--color-text-secondary)]">{addr.phone}</span>
                </div>
              {/if}
              {#if addr.address}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Dirección</span>
                  <span class="text-[var(--color-text-primary)]">{addr.address}</span>
                </div>
              {/if}
              {#if addr.zone || addr.municipality || addr.department}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Ubicación</span>
                  <span class="text-[var(--color-text-secondary)]">
                    {[addr.zone ? `Zona ${addr.zone}` : null, addr.municipality, addr.department].filter(Boolean).join(' · ')}
                  </span>
                </div>
              {/if}
              {#if addr.reference}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Referencia</span>
                  <span class="text-[var(--color-text-tertiary)] italic">{addr.reference}</span>
                </div>
              {/if}
              {#if addr.notes}
                <div class="flex items-baseline gap-2">
                  <span class="w-20 flex-shrink-0 text-[9.5px] text-display text-[var(--color-text-muted)]">Notas envío</span>
                  <span class="text-[var(--color-text-tertiary)] italic">{addr.notes}</span>
                </div>
              {/if}
            </div>
          {/if}

          <!-- Notes section -->
          {#if order.notes}
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-3 mt-5">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">NOTAS</span>
            </div>
            <div class="rounded-[3px] bg-[var(--color-surface-1)] p-3 text-[10.5px] text-[var(--color-text-secondary)]">
              {order.notes}
            </div>
          {/if}

        </div>

        <!-- ── RIGHT: meta sidebar ─────────────────────────────────── -->
        <div class="px-4 py-4 bg-[var(--color-surface-0)] overflow-y-auto space-y-5">

          <!-- Cliente -->
          <div>
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-2">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">CLIENTE</span>
            </div>
            <div class="space-y-1.5 text-[11px]">
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Nombre</span>
                <span class="font-medium truncate">{order.customer.name}</span>
              </div>
              {#if order.customer.phone}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Teléfono</span>
                  <span class="text-mono">{order.customer.phone}</span>
                </div>
              {/if}
              {#if order.customer.email}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Email</span>
                  <span class="text-mono text-[10px] truncate">{order.customer.email}</span>
                </div>
              {/if}
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Canal</span>
                <span class="uppercase text-[var(--color-text-secondary)]">{originLabel(order.origin)}</span>
              </div>
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Plataforma</span>
                <span class="uppercase text-[var(--color-text-secondary)]">{order.customer.platform}</span>
              </div>
            </div>
          </div>

          <!-- Pago -->
          <div>
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-2">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">PAGO</span>
            </div>
            <div class="space-y-1.5 text-[11px]">
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Método</span>
                <span>{paymentLabel(order.paymentMethod)}</span>
              </div>
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Pagado</span>
                <span class="text-mono text-[10px]">{fmtDate(order.paidAt)}</span>
              </div>
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Despachado</span>
                <span class="text-mono text-[10px]">{fmtDate(order.shippedAt)}</span>
              </div>
              {#if order.trackingCode}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Tracking</span>
                  <span class="text-mono text-[10px]">{order.trackingCode}</span>
                </div>
              {/if}
            </div>
          </div>

          <!-- Envío -->
          <div>
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-2">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">ENVÍO</span>
            </div>
            <div class="space-y-1.5 text-[11px]">
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Método</span>
                <span>{shippingMethodLabel(order.shippingMethod)}</span>
              </div>
              {#if order.shippingAddress}
                {@const addr = order.shippingAddress}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Destino</span>
                  <span class="text-right text-[10px] text-[var(--color-text-secondary)]">
                    {[addr.zone ? `Zona ${addr.zone}` : null, addr.municipality].filter(Boolean).join(', ')}
                  </span>
                </div>
              {/if}
            </div>
          </div>

          <!-- Totales -->
          <div>
            <div class="pb-1.5 border-b border-[var(--color-border)] mb-2">
              <span class="text-display text-[10.5px] font-semibold tracking-wider" style="color: var(--color-accent);">TOTALES</span>
            </div>
            <div class="space-y-1.5 text-[11px]">
              <div class="flex justify-between gap-2">
                <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Subtotal</span>
                <span class="text-mono">{fmtQ(order.subtotalGtq)}</span>
              </div>
              {#if order.shippingFeeGtq > 0}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Envío</span>
                  <span class="text-mono">{fmtQ(order.shippingFeeGtq)}</span>
                </div>
              {/if}
              {#if order.discountGtq > 0}
                <div class="flex justify-between gap-2">
                  <span class="text-[var(--color-text-muted)] text-[9.5px] text-display">Descuento</span>
                  <span class="text-mono" style="color: var(--color-danger);">-{fmtQ(order.discountGtq)}</span>
                </div>
              {/if}
              <div class="flex justify-between gap-2 pt-1.5 border-t border-[var(--color-border)]">
                <span class="text-[10px] font-semibold text-display tracking-wider text-[var(--color-text-secondary)]">TOTAL</span>
                <span class="text-mono text-[14px] font-bold" style="color: var(--color-accent);">{fmtQ(order.totalGtq)}</span>
              </div>
            </div>
          </div>

          <!-- Atribución -->
          <div>
            <div class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
              <div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">
                Atribución
                {#if !editingAttribution}
                  <button type="button" onclick={startEditAttr} class="ml-1 text-[10px] text-[var(--color-accent)]">[editar]</button>
                {/if}
              </div>
              {#if editingAttribution}
                <div class="space-y-2">
                  <select
                    bind:value={selectedCampaignId}
                    class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-1 text-[11px]"
                  >
                    <option value={null}>— sin atribución —</option>
                    {#each campaigns as c (c.campaignId)}
                      <option value={c.campaignId}>{c.campaignName ?? c.campaignId}</option>
                    {/each}
                  </select>
                  {#if attrSaveError}<div class="text-[9.5px] text-[var(--color-danger)]">⚠ {attrSaveError}</div>{/if}
                  <div class="flex gap-2">
                    <button
                      type="button"
                      onclick={saveAttribution}
                      disabled={savingAttr}
                      class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-1 text-[10px] font-semibold text-black disabled:opacity-60"
                    >
                      {#if savingAttr}Guardando…{:else}Guardar{/if}
                    </button>
                    <button
                      type="button"
                      onclick={() => (editingAttribution = false)}
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-1 text-[10px]"
                    >Cancelar</button>
                  </div>
                </div>
              {:else if attribution}
                <div class="flex items-center gap-2 text-[11px]">
                  <TrendingUp size={12} strokeWidth={1.8} style="color: var(--color-accent);" />
                  <span class="font-medium">{attribution.adCampaignName ?? attribution.adCampaignId ?? '—'}</span>
                  {#if attribution.source}
                    <span class="text-[9px] text-[var(--color-text-muted)]">· {attribution.source}</span>
                  {/if}
                </div>
              {:else}
                <div class="text-[10px] text-[var(--color-text-tertiary)]">— sin atribución</div>
              {/if}
            </div>
            {#if attributionError}<div class="mt-1 text-[9.5px] text-[var(--color-danger)]">⚠ {attributionError}</div>{/if}
          </div>

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
          {#if order.status !== 'shipped' && order.status !== 'delivered' && order.status !== 'cancelled'}
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
        <div class="flex gap-2">
          <button
            type="button"
            onclick={() => (openEdit = true)}
            class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
          >
            <Pencil size={12} strokeWidth={1.8} /> Editar
          </button>
          <button
            type="button"
            onclick={onClose}
            class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          >Cerrar</button>
        </div>
      </div>
    {/if}
  {/snippet}
</BaseModal>

{#if openEdit && order}
  <SaleFormModal
    mode="edit"
    {order}
    onClose={() => { openEdit = false; void loadOrder(); }}
  />
{/if}
