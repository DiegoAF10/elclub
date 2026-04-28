<script lang="ts">
	import {
		Inbox,
		Search,
		Trophy,
		Rocket,
		BarChart3,
		Package,
		DollarSign,
		Truck,
		Ship,
		LineChart,
		Command,
		Upload,
		Loader2,
		CheckCircle2,
		AlertTriangle,
		RefreshCw,
		Download
	} from 'lucide-svelte';
	import { adapter, NotAvailableInBrowser, isTauri } from '$lib/adapter';
	import type { GitStatusInfo } from '$lib/adapter';
	import { invalidateAll } from '$app/navigation';

	interface NavItem {
		id: string;
		label: string;
		icon: typeof Inbox;
		badge?: number | string;
		section?: string;
	}

	interface Props {
		active?: string;
		onSelect?: (id: string) => void;
		onPushResult?: (msg: string) => void;
		criticalEventsCount?: number;
	}

	let { active = 'audit', onSelect = () => {}, onPushResult = () => {}, criticalEventsCount = 0 }: Props = $props();

	// Git status polling — reads on mount + refresh post-push
	let gitStatus = $state<GitStatusInfo | null>(null);
	let pushState = $state<'idle' | 'busy' | 'success' | 'error'>('idle');
	let gitAvailable = $state(false);

	// Sync state
	let syncState = $state<'idle' | 'busy' | 'success'>('idle');

	// Version (solo si Tauri)
	let appVersion = $state<string | null>(null);
	$effect(() => {
		if (!isTauri()) return;
		void (async () => {
			try {
				const { getVersion } = await import('@tauri-apps/api/app');
				appVersion = await getVersion();
			} catch {
				appVersion = null;
			}
		})();
	});

	async function handleSync() {
		if (syncState === 'busy') return;
		syncState = 'busy';
		try {
			await adapter.invalidateCache();
			await invalidateAll();
			syncState = 'success';
			onPushResult('✓ Datos sincronizados desde catalog.json + SQLite');
			setTimeout(() => (syncState = 'idle'), 2000);
			void refreshGitStatus();
		} catch (err) {
			syncState = 'idle';
			onPushResult(`Sync falló: ${err instanceof Error ? err.message : err}`);
		}
	}

	async function handleOpenUpdates() {
		try {
			await adapter.openMsiFolder();
			onPushResult('Carpeta de updates abierta — doble-click al .msi más reciente');
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onPushResult('Updates: requiere el .exe');
			} else {
				onPushResult(`Error abriendo carpeta: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	async function refreshGitStatus() {
		try {
			gitStatus = await adapter.gitStatus();
			gitAvailable = true;
		} catch (err) {
			gitAvailable = !(err instanceof NotAvailableInBrowser);
			gitStatus = null;
		}
	}

	$effect(() => {
		// Solo initial load — sin polling automático para evitar mini-freezes
		// (cada git status spawnea 2 subprocess). Refresh on-demand: post-push o
		// post-sync refrescan explícitamente.
		void refreshGitStatus();
	});

	async function handlePush() {
		if (pushState === 'busy') return;
		pushState = 'busy';
		try {
			const result = await adapter.commitAndPush('');
			if (result.nothing_to_commit) {
				pushState = 'idle';
				onPushResult('✓ Vault al día — nada que commit');
			} else if (result.pushed) {
				pushState = 'success';
				onPushResult(`✓ Push ${result.commit_sha ?? ''} → vault live en ~30s`);
				setTimeout(() => (pushState = 'idle'), 2500);
			} else {
				pushState = 'error';
				onPushResult(`⚠ Commit ${result.commit_sha ?? ''} guardado, push falló: ${result.error ?? ''}`);
				setTimeout(() => (pushState = 'idle'), 4000);
			}
			void refreshGitStatus();
		} catch (err) {
			pushState = 'error';
			if (err instanceof NotAvailableInBrowser) {
				onPushResult('Push: requiere el .exe — browser mode no tiene acceso a git');
			} else {
				onPushResult(`Push falló: ${err instanceof Error ? err.message : err}`);
			}
			setTimeout(() => (pushState = 'idle'), 4000);
		}
	}

	const ITEMS: NavItem[] = [
		{ id: 'queue', label: 'Queue', icon: Inbox, section: 'workflow' },
		{ id: 'audit', label: 'Audit', icon: Search, section: 'workflow' },
		{
			id: 'mundial',
			label: 'Mundial 2026',
			icon: Trophy,
			section: 'workflow'
			// TODO: badge dinámico "N/96" calculando families Mundial 2026 verified
		},
		{ id: 'publicados', label: 'Publicados', icon: Rocket, section: 'workflow' },
		{ id: 'dashboard', label: 'Dashboard', icon: BarChart3, section: 'data' },
		{ id: 'inventory', label: 'Inventario', icon: Package, section: 'data' },
		{ id: 'comercial', label: 'Comercial', icon: DollarSign, section: 'data' },
		{ id: 'importaciones', label: 'Importaciones', icon: Ship, section: 'data' },
		{ id: 'finanzas', label: 'Finanzas', icon: LineChart, section: 'data' },
		{ id: 'orders', label: 'Órdenes', icon: Truck, section: 'data' }
	];

	const workflow = ITEMS.filter((i) => i.section === 'workflow');
	const data = ITEMS.filter((i) => i.section === 'data');
</script>

<aside
	class="ui-chrome flex h-full w-[200px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-1)]"
>
	<!-- Brand / logo -->
	<div class="flex h-14 items-center gap-2.5 border-b border-[var(--color-border)] px-4">
		<img src="/logo-icon.svg" alt="El Club" class="h-7 w-7 opacity-90" />
		<div class="flex flex-col leading-tight">
			<span class="text-display text-[11px] text-[var(--color-text-primary)]"
				>EL CLUB</span
			>
			<span
				class="text-[9px] font-medium uppercase tracking-[0.14em] text-[var(--color-text-tertiary)]"
			>
				ERP{#if appVersion}<span class="text-mono ml-1 text-[var(--color-text-muted)]">v{appVersion}</span>{/if}
			</span>
		</div>
	</div>

	<!-- Nav -->
	<nav class="flex-1 overflow-y-auto px-2 py-3">
		<div class="mb-4">
			<div class="text-display mb-1.5 px-2 text-[9.5px] text-[var(--color-text-tertiary)]">
				Workflow
			</div>
			{#each workflow as item (item.id)}
				{@const Icon = item.icon}
				<button
					type="button"
					class="group flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[12.5px] transition-all"
					class:bg-[var(--color-surface-2)]={active === item.id}
					class:text-[var(--color-text-primary)]={active === item.id}
					class:text-[var(--color-text-secondary)]={active !== item.id}
					class:hover:bg-[var(--color-surface-2)]={active !== item.id}
					class:hover:text-[var(--color-text-primary)]={active !== item.id}
					onclick={() => onSelect(item.id)}
				>
					<span class="flex items-center gap-2.5">
						<Icon size={14} strokeWidth={1.8} />
						<span class="font-medium">{item.label}</span>
					</span>
					{#if item.badge}
						<span
							class="text-mono rounded-[3px] bg-[var(--color-surface-3)] px-1.5 py-0.5 text-[9.5px] font-semibold text-[var(--color-terminal)] tabular-nums"
						>
							{item.badge}
						</span>
					{/if}
				</button>
			{/each}
		</div>

		<div>
			<div class="text-display mb-1.5 px-2 text-[9.5px] text-[var(--color-text-tertiary)]">
				Data
			</div>
			{#each data as item (item.id)}
				{@const Icon = item.icon}
				<button
					type="button"
					class="group flex w-full items-center gap-2.5 rounded-[3px] px-2 py-1.5 text-[12.5px] transition-all"
					class:bg-[var(--color-surface-2)]={active === item.id}
					class:text-[var(--color-text-primary)]={active === item.id}
					class:text-[var(--color-text-secondary)]={active !== item.id}
					class:hover:bg-[var(--color-surface-2)]={active !== item.id}
					class:hover:text-[var(--color-text-primary)]={active !== item.id}
					onclick={() => onSelect(item.id)}
				>
					<Icon size={14} strokeWidth={1.8} />
					<span class="font-medium">{item.label}</span>
					{#if item.id === 'comercial' && criticalEventsCount > 0}
						<span
							class="ml-auto rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-semibold"
							style="background: rgba(244, 63, 94, 0.18); color: var(--color-danger);"
						>
							{criticalEventsCount}
						</span>
					{/if}
				</button>
			{/each}
		</div>
	</nav>

	<!-- Bottom chrome -->
	<div class="border-t border-[var(--color-border)] p-2">
		<!-- Sync data button — re-lee catalog.json + SQLite -->
		<button
			type="button"
			onclick={handleSync}
			disabled={syncState === 'busy'}
			class="group mb-1 flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[11.5px] transition-all disabled:opacity-50"
			class:text-[var(--color-text-secondary)]={syncState !== 'success'}
			class:text-[var(--color-live)]={syncState === 'success'}
			class:hover:bg-[var(--color-surface-2)]={syncState === 'idle'}
			title="Re-leer catalog.json + SQLite (útil tras scrape externo)"
		>
			<span class="flex items-center gap-2">
				{#if syncState === 'busy'}
					<RefreshCw size={13} strokeWidth={1.8} class="animate-spin" />
				{:else if syncState === 'success'}
					<CheckCircle2 size={13} strokeWidth={1.8} />
				{:else}
					<RefreshCw size={13} strokeWidth={1.8} />
				{/if}
				<span class="font-medium">
					{#if syncState === 'busy'}Sincronizando…{:else if syncState === 'success'}Sincronizado{:else}Sincronizar datos{/if}
				</span>
			</span>
		</button>

		<!-- Updates button — abre carpeta con .msi más recientes -->
		{#if isTauri()}
			<button
				type="button"
				onclick={handleOpenUpdates}
				class="mb-1 flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
				title="Abre la carpeta con .msi nuevos — doble-click al más reciente para actualizar"
			>
				<span class="flex items-center gap-2">
					<Download size={13} strokeWidth={1.8} />
					<span class="font-medium">Buscar updates</span>
				</span>
			</button>
		{/if}

		{#if gitAvailable}
			{@const dirty = gitStatus?.catalog_changed || (gitStatus?.ahead ?? 0) > 0}
			<button
				type="button"
				onclick={handlePush}
				disabled={pushState === 'busy' || !dirty}
				class="group mb-1 flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[11.5px] transition-all disabled:opacity-50"
				class:text-[var(--color-text-secondary)]={pushState === 'idle' && !dirty}
				class:text-[var(--color-accent)]={dirty && pushState === 'idle'}
				class:text-[var(--color-live)]={pushState === 'success'}
				class:text-[var(--color-flagged)]={pushState === 'error'}
				class:hover:bg-[var(--color-surface-2)]={pushState === 'idle' && dirty}
				title={dirty
					? 'Publicar cambios pendientes al vault (GitHub Pages)'
					: 'Nada para publicar — todo sincronizado'}
			>
				<span class="flex items-center gap-2">
					{#if pushState === 'busy'}
						<Loader2 size={13} strokeWidth={1.8} class="animate-spin" />
					{:else if pushState === 'success'}
						<CheckCircle2 size={13} strokeWidth={1.8} />
					{:else if pushState === 'error'}
						<AlertTriangle size={13} strokeWidth={1.8} />
					{:else}
						<Upload size={13} strokeWidth={1.8} />
					{/if}
					<span class="font-medium">
						{#if pushState === 'busy'}Pushing…{:else if pushState === 'success'}Pushed{:else if pushState === 'error'}Error{:else}Push vault{/if}
					</span>
				</span>
				{#if dirty && pushState === 'idle'}
					<span
						class="text-mono rounded-[3px] bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[9.5px] font-semibold text-[var(--color-accent)] tabular-nums"
					>
						{(gitStatus?.ahead ?? 0) > 0 ? `↑${gitStatus?.ahead}` : '●'}
					</span>
				{:else if !dirty && pushState === 'idle'}
					<CheckCircle2 size={11} strokeWidth={2} class="text-[var(--color-live)] opacity-60" />
				{/if}
			</button>
		{/if}
		<button
			type="button"
			class="flex w-full items-center justify-between rounded-[3px] px-2 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
		>
			<span class="flex items-center gap-2">
				<Command size={13} strokeWidth={1.8} />
				<span class="font-medium">Command</span>
			</span>
			<kbd>⌘K</kbd>
		</button>
	</div>
</aside>
