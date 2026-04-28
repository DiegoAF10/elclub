<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }
  let { imp, onUpdated }: Props = $props();
</script>

<div class="flex-1 flex flex-col min-w-0">
  {#if !imp}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Seleccioná un batch del panel izquierdo
    </div>
  {:else}
    <!-- Detail head + sub-tabs vienen en Task 11 -->
    <div class="p-6 text-mono text-sm text-[var(--color-text-secondary)]">
      Batch {imp.import_id} · {imp.status}
    </div>
  {/if}
</div>
