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
	DeleteFamilyResult,
	DeleteSkuResult,
	EditModeloTypeResult,
	GitStatusInfo,
	ListFilter,
	MoveModeloArgs,
	MoveModeloResult,
	PhotoAction,
	RemovePhotosResult,
	SetFamilyVariantResult,
	WatermarkArgs,
	WatermarkResult
} from './types';
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
