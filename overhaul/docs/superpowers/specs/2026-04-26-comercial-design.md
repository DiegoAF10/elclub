# Comercial — Diseño y especificación

**Fecha:** 2026-04-26
**Autor:** Diego + Claude (sesión brainstorming)
**Status:** Diseño · pendiente review de Diego antes de plan de implementación
**Approach final:** CK3 Tabs (sub-tabs dentro de Comercial)
**Releases planificados:** 6 (R1 → R6, ~13-18 días de trabajo)

---

## 1. Resumen ejecutivo

Comercial es la sección del ERP de El Club donde Diego gestiona el **ciclo completo de ventas** — desde que un ad atrae a una persona hasta que esa persona se vuelve cliente recurrente. **NO incluye** finanzas (eso vive en FÉNIX), ni inventario físico (eso vive en imports/supply chain).

El overhaul reemplaza el actual `comercial.py` de Streamlit por una sección integrada al ERP Tauri (overhaul/) con:

- **Sub-navegación CK3-style** — 5 tabs dentro de Comercial: Funnel · Customers · Inbox · Ads · Settings.
- **Pulso bar persistente** — KPIs del día siempre visibles arriba (revenue · órdenes · leads · conv rate · ad spend · ROAS).
- **Modal pattern para todos los detail views** — click "ver detalle" en cualquier entidad abre una ventana grande estilo CK3 character window con header rico + stats + body 2 columnas + footer de acciones.
- **Inbox de eventos por severidad** — ordenados por dolor: órdenes pendientes > ads alerts > pulso > leads sin responder > VIP retention.
- **Integración ManyChat Nivel 2** — sync de threads (transcripciones leíbles desde el ERP), responder afuera (botón "Mensaje WA" abre `wa.me`).

El espíritu visual es **retro gaming / terminal** (Football Manager, CK3, EU4): denso, gamey, expert-friendly. NO Notion/Linear/Stripe minimalism.

---

## 2. Contexto y objetivos

### Por qué overhaul

El actual `erp/comercial.py` (Streamlit, ~462 LOC) cubre las dimensiones funcionales (customers, sales, attribution, sync vault_orders) pero **no es accionable**: es una colección de tabs sin flujo, donde cada KPI vive en una pantalla distinta y las decisiones requieren saltar entre 5 herramientas externas (Meta Ads Manager, ManyChat, WhatsApp Business, Recurrente, Streamlit).

Diego experimentó "el otro lado" cuando construimos el modo Audit del ERP: una pantalla densa, accionable, con identidad visual. Quiere replicar esa experiencia para Comercial.

### Mental model

Diego piensa como un strategy gamer (SimCity, Cities Skylines, EU4, CK3, Football Manager). Manejar El Club es, en sus palabras, "la versión adulta de estos juegos con réditos reales". El diseño se apoya en ese modelo:

- **Densidad de información OK** si está organizada por capas/contextos.
- **Drilldown infinito** — click en cualquier entidad revela ventana grande con todo su detalle + acciones.
- **Eventos demandan decisiones** — como CK3 popups o EU4 events.
- **Causalidad visible** — "esta venta vino de esta campaign que vino de este ad creative".
- **Time control** — slider de período (Hoy / 7d / 30d / Custom).
- **Sense of agency** — todas las acciones del juego (pausar campaign, marcar despachado, generar cupón) viven dentro del mismo lugar.

### Objetivos concretos

1. **Reemplazar el Streamlit actual** para el ciclo de ventas. El Streamlit puede mantenerse para imports/inventory/audit-batch hasta que se overhaule también.
2. **Reducir saltos entre herramientas** — Comercial es el único lugar donde Diego ve y acciona ventas/leads/ads/customers.
3. **Sentido de panorama y control** — entrar a Comercial debe dar la sensación de "abrir el tablero del juego", no "abrir un dashboard".
4. **Cero decisiones perdidas** — eventos críticos (orden pendiente, campaign caída) son visibles sin esfuerzo.

---

## 3. Arquitectura general

### Inserción en el ERP existente

Comercial es un item del sidebar global del ERP (sección Data). El sidebar global no se modifica:

```
ERP Sidebar (sin cambios)
├── WORKFLOW
│   ├── Queue
│   ├── Audit                    ← donde Diego trabaja hoy
│   ├── Mundial 2026
│   └── Publicados
└── DATA
    ├── Comercial                ← este spec
    ├── Dashboard
    └── Inventario
```

