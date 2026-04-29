// Adapter types — contrato agnóstico de plataforma.
// Implementaciones concretas: browser.ts (dev sin Tauri) + tauri.ts (app nativa).

import type { Family, Status } from '../data/types';
import type { Import, ImportItem, ImportPulso, CloseImportResult } from '../data/importaciones';
import type { Expense, ExpenseInput, ProfitSnapshot, HomeSnapshot, RecentExpense } from '../data/finanzas';
import type {
	ComercialEvent,
	DetectedEvent,
	EventStatus,
	OrderForModal,
	PeriodRange,
	Lead,
	ConversationMeta,
	ConversationMessage,
	Customer,
	MetaSyncStatus,
	CustomerProfile,
	CreateCustomerArgs,
	CreateOrderArgs,
	CreateOrderItem,
	Campaign,
	CampaignDetail,
	FunnelAwarenessReal,
	MetaSyncResult,
	SaleAttribution,
	BackfillAttributionResult,
	ImportOrdersResult,
	SalesListResult,
	CustomerSearchResult,
	UpdateSaleArgs
} from '../data/comercial';

export type AuditStatus =
	| 'pending'
	| 'verified'
	| 'flagged'
	| 'skipped'
	| 'needs_rework'
	| 'deleted';

export interface AuditDecision {
	sku: string; // PK — audit_decisions.family_id contiene el SKU post Ops s13
	tier: string | null; // T1-T5 | null
	status: AuditStatus;
	final_verified: boolean; // el sagrado — true = publicada, no tocar sin override
	qa_priority: boolean;
	notes: string | null;
	decided_at: string | null;
	reviewed_at: string | null;
	final_verified_at: string | null;
}

export interface PhotoAction {
	family_id: string;
	original_url: string;
	original_index: number;
	action: 'keep' | 'delete' | 'flag_watermark' | 'flag_regen' | 'hero';
	new_index: number | null;
	is_new_hero: boolean;
	processed_url: string | null;
	decided_at: string;
}

export interface ListFilter {
	published?: boolean;
	tier?: string;
	status?: AuditStatus;
	category?: string;
}

export type WatermarkMode =
	| 'auto' // LaMa + OCR/template detection (default)
	| 'force' // LaMa + mask hardcoded centro
	| 'sd' // Stable Diffusion inpaint (preserva logos mejor)
	| 'gemini'; // Gemini 2.5 Flash Image

export interface WatermarkArgs {
	family_id: string;
	modelo_idx: number;
	photo_idx: number;
	mode: WatermarkMode;
}

export interface WatermarkResult {
	ok: boolean;
	new_url?: string;
	error?: string;
	stderr?: string;
}

export interface CommitResult {
	ok: boolean;
	commit_sha?: string;
	pushed: boolean;
	nothing_to_commit: boolean;
	error?: string;
	stdout?: string;
}

export interface GitStatusInfo {
	clean: boolean;
	catalog_changed: boolean;
	changed_lines: string;
	ahead: number;
	behind: number;
}

export interface DeleteSkuResult {
	ok: boolean;
	family_deleted: boolean;
	was_published: boolean;
	committed: boolean;
	error?: string;
}

export interface DeleteFamilyResult {
	ok: boolean;
	familyId?: string;
	deletedSkus: string[];
	deleteLogRows: number;
	wasPublished: boolean;
	committed: boolean;
	pushError?: string;
	error?: string;
}

export interface BackfillMetaResult {
	ok: boolean;
	stats?: Record<string, number>;
	error?: string;
}

export interface BatchCleanResult {
	ok: boolean;
	total: number;
	cleaned: number;
	failed: number;
	skipped: number;
	errors: string[];
}

export interface RemovePhotosResult {
	removed_from_catalog: number;
	deleted_from_r2: number;
	r2_failed: number;
	r2_errors: string[];
}

export interface NewFamilyData {
	team: string;
	season: string;
	variant: string;
	variantLabel?: string;
	category?: string;
	metaCountry?: string;
	metaLeague?: string;
	metaConfederation?: string;
}

export interface MoveModeloArgs {
	sourceFid: string;
	sourceModeloIdx?: number;
	targetFid?: string;
	newFamily?: NewFamilyData;
	absorbAll?: boolean;
}

export interface MoveModeloResult {
	ok: boolean;
	source_fid?: string;
	target_fid?: string;
	source_empty_now: boolean;
	moved: number;
	old_skus: string[];
	new_skus: string[];
	migrated?: { audit_decisions: number; audit_photo_actions: number };
	error?: string;
}

export interface SetFamilyVariantResult {
	ok: boolean;
	old_variant?: string;
	new_variant?: string;
	old_skus: string[];
	new_skus: string[];
	migrated?: { audit_decisions: number; audit_photo_actions: number };
	error?: string;
}

export interface EditModeloTypeResult {
	ok: boolean;
	old_sku?: string;
	new_sku?: string;
	old_type?: string;
	new_type?: string;
	migrated?: { audit_decisions: number; audit_photo_actions: number };
	error?: string;
}

