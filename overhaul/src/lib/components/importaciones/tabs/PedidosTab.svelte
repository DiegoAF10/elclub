<script lang="ts">
  interface Props {
    onPulsoRefresh: () => void;
  }
  let { onPulsoRefresh }: Props = $props();
</script>

<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  Loading list-detail…
</div>
