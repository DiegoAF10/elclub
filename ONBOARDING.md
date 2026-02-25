# El Club — Paquete de Onboarding para /coo-club

> Este documento contiene TODO el contexto necesario para crear el skill `/coo-club`.
> Fue generado el 2026-02-24 durante la sesion de Loki Mode que construyo el sitio web.
> El skill que lo lea debe absorber esta informacion y operar con ella desde el primer turno.

---

## 1. IDENTIDAD DEL NEGOCIO

**Nombre:** El Club
**Concepto:** Mystery boxes de camisetas de futbol (replicas AAA)
**Pais:** Guatemala
**Moneda:** GTQ (Quetzales)
**Fundado:** Finales de 2023
**Estado actual:** Relanzamiento (estuvo dormido todo 2024-2025)
**Dominio:** elclub.club
**Instagram:** @club.gt
**TikTok:** @club.gtm
**Propietario:** Diego Arriaza Flores (una sola persona maneja todo)

### UVP (Propuesta de Valor Unica)
"No vendemos camisetas. Entregamos historia."

### Posicionamiento
"La unica experiencia futbolera en Guatemala donde el futbol no se compra, se revela."

### Taglines Aprobados
- "La camiseta con historia"
- "Solo para los que entienden"
- "Tu club. Tu historia. Tu box."
- "Cada caja que abris es un pedazo de historia que no sabias que necesitabas"

---

## 2. HISTORIA COMPLETA

| Fecha | Evento |
|-------|--------|
| Nov 2023 | Diego encuentra proveedor chino de camisetas AAA. Compra 20-25. |
| Dic 2023 | Sube TikToks que se hacen virales. 20 camisetas se agotan en 2 dias. |
| Dic 2023 | Crea waitlist de ~80 personas. |
| Ene 2024 | Antigua GFC lo contacta para activacion. Diego se emociona. |
| Ene 2024 | Pide prestado Q70,000 a su papa para compra grande. |
| Feb 2024 | Un tercio del pedido se pierde/roban en transito. |
| Mar 2024 | Evento con Antigua no rinde como esperaba. Stock alto, ventas bajas. |
| Abr-Dic 2024 | Ventas esporadicas (35 en total). Se deprime. Altibajos. |
| 2025 | Negocio dormido. Diego trabaja en VENTUS y Clan Cervecero. |
| Feb 2026 | Decide relanzar. Sesion de Loki Mode construye sitio web completo. |

### Ventas Historicas (de MASTER EL CLUB.xlsm)
- **35 ventas registradas** (Ago-Dic 2024)
- **Precio promedio:** Q400 (formato mystery box)
- **Metodos de pago:** Efectivo, Tarjeta, Transferencia
- **Entrega:** Diego personal, Guatex, Rabbit
- **Revenue total historico:** ~Q30,000 (se gasto todo)

---

## 3. SITUACION FINANCIERA

| Concepto | Monto |
|----------|-------|
| Deuda con papa | Q70,000 |
| Inversion total (camisetas) | Q70,000 (costo hundido) |
| Revenue historico | ~Q30,000 (gastado) |
| Presupuesto actual | Q0 |
| Cash actual | Q0 |
| Inventario estimado | ~60-100 camisetas (necesita conteo fisico) |

**Implicacion critica:** Cada venta de inventario existente es ~100% margen (menos fees de Recurrente 4.5% + Q2/tx). El costo ya fue pagado. Esto es recuperacion de capital puro.

### Matematica de Recuperacion
- ~60 jerseys x Q400 promedio (mystery box) = Q24,000 potencial
- Minus Recurrente fees (~5%) = ~Q22,800 neto
- Eso paga ~32% de la deuda con papa

---

## 4. PRODUCTOS

### Oferta Principal

| Producto | Precio | Contenido | Estado |
|----------|--------|-----------|--------|
| Mystery Box Clasica | Q400 | 2 camisetas curadas | ACTIVO |
| Mystery Box Premium | Q600 | 3 camisetas + bonus | ACTIVO |
| Jersey Individual | Q200-250 | 1 camiseta especifica | ACTIVO |
| Caja Tematica | Q350-500 | Coleccion tematica | FUTURO |
| World Cup 2026 | Q200-350 | Selecciones nacionales | FUTURO (requiere nuevo pedido) |

