<!--
	AdminWebSidebar — sidebar interno del módulo Admin Web (200px).

	Renderiza nav items en 3 grupos (post sidebar reorg 2026-04-28):
	  - Main: Home
	  - Workflow: Audit · Mundial 2026 (movidos del sidebar global)
	  - Data: Vault · Inventario (ex-Stock) · Mystery · Site · Sistema
	Active state según el `section` prop (derivado del URL en AdminWebShell).
	Click navega via goto('/admin-web/{id}') — el +page.svelte de cada section
	maneja el redirect al default tab.

	Badges: count de inbox_events activos por módulo. Se cargan on-mount via
	adminWeb.list_inbox_events() y se agrupan por module client-side. En browser
	mode el adapter retorna [] así que badges quedan en 0 sin crash.

	Estética matchea el Sidebar global del ERP (uppercase display fonts +
	monospace para badges + paleta retro gaming).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { Home, Search, Trophy, Archive, Package, Sparkles, Globe, Server, ArrowLeft } from 'lucide-svelte';
	import { adminWeb } from '$lib/adapter';
	import type { ModuleSlug, InboxEvent, EventSeverity } from '$lib/adapter';

	interface Props {
		section: string;
	}
	let { section }: Props = $props();

	interface NavItem {
		id: string;
		label: string;
		icon: typeof Home;
		section?: 'main' | 'workflow' | 'data';
	}

	// Sidebar reorg 2026-04-28 (Iteración Continuous · D1=c · D4=Dashboard queda · Stock→Inventario):
	//   Workflow group absorbió Audit + Mundial 2026 (movidos del sidebar global).
	//   Vault > Queue/Publicados internas siguen siendo el flujo natural · NO duplicar acá.
	//   Inventario reemplaza Stock (cascarón inicial · funcionalidad por definir).
	const ITEMS: NavItem[] = [
		{ id: 'home', label: 'Home', icon: Home, section: 'main' },
		{ id: 'audit', label: 'Audit', icon: Search, section: 'workflow' },
		{ id: 'mundial', label: 'Mundial 2026', icon: Trophy, section: 'workflow' },
		{ id: 'vault', label: 'Vault', icon: Archive, section: 'data' },
		{ id: 'inventario', label: 'Inventario', icon: Package, section: 'data' },
		{ id: 'mystery', label: 'Mystery', icon: Sparkles, section: 'data' },
		{ id: 'site', label: 'Site', icon: Globe, section: 'data' },
		{ id: 'sistema', label: 'Sistema', icon: Server, section: 'data' }
	];

	const mainItems = ITEMS.filter((i) => i.section === 'main' || !i.section);
	const workflowItems = ITEMS.filter((i) => i.section === 'workflow');
	const dataItems = ITEMS.filter((i) => i.section === 'data');

	// Inbox events agrupados por módulo. Critical+important+info se acumulan
	// en `total`; críticos se reportan aparte para destacar visualmente.
	interface ModuleCounts {
		total: number;
		critical: number;
	}

	// `inventario` reemplazó `stock` como destino del módulo · si el detector de
	// eventos sigue emitiendo `module='stock'` por compat con R7, los mapeamos a
	// inventario en este sidebar. Vez que ADM-R7.1+ corra · podrá emitir module=
	// 'inventario' nativamente.
	let countsByModule = $state<Record<ModuleSlug, ModuleCounts>>({
		vault: { total: 0, critical: 0 },
		stock: { total: 0, critical: 0 },
		mystery: { total: 0, critical: 0 },
		site: { total: 0, critical: 0 },
		sistema: { total: 0, critical: 0 }
	});

	async function loadCounts() {
		try {
			const events = await adminWeb.list_inbox_events({});
			const next: Record<ModuleSlug, ModuleCounts> = {
				vault: { total: 0, critical: 0 },
				stock: { total: 0, critical: 0 },
				mystery: { total: 0, critical: 0 },
				site: { total: 0, critical: 0 },
				sistema: { total: 0, critical: 0 }
			};
			for (const ev of events as InboxEvent[]) {
				if (ev.dismissed_at || ev.resolved_at) continue;
				const target = next[ev.module];
				if (!target) continue;
				target.total += 1;
				if ((ev.severity as EventSeverity) === 'critical') target.critical += 1;
			}
			countsByModule = next;
		} catch {
			// Silencioso — adapter en browser puede no responder; mantener counts en 0
		}
	}

	// Resuelve counts para un item del sidebar, mapeando los nav-ids nuevos
	// (audit, mundial, inventario) a su origen en el detector de eventos.
	function countsForItem(id: string): ModuleCounts | null {
		if (id === 'home' || id === 'audit' || id === 'mundial') return null;
		if (id === 'inventario') return countsByModule.stock;
		const moduleId = id as ModuleSlug;
		return countsByModule[moduleId] ?? null;
	}

	$effect(() => {
		// Initial load + auto-refresh cada 60s. El detector real corre via
		// InboxFeed on-mount (HomeView), así que dejamos un delay corto en el
		// primer refresh para capturar los events que el detector recién creó.
		void loadCounts();
		const initial = setTimeout(() => void loadCounts(), 1500);
		const interval = setInterval(() => void loadCounts(), 60_000);
		return () => {
			clearTimeout(initial);
			clearInterval(interval);
		};
	});

	function navigate(id: string) {
		void goto(`/admin-web/${id}`);
	}
