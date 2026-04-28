<!-- TODO: T2.7 — MysteryShell cascarón con 3 tabs (Pool · Calendario · Universo) -->
<script lang="ts">
	interface Props {
		tab?: string;
	}
	let { tab = 'pool' }: Props = $props();
</script>

<div class="p-6 text-mono text-[12px] text-[var(--color-text-muted)]">
	<div class="text-display mb-3 text-[14px] text-[var(--color-text-primary)]">MYSTERY — {tab.toUpperCase()}</div>
	<div>TODO T2.7 — cascarón Mystery</div>
</div>
