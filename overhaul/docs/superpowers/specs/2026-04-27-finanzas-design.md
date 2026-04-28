# Finanzas — Diseño y especificación

**Fecha:** 2026-04-27 (noche-cierre)
**Autor:** Diego + Claude (sesión brainstorming · post-IMP)
**Status:** Diseño · pendiente review de Diego antes de plan de implementación
**Approach final:** A2 dashboard quadrant (4 cards · primary `Profit operativo` hero) + Estado de Resultados waterfall en tab propia + tab Productos para unit economics per modalidad
**Releases planificados:** 5 (`FIN-R1` → `FIN-R5`, ~12-16 días de trabajo)
**Brainstorm session:** `.superpowers/brainstorm/4941-1777340205/`
**Trigger:** post `IMP-R1` ship · consume `imports.total_landed_gtq`, `sale_items.unit_cost`, `sales.total_gtq`

---

## 1. Resumen ejecutivo

Finanzas es la sección del ERP de El Club donde Diego ve **la salud financiera del business** — específicamente, responde la pregunta canonical: **¿cuánto llevo ganado?**

El módulo es una **answer machine**, no un dashboard genérico. Toda decisión de UI se justifica por: *"¿esto ayuda a responder '¿cuánto llevo ganado?' más rápido?"* — reflejando que Diego tiene TDAH medicado y el costo de fricción es alto.

**Framing canónico** (Diego, sesión 2026-04-27):
> *"La idea es que sea el hub para ver salud financiera de El Club. Ingresos alimentados por Comercial, COGS de Importaciones, hay que resolver lo demás y cómo lo presentamos en el ERP."*
>
> *"La pregunta real es ¿cuánto llevo ganado?"*

El módulo combina 3 fuentes:
1. **Revenue** ← Comercial (`sales.total_gtq` filtered cash basis · paid only)
2. **COGS** ← Importaciones (`sale_items.unit_cost` post-close de IMP-R1)
3. **Opex + Marketing + Owner draw** ← FIN-R1 (tablas nuevas: `expenses`, `recurring_expenses`, `cash_balance_history`, `shareholder_loan_movements`, `owner_draws`)

**Boundary crítico:** FIN-Rx es **operaciones financieras del business El Club only**. NO duplica FÉNIX (CFO personal de Diego). FÉNIX consume FIN-Rx como una de sus fuentes (igual que ya consume VENTUS, Clan, betting). Single source of truth: FIN escribe, FÉNIX lee.

El Home muestra `+QXXX` profit operativo del mes actual con jerarquía despiadada (un número 10× más grande visualmente que todo lo demás). 3 cards secundarias dan contexto (cash, capital amarrado, shareholder loan). Drilldown infinito a tabs específicas.

Estética: retro gaming / terminal heredada de Comercial e IMP. Sin desviaciones.

---

## 2. Contexto y objetivos

### Por qué overhaul

Hoy Diego no tiene un lugar único para "salud financiera de El Club". La data vive distribuida en:

1. **Streamlit Comercial** — revenue per sale visible pero no agregado a profit del mes
2. **PayPal/Recurrente dashboards** — entradas/salidas pero sin contexto de business
3. **Query SQL ad-hoc al `elclub.db`** — para cuando Diego quiere saber margen
4. **Spreadsheet propio mental** — para gastos no-COGS que ningún sistema captura
5. **No lo sabe en tiempo real** — calcula cuando algo lo obliga (papá pregunta · decidir si comprar más jerseys · fin de mes)

5 herramientas, 0 respuestas instantáneas. TDAH amplifica el costo de cada salto entre tools — la respuesta a "¿cuánto llevo ganado?" toma 15-30 minutos hoy y muchas veces se difiere indefinidamente.

### Mental model

Heredado del CLAUDE.md global:
- **Información densa OK** organizada por capas. FM finance tab · CK3 character window.
- **Drilldown infinito** — click en cualquier número revela detail.
- **Eventos demandan decisiones** — Inbox financiero CK3-style (próximo cargo · profit positivo después de 2 meses negativos · shareholder loan creciendo · cash record histórico).
- **Causalidad visible** — del revenue al profit pasando por cada deducción (Estado de Resultados waterfall).
- **Multiple lenses** — Home A2 (snapshot) + Estado de Resultados (causal) + Productos (per modalidad) + Cuenta (cash flow) son 4 lentes sobre la misma data.
- **Time control** — período toggle 8 opciones (Hoy / 7d / 30d / Mes actual default / Mes ant / YTD / Lifetime / Custom).

### Objetivos concretos

1. **Responder "¿cuánto llevo ganado?" en 0.5 segundos** al abrir el módulo. Sin scroll, sin clicks, sin decisiones.
2. **Centralizar la salud financiera** del business en un único módulo del ERP.
3. **Reducir saltos entre herramientas** — Diego no abre PayPal/Recurrente/Streamlit/spreadsheet: todo desde FIN-Rx.
4. **Trackear opex + shareholder_loan + owner draws** que ningún sistema captura hoy.
5. **Exponer datos para FÉNIX** (CFO personal) vía endpoints/queries — FÉNIX consume FIN-Rx como fuente cross-business.
6. **TDAH-respeto absoluto** — anti-fricción, jerarquía despiadada, sin ruido decorativo.

---

## 3. Arquitectura general

### Inserción en el ERP existente

Finanzas es un item del sidebar global del ERP (sección Data):