// ─── Error class for sagrado violations ──────────────────────────────
export class SagradoViolation extends Error {
	constructor(
		public sku: string,
		public reason: string
	) {
		super(`Sagrado violation on ${sku}: ${reason}`);
		this.name = 'SagradoViolation';
	}
}

// ─── IMP-R1.5 input interfaces ──────────────────────────────────────
// camelCase field names match Rust serde rename — transparent translation

export interface CreateImportInput {
	importId: string;       // regex IMP-YYYY-MM-DD enforced server-side
	paidAt: string;         // YYYY-MM-DD
	supplier: string;       // default 'Bond Soccer Jersey' if empty
	brutoUsd: number;       // > 0
	fx: number;             // > 0 · default 7.73 cliente
	nUnits: number;         // > 0
	notes?: string;
	trackingCode?: string;
	carrier?: string;       // default 'DHL' server-side
}

export interface RegisterArrivalInput {
	importId: string;
	arrivedAt: string;      // YYYY-MM-DD
	shippingGtq: number;    // >= 0
	trackingCode?: string;
}

export interface UpdateImportInput {
	importId: string;
	notes?: string;
	trackingCode?: string;
	carrier?: string;
}

// ─── R2: Wishlist ───
import type { WishlistItem } from '$lib/data/wishlist';

export interface ListWishlistInput {
	status?: 'active' | 'promoted' | 'cancelled';  // omitted = all
}

export interface CreateWishlistItemInput {
	familyId:      string;          // D7=B: must exist in catalog.json
	jerseyId?:     string;
	size?:         string;
	playerName?:   string;
	playerNumber?: number;
	patch?:        string;          // 'WC' | 'Champions' | undefined
	version?:      'fan' | 'fan-w' | 'player';
	customerId?:   string;
	expectedUsd?:  number;          // >= 0
	notes?:        string;
}

export interface UpdateWishlistItemInput {
	wishlistItemId: number;
	size?:          string;
	playerName?:    string;
	playerNumber?:  number;
	patch?:         string;
	version?:       'fan' | 'fan-w' | 'player';
	customerId?:    string;
	expectedUsd?:   number;
	notes?:         string;
	// Note: familyId NOT editable post-create
}

export interface PromoteWishlistInput {
	wishlistItemIds: number[];      // length >= 1
	importId:        string;        // regex IMP-YYYY-MM-DD enforced server-side
	status:          'paid' | 'draft';  // Diego decision 2026-04-28: default UI = 'paid'
	paidAt?:         string;        // YYYY-MM-DD · REQUIRED iff status='paid'
	supplier?:       string;        // default 'Bond Soccer Jersey' if empty
	brutoUsd:        number;        // > 0 · sum of expected_usd OR manual override
	fx:              number;        // > 0 · default 7.73 cliente
	notes?:          string;
}

export interface PromoteWishlistResult {
	import:            Import;
	importItemsCount:  number;       // count of import_items rows inserted (= wishlistItemIds.length)
}

// ─── R3: Margen Real ────────────────────────────────────────────────
// camelCase field names match Rust serde rename — transparent translation

export interface MargenFilter {
	periodFrom?: string;       // YYYY-MM-DD
	periodTo?: string;         // YYYY-MM-DD
	supplier?: string;
	includePipeline?: boolean; // default false (closed only)
}

export interface BatchMargenSummary {
	importId: string;
	supplier: string;
	paidAt: string | null;
	arrivedAt: string | null;
	status: string;
	nUnits: number | null;
	totalLandedGtq: number | null;
	nSalesLinked: number;
	nItemsLinked: number;
	revenueTotalGtq: number;        // SUM(sale_items.unit_price) WHERE import_id=?
	margenBrutoGtq: number;
	margenPct: number | null;
	nStockPendiente: number;        // count import_items WHERE status='pending' (R6 single source)
	valorStockPendienteGtq: number; // SUM(COALESCE(import_items.unit_cost_gtq, imports.unit_cost)) for pending items
	nFreeUnits: number;
	valorFreeUnitsGtq: number | null; // null hasta que se decida D-FREE valuation rule
}

export interface LinkedSale {
	saleId: number;                 // Rust i64
	occurredAt: string | null;      // production col: sales.occurred_at
	customerId: number | null;      // production col: sales.customer_id is INTEGER
	total: number;                  // production col: sales.total (NOT total_gtq)
	nItemsFromBatch: number;
}

export interface PendingItem {
	importItemId: number;
	familyId: string;               // production col (NOT sku)
	jerseyId: string | null;
	size: string | null;
	playerName: string | null;
	playerNumber: number | null;
	patch: string | null;
	version: string | null;
	customerId: string | null;      // NULL = stock-future · populated = assigned to specific customer
	expectedUsd: number | null;
	unitCostGtq: number | null;     // null hasta que close (R4) corra prorrateo
	status: string;                 // 'pending' | 'arrived' | 'sold' | 'published' | 'cancelled'
}

export interface FreeUnitRow {
	freeUnitId: number;
	destination: string | null;
	destinationRef: string | null;
	assignedAt: string | null;
	notes: string | null;
}

export interface BatchMargenDetail {
	summary: BatchMargenSummary;
	linkedSales: LinkedSale[];
	pendingItems: PendingItem[];
	freeUnits: FreeUnitRow[];
}

