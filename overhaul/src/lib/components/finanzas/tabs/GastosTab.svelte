<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Expense, ExpenseCategory, PaymentMethod, PeriodRange } from '$lib/data/finanzas';
  import { CATEGORY_LABELS } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';
  import GastoForm from '../gastos/GastoForm.svelte';
  import GastosList from '../gastos/GastosList.svelte';

  let { periodRange }: { periodRange: PeriodRange } = $props();

  let expenses = $state<Expense[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showForm = $state(false);
  let categoryFilter = $state<ExpenseCategory | 'all'>('all');
  let methodFilter = $state<PaymentMethod | 'all'>('all');
  let loadGen = 0;

  $effect(() => {
    const my = ++loadGen;
    void load(periodRange, categoryFilter, methodFilter, my);
  });

  async function load(
    range: PeriodRange,
    cat: ExpenseCategory | 'all',
    method: PaymentMethod | 'all',
    my: number,
  ) {
    loading = true;
    error = null;
    try {
      const result = await adapter.listExpenses({
        periodStart: range.start,
        periodEnd: range.end,
        category: cat === 'all' ? undefined : cat,
        paymentMethod: method === 'all' ? undefined : method,
      });
      if (my !== loadGen) return; // stale
      expenses = result;
    } catch (e) {
      if (my !== loadGen) return;
      console.error('listExpenses failed', e);
      error = e instanceof Error ? e.message : String(e);
      expenses = [];
    } finally {
      if (my === loadGen) loading = false;
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Borrar gasto? Si era TDC personal, también se borra el shareholder_loan_movement asociado.')) return;
    try {
      await adapter.deleteExpense(id);
      const my = ++loadGen;
      await load(periodRange, categoryFilter, methodFilter, my);
    } catch (e) {
      alert(`Error borrando: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  function handleEdit(_exp: Expense) {
    alert('Edit modal en R1.x · por ahora delete + create de nuevo.');
  }

  let totalGtq = $derived(expenses.reduce((sum, e) => sum + e.amount_gtq, 0));
  let categoryCounts = $derived.by(() => {
    const counts = new Map<ExpenseCategory, number>();
    for (const e of expenses) {
      counts.set(e.category, (counts.get(e.category) ?? 0) + 1);
    }
    return counts;
  });

  const CATEGORIES: Array<ExpenseCategory> = ['variable', 'tech', 'marketing', 'operations', 'owner_draw', 'other'];
</script>

<div class="flex-1 p-6 overflow-y-auto">
  <!-- Header: count + total + new button -->
  <div class="flex items-center mb-4">
    <div>
      <h2 class="text-mono text-[14px] uppercase font-semibold text-[var(--color-text-primary)]" style="letter-spacing: 0.04em;">
        Gastos · {expenses.length}
      </h2>
      <div class="text-mono text-[11px] text-[var(--color-text-tertiary)] mt-0.5">
        total del período: <span class="text-[var(--color-danger)] font-bold tabular-nums">−{formatGTQ(totalGtq).replace(/^Q/, 'Q')}</span>
      </div>
    </div>
    <button
      type="button"
      class="ml-auto text-mono text-[11px] font-bold px-4 py-2 bg-[var(--color-accent)] text-[var(--color-bg)] rounded-[3px] hover:bg-[var(--color-accent-hover)] transition-colors"
      onclick={() => showForm = !showForm}
    >
      {showForm ? '× Cerrar' : '+ Nuevo gasto'}
    </button>
  </div>

  <!-- Filters: category + method -->
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] mr-1" style="letter-spacing: 0.08em;">Categoría:</span>
    <button
      type="button"
      class="text-mono text-[10px] px-2 py-1 rounded-[2px] border transition-colors"
      class:bg-[rgba(91,141,239,0.16)]={categoryFilter === 'all'}
      class:text-[var(--color-accent)]={categoryFilter === 'all'}
      class:border-[rgba(91,141,239,0.4)]={categoryFilter === 'all'}
      class:bg-[var(--color-surface-2)]={categoryFilter !== 'all'}
      class:text-[var(--color-text-secondary)]={categoryFilter !== 'all'}
      class:border-[var(--color-border)]={categoryFilter !== 'all'}
      onclick={() => categoryFilter = 'all'}
    >
      Todas
    </button>
    {#each CATEGORIES as cat (cat)}
      {@const count = categoryCounts.get(cat) ?? 0}
      <button
        type="button"
        class="text-mono text-[10px] px-2 py-1 rounded-[2px] border transition-colors"
        class:bg-[rgba(91,141,239,0.16)]={categoryFilter === cat}
        class:text-[var(--color-accent)]={categoryFilter === cat}
        class:border-[rgba(91,141,239,0.4)]={categoryFilter === cat}
        class:bg-[var(--color-surface-2)]={categoryFilter !== cat}
        class:text-[var(--color-text-secondary)]={categoryFilter !== cat}
        class:border-[var(--color-border)]={categoryFilter !== cat}
        onclick={() => categoryFilter = cat}
      >
        {CATEGORY_LABELS[cat]} {#if count > 0}<span class="text-[var(--color-text-tertiary)]">·{count}</span>{/if}
      </button>
    {/each}

    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] ml-3 mr-1" style="letter-spacing: 0.08em;">Método:</span>
    <button
      type="button"
      class="text-mono text-[10px] px-2 py-1 rounded-[2px] border transition-colors"
      class:bg-[rgba(91,141,239,0.16)]={methodFilter === 'all'}
      class:text-[var(--color-accent)]={methodFilter === 'all'}
      class:border-[rgba(91,141,239,0.4)]={methodFilter === 'all'}
      class:bg-[var(--color-surface-2)]={methodFilter !== 'all'}
      class:text-[var(--color-text-secondary)]={methodFilter !== 'all'}
      class:border-[var(--color-border)]={methodFilter !== 'all'}
      onclick={() => methodFilter = 'all'}
    >
      Todos
    </button>
    <button
      type="button"
      class="text-mono text-[10px] px-2 py-1 rounded-[2px] border transition-colors"
      class:bg-[rgba(91,141,239,0.16)]={methodFilter === 'tdc_personal'}
      class:text-[var(--color-accent)]={methodFilter === 'tdc_personal'}
      class:border-[rgba(91,141,239,0.4)]={methodFilter === 'tdc_personal'}
      class:bg-[var(--color-surface-2)]={methodFilter !== 'tdc_personal'}
      class:text-[var(--color-text-secondary)]={methodFilter !== 'tdc_personal'}
      class:border-[var(--color-border)]={methodFilter !== 'tdc_personal'}
      onclick={() => methodFilter = 'tdc_personal'}
    >
      💳 TDC personal
    </button>
    <button
      type="button"
      class="text-mono text-[10px] px-2 py-1 rounded-[2px] border transition-colors"
      class:bg-[rgba(91,141,239,0.16)]={methodFilter === 'cuenta_business'}
      class:text-[var(--color-accent)]={methodFilter === 'cuenta_business'}
      class:border-[rgba(91,141,239,0.4)]={methodFilter === 'cuenta_business'}
      class:bg-[var(--color-surface-2)]={methodFilter !== 'cuenta_business'}
      class:text-[var(--color-text-secondary)]={methodFilter !== 'cuenta_business'}
      class:border-[var(--color-border)]={methodFilter !== 'cuenta_business'}
      onclick={() => methodFilter = 'cuenta_business'}
    >
      🏦 Cuenta business
    </button>
  </div>

  <!-- Form (collapsible) -->
  {#if showForm}
    <div class="mb-6">
      <GastoForm
        onSaved={() => { showForm = false; const my = ++loadGen; void load(periodRange, categoryFilter, methodFilter, my); }}
        onCancel={() => showForm = false}
      />
    </div>
  {/if}

  <!-- List or status -->
  {#if loading}
    <div class="text-mono text-[12px] text-[var(--color-text-tertiary)]">Cargando gastos…</div>
  {:else if error}
    <div class="text-mono text-[12px] text-[var(--color-danger)]">⚠ {error}</div>
  {:else}
    <GastosList {expenses} onEdit={handleEdit} onDelete={handleDelete} />
  {/if}
</div>
