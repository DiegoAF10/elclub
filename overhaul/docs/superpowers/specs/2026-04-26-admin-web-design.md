# Admin Web — Diseño y especificación

**Fecha:** 2026-04-26
**Autor:** Diego + Claude (sesión brainstorming)
**Status:** Diseño aprobado · pendiente plan de implementación R7
**Approach final:** Sidebar por producto (5 módulos) + Home como event queue + tabs internas FM-style
**Releases planificados:** 1 release principal R7 (~10-15 días), profundización en sub-releases R7.1-R7.5 cuando se haga "amor" en cada cascarón

---

## 1. Resumen ejecutivo

**Admin Web** es el módulo del ERP Tauri donde Diego gestiona el **contenido completo del sitio web público** de El Club. Es un CMS específico, multi-producto, con identidad gamer (FM/CK3/EU4) y densidad organizada por capas. Vive **dentro del ERP Tauri local** (no online), no requiere autenticación propia.

**Scope estricto:** Admin Web maneja qué/cómo aparece en el sitio. **NO toca** ventas, funnel, ads, customers, inbox, pedidos físicos, inventario o finanzas — eso vive en módulos hermanos del ERP (Comercial, Operativa, Inventario, FÉNIX).

El módulo se compone de **5 módulos principales** (sidebar nivel 1 dentro de Admin Web) + **Home** como entrada que muestra estado global y eventos accionables:

```
ADMIN WEB
├─ Home          ← KPIs · Accesos · Inbox de eventos
├─ 🗄️ VAULT      ← lo urgente, lo más rico (catálogo Q435)
├─ 📦 STOCK      ← garantizadas Q475 con drops mercadológicos
├─ 🎲 MYSTERY    ← pool sorpresa con drops temáticos
├─ 🌐 SITE       ← landing, branding, comunicación, comunidad, meta
└─ ⚙️ SISTEMA    ← infra del sitio (worker, R2, scrap, deploys, audit)
```

El espíritu visual es **retro gaming / terminal** (Football Manager, CK3, EU4): denso, gamey, expert-friendly. Hereda branding del ERP Tauri (Midnight Stadium dark + accent terminal).

---

## 2. Contexto y objetivos

### Por qué Admin Web

Hoy Diego administra el contenido del sitio (`elclub.club` + `vault.elclub.club`) repartido entre varias herramientas: el modal de Audit en el ERP para el catálogo, el repo `elclub-catalogo-priv` para Vault data, edits manuales en HTML para landing, no hay lugar para drops, ni para gestionar branding, ni para ver el sitio completo como un solo sistema.

Con el lanzamiento del Mundial 2026 + relanzamiento Mystery Box + futuro Stock garantizadas, la complejidad explota. Diego necesita **un solo lugar** donde decidir:
- Qué jerseys aparecen en el catálogo público (Vault)
- Qué jerseys están en stock garantizado con qué precio override y cuándo (Stock + drops)
- Qué pool de jerseys está disponible para Mystery y bajo qué reglas (Mystery)
- Qué landing pages, copy, branding, componentes del sitio están vivos (Site)
- El estado de toda la infra (worker, R2, CDN, scrap, deploys) (Sistema)

### Mental model

Diego piensa como strategy gamer (SimCity, EU4, CK3, Football Manager). Manejar El Club es "la versión adulta de estos juegos con réditos reales." El diseño se apoya en ese modelo:

- **Densidad de información OK** si está organizada por capas/contextos (FM Squad detail, CK3 character window).
- **Drilldown infinito** — click en cualquier entidad (jersey, override, tag) revela ventana grande con todo su detalle + acciones.
- **Eventos demandan decisiones** — tipo CK3 popup queue. Inbox del Home prioriza eventos accionables sobre KPIs estáticos.
- **Múltiples lentes sobre la misma data** — vista por producto (módulo) Y vista cross-producto (filtros). Como SimCity tiene mapa Y ledger.
- **Causalidad visible** — del scrap al audit al published; del override al drop al sitio.
- **Time control** — Calendario de drops + Audit log con histórico filtrable.
- **Sense of agency** — ninguna acción del sistema es "automágica sin opción a tweak." Diego puede editar cualquier auto-derivación.
- **Map / Ledger duality** — Calendario (visual) + Universo (tabla densa) son dos lentes de la misma data.

### Objetivos concretos

1. **Centralizar el CMS multi-producto** del sitio web en un único módulo del ERP.
2. **Reducir saltos entre herramientas** — Diego no abre VS Code, ni `vault.js`, ni el repo de catálogo: todo desde Admin Web.
3. **Sentido de panorama y control** — entrar a Admin Web debe dar la sensación de "abrir el panel del manager", no "abrir un dashboard SaaS."
4. **Cero decisiones perdidas** — eventos críticos (queue lleno, drop terminando, branding deployado) son visibles sin esfuerzo desde Home.
5. **Power-user friendly** — comandos rápidos (⌘K), atajos teclado, vistas guardadas, bulk actions.

---

## 3. Arquitectura general

### Inserción en el ERP Tauri

Admin Web es **un item del sidebar global del ERP** (al nivel de Comercial, Operativa, etc.):

```
ERP TAURI (binario local)
├─ 📦 Admin Web              ← este spec
│  ├─ Home
│  ├─ Vault · Stock · Mystery · Site · Sistema
│
├─ 💰 Comercial              ← Comercial R1 paralela (otro spec)
│  ├─ Funnel · Customers · Inbox · Ads · Settings
│
├─ 📊 Inventario             ← futuro
├─ 📋 Operativa / Pedidos    ← futuro
├─ ⚙️ Sistema ERP global     ← auth, updates, preferencias del binario
```

**Importante:** el `Sistema` como tab DENTRO de Admin Web NO se confunde con el `Sistema ERP global` del binario. El de Admin Web gestiona infra del SITIO público (worker, R2, CDN, scrap del catálogo). El del ERP global gestiona el binario (auth de Diego, updates, preferencias de la app).

### Reglas arquitectónicas

1. **Admin Web es UN item del sidebar global del ERP**, no varios. Vault/Stock/Mystery/Site/Sistema son sub-módulos adentro.
2. **No hay autenticación propia** — el ERP Tauri ya autentica a Diego a nivel global.
3. **No vive online** — es módulo del binario local; sin subdomain, sin login web.
4. **El último módulo+tab abierto se persiste** en localStorage. Reabrir Admin Web entra al estado donde quedaste.
5. **Branding heredado** del ERP Tauri (Midnight Stadium dark). Header del módulo dice "Admin Web" + breadcrumbs (`Admin Web > Vault > Queue`).
6. **Coexistencia con Comercial:** ambos viven en el mismo App.svelte/Router pero subdir distinto. Sin colisión.