### Inventario Actual (PLACEHOLDERS — necesita conteo fisico)
El archivo `content/products.json` tiene 8 productos placeholder:
- MB-CLASICA: Mystery Box Clasica (stock: 10)
- MB-PREMIUM: Mystery Box Premium (stock: 5)
- JRS-001: Barcelona Local 23/24 (stock: 2, tallas M/L)
- JRS-002: Real Madrid Local 23/24 (stock: 3, tallas S/M/L)
- JRS-003: Manchester City Local 23/24 (stock: 2, tallas L/XL)
- JRS-004: Liverpool Local 23/24 (stock: 1, talla M)
- JRS-005: Inter Milan Local 23/24 (stock: 2, tallas S/M/L)
- JRS-006: Argentina Retro (stock: 3, tallas M/L/XL)

**IMPORTANTE:** Estos son placeholders. Diego necesita hacer conteo fisico y actualizar products.json con el inventario real.

### Ligas Representadas (historicamente)
Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Liga MX, Selecciones

---

## 5. BUYER PERSONA (del documento profesional)

**Nombre:** Jose, el Nostalgico Futbolero
- **Edad:** 25-30 anos
- **Genero:** Masculino
- **Ubicacion:** Ciudad de Guatemala (zonas 10, 15, 1, Mixco)
- **Clase:** Media alta
- **Ingreso:** Q10,000-Q15,000/mes
- **Perfil:** Comprador emocional/impulsivo
- **Descubre en:** TikTok (unboxings, contenido viral)
- **Convierte en:** WhatsApp (conversacion directa, confianza)
- **Motivacion:** "No compra para impresionar, compra para conectar"
- **Dolores:** No encuentra jerseys autenticos en Guatemala, todo es generico
- **Deseos:** Experiencia unica, sorpresa, pertenencia a comunidad

---

## 6. ESTRATEGIA DE CANALES (del Channel Mix doc)

| Canal | Peso | Rol |
|-------|------|-----|
| Instagram | 40% | Community building + DM sales |
| WhatsApp | 35% | Motor de conversion, confirmacion de pedidos |
| TikTok | 15% | Top-of-funnel awareness, contenido viral |
| Website | 10% | Punto de referencia y confianza, catalogo |

**Punto clave:** El website NO es el driver de ventas. Es vitrina. La conversion real pasa en DMs y WhatsApp. El website da legitimidad.

---

## 7. GTM — CALENDARIO DE LANZAMIENTO (del GTM doc)

### Semana 1: Teaser
- "Algo se viene..." stories y posts
- Reactivar conversaciones DM con clientes pasados
- Story polls: "Que camisa quieren ver?"

### Semana 2: Reveal
- "Estamos de vuelta" anuncio en IG + TikTok
- Website en vivo
- Contenido de reveal de Mystery Box

### Semana 3: Sale
- Primeras mystery boxes disponibles
- Serie de contenido de unboxing
- Flujo de pedidos por WhatsApp activo

### Semana 4: UGC
- Reposts de unboxings de clientes
- Reviews y testimonios
- Push de comunidad "Unite al Club"

### KPIs Target (del GTM doc)
- 30+ boxes vendidas en 15 dias
- 50 leads calificados via DM/WhatsApp
- 5K+ views en contenido de lanzamiento
- 500 nuevos seguidores
- 15 videos UGC de unboxing

---

## 8. BRAND IDENTITY (del Brandbook)

### Colores
| Token | Hex | Uso |
|-------|-----|-----|
| Carbon | #111111 | Primario — fondos, texto principal |
| Sand | #d4c5a9 | Secundario — bordes, acentos |
| Sand Light | #f0ead6 | Fondos secundarios |
| Cream | #faf7f2 | Fondo de pagina |
| Warm | #8b7355 | Texto de acento vintage |
| Gold | #c9a96e | Highlights, hover states |
| Success | #059669 | Stock disponible |
| Urgency | #dc2626 | Ultimas unidades, badges |

### Tipografia
Montserrat (400, 600, 700, 800) — bold sans-serif

### Tono de Voz
- Emocional, visual, directo, calido, picardia local
- Usa "vos" (espanol guatemalteco)
- Keywords de marca: Unbox, pieza, historia, legendaria, mistica, archivista del futbol
- PROHIBIDO: "stock", "envio inmediato", "producto generico", "la mejor calidad", "100% original"
- Frameworks de copy: AIDA y PAS con triggers emocionales
- Microcopy: "Descubri la box", "Revela la camiseta", "Unite al Club"
- CTA principal: "Pedi tu box secreta ahora"

