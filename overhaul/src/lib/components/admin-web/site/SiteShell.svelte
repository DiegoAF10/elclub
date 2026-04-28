<!--
	SiteShell — cascarón v0 del módulo Site (CMS de elclub.club).
	Header + 6 tabs. R7.3 profundiza con editor de bloques rico, A/B testing,
	multi-idioma. Por ahora solo navegación de tabs + placeholders.

	Tab routing: /admin-web/site/{paginas|branding|componentes|comunicacion|comunidad|meta-tracking}
-->
<script lang="ts">
	import TabBar from '../shared/TabBar.svelte';
	import PlaceholderPanel from '../shared/PlaceholderPanel.svelte';
	import { Globe } from 'lucide-svelte';

	interface Props {
		tab?: string;
	}
	let { tab = 'paginas' }: Props = $props();

	const TABS = [
		{ slug: 'paginas', label: 'Páginas' },
		{ slug: 'branding', label: 'Branding' },
		{ slug: 'componentes', label: 'Componentes' },
		{ slug: 'comunicacion', label: 'Comunicación' },
		{ slug: 'comunidad', label: 'Comunidad' },
		{ slug: 'meta-tracking', label: 'Meta + Tracking' }
	];

	const PANEL_DESC: Record<string, string> = {
		paginas:
			'CRUD de site_pages con editor de bloques (hero, rich_text, gallery, faq, etc). 6 categorías: static, dynamic_seo, campaign, catalog, account, special.',
		branding:
			'Editor key-value de site_branding (palette, fonts, logos). Apply triggera deploy.',
		componentes:
			'Toggle ON/OFF + config de site_components (header, footer, banner_top, cookie_consent, popup, hero_rotativo, chat, etc).',
		comunicacion:
			'Templates de email/sms/whatsapp + workflows + listas de subscribers.',
		comunidad: 'Moderación de reviews, surveys, encuestas NPS.',
		'meta-tracking': 'Pixel events, OG tags, Schema.org, GA4, Search Console.'
	};

	const titleByTab = $derived(
		`SITE · ${(TABS.find((t) => t.slug === tab)?.label ?? tab).toUpperCase()}`
	);
	const descByTab = $derived(PANEL_DESC[tab] ?? 'Cascarón placeholder.');
</script>

<div class="flex flex-1 flex-col">
	<div
		class="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-4"
	>
		<Globe size={16} strokeWidth={1.8} class="text-[var(--color-text-secondary)]" />
		<div>
			<div class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]">SITE</div>
			<div class="text-[10.5px] text-[var(--color-text-muted)]">Landing + branding + comunicación</div>
		</div>
	</div>

	<TabBar basePath="/admin-web/site" tabs={TABS} active={tab} />

	<PlaceholderPanel title={titleByTab} description={descByTab} future="R7.3" />
</div>
