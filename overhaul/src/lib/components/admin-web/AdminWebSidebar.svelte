<!--
	AdminWebSidebar — sidebar interno del módulo Admin Web (200px).

	Renderiza 6 nav items: Home + 5 sub-módulos (vault/stock/mystery/site/sistema).
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
	import { Home, Archive, Package, Sparkles, Globe, Server } from 'lucide-svelte';
	import { adminWeb } from '$lib/adapter';
	import type { ModuleSlug, InboxEvent, EventSeverity } from '$lib/adapter';

	interface Props {
		section: string;
	}
	let { section }: Props = $props();

	interface NavItem {
		id: string; // 'home' | 'vault' | 'stock' | 'mystery' | 'site' | 'sistema'
		label: string;
		icon: typeof Home;
	}

	const ITEMS: NavItem[] = [
		{ id: 'home', label: 'Home', icon: Home },
		{ id: 'vault', label: 'Vault', icon: Archive },
		{ id: 'stock', label: 'Stock', icon: Package },
		{ id: 'mystery', label: 'Mystery', icon: Sparkles },
		{ id: 'site', label: 'Site', icon: Globe },
		{ id: 'sistema', label: 'Sistema', icon: Server }
	];

	// Inbox events agrupados por módulo. Critical+important+info se acumulan
	// en `total`; críticos se reportan aparte para destacar visualmente.
	interface ModuleCounts {
		total: number;
		critical: number;
	}

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

	$effect(() => {
		void loadCounts();
	});

	function navigate(id: string) {
		void goto(`/admin-web/${id}`);
	}
</script>

<aside
	class="ui-chrome flex w-[200px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-1)]"
>
	<!-- Brand strip -->
	<div class="flex h-12 items-center border-b border-[var(--color-border)] px-4">
		<span class="text-display text-[11px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>ADMIN WEB</span
		>
	</div>

	<nav class="flex-1 overflow-y-auto px-2 py-3">
		{#each ITEMS as item (item.id)}
			{@const Icon = item.icon}
			{@const counts = item.id === 'home' ? null : countsByModule[item.id as ModuleSlug]}
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
		{/each}
	</nav>

	<!-- Footer hint -->
	<div class="border-t border-[var(--color-border)] px-3 py-2">
		<div class="text-display text-[8.5px] tracking-[0.14em] text-[var(--color-text-muted)]">
			⌘K command palette
		</div>
	</div>
</aside>
