// Tauri adapter — scaffolding listo para Fase 2.
// Las Rust commands se implementan en src-tauri/src/main.rs (Fase 2).
// Esta impl delegará a `invoke()` del @tauri-apps/api cuando esté wired.
//
// En Fase 1 este módulo está inactivo (isTauri() retorna false sin runtime).
// En Fase 2 se importará dinámicamente @tauri-apps/api y las Rust commands
// estarán registradas en el Rust backend.

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
	FreeUnitFilter
} from './types';
import type { WishlistItem } from '$lib/data/wishlist';
import type { ComercialEvent, DetectedEvent, EventStatus, OrderForModal, PeriodRange, Lead, ConversationMeta, ConversationMessage, Customer, MetaSyncStatus, CustomerProfile, CreateCustomerArgs, CreateOrderArgs, CreateOrderItem, Campaign, CampaignDetail, FunnelAwarenessReal, MetaSyncResult, SaleAttribution, BackfillAttributionResult, ImportOrdersResult, SalesListResult, CustomerSearchResult, UpdateSaleArgs } from '../data/comercial';
import type { Import, ImportItem, ImportPulso, CloseImportResult } from '../data/importaciones';
import type { Family } from '../data/types';
import type { Expense, ExpenseInput, ProfitSnapshot, HomeSnapshot, RecentExpense } from '../data/finanzas';
import { transformFamily } from './transform';

// ─── Detection ────────────────────────────────────────────────────────
// Tauri 2 expone `window.__TAURI_INTERNALS__` en el runtime nativo.
// En browser mode, esta property no existe → isTauri() = false.
export function isTauri(): boolean {
	if (typeof window === 'undefined') return false;
	// Check both v1 (__TAURI__) and v2 (__TAURI_INTERNALS__) for forward-compat.
	return (
		// @ts-expect-error — window augmentation at runtime
		typeof window.__TAURI_INTERNALS__ !== 'undefined' ||
		// @ts-expect-error — window augmentation at runtime
		typeof window.__TAURI__ !== 'undefined'
	);
}

// ─── Dynamic invoke — importa @tauri-apps/api solo si corre en Tauri ──
// Evita que el build browser falle por import no resuelto.
async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	if (!isTauri()) {
		throw new Error(
			`Tauri runtime not detected — tried to invoke "${cmd}" but window.__TAURI_INTERNALS__ is undefined.`
		);
	}
	const { invoke: tauriInvoke } = await import('@tauri-apps/api/core');
	return (await tauriInvoke(cmd, args)) as T;
}

