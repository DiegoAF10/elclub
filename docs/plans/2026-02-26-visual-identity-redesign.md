# El Club — Brand Bible v2.0 "Midnight Stadium"

**Fecha:** 2026-02-26
**Versión:** 2.2 (actualizado — accent color ice blue para kit visual)
**Dirección creativa:** Streetwear Underground / Full Dark Mode / Monocromático
**Concepto:** "Midnight Stadium" — como entrar a un estadio vacío a medianoche. Oscuridad total. Solo bordes y siluetas atrapan la luz. Algo se revela en la penumbra.

---

## 1. Identidad de Marca

### Nombre
**EL CLUB**
- Siempre en mayúsculas en contextos de marca (logos, headers, packaging)
- En copy corrido se puede usar "El Club" con capitalización normal
- Nunca "el club" todo minúscula, nunca "EL CLUB MYSTERY BOX" (el anterior)

### Concepto
Mystery boxes y camisetas de fútbol curadas. No es una tienda — es una experiencia. No vendemos camisetas — entregamos historia.

### Dirección creativa: Midnight Stadium
La marca se siente como entrar a un estadio vacío a medianoche. Oscuridad dominante. Silencio tenso. Solo los bordes atrapan la luz de la luna. Blanco y negro. Sin color. La ausencia de color ES la declaración. Las camisetas de fútbol — llenas de color — son las que rompen el monocromo cuando aparecen. Esa tensión entre la oscuridad de la marca y el color del producto es el corazón visual de El Club.

### UVP (Propuesta de Valor Única)
> "No vendemos camisetas. Entregamos historia."

### Posicionamiento
> "La única experiencia futbolera en Guatemala donde el fútbol no se compra, se revela."

### Taglines aprobados
- "Solo para los que entienden" ← principal
- "La camiseta con historia"
- "Tu club. Tu historia. Tu box."
- "Cada caja que abrís es un pedazo de historia que no sabías que necesitabas"
- "Entrás al Club o te quedás afuera" ← streetwear attitude

---

## 2. Paleta de Colores

