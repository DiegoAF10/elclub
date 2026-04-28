# Admin Web R7: Skeleton + Vault profundo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el módulo **Admin Web** completo dentro del ERP Tauri con: sidebar interno (Home + 5 sub-módulos), Home funcional con KPIs/Accesos/Inbox, Vault con sus 4 tabs operativas (Queue mantenido + Publicados + Grupos + Universo nuevos), modelo de datos extendido (estados + flags + overrides + tags), y cascarones navegables de Stock/Mystery/Site/Sistema con UI estructural pero lógica básica. Diego puede entrar al Admin Web, ver Home con eventos accionables, navegar Vault completo (incluyendo curaduría de tags y vista densa Universo), y abrir cualquier cascarón sin que se rompa la navegación.

**Architecture:** SvelteKit 5 (runes) + Tauri 2 (Rust backend) + SQLite local + Cloudflare Worker para webhooks/cron. Admin Web vive en `overhaul/src/routes/admin-web/` y `overhaul/src/lib/components/admin-web/`. Schema extendido con tablas nuevas (`tags`, `tag_types`, `jersey_tags`, `stock_overrides`, `mystery_overrides`, `inbox_events`, `site_pages`, `site_components`, `system_audit_log`). Reutiliza `audit_decisions` y `catalog.json` para Vault (no schema break, solo extensión).

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte icons
- Backend: Rust (Tauri commands), Python bridge para ops complejas (scrap, parse, pre-audit)
- Storage: SQLite (rusqlite) — `el-club/erp/elclub.db`
- Worker: Cloudflare Workers (TypeScript) — `ventus-system/backoffice/` para webhooks
- Verification: `npm run check` (svelte-check + tsc) + smoke test manual

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-26-admin-web-design.md`

**Branch:** `admin-web-r7`

**Versionado al completar:** ERP v0.1.X → v0.2.0 (minor bump por nuevo módulo grande)

**Pre-requisito de ship:** Comercial R1 ya merged y deployed (ambos módulos coexisten en mismo App.svelte/Router pero subdir disjuntos). Si Comercial R1 cambia patterns del sidebar/router, revalidar este plan.

---

## Patrón de testing en este codebase

El overhaul **no tiene framework de tests automatizados**. Patrón canonical (heredado de Audit y Comercial R1):

1. **TypeScript types como contract** — definir tipos antes que implementación.
2. **`npm run check`** debe pasar después de cada step de código (svelte-check + tsc).
3. **Smoke test manual** al final de cada task (abrir el ERP, hacer la acción, verificar).
4. **Build del MSI** como gate final del release.

Cada task adopta este flow:
- Definir types/contracts → check → implementar → check → smoke → commit.

---

## File Structure

### Archivos NUEVOS

```
overhaul/src/lib/components/admin-web/
├── AdminWebShell.svelte           # Container principal (sidebar interno + body)
├── AdminWebSidebar.svelte         # Sidebar con Home + 5 sub-módulos + badges
├── BreadcrumbBar.svelte           # Top breadcrumb (Admin Web > Vault > Queue, etc.)
├── home/
│   ├── HomeView.svelte            # Container del Home
│   ├── KpisGrid.svelte            # Grid 4×2 de KPIs con sparklines
│   ├── AccesosTiles.svelte        # 5 tiles de módulos
│   ├── InboxFeed.svelte           # Lista de eventos con buckets de prioridad
│   └── EventCard.svelte           # Card individual de evento
├── vault/
│   ├── VaultShell.svelte          # Container del módulo Vault con sus tabs
│   ├── tabs/
│   │   ├── QueueTab.svelte        # Wrapper sobre Audit existente
│   │   ├── PublicadosTab.svelte   # Cards curatoriales + smart filters
│   │   ├── GruposTab.svelte       # Lista de tags por tipo
│   │   └── UniversoTab.svelte     # Tabla densa + filtros + presets
│   ├── PublishedCard.svelte       # Card de jersey publicada
│   ├── TagsManager.svelte         # CRUD de tags adentro del tab Grupos
│   ├── UniversoTable.svelte       # Tabla densa con sort/filter/select
│   ├── UniversoFilters.svelte     # Sidebar de filtros de Universo
│   ├── UniversoPresets.svelte     # Vistas guardadas
│   ├── BulkActionBar.svelte       # Barra reactiva al multi-select
│   └── DropCreatorModal.svelte    # Mini-modal para promover a Stock/Mystery
├── stock/
│   ├── StockShell.svelte          # Container con 3 tabs (cascarón)
│   ├── tabs/
│   │   ├── DropsTab.svelte        # Cards de drops con smart filters
│   │   ├── CalendarioTab.svelte   # Timeline visual (placeholder funcional)
│   │   └── UniversoStockTab.svelte # Tabla densa solo overrides Stock
│   └── DropCard.svelte            # Card individual de drop
├── mystery/
│   ├── MysteryShell.svelte        # Container con 3 tabs + Reglas modal (cascarón)
│   ├── tabs/
│   │   ├── PoolTab.svelte         # Cards del pool actual
│   │   ├── CalendarioMysteryTab.svelte # Timeline drops temáticos
│   │   └── UniversoMysteryTab.svelte # Tabla densa overrides Mystery
│   └── ReglasModal.svelte         # Modal config algoritmo (UI persiste, lógica futura)
├── site/
│   ├── SiteShell.svelte           # Container con 6 tabs (cascarón)
│   ├── tabs/
│   │   ├── PaginasTab.svelte      # Lista páginas + sub-categorías
│   │   ├── BrandingTab.svelte     # Editor paleta+logo+fonts+modo
│   │   ├── ComponentesTab.svelte  # Lista componentes globales
│   │   ├── ComunicacionTab.svelte # Templates + workflows + lists
│   │   ├── ComunidadTab.svelte    # Reviews + encuestas + UGC
│   │   └── MetaTrackingTab.svelte # SEO + pixels + accessibility + audit
│   └── PageBlockEditor.svelte     # Block editor placeholder (funcional v0)
├── sistema/
│   ├── SistemaShell.svelte        # Container con 4 tabs (cascarón)
│   ├── tabs/
│   │   ├── StatusTab.svelte       # Dashboard health + activity feed
│   │   ├── OperacionesTab.svelte  # Scrap + deploys + jobs + backups + logs
│   │   ├── ConfiguracionTab.svelte # APIs + bot + locale + flags
│   │   └── AuditTab.svelte        # Audit log global + colaboradores futuros
│   └── ScrapInterface.svelte      # Comando "Scrap: <URL>" + historial
└── shared/
    ├── BaseModal.svelte           # Componente reusable de modal grande FM-style
    ├── SmartFilters.svelte        # Smart filter chips reutilizable
    ├── CardGrid.svelte            # Grid de cards con toggle a tabla
    └── CommandPalette.svelte      # ⌘K command palette global