export interface MargenPulso {
	nBatchesClosed: number;
	revenueTotalYtdGtq: number;
	landedTotalYtdGtq: number;
	margenTotalYtdGtq: number;
	margenPctAvg: number | null;
	bestBatchId: string | null;
	bestBatchMargenPct: number | null;
	worstBatchId: string | null;
	worstBatchMargenPct: number | null;
	capitalAmarradoGtq: number;
}

// ─── R4: Free Units (regalos · scrap · destinos) ────────────────────
// Rust uses #[serde(rename_all = "camelCase")] so wire format is already camelCase.

export type FreeUnitDestination = 'vip' | 'mystery' | 'garantizada' | 'personal';

export interface FreeUnit {
	freeUnitId: number;
	importId: string;
	familyId: string | null;
	jerseyId: string | null;
	destination: FreeUnitDestination | null;
	destinationRef: string | null;
	assignedAt: string | null;
	assignedBy: string | null;
	notes: string | null;
	createdAt: string;
	// Joined display fields (no extra query needed)
	importSupplier: string | null;
	importPaidAt: string | null;
}

export interface AssignFreeUnitInput {
	freeUnitId: number;
	destination: FreeUnitDestination;
	destinationRef?: string | null;   // required if destination='vip'
	familyId?: string | null;
	jerseyId?: string | null;
	notes?: string | null;
}

export interface FreeUnitFilter {
	importId?: string;
	destination?: FreeUnitDestination | 'unassigned';
	status?: 'assigned' | 'unassigned';
}

// ─── R5: Supplier Scorecard + Feedback Loop ─────────────────────────
// Rust uses #[serde(rename_all = "camelCase")] so wire format is camelCase.

export interface ContactInfo {
	label: string;
	paymentMethod: string;
	carrier: string;
}

export interface PriceBand {
	baseUsd: number | null;
	patchUsd: number | null;
	patchNameUsd: number | null;
	source: string;  // "hardcoded:Bond" | "tbd"
}

export interface SupplierBatchSummary {
	importId: string;
	paidAt: string | null;
	arrivedAt: string | null;
	status: string;
	nUnits: number | null;
	totalLandedGtq: number | null;
	leadTimeDays: number | null;
}

export interface SupplierMetrics {
	supplier: string;
	totalBatches: number;
	closedBatches: number;
	pipelineBatches: number;
	leadTimeAvgDays: number | null;
	leadTimeP50Days: number | null;
	leadTimeP95Days: number | null;
	leadTimeN: number;
	totalLandedGtqYtd: number;
	costAccuracyPct: number | null;
	nextExpectedArrival: string | null;
	lastBatchPaidAt: string | null;
}

export interface SupplierDetail {
	metrics: SupplierMetrics;
	contact: ContactInfo;
	priceBand: PriceBand;
	freePolicyText: string;
	batches: SupplierBatchSummary[];   // sorted DESC by paid_at
}

export interface UnpublishedRequest {
	familyId: string;
	nRequests: number;
	nPending: number;
	nAssigned: number;
	nStock: number;
	lastRequestedAt: string | null;
	published: boolean;   // siempre false en el response (filter aplicado server-side)
}

// ─── IMP-R6 Settings ────────────────────────────────────────────────────

export interface ImpSetting {
	key: string;
	value: string;
	updatedAt: string | null;
	updatedBy: string | null;
}

export interface MigrationLog {
	lastMigrationRunAt: string | null;
	importsCount: number;
	saleItemsLinked: number;
	jerseysLinked: number;
	wishlistCount: number;
	freeUnitsCount: number;
}

export interface IntegrationStatus {
	name: string;
	status: 'active' | 'disabled';
	lastReadAt: string | null;
	note: string | null;
}

export interface IntegrationsStatus {
	integrations: IntegrationStatus[];
}

// ─── Capabilities — lo que cada adapter puede hacer ──────────────────
export interface AdapterCapabilities {
	reads: boolean;
	writes: boolean;
	watermark: boolean;
	git: boolean;
	platform: 'browser' | 'tauri';
}

// ─── El contrato ─────────────────────────────────────────────────────
export interface Adapter {
	capabilities: AdapterCapabilities;

	// Reads
	listFamilies(filter?: ListFilter): Promise<Family[]>;
	getFamily(id: string): Promise<Family | null>;
	getDecision(sku: string): Promise<AuditDecision | null>;
	listDecisions(filter?: ListFilter): Promise<AuditDecision[]>;
	getPhotoActions(familyId: string): Promise<PhotoAction[]>;

