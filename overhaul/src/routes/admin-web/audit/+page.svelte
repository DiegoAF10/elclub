<!--
	/admin-web/audit — interface raíz completo de auditoría de catálogo.

	Mudado desde /+page.svelte raíz cuando ADM-Sidebar-Reorg (Iteración Continuous,
	2026-04-28) eliminó el item Audit del sidebar global y agrupó workflow dentro
	de Admin Web. Este archivo replica EXACTAMENTE el comportamiento original:

	  - ListPane (left) muestra families agrupadas + selección SKU/Family
	  - DetailPane (right · default mode SKU) muestra el SKU seleccionado
	  - FamilyPdpPane (right · mode Family) muestra family-level view
	  - CommandPalette ⌘K busca SKUs
	  - Atajos vim: j/k navegan SKUs · v/f/s setean decision (verified/flagged/skipped)
	  - handleMoveModelo: drag-drop entre families con migration de audit_decisions

	El AdminWebShell (parent layout) ya provee sidebar interno + breadcrumb +
	su propio command palette con atajos 'g X'. Coexisten:
	  - AdminWebCommandPalette (⌘K outside any input · navega entre sub-modules)
	  - este CommandPalette (⌘K dentro del audit · busca SKUs)

	Ambos escuchan ⌘K — el del audit gana porque montamos handleKey con
	stopPropagation cuando esta página está activa. Ver TODO al final.