### Navegación cruzada

| Salida | Destino |
|---|---|
| Click otro módulo del sidebar global (Comercial, Inventario, etc.) | Sale de Admin Web. Al volver, restaura último módulo+tab. |
| Cmd+K command palette | Acepta queries cross-módulo: "ARG-2026-L-FS" → modal jersey en Vault; "Mundial 2026" → tab Grupos del Vault con grupo abierto; "promover a stock" → drop creator. |
| Click breadcrumb | Sube nivel (Vault > Queue → Vault home → Admin Web home). |

### Versionado del módulo

Admin Web vive en `el-club/overhaul/src/routes/admin-web/`. Versionado sigue el del ERP Tauri (`overhaul/src-tauri/Cargo.toml`). Cambios mayores bumpean minor del ERP entero.

---

## 4. Sub-módulos: Home

El Home es la entrada al Admin Web. Pantalla full-HD muestra todo sin scroll. 3 secciones verticales:

### 4.1 — KPIs (mosaico al tope)

8 KPIs en grid 4×2, cada uno con número grande + label + sparkline 7 días:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│   892        47        12         8         140       23       2h        4│
│   PUBL.      STOCK     QUEUE     SCHED.    ACT.MES   GAPS     ÚLT.SCR.  D│
│   ▁▂▄▆█▇▆   ▃▄▅▆▇█▆   ▆▄▃▅▆▄▃   ▁▂▃▄▅█▇   ▂▃▄▅▆▇█   ▆▅▄▃▂▁   ─        ▁│
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
   PUBL. = publicados Vault total
   STOCK = LIVE en Stock ahora
   QUEUE = esperando audit
   SCHED. = drops programados próximos 30 días
   ACT.MES = jerseys nuevas publicadas este mes
   GAPS = supplier_gap conocidos
   ÚLT.SCR. = tiempo desde último scrap exitoso
   DIRTY = publicadas con foto rota detectada
```

Sparklines 7 días — patrón EU4 ledger / Bloomberg terminal. Click en cualquier KPI → drill al lugar que lo materializa.

### 4.2 — Accesos rápidos (tiles 5 módulos)

5 tiles uniformes en fila, cada uno con icon + nombre + mini-stat representativo:

```
🗄️ VAULT      📦 STOCK      🎲 MYSTERY    🌐 SITE       ⚙️ SISTEMA
892 pub       47 LIVE       —             v2.3          OK
12 queue      3 SCHED.      cascarón      deploy ok     3 alerts
```

Mini-stats reflejan estado del módulo. Mystery muestra "cascarón" hasta que se profundice.

### 4.3 — Inbox de eventos (CK3 popup queue)

Buckets de prioridad con border-left color:

- 🔴 CRÍTICO — requiere acción del día
- 🟠 IMPORTANTE — debería atender esta semana
- 🔵 INFORMATIVO — sugerencias / mejoras opcionales

Default visible: 5-7 eventos, sort por prioridad + recencia. Botón `[VER TODOS (N)]` abre vista completa.

```
🔴 12 jerseys esperando audit                       [QUEUE]
🔴 3 publicados con foto rota detectada hoy        [REVISAR]
🟠 Mundial 2026: 8 países sin jersey aún            [GAPS]
🟠 Stock drop programado para 2026-04-28 18:00     [DROP]
🟠 Mystery pool con 0 jerseys eligibles             [POOL]
🔵 5 publicados sin tag de Era — ¿clasificar?       [TAG]
🔵 Branding: logo nuevo deployado hace 3h          [PREVIEW]
```

Cada card es **dismissable** (X en hover). Reglas de auto-cierre:
- Crítico: persiste hasta resolverse (ej. queue=0)
- Importante: persiste 7 días, después auto-degrada a informativo
- Informativo: persiste 3 días, después auto-dismiss

### 4.4 — Command Palette (atajo Cmd+K)

Power feature global: atajo abre overlay con búsqueda fuzzy + acciones rápidas:

```
> _

▸ Scrap nueva categoría
▸ Crear grupo
▸ Crear tag
▸ Buscar jersey por SKU/team
▸ Ir a Vault > Queue
▸ Programar drop
▸ Toggle dirty en jersey
▸ Ver últimas 10 audits
─────────────────
CONFIGURACIÓN
▸ Cambiar tema
```

Atajos teclado adicionales (Vim-style):
- `n` Nueva audit (jump to next QUEUE jersey)
- `g s` Go to Stock
- `g v` Go to Vault
- `g h` Go to Home
- `?` Ver todos los atajos

---

## 5. Sub-módulos: Vault

Vault es **el corazón del Admin Web** y el más urgente. Catálogo completo de jerseys con su workflow de scrap → audit → publish + curaduría con grupos + lente densa universal.

### 5.1 — Sub-tabs del Vault (4)

```
VAULT
├─ Queue       ← pending audit (lo que urge HOY)
├─ Publicados  ← live en el sitio (mantenimiento, fix fotos)
├─ Grupos      ← Mundial · Retros · Top 5 · Latam (curaduría)
└─ Universo    ← TODAS las jerseys, búsqueda global, filtros
```

**Audit NO es tab** — es modo overlay (modal grande FM-style) que se invoca desde cualquier jersey en Queue/Publicados/Grupos/Universo.

### 5.2 — Estados del jersey (modelo de datos)

5 estados primarios mutuamente excluyentes:

```
DRAFT       Pre-pipeline. Catalog OK pero sin audit_decisions entry,
            o con scrap_fail. Vista diagnóstica solamente (Universo + Inbox).

QUEUE       audit_decisions.status='pending'. Tab Queue.

PUBLISHED   catalog.published=true. Live en vault.elclub.club.

REJECTED    audit_decisions.status='deleted'. Soft delete.
            Nunca fue PUBLISHED. Decisión definitiva.

ARCHIVED    Fue PUBLISHED, ya no. Puede revivir → PUBLISHED.
            (NUEVO — agregar flag/estado al schema actual)
```

### 5.3 — Flags ortogonales sobre el jersey

```
dirty: true            PUBLISHED necesita revisión (foto rota, CDN stale,
                       off-by-one thumbnail). Genera evento en Inbox.
scrap_fail: true       DRAFT con datos incompletos (Firecrawl falló L21,
                       skipped_no_hero L20). Bloquea move-to-QUEUE.
low_coverage: true     gallery.length < 3 (assert L20).
supplier_gap: true     proveedor no lo maneja (L12 — Paraguay/Australia/etc.)
                       Renderizar distinto en admin (no es bug del scraper).
