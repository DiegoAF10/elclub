<!--
	BulkActionBar — slide-up al fondo cuando hay multi-select.
	Acciones: TAG (open tag picker), ARCHIVAR, RE-FETCH, ELIMINAR.
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import { Tag as TagIcon, Archive, RefreshCw, Trash2, X } from 'lucide-svelte';

	interface Props {
		selectedFamilyIds: string[];
		availableTags: { id: number; display_name: string; type_slug: string }[];
		onClear: () => void;
		onComplete: () => void;
	}
	let { selectedFamilyIds, availableTags, onClear, onComplete }: Props = $props();

	let busy = $state(false);
	let info = $state<string | null>(null);
	let showTagPicker = $state(false);

	async function run(action: string, payload?: Record<string, unknown>) {
		if (busy) return;
		busy = true;
		info = null;
		try {
			const result = await adminWeb.bulk_action({
				family_ids: selectedFamilyIds,
				action: action as 'tag' | 'archive' | 're_fetch' | 'delete',
				payload
			});
			info = `✓ ${result.affected} afectados${result.errors.length ? ` · ${result.errors.length} errores` : ''}`;
			setTimeout(() => onComplete(), 800);
		} catch (err) {
			info = `✗ ${err instanceof Error ? err.message : err}`;
		} finally {
			busy = false;
		}
	}

	async function applyTag(tagId: number) {
		showTagPicker = false;
		await run('tag', { tag_id: tagId });
	}

	async function archive() {
		if (!confirm(`¿Archivar ${selectedFamilyIds.length} jerseys?`)) return;
		await run('archive');
	}
	async function reFetch() {
		await run('re_fetch');
	}
	async function softDelete() {
		if (!confirm(`¿Eliminar ${selectedFamilyIds.length} jerseys? (soft delete, recuperable)`)) return;
		await run('delete');
	}
</script>

<div
	class="ui-chrome border-t border-[var(--color-terminal)] bg-[var(--color-surface-2)] shadow-[0_-2px_12px_rgba(0,0,0,0.3)]"
>
	<div class="flex items-center gap-3 px-4 py-2">
		<div class="flex items-center gap-2">
			<button
				type="button"
				onclick={onClear}
				class="flex h-6 w-6 items-center justify-center rounded-[3px] hover:bg-[var(--color-surface-3)]"
				title="Limpiar selección"
			>
				<X size={13} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
			</button>
			<span
				class="text-mono rounded-[3px] bg-[var(--color-terminal)] px-2 py-1 text-[11px] font-semibold tabular-nums text-[var(--color-bg)]"
			>
				{selectedFamilyIds.length}
			</span>
			<span class="text-[12px] text-[var(--color-text-secondary)]">seleccionados</span>
		</div>

		<div class="ml-auto flex items-center gap-1.5">
			<div class="relative">
				<button
					type="button"
					onclick={() => (showTagPicker = !showTagPicker)}
					disabled={busy || availableTags.length === 0}
					class="text-display flex items-center gap-1 rounded-[3px] border border-[var(--color-border)] px-3 py-1.5 text-[10.5px] tracking-[0.14em] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)] disabled:opacity-40"
				>
					<TagIcon size={11} strokeWidth={1.8} />
					+ TAG
				</button>
				{#if showTagPicker}
					<div
						class="absolute bottom-full right-0 mb-2 max-h-72 w-64 overflow-y-auto rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-1.5 shadow-2xl"
					>
						{#each availableTags as t (t.id)}
							<button
								type="button"
								onclick={() => applyTag(t.id)}
								class="flex w-full items-center justify-between gap-2 rounded-[3px] px-2 py-1 text-left text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
							>
								<span class="truncate">{t.display_name}</span>
								<span
									class="text-mono shrink-0 text-[9px] uppercase text-[var(--color-text-muted)]"
								>
									{t.type_slug}
								</span>
							</button>
						{/each}
						{#if availableTags.length === 0}
							<div class="p-2 text-[10px] text-[var(--color-text-muted)]">
								No hay tags disponibles
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<button
				type="button"
				onclick={archive}
				disabled={busy}
				class="text-display flex items-center gap-1 rounded-[3px] border border-[var(--color-border)] px-3 py-1.5 text-[10.5px] tracking-[0.14em] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)] disabled:opacity-40"
			>
				<Archive size={11} strokeWidth={1.8} />
				ARCHIVAR
			</button>

			<button
				type="button"
				onclick={reFetch}
				disabled={busy}
				class="text-display flex items-center gap-1 rounded-[3px] border border-[var(--color-border)] px-3 py-1.5 text-[10.5px] tracking-[0.14em] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)] disabled:opacity-40"
			>
				<RefreshCw size={11} strokeWidth={1.8} />
				RE-FETCH
			</button>

			<button
				type="button"
				onclick={softDelete}
				disabled={busy}
				class="text-display flex items-center gap-1 rounded-[3px] border border-[var(--color-border)] px-3 py-1.5 text-[10.5px] tracking-[0.14em] text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 disabled:opacity-40"
			>
				<Trash2 size={11} strokeWidth={1.8} />
				ELIMINAR
			</button>
		</div>

		{#if info}
			<div class="text-mono ml-3 text-[10.5px] text-[var(--color-text-secondary)]">
				{info}
			</div>
		{/if}
	</div>
</div>
