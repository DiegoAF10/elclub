/**
 * El Club — Checkout Wizard
 * 3-step checkout: Resumen → Envío → Pago
 *
 * Payment options:
 *   1. Tarjeta (Recurrente) — calls Worker API → redirects to Recurrente checkout
 *   2. Contra entrega — sends WhatsApp with order + payment method
 */

// ── Config ──
var SHIPPING_COST = 25;
var SHIPPING_KEY = 'elclub_shipping';
var currentStep = 1;

// Worker URL for Recurrente checkout sessions
var ELCLUB_API_URL = 'https://elclub-backoffice.ventusgt.workers.dev';

// ── Step Navigation ──
function goToStep(step) {
  if (step < 1 || step > 3) return;

  if (step === 2 && currentStep === 1) {
    var totals = getCartTotals();
    if (totals.count === 0) return;
  }
  if (step === 3 && currentStep === 2) {
    if (!validateShippingForm()) return;
    saveShippingData();
  }

  currentStep = step;

  for (var i = 1; i <= 3; i++) {
    var panel = document.getElementById('step-' + i);
    if (panel) panel.classList.toggle('hidden', i !== step);
  }

  updateProgressBar();

  if (step === 1) renderStep1();
  if (step === 3) renderStep3();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateProgressBar() {
  for (var i = 1; i <= 3; i++) {
    var stepEl = document.getElementById('progress-step-' + i);
    var lineEl = document.getElementById('progress-line-' + i);
    if (!stepEl) continue;

    stepEl.classList.remove('active', 'completed');
    if (i < currentStep) {
      stepEl.classList.add('completed');
    } else if (i === currentStep) {
      stepEl.classList.add('active');
    }

    if (lineEl) {
      lineEl.classList.toggle('completed', i < currentStep);
    }
  }
}

// ── Step 1: Order Summary ──
function renderStep1() {
  var container = document.getElementById('order-items');
  var subtotalEl = document.getElementById('order-subtotal');
  var shippingEl = document.getElementById('order-shipping');
  var totalEl = document.getElementById('order-total');
  var emptyEl = document.getElementById('order-empty');
  var filledEl = document.getElementById('order-filled');
  if (!container) return;

  var totals = getCartTotals();

  if (totals.count === 0) {
    if (emptyEl) emptyEl.classList.remove('hidden');
    if (filledEl) filledEl.classList.add('hidden');
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');
  if (filledEl) filledEl.classList.remove('hidden');

  var html = '';
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    html += '<div class="flex gap-4 py-4 border-b border-chalk">' +
      '<div class="w-20 h-20 bg-pitch rounded overflow-hidden flex-shrink-0">' +
        '<img src="' + (item.image || '/assets/img/products/placeholder.svg') + '" alt="' + item.name + '" class="w-full h-full object-cover">' +
      '</div>' +
      '<div class="flex-1 min-w-0">' +
        '<p class="text-sm font-bold text-white truncate">' + item.name + '</p>' +
        '<p class="text-xs text-smoke mt-0.5">Talla: ' + item.size + '</p>' +
        '<p class="text-sm font-bold text-ice mt-1">Q' + item.price + '</p>' +
        '<div class="flex items-center gap-2 mt-2">' +
          '<button onclick="updateQuantity(\'' + item.key + '\', ' + (item.quantity - 1) + '); renderStep1();" class="w-7 h-7 border border-chalk rounded flex items-center justify-center text-sm cursor-pointer hover:border-ice text-smoke hover:text-white transition-colors">-</button>' +
          '<span class="text-sm font-semibold w-6 text-center">' + item.quantity + '</span>' +
          '<button onclick="updateQuantity(\'' + item.key + '\', ' + (item.quantity + 1) + '); renderStep1();" class="w-7 h-7 border border-chalk rounded flex items-center justify-center text-sm cursor-pointer hover:border-ice text-smoke hover:text-white transition-colors">+</button>' +
          '<button onclick="removeFromCart(\'' + item.key + '\'); renderStep1();" class="ml-auto text-xs text-ash hover:text-ice cursor-pointer uppercase tracking-wider font-semibold">Quitar</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }
  container.innerHTML = html;

  if (subtotalEl) subtotalEl.textContent = 'Q' + totals.subtotal;
  if (shippingEl) shippingEl.textContent = 'Q' + SHIPPING_COST;
  if (totalEl) totalEl.textContent = 'Q' + (totals.total + SHIPPING_COST);
}

// ── Step 2: Shipping Form ──
function validateShippingForm() {
  var fields = ['shipping-name', 'shipping-email', 'shipping-phone', 'shipping-address'];
  var valid = true;

  for (var i = 0; i < fields.length; i++) {
    var input = document.getElementById(fields[i]);
    var error = document.getElementById(fields[i] + '-error');
    if (!input) continue;

    var val = input.value.trim();
    var hasError = false;

    if (!val) {
      hasError = true;
    } else if (fields[i] === 'shipping-phone' && !/^\d{8}$/.test(val.replace(/\s/g, ''))) {
      hasError = true;
    } else if (fields[i] === 'shipping-email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
      hasError = true;
    }

    if (hasError) {
      input.classList.add('border-red-500');
      input.classList.remove('border-chalk');
      if (error) error.classList.remove('hidden');
      valid = false;
    } else {
      input.classList.remove('border-red-500');
      input.classList.add('border-chalk');
      if (error) error.classList.add('hidden');
    }
  }
  return valid;
}

function saveShippingData() {
  var data = {
    name: document.getElementById('shipping-name').value.trim(),
    email: (document.getElementById('shipping-email') || {}).value ? document.getElementById('shipping-email').value.trim() : '',
    phone: document.getElementById('shipping-phone').value.trim(),
    address: document.getElementById('shipping-address').value.trim(),
    notes: (document.getElementById('shipping-notes') || {}).value || ''
  };
  localStorage.setItem(SHIPPING_KEY, JSON.stringify(data));
}

function loadShippingData() {
  try {
    var raw = localStorage.getItem(SHIPPING_KEY);
    if (!raw) return;
    var data = JSON.parse(raw);
    var nameEl = document.getElementById('shipping-name');
    var emailEl = document.getElementById('shipping-email');
    var phoneEl = document.getElementById('shipping-phone');
    var addressEl = document.getElementById('shipping-address');
    var notesEl = document.getElementById('shipping-notes');
    if (nameEl && data.name) nameEl.value = data.name;
    if (emailEl && data.email) emailEl.value = data.email;
    if (phoneEl && data.phone) phoneEl.value = data.phone;
    if (addressEl && data.address) addressEl.value = data.address;
    if (notesEl && data.notes) notesEl.value = data.notes;
  } catch (e) {}
}

// ── Step 3: Payment ──
function renderStep3() {
  var summaryEl = document.getElementById('payment-summary');
  var totalEl = document.getElementById('payment-total');
  if (!summaryEl) return;

  var totals = getCartTotals();
  var shipping = JSON.parse(localStorage.getItem(SHIPPING_KEY) || '{}');

  var html = '<div class="space-y-2">';
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    html += '<div class="flex justify-between text-sm">' +
      '<span class="text-smoke">' + item.name + ' (' + item.size + ') x' + item.quantity + '</span>' +
      '<span class="text-white font-semibold">Q' + (item.price * item.quantity) + '</span>' +
    '</div>';
  }
  html += '<div class="flex justify-between text-sm border-t border-chalk pt-2 mt-2">' +
    '<span class="text-smoke">Envío</span><span class="text-white font-semibold">Q' + SHIPPING_COST + '</span></div>';
  html += '</div>';

  html += '<div class="mt-4 pt-4 border-t border-chalk">' +
    '<p class="text-xs text-smoke mb-1">Enviar a:</p>' +
    '<p class="text-sm text-white font-semibold">' + (shipping.name || '') + '</p>' +
    '<p class="text-xs text-smoke">' + (shipping.phone || '') + ' — ' + (shipping.address || '') + '</p>' +
    (shipping.notes ? '<p class="text-xs text-ash mt-1">Nota: ' + shipping.notes + '</p>' : '') +
  '</div>';

  summaryEl.innerHTML = html;

  var grandTotal = totals.total + SHIPPING_COST;
  if (totalEl) totalEl.textContent = 'Q' + grandTotal;
}

// ── Payment: Tarjeta (Recurrente) ──
function payWithCard() {
  if (!ELCLUB_API_URL) {
    // Worker not deployed yet — fall back to WhatsApp + Diego sends link
    sendOrderWhatsApp('tarjeta');
    return;
  }

  var totals = getCartTotals();
  if (totals.count === 0) return;

  var shipping = JSON.parse(localStorage.getItem(SHIPPING_KEY) || '{}');

  // Build Recurrente items + product IDs for stock tracking
  var items = [];
  var productIds = [];
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    items.push({
      name: item.name + ' (Talla ' + item.size + ')',
      amount_in_cents: item.price * 100,
      currency: 'GTQ',
      quantity: item.quantity
    });
    productIds.push(item.id);
  }

  // Add shipping as separate line item
  if (SHIPPING_COST > 0) {
    items.push({
      name: 'Envío',
      amount_in_cents: SHIPPING_COST * 100,
      currency: 'GTQ',
      quantity: 1
    });
  }

  // Show loading state
  var btn = document.getElementById('btn-pay-card');
  var btnText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Conectando...';
  }

  fetch(ELCLUB_API_URL + '/api/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      items: items,
      product_ids: productIds,
      customer: {
        name: shipping.name || '',
        email: shipping.email || '',
        phone: shipping.phone || '',
        address: shipping.address || '',
        notes: shipping.notes || ''
      }
    })
  })
  .then(function(res) { return res.json(); })
  .then(function(data) {
    if (data.checkout_url) {
      // Also send WhatsApp notification to Diego
      sendOrderWhatsApp('tarjeta', true);
      // Redirect to Recurrente checkout
      window.location.href = data.checkout_url;
    } else {
      throw new Error(data.error || 'Error al crear el checkout');
    }
  })
  .catch(function(err) {
    console.error('Checkout error:', err);
    // Restore button
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = btnText;
    }
    // Fall back to WhatsApp
    if (confirm('No se pudo conectar con el procesador de pago.\n\n¿Querés continuar por WhatsApp? Diego te enviará el link de pago.')) {
      sendOrderWhatsApp('tarjeta');
    }
  });
}

