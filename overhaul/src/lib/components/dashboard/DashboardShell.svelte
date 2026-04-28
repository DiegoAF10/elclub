<!--
	DashboardShell — cascarón del Dashboard del ERP raíz (sidebar global · primer
	item DATA). Reservado para la PRÓXIMA iteración: hub principal del ERP con
	KPIs agregados de los 4 módulos top-level (Comercial · Importaciones · Finanzas
	· Admin Web) + acciones rápidas + actividad reciente.

	Diego (2026-04-28): "Dashboard es el último de la cola porque primero tiene
	que quedar todo hecho, esto solo es una vista de lo ya construido."

	Visión preliminar (a refinar cuando arranque DASH-Rx):
	  - Hero: pregunta canonical (estilo ProfitHeroCard de FIN) — "¿qué pasó hoy?"
	  - Sub-grid: KPIs cross-módulo (sales del día · imports en pipeline ·
	    profit MTD · queue audit · alertas críticas)
	  - Quick actions: + Nueva venta · + Nuevo gasto · + Nuevo pedido · ⌘K
	  - Activity stream: últimos 20 eventos cross-módulo (sale shipped, expense
	    logged, batch closed, etc.)
	  - InboxFinanciero global (no sólo FIN)
-->
<script lang="ts">
	import { LayoutDashboard } from 'lucide-svelte';
</script>

<div class="flex h-full flex-col">
	<div
		class="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4"
	>
		<LayoutDashboard size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
		<div>
			<div class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]">
				DASHBOARD
			</div>
			<div class="text-[10.5px] text-[var(--color-text-muted)]">
				Hub principal · KPIs cross-módulo · acciones rápidas
			</div>
		</div>
	</div>

	<div class="flex flex-1 items-center justify-center p-8">
		<div class="max-w-lg text-center">
			<div
				class="text-display mb-3 text-[20px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				DASHBOARD
			</div>
			<p class="text-[12.5px] leading-relaxed text-[var(--color-text-secondary)]">
				El hub principal del ERP — una vista consolidada de todo lo construido en
				Comercial · Importaciones · Finanzas · Admin Web. Acciones rápidas, KPIs
				agregados, actividad reciente y atajos a lo que importa hoy.
			</p>
			<p
				class="mt-3 text-[12px] italic leading-relaxed text-[var(--color-text-tertiary)]"
			>
				Es el último en construirse · primero los módulos individuales tienen que
				quedar al 100%.
			</p>
			<div
				class="text-mono mt-5 inline-block rounded-[3px] bg-[var(--color-surface-2)] px-2.5 py-1 text-[10px] tracking-wide text-[var(--color-text-tertiary)]"
			>
				PRÓXIMA ITERACIÓN · DASH-R1 (brainstorm pendiente)
			</div>
		</div>
	</div>
</div>