Click "Comercial" → entra al modo Comercial. El cuerpo principal del ERP cambia a:

```
┌──────────────────────────────────────────────────────┐
│ TABS: [Funnel] [Customers] [Inbox 8] [Ads] [Settings]│
├──────────────────────────────────────────────────────┤
│ PULSO BAR: Q · órdenes · leads · conv · spend · ROAS │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Cuerpo del tab activo (cambia según selección)       │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Reglas arquitectónicas

1. **Comercial es UN item del sidebar, no varios.** Inbox/Funnel/etc. son sub-tabs adentro, no items globales.
2. **El pulso bar persiste entre tabs.** Cambies de tab o no, los KPIs del período seleccionado están siempre arriba.
3. **El sidebar global del ERP no se toca.** Audit sigue funcionando exactamente como hoy.
4. **El último tab abierto se recuerda en localStorage.** Click "Comercial" después de cerrar entra al tab donde estabas (ej. Inbox), no resetea a Funnel.

### Navegación cruzada

| Salida | Destino |
|---|---|
| Click otro item del sidebar (Audit/Mundial/etc.) | Sale de Comercial. Al volver, restaura último tab. |
| Cmd+K command palette | Acepta queries cross-tab: "Pedro G" → modal customer; "CE-JTZZ" → modal orden; "Mystery Box" → tab Ads con campaign abierta. |
| ESC dentro de un modal | Cierra el modal, queda en el tab. |
| Click fuera del modal (backdrop) | Cierra el modal. |

---

## 4. Los 5 tabs en detalle

### Tab 1 · Funnel (default)

**Layout:** 5 etapas como grid horizontal de 5 columnas. Cada etapa con número grande (mono font) + 3 métricas detalle (mono).

**Las 5 etapas:**

```
[1] Awareness     → impressions, clicks, ad spend, CTR
[2] Interest      → leads nuevos por canal (WA / IG / Messenger)
[3] Consideration → conversaciones activas, esperando algo
[4] Sale          → órdenes hoy, esperando pago, esperando despacho
[5] Retention     → customers totales, repeat rate, VIP inactivos, LTV avg
```

**Estados visuales por etapa:**
- 1-2 (cold): azul (#60a5fa)
- 3 (warm): amarillo (#fbbf24)
- 4 (success): verde terminal (#4ade80)
- 5 (neutral): gris (#b4b5b8)
- Etapa con eventos críticos: bordes rojos (#f43f5e)

**Conversion arrows:** entre etapas, badge mono con % de conversión a la siguiente.

**Drilldown:** click una etapa → modal de drilldown con tabla de items + acciones quick.

**Acciones del header:**
- "⇄ Comparar período" → vista split (hoy vs ayer / mes vs anterior)
- "⇣ Exportar CSV" → datos del funnel actual

### Tab 2 · Customers

**Layout:** lista filtrable de customers, ordenable por LTV / última compra / primera compra / total orders / canal de origen.

**Estructura por row:**
```
🏴 Pedro G.  ★VIP        5 órdenes   Q2,140 LTV   últ 12d
pedro.g@... · WA · llegó por Mystery Box (MSG-MYSTERY-A)
```

**Filtros:**
- Por VIP status (LTV ≥ Q1,500)
- Por canal de origen (WA / IG / Messenger / referido / orgánico)
- Por última compra (<30d / 30-60d / 60-90d / +90d)
- Por traits/tags (editables manualmente desde modal)

**Drilldown:** click customer → modal Customer Profile (ver Sec 5).

**Acciones del header:**
- "Crear customer manual" (cuando el cliente te escribe por fuera del bot)
- "⇣ Exportar CSV"
- Buscador (nombre, phone, email, IG handle)

### Tab 3 · Inbox

**Layout:** eventos agrupados por severidad. Como bandeja de entrada en Football Manager.

```
🔴 Crítico     · 2 eventos
🟡 Atención    · 2 eventos
🔵 Info        · 2 eventos
⚪ Estratégico · 2 eventos
```

**Tipos de eventos (catalog):**

| Tipo | Detección | Severidad | Auto-resolve |
|---|---|---|---|
| Órdenes pendientes despacho >24h | Cron 1h | 🔴 Crítico | Cuando todas pasan a `shipped` |
| Campaign performance ↓ >30% | Cron 6h | 🔴 Crítico | Cuando vuelve a benchmark |
| Leads sin responder >12h | Cron 1h | 🟡 Atención | Cuando se responde |
| Stock bajo (<3 unidades de SKU) | Webhook orden cerrada | 🟡 Atención | Cuando stock vuelve >3 |
| Nueva orden | Webhook Recurrente | 🔵 Info | Auto-archive 24h |
| Resumen de leads del día | Cron 1d | 🔵 Info | Auto-archive 24h |
| VIP inactivos +60d | Cron 1d | ⚪ Estratégico | Cuando vuelven a comprar |
| Goal mensual progress | Cron 1d | ⚪ Estratégico | Fin de mes |

**Drilldown:** click evento → modal específico de cada tipo (Order detail, Conversation thread, Campaign detail, etc.)

**Filtros:**
- Por severidad (chips toggleables)
- Buscador (texto libre, busca en título y sub)

**Acciones rápidas (sin abrir modal):**
- "Ignorar" → marca evento como dismissed (no aparece más, queda en `comercial_events.status='ignored'`)
- "Resolver" → marca como done (algunas requieren acción adicional, esto sólo acepta cuando ya está resuelto)

### Tab 4 · Ads

**Layout:** lista de campaigns Meta activas con performance del período seleccionado.

**Estructura por campaign:**
```
MSG-MYSTERYBOX-A      ACTIVE
Q420 spent · 1,247 imp · 47 clicks · CTR 1.4% · ROAS 5.2×
─────────────────────
[pausar] [duplicar] [ver creative]
```

**Métricas mostradas:**
- Status (active / paused / ended)
- Budget gastado vs budget total
- Impressions, clicks, CTR, CPC
- Conversions atribuidas (leads + ventas)
- ROAS (revenue / spend)
- Trend vs período anterior (↑↓ con %)

**Drilldown:** click campaign → modal Campaign Detail con time-series chart + lista de leads/órdenes atribuidos.

**Acciones del header:**
- "+ Nueva campaign" (lanza el flow de creación, posiblemente delega a `club-coo/ads/launch-message-campaign.js`)
- "⇣ Exportar CSV"

### Tab 5 · Settings

**Layout:** secciones colapsables.

**Secciones:**

1. **Umbrales** — editables. Defaults: orden pendiente = 24h, leads sin responder = 12h, stock bajo = 3 unidades, campaign drop = -30%.
2. **Goals** — meta mensual de revenue (default Q25,000), goal de conversion rate, goal de ROAS.
3. **Notifications** — para cada tipo de evento: ¿Inbox? ¿Push WA Diego? ¿Ambos?
4. **Integrations** — estado de conexiones (Recurrente · Meta Ads · ManyChat · WhatsApp Cloud API si está activo). Última sync, errores recientes, botón "Re-sync ahora".
5. **Sync log** — últimas 10 syncs con timestamp + duración + count de items.

---

## 5. Patrón modal — la "carta del juego"

Todos los "ver detalle" abren ventanas emergentes (overlays con backdrop blur), no desplegables inline. Cada modal sigue el mismo esqueleto de 4 zonas:

```
┌────────────────────────────────────────────────┐
│ HEADER RICO                                  ✕ │
│ Avatar · Nombre · Badge · Traits · Meta        │
├────────────────────────────────────────────────┤
│ STATS STRIP (5 columnas)                       │
│ Métrica1 · Métrica2 · Métrica3 · ...           │
├──────────────────────────┬─────────────────────┤
│                          │                     │
│ BODY · timeline narrativo│ BODY · datos        │
│ (eventos, historia)      │ estables (factbook) │
│                          │                     │
├──────────────────────────┴─────────────────────┤
│ FOOTER                                         │
│ [Acción primaria] [Acc 2] [Acc 3]    [Cerrar] │
└────────────────────────────────────────────────┘