### Logo
Escudo con caja abierta + icono de futbol, texto "EL CLUB MYSTERY BOX"
- `assets/img/brand/logo.png` — logo claro (86KB, 500x500)
- `assets/img/brand/logo-dark.png` — logo sobre fondo oscuro (340KB)

---

## 9. STACK TECNICO

| Componente | Tecnologia | Notas |
|------------|------------|-------|
| Website | HTML5 + Tailwind v4 Browser CDN + Vanilla JS | Sin build step |
| Hosting | GitHub Pages | Gratis, SSL via Let's Encrypt |
| Dominio | elclub.club | Propiedad de Diego |
| Pagos | Recurrente | Ya activo de VENTUS (4.5% + Q2/tx) |
| Repositorio | github.com/DiegoAF10/elclub | Publico |
| Analytics | Google Analytics 4 | Placeholder G-XXXXXXXXXX |
| DM Sales | Instagram DM + WhatsApp | Canales primarios de venta |
| Contenido | TikTok + Instagram Reels | Estrategia organica primero |

### Tailwind v4 Browser CDN
```html
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```
Con `@theme` directive en `elclub.css` para tokens custom.

---

## 10. SITIO WEB — ESTADO ACTUAL

### Paginas Construidas y Funcionales

| Pagina | Archivo | Lineas | Estado |
|--------|---------|--------|--------|
| Landing / Home | index.html | 539 | Funcional |
| Mystery Box | mystery-box.html | 614 | Funcional |
| Tienda (catalogo) | tienda.html | 302 | Funcional |
| Producto detalle | producto.html | 505 | Funcional |
| Nosotros | nosotros.html | 444 | Funcional |
| Contacto | contacto.html | 395 | Funcional |
| 404 | 404.html | 40 | Funcional |

### Archivos Core

| Archivo | Proposito |
|---------|-----------|
| `assets/css/elclub.css` | Design system completo con @theme tokens |
| `assets/js/cart.js` | Carrito localStorage + checkout WhatsApp |
| `assets/js/app.js` | Renderizado de productos, filtros, scroll reveal |
| `content/products.json` | Catalogo de productos (8 placeholders) |
| `CNAME` | Dominio elclub.club |

### Funcionalidades Verificadas (via Playwright)
- Hero renderiza con UVP en gold
- Grid de productos muestra imagenes de mystery box y placeholders SVG
- Seleccion de talla funciona (S/M/L/XL)
- Agregar al carrito funciona con toast notification
- Cart drawer se abre con items, controles de cantidad, total
- Boton "Pedir por WhatsApp" genera mensaje pre-formateado
- Filtros de tienda (liga, talla, ordenar) funcionan
- Pagina de producto detalle carga por query param (?id=)
- Badges de "Ultimas X" muestran correctamente
- Breadcrumb funcional
- Productos relacionados se muestran

### Verificacion Visual
El sitio fue probado en viewport desktop con Playwright. Se verifico:
- Homepage: hero, productos destacados, seccion mystery box, como funciona, social proof, footer
- Mystery Box: hero, 3 pasos, seleccion de tier, FAQ accordion
- Tienda: 8 productos, filtros, badges de stock
- Producto: imagen, info, tallas, agregar al carrito, productos relacionados

---

## 11. PENDIENTES CRITICOS

### Bloqueantes (Diego tiene que hacer)

| # | Tarea | Quien | Prioridad |
|---|-------|-------|-----------|
| 1 | **DNS** — Cambiar A records de elclub.club de Shopify (23.227.38.65) a GitHub Pages (185.199.108-111.153) | Diego (registrador de dominio) | URGENTE |
| 2 | **WhatsApp** — Reemplazar `50212345678` en cart.js con numero real | Diego | URGENTE |
| 3 | **Inventario fisico** — Contar ~60-100 camisetas reales | Diego | ALTA |
| 4 | **Actualizar products.json** — Con inventario real (equipos, tallas, cantidades reales) | COO + Diego | ALTA |

### Mejoras Tecnicas

