// overhaul/src/lib/data/kpis.ts
import type { Period, PeriodRange, PulsoKPIs } from './comercial';

interface SaleForKPI {
  ref: string;
  totalGtq: number;
  paidAt: string;          // ISO
  status: string;
}

interface LeadForKPI {
  leadId: number;
  firstContactAt: string;
}

interface AdSpendForKPI {
  campaignId: string;
  spendGtq: number;
  capturedAt: string;
}

/**
 * Convierte un Period en un PeriodRange con start/end ISO.
 * "today" = desde 00:00 local hasta now.
 * "7d"/"30d" = N*24h hacia atrás desde now.
 * "custom" = no implementado, retorna 30d como fallback.
 */
export function resolvePeriod(period: Period, now: Date = new Date()): PeriodRange {
  const end = now.toISOString();
  let startDate: Date;

  switch (period) {
    case 'today':
      startDate = new Date(now);
      startDate.setHours(0, 0, 0, 0);
      break;
    case '7d':
      startDate = new Date(now.getTime() - 7 * 86400000);
      break;
    case '30d':
    case 'custom':
    default:
      startDate = new Date(now.getTime() - 30 * 86400000);
      break;
  }

  return { period, start: startDate.toISOString(), end };
}

/**
 * Computa KPIs del pulso bar para un período dado.
 * Comparación de trend vs período anterior de igual longitud.
 */
export function computePulsoKPIs(
  sales: SaleForKPI[],
  leads: LeadForKPI[],
  adSpend: AdSpendForKPI[],
  range: PeriodRange,
  prevSales: SaleForKPI[] = [],
  prevLeads: LeadForKPI[] = [],
  prevAdSpend: AdSpendForKPI[] = []
): PulsoKPIs {
  const inRange = (iso: string) => iso >= range.start && iso <= range.end;

  const periodSales = sales.filter((s) => inRange(s.paidAt));
  const revenue = periodSales.reduce((sum, s) => sum + s.totalGtq, 0);
  const orders = periodSales.length;
  const periodLeads = leads.length; // ya viene filtrado por el caller con range
  const totalAdSpend = adSpend.reduce((sum, a) => sum + a.spendGtq, 0);
  const conversionRate = periodLeads > 0 ? orders / periodLeads : 0;
  const roas = totalAdSpend > 0 ? revenue / totalAdSpend : 0;

  // Comparación de trend vs período anterior
  const prevRevenue = prevSales.reduce((sum, s) => sum + s.totalGtq, 0);
  const prevOrders = prevSales.length;
  const prevLeadsCount = prevLeads.length;
  const prevConvRate = prevLeadsCount > 0 ? prevOrders / prevLeadsCount : 0;

  const pct = (now: number, prev: number) => (prev === 0 ? 0 : ((now - prev) / prev) * 100);

  return {
    revenue,
    orders,
    leads: periodLeads,
    conversionRate,
    adSpend: totalAdSpend,
    roas,
    trends: {
      revenue: pct(revenue, prevRevenue),
      orders: pct(orders, prevOrders),
      leads: pct(periodLeads, prevLeadsCount),
      conversionRate: pct(conversionRate, prevConvRate)
    }
  };
}