overhaul/src/lib/data/
├── admin-web.ts                   # Types + helpers para Admin Web
├── jersey-states.ts               # Enum + transiciones de estados del jersey
├── tags.ts                        # Tag types + cardinalidad rules
├── overrides.ts                   # Stock + Mystery override schemas
├── inbox-events.ts                # Event types + priority + auto-dismiss rules
└── kpis-admin-web.ts              # Computa KPIs del Home (puro, testeable)

overhaul/src/routes/admin-web/
├── +page.svelte                   # Mount del AdminWebShell (default Home)
├── home/+page.svelte
├── vault/+page.svelte             # Default tab: Queue
├── vault/[tab]/+page.svelte       # Routing dinámico Queue/Publicados/Grupos/Universo
├── stock/+page.svelte
├── stock/[tab]/+page.svelte
├── mystery/+page.svelte
├── mystery/[tab]/+page.svelte
├── site/+page.svelte
├── site/[tab]/+page.svelte
├── sistema/+page.svelte
└── sistema/[tab]/+page.svelte
```

### Archivos a MODIFICAR

```
overhaul/src/lib/components/Sidebar.svelte    # Admin Web pasa de placeholder a navegable
overhaul/src/routes/+page.svelte              # Routing al modo Admin Web
overhaul/src/lib/adapter/types.ts             # Agregar types de tags, overrides, events
overhaul/src/lib/adapter/tauri.ts             # Agregar invocaciones para nuevos commands
overhaul/src/lib/adapter/browser.ts           # NotAvailableInBrowser para nuevos writes
overhaul/src-tauri/src/lib.rs                 # ~25 commands nuevos (CRUD tags, overrides, events, etc.)
overhaul/src-tauri/Cargo.toml                 # version bump
overhaul/src-tauri/tauri.conf.json            # version bump

