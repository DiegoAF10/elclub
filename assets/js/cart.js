/**
 * El Club Cart — localStorage-based shopping cart
 * Adapted from VENTUS cart.js pattern
 */

var CART_KEY = 'elclub_cart';
var CART_MAX_AGE = 7 * 24 * 60 * 60 * 1000; // 7 days

// WhatsApp number for orders (Guatemala format)
var WHATSAPP_NUMBER = '50212345678'; // TODO: Replace with Diego's actual number

// ── Read ──
function getCart() {
  try {
    var raw = localStorage.getItem(CART_KEY);
    if (!raw) return { items: [] };
    var cart = JSON.parse(raw);
    if (cart.updatedAt && (Date.now() - cart.updatedAt > CART_MAX_AGE)) {
      localStorage.removeItem(CART_KEY);
      return { items: [] };
    }
    return cart;
  } catch (e) {
    return { items: [] };
  }
}

// ── Write ──
function saveCart(cart) {
  cart.updatedAt = Date.now();
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartBadge();
  window.dispatchEvent(new CustomEvent('cartUpdated'));
}

// ── Add item ──
function addToCart(id, name, price, size, image) {
  var cart = getCart();
  var key = id + '-' + size;
  var existing = null;
  for (var i = 0; i < cart.items.length; i++) {
    if (cart.items[i].key === key) { existing = cart.items[i]; break; }
  }
  if (existing) {
    existing.quantity = Math.min(5, existing.quantity + 1);
  } else {
    cart.items.push({
      key: key,
      id: id,
      name: name,
      price: price,
      size: size,
      image: image,
      quantity: 1
    });
  }
  saveCart(cart);
  showCartToast(name, price, size);
}

// ── Remove item ──
function removeFromCart(key) {
  var cart = getCart();
  cart.items = cart.items.filter(function(i) { return i.key !== key; });
  saveCart(cart);
}

// ── Update quantity ──
function updateQuantity(key, qty) {
  var cart = getCart();
  for (var i = 0; i < cart.items.length; i++) {
    if (cart.items[i].key === key) {
      if (qty <= 0) {
        cart.items.splice(i, 1);
      } else {
        cart.items[i].quantity = Math.min(5, qty);
      }
      break;
    }
  }
  saveCart(cart);
}

// ── Clear ──
function clearCart() {
  localStorage.removeItem(CART_KEY);
  updateCartBadge();
  window.dispatchEvent(new CustomEvent('cartUpdated'));
}

// ── Totals ──
function getCartTotals() {
  var cart = getCart();
  var subtotal = 0;
  var count = 0;
  for (var i = 0; i < cart.items.length; i++) {
    subtotal += cart.items[i].price * cart.items[i].quantity;
    count += cart.items[i].quantity;
  }
  return {
    items: cart.items,
    subtotal: subtotal,
    count: count,
    shipping: 0, // Free shipping for now (included in price)
    total: subtotal
  };
}

function getCartCount() {
  var cart = getCart();
  var count = 0;
  for (var i = 0; i < cart.items.length; i++) {
    count += cart.items[i].quantity;
  }
  return count;
}

// ── Badge ──
function updateCartBadge() {
  var count = getCartCount();
  var badges = document.querySelectorAll('.cart-badge');
  for (var i = 0; i < badges.length; i++) {
    if (count > 0) {
      badges[i].textContent = count > 9 ? '9+' : count;
      badges[i].classList.remove('hidden');
    } else {
      badges[i].classList.add('hidden');
    }
  }
}

// ── Toast ──
function showCartToast(name, price, size) {
  var existing = document.getElementById('cart-toast');
  if (existing) {
    clearTimeout(existing._timer);
    existing.remove();
  }
  var count = getCartCount();
  var toast = document.createElement('div');
  toast.id = 'cart-toast';
  toast.className = 'fixed top-0 left-0 right-0 z-[70] transform -translate-y-full';
  toast.style.transition = 'transform 0.35s cubic-bezier(0.4,0,0.2,1)';
  toast.innerHTML =
    '<div class="bg-white shadow-lg border-b border-sand">' +
      '<div class="max-w-lg mx-auto px-4 py-3">' +
        '<div class="flex items-center gap-2 mb-2">' +
          '<div class="w-5 h-5 bg-success rounded-full flex items-center justify-center flex-shrink-0">' +
            '<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>' +
          '</div>' +
          '<p class="text-sm font-semibold flex-1">Agregado al carrito</p>' +
          '<button onclick="dismissCartToast()" class="text-gray-400 hover:text-gray-600 p-1 cursor-pointer">' +
            '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>' +
          '</button>' +
        '</div>' +
        '<p class="text-sm text-warm">' + name + ' — Talla ' + size + ' — Q' + price + '</p>' +
        '<div class="flex gap-2 mt-3">' +
          '<button onclick="openCartDrawer(); dismissCartToast();" class="flex-1 text-center text-sm font-bold text-white bg-carbon rounded py-2.5 hover:bg-gold hover:text-carbon transition-colors cursor-pointer uppercase tracking-wider">Ver carrito (' + count + ')</button>' +
          '<button onclick="dismissCartToast()" class="flex-1 text-center text-sm font-bold text-carbon border border-sand rounded py-2.5 hover:bg-sand-light transition-colors cursor-pointer uppercase tracking-wider">Seguir viendo</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  document.body.appendChild(toast);
  requestAnimationFrame(function() {
    requestAnimationFrame(function() {
      toast.style.transform = 'translateY(0)';
    });
  });
  toast._timer = setTimeout(dismissCartToast, 4000);
}

