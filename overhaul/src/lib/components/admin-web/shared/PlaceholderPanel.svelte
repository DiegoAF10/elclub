<!--
	PlaceholderPanel — body de cascarón. Muestra el nombre del tab + nota de
	"profundizar en R7.X" para que Diego pueda navegar el módulo aunque no
	tenga lógica funcional todavía. Reemplazar por componente real cuando
	T7.X profundice cada módulo.
-->
<script lang="ts">
	interface Props {
		title: string; // e.g., 'STOCK · DROPS'
		future?: string; // e.g., 'R7.1' o 'R7.2'
		description?: string;
	}
	let { title, future, description }: Props = $props();
</script>

<div class="flex flex-1 items-center justify-center p-8">
	<div class="max-w-md text-center">
		<div
			class="text-display mb-3 text-[18px] tracking-[0.16em] text-[var(--color-text-primary)]"
		>
			{title}
		</div>
		{#if description}
			<p class="text-[12.5px] leading-relaxed text-[var(--color-text-secondary)]">
				{description}
			</p>
		{/if}
		{#if future}
			<div
				class="text-mono mt-4 inline-block rounded-[3px] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] tracking-wide text-[var(--color-text-tertiary)]"
			>
				PROFUNDIDAD EN {future}
			</div>
		{/if}
	</div>
</div>
