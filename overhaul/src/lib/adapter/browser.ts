// Browser adapter — impl para `npm run dev` sin Tauri.
// Reads: fetch al vite dev plugin que sirve catalog.json + audit_decisions desde filesystem.
// Writes: throw NotAvailableInBrowser — el dev server no escribe (safe by default).

import type {
	Adapter,
	AdapterCapabilities,
	AuditDecision,
	AuditStatus,
	BatchCleanResult,
	CatalogRow,
	CommitResult,
	BackfillMetaResult,
	CreateImportInput,
	CreateWishlistItemInput,
	DeleteFamilyResult,
	DeleteSkuResult,
	EditModeloTypeResult,
	GitStatusInfo,
	ListFilter,
	ListWishlistInput,
	MoveModeloArgs,
	MoveModeloResult,
	PhotoAction,
	PromoteWishlistInput,
	PromoteWishlistResult,
	RegisterArrivalInput,
	RemovePhotosResult,
	SetFamilyVariantResult,
	UpdateImportInput,
	UpdateWishlistItemInput,
	WatermarkArgs,
	WatermarkResult,
	// R3
	MargenFilter,
	BatchMargenSummary,
	BatchMargenDetail,
	MargenPulso,
	// R4
	FreeUnit,
	AssignFreeUnitInput,
	FreeUnitFilter,
	// R5
	SupplierMetrics,
	SupplierDetail,
	UnpublishedRequest
} from './types';
import { NotAvailableInBrowser } from './types';
import type { WishlistItem } from '$lib/data/wishlist';
import type { Family } from '../data/types';
import type { Campaign, CampaignDetail, FunnelAwarenessReal, MetaSyncResult, BackfillAttributionResult, ImportOrdersResult, SalesListResult, CustomerSearchResult } from '../data/comercial';
import type { Import, ImportItem, ImportPulso, CloseImportResult } from '../data/importaciones';
import type { Expense, ExpenseInput, ProfitSnapshot, HomeSnapshot, RecentExpense } from '../data/finanzas';
import { transformFamily } from './transform';

// ─── Endpoints (definidos en vite/plugin-erp-dev.ts) ──────────────────
const EP_CATALOG = '/__erp/catalog';
const EP_DECISIONS = '/__erp/decisions';
const EP_PHOTO_ACTIONS = '/__erp/photo-actions';

// ─── Caches — catalog.json pesa 13MB, cachear en memoria ──────────────
let catalogCache: CatalogRow[] | null = null;
let decisionsCache: Map<string, AuditDecision> | null = null;
let decisionsByFamily: Map<string, AuditDecision[]> | null = null;

async function loadCatalog(): Promise<CatalogRow[]> {
	if (catalogCache) return catalogCache;
	const res = await fetch(EP_CATALOG);
	if (!res.ok) {
		throw new Error(
			`Could not load catalog from dev server (${res.status}). ` +
				`Is the Vite dev plugin enabled? Check vite.config.ts.`
		);
	}
	catalogCache = (await res.json()) as CatalogRow[];
	return catalogCache;
}

async function loadDecisions(): Promise<Map<string, AuditDecision>> {
	if (decisionsCache) return decisionsCache;
	const res = await fetch(EP_DECISIONS);
	if (!res.ok) {
		// Non-fatal: si no hay DB o no podemos leer, seguimos sin decisions.
		// Los modelos salen con derivedStatus basado solo en `published`.
		if (import.meta.env.DEV) {
			console.warn('[erp-adapter] Could not load audit_decisions from dev server:', res.status);
		}
		decisionsCache = new Map();
		return decisionsCache;
	}
	const rows = (await res.json()) as AuditDecision[];
	decisionsCache = new Map(rows.map((d) => [d.sku, d]));
	return decisionsCache;
}

