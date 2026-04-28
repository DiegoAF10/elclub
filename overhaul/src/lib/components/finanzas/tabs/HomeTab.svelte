<script lang="ts">
  import type { PeriodRange } from '$lib/data/finanzas';

  let { periodRange }: { periodRange: PeriodRange } = $props();
</script>

<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  <div class="text-center">
    <div class="text-mono text-[11px] uppercase mb-2" style="letter-spacing: 0.08em;">Home placeholder</div>
    <div class="text-sm">Dashboard A2 (4 cards + waterfall + sub-grid) en Task 7 · período: {periodRange.label}</div>
  </div>
</div>
