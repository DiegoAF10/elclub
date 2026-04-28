<!--
	TabBar — barra de tabs reutilizable para los Shells del Admin Web.

	Cada tab es un slug + label. Click navega via goto al URL `${basePath}/${slug}`.
	Active state computado del prop `active`. Estética matchea el chrome del ERP
	(uppercase display fonts + underline en activo + transición suave).
-->
<script lang="ts">
	import { goto } from '$app/navigation';

	interface Tab {
		slug: string;
		label: string;
		count?: number; // opcional, badge tabular numérico al lado del label
	}

	interface Props {
		basePath: string; // e.g., '/admin-web/stock'
		tabs: Tab[];
		active: string;
	}

	let { basePath, tabs, active }: Props = $props();

	function selectTab(slug: string) {
		void goto(`${basePath}/${slug}`);
	}
</script>

<div
	class="flex h-10 shrink-0 items-center gap-0 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-2"
>
	{#each tabs as tab (tab.slug)}
		{@const isActive = active === tab.slug}
		<button
			type="button"
			class="text-display group relative h-full px-3 text-[10.5px] tracking-[0.14em] transition-colors"
			class:text-[var(--color-text-primary)]={isActive}
			class:text-[var(--color-text-tertiary)]={!isActive}
			class:hover:text-[var(--color-text-primary)]={!isActive}
			onclick={() => selectTab(tab.slug)}
		>
			<span class="flex items-center gap-1.5">
				<span>{tab.label}</span>
				{#if typeof tab.count === 'number' && tab.count > 0}
					<span
						class="text-mono rounded-[3px] bg-[var(--color-surface-3)] px-1 py-0.5 text-[9px] font-semibold tabular-nums normal-case tracking-normal text-[var(--color-text-secondary)]"
					>
						{tab.count}
					</span>
				{/if}
			</span>
			{#if isActive}
				<div
					class="absolute inset-x-3 bottom-0 h-[2px] bg-[var(--color-terminal)]"
				></div>
			{/if}
		</button>
	{/each}
</div>
