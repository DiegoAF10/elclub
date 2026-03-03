/**
 * El Club Backoffice — Cloudflare Worker
 *
 * Minimal backend for Recurrente checkout integration.
 *
 * Endpoints:
 *   POST /api/checkout  — Create Recurrente checkout session (public, CORS)
 *   GET  /health        — Health check
 *
 * Secrets (via `npx wrangler secret put`):
 *   RECURRENTE_PUBLIC_KEY  — pk_live_...
 *   RECURRENTE_SECRET_KEY  — sk_live_...
 */

const ALLOWED_ORIGINS = [
  'https://elclub.club',
  'https://www.elclub.club',
  'http://localhost:5500',
  'http://127.0.0.1:5500',
];

function getCorsHeaders(request) {
  const origin = request.headers.get('Origin') || '';
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function jsonResponse(data, status, corsHeaders) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

/**
 * Validate checkout request data.
 * Items must have name, amount_in_cents (> 0), currency, quantity (> 0).
 */
function validateCheckoutData(data) {
  if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
    return 'Se requiere al menos un producto';
  }
  if (data.items.length > 20) {
    return 'Demasiados productos (max 20)';
  }

  let totalCents = 0;
  for (const item of data.items) {
    if (!item.name || typeof item.name !== 'string') {
      return 'Cada producto debe tener un nombre';
    }
    if (!item.amount_in_cents || item.amount_in_cents < 100) {
      return 'Monto invalido (minimo Q1)';
    }
    if (item.amount_in_cents > 100000) {
      return 'Monto invalido (maximo Q1,000 por item)';
    }
    if (!item.quantity || item.quantity < 1 || item.quantity > 10) {
      return 'Cantidad invalida (1-10)';
    }
    totalCents += item.amount_in_cents * item.quantity;
  }

  if (totalCents > 500000) {
    return 'Total invalido (maximo Q5,000)';
  }

  return null;
}

/**
 * Create a Recurrente checkout session.
 * Docs: https://docs.recurrente.com
 */
async function createCheckout(env, items) {
  const publicKey = env.RECURRENTE_PUBLIC_KEY;
  const secretKey = env.RECURRENTE_SECRET_KEY;

  if (!publicKey || !secretKey) {
    throw new Error('Recurrente credentials not configured');
  }

  // Map items to Recurrente format
  const recurrenteItems = items.map(item => ({
    name: item.name,
    amount_in_cents: item.amount_in_cents,
    currency: item.currency || 'GTQ',
    quantity: item.quantity,
  }));

  const res = await fetch('https://app.recurrente.com/api/checkouts', {
    method: 'POST',
    headers: {
      'X-PUBLIC-KEY': publicKey,
      'X-SECRET-KEY': secretKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      items: recurrenteItems,
      success_url: 'https://elclub.club/gracias.html',
      cancel_url: 'https://elclub.club/pedidos.html',
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error(`Recurrente API ${res.status}: ${body}`);
    throw new Error(`Error al crear checkout (${res.status})`);
  }

  const checkout = await res.json();
  return {
    checkout_id: checkout.id,
    checkout_url: checkout.checkout_url,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = getCorsHeaders(request);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    try {
      // Health check
      if ((url.pathname === '/' || url.pathname === '/health') && request.method === 'GET') {
        return jsonResponse({ status: 'ok', service: 'elclub-backoffice' }, 200, cors);
      }

      // Create Recurrente checkout
      if (url.pathname === '/api/checkout' && request.method === 'POST') {
        let data;
        try {
          data = await request.json();
        } catch {
          return jsonResponse({ error: 'JSON invalido' }, 400, cors);
        }

        const validationError = validateCheckoutData(data);
        if (validationError) {
          return jsonResponse({ error: validationError }, 400, cors);
        }

        const { checkout_id, checkout_url } = await createCheckout(env, data.items);

        console.log(`Checkout created: ${checkout_id} — ${data.items.length} items`);

        return jsonResponse({ checkout_url, checkout_id }, 200, cors);
      }

      return new Response('Not Found', { status: 404 });

    } catch (error) {
      console.error('Worker error:', error);
      return jsonResponse({ error: error.message }, 500, cors);
    }
  },
};