	// Writes (Fase 2 — browser impl throws NotAvailable)
	setDecisionStatus(sku: string, status: AuditStatus, opts?: { override?: boolean }): Promise<void>;
	setFinalVerified(sku: string, verified: boolean): Promise<void>;
	updateGalleryOrder(canonicalFid: string, modeloIdx: number, newOrder: string[]): Promise<void>;
	removeModeloPhotos(
		familyId: string,
		modeloIdx: number,
		photoIndices: number[],
		alsoDeleteR2?: boolean
	): Promise<RemovePhotosResult>;
	setFamilyPublished(familyId: string, published: boolean): Promise<void>;
	setFamilyFeatured(familyId: string, featured: boolean): Promise<void>;
	setFamilyArchived(familyId: string, archived: boolean): Promise<void>;
	setPrimaryModeloIdx(familyId: string, modeloIdx: number): Promise<void>;
	setFamilyVariant(
		familyId: string,
		newVariant: string,
		newVariantLabel?: string
	): Promise<SetFamilyVariantResult>;
	moveModelo(args: MoveModeloArgs): Promise<MoveModeloResult>;
	setModeloSoldOut(familyId: string, modeloIdx: number, soldOut: boolean): Promise<void>;
	setModeloField(
		familyId: string,
		modeloIdx: number,
		field: 'price' | 'sizes' | 'notes',
		value: string | number | null
	): Promise<void>;
	invokeWatermark(args: WatermarkArgs): Promise<WatermarkResult>;
	commitAndPush(message: string): Promise<CommitResult>;
	gitStatus(): Promise<GitStatusInfo>;
	deleteSku(sku: string, motivo: string): Promise<DeleteSkuResult>;
	deleteFamily(familyId: string, motivo: string): Promise<DeleteFamilyResult>;
	backfillMeta(): Promise<BackfillMetaResult>;
	editModeloType(
		fid: string,
		modeloIdx: number,
		newType: string,
		newSleeve: string | null,
		motivo?: string
	): Promise<EditModeloTypeResult>;
	invalidateCache(): Promise<void>;
	openMsiFolder(): Promise<void>;
	batchCleanFamily(familyId: string, modeloIdx?: number): Promise<BatchCleanResult>;

	// ─── Comercial R1 ──────────────────────────────────────────
	listEvents(filter?: { status?: EventStatus; severity?: string }): Promise<ComercialEvent[]>;
	setEventStatus(eventId: number, status: EventStatus): Promise<void>;
	getOrderForModal(ref: string): Promise<OrderForModal | null>;
	markOrderShipped(ref: string, trackingCode?: string): Promise<void>;

	insertEvent(detected: DetectedEvent): Promise<number>;

	// Sales/leads/ads en range — para el pulso
	listSalesInRange(range: PeriodRange): Promise<Array<{ ref: string; totalGtq: number; paidAt: string; status: string }>>;
	listLeadsInRange(range: PeriodRange): Promise<Array<{ leadId: number; firstContactAt: string }>>;
	listAdSpendInRange(range: PeriodRange): Promise<Array<{ campaignId: string; spendGtq: number; capturedAt: string }>>;

	// ─── Comercial R2-combo ────────────────────────────────────────
	syncManychatData(args: { since: string | null; workerBase?: string; dashboardKey: string }): Promise<{ ok: boolean; leadsUpserted: number; conversationsUpserted: number; lastSyncAt: string; error?: string }>;
	listLeads(filter?: { status?: string; range?: PeriodRange }): Promise<Lead[]>;
	listConversations(filter?: { outcome?: string; range?: PeriodRange; leadId?: number }): Promise<ConversationMeta[]>;
	listCustomers(filter?: { lastOrderBefore?: string; minLtvGtq?: number }): Promise<Customer[]>;
	getMetaSync(source: string): Promise<MetaSyncStatus>;
	getConversationMessages(args: { convId: string; workerBase?: string; dashboardKey: string }): Promise<ConversationMessage[]>;

	// ─── Comercial R4 ──────────────────────────────────────────
	getCustomerProfile(customerId: number): Promise<CustomerProfile | null>;
	createCustomer(args: CreateCustomerArgs): Promise<{ ok: boolean; customerId?: number; error?: string }>;
	updateCustomerTraits(customerId: number, traitsJson: Record<string, unknown>): Promise<void>;
	setCustomerBlocked(customerId: number, blocked: boolean): Promise<void>;
	updateCustomerSource(customerId: number, source: string | null): Promise<void>;
	createManualOrder(args: CreateOrderArgs): Promise<{ ok: boolean; ref?: string; saleId?: number; error?: string }>;

	// ─── Comercial R5 ──────────────────────────────────────────
	syncMetaAds(args?: { days?: number; datePreset?: string }): Promise<MetaSyncResult>;
	listCampaigns(args?: { periodDays?: number }): Promise<Campaign[]>;
	getCampaignDetail(campaignId: string, periodDays?: number): Promise<CampaignDetail | null>;
	getFunnelAwarenessReal(args?: { periodStart?: string; periodEnd?: string }): Promise<FunnelAwarenessReal | null>;
	generateCoupon(args: { customerId: number; type: 'percent' | 'amount'; value: number; expiresInDays?: number }): Promise<{ ok: boolean; code?: string; error?: string; pending?: boolean }>;

	// ─── Comercial R6 ──────────────────────────────────────────
	backfillSalesAttribution(): Promise<BackfillAttributionResult>;
	getSaleAttribution(saleId: number): Promise<SaleAttribution | null>;

	// ─── Comercial R7 ──────────────────────────────────────────
	getConversationMeta(convId: string): Promise<ConversationMeta | null>;
	attributeSale(args: { saleId: number; campaignId: string | null; note?: string }): Promise<{ ok: boolean; error?: string }>;

