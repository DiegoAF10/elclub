// el-club/backoffice/src/vault.js
/**
 * Vault lead management — dual-axis state machine + CRUD + coupon gating.
 *
 * State model:
 *   - payment_status: pending | paid | waived_ff | cod_completed | refunded_credit | cancelled
 *   - fulfillment_status: awaiting_import | arrived | shipped_cod | delivered | no_show | import_failed
 *
 * See: docs/superpowers/specs/2026-04-24-vault-q100-reservation-flow-design.md §3
 */

import { createReservationCheckout } from './vault-payment.js';

export const PAYMENT_TRANSITIONS = {
  pending:         ['paid', 'refunded_credit', 'cancelled'],
  paid:            ['cod_completed', 'refunded_credit'],
  waived_ff:       ['cod_completed', 'cancelled'],
  cod_completed:   [],
  refunded_credit: [],
  cancelled:       [],
};

export const FULFILLMENT_TRANSITIONS = {
  awaiting_import: ['arrived', 'import_failed'],
  arrived:         ['shipped_cod'],
  shipped_cod:     ['delivered', 'no_show'],
  delivered:       [],
  no_show:         [],
  import_failed:   [],
};

export const ALL_PAYMENT_STATUSES     = Object.keys(PAYMENT_TRANSITIONS);
export const ALL_FULFILLMENT_STATUSES = Object.keys(FULFILLMENT_TRANSITIONS);

/**
 * Validate a proposed state transition.
 *
 * @param {string} current   - current state
 * @param {string} target    - desired next state
 * @param {'payment'|'fulfillment'} axis
 * @returns {{ valid: boolean, allowed_next: string[], error?: string }}
 */
export function validateTransition(current, target, axis) {
  const table = axis === 'payment' ? PAYMENT_TRANSITIONS
              : axis === 'fulfillment' ? FULFILLMENT_TRANSITIONS
              : null;

  if (!table) {
    return { valid: false, allowed_next: [], error: `axis invalido: ${axis}` };
  }

  if (!(current in table)) {
    return { valid: false, allowed_next: [], error: `estado actual invalido: ${current}` };
  }

  const allowed = table[current];
  if (!allowed.includes(target)) {
    return { valid: false, allowed_next: allowed, error: `transicion invalida ${current} → ${target}` };
  }

  return { valid: true, allowed_next: allowed };
}

// ── Storage ──────────────────────────────────────────────────

export const INDEX_KEY = 'vault_lead_index';
export const INDEX_MAX = 500;
export const HISTORY_MAX = 50;

function nonEmpty(v) { return typeof v === 'string' && v.trim().length > 0; }

/**
 * Insert a new lead into KV.
 * Writes both the full record (vault_lead:{ts}:{telefono}) and updates the index.
 *
 * @returns {Promise<{ leadKey: string, indexEntry: object }>}
 */
export async function saveLead(env, lead) {
  const leadKey = `vault_lead:${lead.timestamp}:${lead.cliente.telefono}`;
  await env.DATA.put(leadKey, JSON.stringify(lead));

  const indexEntry = {
    ref: lead.ref,
    key: leadKey,
    timestamp: lead.timestamp,
    saved_at: lead.saved_at,
    nombre: lead.cliente.nombre,
    telefono: lead.cliente.telefono,
    total: lead.total,
    total_cod: lead.total_cod,
    payment_status: lead.payment_status,
    fulfillment_status: lead.fulfillment_status,
    coupon_code: lead.coupon_code || null,
    has_coupon: !!lead.coupon_code,
  };

  const existing = (await env.DATA.get(INDEX_KEY, { type: 'json' })) || [];
  const updated = [indexEntry, ...existing].slice(0, INDEX_MAX);
  await env.DATA.put(INDEX_KEY, JSON.stringify(updated));

  return { leadKey, indexEntry };
}

/**
 * Find a lead by its ref by scanning the index, then loading the full record.
 *
 * @returns {Promise<{ entry: object, record: object } | null>}
 */
