<!--
	StockShell — cascarón v0 del módulo Stock (jerseys garantizadas Q475 con drops).
	Header con título + 3 tabs. Cada tab muestra PlaceholderPanel hasta que R7.1
	profundice (override engine, calendario interactivo, conflict detection).

	Tab routing via URL: /admin-web/stock/{drops|calendario|universo}
-->
<script lang="ts">
	import TabBar from '../shared/TabBar.svelte';
	import PlaceholderPanel from '../shared/PlaceholderPanel.svelte';
	import { Package } from 'lucide-svelte';

	interface Props {
		tab?: string;
	}
	let { tab = 'drops' }: Props = $props();

	const TABS = [
		{ slug: 'drops', label: 'Drops' },
		{ slug: 'calendario', label: 'Calendario' },
		{ slug: 'universo', label: 'Universo' }
	];

	const PANEL_DESC: Record<string, string> = {
		drops:
			'Lista de stock_overrides activos y programados. Crear/editar/pausar drops, asignar prioridad, definir badge y price_override.',
		calendario:
			'Vista calendario con drops marcados por fecha. Drag para reschedule, conflict detection.',
		universo:
			'Tabla densa de todas las jerseys con override Stock — filtros + bulk actions.'
	};

	const titleByTab = $derived(`STOCK · ${(TABS.find((t) => t.slug === tab)?.label ?? tab).toUpperCase()}`);
	const descByTab = $derived(PANEL_DESC[tab] ?? 'Cascarón placeholder.');
</script>

<div class="flex flex-1 flex-col">
	<!-- Header -->
	<div class="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4">
		<Package size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
		<div>
			<div class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]">STOCK</div>
			<div class="text-[10.5px] text-[var(--color-text-muted)]">Jerseys garantizadas · Q475</div>
		</div>
	</div>

	<TabBar basePath="/admin-web/stock" tabs={TABS} active={tab} />

	<PlaceholderPanel title={titleByTab} description={descByTab} future="R7.1" />
</div>
