// Importaciones — types para el módulo IMP (batches de jerseys desde proveedor).
// Convention: snake_case fields mirror SQL column names exactly (serde default).
// This differs from comercial.ts which uses camelCase for runtime-computed shapes.

export type ImportStatus = 'draft' | 'paid' | 'in_transit' | 'arrived' | 'closed' | 'cancelled';

export interface Import {
  import_id: string;            // 'IMP-2026-04-07'
  paid_at: string | null;       // ISO date
  arrived_at: string | null;
  supplier: string;             // 'Bond Soccer Jersey'
  bruto_usd: number | null;
  shipping_gtq: number | null;
  fx: number;                   // default 7.73 (D-FX), legacy 7.70
  total_landed_gtq: number | null;
  n_units: number | null;
  unit_cost: number | null;     // GTQ post-prorrateo
  status: ImportStatus;
  notes: string | null;
  created_at: string;
  // R1 additions
  tracking_code: string | null;
  carrier: string;              // default 'DHL'
  lead_time_days: number | null;
}

export interface ImportItem {
  // Linkeable a sale_items, jerseys (legacy R1) o import_items (single-source post-R6).
  source_table: 'sale_items' | 'jerseys' | 'import_items';
  source_id: number;
  import_id: string;
  family_id: string | null;
  jersey_id: string | null;
  size: string | null;
  player_name: string | null;
  player_number: number | null;
  patch: string | null;
  version: string | null;
  unit_cost_usd: number | null;     // USD del chino (de chat WA `11+2=13`)
  unit_cost: number | null;         // GTQ post-prorrateo
  customer_id: string | null;       // null = stock futuro
  customer_name: string | null;     // joined
  is_free_unit: boolean;
  // Supplier WA mini-feature (v0.4.6) · only populated for source_table='import_items'.
  sent_to_supplier_at: string | null;       // ISO 8601 localtime · NULL = no enviado
  sent_to_supplier_via: 'china' | 'hk' | null;
}

export interface SupplierMessage {
  item_id: number;
  text: string;            // multi-line formatted message (Name/Number/Size/Patch/Version)
  hero_url: string;        // R2 hero JPG URL (img.elclub.club/families/{family_id}/01.jpg)
  wa_china_url: string;    // wa.me/...?text=... pre-encoded
  wa_hk_url: string;
}

export interface ImportPulso {
  capital_amarrado_gtq: number;     // sum total_landed_gtq de batches paid + in_transit + arrived
  closed_ytd_landed_gtq: number;    // sum total_landed_gtq de batches closed YTD
  avg_landed_unit: number | null;   // avg unit_cost de batches closed
  lead_time_avg_days: number | null;// avg (arrived_at - paid_at) de batches closed
  wishlist_count: number;
  free_units_unassigned: number;
}

export interface CloseImportResult {
  ok: boolean;
  n_items_updated: number;
  n_jerseys_updated: number;
  total_landed_gtq: number;
  avg_unit_cost: number;
  method: string;
}

export interface ImportFilter {
  status?: ImportStatus | 'pipeline' | 'all';   // 'pipeline' = paid+in_transit+arrived
  supplier?: string;
  search?: string;
}

export const STATUS_LABELS: Record<ImportStatus, string> = {
  draft:      'DRAFT',
  paid:       'PAID',
  in_transit: 'TRANSIT',
  arrived:    'ARRIVED',
  closed:     'CLOSED',
  cancelled:  'CANCELLED',
};

export const STATUS_PROGRESS: Record<ImportStatus, number | null> = {
  draft:      1,
  paid:       2,
  in_transit: 3,
  arrived:    4,
  closed:     5,
  cancelled:  null,  // off-ramp — render as cancelled badge, not as step-0 progress
};