el-club/erp/audit_db.py                       # Schema migration: 9 tablas nuevas
el-club/erp/scripts/erp_rust_bridge.py        # Bridge commands para nuevos ops
```

### Schema migration (audit_db.py)

```sql
-- Tags
CREATE TABLE tag_types (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  icon TEXT,
  cardinality TEXT NOT NULL CHECK (cardinality IN ('one', 'many')),
  conditional_rule TEXT,  -- JSON: {applies_when: {...}}
  display_order INTEGER
);

CREATE TABLE tags (
  id INTEGER PRIMARY KEY,
  type_id INTEGER NOT NULL REFERENCES tag_types(id),
  name TEXT NOT NULL,
  icon TEXT,
  color TEXT,
  is_auto_derived INTEGER NOT NULL DEFAULT 0,
  derivation_rule TEXT,  -- JSON for auto tags
  is_deleted INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER,
  UNIQUE(type_id, name)
);

CREATE TABLE jersey_tags (
  family_id TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES tags(id),
  assigned_at INTEGER NOT NULL,
  assigned_by TEXT,  -- 'manual' or 'auto:rule_id'
  PRIMARY KEY (family_id, tag_id)
);

-- Overrides
CREATE TABLE stock_overrides (
  id INTEGER PRIMARY KEY,
  family_id TEXT NOT NULL,
  publish_at INTEGER,
  unpublish_at INTEGER,
  price_override INTEGER,
  badge TEXT,
  copy_override TEXT,
  priority INTEGER NOT NULL DEFAULT 5,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE mystery_overrides (
  id INTEGER PRIMARY KEY,
  family_id TEXT NOT NULL,
  publish_at INTEGER,
  unpublish_at INTEGER,
  pool_weight REAL NOT NULL DEFAULT 1.0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Inbox events
CREATE TABLE inbox_events (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,  -- 'queue_pending', 'dirty_detected', 'drop_starting', etc.
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'important', 'info')),
  title TEXT NOT NULL,
  description TEXT,
  action_label TEXT,
  action_target TEXT,  -- route to navigate to
  created_at INTEGER NOT NULL,
  dismissed_at INTEGER,
  resolved_at INTEGER,
  metadata TEXT  -- JSON
);

-- Site (cascarón)
CREATE TABLE site_pages (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  category TEXT NOT NULL,  -- 'static', 'dynamic_seo', 'campaign', 'catalog', 'account', 'special'
  status TEXT NOT NULL CHECK (status IN ('draft', 'live', 'scheduled')),
  publish_at INTEGER,
  blocks TEXT,  -- JSON array of blocks
  seo_meta TEXT,  -- JSON
  updated_at INTEGER NOT NULL
);