function matchesFilter(fam: CatalogRow, filter?: ListFilter): boolean {
	// Filter zombies: families con status='deleted' (post delete_family).
	// El entry queda en catalog para audit trail pero NO debe aparecer en UI.
	if (fam.status === 'deleted') return false;
	if (!filter) return true;
	if (filter.published !== undefined && !!fam.published !== filter.published) return false;
	if (filter.category !== undefined && fam.category !== filter.category) return false;
	return true;
}

export const browserAdapter: Adapter = {
	capabilities: {
		reads: true,
		writes: false,
		watermark: false,
		git: false,
		platform: 'browser'
	} as AdapterCapabilities,

	// ─── Reads ──────────────────────────────────────────────────────────
	async listFamilies(filter?: ListFilter): Promise<Family[]> {
		const [catalog, decisions] = await Promise.all([loadCatalog(), loadDecisions()]);
		return catalog
			.filter((f) => matchesFilter(f, filter))
			.map((f) => transformFamily(f, decisions));
	},

	async getFamily(id: string): Promise<Family | null> {
		const [catalog, decisions] = await Promise.all([loadCatalog(), loadDecisions()]);
		const row = catalog.find((f) => f.family_id === id);
		return row ? transformFamily(row, decisions) : null;
	},

	async getDecision(sku: string): Promise<AuditDecision | null> {
		const decisions = await loadDecisions();
		return decisions.get(sku) ?? null;
	},

	async listDecisions(filter?: ListFilter): Promise<AuditDecision[]> {
		const decisions = await loadDecisions();
		const all = Array.from(decisions.values());
		if (!filter) return all;
		return all.filter((d) => {
			if (filter.tier !== undefined && d.tier !== filter.tier) return false;
			if (filter.status !== undefined && d.status !== filter.status) return false;
			return true;
		});
	},

	async getPhotoActions(familyId: string): Promise<PhotoAction[]> {
		if (!decisionsByFamily) decisionsByFamily = new Map();
		if (decisionsByFamily.has(familyId)) {
			// Cached empty — re-fetch below (photo_actions pueden cambiar between opens)
		}
		try {
			const res = await fetch(`${EP_PHOTO_ACTIONS}?family_id=${encodeURIComponent(familyId)}`);
			if (!res.ok) return [];
			return (await res.json()) as PhotoAction[];
		} catch {
			return [];
		}
	},

	// ─── Writes — all throw NotAvailableInBrowser ───────────────────────
	async setDecisionStatus(_sku: string, _status: AuditStatus): Promise<void> {
		throw new NotAvailableInBrowser('setDecisionStatus');
	},

	async setFinalVerified(_sku: string, _verified: boolean): Promise<void> {
		throw new NotAvailableInBrowser('setFinalVerified');
	},

	async updateGalleryOrder(
		_canonicalFid: string,
		_modeloIdx: number,
		_newOrder: string[]
	): Promise<void> {
		throw new NotAvailableInBrowser('updateGalleryOrder');
	},

	async removeModeloPhotos(
		_familyId: string,
		_modeloIdx: number,
		_photoIndices: number[],
		_alsoDeleteR2?: boolean
	): Promise<RemovePhotosResult> {
		throw new NotAvailableInBrowser('removeModeloPhotos');
	},

	async setFamilyPublished(_familyId: string, _published: boolean): Promise<void> {
		throw new NotAvailableInBrowser('setFamilyPublished');
	},

	async setFamilyFeatured(_familyId: string, _featured: boolean): Promise<void> {
		throw new NotAvailableInBrowser('setFamilyFeatured');
	},

	async setFamilyArchived(_familyId: string, _archived: boolean): Promise<void> {
		throw new NotAvailableInBrowser('setFamilyArchived');
	},

	async setPrimaryModeloIdx(_familyId: string, _modeloIdx: number): Promise<void> {
		throw new NotAvailableInBrowser('setPrimaryModeloIdx');
	},

	async setFamilyVariant(): Promise<SetFamilyVariantResult> {
		throw new NotAvailableInBrowser('setFamilyVariant');
	},

	async moveModelo(): Promise<MoveModeloResult> {
		throw new NotAvailableInBrowser('moveModelo');
	},

	async setModeloSoldOut(
		_familyId: string,
		_modeloIdx: number,
		_soldOut: boolean
	): Promise<void> {
		throw new NotAvailableInBrowser('setModeloSoldOut');
	},

	async setModeloField(): Promise<void> {
		throw new NotAvailableInBrowser('setModeloField');
	},

	async invokeWatermark(_args: WatermarkArgs): Promise<WatermarkResult> {
		throw new NotAvailableInBrowser('invokeWatermark');
	},

	async commitAndPush(_message: string): Promise<CommitResult> {
		throw new NotAvailableInBrowser('commitAndPush');
	},

	async gitStatus(): Promise<GitStatusInfo> {
		throw new NotAvailableInBrowser('gitStatus');
	},

	async deleteSku(_sku: string, _motivo: string): Promise<DeleteSkuResult> {
		throw new NotAvailableInBrowser('deleteSku');
	},

	async deleteFamily(_familyId: string, _motivo: string): Promise<DeleteFamilyResult> {
		throw new NotAvailableInBrowser('deleteFamily');
	},

	async backfillMeta(): Promise<BackfillMetaResult> {
		throw new NotAvailableInBrowser('backfillMeta');
	},

	async editModeloType(): Promise<EditModeloTypeResult> {
		throw new NotAvailableInBrowser('editModeloType');
	},

	async invalidateCache(): Promise<void> {
		// En browser mode, invalidamos el cache local directamente.
		_invalidateBrowserCaches();
	},

	async openMsiFolder(): Promise<void> {
		throw new NotAvailableInBrowser('openMsiFolder');
	},

	async batchCleanFamily(_familyId: string, _modeloIdx?: number): Promise<BatchCleanResult> {
		throw new NotAvailableInBrowser('batchCleanFamily');
	},

	// ─── Comercial R1 ──────────────────────────────────────────
	async listEvents() {
		return [];
	},

	async setEventStatus() {
		throw new NotAvailableInBrowser('setEventStatus');
	},

	async getOrderForModal() {
		return null;
	},

	async markOrderShipped() {
		throw new NotAvailableInBrowser('markOrderShipped');
	},

	async insertEvent() {
		throw new NotAvailableInBrowser('insertEvent');
	},

	async listSalesInRange() {
		return [];
	},

	async listLeadsInRange() {
		return [];
	},

	async listAdSpendInRange() {
		return [];
	},

	// ─── Comercial R2 ──────────────────────────────────────────
	async syncManychatData() {
		throw new NotAvailableInBrowser('syncManychatData');
	},
	async listLeads() { return []; },
	async listConversations() { return []; },
	async listCustomers() { return []; },
	async getMetaSync(source: string) {
		return { source, lastSyncAt: null, lastStatus: null, lastError: null };
	},
	async getConversationMessages() {
		throw new NotAvailableInBrowser('getConversationMessages');
	},

	// ─── Comercial R4 ──────────────────────────────────────────
	async getCustomerProfile() {
		return null;
	},
	async createCustomer() {
		throw new NotAvailableInBrowser('createCustomer');
	},
	async updateCustomerTraits() {
		throw new NotAvailableInBrowser('updateCustomerTraits');
	},
	async setCustomerBlocked() {
		throw new NotAvailableInBrowser('setCustomerBlocked');
	},
	async updateCustomerSource() {
		throw new NotAvailableInBrowser('updateCustomerSource');
	},
	async createManualOrder() {
		throw new NotAvailableInBrowser('createManualOrder');
	},

	// ─── Comercial R5 ──────────────────────────────────────────
	async syncMetaAds(): Promise<MetaSyncResult> {
		throw new NotAvailableInBrowser('syncMetaAds');
	},
	async listCampaigns(): Promise<Campaign[]> {
		return [];
	},
	async getCampaignDetail(): Promise<CampaignDetail | null> {
		return null;
	},
	async getFunnelAwarenessReal(): Promise<FunnelAwarenessReal | null> {
		return null;
	},
	async generateCoupon(): Promise<{ ok: boolean; code?: string; error?: string; pending?: boolean }> {
		return { ok: false, error: 'Not available in browser', pending: true };
	},

	// ─── Comercial R6 ──────────────────────────────────────────
	async backfillSalesAttribution(): Promise<BackfillAttributionResult> {
		throw new NotAvailableInBrowser('backfillSalesAttribution');
	},
	async getSaleAttribution(): Promise<null> {
		return null;
	},

	// ─── Comercial R7 ──────────────────────────────────────────
	async getConversationMeta(): Promise<null> {
		return null;
	},
	async attributeSale(): Promise<{ ok: boolean; error?: string }> {
		throw new NotAvailableInBrowser('attributeSale');
	},

	// ─── Comercial R9 ──────────────────────────────────────────
	async importOrdersFromWorker(): Promise<ImportOrdersResult> {
		throw new NotAvailableInBrowser('importOrdersFromWorker');
	},
	async listSales(): Promise<SalesListResult> {
		return { ok: true, sales: [], total: 0, totalRevenue: 0 };
	},

	// ─── Comercial R10 ──────────────────────────────────────────
	async searchCustomers(): Promise<CustomerSearchResult[]> {
		return [];
	},
	async updateSale() {
		throw new NotAvailableInBrowser('updateSale');
	},

	// ─── Comercial R11 ──────────────────────────────────────────
	async replaceSaleItems() {
		throw new NotAvailableInBrowser('replaceSaleItems');
	},

	// ─── Importaciones R1 ──────────────────────────────────────
	async listImports(): Promise<Import[]> {
		return [];
	},

	async getImport(_importId: string): Promise<Import> {
		throw new NotAvailableInBrowser('getImport');
	},

	async getImportItems(_importId: string): Promise<ImportItem[]> {
		return [];
	},

	async getImportPulso(): Promise<ImportPulso> {
		return {
			capital_amarrado_gtq: 0,
			closed_ytd_landed_gtq: 0,
			avg_landed_unit: null,
			lead_time_avg_days: null,
			wishlist_count: 0,
			free_units_unassigned: 0,
		};
	},

	async closeImportProportional(_import_id: string): Promise<CloseImportResult> {
		throw new NotAvailableInBrowser('closeImportProportional');
	},

	async createImport(_input: CreateImportInput): Promise<Import> {
		throw new NotAvailableInBrowser('createImport');
	},

	async registerArrival(_input: RegisterArrivalInput): Promise<Import> {
		throw new NotAvailableInBrowser('registerArrival');
	},

	async updateImport(_input: UpdateImportInput): Promise<Import> {
		throw new NotAvailableInBrowser('updateImport');
	},

	async cancelImport(_importId: string): Promise<Import> {
		throw new NotAvailableInBrowser('cancelImport');
	},

	async exportImportsCsv(): Promise<string> {
		throw new NotAvailableInBrowser('exportImportsCsv');
	},

	// ─── Importaciones R2 ──────────────────────────────────────────
	async listWishlist(_input: ListWishlistInput): Promise<WishlistItem[]> {
		throw new NotAvailableInBrowser('listWishlist');
	},

	async createWishlistItem(_input: CreateWishlistItemInput): Promise<WishlistItem> {
		throw new NotAvailableInBrowser('createWishlistItem');
	},

	async updateWishlistItem(_input: UpdateWishlistItemInput): Promise<WishlistItem> {
		throw new NotAvailableInBrowser('updateWishlistItem');
	},

	async cancelWishlistItem(_wishlistItemId: number): Promise<WishlistItem> {
		throw new NotAvailableInBrowser('cancelWishlistItem');
	},

	async promoteWishlistToBatch(_input: PromoteWishlistInput): Promise<PromoteWishlistResult> {
		throw new NotAvailableInBrowser('promoteWishlistToBatch');
	},

	async markInTransit(_importId: string, _trackingCode?: string): Promise<Import> {
		throw new NotAvailableInBrowser('markInTransit');
	},

	// ─── Importaciones R3 (Margen Real) ────────────────────────────────
	async getMargenReal(_filter: MargenFilter): Promise<BatchMargenSummary[]> {
		throw new NotAvailableInBrowser('getMargenReal');
	},

	async getBatchMargenBreakdown(_importId: string): Promise<BatchMargenDetail> {
		throw new NotAvailableInBrowser('getBatchMargenBreakdown');
	},

	async getMargenPulso(): Promise<MargenPulso> {
		throw new NotAvailableInBrowser('getMargenPulso');
	},

	// ─── Importaciones R4 (Free Units) ─────────────────────────────────
	async listFreeUnits(_filter?: FreeUnitFilter): Promise<FreeUnit[]> {
		throw new NotAvailableInBrowser('listFreeUnits');
	},

	async assignFreeUnit(_input: AssignFreeUnitInput): Promise<FreeUnit> {
		throw new NotAvailableInBrowser('assignFreeUnit');
	},

	async unassignFreeUnit(_freeUnitId: number): Promise<FreeUnit> {
		throw new NotAvailableInBrowser('unassignFreeUnit');
	},

	// ─── Importaciones R5 (Supplier Scorecard + Feedback Loop) ─────────
	async getSupplierMetrics(): Promise<SupplierMetrics[]> {
		throw new NotAvailableInBrowser('getSupplierMetrics');
	},

	async getSupplierDetail(_supplier: string): Promise<SupplierDetail> {
		throw new NotAvailableInBrowser('getSupplierDetail');
	},

	async getMostRequestedUnpublished(_limit?: number): Promise<UnpublishedRequest[]> {
		throw new NotAvailableInBrowser('getMostRequestedUnpublished');
	},

	// ─── Finanzas (FIN-R1) ─────────────────────────────────────────────
	async computeProfitSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
	): Promise<ProfitSnapshot> {
		return {
			period_start: periodStart,
			period_end: periodEnd,
			period_label: periodLabel,
			revenue_gtq: 0,
			cogs_gtq: 0,
			marketing_gtq: 0,
			opex_gtq: 0,
			profit_operativo: 0,
			prev_period_profit: undefined,
			trend_pct: undefined,
		};
	},

	async getHomeSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
	): Promise<HomeSnapshot> {
		const profit = await this.computeProfitSnapshot(periodStart, periodEnd, periodLabel);
		return {
			profit,
			cash_business_gtq: null,
			cash_synced_at: null,
			cash_stale_days: null,
			capital_amarrado_gtq: 0,
			shareholder_loan_balance: 0,
			shareholder_loan_trend_30d: 0,
		};
	},

	async createExpense(_input: ExpenseInput): Promise<number> {
		throw new NotAvailableInBrowser('createExpense');
	},

	async listExpenses(): Promise<Expense[]> {
		return [];
	},

	async deleteExpense(_expenseId: number): Promise<void> {
		throw new NotAvailableInBrowser('deleteExpense');
	},

	async updateExpense(_expenseId: number, _input: ExpenseInput): Promise<void> {
		throw new NotAvailableInBrowser('updateExpense');
	},

	async recentExpenses(): Promise<RecentExpense[]> {
		return [];
	},

	async setCashBalance(_b: number, _s: string, _n?: string): Promise<number> {
		throw new NotAvailableInBrowser('setCashBalance');
	},
};

