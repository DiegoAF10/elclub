<!-- TODO: T2.7 — StockShell cascarón con 3 tabs (Drops · Calendario · Universo) -->
<script lang="ts">
	interface Props {
		tab?: string;
	}
	let { tab = 'drops' }: Props = $props();
</script>

<div class="p-6 text-mono text-[12px] text-[var(--color-text-muted)]">
	<div class="text-display mb-3 text-[14px] text-[var(--color-text-primary)]">STOCK — {tab.toUpperCase()}</div>
	<div>TODO T2.7 — cascarón Stock</div>
</div>