### Filosofía: Monocromático + un destello
La base de la marca es blanco y negro. El logo es 100% monocromático — NUNCA lleva color. Pero el kit visual tiene un único color de realce: **ice blue** (#4DA8FF). Representa la luz de los reflectores en un estadio a medianoche — frío, eléctrico, nocturno.

El color aparece en el ecosistema de forma controlada:
1. **Ice blue** — CTAs, links, badges de urgencia, hover states, highlights en posts
2. **Las camisetas de fútbol** — el producto ES la explosión de color
3. **El botón de WhatsApp** — verde obligatorio por la plataforma

El ice blue es streetwear nativo (Palace, Off-White, Jordan lo usan sobre negro). No compite con los colores de las camisetas. Funciona como "luz de estadio" que guía la mirada sin romper la oscuridad.

### Colores de marca

| Token | Hex | RGB | Uso |
|-------|-----|-----|-----|
| `midnight` | `#0D0D0D` | 13, 13, 13 | Fondo principal, navbar, footer, hero, cards |
| `pitch` | `#1C1C1C` | 28, 28, 28 | Superficies elevadas, secciones alternas, cards |
| `chalk` | `#2A2A2A` | 42, 42, 42 | Bordes, separadores, hover states sobre pitch |
| `slate` | `#333333` | 51, 51, 51 | Bordes activos, divisiones más visibles |
| `white` | `#F0F0F0` | 240, 240, 240 | Texto principal, CTAs, elementos primarios |
| `smoke` | `#999999` | 153, 153, 153 | Texto secundario, descripciones |
| `ash` | `#666666` | 102, 102, 102 | Texto terciario, metadata, timestamps |

### Color de realce (kit visual, NO en logo)

| Token | Hex | RGB | Uso |
|-------|-----|-----|-----|
| `ice` | `#4DA8FF` | 77, 168, 255 | CTAs, links, badges de urgencia, hover highlights, elementos interactivos |
| `ice-glow` | `#4DA8FF33` | — | Glow sutil (20% opacity) para hover states, focus rings |
| `ice-dim` | `#3B82B0` | 59, 130, 176 | Hover/active state del ice (más oscuro) |

**Reglas del ice blue:**
1. NUNCA en el logo. El logo es B&W puro. Siempre.
2. Usar con moderación — es un destello, no un baño de color.
3. Máximo 10-15% de la superficie visual. Si hay demasiado azul, se pierde el efecto "midnight".
4. Funciona mejor como punto focal: un botón, un link, un badge. No como fondo.
5. Sobre `midnight` o `pitch` solamente. Nunca sobre `white`.

### Colores funcionales (solo utilitarios)

| Token | Hex | Uso |
|-------|-----|-----|
| `whatsapp` | `#25D366` | Botón WhatsApp (obligatorio por plataforma) |
| `success` | `#22C55E` | Confirmaciones de pedido (solo en flujos, no en UI visible) |
| `alert` | `#F0F0F0` | Badges de urgencia ("ÚLTIMAS 3") — mismo blanco, el contraste basta |

### Reglas de uso

1. **Fondo de página:** SIEMPRE `midnight`. No hay modo claro. Dark mode es la identidad.
2. **Cards/contenedores:** `pitch` con borde `chalk` 1px.
3. **Ice blue para interacción.** Links, CTAs primarios, badges activos, hover highlights.
4. **Blanco para contenido.** Texto, headlines, íconos estáticos.
5. **Texto principal:** `white` (#F0F0F0) — no blanco puro (#FFFFFF) para reducir fatiga visual.
6. **Jerarquía de texto:** white → smoke → ash (3 niveles, nunca más).
7. **Contraste mínimo:** Todo texto debe cumplir WCAG AA sobre su fondo.
8. **Fotos de producto:** Las camisetas sobre fondo `midnight` o `pitch`. El color del producto brilla contra el B&W.
9. **Ice blue con moderación:** Máximo 10-15% de superficie. Si hay mucho azul, se pierde la oscuridad.
10. **Verde WhatsApp** solo en el botón flotante y checkout.
11. **LOGO SIEMPRE B&W.** Ice blue NUNCA toca el logo.

### Combinaciones válidas

| Fondo | Texto primario | Texto secundario | CTA | Links/interacción |
|-------|---------------|-----------------|-----|-------------------|
| midnight | white | smoke | ice (botón sólido) | ice |
| pitch | white | smoke | ice (botón sólido) | ice |
| white (excepcional) | midnight | ash | midnight (botón sólido) | midnight |

---

## 3. Tipografía

### Headline / Display
**Oswald 700 (Bold)**
- Google Fonts: `https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&display=swap`
- Uso: Títulos, headers, hero text, badges, precios
- Siempre en MAYÚSCULAS (`text-transform: uppercase`)
- Letter-spacing: `0.05em` a `0.1em`
- Tamaños: 48-80px (hero), 32-40px (section titles), 18-24px (card titles)

### Body / UI
**Space Grotesk 400/500**
- Google Fonts: `https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap`
- Uso: Texto corrido, descripciones, navegación, botones, formularios
- Capitalización normal (sentence case)
- Letter-spacing: `0` (default) o `0.02em` para small text
- Tamaños: 16px (base), 14px (small/metadata), 12px (tiny/badges)

### Wordmark
El wordmark "EL CLUB" debajo del logo usa una **sans-serif light con tracking amplio** — coherente con el logo aprobado. En web se puede aproximar con Space Grotesk 400, uppercase, tracking 0.2em.

### Reglas tipográficas

1. **Oswald SOLO para headlines.** Nunca para párrafos de más de 2 líneas.
2. **Space Grotesk para TODO lo demás.** Navegación, botones, copy, descripciones.
3. **Headers siempre en uppercase** con Oswald.
4. **No usar Montserrat.** Es la identidad anterior.
5. **No más de 2 fuentes.** Oswald + Space Grotesk, punto.
6. **Peso mínimo para legibilidad en dark mode:** Space Grotesk 400 (no 300).

### Escala tipográfica

| Elemento | Fuente | Peso | Tamaño | Tracking | Transform |
|----------|--------|------|--------|----------|-----------|
| Hero headline | Oswald | 700 | 48-80px | 0.05em | uppercase |
| Section title | Oswald | 700 | 32-40px | 0.08em | uppercase |
| Card title | Oswald | 600 | 18-24px | 0.05em | uppercase |
| Price | Oswald | 700 | 24-32px | 0 | — |
| Badge text | Oswald | 700 | 11-12px | 0.1em | uppercase |
| Body text | Space Grotesk | 400 | 16px | 0 | — |
| Small text | Space Grotesk | 400 | 14px | 0.02em | — |
| Button text | Space Grotesk | 600 | 14px | 0.05em | uppercase |
| Nav links | Space Grotesk | 600 | 14px | 0.08em | uppercase |
| Input text | Space Grotesk | 400 | 16px | 0 | — |
| Tiny/meta | Space Grotesk | 400 | 12px | 0.02em | — |

---

## 4. Logo

### Concepto aprobado
Escudo geométrico con las letras **E** (izquierda) y **C** (derecha) integradas como parte estructural del escudo — los trazos de las letras se fusionan con los bordes del escudo. Un **slash diagonal como espacio negativo** corta el centro, separando la E de la C. El slash se extiende ligeramente más allá de los bordes del escudo (arriba-izquierda y abajo-derecha). **2-3 fragmentos pequeños** se desprenden de la esquina inferior derecha, dando vida y movimiento contenido.

Debajo del escudo: wordmark **"EL CLUB"** en sans-serif light, uppercase, tracking amplio.

### Monocromático
- Escudo y letras: `white` (#F0F0F0) sobre `midnight` (#0D0D0D)
- Slash: espacio negativo (el fondo `midnight` se asoma a través del escudo blanco)
- SIN color de acento en el logo. Nunca.
- Variante inversa (excepcional): `midnight` sobre fondo blanco

### Fragmentos como sistema gráfico
Los fragmentos del logo no son solo decoración — son un **sistema gráfico extensible**:
- En posts de IG: fragmentos flotando como elementos decorativos
- En stories: fragmentos como transiciones
- En packaging: fragmentos como patrón sutil
- En headers web: fragmentos como separadores de sección
- Los fragmentos siempre son blancos sobre negro (o negro sobre blanco en excepciones)

### Composiciones

| Variante | Uso |
|----------|-----|
| Escudo + Wordmark (vertical) | Uso principal — web header, packaging, social |
| Escudo solo | Favicon (32×32), avatar IG/TikTok, stickers, sellos |
| Wordmark solo | Headers horizontales angostos, pie de emails |

### Zona de protección
Espacio libre alrededor del logo = altura del escudo × 0.5 en todos los lados.

### Prohibiciones
- No agregar color al logo (ni rojo, ni dorado, ni ningún otro)
- No estirar, rotar, o distorsionar
- No agregar sombras, gradientes, o efectos
- No poner sobre fondos que compitan (fotos coloridas sin overlay oscuro)
- No cambiar las proporciones entre escudo y wordmark
- No quitar los fragmentos del escudo (son parte del logo)
- No agregar "MYSTERY BOX" ni ningún otro texto al logo

### Archivos requeridos (post-vectorización)

| Archivo | Formato | Uso |
|---------|---------|-----|
| `logo-full.svg` | SVG | Escudo + wordmark, escalable |
| `logo-full-dark.svg` | SVG | Versión para fondos claros (excepcional) |
| `logo-icon.svg` | SVG | Solo escudo, para avatar/favicon source |
| `logo-icon.png` | PNG 512×512 | IG/TikTok avatar |
| `logo-wordmark.svg` | SVG | Solo wordmark "EL CLUB" |
| `favicon.png` | PNG 32×32 | Favicon browser |
| `apple-touch-icon.png` | PNG 192×192 | iOS shortcut |
| `og-image.png` | PNG 1200×630 | Social sharing (escudo centrado sobre midnight) |

---

## 5. Tono de Voz

### Personalidad
- **Misterioso:** No revelamos todo. Dejamos que la curiosidad haga el trabajo.
- **Directo:** Sin rodeos. Frases cortas. Puntos.
- **Confiado:** Sabemos lo que hacemos. No pedimos disculpas.
- **Local:** Voseo guatemalteco. Picardía. Cultura de barrio.

### Cómo hablamos

| Contexto | Estilo | Ejemplo |
|----------|--------|---------|
| Headlines | Cortos, impactantes, uppercase feeling | "NO VENDEMOS CAMISETAS. ENTREGAMOS HISTORIA." |
| Descripciones | Directos, emocionales, 2-3 oraciones max | "Cada caja está curada para vos. No sabés qué viene. Esa es la magia." |
| CTAs | Imperativo, urgente, personalizado | "Pedí tu box", "Revelá la camiseta", "Unite al Club" |
| Social media | Casual, con picardía, voseo | "Mirá lo que le tocó a este crack" |
| WhatsApp | Cercano, como un cuate | "¡Buena! ¿Querés la Clásica o la Premium?" |

### Voseo obligatorio
- "Vos", "tenés", "querés", "sabés", "pedí", "mirá", "fijate"
- NUNCA tuteo ("tú", "tienes") ni ustedeo ("usted")
- NUNCA español neutro o español de España

### Palabras de marca (usar frecuentemente)
`revelar` · `descubrir` · `pieza` · `historia` · `legendaria` · `mística` · `unbox` · `curada` · `edición` · `club`

### Palabras PROHIBIDAS (nunca usar)
`stock` · `envío inmediato` · `producto genérico` · `la mejor calidad` · `100% original` · `réplica` · `copia` · `barato` · `oferta` · `descuento` (usar "acceso" o "precio especial" en su lugar)

### Frameworks de copy

**AIDA (para posts de producto):**
1. **Attention:** Hook visual o pregunta provocadora
2. **Interest:** Historia de la camiseta o del equipo
3. **Desire:** Escasez, exclusividad, misterio
4. **Action:** CTA a WhatsApp/DM

**PAS (para stories/reels):**
1. **Problem:** "¿Otra vez la misma camiseta genérica de la Sexta?"
2. **Agitate:** "En Guatemala no hay dónde encontrar piezas que cuenten algo."
3. **Solve:** "En El Club, cada box es una historia que no sabías que necesitabas."

---

## 6. Fotografía y Contenido Visual

### Estilo fotográfico
- **Fondo:** Negro o muy oscuro (midnight/pitch). NUNCA fondos blancos, de madera, o coloridos.
- **Iluminación:** Dramática. Luz dura lateral o spot desde arriba. Sombras profundas.
- **Producto:** La camiseta es la estrella. Bien doblada o en flat lay sobre negro. El COLOR de la camiseta es el único color en la imagen.
- **Mood:** Cinematográfico, nocturno, misterioso.
- **Edición:** Alto contraste. Negros profundos. Desaturar todo excepto la camiseta.

### Tipos de contenido visual

| Tipo | Plataforma | Descripción |
|------|-----------|-------------|
| Product shot | Web + IG Feed | Camiseta en flat lay sobre fondo midnight. La camiseta es la explosión de color. |
| Unboxing video | TikTok + Reels | POV abriendo la caja. Iluminación dramática. Del negro al color. |
| Detail shot | IG Carousel | Close-up del escudo, textura, etiqueta |
| Mystery reveal | TikTok + Stories | "¿Qué hay adentro?" → reveal con transición |
| Lifestyle | IG Feed | Persona vistiendo la camiseta en contexto urbano nocturno |
| Fragment graphics | IG Stories + Posts | Fragmentos del logo como elementos gráficos decorativos |

### Overlays y gráficos
- Textos sobre foto: siempre Oswald uppercase, blanco
- Badges: fondo `white`, texto `midnight`, Oswald 700 — O fondo transparente con borde blanco
- Fragmentos del logo como elementos decorativos flotantes
- Nunca más de 1-2 elementos gráficos sobre una foto

### El concepto "Del negro al color"
La narrativa visual central: todo es monocromático (la marca, el packaging, el fondo) y la CAMISETA es lo que trae el color. El unboxing es literalmente pasar de B&W a color. Esto aplica en:
- Fotos de producto (fondo B&W, camiseta a color)
- Videos de unboxing (empezar en B&W, al abrir la caja aparece el color)
- Feed de Instagram (posts gráficos en B&W alternados con product shots a color)

---

## 7. Componentes UI (Design System)

### Botones

| Tipo | Fondo | Texto | Borde | Hover |
|------|-------|-------|-------|-------|
| Primary | `ice` | `midnight` | — | `ice-dim` fondo, `midnight` texto |
| Secondary | transparent | `white` | `white` 2px | fill `white`, text `midnight` |
| WhatsApp | `#25D366` | `white` | — | `#128C7E` |
| Ghost | transparent | `smoke` | — | text `ice` |

Todos los botones: Space Grotesk 600, 14px, uppercase, tracking 0.05em, padding 12px 28px.

### Cards de producto
- Fondo: `pitch` (#1C1C1C)
- Borde: `chalk` (#2A2A2A) 1px
- Hover: borde `ice` (#4DA8FF), sutil translateY(-2px)
- Imagen: aspect-ratio 1:1, object-fit cover sobre fondo `pitch`
- Título: Oswald 600, white
- Precio: Oswald 700, white
- Texto secundario: Space Grotesk 400, smoke

### Badges
- "ÚLTIMAS X": fondo `ice`, texto `midnight`, Oswald 700, 11px, uppercase
- "NUEVO": borde `ice` 1px, texto `ice`, fondo transparent, Oswald 700, 11px, uppercase
- "POPULAR": fondo `white`, texto `midnight`, Oswald 700, 11px, uppercase

### Navegación
- Fondo: `midnight`
- Links: Space Grotesk 600, 14px, `white`, uppercase, tracking 0.08em
- Link activo: `ice` con underline
- Hover: `smoke` → `ice` transición
- Logo: izquierda, escudo + wordmark

### Inputs (formularios)
- Fondo: `pitch`
- Borde: `chalk` 1px
- Texto: `white`
- Placeholder: `ash`
- Focus: borde `ice`

### Footer
- Fondo: `midnight`
- Borde superior: `chalk` 1px
- Texto: `smoke` (links), `ash` (copyright)
- Hover links: `ice`

---

## 8. Aplicaciones de Marca

### Packaging (caja mystery box)
- Caja kraft negra o con sticker negro mate
- Sello/sticker del escudo en blanco sobre negro
- Interior: papel tissue negro
- Thank you card: fondo `midnight`, escudo en `white`, texto "Bienvenido al Club." + @club.gt
- Fragmentos del logo como patrón sutil en el interior de la caja

### Instagram Feed (@club.gt)
- Grid estético: B&W gráficos alternados con product shots a color
- Bio: "No vendemos camisetas. Entregamos historia. ⚽"
- Avatar: Escudo del logo (blanco sobre negro)
- Highlights: Iconos minimalistas blancos sobre negro
- Stories: Usar fragmentos del logo como elementos gráficos

### TikTok (@club.gtm)
- Avatar: Mismo escudo que IG
- Content style: Dark, cinematográfico, transiciones de B&W a color
- Text overlays: Oswald uppercase, blanco

### WhatsApp
- Mensaje de bienvenida: "¡Bienvenido al Club! ⚽ ¿En qué te ayudo?"
- Formato de pedido: limpio, blanco sobre fondo oscuro del chat

### Website (elclub.club)
- Full dark mode. Sin modo claro. NUNCA.
- Hero: Headline Oswald gigante en blanco sobre midnight
- Secciones alternas: midnight → pitch → midnight
- CTAs: botones ice blue sólidos — el destello que guía la mirada
- Links y elementos interactivos: ice blue
- Imágenes de producto: las camisetas son la explosión de color
- Fragmentos del logo como separadores de sección

---

## 9. Qué Cambia vs. Identidad Anterior

| Elemento | Antes (v1) | Ahora (v2.1 Midnight Stadium) |
|----------|-----------|-------------------------------|
| Dirección | Premium cálido | Streetwear underground monocromático |
| Paleta | Crema + gold + arena + warm | Negro + blanco. Punto. |
| Fondo | Crema (#faf7f2) | Midnight (#0D0D0D) |
| Acento | Gold (#c9a96e) | Ice blue (#4DA8FF) — solo kit visual, nunca en logo |
| Headlines | Montserrat 800 | Oswald 700 |
| Body | Montserrat 400 | Space Grotesk 400 |
| Logo | Escudo ornamentado + "EL CLUB MYSTERY BOX" | EC integrado en escudo + slash + fragmentos |
| Buttons | Negro con hover gold | Ice blue sólido con hover ice-dim |
| Badges | Rojo urgencia / gold nuevo | Ice blue / blanco sobre midnight |
| Sensación | "Boutique vintage elegante" | "Estadio vacío a medianoche" |
| Tono | Cálido, nostálgico | Misterioso, confiado, austero |
| Color de producto | Compite con la marca | ES el único color — el producto brilla |

---

## 10. Lo que NO Cambia

1. **UVP:** "No vendemos camisetas. Entregamos historia." — intocable
2. **Voseo guatemalteco** — siempre
3. **Canal mix:** IG 40% / WA 35% / TikTok 15% / Web 10%
4. **WhatsApp como canal de cierre** — todo flujo termina ahí
5. **Buyer persona core:** Hombre 25-30, Guate City, comprador emocional
6. **Copy frameworks:** AIDA + PAS
7. **Palabras prohibidas:** stock, envío inmediato, producto genérico, etc.
8. **Stack técnico:** HTML + Tailwind v4 + Vanilla JS + GitHub Pages
9. **Concepto mystery box** como producto hero

---

## 11. Archivos a Generar/Actualizar

| Archivo | Acción | Prioridad |
|---------|--------|-----------|
| `assets/css/elclub.css` | Reescribir — paleta monocromática, nueva tipografía, componentes B&W | CRÍTICA |
| `index.html` | Actualizar — full dark mode, Oswald + Space Grotesk, CTAs blancos | CRÍTICA |
| `mystery-box.html` | Actualizar — misma dirección | ALTA |
| `tienda.html` | Actualizar | ALTA |
| `producto.html` | Actualizar | ALTA |
| `nosotros.html` | Actualizar — corregir "Fundado en 2025" → 2023, nuevo tono | ALTA |
| `contacto.html` | Actualizar | ALTA |
| `404.html` | Actualizar | MEDIA |
| `assets/img/brand/logo.png` | Reemplazar con nuevo escudo EC (vectorizado) | CRÍTICA |
| `assets/img/brand/logo-dark.png` | Reemplazar — versión para fondos claros | ALTA |
| `assets/img/brand/favicon.png` | Reemplazar con escudo solo 32×32 | ALTA |
| `assets/img/brand/apple-touch-icon.png` | Reemplazar 192×192 | ALTA |
| `assets/img/brand/og-image.png` | Crear — escudo centrado sobre midnight, 1200×630 | ALTA |

---

*Brand Bible v2.2 "Midnight Stadium" — El Club, Guatemala. Febrero 2026.*
*Monocromático + ice blue. Escudo EC con slash y fragmentos. Streetwear underground.*
*Dirección creativa definida por Diego Arriaza Flores.*
