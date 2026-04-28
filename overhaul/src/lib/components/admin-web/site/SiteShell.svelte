<!-- TODO: T2.7 — SiteShell cascarón con 6 tabs (Páginas · Branding · Componentes · Comunicación · Comunidad · Meta+Tracking) -->
<script lang="ts">
	interface Props {
		tab?: string;
	}
	let { tab = 'paginas' }: Props = $props();
</script>

<div class="p-6 text-mono text-[12px] text-[var(--color-text-muted)]">
	<div class="text-display mb-3 text-[14px] text-[var(--color-text-primary)]">SITE — {tab.toUpperCase()}</div>
	<div>TODO T2.7 — cascarón Site</div>
</div>
