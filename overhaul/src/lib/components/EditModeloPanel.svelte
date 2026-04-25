<script lang="ts">
	import type { Family, Modelo, ModeloType } from '$lib/data/types';
	import { Check, X, AlertCircle, Loader2 } from 'lucide-svelte';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';

	interface Props {
		family: Family;
		modelo: Modelo;
		onClose: () => void;
		onFlash: (msg: string) => void;
		onRefresh: () => void;
		onSelectSku: (sku: string) => void;
	}

	let { family, modelo, onClose, onFlash, onRefresh, onSelectSku }: Props = $props();

	const TYPE_OPTIONS: { value: ModeloType; label: string; group: string }[] = [
		{ value: 'fan_adult', label: 'Fan adulto', group: 'Adulto' },
		{ value: 'player_adult', label: 'Player adulto', group: 'Adulto' },
		{ value: 'retro_adult', label: 'Retro adulto', group: 'Adulto' },
		{ value: 'goalkeeper', label: 'Arquero', group: 'Adulto' },
		{ value: 'woman', label: 'Mujer', group: 'Variante' },
		{ value: 'kid', label: 'Niño', group: 'Variante' },
		{ value: 'baby', label: 'Bebé', group: 'Variante' },
		{ value: 'training', label: 'Entrenamiento', group: 'Otros' },
		{ value: 'polo', label: 'Polo', group: 'Otros' },
		{ value: 'jacket', label: 'Chaqueta', group: 'Otros' },
		{ value: 'vest', label: 'Vest', group: 'Otros' },
		{ value: 'sweatshirt', label: 'Sweatshirt', group: 'Otros' },
		{ value: 'shorts', label: 'Shorts', group: 'Otros' }
	];

	// Types donde sleeve no aplica (kid/baby no llevan distinción manga corta/larga
	// en el SKU, según convention del playbook §3).
	const NO_SLEEVE_TYPES = new Set(['kid', 'baby', 'retro_adult']);

	let newType = $state<ModeloType>(modelo.modeloType);
	let newSleeve = $state<string | null>(modelo.sleeve ?? null);
	let motivo = $state('mislabeled en scrape');
	let busy = $state(false);

	// Cuando cambia type a no-sleeve, resetear sleeve a null
	$effect(() => {
		if (NO_SLEEVE_TYPES.has(newType)) {
			newSleeve = null;
		} else if (newSleeve === null && !NO_SLEEVE_TYPES.has(newType)) {
			// Si pasa a un type que requiere sleeve, default short
			newSleeve = 'short';
		}
	});

	let hasChanges = $derived(newType !== modelo.modeloType || newSleeve !== (modelo.sleeve ?? null));

	// Heurística de SKU preview — solo cosmética. El SKU real se regenera en
	// Python (audit_db.generate_skus_for_family) que maneja edge cases + colisión.
	const TYPE_CODE: Record<string, string> = {
		fan_adult: 'F',
		player_adult: 'P',
		retro_adult: 'RE',
		woman: 'W',
		kid: 'K',
		baby: 'B',
		goalkeeper: 'G',
		training: 'TR',
		polo: 'PO',
		jacket: 'JA',
		vest: 'VE',
		sweatshirt: 'SW',
		shorts: 'SH'
	};

	function previewSku(type: ModeloType, sleeve: string | null): string {
		// Extraer prefix del SKU actual: BRA-2026-V-FS → BRA-2026-V-
		const oldSku = modelo.sku;
		const dashIdx = oldSku.lastIndexOf('-');
		if (dashIdx < 0) return oldSku;
		const prefix = oldSku.slice(0, dashIdx + 1);

		const code = TYPE_CODE[type] ?? '?';
		// Combos especiales: retro+long → RL, retro+short → RE
		// woman+short → WS, woman+long → WL
		// fan/player + sleeve → FS/FL/PS/PL
		// kid → K (sin sleeve), baby → B, goalkeeper → G/GS/GL
		let suffix = code;
		if (sleeve === 'short' && (type === 'fan_adult' || type === 'player_adult' || type === 'woman' || type === 'goalkeeper')) {
			suffix = `${code}S`;
		} else if (sleeve === 'long' && (type === 'fan_adult' || type === 'player_adult' || type === 'woman' || type === 'goalkeeper')) {
			suffix = `${code}L`;
		} else if (type === 'retro_adult' && sleeve === 'long') {
			suffix = 'RL';
		}
		// kid/baby/retro/etc → solo type code
		return prefix + suffix;
	}

	let skuPreview = $derived(hasChanges ? previewSku(newType, newSleeve) : modelo.sku);
	let skuChanges = $derived(skuPreview !== modelo.sku);

	async function apply() {
		if (!hasChanges || busy) return;
		busy = true;
		const oldSku = modelo.sku;
		try {
			const modeloIdx = family.modelos.findIndex((m) => m.sku === oldSku);
			if (modeloIdx < 0) throw new Error('modelo no encontrado en family');

			const result = await adapter.editModeloType(
				family.id,
				modeloIdx,
				newType,
				newSleeve,
				motivo.trim()
			);
			if (result.ok) {
				const migrated = result.migrated
					? ` · migradas ${result.migrated.audit_decisions}d+${result.migrated.audit_photo_actions}a`
					: '';
				if (result.old_sku !== result.new_sku) {
					onFlash(`✓ ${result.old_sku} → ${result.new_sku}${migrated}`);
				} else {
					onFlash(`✓ Modelo actualizado (SKU sin cambios)`);
				}
				onRefresh();
				if (result.new_sku && result.new_sku !== result.old_sku) {
					onSelectSku(result.new_sku);
				}
				onClose();
			} else {
				onFlash(`✗ Edit falló: ${result.error ?? 'error desconocido'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Edit modelo: requiere el .exe');
			} else {
				onFlash(`Edit falló: ${err instanceof Error ? err.message : err}`);
			}
		} finally {
			busy = false;
		}
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		} else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
			e.preventDefault();
			apply();
		}
	}

	const groupedTypes = TYPE_OPTIONS.reduce<Record<string, typeof TYPE_OPTIONS>>((acc, opt) => {
		(acc[opt.group] ??= []).push(opt);
		return acc;
	}, {});
</script>

<svelte:window on:keydown={handleKey} />

<div
	class="rounded-[6px] border border-[var(--color-accent)]/40 bg-[var(--color-surface-1)] p-3 text-[11px] shadow-[0_0_0_1px_var(--color-accent)/0.15]"
	role="dialog"
	aria-label="Editar modelo type / sleeve"
>
	<div class="mb-2.5 flex items-center justify-between">
		<div class="text-display flex items-center gap-1.5 text-[10px] text-[var(--color-text-tertiary)]">
			<span>Editar modelo</span>
			<span class="text-[var(--color-text-muted)]">·</span>
			<span class="text-mono text-[var(--color-text-secondary)]">{modelo.sku}</span>
		</div>
		<button
			type="button"
			onclick={onClose}
			class="rounded-[3px] p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
			title="Cancelar (Esc)"
			aria-label="Cancelar"
		>
			<X size={12} strokeWidth={2} />
		</button>
	</div>

	<!-- Type selector — grouped grid -->
	<div class="mb-2.5">
		<div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Type</div>
		<div class="space-y-1.5">
			{#each Object.entries(groupedTypes) as [group, opts] (group)}
				<div>
					<div class="text-mono mb-0.5 text-[8.5px] uppercase tracking-wider text-[var(--color-text-muted)]">
						{group}
					</div>
					<div class="flex flex-wrap gap-1">
						{#each opts as opt (opt.value)}
							<button
								type="button"
								onclick={() => (newType = opt.value)}
								class="rounded-[3px] border px-2 py-1 text-[10.5px] transition-colors {newType ===
								opt.value
									? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
									: 'border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text-primary)]'}"
							>
								{opt.label}
							</button>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- Sleeve selector — disabled si type no aplica -->
	{#if !NO_SLEEVE_TYPES.has(newType)}
		<div class="mb-2.5">
			<div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">Manga</div>
			<div class="flex gap-1">
				{#each [{ v: 'short', l: 'Corta' }, { v: 'long', l: 'Larga' }] as opt (opt.v)}
					<button
						type="button"
						onclick={() => (newSleeve = opt.v)}
						class="flex-1 rounded-[3px] border px-2 py-1 text-[10.5px] transition-colors {newSleeve ===
						opt.v
							? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
							: 'border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text-primary)]'}"
					>
						{opt.l}
					</button>
				{/each}
			</div>
		</div>
	{:else}
		<div class="mb-2.5 flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)]">
			<AlertCircle size={11} strokeWidth={1.8} />
			<span>{newType === 'kid' ? 'Niño' : newType === 'baby' ? 'Bebé' : 'Retro'} no usa sleeve en el SKU</span>
		</div>
	{/if}

	<!-- Motivo -->
	<div class="mb-2.5">
		<label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">
			<span>Motivo (opcional)</span>
			<input
				type="text"
				bind:value={motivo}
				placeholder="ej. mislabeled en scrape"
				class="mt-0.5 w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-[10.5px] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
			/>
		</label>
	</div>

	<!-- SKU preview + actions -->
	<div class="flex items-center justify-between gap-2 border-t border-[var(--color-border)] pt-2.5">
		<div class="text-mono text-[10.5px]">
			{#if skuChanges}
				<span class="text-[var(--color-text-muted)] line-through">{modelo.sku}</span>
				<span class="mx-1 text-[var(--color-text-tertiary)]">→</span>
				<span class="font-semibold text-[var(--color-accent)]">{skuPreview}</span>
				<span class="text-display ml-1.5 text-[8.5px] text-[var(--color-text-muted)]">aprox</span>
			{:else if hasChanges}
				<span class="text-[var(--color-text-tertiary)]">SKU sin cambios</span>
			{:else}
				<span class="text-[var(--color-text-muted)]">Sin cambios pendientes</span>
			{/if}
		</div>
		<div class="flex items-center gap-1.5">
			<button
				type="button"
				onclick={onClose}
				disabled={busy}
				class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2.5 py-1 text-[10.5px] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
			>
				Cancelar
			</button>
			<button
				type="button"
				onclick={apply}
				disabled={!hasChanges || busy}
				class="flex items-center gap-1.5 rounded-[3px] border border-[var(--color-accent)]/40 bg-[var(--color-accent)] px-2.5 py-1 text-[10.5px] font-semibold text-[var(--color-accent-on)] transition-colors hover:bg-[var(--color-accent-strong)] disabled:cursor-not-allowed disabled:opacity-40"
				title="Aplicar (Ctrl+Enter)"
			>
				{#if busy}
					<Loader2 size={11} class="animate-spin" />
					Aplicando…
				{:else}
					<Check size={11} strokeWidth={2.2} />
					Aplicar
				{/if}
			</button>
		</div>
	</div>

	{#if skuChanges}
		<div class="mt-2 flex items-start gap-1.5 rounded-[3px] bg-[var(--color-warning)]/10 px-2 py-1.5 text-[10px] text-[var(--color-warning)]">
			<AlertCircle size={11} strokeWidth={1.8} class="mt-0.5 flex-shrink-0" />
			<span>
				Al aplicar se migran rows de <span class="text-mono">audit_decisions</span> +
				<span class="text-mono">audit_photo_actions</span> al SKU nuevo.
			</span>
		</div>
	{/if}
</div>
