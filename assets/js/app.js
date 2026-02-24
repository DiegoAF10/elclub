/**
 * El Club — Main Application Logic
 * Product rendering, filtering, search, scroll reveal
 */

var PRODUCTS = [];

// ── Load Products ──
function loadProducts(callback) {
  if (PRODUCTS.length > 0) { callback(PRODUCTS); return; }
  fetch('/content/products.json')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      PRODUCTS = data;
      callback(data);
    })
    .catch(function() {
      console.error('Error loading products');
      callback([]);
    });
}

// ── Render Product Card ──
function renderProductCard(product) {
  var stockLabel = '';
  if (product.stock <= 0) {
    stockLabel = '<span class="badge-urgency absolute top-3 left-3">Agotado</span>';
  } else if (product.stock <= 3) {
    stockLabel = '<span class="badge-urgency absolute top-3 left-3">Ultimas ' + product.stock + '</span>';
  }

  var priceHtml = '<span class="text-lg font-bold">Q' + product.price + '</span>';

  return '<div class="product-card rounded-lg group">' +
    '<a href="/producto.html?id=' + product.id + '" class="block no-underline text-carbon">' +
      '<div class="relative overflow-hidden">' +
        '<img src="' + product.image + '" alt="' + product.name + '" class="w-full aspect-square object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy">' +
        stockLabel +
      '</div>' +
      '<div class="p-4">' +
        '<p class="text-xs text-warm uppercase tracking-wider font-semibold mb-1">' + (product.league || product.type) + '</p>' +
        '<h3 class="font-bold text-sm mb-2 line-clamp-2">' + product.name + '</h3>' +
        priceHtml +
      '</div>' +
    '</a>' +
  '</div>';
}

// ── Render Product Grid ──
function renderProductGrid(containerId, products) {
  var container = document.getElementById(containerId);
  if (!container) return;
  if (products.length === 0) {
    container.innerHTML = '<p class="text-center text-warm col-span-full py-12">No se encontraron productos.</p>';
    return;
  }
  var html = '';
  for (var i = 0; i < products.length; i++) {
    html += renderProductCard(products[i]);
  }
  container.innerHTML = html;
}

// ── Filter Products ──
function filterProducts(products, filters) {
  return products.filter(function(p) {
    if (filters.type && p.type !== filters.type) return false;
    if (filters.league && p.league !== filters.league) return false;
    if (filters.team && p.team !== filters.team) return false;
    if (filters.size) {
      if (!p.sizes || p.sizes.indexOf(filters.size) === -1) return false;
    }
    if (filters.search) {
      var q = filters.search.toLowerCase();
      var match = (p.name.toLowerCase().indexOf(q) !== -1) ||
        (p.team && p.team.toLowerCase().indexOf(q) !== -1) ||
        (p.league && p.league.toLowerCase().indexOf(q) !== -1) ||
        (p.description && p.description.toLowerCase().indexOf(q) !== -1);
      if (!match) return false;
    }
    return true;
  });
}

// ── Get Unique Values for Filters ──
function getFilterOptions(products, field) {
  var seen = {};
  var options = [];
  for (var i = 0; i < products.length; i++) {
    var val = products[i][field];
    if (val && !seen[val]) {
      seen[val] = true;
      options.push(val);
    }
  }
  return options.sort();
}

// ── Get Product by ID ──
function getProductById(id) {
  for (var i = 0; i < PRODUCTS.length; i++) {
    if (PRODUCTS[i].id === id) return PRODUCTS[i];
  }
  return null;
}

// ── Scroll Reveal ──
function initScrollReveal() {
  var elements = document.querySelectorAll('.reveal');
  if (!elements.length) return;

  var observer = new IntersectionObserver(function(entries) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].isIntersecting) {
        entries[i].target.classList.add('visible');
        observer.unobserve(entries[i].target);
      }
    }
  }, { threshold: 0.1 });

  for (var i = 0; i < elements.length; i++) {
    observer.observe(elements[i]);
  }
}

// ── Mobile Menu ──
function toggleMobileMenu() {
  var menu = document.getElementById('mobile-menu');
  if (menu) menu.classList.toggle('open');
  document.body.style.overflow = menu && menu.classList.contains('open') ? 'hidden' : '';
}

function closeMobileMenu() {
  var menu = document.getElementById('mobile-menu');
  if (menu) menu.classList.remove('open');
  document.body.style.overflow = '';
}

// ── Init ──
document.addEventListener('DOMContentLoaded', function() {
  initScrollReveal();
});