export async function findLeadByRef(env, ref) {
  const index = (await env.DATA.get(INDEX_KEY, { type: 'json' })) || [];
  const entry = index.find(e => e.ref === ref);
  if (!entry) return null;
  const record = await env.DATA.get(entry.key, { type: 'json' });
  if (!record) return null;
  return { entry, record };
}

/**
 * Update one axis of a lead's state. Does NOT validate the transition — caller must.
 * Updates the full lead record, the index entry, and the history list.
 *
 * @param {'payment'|'fulfillment'} axis
 */
export async function updateLeadStatus(env, ref, axis, newStatus, note) {
  const found = await findLeadByRef(env, ref);
  if (!found) throw new Error(`lead ${ref} no existe`);

  const field = axis === 'payment' ? 'payment_status' : 'fulfillment_status';
  const from = found.record[field];

  const updated = {
    ...found.record,
    [field]: newStatus,
    last_status_change: new Date().toISOString(),
  };
  await env.DATA.put(found.entry.key, JSON.stringify(updated));

  // Update index entry in-place
  const index = (await env.DATA.get(INDEX_KEY, { type: 'json' })) || [];
  const newIndex = index.map(e => e.ref === ref ? { ...e, [field]: newStatus } : e);
  await env.DATA.put(INDEX_KEY, JSON.stringify(newIndex));

  await appendStatusHistory(env, ref, from, newStatus, axis, note);

  return { from, to: newStatus, axis };
}

export async function appendStatusHistory(env, ref, from, to, axis, note) {
  const key = `vault_lead_status:${ref}`;
  const existing = (await env.DATA.get(key, { type: 'json' })) || [];
  const entry = {
    axis,
    from,
    to,
    at: new Date().toISOString(),
    note: nonEmpty(note) ? note.trim().slice(0, 500) : null,
  };
  const updated = [entry, ...existing].slice(0, HISTORY_MAX);
  await env.DATA.put(key, JSON.stringify(updated));
}

/**
 * List leads from the index with optional filters.
 *
 * @param {object} options
 * @param {number} [options.limit=50]
 * @param {string[]|null} [options.paymentStatuses]      CSV filter (OR-join). If null, excludes 'pending' and 'cancelled' by default.
 * @param {string[]|null} [options.fulfillmentStatuses]  CSV filter (OR-join).
 * @param {boolean|null}  [options.hasCoupon]            true|false filter; null = no filter.
 * @returns {Promise<object[]>}  light index entries (not full records)
 */
export async function listLeads(env, { limit = 50, paymentStatuses = null, fulfillmentStatuses = null, hasCoupon = null } = {}) {
  const index = (await env.DATA.get(INDEX_KEY, { type: 'json' })) || [];
  let filtered = index;

  if (paymentStatuses && paymentStatuses.length > 0) {
    filtered = filtered.filter(e => paymentStatuses.includes(e.payment_status));
  } else {
    // Default: hide huerfanos 'pending' and terminales 'cancelled'
    filtered = filtered.filter(e => e.payment_status !== 'pending' && e.payment_status !== 'cancelled');
  }

  if (fulfillmentStatuses && fulfillmentStatuses.length > 0) {
    filtered = filtered.filter(e => fulfillmentStatuses.includes(e.fulfillment_status));
  }

  if (hasCoupon === true)  filtered = filtered.filter(e => e.has_coupon);
  if (hasCoupon === false) filtered = filtered.filter(e => !e.has_coupon);

  return filtered.slice(0, limit);
}

/**
 * Fetch a lead + its full history list in one shot.
 *
 * @returns {Promise<{ lead: object, history: object[] } | null>}
 */
export async function getLeadWithHistory(env, ref) {
  const found = await findLeadByRef(env, ref);
  if (!found) return null;
  const history = (await env.DATA.get(`vault_lead_status:${ref}`, { type: 'json' })) || [];
  return { lead: found.record, history };
}

// ── Validation ───────────────────────────────────────────────