qa_priority: 1         whitelist priorización (Mundial 2026, etc.)
in_vault: true         aparece en vault.elclub.club (default true para PUBLISHED).
```

### 5.4 — Overrides por producto (Stock / Mystery)

Cuando una jersey está PUBLISHED, puede tener overrides para Stock o Mystery (Alt B del modelo):

```javascript
stock_override {
  jersey_id: <ref al Vault>
  publish_at: timestamp | null    // drop programado
  unpublish_at: timestamp | null  // fin de drop (limitado/permanente)
  price_override: 475
  badge: "GARANTIZADA"
  copy_override: "última disponible"
  priority: 1-10
}

mystery_override {
  jersey_id: <ref al Vault>
  publish_at: timestamp | null    // entra al pool en X fecha
  unpublish_at: timestamp | null  // sale del pool en Y fecha
  pool_weight: 1.0
}
```

**Status visual del override (en su admin Stock/Mystery):**
- 🟢 LIVE — `publish_at <= now < unpublish_at`
- ⏰ SCHEDULED — override existe + `publish_at > now`
- ⏸ ENDED — `unpublish_at < now` (drop terminó)
- 📝 DRAFT — override existe sin `publish_at` (Diego está armando)

### 5.5 — Transiciones legales

```
DRAFT     → QUEUE       (FETCH OK + SEED, automático del pipeline)
DRAFT     → REJECTED    (manual: "esto no va")
QUEUE     → PUBLISHED   (audit aprueba)
QUEUE     → REJECTED    (audit rechaza)
PUBLISHED → ARCHIVED    (la retirás)
ARCHIVED  → PUBLISHED   (revivís)
REJECTED  → QUEUE       (cambiás de opinión, raro)
PUBLISHED + dirty=true  → no es transición, es flag toggleable
```

### 5.6 — Cómo caen los estados en las tabs

```
Queue       → estado QUEUE
Publicados  → estado PUBLISHED (con badge ⚠ si dirty)
Grupos      → subset de PUBLISHED asignados a un grupo
Universo    → TODOS los estados con filtros
```

DRAFT, REJECTED y ARCHIVED solo se ven desde Universo (filtros). Esto confirma valor de Universo como vista diagnóstica.

### 5.7 — Tab Queue

**No se rediseña** — mantiene UX actual del Audit existente (modal grande FM-style, atajos V/F/S, panel specs editable, BORRAR con preview). Catálogo Admin la abraza como tab, no la reemplaza.

### 5.8 — Tab Publicados

Vista **curatorial** distinta de Universo: cards medianas (no tabla densa) porque Diego acá ve "el frente del catálogo público" y necesita ojo curatorial.

**Smart filters al tope:**
```
[ TODAS · 892 ]  [ ⚠ NECESITA ATENCIÓN · 14 ]  [ 🆕 RECIÉN PUBLICADAS · 23 ]
[ ⏰ SCHEDULED · 8 ]  [ 🏷 SIN TAGS · 47 ]  [ 📅 ANTIGUAS SIN TOCAR · 156 ]
```

**Card propuesta (~280×360px):**
```
┌────────────────────────────┐
│    [JERSEY THUMB GRANDE]   │  ← 280×280 thumbnail visible
│  ⚠ DIRTY                   │
├────────────────────────────┤
│  ARG-2026-L-FS             │
│  Argentina · 2026 · Local  │
│  ⚽🌎🆕🎯                   │  ← tags icons
│  STK ─  MYS ⏰  COV 8/8    │  ← override status + coverage
│  [PROMOVER] [⚙] [🗑]        │
└────────────────────────────┘
```

**Modal al click:** mismo modal grande FM-style del Audit, con set de acciones según estado:

| Estado | Acciones disponibles |
|---|---|
| QUEUE | ✓ Aprobar · ❌ Rechazar · ⏰ Programar drop · 📝 Editar · 🏷 Tags · 💬 Notas |
| PUBLISHED | 📝 Editar · 🏷 Tags · 📦 Promover Stock · 🎲 Promover Mystery · ⚠ Toggle dirty · 🔄 Re-fetch · ⏸ Despublicar temp · 💤 Archivar · 🗑 Eliminar |
| SCHEDULED | ⏰ Editar fecha · ⏰ Cancelar · 📝 Metadata · 🏷 Tags · ▶ Publicar YA · 💤 Archivar |
| ARCHIVED | ▶ Revivir → PUBLISHED · ⏰ Revivir → SCHEDULED · 📝 Read-only · 💀 Eliminar permanente |
| REJECTED | 🔄 Mover a Queue · 💀 Eliminar permanente |

**Drop creator inline** (mini-modal cuando promovés a Stock/Mystery): publish_at, unpublish_at, precio override, badge, copy override, prioridad.

### 5.9 — Tab Grupos

Sistema de **TAGS** (no categorías exclusivas, no jerarquía rígida) con tipos predefinidos. Una jersey puede tener N tags simultáneos, pero **mutuamente excluyentes dentro del mismo tipo** (ej. Latam o Europa, no las dos).

**Catálogo de 10 tipos pre-poblados:**

| Tipo | Cardinalidad | Ejemplos |
|---|---|---|
| 🏆 COMPETICIÓN | N (no excluyente) | Mundial 2026, Champions, Eurocopa, Copa América, Libertadores |
| 🌎 GEOGRAFÍA REGIÓN | 1 (excluyente) | Sudamérica, Norteamérica, Europa, África, Asia, Oceanía, Medio Oriente |
| ⚽ LIGA | 1 (excluyente, solo clubes) | Premier, La Liga, Serie A, Bundesliga, Ligue 1, MLS, Liga MX |
| 🕰 ERA | 1 (excluyente) | Retros 60s, 70s, 80s, 90s, 2000s, 2010s, Modernos |
| 🏟 TIPO DE EQUIPO | 1 (excluyente) | Selección Nacional, Club Pro, Universitario, Amateur, Femenino |
| 👕 VARIANT EDICIÓN | N (no excluyente) | Conmemorativa, Edición Limitada, Anniversary, Co-branded |
| 🎯 COMERCIAL | N (no excluyente) | Top Sellers, Featured, Drop Nuevo, Restock, Limited Edition |
| 🎨 PALETA PRINCIPAL | 1 (excluyente) | Azul, Rojo, Blanco, Negro, Verde, Naranja, Amarillo, Multicolor |
| ⭐ NARRATIVA CULTURAL | N (no excluyente) | Era Maradona, Era Messi, Era Pelé, Final Mundial, Hat-Trick Histórico |
| 🏭 MARCA TÉCNICA | 1 (excluyente) | Adidas, Nike, Puma, Umbro, Kappa, Lotto, Joma |

**Reglas de validación al guardar:**
1. Cardinalidad: si tipo es 1-excluyente y ya tiene un tag, intentar otro → error con prompt "¿reemplazar?"
2. Condicional: Tipo de Equipo = Selección Nacional → Liga no permitido (validación cross-tipo)
3. Condicional: Tipo de Equipo = Club Pro → Liga obligatorio (warn si falta)
4. Soft-delete tag con asignaciones requiere confirmación; hard-delete solo si 0 uso

**Tags temporales / auto-derivados (Mix tipo C):**
- Mayoría manual (Diego prende y apaga)
- Algunos marcados como "auto-derivados" con regla calculable (ej. "Top 5" auto cada semana basado en views/sales del Vault, "Drop Nuevo" auto-prende al entrar y auto-apaga después de N días)

**País como tag + metadata:**
- `meta_country` ya existe en schema (campo)
- Tag tipo "🌍 PAÍS" (~50 tags, 1 excluyente) sincronizado bidireccional con el campo
- Aparece en tab Grupos para coherencia visual

**Permisos del admin sobre el catálogo:**
- Diego PUEDE: crear tag dentro de tipo existente · renombrar · editar color/icono · soft-delete
- Diego NO PUEDE (v0): crear tipo nuevo · cambiar cardinalidad · hard-delete con asignaciones

**UX del tab Grupos:** lista por tipo con badge de cardinalidad visible:

```
🏆 COMPETICIÓN                          [N por jersey] [+]
⚽ Mundial 2026             42 jerseys     [VER] [⚙]
🏆 Champions League         18              [VER] [⚙]