Backdrop: blur del tab activo + overlay oscuro
ESC cierra · click backdrop cierra · ⌘K abre command palette
```

### Catálogo de modals

| Modal | Se abre desde | Header muestra | Acciones primarias |
|---|---|---|---|
| **Customer profile** | Customers list, Funnel-Retention drilldown, timeline de otra modal | Avatar, nombre, VIP badge, traits, contacto, atribución | Crear orden manual · Mensaje WA · Ver conversaciones · Generar cupón · Editar traits · Bloquear |
| **Order detail** | Funnel-Sale drilldown, Inbox eventos de órdenes, Customer timeline | Ref orden, status, amount, cliente | Marcar despachado · Generar guía Forza · Contactar cliente · Refund · Ver tracking |
| **Conversation thread** | Inbox eventos de leads, Customer "ver conversaciones", Funnel-Consideration | Cliente, plataforma (WA/IG/Msg), última actividad, outcome | Responder en WA · Asignar a bot · Marcar resuelto · Crear orden manual |
| **Campaign detail** | Ads tab, Customer atribución, Inbox eventos de campaigns | Nombre campaign, status, budget, time-series mini chart | Pausar · Duplicar · Ver creative · Ajustar budget · Ver atribución completa |
| **Event detail** | Inbox cualquier row | Tipo evento, severidad, tiempo desde detección, items afectados | Acciones específicas + Ignorar/Resolver |
| **Lead profile** | Funnel-Interest/Consideration drilldown | Nombre/handle, canal, traits inferidos, atribución | Convertir en customer · Asignar a bot · Borrar |

### Comportamiento

- **Apertura:** transición fade + scale-in del modal, backdrop fade-in. ~150ms.
- **Cierre:** ESC, click backdrop, botón Cerrar, o click acción que completa el flow (ej. "Crear orden" cierra el modal y abre el modal de la orden nueva).
- **Cmd+K dentro del modal:** abre command palette por encima, permite navegar a otro modal sin cerrar el actual (stack de modals si es necesario).
- **Stack de modals:** si una acción abre otra modal (ej. "Ver conversación" desde Customer profile abre Conversation thread modal), la nueva se monta encima. ESC cierra solo la última.
- **Dimensiones:** ~880px de ancho máximo, altura adaptativa, max-height 90vh con scroll interno si hace falta.
- **Mobile/responsive:** N/A — el ERP es desktop-only (Tauri/Windows).

---

## 6. Decisiones operativas (fijadas)

Estas decisiones afectan el comportamiento del sistema y están **congeladas** en este spec. Cambiarlas requiere editar este doc primero.

| Decisión | Valor | Fuente |
|---|---|---|
| Definición de VIP | LTV ≥ Q1,500 (por valor, no frecuencia) | Diego, Sec 2 |
| Umbral orden pendiente despacho | 24h post-pago | Diego, Sec 2 |
| Umbral leads sin responder | 12h post-último-mensaje-cliente | Default propuesto |
| Umbral stock bajo | < 3 unidades por SKU | Default propuesto |
| Umbral campaign drop | -30% CTR vs benchmark | Default propuesto |
| Goal mensual revenue | Q25,000 (editable en Settings) | Default ejemplo |
| Push notifications WA Diego | Todos los eventos críticos (siempre) | Diego, Sec 3 |
| Retención local de transcripciones | Permanente | Diego, Sec 3 |
| Sync ManyChat | Cada 1h (cron) | Diego, Sec 3 |
| Sync Meta Ads | Cada 1h (cron del worker) | Default propuesto |
| Sync Recurrente → worker | Real-time (webhook desde Recurrente, vía Svix) | Sin opción |
| Sync worker → ERP (pull órdenes nuevas) | Polling cada 1min (ERP pulla al worker) | Default propuesto |
| Detección de eventos del Inbox | Cada 15min (cron del worker, escribe a `comercial_events`) | Default propuesto |

---

## 7. Datos y sincronización

### Tablas SQLite

**Existentes (se mantienen):**

- `customers` — id, name, phone, email, source, first_order_at, total_orders, total_revenue, ...
- `sales` — sale_id, ref, customer_id, modality, payment_method, fulfillment_status, total_gtq, ...
- `sale_items` — sale_id, family_id, jersey_id, size, personalization_json, unit_price, unit_cost
- `sales_attribution` — sale_id, ad_campaign_id, source, attributed_at
- `vault_orders` / `vault_order_items` / `vault_order_status_history` — sync raw del worker
- `imports` — supplier batches (Bond Soccer)

**Nuevas (a crear en Release 1):**

| Tabla | Columnas clave | Source | Retención |
|---|---|---|---|
| `leads` | lead_id PK, name, handle/phone, platform, source_campaign_id, first_contact_at, last_activity_at, status (new/qualified/converted/lost), traits_json | ManyChat sync + DMs manuales | Permanente |
| `conversations` | conv_id PK (matches Cloudflare KV), brand, platform, sender_id, started_at, ended_at, outcome, order_id FK, messages_json (transcripción), tags, analyzed | ManyChat KV → sync c/1h | Permanente |
| `campaigns_snapshot` | snapshot_id PK, campaign_id, captured_at, impressions, clicks, spend, conversions, revenue_attributed | Meta API → sync c/1h | 90 días (luego agregado a `campaigns_daily`) |
| `comercial_events` | event_id PK, type, severity (crit/warn/info/strat), title, sub, items_affected_json, detected_at, status (active/resolved/ignored), resolved_at | Cron interno c/15min | 30 días resueltos / permanente activos |

### ¿Por qué `leads` separado de `customers`?

Un lead puede no convertir nunca. Si vive como `is_lead=true` en `customers`, todas las queries de retention/LTV requieren filtrar — agrega ruido permanente. Con tabla aparte:
- `SELECT * FROM customers` siempre da gente que compró.
- Cuando un lead compra, se mueve a customers (insert + delete del leads).

### Sources de data

```
                    SQLite local del ERP
                            ↑
        ┌───────────────────┼───────────────────┐
        │                   │                   │
  Recurrente webhook   ManyChat KV+API     Meta Ads API
   (real-time, via     (cron c/1h)         (cron c/1h)
    worker)
