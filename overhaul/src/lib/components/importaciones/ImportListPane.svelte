<script lang="ts">
  import { Search } from 'lucide-svelte';
  import ImportRow from './ImportRow.svelte';
  import type { Import, ImportFilter } from '$lib/data/importaciones';

  interface Props {
    imports: Import[];
    activeId: string | null;
    onSelect: (id: string) => void;
  }

  let { imports, activeId, onSelect }: Props = $props();

  let filter = $state<ImportFilter>({ status: 'all' });
  let search = $state('');

  let filtered = $derived(applyFilter(imports, filter, search));

  function applyFilter(list: Import[], f: ImportFilter, q: string): Import[] {
    let out = list;
    if (f.status === 'pipeline') {
      out = out.filter(i => ['paid', 'in_transit', 'arrived'].includes(i.status));
    } else if (f.status === 'closed') {
      out = out.filter(i => i.status === 'closed');
    }
    if (f.supplier) {
      out = out.filter(i => i.supplier === f.supplier);
    }
    if (q.trim()) {
      const ql = q.toLowerCase();
      out = out.filter(i =>
        i.import_id.toLowerCase().includes(ql) ||
        i.supplier.toLowerCase().includes(ql) ||
        i.notes?.toLowerCase().includes(ql)
      );
    }
    return out;
  }

  function countByStatus(s: string): number {
    if (s === 'all') return imports.length;
    if (s === 'pipeline') return imports.filter(i => ['paid','in_transit','arrived'].includes(i.status)).length;
    return imports.filter(i => i.status === s).length;
  }
</script>

<aside class="w-[320px] flex-shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface-1)] flex flex-col">
  <!-- Search -->
  <div class="p-3 border-b border-[var(--color-border)]">
    <div class="flex items-center gap-2 px-2.5 py-1.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px]">
      <Search size={13} class="text-[var(--color-text-tertiary)]" strokeWidth={1.8} />
      <input
        type="text"
        bind:value={search}
        placeholder="ID pedido, SKU, cliente, supplier..."
        class="flex-1 bg-transparent border-0 outline-none text-mono text-[11.5px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]"
      />
    </div>
  </div>

  <!-- Filter chips -->
  <div class="flex gap-1.5 px-3 py-2 border-b border-[var(--color-border)] flex-wrap">
    {#each [{id:'all',label:'Todos'}, {id:'pipeline',label:'Pipeline'}, {id:'closed',label:'Closed'}] as chip}
      <button
        type="button"
        class="text-mono text-[9.5px] px-2 py-0.5 rounded-[2px] border transition-colors"
        class:bg-[rgba(91,141,239,0.14)]={filter.status === chip.id}
        class:text-[var(--color-accent)]={filter.status === chip.id}
        class:border-[rgba(91,141,239,0.3)]={filter.status === chip.id}
        class:bg-[var(--color-surface-2)]={filter.status !== chip.id}
        class:text-[var(--color-text-secondary)]={filter.status !== chip.id}
        class:border-[var(--color-border)]={filter.status !== chip.id}
        style="letter-spacing: 0.05em;"
        onclick={() => filter = { ...filter, status: chip.id as ImportFilter['status'] }}
      >
        {chip.label}<span class="ml-1 text-[var(--color-text-tertiary)]">{countByStatus(chip.id)}</span>
      </button>
    {/each}
  </div>

  <!-- Rows -->
  <div class="flex-1 overflow-y-auto">
    {#each filtered as imp (imp.import_id)}
      <ImportRow {imp} isActive={imp.import_id === activeId} {onSelect} />
    {:else}
      <div class="p-6 text-center text-[var(--color-text-tertiary)] text-sm">
        Sin batches que matcheen los filtros.
      </div>
    {/each}
  </div>
</aside>
