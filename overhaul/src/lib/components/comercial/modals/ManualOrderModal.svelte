<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CustomerProfile, CreateOrderItem } from '$lib/data/comercial';
  import type { Family } from '$lib/data/types';
  import { ShoppingCart, Loader2, Plus, X } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    customer: CustomerProfile;
    onClose: () => void;
  }
  let { customer, onClose }: Props = $props();

  type EditableItem = CreateOrderItem & { localId: number };

  let nextId = 1;
  let items = $state<EditableItem[]>([{
    localId: nextId++,
    familyId: '',
    jerseyId: '',
    team: '',
    size: 'M',
    variantLabel: null,
    version: null,
    personalizationJson: null,
    unitPrice: 0,
    unitCost: null,
    itemType: 'manual',
  }]);

  let paymentMethod = $state<'recurrente' | 'transferencia' | 'contra_entrega' | 'efectivo' | 'otro'>('transferencia');
  let fulfillmentStatus = $state<'pending' | 'sent_to_supplier' | 'in_production' | 'shipped' | 'delivered' | 'cancelled'>('pending');
  let shippingFee = $state(0);
  let discount = $state(0);
  let notes = $state('');
  let saving = $state(false);
  let error = $state<string | null>(null);

  let families = $state<Family[]>([]);
  let loadingCatalog = $state(true);

  $effect(() => {
    void (async () => {
      try {
        const result = await adapter.listFamilies();
        families = result;
      } catch (e) {
        console.warn('[manual-order] catalog load failed', e);
      } finally {
        loadingCatalog = false;
      }
    })();
  });

  let teams = $derived.by(() => {
    const set = new Set<string>();
    for (const f of families) if (f.team) set.add(f.team);
    return Array.from(set).sort();
  });

  function jerseysForTeam(team: string) {
    return families.filter((f) => f.team === team);
  }

  function jerseySublabel(family: Family): string {
    return `${family.season ?? ''} ${family.variantLabel ?? family.variant ?? ''}`.trim() || family.id;
  }

  function onFamilyChange(item: EditableItem) {
    const fam = families.find((f) => f.id === item.familyId);
    if (fam) {
      item.team = fam.team;
      item.variantLabel = fam.variantLabel ?? fam.variant ?? null;
      item.version = fam.season ?? null;
      if (fam.modelos && fam.modelos[0]) {
        item.jerseyId = fam.modelos[0].sku || fam.id;
        if (fam.modelos[0].price) item.unitPrice = fam.modelos[0].price;
      } else {
        item.jerseyId = fam.id;
      }
    }
  }

  function addItem() {
    items.push({
      localId: nextId++,
      familyId: '', jerseyId: '', team: '', size: 'M',
      variantLabel: null, version: null, personalizationJson: null,
      unitPrice: 0, unitCost: null, itemType: 'manual',
    });
  }

  function removeItem(localId: number) {
    if (items.length === 1) return;
    items = items.filter((i) => i.localId !== localId);
  }

  let subtotal = $derived(items.reduce((s, i) => s + (i.unitPrice || 0), 0));
  let total = $derived(subtotal + shippingFee - discount);

  async function handleSubmit() {
    error = null;
    if (items.some((i) => !i.team || !i.familyId || !i.jerseyId || !i.size || !i.unitPrice || i.unitPrice <= 0)) {
      error = 'Cada item necesita: team, jersey, size, unit price > 0';
      return;
    }
    if (total <= 0) {
      error = 'Total debe ser > 0';
      return;
    }
    saving = true;
    try {
      const payload = {
        customerId: customer.customerId,
        items: items.map(({ localId, ...rest }) => rest),
        paymentMethod,
        fulfillmentStatus,
        shippingFee,
        discount,
        notes: notes || undefined,
      };
      const result = await adapter.createManualOrder(payload);
      if (result.ok) {
        if (!result.ref) console.warn('[manual-order] ok=true but no ref returned', result);
        onClose();
      } else {
        error = result.error ?? 'Error desconocido';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
        <ShoppingCart size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Crear orden manual</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Cliente: {customer.name}</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    {#if loadingCatalog}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando catálogo…</div>
    {:else}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px]">
        <!-- Items column -->
        <div class="overflow-y-auto border-r border-[var(--color-border)] px-6 py-4">
          <div class="mb-3 flex items-baseline justify-between">
            <span class="text-display text-[9.5px] text-[var(--color-text-tertiary)]">Items · {items.length}</span>
            <button type="button" onclick={addItem} class="flex items-center gap-1 text-[10px] text-[var(--color-accent)]">
              <Plus size={10} /> Agregar item
            </button>
          </div>

          <div class="space-y-3">
            {#each items as item, idx (item.localId)}
              <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
                <div class="mb-2 flex items-baseline justify-between">
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">item #{idx + 1}</span>
                  {#if items.length > 1}
                    <button type="button" onclick={() => removeItem(item.localId)} class="text-[var(--color-danger)]"><X size={12} /></button>
                  {/if}
                </div>

                <div class="space-y-2 text-[10.5px]">
                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Team</span>
                    <select
                      bind:value={item.team}
                      onchange={() => { item.familyId = ''; item.jerseyId = ''; }}
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    >
                      <option value="">— elegir —</option>
                      {#each teams as t}<option value={t}>{t}</option>{/each}
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Jersey</span>
                    <select
                      bind:value={item.familyId}
                      onchange={() => onFamilyChange(item)}
                      disabled={!item.team}
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5 disabled:opacity-50"
                    >
                      <option value="">— elegir —</option>
                      {#each jerseysForTeam(item.team) as fam}
                        <option value={fam.id}>{jerseySublabel(fam)}</option>
                      {/each}
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Size</span>
                    <select bind:value={item.size} class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5">
                      <option value="S">S</option><option value="M">M</option><option value="L">L</option>
                      <option value="XL">XL</option><option value="XXL">XXL</option>
                    </select>
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Pers.</span>
                    <input
                      type="text"
                      bind:value={item.personalizationJson}
                      placeholder="ej. 10 MESSI"
                      class="flex-1 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                  </div>

                  <div class="flex items-baseline gap-2">
                    <span class="w-16 text-[var(--color-text-tertiary)]">Q precio</span>
                    <input
                      type="number"
                      bind:value={item.unitPrice}
                      class="text-mono w-24 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                    <span class="ml-2 w-16 text-[var(--color-text-tertiary)]">Q cost</span>
                    <input
                      type="number"
                      bind:value={item.unitCost}
                      placeholder="opt"
                      class="text-mono w-24 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-2 py-0.5"
                    />
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Totals + meta sidebar -->
        <div class="bg-[var(--color-surface-0)] px-4 py-4">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Totales</div>
          <div class="mb-4 space-y-1 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Subtotal</span><span class="text-mono">Q{subtotal.toFixed(0)}</span></div>
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-[var(--color-text-tertiary)]">Shipping</span>
              <input type="number" bind:value={shippingFee} class="text-mono w-20 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-right" />
            </div>
            <div class="flex items-baseline justify-between gap-2">
              <span class="text-[var(--color-text-tertiary)]">Discount</span>
              <input type="number" bind:value={discount} class="text-mono w-20 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5 text-right" />
            </div>
            <div class="border-t border-[var(--color-border)] pt-1.5 flex justify-between">
              <span class="font-semibold">TOTAL</span>
              <span class="text-mono font-semibold" style="color: var(--color-accent);">Q{total.toFixed(0)}</span>
            </div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Pago + entrega</div>
          <div class="mb-4 space-y-2 text-[10.5px]">
            <select bind:value={paymentMethod} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5">
              <option value="transferencia">Transferencia</option>
              <option value="recurrente">Recurrente</option>
              <option value="contra_entrega">Contra entrega</option>
              <option value="efectivo">Efectivo</option>
              <option value="otro">Otro</option>
            </select>
            <select bind:value={fulfillmentStatus} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-0.5">
              <option value="pending">Pending</option>
              <option value="sent_to_supplier">Sent to supplier</option>
              <option value="in_production">In production</option>
              <option value="shipped">Shipped</option>
              <option value="delivered">Delivered</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Notes</div>
          <textarea
            bind:value={notes}
            class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10.5px]"
            rows="2"
          ></textarea>

          {#if error}
            <div class="mt-2 rounded-[3px] border border-[var(--color-danger)] p-2 text-[10px] text-[var(--color-danger)]">⚠ {error}</div>
          {/if}
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onClose}
        disabled={saving}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
      >Cancelar</button>
      <button
        type="button"
        onclick={handleSubmit}
        disabled={saving || total <= 0 || items.some((i) => !i.familyId || !i.unitPrice)}
        class="ml-auto flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if saving}<Loader2 size={12} class="animate-spin" /> Registrando…{:else}Registrar orden{/if}
      </button>
    </div>
  {/snippet}
</BaseModal>