-->
<script lang="ts">
	import ListPane from '$lib/components/ListPane.svelte';
	import DetailPane from '$lib/components/DetailPane.svelte';
	import FamilyPdpPane from '$lib/components/FamilyPdpPane.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import { familiesByGroup, allSkus } from '$lib/data/source';
	import type { PageData } from './+page';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';
	import type { AuditStatus } from '$lib/adapter';
	import { invalidateAll } from '$app/navigation';

	let { data }: { data: PageData } = $props();

	let families = $derived(data.families);
	let groups = $derived(familiesByGroup(families));
	let skus = $derived(allSkus(families));

	// Selection modes — SKU o Family (mutually exclusive)
	let selectedSku = $state<string | null>(null);
	let selectedFamilyId = $state<string | null>(null);
	let commandOpen = $state(false);

	async function handleMoveModelo(sourceFid: string, sourceModeloIdx: number, targetFid: string) {
		try {
			const result = await adapter.moveModelo({
				sourceFid,
				sourceModeloIdx,
				targetFid
			});
			if (result.ok) {
				const migCount = result.migrated
					? result.migrated.audit_decisions + result.migrated.audit_photo_actions
					: 0;
				flash(
					`✓ ${result.old_skus[0] ?? ''} → ${result.new_skus[0] ?? result.target_fid ?? ''}${migCount ? ` · ${migCount} migrados` : ''}`
				);
				if (result.new_skus[0]) selectSku(result.new_skus[0]);
				await invalidateAll();
			} else {
				flash(`✗ Move falló: ${result.error ?? 'unknown'}`);
				await invalidateAll();
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) flash('Move: requiere .exe');
			else flash(`Move falló: ${err instanceof Error ? err.message : err}`);
			await invalidateAll();
		}
	}

	// Inicializar selección al primer modelo una vez que las families cargan.
	$effect(() => {
		if (selectedSku === null && selectedFamilyId === null && families.length > 0) {
			const firstSku = families[0]?.modelos[0]?.sku;
			if (firstSku) selectedSku = firstSku;
		}
	});

	let currentMode = $derived<'sku' | 'family'>(selectedFamilyId ? 'family' : 'sku');

	let selectedFamily = $derived.by(() => {
		if (selectedFamilyId) {
			return families.find((f) => f.id === selectedFamilyId) ?? null;
		}
		if (selectedSku) {
			for (const fam of families) {
				if (fam.modelos.some((m) => m.sku === selectedSku)) return fam;
			}
		}
		return null;
	});

	let selectedModelo = $derived.by(() => {
		if (currentMode === 'family') return null;
		if (!selectedFamily || !selectedSku) return null;
		return selectedFamily.modelos.find((m) => m.sku === selectedSku) ?? null;
	});

	function selectSku(sku: string) {
		selectedSku = sku;
		selectedFamilyId = null;
	}

	function selectFamily(fid: string) {
		selectedFamilyId = fid;
		selectedSku = null;
	}

	function handleKey(e: KeyboardEvent) {
		const target = e.target as HTMLElement;
		if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
			if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
				e.preventDefault();
				commandOpen = true;
			}
			return;
		}

		if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
			e.preventDefault();
			// stopPropagation evita que AdminWebCommandPalette (parent) también abra.
			// Cuando estás en /admin-web/audit, ⌘K busca SKUs (el caso de uso real).
			e.stopPropagation();
			commandOpen = true;
			return;
		}

		if (e.key === 'j' || e.key === 'ArrowDown') {
			e.preventDefault();
			if (currentMode === 'sku' && selectedSku) {
				const idx = skus.findIndex((s) => s.sku === selectedSku);
				if (idx >= 0 && idx < skus.length - 1) selectSku(skus[idx + 1].sku);
			}
		} else if (e.key === 'k' || e.key === 'ArrowUp') {
			e.preventDefault();
			if (currentMode === 'sku' && selectedSku) {
				const idx = skus.findIndex((s) => s.sku === selectedSku);
				if (idx > 0) selectSku(skus[idx - 1].sku);
			}
		}

		if (e.key === 'v' || e.key === 'V') {
			e.preventDefault();
			void triggerDecision('verified', '✓ Verify');
		} else if (e.key === 'f' || e.key === 'F') {
			e.preventDefault();
			void triggerDecision('flagged', '⚑ Flag');
		} else if (e.key === 's' || e.key === 'S') {
			e.preventDefault();
			void triggerDecision('skipped', '⏭ Skip');
		}
	}

	async function triggerDecision(status: AuditStatus, label: string) {
		if (!selectedSku) {
			flash(`${label}: seleccioná un SKU primero`);
			return;
		}
		const sku = selectedSku;
		try {
			await adapter.setDecisionStatus(sku, status);
			flash(`${label} · ${sku}`);
			await invalidateAll();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				flash(`${label}: requiere el .exe — browser mode es read-only`);
			} else {
				flash(`${label} falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	let toastMsg = $state('');
	let toastTimer: ReturnType<typeof setTimeout> | null = null;
	function flash(msg: string) {
		toastMsg = msg;
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(() => (toastMsg = ''), 1800);
	}
</script>

<svelte:window onkeydown={handleKey} />

{#if data.loadError}
	<div class="flex h-full items-center justify-center bg-[var(--color-bg)] p-8">
		<div
			class="max-w-xl rounded-lg border border-[var(--color-danger)] bg-[var(--color-surface-1)] p-6 text-[13px] text-[var(--color-text-primary)]"
		>
			<div class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-danger)]">
				Error al cargar el catálogo
			</div>
			<div class="mb-3 text-[var(--color-text-secondary)]">{data.loadError}</div>
			<div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">
				adapter: {data.adapterPlatform}
			</div>
		</div>
	</div>
{:else if families.length === 0}
	<div class="flex h-full items-center justify-center bg-[var(--color-bg)] p-8">
		<div
			class="max-w-md rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-1)] p-6 text-[13px] text-[var(--color-text-primary)]"
		>
			<div class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)]">
				Catálogo vacío
			</div>
			<div class="mb-3 text-[var(--color-text-secondary)]">
				No hay families en <code class="text-mono">catalog.json</code>. Scrape nuevas families
				via el ERP viejo (Streamlit) y van a aparecer acá para auditar.
			</div>
			<div class="text-[11px] text-[var(--color-text-tertiary)]">
				adapter: <span class="text-mono">{data.adapterPlatform}</span>
			</div>
		</div>
	</div>
{:else}
	<div class="flex h-full">
		<ListPane
			{groups}
			{selectedSku}
			{selectedFamilyId}
			onSelectSku={selectSku}
			onSelectFamily={selectFamily}
			onMoveModelo={handleMoveModelo}
		/>
		{#if currentMode === 'family' && selectedFamily}
			<FamilyPdpPane
				family={selectedFamily}
				onSelectSku={selectSku}
				onFlash={flash}
				onRefresh={() => void invalidateAll()}
			/>
		{:else}
			<DetailPane
				family={selectedFamily}
				modelo={selectedModelo}
				{families}
				onSelectSku={selectSku}
				onFlash={flash}
				onRefresh={() => void invalidateAll()}
			/>
		{/if}
	</div>

	<CommandPalette
		open={commandOpen}
		allSkus={skus}
		onClose={() => (commandOpen = false)}
		onSelect={selectSku}
	/>

	{#if toastMsg}
		<div
			class="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-2)] px-4 py-2.5 text-[13px] font-medium text-[var(--color-text-primary)] shadow-2xl"
		>
			{toastMsg}
		</div>
	{/if}
{/if}
