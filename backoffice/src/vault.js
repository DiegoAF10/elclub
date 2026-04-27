// el-club/backoffice/src/vault.js
/**
 * Vault lead management — dual-axis state machine + CRUD + coupon gating.
 *
 * State model:
 *   - payment_status: pending | paid | waived_ff | cod_pending_confirmation | cod_only | cod_completed | refunded_credit | cancelled
 *   - fulfillment_status: awaiting_import | arrived | shipped_cod | delivered | no_show | import_failed
 *
 * See: docs/superpowers/specs/2026-04-24-vault-q100-reservation-flow-design.md §3
 */

import { createReservationCheckout } from './vault-payment.js';

// Pricing model (decisión 2026-04-25, spec §1)
const PRICE_RESERVATION_FLAT = 415;     // Q415 todo incluido si reserva
const PRICE_BASE_NORESERVATION = 435;   // Q435 base sin reserva (addons separados)
const RESERVATION_AMOUNT = 100;         // Q100 anticipo

// Path B (sin reserva) requires WhatsApp confirmation within this window before
// auto-cancellation. Cliente debe escribir "CONFIRMO PEDIDO V-XXXX" al bot WA.
export const COD_CONFIRMATION_TTL_MS = 24 * 60 * 60 * 1000;  // 24h
// At T+12h (halfway through TTL), send a single email nudge to the customer
// reminding them to confirm. Tracked via lead.nudge_12h_sent_at to avoid spam.
export const COD_NUDGE_AT_MS         = 12 * 60 * 60 * 1000;  // 12h