	// ─── Comercial R9 ──────────────────────────────────────────
	importOrdersFromWorker(): Promise<ImportOrdersResult>;
	listSales(args?: { search?: string; status?: string; paymentMethod?: string; periodDays?: number; limit?: number; offset?: number }): Promise<SalesListResult>;

	// ─── Comercial R10 ──────────────────────────────────────────
	searchCustomers(query: string): Promise<CustomerSearchResult[]>;
	updateSale(args: UpdateSaleArgs): Promise<{ ok: boolean; error?: string }>;

	// ─── Comercial R11 ──────────────────────────────────────────
	replaceSaleItems(args: { saleId: number; items: CreateOrderItem[] }): Promise<{ ok: boolean; newSubtotal?: number; newTotal?: number; itemCount?: number; error?: string }>;

	// ─── Importaciones R1 ──────────────────────────────────────
	listImports(): Promise<Import[]>;
	getImport(importId: string): Promise<Import>;
	getImportItems(importId: string): Promise<ImportItem[]>;
	getImportPulso(): Promise<ImportPulso>;
	closeImportProportional(import_id: string): Promise<CloseImportResult>;

	// R1.5 additions
	createImport(input: CreateImportInput): Promise<Import>;
	registerArrival(input: RegisterArrivalInput): Promise<Import>;
	updateImport(input: UpdateImportInput): Promise<Import>;
	cancelImport(importId: string): Promise<Import>;
	exportImportsCsv(): Promise<string>;

	// R2 additions
	listWishlist(input: ListWishlistInput): Promise<WishlistItem[]>;
	createWishlistItem(input: CreateWishlistItemInput): Promise<WishlistItem>;
	updateWishlistItem(input: UpdateWishlistItemInput): Promise<WishlistItem>;
	cancelWishlistItem(wishlistItemId: number): Promise<WishlistItem>;
	promoteWishlistToBatch(input: PromoteWishlistInput): Promise<PromoteWishlistResult>;
	markInTransit(importId: string, trackingCode?: string): Promise<Import>;

	// R3 additions: Margen Real
	getMargenReal(filter: MargenFilter): Promise<BatchMargenSummary[]>;
	getBatchMargenBreakdown(importId: string): Promise<BatchMargenDetail>;
	getMargenPulso(): Promise<MargenPulso>;

	// R4 additions: Free Units
	listFreeUnits(filter?: FreeUnitFilter): Promise<FreeUnit[]>;
	assignFreeUnit(input: AssignFreeUnitInput): Promise<FreeUnit>;
	unassignFreeUnit(freeUnitId: number): Promise<FreeUnit>;

	// R5 additions: Supplier Scorecard + Feedback Loop
	getSupplierMetrics(): Promise<SupplierMetrics[]>;
	getSupplierDetail(supplier: string): Promise<SupplierDetail>;
	getMostRequestedUnpublished(limit?: number): Promise<UnpublishedRequest[]>;

	// R6 additions: Settings · migration log · integrations
	getImpSettings(): Promise<ImpSetting[]>;
	updateImpSetting(key: string, value: string): Promise<ImpSetting>;
	getMigrationLog(): Promise<MigrationLog>;
	getIntegrationsStatus(): Promise<IntegrationsStatus>;
	resyncMigration(): Promise<string>;  // throws on call (stub) · UI displays error

	// ─── Finanzas (FIN-R1) ──────────────────────────────────────
	computeProfitSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
		prevStart?: string,
		prevEnd?: string,
	): Promise<ProfitSnapshot>;
	getHomeSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
		prevStart?: string,
		prevEnd?: string,
	): Promise<HomeSnapshot>;
	createExpense(input: ExpenseInput): Promise<number>;
	listExpenses(filters?: {
		periodStart?: string;
		periodEnd?: string;
		category?: string;
		paymentMethod?: string;
		limit?: number;
	}): Promise<Expense[]>;
	deleteExpense(expenseId: number): Promise<void>;
	updateExpense(expenseId: number, input: ExpenseInput): Promise<void>;
	recentExpenses(limit?: number): Promise<RecentExpense[]>;
	setCashBalance(balanceGtq: number, source: string, notes?: string): Promise<number>;
}

// ─── Error para operaciones no disponibles en dev ────────────────────
export class NotAvailableInBrowser extends Error {
	constructor(op: string) {
		super(
			`"${op}" requires the desktop app. Run the installed ERP (.msi) or "npx tauri dev" — browser mode is read-only.`
		);
		this.name = 'NotAvailableInBrowser';
	}
}

// ─── Shape de la row cruda del catalog.json ──────────────────────────
// No se exporta al frontend — solo para transform.ts.
export interface CatalogRow {
	family_id: string;
	team: string;
	season: string;
	variant: string;
	variant_label?: string;
	category?: string;
	tier?: number | string;
	hero_thumbnail?: string | null;
	gallery?: string[];
	primary_modelo_idx?: number;
	published?: boolean;
	featured?: boolean;
	archived?: boolean;
	sku?: string | null;
	modelos?: CatalogModeloRow[];
	_priority?: number;
	meta_country?: string | null;
	meta_league?: string | null;
	meta_confederation?: string | null;
	wc2026_eligible?: boolean | null;
	supplier_gap?: boolean | null;
	[key: string]: unknown;
}