```
ERP Sidebar (post-FIN · pre-Admin Web R7)
├── WORKFLOW
│   ├── Queue
│   ├── Audit
│   ├── Mundial 2026
│   └── Publicados
└── DATA
    ├── Dashboard
    ├── Inventario
    ├── Comercial
    ├── Importaciones      ← IMP-R1 (en build)
    ├── Finanzas           ← este spec (NEW)
    └── Órdenes
```

Click "Finanzas" → entra al modo Finanzas. Cuerpo principal cambia a:

```
┌─────────────────────────────────────────────────────────────────┐
│ MODULE HEAD: Finanzas · [+ Nuevo gasto] [Estado Res] [Export]   │
├─────────────────────────────────────────────────────────────────┤
│ TABS: 🏠Home  📊EdR  🏷Productos  💸Gastos  🏦Cuenta  🔄Inter  ⚙│
├─────────────────────────────────────────────────────────────────┤
│ PERIOD STRIP: Hoy · 7D · 30D · MES ACTUAL · ... · Custom        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Body del tab activo (cambia según selección)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Reglas arquitectónicas

1. **Finanzas es UN item del sidebar**, no varios. Home/EdR/Productos/Gastos/Cuenta/Inter/Settings son sub-tabs adentro.
2. **Period strip persiste entre tabs.** Cambies de tab o no, el período activo se mantiene · datos del tab activo recalculan al período seleccionado.
3. **No hay Pulso bar global del módulo** — el Home A2 ES el pulso. Evita duplicación entre Pulso bar + cards primary del Home.
4. **El sidebar global del ERP no se rediseña en R1.** Finanzas se inserta como nav-item nuevo. Cuando ADM-R1 ejecute (Admin Web), sidebar se reorganiza completo.
5. **Último tab + período persisten en localStorage.** Reabrir Finanzas restaura estado.
6. **Branding heredado** del ERP Tauri (Midnight Stadium dark + Inter + JetBrains Mono).

### Navegación cruzada

| Salida | Destino |
|---|---|
| Click otro item del sidebar | Sale de Finanzas. Al volver, restaura último tab + período. |
| Cmd+K command palette | Acepta queries cross-tab: "abr 2026 profit" → Home en mes actual; "shareholder" → tab Inter-cuenta; "+gasto Q145 cloudflare" → opens entry form pre-filled. |
| Click card Home → tab correspondiente | Profit hero → EdR · Cash → Cuenta · Capital → IMP · Shareholder → Inter-cuenta. |
| ESC dentro de modal/form | Cierra modal · queda en el tab. |

### Coexistencia con módulos hermanos

| Módulo | Dependencia |
|---|---|
| **Comercial** | FIN lee `sales.total_gtq` (revenue), `sale_items.unit_cost` (COGS), `campaigns_snapshot.spend` (marketing). FIN NO escribe a Comercial. |
| **Importaciones** | FIN lee `imports.total_landed_gtq` (capital amarrado en transit), `sale_items.unit_cost` (COGS post-close). FIN NO escribe a IMP. |
| **Audit / Vault** | Sin dependencia. |
| **FÉNIX** (skill personal de Diego) | FIN expone queries SQL / endpoints para que FÉNIX consume cross-business rollup. FIN NO conoce a FÉNIX. |
| **DIEGO autonomous bot** (`@Claudiego_bot` Telegram) | FIN dispara push notifications via cron worker → bot envía mensajes a Diego. Sync staleness alerts. |

---

## 4. Los sub-tabs en detalle

### Tab 1 · Home (default)

**Layout:** A2 Three-quadrant + row de minis del waterfall comprimido + sub-grid Recent + Inbox.

#### 4 cards principales

```
┌──────────────────────────┬─────────────┬─────────────┬─────────────┐
│ PRIMARY (2 col span)     │ Cash hoy    │ Capital     │ Te debe     │
│ ▸ Llevás ganado este mes │ Q4,180      │ amarrado    │ a vos       │
│                          │ blue        │ Q3,915      │ Q2,420      │
│   +Q1,847 (verde 48px)   │             │ amber       │ muted       │
│   ↑ vs marzo Q-432       │ El Club     │ stock + IMP │ shareholder │
└──────────────────────────┴─────────────┴─────────────┴─────────────┘
```

**Primary card (`profit_operativo`):**
- Hero number GIGANTE (48px JetBrains Mono · color terminal verde si > 0, rojo si < 0)
- Trend vs período anterior (mes actual vs mes anterior)
- Sub: "vs YTD acumulado · vs lifetime"
- Click → tab Estado de Resultados (drilldown causal)

**Secondary 1 — Cash en cuenta business:**
- Balance sincronizado por Diego vía Claude (D-SYNC=A). Default cadencia weekly.
- Color azul (info)
- Sub: "El Club · Recurrente clearing" + timestamp última sync
- Click → tab Cuenta business

**Secondary 2 — Capital amarrado:**
- `imports.total_landed_gtq` de batches con status IN ('paid','in_transit','arrived') + value de stock no vendido
- Color amber (warning · plata no líquida)
- Sub: "stock + IMP en transit"
- Click → tab Importaciones

**Secondary 3 — Te debe a vos (shareholder_loan):**
- Sum de `shareholder_loan_movements` (gastos pagados con TDC personal − recoupments)
- Color muted (info, no urgente)
- Sub: "gastos pagados con TDC personal"
- Click → tab Inter-cuenta

#### Row 2 · Waterfall comprimido (4 minis)

4 KPIs horizontales con bars proporcionales:
- `+ Revenue` · verde · width 100% (anchor)
- `− COGS` · rojo · width proporcional
- `− Marketing` · amber · width proporcional
- `− Opex` · azul · width proporcional

Click cualquiera → tab Estado de Resultados con esa fila pre-expandida.

#### Sub-grid · Últimos gastos + Inbox

**Últimos gastos:** lista de 6 con `date · desc · cat pill · amount + method icon` (💳 TDC personal, 🏦 cuenta business). Scroll vertical. Click → modal Edit gasto.

**Inbox financiero:** eventos CK3-style con `border-left-color` por severidad:
- 🔴 Crítico — runway < 2 meses · TDC personal cerca del límite · gasto inusual (>3× promedio cat)
- 🟠 Atención — próximo cargo recurrente · shareholder loan creciendo · sync stale > N días
- 🔵 Info — profit positivo después de N negativos · cash record histórico · gastos sin categorizar
- ⚪ Estratégico — primer mes profitable · meta mensual cumplida

### Tab 2 · Estado de Resultados

**Layout:** A3 Waterfall expandido vertical · revenue → menos COGS → menos mkt → menos opex = profit · cada fila clickeable y drilleable.

```
+ Revenue Comercial          [bar 100%]              +Q5,500
   8 ventas mes · Q688 ticket avg
