// Admin Web R7 (T1.3) — JerseyState lifecycle + Jersey shape canonical.
// Spec: overhaul/docs/superpowers/specs/admin-web/types.ts (sección JERSEY STATES).

export type JerseyState =
	| 'DRAFT' // Pre-pipeline. Catalog OK pero sin audit_decisions o con scrap_fail.
	| 'QUEUE' // audit_decisions.status='pending'. Tab Queue.
	| 'PUBLISHED' // catalog.published=true. Live en vault.elclub.club.
	| 'REJECTED' // audit_decisions.status='deleted'. Soft delete.
	| 'ARCHIVED'; // Fue PUBLISHED, ya no. Puede revivir.

/** Transiciones legales entre estados */
export const VALID_TRANSITIONS: Record<JerseyState, JerseyState[]> = {
	DRAFT: ['QUEUE', 'REJECTED'],
	QUEUE: ['PUBLISHED', 'REJECTED'],
	PUBLISHED: ['ARCHIVED'],
	REJECTED: ['QUEUE'], // raro pero legal
	ARCHIVED: ['PUBLISHED'] // revivir
};

export function canTransition(from: JerseyState, to: JerseyState): boolean {
	return VALID_TRANSITIONS[from]?.includes(to) ?? false;
}

/** Flags ortogonales sobre el jersey */
export interface JerseyFlags {
	dirty: boolean; // PUBLISHED necesita revisión (foto rota, CDN stale)
	dirty_reason?: string; // ej. "foto rota detectada", "CDN cache stale"
	scrap_fail: boolean; // DRAFT con datos incompletos
	low_coverage: boolean; // gallery.length < 3
	supplier_gap: boolean; // proveedor no lo maneja (L12 del playbook)
	qa_priority: 0 | 1; // whitelist priorización
	in_vault: boolean; // aparece en vault.elclub.club (default true para PUBLISHED)
}

export interface Jersey {
	family_id: string;
	sku: string;
	team: string;
	season: string;
	variant: 'L' | 'V' | 'T' | 'E' | 'G'; // Local, Visita, Third, Special, Goalkeeper
	state: JerseyState;
	flags: JerseyFlags;
	hero_thumbnail: string | null;
	gallery: string[];
	modelos: JerseyModelo[];
	meta_country?: string;
	meta_league?: string;
	meta_confederation?: string;
	archived_at?: number; // unix timestamp si ARCHIVED
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
