<script lang="ts">
	import type { Family, Modelo } from '$lib/data/types';
	import { Search, ChevronDown, Filter, Star, ChevronRight } from 'lucide-svelte';
	import StatusBadge from './StatusBadge.svelte';
	import { dndzone, SHADOW_ITEM_MARKER_PROPERTY_NAME } from 'svelte-dnd-action';

	interface Props {
		groups: Map<string, Family[]>;
		selectedSku: string | null;
		selectedFamilyId: string | null;
		onSelectSku?: (sku: string) => void;
		onSelectFamily?: (fid: string) => void;
		/** Callback cuando el user arrastra un modelo de una family a otra */
		onMoveModelo?: (sourceFid: string, sourceModeloIdx: number, targetFid: string) => void;
	}

	let {
		groups,
		selectedSku,
		selectedFamilyId,
		onSelectSku = () => {},
		onSelectFamily = () => {},
		onMoveModelo = () => {}
	}: Props = $props();

	// ─── Drag & Drop state ──────────────────────────────────────
	// Mantener una copia local de modelos por family_id para que svelte-dnd-action
	// pueda mutar su items sin pisar las props. En `onfinalize` detectamos cross-
	// family moves y los reportamos al padre via onMoveModelo.
	let localFamilies = $state<Map<string, Modelo[]>>(new Map());
	let skuSourceMap = $state<Map<string, string>>(new Map()); // sku → family_id de origen

	$effect(() => {
		const newLocal = new Map<string, Modelo[]>();
		const newSkuMap = new Map<string, string>();
		for (const [, fams] of groups) {
			for (const fam of fams) {
				newLocal.set(fam.id, [...fam.modelos]);
				for (const m of fam.modelos) {
					newSkuMap.set(m.sku, fam.id);
				}
			}
		}
		localFamilies = newLocal;
		skuSourceMap = newSkuMap;
	});

	function handleDndConsider(famId: string, e: CustomEvent<{ items: Modelo[] }>) {
		// Actualiza preview visual durante el drag (no persiste aún)
		const next = new Map(localFamilies);
		next.set(famId, e.detail.items);
		localFamilies = next;
	}

	function handleDndFinalize(famId: string, e: CustomEvent<{ items: Modelo[] }>) {
		const newModelos = e.detail.items;
		// Detect cross-family: ¿hay un sku nuevo en este zone que venía de otra family?
		let crossFamilyDetected = false;
		for (const m of newModelos) {
			const originFid = skuSourceMap.get(m.sku);
			if (originFid && originFid !== famId) {
				crossFamilyDetected = true;
				const sourceFamFresh = findFamily(originFid);
				const srcIdx =
					sourceFamFresh?.modelos.findIndex((x) => x.sku === m.sku) ?? -1;
				if (srcIdx >= 0) {
					onMoveModelo(originFid, srcIdx, famId);
				}
				skuSourceMap.set(m.sku, famId);
			}
		}

		// Reset al state real (groups prop). Esto cubre 2 casos:
		// 1. Cross-family: el parent va a re-cargar el catalog vía onMoveModelo;
		//    el $effect actualiza localFamilies cuando llegue el nuevo groups.
		//    Hasta entonces, mantenemos el estado actual del groups (no el optimistic).
		// 2. Same-family (drop dentro de la misma): svelte-dnd-action a veces NO
		//    restaura el item al final cuando target==source → quedaba length-1
		//    permanente, modelo "desaparecido" hasta restart. Reset = restore.
		const sourceFam = findFamily(famId);
		const next = new Map(localFamilies);
		if (sourceFam) {
			next.set(famId, [...sourceFam.modelos]);
		} else {
			// No debería pasar, pero defensive: si no encontramos family, mantenemos items
			next.set(famId, newModelos);
		}
		localFamilies = next;
		void crossFamilyDetected; // silenciar warning unused (mantiene la rama de detección)
	}

	function findFamily(fid: string): Family | undefined {
		for (const [, fams] of groups) {
			const f = fams.find((x) => x.id === fid);
			if (f) return f;
		}
		return undefined;
	}

	// Collapsed teams state (default: all expanded). Key: `${letter}:${team}`
	let collapsedTeams = $state<Set<string>>(new Set());

	function teamKey(letter: string, team: string): string {
		return `${letter}:${team}`;
	}
	function isCollapsed(letter: string, team: string): boolean {
		return collapsedTeams.has(teamKey(letter, team));
	}
	function toggleTeam(letter: string, team: string) {
		const k = teamKey(letter, team);
		const next = new Set(collapsedTeams);
		if (next.has(k)) next.delete(k);
		else next.add(k);
		collapsedTeams = next;
	}

	// Nested grouping: letter → team → families
	let nestedGroups = $derived.by(() => {
		const out = new Map<string, Map<string, Family[]>>();
		for (const [letter, fams] of groups) {
			const byTeam = new Map<string, Family[]>();
			for (const fam of fams) {
				const key = fam.team;
				if (!byTeam.has(key)) byTeam.set(key, []);
				byTeam.get(key)!.push(fam);
			}
			out.set(letter, byTeam);
		}
		return out;
	});

	let flatSkus = $derived.by(() => {
		const list: Array<{ sku: string; family: Family; modelo: Modelo }> = [];
		for (const [, fams] of groups) {
			for (const fam of fams) {
				for (const m of fam.modelos) {
					list.push({ sku: m.sku, family: fam, modelo: m });
				}
			}
		}
		return list;
	});

	const MODELO_LABEL: Record<string, string> = {
		fan_adult: 'Fan',
		player_adult: 'Player',
		retro_adult: 'Retro',
		woman: 'Mujer',
		kid: 'Niño',
		baby: 'Bebé',
		goalkeeper: 'GK',
		polo: 'Polo',
		vest: 'Vest',
		training: 'Entreno',
		sweatshirt: 'Sudadera',
		jacket: 'Chaqueta',
		shorts: 'Shorts',
		adult: 'Adulto'
	};
	const SLEEVE_LABEL: Record<string, string> = { short: 'M/C', long: 'M/L' };

	// Orden de tipos en el sub-group dentro de cada variant
	const TYPE_ORDER = [
		'fan_adult',
		'player_adult',
		'retro_adult',
		'woman',
		'kid',
		'baby',
		'goalkeeper',
		'training',
		'polo',
		'sweatshirt',
		'jacket',
		'vest',
		'shorts',
		'adult'
	];

	function modeloDesc(m: Modelo): string {
		const base = MODELO_LABEL[m.modeloType] || m.modeloType;
		if (m.sleeve && (m.modeloType === 'fan_adult' || m.modeloType === 'player_adult')) {
			return `${base} ${SLEEVE_LABEL[m.sleeve]}`;
		}
		return base;
	}

	function groupModelosByType(modelos: Modelo[]): Array<{ type: string; modelos: Modelo[] }> {
		const byType = new Map<string, Modelo[]>();
		for (const m of modelos) {
			const key = m.modeloType;
			if (!byType.has(key)) byType.set(key, []);
			byType.get(key)!.push(m);
		}
		// Sort each group: short sleeve first, long second
		for (const [, arr] of byType) {
			arr.sort((a, b) => (a.sleeve === 'long' ? 1 : 0) - (b.sleeve === 'long' ? 1 : 0));
		}
		// Output in TYPE_ORDER
		const out: Array<{ type: string; modelos: Modelo[] }> = [];
		for (const t of TYPE_ORDER) {
			if (byType.has(t)) out.push({ type: t, modelos: byType.get(t)! });
		}
		// Cualquier tipo fuera del orden conocido va al final
		for (const [t, arr] of byType) {
			if (!TYPE_ORDER.includes(t)) out.push({ type: t, modelos: arr });
		}
		return out;
	}

	function countModelos(fams: Family[]): number {
		return fams.reduce((s, f) => s + f.modelos.length, 0);
	}
