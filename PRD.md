# El Club - Football Jersey E-Commerce Relaunch

## Product Requirements Document (PRD)

**Version:** 2.0
**Date:** 2026-02-24
**Owner:** Diego Arriaza Flores
**Domain:** elclub.club
**Instagram:** @club.gt (2,692 followers) | **TikTok:** @club.gtm (1,409 followers)

---

## 1. Executive Summary

Relaunch El Club as the premier football jersey mystery box experience in Guatemala. Founded late 2023, the concept went viral on TikTok (20+ jerseys sold in 2 days). After overextending with a Q.70k inventory order (1/3 stolen in transit) and a failed retail activation with Antigua GFC, the business went dormant.

**Now:** ~100 jerseys in stock (2023 season + retros), 4,100+ social media followers, proven demand, professional brand strategy documents already created, and World Cup 2026 starting in 107 days. Zero cash budget -- organic growth + reinvestment only.

**UVP:** "No vendemos camisetas. Entregamos historia."
**Positioning:** "La unica experiencia futbolera en Guatemala donde el futbol no se compra, se revela."

---

## 2. Brand Identity (From Brandbook + Copywriting Docs)

**Name:** El Club
**Logo:** Shield with open box + football icon, "EL CLUB MYSTERY BOX" text
**Taglines:** "La camiseta con historia" | "Solo para los que entienden" | "Tu club. Tu historia. Tu box."

**Colors:**
- Primary: Negro carbon (black)
- Secondary: Arena (sand/warm beige)
- Accent: Warm vintage tones
- Style: High-contrast, editorial, streetwear-adjacent

**Typography:** Bold sans-serif headers, clean body text

**Tone & Voice (from Copywriting doc):**
- Emotional, visual, direct, warm, local picardy
- Uses "vos" form (Guatemalan Spanish)
- Brand keywords: Unbox, pieza, historia, legendaria, mistica, archivista del futbol
- PROHIBITED: "stock", "envio inmediato", "producto generico", "la mejor calidad", "100% original"
- Copy frameworks: AIDA and PAS with emotional triggers
- Microcopy: "Descubri la box", "Revela la camiseta", "Unite al Club"
- CTA: "Pedi tu box secreta ahora"

**Buyer Persona (from Buyer Persona doc):**
- "Jose, el Nostalgico Futbolero" -- 25-30, male, Guatemala City (zones 10/15/1/Mixco)
- Class: Media alta, Q.10,000-Q.15,000 income
- Emotional/impulse buyer, discovers on TikTok, converts via WhatsApp
- "No compra para impresionar, compra para conectar"

---

## 3. Tech Stack (Mirror VENTUS)

| Component | Technology | Notes |
|-----------|------------|-------|
| Website | HTML5 + Tailwind CSS v4 (Browser) + Vanilla JS | No build step, GitHub Pages |
| Hosting | GitHub Pages | Free, SSL via Let's Encrypt |
| Domain | elclub.club | Owned, SSL expired, needs GitHub Pages reconnection |
| Payments | Recurrente | Already active from VENTUS (4.5% + Q2/tx) |
| Repository | GitHub (DiegoAF10/elclub) | Public repo |
| Analytics | Google Analytics 4 | Existing from VENTUS |
| DM Sales | Instagram DM + WhatsApp | Primary sales channels (IG 40% + WA 35%) |
| Content | TikTok + Instagram Reels | Organic-first strategy |

---

## 4. Product Catalog

### 4.1 Product Types (from Propuesta de Valor)

1. **Mystery Box Clasica** (Q.400)
   - HERO PRODUCT -- proven viral concept
   - 2 jerseys per box (curated by El Club)
   - Unboxing-ready kraft packaging with "EL CLUB MYSTERY BOXES" label
   - Unboxing content for TikTok/IG

2. **Mystery Box Premium** (Q.600)
   - 3 jerseys + bonus item
   - Higher-tier curation

3. **Cajas Tematicas** (Q.350-500)
   - Themed collections: "Retro Legends", "European Elite", "Latin Passion"
   - Curated around specific themes/eras
   - Limited edition runs

4. **Compra Directa / Individual Jerseys** (Q.150-250)
   - Browse by team, league, size
   - Product photos
   - Size guide
   - "Ultimas unidades" messaging

5. **World Cup 2026 Collection** (Q.200-350) -- Phase 2
   - National team jerseys (Guatemala, Mexico, USA, Argentina, etc.)
   - Pre-order system for new stock
   - Bundle deals