```

**Recurrente webhook (2 hops):**

1. **Recurrente → worker:** real-time vía Svix. Worker ya recibe webhooks en `/webhook/recurrente`. Eventos: `payment_intent.succeeded`, `payment_intent.failed`, `bank_transfer_intent.succeeded`. Worker escribe a KV (vault_orders raw) y dispara notificaciones.

2. **Worker → ERP:** polling cada 1min desde el ERP al worker, endpoint `/api/comercial/events?since=<last_sync_ts>`. Idempotente — ERP no procesa eventos ya vistos (dedup por `sale_id` o `event_id`). Trade-off: hasta 1min de latencia entre orden creada y aparición en Inbox del ERP. Acceptable para v1; R6 puede explorar push directo (ej. SSE o long-polling) si la latencia molesta.

**ManyChat:**
- KV `ai_hist:{brand}:{platform}:{senderId}` — conversaciones activas (read on-demand cuando Diego abre el modal).
- KV `conv_archive:{convId}` — conversaciones cerradas con transcripción completa, TTL 90d.
- KV `conv_index:{brand}` — últimos 500 metadata para analytics.
- ERP cron c/1h: copia `conv_archive:*` con `analyzed=true` a `conversations` table local. Marca como sincronizado.
- ERP cron c/1h: copia subscribers de ManyChat a `leads` (auto-merge por phone con customers existentes).

**Meta Ads API:**
- Token ya disponible en `club-coo/ads/.env`.
- ERP cron c/1h: pull de campaigns activas + métricas → `campaigns_snapshot`.
- Acción "Pausar/Activar" desde el ERP usa la API write directamente.

### Source-of-truth (resolución de conflictos)

| Dato | Fuente única | Notas |
|---|---|---|
| Lista de órdenes y status pago | Recurrente webhook → `sales` | El worker es el único que escribe payment_method/payment_status |
| Status de fulfillment | Diego manual desde el ERP | El worker NO toca fulfillment_status |
| Conversaciones (transcripts) | ManyChat KV (read-only) | El ERP lee y archiva. Nunca escribe a ManyChat. |
| Tags / traits del customer | SQLite local del ERP | Diego edita manual. Los syncs nunca pisan. |
| Notas privadas del customer | SQLite local del ERP | Solo Diego las ve. Nunca van a ManyChat ni Recurrente. |
| Campaign budget/status | Meta Ads API (read primario) | Diego puede pausar desde ERP (write a Meta API). El polling siguiente confirma. |
| Atribución de ventas | `sales_attribution` (calculado al webhook) | Cruza orden con último click de campaign del customer en últimos 7d. |

### Política de conflictos

1. **Diego editó traits/notas locales mientras un sync traía data nueva del cliente:** el local gana siempre. Los traits/notas son "tuyos", el sync nunca los pisa.
2. **Worker dice "orden pagada", Diego ya marcó "shipped":** ambos campos coexisten, cada uno con su source. El estado UI muestra el más avanzado (shipped > paid).

---

## 8. Errores, fallbacks, casos borde

### Sync failures

| Falla | Comportamiento del ERP |
|---|---|
| Meta Ads API caída | Tab Ads muestra última snapshot con badge `⚠ stale · última sync hace Xh`. No bloquea reads. |
| ManyChat API rate-limit | Cron retrasa al siguiente ciclo. Si está caído >12h, evento ⚪ estratégico en Inbox: "Sync ManyChat con falla" con timestamp último éxito. |
| Recurrente webhook perdido (Svix retry agotado) | Worker NO recibe el webhook. ERP no se entera. Mitigación: botón "Re-sync órdenes" en Settings que llama a Recurrente API directamente y compara contra `sales` local. Catch manual. |
| Polling worker → ERP falla | ERP retry exponencial (1m, 2m, 4m, max 15m). Si está caído >30min, banner top: `⚠ Sync con worker offline`. Reads locales siguen. |
| Worker Cloudflare caído | Modo degradado: ERP funciona con SQLite local, pulso muestra `⚠ desconectado`. Cuando vuelve, sync diff automático con `since=<last_sync_ts>`. |
| Sin internet en compu de Diego | Reads del SQLite siguen funcionando. Acciones que escriben (responder, pausar campaign) bloqueadas con tooltip "requiere conexión". |

### Conflictos de data

Solo 2 casos posibles, ambos resueltos por las reglas de Sec 7 ("local gana en traits", "cada campo su source"):

1. Diego editó traits locales mientras venía un sync → local persiste.
2. Worker dice "paid", Diego ya marcó "shipped" → ambos coexisten, UI muestra el más avanzado.

### Estados degradados / vacíos

| Cuándo | Qué muestra |
|---|---|
| Primer día sin leads | Funnel con todas las etapas en cero. Mensaje sutil: "Esperando primeros leads — verificá tus campaigns en Ads." |
| Sin órdenes hoy | Pulso muestra Q0 / 0 órdenes en gris. Mensaje sutil: "Día tranquilo." |
| Inbox vacío (todo OK) | Mensaje terminal-style: `> all systems nominal. nothing to worry about.` |
| Loading inicial | Skeleton con shimmer effect (igual al Audit). |
| Error de query | Card rojo con mensaje técnico + botones "Reintentar" / "Reportar". |

### Browser fallback (modo dev sin .exe)

Mantiene el patrón existente del adapter:
- Reads del catalog estático funcionan.
- Writes tiran `NotAvailableInBrowser` con mensaje claro: "Esto requiere el .exe, no el dev server".
- Modals abren igual; footer botones disabled con tooltip explicativo.

### Edge cases específicos

- **Customer con phone null** (lead que vino por IG sin compartir teléfono): aparece como `@handle` en vez de `+502...`. Modal Customer adapta: botón "Mensaje WA" se reemplaza por "Mensaje IG".
- **Orden con cliente nuevo no registrado:** webhook crea customer auto. No bloquea.
- **Lead que escribió 2 veces a la misma family:** sync detecta duplicados por `(plataforma, sender_id)`. Un solo lead.
- **Conversación sin order_id pero outcome="sale":** orden manual fuera del bot. ERP la tagea "manual sale" y permite linkearla a orden existente desde el modal.
- **Pulso bar con periodo Custom:** si Diego elige rango > 90d, advierte "data de campaigns_snapshot puede estar incompleta para fechas viejas" (TTL).

---

## 9. Estilo visual

Heredamos el lenguaje del modo Audit del ERP, sin desviarse:

### Paleta

| Token | Hex | Uso |
|---|---|---|
| Background base | `#0a0b0d` | Fondo principal |
| Surface 0 | `#07080a` | Sidebar, áreas secundarias |
| Surface 1 | `#14161a` | Cards, botones, inputs |
| Surface 2 | `#1a1c20` | Hover states, dividers |
| Border | `#2a2c30` | Bordes default |
| Border strong | `#3a3c40` | Bordes hover |
| Accent verde (terminal/live) | `#4ade80` | Status LIVE, acciones primarias, confirmaciones |
| Warning amarillo | `#fbbf24` | Atención, warning, pending |
| Danger rojo | `#f43f5e` | Crítico, errores, destructivo |
| Info azul | `#60a5fa` | Info neutral |
| Text primary | `#e6e7e9` | Texto principal |
| Text secondary | `#b4b5b8` | Texto secundario |
| Text tertiary | `#6b6e75` | Labels, meta info |
| Text muted | `#4a4c50` | Texto deshabilitado |