🌎 GEOGRAFÍA REGIÓN         [1 por jersey · excluyente] [+]
🌎 Sudamérica               67 jerseys     [VER] [⚙]
🌍 Europa                   140             [VER] [⚙]

🕰 ERA                      [1 por jersey · excluyente] [+]
🕰 Retros 80s               8               [VER] [⚙]
```

Click `[VER]` en un tag → drill: lista de jerseys miembros + drag-drop add/remove + programar drop conjunto + exportar.

### 5.10 — Tab Universo (lente EU4 ledger / FM database)

Vista densa que muestra **TODOS los estados** con filtros poderosos, vistas guardadas, bulk actions y URL state.

**Toggle vista tabla / grid** (default tabla, persiste preferencia):

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  ☐ [📷] SKU              TEAM           SEASON  VAR  EST  COV  TAGS                  STK  MYS  ÚLTIMA  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ☐ [🟦]  ARG-2026-L-FS   Argentina      2026    L    🟢   8/8  ⚽🌎🆕🎯              ─    ─    08/03   │
│  ☐ [🟦]  ARG-2026-L-PS   Argentina      2026    L    🟢   8/8  ⚽🌎🆕                ─    ⏰   07/15   │
│  ☐ [🟦]  ARG-2026-V-FS   Argentina      2026    V    🟢   3/8  ⚠⚽🌎🆕              🟢   ─    08/01   │
│  ☐ [🟥]  BRA-1970-L-RE   Brasil          1970    L    🟢   5/5  🕰🌎⭐                ─    ─    07/22   │
│  ☐ [🟧]  MEX-2026-L-FS   México          2026    L    📥   7/7  ⚽🌎🆕                ─    ─    pending│
│  ☐ [⬜]  TUR-2026-L-FS   Turquía         2026    L    📝   0/0  scrap_fail            ─    ─    fail   │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Leyenda estado:  🟢 PUBLISHED  📥 QUEUE  📝 DRAFT  ⛔ REJECTED  💤 ARCHIVED
Leyenda override: 🟢 LIVE  ⏰ SCHED  ⏸ ENDED  ─ sin override
```

Densidad: ~50px de alto por fila (thumbnail visible 40×55px), monospace tabular-nums, ~15-18 filas por pantalla.

**Filtros disponibles** (sidebar izquierdo, multi-select donde aplique):
- Estado (DRAFT/QUEUE/PUBLISHED/REJECTED/ARCHIVED) con counts reactivos
- Flags (dirty, scrap_fail, low_coverage, supplier_gap, qa_priority=1)
- Producto (in_stock override, in_mystery override, Stock SCHEDULED, Mystery SCHEDULED)
- Tags por tipo (10 secciones colapsables, cada una multi-select)
- Coverage (slider 0-N)
- Última acción (Hoy / Última semana / Último mes / Más antiguo)

Filtros: AND entre secciones, OR dentro de la misma sección.

**Vistas guardadas (presets) — v0:**
```
⭐ Default (todos)
📥 Queue del día
⚠ Publicados con foto rota
🕰 Retros sin tag de Era
⏰ Drops próximos 7 días
🔴 DRAFT con scrap_fail
🇲🇽 Latam Mundial 2026
➕ NUEVA VISTA
```

**Bulk actions** (multi-select con checkbox, barra superior reactiva):
- v0: tag bulk, archivar bulk, re-fetch bulk
- v0.5: drops bulk, eliminar bulk

**Sort + columnas configurables:**
- Click header → sort asc/desc
- Click derecho header → menú toggle visibility de cada columna
- Drag-drop columnas para reordenar

**Default visible:** thumb · SKU · Team · Season · Variant · Estado · Coverage · Tags · Stock · Mystery · Última acción.

**URL state:** filtros + sort + columns visibles persisten en query string. Compartir vista exacta o regresar después con misma config.

### 5.11 — Eventos del Vault que disparan Inbox

```
QUEUE > 0                          → "X esperando audit"
DRAFT + scrap_fail                 → "X scraped fallidos, re-scrap"
DRAFT sin scrap_fail (orphans)     → "X parseadas pero sin fetch"
PUBLISHED + dirty                  → "X publicadas con foto rota"
ARCHIVED > 30 días sin tocar       → "X archivadas viejas, ¿purgar?"
supplier_gap nuevo detectado       → "X sin disponibilidad"
```

---

## 6. Sub-módulos: Stock

**Scope:** CMS del Stock en el sitio (qué jerseys aparecen como garantizadas con qué precio override, badge y cuándo). NO ventas/conversion (eso vive en Comercial).

### 6.1 — Sub-tabs del Stock (3)

```
STOCK
├─ Drops       ← activos + programados + drafts. Vista default.
├─ Calendario  ← timeline visual de drops futuros (planning).
└─ Universo    ← tabla densa todos los overrides con filtros.
```

### 6.2 — Tab Drops

**Smart filters al tope** (mismo patrón que Publicados del Vault):
```
[ TODOS · 47 ]  [ 🟢 LIVE · 23 ]  [ ⏰ SCHEDULED · 8 ]  [ 📝 DRAFTS · 4 ]  [ ⏸ ENDED · 12 ]
```

**Vista default:** cards medianas (consistente con Publicados de Vault):