export const PAYMENT_TRANSITIONS = {
  pending:                   ['paid', 'refunded_credit', 'cancelled'],
  paid:                      ['cod_completed', 'refunded_credit'],
  waived_ff:                 ['cod_completed', 'cancelled'],
  cod_pending_confirmation:  ['cod_only', 'cancelled'],   // NEW: gate WA before activar
  cod_only:                  ['cod_completed', 'cancelled'],
  cod_completed:             [],
  refunded_credit:           [],
  cancelled:                 [],
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
 * @param {object} [extraFields]  Optional extra fields merged into the record
 *                                (e.g. Recurrente enrichment). Applied BEFORE the
 *                                axis field so it cannot overwrite the new status.
 */
export async function updateLeadStatus(env, ref, axis, newStatus, note, extraFields = null) {
  const found = await findLeadByRef(env, ref);
  if (!found) throw new Error(`lead ${ref} no existe`);

  const field = axis === 'payment' ? 'payment_status' : 'fulfillment_status';
  const from = found.record[field];

  const updated = {
    ...found.record,
    ...(extraFields || {}),
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

/**
 * Validate that body.total is coherent with the chosen payment path.
 * Anti-manipulation: prevents a malicious client from sending total=100 with
 * payment_choice='reservation' to get the jersey at the reservation amount.
 *
 * @param {number} total
 * @param {'reservation'|'cod'} paymentChoice
 * @param {number} itemCount  cantidad de jerseys en el cart (min 1)
 * @returns {string|null}  error message or null if valid
 */
export function validatePricingCoherence(total, paymentChoice, itemCount = 1) {
  const n = Math.max(1, itemCount);
  if (paymentChoice === 'reservation') {
    const expected = PRICE_RESERVATION_FLAT * n;
    if (total !== expected) {
      return `total invalido para path reserva: esperado Q${expected} (Q${PRICE_RESERVATION_FLAT} × ${n}), recibido Q${total}`;
    }
    return null;
  }
  if (paymentChoice === 'cod') {
    const minimum = PRICE_BASE_NORESERVATION * n;
    if (typeof total !== 'number' || total < minimum) {
      return `total invalido para path COD: minimo Q${minimum} (Q${PRICE_BASE_NORESERVATION} × ${n}), recibido Q${total}`;
    }
    return null;
  }
  return `payment_choice invalido: ${paymentChoice}`;
}

function generateRef() {
  return 'V-' + Date.now().toString(36).toUpperCase();
}

/**
 * Response helper. CORS headers come from the router — pass empty {} if calling
 * outside the fetch handler (e.g. in the webhook where browser CORS is N/A).
 */
function jsonResp(obj, status = 200, cors = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      ...cors,
      'Content-Type': 'application/json',
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
export async function handleVaultReservation(request, env, cors = {}) {
  let body;
  try { body = await request.json(); }
  catch { return jsonResp({ ok: false, error: 'JSON invalido' }, 400, cors); }

  const errors = validateReservationPayload(body);
  if (errors.length > 0) {
    return jsonResp({ ok: false, error: errors.join('; ') }, 400, cors);
  }

  // Determine payment choice (default 'reservation' for backward compat with Sesión A)
  const paymentChoice = body.payment_choice === 'cod' ? 'cod' : 'reservation';

  // Coupon validation (optional)
  let coupon = null;
  if (nonEmpty(body.coupon_code)) {
    coupon = await validateCouponForReservation(env, body.coupon_code);
    if (coupon && !coupon.valid) {
      return jsonResp({ ok: false, error: `Cupon invalido: ${coupon.error}` }, 400, cors);
    }
  }

  const isFFWaiver = coupon?.valid && coupon.type === 'vault_ff';

  // Validate pricing coherence (skip if F&F — coupon.value is ground truth)
  if (!isFFWaiver) {
    const pricingError = validatePricingCoherence(body.total, paymentChoice, body.productos?.length || 1);
    if (pricingError) {
      return jsonResp({ ok: false, error: pricingError }, 400, cors);
    }
  }

  // total_cod calculation per path:
  //   F&F:         coupon.value * jerseyCount (Q400 por jersey, addons GRATIS bundled)
  //                e.g. 1 jersey: Q400 / 2 jerseys: Q800 / 3 jerseys: Q1200
  //   reservation: body.total - 100 (Q100 flat upfront universal, resto al COD)
  //                e.g. 1 jersey: Q415 - Q100 = Q315 / 2 jerseys: Q830 - Q100 = Q730
  //   cod:         body.total (Q435+addons por jersey, sin reserva deducida)
  const jerseyCount = body.productos?.length || 1;
  const totalCod = isFFWaiver
    ? coupon.value * jerseyCount
    : paymentChoice === 'cod'
      ? body.total
      : body.total - RESERVATION_AMOUNT;

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
    payment_status: isFFWaiver
      ? 'waived_ff'
      : paymentChoice === 'cod'
        ? 'cod_pending_confirmation'
        : 'pending',
    fulfillment_status: 'awaiting_import',
    source: 'vault.elclub.club',
  };

  await saveLead(env, lead);

  if (isFFWaiver) {
    await incrementCouponUsage(env, coupon.code);
    await appendStatusHistory(env, ref, 'init', 'waived_ff', 'payment',
      `Cupon F&F ${coupon.code} aplicado — sin cobro Q100, COD Q${totalCod}`);

    try {
      await notifyDiegoVaultPayment(env, lead, 'waived_ff');
    } catch (err) {
      console.error('Notify Diego F&F failed (non-fatal):', err);
    }

    return jsonResp({
      ok: true,
      lead_id: ref,
      skip_payment: true,
      total_cod: totalCod,
      path: 'ff',
    }, 200, cors);
  }

  if (paymentChoice === 'cod') {
    await appendStatusHistory(env, ref, 'init', 'cod_pending_confirmation', 'payment',
      `Sin reserva — esperando confirmación WA del cliente. COD a cobrar: Q${totalCod}`);

    try {
      await notifyDiegoVaultPayment(env, lead, 'cod_pending_confirmation');
    } catch (err) {
      console.error('Notify Diego cod_pending_confirmation failed (non-fatal):', err);
    }

    return jsonResp({
      ok: true,
      lead_id: ref,
      skip_payment: true,
      total_cod: totalCod,
      path: 'cod_pending',
      requires_wa_confirmation: true,
    }, 200, cors);
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
    }, 500, cors);
  }

  return jsonResp({
    ok: true,
    lead_id: ref,
    path: 'reservation',
    checkout_url: checkout.checkout_url,
  }, 200, cors);
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

// ── Admin handlers ───────────────────────────────────────────

/**
 * GET /api/vault/leads — list leads with optional filters.
 * Query params:
 *   - limit (default 50, max 500)
 *   - payment_status (CSV, OR-join)
 *   - fulfillment_status (CSV, OR-join)
 *   - has_coupon (true|false)
 */
export async function handleListVaultLeads(url, env, cors = {}) {
  const limitRaw = Number(url.searchParams.get('limit'));
  const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(500, Math.floor(limitRaw))) : 50;

  const parseCSV = (p) => {
    const v = url.searchParams.get(p);
    return v ? v.split(',').map(s => s.trim()).filter(Boolean) : null;
  };

  const paymentStatuses     = parseCSV('payment_status');
  const fulfillmentStatuses = parseCSV('fulfillment_status');
  const hasCouponParam      = url.searchParams.get('has_coupon');
  const hasCoupon = hasCouponParam === 'true'  ? true
                 : hasCouponParam === 'false' ? false
                 : null;

  const entries = await listLeads(env, { limit, paymentStatuses, fulfillmentStatuses, hasCoupon });

  // Hydrate: fetch full records for each index entry
  const full = await Promise.all(entries.map(async entry => {
    const record = await env.DATA.get(entry.key, { type: 'json' });
    return record || entry;  // fall back to index entry if record vanished
  }));

  return jsonResp({ ok: true, count: full.length, leads: full }, 200, cors);
}

/**
 * GET /api/vault/lead/:ref — fetch single lead with full history.
 */
export async function handleVaultLeadDetail(env, ref, cors = {}) {
  const result = await getLeadWithHistory(env, ref);
  if (!result) return jsonResp({ ok: false, error: 'lead no encontrado' }, 404, cors);
  return jsonResp({ ok: true, ...result }, 200, cors);
}

/**
 * PATCH /api/vault/lead/:ref/payment — transition payment_status.
 * Body: { status, note?, force? }
 */
export async function handlePatchPaymentStatus(request, env, ref, cors = {}) {
  return await handlePatchAxisStatus(request, env, ref, 'payment', cors);
}

/**
 * PATCH /api/vault/lead/:ref/fulfillment — transition fulfillment_status.
 * Body: { status, note?, force? }
 */
export async function handlePatchFulfillmentStatus(request, env, ref, cors = {}) {
  return await handlePatchAxisStatus(request, env, ref, 'fulfillment', cors);
}

async function handlePatchAxisStatus(request, env, ref, axis, cors = {}) {
  let body;
  try { body = await request.json(); }
  catch { return jsonResp({ ok: false, error: 'JSON invalido' }, 400, cors); }

  const newStatus = body?.status;
  const note = body?.note;
  const force = body?.force === true;

  if (!newStatus || typeof newStatus !== 'string') {
    return jsonResp({ ok: false, error: 'status requerido' }, 400, cors);
  }

  // Guard: even with force=true, only accept known status values. Writing
  // unknown strings would break validateTransition permanently for this lead.
  const allStatuses = axis === 'payment' ? ALL_PAYMENT_STATUSES : ALL_FULFILLMENT_STATUSES;
  if (!allStatuses.includes(newStatus)) {
    return jsonResp({
      ok: false,
      error: `status desconocido: ${newStatus}`,
      valid_values: allStatuses,
    }, 400, cors);
  }

  const found = await findLeadByRef(env, ref);
  if (!found) return jsonResp({ ok: false, error: 'lead no encontrado' }, 404, cors);

  const field = axis === 'payment' ? 'payment_status' : 'fulfillment_status';
  const current = found.record[field];

  if (current === newStatus) {
    return jsonResp({ ok: true, lead_id: ref, axis, status: current, unchanged: true }, 200, cors);
  }

  if (!force) {
    const validation = validateTransition(current, newStatus, axis);
    if (!validation.valid) {
      return jsonResp({
        ok: false,
        error: validation.error,
        allowed_next: validation.allowed_next,
      }, 409, cors);
    }
  }

  await updateLeadStatus(env, ref, axis, newStatus, note);

  return jsonResp({
    ok: true,
    lead_id: ref,
    axis,
    from: current,
    to: newStatus,
    forced: force,
  }, 200, cors);
}

// ── Webhook vault branch ─────────────────────────────────────

/**
 * Called from the webhook handler when the incoming payment_intent
 * (or bank_transfer_intent) corresponds to a vault reservation.
 *
 * Idempotent: if the lead is already 'paid', this is a no-op.
 * Valid event types: payment_intent.succeeded, bank_transfer_intent.succeeded.
 * Failed events are filtered by the caller.
 *
 * @returns {Promise<{ ok: boolean, idempotent?: boolean, vault_ref?: string, reason?: string, current?: string }>}
 */
export async function handleVaultPaymentSuccess(env, vaultRef, paymentIntent) {
  const found = await findLeadByRef(env, vaultRef);
  if (!found) {
    console.error(`Vault webhook: lead ${vaultRef} no existe (ya borrado o TTL expirado)`);
    return { ok: false, reason: 'lead_not_found' };
  }

  // Idempotency: if already paid, do nothing (Svix may retry)
  if (found.record.payment_status === 'paid') {
    console.log(`Vault webhook: lead ${vaultRef} ya esta paid (duplicate delivery, ignorado)`);
    return { ok: true, idempotent: true, vault_ref: vaultRef };
  }

  // Validate transition: pending → paid (only path expected here)
  const validation = validateTransition(found.record.payment_status, 'paid', 'payment');
  if (!validation.valid) {
    console.error(`Vault webhook: transicion invalida ${found.record.payment_status} → paid para ${vaultRef}`);
    return {
      ok: false,
      reason: 'invalid_transition',
      current: found.record.payment_status,
    };
  }

  // Merge Recurrente enrichment AND transition payment_status → paid in one
  // atomic KV write (via updateLeadStatus extraFields). Avoids a double-write
  // and the KV eventual-consistency window between them.
  //
  // Method extraction: Recurrente puts payment_method.type only on card flows.
  // For bank_transfer the field is missing — detect by ID prefix instead:
  //   pi_*  → card (payment intent)
  //   ba_*  → bank_transfer (bank account / ACH)
  //   ch_*  → checkout-derived (uncommon, fallback to card)
  const piId = paymentIntent?.id || '';
  const method = paymentIntent?.payment_method?.type
    || (piId.startsWith('ba_')              ? 'bank_transfer'
       : piId.startsWith('pi_') || piId.startsWith('ch_') ? 'card'
       : 'unknown');
  const amountCents = paymentIntent?.amount_in_cents || null;
  const amountQ = (amountCents || 0) / 100;

  const extraFields = {
    reservation_paid_at: new Date().toISOString(),
    recurrente_payment_id: paymentIntent?.id || null,
    recurrente_amount: amountCents,
    recurrente_method: method,
  };

  await updateLeadStatus(env, vaultRef, 'payment', 'paid',
    `Pago Q${amountQ} via Recurrente (${method})`, extraFields);

  // Best-effort: notify Diego. Failures are swallowed, not propagated.
  // Build the enriched payload locally for the email (without another KV read).
  const enrichedLead = { ...found.record, ...extraFields, payment_status: 'paid' };
  try {
    await notifyDiegoVaultPayment(env, enrichedLead);
  } catch (err) {
    console.error('Notify Diego failed (non-fatal):', err);
  }

  return { ok: true, vault_ref: vaultRef };
}

// ── Path B: WA confirmation gate ─────────────────────────────

/**
 * Confirm a Path B (sin reserva) lead via WhatsApp bot or manual admin click.
 * Idempotent: if already confirmed (cod_only), returns ok=true with action='idempotent'.
 *
 * Caller is responsible for auth — this function trusts its callers.
 *
 * @param {object} env
 * @param {string} ref       vault lead ref (V-XXXX)
 * @param {'bot'|'manual'} source  who confirmed (audit trail)
 * @returns {Promise<{ok: boolean, action: string, ref: string, message?: string}>}
 *   action: 'confirmed' | 'idempotent' | 'invalid_state' | 'not_found' | 'cancelled'
 */
export async function handleConfirmCod(env, ref, source = 'bot') {
  const found = await findLeadByRef(env, ref);
  if (!found) {
    return { ok: false, action: 'not_found', ref, message: 'Lead no existe' };
  }

  const current = found.record.payment_status;

  // Idempotent: already confirmed
  if (current === 'cod_only') {
    return { ok: true, action: 'idempotent', ref, message: 'Ya confirmado previamente' };
  }

  // Cancelled (timeout o admin cancel) → no se puede revivir desde el bot
  if (current === 'cancelled') {
    return { ok: false, action: 'cancelled', ref,
      message: 'Pedido cancelado. Si querés reactivarlo, escribí "Hola" para asistencia.' };
  }

  // Solo confirmamos desde cod_pending_confirmation
  if (current !== 'cod_pending_confirmation') {
    return { ok: false, action: 'invalid_state', ref,
      message: `Estado inesperado: ${current}. Contactá soporte.` };
  }

  await updateLeadStatus(env, ref, 'payment', 'cod_only',
    `Confirmación recibida (source=${source}). Activando pedido — ordenar a China.`);

  // Best-effort: notify Diego del cambio (email B "ordená a China")
  const updatedLead = { ...found.record, payment_status: 'cod_only' };
  try {
    await notifyDiegoVaultPayment(env, updatedLead, 'cod_confirmed');
  } catch (err) {
    console.error('Notify Diego cod_confirmed failed (non-fatal):', err);
  }

  return { ok: true, action: 'confirmed', ref,
    message: 'Pedido confirmado. Te avisamos apenas llegue tu pieza al archivo.' };
}

/**
 * Merge plain fields into a lead's full record + index entry without touching
 * state machine or history. Used for tracking flags like nudge_12h_sent_at.
 */
async function mergeLeadFields(env, ref, fields) {
  const found = await findLeadByRef(env, ref);
  if (!found) throw new Error(`lead ${ref} no existe`);
  const updated = { ...found.record, ...fields };
  await env.DATA.put(found.entry.key, JSON.stringify(updated));
  // Index entry is light — only sync if any of the merged fields exist on the index schema.
  // Currently nudge tracking lives on the full record only (not on the index).
  return updated;
}

/**
 * Cron sweeper: combina dos passes sobre leads en 'cod_pending_confirmation'.
 *   - Pass 1 (T+12h): single email nudge al cliente (si tiene email).
 *     Marca lead.nudge_12h_sent_at para no re-enviar.
 *   - Pass 2 (T+24h): cancel + email C a Diego.
 *
 * Idempotent y tolerante a fallos — un lead malo no para el sweep.
 *
 * @returns {Promise<{scanned: number, nudged: number, cancelled: number, errors: number}>}
 */
export async function runVaultPendingConfirmationSweep(env) {
  const index = (await env.DATA.get(INDEX_KEY, { type: 'json' })) || [];
  const now = Date.now();
  const nudgeCutoff  = now - COD_NUDGE_AT_MS;
  const cancelCutoff = now - COD_CONFIRMATION_TTL_MS;

  // All pending Path B leads (filtered later by age + nudge status)
  const allPending = index.filter(e => {
    if (e.payment_status !== 'cod_pending_confirmation') return false;
    const createdMs = new Date(e.timestamp).getTime();
    return Number.isFinite(createdMs);
  });

  let nudged = 0, cancelled = 0, errors = 0;

  // ── Pass 1: nudge candidates (T+12h, not yet cancelled, not yet nudged) ──
  for (const entry of allPending) {
    const createdMs = new Date(entry.timestamp).getTime();
    if (createdMs >= nudgeCutoff) continue;       // todavía joven, no nudge
    if (createdMs < cancelCutoff) continue;       // ya está en zona de cancel — pass 2 se encarga
    try {
      const found = await findLeadByRef(env, entry.ref);
      if (!found || found.record.nudge_12h_sent_at) continue;  // skip si ya nudged
      if (found.record.cliente?.email) {
        await sendCodPendingNudge(env, found.record);
      }
      // Marcamos siempre (incluso sin email) para no re-evaluar este lead cada 30min
      await mergeLeadFields(env, entry.ref, { nudge_12h_sent_at: new Date().toISOString() });
      nudged++;
    } catch (err) {
      console.error(`Sweep: nudge failed for ${entry.ref}:`, err);
      errors++;
    }
  }

  // ── Pass 2: cancel candidates (T+24h) ──
  for (const entry of allPending) {
    const createdMs = new Date(entry.timestamp).getTime();
    if (createdMs >= cancelCutoff) continue;
    try {
      await updateLeadStatus(env, entry.ref, 'payment', 'cancelled',
        'Auto-cancel: 24h sin confirmación WA del cliente');

      // Notify Diego (email C) — best-effort, errors don't block sweep
      const found = await findLeadByRef(env, entry.ref);
      if (found) {
        try {
          await notifyDiegoVaultPayment(env, found.record, 'cod_cancelled_no_confirmation');
        } catch (notifyErr) {
          console.error(`Sweep: notify Diego failed for ${entry.ref}:`, notifyErr);
        }
      }
      cancelled++;
    } catch (err) {
      console.error(`Sweep: cancel failed for ${entry.ref}:`, err);
      errors++;
    }
  }

  return { scanned: allPending.length, nudged, cancelled, errors };
}

/**
 * Send an email to a customer (not Diego) via Brevo. Brevo free tier supports
 * multi-domain (300/day). Para emails internos a Diego seguimos usando Resend
 * (notifyDiegoVaultPayment) que ya tiene la cuenta + fallback graceful.
 *
 * NOTE: si BREVO_API_KEY no está seteado, falla silently (logging) en vez
 * de bloquear el sweep. Diego puede ver el log y configurar después.
 *
 * @returns {Promise<void>}  throws on Brevo non-2xx for upstream error handling
 */
async function sendBrevoEmail(env, { to, toName, subject, html, fromName = 'El Club Vault' }) {
  if (!env.BREVO_API_KEY) {
    console.warn('[brevo] BREVO_API_KEY not set — skipping customer email');
    return;
  }
  const fromEmail = env.VAULT_CUSTOMER_EMAIL_FROM || 'vault@elclub.club';

  const res = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: {
      'accept': 'application/json',
      'api-key': env.BREVO_API_KEY,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      sender: { name: fromName, email: fromEmail },
      to: [{ email: to, name: toName || to.split('@')[0] }],
      subject,
      htmlContent: html,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    console.error(`[brevo] send failed ${res.status}: ${errText}`);
    throw new Error(`Brevo ${res.status}`);
  }
  const data = await res.json().catch(() => ({}));
  console.log(`[brevo] sent to ${to} messageId=${data.messageId || '?'}`);
}

/**
 * Send a single email nudge to the CUSTOMER (not Diego) at T+12h reminding
 * them to confirm their Path B pedido by sending the WhatsApp message.
 * Pre-rellena el wa.me link con el formato exacto que el bot detecta.
 *
 * Silent-fail — sweep continues even if email send errors.
 *
 * NOTE customer-facing: respeta la regla "no China" (memory:feedback_elclub_no_china).
 * NOTE: usa Brevo (no Resend) porque Resend free permite solo 1 domain
 *       verificado y ese es de VENTUS.
 */
export async function sendCodPendingNudge(env, lead) {
  if (!lead?.cliente?.email) return;

  const to       = lead.cliente.email;
  const ref      = lead.ref;
  const nombre   = lead.cliente.nombre?.split(/\s+/)[0] || 'amigo';
  const totalCod = lead.total_cod || '?';
  const waNumber = '13185343283';
  const confirmText = `CONFIRMO PEDIDO ${ref}`;
  const waLink   = `https://wa.me/${waNumber}?text=${encodeURIComponent(confirmText)}`;

  const subject = `Falta 1 paso para activar tu pedido — ${ref}`;

  // Product cards (max 2 visible — más se ve abrumador). Thumbnail prominent
  // a la izquierda, info estructurada a la derecha. Tabla porque flexbox no
  // funciona consistente en Outlook/Gmail iOS.
  const productosArr = lead.productos || [];
  const productCards = productosArr.slice(0, 2).map(p => {
    const team = p.team || 'Jersey';
    const season = p.season ? ` ${p.season}` : '';
    const variant = p.variant_label ? ` · ${p.variant_label}` : '';
    const sleeve = p.sleeve === 'long' ? ' · Manga larga' : '';
    const size = p.size ? `Talla ${p.size}` : 'Talla a definir';
    const pers = p.personalization || {};
    const persLine = (pers.nombre || pers.numero) ? `${pers.nombre || ''} ${pers.numero ? '#' + pers.numero : ''}`.trim() : '';
    const parche = pers.parche_label && pers.parche_label !== 'ninguno' ? pers.parche_label : '';
    const thumb = p.thumbnail || 'https://vault.elclub.club/assets/img/placeholder.png';
    return `
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:12px;background:#111827;border-radius:8px;overflow:hidden">
        <tr>
          <td width="96" style="vertical-align:top;background:#fff">
            <img src="${thumb}" alt="${team}${season}" width="96" height="96" style="display:block;width:96px;height:96px;object-fit:cover">
          </td>
          <td style="padding:14px 16px;vertical-align:top">
            <div style="font-size:15px;font-weight:700;color:#f9fafb;line-height:1.3;margin-bottom:4px">${team}${season}${variant}</div>
            <div style="font-size:13px;color:#9ca3af;line-height:1.4">${size}${sleeve}</div>
            ${persLine ? `<div style="font-size:12px;color:#fbbf24;font-family:monospace;margin-top:6px;letter-spacing:0.5px">${persLine}</div>` : ''}
            ${parche ? `<div style="font-size:11px;color:#a78bfa;margin-top:4px">+ ${parche}</div>` : ''}
          </td>
        </tr>
      </table>
    `;
  }).join('');
  const remainder = productosArr.length > 2 ? `<div style="text-align:center;font-size:12px;color:#6b7280;margin-top:-4px;margin-bottom:12px">+ ${productosArr.length - 2} producto${productosArr.length - 2 === 1 ? '' : 's'} más</div>` : '';

  const html = `
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${subject}</title></head>
<body style="margin:0;padding:0;background:#0a0b0d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#0a0b0d;padding:20px 0">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;width:100%;background:#0f1115;border-radius:12px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,0.4)">

      <!-- HEADER amber con branding -->
      <tr><td style="background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);padding:28px 24px;text-align:center;color:#1f2937">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:11px;letter-spacing:4px;text-transform:uppercase;font-weight:700;opacity:0.7;margin-bottom:4px">EL CLUB</div>
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;letter-spacing:6px;text-transform:uppercase;font-weight:900;color:#1f2937;line-height:1">VAULT</div>
        <div style="height:2px;width:48px;background:#1f2937;margin:14px auto 18px;opacity:0.4"></div>
        <h1 style="margin:0;font-size:22px;font-weight:700;color:#1f2937;line-height:1.3">Falta 1 paso, ${nombre}</h1>
        <div style="margin-top:8px;font-size:13px;color:#1f2937;opacity:0.75">Tu pedido espera tu confirmación por WhatsApp</div>
      </td></tr>

      <!-- BODY -->
      <tr><td style="padding:28px 24px;background:#0f1115">

        <!-- REF badge -->
        <div style="text-align:center;margin-bottom:24px">
          <span style="display:inline-block;padding:6px 14px;background:#1f2937;border-radius:20px;font-family:monospace;font-size:13px;color:#9ca3af;letter-spacing:1px">${ref}</span>
        </div>

        <!-- PRODUCT CARDS -->
        <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#6b7280;margin-bottom:10px;font-weight:600">Tu pedido</div>
        ${productCards}
        ${remainder}

        <!-- TOTAL pill -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:8px;margin-bottom:28px">
          <tr>
            <td style="padding:12px 14px;background:#0a0b0d;border:1px solid #1f2937;border-radius:6px">
              <table role="presentation" width="100%"><tr>
                <td style="font-size:13px;color:#9ca3af">Total al recibir</td>
                <td style="text-align:right;font-size:18px;font-weight:700;color:#f9fafb;font-family:monospace">Q${totalCod}</td>
              </tr><tr>
                <td colspan="2" style="font-size:11px;color:#6b7280;padding-top:4px">Envío gratis a domicilio · Pago contra entrega</td>
              </tr></table>
            </td>
          </tr>
        </table>

        <!-- DIVIDER -->
        <div style="height:1px;background:#1f2937;margin:0 0 24px"></div>

        <!-- CTA INSTRUCTIONS -->
        <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#fbbf24;margin-bottom:12px;font-weight:600;text-align:center">⏱ Acción requerida</div>
        <p style="margin:0 0 18px;font-size:15px;line-height:1.5;color:#e5e7eb;text-align:center">
          Para activar tu pedido, copiá <strong style="color:#f9fafb">este texto exacto</strong> y mandalo por WhatsApp:
        </p>

        <!-- COPY-ME box -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 18px">
          <tr><td style="padding:18px 16px;background:#1f2937;border:2px dashed #25D366;border-radius:8px;text-align:center">
            <code style="font-family:'SF Mono',Monaco,Consolas,monospace;font-size:16px;color:#f9fafb;letter-spacing:1px;font-weight:600">${confirmText}</code>
          </td></tr>
        </table>

        <!-- CTA BUTTON -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:0 0 12px">
          <tr><td align="center">
            <a href="${waLink}" target="_blank" style="display:inline-block;width:100%;padding:18px 24px;background:#25D366;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:700;font-size:17px;text-align:center;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,sans-serif">
              ✓ CONFIRMAR POR WHATSAPP
            </a>
          </td></tr>
        </table>

        <p style="margin:0 0 24px;font-size:12px;color:#9ca3af;text-align:center;line-height:1.5">
          El botón abre WhatsApp con el mensaje listo.<br>Solo dale <strong style="color:#e5e7eb">Enviar</strong>.
        </p>

        <!-- DEADLINE -->
        <div style="margin:24px 0 0;padding:14px 16px;background:rgba(245,158,11,0.08);border-left:3px solid #f59e0b;border-radius:4px">
          <div style="font-size:12px;color:#fbbf24;font-weight:600;margin-bottom:4px">⏳ Te quedan ~12 horas</div>
          <div style="font-size:12px;color:#9ca3af;line-height:1.5">
            Si no confirmás, el pedido se cancela automáticamente. ¿Cambiaste de idea? Ignorá este correo y se cancela solo.
          </div>
        </div>

      </td></tr>

      <!-- FOOTER -->
      <tr><td style="background:#0a0b0d;padding:24px;text-align:center">
        <div style="font-family:Georgia,serif;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#6b7280;margin-bottom:6px">El Club</div>
        <div style="font-size:13px;color:#9ca3af;font-style:italic;margin-bottom:14px">"La camiseta te elige a vos."</div>
        <div style="font-size:11px;color:#4b5563;line-height:1.6">
          <a href="https://vault.elclub.club" style="color:#9ca3af;text-decoration:none">vault.elclub.club</a>
          &nbsp;·&nbsp;
          <a href="https://instagram.com/club.gt" style="color:#9ca3af;text-decoration:none">@club.gt</a>
          &nbsp;·&nbsp;
          <a href="https://tiktok.com/@club.gtm" style="color:#9ca3af;text-decoration:none">@club.gtm</a>
        </div>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>
  `;

  await sendBrevoEmail(env, {
    to,
    toName: lead.cliente.nombre || nombre,
    subject,
    html,
    fromName: 'El Club Vault',
  });
  console.log(`[nudge] ${ref} → ${to}`);
}

/**
 * Send an email to Diego for vault lifecycle events. Uses Resend.
 * Silent-fail on errors (not critical for the webhook flow).
 *
 * @param {object} env
 * @param {object} lead   The full lead record
 * @param {string} [kind='paid']  Which lifecycle event triggered the email:
 *   - 'paid'                          → Q100 Recurrente cobró (Path A)
 *   - 'waived_ff'                     → cupón F&F saltó el cobro (Path C)
 *   - 'cod_pending_confirmation'      → Path B submit, esperando confirm WA (Email A)
 *   - 'cod_confirmed'                 → bot/admin confirmó Path B → ordená a China (Email B)
 *   - 'cod_cancelled_no_confirmation' → 24h timeout sin confirmación (Email C)
 *   - 'cod_only' (deprecated)         → backward compat alias para 'cod_confirmed'
 */
export async function notifyDiegoVaultPayment(env, lead, kind = 'paid') {
  if (!env.RESEND_API_KEY) {
    console.warn('RESEND_API_KEY not set — skipping email notification');
    return;
  }

  const to   = env.DIEGO_EMAIL || 'diegoarriazaflores@gmail.com';
  const from = env.VAULT_EMAIL_FROM || 'El Club Vault <onboarding@resend.dev>';
  const workerOrigin = env.WORKER_ORIGIN || 'https://elclub-backoffice.ventusgt.workers.dev';

  // Backward-compat alias (legacy code path)
  if (kind === 'cod_only') kind = 'cod_confirmed';

  const items = Array.isArray(lead.productos) ? lead.productos : [];
  const itemsHtml = items.map(it => {
    const label = [it.team, it.season, it.variant_label].filter(Boolean).join(' ') || 'jersey';
    const sleeve = it.sleeve === 'long' ? ' · Long Sleeve' : '';
    const p = it.personalization || {};
    const persParts = [];
    if (p.nombre || p.name) persParts.push(`Nombre: <strong>${p.nombre || p.name}</strong>`);
    if (p.numero || p.number) persParts.push(`#${p.numero || p.number}`);
    if (p.parche_label || p.patch) persParts.push(`Parche: ${p.parche_label || p.patch}`);
    const pers = persParts.length > 0
      ? `<div style="margin-top:4px;padding:6px 10px;background:#f8f8f8;border-left:3px solid #0066ff;font-size:13px;color:#333">${persParts.join(' · ')}</div>`
      : '';
    return `
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #eee;vertical-align:top">
          <div style="font-weight:600;color:#111">${label}</div>
          <div style="font-size:13px;color:#666;margin-top:2px">Talla ${it.size || '—'}${sleeve} · <strong style="color:#111">Q${it.total_price || '—'}</strong></div>
          ${pers}
        </td>
      </tr>
    `;
  }).join('');

  const envio = lead.envio || {};
  const cliente = lead.cliente || {};

  // Per-kind metadata: visual style + subject + payment block + actionable CTA
  const kindMeta = {
    paid: {
      icon: '🏴',
      title: 'Vault pagado — Q100 reserva',
      subject: `🏴 Vault ${lead.ref} pagado — ${cliente.nombre || 'cliente'}`,
      headerBg: '#10b981',
      paymentBlock: `
        <div style="padding:12px 16px;background:#f0fdf4;border-radius:6px;margin:16px 0">
          <div style="color:#065f46;font-weight:600">✅ Q100 reserva recibida via Recurrente</div>
          <div style="color:#047857;margin-top:4px">COD pendiente al entregar: <strong>Q${lead.total_cod || '?'}</strong></div>
          ${lead.recurrente_method ? `<div style="color:#6b7280;font-size:13px;margin-top:4px">Método: ${lead.recurrente_method}</div>` : ''}
        </div>
      `,
      actionBlock: `
        <div style="padding:12px 16px;background:#fef3c7;border-radius:6px;margin:12px 0">
          <strong>Próximo paso:</strong> ordenar a Bond Soccer Jersey en China.<br>
          <a href="${workerOrigin}/api/vault/lead/${lead.ref}/supplier-messages?key=${env.DASHBOARD_KEY || ''}" style="color:#0066ff">Ver mensajes pre-formateados →</a>
        </div>
      `,
    },
    waived_ff: {
      icon: '🎁',
      title: 'Vault F&F reservado',
      subject: `🎁 Vault ${lead.ref} F&F (${lead.coupon_code || '—'}) — ${cliente.nombre || 'cliente'}`,
      headerBg: '#8b5cf6',
      paymentBlock: `
        <div style="padding:12px 16px;background:#faf5ff;border-radius:6px;margin:16px 0">
          <div style="color:#5b21b6;font-weight:600">🎁 Cupón F&F aplicado: <code>${lead.coupon_code || '—'}</code></div>
          <div style="color:#6d28d9;margin-top:4px">Sin cobro upfront. COD a cobrar: <strong>Q${lead.total_cod || '?'}</strong></div>
        </div>
      `,
      actionBlock: `
        <div style="padding:12px 16px;background:#fef3c7;border-radius:6px;margin:12px 0">
          <strong>Próximo paso:</strong> ordenar a Bond Soccer Jersey en China.<br>
          <a href="${workerOrigin}/api/vault/lead/${lead.ref}/supplier-messages?key=${env.DASHBOARD_KEY || ''}" style="color:#0066ff">Ver mensajes pre-formateados →</a>
        </div>
      `,
    },
    cod_pending_confirmation: {
      icon: '🟡',
      title: 'Vault sin reserva — esperando confirmación WA',
      subject: `🟡 Vault ${lead.ref} esperando confirmación — ${cliente.nombre || 'cliente'}`,
      headerBg: '#f59e0b',
      paymentBlock: `
        <div style="padding:12px 16px;background:#fefce8;border:1px solid #fcd34d;border-radius:6px;margin:16px 0">
          <div style="color:#92400e;font-weight:600">⏳ Cliente eligió sin reserva — gate WA activo</div>
          <div style="color:#b45309;margin-top:4px">Sin pago hoy. COD esperado: <strong>Q${lead.total_cod || '?'}</strong></div>
          <div style="color:#78350f;margin-top:8px;font-size:13px">
            El cliente debe escribir <code>CONFIRMO PEDIDO ${lead.ref}</code> al bot WA en las próximas 24h.<br>
            Si no lo hace, el pedido se auto-cancela.
          </div>
        </div>
      `,
      actionBlock: `
        <div style="padding:16px;background:#1f2937;border-radius:6px;margin:16px 0;text-align:center">
          <div style="color:#f3f4f6;margin-bottom:12px;font-size:14px">¿Querés activar manualmente sin esperar al bot?</div>
          <a href="${workerOrigin}/api/vault/lead/${lead.ref}/confirm-cod?key=${env.DASHBOARD_KEY || ''}"
             style="display:inline-block;padding:12px 24px;background:#10b981;color:white;text-decoration:none;border-radius:6px;font-weight:600">
            ✅ Confirmar pedido manualmente
          </a>
          <div style="color:#9ca3af;margin-top:12px;font-size:12px">Un click activa el lead y dispara la confirmación al cliente.</div>
        </div>
      `,
    },
    cod_confirmed: {
      icon: '✅',
      title: 'Vault sin reserva CONFIRMADO',
      subject: `✅ Vault ${lead.ref} CONFIRMADO — ordená a China — ${cliente.nombre || 'cliente'}`,
      headerBg: '#10b981',
      paymentBlock: `
        <div style="padding:12px 16px;background:#f0fdf4;border-radius:6px;margin:16px 0">
          <div style="color:#065f46;font-weight:600">✅ Cliente confirmó el pedido por WhatsApp</div>
          <div style="color:#047857;margin-top:4px">COD a cobrar al entregar: <strong>Q${lead.total_cod || '?'}</strong></div>
        </div>
      `,
      actionBlock: `
        <div style="padding:12px 16px;background:#fef3c7;border-radius:6px;margin:12px 0">
          <strong>Ya podés ordenar a China.</strong><br>
          <a href="${workerOrigin}/api/vault/lead/${lead.ref}/supplier-messages?key=${env.DASHBOARD_KEY || ''}" style="color:#0066ff">Ver mensajes pre-formateados para Bond Soccer →</a>
        </div>
      `,
    },
    cod_cancelled_no_confirmation: {
      icon: '❌',
      title: 'Vault cancelado — sin confirmación 24h',
      subject: `❌ Vault ${lead.ref} cancelado por timeout — ${cliente.nombre || 'cliente'}`,
      headerBg: '#ef4444',
      paymentBlock: `
        <div style="padding:12px 16px;background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;margin:16px 0">
          <div style="color:#991b1b;font-weight:600">❌ Auto-cancelado: 24h sin confirmación WA</div>
          <div style="color:#b91c1c;margin-top:4px;font-size:13px">El cliente nunca escribió <code>CONFIRMO PEDIDO ${lead.ref}</code>.</div>
        </div>
      `,
      actionBlock: `
        <div style="padding:12px 16px;background:#f3f4f6;border-radius:6px;margin:12px 0;font-size:13px;color:#374151">
          <strong>Lead muerto — no ordenes a China.</strong><br>
          Si querés reactivarlo, hacé reach-out manual y creale un nuevo pedido.
        </div>
      `,
    },
  };

  const meta = kindMeta[kind] || kindMeta.paid;

  const html = `
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;color:#111;background:#fff">
      <div style="background:${meta.headerBg};padding:20px 24px;color:white">
        <div style="font-size:13px;opacity:0.9;letter-spacing:1px;text-transform:uppercase">El Club Vault</div>
        <h1 style="margin:6px 0 0;font-size:22px;font-weight:700">${meta.icon} ${meta.title}</h1>
        <div style="margin-top:4px;font-family:monospace;font-size:14px;opacity:0.9">${lead.ref}</div>
      </div>

      <div style="padding:20px 24px">
        <div style="display:flex;justify-content:space-between;align-items:start;gap:16px;margin-bottom:8px">
          <div>
            <div style="font-weight:600;font-size:16px;color:#111">${cliente.nombre || '—'}</div>
            <div style="color:#6b7280;font-size:14px;margin-top:2px">📱 ${cliente.telefono || '—'}${cliente.email ? ` · ✉️ ${cliente.email}` : ''}</div>
          </div>
        </div>

        ${meta.paymentBlock}

        <h3 style="margin:24px 0 8px;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px">Productos · ${items.length}</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
          ${itemsHtml || '<tr><td style="padding:10px 0;color:#999">sin items</td></tr>'}
        </table>

        <h3 style="margin:24px 0 8px;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px">Envío</h3>
        <div style="padding:12px;background:#f9fafb;border-radius:6px;font-size:14px">
          <div style="color:#111"><strong>${envio.modalidad === 'entrega' ? '🚚 Entrega a domicilio' : '🏠 Retiro'}</strong> · ${envio.depto || ''} / ${envio.municipio || ''}</div>
          <div style="color:#374151;margin-top:4px">${envio.direccion || '—'}</div>
          ${envio.referencias ? `<div style="color:#6b7280;margin-top:4px;font-style:italic">Ref: ${envio.referencias}</div>` : ''}
        </div>

        ${lead.notas ? `<div style="margin-top:16px;padding:12px;background:#fef3c7;border-radius:6px;font-size:13px;color:#78350f"><strong>Notas del cliente:</strong> ${lead.notas}</div>` : ''}

        ${meta.actionBlock}

        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0 16px">
        <div style="font-size:11px;color:#9ca3af;line-height:1.5">
          Lead ID: <code>${lead.ref}</code> · Source: ${lead.source || 'vault.elclub.club'}<br>
          Coupon: ${lead.coupon_code || '—'} · Total: Q${lead.total || '—'} · COD: Q${lead.total_cod || '—'}
        </div>
      </div>
    </div>
  `;

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from,
      to: [to],
      subject: meta.subject,
      html,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    console.error(`Resend email failed ${res.status}: ${errText}`);
    throw new Error(`Resend ${res.status}`);
  }
}

