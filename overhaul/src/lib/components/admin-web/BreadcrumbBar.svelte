<!-- TODO: T2.4 — BreadcrumbBar auto-tracking del route -->
<script lang="ts">
	interface Props {
		section: string;
		tab?: string;
	}
	let { section, tab }: Props = $props();
</script>

<div class="text-mono px-3 py-1.5 text-[10px] text-[var(--color-text-muted)]">
	TODO T2.4 · {section}{tab ? ` › ${tab}` : ''}
</div>