| # | Tarea | Prioridad |
|---|-------|-----------|
| 5 | GA4 — Reemplazar `G-XXXXXXXXXX` con measurement ID real | MEDIA |
| 6 | Fotos de producto — Reemplazar placeholders SVG con fotos reales | MEDIA |
| 7 | GA4 en TODAS las paginas (solo index.html lo tiene) | MEDIA |
| 8 | OG image — Crear `/assets/img/brand/og-image.png` (1200x630) | MEDIA |
| 9 | TikTok embeds reales en mystery-box.html y index.html | BAJA |
| 10 | Instagram feed embed | BAJA |

### Estrategicos (roadmap)

| # | Tarea | Timeline |
|---|-------|----------|
| 11 | Ejecutar GTM semana 1 (teaser) | Esta semana |
| 12 | Reactivar Instagram @club.gt | Esta semana |
| 13 | Grabar primeros TikToks de relanzamiento | Esta semana |
| 14 | World Cup 2026 collection (requiere nuevo proveedor) | Marzo 2026 |
| 15 | Guia de tallas con medidas | Semana 2 |

---

## 12. OPORTUNIDAD WORLD CUP 2026

**El mundial empieza el 11 de junio de 2026** — quedan ~107 dias.

| Hito | Fecha | Accion |
|------|-------|--------|
| Contacto proveedor | 1 Mar | Pedir cotizacion de jerseys de selecciones WC |
| Pre-order launch | 15 Mar | Aceptar depositos |
| Llegada de stock | 15 Abr - 1 May | Recibir + fotografiar |
| Landing page WC | 1 May | Coleccion dedicada en vivo |
| Content blitz | 15 May - 19 Jul | Contenido diario WC |
| Peak sales | 1 Jun - 19 Jul | Periodo del torneo |

Esto es el catalizador de crecimiento mas importante. Guatemala, Mexico, USA en el mundial = demanda masiva.

---

## 13. CONTEXTO CRUZADO — ECOSISTEMA DIEGO

### Negocios de Diego
- **Clan Cervecero:** Importadora de cerveza, 12+ anos, 150+ PDV, Walmart. Skill: /coo-clan
- **VENTUS:** Tiras nasales DTC, lanzado Feb 2026. Skill: /coo-ventus
- **El Club:** Mystery boxes de futbol (ESTE). Skill: /coo-club (por crear)

### Recursos Compartidos
- **Recurrente:** Payment processor (ya activo, mismo de VENTUS)
- **GitHub Pages:** Hosting (mismo patron que VENTUS y Clan)
- **Stack web:** HTML5 + Tailwind v4 Browser + Vanilla JS (identico a VENTUS y Clan)
- **FENIX:** Sistema financiero personal de Diego (/fenix). Deuda total ~Q180k.
- **Salary:** Q15,000/mes fijo

### Diferencias Clave con Otros COOs

| Aspecto | coo-ventus | coo-clan | coo-club |
|---------|------------|----------|----------|
| Mentalidad | Supervivencia (quiebra si no vende) | Optimizacion (empresa establecida) | **Redencion (revivir negocio dormido, pagar deuda)** |
| Budget | Minimo ($130 ads) | Q75k/mes fijos | **Q0 absoluto** |
| Equipo | Solo Diego | 9 personas | **Solo Diego** |
| Canales | Website + IG + Ads | Walmart + 150 PDV | **IG + WhatsApp + TikTok** |
| Producto | Fisico (tiras nasales) | Fisico (cerveza importada) | **Fisico (camisetas futbol)** |
| Estacionalidad | Baja | Media (Navidad, verano) | **ALTA (World Cup 2026 = catalista)** |

---

## 14. DOCUMENTOS PROFESIONALES DE REFERENCIA

