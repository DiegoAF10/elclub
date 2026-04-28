<!--
	GruposTab — sistema de tags del Vault. Renderiza una sección por tag_type
	con sus tags. CRUD via TagEditModal. Drill jerseys via TagDrillModal.
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import type { TagType, Tag } from '$lib/adapter';
	import TagsSection from '../TagsSection.svelte';
	import TagEditModal from '../TagEditModal.svelte';
	import TagDrillModal from '../TagDrillModal.svelte';

	let tagTypes = $state<TagType[]>([]);
	let tags = $state<Tag[]>([]);
	let loading = $state(true);

	type EditMode =
		| { kind: 'create'; type_id: number }
		| { kind: 'edit'; tag: { id: number; display_name: string; icon?: string; color?: string } };
	let editMode = $state<EditMode | null>(null);
	let drillTag = $state<{ id: number; display_name: string; icon?: string } | null>(null);

	async function load() {
		loading = true;
		try {
			const [types, allTags] = await Promise.all([
				adminWeb.list_tag_types(),
				adminWeb.list_tags()
			]);
			tagTypes = types as TagType[];
			tags = allTags as Tag[];
		} catch {
			tagTypes = [];
			tags = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void load();
	});

	function tagsForType(typeId: number) {
		return tags
			.filter((t) => t.type_id === typeId)
			.map((t) => ({
				id: t.id,
				slug: t.slug,
				display_name: t.display_name,
				icon: t.icon,
				color: t.color,
				is_auto_derived: t.is_auto_derived,
				count: (t as unknown as { count?: number }).count ?? 0
			}));
	}

	function handleCreate(typeId: number) {
		editMode = { kind: 'create', type_id: typeId };
	}

	function handleEdit(tagId: number) {
		const t = tags.find((x) => x.id === tagId);
		if (!t) return;
		editMode = { kind: 'edit', tag: { id: t.id, display_name: t.display_name, icon: t.icon, color: t.color } };
	}

	function handleView(tagId: number) {
		const t = tags.find((x) => x.id === tagId);
		if (!t) return;
		drillTag = { id: t.id, display_name: t.display_name, icon: t.icon };
	}
</script>

<div class="flex h-full flex-col p-4">
	<div class="mb-3 flex items-baseline justify-between">
		<div>
			<h2
				class="text-display text-[16px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				GRUPOS
			</h2>
			<p class="mt-0.5 text-[11px] text-[var(--color-text-secondary)]">
				Sistema de tags many-to-many · 11 tipos × N tags · cardinality enforced
			</p>
		</div>
		{#if !loading}
			<div class="text-mono text-[10.5px] text-[var(--color-text-muted)]">
				{tagTypes.length} tipos · {tags.length} tags
			</div>
		{/if}
	</div>

	<div class="min-h-0 flex-1 space-y-3 overflow-y-auto pb-4">
		{#if loading}
			{#each Array(4) as _, i (i)}
				<div
					class="h-32 animate-pulse rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
				></div>
			{/each}
		{:else if tagTypes.length === 0}
			<div class="p-8 text-center text-[12px] text-[var(--color-text-muted)]">
				Ningún tag_type cargado. Verificar que seed_admin_web.py corrió (T1.2).
			</div>
		{:else}
			{#each tagTypes as type (type.id)}
				<TagsSection
					tagType={{
						id: type.id,
						slug: type.slug,
						display_name: type.display_name,
						icon: type.icon,
						cardinality: type.cardinality,
						description: type.description
					}}
					tags={tagsForType(type.id)}
					onCreate={handleCreate}
					onView={handleView}
					onEdit={handleEdit}
				/>
			{/each}
		{/if}
	</div>
</div>

{#if editMode}
	<TagEditModal
		mode={editMode}
		onClose={() => (editMode = null)}
		onSuccess={() => {
			editMode = null;
			void load();
		}}
	/>
{/if}

{#if drillTag}
	<TagDrillModal tag={drillTag} onClose={() => (drillTag = null)} />
{/if}
