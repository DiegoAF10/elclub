<!--
	AccesosTiles — 5 tiles de acceso rápido a los sub-módulos del Admin Web.
	Cada tile: icon + nombre + 2 mini-stats (cargados via get_module_stats).
	Click → goto /admin-web/{module} (redirect → default tab).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { Archive, Package, Sparkles, Globe, Server } from 'lucide-svelte';
	import { adminWeb } from '$lib/adapter';
	import type { ModuleSlug } from '$lib/adapter';

	interface Tile {
		slug: ModuleSlug;
		label: string;
		icon: typeof Archive;
		stat1Key: string;
		stat1Label: string;
		stat2Key: string;
		stat2Label: string;
	}

	const TILES: Tile[] = [
		{
			slug: 'vault',
			label: 'Vault',
			icon: Archive,
			stat1Key: 'queue',
			stat1Label: 'Queue',
			stat2Key: 'publicados',
			stat2Label: 'Publicados'
		},
		{
			slug: 'stock',
			label: 'Stock',
			icon: Package,
			stat1Key: 'live',
			stat1Label: 'Live',
			stat2Key: 'scheduled',
			stat2Label: 'Scheduled'
		},
		{
			slug: 'mystery',
			label: 'Mystery',
			icon: Sparkles,
			stat1Key: 'live',
			stat1Label: 'Live',
			stat2Key: 'total',
			stat2Label: 'Pool'
		},
		{
			slug: 'site',
			label: 'Site',
			icon: Globe,
			stat1Key: 'live_pages',
			stat1Label: 'Live',
			stat2Key: 'pages',
			stat2Label: 'Páginas'
		},
		{
			slug: 'sistema',
			label: 'Sistema',
			icon: Server,
			stat1Key: 'jobs',
			stat1Label: 'Jobs',
			stat2Key: 'backups',
			stat2Label: 'Backups'
		}
	];

	let statsByModule = $state<Record<ModuleSlug, Record<string, number>>>({
		vault: {},
		stock: {},
		mystery: {},
		site: {},
		sistema: {}
	});

	async function loadAllStats() {
		const out: Record<ModuleSlug, Record<string, number>> = {
			vault: {},
			stock: {},
			mystery: {},
			site: {},
			sistema: {}
		};
		await Promise.all(
			TILES.map(async (t) => {
				try {
					const stats = await adminWeb.get_module_stats({ module: t.slug });
					// Filtrar a number values
					const numeric: Record<string, number> = {};
					for (const [k, v] of Object.entries(stats)) {
						if (typeof v === 'number') numeric[k] = v;
					}
					out[t.slug] = numeric;
				} catch {
					/* mantener vacío en error */
				}
			})
		);
		statsByModule = out;
	}

	$effect(() => {
		void loadAllStats();
	});
</script>

<div class="grid grid-cols-5 gap-3">
	{#each TILES as tile (tile.slug)}
		{@const Icon = tile.icon}
		{@const stats = statsByModule[tile.slug] ?? {}}
		{@const stat1 = stats[tile.stat1Key]}
		{@const stat2 = stats[tile.stat2Key]}
		<button
			type="button"
			onclick={() => goto(`/admin-web/${tile.slug}`)}
			class="group flex flex-col gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left transition-all hover:border-[var(--color-terminal)] hover:bg-[var(--color-surface-2)] hover:shadow-[0_0_12px_rgba(74,222,128,0.18)]"
		>
			<div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
				<Icon size={14} strokeWidth={1.8} />
				<span
					class="text-display text-[10.5px] tracking-[0.16em] text-[var(--color-text-primary)]"
				>
					{tile.label.toUpperCase()}
				</span>
			</div>
			<div class="flex gap-3 text-[10.5px]">
				<div class="flex flex-col">
					<span class="text-[var(--color-text-muted)]">{tile.stat1Label}</span>
					<span
						class="text-mono text-[14px] font-semibold tabular-nums text-[var(--color-text-primary)]"
					>
						{typeof stat1 === 'number' ? stat1 : '—'}
					</span>
				</div>
				<div class="flex flex-col">
					<span class="text-[var(--color-text-muted)]">{tile.stat2Label}</span>
					<span
						class="text-mono text-[14px] font-semibold tabular-nums text-[var(--color-text-secondary)]"
					>
						{typeof stat2 === 'number' ? stat2 : '—'}
					</span>
				</div>
			</div>
		</button>
	{/each}
</div>
