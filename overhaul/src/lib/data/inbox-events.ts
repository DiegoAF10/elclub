// Admin Web R7 (T1.3) — Inbox events (Home + cron detector).
// Spec: overhaul/docs/superpowers/specs/admin-web/types.ts (sección INBOX EVENTS).
// Schema: inbox_events (admin_web schema migration T1.1).
// Catálogo de detectores: overhaul/docs/superpowers/specs/admin-web/inbox-events-catalog.json.
//
// NOTA T1.3: ModuleSlug se define aquí en lugar de admin-web.ts (deviación
// menor del plan) porque es donde el spec lo introduce naturalmente — al lado
// de los EventType que se taggean por módulo. admin-web.ts importa desde
// acá. Mantiene una sola dirección de imports (admin-web.ts ← inbox-events.ts).

export type ModuleSlug = 'vault' | 'stock' | 'mystery' | 'site' | 'sistema';

export type EventSeverity = 'critical' | 'important' | 'info';

export type EventType =
	// Vault
	| 'queue_pending'
	| 'dirty_detected'
	| 'orphan_drafts'
	| 'scrap_fail'
	| 'archived_old'
	| 'supplier_gap_new'
	| 'no_tag_era'
	| 'no_tag_geography'
	// Stock
	| 'stock_drop_starting_24h'
	| 'stock_drop_ending_24h'
	| 'stock_override_no_publish_at'
	| 'stock_drop_old_no_update'
	// Mystery
	| 'mystery_pool_low'
	| 'mystery_pool_empty'
	| 'mystery_drop_starting_24h'
	| 'mystery_drop_ending_24h'
	| 'mystery_jersey_never_delivered'
	// Site
	| 'branding_changed'
	| 'banner_expires_24h'
	| 'page_draft_stale'
	| '404_spike'
	| 'reviews_pending_moderation'
	| 'ab_test_significant'
	| 'email_workflow_failed'
	| 'nps_dropped'
	| 'contact_form_unanswered'
	| 'seo_keywords_lost'
	| 'accessibility_issue'
	| 'campaign_landing_expires'
	| 'new_subscribers'
	// Sistema
	| 'worker_error_rate_high'
	| 'firecrawl_credits_low'
	| 'last_backup_old'
	| 'deploy_failed'
	| 'cron_job_failed'
	| 'r2_storage_high'
	| 'token_expiring'
	| 'db_size_growth'
	| 'backup_completed'
	| 'scrap_completed'
	| 'new_session';

export interface InboxEvent {
	id: number;
	type: EventType;
	severity: EventSeverity;
	title: string;
	description?: string;
	action_label?: string;
	action_target?: string; // route relativa: '/admin-web/vault/queue'
	module: ModuleSlug;
	metadata?: Record<string, unknown>;
	created_at: number;
	dismissed_at?: number;
	resolved_at?: number;
	expires_at?: number;
}

/**
 * Auto-dismiss rules según severity.
 * `null` = no auto-dismiss (persiste hasta resolverse manualmente).
 * Aplicado por el cron `dirty-detector`/`detect-inbox-events` al setear
 * expires_at = created_at + (días * 86400) en el insert.
 */
export const AUTO_DISMISS_DAYS: Record<EventSeverity, number | null> = {
	critical: null, // persiste hasta resolverse
	important: 7,
	info: 3
};
