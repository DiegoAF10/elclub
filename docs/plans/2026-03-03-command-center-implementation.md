# Command Center UX — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign El Club into a 3-path hub: Sorprendeme (Mystery Box), Explorá (Unified Catalog), Personalizá (Custom Order Builder).

**Architecture:** Static HTML + Tailwind v4 Browser CDN + Vanilla JS. No build step. All product data from `content/products.json`. New pages: `explora.html`, `personaliza.html`. Redesigned: `index.html`. Deprecated: `tienda.html`, `catalogo.html`, `formacion.html`, `mapa.html` (redirect to new pages). Shared overlay/animation CSS extracted to `elclub.css`.

**Tech Stack:** HTML5, Tailwind CSS v4 (browser CDN), Vanilla JavaScript, GitHub Pages

---

## Task 1: Extract Shared Overlay CSS to elclub.css

The overlay system (backdrop, panel, handle, header, close button, grid, card animations) is copy-pasted in formacion.html and mapa.html. Extract to elclub.css so explora.html can reuse it.

**Files:**
- Modify: `assets/css/elclub.css` (append after line 826)
- Modify: `formacion.html` (remove duplicate CSS)
- Modify: `mapa.html` (remove duplicate CSS)

**Step 1: Append overlay CSS to elclub.css**

Add after the last rule in `assets/css/elclub.css`:

