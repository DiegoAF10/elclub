<!--
	KpisGrid — grid 4×2 con 8 KPIs del Home. Lee adminWeb.get_admin_web_kpis()
	on-mount y renderiza una tarjeta por KPI con icon + value + sparkline.
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import type { HomeKpis } from '$lib/adapter';
	import {
		Rocket,
		Package,
		Inbox,
		Calendar,
		Activity,
		AlertTriangle,
		RefreshCw,
		AlertCircle
	} from 'lucide-svelte';
	import KpiCard from './KpiCard.svelte';

	let kpis = $state<HomeKpis | null>(null);
	let loading = $state(true);

	async function loadKpis() {
		loading = true;
		try {
			kpis = await adminWeb.get_admin_web_kpis();
		} catch {
			kpis = null;
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void loadKpis();
	});

	function spark(key: string): number[] {
		return kpis?.sparklines?.[key] ?? [];
	}

	// Tone helpers: thresholds para severity visual
	function queueTone(n: number): 'default' | 'warn' | 'critical' {
		if (n >= 30) return 'critical';
		if (n >= 12) return 'warn';
		return 'default';
	}
	function dirtyTone(n: number): 'default' | 'warn' | 'critical' {
		if (n >= 10) return 'critical';
		if (n >= 3) return 'warn';
		return 'default';
	}
	function scrapTone(h: number): 'default' | 'warn' | 'critical' {
		if (h >= 168) return 'critical'; // > 1 semana
		if (h >= 48) return 'warn';
		return 'default';
	}
	function gapsTone(n: number): 'default' | 'warn' | 'critical' {
		if (n >= 50) return 'critical';
		if (n >= 15) return 'warn';
		return 'default';
	}
</script>

{#if loading}
	<div class="grid grid-cols-4 gap-3">
		{#each Array(8) as _, i (i)}
			<div
				class="h-20 animate-pulse rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
			></div>
		{/each}
	</div>
{:else if kpis}
	<div class="grid grid-cols-4 gap-3">
		<KpiCard
			icon={Rocket}
			label="Publicados"
			value={kpis.publicados_total}
			target="/admin-web/vault/publicados"
			sparkline={spark('publicados_total')}
		/>
		<KpiCard
			icon={Package}
			label="Stock live"
			value={kpis.stock_live}
			target="/admin-web/stock/drops"
			sparkline={spark('stock_live')}
		/>
		<KpiCard
			icon={Inbox}
			label="Queue"
			value={kpis.queue_count}
			target="/admin-web/vault/queue"
			sparkline={spark('queue_count')}
			tone={queueTone(kpis.queue_count)}
		/>
		<KpiCard
			icon={Calendar}
			label="Scheduled 30d"
			value={kpis.scheduled_30d}
			target="/admin-web/stock/calendario"
			sparkline={spark('scheduled_30d')}
		/>
		<KpiCard
			icon={Activity}
			label="Actividad mes"
			value={kpis.activity_month}
			target="/admin-web/sistema/audit"
			sparkline={spark('activity_month')}
		/>
		<KpiCard
			icon={AlertTriangle}
			label="Supplier gaps"
			value={kpis.supplier_gaps}
			target="/admin-web/vault/universo"
			sparkline={spark('supplier_gaps')}
			tone={gapsTone(kpis.supplier_gaps)}
		/>
		<KpiCard
			icon={RefreshCw}
			label="Last scrap"
			value={kpis.hours_since_last_scrap >= 999 ? '—' : kpis.hours_since_last_scrap}
			suffix={kpis.hours_since_last_scrap >= 999 ? '' : 'h'}
			target="/admin-web/sistema/operaciones"
			sparkline={spark('hours_since_last_scrap')}
			tone={scrapTone(kpis.hours_since_last_scrap)}
		/>
		<KpiCard
			icon={AlertCircle}
			label="Dirty count"
			value={kpis.dirty_count}
			target="/admin-web/vault/universo"
			sparkline={spark('dirty_count')}
			tone={dirtyTone(kpis.dirty_count)}
		/>
	</div>
{:else}
	<div
		class="rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-6 text-center text-[12px] text-[var(--color-text-muted)]"
	>
		No se pudieron cargar los KPIs.
	</div>
{/if}
