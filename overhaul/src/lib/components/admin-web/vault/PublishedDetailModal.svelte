<!--
	PublishedDetailModal — modal simplificado para una jersey PUBLISHED.

	NOTA T4.6: el plan original pedía reusar el modal grande FM-style del
	Audit existente, agregando variante para PUBLISHED state. Eso requeriría
	extraer DetailPane.svelte (1844 líneas) en un componente reusable —
	mismo problema que T4.2 (riesgo alto, scope alto). Por R7.0 hacemos un
	modal simplificado con la info clave + acciones quick. R7.0.1 puede
	refactorizar DetailPane si Diego lo prioriza.

	Acciones disponibles (botones):
	  - Toggle dirty flag
	  - Archive jersey
	  - Re-fetch (TODO — viene en T7+/Sistema)
	  - Cerrar
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import { X, AlertCircle, Archive, RefreshCw } from 'lucide-svelte';

	interface Props {
		familyId: string;
		onClose: () => void;
	}
	let { familyId, onClose }: Props = $props();

	let busy = $state(false);
	let info = $state<string | null>(null);

	async function toggleDirty() {
		const reason = prompt('Razón de dirty (vacío = limpiar):', '');
		if (reason === null) return;
		busy = true;
		info = null;
		try {
			await adminWeb.toggle_dirty_flag({
				family_id: familyId,
				dirty: reason.trim().length > 0,
				reason: reason.trim() || undefined
			});
			info = reason.trim() ? '✓ Marcada como dirty' : '✓ Dirty flag limpiado';
		} catch (err) {
			info = `✗ ${err instanceof Error ? err.message : err}`;
		} finally {
			busy = false;
		}
	}

	async function archive() {
		if (!confirm(`¿Archivar ${familyId}? (puede revivirse después)`)) return;
		busy = true;
		try {
			await adminWeb.archive_jersey({ family_id: familyId });
			info = '✓ Archivada';
			setTimeout(() => onClose(), 800);
		} catch (err) {
			info = `✗ ${err instanceof Error ? err.message : err}`;
		} finally {
			busy = false;
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
			<div>
				<div
					class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]"
				>
					DETAIL · PUBLISHED
				</div>
				<div class="text-mono mt-0.5 text-[10px] text-[var(--color-text-muted)]">
					{familyId}
				</div>
			</div>
			<button
				type="button"
				onclick={onClose}
				class="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
			>
				<X size={16} strokeWidth={1.8} />
			</button>
		</div>

		<div class="space-y-3 p-4 text-[12px]">
			<p class="text-[var(--color-text-secondary)]">
				Modal simplificado de R7.0. El detail FM-style completo con
				gallery + meta + edit modelo vive en el Audit del ERP raíz.
			</p>

			<div class="space-y-2 pt-2">
				<button
					type="button"
					onclick={toggleDirty}
					disabled={busy}
					class="text-display flex w-full items-center gap-2 rounded-[3px] border border-[var(--color-border)] px-3 py-2 text-[10.5px] tracking-[0.14em] text-[var(--color-text-secondary)] hover:border-[var(--color-warning)] hover:text-[var(--color-warning)] disabled:opacity-50"
				>
					<AlertCircle size={12} strokeWidth={1.8} />
					Toggle dirty flag
				</button>

				<button
					type="button"
					onclick={archive}
					disabled={busy}
					class="text-display flex w-full items-center gap-2 rounded-[3px] border border-[var(--color-border)] px-3 py-2 text-[10.5px] tracking-[0.14em] text-[var(--color-text-secondary)] hover:border-[var(--color-danger)] hover:text-[var(--color-danger)] disabled:opacity-50"
				>
					<Archive size={12} strokeWidth={1.8} />
					Archivar
				</button>

				<button
					type="button"
					disabled
					class="text-display flex w-full items-center gap-2 rounded-[3px] border border-[var(--color-border)] px-3 py-2 text-[10.5px] tracking-[0.14em] text-[var(--color-text-muted)] opacity-50"
					title="Re-fetch desde Yupoo — viene en T7+"
				>
					<RefreshCw size={12} strokeWidth={1.8} />
					Re-fetch (T7+)
				</button>
			</div>

			{#if info}
				<div
					class="text-mono mt-2 rounded-[3px] bg-[var(--color-surface-2)] p-2 text-[11px] text-[var(--color-text-secondary)]"
				>
					{info}
				</div>
			{/if}
		</div>
	</div>
</div>
