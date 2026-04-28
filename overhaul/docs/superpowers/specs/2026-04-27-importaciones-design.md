# Importaciones — Diseño y especificación

**Fecha:** 2026-04-27
**Autor:** Diego + Claude (sesión brainstorming)
**Status:** Diseño · pendiente review de Diego antes de plan de implementación
**Approach final:** A1 List/Detail FM-style con detail pane in-place (no modal grande inicialmente · Wishlist tab propia · Vínculo Comercial como link)
**Releases planificados:** 6 (`IMP-R1` → `IMP-R6`, ~13-18 días de trabajo)
**Brainstorm session:** `.superpowers/brainstorm/1923-1777335894/`
**Predecesor empírico:** `el-club/erp/comercial.py` (Streamlit) + `el-club/erp/elclub.db` (2 imports + 51 sale_items linked)

---

## 1. Resumen ejecutivo

Importaciones es la sección del ERP de El Club donde Diego gestiona el **costeo y seguimiento de pedidos al supplier**. El módulo nace de dos hechos empíricos:

1. El modelo de datos ya existe en el ERP Streamlit (`erp/comercial.py` + `schema.sql`) y está validado: la tabla `imports` tiene 2 registros reales (`IMP-2026-04-07` cerrado con `unit_cost=Q145`, `IMP-2026-04-18` paid · pendiente cierre) que cubren 90% del dominio.
2. El dolor real **no es modelado** — es UX. Diego: *"Estoy harto de Streamlit, visualmente me quita años de vida."*

El módulo nuevo NO arranca de cero. Migra el schema + funciones (`create_import`, `close_import`, `_refresh_import_unit_cost`) + 2 imports + 51 `sale_items` linkeados al SQLite del Tauri, y los presenta con la estética FM/CK3/EU4 que ya tiene Comercial.

**Framing canónico** (Diego, sesión 2026-04-27):
> *"Lo que quiero es que sea el módulo de costeo. Finanzas se va a alimentar de acá. Es un módulo de compras y de seguimiento de pedidos básicamente."*

El landed cost real (Q145/unidad histórico) es la métrica que el módulo debe reproducir automáticamente y exponer como input estructurado para `FIN-Rx`. La visibilidad económica (capital amarrado · margen per release · lead time avg supplier) es protagónica; el seguimiento físico (DHL tracking, ETA) es accesorio.

El espíritu visual hereda directamente de Comercial: retro gaming / terminal, denso, monospace para números, status pills con dot prefix, drilldown infinito. Mismos tokens (`#08080a` bg · `#5b8def` accent · JetBrains Mono · pattern grid sutil). Sin desviaciones.

---

## 2. Contexto y objetivos

### Por qué overhaul

Hoy Diego trackea pedidos al supplier en tres lugares simultáneos:

1. **Chat personal de WhatsApp** — donde apunta raw los pedidos individuales de los clientes a medida que llegan ("Luis Diaz #7 M World Cup Fan").
2. **Streamlit `comercial.py`** — donde existen las funciones `create_import` / `close_import` y la tabla `imports` con 2 batches reales.
3. **Memoria + cabeza de Diego** — para consolidar wishlist en batch, calcular cuándo es momento de pedirle al chino, y prorratear costos al cierre.

Cuando llega DHL door-to-door, Diego hace cálculo manual: bruto USD × FX + shipping_gtq → ÷ N units → unit_cost. Lo entra a Streamlit, corre `close_import`, y queda registrado. Pero el panorama (qué tengo en pipeline, cuánto capital amarrado, lead time avg, margen real per release Comercial) requiere queries SQL ad-hoc o spreadsheets paralelos.

El módulo nuevo centraliza el ciclo completo en una sección integrada al ERP Tauri con la misma identidad visual del Audit/Comercial.

### Mental model (heredado del CLAUDE.md global)

Diego piensa como strategy gamer (SimCity, EU4, CK3, Football Manager). Manejar El Club es "la versión adulta de estos juegos con réditos reales." El diseño se apoya:

- **Densidad de información OK** organizada por capas. FM Squad detail · CK3 character window.
- **Drilldown infinito** — click en un batch revela detail con todas las stats + actions.
- **Causalidad visible** — del wishlist al batch al close al margen per venta.
- **Time control** — lead time per stage visible, históricos consultables, ETAs proyectadas.
- **Sense of agency** — todas las acciones (registrar arrival, cerrar batch, asignar free unit) viven dentro del mismo lugar.
- **Map / Ledger duality** — list-detail (lente operativa) + futura vista Margen real (lente económica) son dos lentes de la misma data.

### Objetivos concretos

1. **Reemplazar el Streamlit** para gestión de Importaciones. El Streamlit puede mantenerse como referencia hasta que Diego confirme paridad funcional.
2. **Producir el landed cost real** sin cálculo manual. Al registrar `arrived_at` + `shipping_gtq` (DHL door-to-door GTQ), el módulo prorratea automáticamente vía D2=B (por valor USD) y actualiza `sale_items.unit_cost` + `jerseys.cost` linkeados.
3. **Exponer datos para FIN-Rx** — capital amarrado, P&L per import, ROI per release Comercial, deuda outstanding (en este caso = $0 porque Diego paga upfront).
4. **Sentido de panorama y control** — entrar a Importaciones debe dar la sensación de "abrir el panel del compras manager", no "abrir un dashboard SaaS."
5. **Lead time observable** — cada batch muestra días por stage; KPI global "Avg lead time supplier" sirve para predecir arrivals futuros.

---

## 3. Arquitectura general

### Inserción en el ERP existente

Importaciones es un item del sidebar global del ERP, agregado a la sección Data:

```
ERP Sidebar (post-Importaciones · pre-Admin Web R7)
├── WORKFLOW
│   ├── Queue
│   ├── Audit
│   ├── Mundial 2026
│   └── Publicados
└── DATA
    ├── Dashboard
    ├── Inventario
    ├── Comercial         ← spec previo
    ├── Importaciones     ← este spec (NEW)
    └── Órdenes
```

Click "Importaciones" → entra al modo Importaciones. El cuerpo principal del ERP cambia a:

