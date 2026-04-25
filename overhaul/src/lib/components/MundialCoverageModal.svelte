<script lang="ts">
	import type { Family, Modelo } from '$lib/data/types';
	import { TEAM_TO_GROUP, TEAM_TO_ISO } from '$lib/adapter/transform';
	import { X, Check, Circle, CheckCircle2, ChevronRight, ChevronDown } from 'lucide-svelte';

	interface Props {
		open: boolean;
		families: Family[];
		onClose: () => void;
		onSelectFamily?: (fid: string) => void;
	}

	let { open, families, onClose, onSelectFamily = () => {} }: Props = $props();

	// Variantes a rastrear (orden visual)
	const VARIANTS = [
		{ key: 'home', label: 'Local' },
		{ key: 'away', label: 'Visita' },
		{ key: 'third', label: 'Tercera' },
		{ key: 'goalkeeper', label: 'Portero' },
		{ key: 'special', label: 'Especial' },
		{ key: 'training', label: 'Entreno' }
	];

	// Slots de modelo que esperamos en variants genéricas (Local/Visita/Tercera/Especial)
	// Para Portero: solo GK variants. Para Entreno: solo training.
	type ModeloSlot = {
		key: string;
		label: string;
		type: string;
		sleeve?: 'short' | 'long' | null;
	};
	const GENERIC_SLOTS: ModeloSlot[] = [
		{ key: 'fan_s', label: 'Fan M/C', type: 'fan_adult', sleeve: 'short' },
		{ key: 'fan_l', label: 'Fan M/L', type: 'fan_adult', sleeve: 'long' },
		{ key: 'player_s', label: 'Player M/C', type: 'player_adult', sleeve: 'short' },
		{ key: 'player_l', label: 'Player M/L', type: 'player_adult', sleeve: 'long' },
		{ key: 'woman', label: 'Mujer', type: 'woman' },
		{ key: 'kid', label: 'Niño', type: 'kid' },
		{ key: 'baby', label: 'Bebé', type: 'baby' }
	];
	const GOALKEEPER_SLOTS: ModeloSlot[] = [
		{ key: 'gk_s', label: 'GK M/C', type: 'goalkeeper', sleeve: 'short' },
		{ key: 'gk_l', label: 'GK M/L', type: 'goalkeeper', sleeve: 'long' }
	];
	const TRAINING_SLOTS: ModeloSlot[] = [
		{ key: 'training', label: 'Training', type: 'training' }
	];

	function slotsForVariant(variantKey: string): ModeloSlot[] {
		if (variantKey === 'goalkeeper') return GOALKEEPER_SLOTS;
		if (variantKey === 'training') return TRAINING_SLOTS;
		return GENERIC_SLOTS;
	}

	// ─── Normalización de teams (dedup aliases) ──────────────────────────
	// TEAM_TO_GROUP tiene "Bosnia and Herzegovina" y "Bosnia & Herzegovina" como keys
	// separadas pero representan al mismo team. Normalizamos a un canonical name.
	const TEAM_ALIASES: Record<string, string> = {
		'Bosnia and Herzegovina': 'Bosnia & Herzegovina',
		USA: 'United States'
	};
	function canonicalTeam(t: string): string {
		return TEAM_ALIASES[t] || t;
	}

	// ─── Expansion state ──────────────────────────────────────────────────
	let expanded = $state<Set<string>>(new Set());
	function toggleExpand(team: string) {
		const next = new Set(expanded);
		if (next.has(team)) next.delete(team);
		else next.add(team);
		expanded = next;
	}

	type CoverageRow = {
		team: string;
		group: string;
		flagIso?: string;
		// byVariant: family principal publicada (si hay) o draft (si hay)
		byVariant: Record<string, Family | null>;
		// byVariantSlot[variantKey][slotKey] = Modelo | null
		byVariantSlot: Record<string, Record<string, { modelo: Modelo; family: Family } | null>>;
		// stats
		totalSlots: number;
		publishedSlots: number;
		draftSlots: number;
	};

	function findSlot(modelos: Modelo[], slot: ModeloSlot): Modelo | null {
		return (
			modelos.find((m) => {
				if (m.modeloType !== slot.type) return false;
				if (slot.sleeve === undefined) return true; // slot sin sleeve requerido
				return (m.sleeve ?? null) === slot.sleeve;
			}) ?? null
		);
	}

	let coverage = $derived.by<CoverageRow[]>(() => {
		// Dedupe teams canónicamente
		const canonicalGroups = new Map<string, string>();
		const canonicalFlags = new Map<string, string | undefined>();
		for (const [raw, group] of Object.entries(TEAM_TO_GROUP)) {
			const canon = canonicalTeam(raw);
			if (!canonicalGroups.has(canon)) {
				canonicalGroups.set(canon, group);
				canonicalFlags.set(canon, TEAM_TO_ISO[raw] ?? TEAM_TO_ISO[canon]);
			}
		}

		const teams = [...canonicalGroups.keys()].sort((a, b) => {
			const ga = canonicalGroups.get(a)!;
			const gb = canonicalGroups.get(b)!;
			if (ga !== gb) return ga.localeCompare(gb);
			return a.localeCompare(b);
		});

		// Index families por (canonicalTeam, variant) — preferimos published
		const idx = new Map<string, Family>();
		for (const fam of families) {
			if (!fam.season || !fam.season.includes('2026')) continue;
			const canon = canonicalTeam(fam.team);
			const key = `${canon}|${fam.variant}`;
			const existing = idx.get(key);
			if (!existing || (!existing.published && fam.published)) {
				idx.set(key, fam);
			}
		}

		return teams.map((team) => {
			const byVariant: Record<string, Family | null> = {};
			const byVariantSlot: Record<
				string,
				Record<string, { modelo: Modelo; family: Family } | null>
			> = {};

			let totalSlots = 0;
			let publishedSlots = 0;
			let draftSlots = 0;

			for (const v of VARIANTS) {
				const fam = idx.get(`${team}|${v.key}`) ?? null;
				byVariant[v.key] = fam;
				const slots = slotsForVariant(v.key);
				byVariantSlot[v.key] = {};
				for (const slot of slots) {
					totalSlots++;
					if (!fam) {
						byVariantSlot[v.key][slot.key] = null;
						continue;
					}
					const modelo = findSlot(fam.modelos, slot);
					if (!modelo) {
						byVariantSlot[v.key][slot.key] = null;
						continue;
					}
					byVariantSlot[v.key][slot.key] = { modelo, family: fam };
					if (fam.published) publishedSlots++;
					else draftSlots++;
				}
			}

			return {
				team,
				group: canonicalGroups.get(team)!,
				flagIso: canonicalFlags.get(team),
				byVariant,
				byVariantSlot,
				totalSlots,
				publishedSlots,
				draftSlots
			};
		});
	});

	let stats = $derived.by(() => {
		const totalTeams = coverage.length;
		let teamsWithAnyPublished = 0;
		let totalPublishedSlots = 0;
		let totalDraftSlots = 0;
		for (const row of coverage) {
			if (row.publishedSlots > 0) teamsWithAnyPublished++;
			totalPublishedSlots += row.publishedSlots;
			totalDraftSlots += row.draftSlots;
		}
		return { totalTeams, teamsWithAnyPublished, totalPublishedSlots, totalDraftSlots };
	});

	let byGroup = $derived.by(() => {
		const map = new Map<string, CoverageRow[]>();
		for (const row of coverage) {
			if (!map.has(row.group)) map.set(row.group, []);
			map.get(row.group)!.push(row);
		}
		return map;
	});

	function handleCellClick(fam: Family | null | undefined) {
		if (fam) {
			onSelectFamily(fam.id);
			onClose();
		}
	}

	function handleKey(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			onClose();
		}
	}

	// Estado global de un slot: 'live' (pub) / 'draft' (no pub) / 'missing'
	function slotStatus(
		cell: { modelo: Modelo; family: Family } | null
	): 'live' | 'draft' | 'missing' {
		if (!cell) return 'missing';
		return cell.family.published ? 'live' : 'draft';
	}

	// Clases Tailwind por status del slot (evita class: directive con slashes)
	function chipClasses(status: 'live' | 'draft' | 'missing'): string {
		const base = 'flex items-center gap-1 rounded-[4px] border px-2 py-1 text-[10px] font-medium transition-colors';
		if (status === 'live') {
			return `${base} border-[var(--color-live)]/40 bg-[var(--color-live)]/15 text-[var(--color-live)] hover:bg-[var(--color-live)]/30`;
		}
		if (status === 'draft') {
			return `${base} border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 text-[var(--color-warning)] hover:bg-[var(--color-warning)]/25`;
		}
		return `${base} border-[var(--color-border)] bg-transparent text-[var(--color-text-muted)] opacity-50 cursor-not-allowed`;
	}
