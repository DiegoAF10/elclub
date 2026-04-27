// Comercial — types core compartidos por todos los componentes del modo.

export type EventSeverity = 'crit' | 'warn' | 'info' | 'strat';

export type EventType =
  | 'order_pending_24h'      // crit
  | 'order_new'              // info
  | 'campaign_drop_30'       // crit (R5)
  | 'lead_unanswered_12h'    // warn (R3)
  | 'stock_low'              // warn
  | 'leads_daily_summary'    // info
  | 'vip_inactive_60d'       // strat (R4)
  | 'campaign_perf_drop'     // warn (R5)
  | 'monthly_goal_progress'; // strat

export type EventStatus = 'active' | 'resolved' | 'ignored';

export interface ComercialEvent {
  eventId: number;
  type: EventType;
  severity: EventSeverity;
  title: string;
  sub: string | null;
  itemsAffected: ItemAffected[];
  detectedAt: string;       // ISO timestamp
  status: EventStatus;
  resolvedAt: string | null;
  pushSent: boolean;
}

export interface ItemAffected {
  type: 'order' | 'lead' | 'customer' | 'campaign';
  id: string;               // sale ref, lead_id, customer_id, campaign_id
  hint?: string;            // info breve para mostrar
}

export type ComercialTab = 'funnel' | 'customers' | 'inbox' | 'ads' | 'settings';

export interface DetectedEvent {
  type: string;
  severity: 'crit' | 'warn' | 'info' | 'strat';
  title: string;
  sub: string | null;
  itemsAffected: Array<{ type: string; id: string; hint?: string }>;
}

export type Period = 'today' | '7d' | '30d' | 'custom';

export interface PeriodRange {
  period: Period;
  start: string;            // ISO
  end: string;              // ISO
}

export interface PulsoKPIs {
  revenue: number;          // GTQ
  orders: number;
  leads: number;
  conversionRate: number;   // 0-1
  adSpend: number;          // GTQ
  roas: number;             // revenue / adSpend
  trends: {
    revenue: number;        // % vs período anterior
    orders: number;
    leads: number;
    conversionRate: number;
  };
}

export interface OrderForModal {
  ref: string;              // CE-XXXX
  saleId: number;
  status: 'paid' | 'shipped' | 'delivered' | 'refunded' | 'cancelled';
  paidAt: string | null;
  shippedAt: string | null;
  totalGtq: number;
  customer: {
    name: string;
    phone: string | null;
    handle: string | null;
    platform: 'wa' | 'ig' | 'messenger' | 'web';
  };
  items: OrderItem[];
  paymentMethod: 'recurrente' | 'transfer' | 'cod';
  notes: string | null;
}

export interface OrderItem {
  familyId: string;
  jerseySku: string | null;
  size: string;
  unitPriceGtq: number;
  unitCostGtq: number | null;
  personalizationJson: string | null;
}

// ─── R2-combo: ManyChat sync + Funnel ──────────────────────────────

export interface Lead {
  leadId: number;
  name: string | null;
  handle: string | null;
  phone: string | null;
  platform: 'wa' | 'ig' | 'messenger' | 'web';
  senderId: string;
  sourceCampaignId: string | null;
  firstContactAt: string;
  lastActivityAt: string;
  status: 'new' | 'qualified' | 'converted' | 'lost';
  traitsJson: Record<string, unknown>;
}

export interface ConversationMeta {
  convId: string;
  leadId: number | null;
  brand: string;
  platform: 'wa' | 'ig' | 'messenger' | 'web';
  senderId: string;
  startedAt: string;
  endedAt: string;
  outcome: 'sale' | 'no_sale' | 'objection' | 'pending' | null;
  orderId: string | null;
  messagesTotal: number;
  tagsJson: string[];
  analyzed: boolean;
  syncedAt: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;       // ISO, may be approximate
}

export interface Customer {
  customerId: number;
  name: string;
  phone: string | null;
  email: string | null;
  source: string | null;
  firstOrderAt: string;
  totalOrders: number;
  totalRevenueGtq: number;   // computed in query, not stored
  lastOrderAt: string | null;
}

export interface FunnelKPIs {
  awareness: { impressions: number; clicks: number; spendGtq: number; ctr: number };
  interest: {
    totalLeads: number;
    byPlatform: { wa: number; ig: number; messenger: number; web: number };
  };
  consideration: { activeConversations: number; pending: number; objection: number };
  sale: { ordersToday: number; awaitingPayment: number; awaitingShipment: number };
  retention: {
    totalCustomers: number;
    repeatRate: number;        // 0-1
    vipInactive60d: number;    // R4 will populate; R2-combo returns 0
    ltvAvgGtq: number;
  };
  conversion: {
    awarenessToInterest: number;     // 0-1
    interestToConsideration: number;
    considerationToSale: number;
    saleToRetention: number;
  };
}