```
┌──────────────────────────────────────────────────────────────────┐
│ MODULE HEAD: Importaciones · [Export CSV] [Sync DHL] [+ Nuevo]   │
├──────────────────────────────────────────────────────────────────┤
│ TABS: [Pedidos] [Wishlist 14] [Margen real] [Free units 2] [Sup] │
├──────────────────────────────────────────────────────────────────┤
│ PULSO: Capital · Closed YTD · Avg landed · Lead time · Wishlist  │
├──────────────────────────────────────────────────────────────────┤
│  LIST (320px)              │   DETAIL (resto)                    │
│  search · chips            │   id · status · meta · actions      │
│  rows con mini-progress    │   sub-tabs: Overview/Items/Costos…  │
│                            │   stats strip · timeline · items    │
└──────────────────────────────────────────────────────────────────┘
```

### Reglas arquitectónicas

1. **Importaciones es UN item del sidebar global del ERP**, no varios. Wishlist/Margen/Free/Supplier son sub-tabs adentro.
2. **Detail pane in-place**, no modal flotante. El list-detail vive lado a lado dentro del cuerpo del módulo. El BaseModal del Comercial se reusa solo para sub-flows específicos (drop creator, free unit assignment, edit batch).
3. **El sidebar global del ERP NO se rediseña en R1.** Importaciones simplemente se inserta como nav-item nuevo. **Flag cross-bucket:** cuando ADM-R1 ejecute (Admin Web), el sidebar global se reorganiza completo (5 módulos top-level: Admin Web, Comercial, Importaciones, Finanzas, Inventario). Hasta entonces, Importaciones convive con el sidebar actual de 8 items + 1 = 9.
4. **El último tab abierto se persiste** en localStorage. Click "Importaciones" después de cerrar entra al tab donde estabas.
5. **Branding heredado** del ERP Tauri (Midnight Stadium dark + Inter + JetBrains Mono).

### Navegación cruzada

| Salida | Destino |
|---|---|
| Click otro item del sidebar | Sale de Importaciones. Al volver, restaura último tab. |
| Cmd+K command palette | Acepta queries cross-tab: "IMP-2026-04-07" → tab Pedidos con batch abierto; "Argentina Messi" → wishlist con item; "Q3,182" → batch cerrado con ese landed total. |
| **Vínculo Comercial · N ventas** (link en detail-meta) | Lleva a `Comercial > Customers` o `Comercial > Sales` filtrado por las ventas del batch actual. |
| ESC | Sale del detail pane (vuelve a list neutral) o cierra modal si hay uno abierto. |

### Coexistencia con módulos hermanos

| Módulo | Dependencia |
|---|---|
| **Comercial** | `sale_items.import_id` y `sale_items.unit_cost` son escritos por Importaciones al close. Comercial los lee para margen reportado. **No conflict.** |
| **Audit / Vault** | D7=B exige SKU existente en wishlist. Wishlist no escribe a `audit_decisions`; lee `catalog.json` para validar. |
| **FIN-Rx** (futuro) | Lee `imports`, `sale_items`, `jerseys` para cash flow + P&L per release + ROI. Schema de Importaciones es input. |
| **INV-Rx** (futuro) | Cuando exista, `imports.status='arrived'` debería disparar +stock. Hook a definir en INV-R1. |
| **Operativa / Forza** | Forza shipping local Diego→cliente (~Q30) NO vive acá. Es un costo de venta, no de import. Operativa lo gestiona. |

---

## 4. Los sub-tabs en detalle

### Tab 1 · Pedidos (default)

**Layout:** list-detail in-place. List pane 320px a la izquierda; detail pane flexible a la derecha.

**List pane:**

```
┌── search box ────────────────────────────┐
│ ⌕ ID pedido, SKU, cliente, supplier…  ⌘K │
├──────────────────────────────────────────┤
│ [Todos·2] [Pipeline·1] [Closed·1] [Bond·2]│
├──────────────────────────────────────────┤
│ IMP-2026-04-18                  ~Q145?   │
│ Bond · $372 · 27u           [● PAID]     │
│ ▓▓▓░░  9d                                │
├──────────────────────────────────────────┤
│ IMP-2026-04-07                  Q145/u   │
│ Bond · 22u · Q3,182        [● CLOSED]    │
│ ▓▓▓▓▓  8d ✓                              │
└──────────────────────────────────────────┘
```

Cada row muestra:
- ID (mono)
- Cost label (highlight: `Q145/u` closed verde · `~Q145?` paid amber · `acumulando` draft muted)
- Sub-meta: supplier · USD · units
- Status pill con dot prefix
- Mini-progress bar 5-stage (DRAFT/PAID/IN_TRANSIT/ARRIVED/CLOSED) con tick verde/amber/empty
- Lead time badge (`9d` amber if in pipeline · `8d ✓` verde if closed)

Click row → activa detail pane (no modal). Border-left 2px verde-accent + background ligeramente más claro.

**Filter chips:** Todos / Pipeline (paid+in_transit+arrived) / Closed / + chips dinámicos por supplier (Bond solo, por ahora).

**Sort options:** paid_at DESC (default) · arrived_at · landed total · n_units · lead time real.

### Tab 2 · Wishlist

**Scope:** pre-pedidos individuales de cliente que se van acumulando hasta consolidar batch al supplier. Sustituye el chat personal de WA donde Diego apunta hoy.

**Reglas (D7=B fija):**
- Cada item del wishlist requiere un SKU existente en `catalog.json` (validación al insertar).
- Si el cliente pide algo que NO está en catalog, Diego primero scrapea/audita (workflow existente Audit) y después wishlistea.
- Los items pueden estar `assigned` (vinculado a un customer/lead) o `stock` (Diego decide pre-comprar para inventario futuro).

**Layout:** lista vertical de items wishlist + acciones bulk.

```
┌── header ────────────────────────────────────────────┐
│ Wishlist activa · 14 / 20 target  [↗ Promover a batch]│
└──────────────────────────────────────────────────────┘

[ASSIGNED · 11]
☐ ARG-2026-L-FS · Messi 10 · WC patch · Pedro G.    [editar][quitar]
☐ FRA-2026-L-FS · Mbappé 10 · Fan W · Andrés R.    [editar][quitar]
…

[STOCK FUTURO · 3]
☐ BRA-2026-L-FS · Vinicius 7 · Fan       [editar][quitar]
…
```

