<script lang="ts">
  import { onMount } from 'svelte';
  import { adapter } from '$lib/adapter';
  import type { RecentExpense } from '$lib/data/finanzas';
  import { CATEGORY_LABELS, CATEGORY_PILL_CLASS, PAYMENT_METHOD_ICON } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let items = $state<RecentExpense[]>([]);
  let loading = $state(true);

  onMount(async () => {
    try {
      items = await adapter.recentExpenses(6);
    } catch (e) {
      console.error('recentExpenses failed', e);
      items = [];
    } finally {
      loading = false;
    }
  });
</script>

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 flex flex-col min-h-0">
  <div class="text-mono text-[10px] uppercase mb-3 text-[var(--color-text-tertiary)] flex items-center justify-between" style="letter-spacing: 0.08em;">
    <span>Últimos gastos</span>
    <span class="text-[var(--color-text-secondary)]">{items.length}</span>
  </div>
  {#if loading}
    <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">cargando…</div>
  {:else if items.length === 0}
    <div class="text-mono text-[11px] text-[var(--color-text-tertiary)] italic">sin gastos registrados</div>
  {:else}
    <ul class="flex flex-col gap-1.5 overflow-y-auto">
      {#each items as exp (exp.expense_id)}
        <li class="flex items-center gap-2 text-[11.5px]">
          <span class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] w-[78px] shrink-0">{exp.paid_at}</span>
          <span class="flex-1 truncate text-[var(--color-text-primary)]">{exp.notes ?? CATEGORY_LABELS[exp.category]}</span>
          <span class="text-mono text-[9px] px-1.5 py-0.5 rounded-[2px] {CATEGORY_PILL_CLASS[exp.category]}" style="letter-spacing: 0.04em;">{CATEGORY_LABELS[exp.category]}</span>
          <span class="text-base shrink-0" aria-hidden="true">{PAYMENT_METHOD_ICON[exp.payment_method]}</span>
          <span class="text-mono text-[12px] font-bold tabular-nums text-[var(--color-danger)] shrink-0">−{formatGTQ(exp.amount_gtq).replace(/^Q/, 'Q')}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>
