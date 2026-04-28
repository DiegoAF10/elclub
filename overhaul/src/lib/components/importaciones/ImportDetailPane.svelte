<script lang="ts">
  import ImportDetailHead from './ImportDetailHead.svelte';
  import ImportDetailSubtabs from './ImportDetailSubtabs.svelte';
  import OverviewSubtab from './detail/OverviewSubtab.svelte';
  import ItemsSubtab from './detail/ItemsSubtab.svelte';
  import CostosSubtab from './detail/CostosSubtab.svelte';
  import { adapter } from '$lib/adapter';
  import type { Import, ImportItem } from '$lib/data/importaciones';

  type SubtabId = 'overview' | 'items' | 'costos' | 'pagos' | 'timeline';

  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }

  let { imp, onUpdated }: Props = $props();

  let items = $state<ImportItem[]>([]);
  let activeSubtab = $state<SubtabId>('overview');

  $effect(() => {
    if (imp) loadItems(imp.import_id);
    else items = [];
  });

  async function loadItems(id: string) {
    items = await adapter.getImportItems(id);
  }

  function handleRegisterArrival() {
    // R1.x: modal de registro · por ahora prompt simple
    alert('Registrar arrival viene en R1.x — flow: input arrived_at + shipping_gtq');
  }

  function handleClose() {
    if (!imp) return;
    if (!confirm(`Cerrar batch ${imp.import_id}?\nEsto aplica prorrateo proporcional D2=B a ${items.length} items.`)) return;
    // Implementar en Task 13
    alert('Close batch viene en Task 13 (close_import_proportional)');
  }

  function handleCancel() {
    alert('Cancelar batch viene en R1.x');
  }
</script>

<div class="flex-1 flex flex-col min-w-0 overflow-hidden">
  {#if !imp}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Seleccioná un batch del panel izquierdo
    </div>
  {:else}
    <ImportDetailHead {imp} onRegisterArrival={handleRegisterArrival} onClose={handleClose} onCancel={handleCancel} />
    <ImportDetailSubtabs bind:activeSubtab itemsCount={items.length} paymentsCount={imp.bruto_usd ? 1 : 0} />

    <div class="flex-1 overflow-y-auto">
      {#if activeSubtab === 'overview'}
        <OverviewSubtab {imp} {items} />
      {:else if activeSubtab === 'items'}
        <ItemsSubtab {items} />
      {:else if activeSubtab === 'costos'}
        <CostosSubtab {imp} {items} />
      {:else if activeSubtab === 'pagos'}
        <div class="p-6 text-[var(--color-text-tertiary)]">Lista de pagos viene en R1.x</div>
      {:else if activeSubtab === 'timeline'}
        <div class="p-6 text-[var(--color-text-tertiary)]">Timeline expandido viene en R1.x</div>
      {/if}
    </div>
  {/if}
</div>