**Acciones del item:**
- Edit player spec (Name/Number/Size/Patch/Version)
- Asignar a customer existente
- Quitar del wishlist (descartar)

**Acción del wishlist completo:**
- **Promover a batch** — cuando hay ~20 items o Diego decide. Crea `imports` row con `status='draft'`, mueve los items wishlist a items linkeados al batch, calcula `expected_usd` aproximado (precio chino estimado por jersey). Limpia wishlist.

**Eventos de Inbox que el wishlist dispara:**
- `wishlist > 20 items` → "Hora de consolidar batch"
- `wishlist item con SKU missing` → "Pendiente de auditar antes de batch" (D7=B)
- `wishlist item asignado > 30 días sin batch` → "Cliente Pedro G. lleva 32 días esperando — considerá batch parcial"

### Tab 3 · Margen real

**Scope:** vista de la lente económica — cruza Comercial sales × Importaciones landed cost por release de batch. Es el output principal que FIN-Rx consume.

**Layout:** lista de batches closed + breakdown de revenue / cost / margin per batch.

```
┌────────────────────────────────────────────────────────┐
│ IMP-2026-04-07 · 22u · CLOSED                          │
├────────────────────────────────────────────────────────┤
│ Revenue Comercial    Q5,500    (15 ventas linkeadas)   │
│ Landed total         Q3,182                            │
│ Margen bruto         Q2,318    +73%                    │
│ Free units (2)       valor Q—  (sin asignar)           │
│ Stock pendiente (5u) Q725 amarrado                     │
├────────────────────────────────────────────────────────┤
│ → Ver ventas linkeadas · → Ver items pendientes        │
└────────────────────────────────────────────────────────┘
```

Per batch closed:
- Revenue Comercial = `SUM(sales.total_gtq)` para sales con items donde `import_id` matches
- Landed total = `imports.total_landed_gtq`
- Margen bruto = Revenue − Landed
- Stock pendiente = items del batch sin venta linkeada (capital amarrado)
- Free units count + valor (si asignadas a Mystery/Garantizada)

**Filtros:** período · supplier · status (`closed only` por default; opt-in para incluir `paid`+`arrived` con margen estimado).

**Cross-link:** tab Margen real es la fuente que FIN-Rx pulla. Schema queries documentadas en sec 7.

### Tab 4 · Free units

**Scope:** ledger de las unidades regaladas (1/10) por el supplier. Tracking de qué pasó con cada una (D-FREE=A · sin asignar default).

**Estados de free unit:**
- `unassigned` — recién creada, sin destino
- `assigned_vip` — regalada a customer VIP (linkeada a `customer_id` + `sale_id` con `total_gtq=0` y notes="free unit IMP-X")
- `assigned_mystery` — entró al pool Mystery (cuando ese módulo exista en el ERP)
- `assigned_garantizada` — publicada en Stock Q475 (cuando Stock exista)
- `assigned_personal` — Diego se la quedó

**Layout:** tabla con columnas `import_id · sku_placeholder · player_spec · created_at · status · destination · notes`.

**Acciones:** asignar destino (4 opciones) + nota opcional. Trigger: cada `close_import` que tenga `n_free_units > 0` genera evento Inbox "X free unit(s) sin asignar — ¿qué hacés?"

**Cálculo de N free units:** `floor(n_paid_units / 10)` donde `n_paid_units` es el count de items que NO sean free. La regla "1 gratis por 10" del supplier.

**Migración:** los 2 imports históricos tienen las free units como string en `imports.notes` ("2 Argentina regalo"). Script de migración (R1 task) parsea las notes con regex / pregunta a Diego para crear las free unit rows estructuradas.

### Tab 5 · Supplier

**Scope (R1 = mínimo):** tarjeta del supplier actual (Bond Soccer Jersey) con metrics agregados.

**Layout:**

```
Bond Soccer Jersey
─────────────────────────────────────────
WhatsApp · 志鵬 黎 · PayPal · DHL door-to-door

LEAD TIME           8 días avg (paid → arrived, n=1)
COST ACCURACY       ±0% (1 batch closed sin disputas)
PRICE BAND          $11 base · $13 +patch · $15 +patch+name
FREE POLICY         1 unit cada 10 paid units
TOTAL BATCHES       2 (1 closed, 1 paid)
TOTAL LANDED YTD    Q3,182 (closed)
NEXT EXPECTED       hoy 28-abr (DHL pendiente)
```

**Para v0.5 (futuro IMP-R5):** estructura para multi-supplier · scorecards comparativos · contact info · payment terms · disputes log.

### Tab 6 · Settings

**Layout:** secciones colapsables.

**Secciones:**

1. **Defaults**
   - FX default (default 7.73, override per batch)
   - Free unit ratio (default 1/10)
   - Wishlist target size para promote (default 20)
   - Lead time supplier expected (auto-calculado de batches closed)

2. **Umbrales (Inbox events)**
   - Wishlist item sin batch > N días → alert (default 30d)
   - Batch paid sin arrived > N días → alert (default 14d)
   - Cost overrun threshold → alert (default 30% sobre avg)
   - Free unit sin asignar > N días → alert (default 7d)

3. **Migration log** (read-only)
   - Última migración desde `erp/elclub.db`: timestamp + counts (X imports + Y sale_items + Z jerseys)
   - Botón "Re-sync ahora" que re-corre migración idempotente

4. **Integrations (status read-only)**
   - elclub.db source (Streamlit) — last read timestamp
   - PayPal screenshot OCR (futuro v0.5) — disabled
   - DHL tracking API (futuro v0.5) — disabled

---

## 5. Patrón Detail Pane — el corazón del módulo

A diferencia de Comercial donde "ver detalle" abre un modal flotante, Importaciones usa un **detail pane in-place** dentro del list-detail layout. Razón: en Importaciones se trabaja sostenidamente sobre un batch (cargar items, registrar arrival, cerrar) — un modal sería ergonómicamente peor.

El BaseModal del Comercial se reusa solo para sub-flows: edit batch metadata · drop creator · free unit assignment · cancel confirmation.

### Estructura del detail pane

