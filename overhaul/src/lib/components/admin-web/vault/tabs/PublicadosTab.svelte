<!--
	PublicadosTab — vista de jerseys PUBLISHED en Vault.

	Layout:
	  - Smart filters chips (6 filters: all, attention, recent, scheduled, no_tags, old)
	  - Cards grid responsivo
	  - URL state: ?filter=X persiste preferencia

	Click en PROMOVER abre DropCreatorModal (T4.7).
	Click en ⚙ abre detail modal simple (T4.6 simplificado).
	Click en 🗑 archive_jersey con confirm.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { adminWeb } from '$lib/adapter';
	import { LayoutGrid, List } from 'lucide-svelte';
	import PublishedCard from '../PublishedCard.svelte';
	import DropCreatorModal from '../DropCreatorModal.svelte';
	import PublishedDetailModal from '../PublishedDetailModal.svelte';

	type ViewMode = 'cards' | 'table';
	const STORAGE_KEY = 'admin-web:vault.publicados:view';

	function readStoredView(): ViewMode {
		if (typeof localStorage === 'undefined') return 'cards';
		try {
			const v = localStorage.getItem(STORAGE_KEY);
			return v === 'table' ? 'table' : 'cards';
		} catch {
			return 'cards';
		}
	}
	let viewMode = $state<ViewMode>(readStoredView());

	function setViewMode(v: ViewMode) {
		viewMode = v;
		try {
			localStorage.setItem(STORAGE_KEY, v);
		} catch {
			/* noop */
		}
	}

	const FILTERS = [
		{ slug: 'all', label: 'Todas' },
		{ slug: 'attention', label: 'Atención' },
		{ slug: 'recent', label: 'Recientes' },
		{ slug: 'scheduled', label: 'Scheduled' },
		{ slug: 'no_tags', label: 'Sin tags' },
		{ slug: 'old', label: 'Antiguas' }
	] as const;

	type FilterSlug = (typeof FILTERS)[number]['slug'];

	const currentFilter = $derived.by((): FilterSlug => {
		const f = $page.url.searchParams.get('filter');
		const valid = FILTERS.map((x) => x.slug as string);
		return valid.includes(f ?? '') ? (f as FilterSlug) : 'all';
	});

	let jerseys = $state<Record<string, unknown>[]>([]);
	let loading = $state(true);
	let promotingFamily = $state<string | null>(null);
	let detailFamily = $state<string | null>(null);

	async function load(filter: FilterSlug) {
		loading = true;
		try {
			const list = await adminWeb.list_published({ filter, pagination: { page: 1, per_page: 60 } });
			// Tauri devuelve pseudo-Jersey con shape parcial (Rust list_published
			// devuelve Vec<Value> con campos selectivos) — cast vía unknown.
			jerseys = list as unknown as Record<string, unknown>[];
		} catch {
			jerseys = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void load(currentFilter);
	});

	function selectFilter(slug: FilterSlug) {
		const url = new URL($page.url);
		if (slug === 'all') {
			url.searchParams.delete('filter');
		} else {
			url.searchParams.set('filter', slug);
		}
		void goto(url.pathname + url.search, { replaceState: false, noScroll: true, keepFocus: true });
	}

	async function archive(familyId: string) {
		if (!confirm(`¿Archivar ${familyId}?`)) return;
		try {
			await adminWeb.archive_jersey({ family_id: familyId });
			jerseys = jerseys.filter((j) => j.family_id !== familyId);
		} catch (err) {
			alert(`No se pudo archivar: ${err instanceof Error ? err.message : err}`);
		}
	}
</script>