```css
/* ── Overlay System ─────────────────────────── */
.overlay-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0);
  backdrop-filter: blur(0px);
  -webkit-backdrop-filter: blur(0px);
  z-index: 100;
  pointer-events: none;
  transition: background 0.4s ease, backdrop-filter 0.4s ease, -webkit-backdrop-filter 0.4s ease;
}

.overlay-backdrop.active {
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  pointer-events: auto;
}

.overlay-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 85vh;
  background: #111;
  border-top: 1px solid rgba(77, 168, 255, 0.3);
  border-radius: 20px 20px 0 0;
  z-index: 101;
  transform: translateY(100%);
  transition: transform 0.5s cubic-bezier(0.32, 0.72, 0, 1);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.overlay-panel.active {
  transform: translateY(0);
}

.overlay-handle {
  width: 40px;
  height: 4px;
  background: rgba(255,255,255,0.2);
  border-radius: 2px;
  margin: 12px auto 0;
}

.overlay-header {
  position: sticky;
  top: 0;
  background: linear-gradient(180deg, #111 80%, transparent);
  padding: 20px 24px 16px;
  z-index: 2;
}

.overlay-close {
  position: absolute;
  top: 16px;
  right: 20px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.overlay-close:hover {
  background: rgba(255,255,255,0.15);
  border-color: rgba(77, 168, 255, 0.4);
}

.overlay-grid {
  padding: 0 24px 40px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (min-width: 640px) {
  .overlay-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (min-width: 768px) {
  .overlay-grid { grid-template-columns: repeat(4, 1fr); max-width: 900px; margin: 0 auto; }
}

/* ── Overlay Card Animation ─────────────────── */
@keyframes cardShootIn {
  0% { opacity: 0; transform: translateY(60px) scale(0.85); }
  60% { opacity: 1; transform: translateY(-8px) scale(1.02); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

.card-shoot {
  animation: cardShootIn 0.6s cubic-bezier(0.22, 1.2, 0.36, 1) forwards;
  opacity: 0;
}

/* ── Overlay Cards (shared between country/player views) ─── */
.overlay-card {
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
  text-decoration: none;
  display: block;
}

.overlay-card:hover {
  border-color: #4DA8FF;
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(77, 168, 255, 0.2);
}

.overlay-card img {
  width: 100%;
  object-fit: cover;
  background-color: #1C1C1C;
}

/* ── Hub Cards (homepage) ───────────────────── */
.hub-card {
  background: #1C1C1C;
  border: 2px solid #2A2A2A;
  border-radius: 12px;
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  text-decoration: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  min-height: 320px;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.hub-card:hover {
  border-color: #4DA8FF;
  transform: translateY(-6px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(77, 168, 255, 0.3), 0 0 40px rgba(77, 168, 255, 0.1);
}

.hub-card-icon {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.4s ease;
}

.hub-card:hover .hub-card-icon {
  transform: scale(1.1);
}

.hub-card-title {
  font-family: 'Oswald', system-ui, sans-serif;
  font-weight: 700;
  font-size: 24px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #F0F0F0;
}

.hub-card-sub {
  color: #999;
  font-size: 14px;
  line-height: 1.5;
  max-width: 220px;
}

.hub-card-meta {
  color: #4DA8FF;
  font-family: 'Oswald', system-ui, sans-serif;
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* Hub card micro-animations */
@keyframes boxShake {
  0%, 100% { transform: rotate(0); }
  15% { transform: rotate(-8deg); }
  30% { transform: rotate(8deg); }
  45% { transform: rotate(-5deg); }
  60% { transform: rotate(5deg); }
  75% { transform: rotate(-2deg); }
}

@keyframes jerseyFill {
  0% { clip-path: inset(100% 0 0 0); }
  100% { clip-path: inset(0 0 0 0); }
}

/* ── Explora Tabs ───────────────────────────── */
.explora-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #2A2A2A;
  overflow-x: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.explora-tabs::-webkit-scrollbar { display: none; }

.explora-tab {
  padding: 12px 24px;
  font-family: 'Oswald', system-ui, sans-serif;
  font-weight: 600;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #666;
  cursor: pointer;
  border: none;
  background: none;
  border-bottom: 2px solid transparent;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.explora-tab:hover {
  color: #999;
}

.explora-tab.active {
  color: #4DA8FF;
  border-bottom-color: #4DA8FF;
}

.explora-content {
  display: none;
}

.explora-content.active {
  display: block;
}

/* ── Builder (personaliza) ──────────────────── */
.builder-steps {
  display: flex;
  justify-content: center;
  gap: 0;
  margin-bottom: 32px;
}

.builder-step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
  font-family: 'Oswald', system-ui, sans-serif;
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.builder-step.active {
  color: #4DA8FF;
}

.builder-step.completed {
  color: #22C55E;
}

.builder-step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  border: 2px solid #2A2A2A;
  color: #666;
  background: transparent;
  transition: all 0.3s ease;
}

.builder-step.active .builder-step-dot {
  border-color: #4DA8FF;
  background: #4DA8FF;
  color: #0D0D0D;
}

.builder-step.completed .builder-step-dot {
  border-color: #22C55E;
  background: #22C55E;
  color: #0D0D0D;
}

.builder-line {
  width: 48px;
  height: 2px;
  background: #2A2A2A;
  margin: 0 4px;
  transition: background 0.3s ease;
}

.builder-line.completed {
  background: #22C55E;
}

.builder-option {
  background: #1C1C1C;
  border: 2px solid #2A2A2A;
  border-radius: 8px;
  padding: 16px 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
  color: #F0F0F0;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-weight: 500;
  font-size: 15px;
}

.builder-option:hover {
  border-color: #4DA8FF;
  background: #222;
}

.builder-option.selected {
  border-color: #4DA8FF;
  background: rgba(77, 168, 255, 0.1);
  color: #4DA8FF;
}
```

**Step 2: Remove duplicate overlay CSS from formacion.html**

In `formacion.html`, remove the overlay-related CSS rules from the inline `<style>` block (the `.overlay-backdrop`, `.overlay-panel`, `.overlay-handle`, `.overlay-header`, `.overlay-close`, `.overlay-grid`, `.country-card`/`.player-card` hover, `cardShootIn`, `.card-shoot` rules). Keep the pitch-specific CSS (`.pitch-container`, `.pitch-zone`, `.pitch-dot`, etc).

Update card class references from `player-card` to `overlay-card` in the JS `openOverlay()` function.

**Step 3: Remove duplicate overlay CSS from mapa.html**

Same as Step 2. Remove overlay CSS from inline `<style>`. Keep map-specific CSS (`.map-container`, `.has-jerseys`, `.map-tooltip`, `countryPulse`). Update `country-card` to `overlay-card`.

