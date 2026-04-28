<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  import { STATUS_LABELS } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    onRegisterArrival: () => void;
    onClose: () => void;
    onCancel: () => void;
    onEdit: () => void;
  }

  let { imp, onRegisterArrival, onClose, onCancel, onEdit }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let canClose = $derived(imp.arrived_at !== null && imp.shipping_gtq !== null && imp.status !== 'closed');
  let canEdit = $derived(imp.status !== 'closed' && imp.status !== 'cancelled');

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function statusPillClass(status: string): string {
    return {
      closed:  'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      paid:    'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      arrived: 'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      draft:   'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled: 'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] ?? 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>

<div class="px-6 pt-4 pb-3 border-b border-[var(--color-border)]">
  <!-- ID row -->
  <div class="flex items-center gap-3 mb-2.5">
    <span class="text-mono text-[22px] font-bold text-[var(--color-text-primary)]" style="letter-spacing: -0.01em;">
      {imp.import_id}
    </span>
    <span class="text-mono text-[10px] uppercase tracking-wider rounded-[2px] px-2.5 py-1 {statusPillClass(imp.status)}">
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5"></span>
      {STATUS_LABELS[imp.status as keyof typeof STATUS_LABELS]}
    </span>
  </div>

  <!-- Meta row -->
  <div class="flex items-center gap-3 flex-wrap text-mono text-[11px] text-[var(--color-text-secondary)] mb-3">
    <strong class="text-[var(--color-text-primary)]">{imp.supplier}</strong>
    <span class="text-[var(--color-border-strong)]">·</span>
    <span>paid {imp.paid_at ?? 'pendiente'}</span>
    {#if leadDays !== null && imp.status !== 'closed'}
      <span class="text-[var(--color-border-strong)]">·</span>
      <span class="text-[var(--color-warning)]">{leadDays} días en pipeline</span>
    {/if}
    <span class="text-[var(--color-border-strong)]">·</span>
    <span>{imp.n_units ?? 0} units</span>
    <a href="#comercial-link" class="text-[var(--color-accent)] inline-flex items-center gap-1 px-2 py-0.5 border border-[rgba(91,141,239,0.3)] rounded-[2px] bg-[rgba(91,141,239,0.06)] hover:bg-[rgba(91,141,239,0.14)] no-underline">
      → Vínculo Comercial
    </a>
  </div>

  <!-- Action toolbar — ARRIBA (D-Diego v2) -->
  <div class="flex items-center gap-2 pt-3 border-t border-[var(--color-surface-2)]">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] mr-1" style="letter-spacing: 0.08em;">Acciones:</span>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]" onclick={onRegisterArrival}>
      📥 Registrar arrival
    </button>
    <button
      disabled
      title="PayPal invoice viewer diferido a IMP-R5+ · upload manual via Notes por ahora"
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60"
    >
      📋 Ver invoice PayPal
    </button>
    <button
      disabled
      title="DHL tracking auto-sync diferido a IMP-R5+ · pegar tracking_code en Editar por ahora"
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-60"
    >
      📋 Ver tracking DHL
    </button>
    <button
      onclick={onEdit}
      disabled={!canEdit}
      title={canEdit ? 'Editar notes/tracking/carrier' : 'No editable en status closed o cancelled'}
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
      class:cursor-not-allowed={!canEdit}
      class:opacity-60={!canEdit}
    >
      📝 Editar
    </button>
    <span class="flex-1"></span>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-[rgba(244,63,94,0.3)] text-[var(--color-danger)] hover:bg-[rgba(244,63,94,0.10)]" onclick={onCancel}>
      🚫 Cancelar batch
    </button>
    <button
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] font-semibold transition-colors"
      class:bg-[var(--color-accent)]={canClose}
      class:text-[var(--color-bg)]={canClose}
      class:hover:bg-[var(--color-accent-hover)]={canClose}
      class:bg-[var(--color-surface-2)]={!canClose}
      class:text-[var(--color-text-tertiary)]={!canClose}
      class:cursor-not-allowed={!canClose}
      disabled={!canClose}
      title={canClose ? 'Cerrar batch · prorrateo proporcional D2=B' : 'Disponible cuando arrived_at + shipping_gtq estén llenos'}
      onclick={onClose}
    >
      ✅ Cerrar batch
    </button>
  </div>
</div>