```
┌────────────────────────────┐
│    [JERSEY THUMB]          │  ← thumb del jersey base (Vault)
│  🟢 LIVE                   │
├────────────────────────────┤
│  ARG-2026-L-FS             │
│  Argentina · 2026 · Local  │
│  ⚽🌎 (tags heredados)      │
│  Q475 (override)           │  ← precio override
│  Badge: GARANTIZADA         │
│  Termina: 2026-05-15 18:00 │  ← unpublish_at
│  [EDITAR] [⏸ PAUSAR] [🗑]   │
└────────────────────────────┘
```

Click thumb → modal grande FM-style del jersey base (mismo del Vault). Modal indica: "Estás viendo el override Stock — para editar la jersey base ir al Vault."

### 6.3 — Tab Calendario (power feature)

Vista timeline de drops futuros, tipo CK3 succession timeline / Google Calendar:

```
       ABR  │   MAYO   │   JUNIO   │   JULIO    │
  ──────────┼──────────┼───────────┼────────────┤
            │ ⚽ Drop  │           │ 🌎 Drop    │
            │ Mundial  │           │ Eurocopa   │
            │ Wave 1   │           │ Recap      │
            │ 12 jersey│           │ 8 jerseys  │
            │ 5/15-30  │           │ 7/8-30     │
            │          │ ⭐ Drop  │            │
            │          │ Top 5    │            │
            │          │ recap    │            │
            │          │ 5/22-6/22│            │
```

Vista mensual default · toggle a semanal/trimestral. Click drop → drill al grupo de jerseys del drop. Drag-drop para mover fechas (con confirmación porque es destructivo).

### 6.4 — Tab Universo Stock

Misma vista densa que Vault > Universo (consistencia), pero filtrada por: **solo overrides Stock**. Filtros adicionales:
- Estado override (LIVE / SCHEDULED / ENDED / DRAFT)
- Precio override range
- Badge
- Duración del drop (permanente vs limitado)
- Días desde inicio
- Días hasta fin

### 6.5 — Eventos del Stock

```
Drop comienza próximas 24h        → "X drops Stock entran mañana"
Drop termina próximas 24h         → "X drops Stock terminan mañana"
Override sin publish_at > 7 días  → "X overrides en draft sin programar"
Drop activo > 90 días sin update  → "X drops antiguos, ¿revisar?"
```

### 6.6 — Profundidad v0 vs v0.5

**v0 cascarón:**
- Estructura tabs (Drops · Calendario · Universo)
- Override model con publish_at, unpublish_at, precio, badge, copy, prioridad
- Smart filters básicos en Drops
- Drop creator inline (definido en Vault > Publicados)
- Modal reutilizado del jersey base

**v0.5:**
- Vista calendario funcional drag-drop
- Bulk actions avanzadas
- Reglas de drop conflict (jersey en múltiples drops simultáneos)
- Templates de drop reutilizables (preset "Drop estándar 7 días Q475 con badge X")
- Webhooks/notificaciones a Comercial cuando drop arranca/termina

---

## 7. Sub-módulos: Mystery

**Scope:** CMS del Mystery (qué jerseys entran al pool, reglas de elegibilidad, drops temáticos). NO operaciones (quién compró, qué se entregó vive en Comercial/Operativa).

### 7.1 — Sub-tabs del Mystery (3 + Reglas modal)

```
MYSTERY                    ⚙ (icon junto al título → modal Reglas)
├─ Pool        ← jerseys elegibles AHORA (mystery override LIVE)
├─ Calendario  ← drops temáticos programados (timeline)
└─ Universo    ← todos los overrides Mystery + histórico
```

### 7.2 — Tab Pool

Smart filters al tope:
```
[ TODOS · 87 ]  [ 🟢 LIVE · 67 ]  [ ⏰ SCHEDULED · 12 ]  [ 📝 DRAFT · 8 ]
```

Cards iguales a Stock pero adaptadas:
```
┌────────────────────────────┐
│    [JERSEY THUMB]          │
│  🟢 LIVE                   │
├────────────────────────────┤
│  ARG-2026-L-FS             │
│  Argentina · 2026 · Local  │
│  ⚽🌎                       │
│  Weight: 1.5x              │  ← peso en algoritmo
│  Pool desde: 2026-04-01    │
│  Termina: permanente       │
│  [EDITAR] [⏸ PAUSAR] [🗑]   │
└────────────────────────────┘
```

### 7.3 — Tab Calendario

Igual a Stock Calendario. Power move: drops temáticos que substituyen/limitan el pool por un período (ej. "esta semana el pool Mystery incluye SOLO Mundial 2026").

### 7.4 — Tab Universo Mystery

Tabla densa todos los overrides Mystery + histórico. Filtros: weight range, días en pool, drops históricos, selecciones acumuladas.

### 7.5 — Modal de Reglas (icono ⚙)

Configuración del algoritmo de selección. v0 cascarón muestra UI con placeholders:

```
ALGORITMO BASE
○ Random uniforme
● Random ponderado (weight per jersey)
○ Por preferencias del cliente (wizard)
○ Híbrido (preferencias + ponderado)

ANTI-REPEAT
☑ No repetir misma jersey al mismo cliente en menos de [60] días

FAIRNESS
☑ Boost weight de jerseys NUNCA entregadas (rotación natural)

EXCLUSIONES
☑ Excluir jerseys con coverage < 5 fotos
☑ Excluir jerseys con dirty=true

POOL OVERRIDE TEMPORAL (drops temáticos)
○ Substituir pool completo
● Restringir pool al subset del drop
```

**v0:** UI persiste config. **v0.5+:** implementación de algoritmos en backend.

### 7.6 — Cómo entra una jersey al Pool

3 caminos:
1. **Por regla** (config en modal Reglas): "auto-eligibles todas las PUBLISHED con tag X"
2. **Promover individual** desde Publicados del Vault (drop creator inline)
3. **Bulk desde Universo del Vault**: select N jerseys → "Agregar a Mystery pool"

### 7.7 — Eventos del Mystery

```
Pool < 20 jerseys                       → "Pool Mystery bajo, considerá agregar"
Drop Mystery comienza próximas 24h      → "Drop temático Mystery mañana"
Drop Mystery termina próximas 24h       → "Drop temático Mystery termina mañana"
0 jerseys elegibles bajo reglas actuales → "🔴 Pool vacío, Mystery no opera"
Jersey pool > 90 días sin entregar      → "X jerseys nunca entregadas, ¿boost?"
```

### 7.8 — Profundidad v0 vs v0.5

**v0 cascarón:**
- Estructura tabs (Pool · Calendario · Universo)
- Override model con weight + drops
- Modal de Reglas con UI (config persiste, algoritmo viene después)
- Promover desde Vault > Publicados
- Bulk desde Vault > Universo