### Tipografía

- **Sans (default):** -apple-system, system-ui, 'Segoe UI'
- **Mono (números, IDs, SKUs, refs):** 'Geist Mono', ui-monospace
- **Display (labels uppercase):** mismo sans, con `text-transform: uppercase` + `letter-spacing: 0.08em`

### Patrones

- **Status pills:** `● UPPERCASE` con dot prefix, bg semi-transparente del color, padding 2px 9px, border-radius 3px.
- **Section labels:** uppercase 9.5px, color tertiary, opcional separador horizontal a la derecha.
- **Cards:** background surface-1, border 1px border, border-radius 4-6px.
- **Buttons primary:** bg accent verde, color black, font-weight 600.
- **Buttons secondary:** bg surface-1, border, color text-secondary.
- **Buttons danger:** bg semi-transparente del rojo, color rojo, border semi-transparente.
- **Mono numbers:** `font-variant-numeric: tabular-nums` para alineación.

### Mockups de referencia

Los mockups visuales del proceso brainstorming están guardados en:
- `.superpowers/brainstorm/507-1777167488/content/comercial-approach-1-v2.html`
- `.superpowers/brainstorm/507-1777167488/content/comercial-approach-2.html`
- `.superpowers/brainstorm/507-1777167488/content/comercial-approach-3.html` (approach final)
- `.superpowers/brainstorm/507-1777167488/content/modal-customer-profile.html` (patrón modal de referencia)

