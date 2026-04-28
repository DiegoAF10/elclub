/**
 * Admin Web — TypeScript Types Canonical
 * =============================================================================
 * Standalone, listos para mover a:
 *   overhaul/src/lib/data/admin-web.ts
 *   overhaul/src/lib/data/jersey-states.ts
 *   overhaul/src/lib/data/tags.ts
 *   overhaul/src/lib/data/overrides.ts
 *   overhaul/src/lib/data/inbox-events.ts
 *   overhaul/src/lib/adapter/types.ts (extender el existente)
 *
 * Sincronizados con schema-migration.sql.
 * =============================================================================
 */

// =============================================================================
// JERSEY STATES
// =============================================================================

export type JerseyState =
  | 'DRAFT'      // Pre-pipeline. Catalog OK pero sin audit_decisions o con scrap_fail.
  | 'QUEUE'      // audit_decisions.status='pending'. Tab Queue.
  | 'PUBLISHED'  // catalog.published=true. Live en vault.elclub.club.
  | 'REJECTED'   // audit_decisions.status='deleted'. Soft delete.
  | 'ARCHIVED';  // Fue PUBLISHED, ya no. Puede revivir.

/** Transiciones legales entre estados */
export const VALID_TRANSITIONS: Record<JerseyState, JerseyState[]> = {
  DRAFT: ['QUEUE', 'REJECTED'],
  QUEUE: ['PUBLISHED', 'REJECTED'],
  PUBLISHED: ['ARCHIVED'],
  REJECTED: ['QUEUE'],            // raro pero legal
  ARCHIVED: ['PUBLISHED'],         // revivir
};

