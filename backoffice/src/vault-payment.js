// el-club/backoffice/src/vault-payment.js
/**
 * Recurrente checkout creation for vault Q100 reservations.
 *
 * Uses the El Club Recurrente account (RECURRENTE_PUBLIC_KEY / RECURRENTE_SECRET_KEY).
 * Writes a reverse lookup in KV: vault_reservation:{checkout_id} → { vault_ref }
 * (TTL 48h) so the webhook handler can resolve which vault lead corresponds to
 * an incoming payment.
 */

const RESERVATION_AMOUNT_CENTS = 10000;  // Q100 flat universal (per decisión DEEP)
const RESERVATION_TTL_SECONDS  = 172800; // 48h

/**
 * Create a Recurrente checkout session for a Q100 vault reservation.
 *
 * @param {object} env           - Worker env (needs DATA, RECURRENTE_PUBLIC_KEY, RECURRENTE_SECRET_KEY)
 * @param {string} vaultRef      - the lead ref (e.g. "V-ABC123")
 * @param {string} customerName  - shown in the checkout UI
 * @returns {Promise<{ checkout_id: string, checkout_url: string }>}
 * @throws  when Recurrente credentials are missing or the API call fails
 */
export async function createReservationCheckout(env, vaultRef, customerName) {
  const publicKey = env.RECURRENTE_PUBLIC_KEY;
  const secretKey = env.RECURRENTE_SECRET_KEY;
  if (!publicKey || !secretKey) {
    throw new Error('Recurrente credentials not configured');
  }

  const res = await fetch('https://app.recurrente.com/api/checkouts', {
    method: 'POST',
    headers: {
      'X-PUBLIC-KEY': publicKey,
      'X-SECRET-KEY': secretKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      items: [{
        name: `Reserva Vault — ${vaultRef}`,
        amount_in_cents: RESERVATION_AMOUNT_CENTS,
        currency: 'GTQ',
        quantity: 1,
      }],
      success_url: `https://vault.elclub.club/gracias.html?ref=${encodeURIComponent(vaultRef)}`,
      cancel_url:  `https://vault.elclub.club/checkout.html?ref=${encodeURIComponent(vaultRef)}&cancelled=1`,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error(`Recurrente API ${res.status}: ${body}`);
    throw new Error(`Error al crear checkout Recurrente (${res.status})`);
  }

  const checkout = await res.json();

  // Reverse lookup for webhook handler
  await env.DATA.put(
    `vault_reservation:${checkout.id}`,
    JSON.stringify({
      vault_ref: vaultRef,
      customer_name: customerName,
      created_at: new Date().toISOString(),
    }),
    { expirationTtl: RESERVATION_TTL_SECONDS }
  );

  return { checkout_id: checkout.id, checkout_url: checkout.checkout_url };
}
