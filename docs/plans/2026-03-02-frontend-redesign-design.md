# El Club — Frontend Redesign: "Midnight Stadium v2"

**Fecha:** 2026-03-02
**Dirección elegida:** C: Híbrido — Stadium + Editorial
**Vibe:** Cinematográfico con alma. Visual inmersivo + storytelling editorial.
**Stack:** HTML5 + Tailwind v4 Browser CDN + Vanilla JS (sin cambios)

---

## Páginas

### 1. HOME — "La Entrada al Estadio"

**Concepto:** No es una tienda. Es la puerta de entrada al club. El visitante siente que está entrando a un túnel de vestuario a medianoche.

**Secciones (scroll vertical):**

1. **Hero Fullscreen (100vh)**
   - Fondo: gradiente oscuro animado con partículas de humo/niebla (CSS puro, `@keyframes` + pseudo-elements)
   - "LA CAMISETA TE ELIGE A VOS" — Oswald 700, clamp() responsive
   - "No elegís. Descubrís." — Space Grotesk 400, smoke color
   - CTA: "ENTRAR AL CLUB" con pulso ice-glow
   - Nav NO visible en el hero — aparece sticky al scrollear

2. **Bifurcación (2 cards lado a lado)**
   - Izquierda: "MYSTERY BOX" + imagen de caja + "Confiá en la caja" → /mystery-box.html
   - Derecha: "CATÁLOGO" + jersey destacado + "Elegí tu pieza" → /catalogo.html
   - Hover: scale 1.02 + borde ice
   - Mobile: stack vertical, 100% width

3. **Jersey Destacado (editorial)**
   - Layout asimétrico: imagen (60%) + texto (40%)
   - Mini-historia de la camiseta
   - Precio + CTA "Ver pieza"
   - Se popula del primer `featured: true` jersey en products.json

4. **Social Proof** (condicional)
   - Con UGC: grid de 3 cards con embeds TikTok/Reels
   - Sin UGC: sección oculta (NO "Pronto")

5. **Footer minimalista**
   - Logo + links + socials + WhatsApp float

**Nav (sticky post-hero):**
- Logo | Mystery Box | Catálogo | Pedidos | Cart icon (badge)
- Mobile: logo + hamburger + cart badge
- 4 items solamente

---

### 2. CATÁLOGO — "La Vitrina del Archivista"

**Concepto:** Colección curada donde cada camiseta tiene contexto. Filtrado rápido, browsing placentero.

**Secciones:**

1. **Header de página**
   - "CATÁLOGO" en Oswald gigante (editorial)
   - "Cada pieza tiene historia. Encontrá la tuya."
   - Contador: "12 piezas en stock" (dinámico)

2. **Filtros como pills flotantes**
   - Row scrolleable: "Todas" | ligas dinámicas
   - Pill activa = fondo ice, texto dark
   - Search: icono que expande input al click
   - Tallas como pills secundarias (S | M | L | XL)
   - Sin dropdowns — todo visual y clickeable

3. **Grid asimétrico**
   - Desktop: 3 cols, primer item = hero (2 cols, más grande)
   - Hero rota: jersey más nuevo o más vendido
   - Mobile: 2 cols, hero = full width primera row

4. **Product Card (rediseñada)**
   - Imagen 1:1 (object-fit cover)
   - Hover: overlay slide-up con mini-historia (2 líneas)
   - **Quick Add:** hover muestra pills de talla → click = al carrito + toast
   - Click en imagen/nombre → /producto.html?id=X
   - Debajo: equipo + temporada, nombre jersey, precio (ice, bold)
   - Badge "Últimas N" si stock ≤ 3
   - Badge "NUEVO" si recién agregado

5. **Empty state**
   - Icono de camiseta + "No encontramos piezas con esos filtros" + "Ver todo"

---

### 3. MYSTERY BOX — "El Ritual"

**Concepto:** Experiencia, no página de producto. Vende la emoción, no el contenido.

**Secciones:**

1. **Hero editorial**
   - "NO ELEGÍS. DESCUBRÍS."
   - "Cada box es curada a mano con piezas de historia del fútbol mundial."
   - Scroll indicator

2. **Cómo funciona (3 pasos)**
   - Iconos con animación al scroll
   - 1: "Elegí tu box" | 2: "Elegí tu talla" | 3: "Recibí la sorpresa"
   - Horizontal desktop, vertical mobile
   - Fade-in escalonado

3. **Tiers lado a lado**
   - **Clásica (Q400):** borde chalk, 2 camisetas, features, talla pills, CTA
   - **Premium (Q600):** borde ice + glow, badge "PREMIUM", 3 camisetas + bonus, features expandidos, talla pills, CTA
   - Desktop: lado a lado. Mobile: Premium primero (upsell).
   - CTA deshabilitado sin talla seleccionada

4. **"¿Qué puede venir en tu box?"**
   - Grid 4-6 jerseys de muestra con mini-historias
   - "Estas son piezas de ejemplo. Tu box será única."