− COGS · landed cost         [bar 28%]               −Q1,520
   8 jerseys × Q145 + 2 hidden cost
− Marketing                  [bar 30%]               −Q1,650
   Meta Ads · 3 campañas activas
− Opex                       [bar 9%]                −Q483
   Forza · Recurrente fee · tech infra · pkg
─────────────────────────────────────────
= Profit operativo           [bar 34%]               +Q1,847
   vs marzo Q-432 · vs YTD Q1,415
```

**Drilldown click en cada fila:**
- `Revenue` → tabla de sales del período (modality / customer / amount / paid_at)
- `COGS` → tabla de items vendidos con unit_cost prorrateado
- `Marketing` → campaigns_snapshot del período (link a Comercial Ads)
- `Opex` → tabla de expenses del período filtrada por categoría

**Toggle vista:**
- Total (default · 1 columna)
- Por modalidad (3 columnas: Mystery / Drop / Vault)
- Por mes (compara meses lado-a-lado · YTD)

### Tab 3 · Productos · economía per modalidad

**Scope:** unit economics ranking de cada modalidad activa en DB (`Mystery / Drop / Vault` actuales; futuras se agregan auto al detectar nuevas modalities en sales).

**Layout:** ranking por margin GTQ con bars proporcionales.

#### Top KPIs (5 cards strip)

- 🥇 Top en margen `Modalidad X · +QY/u · Z%`
- 📦 Top en volumen `Modalidad X · N sales`
- 🩸 Producto que más sangra (si margin < 0)
- ⚖️ Margin avg ponderado (incluye todas)
- ✨ Margin avg sin loss leaders (excluye margin < 0)

#### Tabla ranking

| # | Modalidad | Margin Bar | Margin GTQ | Revenue | COGS | Margin % | N sales | Ticket avg |
|---|---|---|---|---|---|---|---|---|
| 🥇 | Mystery | bar verde 100% | +QXXX | +QYYY | −QZZZ | NN% | N | QXXX |
| ... |

Sortable por cualquier columna. Default sort: Margin GTQ DESC.

**Drilldown click en row:** abre detail per modalidad con:
- Time series de margin per mes
- Breakdown SKU dentro de la modalidad (Argentina vs Brasil vs Retros)
- Ticket avg trend
- Velocidad de venta (días promedio paid → delivered)

**Tab body bottom:** insight automático generado per período. Ejemplo: *"Sin contar F&F, business tiene +62% margin avg ponderado. Mystery gana en volumen, Garantizada en per-unit. F&F arrastra Q-X — considerá si va a marketing inversión o cogs."*

### Tab 4 · Gastos

**Scope:** CRUD de expenses. Entry rapid TDAH-friendly + lista filtrable + recurring templates.

#### Form de entry · 3 actions max

```
┌─ + Nuevo gasto ─────────────────────────┐
│ Monto:  [   Q1,540   ]                   │  (tipear · 1 action)
│                                          │
│ Categoría: [Variable] [Tech] [Mkt]      │  (click 1 · 6 buckets)
│            [Ops] [Owner draw] [Otros]   │
│                                          │
│ Pagado con: [💳 TDC personal] [🏦 Bus.] │  (click 1)
│                                          │
│ Fecha: 2026-04-27 (default hoy · click   │  (auto)
│        para retroactivo)                  │
│                                          │
│ Notas: [opcional · qué es el gasto]     │  (opcional · agregado D-NOTES)
│                                          │
│ Moneda: [Q] [USD]  USD → conversion 7.73│  (D-CURRENCY=A)
│                                          │
│         [Cancelar]  [Guardar gasto]     │
└──────────────────────────────────────────┘
```

3 actions efectivas (monto + categoría + método). Fecha y notas opcional. Submit en 1 click.

#### Categorías (6 buckets · D2 confirmado)

| Bucket | Ejemplos | Pattern entry | Frecuencia |
|---|---|---|---|
| **1. Variable per sale** | Forza Q30/entrega · Recurrente fee 4.5%+Q2 · packaging por unit | **Auto** (deducido per sale) | cada venta |
| **2. Tech infra recurrente** | Cloudflare · dominio elclub.club · Brevo · Anthropic API · ManyChat | **Template recurrente** (set once, auto-loguea) | mensual |
| **3. Marketing** | Meta Ads | **Auto-pull** desde `campaigns_snapshot.spend` | continuo |
| **4. Operaciones one-off** | Packaging bulk · photoshoots · freelancers · contenido | **Manual** rapid | irregular |
| **5. Owner draw** | Diego sacando plata del business | **Manual con flag especial** (no entra en profit operativo) | irregular |
| **6. Otros** | Edge cases | **Manual** | raro |

#### Lista de gastos

Tabla densa con filtros por categoría / método / período. Sortable. Bulk actions (re-categorize, delete, export).

#### Recurring templates

Tab interno (sub-section) con templates de gastos que recurren mensualmente. Cada template tiene: `name, amount, currency, day_of_month, active, started_at, payment_method_default, category, notes_template`. Cron worker logs auto cada mes a `expenses` table.

Templates iniciales (R1 backfill):
- Cloudflare Workers (~Q145/mes · TDC personal)
- Anthropic API (~Q142/mes · TDC personal)
- Brevo email (free hasta 300/día · escala)
- ManyChat (free hasta 1k subs · escala)
- Dominio elclub.club (~$12/año · annual)

### Tab 5 · Cuenta business

**Scope:** balance bancario del business + cash flow histórico.

#### Layout

```
┌─ Balance hoy ───────────────────────────────┐
│   Q4,180  (sincronizado lunes 8am · 6d ago) │
│   ⚠ Stale · sync now                         │
│   Sparkline 30d ──────────────────╱──        │
└──────────────────────────────────────────────┘

