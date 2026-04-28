<!--
	TagRow — display unitario de un tag dentro de TagsSection.
	icon + name + count + acciones (VER, EDITAR).
-->
<script lang="ts">
	import { Eye, Settings2, Bot } from 'lucide-svelte';

	interface Props {
		tag: {
			id: number;
			slug: string;
			display_name: string;
			icon?: string;
			color?: string;
			is_auto_derived: boolean;
			count: number;
		};
		onView?: (tagId: number) => void;
		onEdit?: (tagId: number) => void;
	}
	let { tag, onView, onEdit }: Props = $props();
</script>

<div
	class="group flex items-center gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[12px] transition-colors hover:border-[var(--color-text-tertiary)]"
>
	{#if tag.icon}
		<span class="text-[14px] leading-none">{tag.icon}</span>
	{/if}
	<span
		class="flex-1 truncate text-[var(--color-text-primary)]"
		style:color={tag.color}
		title={tag.slug}
	>
		{tag.display_name}
	</span>

	{#if tag.is_auto_derived}
		<span
			class="text-mono inline-flex items-center gap-0.5 rounded-[2px] bg-[var(--color-surface-3)] px-1 py-0.5 text-[8.5px] uppercase tracking-wide text-[var(--color-text-secondary)]"
			title="Auto-derived rule"
		>
			<Bot size={9} strokeWidth={2} />
			AUTO
		</span>
	{/if}

	<span
		class="text-mono shrink-0 rounded-[2px] bg-[var(--color-surface-3)] px-1.5 py-0.5 text-[10px] tabular-nums text-[var(--color-text-secondary)]"
	>
		{tag.count}
	</span>

	<div class="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
		<button
			type="button"
			onclick={() => onView?.(tag.id)}
			title="Ver jerseys con este tag"
			class="rounded-[2px] p-1 text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
		>
			<Eye size={11} strokeWidth={1.8} />
		</button>
		<button
			type="button"
			onclick={() => onEdit?.(tag.id)}
			title="Editar tag"
			class="rounded-[2px] p-1 text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
		>
			<Settings2 size={11} strokeWidth={1.8} />
		</button>
	</div>
</div>
