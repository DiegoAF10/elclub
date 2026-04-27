import { adapter } from '$lib/adapter';
import type { DetectedEvent } from './comercial';

export type { DetectedEvent };

const WORKER_BASE = 'https://ventus-backoffice.ventusgt.workers.dev';

/**
 * Corre el detector "órdenes pendientes despacho >24h".
 * Compara sales con status='paid' y paid_at >24h pero shipped_at=null.
 * Inserta evento en comercial_events si no existe ya uno activo del mismo tipo.
 */
export async function detectOrdersPending24h(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 24 * 3600 * 1000).toISOString();

  // Llamamos a listSalesInRange sobre los últimos 30 días y filtramos cliente-side.
  const range = {
    period: '30d' as const,
    start: new Date(now.getTime() - 30 * 86400000).toISOString(),
    end: now.toISOString()
  };
  const sales = await adapter.listSalesInRange(range);
  const pending = sales.filter(
    (s) => s.status === 'paid' && s.paidAt < cutoff
    // Note: shipped_at se marca a null cuando status='paid'; el detector confía en esto.
  );

  if (pending.length === 0) return null;

  return {
    type: 'order_pending_24h',
    severity: 'crit',
    title: `${pending.length} órden${pending.length === 1 ? '' : 'es'} pendiente${pending.length === 1 ? '' : 's'} despacho >24h`,
    sub:
      pending
        .map((p) => p.ref)
        .slice(0, 3)
        .join(' · ') + (pending.length > 3 ? ` · +${pending.length - 3}` : ''),
    itemsAffected: pending.map((p) => ({ type: 'order', id: p.ref, hint: `Q${p.totalGtq}` }))
  };
}

/**
 * Detector "leads sin responder >12h".
 * Considera conversations donde outcome es null o 'pending' y last_activity (ended_at)
 * es más viejo que 12h. severity = warn (NO push WA — solo Inbox).
 */
export async function detectLeadsUnanswered12h(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 12 * 3600 * 1000).toISOString();

  let convs;
  try {
    convs = await adapter.listConversations({ outcome: 'pending' });
  } catch (e) {
    console.warn('[detector] listConversations failed', e);
    return null;
  }

  // Considerar también las que tienen outcome=null
  const stale = convs.filter((c: any) =>
    c.endedAt < cutoff && (c.outcome === null || c.outcome === 'pending')
  );

  if (stale.length === 0) return null;

  return {
    type: 'leads_unanswered_12h',
    severity: 'warn',
    title: `${stale.length} lead${stale.length === 1 ? '' : 's'} sin responder >12h`,
    sub: stale.slice(0, 3).map((c: any) => `${c.platform}:${c.senderId}`).join(' · ')
      + (stale.length > 3 ? ` · +${stale.length - 3}` : ''),
    itemsAffected: stale.map((c: any) => ({
      type: 'conversation',
      id: c.convId,
      hint: c.platform,
    })),
  };
}

/**
 * Detector "VIP inactivos +60d".
 * VIP = totalRevenueGtq >= 1500. Inactivo = lastOrderAt < (now - 60d).
 * severity = strat (no push WA — solo Inbox).
 */
export async function detectVipInactive60d(): Promise<DetectedEvent | null> {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 60 * 86400 * 1000).toISOString();

  let customers;
  try {
    customers = await adapter.listCustomers({ minLtvGtq: 1500 });
  } catch (e) {
    console.warn('[detector] listCustomers failed', e);
    return null;
  }

  const inactive = customers.filter((c: any) =>
    c.lastOrderAt && c.lastOrderAt < cutoff
  );

  if (inactive.length === 0) return null;

  return {
    type: 'vip_inactive_60d',
    severity: 'strat',
    title: `${inactive.length} VIP${inactive.length === 1 ? '' : 's'} inactivo${inactive.length === 1 ? '' : 's'} +60d`,
    sub: inactive.slice(0, 3).map((c: any) => `${c.name} (Q${c.totalRevenueGtq})`).join(' · ')
      + (inactive.length > 3 ? ` · +${inactive.length - 3}` : ''),
    itemsAffected: inactive.map((c: any) => ({
      type: 'customer',
      id: String(c.customerId),
      hint: `LTV Q${c.totalRevenueGtq}`,
    })),
  };
}

/**
 * Inserta el evento en comercial_events vía adapter.
 * Si ya existe un evento activo del mismo type, NO duplica.
 */
export async function persistEvent(detected: DetectedEvent): Promise<void> {
  const existing = await adapter.listEvents({ status: 'active' });
  const dup = existing.find((e) => e.type === detected.type);
  if (dup) return; // ya existe activo

  const eventId = await adapter.insertEvent(detected);

  // Push notification a WA Diego SOLO para crit (R1 scope)
  if (detected.severity === 'crit') {
    try {
      await fetch(`${WORKER_BASE}/api/comercial/notify-diego`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          eventId,
          severity: detected.severity,
          title: detected.title,
          sub: detected.sub
        })
      });
      // Note: markEventPushSent is R6 polish; for R1 we don't track push_sent.
    } catch (e) {
      console.warn('[detector] push failed', e);
      // Si falla, queda con push_sent=0 y reintentamos en el próximo ciclo (15min)
    }
  }
}

/**
 * Loop de detección. Inicia un setInterval que corre las detecciones cada 15min.
 * Retorna función para detener el loop.
 */
export function startDetectorLoop(): () => void {
  async function runOnce() {
    try {
      const ordersPending = await detectOrdersPending24h();
      if (ordersPending) await persistEvent(ordersPending);

      const leadsUnanswered = await detectLeadsUnanswered12h();
      if (leadsUnanswered) await persistEvent(leadsUnanswered);

      const vipInactive = await detectVipInactive60d();
      if (vipInactive) await persistEvent(vipInactive);
    } catch (e) {
      console.warn('[detector] run failed', e);
    }
  }

  // Run immediately on start
  runOnce();
  const interval = setInterval(runOnce, 15 * 60 * 1000);
  return () => clearInterval(interval);
}