```
┌─ detail-head ─────────────────────────────────────────────┐
│ IMP-2026-04-18  [● PAID]                                  │
│ Bond · paid 18-abr · 9 días en pipeline · 27u · → Vínculo │
│                                                            │
│ Acciones: [Registrar arrival] [Ver invoice] [Ver tracking] │
│           [Editar]                  [Cancelar] [Cerrar batch]│
├─ sub-tabs ────────────────────────────────────────────────┤
│ [Overview] [Items 27] [Costos] [Pagos 1] [Timeline]       │
├─ detail-body ─────────────────────────────────────────────┤
│ STATS STRIP (6 columnas)                                   │
│ Bruto · DHL · Días paid · Total · Units · Landed/u         │
│                                                            │
│ ITEMS PREVIEW (5 rows + "ver todo")                        │
│ Timeline (6 stages con elapsed badges)                     │
└────────────────────────────────────────────────────────────┘
```

### Sub-tabs del detail

| Sub-tab | Contenido | R# |
|---|---|---|
| **Overview** | Stats strip 6 KPIs · items preview (5) · timeline | R1 |
| **Items** | Tabla completa de items del batch · columnas SKU/Variante/Player spec/Asignado/Status/USD/Landed/Margen · sortable · filtrable | R1 |
| **Costos** | Cost flow detallado (sacado del Overview por petición Diego — overwhelming): PayPal bruto, PayPal fee 4.4% incl, DHL, FX, total landed, formula, prorrateo per item table | R1 |
| **Pagos** | Lista de pagos al supplier con date, monto, método (PayPal/transfer), reference, screenshot adjunto. Para batches normales = 1 pago. | R1 |
| **Timeline** | Vista expandida del timeline con todos los stages + custom events (cost overrun warning, ETA update, etc.) + lead time per stage | R1 |

### Stats strip (6 KPIs per batch)

| KPI | Fuente | Highlight |
|---|---|---|
| Bruto USD | `imports.bruto_usd` | normal |
| DHL door-to-door | `imports.shipping_gtq` | amber si null/pending · normal si numeric |
| Días desde paid | `now − imports.paid_at` | blue · sub-text "vs avg Xd · ETA hoy" si en ventana |
| Total landed est | `bruto × fx + shipping` | amber si paid (estimado) · verde si closed |
| Units | `n_units` | normal · "/N" si discrepancia con notes |
| Landed / unidad | `total_landed / n_units` (D2=A) o weighted (D2=B) | green · "estimado" si pre-cierre |

### Action toolbar (arriba, no abajo · D-Diego)

Layout: `[Action 1] [Action 2] [Action 3] [Edit] [spacer] [Cancel] [Close batch primary]`.

Acciones disponibles según status:

| Status | Acciones disponibles |
|---|---|
| `draft` | Editar · Eliminar · Promover a paid |
| `paid` | Registrar arrival · Ver invoice PayPal · Editar · Cancelar |
| `in_transit` | Registrar arrival · Ver tracking DHL · Editar · Cancelar |
| `arrived` | Cerrar batch (primary) · Edit shipping_gtq · Cancelar |
| `closed` | Ver invoice · Ver tracking · Re-abrir (admin only · destructivo) |
| `cancelled` | Re-abrir · Ver historial |

**Cerrar batch** está disabled hasta que `arrived_at IS NOT NULL` y `shipping_gtq IS NOT NULL`. Tooltip explica el bloqueo.

### Cálculo de landed cost per unit (D2=B)

Cuando Diego dispara "Cerrar batch":

```python
def close_import_proportional(conn, import_id):
    imp = get_import(conn, import_id)
    items = get_items_for_import(conn, import_id)  # sale_items + jerseys
    total_usd = sum(item.unit_cost_usd for item in items)
    # NEW: total_landed_gtq = bruto_usd × fx + shipping_gtq (PayPal fee already incl in bruto_usd)
    total_landed = imp.bruto_usd * imp.fx + imp.shipping_gtq

    for item in items:
        # D2=B: prorrateo proporcional al USD chino del item
        weight = item.unit_cost_usd / total_usd
        item_landed_gtq = round(weight * total_landed)
        update_item_unit_cost(conn, item.id, item_landed_gtq)

    update_import_status(conn, import_id, 'closed')
```

**Implicación schema:** `sale_items.unit_cost_usd REAL` debe ser agregado en R1 task (no existe hoy, solo `sale_items.unit_cost` que es GTQ post-prorrateo). Migration: para los 51 items históricos, asignar `unit_cost_usd` desde el chat WA del chino o estimación uniforme (`bruto_usd / n_units`).

### Lead time observability

Tres niveles de visibilidad:

1. **Per-row badge en list pane** — `9d` (amber, in-pipeline) · `8d ✓` (verde, closed)
2. **Pulso bar global** — `Lead time avg supplier: 8 días` (calculado de batches closed)
3. **Detail header** — `9 días en pipeline` junto a la fecha de paid
4. **Timeline stages** — elapsed badges per stage `+2d / +1d / 9d desde paid`

Cuando un batch entra en ventana esperada (avg ± 2d), el detail muestra en el stage activo: *"ya en ventana esperada de arrival"*. Cuando excede (avg + 4d sin arrived), Inbox event "batch X fuera de ventana avg supplier".

---

## 6. Decisiones operativas (fijadas)

### Decisiones cargadas pre-sesión (NO reabrir)

| ID | Decisión | Resolución | Fuente |
|---|---|---|---|
| Pre-D1 | Sub-módulo o propio | **Propio** en sidebar, NO bajo Admin Web | Diego pre-sesión |
| Pre-D2 | Trigger | **NEXT** post-Comercial polish | Diego pre-sesión |
| Pre-D3 | Approach brainstorm | **Sub-agent superpowers** | Diego pre-sesión |
| Pre-D4 | Nomenclatura release | **`IMP-Rx`** canonical | `docs/ERP-ROADMAP.md` |

### Decisiones tomadas en esta sesión

