// overhaul/src/lib/data/funnelKpis.ts
import type {
  FunnelKPIs,
  Lead,
  ConversationMeta,
  Customer,
  PeriodRange,
} from './comercial';

interface SaleForFunnel {
  ref: string;
  totalGtq: number;
  paidAt: string;          // ISO; sales.occurred_at as paidAt
  status: string;          // fulfillment_status
}

interface AdSpendForFunnel {
  campaignId: string;
  spendGtq: number;
  capturedAt: string;
  impressions?: number;
  clicks?: number;
}

const inRange = (iso: string, range: PeriodRange) =>
  iso >= range.start && iso <= range.end;

/**
 * Computa todos los KPIs del Funnel para un range dado.
 * Las sub-métricas siguen las definiciones del spec sec 5.5.
 *
 * Notas:
 * - Awareness viene de adSpend (vacío en R2-combo; R5 lo populiza).
 * - Retention.vipInactive60d retorna 0 hasta R4 (no hay VIP detection automática).
 * - Conversion rates se calculan best-effort sobre el período actual.
 */
export function computeFunnelKPIs(
  range: PeriodRange,
  leads: Lead[],
  conversations: ConversationMeta[],
  sales: SaleForFunnel[],
  customers: Customer[],
  adSpend: AdSpendForFunnel[]
): FunnelKPIs {
  // === Awareness ===
  const periodAdSpend = adSpend.filter((a) => inRange(a.capturedAt, range));
  const impressions = periodAdSpend.reduce((s, a) => s + (a.impressions ?? 0), 0);
  const clicks = periodAdSpend.reduce((s, a) => s + (a.clicks ?? 0), 0);
  const spendGtq = periodAdSpend.reduce((s, a) => s + a.spendGtq, 0);
  const ctr = impressions > 0 ? clicks / impressions : 0;

  // === Interest (leads) ===
  const periodLeads = leads.filter((l) => inRange(l.firstContactAt, range));
  const byPlatform = { wa: 0, ig: 0, messenger: 0, web: 0 };
  for (const l of periodLeads) {
    if (l.platform in byPlatform) {
      (byPlatform as Record<string, number>)[l.platform]++;
    }
  }
  const totalLeads = periodLeads.length;

  // === Consideration (conversations) ===
  const periodConvs = conversations.filter((c) => inRange(c.startedAt, range));
  const activeConversations = periodConvs.filter((c) => !c.outcome).length;
  const pending = periodConvs.filter((c) => c.outcome === 'pending').length;
  const objection = periodConvs.filter((c) => c.outcome === 'objection').length;

  // === Sale ===
  const periodSales = sales.filter((s) => inRange(s.paidAt, range));
  const ordersToday = periodSales.length;
  const awaitingPayment = periodSales.filter((s) => s.status === 'pending_payment').length;
  const awaitingShipment = periodSales.filter(
    (s) => s.status === 'paid' || s.status === 'awaiting_shipment'
  ).length;

  // === Retention ===
  const totalCustomers = customers.length;
  const repeatCustomers = customers.filter((c) => c.totalOrders > 1).length;
  const repeatRate = totalCustomers > 0 ? repeatCustomers / totalCustomers : 0;
  const vipInactive60d = 0; // R4 populará
  const ltvAvgGtq =
    totalCustomers > 0
      ? customers.reduce((s, c) => s + c.totalRevenueGtq, 0) / totalCustomers
      : 0;

  // === Conversion rates ===
  const awarenessToInterest = clicks > 0 ? totalLeads / clicks : 0;
  const interestToConsideration = totalLeads > 0 ? activeConversations / totalLeads : 0;
  const considerationToSale =
    periodConvs.length > 0
      ? periodConvs.filter((c) => c.outcome === 'sale').length / periodConvs.length
      : 0;
  const saleToRetention = ordersToday > 0 ? repeatCustomers / ordersToday : 0;

  return {
    awareness: { impressions, clicks, spendGtq, ctr },
    interest: { totalLeads, byPlatform },
    consideration: { activeConversations, pending, objection },
    sale: { ordersToday, awaitingPayment, awaitingShipment },
    retention: { totalCustomers, repeatRate, vipInactive60d, ltvAvgGtq },
    conversion: {
      awarenessToInterest,
      interestToConsideration,
      considerationToSale,
      saleToRetention,
    },
  };
}
