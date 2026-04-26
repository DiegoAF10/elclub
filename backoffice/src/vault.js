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

// Pricing model (decisión 2026-04-25, spec §1)
const PRICE_RESERVATION_FLAT = 415;     // Q415 todo incluido si reserva
const PRICE_BASE_NORESERVATION = 435;   // Q435 base sin reserva (addons separados)
const RESERVATION_AMOUNT = 100;         // Q100 anticipo

export const PAYMENT_TRANSITIONS = {
  pending:         ['paid', 'refunded_credit', 'cancelled'],
  paid:            ['cod_completed', 'refunded_credit'],
  waived_ff:       ['cod_completed', 'cancelled'],
  cod_only:        ['cod_completed', 'cancelled'],   // NEW: customer chose no reservation
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
 * @returns {string|null}  error message or null if valid
 */
export function validatePricingCoherence(total, paymentChoice) {
  if (paymentChoice === 'reservation') {
    if (total !== PRICE_RESERVATION_FLAT) {
      return `total invalido para path reserva: esperado Q${PRICE_RESERVATION_FLAT} (todo incluido), recibido Q${total}`;
    }
    return null;
  }
  if (paymentChoice === 'cod') {
    if (typeof total !== 'number' || total < PRICE_BASE_NORESERVATION) {
      return `total invalido para path COD: minimo Q${PRICE_BASE_NORESERVATION}, recibido Q${total}`;
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
    const pricingError = validatePricingCoherence(body.total, paymentChoice);
    if (pricingError) {
      return jsonResp({ ok: false, error: pricingError }, 400, cors);
    }
  }

  // total_cod calculation per path:
  //   F&F:        coupon.value (Q400)
  //   reservation: body.total - 100 = Q315 (since body.total === Q415)
  //   cod:         body.total (Q435+addons, no reservation deducted)
  const totalCod = isFFWaiver
    ? coupon.value
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
        ? 'cod_only'
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
    await appendStatusHistory(env, ref, 'init', 'cod_only', 'payment',
      `Sin reserva — todo COD Q${totalCod}`);

    try {
      await notifyDiegoVaultPayment(env, lead, 'cod_only');
    } catch (err) {
      console.error('Notify Diego cod_only failed (non-fatal):', err);
    }

    return jsonResp({
      ok: true,
      lead_id: ref,
      skip_payment: true,
      total_cod: totalCod,
      path: 'cod',
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
  const method = paymentIntent?.payment_method?.type || 'unknown';
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

/**
 * Send an email to Diego when a vault reservation is created or paid.
 * Uses Resend. Silent-fail on errors (not critical for the webhook flow).
 *
 * @param {object} env
 * @param {object} lead            The full lead record
 * @param {'paid'|'waived_ff'|'cod_only'} [kind='paid']  Which lifecycle event triggered the email.
 *                                            'paid'     → Q100 Recurrente cobró
 *                                            'waived_ff' → cupón F&F saltó el cobro
 *                                            'cod_only' → cliente eligió sin reserva (todo COD)
 */
export async function notifyDiegoVaultPayment(env, lead, kind = 'paid') {
  if (!env.RESEND_API_KEY) {
    console.warn('RESEND_API_KEY not set — skipping email notification');
    return;
  }

  const to   = env.DIEGO_EMAIL || 'diegoarriazaflores@gmail.com';
  const from = env.VAULT_EMAIL_FROM || 'El Club Vault <onboarding@resend.dev>';

  const items = Array.isArray(lead.productos) ? lead.productos : [];
  const itemsHtml = items.map(it => {
    const label = [it.team, it.season, it.variant_label].filter(Boolean).join(' ') || 'jersey';
    const p = it.personalization || {};
    const pers = [
      p.name && `Name: ${p.name}`,
      (p.number !== undefined && p.number !== null && p.number !== '') && `#${p.number}`,
      p.patch && `Patch: ${p.patch}`,
    ].filter(Boolean).join(' · ');
    return `<li><strong>${label}</strong> — Talla ${it.size || '—'} · Q${it.total_price || '—'}${pers ? ` <br><span style="color:#666">${pers}</span>` : ''}</li>`;
  }).join('');

  const envio = lead.envio || {};
  const cliente = lead.cliente || {};

  const kindMeta = {
    paid:      { icon: '🏴', title: 'Vault pagado',          subjectFragment: 'pagado — Q100 reserva' },
    waived_ff: { icon: '🎁', title: 'Vault F&F reservado',   subjectFragment: 'F&F' },
    cod_only:  { icon: '📦', title: 'Vault sin reserva',     subjectFragment: 'sin reserva (COD)' },
  };
  const meta = kindMeta[kind] || kindMeta.paid;

  const paymentLine = (() => {
    if (kind === 'waived_ff') {
      return `<p style="margin:12px 0 4px"><strong>Cupón F&F aplicado (${lead.coupon_code || '—'}).</strong> Sin cobro Q100 upfront. COD a cobrar: <strong>Q${lead.total_cod || '?'}</strong></p>`;
    }
    if (kind === 'cod_only') {
      return `<p style="margin:12px 0 4px"><strong>Cliente eligió sin reserva.</strong> Sin pago hoy. COD a cobrar al entregar: <strong>Q${lead.total_cod || '?'}</strong></p>`;
    }
    // 'paid' default
    return `<p style="margin:12px 0 4px"><strong>Q100 reserva recibida.</strong> COD pendiente: <strong>Q${lead.total_cod || '?'}</strong></p>`;
  })();

  const subject = `${meta.icon} Vault ${lead.ref} ${meta.subjectFragment} (${lead.cliente?.nombre || 'cliente'})`;

  const html = `
    <div style="font-family:system-ui,sans-serif;max-width:560px;color:#111">
      <h2 style="margin:0 0 8px">${meta.icon} ${meta.title} — ${lead.ref}</h2>
      <p style="margin:0 0 4px"><strong>${cliente.nombre || '—'}</strong> · ${cliente.telefono || '—'}</p>
      ${cliente.email ? `<p style="margin:0 0 12px">Email: ${cliente.email}</p>` : ''}

      ${paymentLine}

      <h3 style="margin:20px 0 8px;font-size:14px;color:#666;text-transform:uppercase">Productos (${items.length})</h3>
      <ul style="margin:0 0 12px;padding-left:20px">${itemsHtml || '<li>sin items</li>'}</ul>

      <h3 style="margin:20px 0 8px;font-size:14px;color:#666;text-transform:uppercase">Envío</h3>
      <p style="margin:0 0 4px">${envio.modalidad || '—'} · ${envio.depto || ''} / ${envio.municipio || ''}</p>
      <p style="margin:0 0 4px;color:#555">${envio.direccion || '—'}</p>
      ${envio.referencias ? `<p style="margin:0 0 4px;color:#666"><em>Ref: ${envio.referencias}</em></p>` : ''}

      ${lead.notas ? `<p style="margin:12px 0;color:#666"><em>Notas: ${lead.notas}</em></p>` : ''}

      <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
      <p style="margin:0;font-size:12px;color:#888">
        Siguiente paso: marcar <code>arrived</code> cuando llegue el container.<br>
        <code>PATCH /api/vault/lead/${lead.ref}/fulfillment</code> con <code>{"status":"arrived"}</code>
      </p>
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
      subject,
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
  const name    = nonEmpty(p.name)    ? p.name.trim()  : '-';
  const number  = (p.number === 0 || nonEmpty(String(p.number || ''))) ? String(p.number) : '-';
  const patch   = nonEmpty(p.patch)   ? p.patch.trim() : '-';
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
