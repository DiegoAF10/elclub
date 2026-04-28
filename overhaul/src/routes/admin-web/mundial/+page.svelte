<!--
	/admin-web/mundial — Mundial 2026 coverage view.

	Mudado desde /+page.svelte raíz cuando ADM-Sidebar-Reorg (Iteración Continuous,
	2026-04-28) movió el item Mundial 2026 del sidebar global al sidebar interno
	de Admin Web (Workflow group).

	Aproach: reusamos MundialCoverageModal con `open=true` permanente. El "cerrar"
	del modal es el botón "← Volver al ERP" del AdminWebShell (nav superior). Si
	el user clickea una family, navegamos a /admin-web/audit (donde el catálogo
	puede inspeccionarse al detalle).

	Alternativa futura: refactorear MundialCoverageModal a CoverageView (sin chrome
	de modal · embedido directo). Por ahora el reuse evita duplicación.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import MundialCoverageModal from '$lib/components/MundialCoverageModal.svelte';
	import type { PageData } from './+page';

	let { data }: { data: PageData } = $props();
	let families = $derived(data.families);

	function handleSelectFamily(_fid: string) {
		// TODO: pasar el fid via query param a /admin-web/audit?family=...
		// para preseleccionar. Por ahora solo navegamos al Audit interface.
		void goto('/admin-web/audit');
	}

	function handleClose() {
		// "Cerrar" en este contexto = volver al Home del Admin Web.
		void goto('/admin-web/home');
	}
</script>

{#if data.loadError}
	<div class="flex h-full items-center justify-center bg-[var(--color-bg)] p-8">
		<div class="max-w-xl rounded-lg border border-[var(--color-danger)] bg-[var(--color-surface-1)] p-6 text-[13px] text-[var(--color-text-primary)]">
			<div class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-danger)]">
				Error al cargar el catálogo
			</div>
			<div class="text-[var(--color-text-secondary)]">{data.loadError}</div>
		</div>
	</div>
{:else}
	<MundialCoverageModal
		open={true}
		{families}
		onClose={handleClose}
		onSelectFamily={handleSelectFamily}
	/>
{/if}
