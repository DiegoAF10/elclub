<script lang="ts">
  import type { Customer } from '$lib/data/comercial';
  import { Users } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    customers: Customer[];
    onClose: () => void;
  }
  let { customers, onClose }: Props = $props();

  type SortKey = 'ltv' | 'lastOrder' | 'totalOrders' | 'firstOrder';
  let sortBy = $state<SortKey>('ltv');

  let sorted = $derived.by(() => {
    const arr = [...customers];
    switch (sortBy) {
      case 'ltv':
        return arr.sort((a, b) => b.totalRevenueGtq - a.totalRevenueGtq);
      case 'lastOrder':
        return arr.sort((a, b) => (b.lastOrderAt ?? '').localeCompare(a.lastOrderAt ?? ''));
      case 'totalOrders':
        return arr.sort((a, b) => b.totalOrders - a.totalOrders);
      case 'firstOrder':
        return arr.sort((a, b) => (a.firstOrderAt ?? '').localeCompare(b.firstOrderAt ?? ''));
    }
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(180,181,184,0.12); border: 1px solid rgba(180,181,184,0.3);">
        <Users size={18} strokeWidth={1.8} style="color: var(--color-text-tertiary);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Customers · {customers.length}</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Vista simple — profile completo en R4</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    <div class="px-6 py-4">
      <div class="mb-3 flex gap-1.5">
        {#each [['ltv','LTV'],['lastOrder','Última'],['totalOrders','Órdenes'],['firstOrder','Primera']] as [key, lbl]}
          {@const active = sortBy === key}
          <button
            type="button"
            onclick={() => (sortBy = key as SortKey)}
            class="rounded-[3px] border px-2.5 py-0.5 text-[10px] transition-colors"
            style="
              background: {active ? 'rgba(74,222,128,0.12)' : 'var(--color-surface-1)'};
              border-color: {active ? 'rgba(74,222,128,0.4)' : 'var(--color-border)'};
              color: {active ? 'var(--color-accent)' : 'var(--color-text-secondary)'};
            "
          >Sort: {lbl}</button>
        {/each}
      </div>

      <table class="w-full text-[11.5px]">
        <thead>
          <tr class="text-display border-b border-[var(--color-border)] text-[9.5px] text-[var(--color-text-tertiary)]">
            <th class="px-2 py-1 text-left">Cliente</th>
            <th class="px-2 py-1 text-right">Órdenes</th>
            <th class="px-2 py-1 text-right">LTV</th>
            <th class="px-2 py-1 text-right">Primera</th>
            <th class="px-2 py-1 text-right">Última</th>
          </tr>
        </thead>
        <tbody>
          {#each sorted as c (c.customerId)}
            <tr class="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-1)]">
              <td class="px-2 py-1.5">
                <div class="text-[12px]">{c.name}</div>
                <div class="text-[10px] text-[var(--color-text-muted)]">{c.phone ?? c.email ?? '—'}</div>
              </td>
              <td class="text-mono px-2 py-1.5 text-right">{c.totalOrders}</td>
              <td class="text-mono px-2 py-1.5 text-right" style="color: var(--color-accent);">Q{c.totalRevenueGtq.toFixed(0)}</td>
              <td class="text-mono px-2 py-1.5 text-right text-[var(--color-text-tertiary)]">{fmtDate(c.firstOrderAt)}</td>
              <td class="text-mono px-2 py-1.5 text-right text-[var(--color-text-tertiary)]">{fmtDate(c.lastOrderAt)}</td>
            </tr>
          {/each}
        </tbody>
      </table>

      {#if customers.length === 0}
        <div class="mt-4 text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 customers — todavía no hay compradores recurrentes</div>
      {/if}
    </div>
  {/snippet}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
    >Cerrar</button>
  {/snippet}
</BaseModal>