</script>

<svelte:window onkeydown={handleKey} />

{#if open}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/80 backdrop-blur-sm"
		onclick={onClose}
		onkeydown={(e) => e.key === 'Escape' && onClose()}
		role="dialog"
		tabindex="-1"
		aria-label="Coverage Mundial 2026"
	>
		<div
			class="flex max-h-[92vh] w-[980px] max-w-[96vw] flex-col overflow-hidden rounded-[8px] border border-[var(--color-border-strong)] bg-[var(--color-surface-1)] shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="presentation"
		>
			<!-- Header -->
			<header
				class="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] px-5 py-3"
			>
				<div class="flex items-center gap-3">
					<span class="text-display text-[13px] text-[var(--color-text-primary)]"
						>Mundial 2026 · Coverage</span
					>
					<span
						class="text-mono rounded-[3px] bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-text-secondary)] tabular-nums"
					>
						{stats.teamsWithAnyPublished}/{stats.totalTeams} teams con algo
					</span>
					<span
						class="text-mono rounded-[3px] bg-[var(--color-live)]/20 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-live)] tabular-nums"
						title="Slots de modelo publicados"
					>
						{stats.totalPublishedSlots} pub
					</span>
					{#if stats.totalDraftSlots > 0}
						<span
							class="text-mono rounded-[3px] bg-[var(--color-warning)]/20 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-warning)] tabular-nums"
							title="Slots en audit queue (draft)"
						>
							{stats.totalDraftSlots} draft
						</span>
					{/if}
				</div>
				<button
					type="button"
					onclick={onClose}
					class="flex h-8 w-8 items-center justify-center rounded-[4px] text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					title="Cerrar (ESC)"
				>
					<X size={16} strokeWidth={1.8} />
				</button>
			</header>

			<!-- Table -->
			<div class="flex-1 overflow-auto">
				<table class="w-full border-collapse text-[11px]">
					<thead
						class="text-display sticky top-0 z-10 bg-[var(--color-surface-2)] text-[9.5px] text-[var(--color-text-tertiary)]"
					>
						<tr>
							<th class="border-b border-[var(--color-border)] px-3 py-2 text-left" colspan="2"
								>Team</th
							>
							{#each VARIANTS as v (v.key)}
								<th
									class="border-b border-[var(--color-border)] px-3 py-2 text-center tabular-nums"
									>{v.label}</th
								>
							{/each}
							<th
								class="border-b border-[var(--color-border)] px-3 py-2 text-right text-[9px]"
							>
								Slots
							</th>
						</tr>
					</thead>
					<tbody>
						{#each [...byGroup] as [groupLetter, rows] (groupLetter)}
							<tr>
								<td
									colspan={3 + VARIANTS.length}
									class="bg-[var(--color-bg)] px-3 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-tertiary)]"
								>
									Grupo {groupLetter}
								</td>
							</tr>
							{#each rows as row (row.team)}
								{@const isExpanded = expanded.has(row.team)}
								<tr
									class="border-b border-[var(--color-border)]/40 transition-colors hover:bg-[var(--color-surface-2)]/60"
								>
									<!-- Expand chevron -->
									<td class="w-6 px-1 py-2 text-center">
										<button
											type="button"
											onclick={() => toggleExpand(row.team)}
											class="flex h-5 w-5 items-center justify-center rounded-[3px] text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
											title={isExpanded ? 'Contraer' : 'Expandir detalle'}
										>
											{#if isExpanded}
												<ChevronDown size={12} strokeWidth={2} />
											{:else}
												<ChevronRight size={12} strokeWidth={2} />
											{/if}
										</button>
									</td>
									<td class="px-2 py-2">
										<button
											type="button"
											onclick={() => toggleExpand(row.team)}
											class="flex items-center gap-2 text-left"
										>
											{#if row.flagIso}
												<img
													src="/flags/{row.flagIso}.svg"
													alt=""
													class="h-3.5 w-5 shrink-0 rounded-[2px]"
												/>
											{/if}
											<span class="text-[var(--color-text-primary)]">{row.team}</span>
										</button>
									</td>
									{#each VARIANTS as v (v.key)}
										{@const fam = row.byVariant[v.key]}
										<td class="px-3 py-2 text-center">
											{#if fam?.published}
												<button
													type="button"
													onclick={() => handleCellClick(fam)}
													title="{row.team} {v.label} — publicado · click para abrir"
													class="inline-flex h-7 w-7 items-center justify-center rounded-[4px] bg-[var(--color-live)]/15 text-[var(--color-live)] transition-colors hover:bg-[var(--color-live)]/30"
												>
													<CheckCircle2 size={14} strokeWidth={2} />
												</button>
											{:else if fam}
												<button
													type="button"
													onclick={() => handleCellClick(fam)}
													title="{row.team} {v.label} — en audit · click para abrir"
													class="inline-flex h-7 w-7 items-center justify-center rounded-[4px] bg-[var(--color-warning)]/15 text-[var(--color-warning)] transition-colors hover:bg-[var(--color-warning)]/30"
												>
													<Circle size={14} strokeWidth={2} />
												</button>
											{:else}
												<span
													class="inline-flex h-7 w-7 items-center justify-center text-[var(--color-text-muted)]"
													title="No scraped yet"
												>
													—
												</span>
											{/if}
										</td>
									{/each}
									<!-- Slot counter column -->
									<td
										class="text-mono px-3 py-2 text-right text-[10px] tabular-nums text-[var(--color-text-tertiary)]"
										title="publicados / draft / total"
									>
										<span class="text-[var(--color-live)]">{row.publishedSlots}</span>
										<span class="opacity-50">·</span>
										<span class="text-[var(--color-warning)]">{row.draftSlots}</span>
										<span class="opacity-50">/ {row.totalSlots}</span>
									</td>
								</tr>

								<!-- Expanded detail row -->
								{#if isExpanded}
									<tr class="border-b border-[var(--color-border)]/40">
										<td></td>
										<td
											colspan={2 + VARIANTS.length}
											class="bg-[var(--color-bg)]/60 p-3"
										>
											<div class="space-y-1.5">
												{#each VARIANTS as v (v.key)}
													{@const slots = slotsForVariant(v.key)}
													{@const variantFam = row.byVariant[v.key]}
													<!-- Mostrar solo si hay algo en esta variant O si es Local/Visita (siempre útil ver missing) -->
													{#if variantFam || v.key === 'home' || v.key === 'away'}
														<div class="flex items-start gap-3">
															<span
																class="text-display mt-1 w-16 shrink-0 text-[9.5px] text-[var(--color-text-tertiary)]"
																>{v.label}</span
															>
															<div class="flex flex-wrap gap-1">
																{#each slots as slot (slot.key)}
																	{@const cell = row.byVariantSlot[v.key][slot.key]}
																	{@const status = slotStatus(cell)}
																	<button
																		type="button"
																		disabled={!cell}
																		onclick={() => cell && handleCellClick(cell.family)}
																		title={cell
																			? `${cell.modelo.sku} — ${status} · click para abrir`
																			: `${slot.label} no existe en catalog`}
																		class={chipClasses(status)}
																	>
																		<span>{slot.label}</span>
																		{#if status === 'live'}
																			<Check size={10} strokeWidth={2.5} />
																		{:else if status === 'draft'}
																			<Circle size={10} strokeWidth={2.5} />
																		{:else}
																			<span>—</span>
																		{/if}
																	</button>
																{/each}
															</div>
														</div>
													{/if}
												{/each}
											</div>
										</td>
									</tr>
								{/if}
							{/each}
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Legend -->
			<footer
				class="flex shrink-0 items-center gap-4 border-t border-[var(--color-border)] px-5 py-2 text-[10px] text-[var(--color-text-tertiary)]"
			>
				<span class="flex items-center gap-1.5">
					<CheckCircle2 size={12} strokeWidth={2} class="text-[var(--color-live)]" />
					published (live)
				</span>
				<span class="flex items-center gap-1.5">
					<Circle size={12} strokeWidth={2} class="text-[var(--color-warning)]" />
					draft (en audit)
				</span>
				<span class="flex items-center gap-1.5">
					<span class="text-[var(--color-text-muted)]">—</span>
					no scraped
				</span>
				<span class="ml-auto">Click ▸ fila para expandir · Click chip/✓ abre family</span>
			</footer>
		</div>
	</div>
{/if}
