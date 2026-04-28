<!--
	TagsSection — sección de un tag_type con su lista de tags.
	Header: icon + nombre + cardinality badge + count + boton "+ NUEVO".
	Body: grid de TagRow.
-->
<script lang="ts">
	import { Plus } from 'lucide-svelte';
	import TagRow from './TagRow.svelte';

	interface TagItem {
		id: number;
		slug: string;
		display_name: string;
		icon?: string;
		color?: string;
		is_auto_derived: boolean;
		count: number;
	}

	interface Props {
		tagType: {
			id: number;
			slug: string;
			display_name: string;
			icon?: string;
			cardinality: 'one' | 'many' | string;
			description?: string;
		};
		tags: TagItem[];
		onCreate?: (typeId: number) => void;
		onView?: (tagId: number) => void;
		onEdit?: (tagId: number) => void;
	}
	let { tagType, tags, onCreate, onView, onEdit }: Props = $props();
</script>

<div class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]">
	<!-- Header -->
	<div
		class="flex items-center gap-2 border-b border-[var(--color-border)] px-3 py-2"
	>
		{#if tagType.icon}
			<span class="text-[16px] leading-none">{tagType.icon}</span>
		{/if}
		<div class="flex-1">
			<div class="flex items-center gap-2">
				<span
					class="text-display text-[11px] tracking-[0.14em] text-[var(--color-text-primary)]"
				>
					{tagType.display_name.toUpperCase()}
				</span>
				<span
					class="text-mono rounded-[2px] bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[8.5px] uppercase tracking-wide text-[var(--color-text-secondary)]"
				>
					{tagType.cardinality}
				</span>
				<span class="text-mono text-[10px] text-[var(--color-text-muted)]">
					· {tags.length} tags
				</span>
			</div>
			{#if tagType.description}
				<div class="mt-0.5 truncate text-[10.5px] text-[var(--color-text-muted)]">
					{tagType.description}
				</div>
			{/if}
		</div>

		<button
			type="button"
			onclick={() => onCreate?.(tagType.id)}
			class="text-display flex items-center gap-1 rounded-[3px] border border-[var(--color-terminal)]/40 px-2 py-1 text-[9px] tracking-[0.14em] text-[var(--color-terminal)] transition-colors hover:bg-[var(--color-terminal)] hover:text-[var(--color-bg)]"
			title="Crear tag nuevo en este tipo"
		>
			<Plus size={11} strokeWidth={2} />
			NUEVO
		</button>
	</div>

	<!-- Body: grid de tags -->
	<div class="grid grid-cols-1 gap-1.5 p-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
		{#if tags.length === 0}
			<div class="col-span-full p-3 text-center text-[10.5px] text-[var(--color-text-muted)]">
				Sin tags. Crear el primero ↑
			</div>
		{:else}
			{#each tags as tag (tag.id)}
				<TagRow {tag} {onView} {onEdit} />
			{/each}
		{/if}
	</div>
</div>