| ID | Decisión | Resolución | Impact |
|---|---|---|---|
| **D1** | Naming del módulo | **A** · "Importaciones" (mantiene continuidad con Streamlit + schema `imports`) | R1 |
| **D2** | Prorrateo de landed cost per SKU | **B** · Por valor USD (proporcional). Refleja realidad económica · jersey cara absorbe más shipping | R1 |
| **D-FX** | Tipo de cambio USD → GTQ | Manual per batch · **default 7.73** (Nexa promedio). Override per batch disponible. Histórico se queda con sus FX originales (7.70). | R1 |
| **D6** | Wishlist como entidad | **A** · Tab propia con UX optimizada para acumular pre-pedidos antes de promover a batch | R1 (tab) · R2 (workflow) |
| **D7** | SKUs nuevos en wishlist | **B** · Requiere SKU existente. Diego primero scrapea/audita, después wishlistea. | R2 |
| **D-FREE** | Destino default de free units | **A** · Sin asignar default. Diego decide caso a caso (VIP / Mystery / Garantizada / personal). Inbox event si > 7d sin asignar. | R4 |
| **D-MIG** | Migración data histórica | **A** · Script idempotente migra 2 imports + 51 sale_items + jerseys linked desde `erp/elclub.db` | R1 task #1 |

### Datos operativos confirmados (no son decisiones — son hechos del flujo)

| Variable | Valor | Fuente |
|---|---|---|
| Supplier actual | Bond Soccer Jersey (志鵬 黎) | Diego + WA screenshots |
| Carrier internacional | DHL door-to-door (incluye shipping + impuestos GT) | Diego sesión |
| Forza shipping local | Q30/entrega (Diego→cliente final, NO en imports) | Diego sesión |
| Pago | PayPal upfront · ~4.4% fee incluido en bruto | Diego sesión + screenshot $357+$15.64 |
| Política free | 1 unidad regalada por 10 paid | Diego sesión |
| Pricing chino | $11 base · +$2 patch · +$2 player name (formula `11+2+2=15`) | Diego sesión + WA chats |
| Wishlist actual | Vive en chat personal de WA de Diego (a migrar al módulo) | Diego sesión |
| Ciclo típico | Batch ~20-25 items · ~1 contenedor · 7-10d lead time | Diego sesión + IMP-04-07 (8d real) |

---

## 7. Datos y sincronización

### Schema SQLite

**Existentes (se mantienen tal cual del Streamlit):**

```sql
imports (
  import_id        TEXT PRIMARY KEY,
  paid_at          TEXT,
  arrived_at       TEXT,
  supplier         TEXT DEFAULT 'Bond Soccer Jersey',
  bruto_usd        REAL,
  shipping_gtq     REAL,
  fx               REAL DEFAULT 7.70,         -- ← CAMBIAR a 7.73 (D-FX)
  total_landed_gtq REAL,
  n_units          INTEGER,
  unit_cost        REAL,
  status           TEXT CHECK(status IN ('draft','paid','in_transit','arrived','closed','cancelled')),
  notes            TEXT,
  created_at       TEXT
);

sale_items.import_id   -- FK existente
jerseys.import_id      -- FK existente
sale_items.unit_cost   -- GTQ post-prorrateo (existente)
```

**Adiciones requeridas en R1:**

```sql
-- 1. Default FX update
ALTER TABLE imports ALTER COLUMN fx SET DEFAULT 7.73;

-- 2. USD per item (necesario para D2=B prorrateo proporcional)
ALTER TABLE sale_items ADD COLUMN unit_cost_usd REAL;
ALTER TABLE jerseys ADD COLUMN unit_cost_usd REAL;

-- 3. Tracking + carrier
ALTER TABLE imports ADD COLUMN tracking_code TEXT;
ALTER TABLE imports ADD COLUMN carrier TEXT DEFAULT 'DHL';

-- 4. Lead time auto-calculado al close
ALTER TABLE imports ADD COLUMN lead_time_days INTEGER;
```

**Tablas nuevas:**

```sql
-- Wishlist (D6=A · tab propia · D7=B requiere SKU existente)
CREATE TABLE IF NOT EXISTS import_wishlist (
  wishlist_item_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  family_id         TEXT NOT NULL,            -- ← FK a catalog.json (D7=B validation)
  jersey_id         TEXT,                     -- nullable, para variante específica
  size              TEXT,
  player_name       TEXT,
  player_number     INTEGER,
  patch             TEXT,                     -- 'WC', 'Champions', null
  version           TEXT,                     -- 'fan', 'fan-w', 'player'
  customer_id       TEXT,                     -- nullable (stock futuro vs assigned)
  expected_usd      REAL,                     -- estimado pre-pricing del chino
  status            TEXT DEFAULT 'active'
                    CHECK(status IN ('active','promoted','cancelled')),
  promoted_to_import_id TEXT,                 -- FK a imports cuando promueve
  created_at        TEXT DEFAULT (datetime('now', 'localtime')),
  notes             TEXT
);

-- Free units ledger (D-FREE=A)
CREATE TABLE IF NOT EXISTS import_free_unit (
  free_unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id         TEXT NOT NULL,            -- FK a imports
  family_id         TEXT,                     -- nullable hasta que Diego asigne
  jersey_id         TEXT,
  destination       TEXT
                    CHECK(destination IN ('unassigned','vip','mystery','garantizada','personal')),
  destination_ref   TEXT,                     -- customer_id, sale_id, mystery_pool_id
  assigned_at       TEXT,
  assigned_by       TEXT,                     -- 'diego'
  notes             TEXT,
  created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_wishlist_status ON import_wishlist(status);
CREATE INDEX idx_wishlist_customer ON import_wishlist(customer_id);
CREATE INDEX idx_free_unit_import ON import_free_unit(import_id);
CREATE INDEX idx_free_unit_destination ON import_free_unit(destination);
```

### Migration script (R1 task #1)

**⚠️ Hallazgo empírico post-spec (2026-04-27):** Tauri ERP usa **la MISMA `elclub.db` que el Streamlit** (`src-tauri/src/lib.rs:64` → `db_path` apunta a `C:\Users\Diego\el-club\erp\elclub.db`). **NO hay migration de data** — los 2 imports + 51 sale_items + jerseys linked ya son accesibles desde el Tauri vía SELECT directo.

Lo que en R1 se aplica es: **schema additions** (ALTER + CREATE TABLE wishlist/free_unit) sobre la DB compartida. El "migration script" es realmente un script de aplicación de schema, idempotente (CREATE TABLE IF NOT EXISTS · ALTER TABLE … sin error si la columna ya existe).

