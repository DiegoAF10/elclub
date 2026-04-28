<!--
	UniversoFilters — sidebar de filters para Universo.
	Estado, flags, last_action. Counts reactivos por estado desde filters_counts.
-->
<script lang="ts">
	import { Filter, X } from 'lucide-svelte';

	interface Filters {
		states: string[];
		dirty: boolean;
		qa_priority: boolean;
		last_action?: 'today' | 'week' | 'month' | 'older';
		search: string;
		tags: number[];
	}

	interface Props {
		filters: Filters;
		stateCounts: Record<string, number>;
		onChange: (next: Partial<Filters>) => void;
		onClear: () => void;
	}
	let { filters, stateCounts, onChange, onClear }: Props = $props();

	const STATES = [
		{ slug: 'DRAFT', label: 'Draft' },
		{ slug: 'QUEUE', label: 'Queue' },
		{ slug: 'PUBLISHED', label: 'Published' },
		{ slug: 'ARCHIVED', label: 'Archived' },
		{ slug: 'REJECTED', label: 'Rejected' }
	];

	const LAST_ACTION_OPTS = [
		{ slug: '', label: 'Cualquiera' },
		{ slug: 'today', label: 'Hoy' },
		{ slug: 'week', label: 'Última semana' },
		{ slug: 'month', label: 'Último mes' },
		{ slug: 'older', label: 'Más viejo' }
	];

	function toggleState(slug: string) {
		const has = filters.states.includes(slug);
		onChange({ states: has ? filters.states.filter((s) => s !== slug) : [...filters.states, slug] });
	}

	const anyFilterActive = $derived(
		filters.states.length > 0 ||
			filters.dirty ||
			filters.qa_priority ||
			filters.last_action != null ||
			filters.search !== '' ||
			filters.tags.length > 0
	);
</script>

<aside
	class="flex w-[220px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-1)]"
>
	<div
		class="flex h-10 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-3"
	>
		<div class="flex items-center gap-2">
			<Filter size={12} strokeWidth={1.8} class="text-[var(--color-text-tertiary)]" />
			<span
				class="text-display text-[10.5px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				FILTERS
			</span>
		</div>
		{#if anyFilterActive}
			<button
				type="button"
				onclick={onClear}
				class="flex items-center gap-0.5 text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
				title="Limpiar todos los filters"
			>
				<X size={11} strokeWidth={1.8} />
				LIMPIAR
			</button>
		{/if}
	</div>

	<div class="flex-1 overflow-y-auto p-3">
		<!-- Search -->
		<label class="mb-3 block">
			<span
				class="text-display mb-1 block text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
			>
				BUSCAR
			</span>
			<input
				type="text"
				placeholder="SKU, family_id, team…"
				value={filters.search}
				oninput={(e) => onChange({ search: e.currentTarget.value })}
				class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[11px] text-[var(--color-text-primary)]"
			/>
		</label>

		<!-- Estado -->
		<div class="mb-3">
			<div
				class="text-display mb-1.5 text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
			>
				ESTADO
			</div>
			<div class="space-y-0.5">
				{#each STATES as s (s.slug)}
					{@const checked = filters.states.includes(s.slug)}
					{@const count = stateCounts[s.slug] ?? 0}
					<label
						class="flex cursor-pointer items-center gap-2 rounded-[3px] px-1.5 py-1 text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
					>
						<input
							type="checkbox"
							{checked}
							onchange={() => toggleState(s.slug)}
							class="h-3 w-3 accent-[var(--color-terminal)]"
						/>
						<span class="flex-1">{s.label}</span>
						<span class="text-mono text-[9.5px] tabular-nums text-[var(--color-text-muted)]">
							{count}
						</span>
					</label>
				{/each}
			</div>
		</div>

		<!-- Flags -->
		<div class="mb-3">
			<div
				class="text-display mb-1.5 text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
			>
				FLAGS
			</div>
			<div class="space-y-0.5">
				<label
					class="flex cursor-pointer items-center gap-2 rounded-[3px] px-1.5 py-1 text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
				>
					<input
						type="checkbox"
						checked={filters.dirty}
						onchange={(e) => onChange({ dirty: e.currentTarget.checked })}
						class="h-3 w-3 accent-[var(--color-terminal)]"
					/>
					<span>Dirty</span>
				</label>
				<label
					class="flex cursor-pointer items-center gap-2 rounded-[3px] px-1.5 py-1 text-[11.5px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]"
				>
					<input
						type="checkbox"
						checked={filters.qa_priority}
						onchange={(e) => onChange({ qa_priority: e.currentTarget.checked })}
						class="h-3 w-3 accent-[var(--color-terminal)]"
					/>
					<span>QA priority</span>
				</label>
			</div>
		</div>

		<!-- Last action -->
		<div class="mb-3">
			<div
				class="text-display mb-1.5 text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
			>
				ÚLTIMA ACCIÓN
			</div>
			<select
				value={filters.last_action ?? ''}
				onchange={(e) => {
					const v = e.currentTarget.value;
					onChange({
						last_action:
							v === '' ? undefined : (v as 'today' | 'week' | 'month' | 'older')
					});
				}}
				class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-[11px] text-[var(--color-text-primary)]"
			>
				{#each LAST_ACTION_OPTS as opt (opt.slug)}
					<option value={opt.slug}>{opt.label}</option>
				{/each}
			</select>
		</div>
	</div>
</aside>
