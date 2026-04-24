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
 * @param {string[]|null} [options.paymentStatuses]      CSV filter (OR-join). If null, excludes 'pending' by default.
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
