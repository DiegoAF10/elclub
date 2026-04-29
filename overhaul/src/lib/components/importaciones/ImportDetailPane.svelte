<script lang="ts">
  import { adapter } from '$lib/adapter';
  import ImportDetailHead from './ImportDetailHead.svelte';
  import ImportDetailSubtabs from './ImportDetailSubtabs.svelte';
  import OverviewSubtab from './detail/OverviewSubtab.svelte';
  import ItemsSubtab from './detail/ItemsSubtab.svelte';
  import CostosSubtab from './detail/CostosSubtab.svelte';
  import RegisterArrivalModal from './RegisterArrivalModal.svelte';
  import EditImportModal from './EditImportModal.svelte';
  import ConfirmCancelModal from './ConfirmCancelModal.svelte';
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }

  let { imp, onUpdated }: Props = $props();

  type SubtabId = 'overview' | 'items' | 'costos';
  let activeSubtab = $state<SubtabId>('overview');
  let items = $state<ImportItem[]>([]);

  // R1.5: Modal state
  let showArrivalModal = $state(false);
  let showEditModal = $state(false);
  let showCancelModal = $state(false);

  $effect(() => {
    if (imp) {
      loadItems(imp.import_id);
    } else {
      items = [];
      // Close any open modals · prevents stale state if user reopens after re-selection
      showArrivalModal = false;
      showEditModal = false;
      showCancelModal = false;
    }
  });

  async function loadItems(id: string) {
    items = await adapter.getImportItems(id);
  }

  function handleRegisterArrival() {
    if (!imp) return;
    showArrivalModal = true;
  }

  function handleEdit() {
    if (!imp) return;
    showEditModal = true;
  }

  async function handleClose() {
    if (!imp) return;
    if (!confirm(`Cerrar batch ${imp.import_id}?\nProrrateo D2=B aplicado a ${items.length} items.`)) return;
    try {
      const res = await adapter.closeImportProportional(imp.import_id);
      alert(`Batch cerrado · ${res.n_items_updated} sale_items + ${res.n_jerseys_updated} jerseys actualizados\nLanded total: Q${Math.round(res.total_landed_gtq)} · Avg/u: Q${Math.round(res.avg_unit_cost)}`);
      onUpdated();
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  function handleCancel() {
    if (!imp) return;
    showCancelModal = true;
  }
</script>

<div class="flex-1 flex flex-col min-w-0 overflow-hidden">
  {#if !imp}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Seleccioná un batch del panel izquierdo
    </div>
  {:else}
    <ImportDetailHead
      {imp}
      onRegisterArrival={handleRegisterArrival}
      onClose={handleClose}
      onCancel={handleCancel}
      onEdit={handleEdit}
      onRefresh={onUpdated}
    />
    <ImportDetailSubtabs bind:activeSubtab itemsCount={items.length} />

    <div class="flex-1 overflow-y-auto">
      {#if activeSubtab === 'overview'}
        <OverviewSubtab {imp} {items} />
      {:else if activeSubtab === 'items'}
        <ItemsSubtab {items} />
      {:else if activeSubtab === 'costos'}
        <CostosSubtab {imp} {items} />
      {/if}
    </div>
  {/if}
</div>

<RegisterArrivalModal
  open={showArrivalModal}
  importId={imp?.import_id ?? null}
  onClose={() => { showArrivalModal = false; }}
  onRegistered={() => { onUpdated(); showArrivalModal = false; }}
/>

<EditImportModal
  open={showEditModal}
  imp={imp}
  onClose={() => { showEditModal = false; }}
  onUpdated={() => { onUpdated(); showEditModal = false; }}
/>

<ConfirmCancelModal
  open={showCancelModal}
  imp={imp}
  onClose={() => { showCancelModal = false; }}
  onCancelled={() => { onUpdated(); showCancelModal = false; }}
/>
