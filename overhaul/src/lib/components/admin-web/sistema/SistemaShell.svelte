<!--
	SistemaShell — cascarón v0 del módulo Sistema (health + ops + audit + config).
	Header + 4 tabs. R7.4 profundiza con deploy buttons funcionales, scrap UI real.

	Tab routing: /admin-web/sistema/{status|operaciones|configuracion|audit}
-->
<script lang="ts">
	import TabBar from '../shared/TabBar.svelte';
	import PlaceholderPanel from '../shared/PlaceholderPanel.svelte';
	import { Server } from 'lucide-svelte';

	interface Props {
		tab?: string;
	}
	let { tab = 'status' }: Props = $props();

	const TABS = [
		{ slug: 'status', label: 'Status' },
		{ slug: 'operaciones', label: 'Operaciones' },
		{ slug: 'configuracion', label: 'Configuración' },
		{ slug: 'audit', label: 'Audit' }
	];

	const PANEL_DESC: Record<string, string> = {
		status:
			'Health snapshot — uptime, latency p50/p95, error rate, CDN hit, R2 storage, KV ops, Firecrawl credits.',
		operaciones:
			'Scrap history + trigger nuevo scrap, deploy history + trigger/rollback, scheduled_jobs + run-now, backups create/restore.',
		configuracion:
			'admin_web_config key-value editor + API connections (test + rotate secrets).',
		audit: 'system_audit_log con filtros (module, user, period, severity) + export CSV.'
	};

	const titleByTab = $derived(
		`SISTEMA · ${(TABS.find((t) => t.slug === tab)?.label ?? tab).toUpperCase()}`
	);
	const descByTab = $derived(PANEL_DESC[tab] ?? 'Cascarón placeholder.');
</script>

<div class="flex flex-1 flex-col">
	<div
		class="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4"
	>
		<Server size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
		<div>
			<div class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]">
				SISTEMA
			</div>
			<div class="text-[10.5px] text-[var(--color-text-muted)]">Health · Ops · Config · Audit</div>
		</div>
	</div>

	<TabBar basePath="/admin-web/sistema" tabs={TABS} active={tab} />

	<PlaceholderPanel title={titleByTab} description={descByTab} future="R7.4" />
</div>