---

## 10. Estrategia de implementación por releases

6 releases secuenciales con dependencies. Cada release es shippable independientemente con valor visible.

### Release 1 — Setup + Inbox crítico (3-4 días)

**Scope:**
- Skeleton de Comercial: sidebar nav item activo, tabs vacíos, pulso bar funcional, estructura general.
- Schema SQLite: las 4 tablas nuevas (`leads`, `conversations`, `campaigns_snapshot`, `comercial_events`).
- Modal pattern reusable (componente Svelte `BaseModal.svelte`).
- Detección de evento "Órdenes pendientes despacho >24h" (cron 1h en worker o cron interno del ERP, depende implementación).
- Tab Inbox funcional con eventos del tipo "órdenes pendientes" + "nueva orden".
- Modal `OrderDetailModal.svelte` con acciones primarias (marcar despachado, generar guía, contactar cliente).
- Push notifications a WA Diego para eventos críticos (vía worker existente).

**Diego ya puede:** ver pendientes, despachar desde el ERP, recibir alertas en WA.

**Dependencies:** ninguna (cimientos).

### Release 2 — Funnel + Pulso (2-3 días)

**Scope:**
- Tab Funnel con 5 etapas reales (Awareness, Interest, Consideration, Sale, Retention) populated con data del SQLite.
- Drilldown modal por etapa (lista de items + acciones quick).
- Pulso bar con KPIs reales calculados en runtime (revenue, órdenes, leads, conv rate, ad spend, ROAS) según período seleccionado.
- Time control: tabs Hoy / 7d / 30d / Custom range picker.

