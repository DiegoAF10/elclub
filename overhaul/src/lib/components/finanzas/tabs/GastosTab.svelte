<script lang="ts">
  import type { PeriodRange } from '$lib/data/finanzas';

  let { periodRange }: { periodRange: PeriodRange } = $props();
</script>

<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  <div class="text-center">
    <div class="text-mono text-[11px] uppercase mb-2" style="letter-spacing: 0.08em;">Gastos placeholder</div>
    <div class="text-sm">Form 3 actions + lista filtrable en Tasks 8/9 · período: {periodRange.label}</div>
  </div>
</div>