export interface CatalogModeloRow {
	sku?: string;
	type?: string;
	sleeve?: string | null;
	gallery?: string[];
	hero_thumbnail?: string | null;
	price?: number;
	sizes?: string;
	source_family_id?: string;
	[key: string]: unknown;
}

// ─── IMP-R1 ──────────────────────────────────────────────────────────
export type { Import, ImportStatus, ImportItem, ImportPulso, ImportFilter, CloseImportResult } from '../data/importaciones';
export { STATUS_LABELS as IMPORT_STATUS_LABELS, STATUS_PROGRESS as IMPORT_STATUS_PROGRESS } from '../data/importaciones';

// ─── Finanzas (FIN-R1) ─────────────────────────────────────────────
export type {
  Expense,
  ExpenseInput,
  ExpenseCategory,
  ExpenseSource,
  PaymentMethod,
  Currency,
  Period,
  PeriodRange,
  ProfitSnapshot,
  HomeSnapshot,
  RecentExpense,
  InboxSeverity,
  FinanzasInboxEvent,
} from '$lib/data/finanzas';

export {
  CATEGORY_LABELS as FIN_CATEGORY_LABELS,
  CATEGORY_PILL_CLASS as FIN_CATEGORY_PILL,
  PAYMENT_METHOD_ICON as FIN_PAYMENT_ICON,
  PAYMENT_METHOD_LABEL as FIN_PAYMENT_LABEL,
} from '$lib/data/finanzas';

// Re-export para conveniencia
export type { Family, Status };

// =============================================================================
// Admin Web R7 (T1.3) — Tauri commands contract
// =============================================================================
// AdminWebTauriCommands documenta el set de IPC commands que el ERP Rust va a
// implementar en src-tauri/src/lib.rs. NO forma parte del `Adapter` interface
// existente — el patron de Audit/Comercial era una sola `Adapter` interface
// monolitica, pero Admin Web tiene 60+ commands y un dominio nuevo, asi que
// los wrappers viven como funciones independientes en tauri.ts (T1.4) y este
// interface sirve como contrato + auto-completado.
// Imports de los 5 archivos lib/data/ y de los re-exports existentes.

import type {
	HomeKpis,
	SavedView,
	ModuleViewKey,
	UniversoFilters,
	UniversoQueryResult,
	SortConfig,
	PaginationConfig,
	SitePage,
	PageCategory,
	PageStatus,
	SiteComponent,
	ComponentType,
	BrandingValue,
	BrandingValueType,
	CommunicationTemplate,
	CommunicationChannel,
	Subscriber,
	Workflow,
	Review,
	ReviewStatus,
	Survey,
	AuditLogEntry,
	AuditSeverity,
	ScrapHistoryEntry,
	DeployHistoryEntry,
	DeployTarget,
	ScheduledJob,
	BackupEntry,
	BackupType,
	HealthSnapshot
} from '../data/admin-web';
import type { Jersey } from '../data/jersey-states';
import type {
	TagType,
	Tag,
	TagAssignmentValidation
} from '../data/tags';
import type {
	StockOverride,
	MysteryOverride,
	OverrideStatus
} from '../data/overrides';
import type {
	InboxEvent,
	EventSeverity,
	ModuleSlug
} from '../data/inbox-events';

export interface AdminWebTauriCommands {
	// === HOME ===
	get_admin_web_kpis: () => Promise<HomeKpis>;
	get_module_stats: (args: { module: ModuleSlug }) => Promise<Record<string, unknown>>;

	// === INBOX EVENTS ===
	list_inbox_events: (args: {
		include_dismissed?: boolean;
		severity_filter?: EventSeverity[];
	}) => Promise<InboxEvent[]>;
	dismiss_event: (args: { id: number }) => Promise<void>;
	resolve_event: (args: { id: number }) => Promise<void>;
	detect_events_now: () => Promise<{ events_created: number }>;

	// === VAULT — TAGS ===
	list_tag_types: () => Promise<TagType[]>;
	list_tags: (args?: { type_id?: number; include_deleted?: boolean }) => Promise<Tag[]>;
	create_tag: (args: {
		type_id: number;
		slug: string;
		display_name: string;
		icon?: string;
		color?: string;
	}) => Promise<Tag>;
	update_tag: (args: { id: number; updates: Partial<Tag> }) => Promise<Tag>;
	soft_delete_tag: (args: { id: number }) => Promise<void>;
	list_jersey_tags: (args: { family_id: string }) => Promise<Tag[]>;
	list_jerseys_by_tag: (args: {
		tag_id: number;
		pagination?: PaginationConfig;
	}) => Promise<Jersey[]>;
	validate_tag_assignment: (args: {
		family_id: string;
		tag_id: number;
	}) => Promise<TagAssignmentValidation>;
	assign_tag: (args: {
		family_id: string;
		tag_id: number;
		force_replace?: boolean;
	}) => Promise<void>;
	remove_tag: (args: { family_id: string; tag_id: number }) => Promise<void>;

