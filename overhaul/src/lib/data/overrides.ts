// Admin Web R7 (T1.3) — Stock + Mystery overrides sobre catalog.json.
// Spec: overhaul/docs/superpowers/specs/admin-web/types.ts (sección OVERRIDES).
// Schema: stock_overrides, mystery_overrides (admin_web schema migration T1.1).
// computed_status viene de las views v_stock_status / v_mystery_status.

export type OverrideStatus = 'draft' | 'scheduled' | 'live' | 'ended' | 'paused';

export interface StockOverride {
	id: number;
	family_id: string;
	publish_at: number | null;
	unpublish_at: number | null;
	price_override: number | null; // en centavos GTQ (47500 = Q475)
	badge: string | null;
	copy_override: string | null;
	priority: number; // 1-10
	status: OverrideStatus;
	computed_status: OverrideStatus; // calculado por SQL view en runtime
	created_at: number;
	updated_at: number;
	created_by: string;
}

export interface MysteryOverride {
	id: number;
	family_id: string;
	publish_at: number | null;
	unpublish_at: number | null;
	pool_weight: number; // multiplicador en algoritmo (default 1.0)
	status: OverrideStatus;
	computed_status: OverrideStatus;
	created_at: number;
	updated_at: number;
	created_by: string;
}
