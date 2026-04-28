// Admin Web R7 (T1.3) — Cross-cutting types canonical.
// Spec: overhaul/docs/superpowers/specs/admin-web/types.ts.
// Distribuido en 5 archivos según el plan; este archivo agrupa lo que no
// cabe en jersey-states / tags / overrides / inbox-events:
//   - HomeKpis + KpiSnapshot (Home dashboard)
//   - SavedView + ModuleViewKey (Universo presets)
//   - Filters & pagination (UniversoFilters, SortConfig, PaginationConfig)
//   - Site (Pages, Components, Branding, Communication, Community)
//   - Sistema (Audit log, Scrap, Deploys, Jobs, Backups)
//   - Health monitoring + Command palette
//
// ModuleSlug + EventSeverity vienen de inbox-events.ts (deviación menor del
// plan, ver comentario en ese archivo). Import direction one-way:
// admin-web.ts ← inbox-events.ts.

import type { Jersey, JerseyState } from './jersey-states';
import type { ModuleSlug, EventSeverity } from './inbox-events';

// =============================================================================
// HOME KPIS
// =============================================================================

export interface KpiSnapshot {
	date: string; // 'YYYY-MM-DD'
	kpi_key: string;
	value: number;
}

export interface HomeKpis {
	publicados_total: number;
	stock_live: number;
	queue_count: number;
	scheduled_30d: number;
	activity_month: number;
	supplier_gaps: number;
	hours_since_last_scrap: number;
	dirty_count: number;
	// sparklines (últimos 7 días)
	sparklines: Record<string, number[]>;
}

// =============================================================================
// SAVED VIEWS (Universo, etc.)
// =============================================================================

export type ModuleViewKey =
	| 'vault.universo'
	| 'vault.publicados'
	| 'stock.universo'
	| 'mystery.universo'
	| 'site.pages';

export interface SavedView {
	id: number;
	module: ModuleViewKey;
	slug: string;
	display_name: string;
	icon?: string;
	filters: Record<string, unknown>;
	sort?: { column: string; direction: 'asc' | 'desc' };
	columns?: { key: string; visible: boolean; order: number }[];
	is_factory: boolean;
	display_order: number;
	created_at: number;
}

// =============================================================================
// SITE — PAGES, COMPONENTS, BRANDING, COMMUNICATION, COMMUNITY
// =============================================================================

export type PageCategory = 'static' | 'dynamic_seo' | 'campaign' | 'catalog' | 'account' | 'special';
export type PageStatus = 'draft' | 'live' | 'scheduled';

export type BlockType =
	| 'hero'
	| 'rich_text'
	| 'cta_button'
	| 'gallery'
	| 'testimonials'
	| 'faq_accordion'
	| 'embed_video'
	| 'divider'
	| 'spacer'
	| 'custom_html';

export interface PageBlock {
	id: string; // uuid
	type: BlockType;
	config: Record<string, unknown>; // varía según type
	order: number;
}

export interface SitePage {
	id: number;
	slug: string;
	title: string;
	category: PageCategory;
	status: PageStatus;
	publish_at?: number;
	blocks: PageBlock[];
	seo_meta?: SeoMeta;
	created_at: number;
	updated_at: number;
}

export interface SeoMeta {
	title?: string;
	description?: string;
	og_image?: string;
	og_title?: string;
	og_description?: string;
	twitter_card?: 'summary' | 'summary_large_image';
	canonical_url?: string;
	robots?: string;
}

export type ComponentType =
	| 'header'
	| 'footer'
	| 'banner_top'
	| 'cookie_consent'
	| 'popup_newsletter'
	| 'hero_rotativo'
	| 'chat_widget'
	| 'instagram_feed'
	| 'tiktok_embed'
	| 'reviews_carousel'
	| 'contact_form'
	| 'referrals_ui'
	| 'loyalty_tier_display';

export interface SiteComponent {
	id: number;
	type: ComponentType;
	config: Record<string, unknown>;
	enabled: boolean;
	publish_at?: number;
	unpublish_at?: number;
	created_at: number;
	updated_at: number;
}

export type BrandingValueType = 'string' | 'color' | 'url' | 'json' | 'number' | 'boolean';

export interface BrandingValue {
	key: string; // 'palette.primary', 'logo.dark', 'fonts.heading'
	value: string;
	value_type: BrandingValueType;
	updated_at: number;
	updated_by: string;
}

export type CommunicationChannel = 'email' | 'sms' | 'whatsapp' | 'web_push';

export interface CommunicationTemplate {
	id: number;
	slug: string;
	channel: CommunicationChannel;
	display_name: string;
	subject?: string;
	body: string;
	variables: string[];
	enabled: boolean;
	created_at: number;
	updated_at: number;
}

export interface SubscriberList {
	id: number;
	slug: string;
	display_name: string;
	description?: string;
	segment_rule?: SegmentRule;
	member_count?: number;
	created_at: number;
}

export interface SegmentRule {
	type: 'all_with_email' | 'recent_purchases' | 'inactive_days' | 'custom';
	config: Record<string, unknown>;
}

export interface Subscriber {
	id: number;
	email?: string;
	phone?: string;
	name?: string;
	metadata?: Record<string, unknown>;
	subscribed_at: number;
	unsubscribed_at?: number;
	source?: 'newsletter_form' | 'import' | 'order';
}

export interface Workflow {
	id: number;
	slug: string;
	display_name: string;
	trigger_type: WorkflowTrigger;
	trigger_config?: Record<string, unknown>;
	steps: WorkflowStep[];
	enabled: boolean;
	created_at: number;
	updated_at: number;
}