export const tauriAdapter: Adapter = {
	capabilities: {
		reads: true,
		writes: true,
		watermark: true,
		git: true,
		platform: 'tauri'
	} as AdapterCapabilities,

	// ─── Reads ──────────────────────────────────────────────────────────
	async listFamilies(filter?: ListFilter): Promise<Family[]> {
		// Rust devuelve raw catalog rows. Merge con decisions + transform acá
		// (mismo pipeline que browser.ts, single source of truth en transform.ts).
		const [rows, decisionsList] = await Promise.all([
			invoke<CatalogRow[]>('list_families', { filter }),
			invoke<AuditDecision[]>('list_decisions', { filter: undefined }).catch(
				() => [] as AuditDecision[]
			)
		]);
		const decisionsBySku = new Map(decisionsList.map((d) => [d.sku, d]));
		return rows.map((r) => transformFamily(r, decisionsBySku));
	},

	async getFamily(id: string): Promise<Family | null> {
		const [row, decisionsList] = await Promise.all([
			invoke<CatalogRow | null>('get_family', { id }),
			invoke<AuditDecision[]>('list_decisions', { filter: undefined }).catch(
				() => [] as AuditDecision[]
			)
		]);
		if (!row) return null;
		const decisionsBySku = new Map(decisionsList.map((d) => [d.sku, d]));
		return transformFamily(row, decisionsBySku);
	},

	async getDecision(sku: string): Promise<AuditDecision | null> {
		return invoke<AuditDecision | null>('get_decision', { sku });
	},

	async listDecisions(filter?: ListFilter): Promise<AuditDecision[]> {
		return invoke<AuditDecision[]>('list_decisions', { filter });
	},

	async getPhotoActions(familyId: string): Promise<PhotoAction[]> {
		return invoke<PhotoAction[]>('get_photo_actions', { familyId });
	},

	// ─── Writes — requieren Rust commands registrados en src-tauri ─────
	async setDecisionStatus(
		sku: string,
		status: AuditStatus,
		opts?: { override?: boolean }
	): Promise<void> {
		// Tauri auto-converts JS camelCase → Rust snake_case; pasamos overrideSagrado
		// para matchear `override_sagrado: Option<bool>` en lib.rs.
		return invoke<void>('set_decision_status', {
			sku,
			status,
			overrideSagrado: !!opts?.override
		});
	},

	async setFinalVerified(sku: string, verified: boolean): Promise<void> {
		return invoke<void>('set_final_verified', { sku, verified });
	},

	async updateGalleryOrder(
		canonicalFid: string,
		modeloIdx: number,
		newOrder: string[]
	): Promise<void> {
		return invoke<void>('update_gallery_order', {
			canonicalFid,
			modeloIdx,
			newOrder
		});
	},

	async removeModeloPhotos(
		familyId: string,
		modeloIdx: number,
		photoIndices: number[],
		alsoDeleteR2?: boolean
	): Promise<RemovePhotosResult> {
		return invoke<RemovePhotosResult>('remove_modelo_photos', {
			familyId,
			modeloIdx,
			photoIndices,
			alsoDeleteR2: !!alsoDeleteR2
		});
	},

	async setFamilyPublished(familyId: string, published: boolean): Promise<void> {
		return invoke<void>('set_family_published', { familyId, published });
	},

	async setFamilyFeatured(familyId: string, featured: boolean): Promise<void> {
		return invoke<void>('set_family_featured', { familyId, featured });
	},

	async setFamilyArchived(familyId: string, archived: boolean): Promise<void> {
		return invoke<void>('set_family_archived', { familyId, archived });
	},

	async setPrimaryModeloIdx(familyId: string, modeloIdx: number): Promise<void> {
		return invoke<void>('set_primary_modelo_idx', { familyId, modeloIdx });
	},

	async setFamilyVariant(
		familyId: string,
		newVariant: string,
		newVariantLabel?: string
	): Promise<SetFamilyVariantResult> {
		return invoke<SetFamilyVariantResult>('set_family_variant', {
			familyId,
			newVariant,
			newVariantLabel: newVariantLabel ?? null
		});
	},

	async moveModelo(args: MoveModeloArgs): Promise<MoveModeloResult> {
		return invoke<MoveModeloResult>('move_modelo', { args });
	},

	async setModeloSoldOut(familyId: string, modeloIdx: number, soldOut: boolean): Promise<void> {
		return invoke<void>('set_modelo_sold_out', { familyId, modeloIdx, soldOut });
	},

	async setModeloField(
		familyId: string,
		modeloIdx: number,
		field: 'price' | 'sizes' | 'notes',
		value: string | number | null
	): Promise<void> {
		return invoke<void>('set_modelo_field', { familyId, modeloIdx, field, value });
	},

	async invokeWatermark(args: WatermarkArgs): Promise<WatermarkResult> {
		return invoke<WatermarkResult>('invoke_watermark', { args });
	},

	async commitAndPush(message: string): Promise<CommitResult> {
		return invoke<CommitResult>('commit_and_push', { message });
	},

	async gitStatus(): Promise<GitStatusInfo> {
		return invoke<GitStatusInfo>('git_status');
	},

	async deleteSku(sku: string, motivo: string): Promise<DeleteSkuResult> {
		return invoke<DeleteSkuResult>('delete_sku', { args: { sku, motivo } });
	},

	async deleteFamily(familyId: string, motivo: string): Promise<DeleteFamilyResult> {
		return invoke<DeleteFamilyResult>('delete_family', { args: { familyId, motivo } });
	},

	async backfillMeta(): Promise<BackfillMetaResult> {
		return invoke<BackfillMetaResult>('backfill_meta');
	},

	async editModeloType(
		fid: string,
		modeloIdx: number,
		newType: string,
		newSleeve: string | null,
		motivo?: string
	): Promise<EditModeloTypeResult> {
		return invoke<EditModeloTypeResult>('edit_modelo_type', {
			args: {
				fid,
				modeloIdx,
				newType,
				newSleeve,
				motivo: motivo ?? ''
			}
		});
	},

	async invalidateCache(): Promise<void> {
		return invoke<void>('invalidate_cache');
	},

	async openMsiFolder(): Promise<void> {
		return invoke<void>('open_msi_folder');
	},

	async batchCleanFamily(familyId: string, modeloIdx?: number): Promise<BatchCleanResult> {
		return invoke<BatchCleanResult>('batch_clean_family', { familyId, modeloIdx });
	},

	// ─── Comercial R1 ──────────────────────────────────────────
	async listEvents(filter?: { status?: EventStatus; severity?: string }): Promise<ComercialEvent[]> {
		return invoke<ComercialEvent[]>('comercial_list_events', { filter: filter ?? {} });
	},

	async setEventStatus(eventId: number, status: EventStatus): Promise<void> {
		return invoke<void>('comercial_set_event_status', { eventId, status });
	},

	async getOrderForModal(ref: string): Promise<OrderForModal | null> {
		return invoke<OrderForModal | null>('comercial_get_order', { args: { ref } });
	},

	async markOrderShipped(ref: string, trackingCode?: string): Promise<void> {
		return invoke<void>('comercial_mark_order_shipped', { args: { ref, trackingCode: trackingCode ?? null } });
	},

	async insertEvent(detected: DetectedEvent): Promise<number> {
		return invoke<number>('comercial_insert_event', {
			args: {
				type: detected.type,
				severity: detected.severity,
				title: detected.title,
				sub: detected.sub,
				itemsAffected: detected.itemsAffected
			}
		});
	},

	async listSalesInRange(range: PeriodRange) {
		return invoke<Array<{ ref: string; totalGtq: number; paidAt: string; status: string }>>(
			'comercial_list_sales_in_range',
			{ start: range.start, end: range.end }
		);
	},

	async listLeadsInRange(range: PeriodRange) {
		return invoke<Array<{ leadId: number; firstContactAt: string }>>(
			'comercial_list_leads_in_range',
			{ start: range.start, end: range.end }
		);
	},

	async listAdSpendInRange(range: PeriodRange) {
		return invoke<Array<{ campaignId: string; spendGtq: number; capturedAt: string }>>(
			'comercial_list_ad_spend_in_range',
			{ start: range.start, end: range.end }
		);
	},

	// ─── Comercial R2 ──────────────────────────────────────────
	async syncManychatData(args) {
		return invoke<{ ok: boolean; leadsUpserted: number; conversationsUpserted: number; lastSyncAt: string; error?: string }>(
			'comercial_sync_manychat',
			{ args: { since: args.since, workerBase: args.workerBase, dashboardKey: args.dashboardKey } }
		);
	},

	async listLeads(filter?: { status?: string; range?: PeriodRange }): Promise<Lead[]> {
		const f = filter ?? {};
		const result = await invoke<unknown[]>('comercial_list_leads', {
			filter: {
				status: f.status,
				rangeStart: f.range?.start,
				rangeEnd: f.range?.end,
			},
		});
		return result as Lead[];
	},

	async listConversations(filter?: { outcome?: string; range?: PeriodRange; leadId?: number }): Promise<ConversationMeta[]> {
		const f = filter ?? {};
		const result = await invoke<unknown[]>('comercial_list_conversations', {
			filter: {
				outcome: f.outcome,
				rangeStart: f.range?.start,
				rangeEnd: f.range?.end,
				leadId: f.leadId,
			},
		});
		return result as ConversationMeta[];
	},

	async listCustomers(filter?: { lastOrderBefore?: string; minLtvGtq?: number }): Promise<Customer[]> {
		const f = filter ?? {};
		const result = await invoke<unknown[]>('comercial_list_customers', {
			filter: { lastOrderBefore: f.lastOrderBefore, minLtvGtq: f.minLtvGtq },
		});
		return result as Customer[];
	},

	async getMetaSync(source: string): Promise<MetaSyncStatus> {
		const result = await invoke<unknown>('comercial_get_meta_sync', { source });
		if (!result) return { source, lastSyncAt: null, lastStatus: null, lastError: null };
		return result as MetaSyncStatus;
	},

	async getConversationMessages(args): Promise<ConversationMessage[]> {
		return invoke<ConversationMessage[]>('comercial_get_conversation_messages', {
			args: {
				convId: args.convId,
				workerBase: args.workerBase,
				dashboardKey: args.dashboardKey,
			},
		});
	},

	// ─── Comercial R4 ──────────────────────────────────────────
	async getCustomerProfile(customerId: number): Promise<CustomerProfile | null> {
		const result = await invoke<unknown>('comercial_get_customer_profile', { customerId });
		return (result as CustomerProfile | null) ?? null;
	},

	async createCustomer(args: CreateCustomerArgs) {
		return invoke<{ ok: boolean; customerId?: number; error?: string }>(
			'comercial_create_customer',
			{ args: { name: args.name, phone: args.phone, email: args.email, source: args.source } }
		);
	},

	async updateCustomerTraits(customerId: number, traitsJson: Record<string, unknown>): Promise<void> {
		await invoke('comercial_update_customer_traits', {
			args: { customerId, traitsJson },
		});
	},

	async setCustomerBlocked(customerId: number, blocked: boolean): Promise<void> {
		await invoke('comercial_set_customer_blocked', {
			args: { customerId, blocked },
		});
	},

	async updateCustomerSource(customerId: number, source: string | null): Promise<void> {
		await invoke('comercial_update_customer_source', {
			args: { customerId, source },
		});
	},

	async createManualOrder(args: CreateOrderArgs) {
		return invoke<{ ok: boolean; ref?: string; saleId?: number; error?: string }>(
			'comercial_create_manual_order',
			{
				args: {
					customerId: args.customerId,
					items: args.items,
					paymentMethod: args.paymentMethod,
					fulfillmentStatus: args.fulfillmentStatus,
					shippingFee: args.shippingFee,
					discount: args.discount,
					notes: args.notes,
					modality: args.modality,
					origin: args.origin,
					shippingMethod: args.shippingMethod,
					shippingAddress: args.shippingAddress,
					occurredAt: args.occurredAt,
				},
			}
		);
	},

	// ─── Comercial R5 ──────────────────────────────────────────
	async syncMetaAds(args = {}) {
		return invoke<MetaSyncResult>('comercial_sync_meta_ads', { args: { days: args.days, datePreset: args.datePreset } });
	},

	async listCampaigns(args = {}) {
		const result = await invoke<unknown>('comercial_list_campaigns', { args: { periodDays: args.periodDays } });
		return (result as Campaign[]) ?? [];
	},

	async getCampaignDetail(campaignId: string, periodDays?: number) {
		const result = await invoke<unknown>('comercial_get_campaign_detail', { args: { campaignId, periodDays } });
		return (result as CampaignDetail | null) ?? null;
	},

	async getFunnelAwarenessReal(args = {}) {
		const result = await invoke<unknown>('comercial_get_funnel_awareness_real', { args: { periodStart: args.periodStart, periodEnd: args.periodEnd } });
		return (result as FunnelAwarenessReal | null) ?? null;
	},

	async generateCoupon(args) {
		return invoke<{ ok: boolean; code?: string; error?: string; pending?: boolean }>(
			'comercial_generate_coupon',
			{ args: { customerId: args.customerId, type: args.type, value: args.value, expiresInDays: args.expiresInDays } }
		);
	},

	// ─── Comercial R6 ──────────────────────────────────────────
	async backfillSalesAttribution() {
		return invoke<BackfillAttributionResult>('comercial_backfill_sales_attribution');
	},

	async getSaleAttribution(saleId: number) {
		const result = await invoke<unknown>('comercial_get_sale_attribution', { saleId });
		return (result as SaleAttribution | null) ?? null;
	},

	// ─── Comercial R7 ──────────────────────────────────────────
	async getConversationMeta(convId: string) {
		const result = await invoke<unknown>('comercial_get_conversation_meta', { convId });
		return (result as ConversationMeta | null) ?? null;
	},

	async attributeSale(args) {
		return invoke<{ ok: boolean; error?: string }>(
			'comercial_attribute_sale',
			{ args: { saleId: args.saleId, campaignId: args.campaignId, note: args.note } }
		);
	},

	// ─── Comercial R9 ──────────────────────────────────────────
	async importOrdersFromWorker() {
		return invoke<ImportOrdersResult>('comercial_import_orders_from_worker');
	},
	async listSales(args = {}) {
		return invoke<SalesListResult>('comercial_list_sales', { args: {
			search: args.search,
			status: args.status,
			paymentMethod: args.paymentMethod,
			periodDays: args.periodDays,
			limit: args.limit,
			offset: args.offset,
		}});
	},

	// ─── Comercial R10 ──────────────────────────────────────────
	async searchCustomers(query: string) {
		const result = await invoke<unknown>('comercial_search_customers', { args: { query } });
		return (result as CustomerSearchResult[]) ?? [];
	},

	async updateSale(args: UpdateSaleArgs) {
		return invoke<{ ok: boolean; error?: string }>('comercial_update_sale', {
			args: {
				saleId: args.saleId,
				occurredAt: args.occurredAt,
				modality: args.modality,
				origin: args.origin,
				paymentMethod: args.paymentMethod,
				fulfillmentStatus: args.fulfillmentStatus,
				shippingMethod: args.shippingMethod,
				trackingCode: args.trackingCode,
				shippingFee: args.shippingFee,
				discount: args.discount,
				notes: args.notes,
				shippingAddress: args.shippingAddress,
				customerId: args.customerId,
			},
		});
	},

	// ─── Comercial R11 ──────────────────────────────────────────
	async replaceSaleItems(args: { saleId: number; items: CreateOrderItem[] }) {
		return invoke<{ ok: boolean; newSubtotal?: number; newTotal?: number; itemCount?: number; error?: string }>(
			'comercial_replace_sale_items',
			{ args: { saleId: args.saleId, items: args.items } }
		);
	},

	// ─── Importaciones R1 ──────────────────────────────────────
	async listImports(): Promise<Import[]> {
		return invoke<Import[]>('cmd_list_imports');
	},

	async getImport(importId: string): Promise<Import> {
		return invoke<Import>('cmd_get_import', { importId });
	},

	async getImportItems(importId: string): Promise<ImportItem[]> {
		return invoke<ImportItem[]>('cmd_get_import_items', { importId });
	},

	async getImportPulso(): Promise<ImportPulso> {
		return invoke<ImportPulso>('cmd_get_import_pulso');
	},

	async closeImportProportional(import_id: string): Promise<CloseImportResult> {
		return invoke<CloseImportResult>('cmd_close_import_proportional', { importId: import_id });
	},

	async createImport(input: CreateImportInput): Promise<Import> {
		return await invoke<Import>('cmd_create_import', { input });
	},

	async registerArrival(input: RegisterArrivalInput): Promise<Import> {
		return await invoke<Import>('cmd_register_arrival', { input });
	},

	async updateImport(input: UpdateImportInput): Promise<Import> {
		return await invoke<Import>('cmd_update_import', { input });
	},

	async cancelImport(importId: string): Promise<Import> {
		return await invoke<Import>('cmd_cancel_import', { importId });
	},

	async exportImportsCsv(): Promise<string> {
		return await invoke<string>('cmd_export_imports_csv');
	},

	// ─── Importaciones R2 ──────────────────────────────────────────
	async listWishlist(input: ListWishlistInput): Promise<WishlistItem[]> {
		return await invoke<WishlistItem[]>('cmd_list_wishlist', { input });
	},

	async createWishlistItem(input: CreateWishlistItemInput): Promise<WishlistItem> {
		return await invoke<WishlistItem>('cmd_create_wishlist_item', { input });
	},

	async updateWishlistItem(input: UpdateWishlistItemInput): Promise<WishlistItem> {
		return await invoke<WishlistItem>('cmd_update_wishlist_item', { input });
	},

	async cancelWishlistItem(wishlistItemId: number): Promise<WishlistItem> {
		return await invoke<WishlistItem>('cmd_cancel_wishlist_item', { wishlistItemId });
	},

	async promoteWishlistToBatch(input: PromoteWishlistInput): Promise<PromoteWishlistResult> {
		return await invoke<PromoteWishlistResult>('cmd_promote_wishlist_to_batch', { input });
	},

	async markInTransit(importId: string, trackingCode?: string): Promise<Import> {
		return await invoke<Import>('cmd_mark_in_transit', { importId, trackingCode });
	},

	// ─── Importaciones R3 (Margen Real) ────────────────────────────────
	async getMargenReal(filter: MargenFilter): Promise<BatchMargenSummary[]> {
		return await invoke<BatchMargenSummary[]>('cmd_get_margen_real', { filter });
	},

	async getBatchMargenBreakdown(importId: string): Promise<BatchMargenDetail> {
		return await invoke<BatchMargenDetail>('cmd_get_batch_margen_breakdown', { importId });
	},

	async getMargenPulso(): Promise<MargenPulso> {
		return await invoke<MargenPulso>('cmd_get_margen_pulso');
	},

	// ─── Importaciones R4 (Free Units) ─────────────────────────────────
	// Rust serializes with #[serde(rename_all = "camelCase")] · wire format already camelCase.
	async listFreeUnits(filter?: FreeUnitFilter): Promise<FreeUnit[]> {
		return await invoke<FreeUnit[]>('cmd_list_free_units', { filter: filter ?? null });
	},

	async assignFreeUnit(input: AssignFreeUnitInput): Promise<FreeUnit> {
		return await invoke<FreeUnit>('cmd_assign_free_unit', { input });
	},

	async unassignFreeUnit(freeUnitId: number): Promise<FreeUnit> {
		return await invoke<FreeUnit>('cmd_unassign_free_unit', { freeUnitId });
	},

	// ─── Finanzas (FIN-R1) ─────────────────────────────────────────────
	async computeProfitSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
		prevStart?: string,
		prevEnd?: string,
	): Promise<ProfitSnapshot> {
		return invoke<ProfitSnapshot>('cmd_compute_profit_snapshot', {
			periodStart,
			periodEnd,
			periodLabel,
			prevStart: prevStart ?? null,
			prevEnd: prevEnd ?? null,
		});
	},

	async getHomeSnapshot(
		periodStart: string,
		periodEnd: string,
		periodLabel: string,
		prevStart?: string,
		prevEnd?: string,
	): Promise<HomeSnapshot> {
		return invoke<HomeSnapshot>('cmd_get_home_snapshot', {
			periodStart,
			periodEnd,
			periodLabel,
			prevStart: prevStart ?? null,
			prevEnd: prevEnd ?? null,
		});
	},

	async createExpense(input: ExpenseInput): Promise<number> {
		return invoke<number>('cmd_create_expense', { input });
	},

	async listExpenses(filters: {
		periodStart?: string;
		periodEnd?: string;
		category?: string;
		paymentMethod?: string;
		limit?: number;
	} = {}): Promise<Expense[]> {
		return invoke<Expense[]>('cmd_list_expenses', filters);
	},

	async deleteExpense(expenseId: number): Promise<void> {
		return invoke<void>('cmd_delete_expense', { expenseId });
	},

	async updateExpense(expenseId: number, input: ExpenseInput): Promise<void> {
		return invoke<void>('cmd_update_expense', { expenseId, input });
	},

	async recentExpenses(limit?: number): Promise<RecentExpense[]> {
		return invoke<RecentExpense[]>('cmd_recent_expenses', { limit: limit ?? null });
	},

	async setCashBalance(balanceGtq: number, source: string, notes?: string): Promise<number> {
		return invoke<number>('cmd_set_cash_balance', {
			balanceGtq,
			source,
			notes: notes ?? null,
		});
	},
};

