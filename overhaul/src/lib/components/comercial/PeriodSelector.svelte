<script lang="ts">
  import type { Period } from '$lib/data/comercial';

  interface Props {
    value: Period;
    onChange: (p: Period) => void;
  }

  let { value, onChange }: Props = $props();

  const PERIODS: { id: Period; label: string }[] = [
    { id: 'today', label: 'Hoy' },
    { id: '7d', label: '7d' },
    { id: '30d', label: '30d' },
    { id: 'custom', label: 'Custom' }
  ];
</script>

<div class="flex gap-1">
  {#each PERIODS as p (p.id)}
    {@const isActive = value === p.id}
    <button
      type="button"
      onclick={() => onChange(p.id)}
      class="rounded-[3px] px-2.5 py-1 text-[10.5px] transition-colors"
      style="
        background: {isActive ? 'var(--color-surface-1)' : 'transparent'};
        color: {isActive ? 'var(--color-text-secondary)' : 'var(--color-text-tertiary)'};
      "
    >
      {p.label}
    </button>
  {/each}
</div>