Ubicacion: `C:\Users\Diego\OneDrive - Clan Cervecero\EL CLUB\Documentos Profesionales\`

| Documento | Contenido Clave |
|-----------|-----------------|
| **GTM Strategy** | Calendario 4 semanas, KPIs, fases teaser→reveal→sale→UGC |
| **Buyer Persona** | "Jose el Nostalgico Futbolero", 25-30, zonas 10/15, Q10-15k ingreso |
| **Copywriting Guide** | AIDA/PAS frameworks, palabras prohibidas, microcopy, CTAs |
| **Channel Mix** | IG 40%, WA 35%, TikTok 15%, Web 10% |
| **Propuesta de Valor** | UVP, diferenciadores, manifesto de marca |
| **Brandbook** | Colores, tipografia, logo, tono, identidad visual |

**Excel de datos:** `C:\Users\Diego\OneDrive - Clan Cervecero\EL CLUB\MASTER EL CLUB.xlsm`
- Hojas: ESTADO DE RESULTADOS MENSUAL, INVENTARIO (vacio), VENTAS (35 records), GASTOS (Q70k), Opciones

---

## 15. RUTAS DE ARCHIVOS CRITICAS

### Sitio Web
```
C:\Users\Diego\el-club\                    ← Raiz del proyecto (git repo)
  index.html                                ← Landing page
  mystery-box.html                          ← Pagina de mystery box
  tienda.html                               ← Catalogo
  producto.html                             ← Detalle de producto
  nosotros.html                             ← Manifiesto de marca
  contacto.html                             ← Contacto
  404.html                                  ← Error page
  CNAME                                     ← elclub.club
  PRD.md                                    ← Product Requirements Document v2.0
  ONBOARDING.md                             ← ESTE archivo
  content/products.json                     ← Catalogo de productos
  assets/css/elclub.css                     ← Design system
  assets/js/cart.js                         ← Carrito + WhatsApp checkout
  assets/js/app.js                          ← App logic, filtros, renderizado
  assets/img/brand/logo.png                 ← Logo principal (86KB)
  assets/img/brand/logo-dark.png            ← Logo fondo oscuro (340KB)
  assets/img/brand/favicon.png              ← Favicon 32x32
  assets/img/brand/apple-touch-icon.png     ← Apple icon 192x192
  assets/img/products/mystery-box-clasica.jpg ← Foto mystery box (76KB)
  assets/img/products/placeholder.svg       ← Placeholder jersey SVG
```

### GitHub
- **Repo:** github.com/DiegoAF10/elclub
- **Branch:** main
- **Pages:** Habilitado (source: main, path: /)
- **Dominio:** elclub.club (CNAME configurado, DNS pendiente)

### Documentos de Marca (OneDrive)
```
C:\Users\Diego\OneDrive - Clan Cervecero\EL CLUB\
  MASTER EL CLUB.xlsm
  Documentos Profesionales\
    *.pdf (6 documentos de estrategia)
  Logos\
    *.png, *.svg (3 variantes)
  Shopify\
    *.png (foto mystery box original)
  Posts\
    *.png (8 disenos para IG)
  Caja Referencia\
    *.jpg (4 fotos de referencia de caja)
```

### Estado COO (por crear en sesion de skill)
```
C:\Users\Diego\club-coo\                   ← Directorio de estado del COO
  config\settings.json                      ← Configuracion del negocio
  config\CLAUDE.md                          ← Auto-memory
  tracker.json                              ← Iniciativas activas
  memory\club-notes.md                      ← Patrones y aprendizajes
  memory\CLAUDE.md                          ← Auto-memory
```

---

## 16. CHECKOUT FLOW — COMO FUNCIONA

```
1. Cliente navega sitio (o llega por IG/TikTok)
2. Selecciona producto + talla
3. Agrega al carrito (localStorage)
4. Abre cart drawer → ve items + total
5. Click "Pedir por WhatsApp"
6. Se abre wa.me con mensaje pre-formateado:

   "Hola! Quiero hacer un pedido en El Club:

   - Mystery Box Clasica (Talla M) x1 — Q400

   Total: Q400

   Espero confirmacion para proceder con el pago."

7. Diego responde por WhatsApp
8. Diego envia link de pago Recurrente
9. Cliente paga (4.5% + Q2 fee)
10. Diego empaca y entrega (personal/Guatex/Rabbit)
```

---

## 17. METRICAS CLAVE PARA EL COO

### Revenue / Ventas
- Cajas vendidas por semana
- Revenue semanal/mensual
- Ticket promedio
- Conversion rate (DM → venta)
- Inventory burn rate (a que ritmo se agota)

### Marketing / Growth
- Seguidores IG + TikTok (crecimiento semanal)
- Views en contenido
- DMs recibidos
- WhatsApp conversations iniciadas desde web
- UGC generado (videos de unboxing de clientes)

### Financiero
- Cash collected vs deuda pendiente
- % de inventario vendido
- Revenue per jersey (mystery box vs individual)
- Proyeccion de agotamiento de stock

---

*Generado por Loki Mode v5.53.0 el 2026-02-24. Toda la informacion aqui proviene de los 6 PDFs profesionales, el Excel MASTER, la sesion de construccion del sitio web, y el contexto directo de Diego.*