**Tablas migradas:**
1. `imports` (2 rows: IMP-2026-04-07, IMP-2026-04-18)
2. `sale_items` con `import_id NOT NULL` (51 rows · preserva `unit_cost` existente)
3. `jerseys` con `import_id NOT NULL` (subset)

**Datos NO migrados pero parseados:**
- Free units mencionadas en `imports.notes` como string ("2 Argentina regalo") → script parsea con regex y pregunta a Diego para crear `import_free_unit` rows.
- Player specs de cada item (que viven en `sale_items.personalization_json`) se preservan como están.

**Datos NO migrables sin input de Diego:**
- `unit_cost_usd` por item (no existe en histórico). Default: estimación uniforme = `bruto_usd / n_units`. Diego puede override per item después.

### Sources de data

```
                    SQLite local del Tauri ERP
                              ↑
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
  el-club/erp/elclub.db   PayPal screenshots    DHL email/WA
   (migration ONE-TIME)    (manual upload)       (manual entry)
                              │                     │
                          ─ R1 task ─           ─ post-R1 ─
```

**No real-time sync** en R1. Todo es manual o triggered por Diego:

- Migration: corre 1 vez desde elclub.db. Re-runnable si Diego sigue cerrando batches en Streamlit (mientras valida paridad).
- PayPal: screenshot adjunto al pago, Diego entra `bruto_usd` manualmente (futuro v0.5: OCR).
- DHL tracking: Diego pega el `tracking_code` del WA del chino al field. Futuro v0.5: webhook DHL API.
- DHL invoice GTQ: Diego entra `shipping_gtq` cuando llega el comprobante. Trigger close_import.

### Source-of-truth

| Dato | Fuente única | Notas |
|---|---|---|
| Lista de imports y status | SQLite local del Tauri | Streamlit puede seguir leyendo en paralelo durante validación, pero Tauri es el writer authoritativo post-R1 ship. |
| `unit_cost` y `unit_cost_usd` per item | Calculado por `close_import_proportional()` al cierre | Diego override manual disponible en R1.x. |
| `arrived_at` | Manual de Diego | DHL no auto-syncea hoy. |
| Free unit destination | Manual de Diego en tab Free units | Sin auto-asignación (D-FREE=A). |

### Política de conflictos

Durante el período de validación (R1 ship → Diego confirma paridad):
- Diego puede seguir cerrando batches en Streamlit O en Tauri (no ambos al mismo tiempo).
- Si cierra en Streamlit, re-corre migración para sync al Tauri.
- Una vez confirmada paridad, Streamlit pasa a read-only para Importaciones (las otras tabs del Streamlit pueden seguir activas).

---

## 8. Errores, fallbacks, casos borde

### Sync failures

| Falla | Comportamiento del ERP |
|---|---|
| Migration falla a mitad de corrida | Idempotente · re-correr no duplica · Diego ve diff con badge "Migration partial · X imports OK · Y pendientes". |
| `elclub.db` no encontrado | Banner: "Source Streamlit no detectado. ¿Está movido?" + path settings. |
| `catalog.json` no se puede leer en wishlist insert (D7=B validation) | Bloquea insert con mensaje "Validación de SKU no disponible — refrescá catalog en Vault". |
| Sin internet | Reads del SQLite siguen funcionando. Acciones que escriben (cerrar batch, asignar free) ok local. Sync con Streamlit bloqueado. |

### Casos borde de domain

- **Batch con 1 item** — `n_units=1` · `floor(1/10)=0` free units. OK.
- **Batch con 0 paid items (todo cancelled)** — `n_units=0` · close_import bloqueado con mensaje "No hay items linkeados".
- **Item con `unit_cost_usd=null` al close** — bloquea con "Item X sin USD chino — entrá el precio del chat WA antes de cerrar". Para migración histórica: default = `bruto_usd / n_units` uniforme.
- **FX manual override negativo o cero** — bloquea con validation error.
- **Wishlist promote con 0 items** — botón disabled.
- **Wishlist promote con item de SKU inexistente** (race condition: Diego eliminó el SKU mientras wishlist estaba activo) — bloquea con mensaje "SKU X ya no existe en catalog. Re-asignar o quitar".
- **Free unit asignada a customer_id inexistente** — bloquea con select picker que valida customers.

### Estados degradados / vacíos

| Cuándo | Qué muestra |
|---|---|
| Sin batches (primer día) | Pulso en cero · list "No hay imports todavía. [+ Nuevo pedido] o [Migrar desde Streamlit]". |
| Batches todos closed (sin pipeline) | Pulso · `Capital amarrado: Q0` · list muestra closed con muted styling. |
| Wishlist vacía | "Sin pre-pedidos. Cuando un cliente pida algo, agregá item acá. Recordatorio: D7=B · SKU debe existir en catalog." |
| Free units sin asignar | Inbox event persistente hasta resolver. |

### Browser fallback

Mantiene patrón existente del adapter:
- Reads del catalog estático funcionan.
- Writes tiran `NotAvailableInBrowser` con mensaje claro: "Esto requiere el .exe, no el dev server".
- Migration ONLY runs en Tauri (no browser).

---

## 9. Estilo visual

Heredado 100% del ERP existente (sin desviarse). Tokens canonical en `el-club/overhaul/src/app.css`.

### Paleta (de `app.css`)

| Token | Hex | Uso |
|---|---|---|
| Background base | `#08080a` | Fondo principal |
| Surface 1 | `#0f0f12` | Sidebar, cards, áreas secundarias |
| Surface 2 | `#16161b` | Hover states, dividers, chips |
| Surface 3 | `#1e1e24` | Hover lift, badges |
| Border | `#22222a` | Bordes default |
| Border strong | `#35353f` | Bordes hover |
| **Accent (primary)** | `#5b8def` | Azul Linear · acciones primarias, focus, links |
| **Terminal (gaming)** | `#4ade80` | Status LIVE/closed, success, glow |
| Warning | `#f5a524` | Pending, atención, ETA, lead time amber |
| Danger | `#f43f5e` | Crítico, errores, cancelar batch |
| Info | `#60a5fa` | Info neutral |
| Text primary | `#e6e6ea` | Texto principal |
| Text secondary | `#9a9aa3` | Texto secundario |
| Text tertiary | `#63636d` | Labels, meta info |
| Text muted | `#42424a` | Texto deshabilitado |