export type WorkflowTrigger =
	| 'order_placed'
	| 'order_shipped'
	| 'cart_abandoned'
	| 'newsletter_signup'
	| 'review_submitted'
	| 'birthday'
	| 'inactive_60d';

export interface WorkflowStep {
	id: string;
	template_id: number;
	delay_seconds?: number;
	condition?: WorkflowCondition;
}

export interface WorkflowCondition {
	type: 'opened_previous' | 'clicked_previous' | 'metadata_match';
	config: Record<string, unknown>;
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'featured';

export interface Review {
	id: number;
	family_id?: string;
	customer_id?: number;
	rating: number; // 1-5
	title?: string;
	body: string;
	photo_urls?: string[];
	status: ReviewStatus;
	moderation_note?: string;
	submitted_at: number;
	moderated_at?: number;
	moderated_by?: string;
}

export interface Survey {
	id: number;
	slug: string;
	display_name: string;
	questions: SurveyQuestion[];
	trigger?: 'pre_checkout' | 'post_purchase' | 'nps_quarterly';
	enabled: boolean;
	created_at: number;
}

export interface SurveyQuestion {
	id: string;
	type: 'rating_1_5' | 'rating_1_10' | 'multiple_choice' | 'free_text' | 'nps';
	question: string;
	options?: string[];
	required: boolean;
}

// =============================================================================
// SISTEMA — AUDIT LOG, SCRAP HISTORY, DEPLOYS, JOBS, BACKUPS, CONFIG
// =============================================================================

export type AuditAction =
	| 'create'
	| 'update'
	| 'delete'
	| 'archive'
	| 'revive'
	| 'publish'
	| 'unpublish'
	| 'bulk_action'
	| 'login'
	| 'logout';
export type AuditSeverity = 'info' | 'warning' | 'critical';

export interface AuditLogEntry {
	id: number;
	timestamp: number;
	user: string;
	module: ModuleSlug;
	action: AuditAction;
	entity_type?: string; // 'jersey', 'tag', 'override', 'page'
	entity_id?: string;
	diff?: { before?: unknown; after?: unknown; fields?: string[] };
	severity: AuditSeverity;
	ip_address?: string;
	user_agent?: string;
}

export type ScrapStatus = 'running' | 'success' | 'failed' | 'cancelled';

export interface ScrapHistoryEntry {
	id: number;
	category_url: string;
	domain?: string;
	status: ScrapStatus;
	started_at: number;
	finished_at?: number;
	firecrawl_credits_used?: number;
	families_created?: number;
	families_wiped?: number;
	galleries_fetched?: number;
	errors?: string;
	triggered_by: string;
}

export type DeployTarget = 'worker' | 'site' | 'erp_msi';
export type DeployStatus = 'running' | 'success' | 'failed' | 'rolled_back';

export interface DeployHistoryEntry {
	id: number;
	target: DeployTarget;
	version: string;
	commit_sha?: string;
	status: DeployStatus;
	started_at: number;
	finished_at?: number;
	triggered_by: string;
	release_notes?: string;
}

export interface ScheduledJob {
	id: number;
	slug: string;
	display_name: string;
	cron_expression: string;
	handler: string;
	enabled: boolean;
	last_run_at?: number;
	last_status?: 'success' | 'failed';
	last_error?: string;
	next_run_at?: number;
	created_at: number;
}

export type BackupType = 'catalog' | 'db' | 'r2_manifest' | 'full';

export interface BackupEntry {
	id: number;
	type: BackupType;
	path: string;
	size_bytes?: number;
	created_at: number;
	triggered_by: 'cron' | 'diego';
	expires_at?: number;
}

// =============================================================================
// HEALTH MONITORING
// =============================================================================

export interface HealthSnapshot {
	worker_uptime_pct: number;
	worker_latency_p50_ms: number;
	worker_latency_p95_ms: number;
	error_rate_pct: number;
	cdn_cache_hit_pct: number;
	r2_storage_gb: number;
	kv_ops_per_min: number;
	firecrawl_credits_remaining: number;
	firecrawl_credits_total: number;
	last_scrap_at: number;
	db_size_mb: number;
	active_sessions: number;
	active_alerts: HealthAlert[];
}

export interface HealthAlert {
	metric: string;
	severity: EventSeverity;
	message: string;
	triggered_at: number;
}

// =============================================================================
// COMMAND PALETTE
// =============================================================================

export type CommandCategory = 'navigation' | 'action' | 'search' | 'config';

export interface CommandPaletteItem {
	id: string;
	category: CommandCategory;
	label: string;
	description?: string;
	icon?: string;
	shortcut?: string;
	action: () => void | Promise<void>;
	search_terms?: string[]; // términos extra para fuzzy match
}

// =============================================================================
// FILTERS & PAGINATION (común a vistas densas — Universo, Publicados, etc.)
// =============================================================================

export interface UniversoFilters {
	states?: JerseyState[];
	flags?: Partial<{
		dirty: boolean;
		scrap_fail: boolean;
		low_coverage: boolean;
		supplier_gap: boolean;
		qa_priority: boolean;
	}>;
	product?: Partial<{
		in_stock: boolean;
		in_mystery: boolean;
		stock_scheduled: boolean;
		mystery_scheduled: boolean;
	}>;
	tags?: number[]; // IDs de tags
	coverage_min?: number;
	coverage_max?: number;
	last_action?: 'today' | 'week' | 'month' | 'older';
	search?: string; // texto libre (SKU, team, etc.)
}

export interface SortConfig {
	column: string;
	direction: 'asc' | 'desc';
}

export interface PaginationConfig {
	page: number; // 1-indexed
	per_page: number;
}

export interface UniversoQueryResult {
	rows: Jersey[];
	total: number;
	filters_counts: Record<string, number>;
}