**v0.5+:**
- Implementación real de algoritmos (random ponderado, anti-repeat, fairness)
- Integración con wizard de preferencias del checkout existente
- Histórico de selecciones (cruza con Comercial)
- Métricas de pool (rotación, frecuencia, fairness real)
- Drops temáticos como entidad propia (template + recurrencia)

---

## 8. Sub-módulos: Site

**Scope amplio:** todo lo que Diego puede modificar sin programador, lo que NO es producto. El más amplio en perímetro.

### 8.1 — Sub-tabs del Site (6)

```
SITE
├─ Páginas        ← URLs navegables (estáticas + dinámicas + campañas)
├─ Branding       ← visual identity (paleta, logo, fonts, modo)
├─ Componentes    ← chrome global + embeds + integraciones de UI
├─ Comunicación   ← outbound + inbound + suscriptores
├─ Comunidad      ← reviews, encuestas, testimonios, feedback
└─ Meta + Tracking← SEO, A/B, accessibility, code, performance del sitio
```

### 8.2 — Tab Páginas

Lista con sub-categorías:

```
PÁGINAS
├─ 🏠 Estáticas         landing, FAQ, About, Términos, Privacidad, Envíos
├─ 🌍 Dinámicas/SEO    /mundial-2026, /retros, /latam — landing por grupo del Vault
├─ 🎯 Campañas         /promo-mundial, /buy2get1 — landing temporales para ads (UTM-aware)
├─ 🛒 Catálogo         configuración del listing /vault, /stock, /mystery
├─ 👤 Cuenta           /mi-cuenta, /mis-pedidos, /favoritos, /tracking
├─ 🚧 Especiales       /mantenimiento, /404, /500, /coming-soon
└─ [+ NUEVA PÁGINA]
```

**Editor de bloques** (tipo Notion/Squarespace, NO markdown crudo):
- Bloques pre-definidos: Hero · Texto rich · CTA button · Gallery · Testimonios · FAQ accordion · Embed video · Divider · Spacer · Custom HTML (escape hatch v0.5+)
- Drag-drop reordenar
- Cada bloque tiene panel de propiedades a la derecha
- Preview live en panel central

**Estados de página:** DRAFT · LIVE · SCHEDULED (programada para go-live).

### 8.3 — Tab Branding

```
PALETA
Primary, Accent, Warning, Alert, Success, Surface, Border (colores configurables con preview)

LOGO
Upload SVG/PNG · variantes dark/light/monochrome · favicon

TIPOGRAFÍA
Heading · Body · Mono (SKUs, IDs) · Display (UPPERCASE) — selector tipo Google Fonts

VARIANTES AVANZADAS (power user)
Spacing scale (tight/normal/loose) · Border radius scale (sharp/rounded/pill)
Animation level (none/subtle/full) · Sound design (toggle UI sounds)

MODO
● Dark only (default sitio) · ○ Toggle dark/light disponible

PREVIEW LIVE
[iframe del sitio actualizado en tiempo real]
```

Cambios disparan `dirty` flag global → preview en iframe. Apply real con confirmación + cache bust + redeploy automático.

### 8.4 — Tab Componentes

Lista de componentes globales editables, schedulables (publish_at / unpublish_at):

```
🎯 Header                                    [EDITAR]
🦶 Footer                                    [EDITAR]
📢 Banner top (announcement)                 [EDITAR] 🟢
🍪 Cookie consent + GDPR                     [EDITAR] 🟢
📧 Popup newsletter signup                   [EDITAR] ⏸
🎬 Hero rotativo del landing                 [EDITAR]
💬 Chat widget (Manychat/IG/WA)              [EDITAR] 🟢
📷 Instagram feed embed                      [EDITAR]
🎵 TikTok embed                              [EDITAR]
⭐ Reviews carousel global                    [EDITAR]
📩 Formulario de contacto                    [EDITAR]
🎁 Programa de referrals UI                   [EDITAR] (v0.5)
🏆 Loyalty tier display                      [EDITAR] (v0.5)
[+ NUEVO COMPONENTE]
```

### 8.5 — Tab Comunicación

```
✉️ Email Templates       confirmación pedido, envío, entrega, abandono carrito,
                          post-purchase, welcome, re-engagement, newsletter
📱 SMS Templates         tracking, alerta drop, OTP
💚 WhatsApp Templates   confirmación, recordatorios (cuando WABA OK)
🔔 Web Push Templates   nuevo drop, abandono carrito browser-side
📋 Listas y Segmentos   newsletter subscribers, customers, VIP, cold
🔄 Workflows            welcome series, abandoned cart, post-purchase upsell, win-back
📩 Forms inbound         contacto, newsletter, wishlist personalizada, encuestas
📊 Performance         open rate, CTR, unsubscribe (read-only stats)
```

**Frontera con Comercial:** marketing campaigns viven en Comercial. Acá vive **el contenido y plomería** (templates + workflows + lists). Comercial dispara y mide; Site configura.

### 8.6 — Tab Comunidad

```
⭐ Reviews                lista, moderación, respuestas, schema markup
                           filter: pending / approved / rejected / featured
🗣 Testimonios curados   selección manual para hero + reviews carousel
📊 Encuestas              pre-checkout, post-purchase, NPS, satisfaction
💌 Feedback inbound       mensajes contact form, suggestions, bug reports
🏷 User-generated content  fotos #elclubgt, testimonials con foto, unboxing videos
```

### 8.7 — Tab Meta + Tracking

```
🔍 SEO Global             title template, meta default, OG default, robots, sitemap
🌐 Páginas dinámicas SEO  reglas SEO para grupos del Vault (auto-vars)
📊 Analytics y Pixels     Meta Pixel, GA4, TikTok Pixel, Hotjar/Clarity
🏷 GTM / Tag Manager      Container ID + tags
🧪 A/B Testing            variantes página/copy/CTA + winner picker + stats
🌎 Idiomas y monedas      ES default, multi-idioma (v0.5), GTQ default, USD opt-in
📦 Regiones de envío      Guatemala depts, costos, SLA visible
♿ Accessibility           contrast, alt text auditor, ARIA review
⚡ Performance            CDN config, image optimization, lazy load, cache TTL, CWV
🚧 Maintenance mode        toggle on/off + custom message
📜 Audit log               todo cambio del Site + quién + cuándo (rollback)
🔍 Search config           campos buscables, synonims, trending, no-results page
```

**Code injection per-page:** OUT de v0 (overdesign).

### 8.8 — Eventos del Site