export interface MetaSyncStatus {
  source: string;
  lastSyncAt: string | null;
  lastStatus: 'ok' | 'error' | null;
  lastError: string | null;
}

// ─── R4: Customers + Atribución ────────────────────────────────────

export interface CustomerProfile {
  // Base customer fields (from Customer type, but with R4 additions)
  customerId: number;
  name: string;
  phone: string | null;
  email: string | null;
  source: string | null;
  firstOrderAt: string | null;
  totalOrders: number;
  totalRevenueGtq: number;
  lastOrderAt: string | null;
  // R4 additions
  isVip: boolean;                        // derived: totalRevenueGtq >= 1500
  daysInactive: number | null;           // null if never ordered; computed from lastOrderAt
  blocked: boolean;
  traitsJson: Record<string, unknown>;
  attribution: {
    customerSource: string | null;
    leadCampaigns: string[];             // unique source_campaign_id from joined leads (by phone)
  };
  timeline: TimelineEntry[];
}

export type TimelineEntry =
  | { kind: 'order'; ref: string; totalGtq: number; status: string; occurredAt: string; itemsCount: number }
  | { kind: 'conversation'; convId: string; platform: string; outcome: string | null; messagesTotal: number; endedAt: string };

export interface CreateCustomerArgs {
  name: string;
  phone?: string | null;
  email?: string | null;
  source?: string | null;
}

export interface CreateOrderArgs {
  customerId: number;
  items: CreateOrderItem[];
  paymentMethod: 'recurrente' | 'transferencia' | 'contra_entrega' | 'efectivo' | 'otro';
  fulfillmentStatus: 'pending' | 'sent_to_supplier' | 'in_production' | 'shipped' | 'delivered' | 'cancelled';
  shippingFee?: number;        // default 0
  discount?: number;           // default 0
  notes?: string;
}

export interface CreateOrderItem {
  familyId: string;
  jerseyId: string;
  team: string;
  size: string;
  variantLabel?: string | null;
  version?: string | null;
  personalizationJson?: string | null;
  unitPrice: number;
  unitCost?: number | null;
  itemType?: string | null;
}

// ─── R5: Ads + Performance ────────────────────────────────────

export interface Campaign {
  campaignId: string;
  campaignName: string | null;
  lastSyncAt: string | null;
  totalSpendGtq: number;
  totalImpressions: number;
  totalClicks: number;
  totalConversions: number;
  totalRevenueGtq: number;
  costPerConversionGtq: number | null;
  status: 'active' | 'paused' | 'archived' | 'unknown';
}

export interface CampaignSnapshot {
  snapshotId: number;
  campaignId: string;
  capturedAt: string;
  impressions: number;
  clicks: number;
  spendGtq: number;
  conversions: number;
  revenueAttributedGtq: number;
}

export interface CampaignTimePoint {
  date: string;
  spendGtq: number;
  conversions: number;
  revenueGtq: number;
  impressions: number;
  clicks: number;
}

export interface CampaignDetail {
  campaign: Campaign;
  daily: CampaignTimePoint[];
  attributedSales: Array<{
    saleId: number;
    ref: string;
    customerName: string | null;
    totalGtq: number;
    occurredAt: string;
  }>;
}

export interface FunnelAwarenessReal {
  periodStart: string;
  periodEnd: string;
  totalCampaigns: number;
  impressions: number;
  clicks: number;
  spendGtq: number;
  conversions: number;
  revenueAttributedGtq: number;
  cpm: number | null;
  cpc: number | null;
  ctr: number | null;
  byCampaign: Array<{ campaignId: string; campaignName: string | null; spendGtq: number; impressions: number }>;
  lastSyncAt: string | null;
}

export interface MetaSyncResult {
  ok: boolean;
  campaignsSynced: number;
  errors: string[];
  syncedAt: string;
}

// ─── R6: Sales Attribution ─────────────────────────────────────

export interface SaleAttribution {
  id: number;
  saleId: number;
  adCampaignId: string | null;
  adCampaignName: string | null;
  source: string | null;
  note: string | null;
  createdAt: string;
}

export interface BackfillAttributionResult {
  ok: boolean;
  inserted: number;
  skippedNoMatch: number;
  skippedAlreadyAttributed: number;
  errors: string[];
}