// =============================================================================
// Admin Web R7 (T1.4) — Tauri wrappers
// =============================================================================
// Free-standing object literal implementando AdminWebTauriCommands. NO se
// hace methods sobre tauriAdapter porque el set es disjunto (60+ commands
// de un dominio nuevo) y el plan dictó wrappers separados. La implementación
// Rust de cada command vive en src-tauri/src/lib.rs (T2.X+ — por ahora son
// stubs en lo que respecta a backend; las invocaciones existen pero el Rust
// devolverá UNHANDLED hasta que T3.1+ las registre).

import type { AdminWebTauriCommands } from './types';
import type {
	HomeKpis,
	SavedView,
	SitePage,
	SiteComponent,
	BrandingValue,
	CommunicationTemplate,
	Subscriber,
	Workflow,
	Review,
	Survey,
	AuditLogEntry,
	ScrapHistoryEntry,
	DeployHistoryEntry,
	ScheduledJob,
	BackupEntry,
	HealthSnapshot
} from '../data/admin-web';
import type { Jersey } from '../data/jersey-states';
import type { TagType, Tag, TagAssignmentValidation } from '../data/tags';
import type { StockOverride, MysteryOverride } from '../data/overrides';
import type { InboxEvent } from '../data/inbox-events';

export const adminWebTauri: AdminWebTauriCommands = {
	// === HOME ===
	get_admin_web_kpis: () => invoke<HomeKpis>('get_admin_web_kpis'),
	get_module_stats: (args) => invoke<Record<string, unknown>>('get_module_stats', args),

	// === INBOX EVENTS ===
	list_inbox_events: (args) => invoke<InboxEvent[]>('list_inbox_events', args),
	dismiss_event: (args) => invoke<void>('dismiss_event', args),
	resolve_event: (args) => invoke<void>('resolve_event', args),
	detect_events_now: () => invoke<{ events_created: number }>('detect_events_now'),

	// === VAULT — TAGS ===
	list_tag_types: () => invoke<TagType[]>('list_tag_types'),
	list_tags: (args) => invoke<Tag[]>('list_tags', args ?? {}),
	create_tag: (args) => invoke<Tag>('create_tag', args),
	update_tag: (args) => invoke<Tag>('update_tag', args),
	soft_delete_tag: (args) => invoke<void>('soft_delete_tag', args),
	list_jersey_tags: (args) => invoke<Tag[]>('list_jersey_tags', args),
	list_jerseys_by_tag: (args) => invoke<Jersey[]>('list_jerseys_by_tag', args),
	validate_tag_assignment: (args) =>
		invoke<TagAssignmentValidation>('validate_tag_assignment', args),
	assign_tag: (args) => invoke<void>('assign_tag', args),
	remove_tag: (args) => invoke<void>('remove_tag', args),

	// === VAULT — PUBLICADOS ===
	list_published: (args) => invoke<Jersey[]>('list_published', args),
	promote_to_stock: (args) => invoke<StockOverride>('promote_to_stock', args),
	promote_to_mystery: (args) => invoke<MysteryOverride>('promote_to_mystery', args),
	toggle_dirty_flag: (args) => invoke<void>('toggle_dirty_flag', args),
	archive_jersey: (args) => invoke<void>('archive_jersey', args),
	revive_archived: (args) => invoke<void>('revive_archived', args),

	// === VAULT — UNIVERSO ===
	list_universo: (args) => invoke('list_universo', args),
	bulk_action: (args) => invoke('bulk_action', args),

	// === SAVED VIEWS ===
	list_saved_views: (args) => invoke<SavedView[]>('list_saved_views', args),
	save_view: (args) => invoke<SavedView>('save_view', args),
	delete_view: (args) => invoke<void>('delete_view', args),

	// === STOCK ===
	list_stock_overrides: (args) => invoke<StockOverride[]>('list_stock_overrides', args ?? {}),
	create_stock_override: (args) => invoke<StockOverride>('create_stock_override', args),
	update_stock_override: (args) => invoke<StockOverride>('update_stock_override', args),
	delete_stock_override: (args) => invoke<void>('delete_stock_override', args),
	pause_stock_override: (args) => invoke<void>('pause_stock_override', args),
	list_stock_calendar: (args) => invoke<StockOverride[]>('list_stock_calendar', args),

	// === MYSTERY ===
	list_mystery_overrides: (args) =>
		invoke<MysteryOverride[]>('list_mystery_overrides', args ?? {}),
	create_mystery_override: (args) => invoke<MysteryOverride>('create_mystery_override', args),
	update_mystery_override: (args) => invoke<MysteryOverride>('update_mystery_override', args),
	delete_mystery_override: (args) => invoke<void>('delete_mystery_override', args),
	list_mystery_calendar: (args) => invoke<MysteryOverride[]>('list_mystery_calendar', args),
	get_mystery_rules: () => invoke<Record<string, unknown>>('get_mystery_rules'),
	update_mystery_rules: (args) => invoke<void>('update_mystery_rules', args),

	// === SITE — PAGES ===
	list_pages: (args) => invoke<SitePage[]>('list_pages', args ?? {}),
	get_page: (args) => invoke<SitePage>('get_page', args),
	create_page: (args) => invoke<SitePage>('create_page', args),
	update_page: (args) => invoke<SitePage>('update_page', args),
	delete_page: (args) => invoke<void>('delete_page', args),
	publish_page: (args) => invoke<void>('publish_page', args),

	// === SITE — COMPONENTS ===
	list_components: (args) => invoke<SiteComponent[]>('list_components', args ?? {}),
	update_component: (args) => invoke<SiteComponent>('update_component', args),
	toggle_component: (args) => invoke<void>('toggle_component', args),

	// === SITE — BRANDING ===
	list_branding: () => invoke<BrandingValue[]>('list_branding'),
	set_branding: (args) => invoke<void>('set_branding', args),
	apply_branding_changes: () =>
		invoke<{ deploy_triggered: boolean }>('apply_branding_changes'),

	// === SITE — COMMUNICATION ===
	list_templates: (args) => invoke<CommunicationTemplate[]>('list_templates', args ?? {}),
	create_template: (args) => invoke<CommunicationTemplate>('create_template', args),
	update_template: (args) => invoke<CommunicationTemplate>('update_template', args),
	list_subscribers: (args) => invoke<Subscriber[]>('list_subscribers', args ?? {}),
	list_workflows: () => invoke<Workflow[]>('list_workflows'),
	toggle_workflow: (args) => invoke<void>('toggle_workflow', args),

	// === SITE — COMMUNITY ===
	list_reviews: (args) => invoke<Review[]>('list_reviews', args ?? {}),
	moderate_review: (args) => invoke<void>('moderate_review', args),
	list_surveys: () => invoke<Survey[]>('list_surveys'),
	list_survey_responses: (args) =>
		invoke<{ id: number; answers: unknown; submitted_at: number }[]>(
			'list_survey_responses',
			args
		),

	// === SISTEMA ===
	get_health_snapshot: () => invoke<HealthSnapshot>('get_health_snapshot'),
	get_health_history: (args) => invoke<HealthSnapshot[]>('get_health_history', args),
	list_scrap_history: (args) => invoke<ScrapHistoryEntry[]>('list_scrap_history', args ?? {}),
	trigger_scrap: (args) => invoke<{ scrap_id: number }>('trigger_scrap', args),
	list_deploy_history: (args) =>
		invoke<DeployHistoryEntry[]>('list_deploy_history', args ?? {}),
	trigger_deploy: (args) => invoke<{ deploy_id: number }>('trigger_deploy', args),
	rollback_deploy: (args) => invoke<void>('rollback_deploy', args),
	list_jobs: () => invoke<ScheduledJob[]>('list_jobs'),
	toggle_job: (args) => invoke<void>('toggle_job', args),
	run_job_now: (args) => invoke<void>('run_job_now', args),
	list_backups: (args) => invoke<BackupEntry[]>('list_backups', args ?? {}),
	create_backup_now: (args) => invoke<BackupEntry>('create_backup_now', args),
	restore_from_backup: (args) => invoke<void>('restore_from_backup', args),
	stream_logs: (args) => invoke<string>('stream_logs', args),
	list_audit_log: (args) => invoke<AuditLogEntry[]>('list_audit_log', args),
	export_audit_log_csv: (args) =>
		invoke<{ file_path: string }>('export_audit_log_csv', args),
	get_admin_config: () =>
		invoke<Record<string, { value: string; value_type: string }>>('get_admin_config'),
	set_admin_config: (args) => invoke<void>('set_admin_config', args),
	list_api_connections: () =>
		invoke<
			{
				name: string;
				status: 'connected' | 'failing' | 'pending';
				last_test_at?: number;
				usage?: Record<string, unknown>;
			}[]
		>('list_api_connections'),
	test_api_connection: (args) =>
		invoke<{ success: boolean; message?: string }>('test_api_connection', args),
	rotate_secret: (args) => invoke<{ success: boolean }>('rotate_secret', args)
};
