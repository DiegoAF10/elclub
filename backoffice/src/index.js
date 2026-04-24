/**
 * El Club Backoffice — Cloudflare Worker
 *
 * Endpoints:
 *   POST /api/checkout              — Create Recurrente checkout session
 *   GET  /api/coupons/validate      — Validate a coupon code
 *   POST /api/coupons/admin         — Create a coupon (admin, X-Admin-Key)
 *   POST /webhook/recurrente        — Receive payment webhook (Svix)
 *   POST /api/order/custom          — Create custom jersey order (form capture)
 *   GET  /api/orders                — List orders (admin, X-Admin-Key)
 *   PATCH /api/order/:code          — Update order status (admin, X-Admin-Key)
 *   GET  /health                    — Health check
 *
 * Secrets:
 *   RECURRENTE_PUBLIC_KEY, RECURRENTE_SECRET_KEY — Recurrente API
 *   RESEND_API_KEY          — Email sending
 *   GITHUB_TOKEN            — Update products.json stock
 *   WEBHOOK_SECRET          — Svix signature verification
 *   ADMIN_KEY               — Admin endpoint authentication
 */

import {
  validateTransition,
  saveLead,
  findLeadByRef,
  updateLeadStatus,
  listLeads,
  getLeadWithHistory,
  handleVaultReservation,
} from './vault.js';
import { createReservationCheckout } from './vault-payment.js';

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
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Key',
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
  console.log('Recurrente checkout response:', JSON.stringify(checkout));

  // Store pending checkout in KV (48h TTL)
  const pendingData = {
    items: data.items,
    product_ids: data.product_ids || [],
    product_quantities: data.product_quantities || {},
    customer: data.customer || {},
    coupon_code: data.coupon_code || null,
    created_at: new Date().toISOString(),
  };
  await env.DATA.put(
    `pending:${checkout.id}`,
    JSON.stringify(pendingData),
    { expirationTtl: 172800 }
  );

  return { checkout_id: checkout.id, checkout_url: checkout.checkout_url };
}

// ── Svix signature verification ──────────────────────────────

async function validateSvixSignature(body, headers, secret) {
  if (!secret) {
    console.warn('⚠ WEBHOOK_SECRET not configured — skipping signature verification');
    return { valid: false, reason: 'no_secret' };
  }

  const msgId = headers.get('svix-id') || headers.get('webhook-id');
  const timestamp = headers.get('svix-timestamp') || headers.get('webhook-timestamp');
  const signature = headers.get('svix-signature') || headers.get('webhook-signature');

  if (!msgId || !timestamp || !signature) {
    console.warn('Missing Svix headers for signature verification');
    return { valid: false, reason: 'missing_headers' };
  }

  // Reject requests with timestamps older than 5 minutes (replay protection)
  const now = Math.floor(Date.now() / 1000);
  const ts = parseInt(timestamp, 10);
  if (isNaN(ts) || Math.abs(now - ts) > 300) {
    console.warn(`Svix timestamp too old or invalid: ${timestamp}`);
    return { valid: false, reason: 'timestamp_expired' };
  }

  try {
    // Remove whsec_ prefix and base64-decode the secret
    const secretBase64 = secret.startsWith('whsec_') ? secret.slice(6) : secret;
    const secretBytes = Uint8Array.from(atob(secretBase64), c => c.charCodeAt(0));

    // Sign: msg_id.timestamp.body
    const toSign = `${msgId}.${timestamp}.${body}`;
    const encoder = new TextEncoder();

    const key = await crypto.subtle.importKey(
      'raw',
      secretBytes,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(toSign));
    const computed = btoa(String.fromCharCode(...new Uint8Array(sig)));

    // Svix sends multiple signatures: "v1,sig1 v1,sig2" — check if any match
    const signatures = signature.split(' ');
    for (const s of signatures) {
      const [version, sigValue] = s.split(',');
      if (version === 'v1' && sigValue === computed) {
        return { valid: true };
      }
    }

    console.warn(`Svix signature mismatch — msgId=${msgId} ts=${timestamp}`);
    return { valid: false, reason: 'signature_mismatch' };
  } catch (err) {
    console.error('Signature validation error:', err.message);
    return { valid: false, reason: 'crypto_error' };
  }
}

// ── Webhook handler ──────────────────────────────────────────