<div class="flex h-full flex-col p-4">
	<!-- Smart filters chips -->
	<div class="mb-4 flex items-center gap-1.5 overflow-x-auto pb-1">
		{#each FILTERS as f (f.slug)}
			{@const isActive = currentFilter === f.slug}
			<button
				type="button"
				onclick={() => selectFilter(f.slug)}
				class="text-display shrink-0 rounded-[3px] border px-3 py-1.5 text-[10.5px] tracking-[0.14em] transition-all"
				class:border-[var(--color-terminal)]={isActive}
				class:bg-[var(--color-terminal)]={isActive}
				class:text-[var(--color-bg)]={isActive}
				class:border-[var(--color-border)]={!isActive}
				class:bg-[var(--color-surface-1)]={!isActive}
				class:text-[var(--color-text-secondary)]={!isActive}
				class:hover:border-[var(--color-text-tertiary)]={!isActive}
				class:hover:text-[var(--color-text-primary)]={!isActive}
			>
				{f.label.toUpperCase()}
			</button>
		{/each}

		<!-- Result counter + view toggle -->
		<div class="ml-auto flex shrink-0 items-center gap-2">
			<div class="text-mono text-[10.5px] text-[var(--color-text-muted)]">
				{loading ? 'cargando…' : `${jerseys.length} resultado${jerseys.length === 1 ? '' : 's'}`}
			</div>
			<div
				class="ml-2 flex overflow-hidden rounded-[3px] border border-[var(--color-border)]"
			>
				<button
					type="button"
					onclick={() => setViewMode('cards')}
					title="Ver como tarjetas"
					class="flex h-7 w-7 items-center justify-center transition-colors"
					class:bg-[var(--color-surface-2)]={viewMode === 'cards'}
					class:text-[var(--color-text-primary)]={viewMode === 'cards'}
					class:text-[var(--color-text-tertiary)]={viewMode !== 'cards'}
				>
					<LayoutGrid size={12} strokeWidth={1.8} />
				</button>
				<button
					type="button"
					onclick={() => setViewMode('table')}
					title="Ver como tabla"
					class="flex h-7 w-7 items-center justify-center transition-colors"
					class:bg-[var(--color-surface-2)]={viewMode === 'table'}
					class:text-[var(--color-text-primary)]={viewMode === 'table'}
					class:text-[var(--color-text-tertiary)]={viewMode !== 'table'}
				>
					<List size={12} strokeWidth={1.8} />
				</button>
			</div>
		</div>
	</div>

	<!-- Cards grid -->
	<div class="min-h-0 flex-1 overflow-auto">
		{#if loading}
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
				{#each Array(10) as _, i (i)}
					<div
						class="aspect-[3/4] animate-pulse rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
					></div>
				{/each}
			</div>
		{:else if jerseys.length === 0}
			<div class="flex h-full items-center justify-center p-8 text-center">
				<div>
					<div
						class="text-display mb-2 text-[14px] tracking-[0.16em] text-[var(--color-text-tertiary)]"
					>
						SIN RESULTADOS
					</div>
					<p class="text-[11.5px] text-[var(--color-text-muted)]">
						Ningún publicado matchea el filtro <span class="text-mono">{currentFilter}</span>.
					</p>
				</div>
			</div>
		{:else if viewMode === 'cards'}
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
				{#each jerseys as jersey (jersey.family_id)}
					<PublishedCard
						{jersey}
						onPromote={(id) => (promotingFamily = id)}
						onOpenDetail={(id) => (detailFamily = id)}
						onDelete={archive}
					/>
				{/each}
			</div>
		{:else}
			<!-- Tabla densa (T4.9 simple, T6.2 hace la version power-user) -->
			<div
				class="overflow-auto rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
			>
				<table class="w-full text-[12px]">
					<thead
						class="text-display sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
					>
						<tr>
							<th class="px-3 py-2 text-left">Thumb</th>
							<th class="px-3 py-2 text-left">SKU</th>
							<th class="px-3 py-2 text-left">Team</th>
							<th class="px-3 py-2 text-left">Season</th>
							<th class="px-3 py-2 text-left">Tier</th>
							<th class="px-3 py-2 text-left">Flags</th>
							<th class="px-3 py-2"></th>
						</tr>
					</thead>
					<tbody>
						{#each jerseys as jersey (jersey.family_id)}
							{@const familyId = String(jersey.family_id ?? '')}
							{@const sku = String(jersey.sku ?? jersey.family_id ?? '')}
							{@const team = String(jersey.team ?? '')}
							{@const season = String(jersey.season ?? '')}
							{@const tier = jersey.tier as string | null | undefined}
							{@const hero = jersey.hero_thumbnail as string | null | undefined}
							{@const flags = (jersey.flags as Record<string, unknown> | undefined) ?? {}}
							{@const isDirty = flags.dirty === true}
							<tr
								class="border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-surface-2)]"
							>
								<td class="px-2 py-1">
									{#if hero}
										<img
											src={hero}
											alt={team}
											class="h-9 w-9 rounded-[2px] object-cover"
											loading="lazy"
										/>
									{:else}
										<div class="h-9 w-9 rounded-[2px] bg-[var(--color-surface-2)]"></div>
									{/if}
								</td>
								<td class="text-mono px-3 py-2 text-[var(--color-text-primary)]">{sku}</td>
								<td class="px-3 py-2 text-[var(--color-text-secondary)]">{team || '—'}</td>
								<td class="text-mono px-3 py-2 text-[var(--color-text-secondary)]">
									{season || '—'}
								</td>
								<td class="text-mono px-3 py-2 text-[var(--color-text-tertiary)]">
									{tier ?? '—'}
								</td>
								<td class="px-3 py-2">
									{#if isDirty}
										<span
											class="text-mono rounded-[2px] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
											style:background="rgba(244, 63, 94, 0.18)"
											style:color="var(--color-danger)"
										>
											DIRTY
										</span>
									{:else}
										<span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">—</span>
									{/if}
								</td>
								<td class="whitespace-nowrap px-3 py-2 text-right">
									<button
										type="button"
										onclick={() => (promotingFamily = familyId)}
										class="text-display rounded-[3px] border border-[var(--color-terminal)]/40 px-2 py-1 text-[9px] tracking-[0.14em] text-[var(--color-terminal)] hover:bg-[var(--color-terminal)] hover:text-[var(--color-bg)]"
									>
										PROMOVER
									</button>
									<button
										type="button"
										onclick={() => (detailFamily = familyId)}
										class="text-display ml-1 rounded-[3px] px-2 py-1 text-[9px] tracking-[0.14em] text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
									>
										DETALLE
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>

{#if promotingFamily}
	<DropCreatorModal
		familyId={promotingFamily}
		onClose={() => (promotingFamily = null)}
		onSuccess={() => {
			promotingFamily = null;
			void load(currentFilter);
		}}
	/>
{/if}

{#if detailFamily}
	<PublishedDetailModal
		familyId={detailFamily}
		onClose={() => (detailFamily = null)}
	/>
{/if}