function validPhone(p) { return typeof p === 'string' && /^\d{8}$/.test(p.trim()); }

/**
 * Validate a reservation payload. Returns array of error messages (empty = valid).
 *
 * @param {object} body  - request body
 * @returns {string[]}   - empty if valid
 */
export function validateReservationPayload(body) {
  const errors = [];
  if (!body) { errors.push('body vacio'); return errors; }

  const cliente = body?.cliente || {};
  if (!nonEmpty(cliente.nombre))           errors.push('cliente.nombre requerido');
  if (!validPhone(cliente.telefono))       errors.push('cliente.telefono debe tener 8 digitos');

  const envio = body?.envio || {};
  if (!nonEmpty(envio.modalidad))          errors.push('envio.modalidad requerido');
  if (envio.modalidad && !['entrega','retiro'].includes(envio.modalidad)) {
    errors.push('envio.modalidad debe ser entrega|retiro');
  }
  if (!nonEmpty(envio.depto))              errors.push('envio.depto requerido');
  if (!nonEmpty(envio.municipio))          errors.push('envio.municipio requerido');
  if (!nonEmpty(envio.direccion))          errors.push('envio.direccion requerido');

  if (!Array.isArray(body?.productos) || body.productos.length === 0) {
    errors.push('productos[] requerido (min 1)');
  }

  if (typeof body?.total !== 'number' || body.total <= 0) {
    errors.push('total debe ser numero positivo');
  }

  return errors;
}

function generateRef() {
  return 'V-' + Date.now().toString(36).toUpperCase();
}

function jsonResp(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',  // CORS tightened in Task 9
    },
  });
}

// ── Handler: POST /api/vault/reservation ─────────────────────

/**
 * Public endpoint. Creates a vault lead and either:
 *   - If a valid `vault_ff` coupon is present: skips Recurrente (payment_status='waived_ff')
 *     and returns { skip_payment: true, total_cod }.
 *   - Otherwise: creates a Recurrente Q100 checkout and returns { checkout_url }.
 *
 * Percent/fixed coupons are tracked on the lead for analytics but flow through the
 * standard Q100 Recurrente path — the discount applies at COD time (future task).
 */