// ── Payment: Contra Entrega ──
function payContraEntrega() {
  sendOrderWhatsApp('contra_entrega');
}

// ── WhatsApp Order Message ──
function sendOrderWhatsApp(paymentMethod, silent) {
  var totals = getCartTotals();
  var shipping = JSON.parse(localStorage.getItem(SHIPPING_KEY) || '{}');
  if (totals.count === 0) return;

  var method = paymentMethod === 'tarjeta' ? '💳 TARJETA' : '🤝 CONTRA ENTREGA';

  var msg = '¡Hola! Quiero hacer un pedido en El Club:\n\n';
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    msg += '⚽ ' + item.name + ' (Talla ' + item.size + ') x' + item.quantity + ' — Q' + (item.price * item.quantity) + '\n';
  }
  msg += '\n💰 Subtotal: Q' + totals.total;
  msg += '\n🚚 Envío: Q' + SHIPPING_COST;
  msg += '\n✅ Total: Q' + (totals.total + SHIPPING_COST);
  msg += '\n\n📦 Datos de envío:';
  msg += '\n👤 ' + (shipping.name || 'No indicado');
  msg += '\n📱 ' + (shipping.phone || 'No indicado');
  msg += '\n📍 ' + (shipping.address || 'No indicado');
  if (shipping.notes) msg += '\n📝 ' + shipping.notes;
  msg += '\n\n' + method;

  if (paymentMethod === 'tarjeta') {
    msg += '\n(Esperando link de pago de Recurrente)';
  } else {
    msg += '\n(Pago al momento de la entrega)';
  }

  var url = 'https://wa.me/' + WHATSAPP_NUMBER + '?text=' + encodeURIComponent(msg);

  if (silent) {
    // Open in background (for card payments where we also redirect to Recurrente)
    var w = window.open(url, '_blank');
    if (w) setTimeout(function() { w.close(); }, 1000);
  } else {
    window.open(url, '_blank');
  }
}

// ── Inline validation on blur ──
function validateOnBlur(inputId) {
  var input = document.getElementById(inputId);
  var error = document.getElementById(inputId + '-error');
  if (!input) return;

  var val = input.value.trim();
  var hasError = false;

  if (!val) {
    hasError = true;
  } else if (inputId === 'shipping-phone' && !/^\d{8}$/.test(val.replace(/\s/g, ''))) {
    hasError = true;
  }

  if (hasError) {
    input.classList.add('border-red-500');
    input.classList.remove('border-chalk');
    if (error) error.classList.remove('hidden');
  } else {
    input.classList.remove('border-red-500');
    input.classList.add('border-chalk');
    if (error) error.classList.add('hidden');
  }
}

// ── Init ──
document.addEventListener('DOMContentLoaded', function() {
  renderStep1();
  loadShippingData();
  updateProgressBar();
});
