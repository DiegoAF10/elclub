<script lang="ts">
	import type { Family, Modelo } from '$lib/data/types';
	import {
		ExternalLink,
		Copy,
		Star,
		Eye,
		EyeOff,
		Archive,
		Upload,
		Shuffle,
		Trash2,
		ChevronRight,
		Crown
	} from 'lucide-svelte';
	import StatusBadge from './StatusBadge.svelte';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';

	interface Props {
		family: Family;
		onSelectSku?: (sku: string) => void;
		onFlash?: (msg: string) => void;
		onRefresh?: () => void;
	}

	let {
		family,
		onSelectSku = () => {},
		onFlash = () => {},
		onRefresh = () => {}
	}: Props = $props();

	async function handleSetPrimary(modeloIdx: number) {
		if (family.primaryModeloIdx === modeloIdx) {
			onFlash('Este modelo ya es primary');
			return;
		}
		try {
			await adapter.setPrimaryModeloIdx(family.id, modeloIdx);
			const m = family.modelos[modeloIdx];
			onFlash(`✓ Primary → ${m?.sku ?? `modelo[${modeloIdx}]`}`);
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash('Set primary: requiere .exe');
			else onFlash(`Set primary falló: ${err instanceof Error ? err.message : err}`);
		}
	}

	let deleteState = $state<'idle' | 'busy'>('idle');

	async function handleDeleteFamily() {
		if (deleteState === 'busy') return;

		// Guard 1: published=true es sagrado. UI block antes del Python check.
		if (family.published) {
			onFlash(
				`✗ Family ${family.id} está publicada — despublicar primero (toggle en SPECS), después borrar`
			);
			return;
		}

		const modelosCount = family.modelos.length;
		const summary = modelosCount === 0
			? `${family.id} (vacío)`
			: `${family.id} con ${modelosCount} modelo${modelosCount === 1 ? '' : 's'}`;

		const confirmed = window.confirm(
			`Borrar family completa: ${summary}?\n\n` +
				`Esto:\n` +
				`  • Marca audit_decisions.status='deleted' para cada SKU\n` +
				`  • Inserta row en audit_delete_log con tu motivo\n` +
				`  • Borra modelos[] del catalog.json\n` +
				`  • Commit + push automático al vault\n\n` +
				`Las families published=true NO se borran (sagrado).`
		);
		if (!confirmed) return;

		const motivo = window.prompt(
			`Motivo del delete (requerido):\n\n` +
				`Ej. "duplicado de mexico-2026-home", "scrape-error: no es México",\n` +
				`"family vacía sin valor para audit"`,
			''
		);
		if (motivo === null) return; // Cancel
		if (!motivo.trim()) {
			onFlash('✗ Delete cancelado: motivo requerido');
			return;
		}

		deleteState = 'busy';
		onFlash(`🗑 Borrando ${family.id}…`);
		try {
			const result = await adapter.deleteFamily(family.id, motivo.trim());
			if (result.ok) {
				const skus = result.deletedSkus.length;
				const committed = result.committed ? ' · pushed al vault' : '';
				const pushFail = result.pushError ? ` · push falló: ${result.pushError}` : '';
				onFlash(`✓ Family ${family.id} borrada (${skus} SKU${skus === 1 ? '' : 's'})${committed}${pushFail}`);
				onRefresh();
			} else {
				onFlash(`✗ Delete falló: ${result.error ?? 'error desconocido'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Delete family: requiere el .exe');
			} else {
				onFlash(`Delete falló: ${err instanceof Error ? err.message : err}`);
			}
		} finally {
			deleteState = 'idle';
		}
	}

	const MODELO_LABEL: Record<string, string> = {
		fan_adult: 'Fan adulto',
		player_adult: 'Player adulto',
		retro_adult: 'Retro',
		woman: 'Mujer',
		kid: 'Niño',
		baby: 'Bebé',
		goalkeeper: 'Goalkeeper'
	};
	const SLEEVE_LABEL: Record<string, string> = { short: 'Manga corta', long: 'Manga larga' };

	// Primary modelo = el que se muestra como card principal del family en el vault.
	// Orden de preferencia:
	//   1. family.primaryModeloIdx (seteado explícitamente por Diego vía Crown click)
	//   2. primer modelo 'live'
	//   3. primer modelo 'ready'
	//   4. modelos[0]
	let primaryModelo = $derived.by<Modelo | null>(() => {
		if (family.modelos.length === 0) return null;
		if (
			typeof family.primaryModeloIdx === 'number' &&
			family.primaryModeloIdx >= 0 &&
			family.primaryModeloIdx < family.modelos.length
		) {
			return family.modelos[family.primaryModeloIdx];
		}
		const live = family.modelos.find((m) => m.status === 'live');
		if (live) return live;
		const ready = family.modelos.find((m) => m.status === 'ready');
		if (ready) return ready;
		return family.modelos[0];
	});

	// Tab state — qué modelo está highlighted en el grid de siblings
	let previewSku = $state<string | null>(null);

	// Al cambiar de family, resetear previewSku
	$effect(() => {
		if (family) previewSku = primaryModelo?.sku ?? null;
	});

	let viewedModelo = $derived.by(() => {
		if (!previewSku) return primaryModelo;
		return family.modelos.find((m) => m.sku === previewSku) || primaryModelo;
	});

	let heroPhoto = $derived(viewedModelo?.fotos.find((p) => p.isHero) || viewedModelo?.fotos[0]);

	let familyReady = $derived.by(() => {
		const total = family.modelos.length;
		const verified = family.modelos.filter(
			(m) => m.status === 'live' || m.status === 'ready'
		).length;
		return { ready: total > 0 && verified === total, total, verified };
	});

	function modeloDesc(m: Modelo): string {
		const base = MODELO_LABEL[m.modeloType] || m.modeloType;
		if (m.sleeve && (m.modeloType === 'fan_adult' || m.modeloType === 'player_adult')) {
			return `${base} · ${SLEEVE_LABEL[m.sleeve] || m.sleeve}`;
		}
		return base;
	}

	async function copyToClipboard(text: string) {
		try {
			await navigator.clipboard.writeText(text);
		} catch (e) {
			console.error('clipboard', e);
		}
	}
</script>

<section class="flex h-full flex-1 flex-col bg-[var(--color-bg)]">
	<!-- Header family-level -->
	<header
		class="ui-chrome flex h-16 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-6"
	>
		<div class="flex items-center gap-3">
			{#if family.flagIso}
				<img
					src="/flags/{family.flagIso}.svg"
					alt=""
					class="h-8 w-11 rounded-[3px] shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
				/>
			{/if}
			<div class="flex flex-col gap-0.5">
				<div class="flex items-center gap-2.5">
					<span class="text-[15px] font-semibold text-[var(--color-text-primary)]">
						{family.team}
						<span class="text-[var(--color-text-tertiary)]">·</span>
						{family.season}
						<span class="text-[var(--color-text-tertiary)]">·</span>
						{family.variantLabel}
					</span>
					{#if family.published}
						<span
							class="text-display flex items-center gap-1 rounded-[3px] bg-[var(--color-live)]/15 px-1.5 py-0.5 text-[9.5px] text-[var(--color-live)]"
						>
							<span class="h-1.5 w-1.5 rounded-full bg-[var(--color-live)] glow-live"></span>
							LIVE
						</span>
					{/if}
					{#if family.featured}
						<span
							class="text-display flex items-center gap-1 rounded-[3px] bg-[var(--color-warning)]/15 px-1.5 py-0.5 text-[9.5px] text-[var(--color-warning)]"
						>
							<Star size={9} strokeWidth={2.2} fill="currentColor" />
							TOP
						</span>
					{/if}
				</div>
				<div class="flex items-center gap-2 text-[10.5px] text-[var(--color-text-tertiary)]">
					<span class="text-mono font-semibold text-[var(--color-text-secondary)]">
						{family.id}
					</span>
					<span class="text-[var(--color-text-muted)]">·</span>
					<span>Grupo {family.group}</span>
					<span class="text-[var(--color-text-muted)]">·</span>
					<span>{family.modelos.length} variantes</span>
				</div>
			</div>
		</div>
		<div class="flex items-center gap-1.5">
			<button
				type="button"
				onclick={() => copyToClipboard(family.id)}
				class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
			>
				<Copy size={12} strokeWidth={1.8} />
				family_id
			</button>
			<button
				type="button"
				class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)]"
			>
				<ExternalLink size={12} strokeWidth={1.8} />
				Ver en PDP live
			</button>
		</div>
	</header>

	<!-- Scroll body -->
	<div class="flex-1 overflow-y-auto">
		<!-- Hero + side info split -->
		<div class="grid grid-cols-[1fr_340px] gap-6 border-b border-[var(--color-border)] px-6 py-5">
			<!-- Hero photo grande -->
			<div>
				{#if heroPhoto}
					<div
						class="aspect-square overflow-hidden rounded-[6px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
					>
						<img src={heroPhoto.url} alt="" class="h-full w-full object-cover" />
					</div>
				{:else}
					<div
						class="flex aspect-square items-center justify-center rounded-[6px] border border-dashed border-[var(--color-border)] text-[12px] text-[var(--color-text-tertiary)]"
					>
						Sin fotos
					</div>
				{/if}
			</div>

			<!-- PDP-style info panel -->
			<div class="flex flex-col gap-5">
				<!-- Title / hero -->
				<div>
					<div class="text-display mb-1 text-[9.5px] text-[var(--color-text-tertiary)]">
						Current variant
					</div>
					{#if viewedModelo}
						<div class="text-[14.5px] font-semibold text-[var(--color-text-primary)]">
							{modeloDesc(viewedModelo)}
						</div>
						<div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">
							{viewedModelo.sku}
						</div>
					{/if}
				</div>

				<!-- Price + sizes -->
				<div class="flex items-baseline gap-3 border-b border-[var(--color-border)] pb-4">
					{#if viewedModelo?.price}
						<span class="text-mono text-[22px] font-semibold text-[var(--color-text-primary)]">
							Q{viewedModelo.price}
						</span>
					{/if}
					{#if viewedModelo?.sizes}
						<span class="text-[11px] text-[var(--color-text-tertiary)]">
							· tallas {viewedModelo.sizes}
						</span>
					{/if}
				</div>

				<!-- Modelo selector (variants del family) -->
				<div>
					<div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">
						Variants · {family.modelos.length}
					</div>
					<div class="flex flex-col gap-1">
						{#each family.modelos as m, mIdx (m.sku)}
							<div
								class="group relative flex w-full items-center gap-2.5 rounded-[4px] border transition-all"
								class:border-[var(--color-accent)]={previewSku === m.sku}
								class:bg-[var(--color-accent-soft)]={previewSku === m.sku}
								class:border-[var(--color-border)]={previewSku !== m.sku}
								class:bg-[var(--color-surface-1)]={previewSku !== m.sku}
								class:hover:border-[var(--color-border-strong)]={previewSku !== m.sku}
								onmouseenter={() => (previewSku = m.sku)}
								role="presentation"
							>
								<!-- Crown: click = set como primary del family -->
								<button
									type="button"
									onclick={(e) => {
										e.stopPropagation();
										void handleSetPrimary(mIdx);
									}}
									title={m === primaryModelo
										? 'Primary · card principal del family en el vault'
										: 'Click para hacer este modelo el primary del family'}
									class="ml-2.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[3px] transition-all"
									class:bg-[var(--color-accent)]={m === primaryModelo}
									class:text-white={m === primaryModelo}
									class:bg-transparent={m !== primaryModelo}
									class:text-[var(--color-text-muted)]={m !== primaryModelo}
									class:opacity-0={m !== primaryModelo}
									class:group-hover:opacity-100={m !== primaryModelo}
									class:hover:bg-[var(--color-accent-soft)]={m !== primaryModelo}
									class:hover:text-[var(--color-accent)]={m !== primaryModelo}
								>
									<Crown size={11} strokeWidth={2.2} />
								</button>
								<button
									type="button"
									onclick={() => onSelectSku(m.sku)}
									class="flex flex-1 items-center gap-2.5 py-2 pr-2.5 text-left"
								>
								<div class="flex flex-1 flex-col gap-0.5">
									<div class="flex items-center gap-2">
										<span
											class="text-[12px] font-medium"
											class:text-[var(--color-text-primary)]={previewSku === m.sku}
											class:text-[var(--color-text-secondary)]={previewSku !== m.sku}
										>
											{modeloDesc(m)}
										</span>
									</div>
									<div class="flex items-center gap-2 text-[10px] text-[var(--color-text-tertiary)]">
										<span class="text-mono tabular-nums">{m.sku}</span>
										<span>·</span>
										<span>{m.fotos.length} fotos</span>
										{#if m.price}
											<span>·</span>
											<span class="text-mono">Q{m.price}</span>
										{/if}
									</div>
								</div>
									<StatusBadge status={m.status} size="xs" />
									<ChevronRight
										size={11}
										strokeWidth={1.8}
										class="text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
									/>
								</button>
							</div>
						{/each}
					</div>
					<div class="mt-2 text-[10px] text-[var(--color-text-muted)]">
						Hover = preview · click = abrir audit del modelo
					</div>
				</div>
			</div>
		</div>

		<!-- Family-level actions -->
		<div class="border-b border-[var(--color-border)] px-6 py-4">
			<div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">
				Family actions
			</div>
			<div class="flex flex-wrap items-center gap-1.5">
				{#if familyReady.ready}
					<button
						type="button"
						class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-terminal)] px-3 py-1.5 text-[11.5px] font-semibold text-black transition-all hover:brightness-110"
						style="box-shadow: 0 0 0 1px rgba(74, 222, 128, 0.4), 0 0 12px rgba(74, 222, 128, 0.15);"
					>
						<Upload size={13} strokeWidth={2.5} />
						Re-publicar + Push
					</button>
				{:else}
					<span
						class="rounded-[4px] border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-warning)]"
					>
						{familyReady.verified}/{familyReady.total} verificados — faltan {familyReady.total -
							familyReady.verified}
					</span>
				{/if}
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
				>
					{#if family.published}
						<EyeOff size={13} strokeWidth={1.8} />
						Ocultar del vault
					{:else}
						<Eye size={13} strokeWidth={1.8} />
						Publicar
					{/if}
				</button>
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-warning)] transition-colors hover:border-[var(--color-warning)]/60 hover:bg-[var(--color-warning)]/20"
				>
					<Star
						size={13}
						strokeWidth={1.8}
						fill={family.featured ? 'currentColor' : 'none'}
					/>
					{family.featured ? 'Unfeature' : 'Featured TOP'}
				</button>
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-info)]/30 bg-[var(--color-info)]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-info)] transition-colors hover:border-[var(--color-info)]/60 hover:bg-[var(--color-info)]/20"
				>
					<Shuffle size={13} strokeWidth={1.8} />
					Merge con otra
				</button>
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)]"
				>
					<Archive size={13} strokeWidth={1.8} />
					Archivar
				</button>
				<button
					type="button"
					onclick={handleDeleteFamily}
					disabled={deleteState === 'busy' || family.published}
					title={family.published
						? 'Family publicada — despublicar primero (sagrado)'
						: 'Borrar family entera (motivo requerido)'}
					class="ml-auto flex items-center gap-1.5 rounded-[4px] border border-[var(--color-flagged)]/30 bg-[var(--color-flagged)]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-flagged)] transition-colors hover:border-[var(--color-flagged)]/60 hover:bg-[var(--color-flagged)]/20 disabled:cursor-not-allowed disabled:opacity-40"
				>
					<Trash2 size={13} strokeWidth={1.8} />
					{deleteState === 'busy' ? 'Borrando…' : 'Delete family'}
				</button>
			</div>
		</div>

		<!-- Resumen de fotos por variant -->
		<div class="px-6 py-4">
			<div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">
				Resumen de galerías
			</div>
			<div class="flex flex-col gap-3">
				{#each family.modelos as m (m.sku)}
					<div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3">
						<div class="mb-2 flex items-center justify-between">
							<div class="flex items-center gap-2">
								<span class="text-mono text-[10px] font-semibold text-[var(--color-text-tertiary)]">
									{m.sku}
								</span>
								<span class="text-[11.5px] font-medium text-[var(--color-text-primary)]">
									{modeloDesc(m)}
								</span>
								<StatusBadge status={m.status} size="xs" />
							</div>
							<button
								type="button"
								onclick={() => onSelectSku(m.sku)}
								class="flex items-center gap-1 rounded-[3px] px-2 py-0.5 text-[10.5px] font-medium text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]"
							>
								Abrir audit
								<ChevronRight size={11} strokeWidth={1.8} />
							</button>
						</div>
						{#if m.fotos.length === 0}
							<div
								class="text-[10.5px] italic text-[var(--color-text-tertiary)]"
							>
								Sin fotos
							</div>
						{:else}
							<div class="flex gap-1 overflow-x-auto">
								{#each m.fotos.slice(0, 8) as f (f.id)}
									<div
										class="relative h-16 w-16 shrink-0 overflow-hidden rounded-[3px] border border-[var(--color-border)]"
									>
										<img
											src={f.url}
											alt=""
											loading="lazy"
											fetchpriority="low"
											class="h-full w-full object-cover"
										/>
										{#if f.isHero}
											<span
												class="absolute top-0.5 right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-[2px] bg-[var(--color-accent)]/95 text-white"
											>
												<Crown size={8} strokeWidth={2.2} />
											</span>
										{/if}
									</div>
								{/each}
								{#if m.fotos.length > 8}
									<div
										class="flex h-16 w-16 shrink-0 items-center justify-center rounded-[3px] border border-dashed border-[var(--color-border)] text-[10px] text-[var(--color-text-tertiary)]"
									>
										+{m.fotos.length - 8}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	</div>
</section>