function dismissCartToast() {
  var toast = document.getElementById('cart-toast');
  if (!toast) return;
  clearTimeout(toast._timer);
  toast.style.transform = 'translateY(-100%)';
  setTimeout(function() { if (toast.parentNode) toast.remove(); }, 350);
}

// ── Cart Drawer ──
function openCartDrawer() {
  var overlay = document.getElementById('cart-overlay');
  var drawer = document.getElementById('cart-drawer');
  if (overlay) overlay.classList.add('open');
  if (drawer) drawer.classList.add('open');
  document.body.style.overflow = 'hidden';
  renderCartDrawer();
}

function closeCartDrawer() {
  var overlay = document.getElementById('cart-overlay');
  var drawer = document.getElementById('cart-drawer');
  if (overlay) overlay.classList.remove('open');
  if (drawer) drawer.classList.remove('open');
  document.body.style.overflow = '';
}

function renderCartDrawer() {
  var container = document.getElementById('cart-items');
  var totalEl = document.getElementById('cart-total');
  var emptyEl = document.getElementById('cart-empty');
  var filledEl = document.getElementById('cart-filled');
  if (!container) return;

  var totals = getCartTotals();
  if (totals.count === 0) {
    if (emptyEl) emptyEl.classList.remove('hidden');
    if (filledEl) filledEl.classList.add('hidden');
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');
  if (filledEl) filledEl.classList.remove('hidden');

  container.innerHTML = '';
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    var row = document.createElement('div');
    row.className = 'flex gap-3 py-4 border-b border-sand-light';
    row.innerHTML =
      '<div class="w-20 h-20 bg-sand-light rounded overflow-hidden flex-shrink-0">' +
        '<img src="' + (item.image || '/assets/img/products/placeholder.jpg') + '" alt="' + item.name + '" class="w-full h-full object-cover">' +
      '</div>' +
      '<div class="flex-1 min-w-0">' +
        '<p class="text-sm font-bold truncate">' + item.name + '</p>' +
        '<p class="text-xs text-warm mt-0.5">Talla: ' + item.size + '</p>' +
        '<p class="text-sm font-bold mt-1">Q' + item.price + '</p>' +
        '<div class="flex items-center gap-2 mt-2">' +
          '<button onclick="updateQuantity(\'' + item.key + '\', ' + (item.quantity - 1) + '); renderCartDrawer();" class="w-7 h-7 border border-sand rounded flex items-center justify-center text-sm cursor-pointer hover:bg-sand-light">-</button>' +
          '<span class="text-sm font-semibold w-6 text-center">' + item.quantity + '</span>' +
          '<button onclick="updateQuantity(\'' + item.key + '\', ' + (item.quantity + 1) + '); renderCartDrawer();" class="w-7 h-7 border border-sand rounded flex items-center justify-center text-sm cursor-pointer hover:bg-sand-light">+</button>' +
          '<button onclick="removeFromCart(\'' + item.key + '\'); renderCartDrawer();" class="ml-auto text-xs text-warm hover:text-urgency cursor-pointer uppercase tracking-wider font-semibold">Quitar</button>' +
        '</div>' +
      '</div>';
    container.appendChild(row);
  }
  if (totalEl) totalEl.textContent = 'Q' + totals.total;
}

// ── WhatsApp Checkout ──
function checkoutWhatsApp() {
  var totals = getCartTotals();
  if (totals.count === 0) return;

  var msg = 'Hola! Quiero hacer un pedido en El Club:\n\n';
  for (var i = 0; i < totals.items.length; i++) {
    var item = totals.items[i];
    msg += '- ' + item.name + ' (Talla ' + item.size + ') x' + item.quantity + ' — Q' + (item.price * item.quantity) + '\n';
  }
  msg += '\nTotal: Q' + totals.total + '\n';
  msg += '\nEspero confirmacion para proceder con el pago.';

  var url = 'https://wa.me/' + WHATSAPP_NUMBER + '?text=' + encodeURIComponent(msg);
  window.open(url, '_blank');
}

// Init
document.addEventListener('DOMContentLoaded', function() {
  updateCartBadge();
  // Cart overlay click to close
  var overlay = document.getElementById('cart-overlay');
  if (overlay) {
    overlay.addEventListener('click', closeCartDrawer);
  }
});

// Listen for cart updates to re-render drawer if open
window.addEventListener('cartUpdated', function() {
  var drawer = document.getElementById('cart-drawer');
  if (drawer && drawer.classList.contains('open')) {
    renderCartDrawer();
  }
});
