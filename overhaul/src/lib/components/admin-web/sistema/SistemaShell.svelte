<!-- TODO: T2.7 — SistemaShell cascarón con 4 tabs (Status · Operaciones · Configuración · Audit) -->
<script lang="ts">
	interface Props {
		tab?: string;
	}
	let { tab = 'status' }: Props = $props();
</script>

<div class="p-6 text-mono text-[12px] text-[var(--color-text-muted)]">
	<div class="text-display mb-3 text-[14px] text-[var(--color-text-primary)]">SISTEMA — {tab.toUpperCase()}</div>
	<div>TODO T2.7 — cascarón Sistema</div>
</div>
