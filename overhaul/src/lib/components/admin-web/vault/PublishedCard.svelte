<!--
	PublishedCard — tarjeta para una jersey PUBLISHED en Vault > Publicados.
	Layout vertical: thumbnail grande arriba + badges + meta + quick actions.
-->
<script lang="ts">
	import { AlertCircle, Calendar, Star, Rocket, Sparkles, MoreHorizontal, Trash2 } from 'lucide-svelte';

	interface Props {
		jersey: Record<string, unknown>;
		onPromote?: (familyId: string) => void;
		onOpenDetail?: (familyId: string) => void;
		onDelete?: (familyId: string) => void;
	}
	let { jersey, onPromote, onOpenDetail, onDelete }: Props = $props();

	const familyId = $derived(String(jersey.family_id ?? ''));
	const sku = $derived(String(jersey.sku ?? jersey.family_id ?? ''));
	const team = $derived(String(jersey.team ?? ''));
	const season = $derived(String(jersey.season ?? ''));
	const variant = $derived(String(jersey.variant ?? ''));
	const hero = $derived(jersey.hero_thumbnail as string | null | undefined);
	const tier = $derived(jersey.tier as string | null | undefined);

	const flags = $derived((jersey.flags as Record<string, unknown> | undefined) ?? {});
	const isDirty = $derived(flags.dirty === true);
	const isQaPriority = $derived(flags.qa_priority === 1 || flags.qa_priority === true);

	const galleryArr = $derived((jersey.gallery as string[] | undefined) ?? []);
	const coverage = $derived(galleryArr.length);
</script>

<div
	class="group flex flex-col rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] transition-all hover:border-[var(--color-text-tertiary)]"
>
	<!-- Thumb -->
	<button
		type="button"
		onclick={() => onOpenDetail?.(familyId)}
		class="relative aspect-[3/4] overflow-hidden bg-[var(--color-surface-2)]"
	>
		{#if hero}
			<img
				src={hero}
				alt={team}
				class="h-full w-full object-cover transition-transform group-hover:scale-105"
				loading="lazy"
			/>
		{:else}
			<div class="flex h-full w-full items-center justify-center text-[10px] text-[var(--color-text-muted)]">
				sin foto
			</div>
		{/if}

		<!-- Badges overlay -->
		<div class="absolute left-2 top-2 flex flex-col gap-1">
			{#if isDirty}
				<span
					class="text-mono inline-flex items-center gap-1 rounded-[2px] px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-wide"
					style:background="rgba(244, 63, 94, 0.85)"
					style:color="white"
					title={(flags.dirty_reason as string | undefined) ?? 'Foto rota detectada'}
				>
					<AlertCircle size={9} strokeWidth={2.2} />
					DIRTY
				</span>
			{/if}
			{#if isQaPriority}
				<span
					class="text-mono inline-flex items-center gap-1 rounded-[2px] bg-[var(--color-terminal)]/90 px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-wide text-[var(--color-bg)]"
				>
					<Star size={9} strokeWidth={2.2} />
					QA
				</span>
			{/if}
		</div>

		{#if tier}
			<span
				class="text-mono absolute right-2 top-2 rounded-[2px] bg-black/60 px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-wide text-white"
			>
				{tier}
			</span>
		{/if}

		{#if coverage > 0}
			<span
				class="text-mono absolute bottom-2 right-2 rounded-[2px] bg-black/60 px-1.5 py-0.5 text-[8.5px] tabular-nums text-white"
			>
				{coverage}📷
			</span>
		{/if}
	</button>

	<!-- Meta -->
	<div class="flex flex-col gap-1.5 p-2.5">
		<div class="text-mono truncate text-[11px] font-semibold text-[var(--color-text-primary)]" title={sku}>
			{sku}
		</div>
		<div class="flex items-center gap-1.5 text-[10px] text-[var(--color-text-secondary)]">
			<span class="truncate" title={team}>{team || '—'}</span>
			{#if season}
				<span class="text-[var(--color-text-muted)]">·</span>
				<span class="text-mono">{season}</span>
			{/if}
			{#if variant}
				<span class="text-[var(--color-text-muted)]">·</span>
				<span class="text-mono uppercase">{variant}</span>
			{/if}
		</div>

		<!-- Quick actions -->
		<div class="mt-1 flex gap-1">
			<button
				type="button"
				onclick={() => onPromote?.(familyId)}
				class="text-display flex flex-1 items-center justify-center gap-1 rounded-[3px] border border-[var(--color-terminal)]/40 bg-transparent px-2 py-1 text-[9px] tracking-[0.14em] text-[var(--color-terminal)] transition-colors hover:bg-[var(--color-terminal)] hover:text-[var(--color-bg)]"
				title="Promover a Stock o Mystery"
			>
				<Rocket size={10} strokeWidth={2} />
				PROMOVER
			</button>
			<button
				type="button"
				onclick={() => onOpenDetail?.(familyId)}
				class="rounded-[3px] border border-[var(--color-border)] px-2 text-[var(--color-text-tertiary)] transition-colors hover:border-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
				title="Más opciones"
			>
				<MoreHorizontal size={12} strokeWidth={1.8} />
			</button>
			<button
				type="button"
				onclick={() => onDelete?.(familyId)}
				class="rounded-[3px] border border-[var(--color-border)] px-2 text-[var(--color-text-tertiary)] transition-colors hover:border-[var(--color-danger)] hover:text-[var(--color-danger)]"
				title="Archivar"
			>
				<Trash2 size={12} strokeWidth={1.8} />
			</button>
		</div>
	</div>
</div>
