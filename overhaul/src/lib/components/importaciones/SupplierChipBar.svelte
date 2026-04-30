<script lang="ts">
  import type { SupplierMetrics } from '$lib/adapter/types';

  interface Props {
    suppliers: SupplierMetrics[];
    activeSupplier: string | null;
    onSelect: (supplier: string) => void;
  }

  let { suppliers, activeSupplier, onSelect }: Props = $props();
</script>

<div class="flex items-center gap-2 mb-4 flex-wrap">
  {#each suppliers as s (s.supplier)}
    <button
      onclick={() => onSelect(s.supplier)}
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] border transition-colors"
      class:bg-[var(--color-accent)]={activeSupplier === s.supplier}
      class:text-[var(--color-bg)]={activeSupplier === s.supplier}
      class:border-[var(--color-accent)]={activeSupplier === s.supplier}
      class:bg-[var(--color-surface-2)]={activeSupplier !== s.supplier}
      class:border-[var(--color-border)]={activeSupplier !== s.supplier}
      class:text-[var(--color-text-primary)]={activeSupplier !== s.supplier}
      style="letter-spacing: 0.04em;"
    >
      {s.supplier}
      <span class="ml-1.5 opacity-70 tabular-nums">({s.totalBatches})</span>
    </button>
  {/each}

  <!-- Future scaffold: + supplier · disabled per Open Question recommendation -->
  <button
    disabled
    title="Multi-supplier en v0.5 (cuando Diego agregue Yupoo direct/Aliexpress)"
    class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-dashed border-[var(--color-border)] text-[var(--color-text-tertiary)] cursor-not-allowed opacity-50"
    style="letter-spacing: 0.04em;"
  >
    + supplier
  </button>
</div>
