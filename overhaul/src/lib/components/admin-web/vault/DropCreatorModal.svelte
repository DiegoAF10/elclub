<!--
	DropCreatorModal — modal inline para promover una jersey a Stock o Mystery.

	Form fields:
	  - target: 'stock' | 'mystery' (radio)
	  - publish_at: datetime-local (opcional, NULL = DRAFT)
	  - unpublish_at: datetime-local (opcional)
	  - Stock-specific: price_override (Q*100 internamente), badge, copy_override, priority
	  - Mystery-specific: pool_weight (default 1.0)

	Validación cliente: publish_at < unpublish_at, price > 0.
	Submit → adminWeb.promote_to_stock | promote_to_mystery → onSuccess.
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import { X, Rocket, Sparkles } from 'lucide-svelte';

	interface Props {
		familyId: string;
		onClose: () => void;
		onSuccess: () => void;
	}
	let { familyId, onClose, onSuccess }: Props = $props();

	let target = $state<'stock' | 'mystery'>('stock');
	let publishAt = $state(''); // datetime-local string
	let unpublishAt = $state('');
	let priceQ = $state(''); // en Quetzales (Q475 → "475")
	let badge = $state('');
	let copyOverride = $state('');
	let priority = $state(5);
	let poolWeight = $state(1.0);

	let submitting = $state(false);
	let error = $state<string | null>(null);

	function toUnix(local: string): number | null {
		if (!local) return null;
		const d = new Date(local);
		if (isNaN(d.getTime())) return null;
		return Math.floor(d.getTime() / 1000);
	}

	function validate(): string | null {
		const pub = toUnix(publishAt);
		const unpub = toUnix(unpublishAt);
		if (pub && unpub && unpub <= pub) return 'unpublish_at debe ser posterior a publish_at';
		if (target === 'stock' && priceQ) {
			const n = parseInt(priceQ, 10);
			if (isNaN(n) || n <= 0) return 'price_override debe ser número positivo';
		}
		return null;
	}

	async function submit() {
		error = validate();
		if (error) return;
		submitting = true;
		try {
			const pub = toUnix(publishAt);
			const unpub = toUnix(unpublishAt);
			if (target === 'stock') {
				const priceCents = priceQ ? parseInt(priceQ, 10) * 100 : null;
				await adminWeb.promote_to_stock({
					family_id: familyId,
					override: {
						publish_at: pub,
						unpublish_at: unpub,
						price_override: priceCents,
						badge: badge || null,
						copy_override: copyOverride || null,
						priority,
						status: pub == null ? 'draft' : pub > Math.floor(Date.now() / 1000) ? 'scheduled' : 'live',
						created_at: 0,
						updated_at: 0,
						created_by: 'diego',
						id: 0,
						computed_status: 'draft'
					}
				});
			} else {
				await adminWeb.promote_to_mystery({
					family_id: familyId,
					override: {
						publish_at: pub,
						unpublish_at: unpub,
						pool_weight: poolWeight,
						status: pub == null ? 'draft' : pub > Math.floor(Date.now() / 1000) ? 'scheduled' : 'live',
						created_at: 0,
						updated_at: 0,
						created_by: 'diego',
						id: 0,
						computed_status: 'draft'
					}
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
		class="w-full max-w-lg rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] shadow-2xl"
	>
		<!-- Header -->
		<div
			class="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"
		>
			<div>
				<div
					class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]"
				>
					CREAR DROP
				</div>
				<div class="text-mono mt-0.5 text-[10px] text-[var(--color-text-muted)]">
					{familyId}
				</div>
			</div>
			<button
				type="button"
				onclick={onClose}
				class="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
				title="Cerrar"
			>
				<X size={16} strokeWidth={1.8} />
			</button>
		</div>

		<!-- Body -->
		<div class="space-y-3 p-4">
			<!-- Target selector -->
			<div>
				<div
					class="text-display mb-1.5 text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
				>
					DESTINO
				</div>
				<div class="grid grid-cols-2 gap-2">
					<button
						type="button"
						onclick={() => (target = 'stock')}
						class="flex items-center justify-center gap-2 rounded-[3px] border px-3 py-2 text-[12px] transition-all"
						class:border-[var(--color-terminal)]={target === 'stock'}
						class:bg-[var(--color-terminal)]={target === 'stock'}
						class:text-[var(--color-bg)]={target === 'stock'}
						class:border-[var(--color-border)]={target !== 'stock'}
						class:text-[var(--color-text-secondary)]={target !== 'stock'}
					>
						<Rocket size={13} strokeWidth={1.8} />
						Stock
					</button>
					<button
						type="button"
						onclick={() => (target = 'mystery')}
						class="flex items-center justify-center gap-2 rounded-[3px] border px-3 py-2 text-[12px] transition-all"
						class:border-[var(--color-terminal)]={target === 'mystery'}
						class:bg-[var(--color-terminal)]={target === 'mystery'}
						class:text-[var(--color-bg)]={target === 'mystery'}
						class:border-[var(--color-border)]={target !== 'mystery'}
						class:text-[var(--color-text-secondary)]={target !== 'mystery'}
					>
						<Sparkles size={13} strokeWidth={1.8} />
						Mystery
					</button>
				</div>
			</div>

			<!-- Schedule -->
			<div class="grid grid-cols-2 gap-2">
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						PUBLISH AT
					</span>
					<input
						type="datetime-local"
						bind:value={publishAt}
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
					/>
				</label>
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						UNPUBLISH AT
					</span>
					<input
						type="datetime-local"
						bind:value={unpublishAt}
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
					/>
				</label>
			</div>

			{#if target === 'stock'}
				<div class="grid grid-cols-2 gap-2">
					<label class="block">
						<span
							class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
						>
							PRECIO Q
						</span>
						<input
							type="number"
							placeholder="475"
							bind:value={priceQ}
							class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
						/>
					</label>
					<label class="block">
						<span
							class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
						>
							PRIORITY (1-10)
						</span>
						<input
							type="number"
							min="1"
							max="10"
							bind:value={priority}
							class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
						/>
					</label>
				</div>
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						BADGE
					</span>
					<input
						type="text"
						placeholder="GARANTIZADA, EXCLUSIVA, etc"
						bind:value={badge}
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
					/>
				</label>
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						COPY OVERRIDE
					</span>
					<textarea
						placeholder="Copy custom para esta jersey en Stock"
						bind:value={copyOverride}
						rows="2"
						class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
					></textarea>
				</label>
			{:else}
				<label class="block">
					<span
						class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						POOL WEIGHT (1.0 default)
					</span>
					<input
						type="number"
						step="0.1"
						min="0.1"
						bind:value={poolWeight}
						class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[12px] text-[var(--color-text-primary)]"
					/>
				</label>
			{/if}

			{#if error}
				<div
					class="rounded-[3px] border border-[var(--color-danger)] bg-[var(--color-danger)]/10 p-2 text-[11px] text-[var(--color-danger)]"
				>
					{error}
				</div>
			{/if}
		</div>

		<!-- Footer -->
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
				{submitting ? 'CREANDO…' : 'CREAR DROP'}
			</button>
		</div>
	</div>
</div>
