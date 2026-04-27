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
import { NotAvailableInBrowser } from './types';
import type { Family } from '../data/types';
import type { Campaign, CampaignDetail, FunnelAwarenessReal, MetaSyncResult } from '../data/comercial';
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
};

// Test helper (también útil si queremos invalidar cache en dev)
export function _invalidateBrowserCaches() {
	catalogCache = null;
	decisionsCache = null;
	decisionsByFamily = null;
}
