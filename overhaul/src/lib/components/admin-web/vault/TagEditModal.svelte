<!--
	TagEditModal — modal create/edit de un tag.
	Form: display_name (auto slug), icon (emoji input), color (hex), is_auto_derived.

	Mode 'create': type_id ya seleccionado, llama create_tag.
	Mode 'edit': tag_id provisto, llama update_tag.
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import { X } from 'lucide-svelte';

	type Mode =
		| { kind: 'create'; type_id: number }
		| {
				kind: 'edit';
				tag: {
					id: number;
					display_name: string;
					icon?: string;
					color?: string;
				};
		  };

	interface Props {
		mode: Mode;
		onClose: () => void;
		onSuccess: () => void;
	}
	let { mode, onClose, onSuccess }: Props = $props();

	let displayName = $state(mode.kind === 'edit' ? mode.tag.display_name : '');
	let icon = $state(mode.kind === 'edit' ? (mode.tag.icon ?? '') : '');
	let color = $state(mode.kind === 'edit' ? (mode.tag.color ?? '') : '');

	let submitting = $state(false);
	let error = $state<string | null>(null);

	function slugify(s: string): string {
		return s
			.toLowerCase()
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '');
	}

	const slug = $derived(slugify(displayName));

	async function submit() {
		error = null;
		if (!displayName.trim()) {
			error = 'display_name requerido';
			return;
		}
		submitting = true;
		try {
			if (mode.kind === 'create') {
				await adminWeb.create_tag({
					type_id: mode.type_id,
					slug,
					display_name: displayName.trim(),
					icon: icon || undefined,
					color: color || undefined
				});
			} else {
				await adminWeb.update_tag({
					id: mode.tag.id,
					updates: {
						display_name: displayName.trim(),
						icon: icon || null,
						color: color || null
					} as never
				});
			}
			onSuccess();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			submitting = false;
		}
	}

	function handleBackdrop(e: MouseEvent) {
		if (e.target === e.currentTarget) onClose();
	}
	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<svelte:window onkeydown={handleKey} />

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
	onclick={handleBackdrop}
	role="dialog"
	aria-modal="true"
	tabindex="-1"
>
	<div
		class="w-full max-w-md rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] shadow-2xl"
	>
		<div
			class="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"
		>
			<div
				class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				{mode.kind === 'create' ? 'NUEVO TAG' : 'EDITAR TAG'}
			</div>
			<button
				type="button"
				onclick={onClose}
				class="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
			>
				<X size={16} strokeWidth={1.8} />
			</button>
		</div>

		<div class="space-y-3 p-4">
			<label class="block">
				<span
					class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
				>
					DISPLAY NAME
				</span>
				<input
					type="text"
					bind:value={displayName}
					placeholder="Mundial 2026"
					class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
				/>
			</label>

			{#if mode.kind === 'create'}
				<div>
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						SLUG (auto)
					</span>
					<div
						class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-3)] px-2 py-1.5 text-[12px] text-[var(--color-text-secondary)]"
					>
						{slug || '—'}
					</div>
				</div>
			{/if}

			<div class="grid grid-cols-2 gap-3">
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						ICON (emoji)
					</span>
					<input
						type="text"
						bind:value={icon}
						placeholder="⚽"
						maxlength="4"
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-center text-[14px]"
					/>
				</label>
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						COLOR (hex)
					</span>
					<input
						type="text"
						bind:value={color}
						placeholder="#4ade80"
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px]"
					/>
				</label>
			</div>

			{#if error}
				<div
					class="rounded-[3px] border border-[var(--color-danger)] bg-[var(--color-danger)]/10 p-2 text-[11px] text-[var(--color-danger)]"
				>
					{error}
				</div>
			{/if}
		</div>

		<div
			class="flex items-center justify-end gap-2 border-t border-[var(--color-border)] px-4 py-3"
		>
			<button
				type="button"
				onclick={onClose}
				disabled={submitting}
				class="rounded-[3px] px-3 py-1.5 text-[11px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
			>
				Cancelar
			</button>
			<button
				type="button"
				onclick={submit}
				disabled={submitting}
				class="text-display rounded-[3px] bg-[var(--color-terminal)] px-3 py-1.5 text-[10.5px] tracking-[0.14em] text-[var(--color-bg)] transition-opacity hover:opacity-90 disabled:opacity-50"
			>
				{submitting ? 'GUARDANDO…' : mode.kind === 'create' ? 'CREAR' : 'GUARDAR'}
			</button>
		</div>
	</div>
</div>
