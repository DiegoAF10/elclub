<!--
	/  — ERP raíz · dispatcher de shells de los 4 módulos top-level.

	Post sidebar reorg arquitectural (Iteración Continuous · 2026-04-28):
	Este archivo se simplificó dramáticamente. Antes albergaba el Audit interface
	completo (ListPane + DetailPane + FamilyPdpPane + CommandPalette +
	MundialCoverageModal). Ahora todo eso vive en /admin-web/audit y
	/admin-web/mundial, dejando este page como un dispatcher mínimo entre los
	shells de los 4 módulos disponibles desde el sidebar global:

	  - Dashboard      (cascarón hub principal · DASH-Rx pendiente)
	  - Comercial      (ComercialShell)
	  - Importaciones  (ImportShell)
	  - Finanzas       (FinanzasShell)
	  - Admin Web      (URL space disjunto · goto('/admin-web/home'))

	Default landing es 'dashboard' (primer item DATA · cascarón honesto).
-->
<script lang="ts">
	import Sidebar from '$lib/components/Sidebar.svelte';
	import DashboardShell from '$lib/components/dashboard/DashboardShell.svelte';
	import ComercialShell from '$lib/components/comercial/ComercialShell.svelte';
	import ImportShell from '$lib/components/importaciones/ImportShell.svelte';
	import FinanzasShell from '$lib/components/finanzas/FinanzasShell.svelte';
	import { goto } from '$app/navigation';

	let sidebarActive = $state('dashboard');

	function handleSidebarSelect(id: string) {
		if (id === 'admin-web') {
			// Admin Web vive en URL space separado (/admin-web/*) con su propio
			// chrome (AdminWebShell). Navegamos en lugar de mutar sidebarActive.
			void goto('/admin-web');
			return;
		}
		sidebarActive = id;
	}

	// Toast simple para mensajes de Sidebar (push/sync results)
	let toastMsg = $state('');
	let toastTimer: ReturnType<typeof setTimeout> | null = null;
	function flash(msg: string) {
		toastMsg = msg;
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(() => (toastMsg = ''), 1800);
	}
</script>

<div class="fixed inset-0 flex">
	<Sidebar active={sidebarActive} onSelect={handleSidebarSelect} onPushResult={flash} />

	<div class="flex-1 overflow-hidden">
		{#if sidebarActive === 'dashboard'}
			<DashboardShell />
		{:else if sidebarActive === 'comercial'}
			<ComercialShell />
		{:else if sidebarActive === 'importaciones'}
			<ImportShell />
		{:else if sidebarActive === 'finanzas'}
			<FinanzasShell />
		{:else}
			<!-- Fallback defensivo: si algún ID desconocido llega vía sidebar/state, mostramos Dashboard -->
			<DashboardShell />
		{/if}
	</div>
</div>

{#if toastMsg}
	<div
		class="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-2)] px-4 py-2.5 text-[13px] font-medium text-[var(--color-text-primary)] shadow-2xl"
	>
		{toastMsg}
	</div>
{/if}
