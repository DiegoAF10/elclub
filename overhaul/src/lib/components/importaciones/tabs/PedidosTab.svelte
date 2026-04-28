<script lang="ts">
  import { onMount } from 'svelte';
  import ImportListPane from '../ImportListPane.svelte';
  import ImportDetailPane from '../ImportDetailPane.svelte';
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    onPulsoRefresh: () => void;
  }
  let { onPulsoRefresh }: Props = $props();

  let imports = $state<Import[]>([]);
  let activeId = $state<string | null>(null);
  let activeImport = $derived(imports.find(i => i.import_id === activeId) ?? null);
  let loading = $state(true);

  onMount(load);

  async function load() {
    loading = true;
    imports = await adapter.listImports();
    if (imports.length > 0 && !activeId) {
      activeId = imports[0].import_id;  // default: most recent
    }
    loading = false;
  }

  function handleSelect(id: string) {
    activeId = id;
  }

  async function handleBatchUpdated() {
    await load();
    onPulsoRefresh();
  }
</script>

<div class="flex flex-1 min-h-0">
  {#if loading}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Cargando batches…
    </div>
  {:else}
    <ImportListPane {imports} {activeId} onSelect={handleSelect} />
    <ImportDetailPane imp={activeImport} onUpdated={handleBatchUpdated} />
  {/if}
</div>
