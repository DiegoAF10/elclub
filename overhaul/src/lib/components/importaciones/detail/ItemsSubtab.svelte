<script lang="ts">
  import type { ImportItem } from '$lib/data/importaciones';
  import { adapter } from '$lib/adapter';

  interface Props {
    items: ImportItem[];
    onRefresh?: () => void;
  }
  let { items, onRefresh }: Props = $props();

  let sortBy = $state<'sku' | 'usd' | 'landed' | 'customer'>('sku');
  let sortDesc = $state(false);
  let toast = $state<{ msg: string; type: 'ok' | 'err' } | null>(null);
  let busy = $state<Set<number>>(new Set());

  let sorted = $derived([...items].sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'sku') cmp = (a.family_id ?? '').localeCompare(b.family_id ?? '');
    else if (sortBy === 'usd') cmp = (a.unit_cost_usd ?? 0) - (b.unit_cost_usd ?? 0);
    else if (sortBy === 'landed') cmp = (a.unit_cost ?? 0) - (b.unit_cost ?? 0);
    else if (sortBy === 'customer') cmp = (a.customer_name ?? '').localeCompare(b.customer_name ?? '');
    return sortDesc ? -cmp : cmp;
  }));

  function setSort(col: typeof sortBy) {
    if (sortBy === col) sortDesc = !sortDesc;
    else { sortBy = col; sortDesc = false; }
  }

  function fmtUsd(n: number | null | undefined): string {
    return n === null || n === undefined ? '—' : `$${n.toFixed(2)}`;
  }
  function fmtQ(n: number | null | undefined): string {
    return n === null || n === undefined ? '—' : `Q${Math.round(n).toLocaleString('es-GT')}`;
  }

  function showToast(msg: string, type: 'ok' | 'err' = 'ok') {
    toast = { msg, type };
    setTimeout(() => { toast = null; }, 3500);
  }

  function timeAgo(iso: string | null): string {
    if (!iso) return '';
    // SQLite localtime format "YYYY-MM-DD HH:MM:SS" — make it ISO-compatible
    const then = new Date(iso.replace(' ', 'T')).getTime();
    const diffMin = Math.floor((Date.now() - then) / 60000);
    if (diffMin < 1) return 'recién';
    if (diffMin < 60) return `${diffMin}m`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h`;
    return `${Math.floor(diffHr / 24)}d`;
  }

  async function sendToSupplier(item: ImportItem, supplier: 'china' | 'hk') {
    const itemId = item.source_id;
    // Q=C: confirm dialog si re-send al mismo supplier (Diego decision 2026-04-30)
    if (item.sent_to_supplier_at && item.sent_to_supplier_via === supplier) {
      const ago = timeAgo(item.sent_to_supplier_at);
      const ok = confirm(`Ya enviado a ${supplier.toUpperCase()} hace ${ago}. ¿Re-enviar?`);
      if (!ok) return;
    }
    busy = new Set([...busy, itemId]);
    try {
      const msg = await adapter.getSupplierMessage(itemId);
      await adapter.copyHeroToClipboard(msg.hero_url);
      const url = supplier === 'china' ? msg.wa_china_url : msg.wa_hk_url;
      window.open(url, '_blank');
      // Q=B: marcar SOLO al final si toda la chain succeeded
      await adapter.markItemSent(itemId, supplier);
      showToast(`Imagen copiada · pegá en WA con Ctrl+V`, 'ok');
      onRefresh?.();
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      showToast(`Error: ${errMsg}`, 'err');
    } finally {
      const next = new Set(busy);
      next.delete(itemId);
      busy = next;
    }
  }
</script>

<div class="p-6 overflow-y-auto relative">
  <table class="w-full text-[11.5px] border-collapse">
    <thead class="bg-[var(--color-bg)] sticky top-0">
      <tr>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('sku')}>
          SKU {#if sortBy === 'sku'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Variante</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Spec (player)</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('customer')}>
          Asignado {#if sortBy === 'customer'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Source</th>
        <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('usd')}>
          USD chino {#if sortBy === 'usd'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('landed')}>
          Landed Q {#if sortBy === 'landed'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-center text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Supplier</th>
      </tr>
    </thead>
    <tbody>
      {#each sorted as item (item.source_table + ':' + item.source_id)}
        <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
          <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-primary)]">
            {item.family_id ?? item.jersey_id ?? '—'}
            {#if item.is_free_unit}
              <span class="ml-1 text-mono text-[9px] px-1.5 py-0.5 bg-[rgba(167,243,208,0.12)] text-[var(--color-ready)] rounded-[2px]">FREE</span>
            {/if}
          </td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.size ?? '—'} · {item.version ?? '—'}</td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">
            {#if item.player_name}{item.player_name}{:else}—{/if}
            {#if item.player_number}<span class="text-[var(--color-text-tertiary)]"> #{item.player_number}</span>{/if}
            {#if item.patch}<span class="text-[var(--color-text-tertiary)]"> · {item.patch}</span>{/if}
          </td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.customer_name ?? (item.customer_id ? '(loading)' : 'stock')}</td>
          <td class="py-1.5 px-2.5 text-mono text-[10px] text-[var(--color-text-tertiary)] uppercase">{item.source_table === 'sale_items' ? 'sale' : item.source_table === 'jerseys' ? 'jersey' : 'item'}</td>
          <td class="py-1.5 px-2.5 text-right text-mono">{fmtUsd(item.unit_cost_usd)}</td>
          <td class="py-1.5 px-2.5 text-right text-mono text-[var(--color-live)] font-semibold">{fmtQ(item.unit_cost)}</td>
          <td class="py-1.5 px-2.5 text-center whitespace-nowrap">
            {#if item.source_table === 'import_items'}
              {@const isBusy = busy.has(item.source_id)}
              {@const sentChina = item.sent_to_supplier_at && item.sent_to_supplier_via === 'china'}
              {@const sentHk = item.sent_to_supplier_at && item.sent_to_supplier_via === 'hk'}
              <div class="flex items-center justify-center gap-1.5">
                <button
                  class="text-mono text-[10px] uppercase px-2 py-1 rounded-[3px] border border-[var(--color-border)] hover:border-[var(--color-live)] hover:text-[var(--color-live)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors {sentChina ? 'border-[var(--color-live)] text-[var(--color-live)]' : 'text-[var(--color-text-secondary)]'}"
                  disabled={isBusy}
                  onclick={() => sendToSupplier(item, 'china')}
                  title={sentChina ? `Enviado a China hace ${timeAgo(item.sent_to_supplier_at)}` : 'Enviar a China (Bond)'}
                >
                  CN{#if sentChina} ✓{/if}
                </button>
                <button
                  class="text-mono text-[10px] uppercase px-2 py-1 rounded-[3px] border border-[var(--color-border)] hover:border-[var(--color-live)] hover:text-[var(--color-live)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors {sentHk ? 'border-[var(--color-live)] text-[var(--color-live)]' : 'text-[var(--color-text-secondary)]'}"
                  disabled={isBusy}
                  onclick={() => sendToSupplier(item, 'hk')}
                  title={sentHk ? `Enviado a HK hace ${timeAgo(item.sent_to_supplier_at)}` : 'Enviar a HK (Bond)'}
                >
                  HK{#if sentHk} ✓{/if}
                </button>
              </div>
              {#if item.sent_to_supplier_at}
                <div class="text-mono text-[9px] text-[var(--color-text-tertiary)] mt-1">
                  hace {timeAgo(item.sent_to_supplier_at)}
                </div>
              {/if}
            {:else}
              <span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">—</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>

  {#if toast}
    <div
      class="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-md text-mono text-[12px] shadow-lg max-w-md"
      class:bg-ready={toast.type === 'ok'}
      class:bg-alert={toast.type === 'err'}
      style="background-color: {toast.type === 'ok' ? 'var(--color-ready)' : 'var(--color-alert)'}; color: {toast.type === 'ok' ? '#000' : '#fff'};"
    >
      {toast.msg}
    </div>
  {/if}
</div>
