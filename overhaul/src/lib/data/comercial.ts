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