5. **FAQ accordion**
   - 5-7 preguntas con personalidad
   - Icono + → × al expandir
   - "¿Puedo elegir?" → "No. Ese es el punto. Confiá en la caja."

6. **CTA final**
   - "Tu camiseta ya sabe quién sos."
   - Botón scroll-to-tiers

---

### 4. PEDIDOS — "El Checkout Premium"

**Concepto:** Checkout real con Recurrente. WhatsApp como backup, no como único camino.

**Wizard de 3 pasos:**

**Progress bar:**
```
● Resumen  ───  ○ Envío  ───  ○ Pago
```
Activo = ice filled. Completo = check. Pendiente = outline.

**Paso 1: Resumen**
- Items con thumbnail + nombre + talla + precio
- Cantidad (+/-)
- Eliminar por item
- Subtotal + Envío (Q25 fijo) + Total (Oswald grande, ice)
- "CONTINUAR" + "Seguir comprando"

**Paso 2: Datos de Envío**
- Single-column form
- Campos: Nombre, Teléfono (WhatsApp), Zona/Dirección, Notas (opcional)
- Labels arriba (no placeholder-as-label)
- Validación inline on blur
- "CONTINUAR AL PAGO"

**Paso 3: Pago**
- Resumen compacto (collapsible)
- "PAGAR CON RECURRENTE" → abre link de pago en nueva pestaña
- "¿Preferís pagar por WhatsApp?" → wa.me con resumen
- Datos del paso 2 se guardan en localStorage + se envían vía WhatsApp auto

**Confirmación:**
- "Pedido recibido" con animación
- Número de pedido (timestamp)
- "Te contactaremos por WhatsApp para coordinar entrega"
- Resumen + "Volver al inicio"

---

## Componentes Transversales

### Cart Drawer (mejorado)
- Slide-in desde la derecha (400px)
- Items con thumbnail, nombre, talla, precio, qty +/-
- Total visible siempre
- CTA "IR A PEDIDOS" (va a /pedidos.html)
- CTA secundario "Seguir comprando"

### Toast de confirmación
- 4s auto-dismiss
- "Agregaste [nombre] (talla [X]) al carrito"
- Botón "Ver carrito" + "Seguir viendo"

### WhatsApp float
- Se mantiene en todas las páginas
- Posición: bottom-right, 20px del borde

### Mobile Menu
- Full-screen overlay desde izquierda
- 4 links + socials + "Cerrar"

---

## Design Tokens (Midnight Stadium — sin cambios)

```
midnight:  #0D0D0D  (bg)
pitch:     #1C1C1C  (cards)
chalk:     #2A2A2A  (borders)
slate:     #333333  (active borders)
white:     #F0F0F0  (text)
smoke:     #999999  (secondary)
ash:       #666666  (tertiary)
ice:       #4DA8FF  (accent)
ice-glow:  #4DA8FF33 (glow)
ice-dim:   #3B82B0  (hover)
whatsapp:  #25D366
```

**Fonts:** Oswald 700 (headlines) + Space Grotesk 400/500/600/700 (body/UI)

---

## Archivos a Crear/Modificar

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `index.html` | REESCRIBIR | Home fullscreen con hero animado |
| `catalogo.html` | CREAR (reemplaza tienda.html) | Catálogo con grid asimétrico + Quick Add |
| `mystery-box.html` | REESCRIBIR | Experiencia ritual con tiers |
| `pedidos.html` | CREAR | Checkout wizard 3 pasos |
| `producto.html` | MANTENER | Ya tiene galería de thumbnails |
| `assets/css/elclub.css` | MODIFICAR | Nuevas animaciones, componentes |
| `assets/js/app.js` | REESCRIBIR | Lógica de filtros, grid, Quick Add |
| `assets/js/cart.js` | MODIFICAR | Agregar lógica de checkout, localStorage de datos |
| `assets/js/checkout.js` | CREAR | Wizard de pedidos, validación, Recurrente |
| `content/products.json` | MANTENER | Schema actual funciona |
| `tienda.html` | ELIMINAR | Reemplazada por catalogo.html |
| `nosotros.html` | EVALUAR | Podría integrarse en Home o eliminarse |
| `contacto.html` | ELIMINAR | WhatsApp es el contacto |

---

## Decisiones de Diseño Clave

1. **Quick Add en catálogo:** Hover muestra tallas, click agrega al carrito sin ir al detalle
2. **Nav oculto en hero:** Aparece sticky al scrollear. Reduce ruido visual.
3. **Recurrente + WhatsApp dual:** Checkout formal con fallback a WhatsApp
4. **Datos de envío en localStorage:** Se preservan entre sesiones y se envían vía WA como backup
5. **Social proof condicional:** Sin UGC = sección oculta. No placeholders.
6. **Premium first en mobile:** Upsell posicional en Mystery Box
7. **Grid asimétrico con hero:** El primer jersey del catálogo se destaca visualmente
8. **Filtros como pills:** Sin dropdowns. Todo visual, todo clickeable.
