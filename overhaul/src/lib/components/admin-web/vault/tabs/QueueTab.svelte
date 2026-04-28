<!--
	QueueTab — vista simplificada del Queue dentro de Admin Web > Vault.

	NOTA T4.2: el plan original decía "wrap del Audit existente sin cambios,
	reutilizar el modal grande FM-style". Esto requeriría extraer la mitad
	del legacy +page.svelte (ListPane + DetailPane + estado de selección
	+ adapter calls) en un componente reusable. Riesgo alto sin valor para
	R7 (la rama no debe romper el Audit existente hasta T8.6 ship).

	Por ahora QueueTab muestra:
	  - Header con queue_count
	  - Botón "AUDIT COMPLETO" que navega a / (donde vive el Audit FM-style
	    completo) — el usuario sale del Admin Web hacia el ERP raíz.
	  - Lista compacta de los próximos N pendientes (sku + tier + decided_at)
	    con click → mismo redirect.

	En R7.0.1 (post-ship) se puede refactorizar +page.svelte para que el
	Audit tool sea un componente standalone embedable acá. Hoy: link out.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { ExternalLink, Inbox, Clock } from 'lucide-svelte';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';
	import type { AuditDecision } from '$lib/adapter';

	let pending = $state<AuditDecision[]>([]);
	let loaded = $state(false);

	async function load() {
		try {
			const list = await adapter.listDecisions({ status: 'pending' });
			pending = list;
		} catch (err) {
			if (!(err instanceof NotAvailableInBrowser)) {
				// eslint-disable-next-line no-console
				console.error('[QueueTab] listDecisions fallo:', err);
			}
			pending = [];
		} finally {
			loaded = true;
		}
	}

	$effect(() => {
		void load();
	});

	function gotoAudit() {
		// Navegar al ERP raíz — el Audit tool vive ahí (sidebarActive='audit')
		void goto('/');
	}

	function formatRelative(iso: string | null | undefined): string {
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

<div class="flex h-full flex-col p-6">
	<!-- Header summary -->
	<div class="mb-4 flex items-start justify-between gap-4">
		<div>
			<div class="flex items-center gap-2">
				<Inbox size={18} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
				<h2
					class="text-display text-[18px] tracking-[0.16em] text-[var(--color-text-primary)]"
				>
					QUEUE
				</h2>
				<span
					class="text-mono ml-2 rounded-[3px] bg-[var(--color-surface-2)] px-2 py-1 text-[12px] font-semibold tabular-nums text-[var(--color-terminal)]"
				>
					{loaded ? pending.length : '—'}
				</span>
			</div>
			<p class="mt-1 text-[12px] text-[var(--color-text-secondary)]">
				Jerseys esperando audit (status=<span class="text-mono">pending</span>). El audit
				completo con modal FM-style + atajos V/F/S vive en el Audit tool del ERP raíz.
			</p>
		</div>

		<button
			type="button"
			onclick={gotoAudit}
			class="text-mono flex shrink-0 items-center gap-1.5 rounded-[3px] border border-[var(--color-terminal)] bg-[var(--color-terminal)] px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-bg)] transition-colors hover:bg-[var(--color-terminal)]/90"
		>
			Audit completo
			<ExternalLink size={12} strokeWidth={2} />
		</button>
	</div>

	<!-- Lista compacta -->
	<div
		class="flex-1 overflow-y-auto rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
	>
		{#if !loaded}
			<div class="p-4 text-[11px] text-[var(--color-text-muted)]">Cargando…</div>
		{:else if pending.length === 0}
			<div class="flex h-full items-center justify-center p-8 text-center">
				<div>
					<div
						class="text-display mb-2 text-[14px] tracking-[0.16em] text-[var(--color-live)]"
					>
						● ALL CLEAR
					</div>
					<p class="text-[11.5px] text-[var(--color-text-muted)]">
						No hay jerseys esperando audit.
					</p>
				</div>
			</div>
		{:else}
			<table class="w-full text-[12px]">
				<thead
					class="text-display sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] text-[9.5px] tracking-[0.14em] text-[var(--color-text-tertiary)]"
				>
					<tr>
						<th class="px-3 py-2 text-left">SKU</th>
						<th class="px-3 py-2 text-left">Tier</th>
						<th class="px-3 py-2 text-left">Decisión</th>
						<th class="px-3 py-2"></th>
					</tr>
				</thead>
				<tbody>
					{#each pending.slice(0, 100) as d (d.sku)}
						<tr
							class="border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-surface-2)]"
						>
							<td class="text-mono px-3 py-2 text-[var(--color-text-primary)]">{d.sku}</td>
							<td class="text-mono px-3 py-2 text-[var(--color-text-secondary)]">
								{d.tier ?? '—'}
							</td>
							<td
								class="text-mono px-3 py-2 text-[var(--color-text-muted)]"
							>
								<span class="inline-flex items-center gap-1">
									<Clock size={11} strokeWidth={1.8} />
									{formatRelative(d.decided_at)}
								</span>
							</td>
							<td class="px-3 py-2 text-right">
								<button
									type="button"
									onclick={gotoAudit}
									class="text-display rounded-[3px] px-2 py-1 text-[9.5px] tracking-wide text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]"
									title="Abrir Audit completo"
								>
									ABRIR →
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
			{#if pending.length > 100}
				<div
					class="border-t border-[var(--color-border)] p-2 text-center text-[10.5px] text-[var(--color-text-muted)]"
				>
					Mostrando 100 de {pending.length} · ir al Audit para ver todos
				</div>
			{/if}
		{/if}
	</div>
</div>
