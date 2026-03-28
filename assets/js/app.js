/**
 * El Club — Main Application Logic v2
 * Product rendering (asymmetric grid, Quick Add), pill filters, scroll reveal
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

// ── Render Product Card (v2 — with overlay + Quick Add) ──
function renderProductCard(product, isHero) {
  var stockLabel = '';
  if (product.stock <= 0) {
    stockLabel = '<span class="badge-urgency absolute top-3 left-3 z-10">Agotado</span>';
  } else if (product.stock <= 3) {
    stockLabel = '<span class="badge-urgency absolute top-3 left-3 z-10">Ultimas ' + product.stock + '</span>';
  }

  // Quick Add size pills (only for in-stock jerseys)
  var quickAddHtml = '';
  if (product.stock > 0 && product.sizes && product.sizes.length > 0) {
    var pills = '';
    for (var i = 0; i < product.sizes.length; i++) {
      pills += '<button class="quick-add-btn" onclick="event.preventDefault(); event.stopPropagation(); addToCart(\'' +
        product.id + '\', \'' + product.name.replace(/'/g, "\\'") + '\', ' + product.price + ', \'' +
        product.sizes[i] + '\', \'' + (product.image || '') + '\', ' + (product.stock || 1) + ')">' +
        product.sizes[i] + '</button>';
    }
    quickAddHtml = '<div class="quick-add mt-2">' + pills + '</div>';
  }

  // Overlay with description
  var overlayHtml = '';
  if (product.description) {
    overlayHtml = '<div class="card-overlay">' +
      '<p class="text-smoke text-xs leading-relaxed line-clamp-2">' + product.description + '</p>' +
      quickAddHtml +
    '</div>';
  } else if (quickAddHtml) {
    overlayHtml = '<div class="card-overlay">' + quickAddHtml + '</div>';
  }

  var metaText = '';
  if (product.team) {
    metaText = product.team;
    if (product.season) metaText += ' — ' + product.season;
  } else {
    metaText = product.type === 'mystery-box' ? 'Mystery Box' : (product.league || '');
  }

  var heroClass = isHero ? ' md:col-span-2 md:row-span-2' : '';

  return '<div class="product-card rounded-lg group' + heroClass + '">' +
    '<a href="/producto.html?id=' + product.id + '" class="block no-underline">' +
      '<div class="relative overflow-hidden">' +
        '<img src="' + (product.image || '/assets/img/products/placeholder.svg') + '" alt="' + product.name + '" class="w-full aspect-square object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy">' +
        stockLabel +
        overlayHtml +
      '</div>' +
      '<div class="p-4">' +
        '<p class="text-xs text-smoke uppercase tracking-wider font-semibold mb-1">' + metaText + '</p>' +
        '<h3 class="font-bold text-sm mb-2 text-white line-clamp-2">' + product.name + '</h3>' +
        '<span class="text-ice text-lg font-bold">Q' + product.price + '</span>' +
      '</div>' +
    '</a>' +
  '</div>';
}

// ── Render Asymmetric Product Grid ──
function renderProductGrid(containerId, products, asymmetric) {
  var container = document.getElementById(containerId);
  if (!container) return;

  if (products.length === 0) {
    container.innerHTML =
      '<div class="col-span-full py-16 text-center">' +
        '<svg class="w-16 h-16 mx-auto mb-4 text-chalk" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1">' +
          '<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>' +
        '</svg>' +
        '<p class="text-smoke font-semibold mb-2">No encontramos piezas con esos filtros</p>' +
        '<button onclick="clearAllFilters()" class="btn-ghost text-sm cursor-pointer">Ver todo</button>' +
      '</div>';
    return;
  }

  var html = '';
  for (var i = 0; i < products.length; i++) {
    var isHero = asymmetric && i === 0;
    html += renderProductCard(products[i], isHero);
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
    if (filters.availableOnly) {
      if (p.stock <= 0) return false;
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

// ── Pill Filter System ──
var currentFilters = { league: null, size: null, search: '', type: 'jersey', availableOnly: true };

function initPillFilters(products) {
  var leagueContainer = document.getElementById('league-pills');
  var sizeContainer = document.getElementById('size-pills');
  if (!leagueContainer) return;

  // Get leagues from jersey products only
  var jerseys = products.filter(function(p) { return p.type === 'jersey'; });
  var leagues = getFilterOptions(jerseys, 'league');

  // Render league pills
  var html = '<button class="pill active" onclick="setLeagueFilter(null, this)">Todas</button>';
  for (var i = 0; i < leagues.length; i++) {
    html += '<button class="pill" onclick="setLeagueFilter(\'' + leagues[i] + '\', this)">' + leagues[i] + '</button>';
  }
  leagueContainer.innerHTML = html;

  // Size pills (static)
  if (sizeContainer) {
    var sizes = ['S', 'M', 'L', 'XL'];
    var sizeHtml = '';
    for (var j = 0; j < sizes.length; j++) {
      sizeHtml += '<button class="pill text-xs" onclick="setSizeFilter(\'' + sizes[j] + '\', this)">' + sizes[j] + '</button>';
    }
    sizeContainer.innerHTML = sizeHtml;
  }
}

function setLeagueFilter(league, el) {
  currentFilters.league = league;
  // Update active pill
  var pills = el.parentElement.querySelectorAll('.pill');
  for (var i = 0; i < pills.length; i++) pills[i].classList.remove('active');
  el.classList.add('active');
  applyFilters();
}

function setSizeFilter(size, el) {
  if (currentFilters.size === size) {
    currentFilters.size = null;
    el.classList.remove('active');
  } else {
    currentFilters.size = size;
    var pills = el.parentElement.querySelectorAll('.pill');
    for (var i = 0; i < pills.length; i++) pills[i].classList.remove('active');
    el.classList.add('active');
  }
  applyFilters();
}

function setSearchFilter(value) {
  currentFilters.search = value;
  applyFilters();
}

function clearAllFilters() {
  currentFilters = { league: null, size: null, search: '', type: 'jersey', availableOnly: true };
  // Reset pills
  var leaguePills = document.querySelectorAll('#league-pills .pill');
  for (var i = 0; i < leaguePills.length; i++) {
    leaguePills[i].classList.remove('active');
    if (i === 0) leaguePills[i].classList.add('active');
  }
  var sizePills = document.querySelectorAll('#size-pills .pill');
  for (var j = 0; j < sizePills.length; j++) sizePills[j].classList.remove('active');
  // Reset search
  var searchInput = document.getElementById('catalog-search');
  if (searchInput) searchInput.value = '';
  applyFilters();
}

function applyFilters() {
  var filtered = filterProducts(PRODUCTS, currentFilters);
  renderProductGrid('product-grid', filtered, true);
  // Update count
  var countEl = document.getElementById('piece-count');
  if (countEl) countEl.textContent = filtered.length + ' pieza' + (filtered.length !== 1 ? 's' : '');
}

// ── Search expand toggle ──
function toggleSearch() {
  var container = document.getElementById('search-container');
  var input = document.getElementById('catalog-search');
  if (!container) return;
  container.classList.toggle('expanded');
  if (container.classList.contains('expanded') && input) {
    setTimeout(function() { input.focus(); }, 300);
  }
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

// ── FAQ Toggle ──
function toggleFaq(el) {
  var item = el.closest('.faq-item');
  if (!item) return;
  item.classList.toggle('open');
}

// ── Init ──
document.addEventListener('DOMContentLoaded', function() {
  initScrollReveal();
});