**Step 4: Verify both pages still work**

Open `formacion.html` and `mapa.html` in browser. Verify:
- Pitch zones clickable, overlay slides up
- Map countries clickable, overlay slides up
- Card animations work
- Close button works

**Step 5: Commit**

```bash
git add assets/css/elclub.css formacion.html mapa.html
git commit -m "refactor: extract shared overlay CSS to elclub.css"
```

---

## Task 2: Create leagues.json Data File

**Files:**
- Create: `content/leagues.json`

**Step 1: Write leagues data**

```json
{
  "La Liga": ["Barcelona", "Real Madrid", "Atlético de Madrid", "Sevilla", "Valencia", "Real Betis", "Athletic Bilbao", "Real Sociedad", "Villarreal", "Girona"],
  "Premier League": ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United", "Tottenham", "Newcastle", "Aston Villa", "West Ham", "Brighton"],
  "Serie A": ["Juventus", "Inter", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna"],
  "Bundesliga": ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Bayer Leverkusen", "Stuttgart", "Frankfurt"],
  "Ligue 1": ["PSG", "Marseille", "Lyon", "Monaco", "Lille", "Nice"],
  "Liga MX": ["América", "Chivas", "Cruz Azul", "Monterrey", "Tigres", "Pumas", "Santos Laguna", "Toluca"],
  "MLS": ["Inter Miami", "LA Galaxy", "LAFC", "Atlanta United", "Seattle Sounders", "Columbus Crew"],
  "Selecciones": ["Argentina", "Brasil", "Francia", "España", "Alemania", "Italia", "Inglaterra", "México", "Colombia", "Guatemala", "Portugal", "Países Bajos", "Croacia", "Uruguay"]
}
```

**Step 2: Commit**

```bash
git add content/leagues.json
git commit -m "data: add leagues.json for custom order builder"
```

---

## Task 3: Redesign Homepage (index.html)

This is the biggest task. Replace the current hero + bifurcation + featured + how-it-works with the Command Center hub.

**Files:**
- Modify: `index.html` (major rewrite of body content, keep head/scripts)

**Step 1: Rewrite the body content**

Keep the `<head>` (lines 1-53), `<body>` tag (line 54). Replace everything between the nav and footer with the hub.

**New nav** (unified, replaces current lines 56-94):
```html
<header id="site-header" class="fixed top-0 left-0 right-0 z-40 bg-midnight/95 backdrop-blur-sm border-b border-chalk transition-all duration-300">
  <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
    <a href="/" class="flex items-center gap-2">
      <img src="/assets/img/brand/logo.svg" alt="El Club" class="h-10 w-auto">
    </a>
    <div class="hidden md:flex items-center gap-8">
      <a href="/explora.html" class="nav-link">Explorá</a>
      <a href="/mystery-box.html" class="nav-link">Mystery Box</a>
      <a href="/personaliza.html" class="nav-link">Personalizá</a>
      <a href="/nosotros.html" class="nav-link">Nosotros</a>
    </div>
    <div class="flex items-center gap-4">
      <button onclick="openCartDrawer()" class="relative cursor-pointer bg-transparent border-none text-white">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/></svg>
        <span class="cart-badge hidden">0</span>
      </button>
      <button onclick="toggleMobileMenu()" class="md:hidden cursor-pointer bg-transparent border-none text-white">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
      </button>
    </div>
  </div>
</header>
```