### 4.2 Existing Inventory Profile

From MASTER EL CLUB.xlsm sales data:
- SKU range: 502-594 (~93 total SKUs originally)
- 35 jerseys sold (Aug-Dec 2024) at Q.400 avg (mystery box format)
- Remaining stock: ~58-60 jerseys (needs physical count)
- Leagues represented: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Liga MX, and more
- Delivery: Diego (personal), Guatex, Rabbit couriers
- Payment methods: Efectivo, Tarjeta, Transferencia Bancaria
- Avg sale: Q.400-430 (price + shipping)

### 4.3 Inventory Management

Simple JSON-based inventory (VENTUS-style):
- Product ID, name, team, league, size, quantity, price, image URLs
- Stock sync between website display and actual count
- "Ultimas unidades" urgency messaging
- Sold-out handling with WhatsApp waitlist

---

## 5. Website Structure

```
elclub.club/
  index.html              -- Landing (hero + mystery box CTA + social proof)
  tienda.html             -- Full catalog with filters
  mystery-box.html        -- Mystery Box experience page
  producto.html           -- Individual product detail (query param based)
  nosotros.html           -- Brand manifesto ("El Club donde el futbol se viste de culto")
  contacto.html           -- WhatsApp link + form
  assets/
    css/                  -- Custom styles
    js/                   -- Cart logic, filters, inventory
    img/                  -- Product photos, brand assets, logos
    fonts/                -- Brand typography
  content/
    products.json         -- Product catalog data
```

### 5.1 Key Pages

**Landing Page (index.html)**
- Hero: "No vendemos camisetas. Entregamos historia."
- Mystery Box CTA front and center ("Pedi tu box secreta ahora")
- Featured products grid
- Social proof: TikTok embeds, unboxing videos, customer photos
- Instagram feed integration
- WhatsApp floating button

**Tienda (tienda.html)**
- Grid layout with product cards
- Filters: Liga, Equipo, Talla, Precio
- Sort: Precio, Recientes
- Quick add to cart
- "Ultimas unidades" badges

**Mystery Box (mystery-box.html)**
- Full immersive experience
- "Como funciona" (3 steps)
- Past unboxing videos (TikTok embeds)
- Tier selection (Clasica Q.400 vs Premium Q.600)
- FAQ section
- "Edicion limitada" urgency
- CTA to WhatsApp

**Product Detail (producto.html)**
- Large product image(s)
- Team, league, season info
- Size selector with guide
- Price + Add to cart
- Related products
- Share to WhatsApp

**Nosotros (nosotros.html)**
- Brand manifesto (from Propuesta de Valor doc):
  "El Club no es una tienda. Es un ritual."
  "Cada caja que abrís es un pedazo de historia que no sabías que necesitabas."
- Brand story
- Logo + identity

---

## 6. Channel Strategy (from Channel Mix doc)

| Channel | Weight | Role |
|---------|--------|------|
| Instagram | 40% | Community building + DM sales |
| WhatsApp | 35% | Conversion engine, order confirmation |
| TikTok | 15% | Top-of-funnel awareness, viral content |
| Website | 10% | Trust/reference point, catalog backup |

**Website role:** "Backup and reference point, NOT active traffic driver." Primary conversion happens in DMs and WhatsApp. Website provides legitimacy and catalog browsing.

---

## 7. GTM Strategy (from GTM doc)

### 4-Week Launch Calendar:

**Week 1: Teaser**
- "Algo se viene..." stories and posts
- Reactivate past customer DM conversations
- Story polls: "Que camisa quieren ver?"

**Week 2: Reveal**
- "Estamos de vuelta" announcement on IG + TikTok
- Website goes live
- Mystery Box reveal content

**Week 3: Sale**
- First mystery boxes available
- Unboxing content series
- WhatsApp order flow active

**Week 4: UGC**
- Customer unboxing reposts
- Reviews and testimonials
- "Unite al Club" community push

### KPIs (from GTM doc):
- 30+ boxes sold in 15 days
- 50 qualified leads via DM/WhatsApp
- 5K+ views on launch content
- 500 new followers across platforms
- 15 UGC unboxing videos

---

## 8. Cart and Checkout Flow

```
[Browse/DM] -> [Add to Cart] -> [Cart Sidebar] -> [Recurrente Checkout] -> [WhatsApp Confirmation]
```