┌─ Movimientos · 30d ─────────────────────────┐
│ Date         Concepto       Method     Amount │
│ 2026-04-25   Sale CE-ABCD   Recurrente +Q335 │
│ 2026-04-24   Forza 2x       Cash      −Q60   │
│ 2026-04-22   Cloudflare     TDC pers  (—)    │  ← no afecta cash business
│ ...                                            │
└──────────────────────────────────────────────┘
```

#### Balance widget

- Big number (balance al último sync)
- Timestamp + age (`6d ago`)
- Status pill: `🟢 fresh` (< 7d) · `🟡 stale` (7-14d) · `🔴 muy stale` (> 14d)
- Botón "Sync now" — abre modal con instructions: "Andá a tu app bancaria, copiá el balance, pegámelo acá"
- Sparkline 30d del balance histórico

#### Sync nudge cron (D-SYNC=A · D-SYNC-CADENCE=weekly default)

- Cron worker (cada lunes 8am GT) verifica `cash_balance_history.last_synced_at` del business account
- Si > N días (default 7), dispara push:
  - Telegram via DIEGO autonomous bot (`@Claudiego_bot`)
  - Mensaje: "🏦 Balance El Club stale (Xd) · andá al ERP > Finanzas > Cuenta y syncea"
- Si > 2× cadencia (default 14d), escalation con icono ⚠ urgente
- Diego responde por:
  - Telegram → bot persiste en KV → cron pull → ERP update
  - O · Claude Code session: "/fenix sync-cuenta-elclub Q5,200" → command Tauri update
  - O · directo en ERP: tab Cuenta → "Sync now" → input balance → save

#### Lista de movimientos

Tabla con todos los movements `cash_business`-related en período seleccionado:
- Sales paid (revenue · vía Recurrente clearing) — `+Q`
- Expenses pagados con `payment_method='cuenta_business'` — `−Q`
- Owner draws — `−Q` flag especial
- Adjustments manuales (reconciliation) — `±Q`

Lista NO incluye expenses pagados con TDC personal (no afectan cash business · viven en `shareholder_loan_movements`).

### Tab 6 · Inter-cuenta · shareholder loan

**Scope:** trackea la deuda dinámica entre el business y Diego personal.

#### Concepto canonical

Cada vez que Diego paga un gasto del business con TDC personal, **el business le queda debiendo**. La acumulación es `shareholder_loan`. Cuando Diego mueve plata de cuenta business → personal, primero paga la deuda; el exceso es owner draw.

D-DRAW=A · auto-resolve: sistema computa si un movimiento es recoupment o draw, no Diego per movement.

#### Layout

```
┌─ Te debe a vos ─────────────────────────────┐
│   Q2,420  (al 27-abr)                        │
│   +Q1,200 últimos 30d · creciendo            │
│   ▰ ▰ ▱ ▱ progress · ¿retiro?               │
└──────────────────────────────────────────────┘

┌─ Histórico de movimientos ──────────────────┐
│ Date       Tipo            Amount   Loan bal │
│ 2026-04-26 Pago Anthropic +Q142    Q2,420   │
│ 2026-04-22 Pago CF Workers +Q145   Q2,278   │
│ 2026-04-08 Pkg bulk        +Q450   Q2,133   │
│ 2026-03-30 Recoupment      −Q500   Q1,683   │
│ 2026-03-25 Pago Cloudflare +Q145   Q2,183   │
│ ...                                            │
└──────────────────────────────────────────────┘