**Hub section** (replaces hero + bifurcation + featured + how-it-works):
```html
<main class="pt-20 pb-16">
  <!-- Hub Cards -->
  <section class="max-w-5xl mx-auto px-4 py-12 md:py-20">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">

      <!-- Sorprendeme -->
      <a href="/mystery-box.html" class="hub-card group" id="hub-surprise">
        <div class="hub-card-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="#4DA8FF" stroke-width="1.5">
            <rect x="8" y="24" width="48" height="36" rx="2"/>
            <path d="M8 24l24-16 24 16"/>
            <line x1="32" y1="8" x2="32" y2="60"/>
            <path d="M20 24c0-8 6-16 12-16s12 8 12 16"/>
          </svg>
        </div>
        <h2 class="hub-card-title">Sorprendeme</h2>
        <p class="hub-card-sub">Dejá que el destino elija. Cada box es curada a mano con piezas legendarias.</p>
        <span class="hub-card-meta">Desde Q400 · 2-3 camisas</span>
      </a>

      <!-- Explorá -->
      <a href="/explora.html" class="hub-card group" id="hub-explore">
        <div class="hub-card-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="#4DA8FF" stroke-width="1.5">
            <rect x="4" y="4" width="24" height="24" rx="2"/>
            <rect x="36" y="4" width="24" height="24" rx="2"/>
            <rect x="4" y="36" width="24" height="24" rx="2"/>
            <rect x="36" y="36" width="24" height="24" rx="2"/>
          </svg>
        </div>
        <h2 class="hub-card-title">Explorá</h2>
        <p class="hub-card-sub">Encontrá tu pieza legendaria. Filtrá por liga, país o posición.</p>
        <span class="hub-card-meta" id="hub-explore-count">Cargando...</span>
      </a>

      <!-- Personalizá -->
      <a href="/personaliza.html" class="hub-card group" id="hub-custom">
        <div class="hub-card-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="#4DA8FF" stroke-width="1.5">
            <path d="M20 8 C20 8 12 12 12 20 L12 56 L32 60 L52 56 L52 20 C52 12 44 8 44 8 L32 4 Z" stroke-dasharray="4 3"/>
            <line x1="32" y1="4" x2="32" y2="60" stroke-dasharray="4 3"/>
          </svg>
        </div>
        <h2 class="hub-card-title">Personalizá</h2>
        <p class="hub-card-sub">Armá tu camisa soñada. Cualquier equipo, cualquier jugador.</p>
        <span class="hub-card-meta">Desde Q400 · 3-5 semanas</span>
      </a>

    </div>
  </section>

  <!-- How it works (compact) -->
  <section class="max-w-4xl mx-auto px-4 py-12 border-t border-chalk">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
      <div>
        <div class="text-3xl font-bold text-ice mb-2" style="font-family:'Oswald',system-ui,sans-serif;">1</div>
        <p class="text-white font-semibold text-sm uppercase tracking-wider mb-1">Elegí tu camino</p>
        <p class="text-smoke text-xs">Sorpresa, catálogo o pedido personalizado</p>
      </div>
      <div>
        <div class="text-3xl font-bold text-ice mb-2" style="font-family:'Oswald',system-ui,sans-serif;">2</div>
        <p class="text-white font-semibold text-sm uppercase tracking-wider mb-1">Coordinamos por WhatsApp</p>
        <p class="text-smoke text-xs">Confirmamos tu pedido y método de pago</p>
      </div>
      <div>
        <div class="text-3xl font-bold text-ice mb-2" style="font-family:'Oswald',system-ui,sans-serif;">3</div>
        <p class="text-white font-semibold text-sm uppercase tracking-wider mb-1">Recibí tu pieza</p>
        <p class="text-smoke text-xs">Entrega en Guatemala en 2-7 días</p>
      </div>
    </div>
  </section>

  <!-- Tagline -->
  <section class="text-center py-12">
    <p class="text-2xl md:text-3xl font-bold tracking-wider text-white" style="font-family:'Oswald',system-ui,sans-serif;">La camiseta con historia.</p>
  </section>
</main>
```

**Mobile menu** (update links):
```html
<div id="mobile-menu" class="mobile-menu">
  <div class="p-4 flex justify-end">
    <button onclick="closeMobileMenu()" class="cursor-pointer bg-transparent border-none text-white">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  </div>
  <div class="flex flex-col items-center gap-8 mt-12">
    <a href="/explora.html" onclick="closeMobileMenu()" class="text-2xl font-bold uppercase tracking-wider text-white hover:text-ice transition-colors">Explorá</a>
    <a href="/mystery-box.html" onclick="closeMobileMenu()" class="text-2xl font-bold uppercase tracking-wider text-white hover:text-ice transition-colors">Mystery Box</a>
    <a href="/personaliza.html" onclick="closeMobileMenu()" class="text-2xl font-bold uppercase tracking-wider text-white hover:text-ice transition-colors">Personalizá</a>
    <a href="/nosotros.html" onclick="closeMobileMenu()" class="text-2xl font-bold uppercase tracking-wider text-white hover:text-ice transition-colors">Nosotros</a>
    <a href="/contacto.html" onclick="closeMobileMenu()" class="text-2xl font-bold uppercase tracking-wider text-white hover:text-ice transition-colors">Contacto</a>
  </div>
</div>
```