export async function handleVaultReservation(request, env) {
  let body;
  try { body = await request.json(); }
  catch { return jsonResp({ ok: false, error: 'JSON invalido' }, 400); }

  const errors = validateReservationPayload(body);
  if (errors.length > 0) {
    return jsonResp({ ok: false, error: errors.join('; ') }, 400);
  }

  // Coupon validation (optional)
  let coupon = null;
  if (nonEmpty(body.coupon_code)) {
    coupon = await validateCouponForReservation(env, body.coupon_code);
    if (coupon && !coupon.valid) {
      return jsonResp({ ok: false, error: `Cupon invalido: ${coupon.error}` }, 400);
    }
  }

  const isFFWaiver = coupon?.valid && coupon.type === 'vault_ff';
  // For vault_ff: coupon.value is the COD amount (Q435 or Q400 etc)
  // For percent/fixed: the discount applies at COD time, out of scope for the reservation. Still track coupon_code for analytics.
  const totalCod = isFFWaiver ? coupon.value : (body.total - 100);

  const ref = generateRef();
  const nowIso = new Date().toISOString();

  const lead = {
    ref,
    timestamp: nowIso,
    saved_at: nowIso,
    cliente: {
      nombre:   body.cliente.nombre.trim(),
      telefono: body.cliente.telefono.trim(),
      email:    nonEmpty(body.cliente.email) ? body.cliente.email.trim() : null,
    },
    envio: {
      modalidad:   body.envio.modalidad,
      depto:       body.envio.depto.trim(),
      municipio:   body.envio.municipio.trim(),
      direccion:   body.envio.direccion.trim(),
      referencias: nonEmpty(body.envio.referencias) ? body.envio.referencias.trim() : null,
    },
    productos: body.productos,
    total: body.total,
    total_cod: totalCod,
    notas: nonEmpty(body.notas) ? body.notas.trim() : null,
    reorder_of: nonEmpty(body.reorder_of) ? body.reorder_of.trim() : null,
    coupon_code: coupon?.valid ? coupon.code : null,
    payment_status: isFFWaiver ? 'waived_ff' : 'pending',
    fulfillment_status: 'awaiting_import',
    source: 'vault.elclub.club',
  };

  await saveLead(env, lead);

  if (isFFWaiver) {
    await incrementCouponUsage(env, coupon.code);
    await appendStatusHistory(env, ref, 'init', 'waived_ff', 'payment',
      `Cupon F&F ${coupon.code} aplicado — sin cobro Q100, COD Q${totalCod}`);
    return jsonResp({
      ok: true,
      lead_id: ref,
      skip_payment: true,
      total_cod: totalCod,
    });
  }

  // Standard path: Recurrente checkout
  await appendStatusHistory(env, ref, 'init', 'pending', 'payment',
    coupon?.valid
      ? `Lead creado con cupon ${coupon.code} (type=${coupon.type}); esperando pago Q100`
      : 'Lead creado, esperando pago Q100 via Recurrente');

  let checkout;
  try {
    checkout = await createReservationCheckout(env, ref, lead.cliente.nombre);
  } catch (err) {
    console.error('Recurrente checkout creation failed:', err);
    try {
      await updateLeadStatus(env, ref, 'payment', 'cancelled',
        `Recurrente API fallo: ${String(err.message || err).slice(0,200)}`);
    } catch (updateErr) {
      console.error('Failed to cancel lead after Recurrente error:', updateErr);
    }
    return jsonResp({
      ok: false,
      error: 'No se pudo crear la sesion de pago. Probá otra vez o contactá por WhatsApp.',
    }, 500);
  }

  return jsonResp({
    ok: true,
    lead_id: ref,
    checkout_url: checkout.checkout_url,
  });
}

// ── Coupon validation for reservation ────────────────────────

/**
 * Fetch + validate a coupon. Returns a normalized object — never throws.
 *
 * @returns {Promise<{ valid: boolean, code?: string, type?: string, value?: number, notes?: string, error?: string } | null>}
 *          null if no couponCode provided
 */
export async function validateCouponForReservation(env, couponCode) {
  if (!couponCode) return null;

  const code = couponCode.trim().toUpperCase();
  const raw = await env.DATA.get(`coupon:${code}`);
  if (!raw) return { valid: false, error: 'Cupon no existe' };

  let coupon;
  try { coupon = JSON.parse(raw); }
  catch { return { valid: false, error: 'Cupon mal formado' }; }

  if (!coupon.active) return { valid: false, error: 'Cupon inactivo' };
  if (coupon.expires_at && new Date(coupon.expires_at) < new Date()) {
    return { valid: false, error: 'Cupon expirado' };
  }
  if (typeof coupon.max_uses === 'number' && coupon.used >= coupon.max_uses) {
    return { valid: false, error: 'Cupon agotado' };
  }

  return {
    valid: true,
    code: coupon.code,
    type: coupon.type,
    value: coupon.value,
    notes: coupon.notes || null,
  };
}

/**
 * Atomically increment a coupon's `used` count. Safe to call for cupons that
 * don't exist (no-op). Preserves `expires_at` TTL if set.
 */
export async function incrementCouponUsage(env, couponCode) {
  if (!couponCode) return;
  const code = couponCode.trim().toUpperCase();
  const raw = await env.DATA.get(`coupon:${code}`);
  if (!raw) return;

  let coupon;
  try { coupon = JSON.parse(raw); }
  catch { return; }

  coupon.used = (coupon.used || 0) + 1;

  const putOptions = {};
  if (coupon.expires_at) {
    const ttl = Math.floor((new Date(coupon.expires_at).getTime() - Date.now()) / 1000);
    if (ttl > 0) putOptions.expirationTtl = ttl;
  }

  await env.DATA.put(`coupon:${code}`, JSON.stringify(coupon), putOptions);
}
