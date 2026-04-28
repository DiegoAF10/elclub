<!-- TODO: T2.3 — AdminWebSidebar con 6 items + badges reactivos -->
<script lang="ts">
	interface Props {
		section: string;
	}
	let { section }: Props = $props();
</script>

<aside
	class="w-[200px] shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface-1)] p-2"
>
	<div class="text-mono text-[10px] text-[var(--color-text-muted)]">TODO T2.3 · {section}</div>
</aside>
