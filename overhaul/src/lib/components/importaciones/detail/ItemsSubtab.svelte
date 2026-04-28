<script lang="ts">
  import type { ImportItem } from '$lib/data/importaciones';

  interface Props { items: ImportItem[]; }
  let { items }: Props = $props();

  let sortBy = $state<'sku' | 'usd' | 'landed' | 'customer'>('sku');
  let sortDesc = $state(false);

  let sorted = $derived([...items].sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'sku') cmp = a.family_id.localeCompare(b.family_id);
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
</script>

<div class="p-6 overflow-y-auto">
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
      </tr>
    </thead>
    <tbody>
      {#each sorted as item (item.source_table + ':' + item.source_id)}
        <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
          <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-primary)]">
            {item.family_id}
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
          <td class="py-1.5 px-2.5 text-mono text-[10px] text-[var(--color-text-tertiary)] uppercase">{item.source_table === 'sale_items' ? 'sale' : 'jersey'}</td>
          <td class="py-1.5 px-2.5 text-right text-mono">{fmtUsd(item.unit_cost_usd)}</td>
          <td class="py-1.5 px-2.5 text-right text-mono text-[var(--color-live)] font-semibold">{fmtQ(item.unit_cost)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