export function canTransition(from: JerseyState, to: JerseyState): boolean {
  return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

/** Flags ortogonales sobre el jersey */
export interface JerseyFlags {
  dirty: boolean;              // PUBLISHED necesita revisión (foto rota, CDN stale)
  dirty_reason?: string;       // ej. "foto rota detectada", "CDN cache stale"
  scrap_fail: boolean;         // DRAFT con datos incompletos
  low_coverage: boolean;       // gallery.length < 3
  supplier_gap: boolean;       // proveedor no lo maneja (L12 del playbook)
  qa_priority: 0 | 1;          // whitelist priorización
  in_vault: boolean;           // aparece en vault.elclub.club (default true para PUBLISHED)
}

export interface Jersey {
  family_id: string;
  sku: string;
  team: string;
  season: string;
  variant: 'L' | 'V' | 'T' | 'E' | 'G';   // Local, Visita, Third, Special, Goalkeeper
  state: JerseyState;
  flags: JerseyFlags;
  hero_thumbnail: string | null;
  gallery: string[];
  modelos: JerseyModelo[];
  meta_country?: string;
  meta_league?: string;
  meta_confederation?: string;
  archived_at?: number;        // unix timestamp si ARCHIVED
  created_at: number;
  last_updated: number;
}

export interface JerseyModelo {
  type: 'fan_adult' | 'player_adult' | 'retro_adult' | 'woman' | 'kid' | 'baby' | 'goalkeeper';
  sleeve: 'short' | 'long';
  album_id: string;
  store: 'minkang' | 'wavesoccer';
  yupoo_title: string;
  gallery: string[];
  hero_thumbnail: string;
  sizes: string;
  price: number;
  sku: string;
}

// =============================================================================
// TAGS SYSTEM
// =============================================================================

export type TagCardinality = 'one' | 'many';

export type TagTypeSlug =
  | 'competicion'
  | 'geografia_region'
  | 'pais'
  | 'liga'
  | 'era'
  | 'tipo_equipo'
  | 'variant_edicion'
  | 'comercial'
  | 'paleta_principal'
  | 'narrativa_cultural'
  | 'marca_tecnica';

export interface ConditionalRule {
  // Una de las tres puede aplicar:
  applies_when?: { tag_type: TagTypeSlug; tag_slug: string };
  forbidden_when?: { tag_type: TagTypeSlug; tag_slug: string };
  required_when?: { tag_type: TagTypeSlug; tag_slug: string };
}

export interface TagType {
  id: number;
  slug: TagTypeSlug;
  display_name: string;
  icon: string;
  cardinality: TagCardinality;
  display_order: number;
  conditional_rule?: ConditionalRule;
  description?: string;
  created_at: number;
  updated_at: number;
}

export interface Tag {
  id: number;
  type_id: number;
  type_slug: TagTypeSlug;       // denormalized para queries rápidas
  slug: string;
  display_name: string;
  icon?: string;
  color?: string;
  is_auto_derived: boolean;
  derivation_rule?: AutoDerivationRule;
  is_deleted: boolean;
  display_order: number;
  count?: number;               // cuántas jerseys tienen este tag (computed)
  created_at: number;
  updated_at: number;
}

export interface AutoDerivationRule {
  type: 'top_n_by_metric' | 'recent_n_days' | 'matches_filter' | 'custom_sql';
  config: Record<string, unknown>;
  refresh_interval: 'hourly' | 'daily' | 'weekly';
}

export interface JerseyTag {
  family_id: string;
  tag_id: number;
  assigned_at: number;
  assigned_by: 'manual' | string;  // 'auto:rule_id' | 'bulk:user'
}

/**
 * Resultado de validación al asignar un tag.
 * Si valid=false, el reason indica el motivo y conflicting_tags
 * (si aplica) lista los tags que están en conflicto.
 */
export interface TagAssignmentValidation {
  valid: boolean;
  reason?: 'cardinality_violation' | 'forbidden_by_conditional' | 'tag_deleted' | 'jersey_not_found';
  conflicting_tags?: Tag[];
  message?: string;
}

// =============================================================================
// OVERRIDES (Stock + Mystery)
// =============================================================================

export type OverrideStatus = 'draft' | 'scheduled' | 'live' | 'ended' | 'paused';

export interface StockOverride {
  id: number;
  family_id: string;
  publish_at: number | null;
  unpublish_at: number | null;
  price_override: number | null;     // en centavos GTQ (47500 = Q475)
  badge: string | null;
  copy_override: string | null;
  priority: number;                  // 1-10
  status: OverrideStatus;
  computed_status: OverrideStatus;   // calculado por SQL view en runtime
  created_at: number;
  updated_at: number;
  created_by: string;
}

export interface MysteryOverride {
  id: number;
  family_id: string;
  publish_at: number | null;
  unpublish_at: number | null;
  pool_weight: number;               // multiplicador en algoritmo (default 1.0)
  status: OverrideStatus;
  computed_status: OverrideStatus;
  created_at: number;
  updated_at: number;
  created_by: string;
}

// =============================================================================
// INBOX EVENTS
// =============================================================================

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

export type ModuleSlug = 'vault' | 'stock' | 'mystery' | 'site' | 'sistema';

export interface InboxEvent {
  id: number;
  type: EventType;
  severity: EventSeverity;
  title: string;
  description?: string;
  action_label?: string;
  action_target?: string;          // route relativa: '/admin-web/vault/queue'
  module: ModuleSlug;
  metadata?: Record<string, unknown>;
  created_at: number;
  dismissed_at?: number;
  resolved_at?: number;
  expires_at?: number;
}

/** Auto-dismiss rules según severity */
export const AUTO_DISMISS_DAYS: Record<EventSeverity, number | null> = {
  critical: null,                  // persiste hasta resolverse
  important: 7,
  info: 3,
};

// =============================================================================
// HOME KPIS
// =============================================================================

export interface KpiSnapshot {
  date: string;                    // 'YYYY-MM-DD'
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
  id: string;                      // uuid
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
  key: string;                     // 'palette.primary', 'logo.dark', 'fonts.heading'
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
  rating: number;                  // 1-5
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

export type AuditAction = 'create' | 'update' | 'delete' | 'archive' | 'revive' | 'publish' | 'unpublish' | 'bulk_action' | 'login' | 'logout';
export type AuditSeverity = 'info' | 'warning' | 'critical';

export interface AuditLogEntry {
  id: number;
  timestamp: number;
  user: string;
  module: ModuleSlug;
  action: AuditAction;
  entity_type?: string;            // 'jersey', 'tag', 'override', 'page'
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
  search_terms?: string[];        // términos extra para fuzzy match
}

// =============================================================================
// FILTERS & PAGINATION (común a vistas densas)
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
  tags?: number[];                // IDs de tags
  coverage_min?: number;
  coverage_max?: number;
  last_action?: 'today' | 'week' | 'month' | 'older';
  search?: string;                // texto libre (SKU, team, etc.)
}

export interface SortConfig {
  column: string;
  direction: 'asc' | 'desc';
}

export interface PaginationConfig {
  page: number;                   // 1-indexed
  per_page: number;
}

export interface UniversoQueryResult {
  rows: Jersey[];
  total: number;
  filters_counts: Record<string, number>;
}

// =============================================================================
// TAURI COMMANDS — contracts (signatures de IPC)
// =============================================================================

/**
 * Conjunto de Tauri commands necesarios para Admin Web.
 * Implementación va en overhaul/src-tauri/src/lib.rs.
 * Cliente TypeScript va en overhaul/src/lib/adapter/tauri.ts.
 */

export interface AdminWebTauriCommands {
  // === HOME ===
  get_admin_web_kpis: () => Promise<HomeKpis>;
  get_module_stats: (args: { module: ModuleSlug }) => Promise<Record<string, unknown>>;

  // === INBOX EVENTS ===
  list_inbox_events: (args: { include_dismissed?: boolean; severity_filter?: EventSeverity[] }) => Promise<InboxEvent[]>;
  dismiss_event: (args: { id: number }) => Promise<void>;
  resolve_event: (args: { id: number }) => Promise<void>;
  detect_events_now: () => Promise<{ events_created: number }>;

  // === VAULT — TAGS ===
  list_tag_types: () => Promise<TagType[]>;
  list_tags: (args?: { type_id?: number; include_deleted?: boolean }) => Promise<Tag[]>;
  create_tag: (args: { type_id: number; slug: string; display_name: string; icon?: string; color?: string }) => Promise<Tag>;
  update_tag: (args: { id: number; updates: Partial<Tag> }) => Promise<Tag>;
  soft_delete_tag: (args: { id: number }) => Promise<void>;

  list_jersey_tags: (args: { family_id: string }) => Promise<Tag[]>;
  list_jerseys_by_tag: (args: { tag_id: number; pagination?: PaginationConfig }) => Promise<Jersey[]>;
  validate_tag_assignment: (args: { family_id: string; tag_id: number }) => Promise<TagAssignmentValidation>;
  assign_tag: (args: { family_id: string; tag_id: number; force_replace?: boolean }) => Promise<void>;
  remove_tag: (args: { family_id: string; tag_id: number }) => Promise<void>;

  // === VAULT — PUBLICADOS ===
  list_published: (args: { filter?: 'all' | 'attention' | 'recent' | 'scheduled' | 'no_tags' | 'old'; pagination?: PaginationConfig }) => Promise<Jersey[]>;
  promote_to_stock: (args: { family_id: string; override: Partial<StockOverride> }) => Promise<StockOverride>;
  promote_to_mystery: (args: { family_id: string; override: Partial<MysteryOverride> }) => Promise<MysteryOverride>;
  toggle_dirty_flag: (args: { family_id: string; dirty: boolean; reason?: string }) => Promise<void>;
  archive_jersey: (args: { family_id: string }) => Promise<void>;
  revive_archived: (args: { family_id: string; scheduled_at?: number }) => Promise<void>;

  // === VAULT — UNIVERSO ===
  list_universo: (args: { filters: UniversoFilters; sort?: SortConfig; pagination: PaginationConfig }) => Promise<UniversoQueryResult>;
  bulk_action: (args: { family_ids: string[]; action: 'tag' | 'archive' | 're_fetch' | 'delete'; payload?: Record<string, unknown> }) => Promise<{ affected: number; errors: string[] }>;

  // === SAVED VIEWS ===
  list_saved_views: (args: { module: ModuleViewKey }) => Promise<SavedView[]>;
  save_view: (args: Omit<SavedView, 'id' | 'created_at'>) => Promise<SavedView>;
  delete_view: (args: { id: number }) => Promise<void>;

  // === STOCK ===
  list_stock_overrides: (args: { status_filter?: OverrideStatus[]; pagination?: PaginationConfig }) => Promise<StockOverride[]>;
  create_stock_override: (args: { override: Omit<StockOverride, 'id' | 'computed_status' | 'created_at' | 'updated_at'> }) => Promise<StockOverride>;
  update_stock_override: (args: { id: number; updates: Partial<StockOverride> }) => Promise<StockOverride>;
  delete_stock_override: (args: { id: number }) => Promise<void>;
  pause_stock_override: (args: { id: number }) => Promise<void>;
  list_stock_calendar: (args: { from: number; to: number }) => Promise<StockOverride[]>;

  // === MYSTERY ===
  list_mystery_overrides: (args: { status_filter?: OverrideStatus[]; pagination?: PaginationConfig }) => Promise<MysteryOverride[]>;
  create_mystery_override: (args: { override: Omit<MysteryOverride, 'id' | 'computed_status' | 'created_at' | 'updated_at'> }) => Promise<MysteryOverride>;
  update_mystery_override: (args: { id: number; updates: Partial<MysteryOverride> }) => Promise<MysteryOverride>;
  delete_mystery_override: (args: { id: number }) => Promise<void>;
  list_mystery_calendar: (args: { from: number; to: number }) => Promise<MysteryOverride[]>;
  get_mystery_rules: () => Promise<Record<string, unknown>>;
  update_mystery_rules: (args: { rules: Record<string, unknown> }) => Promise<void>;

  // === SITE — PAGES ===
  list_pages: (args?: { category?: PageCategory; status?: PageStatus }) => Promise<SitePage[]>;
  get_page: (args: { id: number }) => Promise<SitePage>;
  create_page: (args: { page: Omit<SitePage, 'id' | 'created_at' | 'updated_at'> }) => Promise<SitePage>;
  update_page: (args: { id: number; updates: Partial<SitePage> }) => Promise<SitePage>;
  delete_page: (args: { id: number }) => Promise<void>;
  publish_page: (args: { id: number; scheduled_at?: number }) => Promise<void>;

  // === SITE — COMPONENTS ===
  list_components: (args?: { type_filter?: ComponentType[] }) => Promise<SiteComponent[]>;
  update_component: (args: { id: number; updates: Partial<SiteComponent> }) => Promise<SiteComponent>;
  toggle_component: (args: { id: number; enabled: boolean }) => Promise<void>;

  // === SITE — BRANDING ===
  list_branding: () => Promise<BrandingValue[]>;
  set_branding: (args: { key: string; value: string; value_type: BrandingValueType }) => Promise<void>;
  apply_branding_changes: () => Promise<{ deploy_triggered: boolean }>;

  // === SITE — COMMUNICATION ===
  list_templates: (args?: { channel_filter?: CommunicationChannel[] }) => Promise<CommunicationTemplate[]>;
  create_template: (args: { template: Omit<CommunicationTemplate, 'id' | 'created_at' | 'updated_at'> }) => Promise<CommunicationTemplate>;
  update_template: (args: { id: number; updates: Partial<CommunicationTemplate> }) => Promise<CommunicationTemplate>;
  list_subscribers: (args?: { list_id?: number; pagination?: PaginationConfig }) => Promise<Subscriber[]>;
  list_workflows: () => Promise<Workflow[]>;
  toggle_workflow: (args: { id: number; enabled: boolean }) => Promise<void>;

  // === SITE — COMMUNITY ===
  list_reviews: (args?: { status_filter?: ReviewStatus[]; pagination?: PaginationConfig }) => Promise<Review[]>;
  moderate_review: (args: { id: number; status: ReviewStatus; note?: string }) => Promise<void>;
  list_surveys: () => Promise<Survey[]>;
  list_survey_responses: (args: { survey_id: number; pagination?: PaginationConfig }) => Promise<{ id: number; answers: unknown; submitted_at: number }[]>;

  // === SISTEMA ===
  get_health_snapshot: () => Promise<HealthSnapshot>;
  get_health_history: (args: { metric: string; from: number; to: number }) => Promise<HealthSnapshot[]>;
  list_scrap_history: (args?: { pagination?: PaginationConfig }) => Promise<ScrapHistoryEntry[]>;
  trigger_scrap: (args: { category_url: string; flags?: Record<string, unknown> }) => Promise<{ scrap_id: number }>;
  list_deploy_history: (args?: { target?: DeployTarget; pagination?: PaginationConfig }) => Promise<DeployHistoryEntry[]>;
  trigger_deploy: (args: { target: DeployTarget; commit_sha?: string }) => Promise<{ deploy_id: number }>;
  rollback_deploy: (args: { deploy_id: number }) => Promise<void>;
  list_jobs: () => Promise<ScheduledJob[]>;
  toggle_job: (args: { id: number; enabled: boolean }) => Promise<void>;
  run_job_now: (args: { id: number }) => Promise<void>;
  list_backups: (args?: { type?: BackupType; pagination?: PaginationConfig }) => Promise<BackupEntry[]>;
  create_backup_now: (args: { type: BackupType }) => Promise<BackupEntry>;
  restore_from_backup: (args: { backup_id: number; confirm_token: string }) => Promise<void>;
  stream_logs: (args: { tail_lines?: number }) => Promise<string>;     // returns initial buffer; events via Tauri Event
  list_audit_log: (args: { filters?: { module?: ModuleSlug; user?: string; from?: number; to?: number; severity?: AuditSeverity }; pagination?: PaginationConfig }) => Promise<AuditLogEntry[]>;
  export_audit_log_csv: (args: { filters?: Record<string, unknown> }) => Promise<{ file_path: string }>;
  get_admin_config: () => Promise<Record<string, { value: string; value_type: string }>>;
  set_admin_config: (args: { key: string; value: string; value_type: string }) => Promise<void>;
  list_api_connections: () => Promise<{ name: string; status: 'connected' | 'failing' | 'pending'; last_test_at?: number; usage?: Record<string, unknown> }[]>;
  test_api_connection: (args: { name: string }) => Promise<{ success: boolean; message?: string }>;
  rotate_secret: (args: { name: string }) => Promise<{ success: boolean }>;
}
