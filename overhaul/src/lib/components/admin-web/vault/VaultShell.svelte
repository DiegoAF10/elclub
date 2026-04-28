<!--
	VaultShell — el módulo más profundo del Admin Web R7.
	4 tabs: Queue · Publicados · Grupos · Universo
	Header con count badges reactivos (queue_count, publicados_count, etc).

	Tab routing 100% URL-based: /admin-web/vault/{queue|publicados|grupos|universo}
-->
<script lang="ts">
	import TabBar from '../shared/TabBar.svelte';
	import { Archive } from 'lucide-svelte';
	import { adminWeb } from '$lib/adapter';
	import QueueTab from './tabs/QueueTab.svelte';
	import PublicadosTab from './tabs/PublicadosTab.svelte';
	import GruposTab from './tabs/GruposTab.svelte';
	import UniversoTab from './tabs/UniversoTab.svelte';

	interface Props {
		tab?: string;
	}
	let { tab = 'queue' }: Props = $props();

	// Counts reactivos para los badges del TabBar
	let counts = $state<Record<string, number>>({});

	async function loadCounts() {
		try {
			const stats = (await adminWeb.get_module_stats({ module: 'vault' })) as Record<
				string,
				unknown
			>;
			const num = (k: string): number => (typeof stats[k] === 'number' ? (stats[k] as number) : 0);
			counts = {
				queue: num('queue'),
				publicados: num('publicados')
				// grupos / universo: counts dinámicos, los pueden cargar los tabs
			};
		} catch {
			counts = {};
		}
	}

	$effect(() => {
		void loadCounts();
	});

	const TABS = $derived([
		{ slug: 'queue', label: 'Queue', count: counts.queue },
		{ slug: 'publicados', label: 'Publicados', count: counts.publicados },
		{ slug: 'grupos', label: 'Grupos' },
		{ slug: 'universo', label: 'Universo' }
	]);
</script>

<div class="flex h-full flex-1 flex-col">
	<!-- Header -->
	<div
		class="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4"
	>
		<Archive size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
		<div>
			<div class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]">
				VAULT
			</div>
			<div class="text-[10.5px] text-[var(--color-text-muted)]">
				Catálogo Q435 · pipeline completa de jerseys
			</div>
		</div>
	</div>

	<TabBar basePath="/admin-web/vault" tabs={TABS} active={tab} />

	<!-- Body: switch por tab -->
	<div class="min-h-0 flex-1 overflow-auto">
		{#if tab === 'queue'}
			<QueueTab />
		{:else if tab === 'publicados'}
			<PublicadosTab />
		{:else if tab === 'grupos'}
			<GruposTab />
		{:else if tab === 'universo'}
			<UniversoTab />
		{:else}
			<div class="p-6 text-[12px] text-[var(--color-text-muted)]">Tab desconocido: {tab}</div>
		{/if}
	</div>
</div>