### Tipografía (de `app.css`)

- **Sans (default):** 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI'
- **Mono (números, IDs, SKUs, FX):** 'JetBrains Mono', 'SF Mono', Menlo, Consolas
- **Display (labels uppercase):** mismo mono con `text-transform: uppercase` + `letter-spacing: 0.04em–0.08em`

Base font-size: 13px · line-height: 1.5 · `font-variant-numeric: tabular-nums` para todos los numbers.

### Patrones (heredados de Comercial)

- **Status pills:** `● UPPERCASE` con dot prefix · padding 2-3px · border-radius 2-3px · bg semi-transparente del color · `pulse-live` animation para LIVE/active
- **Section labels:** uppercase 9.5px · color tertiary · letter-spacing 0.08em
- **Cards:** background surface-1 · border 1px border · border-radius 4-6px
- **Buttons primary:** bg accent verde-azul · color black · font-weight 600
- **Buttons secondary:** bg surface-1 · border · color text-secondary
- **Buttons danger:** transparent · border rojo semi-transp · color rojo
- **Mono numbers:** `font-variant-numeric: tabular-nums` para alineación
- **Mini-progress bars:** 5 ticks horizontales para el state machine de import (DRAFT/PAID/IN_TRANSIT/ARRIVED/CLOSED)
- **Glow effects:** `pulse-live` en status pills LIVE · `glow-accent` en focus

### Mockups de referencia

Ver `.superpowers/brainstorm/1923-1777335894/content/`:

- `00-intro.html` — Roadmap de las 5 fases del brainstorm
- `01-flujo-actual.html` — Flujo end-to-end del proceso actual (7 etapas)
- `02-data-historica.html` — Schema imports + 2 records reales + verificación Q145
- `03-dominio.html` — Mapeo entidades/acciones/eventos extendido
- `04-approaches.html` — 3 approaches comparados (A1/A2/A3)
- `05-mockup-a1-hd.html` — HD mockup A1 v1
- `06-mockup-a1-hd-v2.html` — HD mockup A1 v2 (con correcciones de Diego: botones arriba, FX out, cost-flow out, Wishlist tab propia, lead time KPIs)
- `07-decisiones.html` — Las 6 D's de Fase 4 con recomendaciones

---

## 10. Estrategia de implementación por releases

6 releases secuenciales con dependencies. Cada release shippable independientemente con valor visible. Compromiso Diego: *"iteramos mientras lo vaya probando."*

### IMP-R1 — Skeleton + Pedidos + Migration (4-5 días)

**Scope:**
- Skeleton del módulo Importaciones · sidebar nav-item activo · tabs vacíos excepto Pedidos · pulso bar funcional
- Schema additions: `sale_items.unit_cost_usd`, `jerseys.unit_cost_usd`, `imports.tracking_code`, `imports.carrier`, `imports.lead_time_days`, default FX → 7.73
- **Migration script idempotente:** `el-club/erp/elclub.db` → SQLite del Tauri (2 imports + 51 sale_items + jerseys linked)
- Tab Pedidos con list-detail in-place funcional (sin modal grande)
- Detail pane: Overview sub-tab con stats strip (6 KPIs) + items preview (5) + timeline (6 stages con elapsed badges)
- Action toolbar arriba: Registrar arrival · Ver invoice · Ver tracking · Editar · Cancelar · Cerrar batch
- `close_import_proportional()` con D2=B (por valor USD) usando `unit_cost_usd` per item
- Items sub-tab con tabla completa (sortable básico)
- Costos sub-tab con cost flow detallado (movido del Overview por petición Diego)
- Pulso global con KPIs: Capital amarrado · Closed YTD · Avg landed · Lead time avg supplier · Wishlist count · Free units count
- Vínculo Comercial como link en detail-meta (lleva a Comercial filtrado por sales del batch)

**Diego ya puede:** ver los 2 batches existentes con UX nueva, cerrar IMP-2026-04-18 cuando llegue DHL, ver landed por unidad y per item.

**Dependencies:** ninguna (cimientos).

### IMP-R2 — Wishlist (3 días)

**Scope:**
- Tab Wishlist funcional con lista de items · filtros por status (assigned/stock/promoted)
- D7=B: validación de SKU existente al insertar (lee `catalog.json` via adapter)
- Acción "Promover a batch" — crea `imports` row draft y vincula items wishlist como `sale_items` (o `jerseys` para stock futuro)
- Inbox event: "wishlist > 20 → consolidar batch" + "wishlist item asignado > 30d"
- Settings: wishlist target size (default 20)
- Migration de wishlist desde chat WA personal de Diego: NO automatizable. Diego entra los 14 items que tiene actualmente como ejercicio de bootstrapping.

**Diego ya puede:** sustituir el chat personal de WA con el módulo, asignar pedidos a customers, promover batch cuando hay masa crítica.

**Dependencies:** R1 (schema + adapter).

### IMP-R3 — Margen real cross-Comercial (2-3 días)

**Scope:**
- Tab Margen real con lista de batches closed + breakdown revenue/cost/margin
- Queries cross-table: `sales` × `sale_items.import_id` × `imports.total_landed_gtq`
- Card per batch closed con Revenue, Landed, Margen bruto, Stock pendiente, Free units valor
- Filtros: período · supplier · status (closed default)
- Endpoints `/api/imports/margin` (Tauri command) que FIN-Rx pulla en su R1

**Diego ya puede:** ver margen real per batch shipping → cierra el loop con Comercial Sales Attribution.

**Dependencies:** R1 (close + sale_items.unit_cost) · idealmente Comercial R6 ya shipped (que ya lo está).

### IMP-R4 — Free units ledger (2 días)

**Scope:**
- Tab Free units con tabla y acciones (asignar destino: VIP/Mystery/Garantizada/personal)
- Schema `import_free_unit` poblado al close_import (auto-detect `floor(n_paid/10)` free units)
- Inbox event "free unit sin asignar > 7d"
- Migration de free units desde `imports.notes` strings (script regex + prompt a Diego para confirmar destino histórico)