// Test helper (también útil si queremos invalidar cache en dev)
export function _invalidateBrowserCaches() {
	catalogCache = null;
	decisionsCache = null;
	decisionsByFamily = null;
}

// =============================================================================
// Admin Web R7 (T1.4) — Browser stubs
// =============================================================================
// Patrón consistente con browserAdapter pre-existente:
//   - reads (list_*, get_*): retornan arrays/objetos vacíos para que la UI
//     renderice en `npm run dev` sin crashes (skeleton states funcionando)
//   - writes (create/update/delete/dismiss/etc): throw NotAvailableInBrowser
//
// El plan T1.4 dice "los NotAvailableInBrowser correspondientes" — interpreto
// "correspondientes" = donde aplique. En writes corresponde; en reads
// preferimos degradación graceful para preservar el dev loop.

import type { AdminWebTauriCommands } from './types';

export const adminWebBrowser: AdminWebTauriCommands = {
	// === HOME ===
	get_admin_web_kpis: async () => ({
		publicados_total: 0,
		stock_live: 0,
		queue_count: 0,
		scheduled_30d: 0,
		activity_month: 0,
		supplier_gaps: 0,
		hours_since_last_scrap: 0,
		dirty_count: 0,
		sparklines: {}
	}),
	get_module_stats: async () => ({}),

	// === INBOX EVENTS ===
	list_inbox_events: async () => [],
	dismiss_event: async () => {
		throw new NotAvailableInBrowser('dismiss_event');
	},
	resolve_event: async () => {
		throw new NotAvailableInBrowser('resolve_event');
	},
	detect_events_now: async () => {
		throw new NotAvailableInBrowser('detect_events_now');
	},

	// === VAULT — TAGS ===
	list_tag_types: async () => [],
	list_tags: async () => [],
	create_tag: async () => {
		throw new NotAvailableInBrowser('create_tag');
	},
	update_tag: async () => {
		throw new NotAvailableInBrowser('update_tag');
	},
	soft_delete_tag: async () => {
		throw new NotAvailableInBrowser('soft_delete_tag');
	},
	list_jersey_tags: async () => [],
	list_jerseys_by_tag: async () => [],
	validate_tag_assignment: async () => ({ valid: true }),
	assign_tag: async () => {
		throw new NotAvailableInBrowser('assign_tag');
	},
	remove_tag: async () => {
		throw new NotAvailableInBrowser('remove_tag');
	},

	// === VAULT — PUBLICADOS ===
	list_published: async () => [],
	promote_to_stock: async () => {
		throw new NotAvailableInBrowser('promote_to_stock');
	},
	promote_to_mystery: async () => {
		throw new NotAvailableInBrowser('promote_to_mystery');
	},
	toggle_dirty_flag: async () => {
		throw new NotAvailableInBrowser('toggle_dirty_flag');
	},
	archive_jersey: async () => {
		throw new NotAvailableInBrowser('archive_jersey');
	},
	revive_archived: async () => {
		throw new NotAvailableInBrowser('revive_archived');
	},

	// === VAULT — UNIVERSO ===
	list_universo: async () => ({ rows: [], total: 0, filters_counts: {} }),
	bulk_action: async () => {
		throw new NotAvailableInBrowser('bulk_action');
	},

	// === SAVED VIEWS ===
	list_saved_views: async () => [],
	save_view: async () => {
		throw new NotAvailableInBrowser('save_view');
	},
	delete_view: async () => {
		throw new NotAvailableInBrowser('delete_view');
	},

	// === STOCK ===
	list_stock_overrides: async () => [],
	create_stock_override: async () => {
		throw new NotAvailableInBrowser('create_stock_override');
	},
	update_stock_override: async () => {
		throw new NotAvailableInBrowser('update_stock_override');
	},
	delete_stock_override: async () => {
		throw new NotAvailableInBrowser('delete_stock_override');
	},
	pause_stock_override: async () => {
		throw new NotAvailableInBrowser('pause_stock_override');
	},
	list_stock_calendar: async () => [],

	// === MYSTERY ===
	list_mystery_overrides: async () => [],
	create_mystery_override: async () => {
		throw new NotAvailableInBrowser('create_mystery_override');
	},
	update_mystery_override: async () => {
		throw new NotAvailableInBrowser('update_mystery_override');
	},
	delete_mystery_override: async () => {
		throw new NotAvailableInBrowser('delete_mystery_override');
	},
	list_mystery_calendar: async () => [],
	get_mystery_rules: async () => ({}),
	update_mystery_rules: async () => {
		throw new NotAvailableInBrowser('update_mystery_rules');
	},

	// === SITE — PAGES ===
	list_pages: async () => [],
	get_page: async () => {
		throw new NotAvailableInBrowser('get_page');
	},
	create_page: async () => {
		throw new NotAvailableInBrowser('create_page');
	},
	update_page: async () => {
		throw new NotAvailableInBrowser('update_page');
	},
	delete_page: async () => {
		throw new NotAvailableInBrowser('delete_page');
	},
	publish_page: async () => {
		throw new NotAvailableInBrowser('publish_page');
	},

	// === SITE — COMPONENTS ===
	list_components: async () => [],
	update_component: async () => {
		throw new NotAvailableInBrowser('update_component');
	},
	toggle_component: async () => {
		throw new NotAvailableInBrowser('toggle_component');
	},

	// === SITE — BRANDING ===
	list_branding: async () => [],
	set_branding: async () => {
		throw new NotAvailableInBrowser('set_branding');
	},
	apply_branding_changes: async () => {
		throw new NotAvailableInBrowser('apply_branding_changes');
	},

	// === SITE — COMMUNICATION ===
	list_templates: async () => [],
	create_template: async () => {
		throw new NotAvailableInBrowser('create_template');
	},
	update_template: async () => {
		throw new NotAvailableInBrowser('update_template');
	},
	list_subscribers: async () => [],
	list_workflows: async () => [],
	toggle_workflow: async () => {
		throw new NotAvailableInBrowser('toggle_workflow');
	},

	// === SITE — COMMUNITY ===
	list_reviews: async () => [],
	moderate_review: async () => {
		throw new NotAvailableInBrowser('moderate_review');
	},
	list_surveys: async () => [],
	list_survey_responses: async () => [],

	// === SISTEMA ===
	get_health_snapshot: async () => ({
		worker_uptime_pct: 0,
		worker_latency_p50_ms: 0,
		worker_latency_p95_ms: 0,
		error_rate_pct: 0,
		cdn_cache_hit_pct: 0,
		r2_storage_gb: 0,
		kv_ops_per_min: 0,
		firecrawl_credits_remaining: 0,
		firecrawl_credits_total: 0,
		last_scrap_at: 0,
		db_size_mb: 0,
		active_sessions: 0,
		active_alerts: []
	}),
	get_health_history: async () => [],
	list_scrap_history: async () => [],
	trigger_scrap: async () => {
		throw new NotAvailableInBrowser('trigger_scrap');
	},
	list_deploy_history: async () => [],
	trigger_deploy: async () => {
		throw new NotAvailableInBrowser('trigger_deploy');
	},
	rollback_deploy: async () => {
		throw new NotAvailableInBrowser('rollback_deploy');
	},
	list_jobs: async () => [],
	toggle_job: async () => {
		throw new NotAvailableInBrowser('toggle_job');
	},
	run_job_now: async () => {
		throw new NotAvailableInBrowser('run_job_now');
	},
	list_backups: async () => [],
	create_backup_now: async () => {
		throw new NotAvailableInBrowser('create_backup_now');
	},
	restore_from_backup: async () => {
		throw new NotAvailableInBrowser('restore_from_backup');
	},
	stream_logs: async () => '',
	list_audit_log: async () => [],
	export_audit_log_csv: async () => {
		throw new NotAvailableInBrowser('export_audit_log_csv');
	},
	get_admin_config: async () => ({}),
	set_admin_config: async () => {
		throw new NotAvailableInBrowser('set_admin_config');
	},
	list_api_connections: async () => [],
	test_api_connection: async () => {
		throw new NotAvailableInBrowser('test_api_connection');
	},
	rotate_secret: async () => {
		throw new NotAvailableInBrowser('rotate_secret');
	}
};