┌─ Owner draws acumulados ────────────────────┐
│ YTD Q1,500  (1 movement: 2026-03-30 Q500)   │
│ Lifetime Q1,500                              │
└──────────────────────────────────────────────┘
```

#### Acciones

- "Registrar movimiento business → personal" — input `Q amount` · sistema auto-resolve recoupment + draw
- "Ver detalle de un mes" — drilldown con todos los movements

### Tab 7 · Settings

**Layout:** secciones colapsables.

**Secciones:**

1. **Período**
   - Default período al abrir (mes actual default)
   - Primer día del año fiscal (default enero 1)

2. **Sync cadence**
   - Cuenta business: weekly default · diario / quincenal / mensual / off
   - Recurring expenses: monthly cron day-of-month default

3. **Categorías custom** (v0.5)
   - Agregar bucket nuevo (default 6 buckets fijos en R1)

4. **FX**
   - Default 7.73 (heredado de IMP-R1)
   - Override per gasto disponible

5. **Notifications config**
   - Telegram channel: `@Claudiego_bot` (DIEGO autonomous)
   - Threshold runway (default < 2 meses → critical)
   - Threshold gasto inusual (default 3× promedio categoría)
   - Quiet hours (default 22:00-07:00)

6. **Recurring templates**
   - Lista de templates activas con edit / pause / delete

7. **Boundary FÉNIX**
   - Read-only info: queries que FÉNIX consume + última sync
   - Botón "Re-export ahora"

---

## 5. Decisiones operativas (fijadas · 13 total)

### Decisiones cargadas pre-sesión (NO reabrir)

| ID | Decisión | Resolución |
|---|---|---|
| Pre-D1 | Sub-módulo o propio | **Propio** en sidebar (nuevo item Data) |
| Pre-D2 | Trigger | Post-IMP-R1 ship · consume IMP data |
| Pre-D3 | Approach brainstorm | Sub-agent superpowers |
| Pre-D4 | Nomenclatura release | `FIN-Rx` canonical |

### Decisiones tomadas en sesión

| ID | Decisión | Resolución | Impact |
|---|---|---|---|
| **D-BOUNDARY** | FÉNIX vs FIN-Rx scope | **A** · separados · FIN expone queries · FÉNIX consume | R1 |
| **D-PROFIT-DEF** | Definición canonical de "ganado" | **B** · profit operativo = revenue − COGS − opex − marketing | R1 |
| **D-PERIOD-DEFAULT** | Período default | **Mes actual** · filtrable 8 opciones | R1 |
| **D-PAYMENT-METHOD** | Pago con TDC personal vs cuenta business | **2 actores** · `payment_method` flag · shareholder_loan tracked | R1 |
| **D-RETROACTIVO** | Fecha arranque data | **Marzo 2026** · backfill manual recurring + actuales | R1 |
| **D-CASH-BASIS** | Cuándo cuenta una venta | **A** · cash basis · cuando entra plata (`paid_at IS NOT NULL`) | R1 |
| **D-MODALITY-SET** | Modalidades en DB | **Mystery / Drop / Vault** (las 3 con MOD column R11). Futuras se agregan auto al detectar. | R1 |
| **D-APPROACH-HOME** | UI Home | **A2** · 4 cards (primary profit + 3 secundarias) + waterfall mini + sub-grid Recent + Inbox | R1 |
| **D-FEE** | Recurrente fee tratamiento | **A** · opex variable bucket · revenue se ve bruto | R1 |
| **D-SYNC** | Cash sync cuenta business | **A** · manual entry vía Claude · ERP nudge push notification | R1 |
| **D-SYNC-CADENCE** | Cadencia default sync | **Weekly** · lunes 8am push · configurable | R1 |
| **D-DRAW** | Owner draw modeling | **A** · auto-resolve · primero recoupment, luego draw | R1 |
| **D-REV-OVERRIDE** | FIN edita revenue | **A** · solo lee · arreglar en Comercial (single source) | R1 |
| **D-CURRENCY** | Multi-currency | **A** · display GTQ · entry nativo (USD/GTQ) con FX 7.73 | R1 |

---

## 6. Datos y sincronización

### Schema SQLite · adiciones

DB compartida con Streamlit (igual que IMP descubrió): `el-club/erp/elclub.db`. Schema additions vía script idempotente (similar `apply_imports_schema.py`).

#### Tablas nuevas

```sql
CREATE TABLE IF NOT EXISTS expenses (
  expense_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  amount_gtq        REAL NOT NULL,           -- canonical GTQ
  amount_native     REAL,                    -- USD/GTQ original entry
  currency          TEXT DEFAULT 'GTQ' CHECK(currency IN ('GTQ','USD')),
  fx_used           REAL DEFAULT 7.73,
  category          TEXT NOT NULL CHECK(category IN ('variable','tech','marketing','operations','owner_draw','other')),
  payment_method    TEXT NOT NULL CHECK(payment_method IN ('tdc_personal','cuenta_business')),
  paid_at           TEXT NOT NULL,           -- ISO date · cuándo se pagó
  notes             TEXT,
  source            TEXT DEFAULT 'manual' CHECK(source IN ('manual','recurring_template','auto_sale_derived','auto_marketing_pull')),
  source_ref        TEXT,                    -- e.g., recurring_template_id, sale_id, campaign_id
  created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS recurring_expenses (
  template_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  name              TEXT NOT NULL,           -- 'Cloudflare Workers'
  amount_native     REAL NOT NULL,
  currency          TEXT DEFAULT 'GTQ',
  category          TEXT NOT NULL,
  payment_method    TEXT NOT NULL,
  day_of_month      INTEGER CHECK(day_of_month BETWEEN 1 AND 28),
  notes_template    TEXT,
  active            INTEGER DEFAULT 1,
  started_at        TEXT NOT NULL,
  ended_at          TEXT,                    -- nullable · cuando se desactiva
  created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS cash_balance_history (
  balance_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  account           TEXT NOT NULL DEFAULT 'el_club_business',
  balance_gtq       REAL NOT NULL,
  synced_at         TEXT NOT NULL,
  source            TEXT NOT NULL CHECK(source IN ('manual_via_claude','manual_via_telegram','manual_direct','api_recurrente','reconciliation')),
  notes             TEXT
);

CREATE TABLE IF NOT EXISTS shareholder_loan_movements (
  movement_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  amount_gtq        REAL NOT NULL,           -- positivo: business le debe más a Diego · negativo: recoupment
  source_type       TEXT NOT NULL CHECK(source_type IN ('expense_tdc','recoupment','adjustment')),
  source_ref        TEXT,                    -- expense_id si source=expense_tdc · null si recoupment
  movement_date     TEXT NOT NULL,
  loan_balance_after REAL NOT NULL,          -- snapshot del loan balance post-movement
  notes             TEXT,
  created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS owner_draws (
  draw_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  amount_gtq        REAL NOT NULL,
  draw_date         TEXT NOT NULL,
  was_recoupment    INTEGER DEFAULT 0,       -- 1 si fue parcial/total recoupment de loan
  recoupment_amount REAL DEFAULT 0,
  pure_draw_amount  REAL,                    -- exceso después de recoupment
  notes             TEXT,
  created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_expenses_paid_at ON expenses(paid_at);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_payment_method ON expenses(payment_method);
CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_expenses(active);
CREATE INDEX IF NOT EXISTS idx_cash_synced_at ON cash_balance_history(synced_at);
CREATE INDEX IF NOT EXISTS idx_loan_date ON shareholder_loan_movements(movement_date);
CREATE INDEX IF NOT EXISTS idx_draw_date ON owner_draws(draw_date);
```

#### Vistas (computed values)

```sql
-- Profit operativo per mes
CREATE VIEW IF NOT EXISTS v_monthly_profit AS
SELECT
  strftime('%Y-%m', s.paid_at) AS month,
  SUM(s.total_gtq) AS revenue,
  SUM(COALESCE(si.unit_cost, 0)) AS cogs,
  (SELECT SUM(amount_gtq) FROM expenses
    WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', s.paid_at)
    AND category = 'marketing') AS marketing,
  (SELECT SUM(amount_gtq) FROM expenses
    WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', s.paid_at)
    AND category NOT IN ('marketing', 'owner_draw')) AS opex,
  (SELECT SUM(spend_gtq) FROM campaigns_snapshot
    WHERE strftime('%Y-%m', captured_at) = strftime('%Y-%m', s.paid_at)) AS marketing_meta_pull
FROM sales s
LEFT JOIN sale_items si ON si.sale_id = s.sale_id
WHERE s.paid_at IS NOT NULL
GROUP BY strftime('%Y-%m', s.paid_at);

-- Shareholder loan current balance
CREATE VIEW IF NOT EXISTS v_shareholder_loan_balance AS
SELECT
  COALESCE(SUM(amount_gtq), 0) AS current_balance
FROM shareholder_loan_movements;
```

### Sources de data

```
                     SQLite local (compartido el-club/erp/elclub.db)
                                         ↑
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
   Comercial existing               IMP existing                    FIN-R1 (NEW)
   sales · sale_items.unit_cost     imports · sale_items.unit_cost   expenses · recurring_expenses
   campaigns_snapshot                                                  cash_balance_history
                                                                       shareholder_loan_movements
                                                                       owner_draws
                                         ↓
                                   FIN-R1 reads
                                         ↓
                                   Tab Home (A2)
                                         ↓
                          Outputs FÉNIX consume cross-business
```

**Sin migration de data** (igual que IMP) — Tauri usa la misma `elclub.db` que Streamlit. Schema additions idempotentes vía `apply_finanzas_schema.py`.

### Source-of-truth

| Dato | Fuente | Notas |
|---|---|---|
| Revenue per sale | `sales.total_gtq` (Comercial) | FIN solo lee. Si está mal, se arregla en Comercial. |
| COGS per sale | `sale_items.unit_cost` (post-IMP close) | FIN solo lee. |
| Marketing spend | `campaigns_snapshot.spend` (Comercial Meta Ads) | FIN solo lee. |
| Opex | `expenses` (FIN) | FIN escribe. |
| Cash balance business | `cash_balance_history` last entry (FIN) | FIN escribe. Manual via Claude/Telegram/UI. |
| Shareholder loan | `shareholder_loan_movements` aggregate (FIN) | FIN escribe. Auto-poblada al insert expense con `payment_method='tdc_personal'` y al insert owner_draw. |
| Owner draws | `owner_draws` (FIN) | FIN escribe. |
| FX default | `imports.fx` default 7.73 (heredado IMP) | FIN solo lee config. |

### Política de conflictos

**Sin conflictos esperados** porque:
- FIN es el único writer de `expenses`, `recurring_expenses`, `cash_balance_history`, `shareholder_loan_movements`, `owner_draws`.
- FIN solo lee de `sales`, `sale_items`, `campaigns_snapshot`, `imports`.
- Comercial e IMP no tocan tablas de FIN.

Único caso de conflict: si Diego corre FIN y también edita sales en Comercial al mismo tiempo, el cálculo de profit puede hacer race. Mitigación: cache invalidation cada 60s + botón "Refresh" manual.

---

## 7. Errores, fallbacks, casos borde

### Sync failures

| Falla | Comportamiento del ERP |
|---|---|
| Telegram bot no responde al push | Cron retrasa al siguiente ciclo · log de fallas en Sistema. |
| Diego nunca syncea cash · stale > 30d | Stats del Home muestran banner: "⚠ Cash balance Xd stale · datos pueden no reflejar realidad" |
| Comercial DB lock al leer sales | FIN retry 3 veces · si falla, muestra last cached values con timestamp. |
| Recurring template falla al loggear (cron worker error) | Log del Sistema · Inbox event "⚠ Cargo recurrente Cloudflare no se logueó este mes" · Diego lo registra manual. |

### Casos borde de domain

- **Mes sin ventas (revenue Q0)** — profit = -opex - marketing (negativo). Display normal con banner "Mes flojo".
- **Período custom > 1 año** — performance degraded · advertencia "rango grande puede tardar".
- **Expense en USD con FX null** — bloquea con error "ingresá FX o usá default 7.73".
- **Owner draw sin recoupment posible (loan = 0)** — el draw entero va a `pure_draw_amount`. OK.
- **Recoupment > loan balance** — sistema bloquea con error "no podés recoupear más de Q lo que el business te debe". Diego ajusta el monto.
- **Categoría `owner_draw` en expense form** — disabled/hidden. Owner draws viven en tab Inter-cuenta, no en Gastos. Evita confusión.
- **Sale con paid_at NULL** — no entra al cálculo (cash basis · D-CASH-BASIS=A).
- **Sale cancelled después de paid** — entra al período si `paid_at IS NOT NULL` aunque después se cancele. Spec deja esta decisión sin resolver — flag para R1.x.

### Estados degradados / vacíos

| Cuándo | Qué muestra |
|---|---|
| Mes sin gastos ni revenue (primer día) | Home con cards en cero. Banner: "Sin actividad financiera todavía. Empezá registrando un gasto o esperá la primera venta." |
| Sin recurring templates | Tab Gastos > Recurring section vacía con "Agregar primer template" CTA. |
| Cash balance never synced | Card "Cash" muestra "—" · botón gigante "Sincronizar primer balance". |
| Inbox vacío | Mensaje terminal-style: `> all clean. nothing to act on.` |

### Browser fallback

Mantiene el patrón existente del adapter:
- Reads de Home con datos calculados funcionan con la SQLite del browser-shim (si dev mode).
- Writes (registrar gasto, sync balance, owner draw) tiran `NotAvailableInBrowser` con mensaje claro.
- Modal/forms abren igual; submit buttons disabled con tooltip "Requiere el .exe".

---

## 8. Estilo visual

Heredado 100% del ERP existente (sin desviarse). Tokens canonical en `el-club/overhaul/src/app.css` — los mismos que IMP y Comercial.

Patrones específicos de FIN-Rx (heredados):
- **Big number hero:** font-size 48px JetBrains Mono · color terminal verde (success > 0) · rojo (loss < 0)
- **Period selector:** botones mono pill-style en strip horizontal · active = `var(--color-accent)`
- **Cards primary vs secondary:** primary tiene border-color verde-tinted + bg gradient sutil · secondary border default
- **Bars proporcionales:** height 18px · linear-gradient para profit · solid color para componentes
- **Status pills:** `● UPPERCASE` con dot prefix · `pulse-live` animation para urgent items
- **Inbox events:** border-left 3px del color severity · padding 8/12 · cursor pointer

### Mockups de referencia

`.superpowers/brainstorm/4941-1777340205/content/`:
- `00-framing.html` — pregunta canonical + boundary
- `01-modelo-pagos.html` — 2 actores money flow + form TDAH
- `02-approaches.html` — A1/A2/A3 comparados
- `03-mockup-a2-hd.html` — HD del Home A2 (canonical)
- `04-tab-productos.html` — economía per modalidad ranking
- `05-decisiones.html` — Fase 4 grid

---

## 9. Releases planificados

5 releases secuenciales con dependencies. Cada shippable independientemente. Compromiso Diego: *"iteramos mientras lo vaya probando."*

### FIN-R1 — Skeleton + Home + Gastos CRUD (4-5 días)

**Scope:**
- Skeleton del módulo · sidebar nav-item activo · 7 tabs (2 funcionales · 5 placeholder con CTA "Próximamente en R2-R5") · period strip funcional
- Schema additions: 5 tablas nuevas (`expenses`, `recurring_expenses`, `cash_balance_history`, `shareholder_loan_movements`, `owner_draws`) + 2 views
- Home A2 funcional: 4 cards primary/secondary computados de DB · row 2 minis del waterfall · sub-grid Recent + Inbox
- Tab Gastos funcional: form 3 actions + lista filtrable + 6 buckets + auto-update de shareholder_loan al insert con `tdc_personal`
- Pulso global: removido (Home A2 ES el pulso)
- Period strip: 8 botones funcionales · cambio de período recalcula Home en runtime
- Cash sync widget: input manual del balance + history sparkline (R1 sin nudge cron · R3 lo agrega)

**Diego ya puede:** registrar gastos, ver profit operativo del mes actual al abrir, navegar períodos, ver shareholder_loan creciendo automáticamente.

**Dependencies:** IMP-R1 ship (necesita `sale_items.unit_cost` para COGS reales).

### FIN-R2 — Estado de Resultados + Productos (3-4 días)

**Scope:**
- Tab Estado de Resultados: waterfall expandido vertical · 4 filas + total · cada fila clickeable con drilldown
- Toggle vista: Total / Por modalidad / Por mes
- Tab Productos: ranking de modalidades por margin con bars proporcionales · top KPIs strip · drilldown per modality
- Insights automáticos generados (margin avg, top en margen, top en volumen)

**Diego ya puede:** entender la causalidad del profit · saber qué modalidad le deja más.

**Dependencies:** R1.

### FIN-R3 — Cuenta business + Inter-cuenta + Sync nudge (3 días)

**Scope:**
- Tab Cuenta business funcional: balance widget + sparkline 30d + lista de movements
- Tab Inter-cuenta funcional: histórico shareholder_loan + lista de owner_draws
- Sync nudge cron worker: detecta staleness · push Telegram via DIEGO autonomous bot · escalation > 14d
- Modal "Sync now" con instructions + input balance
- Modal "Registrar movimiento business → personal" con auto-resolve recoupment + draw

**Diego ya puede:** ver cash bancario actualizado · trackear toda la inter-cuenta · recibir nudges semanales.

**Dependencies:** R1.

### FIN-R4 — Recurring templates automation (2 días)

**Scope:**
- Tab Settings > Recurring section: CRUD de templates
- Cron worker mensual: día N del mes loggea automáticamente expenses para cada active template
- Inbox event si template falla
- Backfill manual desde marzo 2026 (Diego entra retroactivo via UI o bulk SQL si es masivo)

**Diego ya puede:** olvidarse de registrar Cloudflare/Anthropic/etc cada mes — el sistema lo hace solo.

**Dependencies:** R1.

### FIN-R5 — Polish + FÉNIX export endpoints (2-3 días)

**Scope:**
- Endpoints/queries SQL canonical para que FÉNIX skill consume FIN-Rx data
- Export CSV de expenses · sales · profit per mes · shareholder loan history
- Empty states pulidos en todos los tabs
- Loading skeletons consistentes
- Bug fixes y feedback acumulado de R1-R4
- Browser fallback completos

**Diego ya puede:** desde FÉNIX skill, leer FIN-Rx data como una de las fuentes del rollup personal cross-business.

**Dependencies:** R1-R4.

### Total

```
R1 → R2 → R3 (R3 puede solapar con R2)
        ↓
        R4 → R5
```

**Tiempo total de trabajo:** 14-17 días.
**Tiempo calendario realista:** 3-4 semanas con pausas para feedback y vida.

### Ritmo decidido

Mismo que Comercial e IMP: empezamos R1, vemos cómo se siente, decidimos ritmo en vivo.

---

## 10. Open questions / TBD

Ninguna abierta al cierre del brainstorming. Todas las 13 decisiones están fijadas en sec 5.

**Diferidos a v0.5+ / R5+ (no blockean R1):**

- API Recurrente clearing auto-pull (D-SYNC opción B · diferido)
- API banco GT (no existe standard · diferido)
- Categorías custom en Settings (R1 = 6 fijas · v0.5 = custom)
- Multi-business support (FIN-Rx solo El Club · si Diego agrega VENTUS / Clan al ERP, requiere refactor)
- Receipts attachments (foto del comprobante de gasto · v0.5)
- Tax tracking (IVA · ISR · diferido hasta que Diego formalice)
- Reportes avanzados (P&L tipo contable · cash flow statement · balance sheet · v0.5)

### Cross-bucket flags

- **FÉNIX skill update:** post FIN-R5 ship, FÉNIX necesita actualizar sus queries para consumir las views/endpoints de FIN-Rx (en lugar de leer Streamlit). Coordinación cuando R5 cierre.
- **Telegram bot DIEGO autonomous:** push messages adicionales al `@Claudiego_bot`. Coordinar con DIEGO bot owner para no spammear.
- **Sidebar reorganization (ADM-R1):** post FIN ship, sidebar tiene 11 items totales (8 originales + IMP + FIN + futuros). ADM-R1 debe reorganizar a 5 top-level (Admin Web · Comercial · Importaciones · Finanzas · Inventario).
- **Comercial cross-link:** si Diego implementa "ajustar revenue de sales históricas" (los 47 mundial F&F que mencionó), eso vive en Comercial · FIN se actualiza automático al refresh.

---

## 11. Apéndice — referencias

### Archivos existentes relevantes

- `el-club/erp/elclub.db` — DB compartida con Streamlit y Tauri (mismo path).
- `el-club/erp/comercial.py` — Streamlit con `sales`, `sale_items`, `campaigns_snapshot`. Source-of-truth de revenue + marketing.
- `el-club/erp/schema.sql` — schema canonical · documentar additions ahí.
- `el-club/overhaul/src/app.css` — tokens visuales canonical.
- `el-club/overhaul/src/lib/components/Sidebar.svelte` — sidebar global a extender.
- `el-club/overhaul/src/lib/components/StatusBadge.svelte` — pattern reusable.
- `el-club/overhaul/src/lib/components/comercial/BaseModal.svelte` — modal pattern para sub-flows.
- `el-club/overhaul/docs/superpowers/specs/2026-04-27-importaciones-design.md` — IMP spec (FIN consume IMP data).
- `~/.claude/skills/fenix/SKILL.md` — FÉNIX skill (CFO personal · consume FIN cross-business).
- `~/.claude/skills/diego/SKILL.md` — DIEGO autonomous (Telegram bot).
- `~/.claude/CLAUDE.md` global — Diego mental model + retro gaming aesthetic.

### Skills aplicables durante implementación

- `superpowers:writing-plans` — paso siguiente a este spec.
- `superpowers:test-driven-development` — para cada release.
- `superpowers:dispatching-parallel-agents` — útil para R2/R3 en paralelo.
- `superpowers:verification-before-completion` — antes de declarar cada release como hecho.

### Decisiones que aplican retroactivamente

- **TDAH-friendly UX** como principio: aplica a todos los módulos del ERP de Diego de aquí en adelante. Anti-fricción, jerarquía despiadada, sin ruido decorativo. Anclado.
- **Single source of truth** entre módulos: si la data está en Comercial, FIN solo lee. Evita double-source bugs. Aplica a futuros módulos.
- **Cash basis para revenue** (D-CASH-BASIS) puede aplicar a Comercial reportes también si son consistencia útil.

---

**Fin del spec.**

Próximo paso: review de Diego → invocar `superpowers:writing-plans` para generar plan `FIN-R1` detallado con 14-16 tasks ejecutables.
