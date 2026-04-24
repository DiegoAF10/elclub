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