**Footer** (update nav links to match new structure).

**Inline JS** (replace the nav scroll + featured jersey logic):
```html
<script>
  // Populate explore count from products.json
  loadProducts(function(products) {
    var jerseys = products.filter(function(p) { return p.type === 'jersey' && p.stock > 0; });
    var el = document.getElementById('hub-explore-count');
    if (el) el.textContent = jerseys.length + ' piezas disponibles';
  });

  // Hub card hover animations
  var hubSurprise = document.getElementById('hub-surprise');
  if (hubSurprise) {
    hubSurprise.addEventListener('mouseenter', function() {
      var icon = this.querySelector('.hub-card-icon');
      if (icon) icon.style.animation = 'boxShake 0.6s ease';
    });
    hubSurprise.addEventListener('mouseleave', function() {
      var icon = this.querySelector('.hub-card-icon');
      if (icon) icon.style.animation = '';
    });
  }
</script>
```

**Step 2: Verify homepage**

Open `index.html` in browser. Verify:
- 3 cards visible immediately (no hero blocking)
- Cards hover with border glow + lift
- "Sorprendeme" icon shakes on hover
- Explore count shows correct number
- Mobile: cards stack vertically
- Nav links correct: Explorá, Mystery Box, Personalizá, Nosotros

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: redesign homepage as Command Center hub with 3 paths"
```

---

## Task 4: Create personaliza.html (Custom Order Builder)

**Files:**
- Create: `personaliza.html`

**Step 1: Create the builder page**

Full page with 4-step wizard. Steps show/hide via JS. Liga → Equipo → Detalles → Confirmar → WhatsApp.

Key patterns to reuse:
- Nav: same unified nav from Task 3
- Footer: compact (like catalogo.html)
- Progress bar: similar to pedidos.html but horizontal with labels
- Size pills: reuse `.size-btn` from elclub.css
- Builder options: use `.builder-option` from elclub.css (Task 1)

The league/team data is loaded from `content/leagues.json` via fetch.

JS logic:
- `var builderState = { liga: null, equipo: null, temporada: null, version: null, jugador: '', numero: '', talla: null }`
- `goToBuilderStep(n)` — shows/hides step panels, updates progress bar
- `selectLiga(liga)` — sets state, renders teams, advances
- `selectEquipo(equipo)` — sets state, advances
- `submitDetails()` — validates talla selected, advances to confirm
- `sendCustomOrder()` — builds WhatsApp message, opens wa.me link

WhatsApp message format:
```
Hola! Quiero hacer un pedido personalizado en El Club:

⚽ Equipo: {equipo}
🏆 Liga: {liga}
📅 Temporada: {temporada}
🏠 Versión: {version}
👤 Jugador: {jugador} #{numero}
📏 Talla: {talla}

Precio estimado: Q400-450
Anticipo: 50%
Entrega estimada: 3-5 semanas