**Diego ya puede:** trackear qué pasó con cada free unit · perder de vista nunca más.

**Dependencies:** R1.

### IMP-R5 — Supplier scorecard + multi-supplier infra (2-3 días)

**Scope:**
- Tab Supplier con tarjeta Bond Soccer Jersey + metrics agregados
- Lead time avg/p50/p95 · cost accuracy · dispute count · price band
- Estructura para agregar suppliers futuros (Yupoo direct, Aliexpress wholesale, etc.)
- Per supplier: contact info, payment terms, default carrier, default FX

**Diego ya puede:** comparar suppliers (cuando agregue un segundo) · datos sólidos para negociar con Bond.

**Dependencies:** R1 + datos suficientes (mínimo 5 batches closed).

### IMP-R6 — Settings + Polish (1-2 días)

**Scope:**
- Tab Settings con todas las secciones (Defaults, Umbrales, Migration log, Integrations placeholders)
- Empty states pulidos en todos los tabs
- Loading skeletons consistentes
- Bug fixes y feedback acumulado de R1-R5
- Browser fallback completos

**Diego ya puede:** tunear el módulo a su medida.

**Dependencies:** R1-R5.

### Total

```
R1 → R2 → R3 (R3 puede solapar con R2)
        ↓
        R4
        ↓
        R5 → R6
```

**Tiempo total de trabajo:** 14-18 días.
**Tiempo calendario realista:** 3-5 semanas con pausas para feedback y vida.

### Ritmo decidido

Mismo que Comercial: empezamos R1, vemos cómo se siente, decidimos ritmo en vivo. Diego: *"iteramos mientras lo vaya probando."*

---

## 11. Open questions / TBD

Ninguna abierta al cierre del brainstorming. Las decisiones D1–D7 + D-FX + D-FREE + D-MIG están fijadas (sec 6).

**Diferidos a v0.5+ (post-R6, no blockean R1):**

- BANGUAT API auto-fetch FX del día (D-FX opción C)
- DHL tracking webhook para auto-update `arrived_at`
- PayPal screenshot OCR para auto-llenar `bruto_usd`
- Multi-supplier real (más de Bond) con scorecards comparativos
- Bot ManyChat capture de wishlist (cliente pide en WA → entra automático al wishlist)
- Webhook a Comercial cuando close_import dispara (push notification "margen real disponible para release X")

Si durante implementación surgen ambigüedades:
1. Pausar.
2. Editar este spec con la decisión nueva.
3. Commit del spec actualizado.
4. Reanudar.

No improvisar in-flight.

### Cross-bucket flags (para Strategy)

- **FIN-Rx data dependencies:** Importaciones expone `imports.total_landed_gtq`, `sale_items.unit_cost`, `import_free_unit` para que FIN consuma cash flow + P&L per release + ROI. Schema queries documentadas en sec 7.
- **INV-Rx flow:** cuando Inventario exista, `imports.status='arrived'` debería disparar +stock automático para items con `customer_id IS NULL` (stock futuro). Hook a definir en INV-R1.
- **Comercial cross-link:** Sales Attribution loop ya existe en Comercial R6. Importaciones lo extiende escribiendo `sale_items.unit_cost` post-close, lo cual habilita "margen real per venta" en Comercial (ya consumible vía Margen real tab).
- **Sidebar reorganization:** Importaciones agrega 1 item al sidebar global (8 → 9). ADM-R1 debe reorganizar a 5 módulos top-level (Admin Web, Comercial, Importaciones, Finanzas, Inventario).

---

## 12. Apéndice — referencias

### Archivos existentes relevantes

- `el-club/erp/comercial.py` — Streamlit actual, fuente de la lógica `create_import` / `close_import` / `_refresh_import_unit_cost` / `get_pnl_by_import` a portar.
- `el-club/erp/schema.sql` — Schema imports + sale_items + jerseys con FK existentes.
- `el-club/erp/elclub.db` — DB con 2 imports históricos + 51 sale_items linked.
- `el-club/overhaul/src/app.css` — Tokens visuales canonical del ERP.
- `el-club/overhaul/src/lib/components/Sidebar.svelte` — Sidebar global actual (a extender con item Importaciones).
- `el-club/overhaul/src/lib/components/StatusBadge.svelte` — Status pill pattern a reusar.
- `el-club/overhaul/src/lib/components/comercial/BaseModal.svelte` — Modal pattern reusable para sub-flows (edit batch, drop creator, free unit assignment).
- `el-club/overhaul/src/lib/adapter` — Adapter Tauri/browser para DB access.
- `elclub-catalogo-priv/data/catalog.json` — Source para validación D7=B.

### Skills aplicables durante implementación

- `superpowers:writing-plans` — paso siguiente a este spec.
- `superpowers:test-driven-development` — para cada release.
- `superpowers:dispatching-parallel-agents` — útil para R2/R3 en paralelo (no comparten state).
- `superpowers:verification-before-completion` — antes de declarar cada release como hecho.

### Decisiones que aplican retroactivamente

Todas las decisiones del Comercial design (estilo visual retro gaming, mental model FM/EU4/CK3, modal pattern donde aplique) aplican a Importaciones sin modificación. Spec actualiza:

- **Detail pane in-place** como variante del modal pattern (cuando se trabaja sostenidamente sobre un detail · no para "ver y cerrar")

### Histórico Streamlit como referencia (no source-of-truth post-R1)

`erp/comercial.py` líneas 650–750 contienen las funciones que portamos:

- `create_import(conn, ...)` → equivalente Tauri command `commands::imports::create()`
- `close_import(conn, ...)` → `commands::imports::close_proportional()` (D2=B)
- `_refresh_import_unit_cost(conn, ...)` → `commands::imports::refresh_unit_cost()` (sigue siendo 1/N para count, prorrateo proporcional para values)
- `get_pnl_by_import(conn)` → `commands::imports::pnl()` (consumido por tab Margen real)

---

**Fin del spec.**

Próximo paso: review de Diego → invocar `superpowers:writing-plans` para generar plan `IMP-R1` detallado con 12-18 tasks ejecutables.