- Cart stored in localStorage
- Cart sidebar with item list, quantities, total
- Checkout button generates Recurrente payment link
- WhatsApp notification to Diego on order
- Manual tracking initially

---

## 9. World Cup 2026 Strategy

**Timeline:** Event starts June 11, 2026 (107 days from today)

| Milestone | Date | Action |
|-----------|------|--------|
| Supplier contact | March 1 | Reach out for WC jerseys |
| Pre-order launch | March 15 | Accept deposits |
| Stock arrival | April 15-May 1 | Receive + photograph |
| WC landing page | May 1 | Dedicated collection live |
| Content blitz | May 15 - July 19 | Daily WC content |
| Peak sales | June 1 - July 19 | Tournament period |

---

## 10. Revenue Model

| Product | Price | Est. Cost | Margin | Notes |
|---------|-------|-----------|--------|-------|
| Mystery Box Clasica | Q.400 | Q.0* | 100%* | Existing stock, already paid |
| Mystery Box Premium | Q.600 | Q.0* | 100%* | Existing stock, already paid |
| Individual Jersey | Q.200 avg | Q.0* | 100%* | Existing stock |
| Caja Tematica | Q.450 avg | Q.0* | 100%* | Existing stock |
| WC Jersey (new) | Q.250 avg | Q.100 | 60% | Requires new order |

*Existing stock cost is sunk (Q.70k already invested). Every sale minus Recurrente fees (4.5% + Q2) is direct cash recovery.

**Recovery math:** ~60 jerseys x Q.400 avg (mystery box) = Q.24,000 potential revenue from existing stock.

---

## 11. Technical Requirements

### Must Have (MVP)
- [ ] Responsive website (mobile-first, 90%+ traffic from social)
- [ ] Product catalog with filters (liga, equipo, talla)
- [ ] Mystery Box page with tier selection
- [ ] Cart with localStorage
- [ ] Recurrente checkout integration
- [ ] WhatsApp floating button + order flow
- [ ] Basic inventory display with "ultimas unidades"
- [ ] Social media links
- [ ] Google Analytics 4
- [ ] Brand-aligned design (arena + negro carbon palette)
- [ ] SEO basics (meta tags, OG images)

### Should Have (Week 2-3)
- [ ] Size guide with measurements
- [ ] TikTok video embeds on Mystery Box page
- [ ] Instagram feed embed
- [ ] Share product to WhatsApp
- [ ] World Cup countdown timer

### Nice to Have (Month 2+)
- [ ] Pre-order system for WC jerseys
- [ ] Email capture / newsletter
- [ ] Customer reviews section
- [ ] Referral discount system

---

## 12. Constraints

- **Budget:** Q.0 -- zero paid tools or hosting
- **Timeline:** MVP this week, World Cup ready by May 1
- **Stock:** ~60 existing jerseys (needs physical inventory count)
- **One person:** Diego manages everything
- **Proven stack:** GitHub Pages + Tailwind v4 Browser + Recurrente
- **Brand docs:** Must faithfully execute existing brand strategy (6 PDFs)

---

## 13. Existing Assets

| Asset | Location | Status |
|-------|----------|--------|
| Brandbook PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| Buyer Persona PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| Channel Mix PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| Copywriting Guide PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| GTM Strategy PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| Propuesta de Valor PDF | OneDrive/EL CLUB/Entregables/ | Complete |
| Logo (3 variants PNG+SVG) | OneDrive/EL CLUB/Logos/ | Ready for web |
| Mystery Box packaging photo | OneDrive/EL CLUB/Shopify/ | Ready |
| 8 social media post designs | OneDrive/EL CLUB/Posts/ | Ready for IG |
| Box reference photos (4) | OneDrive/EL CLUB/Caja Referencia/ | Ready |
| MASTER EL CLUB.xlsm | OneDrive/EL CLUB/ | Sales data, empty inventory |

---

## 14. Definition of Done

The MVP is done when:
1. Website is live at elclub.club with SSL
2. Brand-aligned design matching Brandbook (arena + negro carbon)
3. Mystery Box page is functional with tier selection
4. Product catalog with at least placeholder products
5. Cart works and redirects to Recurrente
6. WhatsApp button and order notification flow
7. Google Analytics tracking active
8. Mobile-first, fast-loading
9. OG images and meta tags for social sharing

---

*PRD v2.0 -- El Club Relaunch (aligned with existing brand strategy)*
