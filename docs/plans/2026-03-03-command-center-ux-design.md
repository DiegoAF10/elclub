# El Club — Command Center UX Design

**Date:** 2026-03-03
**Status:** Approved
**Author:** COO (Claude) + Diego

---

## Context

El Club has 3 user paths:
1. **Mystery Box** — Surprise curated boxes (existing)
2. **Catalog Browse** — Browse and buy individual jerseys (existing, fragmented across 4 pages)
3. **Custom Order** — Client requests any jersey, pays deposit, receives in 3-5 weeks (NEW)

Current site has 2 parallel nav systems, 4 separate browse experiences (tienda, catalogo, formacion, mapa), inconsistent checkout flows, and no custom order path.

## Design: "Command Center" Hub

### Philosophy

No hero, no fluff. The user lands and immediately sees 3 interactive paths. Each reacts to their interaction with unique micro-animations. The site is an experience, not a generic store.

---

## 1. Homepage (index.html) — Rediseign

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  NAV: Logo | Explorá | Mystery Box | Personalizá | Nosotros     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ │
│  │                  │ │                  │ │                  │ │
│  │   SORPRENDEME    │ │   EXPLORÁ        │ │   PERSONALIZÁ    │ │
│  │                  │ │                  │ │                  │ │
│  │   [box shake     │ │   [mini cards    │ │   [jersey wipe   │ │
│  │    animation]    │ │    stagger in]   │ │    fill anim]    │ │
│  │                  │ │                  │ │                  │ │
│  │   "Dejá que el   │ │   "Encontrá tu   │ │   "Armá tu       │ │
│  │    destino       │ │    pieza         │ │    camisa        │ │
│  │    elija"        │ │    legendaria"   │ │    soñada"       │ │
│  │                  │ │                  │ │                  │ │
│  │   Desde Q400     │ │   {N} piezas     │ │   Desde Q400     │ │
│  │   2-3 camisas    │ │   disponibles    │ │   Cualquier      │ │
│  │                  │ │                  │ │   equipo         │ │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘ │
│                                                                  │
│  ──── Cómo funciona ────                                        │
│  [1] Elegí tu camino                                            │
│  [2] Coordinamos por WhatsApp                                   │
│  [3] Recibí tu pieza                                            │
│                                                                  │
│  "La camiseta con historia."                                    │
│                                                                  │
│  ──── Footer ────                                               │
└──────────────────────────────────────────────────────────────────┘
```

### Mobile: 3 cards stack vertically, full-width, tap to interact.

### Micro-interactions

| Card | Icon | Hover/Tap Animation |
|------|------|---------------------|
| Sorprendeme | Box silhouette | Shake → open with light burst |
| Explorá | Mini grid/cards | Staggered fade-in reveal |
| Personalizá | Jersey outline (dashed) | Color wipe fill animation |

### Click destinations

- Sorprendeme → `/mystery-box.html`
- Explorá → `/explora.html`
- Personalizá → `/personaliza.html`

### Design tokens

- Card bg: `#1C1C1C` (pitch)
- Card border: `#2A2A2A` → `#4DA8FF` on hover
- Transition: 0.4-0.6s, cubic-bezier spring
- Gap: 24px desktop, 16px mobile
- Top padding: ~64px (breathe below nav)

---

## 2. Mystery Box (mystery-box.html) — Minor Adjustments

- Compact hero (40vh, not 70vh)
- Add "← Volver al hub" breadcrumb
- Keep tiers (Clásica Q400 / Premium Q600) as-is
- Keep FAQ, sample jerseys, how-it-works
- Ensure checkout flow uses pedidos.html (3-step wizard)

---

## 3. Explorá (explora.html) — NEW (Unified Browse)

Replaces: tienda.html, catalogo.html, formacion.html, mapa.html

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  ← Volver al hub                                         │
│                                                          │
│  EXPLORÁ                                                 │
│  {N} piezas disponibles                                  │
│                                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ FILTROS │ │  MAPA   │ │ CANCHA  │ │ BUSCAR  │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
│  (tab bar — active has ice underline)                    │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │                                              │       │
│  │  [Content area changes based on active tab]  │       │
│  │                                              │       │
│  └──────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### Tab: Filtros (default)
- League pills (horizontal scroll)
- Size pills (S, M, L, XL)
- Product grid (2 cols mobile / 3-4 cols desktop)
- Asymmetric first card (hero treatment, spans 2 cols)
- Quick-add size pills on hover
- Based on current catalogo.html logic

### Tab: Mapa
- SVG world map (SimpleMaps Robinson, already built)
- Countries with inventory glow blue
- Click → fullscreen overlay with jersey cards
- Mobile auto-zoom to Europe

### Tab: Cancha
- Interactive pitch (80vh, already built)
- 4 zones: DEL, MED, DEF, POR
- Click zone → fullscreen overlay with player cards
- Dot animations, zone glow effects

### Tab: Buscar
- Full-width search input (auto-focus on tab select)
- Real-time filter (debounced 300ms)
- Results in same card grid format
- Searches: name, team, league, player, season, description