Espero confirmación de disponibilidad.
```

**Step 2: Verify builder flow**

Open `personaliza.html` in browser. Walk through all 4 steps:
1. Select a league → teams appear
2. Select a team → details form appears
3. Fill details + select size → summary appears
4. Click "Pedir por WhatsApp" → wa.me link opens with correct message

Also test:
- "Otra" option in liga → shows free text input
- "Otro equipo" option → shows free text input
- Back buttons work at each step
- Mobile responsive

**Step 3: Commit**

```bash
git add personaliza.html
git commit -m "feat: add personaliza.html custom order builder (4-step wizard)"
```

---

## Task 5: Create explora.html (Unified Browse)

This is the most complex task. Combines the functionality of catalogo.html (filters), mapa.html (world map), and formacion.html (pitch) into one tabbed page.

**Files:**
- Create: `explora.html`

**Step 1: Create the unified browse page**

4 tabs: Filtros (default) | Mapa | Cancha | Buscar

Key patterns to reuse:
- Filtros tab: pill filters from `catalogo.html` + `app.js` functions (`initPillFilters`, `applyFilters`, `renderProductGrid`)
- Mapa tab: SVG loading + country matching from `mapa.html` JS
- Cancha tab: pitch SVG + zone selection from `formacion.html` JS
- Buscar tab: search input + live filter from `app.js` (`setSearchFilter`)
- Overlay system: now in elclub.css (Task 1)
- Product grid: `renderProductGrid()` from app.js

Tab switching via JS + URL hash:
- `#filtros` (default), `#mapa`, `#cancha`, `#buscar`
- `switchTab(tabName)` — hides all `.explora-content`, shows matching one
- On page load: read hash, default to `#filtros`

Each tab has its own `<div class="explora-content" id="tab-{name}">` container.

**Filtros tab content:**
- League pills + size pills + product grid
- Reuses `initPillFilters()`, `applyFilters()`, `renderProductGrid()`

**Mapa tab content:**
- `<div class="map-container" id="map-container">` (SVG injected)
- Map-specific inline CSS for `.has-jerseys`, tooltip, etc.
- All JS from mapa.html (SVG_TO_COUNTRY, colorizeMap, bindMapEvents, etc.)
- Overlay opens on country click

**Cancha tab content:**
- `<div class="pitch-container">` with SVG lines + zones + dots
- Pitch-specific inline CSS
- All JS from formacion.html (selectZone, dot management, etc.)
- Overlay opens on zone click

**Buscar tab content:**
- Full-width search input (auto-focuses on tab switch)
- `#search-results` grid populated by `renderProductGrid()`
- Live filter on input (debounced 300ms)

The shared overlay (backdrop + panel + grid) lives ONCE at the bottom of the page, reused by both Mapa and Cancha tabs.

**Step 2: Verify all tabs work**

Open `explora.html` in browser. Test each tab:
1. Filtros: pills filter, grid renders, quick-add works
2. Mapa: SVG loads, countries glow, click opens overlay with cards
3. Cancha: pitch renders, zones clickable, overlay opens with player cards
4. Buscar: search input filters in real time

Also test:
- Tab switching smooth (no flash)
- URL hash updates: `#mapa`, `#cancha`, `#buscar`
- Direct link to `explora.html#mapa` works
- Mobile responsive on all tabs
- Cart add works from all views

**Step 3: Commit**

```bash
git add explora.html
git commit -m "feat: add explora.html unified browse with 4 tabs (filtros/mapa/cancha/buscar)"
```

---

## Task 6: Update Nav on All Remaining Pages

**Files:**
- Modify: `mystery-box.html` — update nav + compact hero + breadcrumb
- Modify: `producto.html` — update nav + fix breadcrumb link
- Modify: `pedidos.html` — update nav
- Modify: `nosotros.html` — update nav + footer
- Modify: `contacto.html` — update nav + footer
- Modify: `404.html` — update nav

**Step 1: Define the unified nav HTML**

All pages use:
```html
<header class="fixed top-0 left-0 right-0 z-40 bg-midnight/95 backdrop-blur-sm border-b border-chalk">
  <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
    <a href="/"><img src="/assets/img/brand/logo.svg" alt="El Club" class="h-10 w-auto"></a>
    <div class="hidden md:flex items-center gap-8">
      <a href="/explora.html" class="nav-link">Explorá</a>
      <a href="/mystery-box.html" class="nav-link">Mystery Box</a>
      <a href="/personaliza.html" class="nav-link">Personalizá</a>
      <a href="/nosotros.html" class="nav-link">Nosotros</a>
    </div>
    <!-- cart + hamburger buttons -->
  </div>
</header>
```

