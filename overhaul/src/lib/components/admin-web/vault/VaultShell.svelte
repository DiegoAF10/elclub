<!-- TODO: T4.1 — VaultShell con 4 tabs (Queue · Publicados · Grupos · Universo) -->
<script lang="ts">
	interface Props {
		tab?: string;
	}
	let { tab = 'queue' }: Props = $props();
</script>

<div class="p-6 text-mono text-[12px] text-[var(--color-text-muted)]">
	<div class="text-display mb-3 text-[14px] text-[var(--color-text-primary)]">VAULT — {tab.toUpperCase()}</div>
	<div>TODO T4.x — Queue · Publicados · Grupos · Universo</div>
</div>