```
Cambio de branding deployado            → "Branding cambió hace 3h"
Banner top expira en 24h                → "Banner Mundial termina mañana"
Página DRAFT > 7 días sin tocar         → "Sobre nosotros lleva 7 días"
404 spike detectado                     → "X 404s nuevos esta semana"
Reviews pendientes moderación           → "12 reviews esperando moderación"
A/B test alcanzó significancia          → "Variante B ganó +18%, ¿aplicar?"
Email workflow falló                    → "Welcome series falló para 3 users"
Encuesta NPS bajo                       → "NPS bajó 12pts esta semana"
Form contacto sin respuesta > 48h       → "8 mensajes inbound sin contestar"
Page coverage SEO bajó                  → "Mundial 2026 perdió 3 keywords top"
Accessibility issue detectado           → "23 imágenes sin alt text"
Drop landing campaign termina 24h       → "Landing /promo-mundial expira"
Suscriptores nuevos esta semana         → "+47 suscriptores newsletter"
```

### 8.9 — Profundidad v0 vs v0.5

**v0 cascarón:**
- 6 tabs estructurales
- Páginas: lista + editor de bloques básicos
- Branding completo
- Componentes core
- Comunicación: email templates + workflows básicos + suscribers
- Comunidad: reviews moderación + encuestas básicas
- Meta + Tracking: SEO + pixels + GTM + accessibility check + maintenance + audit log

**v0.5+:**
- Editor de bloques rico
- A/B testing funcional con stats
- Multi-idioma real
- Loyalty/referrals UI
- Workflows visuales (drag-drop tipo Zapier)
- Page versioning + rollback granular
- Performance monitoring auto + alerts
- UGC moderación con AI assist

**Membresías** = vive en Comercial, NO acá.

---

## 9. Sub-módulos: Sistema

**Scope:** infra del SITIO público (worker, R2, CDN, scrap del catálogo, deploys, audit log de cambios). NO es el "Sistema ERP global" (auth/updates del binario Tauri).

### 9.1 — Sub-tabs del Sistema (4)

```
SISTEMA
├─ Status         ← health del sistema (worker, CDN, R2, alerts, activity feed)
├─ Operaciones    ← scrap, deploys, jobs/cron, backups (todo lo ejecutable)
├─ Configuración  ← APIs, tokens, locale, bot, feature flags (todo lo settable)
└─ Audit          ← audit log global del sitio + colaboradores futuros
```

(Acceso/login NO entra: ERP autentica a nivel global.)

### 9.2 — Tab Status (dashboard health tipo Grafana)

```
HEALTH OVERVIEW                                    🟢 ALL OK

Worker uptime           99.97%      ▁▂▄▆█▇█  últimos 7d
Worker latency p50      45ms        ▆▅▄▃▄▅▄
Worker latency p95      180ms       ▅▆▇▅▄▆▅
Error rate              0.12%       ▁▁▂▁▁▁▁
CDN cache hit rate      94%         ▇█████▇
R2 storage              4.2 GB      ▁▂▃▄▅▆▇
KV operations/min       340         ▄▅▆▇▆▅▄
Firecrawl credits       2,847 / 5K  ▇▆▅▄▃▂▁
Last successful scrap   2h ago
DB size (catalog.json)  14.2 MB     ▄▄▄▄▅▅▅

ACTIVE ALERTS
🔴 ninguna

ACTIVITY FEED (últimos 20 eventos)
10:42  ✓ Scrap completado: cat 711624 (Retros) — 120 albums
10:35  ✓ Deploy worker abcb9c4 → prod
10:30  ✓ Backup catalog.json (14.2 MB) → R2
10:15  ⚠ Firecrawl credits bajaron a 30%
[VER LOG COMPLETO]
```

Click cualquier KPI → drill al detalle.

### 9.3 — Tab Operaciones

```
🔄 Scrap                     interface "Scrap: <URL>" + historial + costos
🚀 Deploys                  worker version + last deploys + rollback
                             GitHub commits pendientes de deploy
⏰ Jobs / Cron              schedules: nombre, cron expr, last/next run, status
                             botón "ejecutar ya" + pause
💾 Backups                  lista (catalog + DB + R2 manifests)
                             schedule auto + retention + restore
🔧 Maintenance tasks       comandos one-shot: clear CDN cache, re-build sitemap,
                             regenerate thumbnails, vacuum DB, purge ARCHIVED viejos
📜 Logs                      streaming logs del worker + búsqueda
                             filter por severity / tag / fecha
```

Cada operación con confirmación si es destructiva. Logs streaming live.

### 9.4 — Tab Configuración

```
🔌 APIs y Conexiones        lista por integración con status:
                              GitHub 🟢 · Cloudflare 🟢 · R2 🟢 · Firecrawl 30%
                              Recurrente 🟢 · Resend 🟢 · Manychat 🟢
                              WhatsApp WABA 🔴 pending Meta verify
                              Meta Pixel/API 🟢 · Anthropic 🟢 Sonnet 4
                              cada uno: status, last test, rotate secret, usage stats

🤖 Bot Config               prompt del bot (editar inline)
                              modelo (Sonnet 4 / Haiku selector)
                              tools/MCP enabled (toggles)
                              knowledge base management
                              test bot (sandbox chat)

🌐 Locale del sistema       timezone (America/Guatemala)
                              date format (DD/MM/YYYY)
                              currency display (GTQ)
                              language (ES) · first day of week

🔔 Notifications config     canales: Telegram (Diego), email, push
                              threshold per severity · quiet hours · digest cadence

🚩 Feature Flags             toggles para experimentar

🔒 Secrets vault            lista (sin valores) · rotation history · audit de uso
```

### 9.5 — Tab Audit

```
📜 Audit log global         todo cambio del sistema:
                              timestamp · user · módulo · acción · diff
                              filter: fecha, usuario, módulo, severity
                              export CSV

👥 Colaboradores            (v0.5) invitar usuarios:
                              roles: admin / operator / viewer
                              permisos por módulo
```

### 9.6 — Eventos del Sistema

```
🔴 Worker error rate > 1%               → "Worker errores subieron a X%"
🔴 Firecrawl credits < 5%               → "Firecrawl casi sin créditos"
🔴 Last backup > 7 días                 → "Último backup hace X días, ¿forzar?"
🔴 Deploy failed                        → "Deploy de hace 1h falló"
🔴 Cron job failed N veces seguidas     → "Job X falló 3 veces seguidas"
🟠 R2 storage > 80%                     → "R2 al 85%, considerar cleanup"
🟠 Token API expira < 30 días           → "Token GitHub expira en 12 días"
🟠 DB size aumentó >20% en una semana   → "catalog.json creció 18% esta semana"
🔵 Backup completado                    → informativo (auto-dismiss 24h)
🔵 Scrap exitoso                        → informativo
```

### 9.7 — Profundidad v0 vs v0.5

**v0 cascarón:**
- 4 tabs estructurales
- Status: dashboard health + activity feed + active alerts
- Operaciones: scrap interface + deploys básicos + backups manuales + logs streaming
- Configuración: APIs lista con status + bot config + locale + notifications + feature flags
- Audit: audit log global

