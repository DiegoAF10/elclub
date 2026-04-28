<!--
	MysteryShell — cascarón v0 del módulo Mystery (pool de sorpresa con drops temáticos).
	Header con título + icon ⚙ "Reglas" (no funcional en R7, abre modal en R7.2)
	+ 3 tabs. R7.2 implementa el algoritmo random ponderado, anti-repeat, fairness.

	Tab routing: /admin-web/mystery/{pool|calendario|universo}
-->
<script lang="ts">
	import TabBar from '../shared/TabBar.svelte';
	import PlaceholderPanel from '../shared/PlaceholderPanel.svelte';
	import { Sparkles, Settings2 } from 'lucide-svelte';

	interface Props {
		tab?: string;
	}
	let { tab = 'pool' }: Props = $props();

	const TABS = [
		{ slug: 'pool', label: 'Pool' },
		{ slug: 'calendario', label: 'Calendario' },
		{ slug: 'universo', label: 'Universo' }
	];

	const PANEL_DESC: Record<string, string> = {
		pool:
			'Lista de jerseys en pool Mystery con pool_weight (multiplicador del algoritmo). Activar/pausar/ajustar weights.',
		calendario: 'Drops temáticos del Mystery por fecha (ej. "Mundial Week", "Retro Sundays").',
		universo: 'Universo de jerseys con override Mystery — filtros densos + bulk actions.'
	};

	const titleByTab = $derived(
		`MYSTERY · ${(TABS.find((t) => t.slug === tab)?.label ?? tab).toUpperCase()}`
	);
	const descByTab = $derived(PANEL_DESC[tab] ?? 'Cascarón placeholder.');
</script>

<div class="flex flex-1 flex-col">
	<!-- Header con título + icon ⚙ Reglas -->
	<div
		class="flex h-12 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4"
	>
		<div class="flex items-center gap-3">
			<Sparkles size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
			<div>
				<div
					class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]"
				>
					MYSTERY
				</div>
				<div class="text-[10.5px] text-[var(--color-text-muted)]">
					Pool sorpresa · algoritmo ponderado
				</div>
			</div>
		</div>

		<button
			type="button"
			disabled
			class="flex items-center gap-1.5 rounded-[3px] border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-tertiary)] opacity-60"
			title="Reglas del pool — funcionalidad en R7.2"
		>
			<Settings2 size={12} strokeWidth={1.8} />
			<span class="font-medium">Reglas</span>
		</button>
	</div>

	<TabBar basePath="/admin-web/mystery" tabs={TABS} active={tab} />

	<PlaceholderPanel title={titleByTab} description={descByTab} future="R7.2" />
</div>