### Tab switching
- URL hash: `#filtros`, `#mapa`, `#cancha`, `#buscar`
- Content area transitions: fade-out old → fade-in new (250ms)
- Tab bar sticky on scroll (z-index above content)

### Redirects
- `/tienda.html` → `/explora.html#filtros`
- `/catalogo.html` → `/explora.html#filtros`
- `/formacion.html` → `/explora.html#cancha`
- `/mapa.html` → `/explora.html#mapa`

---

## 4. Personalizá (personaliza.html) — NEW (Custom Order Builder)

### 4-Step Wizard

```
  [1 Liga] ——— [2 Equipo] ——— [3 Detalles] ——— [4 Confirmar]
```

### Step 1: Liga
- Large pills or cards, one per league
- Options: La Liga, Premier League, Serie A, Bundesliga, Ligue 1, Liga MX, MLS, Selecciones Nacionales, Otra (free input)
- Click to select → auto-advance to Step 2

### Step 2: Equipo
- Grid of popular teams for selected league (hardcoded JSON)
- Each team = styled button with name
- "Otro equipo" option with free text input
- No logos (copyright), just names

### Step 3: Detalles
- Temporada: dropdown (2024/25, 2023/24, 2022/23, Otra)
- Versión: pills (Local, Visita, Tercera)
- Jugador: text input (optional)
- Número: text input (optional)
- Talla: pills (S, M, L, XL, XXL)

### Step 4: Confirmar
- Visual summary of all selections
- Price: "Desde Q400-450" (exact confirmed via WhatsApp)
- Delivery: "3-5 semanas estimado"
- Payment: "Anticipo 50%"
- CTA: "Pedir por WhatsApp"

### WhatsApp Message Format

```
Hola! Quiero hacer un pedido personalizado en El Club:

⚽ Equipo: {team}
📅 Temporada: {season}
🏠 Versión: {variant}
👤 Jugador: {player} #{number}
📏 Talla: {size}

Precio estimado: Q400-450
Anticipo: 50%
Entrega estimada: 3-5 semanas

Espero confirmación de disponibilidad.
```

### Data Source

Static JSON inline or in `content/leagues.json`:

```json
{
  "La Liga": ["Barcelona", "Real Madrid", "Atlético de Madrid", "Sevilla", "Valencia", "Real Betis", "Athletic Bilbao", "Real Sociedad", "Villarreal"],
  "Premier League": ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United", "Tottenham", "Newcastle", "Aston Villa", "West Ham"],
  "Serie A": ["Juventus", "Inter", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina"],
  "Bundesliga": ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Bayer Leverkusen", "Stuttgart"],
  "Ligue 1": ["PSG", "Marseille", "Lyon", "Monaco", "Lille"],
  "Liga MX": ["América", "Chivas", "Cruz Azul", "Monterrey", "Tigres", "Pumas", "Santos"],
  "MLS": ["Inter Miami", "LA Galaxy", "LAFC", "Atlanta United", "Seattle Sounders"],
  "Selecciones": ["Argentina", "Brasil", "Francia", "España", "Alemania", "Italia", "Inglaterra", "México", "Colombia", "Guatemala"]
}
```

---

## 5. Navigation — Unified

### Desktop nav
```
Logo | Explorá | Mystery Box | Personalizá | Nosotros
```

### Mobile nav (hamburger)
Same links, full-screen overlay.

### Applied to ALL pages:
- index.html, mystery-box.html, explora.html, personaliza.html
- producto.html, pedidos.html, nosotros.html, contacto.html, 404.html

### Old pages (redirects):
- tienda.html → 301 to /explora.html#filtros
- catalogo.html → 301 to /explora.html#filtros
- formacion.html → 301 to /explora.html#cancha
- mapa.html → 301 to /explora.html#mapa

---

## 6. URL Map

| Page | URL | Status |
|------|-----|--------|
| Hub (homepage) | `/` | Redesign |
| Mystery Box | `/mystery-box.html` | Minor adjustments |
| Explorá (unified browse) | `/explora.html` | NEW |
| Personalizá (builder) | `/personaliza.html` | NEW |
| Product detail | `/producto.html?id=X` | Keep |
| Checkout wizard | `/pedidos.html` | Keep |
| About | `/nosotros.html` | Keep |
| Contact | `/contacto.html` | Footer only |
| 404 | `/404.html` | Update nav |

---

## 7. Tech Notes

- Stack: HTML5 + Tailwind v4 Browser CDN + Vanilla JS (no changes)
- No build step required
- Animations: pure CSS (keyframes + transitions)
- Tab switching: JS show/hide with hash routing
- Builder data: static JSON (no API needed)
- WhatsApp: wa.me link with pre-formatted message
- SVG map: already built (SimpleMaps Robinson, 152KB)
- Pitch: already built (80vh, 4-3-3 formation)
- All product data: `content/products.json` (single source of truth)

---

## 8. Implementation Priority

1. **Homepage redesign** — The hub with 3 interactive cards
2. **Personalizá page** — The new builder (unique differentiator)
3. **Explorá page** — Unify browse experiences under tabs
4. **Nav unification** — Update all pages to new nav
5. **Redirects** — Old pages → new URLs
6. **Cleanup** — Remove deprecated pages/code