</script>

<aside
	class="ui-chrome flex w-[200px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-1)]"
>
	<!-- Volver al ERP raíz (Audit, Comercial, Finanzas, etc) -->
	<button
		type="button"
		onclick={() => goto('/')}
		class="text-display flex h-9 shrink-0 items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 text-[10px] tracking-[0.14em] text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
		title="Volver al ERP principal (Audit, Comercial, Finanzas, etc)"
	>
		<ArrowLeft size={11} strokeWidth={1.8} />
		VOLVER AL ERP
	</button>

	<!-- Brand strip -->
	<div class="flex h-12 items-center border-b border-[var(--color-border)] px-4">
		<span class="text-display text-[11px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>ADMIN WEB</span
		>
	</div>

	{#snippet navButton(item: NavItem)}
		{@const Icon = item.icon}
		{@const counts = countsForItem(item.id)}
		{@const isActive = section === item.id}
		<button
			type="button"
			class="group mb-0.5 flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[12.5px] transition-all"
			class:bg-[var(--color-surface-2)]={isActive}
			class:text-[var(--color-text-primary)]={isActive}
			class:text-[var(--color-text-secondary)]={!isActive}
			class:hover:bg-[var(--color-surface-2)]={!isActive}
			class:hover:text-[var(--color-text-primary)]={!isActive}
			onclick={() => navigate(item.id)}
		>
			<span class="flex items-center gap-2.5">
				<Icon size={14} strokeWidth={1.8} />
				<span class="font-medium">{item.label}</span>
			</span>
			{#if counts && counts.total > 0}
				<span
					class="text-mono rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-semibold tabular-nums"
					class:bg-[var(--color-surface-3)]={counts.critical === 0}
					class:text-[var(--color-terminal)]={counts.critical === 0}
					style:background={counts.critical > 0 ? 'rgba(244, 63, 94, 0.18)' : undefined}
					style:color={counts.critical > 0 ? 'var(--color-danger)' : undefined}
				>
					{counts.total}
				</span>
			{/if}
		</button>
	{/snippet}

	<nav class="flex-1 overflow-y-auto px-2 py-3">
		<div class="mb-3">
			{#each mainItems as item (item.id)}
				{@render navButton(item)}
			{/each}
		</div>

		<div class="mb-3">
			<div class="text-display mb-1.5 px-2 text-[9.5px] text-[var(--color-text-tertiary)]">
				Workflow
			</div>
			{#each workflowItems as item (item.id)}
				{@render navButton(item)}
			{/each}
		</div>

		<div>
			<div class="text-display mb-1.5 px-2 text-[9.5px] text-[var(--color-text-tertiary)]">
				Data
			</div>
			{#each dataItems as item (item.id)}
				{@render navButton(item)}
			{/each}
		</div>
	</nav>

	<!-- Footer hint -->
	<div class="border-t border-[var(--color-border)] px-3 py-2">
		<div class="text-display text-[8.5px] tracking-[0.14em] text-[var(--color-text-muted)]">
			⌘K command palette
		</div>
	</div>
</aside>
