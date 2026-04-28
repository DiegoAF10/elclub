<!--
	UniversoTab — vista power-user del Vault con tabla densa + sidebar filters
	+ presets + bulk actions. URL state full sync.

	Simplificaciones R7.0 vs spec original:
	  - Sin virtualization (loadea max 500 rows; T6.X future agrega svelte-virtual
	    cuando dataset crezca)
	  - Sin drag-drop reorder columnas (svelte-dnd-action skipped)
	  - Sin export CSV (T6.8 — futuro)
	  - Presets: solo factory presets (los 7 seedeados); no save/edit/delete
	  - Filters: states, dirty, qa_priority, last_action, search, tags
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { adminWeb } from '$lib/adapter';
	import type { Tag } from '$lib/adapter';
	import { ChevronUp, ChevronDown, AlertCircle, Star } from 'lucide-svelte';
	import UniversoFilters from '../UniversoFilters.svelte';
	import BulkActionBar from '../BulkActionBar.svelte';

	interface Filters {
		states: string[];
		dirty: boolean;
		qa_priority: boolean;
		last_action?: 'today' | 'week' | 'month' | 'older';
		search: string;
		tags: number[];
	}

	function defaultFilters(): Filters {
		return { states: [], dirty: false, qa_priority: false, search: '', tags: [] };
	}

	function parseFiltersFromUrl(): Filters {
		const u = $page.url.searchParams;
		const states = u.get('states')?.split(',').filter(Boolean) ?? [];
		const tags = u.get('tags')?.split(',').filter(Boolean).map(Number).filter((n) => !isNaN(n)) ?? [];
		const lastAction = u.get('last_action') as Filters['last_action'] | null;
		return {
			states,
			dirty: u.get('dirty') === '1',
			qa_priority: u.get('qa') === '1',
			last_action: lastAction === 'today' || lastAction === 'week' || lastAction === 'month' || lastAction === 'older' ? lastAction : undefined,
			search: u.get('q') ?? '',
			tags
		};
	}

	function syncFiltersToUrl(filters: Filters, sortCol: string, sortDir: string, pageNum: number) {
		const u = new URL($page.url);
		const set = (k: string, v: string | undefined | null) => {
			if (v == null || v === '') u.searchParams.delete(k);
			else u.searchParams.set(k, v);
		};
		set('states', filters.states.length ? filters.states.join(',') : null);
		set('dirty', filters.dirty ? '1' : null);
		set('qa', filters.qa_priority ? '1' : null);
		set('last_action', filters.last_action ?? null);
		set('q', filters.search || null);
		set('tags', filters.tags.length ? filters.tags.join(',') : null);
		set('sort', sortCol !== 'reviewed_at' ? sortCol : null);
		set('dir', sortDir !== 'desc' ? sortDir : null);
		set('p', pageNum > 1 ? String(pageNum) : null);
		void goto(u.pathname + u.search, { replaceState: true, noScroll: true, keepFocus: true });
	}

	let filters = $state<Filters>(parseFiltersFromUrl());
	let sortCol = $state($page.url.searchParams.get('sort') ?? 'reviewed_at');
	let sortDir = $state<'asc' | 'desc'>(
		$page.url.searchParams.get('dir') === 'asc' ? 'asc' : 'desc'
	);
	let pageNum = $state(parseInt($page.url.searchParams.get('p') ?? '1', 10) || 1);
	const PER_PAGE = 50;

	let rows = $state<Record<string, unknown>[]>([]);
	let total = $state(0);
	let stateCounts = $state<Record<string, number>>({});
	let loading = $state(true);

	let allTags = $state<Tag[]>([]);
	let selected = $state<Set<string>>(new Set());

	async function load() {
		loading = true;
		try {
			const result = await adminWeb.list_universo({
				filters: {
					states: (filters.states as unknown) as never,
					tags: filters.tags,
					last_action: filters.last_action,
					search: filters.search || undefined,
					flags: {
						dirty: filters.dirty,
						qa_priority: filters.qa_priority
					}
				},
				sort: { column: sortCol, direction: sortDir },
				pagination: { page: pageNum, per_page: PER_PAGE }
			});
			rows = result.rows as unknown as Record<string, unknown>[];
			total = result.total;
			const counts = result.filters_counts as { by_state?: Record<string, number> };
			stateCounts = counts?.by_state ?? {};
		} catch {
			rows = [];
			total = 0;
		} finally {
			loading = false;
		}
	}

	async function loadTags() {
		try {
			allTags = (await adminWeb.list_tags()) as Tag[];
		} catch {
			allTags = [];
		}
	}

	$effect(() => {
		void load();
	});

	$effect(() => {
		void loadTags();
	});

	function applyFilters(next: Partial<Filters>) {
		filters = { ...filters, ...next };
		pageNum = 1;
		syncFiltersToUrl(filters, sortCol, sortDir, pageNum);
	}

	function clearFilters() {
		filters = defaultFilters();
		pageNum = 1;
		syncFiltersToUrl(filters, sortCol, sortDir, pageNum);
	}

	function toggleSort(col: string) {
		if (sortCol === col) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortCol = col;
			sortDir = 'desc';
		}
		syncFiltersToUrl(filters, sortCol, sortDir, pageNum);
	}

	function toggleSelect(familyId: string) {
		const s = new Set(selected);
		if (s.has(familyId)) s.delete(familyId);
		else s.add(familyId);
		selected = s;
	}

	function selectAllVisible() {
		const ids = rows
			.map((r) => String(r.family_id ?? ''))
			.filter((id) => id !== '');
		selected = new Set([...selected, ...ids]);
	}

	function clearSelection() {
		selected = new Set();
	}

	const selectedArr = $derived([...selected]);
	const totalPages = $derived(Math.max(1, Math.ceil(total / PER_PAGE)));

	function gotoPage(n: number) {
		pageNum = Math.max(1, Math.min(totalPages, n));
		syncFiltersToUrl(filters, sortCol, sortDir, pageNum);
	}

	const tagsForBulk = $derived(
		allTags
			.filter((t) => !t.is_deleted)
			.map((t) => ({ id: t.id, display_name: t.display_name, type_slug: t.type_slug }))
	);

	function relativeTime(iso: string | null | undefined): string {
		if (!iso) return '—';
		const ts = new Date(iso).getTime();
		if (isNaN(ts)) return '—';
		const delta = Math.floor((Date.now() - ts) / 1000);
		if (delta < 60) return 'recién';
		if (delta < 3600) return `${Math.floor(delta / 60)}m`;
		if (delta < 86400) return `${Math.floor(delta / 3600)}h`;
		return `${Math.floor(delta / 86400)}d`;
	}