	// === VAULT — PUBLICADOS ===
	list_published: (args: {
		filter?: 'all' | 'attention' | 'recent' | 'scheduled' | 'no_tags' | 'old';
		pagination?: PaginationConfig;
	}) => Promise<Jersey[]>;
	promote_to_stock: (args: {
		family_id: string;
		override: Partial<StockOverride>;
	}) => Promise<StockOverride>;
	promote_to_mystery: (args: {
		family_id: string;
		override: Partial<MysteryOverride>;
	}) => Promise<MysteryOverride>;
	toggle_dirty_flag: (args: {
		family_id: string;
		dirty: boolean;
		reason?: string;
	}) => Promise<void>;
	archive_jersey: (args: { family_id: string }) => Promise<void>;
	revive_archived: (args: {
		family_id: string;
		scheduled_at?: number;
	}) => Promise<void>;

	// === VAULT — UNIVERSO ===
	list_universo: (args: {
		filters: UniversoFilters;
		sort?: SortConfig;
		pagination: PaginationConfig;
	}) => Promise<UniversoQueryResult>;
	bulk_action: (args: {
		family_ids: string[];
		action: 'tag' | 'archive' | 're_fetch' | 'delete';
		payload?: Record<string, unknown>;
	}) => Promise<{ affected: number; errors: string[] }>;

	// === SAVED VIEWS ===
	list_saved_views: (args: { module: ModuleViewKey }) => Promise<SavedView[]>;
	save_view: (args: Omit<SavedView, 'id' | 'created_at'>) => Promise<SavedView>;
	delete_view: (args: { id: number }) => Promise<void>;

	// === STOCK ===
	list_stock_overrides: (args: {
		status_filter?: OverrideStatus[];
		pagination?: PaginationConfig;
	}) => Promise<StockOverride[]>;
	create_stock_override: (args: {
		override: Omit<StockOverride, 'id' | 'computed_status' | 'created_at' | 'updated_at'>;
	}) => Promise<StockOverride>;
	update_stock_override: (args: {
		id: number;
		updates: Partial<StockOverride>;
	}) => Promise<StockOverride>;
	delete_stock_override: (args: { id: number }) => Promise<void>;
	pause_stock_override: (args: { id: number }) => Promise<void>;
	list_stock_calendar: (args: { from: number; to: number }) => Promise<StockOverride[]>;

	// === MYSTERY ===
	list_mystery_overrides: (args: {
		status_filter?: OverrideStatus[];
		pagination?: PaginationConfig;
	}) => Promise<MysteryOverride[]>;
	create_mystery_override: (args: {
		override: Omit<MysteryOverride, 'id' | 'computed_status' | 'created_at' | 'updated_at'>;
	}) => Promise<MysteryOverride>;
	update_mystery_override: (args: {
		id: number;
		updates: Partial<MysteryOverride>;
	}) => Promise<MysteryOverride>;
	delete_mystery_override: (args: { id: number }) => Promise<void>;
	list_mystery_calendar: (args: {
		from: number;
		to: number;
	}) => Promise<MysteryOverride[]>;
	get_mystery_rules: () => Promise<Record<string, unknown>>;
	update_mystery_rules: (args: { rules: Record<string, unknown> }) => Promise<void>;

	// === SITE — PAGES ===
	list_pages: (args?: {
		category?: PageCategory;
		status?: PageStatus;
	}) => Promise<SitePage[]>;
	get_page: (args: { id: number }) => Promise<SitePage>;
	create_page: (args: {
		page: Omit<SitePage, 'id' | 'created_at' | 'updated_at'>;
	}) => Promise<SitePage>;
	update_page: (args: { id: number; updates: Partial<SitePage> }) => Promise<SitePage>;
	delete_page: (args: { id: number }) => Promise<void>;
	publish_page: (args: { id: number; scheduled_at?: number }) => Promise<void>;

	// === SITE — COMPONENTS ===
	list_components: (args?: {
		type_filter?: ComponentType[];
	}) => Promise<SiteComponent[]>;
	update_component: (args: {
		id: number;
		updates: Partial<SiteComponent>;
	}) => Promise<SiteComponent>;
	toggle_component: (args: { id: number; enabled: boolean }) => Promise<void>;

	// === SITE — BRANDING ===
	list_branding: () => Promise<BrandingValue[]>;
	set_branding: (args: {
		key: string;
		value: string;
		value_type: BrandingValueType;
	}) => Promise<void>;
	apply_branding_changes: () => Promise<{ deploy_triggered: boolean }>;

	// === SITE — COMMUNICATION ===
	list_templates: (args?: {
		channel_filter?: CommunicationChannel[];
	}) => Promise<CommunicationTemplate[]>;
	create_template: (args: {
		template: Omit<CommunicationTemplate, 'id' | 'created_at' | 'updated_at'>;
	}) => Promise<CommunicationTemplate>;
	update_template: (args: {
		id: number;
		updates: Partial<CommunicationTemplate>;
	}) => Promise<CommunicationTemplate>;
	list_subscribers: (args?: {
		list_id?: number;
		pagination?: PaginationConfig;
	}) => Promise<Subscriber[]>;
	list_workflows: () => Promise<Workflow[]>;
	toggle_workflow: (args: { id: number; enabled: boolean }) => Promise<void>;

