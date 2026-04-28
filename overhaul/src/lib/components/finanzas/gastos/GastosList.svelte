<script lang="ts">
  import type { Expense, ExpenseCategory, PaymentMethod } from '$lib/data/finanzas';
  import { CATEGORY_LABELS, CATEGORY_PILL_CLASS, PAYMENT_METHOD_ICON, PAYMENT_METHOD_LABEL } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let {
    expenses,
    onEdit,
    onDelete,
  }: {
    expenses: Expense[];
    onEdit: (e: Expense) => void;
    onDelete: (id: number) => void;
  } = $props();
</script>

<div class="border border-[var(--color-border)] rounded-[4px] overflow-hidden">
  <table class="w-full text-[11.5px] border-collapse">
    <thead class="bg-[var(--color-surface-1)]">
      <tr>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Fecha</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Notas</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Categoría</th>
        <th class="text-center text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Método</th>
        <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Monto</th>
        <th class="text-center text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Acc</th>
      </tr>
    </thead>
    <tbody>
      {#each expenses as exp (exp.expense_id)}
        <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)] transition-colors">
          <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-tertiary)] tabular-nums">{exp.paid_at}</td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-primary)] truncate max-w-[280px]" title={exp.notes ?? ''}>{exp.notes ?? '—'}</td>
          <td class="py-1.5 px-2.5">
            <span class="text-mono text-[9px] px-1.5 py-0.5 rounded-[2px] {CATEGORY_PILL_CLASS[exp.category as ExpenseCategory]}" style="letter-spacing: 0.04em;">
              {CATEGORY_LABELS[exp.category as ExpenseCategory]}
            </span>
          </td>
          <td class="py-1.5 px-2.5 text-center" title={PAYMENT_METHOD_LABEL[exp.payment_method as PaymentMethod]}>
            {PAYMENT_METHOD_ICON[exp.payment_method as PaymentMethod]}
          </td>
          <td class="py-1.5 px-2.5 text-right text-mono font-bold tabular-nums text-[var(--color-danger)]">
            −{formatGTQ(exp.amount_gtq).replace(/^Q/, 'Q')}
          </td>
          <td class="py-1.5 px-2.5 text-center whitespace-nowrap">
            <button
              type="button"
              class="text-mono text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] transition-colors"
              onclick={() => onEdit(exp)}
              title="Edit (R1.x)"
            >
              edit
            </button>
            <button
              type="button"
              class="text-mono text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-danger)] ml-2 transition-colors"
              onclick={() => onDelete(exp.expense_id)}
              title="Borrar gasto"
            >
              ×
            </button>
          </td>
        </tr>
      {/each}
      {#if expenses.length === 0}
        <tr>
          <td colspan="6" class="text-center py-8 text-mono text-[11px] text-[var(--color-text-tertiary)] italic">
            Sin gastos en el período seleccionado.
          </td>
        </tr>
      {/if}
    </tbody>
  </table>
</div>