**v0.5+:**
- Colaboradores con RBAC real
- Performance profiler avanzado
- Auto-remediation (scripts que corren cuando Inbox dispara cierto evento)
- Disaster recovery playbook automatizado
- Multi-environment (staging/prod toggle)
- DB query analyzer / slow query detector
- Cost tracking per servicio (Cloudflare, Firecrawl, Anthropic, Recurrente)

---

## 10. Decisiones de domain capturadas

| # | Decisión | Resolución |
|---|---|---|
| D1 | Sidebar organización raíz | A — por producto (Vault/Stock/Mystery/Site/Sistema) |
| D2 | Home tipo | C+B híbrido — KPIs + Accesos + Inbox de eventos |
| D3 | Tabs internas Vault | 4 — Queue · Publicados · Grupos · Universo |
| D4 | Modelo de estados jersey | 5 estados + flags + overrides por producto (Alt B drops) |
| D5.1 | Grupos como qué tipo | A — TAGS (no categorías exclusivas, no jerarquía) |
| D5.2 | Tipos de tags | B — sí, con cardinalidad por tipo |
| D5.3 | Cuántos tipos | 10 (rico, power user) |
| D5.4 | Tags excluyentes dentro del tipo | Sí (1 Geografía, 1 Era, 1 Liga, etc.) |
| D5.5 | Tags temporales/auto | C — mix manual + algunos auto-derivados |
| D5.6 | País como tag o metadata | Ambos (tag + campo `meta_country` sincronizados) |
| D5.7 | Tag privado/wishlist Diego | NO — se maneja desde sitio público con cuenta de usuario |
| D6 | Vista Universo | Toggle tabla/grid · Vistas guardadas v0 · Bulk v0 · Thumb visible · URL state |
| D7 | Vista Publicados | Curatorial cards default · 6 smart filters · modal reutilizado · drop creator inline |
| D8 | Composición Home | 8 KPIs sparkline · 5 tiles accesos · 5-7 inbox cards · Cmd+K · atajos Vim |
| D9 | Cascarón Stock | 3 tabs (Drops · Calendario · Universo) · Calendario v0 placeholder |
| D10 | Cascarón Mystery | 3 tabs + Reglas modal (⚙) · 3 caminos al pool |
| D11 | Cascarón Site | 6 tabs (Páginas · Branding · Componentes · Comunicación · Comunidad · Meta+Tracking) · Membresías → Comercial · Code injection out v0 |
| D12 | Cascarón Sistema | 4 tabs (Status · Operaciones · Configuración · Audit) sin Acceso (ERP autentica) |
| D13 | Naming + ubicación | "Admin Web" · vive dentro del ERP Tauri local · sin subdomain · sin auth web · branding heredado del ERP |

---

## 11. Invariantes

- ERP Tauri es el destino final · NO referenciar Streamlit en este spec.
- Coexistencia con Comercial R1 — ambos viven en mismo App.svelte/Router pero subdir distinto.
- Audit existing UX (modal grande FM-style, atajos V/F/S, panel specs editable, BORRAR con preview) NO se rediseña — Admin Web la abraza, no la reemplaza.
- `published=true` flag sigue sagrado a nivel datos.
- Schema `audit_decisions` cambios requieren sincronizar con `elclub-catalogo-priv/data/catalog.json` por `family_id`.
- `wc2026-classified.json` sigue siendo source-of-truth de Mundial — no duplicar lista en código del ERP.
- Estética retro gaming + tipografía monospace para números/IDs + color tokens del ERP existente (Midnight Stadium dark).
- Sub-módulos del sidebar nivel 1 (de Admin Web) = 5 fijos. Home + 5 = 6 entries de navegación interna del módulo.
- No hay autenticación ni login dentro de Admin Web (la maneja el ERP).
- Branding heredado del ERP (no toggle interno, no variantes visuales propias).

---

## 12. Releases planificados

### R7 — Skeleton Admin Web + Vault profundo (10-15 días)

Build del cascarón completo del Admin Web con los 5 sub-módulos esqueleteados + Home funcional + **Vault con profundidad real** (las 4 tabs operativas). Stock/Mystery/Site/Sistema quedan como cascarones navegables con UI básico pero sin lógica completa.

**Plan detallado:** `el-club/overhaul/docs/superpowers/plans/2026-04-26-admin-web-r7-skeleton-plus-vault.md`

### R7.1 — Stock profundo (5-7 días)

Override model implementado · Drops con drop creator funcional · Calendario v1 visual (sin drag-drop drag aún) · Universo Stock con filtros · Bulk básico.

### R7.2 — Mystery profundo (5-7 días)

Pool funcional · Algoritmo de selección random ponderado básico · Anti-repeat · Modal Reglas funcional · Integración con wizard de checkout existente · Drops temáticos.

### R7.3 — Site profundo (10-14 días — el más grande)

Editor de bloques funcional · Branding live preview · Componentes core editables · Comunicación con templates + workflows básicos · Comunidad (reviews moderación) · Meta + Tracking básico.

### R7.4 — Sistema profundo (5-7 días)

Status dashboard live · Operaciones funcionales (scrap interface, deploys, backups) · Configuración con APIs lista + Bot config + Feature Flags · Audit log global.

### R7.5 — Polish + Power features (3-5 días)

Command Palette ⌘K · Atajos teclado Vim · Vistas guardadas funcionales · Bulk actions completos · URL state en todas las vistas · Mini-charts y sparklines · Animaciones sutiles.

---

## 13. Fuera de scope (este spec)

- Implementación de algoritmos backend de Mystery (random ponderado, fairness) — viene en R7.2.
- Integraciones avanzadas (A/B testing real, multi-idioma, loyalty/referrals UI funcionales) — v0.5+.
- Page versioning con rollback granular — v0.5+.
- Code injection per-page — descartado.
- Membresías / programas de loyalty — vive en Comercial.
- Page builder rico custom — v0.5+.
- Performance monitoring auto-remediation — v0.5+.
- Multi-environment (staging/prod) — v0.5+.

---

## 14. Mockups visuales

Ver carpeta `el-club/overhaul/.superpowers/brainstorm/{id}/content/`:

- `mockup-1-home.html` — Home del Admin Web (KPIs · Accesos · Inbox)
- `mockup-2-vault-universo.html` — Tab Universo con tabla densa, filtros, presets
- `mockup-3-stock-calendario.html` — Calendario de drops Stock visual

---

**Próximo paso:** Diego revisa este spec → si OK, plan R7 detallado se commitea + se lanza implementación post-Comercial R1 ship. Brainstorm cierra acá. Sesión de implementación arranca otro día.