Active state: add `active` class to the matching nav-link per page.

**Step 2: Update mobile menus** on all pages to match the new link structure.

**Step 3: Update footers** — nav links in footers should include: Explorá, Mystery Box, Personalizá, Nosotros, Contacto.

**Step 4: mystery-box.html specific changes**
- Compact hero: change `min-h-[70vh]` to `min-h-[40vh]`
- Add breadcrumb below header: `← Volver` linking to `/`

**Step 5: producto.html specific changes**
- Update breadcrumb to link to `/explora.html` instead of `/tienda.html`

**Step 6: Verify all pages**

Open each page and verify:
- Nav shows correct links
- Active state highlights correct link
- Mobile menu works
- Footer links correct
- Cart drawer works

**Step 7: Commit**

```bash
git add mystery-box.html producto.html pedidos.html nosotros.html contacto.html 404.html
git commit -m "feat: unify nav across all pages (Explorá/Mystery Box/Personalizá/Nosotros)"
```

---

## Task 7: Add Redirects for Deprecated Pages

**Files:**
- Modify: `tienda.html` (replace with redirect)
- Modify: `catalogo.html` (replace with redirect)
- Modify: `formacion.html` (replace with redirect)
- Modify: `mapa.html` (replace with redirect)

**Step 1: Replace each file with a simple redirect page**

Since GitHub Pages doesn't support server-side redirects, use `<meta http-equiv="refresh">` + JS fallback:

```html
<!DOCTYPE html>
<html lang="es-GT">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0;url=/explora.html#filtros">
  <title>Redirigiendo...</title>
  <script>window.location.replace('/explora.html#filtros');</script>
</head>
<body>
  <p>Redirigiendo a <a href="/explora.html#filtros">Explorá</a>...</p>
</body>
</html>
```

Redirect targets:
- `tienda.html` → `/explora.html#filtros`
- `catalogo.html` → `/explora.html#filtros`
- `formacion.html` → `/explora.html#cancha`
- `mapa.html` → `/explora.html#mapa`

**Step 2: Commit**

```bash
git add tienda.html catalogo.html formacion.html mapa.html
git commit -m "feat: redirect deprecated pages to explora.html"
```

---

## Task 8: Final Cleanup & Push

**Files:**
- Modify: `assets/js/cart.js` — add TODO comment for WhatsApp number

**Step 1: Fix cart drawer behavior**

Ensure all pages' cart drawers use "Ir a pedidos" CTA (not `checkoutWhatsApp()` direct). Since old pages now redirect, this is mainly about explora.html and personaliza.html having the correct cart drawer HTML.

**Step 2: Remove unused code**

- Remove `gen_map.py` (SVG generation no longer needed — using SimpleMaps)
- Clean up any TODO comments

**Step 3: Final verification**

Open each page and do a full walkthrough:
1. Homepage → 3 cards visible, all link correctly
2. Mystery Box → tiers work, add to cart, go to pedidos
3. Explorá → all 4 tabs work
4. Personalizá → 4-step builder, WhatsApp message correct
5. Product → detail page loads, add to cart works
6. Pedidos → 3-step checkout wizard works
7. Old URLs redirect correctly

**Step 4: Commit and push**

```bash
git add -A
git commit -m "cleanup: remove deprecated files, fix cart drawer consistency"
git push origin main
```

---

## Execution Order Summary

| # | Task | New/Modify | Complexity |
|---|------|-----------|-----------|
| 1 | Extract overlay CSS | Modify 3 files | Low |
| 2 | Create leagues.json | Create 1 file | Low |
| 3 | Redesign homepage | Modify 1 file | Medium |
| 4 | Create personaliza.html | Create 1 file | Medium |
| 5 | Create explora.html | Create 1 file | High |
| 6 | Update nav on all pages | Modify 6 files | Medium |
| 7 | Add redirects | Modify 4 files | Low |
| 8 | Cleanup & push | Misc | Low |

**Estimated commits:** 8
**Critical dependency:** Task 1 must complete before Task 5 (explora needs overlay CSS in elclub.css)