CREATE TABLE site_components (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,  -- 'header', 'footer', 'banner_top', 'cookie_consent', etc.
  config TEXT NOT NULL,  -- JSON
  enabled INTEGER NOT NULL DEFAULT 1,
  publish_at INTEGER,
  unpublish_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE site_branding (
  key TEXT PRIMARY KEY,  -- 'palette', 'logo', 'fonts', 'mode', etc.
  value TEXT NOT NULL,  -- JSON
  updated_at INTEGER NOT NULL
);

-- Audit log
CREATE TABLE system_audit_log (
  id INTEGER PRIMARY KEY,
  timestamp INTEGER NOT NULL,
  user TEXT NOT NULL,
  module TEXT NOT NULL,  -- 'vault', 'stock', 'mystery', 'site', 'sistema'
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  diff TEXT,  -- JSON
  severity TEXT
);

-- Add ARCHIVED state support to existing audit_decisions
ALTER TABLE audit_decisions ADD COLUMN archived_at INTEGER;
ALTER TABLE audit_decisions ADD COLUMN dirty_flag INTEGER DEFAULT 0;
```

---

## Tasks

### Fase 1 — Skeleton del módulo + routing (días 1-2)

#### T1: Schema migration y types base
- [ ] Implementar 9 tablas nuevas en `audit_db.py:_ensure_schema()`
- [ ] Agregar `archived_at` y `dirty_flag` a `audit_decisions`
- [ ] Crear seed inicial de `tag_types` (10 tipos pre-definidos) + `tags` ejemplo (~50 tags)
- [ ] Definir TypeScript types en `overhaul/src/lib/data/admin-web.ts`, `jersey-states.ts`, `tags.ts`, `overrides.ts`, `inbox-events.ts`
- [ ] `npm run check` pasa
- [ ] Smoke: abrir SQLite browser y verificar tablas creadas con seed

#### T2: AdminWebShell + sidebar interno + routing base
- [ ] Crear `AdminWebShell.svelte` con sidebar interno (Home + 5 módulos)
- [ ] Crear `AdminWebSidebar.svelte` con badges reactivos (queue count, etc.)
- [ ] Crear `BreadcrumbBar.svelte` con auto-tracking del route
- [ ] Routing en `routes/admin-web/+page.svelte` (default Home) + sub-routes
- [ ] LocalStorage para persistir último módulo+tab abierto
- [ ] Update `Sidebar.svelte` global del ERP: Admin Web pasa de placeholder a navegable
- [ ] `npm run check` pasa
- [ ] Smoke: navegar entre los 5 módulos + Home, verificar breadcrumb actualiza

#### T3: Cascarones navegables de Stock/Mystery/Site/Sistema
- [ ] `StockShell.svelte` con 3 tabs vacíos (placeholders con texto "Drops" / "Calendario" / "Universo")
- [ ] `MysteryShell.svelte` con 3 tabs + icon ⚙ Reglas (modal vacío)
- [ ] `SiteShell.svelte` con 6 tabs vacíos (Páginas, Branding, Componentes, Comunicación, Comunidad, Meta+Tracking)
- [ ] `SistemaShell.svelte` con 4 tabs vacíos (Status, Operaciones, Configuración, Audit)
- [ ] Routing dinámico para cada tab (`stock/[tab]/+page.svelte`, etc.)
- [ ] `npm run check` pasa
- [ ] Smoke: entrar a cada cascarón, navegar tabs, verificar URL actualiza

### Fase 2 — Home funcional (día 3)

#### T4: KPIs grid + sparklines
- [ ] `KpisGrid.svelte` con 8 KPIs y mini-sparklines (datos mock OK por ahora)
- [ ] Tauri command `get_admin_web_kpis()` retorna JSON con valores reales
- [ ] Helper `kpis-admin-web.ts` computa KPIs desde DB (publ count, queue count, dirty count, etc.)
- [ ] Click en KPI → navegación al destino correcto
- [ ] `npm run check` pasa
- [ ] Smoke: abrir Home, ver 8 KPIs con números reales

#### T5: Accesos tiles
- [ ] `AccesosTiles.svelte` con 5 tiles + mini-stats reactivos
- [ ] Mini-stats vienen de Tauri command `get_module_stats(module: string)`
- [ ] Click en tile → entra al módulo
- [ ] `npm run check` pasa
- [ ] Smoke: ver tiles, click cada uno

#### T6: Inbox de eventos con buckets de prioridad
- [ ] `InboxFeed.svelte` + `EventCard.svelte` con 3 buckets de severidad (critical/important/info)
- [ ] Tauri commands: `list_inbox_events()`, `dismiss_event(id)`, `resolve_event(id)`
- [ ] Auto-dismiss rules en backend (cron worker o task on-demand)
- [ ] Click en `[ACCIÓN]` de cada card → navegación al target
- [ ] Botón "VER TODOS" → vista completa de Inbox (tab/modal)
- [ ] Detector inicial de eventos: queue_pending, dirty_detected, drop_starting (los demás vienen en R7.1+)
- [ ] `npm run check` pasa
- [ ] Smoke: insertar evento manual en DB, verificar aparece en Inbox, dismiss funciona

### Fase 3 — Vault: tabs Queue + Publicados (días 4-6)

#### T7: Vault Shell + tab Queue (mantener Audit existente)
- [ ] `VaultShell.svelte` con 4 tabs (Queue activo por default)
- [ ] `QueueTab.svelte` envuelve el Audit existente sin cambios (modal grande FM-style intacto)
- [ ] Reutilizar el modal de Audit de `overhaul/src/lib/components/audit/` existente
- [ ] Atajos V/F/S siguen funcionando dentro del tab
- [ ] `npm run check` pasa
- [ ] Smoke: entrar a Vault > Queue, audit funciona como hoy

#### T8: Tab Publicados con cards curatoriales
- [ ] `PublicadosTab.svelte` con grid de `PublishedCard.svelte`
- [ ] Smart filters al tope: Todas / Necesita atención / Recientes / SCHEDULED / Sin tags / Antiguas
- [ ] Cards con thumb grande, SKU, tags, override status, quick actions
- [ ] Tauri command `list_published(filter)` retorna jerseys filtradas
- [ ] Click thumb → reutilizar modal grande del Audit en "modo PUBLISHED" con set de acciones según estado
- [ ] Quick actions: PROMOVER (menú a Stock/Mystery) · ⚙ menú · 🗑 eliminar
- [ ] `DropCreatorModal.svelte` (mini-modal inline) para promover a Stock/Mystery
- [ ] `npm run check` pasa
- [ ] Smoke: entrar a Publicados, ver cards, click smart filter, abrir modal, promover a Stock con drop

### Fase 4 — Vault: Grupos (tags system) (días 7-9)

#### T9: Sistema de tags backend
- [ ] CRUD endpoints Tauri: `create_tag(type_id, name, ...)`, `update_tag(id, ...)`, `soft_delete_tag(id)`, `list_tags()`, `list_tag_types()`
- [ ] CRUD asignaciones: `assign_tag(family_id, tag_id)`, `remove_tag(family_id, tag_id)`, `list_jersey_tags(family_id)`, `list_jerseys_by_tag(tag_id)`
- [ ] Validación de cardinalidad: si tipo es 'one' y ya tiene tag, retornar error con prompt "¿reemplazar?"
- [ ] Validación condicional: si Tipo de Equipo = Selección, no permite Liga
- [ ] Sincronización bidireccional `meta_country` ↔ tag País
- [ ] `npm run check` pasa
- [ ] Smoke: crear tag, asignar a jersey, intentar violar cardinalidad → error

#### T10: Tab Grupos UI
- [ ] `GruposTab.svelte` muestra lista por tipo con badge de cardinalidad
- [ ] `TagsManager.svelte` con CRUD de tags (crear, renombrar, color, soft-delete)
- [ ] Click en tag `[VER]` → drill a vista del grupo (lista de jerseys + drag-drop add/remove)
- [ ] Click `[+ NEW]` por tipo → modal crear tag
- [ ] Click `[⚙]` → editar tag (nombre, color, icono, toggle auto-derivado)
- [ ] `npm run check` pasa
- [ ] Smoke: ver tipos, crear tag nuevo, asignar a jerseys, ver drill

### Fase 5 — Vault: Universo (vista densa) (días 10-12)

#### T11: UniversoTable con filtros + sort + columnas
- [ ] `UniversoTable.svelte` con tabla densa (~50px rows, monospace tabular)
- [ ] `UniversoFilters.svelte` con filtros agrupados (Estado, Flags, Producto, Tags por tipo, Coverage, Última acción)
- [ ] Filtros AND entre secciones, OR dentro
- [ ] Counts reactivos en cada filtro
- [ ] Sort por header click (asc/desc)
- [ ] Right-click header → menú toggle visibility de columnas
- [ ] Drag-drop columnas para reordenar
- [ ] Tauri command `list_universo(filters, sort, pagination)` con server-side filtering
- [ ] `npm run check` pasa
- [ ] Smoke: aplicar filtros combinados, sort, toggle columnas

#### T12: Vistas guardadas + URL state
- [ ] `UniversoPresets.svelte` con vistas guardadas (presets fábrica + custom de Diego)
- [ ] Tauri commands: `list_presets()`, `save_preset(name, filters, sort, columns)`, `delete_preset(id)`
- [ ] URL state: filtros + sort + columnas se serializan a query string
- [ ] Compartir URL → restaura vista exacta
- [ ] Presets fábrica seed: Default, Queue del día, Publicados con foto rota, Retros sin Era, Drops próximos 7d, DRAFT con scrap_fail
- [ ] `npm run check` pasa
- [ ] Smoke: crear preset, recargar página → vista restaura desde URL

#### T13: Toggle vista tabla/grid + bulk actions
- [ ] Toggle button cambia entre tabla densa y grid de cards (persiste en localStorage)
- [ ] `BulkActionBar.svelte` aparece al multi-select (checkbox cell)
- [ ] Bulk actions v0: tag bulk, archivar bulk, re-fetch bulk
- [ ] Tauri commands para cada bulk action
- [ ] Confirmación con preview antes de ejecutar bulk destructivo
- [ ] `npm run check` pasa
- [ ] Smoke: seleccionar 3 jerseys, asignar tag bulk, verificar resultado

### Fase 6 — Power features cross-Admin Web (días 13-14)

#### T14: Command Palette (⌘K)
- [ ] `CommandPalette.svelte` con overlay + búsqueda fuzzy
- [ ] Atajo global ⌘K abre palette desde cualquier vista del Admin Web
- [ ] Acciones disponibles: navegar a módulo+tab, buscar jersey por SKU, crear tag, programar drop, scrap nueva categoría, etc.
- [ ] Búsqueda fuzzy con `fuse.js` o similar
- [ ] `npm run check` pasa
- [ ] Smoke: abrir ⌘K, escribir "ARG", aparece jersey + opciones

#### T15: Atajos teclado Vim-style
- [ ] Atajos globales: `g h` Home, `g v` Vault, `g s` Stock, `g m` Mystery, `g w` Site, `g c` Sistema (config)
- [ ] Atajo `n` (Vault > Queue): jump al next jersey de la queue
- [ ] Atajo `?` muestra modal con todos los atajos disponibles
- [ ] Display de atajos en hover de items del sidebar (tooltip)
- [ ] `npm run check` pasa
- [ ] Smoke: usar todos los atajos

#### T16: Audit log global del Admin Web
- [ ] Trigger en cada mutation (crear/editar/borrar tag, override, evento, etc.) → escribe a `system_audit_log`
- [ ] `AuditTab.svelte` (Sistema > Audit) muestra log con filtros (fecha, usuario, módulo, severity)
- [ ] Export CSV
- [ ] `npm run check` pasa
- [ ] Smoke: hacer 5 cambios, verificar aparecen en audit log con diff correcto

### Fase 7 — Polish + ship (día 15)

#### T17: Sparklines y mini-charts en KPIs
- [ ] Implementar sparklines reales (no mock) usando histórico de la DB
- [ ] Cron de snapshot diario para histórico de KPIs (worker)
- [ ] `npm run check` pasa
- [ ] Smoke: ver sparklines con data real de los últimos 7 días

#### T18: Branding heredado del ERP + Admin Web header
- [ ] Verificar que Admin Web hereda paleta del ERP (Midnight Stadium dark)
- [ ] Header del módulo dice "Admin Web" + breadcrumbs visibles
- [ ] Sin variantes visuales propias (consistencia con resto del ERP)
- [ ] `npm run check` pasa
- [ ] Smoke: comparar visualmente con Comercial — mismo look

#### T19: Verification + version bump + build MSI
- [ ] Run `npm run check` final — todo pasa
- [ ] Smoke test completo end-to-end:
  - [ ] Abrir ERP → Admin Web → Home con KPIs reales
  - [ ] Navegar a Vault > Queue → audit funciona como antes
  - [ ] Vault > Publicados → ver cards, abrir modal, promover a Stock
  - [ ] Vault > Grupos → crear tag, asignar
  - [ ] Vault > Universo → filtros, presets, bulk
  - [ ] Stock/Mystery/Site/Sistema → cascarones navegables sin error
  - [ ] ⌘K command palette funciona
  - [ ] Atajos teclado funcionan
- [ ] Bump version `Cargo.toml` + `tauri.conf.json` (v0.1.X → v0.2.0)
- [ ] Build MSI: `npm run tauri build`
- [ ] Crear release notes
- [ ] Commit final + tag

---

## Acceptance criteria (cierre R7)

- [ ] Admin Web es navegable desde el sidebar global del ERP.
- [ ] Home muestra KPIs reales, accesos a 5 módulos, e Inbox con eventos detectados.
- [ ] Vault tiene 4 tabs operativas: Queue (Audit existente intacto), Publicados (cards + filtros + modal), Grupos (CRUD tags), Universo (tabla densa + filtros + presets + bulk).
- [ ] Stock/Mystery/Site/Sistema son navegables como cascarones (UI estructural sin lógica completa, no rompen).
- [ ] Modelo de datos extendido: 9 tablas nuevas + 2 columnas nuevas en `audit_decisions`.
- [ ] Command Palette ⌘K + atajos teclado Vim funcionan.
- [ ] Audit log captura mutations.
- [ ] `npm run check` pasa sin errores.
- [ ] MSI build OK + smoke test end-to-end pasa.
- [ ] Comercial R1 sigue funcionando sin regresiones.

---

## Out of scope (R7) — viene después

- Stock profundo (override engine + drop conflicts + templates) → R7.1
- Mystery algoritmos reales (random ponderado, anti-repeat, fairness) → R7.2
- Site editor de bloques rico + A/B testing + multi-idioma → R7.3
- Sistema deploys funcionales + auto-remediation + cost tracking → R7.4
- Polish final (animaciones, micro-interactions) → R7.5
- Implementación de tags auto-derivados (algoritmo) → R7.1
- Reglas Mystery condicionales con cross-tipo validation avanzada → R7.2
- Page versioning + rollback granular → R7.3
- Performance monitoring auto + alerts → R7.4

---

**Pre-flight checklist antes de arrancar R7:**

1. ✅ Comercial R1 mergeado y deployed
2. ✅ Spec aprobado: `el-club/overhaul/docs/superpowers/specs/2026-04-26-admin-web-design.md`
3. ✅ Mockups visualizados con Diego: `el-club/overhaul/.superpowers/brainstorm/508-1777229441/content/`
4. ✅ Branch creado: `git checkout -b admin-web-r7`
5. ✅ Schema migration testeada en DB local antes de tocar producción
6. ✅ Backup de `elclub.db` antes de arrancar T1
7. ✅ Heads-up a Strategy: cross-bucket Admin Web arranca, posibles cambios de schema en `audit_decisions`