	// === SITE — COMMUNITY ===
	list_reviews: (args?: {
		status_filter?: ReviewStatus[];
		pagination?: PaginationConfig;
	}) => Promise<Review[]>;
	moderate_review: (args: {
		id: number;
		status: ReviewStatus;
		note?: string;
	}) => Promise<void>;
	list_surveys: () => Promise<Survey[]>;
	list_survey_responses: (args: {
		survey_id: number;
		pagination?: PaginationConfig;
	}) => Promise<{ id: number; answers: unknown; submitted_at: number }[]>;

	// === SISTEMA ===
	get_health_snapshot: () => Promise<HealthSnapshot>;
	get_health_history: (args: {
		metric: string;
		from: number;
		to: number;
	}) => Promise<HealthSnapshot[]>;
	list_scrap_history: (args?: {
		pagination?: PaginationConfig;
	}) => Promise<ScrapHistoryEntry[]>;
	trigger_scrap: (args: {
		category_url: string;
		flags?: Record<string, unknown>;
	}) => Promise<{ scrap_id: number }>;
	list_deploy_history: (args?: {
		target?: DeployTarget;
		pagination?: PaginationConfig;
	}) => Promise<DeployHistoryEntry[]>;
	trigger_deploy: (args: {
		target: DeployTarget;
		commit_sha?: string;
	}) => Promise<{ deploy_id: number }>;
	rollback_deploy: (args: { deploy_id: number }) => Promise<void>;
	list_jobs: () => Promise<ScheduledJob[]>;
	toggle_job: (args: { id: number; enabled: boolean }) => Promise<void>;
	run_job_now: (args: { id: number }) => Promise<void>;
	list_backups: (args?: {
		type?: BackupType;
		pagination?: PaginationConfig;
	}) => Promise<BackupEntry[]>;
	create_backup_now: (args: { type: BackupType }) => Promise<BackupEntry>;
	restore_from_backup: (args: {
		backup_id: number;
		confirm_token: string;
	}) => Promise<void>;
	stream_logs: (args: { tail_lines?: number }) => Promise<string>;
	list_audit_log: (args: {
		filters?: {
			module?: ModuleSlug;
			user?: string;
			from?: number;
			to?: number;
			severity?: AuditSeverity;
		};
		pagination?: PaginationConfig;
	}) => Promise<AuditLogEntry[]>;
	export_audit_log_csv: (args: {
		filters?: Record<string, unknown>;
	}) => Promise<{ file_path: string }>;
	get_admin_config: () => Promise<Record<string, { value: string; value_type: string }>>;
	set_admin_config: (args: {
		key: string;
		value: string;
		value_type: string;
	}) => Promise<void>;
	list_api_connections: () => Promise<
		{
			name: string;
			status: 'connected' | 'failing' | 'pending';
			last_test_at?: number;
			usage?: Record<string, unknown>;
		}[]
	>;
	test_api_connection: (args: {
		name: string;
	}) => Promise<{ success: boolean; message?: string }>;
	rotate_secret: (args: { name: string }) => Promise<{ success: boolean }>;
}

// Re-export de types nuevos para conveniencia (mismo patrón que IMP/FIN arriba).
export type {
	JerseyState,
	JerseyFlags,
	Jersey,
	JerseyModelo
} from '../data/jersey-states';
export { VALID_TRANSITIONS, canTransition } from '../data/jersey-states';

export type {
	TagCardinality,
	TagTypeSlug,
	ConditionalRule,
	TagType,
	Tag,
	AutoDerivationRule,
	JerseyTag,
	TagAssignmentValidation
} from '../data/tags';

export type {
	OverrideStatus,
	StockOverride,
	MysteryOverride
} from '../data/overrides';

export type {
	ModuleSlug,
	EventSeverity,
	EventType,
	InboxEvent
} from '../data/inbox-events';
export { AUTO_DISMISS_DAYS } from '../data/inbox-events';

export type {
	HomeKpis,
	KpiSnapshot,
	ModuleViewKey,
	SavedView,
	PageCategory,
	PageStatus,
	BlockType,
	PageBlock,
	SitePage,
	SeoMeta,
	ComponentType,
	SiteComponent,
	BrandingValueType,
	BrandingValue,
	CommunicationChannel,
	CommunicationTemplate,
	SubscriberList,
	SegmentRule,
	Subscriber,
	Workflow,
	WorkflowTrigger,
	WorkflowStep,
	WorkflowCondition,
	ReviewStatus,
	Review,
	Survey,
	SurveyQuestion,
	AuditAction,
	AuditSeverity,
	AuditLogEntry,
	ScrapStatus,
	ScrapHistoryEntry,
	DeployTarget,
	DeployStatus,
	DeployHistoryEntry,
	ScheduledJob,
	BackupType,
	BackupEntry,
	HealthSnapshot,
	HealthAlert,
	CommandCategory,
	CommandPaletteItem,
	UniversoFilters,
	SortConfig,
	PaginationConfig,
	UniversoQueryResult
} from '../data/admin-web';
