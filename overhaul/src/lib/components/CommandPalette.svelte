<script lang="ts">
	import type { Family, Modelo } from '$lib/data/types';
	import { Search, CornerDownLeft, ArrowUp, ArrowDown } from 'lucide-svelte';

	interface Props {
		open: boolean;
		allSkus: Array<{ sku: string; family: Family; modelo: Modelo }>;
		onClose: () => void;
		onSelect: (sku: string) => void;
	}

	let { open, allSkus, onClose, onSelect }: Props = $props();

	let query = $state('');
	let selectedIdx = $state(0);

	let results = $derived.by(() => {
		if (!query.trim()) return allSkus.slice(0, 8);
		const q = query.toLowerCase();
		const tokens = q.split(/\s+/).filter((t) => t);
		return allSkus
			.filter((item) => {
				const haystack =
					`${item.sku} ${item.family.team} ${item.family.teamAliasEs || ''} ${item.family.variant} ${item.modelo.modeloType} ${item.modelo.sleeve || ''}`.toLowerCase();
				return tokens.every((t) => haystack.includes(t));
			})
			.slice(0, 10);
	});

	$effect(() => {
		if (open) selectedIdx = 0;
	});

	function handleKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		} else if (e.key === 'ArrowDown' || (e.key === 'j' && e.ctrlKey)) {
			e.preventDefault();
			selectedIdx = Math.min(selectedIdx + 1, results.length - 1);
		} else if (e.key === 'ArrowUp' || (e.key === 'k' && e.ctrlKey)) {
			e.preventDefault();
			selectedIdx = Math.max(selectedIdx - 1, 0);
		} else if (e.key === 'Enter' && results[selectedIdx]) {
			e.preventDefault();
			onSelect(results[selectedIdx].sku);
			onClose();
		}
	}

	const MODELO_LABEL: Record<string, string> = {
		fan_adult: 'Fan',
		player_adult: 'Player',
		retro_adult: 'Retro',
		woman: 'Mujer',
		kid: 'Niño',
		baby: 'Bebé',
		goalkeeper: 'GK'
	};
</script>

<svelte:window onkeydown={handleKey} />

{#if open}
	<div
		class="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm pt-[15vh]"
		onclick={onClose}
		role="presentation"
	>
		<div
			class="w-[580px] overflow-hidden rounded-[6px] border border-[var(--color-border-strong)] bg-[var(--color-surface-1)] shadow-2xl"
			style="box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px var(--color-border-strong), 0 0 40px rgba(91, 141, 239, 0.1);"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
		>
			<div class="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3">
				<Search size={15} strokeWidth={1.8} class="text-[var(--color-text-tertiary)]" />
				<input
					type="text"
					placeholder="Buscar SKU, team, variante…"
					bind:value={query}
					class="flex-1 bg-transparent text-[14px] text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none"
					autofocus
				/>
				<kbd>ESC</kbd>
			</div>

			<div class="max-h-[400px] overflow-y-auto py-1">
				{#if results.length === 0}
					<div class="px-4 py-8 text-center text-[12px] text-[var(--color-text-tertiary)]">
						Sin resultados para "{query}"
					</div>
				{:else}
					{#each results as item, i (item.sku)}
						<button
							type="button"
							class="relative flex w-full items-center gap-3 px-4 py-2 text-left"
							class:bg-[var(--color-surface-2)]={selectedIdx === i}
							onmouseenter={() => (selectedIdx = i)}
							onclick={() => {
								onSelect(item.sku);
								onClose();
							}}
						>
							{#if selectedIdx === i}
								<span
									class="absolute left-0 top-1 bottom-1 w-[2px] bg-[var(--color-accent)]"
								></span>
							{/if}
							<span
								class="text-mono w-[120px] shrink-0 text-[10.5px] font-semibold tabular-nums"
								class:text-[var(--color-accent)]={selectedIdx === i}
								class:text-[var(--color-text-tertiary)]={selectedIdx !== i}
							>
								{item.sku}
							</span>
							<span class="flex-1 text-[12.5px] text-[var(--color-text-primary)]">
								{item.family.team}
								<span class="text-[var(--color-text-tertiary)]">·</span>
								{item.family.variantLabel}
								<span class="text-[var(--color-text-tertiary)]">·</span>
								{MODELO_LABEL[item.modelo.modeloType] || item.modelo.modeloType}
							</span>
							<span
								class="text-display text-[9.5px] text-[var(--color-text-tertiary)]"
							>
								Grupo {item.family.group}
							</span>
						</button>
					{/each}
				{/if}
			</div>

			<div
				class="flex items-center justify-between border-t border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-2 text-[10px] text-[var(--color-text-tertiary)]"
			>
				<span class="flex items-center gap-1.5">
					<kbd><ArrowUp size={9} strokeWidth={2} /></kbd>
					<kbd><ArrowDown size={9} strokeWidth={2} /></kbd>
					<span>navegar</span>
				</span>
				<span class="flex items-center gap-1.5">
					<kbd><CornerDownLeft size={9} strokeWidth={2} /></kbd>
					<span>abrir</span>
				</span>
			</div>
		</div>
	</div>
{/if}