async function handleWebhook(request, env) {
  // Read body as text first (needed for signature verification before JSON parse)
  const body = await request.text();

  // Validate Svix signature
  const sigResult = await validateSvixSignature(body, request.headers, env.WEBHOOK_SECRET);

  if (!sigResult.valid) {
    if (sigResult.reason === 'no_secret') {
      // Graceful fallback: no secret configured yet, process anyway with a warning
      console.warn('Processing webhook WITHOUT signature verification — configure WEBHOOK_SECRET to secure this endpoint');
    } else {
      // Secret IS configured but signature is invalid — reject
      console.error(`Webhook rejected: ${sigResult.reason}`);
      return new Response(JSON.stringify({ error: 'Invalid signature' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

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

  // Recurrente sends the payment intent as the root object
  const pi = payload.payment_intent || payload;
  const checkout = pi.checkout || {};
  const checkoutId = checkout.id;
  const amountCents = pi.amount_in_cents;

  // Customer data from Recurrente payload
  const customer = pi.customer || {};
  const customerEmail = customer.email || checkout.customer_email || '';
  const customerName = customer.full_name || checkout.customer_name || '';
  const paymentMethod = checkout.payment_method || {};
  const customerPhone = paymentMethod.phone_number || checkout.customer_phone || '';

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
  const productQuantities = pendingData?.product_quantities || {};
  const shippingCustomer = pendingData?.customer || {};

  const couponCode = pendingData?.coupon_code || null;

  // Build order record
  const order = {
    checkout_id: checkoutId,
    payment_id: pi.id,
    amount_cents: amountCents,
    items,
    product_ids: productIds,
    product_quantities: productQuantities,
    coupon_code: couponCode,
    customer: {
      name: customerName || shippingCustomer.name || '',
      email: customerEmail,
      phone: customerPhone || shippingCustomer.phone || '',
      address: shippingCustomer.address || '',
      notes: shippingCustomer.notes || '',
    },
    payment_method: 'tarjeta',
    receipt_number: pi.receipt_number || null,
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

  // Email to Diego (via tiendaventus.com domain — already verified in Resend)
  if (env.RESEND_API_KEY) {
    tasks.push(
      sendDiegoAlert(env, order)
        .catch(err => console.error('Diego alert failed:', err))
    );
  }

  // WhatsApp confirmation to customer via ManyChat
  // Use any available phone: from pending data, Recurrente payload, or payment method
  const mcPhone = order.customer.phone || customerPhone;
  if (env.MANYCHAT_API_KEY && mcPhone) {
    // Ensure order has phone for ManyChat function
    order.customer.phone = mcPhone;
    tasks.push(
      sendManyChatConfirmation(env, order)
        .catch(err => console.error('ManyChat confirmation failed:', err))
    );
  } else {
    console.log(`ManyChat skipped: key=${!!env.MANYCHAT_API_KEY}, phone=${mcPhone || 'none'}`);
  }

  // Update stock on GitHub (quantity-aware)
  if (productIds.length > 0 && env.GITHUB_TOKEN) {
    tasks.push(
      updateStock(env, productIds, productQuantities)
        .catch(err => console.error('Stock update failed:', err))
    );
  }

  // Increment coupon usage
  if (couponCode) {
    tasks.push(
      incrementCouponUsage(env, couponCode)
        .catch(err => console.error('Coupon usage increment failed:', err))
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
    .map(i => `${i.name} x${i.quantity} — Q${(i.amount_in_cents * i.quantity) / 100}`)
    .join('\n');

  // Build WhatsApp confirmation link for customer
  const customerPhone = (order.customer.phone || '').replace(/\D/g, '');
  const customerFirst = (order.customer.name || 'cliente').split(' ')[0];
  const waMessage = `Hola ${customerFirst}! Soy Diego de El Club. Tu pago de Q${order.amount_cents / 100} fue confirmado. Ya estoy preparando tu pedido. Te aviso cuando esté listo para entrega.`;
  const waLink = customerPhone
    ? `https://wa.me/${customerPhone}?text=${encodeURIComponent(waMessage)}`
    : '(sin teléfono)';

  const html = `
<div style="font-family: -apple-system, sans-serif; max-width: 520px; margin: 0 auto; color: #333;">
  <h2 style="margin: 0 0 4px; color: #111;">NUEVA VENTA — El Club</h2>
  <p style="margin: 0 0 16px; font-size: 14px; font-weight: 700; color: ${order.payment_method === 'contra_entrega' ? '#e67e22' : '#27ae60'};">${order.payment_method === 'contra_entrega' ? 'CONTRA ENTREGA — PENDIENTE DE COBRO' : 'PAGADO CON TARJETA'}</p>

  <div style="background: #f4f4f4; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
    <p style="margin: 0 0 8px; font-size: 14px; white-space: pre-line;">${itemLines}</p>
    <p style="margin: 0; font-size: 18px; font-weight: 700;">Total: Q${order.amount_cents / 100}</p>
  </div>

  <table style="font-size: 14px; border-collapse: collapse; width: 100%; margin-bottom: 16px;">
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Cliente</td><td style="padding: 4px 0;">${order.customer.name}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Email</td><td style="padding: 4px 0;">${order.customer.email}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Teléfono</td><td style="padding: 4px 0;">${order.customer.phone || '(no proporcionado)'}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Dirección</td><td style="padding: 4px 0;">${order.customer.address || '(coordinar por WA)'}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Referencia</td><td style="padding: 4px 0;">${order.customer.reference || order.customer.notes || '(ninguna)'}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Recibo</td><td style="padding: 4px 0;">${order.receipt_number || order.checkout_id}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Pago</td><td style="padding: 4px 0; font-weight: 700;">${order.payment_method === 'contra_entrega' ? 'Contra entrega' : 'Tarjeta (Recurrente)'}</td></tr>
  </table>

  ${customerPhone ? `<a href="${waLink}" style="display: inline-block; background: #25D366; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; font-size: 14px;">Confirmar por WhatsApp</a>` : '<p style="color: #c00;">Sin teléfono — confirmar por email</p>'}

  <p style="color: #aaa; font-size: 12px; margin-top: 24px;">Checkout: ${order.checkout_id} · ${order.paid_at}</p>
</div>`;

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'El Club Bot <noreply@tiendaventus.com>',
      to: diegoEmail,
      subject: `${order.payment_method === 'contra_entrega' ? 'CE' : 'PAGADO'} Q${order.amount_cents / 100} — ${order.customer.name || 'Cliente'}`,
      html,
    }),
  });

  console.log(`Diego alert sent for ${order.checkout_id}`);
}

// ── Stock update via GitHub API ──────────────────────────────

async function updateStock(env, productIds, productQuantities = {}) {
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

  // 2. Decrement stock for each product ID sold (quantity-aware)
  let changed = false;
  for (const pid of productIds) {
    const product = products.find(p => p.id === pid);
    if (!product) {
      console.log(`Product ${pid} not found in products.json`);
      continue;
    }

    const qty = productQuantities[pid] || 1;
    const prevStock = product.stock;
    product.stock = Math.max(0, product.stock - qty);

    if (product.stock !== prevStock) {
      changed = true;
      console.log(`Stock updated: ${pid} ${prevStock} → ${product.stock} (sold ${qty})`);
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
      message: `stock: ${productIds.map(pid => `${pid} x${productQuantities[pid] || 1}`).join(', ')} vendido (webhook)`,
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

// ── Coupon: Validate ─────────────────────────────────────────

async function handleCouponValidate(url, env) {
  const code = (url.searchParams.get('code') || '').trim().toUpperCase();

  if (!code) {
    return { valid: false, reason: 'Ingresá un código' };
  }

  const raw = await env.DATA.get(`coupon:${code}`);
  if (!raw) {
    return { valid: false, reason: 'Código no válido' };
  }

  const coupon = JSON.parse(raw);

  if (!coupon.active) {
    return { valid: false, reason: 'Código inactivo' };
  }

  if (coupon.expires_at && new Date(coupon.expires_at) < new Date()) {
    return { valid: false, reason: 'Código expirado' };
  }

  if (typeof coupon.max_uses === 'number' && coupon.used >= coupon.max_uses) {
    return { valid: false, reason: 'Código agotado' };
  }

  return { valid: true, code: coupon.code, type: coupon.type, value: coupon.value };
}

// ── Coupon: Admin Create ─────────────────────────────────────

function nonEmpty(v) { return typeof v === 'string' && v.trim().length > 0; }

async function handleCouponAdmin(request, env) {
  // Auth check
  const adminKey = request.headers.get('X-Admin-Key');
  if (!env.ADMIN_KEY || adminKey !== env.ADMIN_KEY) {
    return { _status: 401, error: 'Unauthorized' };
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return { _status: 400, error: 'JSON inválido' };
  }

  const code = (body.code || '').trim().toUpperCase();
  if (!code || code.length < 3) {
    return { _status: 400, error: 'Código debe tener al menos 3 caracteres' };
  }

  const type = (body.type || 'percent').toLowerCase();
  if (!['percent', 'fixed', 'vault_ff'].includes(type)) {
    return { _status: 400, error: 'Tipo debe ser "percent", "fixed" o "vault_ff"' };
  }

  const value = Number(body.value);
  if (!Number.isFinite(value) || value <= 0) {
    return { _status: 400, error: 'Valor debe ser un número positivo' };
  }

  const maxUses = Number(body.max_uses) || null;
  const expiresAt = body.expires_at || null;

  const couponData = {
    code,
    type,
    value,
    active: true,
    max_uses: maxUses,
    used: 0,
    expires_at: expiresAt,
    notes: nonEmpty(body.notes) ? body.notes.trim() : null,
    created_at: new Date().toISOString(),
  };

  // Calculate TTL if expiration is set
  const putOptions = {};
  if (expiresAt) {
    const ttl = Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000);
    if (ttl > 0) putOptions.expirationTtl = ttl;
  }

  await env.DATA.put(`coupon:${code}`, JSON.stringify(couponData), putOptions);

  console.log(`Admin coupon created: ${code} (${type} ${value}) max_uses=${maxUses}`);

  return couponData;
}

// ── Coupon: Increment usage after payment ────────────────────

async function incrementCouponUsage(env, couponCode) {
  if (!couponCode) return;

  const code = couponCode.trim().toUpperCase();
  const raw = await env.DATA.get(`coupon:${code}`);
  if (!raw) return;

  const coupon = JSON.parse(raw);
  coupon.used = (coupon.used || 0) + 1;

  // Preserve original TTL by re-calculating from expires_at
  const putOptions = {};
  if (coupon.expires_at) {
    const ttl = Math.floor((new Date(coupon.expires_at).getTime() - Date.now()) / 1000);
    if (ttl > 0) putOptions.expirationTtl = ttl;
  }

  await env.DATA.put(`coupon:${code}`, JSON.stringify(coupon), putOptions);

  console.log(`Coupon ${code} usage incremented to ${coupon.used}`);
}

// ── ManyChat: WhatsApp order confirmation ────────────────────

const MC_BASE = 'https://api.manychat.com/fb';
const MC_TAG_ORDEN_CONFIRMADA = 84300143;
const MC_TAG_CONFIRMACION_ENVIADA = 84300145;
const MC_FIELD_ORDER_NUMBER = 14431602;
const MC_FIELD_ORDER_TOTAL = 14431603;

async function mcApi(env, method, endpoint, body) {
  const res = await fetch(`${MC_BASE}${endpoint}`, {
    method,
    headers: {
      'Authorization': `Bearer ${env.MANYCHAT_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

async function sendManyChatConfirmation(env, order) {
  const phone = (order.customer.phone || '').replace(/\D/g, '');
  if (!phone || phone.length < 8) {
    console.log('ManyChat: no valid phone, skipping');
    return;
  }

  // Format phone with country code
  const fullPhone = phone.startsWith('502') ? `+${phone}` : `+502${phone}`;

  // 1. Find or create subscriber by phone (try phone first, then whatsapp_phone)
  let subscriberId;
  let found = await mcApi(env, 'GET', `/subscriber/findBySystemField?phone=${encodeURIComponent(fullPhone)}`);
  if (found.status !== 'success' || !found.data?.id) {
    found = await mcApi(env, 'GET', `/subscriber/findBySystemField?whatsapp_phone=${encodeURIComponent(fullPhone)}`);
  }

  if (found.status === 'success' && found.data?.id) {
    subscriberId = found.data.id;
    console.log(`ManyChat: found subscriber ${subscriberId} for ${fullPhone}`);
  } else {
    // Create new subscriber with WhatsApp opt-in
    const created = await mcApi(env, 'POST', '/subscriber/createSubscriber', {
      phone: fullPhone,
      whatsapp_phone: fullPhone,
      first_name: order.customer.name?.split(' ')[0] || '',
      last_name: order.customer.name?.split(' ').slice(1).join(' ') || '',
      email: order.customer.email || undefined,
      has_opt_in_sms: true,
      has_opt_in_email: !!order.customer.email,
      consent_phrase: 'Checkout El Club',
    });
    console.log('ManyChat createSubscriber response:', JSON.stringify(created));

    if (created.status === 'success' && created.data?.id) {
      subscriberId = created.data.id;
      console.log(`ManyChat: created subscriber ${subscriberId} for ${fullPhone}`);
    } else {
      console.error('ManyChat: failed to create subscriber', JSON.stringify(created));
      return;
    }
  }

  // 2. Set custom fields: order_number, order_total
  const orderNum = order.receipt_number || order.checkout_id || 'N/A';
  const orderTotal = order.amount_cents ? String(order.amount_cents / 100) : '0';

  await mcApi(env, 'POST', '/subscriber/setCustomField', {
    subscriber_id: subscriberId,
    field_id: MC_FIELD_ORDER_NUMBER,
    field_value: orderNum,
  });

  await mcApi(env, 'POST', '/subscriber/setCustomField', {
    subscriber_id: subscriberId,
    field_id: MC_FIELD_ORDER_TOTAL,
    field_value: orderTotal,
  });

  console.log(`ManyChat: set fields — order=${orderNum}, total=Q${orderTotal}`);

  // 3. Remove "confirmacion_enviada" tag (in case of repeat purchase)
  await mcApi(env, 'POST', '/subscriber/removeTag', {
    subscriber_id: subscriberId,
    tag_id: MC_TAG_CONFIRMACION_ENVIADA,
  });

  // 4. Apply "orden_confirmada" tag → triggers ManyChat WhatsApp flow
  const tagResult = await mcApi(env, 'POST', '/subscriber/addTag', {
    subscriber_id: subscriberId,
    tag_id: MC_TAG_ORDEN_CONFIRMADA,
  });

  if (tagResult.status === 'success') {
    console.log(`ManyChat: tag orden_confirmada applied to ${subscriberId} — flow should trigger`);
  } else {
    console.error('ManyChat: failed to apply tag', JSON.stringify(tagResult));
  }
}

// ── Custom Order (made-to-order jerseys) ────────────────────

async function sendCustomOrderAlert(env, order) {
  const diegoEmail = env.DIEGO_EMAIL;
  if (!diegoEmail) {
    console.log('DIEGO_EMAIL not configured, skipping custom order alert');
    return;
  }

  const isWorldCup = order.source === 'mundial';
  const badge = isWorldCup ? 'MUNDIAL 2026' : 'PEDIDO CUSTOM';
  const badgeColor = isWorldCup ? '#c9a96e' : '#4DA8FF';

  const dorsalLine = order.dorsal?.enabled
    ? `${order.dorsal.name || ''} #${order.dorsal.number || ''}`.trim()
    : 'Sin dorsal';

  const patchLine = order.patches > 0
    ? 'Con parches (Q15)'
    : 'Sin parches';

  const customerPhone = (order.customer.whatsapp || '').replace(/\D/g, '');
  const customerFirst = (order.customer.name || 'cliente').split(' ')[0];
  const waMessage = `Hola ${customerFirst}! Soy Diego de El Club. Recibí tu pedido ${order.order_code} de la camiseta de ${order.team} (${order.version}). Te confirmo disponibilidad y coordino el pago. Cualquier duda me avisás!`;
  const waLink = customerPhone
    ? `https://wa.me/${customerPhone}?text=${encodeURIComponent(waMessage)}`
    : '(sin teléfono)';

  const html = `
<div style="font-family: -apple-system, sans-serif; max-width: 520px; margin: 0 auto; color: #333;">
  <h2 style="margin: 0 0 4px; color: #111;">${badge} — ${order.order_code}</h2>
  <p style="margin: 0 0 16px; font-size: 14px; font-weight: 700; color: ${badgeColor};">PEDIDO PERSONALIZADO — PENDIENTE DE CONTACTO</p>

  <div style="background: #f4f4f4; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
    <p style="margin: 0 0 4px; font-size: 16px; font-weight: 700;">${order.team} — ${order.version}</p>
    ${order.league ? `<p style="margin: 0 0 4px; font-size: 13px; color: #666;">${order.league}${order.season ? ' · ' + order.season : ''}</p>` : ''}
    <p style="margin: 0 0 4px; font-size: 13px; color: #666;">Talla: ${order.size} · ${dorsalLine}</p>
    <p style="margin: 0 0 4px; font-size: 13px; color: #666;">${patchLine}</p>
    <p style="margin: 8px 0 0; font-size: 20px; font-weight: 700;">Total: Q${order.price.total}</p>
  </div>

  <table style="font-size: 14px; border-collapse: collapse; width: 100%; margin-bottom: 16px;">
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Cliente</td><td style="padding: 4px 0;">${order.customer.name}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">WhatsApp</td><td style="padding: 4px 0;">${order.customer.whatsapp || '(no proporcionado)'}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Zona</td><td style="padding: 4px 0;">${order.customer.zone || '(no especificada)'}</td></tr>
    <tr><td style="padding: 4px 8px 4px 0; color: #888;">Notas</td><td style="padding: 4px 0;">${order.customer.notes || '(ninguna)'}</td></tr>
  </table>

  <div style="margin-bottom: 16px;">
    <p style="font-size: 13px; color: #888; margin: 0 0 8px;">Desglose:</p>
    <table style="font-size: 13px; border-collapse: collapse;">
      <tr><td style="padding: 2px 12px 2px 0;">Camiseta base</td><td>Q${order.price.base}</td></tr>
      ${order.price.dorsal ? `<tr><td style="padding: 2px 12px 2px 0;">Dorsal</td><td>Q${order.price.dorsal}</td></tr>` : ''}
      ${order.price.patches ? `<tr><td style="padding: 2px 12px 2px 0;">Parches ×${order.patches}</td><td>Q${order.price.patches}</td></tr>` : ''}
    </table>
  </div>

  ${customerPhone ? `<a href="${waLink}" style="display: inline-block; background: #25D366; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; font-size: 14px;">Contactar por WhatsApp</a>` : '<p style="color: #c00;">Sin WhatsApp — revisar</p>'}

  <p style="color: #aaa; font-size: 12px; margin-top: 24px;">Orden: ${order.order_code} · ${order.created_at}</p>
</div>`;

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'El Club Bot <noreply@tiendaventus.com>',
      to: diegoEmail,
      subject: `${isWorldCup ? 'WC' : 'CUSTOM'} Q${order.price.total} — ${order.team} — ${order.customer.name || 'Cliente'}`,
      html,
    }),
  });

  console.log(`Custom order alert sent for ${order.order_code}`);
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

      // ── Custom jersey order (from builder) ──
      if (url.pathname === '/api/order/custom' && request.method === 'POST') {
        let data;
        try { data = await request.json(); } catch {
          return json({ error: 'JSON invalido' }, 400, cors);
        }

        // Validate required fields
        if (!data.team) return json({ error: 'Equipo requerido' }, 400, cors);
        if (!data.size) return json({ error: 'Talla requerida' }, 400, cors);
        if (!data.version) return json({ error: 'Versión requerida' }, 400, cors);
        if (!data.customer?.name) return json({ error: 'Nombre requerido' }, 400, cors);
        if (!data.customer?.whatsapp) return json({ error: 'WhatsApp requerido' }, 400, cors);
        if (!data.price?.total) return json({ error: 'Precio requerido' }, 400, cors);

        // Generate sequential order code
        const isWorldCup = data.source === 'mundial';
        const prefix = isWorldCup ? 'WC' : 'EC';
        const counterKey = `counter:custom_orders_${prefix.toLowerCase()}`;
        const currentCount = parseInt(await env.DATA.get(counterKey) || '0', 10);
        const nextCount = currentCount + 1;
        await env.DATA.put(counterKey, String(nextCount));
        const orderCode = `${prefix}-${String(nextCount).padStart(4, '0')}`;

        const order = {
          order_code: orderCode,
          type: 'custom',
          source: data.source || 'club',
          team: data.team,
          league: data.league || null,
          season: data.season || null,
          version: data.version,
          dorsal: data.dorsal || { enabled: false },
          patches: data.patches || 0,
          size: data.size,
          price: data.price,
          customer: {
            name: data.customer.name,
            whatsapp: data.customer.whatsapp,
            zone: data.customer.zone || '',
            notes: data.customer.notes || '',
          },
          status: 'pending',
          created_at: new Date().toISOString(),
        };

        // Store in KV (90 days)
        await env.DATA.put(`order:${orderCode}`, JSON.stringify(order), { expirationTtl: 7776000 });

        // Also store in a list index for admin queries
        const indexKey = 'index:custom_orders';
        const existingIndex = JSON.parse(await env.DATA.get(indexKey) || '[]');
        existingIndex.push({ code: orderCode, created_at: order.created_at, status: 'pending' });
        await env.DATA.put(indexKey, JSON.stringify(existingIndex));

        // Send email alert to Diego
        if (env.RESEND_API_KEY) {
          await sendCustomOrderAlert(env, order).catch(err => console.error('Custom alert failed:', err));
        }

        console.log(`Custom order created: ${orderCode} — ${order.team} — Q${order.price.total}`);
        return json({ order_code: orderCode, created_at: order.created_at }, 200, cors);
      }

      // ── List custom orders (admin) ──
      if (url.pathname === '/api/orders' && request.method === 'GET') {
        const adminKey = request.headers.get('X-Admin-Key');
        if (!adminKey || adminKey !== env.ADMIN_KEY) {
          return json({ error: 'Unauthorized' }, 401, cors);
        }

        const statusFilter = url.searchParams.get('status');
        const index = JSON.parse(await env.DATA.get('index:custom_orders') || '[]');

        // Fetch full order data for each
        const orders = [];
        for (const entry of index) {
          if (statusFilter && entry.status !== statusFilter) continue;
          const raw = await env.DATA.get(`order:${entry.code}`);
          if (raw) orders.push(JSON.parse(raw));
        }

        // Sort newest first
        orders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        return json({ orders, total: orders.length }, 200, cors);
      }

      // ── Update order status (admin) ──
      if (url.pathname.startsWith('/api/order/') && request.method === 'PATCH') {
        const adminKey = request.headers.get('X-Admin-Key');
        if (!adminKey || adminKey !== env.ADMIN_KEY) {
          return json({ error: 'Unauthorized' }, 401, cors);
        }

        const orderCode = url.pathname.replace('/api/order/', '');
        if (!orderCode) return json({ error: 'Código requerido' }, 400, cors);

        const raw = await env.DATA.get(`order:${orderCode}`);
        if (!raw) return json({ error: 'Orden no encontrada' }, 404, cors);

        let updates;
        try { updates = await request.json(); } catch {
          return json({ error: 'JSON invalido' }, 400, cors);
        }

        const validStatuses = ['pending', 'contacted', 'paid', 'shipped', 'delivered', 'cancelled'];
        if (updates.status && !validStatuses.includes(updates.status)) {
          return json({ error: `Status invalido. Válidos: ${validStatuses.join(', ')}` }, 400, cors);
        }

        const order = JSON.parse(raw);
        if (updates.status) order.status = updates.status;
        if (updates.notes) order.admin_notes = updates.notes;
        order.updated_at = new Date().toISOString();

        await env.DATA.put(`order:${orderCode}`, JSON.stringify(order), { expirationTtl: 7776000 });

        // Update index too
        const index = JSON.parse(await env.DATA.get('index:custom_orders') || '[]');
        const idx = index.findIndex(e => e.code === orderCode);
        if (idx >= 0) {
          index[idx].status = order.status;
          await env.DATA.put('index:custom_orders', JSON.stringify(index));
        }

        return json({ order_code: orderCode, status: order.status, updated_at: order.updated_at }, 200, cors);
      }

      // Cash on delivery order
      if (url.pathname === '/api/order/cod' && request.method === 'POST') {
        let data;
        try { data = await request.json(); } catch {
          return json({ error: 'JSON invalido' }, 400, cors);
        }

        if (!data.items || !data.items.length) {
          return json({ error: 'Se requiere al menos un producto' }, 400, cors);
        }

        // Generate order number
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let orderCode = 'CE-';
        for (let i = 0; i < 4; i++) orderCode += chars[Math.floor(Math.random() * chars.length)];

        const totalCents = data.items.reduce((sum, i) => sum + (i.amount_in_cents * i.quantity), 0);

        const order = {
          checkout_id: orderCode,
          payment_id: null,
          payment_method: 'contra_entrega',
          amount_cents: totalCents,
          items: data.items,
          product_ids: data.product_ids || [],
          product_quantities: data.product_quantities || {},
          coupon_code: data.coupon_code || null,
          customer: data.customer || {},
          receipt_number: orderCode,
          paid_at: null,
          created_at: new Date().toISOString(),
        };

        // Store order in KV (90 days)
        await env.DATA.put(`order:${orderCode}`, JSON.stringify(order), { expirationTtl: 7776000 });

        // Run tasks in parallel
        const tasks = [];

        // Email to Diego
        if (env.RESEND_API_KEY) {
          tasks.push(sendDiegoAlert(env, order).catch(err => console.error('Diego alert failed:', err)));
        }

        // WhatsApp confirmation to customer via ManyChat
        if (env.MANYCHAT_API_KEY && order.customer.phone) {
          tasks.push(sendManyChatConfirmation(env, order).catch(err => console.error('ManyChat failed:', err)));
        }

        // Reserve stock on GitHub
        if (data.product_ids?.length > 0 && env.GITHUB_TOKEN) {
          tasks.push(updateStock(env, data.product_ids, data.product_quantities).catch(err => console.error('Stock failed:', err)));
        }

        await Promise.allSettled(tasks);

        console.log(`COD order created: ${orderCode} — Q${totalCents / 100}`);
        return json({ order_id: orderCode, status: 'reserved' }, 200, cors);
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

      // Get order by checkout ID (public — no sensitive data exposed)
      if (url.pathname.startsWith('/api/order/') && request.method === 'GET') {
        const orderId = url.pathname.replace('/api/order/', '');
        if (!orderId) return json({ error: 'ID requerido' }, 400, cors);

        const raw = await env.DATA.get(`order:${orderId}`);
        if (!raw) return json({ error: 'Orden no encontrada' }, 404, cors);

        const order = JSON.parse(raw);
        // Return only customer-safe fields
        return json({
          checkout_id: order.checkout_id,
          items: (order.items || []).map(i => ({
            name: i.name,
            quantity: i.quantity,
            amount: i.amount_in_cents ? i.amount_in_cents / 100 : 0
          })),
          total: order.amount_cents ? order.amount_cents / 100 : 0,
          receipt_number: order.receipt_number || null,
          customer_name: order.customer?.name || '',
          paid_at: order.paid_at,
        }, 200, cors);
      }

      // Validate coupon
      if (url.pathname === '/api/coupons/validate' && request.method === 'GET') {
        const result = await handleCouponValidate(url, env);
        return json(result, 200, cors);
      }

      // Admin: create coupon
      if (url.pathname === '/api/coupons/admin' && request.method === 'POST') {
        const result = await handleCouponAdmin(request, env);
        const status = result._status || 200;
        if (result._status) delete result._status;
        return json(result, status, cors);
      }

      // Recurrente webhook (Svix)
      if (url.pathname === '/webhook/recurrente' && request.method === 'POST') {
        return await handleWebhook(request, env);
      }

      // ── Vault reservation (public — called by checkout form) ─────
      if (url.pathname === '/api/vault/reservation' && request.method === 'POST') {
        return await handleVaultReservation(request, env);
      }

      // ── DEBUG auth gate (temporary, all /__debug/* endpoints behind this) ──
      if (url.pathname.startsWith('/__debug/')) {
        const adminKey = request.headers.get('X-Admin-Key');
        if (!env.ADMIN_KEY || adminKey !== env.ADMIN_KEY) {
          return new Response(
            JSON.stringify({ error: 'Unauthorized — debug endpoints require X-Admin-Key' }),
            { status: 401, headers: { 'Content-Type': 'application/json' } }
          );
        }
      }

      // ── DEBUG: state machine validator (temporary, remove before deploy) ──
      if (url.pathname === '/__debug/validate-transition' && request.method === 'GET') {
        const current = url.searchParams.get('current');
        const target  = url.searchParams.get('target');
        const axis    = url.searchParams.get('axis');
        if (!current || !target || !axis) {
          return new Response(
            JSON.stringify({ error: 'Params requeridos: current, target, axis' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } }
          );
        }
        const result = validateTransition(current, target, axis);
        return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
      }

      // ── DEBUG: storage round-trip (temporary, remove before deploy) ──
      if (url.pathname === '/__debug/save-lead' && request.method === 'POST') {
        const data = await request.json();
        const result = await saveLead(env, data);
        return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/__debug/find-lead' && request.method === 'GET') {
        const ref = url.searchParams.get('ref');
        if (!ref) {
          return new Response(JSON.stringify({ error: 'Param requerido: ref' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
        }
        const result = await findLeadByRef(env, ref);
        return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/__debug/update-status' && request.method === 'POST') {
        const { ref, axis, new_status, note } = await request.json();
        if (!ref || !axis || !new_status) {
          return new Response(JSON.stringify({ error: 'Body requiere: ref, axis, new_status' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
        }
        const result = await updateLeadStatus(env, ref, axis, new_status, note);
        return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/__debug/list-leads' && request.method === 'GET') {
        const paymentStatuses = url.searchParams.get('payment_status')?.split(',').filter(Boolean) || null;
        const fulfillmentStatuses = url.searchParams.get('fulfillment_status')?.split(',').filter(Boolean) || null;
        const hasCouponParam = url.searchParams.get('has_coupon');
        const hasCoupon = hasCouponParam === 'true' ? true : hasCouponParam === 'false' ? false : null;
        const limit = Number(url.searchParams.get('limit')) || 50;
        const result = await listLeads(env, { limit, paymentStatuses, fulfillmentStatuses, hasCoupon });
        return new Response(JSON.stringify({ count: result.length, leads: result }), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/__debug/get-lead-with-history' && request.method === 'GET') {
        const ref = url.searchParams.get('ref');
        if (!ref) {
          return new Response(JSON.stringify({ error: 'Param requerido: ref' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
        }
        const result = await getLeadWithHistory(env, ref);
        return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/__debug/create-reservation-checkout' && request.method === 'POST') {
        const { vault_ref, customer_name } = await request.json();
        if (!vault_ref || !customer_name) {
          return new Response(JSON.stringify({ error: 'Body requiere: vault_ref, customer_name' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
        }
        try {
          const result = await createReservationCheckout(env, vault_ref, customer_name);
          return new Response(JSON.stringify(result), { headers: { 'Content-Type': 'application/json' } });
        } catch (err) {
          return new Response(JSON.stringify({ error: String(err.message || err) }), { status: 500, headers: { 'Content-Type': 'application/json' } });
        }
      }

      return new Response('Not Found', { status: 404 });

    } catch (error) {
      console.error('Worker error:', error);
      return json({ error: error.message }, 500, cors);
    }
  },
};
