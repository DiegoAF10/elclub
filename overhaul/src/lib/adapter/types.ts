// Adapter types — contrato agnóstico de plataforma.
// Implementaciones concretas: browser.ts (dev sin Tauri) + tauri.ts (app nativa).

import type { Family, Status } from '../data/types';
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
	CreateOrderArgs
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

// Re-export para conveniencia
export type { Family, Status };
