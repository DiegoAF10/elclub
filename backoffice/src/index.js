/**
 * El Club Backoffice — Cloudflare Worker
 *
 * Endpoints:
 *   POST /api/checkout         — Create Recurrente checkout session
 *   POST /webhook/recurrente   — Receive payment webhook (Svix)
 *   GET  /health               — Health check
 *
 * Secrets:
 *   RECURRENTE_PUBLIC_KEY, RECURRENTE_SECRET_KEY — Recurrente API
 *   RESEND_API_KEY          — Email sending
 *   GITHUB_TOKEN            — Update products.json stock
 *   WEBHOOK_SECRET          — Svix signature verification
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

function json(data, status, cors) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

// ── Checkout validation ──────────────────────────────────────

function validateCheckoutData(data) {
  if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
    return 'Se requiere al menos un producto';
  }
  if (data.items.length > 20) return 'Demasiados productos (max 20)';

  let totalCents = 0;
  for (const item of data.items) {
    if (!item.name || typeof item.name !== 'string') return 'Producto sin nombre';
    if (!item.amount_in_cents || item.amount_in_cents < 100) return 'Monto invalido (min Q1)';
    if (item.amount_in_cents > 100000) return 'Monto invalido (max Q1,000/item)';
    if (!item.quantity || item.quantity < 1 || item.quantity > 10) return 'Cantidad invalida (1-10)';
    totalCents += item.amount_in_cents * item.quantity;
  }
  if (totalCents > 500000) return 'Total invalido (max Q5,000)';
  return null;
}

// ── Create Recurrente checkout ───────────────────────────────

async function createCheckout(env, data) {
  const publicKey = env.RECURRENTE_PUBLIC_KEY;
  const secretKey = env.RECURRENTE_SECRET_KEY;
  if (!publicKey || !secretKey) throw new Error('Recurrente credentials not configured');

  const recurrenteItems = data.items.map(item => ({
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

  // Store pending checkout in KV (48h TTL)
  const pendingData = {
    items: data.items,
    product_ids: data.product_ids || [],
    customer: data.customer || {},
    created_at: new Date().toISOString(),
  };
  await env.DATA.put(
    `pending:${checkout.id}`,
    JSON.stringify(pendingData),
    { expirationTtl: 172800 }
  );

  return { checkout_id: checkout.id, checkout_url: checkout.checkout_url };
}

// ── Webhook handler ──────────────────────────────────────────

async function handleWebhook(request, env) {
  const body = await request.text();
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    return new Response('Invalid JSON', { status: 400 });
  }

  const eventType = payload.event_type;
  console.log(`Webhook received: ${eventType}`);

  // Only process successful payments
  if (eventType !== 'payment_intent.succeeded') {
    return new Response(JSON.stringify({ status: 'ignored', event: eventType }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const pi = payload.payment_intent;
  const checkout = pi.checkout || {};
  const checkoutId = checkout.id;
  const amountCents = pi.amount_in_cents;

  // Customer data from Recurrente checkout form
  const customerEmail = checkout.customer_email || '';
  const customerName = checkout.customer_name || '';
  const customerPhone = checkout.customer_phone || '';

  // Look up pending checkout data from KV
  let pendingData = null;
  if (checkoutId) {
    const raw = await env.DATA.get(`pending:${checkoutId}`);
    if (raw) {
      pendingData = JSON.parse(raw);
      // Clean up
      await env.DATA.delete(`pending:${checkoutId}`);
    }
  }

  const items = pendingData?.items || [{ name: checkout.product_name || 'Producto', amount_in_cents: amountCents, quantity: 1 }];
  const productIds = pendingData?.product_ids || [];
  const shippingCustomer = pendingData?.customer || {};

  // Build order record
  const order = {
    checkout_id: checkoutId,
    payment_id: pi.id,
    amount_cents: amountCents,
    items,
    product_ids: productIds,
    customer: {
      name: customerName || shippingCustomer.name || '',
      email: customerEmail,
      phone: customerPhone || shippingCustomer.phone || '',
      address: shippingCustomer.address || '',
      notes: shippingCustomer.notes || '',
    },
    paid_at: new Date().toISOString(),
  };

  // Store completed order
  await env.DATA.put(
    `order:${checkoutId}`,
    JSON.stringify(order),
    { expirationTtl: 7776000 } // 90 days
  );

  console.log(`Payment confirmed: ${checkoutId} — Q${amountCents / 100} — ${customerEmail}`);

  // Run post-payment tasks in parallel
  const tasks = [];

  // Email to customer
  if (customerEmail && env.RESEND_API_KEY) {
    tasks.push(
      sendCustomerEmail(env, customerEmail, customerName, items, amountCents)
        .catch(err => console.error('Customer email failed:', err))
    );
  }

  // Email to Diego
  if (env.RESEND_API_KEY) {
    tasks.push(
      sendDiegoAlert(env, order)
        .catch(err => console.error('Diego alert failed:', err))
    );
  }

  // Update stock on GitHub
  if (productIds.length > 0 && env.GITHUB_TOKEN) {
    tasks.push(
      updateStock(env, productIds)
        .catch(err => console.error('Stock update failed:', err))
    );
  }

  await Promise.allSettled(tasks);

  return new Response(JSON.stringify({ status: 'ok', checkout_id: checkoutId }), {
    headers: { 'Content-Type': 'application/json' },
  });
}

// ── Email: Customer confirmation ─────────────────────────────

async function sendCustomerEmail(env, email, name, items, totalCents) {
  const itemLines = items
    .filter(i => i.name !== 'Envío')
    .map(i => `  ${i.name} x${i.quantity} — Q${(i.amount_in_cents * i.quantity) / 100}`)
    .join('\n');

  const shippingItem = items.find(i => i.name === 'Envío');
  const shippingLine = shippingItem ? `  Envío: Q${shippingItem.amount_in_cents / 100}` : '';

  const html = `
<div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #333;">
  <div style="text-align: center; padding: 32px 0 24px;">
    <h1 style="font-size: 24px; font-weight: 700; margin: 0;">¡Pago confirmado!</h1>
  </div>

  <p>Hola${name ? ' ' + name.split(' ')[0] : ''},</p>

  <p>Tu pago en <strong>El Club</strong> fue procesado. Acá está tu resumen:</p>

  <div style="background: #f8f8f8; border-radius: 8px; padding: 20px; margin: 20px 0;">
    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
      ${items.map(i => `
      <tr>
        <td style="padding: 6px 0; border-bottom: 1px solid #eee;">${i.name}${i.quantity > 1 ? ' x' + i.quantity : ''}</td>
        <td style="padding: 6px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: 600;">Q${(i.amount_in_cents * i.quantity) / 100}</td>
      </tr>`).join('')}
      <tr>
        <td style="padding: 12px 0 0; font-weight: 700; font-size: 16px;">Total</td>
        <td style="padding: 12px 0 0; text-align: right; font-weight: 700; font-size: 16px; color: #4DA8FF;">Q${totalCents / 100}</td>
      </tr>
    </table>
  </div>

  <p>Te escribimos por WhatsApp para coordinar la entrega. Si tenés alguna duda, respondé a este correo.</p>

  <p style="color: #888; font-size: 13px; margin-top: 32px;">— El Club<br>elclub.club</p>
</div>`;

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'El Club <noreply@elclub.club>',
      to: email,
      subject: '¡Tu pedido en El Club está confirmado!',
      html,
    }),
  });

  console.log(`Customer email sent to ${email}`);
}

// ── Email: Diego alert ───────────────────────────────────────

async function sendDiegoAlert(env, order) {
  const diegoEmail = env.DIEGO_EMAIL;
  if (!diegoEmail) {
    console.log('DIEGO_EMAIL not configured, skipping alert');
    return;
  }

  const itemLines = order.items
    .map(i => `• ${i.name} x${i.quantity} — Q${(i.amount_in_cents * i.quantity) / 100}`)
    .join('\n');

  const text = `NUEVA VENTA — El Club

${itemLines}

Total: Q${order.amount_cents / 100}
Checkout: ${order.checkout_id}

Cliente:
  Nombre: ${order.customer.name}
  Email: ${order.customer.email}
  Teléfono: ${order.customer.phone}
  Dirección: ${order.customer.address}
  Notas: ${order.customer.notes || '(ninguna)'}

Pagado: ${order.paid_at}

SKUs a actualizar: ${order.product_ids.join(', ') || '(no especificados)'}`;

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'El Club Bot <noreply@elclub.club>',
      to: diegoEmail,
      subject: `Venta Q${order.amount_cents / 100} — ${order.customer.name || 'Cliente'}`,
      text,
    }),
  });

  console.log(`Diego alert sent for ${order.checkout_id}`);
}

// ── Stock update via GitHub API ──────────────────────────────

async function updateStock(env, productIds) {
  const repo = env.GITHUB_REPO || 'DiegoAF10/elclub';
  const branch = env.GITHUB_BRANCH || 'main';
  const path = 'content/products.json';
  const token = env.GITHUB_TOKEN;

  if (!token) {
    console.log('GITHUB_TOKEN not configured, skipping stock update');
    return;
  }

  // 1. Read current products.json from GitHub
  const getRes = await fetch(`https://api.github.com/repos/${repo}/contents/${path}?ref=${branch}`, {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'elclub-backoffice',
    },
  });

  if (!getRes.ok) {
    throw new Error(`GitHub GET failed: ${getRes.status}`);
  }

  const fileData = await getRes.json();
  const content = atob(fileData.content.replace(/\n/g, ''));
  const products = JSON.parse(content);

  // 2. Decrement stock for each product ID sold
  let changed = false;
  for (const pid of productIds) {
    const product = products.find(p => p.id === pid);
    if (!product) {
      console.log(`Product ${pid} not found in products.json`);
      continue;
    }

    if (product.stock > 0) {
      product.stock -= 1;
      changed = true;
      console.log(`Stock updated: ${pid} → ${product.stock}`);
    }

    if (product.stock <= 0) {
      product.available = false;
      console.log(`Product ${pid} marked unavailable`);
    }
  }

  if (!changed) {
    console.log('No stock changes needed');
    return;
  }

  // 3. Commit updated products.json back to GitHub
  const updatedContent = btoa(unescape(encodeURIComponent(JSON.stringify(products, null, 2) + '\n')));

  const putRes = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`, {
    method: 'PUT',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'elclub-backoffice',
    },
    body: JSON.stringify({
      message: `stock: ${productIds.join(', ')} vendido (webhook)`,
      content: updatedContent,
      sha: fileData.sha,
      branch,
    }),
  });

  if (!putRes.ok) {
    const err = await putRes.text();
    throw new Error(`GitHub PUT failed: ${putRes.status} — ${err}`);
  }

  console.log(`products.json updated on GitHub for: ${productIds.join(', ')}`);
}

// ── Router ───────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = getCorsHeaders(request);

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    try {
      // Health check
      if ((url.pathname === '/' || url.pathname === '/health') && request.method === 'GET') {
        return json({ status: 'ok', service: 'elclub-backoffice' }, 200, cors);
      }

      // Create Recurrente checkout
      if (url.pathname === '/api/checkout' && request.method === 'POST') {
        let data;
        try { data = await request.json(); } catch {
          return json({ error: 'JSON invalido' }, 400, cors);
        }

        const err = validateCheckoutData(data);
        if (err) return json({ error: err }, 400, cors);

        const result = await createCheckout(env, data);
        console.log(`Checkout created: ${result.checkout_id} — ${data.items.length} items`);
        return json(result, 200, cors);
      }

      // Recurrente webhook (Svix)
      if (url.pathname === '/webhook/recurrente' && request.method === 'POST') {
        return await handleWebhook(request, env);
      }

      return new Response('Not Found', { status: 404 });

    } catch (error) {
      console.error('Worker error:', error);
      return json({ error: error.message }, 500, cors);
    }
  },
};