// ── Supplier messages (migrated from VENTUS worker) ──────────

const SUPPLIER_WA_NUMBER = '8615361409693';
const VALID_VERSIONS = new Set(['Fan', 'Player', 'Woman', 'Baby', 'Kid', 'Retro']);

function normalizeVersion(raw) {
  if (!nonEmpty(raw)) return 'Fan';
  const capped = raw.trim().charAt(0).toUpperCase() + raw.trim().slice(1).toLowerCase();
  return VALID_VERSIONS.has(capped) ? capped : 'Fan';
}

/**
 * Build the supplier message for a single item — English, exact format
 * Bond Soccer Jersey expects. Image is attached manually by Diego in WhatsApp.
 */
export function formatSupplierMessage(item) {
  const p = item?.personalization || {};
  const name    = nonEmpty(p.nombre || p.name) ? (p.nombre || p.name).trim() : '-';
  const number  = nonEmpty(String(p.numero ?? p.number ?? '')) ? String(p.numero ?? p.number) : '-';
  const patch   = nonEmpty(p.parche_label || p.parche || p.patch) ? (p.parche_label || p.parche || p.patch).trim() : '-';
  const size    = nonEmpty(item?.size) ? item.size.trim() : '-';
  const version = normalizeVersion(item?.version);

  const headerBits = [item?.team, item?.season, item?.variant_label]
    .filter(x => nonEmpty(x))
    .map(x => x.trim());
  const header = headerBits.length > 0 ? `${headerBits.join(' ')}\n` : '';

  return `${header}Name: ${name}\nNumber: ${number}\nPatch: ${patch}\nSize: ${size}\nVersion: ${version}`;
}

/**
 * GET /api/vault/lead/:ref/supplier-messages
 * Returns WA message + wa.me link for each item in the lead.
 */
export async function handleVaultSupplierMessages(env, ref, cors = {}) {
  const found = await findLeadByRef(env, ref);
  if (!found) return jsonResp({ ok: false, error: 'lead no encontrado' }, 404, cors);

  const items = Array.isArray(found.record.productos) ? found.record.productos : [];
  const messages = items.map((item, i) => {
    const message = formatSupplierMessage(item);
    return {
      index: i,
      family_id: item?.family_id || null,
      team: item?.team || null,
      season: item?.season || null,
      variant_label: item?.variant_label || null,
      size: item?.size || null,
      version: normalizeVersion(item?.version),
      message,
      wa_link: `https://wa.me/${SUPPLIER_WA_NUMBER}?text=${encodeURIComponent(message)}`,
    };
  });

  return jsonResp({
    ok: true,
    lead_id: ref,
    supplier: { number: SUPPLIER_WA_NUMBER, name: 'Bond Soccer Jersey' },
    count: messages.length,
    messages,
  }, 200, cors);
}
