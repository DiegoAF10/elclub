<!--
	AdminWebCommandPalette — overlay ⌘K para navegación rápida + acciones.

	NOTA T7.1: el plan original pedía fuse.js para fuzzy search. R7.0 usa
	substring match simple (toLowerCase + includes). Suficiente para los ~15
	items canonical del Admin Web; cuando crezca a >50 podemos sumar fuse.js.

	Items:
	  - Navigation: ir a Home/Vault/Stock/Mystery/Site/Sistema + tabs
	  - Action: Crear tag, Detect events, Backup now (futuro)

	Keyboard:
	  - ⌘K / Ctrl+K abre/cierra
	  - Esc cierra
	  - ↑↓ navega lista
	  - Enter ejecuta item activo
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { adminWeb } from '$lib/adapter';
	import { Search, ArrowRight, Zap } from 'lucide-svelte';

	interface Props {
		open: boolean;
		onClose: () => void;
	}
	let { open = $bindable(false), onClose }: Props = $props();

	interface PaletteItem {
		id: string;
		category: 'navigation' | 'action';
		label: string;
		description?: string;
		shortcut?: string;
		searchTerms?: string[];
		execute: () => void | Promise<void>;
	}

	function makeItems(close: () => void): PaletteItem[] {
		const nav = (target: string, label: string, terms?: string[]): PaletteItem => ({
			id: `nav-${target}`,
			category: 'navigation',
			label,
			description: target,
			searchTerms: terms,
			execute: () => {
				void goto(target);
				close();
			}
		});

		return [
			nav('/admin-web/home', 'Ir a Home', ['inicio', 'dashboard', 'kpis', 'gh']),
			nav('/admin-web/vault/queue', 'Vault › Queue', ['audit', 'pending', 'gv', 'gq']),
			nav('/admin-web/vault/publicados', 'Vault › Publicados', ['live', 'cards', 'gp']),
			nav('/admin-web/vault/grupos', 'Vault › Grupos (tags)', ['tags', 'tipos', 'gg']),
			nav('/admin-web/vault/universo', 'Vault › Universo', ['todos', 'tabla', 'gu']),
			nav('/admin-web/stock/drops', 'Stock › Drops', ['gs', 'garantizadas']),
			nav('/admin-web/stock/calendario', 'Stock › Calendario', ['fechas']),
			nav('/admin-web/mystery/pool', 'Mystery › Pool', ['gm', 'sorpresa']),
			nav('/admin-web/site/paginas', 'Site › Páginas', ['gw', 'cms']),
			nav('/admin-web/site/branding', 'Site › Branding'),
			nav('/admin-web/sistema/status', 'Sistema › Status', ['gc', 'health', 'monitoring']),
			nav('/admin-web/sistema/operaciones', 'Sistema › Operaciones', ['ops', 'scrap', 'deploy']),
			nav('/admin-web/sistema/audit', 'Sistema › Audit log', ['log', 'history']),
			{
				id: 'action-detect-events',
				category: 'action',
				label: 'Detectar eventos ahora',
				description: 'Corre el detector cron manualmente',
				searchTerms: ['inbox', 'sync'],
				execute: async () => {
					try {
						await adminWeb.detect_events_now();
					} finally {
						close();
					}
				}
			},
			{
				id: 'action-backup-db',
				category: 'action',
				label: 'Crear backup DB',
				description: 'Snapshot manual del SQLite',
				searchTerms: ['snapshot', 'export'],
				execute: async () => {
					try {
						await adminWeb.create_backup_now({ type: 'db' });
					} finally {
						close();
					}
				}
			}
		];
	}

	const items = $derived(makeItems(onClose));

	let search = $state('');
	let activeIndex = $state(0);

	const filtered = $derived.by(() => {
		const q = search.trim().toLowerCase();
		if (!q) return items;
		return items.filter((item) => {
			const terms = [
				item.label.toLowerCase(),
				item.description?.toLowerCase() ?? '',
				...(item.searchTerms?.map((t) => t.toLowerCase()) ?? [])
			];
			return terms.some((t) => t.includes(q));
		});
	});

	$effect(() => {
		// Reset cursor cuando cambia el search
		const _ = search;
		activeIndex = 0;
	});

	function execute(idx: number) {
		const item = filtered[idx];
		if (!item) return;
		void item.execute();
	}

	function handleKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			activeIndex = (activeIndex + 1) % Math.max(1, filtered.length);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			activeIndex = (activeIndex - 1 + filtered.length) % Math.max(1, filtered.length);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			execute(activeIndex);
		}
	}

	function handleBackdrop(e: MouseEvent) {
		if (e.target === e.currentTarget) onClose();
	}

	let inputEl = $state<HTMLInputElement | null>(null);
	$effect(() => {
		if (open && inputEl) {
			search = '';
			activeIndex = 0;
			inputEl.focus();
		}
	});
</script>

<svelte:window onkeydown={handleKey} />

{#if open}
	<div
		class="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 p-4 pt-[15vh] backdrop-blur-md"
		onclick={handleBackdrop}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<div
			class="ui-chrome w-full max-w-xl overflow-hidden rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] shadow-2xl"
		>
			<div
				class="flex items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5"
			>
				<Search size={14} strokeWidth={1.8} class="text-[var(--color-text-tertiary)]" />
				<input
					bind:this={inputEl}
					bind:value={search}
					type="text"
					placeholder="Buscar comando o navegar…"
					class="text-mono flex-1 bg-transparent text-[13px] text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]"
				/>
				<kbd
					class="text-mono rounded-[3px] bg-[var(--color-surface-3)] px-1.5 py-0.5 text-[9px] text-[var(--color-text-tertiary)]"
				>
					ESC
				</kbd>
			</div>

			<div class="max-h-[50vh] overflow-y-auto">
				{#if filtered.length === 0}
					<div class="p-6 text-center text-[12px] text-[var(--color-text-muted)]">
						Sin resultados para "{search}"
					</div>
				{:else}
					{#each filtered as item, i (item.id)}
						{@const isActive = activeIndex === i}
						<button
							type="button"
							onclick={() => execute(i)}
							onmouseenter={() => (activeIndex = i)}
							class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-[12.5px] transition-colors"
							class:bg-[var(--color-surface-2)]={isActive}
							class:text-[var(--color-text-primary)]={isActive}
							class:text-[var(--color-text-secondary)]={!isActive}
						>
							{#if item.category === 'navigation'}
								<ArrowRight
									size={12}
									strokeWidth={1.8}
									class={isActive
										? 'text-[var(--color-terminal)]'
										: 'text-[var(--color-text-muted)]'}
								/>
							{:else}
								<Zap
									size={12}
									strokeWidth={1.8}
									class={isActive
										? 'text-[var(--color-warning)]'
										: 'text-[var(--color-text-muted)]'}
								/>
							{/if}
							<span class="flex-1">{item.label}</span>
							{#if item.description}
								<span
									class="text-mono shrink-0 text-[10px] text-[var(--color-text-muted)]"
								>
									{item.description}
								</span>
							{/if}
						</button>
					{/each}
				{/if}
			</div>

			<div
				class="flex items-center justify-between border-t border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[10px] text-[var(--color-text-muted)]"
			>
				<span class="text-mono">
					<kbd class="rounded-[2px] bg-[var(--color-surface-3)] px-1">↑↓</kbd> navegar
					<kbd class="ml-2 rounded-[2px] bg-[var(--color-surface-3)] px-1">↵</kbd> ejecutar
				</span>
				<span class="text-mono">
					{filtered.length} de {items.length}
				</span>
			</div>
		</div>
	</div>
{/if}