**Diego ya puede:** ver el panorama del día completo, navegar entre períodos, drillear a cualquier etapa.

**Dependencies:** R1 (necesita schema + modal pattern).

### Release 3 — ManyChat conversaciones (2-3 días)

**Scope:**
- Sync ManyChat KV → `conversations` table (cron c/1h).
- Sync subscribers ManyChat → `leads` table (cron c/1h, merge por phone).
- Tab Funnel etapa "Consideration" populated con threads activos.
- Modal `ConversationThreadModal.svelte` con transcripción completa.
- Botón "Responder en WA" → abre `wa.me` con contacto pre-cargado.
- Detección de evento "Leads sin responder >12h".

**Diego ya puede:** ver con quién hay que hablar, leer toda la conversación previa, responder afuera con un click.

**Dependencies:** R1 (infra de sync).

### Release 4 — Customers + Atribución (3 días)

**Scope:**
- Tab Customers con lista filtrable + buscador.
- Detección de VIP (LTV ≥ Q1,500) automática.
- Modal `CustomerProfileModal.svelte` completo con timeline + traits + notas privadas + atribución.
- Atribución básica: cruzar leads/sales con campaigns vía `sales_attribution`.
- Detección de evento "VIP inactivos +60d".
- Acciones del modal: Crear orden manual, Generar cupón, Editar traits, Bloquear.

