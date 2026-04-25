<script lang="ts">
	import type { Family, Modelo } from '$lib/data/types';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';
	import type { MoveModeloArgs } from '$lib/adapter';
	import { X, Search, Plus, ArrowRight, Loader2 } from 'lucide-svelte';
	import { invalidateAll } from '$app/navigation';

	interface Props {
		open: boolean;
		/** Family origen (donde vive el modelo a mover) */
		sourceFamily: Family | null;
		/** Modelo específico a mover. Si null + absorb=true, mueve todos los modelos de source */
		sourceModelo: Modelo | null;
		/** Lista completa de families (para typeahead target) */
		families: Family[];
		onClose: () => void;
		onFlash?: (msg: string) => void;
		onSelectSku?: (sku: string) => void;
	}

	let {
		open,
		sourceFamily,
		sourceModelo,
		families,
		onClose,
		onFlash = () => {},
		onSelectSku = () => {}
	}: Props = $props();

	let tab = $state<'existing' | 'new'>('existing');
	let busy = $state(false);

	// Tab 1: Move to existing family
	let searchQuery = $state('');
	let selectedTargetFid = $state<string | null>(null);
	let absorbAll = $state(false);

	// Tab 2: Create new family
	let newTeam = $state('');
	let newSeason = $state('2026');
	let newVariant = $state('home');
	let newCategory = $state('adult');

	const VARIANT_OPTIONS = [
		{ value: 'home', label: 'Local' },
		{ value: 'away', label: 'Visita' },
		{ value: 'third', label: 'Tercera' },
		{ value: 'goalkeeper', label: 'Portero' },
		{ value: 'special', label: 'Especial' },
		{ value: 'training', label: 'Entrenamiento' }
	];

	// Reset state on open/close
	$effect(() => {
		if (open) {
			tab = 'existing';
			searchQuery = '';
			selectedTargetFid = null;
			absorbAll = false;
			newTeam = sourceFamily?.team ?? '';
			newSeason = sourceFamily?.season || '2026';
			newVariant = sourceFamily?.variant || 'home';
		}
	});

	// Typeahead — filtra families que NO son el source
	let filteredTargets = $derived.by(() => {
		if (!sourceFamily) return [];
		const q = searchQuery.trim().toLowerCase();
		const candidates = families.filter((f) => f.id !== sourceFamily.id);
		if (!q) return candidates.slice(0, 50);
		return candidates
			.filter((f) => {
				const hay = `${f.team} ${f.season} ${f.variantLabel} ${f.id}`.toLowerCase();
				return hay.includes(q);
			})
			.slice(0, 50);
	});

	async function handleMoveToExisting() {
		if (!sourceFamily || !selectedTargetFid || busy) return;
		const modeloIdx = sourceModelo
			? sourceFamily.modelos.findIndex((m) => m.sku === sourceModelo.sku)
			: undefined;
		if (!absorbAll && modeloIdx === undefined) return;

		busy = true;
		try {
			const args: MoveModeloArgs = {
				sourceFid: sourceFamily.id,
				sourceModeloIdx: absorbAll ? undefined : modeloIdx,
				targetFid: selectedTargetFid,
				absorbAll
			};
			const result = await adapter.moveModelo(args);
			if (result.ok) {
				const moveMsg = absorbAll ? `${result.moved} modelos absorbidos` : 'modelo movido';
				const migCount = result.migrated
					? result.migrated.audit_decisions + result.migrated.audit_photo_actions
					: 0;
				onFlash(
					`✓ ${moveMsg} → ${result.target_fid}${migCount ? ` · ${migCount} rows migradas` : ''}`
				);
				if (result.new_skus.length > 0) onSelectSku(result.new_skus[0]);
				await invalidateAll();
				onClose();
			} else {
				onFlash(`✗ Move falló: ${result.error ?? 'unknown'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash('Move: requiere .exe');
			else onFlash(`Move falló: ${err instanceof Error ? err.message : err}`);
		} finally {
			busy = false;
		}
	}

	async function handleMoveToNew() {
		if (!sourceFamily || busy) return;
		if (!newTeam.trim() || !newSeason.trim()) {
			onFlash('Team y Season son requeridos');
			return;
		}
		const modeloIdx = sourceModelo
			? sourceFamily.modelos.findIndex((m) => m.sku === sourceModelo.sku)
			: undefined;
		if (!absorbAll && modeloIdx === undefined) return;

		busy = true;
		try {
			const args: MoveModeloArgs = {
				sourceFid: sourceFamily.id,
				sourceModeloIdx: absorbAll ? undefined : modeloIdx,
				newFamily: {
					team: newTeam.trim(),
					season: newSeason.trim(),
					variant: newVariant,
					category: newCategory
				},
				absorbAll
			};
			const result = await adapter.moveModelo(args);
			if (result.ok) {
				const moveMsg = absorbAll ? `${result.moved} modelos` : 'modelo';
				onFlash(`✓ ${moveMsg} movidos a family nueva ${result.target_fid}`);
				if (result.new_skus.length > 0) onSelectSku(result.new_skus[0]);
				await invalidateAll();
				onClose();
			} else {
				onFlash(`✗ Create+Move falló: ${result.error ?? 'unknown'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash('Move: requiere .exe');
			else onFlash(`Move falló: ${err instanceof Error ? err.message : err}`);
		} finally {
			busy = false;
		}
	}

	function handleKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKey} />

{#if open && sourceFamily}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
		onclick={onClose}
		onkeydown={(e) => e.key === 'Escape' && onClose()}
		role="dialog"
		tabindex="-1"
		aria-label="Mover modelo"
	>
		<div
			class="flex max-h-[90vh] w-[640px] max-w-[95vw] flex-col overflow-hidden rounded-[8px] border border-[var(--color-border-strong)] bg-[var(--color-surface-1)] shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="presentation"
		>
			<!-- Header -->
			<header
				class="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] px-5 py-3"
			>
				<div class="flex flex-col">
					<span class="text-display text-[13px] text-[var(--color-text-primary)]">
						{absorbAll
							? `Absorber family entera`
							: sourceModelo
								? `Mover modelo`
								: `Mover`}
					</span>
					<span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">
						{#if absorbAll}
							{sourceFamily.id} ({sourceFamily.modelos.length} modelos) → ?
						{:else if sourceModelo}
							{sourceModelo.sku} · {sourceFamily.id} → ?
						{/if}
					</span>
				</div>
				<button
					type="button"
					onclick={onClose}
					class="flex h-8 w-8 items-center justify-center rounded-[4px] text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
				>
					<X size={16} strokeWidth={1.8} />
				</button>
			</header>

			<!-- Tabs -->
			<div class="flex shrink-0 border-b border-[var(--color-border)]">
				<button
					type="button"
					onclick={() => (tab = 'existing')}
					class="flex-1 px-4 py-2.5 text-[11.5px] font-medium transition-colors"
					class:text-[var(--color-accent)]={tab === 'existing'}
					class:text-[var(--color-text-secondary)]={tab !== 'existing'}
					class:border-b-2={tab === 'existing'}
					class:border-[var(--color-accent)]={tab === 'existing'}
				>
					<Search size={12} strokeWidth={2} class="inline mr-1.5" />
					Family existente
				</button>
				<button
					type="button"
					onclick={() => (tab = 'new')}
					class="flex-1 px-4 py-2.5 text-[11.5px] font-medium transition-colors"
					class:text-[var(--color-accent)]={tab === 'new'}
					class:text-[var(--color-text-secondary)]={tab !== 'new'}
					class:border-b-2={tab === 'new'}
					class:border-[var(--color-accent)]={tab === 'new'}
				>
					<Plus size={12} strokeWidth={2} class="inline mr-1.5" />
					Crear family nueva
				</button>
			</div>

			<!-- Absorb checkbox -->
			{#if sourceFamily.modelos.length > 1}
				<div class="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-bg)]/40 px-5 py-2.5">
					<label class="flex items-start gap-2 text-[11.5px] cursor-pointer">
						<input type="checkbox" bind:checked={absorbAll} class="mt-0.5" />
						<span>
							<span class="font-medium text-[var(--color-text-primary)]">Absorber TODOS los modelos</span>
							<span class="block text-[10.5px] text-[var(--color-text-tertiary)]">
								Mueve los {sourceFamily.modelos.length} modelos de <span class="text-mono">{sourceFamily.id}</span> al target.
								Útil si toda la family fue mal scraped.
							</span>
						</span>
					</label>
				</div>
			{/if}

			<!-- Body — varía por tab -->
			<div class="flex-1 overflow-auto p-5">
				{#if tab === 'existing'}
					<div class="mb-3">
						<label class="text-display mb-1.5 block text-[9.5px] text-[var(--color-text-tertiary)]">
							Buscar family destino
						</label>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="team, season, variant..."
							class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-[12px] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
						/>
					</div>
					<div
						class="max-h-[320px] overflow-y-auto rounded-[4px] border border-[var(--color-border)]"
					>
						{#each filteredTargets as f (f.id)}
							<button
								type="button"
								onclick={() => (selectedTargetFid = f.id)}
								class="group flex w-full items-center gap-2.5 border-b border-[var(--color-border)]/50 px-3 py-2 text-left transition-colors last:border-0 hover:bg-[var(--color-surface-2)]"
								class:bg-[var(--color-accent-soft)]={selectedTargetFid === f.id}
							>
								{#if f.flagIso}
									<img src="/flags/{f.flagIso}.svg" alt="" class="h-3.5 w-5 shrink-0 rounded-[2px]" />
								{/if}
								<span class="flex-1 text-[12px] text-[var(--color-text-primary)]">
									{f.team} · {f.season} · {f.variantLabel}
								</span>
								<span class="text-mono text-[10px] text-[var(--color-text-tertiary)]">
									{f.id}
								</span>
							</button>
						{:else}
							<div class="px-3 py-6 text-center text-[11px] text-[var(--color-text-tertiary)]">
								Sin matches. Usá "Crear family nueva" si el target no existe.
							</div>
						{/each}
					</div>
				{:else}
					<!-- New family form -->
					<div class="grid grid-cols-[100px_1fr] gap-x-3 gap-y-2 text-[12px]">
						<label class="py-1 text-[var(--color-text-tertiary)]" for="new-team">Team</label>
						<input
							id="new-team"
							type="text"
							bind:value={newTeam}
							placeholder="e.g. Argentina"
							class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none"
						/>

						<label class="py-1 text-[var(--color-text-tertiary)]" for="new-season">Season</label>
						<input
							id="new-season"
							type="text"
							bind:value={newSeason}
							placeholder="e.g. 2026 o 25-26"
							class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none"
						/>

						<label class="py-1 text-[var(--color-text-tertiary)]" for="new-variant">Variant</label>
						<select
							id="new-variant"
							bind:value={newVariant}
							class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none"
						>
							{#each VARIANT_OPTIONS as opt (opt.value)}
								<option value={opt.value}>{opt.label}</option>
							{/each}
						</select>

						<label class="py-1 text-[var(--color-text-tertiary)]" for="new-category">Category</label>
						<select
							id="new-category"
							bind:value={newCategory}
							class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none"
						>
							<option value="adult">adult</option>
							<option value="women">women</option>
							<option value="kids">kids</option>
							<option value="baby">baby</option>
							<option value="training">training</option>
							<option value="polo">polo</option>
							<option value="jacket">jacket</option>
							<option value="other">other</option>
						</select>
					</div>

					<div
						class="mt-4 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg)]/40 p-2.5 text-[10.5px] text-[var(--color-text-tertiary)]"
					>
						family_id se generará como:
						<span class="text-mono text-[var(--color-accent)]">
							{(newTeam.toLowerCase().replace(/\s+/g, '-') || 'team')}-{newSeason
								.replace(/\//g, '-')
								.replace(/\s+/g, '-') || 'season'}-{newVariant}
						</span>
					</div>
				{/if}
			</div>

			<!-- Footer actions -->
			<footer
				class="flex shrink-0 items-center justify-between gap-2 border-t border-[var(--color-border)] px-5 py-3"
			>
				<div class="text-[10.5px] text-[var(--color-text-tertiary)]">
					SKU se regenera automáticamente al mover
				</div>
				<div class="flex gap-2">
					<button
						type="button"
						onclick={onClose}
						class="rounded-[4px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						Cancelar
					</button>
					{#if tab === 'existing'}
						<button
							type="button"
							disabled={!selectedTargetFid || busy}
							onclick={handleMoveToExisting}
							class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-accent)]/40 bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-medium text-white transition-colors hover:opacity-90 disabled:opacity-40"
						>
							{#if busy}
								<Loader2 size={12} strokeWidth={1.8} class="animate-spin" />
								Moviendo…
							{:else}
								<ArrowRight size={12} strokeWidth={1.8} />
								Mover
							{/if}
						</button>
					{:else}
						<button
							type="button"
							disabled={!newTeam.trim() || !newSeason.trim() || busy}
							onclick={handleMoveToNew}
							class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-accent)]/40 bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-medium text-white transition-colors hover:opacity-90 disabled:opacity-40"
						>
							{#if busy}
								<Loader2 size={12} strokeWidth={1.8} class="animate-spin" />
								Creando…
							{:else}
								<Plus size={12} strokeWidth={1.8} />
								Crear + Mover
							{/if}
						</button>
					{/if}
				</div>
			</footer>
		</div>
	</div>
{/if}
