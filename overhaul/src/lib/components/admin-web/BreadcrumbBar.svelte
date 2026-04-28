<!--
	BreadcrumbBar — top bar con path navegable: "Admin Web › Module › Tab".

	Cada segmento es clickeable y sube nivel:
		- "Admin Web" → /admin-web (redirect → /home)
		- {Module}    → /admin-web/{section} (redirect → default tab)
		- {Tab}       → current page (no-op)

	Section/tab vienen como props del AdminWebShell (derivados del URL).
	Display names de tabs son maps locales — si un tab no tiene mapping,
	se muestra capitalizado raw.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { ChevronRight } from 'lucide-svelte';

	interface Props {
		section: string;
		tab?: string;
	}
	let { section, tab }: Props = $props();

	const SECTION_LABELS: Record<string, string> = {
		home: 'Home',
		vault: 'Vault',
		stock: 'Stock',
		mystery: 'Mystery',
		site: 'Site',
		sistema: 'Sistema'
	};

	const TAB_LABELS: Record<string, Record<string, string>> = {
		vault: {
			queue: 'Queue',
			publicados: 'Publicados',
			grupos: 'Grupos',
			universo: 'Universo'
		},
		stock: {
			drops: 'Drops',
			calendario: 'Calendario',
			universo: 'Universo'
		},
		mystery: {
			pool: 'Pool',
			calendario: 'Calendario',
			universo: 'Universo'
		},
		site: {
			paginas: 'Páginas',
			branding: 'Branding',
			componentes: 'Componentes',
			comunicacion: 'Comunicación',
			comunidad: 'Comunidad',
			'meta-tracking': 'Meta + Tracking'
		},
		sistema: {
			status: 'Status',
			operaciones: 'Operaciones',
			configuracion: 'Configuración',
			audit: 'Audit'
		}
	};

	function capitalize(s: string): string {
		return s.charAt(0).toUpperCase() + s.slice(1);
	}

	const sectionLabel = $derived(SECTION_LABELS[section] ?? capitalize(section));
	const tabLabel = $derived(tab ? (TAB_LABELS[section]?.[tab] ?? capitalize(tab)) : null);

	function goRoot() {
		void goto('/admin-web');
	}
	function goSection() {
		void goto(`/admin-web/${section}`);
	}
</script>

<div
	class="ui-chrome flex h-10 shrink-0 items-center gap-1 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4 text-[11.5px]"
>
	<button
		type="button"
		class="text-display tracking-[0.14em] text-[var(--color-text-tertiary)] transition-colors hover:text-[var(--color-text-primary)]"
		onclick={goRoot}
	>
		ADMIN WEB
	</button>

	<ChevronRight size={12} class="text-[var(--color-text-muted)]" />

	{#if section !== 'home' || tabLabel}
		<button
			type="button"
			class="font-medium transition-colors"
			class:text-[var(--color-text-primary)]={!tabLabel}
			class:text-[var(--color-text-secondary)]={!!tabLabel}
			class:hover:text-[var(--color-text-primary)]={!!tabLabel}
			onclick={goSection}
		>
			{sectionLabel}
		</button>
	{:else}
		<span class="font-medium text-[var(--color-text-primary)]">{sectionLabel}</span>
	{/if}

	{#if tabLabel}
		<ChevronRight size={12} class="text-[var(--color-text-muted)]" />
		<span class="font-medium text-[var(--color-text-primary)]">{tabLabel}</span>
	{/if}
</div>