**Diego ya puede:** conocer a sus clientes a fondo, identificar VIPs, mantener notas personales.

**Dependencies:** R2 (sales/leads populated), R3 (conversations linked).

### Release 5 — Ads + Performance (2-3 días)

**Scope:**
- Tab Ads con lista de campaigns Meta activas.
- Sync Meta API c/1h → `campaigns_snapshot`.
- Modal `CampaignDetailModal.svelte` con time-series chart + lista de leads/órdenes atribuidos.
- Detección de evento "Campaign performance ↓ >30%".
- Acciones: Pausar/Activar (vía Meta API write), Duplicar, Ajustar budget.

**Diego ya puede:** decidir sobre campaigns desde un solo lugar, ver atribución visual, reaccionar rápido a drops.

**Dependencies:** R4 (atribución completa) — opcional, R5 puede ir antes con atribución parcial.

### Release 6 — Settings + Polish (1-2 días)

**Scope:**
- Tab Settings con todas las secciones (umbrales, goals, notifications, integrations, sync log).
- Empty states pulidos en todos los tabs.
- Loading skeletons consistentes.
- Bug fixes y feedback acumulado de R1-R5.
- Browser fallback completos (todos los modals con behavior correcto en modo browser).

**Diego ya puede:** tunear el ERP a su medida, tener una experiencia pulida.

**Dependencies:** R1-R5 (necesita todas las features para ajustar sus settings).

### Total

```
R1 → R2 → R3 (en paralelo posible: R2/R3 después de R1)
        ↓
        R4 → R5
              ↓
              R6
```

**Tiempo total de trabajo:** 13-18 días.
**Tiempo calendario realista:** 3-5 semanas (con pausas entre releases para feedback y vida).

### Ritmo decidido

Empezamos R1, vemos cómo se siente, decidimos ritmo en vivo. (Decisión 5.2.C de Diego.)

---

## 11. Open questions / TBD

Ninguna al cierre del brainstorming. Todas las decisiones están fijadas en Sec 6.

Si durante implementación surgen ambigüedades, el proceso es:
1. Pausar la implementación.
2. Editar este spec con la decisión nueva.
3. Commit del spec actualizado.
4. Reanudar.

No improvisar in-flight.

---

## 12. Apéndice — referencias

### Archivos existentes relevantes

- `erp/comercial.py` — Streamlit actual, fuente de la lógica de negocio a portar.
- `erp/db.py` — conexión SQLite compartida.
- `erp/audit_db.py` — patrones de schema management que reutilizamos.
- `ventus-system/backoffice/src/conversation-store.js` — bot logic (read-only desde ERP).
- `ventus-system/backoffice/src/conversation-analyzer.js` — cron analyzer (read-only).
- `club-coo/ads/CAMPAIGN-STATUS.md` — referencia de campaigns activas.
- `overhaul/src-tauri/src/lib.rs` — backend Tauri (Rust).
- `overhaul/src/lib/components/MoveModeloModal.svelte` — patrón modal de referencia.
- `overhaul/src/lib/components/MundialCoverageModal.svelte` — otro patrón modal de referencia.

### Skills aplicables durante implementación

- `superpowers:writing-plans` — paso siguiente a este spec.
- `superpowers:test-driven-development` — para cada release.
- `superpowers:dispatching-parallel-agents` — útil para R2/R3 en paralelo.
- `superpowers:verification-before-completion` — antes de declarar cada release como hecho.

### Decisiones que aplican retroactivamente al ERP completo

Durante el brainstorming surgieron decisiones que no son específicas de Comercial pero quedaron documentadas:

- **Estilo visual retro gaming/terminal** — anclado en `~/.claude/CLAUDE.md` global, aplica a todos los proyectos de Diego.
- **Mental model de juegos de gestión** — anclado en `~/.claude/CLAUDE.md` global.
- **Pattern modal grande para detail views** — extender a Audit donde aplique (futuro overhaul de algún detail view actual).

---

**Fin del spec.**

Próximo paso: review de Diego → invocar `superpowers:writing-plans` para generar plan de implementación detallado por release.
