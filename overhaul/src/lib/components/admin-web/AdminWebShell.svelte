<!-- TODO: T2.2 — AdminWebShell que orquesta sidebar interno + body slot -->
<script lang="ts">
	let { children } = $props();
</script>

<div class="flex h-full">
	<div class="text-mono p-4 text-[10px] text-[var(--color-text-muted)]">TODO T2.2</div>
	{@render children?.()}
</div>