</script>

<section
	class="flex h-full w-[380px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]"
>
	<header
		class="ui-chrome flex h-14 items-center justify-between border-b border-[var(--color-border)] px-4"
	>
		<div class="flex items-center gap-2.5">
			<span class="text-display text-[12px] text-[var(--color-text-primary)]">Catálogo</span>
			<span
				class="text-mono rounded-[3px] bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-text-secondary)] tabular-nums"
				title="{flatSkus.length} SKUs totales"
			>
				{flatSkus.length}
			</span>
		</div>
		<button
			type="button"
			class="flex items-center gap-1 rounded-[3px] px-2 py-1 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
		>
			<Filter size={12} strokeWidth={1.8} />
			MVP
			<ChevronDown size={11} strokeWidth={1.8} />
		</button>
	</header>

	<div class="relative border-b border-[var(--color-border)] px-3 py-2">
		<Search
			size={13}
			strokeWidth={1.8}
			class="pointer-events-none absolute left-[22px] top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)]"
		/>
		<input
			type="text"
			placeholder="Buscar SKU, team, variante…"
			class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] py-1.5 pl-7 pr-2.5 text-[12px] text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] transition-colors focus:border-[var(--color-accent)] focus:outline-none"
		/>
	</div>

	<div class="flex-1 overflow-y-auto">
		{#each [...nestedGroups] as [letter, byTeam] (letter)}
			<div class="border-b border-[var(--color-border)]/50 last:border-0">
				<!-- Group header (Grupo A-L o —) -->
				<div
					class="text-display sticky top-0 z-10 flex items-center justify-between border-b border-[var(--color-border)]/50 bg-[var(--color-surface-1)]/95 px-4 py-1.5 text-[10px] text-[var(--color-text-tertiary)] backdrop-blur-sm"
				>
					<span class="tracking-[0.14em]">
						{letter === '—' ? 'SIN GRUPO' : `GRUPO ${letter}`}
					</span>
					<span class="text-mono tabular-nums"
						>{[...byTeam.values()].reduce((s, f) => s + countModelos(f), 0)}</span
					>
				</div>

				{#each [...byTeam] as [team, fams] (team)}
					{@const collapsed = isCollapsed(letter, team)}
					{@const sample = fams[0]}
					{@const nVariants = fams.length}
					{@const nModelos = countModelos(fams)}
					{@const anyFeatured = fams.some((f) => f.featured)}

					<!-- Team header — clickable, toggles collapse -->
					<button
						type="button"
						onclick={() => toggleTeam(letter, team)}
						class="group flex w-full items-center gap-2 px-3 py-1.5 text-[11.5px] transition-colors hover:bg-[var(--color-surface-1)]"
					>
						<ChevronDown
							size={11}
							strokeWidth={2}
							class="shrink-0 text-[var(--color-text-tertiary)] transition-transform"
							style="transform: rotate({collapsed ? -90 : 0}deg);"
						/>
						{#if sample.flagIso}
							<img
								src="/flags/{sample.flagIso}.svg"
								alt=""
								class="h-3.5 w-5 shrink-0 rounded-[2px] shadow-[0_0_0_1px_rgba(255,255,255,0.06)]"
							/>
						{/if}
						<span class="flex-1 text-left font-semibold text-[var(--color-text-primary)]"
							>{team}</span
						>
						{#if anyFeatured}
							<Star
								size={10}
								strokeWidth={2}
								class="text-[var(--color-warning)]"
								fill="currentColor"
							/>
						{/if}
						<span
							class="text-mono rounded-[3px] bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[9.5px] font-semibold text-[var(--color-text-secondary)] tabular-nums"
						>
							{nVariants}v · {nModelos}
						</span>
					</button>

					{#if !collapsed}
						<div class="pb-1">
							{#each fams as fam (fam.id)}
								<!-- Variant header — clickable, selecciona FAMILY -->
								<button
									type="button"
									onclick={() => onSelectFamily(fam.id)}
									class="group relative flex w-full items-center gap-2 rounded-[3px] px-4 py-1 text-left transition-colors hover:bg-[var(--color-surface-2)]/60"
									class:bg-[var(--color-accent-soft)]={selectedFamilyId === fam.id}
								>
									{#if selectedFamilyId === fam.id}
										<span
											class="absolute left-0 top-0 bottom-0 w-[2px] bg-[var(--color-accent)]"
										></span>
									{/if}
									<span
										class="text-[10.5px] font-medium"
										class:text-[var(--color-accent)]={selectedFamilyId === fam.id}
										class:text-[var(--color-text-tertiary)]={selectedFamilyId !== fam.id}
									>
										{fam.variantLabel}
									</span>
									{#if fam.featured}
										<Star
											size={9}
											strokeWidth={2}
											class="text-[var(--color-warning)]"
											fill="currentColor"
										/>
									{/if}
									<span
										class="text-mono ml-auto text-[9.5px] text-[var(--color-text-muted)] tabular-nums"
									>
										{fam.modelos.length} modelo{fam.modelos.length !== 1 ? 's' : ''}
									</span>
									<ChevronRight
										size={10}
										strokeWidth={1.8}
										class="text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
									/>
								</button>

								<!-- Modelos — dndzone para drag entre families.
									 svelte-dnd-action requiere que cada item tenga `id`. Como Modelo usa
									 `sku` como unique key, lo mapeamos a `id` para el lib sin mutar originals. -->
								{@const zoneModelos = localFamilies.get(fam.id) ?? fam.modelos}
								{@const dndItems = zoneModelos.map((m) => ({ ...m, id: m.sku }))}
								<div
									use:dndzone={{
										items: dndItems,
										flipDurationMs: 180,
										type: 'modelo',
										dropTargetStyle: {
											outline: '2px dashed var(--color-accent)',
											outlineOffset: '-2px',
											backgroundColor: 'var(--color-accent-soft)'
										}
									}}
									onconsider={(e) => handleDndConsider(fam.id, e)}
									onfinalize={(e) => handleDndFinalize(fam.id, e)}
								>
									{#each dndItems as m (m.id)}
										{@const isShadow = !!(m as unknown as Record<string, unknown>)[SHADOW_ITEM_MARKER_PROPERTY_NAME]}
										<button
											type="button"
											class="group relative flex w-full cursor-grab items-center gap-2 rounded-[3px] py-1 pl-7 pr-2 text-left transition-colors hover:bg-[var(--color-surface-2)] active:cursor-grabbing"
											class:bg-[var(--color-surface-2)]={selectedSku === m.sku}
											class:opacity-40={isShadow}
											onclick={() => onSelectSku(m.sku)}
										>
											{#if selectedSku === m.sku}
												<span
													class="absolute left-0 top-1 bottom-1 w-[2px] bg-[var(--color-accent)]"
												></span>
											{/if}
											<span
												class="text-mono shrink-0 text-[10px] font-semibold tabular-nums"
												class:text-[var(--color-accent)]={selectedSku === m.sku}
												class:text-[var(--color-text-tertiary)]={selectedSku !== m.sku}
											>
												{m.sku}
											</span>
											<span
												class="flex-1 truncate text-[11px] text-[var(--color-text-secondary)]"
											>
												{modeloDesc(m)}
											</span>
											<StatusBadge status={m.status} size="xs" />
										</button>
									{/each}
								</div>
							{/each}
						</div>
					{/if}
				{/each}
			</div>
		{/each}
	</div>

	<footer
		class="ui-chrome flex h-9 items-center justify-between border-t border-[var(--color-border)] px-4 text-[10px] text-[var(--color-text-tertiary)]"
	>
		<span class="flex items-center gap-1.5">
			<kbd>J</kbd><kbd>K</kbd>
			<span class="text-[10px]">navegar</span>
		</span>
		<span class="flex items-center gap-1.5">
			<kbd>↵</kbd>
			<span class="text-[10px]">abrir</span>
		</span>
	</footer>
</section>
