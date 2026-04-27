<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type {
    CreateOrderItem, CreateOrderArgs, UpdateSaleArgs,
    CustomerSearchResult, ShippingAddress, Campaign, OrderForModal, OrderItem
  } from '$lib/data/comercial';
  import { ShoppingCart, Loader2, Plus, X, Search, UserCheck } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    mode: 'create' | 'edit';
    order?: OrderForModal | null;
    customerId?: number;
    customerName?: string;
    onClose: () => void;
  }
  let { mode, order = null, customerId, customerName, onClose }: Props = $props();

  // Customer
  let custQuery = $state(customerName ?? '');
  let custResults = $state<CustomerSearchResult[]>([]);
  let custDropdownOpen = $state(false);
  let selectedCustomerId = $state<number | null>(customerId ?? null);
  let custName = $state(customerName ?? '');
  let custPhone = $state('');
  let custEmail = $state('');

  // Address
  let addrAddress = $state('');
  let addrDepartment = $state('');
  let addrMunicipality = $state('');
  let addrZone = $state('');
  let addrReference = $state('');
  let addrNotes = $state('');

  // Sale meta
  let occurredAt = $state(new Date().toISOString().slice(0, 10));
  let modality = $state<'mystery' | 'stock' | 'ondemand'>('mystery');
  let origin = $state<string>('web');
  let paymentMethod = $state<'recurrente' | 'transferencia' | 'contra_entrega' | 'efectivo' | 'otro'>('transferencia');
  let fulfillmentStatus = $state<'pending' | 'sent_to_supplier' | 'in_production' | 'shipped' | 'delivered' | 'cancelled'>('pending');
  let shippingMethod = $state<string>('forza');
  let notes = $state('');
  let shippingFee = $state(0);
  let discount = $state(0);

  // Items
  type EditableItem = CreateOrderItem & { localId: number };
  let nextItemId = 1;
  let items = $state<EditableItem[]>([{
    localId: nextItemId++,
    familyId: '', jerseyId: '', team: '', size: 'M',
    variantLabel: null, version: null, personalizationJson: null,
    unitPrice: 0, unitCost: null, itemType: 'manual',
  }]);

  // Catalog
  let families = $state<any[]>([]);
  let loadingCatalog = $state(true);
  $effect(() => {
    void (async () => {
      try {
        families = await adapter.listFamilies();
      } catch (e) {
        console.warn('[sale-form] catalog load failed', e);
      } finally {
        loadingCatalog = false;
      }
    })();
  });

  // Campaigns
  let campaigns = $state<Campaign[]>([]);
  let selectedCampaignId = $state<string | null>(null);
  $effect(() => {
    void (async () => {
      try {
        campaigns = await adapter.listCampaigns({ periodDays: 90 });
      } catch (e) {
        console.warn('[sale-form] campaigns load failed', e);
      }
    })();
  });

  // Edit mode pre-fill
  $effect(() => {
    if (mode === 'edit' && order) {
      custName = order.customer?.name ?? '';
      custPhone = order.customer?.phone ?? '';
      occurredAt = (order.paidAt ?? new Date().toISOString()).slice(0, 10);
      paymentMethod = (
        order.paymentMethod === 'transfer' ? 'transferencia' :
        order.paymentMethod === 'cod' ? 'contra_entrega' :
        order.paymentMethod === 'recurrente' ? 'recurrente' : 'transferencia'
      ) as typeof paymentMethod;
      fulfillmentStatus = (
        order.status === 'paid' ? 'pending' :
        order.status === 'shipped' ? 'shipped' :
        order.status === 'delivered' ? 'delivered' :
        order.status === 'cancelled' ? 'cancelled' : 'pending'
      ) as typeof fulfillmentStatus;
      notes = order.notes ?? '';
      if (order.items && order.items.length > 0) {
        items = order.items.map((it: OrderItem) => ({
          localId: nextItemId++,
          familyId: it.familyId,
          jerseyId: it.jerseySku ?? it.familyId,
          team: '',
          size: it.size,
          variantLabel: null, version: null,
          personalizationJson: it.personalizationJson,
          unitPrice: it.unitPriceGtq,
          unitCost: it.unitCostGtq,
          itemType: 'manual',
        }));
      }
    }
  });

  // Customer search
  let custSearchTimer: ReturnType<typeof setTimeout> | null = null;
  function onCustQueryInput() {
    if (custSearchTimer) clearTimeout(custSearchTimer);
    if (custQuery.trim().length < 2) {
      custResults = [];
      custDropdownOpen = false;
      return;
    }
    custSearchTimer = setTimeout(async () => {
      try {
        custResults = await adapter.searchCustomers(custQuery.trim());
        custDropdownOpen = custResults.length > 0;
      } catch (e) {
        console.warn('[sale-form] customer search failed', e);
      }
    }, 250);
  }

  function selectCustomer(c: CustomerSearchResult) {
    selectedCustomerId = c.customerId;
    custName = c.name;
    custPhone = c.phone ?? '';
    custEmail = c.email ?? '';
    custQuery = c.name;
    custDropdownOpen = false;
  }

  // Items helpers
  let teams = $derived.by(() => {
    const set = new Set<string>();
    for (const f of families) if (f.team) set.add(f.team);
    return Array.from(set).sort();
  });

  function jerseysForTeam(team: string) {
    return families.filter((f) => f.team === team);
  }

  function jerseySublabel(family: any): string {
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
      localId: nextItemId++,
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

  let stockWarnings = $derived.by(() => {
    if (modality === 'ondemand') return [];
    return items
      .filter(i => i.familyId && !families.find(f => f.id === i.familyId))
      .map(i => `Item ${i.familyId}: SKU no encontrado en catálogo`);
  });

  let forceStockCheck = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);

  async function handleSubmit() {
    error = null;

    if (!custName.trim() && !selectedCustomerId) {
      error = 'Cliente requerido';
      return;
    }
    if (items.some((i) => !i.familyId || !i.jerseyId || !i.size || !i.unitPrice || i.unitPrice <= 0)) {
      error = 'Cada item necesita: team, jersey, size, unit price > 0';
      return;
    }
    if (total <= 0) {
      error = 'Total debe ser > 0';
      return;
    }

    saving = true;
    try {
      let resolvedCustomerId = selectedCustomerId;
      if (!resolvedCustomerId) {
        const r = await adapter.createCustomer({
          name: custName.trim(),
          phone: custPhone.trim() || null,
          email: custEmail.trim() || null,
          source: origin || null,
        });
        if (!r.ok || !r.customerId) {
          error = r.error ?? 'Error creando customer';
          return;
        }
        resolvedCustomerId = r.customerId;
      }

      const hasAddress = addrAddress.trim() || addrDepartment.trim() || addrMunicipality.trim() || addrZone.trim();
      const shippingAddress: ShippingAddress | null = hasAddress ? {
        name: custName.trim(),
        phone: custPhone.trim() || null,
        address: addrAddress.trim(),
        department: addrDepartment.trim(),
        municipality: addrMunicipality.trim(),
        zone: addrZone.trim(),
        reference: addrReference.trim(),
        notes: addrNotes.trim(),
      } : null;

      const occurredAtIso = `${occurredAt}T12:00:00`;

      if (mode === 'create') {
        const args: CreateOrderArgs = {
          customerId: resolvedCustomerId,
          items: items.map(({ localId, ...rest }) => rest),
          paymentMethod,
          fulfillmentStatus,
          shippingFee,
          discount,
          notes: notes.trim() || undefined,
          modality,
          origin,
          shippingMethod,
          shippingAddress,
          occurredAt: occurredAtIso,
        };
        const result = await adapter.createManualOrder(args);
        if (!result.ok || !result.ref) {
          error = result.error ?? 'Error desconocido';
          return;
        }
        if (selectedCampaignId && result.saleId) {
          try {
            await adapter.attributeSale({ saleId: result.saleId, campaignId: selectedCampaignId });
          } catch (e) {
            console.warn('[sale-form] attribution failed (non-fatal)', e);
          }
        }
        onClose();
      } else if (mode === 'edit' && order) {
        const updateArgs: UpdateSaleArgs = {
          saleId: order.saleId,
          occurredAt: occurredAtIso,
          modality,
          origin,
          paymentMethod,
          fulfillmentStatus,
          shippingMethod,
          shippingFee,
          discount,
          notes: notes.trim() || undefined,
          shippingAddress,
          customerId: resolvedCustomerId ?? undefined,
        };
        const result = await adapter.updateSale(updateArgs);
        if (!result.ok) {
          error = result.error ?? 'Error desconocido';
          return;
        }
        // Replace sale_items (idempotent — DELETE + INSERT atomic)
        const itemsResult = await adapter.replaceSaleItems({
          saleId: order.saleId,
          items: items.map(({ localId, ...rest }) => rest),
        });
        if (!itemsResult.ok) {
          error = itemsResult.error ?? 'Items error';
          return;
        }
        if (selectedCampaignId) {
          try {
            await adapter.attributeSale({ saleId: order.saleId, campaignId: selectedCampaignId });
          } catch (e) {
            console.warn('[sale-form] attribution failed (non-fatal)', e);
          }
        }
        onClose();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  const ORIGINS = ['web', 'instagram', 'messenger', 'whatsapp', 'walk-in', 'manual', 'otro'];
  const SHIPPING_METHODS = ['forza', 'personal', 'otro'];
  const MODALITIES: Array<['mystery' | 'stock' | 'ondemand', string]> = [
    ['mystery', 'Mystery'],
    ['stock', 'Drop'],
    ['ondemand', 'Vault'],
  ];
</script>

<BaseModal open={true} {onClose} maxWidth={980}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
        <ShoppingCart size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">
          {mode === 'create' ? 'Nueva venta manual' : `Editar venta ${order?.ref ?? ''}`}
        </div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">
          {mode === 'create' ? 'Registro completo. Importá cliente existente o llenalo a mano.' : 'Editar campos e items. Los cambios en items reemplazan todos los items anteriores.'}
        </div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    {#if loadingCatalog}
      <div class="px-6 py-4 text-[11px] text-[var(--color-text-tertiary)]">Cargando catálogo…</div>
    {:else}
      <div class="grid grid-cols-[1fr_320px] gap-0 max-h-[600px] overflow-hidden">

        <!-- LEFT: customer + address + items -->
        <div class="overflow-y-auto border-r border-[var(--color-border)] px-6 py-4 space-y-4">

          <!-- Customer block -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">CLIENTE</h3>
            <div class="space-y-2">
              <!-- Typeahead search -->
              <div class="relative">
                <label class="text-display mb-1 block text-[9px] text-[var(--color-text-muted)]">Buscar / Importar existente</label>
                <div class="relative">
                  <Search size={11} class="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]" />
                  <input
                    type="text"
                    bind:value={custQuery}
                    oninput={onCustQueryInput}
                    placeholder="Nombre, teléfono o email..."
                    class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1 pl-7 pr-2 text-[11px]"
                  />
                </div>
                {#if custDropdownOpen}
                  <div class="absolute z-10 mt-1 w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-0)] max-h-48 overflow-y-auto">
                    {#each custResults as c}
                      <button
                        type="button"
                        onclick={() => selectCustomer(c)}
                        class="flex w-full items-baseline justify-between px-2 py-1.5 text-left text-[10.5px] hover:bg-[var(--color-surface-1)]"
                      >
                        <span>{c.name}</span>
                        <span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">{c.phone ?? c.email ?? ''}</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>

              {#if selectedCustomerId}
                <div class="rounded-[3px] border border-[var(--color-accent)] bg-[var(--color-surface-1)] p-1.5 text-[10px] flex items-center gap-1.5">
                  <UserCheck size={10} style="color: var(--color-accent);" />
                  <span style="color: var(--color-accent);">Cliente importado #{selectedCustomerId}</span>
                  <button
                    type="button"
                    onclick={() => { selectedCustomerId = null; custQuery = ''; custName = ''; custPhone = ''; custEmail = ''; }}
                    class="ml-auto text-[var(--color-text-muted)]"
                  >[deseleccionar]</button>
                </div>
              {/if}

              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Nombre *</label>
                  <input type="text" bind:value={custName} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
                <div>
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Teléfono</label>
                  <input type="text" bind:value={custPhone} class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
                <div class="col-span-2">
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Email (opcional)</label>
                  <input type="email" bind:value={custEmail} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
              </div>
            </div>
          </section>

          <!-- Address block -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">DIRECCIÓN DE ENTREGA</h3>
            <div class="space-y-2">
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Dirección</label>
                <input type="text" bind:value={addrAddress} placeholder="Avenida X, calle Y, casa Z" class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
              </div>
              <div class="grid grid-cols-3 gap-2">
                <div>
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Depto.</label>
                  <input type="text" bind:value={addrDepartment} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
                <div>
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Municipio</label>
                  <input type="text" bind:value={addrMunicipality} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
                <div>
                  <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Zona</label>
                  <input type="text" bind:value={addrZone} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
                </div>
              </div>
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Referencia</label>
                <input type="text" bind:value={addrReference} placeholder="Casa color verde, frente al parque" class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
              </div>
            </div>
          </section>

          <!-- Items block -->
          <section>
            <div class="mb-2 flex items-baseline justify-between">
              <h3 class="text-display text-[9.5px] text-[var(--color-text-tertiary)]">ITEMS · {items.length}</h3>
              <button type="button" onclick={addItem} class="flex items-center gap-1 text-[10px] text-[var(--color-accent)]">
                <Plus size={10} /> Agregar
              </button>
            </div>

            <div class="space-y-2">
              {#each items as item, idx (item.localId)}
                <div class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2">
                  <div class="mb-1.5 flex items-baseline justify-between">
                    <span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">item #{idx + 1}</span>
                    {#if items.length > 1}
                      <button type="button" onclick={() => removeItem(item.localId)} class="text-[var(--color-danger)]"><X size={11} /></button>
                    {/if}
                  </div>
                  <div class="space-y-1.5 text-[10px]">
                    <div class="grid grid-cols-[60px_1fr] items-baseline gap-1.5">
                      <span class="text-[var(--color-text-tertiary)]">Team</span>
                      <select
                        bind:value={item.team}
                        onchange={() => { item.familyId = ''; item.jerseyId = ''; }}
                        class="rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5"
                      >
                        <option value="">— elegir —</option>
                        {#each teams as t}<option value={t}>{t}</option>{/each}
                      </select>
                    </div>
                    <div class="grid grid-cols-[60px_1fr] items-baseline gap-1.5">
                      <span class="text-[var(--color-text-tertiary)]">Jersey</span>
                      <select
                        bind:value={item.familyId}
                        disabled={!item.team}
                        onchange={() => onFamilyChange(item)}
                        class="rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5 disabled:opacity-50"
                      >
                        <option value="">— elegir —</option>
                        {#each jerseysForTeam(item.team) as fam}
                          <option value={fam.id}>{jerseySublabel(fam)}</option>
                        {/each}
                      </select>
                    </div>
                    <div class="grid grid-cols-[60px_1fr_60px_1fr] items-baseline gap-1.5">
                      <span class="text-[var(--color-text-tertiary)]">Size</span>
                      <select bind:value={item.size} class="rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5">
                        <option value="S">S</option>
                        <option value="M">M</option>
                        <option value="L">L</option>
                        <option value="XL">XL</option>
                        <option value="XXL">XXL</option>
                      </select>
                      <span class="text-[var(--color-text-tertiary)]">Pers.</span>
                      <input
                        type="text"
                        bind:value={item.personalizationJson}
                        placeholder="ej. 10 MESSI"
                        class="rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5"
                      />
                    </div>
                    <div class="grid grid-cols-[60px_1fr_60px_1fr] items-baseline gap-1.5">
                      <span class="text-[var(--color-text-tertiary)]">Q precio</span>
                      <input
                        type="number"
                        bind:value={item.unitPrice}
                        min="0"
                        class="text-mono rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5"
                      />
                      <span class="text-[var(--color-text-tertiary)]">Q costo</span>
                      <input
                        type="number"
                        bind:value={item.unitCost}
                        min="0"
                        placeholder="opt"
                        class="text-mono rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-0)] px-1.5 py-0.5"
                      />
                    </div>
                  </div>
                </div>
              {/each}
            </div>

            {#if stockWarnings.length > 0}
              <div class="mt-2 rounded-[3px] border border-[var(--color-warning)] bg-[var(--color-surface-1)] p-2 text-[10px]" style="color: var(--color-warning);">
                ⚠ Stock check soft-warn:
                <ul class="mt-1 ml-3 list-disc">
                  {#each stockWarnings as w}<li>{w}</li>{/each}
                </ul>
                <label class="mt-2 flex items-center gap-1.5 text-[9.5px] cursor-pointer">
                  <input type="checkbox" bind:checked={forceStockCheck} />
                  <span>Forzar venta sin stock</span>
                </label>
              </div>
            {/if}
          </section>
        </div>

        <!-- RIGHT: meta sidebar -->
        <div class="overflow-y-auto bg-[var(--color-surface-0)] px-4 py-4 space-y-4">

          <!-- Date + modality -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">PEDIDO</h3>
            <div class="space-y-2">
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Fecha</label>
                <input type="date" bind:value={occurredAt} class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]" />
              </div>
              <div>
                <label class="text-display mb-1 block text-[9px] text-[var(--color-text-muted)]">Producto</label>
                <div class="grid grid-cols-3 gap-1">
                  {#each MODALITIES as [val, lbl]}
                    {@const active = modality === val}
                    <button
                      type="button"
                      onclick={() => (modality = val)}
                      class="rounded-[2px] border px-1 py-1 text-[10px]"
                      style="background: {active ? 'rgba(74,222,128,0.15)' : 'var(--color-surface-1)'}; border-color: {active ? 'var(--color-accent)' : 'var(--color-border)'}; color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};"
                    >
                      {lbl}
                    </button>
                  {/each}
                </div>
                {#if modality === 'ondemand'}
                  <div class="mt-1 text-[9px] text-[var(--color-text-muted)]">→ Genera pendiente para próximo pedido al chino</div>
                {/if}
              </div>
            </div>
          </section>

          <!-- Origin / channel + attribution -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">ATRIBUCIÓN</h3>
            <div class="space-y-2">
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Canal / origen</label>
                <select bind:value={origin} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]">
                  {#each ORIGINS as o}<option value={o}>{o}</option>{/each}
                </select>
              </div>
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Ad / Campaña (opcional)</label>
                <select bind:value={selectedCampaignId} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]">
                  <option value={null}>— ninguna —</option>
                  {#each campaigns as c}<option value={c.campaignId}>{c.campaignName ?? c.campaignId}</option>{/each}
                </select>
              </div>
            </div>
          </section>

          <!-- Pago + entrega -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">PAGO + ENTREGA</h3>
            <div class="space-y-2">
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Forma de pago</label>
                <select bind:value={paymentMethod} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]">
                  <option value="transferencia">Transferencia</option>
                  <option value="recurrente">Recurrente (tarjeta)</option>
                  <option value="contra_entrega">Contra entrega</option>
                  <option value="efectivo">Efectivo</option>
                  <option value="otro">Otro</option>
                </select>
              </div>
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Estado del pedido</label>
                <select bind:value={fulfillmentStatus} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]">
                  <option value="pending">Pendiente</option>
                  <option value="sent_to_supplier">Enviado al chino</option>
                  <option value="in_production">En producción</option>
                  <option value="shipped">Despachado al cliente</option>
                  <option value="delivered">Entregado</option>
                  <option value="cancelled">Cancelado</option>
                </select>
              </div>
              <div>
                <label class="text-display mb-0.5 block text-[9px] text-[var(--color-text-muted)]">Envío (absorbido por El Club)</label>
                <select bind:value={shippingMethod} class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]">
                  {#each SHIPPING_METHODS as s}<option value={s}>{s}</option>{/each}
                </select>
              </div>
            </div>
          </section>

          <!-- Totals -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">TOTALES</h3>
            <div class="space-y-1 text-[11px]">
              <div class="flex justify-between">
                <span class="text-[var(--color-text-tertiary)]">Subtotal</span>
                <span class="text-mono">Q{subtotal.toFixed(0)}</span>
              </div>
              <div class="flex items-baseline justify-between gap-1.5">
                <span class="text-[var(--color-text-tertiary)]">Envío Q</span>
                <input type="number" bind:value={shippingFee} min="0" class="text-mono w-16 rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-1.5 py-0.5 text-right text-[10.5px]" />
              </div>
              <div class="flex items-baseline justify-between gap-1.5">
                <span class="text-[var(--color-text-tertiary)]">Descuento Q</span>
                <input type="number" bind:value={discount} min="0" class="text-mono w-16 rounded-[2px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-1.5 py-0.5 text-right text-[10.5px]" />
              </div>
              <div class="flex justify-between border-t border-[var(--color-border)] pt-1 text-[12px]">
                <span class="font-semibold">TOTAL</span>
                <span class="text-mono font-semibold" style="color: var(--color-accent);">Q{total.toFixed(0)}</span>
              </div>
            </div>
          </section>

          <!-- Notes -->
          <section>
            <h3 class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">NOTAS</h3>
            <textarea bind:value={notes} rows="2" class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[10.5px]" placeholder="Internal notes..."></textarea>
          </section>

          {#if error}
            <div class="rounded-[3px] border border-[var(--color-danger)] p-2 text-[10px] text-[var(--color-danger)]">⚠ {error}</div>
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
        disabled={saving || total <= 0 || (stockWarnings.length > 0 && !forceStockCheck && modality !== 'ondemand')}
        class="ml-auto flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if saving}
          <Loader2 size={12} class="animate-spin" />
          {mode === 'create' ? 'Registrando…' : 'Guardando…'}
        {:else}
          {mode === 'create' ? 'Registrar venta' : 'Guardar cambios'}
        {/if}
      </button>
    </div>
  {/snippet}
</BaseModal>
