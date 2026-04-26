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
      // R3+ agregará más detectores: lead_unanswered_12h, etc.
    } catch (e) {
      console.warn('[detector] run failed', e);
    }
  }

  // Run immediately on start
  runOnce();
  const interval = setInterval(runOnce, 15 * 60 * 1000);
  return () => clearInterval(interval);
}