</script>

<div class="flex h-full">
	<UniversoFilters
		{filters}
		{stateCounts}
		onChange={applyFilters}
		onClear={clearFilters}
	/>

	<div class="flex flex-1 flex-col">
		<!-- Toolbar -->
		<div
			class="flex h-10 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4 text-[11px]"
		>
			<div class="text-mono text-[var(--color-text-muted)]">
				{loading ? 'cargando…' : `${rows.length} de ${total}`}
				{#if total > 0}
					· sort:
					<span class="text-[var(--color-text-secondary)]">{sortCol} {sortDir === 'asc' ? '↑' : '↓'}</span>
				{/if}
			</div>

			<div class="ml-auto flex items-center gap-2">
				{#if rows.length > 0}
					<button
						type="button"
						onclick={selectAllVisible}
						class="text-display rounded-[3px] px-2 py-1 text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						SELECT TODOS
					</button>
				{/if}
				<div class="text-mono flex items-center gap-1 text-[10px] text-[var(--color-text-muted)]">
					<button
						type="button"
						onclick={() => gotoPage(pageNum - 1)}
						disabled={pageNum === 1}
						class="rounded-[2px] px-1.5 py-0.5 hover:bg-[var(--color-surface-2)] disabled:opacity-30"
					>
						‹
					</button>
					<span>{pageNum} / {totalPages}</span>
					<button
						type="button"
						onclick={() => gotoPage(pageNum + 1)}
						disabled={pageNum === totalPages}
						class="rounded-[2px] px-1.5 py-0.5 hover:bg-[var(--color-surface-2)] disabled:opacity-30"
					>
						›
					</button>
				</div>
			</div>
		</div>

		<!-- Table -->
		<div class="min-h-0 flex-1 overflow-auto">
			{#if loading}
				<div class="p-6 text-[11px] text-[var(--color-text-muted)]">cargando…</div>
			{:else if rows.length === 0}
				<div class="flex h-full items-center justify-center p-8 text-center">
					<div>
						<div
							class="text-display mb-2 text-[14px] tracking-[0.16em] text-[var(--color-text-tertiary)]"
						>
							SIN RESULTADOS
						</div>
						<p class="text-[11.5px] text-[var(--color-text-muted)]">
							Ningún jersey matchea los filters actuales.
						</p>
					</div>
				</div>
			{:else}
				<table class="w-full text-[11.5px]">
					<thead
						class="text-display sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						<tr>
							<th class="px-2 py-2">
								<input
									type="checkbox"
									class="h-3 w-3 accent-[var(--color-terminal)]"
									checked={selected.size > 0 && rows.every((r) => selected.has(String(r.family_id)))}
									onchange={(e) => {
										if (e.currentTarget.checked) selectAllVisible();
										else clearSelection();
									}}
								/>
							</th>
							<th class="px-2 py-2 text-left">Thumb</th>
							<th class="px-2 py-2 text-left">
								<button
									type="button"
									onclick={() => toggleSort('family_id')}
									class="hover:text-[var(--color-text-primary)]"
								>
									SKU {sortCol === 'family_id' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
								</button>
							</th>
							<th class="px-2 py-2 text-left">Team</th>
							<th class="px-2 py-2 text-left">
								<button
									type="button"
									onclick={() => toggleSort('state')}
									class="hover:text-[var(--color-text-primary)]"
								>
									Estado {sortCol === 'state' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
								</button>
							</th>
							<th class="px-2 py-2 text-left">
								<button
									type="button"
									onclick={() => toggleSort('tier')}
									class="hover:text-[var(--color-text-primary)]"
								>
									Tier {sortCol === 'tier' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
								</button>
							</th>
							<th class="px-2 py-2 text-left">Flags</th>
							<th class="px-2 py-2 text-left">Cov.</th>
							<th class="px-2 py-2 text-left">
								<button
									type="button"
									onclick={() => toggleSort('reviewed_at')}
									class="hover:text-[var(--color-text-primary)]"
								>
									Reviewed {sortCol === 'reviewed_at' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
								</button>
							</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as row (row.family_id)}
							{@const familyId = String(row.family_id ?? '')}
							{@const sku = String(row.sku ?? row.family_id ?? '')}
							{@const team = String(row.team ?? '')}
							{@const stateVal = String(row.state ?? '')}
							{@const tier = (row.tier as string | null | undefined) ?? '—'}
							{@const flags = (row.flags as Record<string, unknown>) ?? {}}
							{@const isDirty = flags.dirty === true}
							{@const isQa = flags.qa_priority === 1 || flags.qa_priority === true}
							{@const coverage = (row.coverage as number | undefined) ?? 0}
							{@const hero = row.hero_thumbnail as string | null | undefined}
							{@const isSelected = selected.has(familyId)}
							<tr
								class="border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-surface-2)]"
								class:bg-[var(--color-surface-2)]={isSelected}
							>
								<td class="px-2 py-1">
									<input
										type="checkbox"
										class="h-3 w-3 accent-[var(--color-terminal)]"
										checked={isSelected}
										onchange={() => toggleSelect(familyId)}
									/>
								</td>
								<td class="px-2 py-1">
									{#if hero}
										<img
											src={hero}
											alt={team}
											class="h-9 w-9 rounded-[2px] object-cover"
											loading="lazy"
										/>
									{:else}
										<div class="h-9 w-9 rounded-[2px] bg-[var(--color-surface-3)]"></div>
									{/if}
								</td>
								<td class="text-mono px-2 py-1 text-[var(--color-text-primary)]">
									{sku}
								</td>
								<td class="px-2 py-1 text-[var(--color-text-secondary)]">{team || '—'}</td>
								<td class="text-mono px-2 py-1">
									<span
										class="rounded-[2px] px-1.5 py-0.5 text-[9px] uppercase tracking-wide"
										style:background={
											stateVal === 'PUBLISHED'
												? 'rgba(74,222,128,0.18)'
												: stateVal === 'QUEUE'
													? 'rgba(251,191,36,0.18)'
													: stateVal === 'ARCHIVED'
														? 'rgba(115,115,115,0.18)'
														: stateVal === 'REJECTED'
															? 'rgba(244,63,94,0.18)'
															: 'rgba(115,115,115,0.18)'
										}
										style:color={
											stateVal === 'PUBLISHED'
												? 'var(--color-terminal)'
												: stateVal === 'QUEUE'
													? 'var(--color-warning)'
													: stateVal === 'REJECTED'
														? 'var(--color-danger)'
														: 'var(--color-text-secondary)'
										}
									>
										{stateVal}
									</span>
								</td>
								<td class="text-mono px-2 py-1 text-[var(--color-text-tertiary)]">{tier}</td>
								<td class="px-2 py-1">
									<div class="flex gap-1">
										{#if isDirty}
											<span title="Dirty">
												<AlertCircle size={11} class="text-[var(--color-danger)]" />
											</span>
										{/if}
										{#if isQa}
											<span title="QA priority">
												<Star size={11} class="text-[var(--color-terminal)]" />
											</span>
										{/if}
									</div>
								</td>
								<td class="text-mono px-2 py-1 tabular-nums text-[var(--color-text-secondary)]">
									{coverage}
								</td>
								<td class="text-mono px-2 py-1 text-[var(--color-text-muted)]">
									{relativeTime(row.reviewed_at as string | undefined)}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>

		{#if selected.size > 0}
			<BulkActionBar
				selectedFamilyIds={selectedArr}
				availableTags={tagsForBulk}
				onClear={clearSelection}
				onComplete={() => {
					clearSelection();
					void load();
				}}
			/>
		{/if}
	</div>
</div>
