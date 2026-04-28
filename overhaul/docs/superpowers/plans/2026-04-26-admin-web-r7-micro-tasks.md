# Admin Web R7 — Plan con micro-tasks

> **Versión micro-tasks** del plan principal `2026-04-26-admin-web-r7-skeleton-plus-vault.md`. Subdivide cada T en sub-T de 15-30 min. El dev no pierde tiempo decidiendo orden ni scope — solo ejecuta.

**Goal:** Mismo que el plan principal — skeleton completo del Admin Web + Vault profundo. La diferencia es **granularidad** para que la implementación sea casi mecánica.

**Pre-requisitos:**
- ✅ Comercial R1 mergeado y deployed
- ✅ `el-club/overhaul/docs/superpowers/specs/2026-04-26-admin-web-design.md` aprobado
- ✅ `el-club/overhaul/docs/superpowers/specs/admin-web/schema-migration.sql` revisado
- ✅ `el-club/overhaul/docs/superpowers/specs/admin-web/types.ts` revisado
- ✅ `el-club/overhaul/docs/superpowers/specs/admin-web/tags-seed.json` revisado
- ✅ `el-club/overhaul/docs/superpowers/specs/admin-web/inbox-events-catalog.json` revisado
- ✅ Backup pre-flight: `cp el-club/erp/elclub.db el-club/erp/elclub.backup-before-admin-web-r7.db`

**Branch:** `git checkout -b admin-web-r7`

---

## FASE 1 — Schema + Types base (día 1, ~6h)

### T1.1 — DB Migration (~30 min) ✅ commit 18dfb57
- [x] Cargar `schema-migration.sql` y validar idempotencia con DB de prueba
- [x] Adaptar a `audit_db.py:init_audit_schema()` (NO `_ensure_schema()` — el nombre real en codebase) reproduciendo cada `CREATE TABLE IF NOT EXISTS`
- [x] Wrapping de los `ALTER TABLE` de `audit_decisions` con check de columna previo (SQLite no soporta `IF NOT EXISTS`)
- [x] Ejecutar manualmente sobre `elclub.db` real
- [x] Verify: `.tables` muestra **26** tablas nuevas (no 18 como decía el spec; el conteo real fue mayor) + las existentes. Total post-migration: 57 tables, 12 views.
- [x] Verify: `PRAGMA table_info(audit_decisions)` muestra `archived_at`, `dirty_flag`, `dirty_reason`, `dirty_detected_at` ✓
- [x] Idempotencia probada: 2da ejecución no errored
- [x] Vista `v_jersey_state` devuelve 520 rows reales clasificadas

### T1.2 — Seed inicial (~20 min) ✅ commit f2e1ede
- [x] Cargar `tags-seed.json` y crear `seed_admin_web.py` que itera tag_types primero, después tags por type_slug
- [x] Insertar también seed factory de `saved_views` para `vault.universo` (los 7 presets pedidos)
- [x] Insertar seed inicial de `scheduled_jobs` (detect-inbox-events hourly, kpi-snapshot daily, dirty-detector every 4h)
- [x] Insertar seed inicial de `site_components` con configs default (header, footer, banner_top off, cookie_consent on)
- [x] Verify: `SELECT COUNT(*) FROM tags` → **122** (NO 110 como decía el spec; el _meta del JSON estaba desactualizado, los datos del archivo son consistentes con sí mismos a 122)
- [x] Idempotencia probada: 2da ejecución insertó 0 filas en todas las tablas

### T1.3 — TypeScript types (~30 min) ✅ commit f5fac6b
- [x] Copiar `specs/admin-web/types.ts` a 5 archivos:
  - `overhaul/src/lib/data/admin-web.ts` (HomeKpis, KpiSnapshot, SavedView, all Site types, all Sistema types, HealthSnapshot, CommandPalette, UniversoFilters, etc.)
  - `overhaul/src/lib/data/jersey-states.ts` (JerseyState, VALID_TRANSITIONS, canTransition, JerseyFlags, Jersey, JerseyModelo)
  - `overhaul/src/lib/data/tags.ts` (TagCardinality, TagTypeSlug, ConditionalRule, TagType, Tag, AutoDerivationRule, JerseyTag, TagAssignmentValidation)
  - `overhaul/src/lib/data/overrides.ts` (OverrideStatus, StockOverride, MysteryOverride)
  - `overhaul/src/lib/data/inbox-events.ts` (ModuleSlug, EventSeverity, EventType, InboxEvent, AUTO_DISMISS_DAYS) — NOTA: ModuleSlug se mudó acá desde admin-web.ts para preservar dirección única de imports y evitar ciclo (admin-web.ts ← inbox-events.ts)
- [x] Extender `overhaul/src/lib/adapter/types.ts` agregando AdminWebTauriCommands interface (60+ commands)
- [x] `npm run check` pasa con 0 errors (37 warnings pre-existentes a11y en componentes no relacionados)
- [ ] ~~Smoke: `import { JerseyState } from '$lib/data/jersey-states'` desde un componente test~~ — implícito: svelte-check valida grafo completo y pasó

### T1.4 — Adapter scaffolding (~45 min) ✅ commit e0e511d
- [x] Agregar a `overhaul/src/lib/adapter/tauri.ts` funciones wrapper para los 60+ commands de `AdminWebTauriCommands` (object literal `adminWebTauri`)
- [x] Cada wrapper: `(args) => invoke<T>('command_name', args)` — formato compacto. `args ?? {}` para opcionales (evita `undefined` que algunos handlers Rust no toleran)
- [x] Por ahora son stubs — la implementación Rust viene en T2.X+. Tauri devuelve UNHANDLED si se invocan ahora.
- [x] Agregar a `overhaul/src/lib/adapter/browser.ts` stubs degradados (reads → arrays/objects vacíos para que las shells rendericen, writes → `NotAvailableInBrowser`)
- [x] Wire up `adminWeb` Proxy en `lib/adapter/index.ts` con el mismo patrón lazy-init
- [x] `npm run check` pasa con 0 errors

---

## FASE 2 — AdminWebShell + sidebar interno + routing (día 2, ~5h)

### T2.1 — File structure scaffolding (~15 min)
- [ ] `mkdir -p overhaul/src/lib/components/admin-web/{home,vault,stock,mystery,site,sistema,shared}`
- [ ] `mkdir -p overhaul/src/lib/components/admin-web/{vault,stock,mystery,site,sistema}/tabs`
- [ ] `mkdir -p overhaul/src/routes/admin-web/{home,vault,stock,mystery,site,sistema}`
- [ ] `mkdir -p overhaul/src/routes/admin-web/{vault,stock,mystery,site,sistema}/[tab]`
- [ ] Crear archivos vacíos con placeholder comment `<!-- TODO: T2.X -->`

### T2.2 — AdminWebShell.svelte (~45 min)
- [ ] Container que orquesta sidebar interno + body
- [ ] Layout: flex con `AdminWebSidebar` width 200px + body flex-1
- [ ] Slot `{children}` para el route activo
- [ ] State: `currentModule` derivado del route
- [ ] LocalStorage: persiste último `currentModule` + `currentTab` por module
- [x] `npm run check` pasa

### T2.3 — AdminWebSidebar.svelte (~45 min)
- [ ] Sidebar con sections "Admin Web" + lista de items (Home + 5 módulos)
- [ ] Cada item: icon + nombre + badge reactivo
- [ ] Badge fuente: `inbox_events` count por módulo (Tauri command `get_inbox_counts_per_module`)
- [ ] Active state según route
- [ ] Click navega via `goto('/admin-web/${slug}')`
- [x] `npm run check` pasa

### T2.4 — BreadcrumbBar.svelte (~30 min)
- [ ] Top breadcrumb auto-tracking del route
- [ ] Formato: `Admin Web > {Module} > {Tab}` con separadores `›`
- [ ] Cada segmento clickeable (sube nivel)
- [x] `npm run check` pasa

### T2.5 — Routing root (~45 min)
- [ ] `routes/admin-web/+page.svelte` redirige a `/admin-web/home`
- [ ] `routes/admin-web/+layout.svelte` mounts AdminWebShell + slot `{children}`
- [ ] Sub-routes para cada módulo: `vault/+page.svelte`, `stock/+page.svelte`, etc.
- [ ] Tab routing dinámico: `vault/[tab]/+page.svelte` con switch interno
- [ ] LocalStorage sync con route changes
- [x] `npm run check` pasa
- [ ] Smoke: navegar entre los 5 módulos, breadcrumb actualiza, recarga restaura último

### T2.6 — Sidebar global (Sidebar.svelte) — wire Admin Web (~30 min)
- [ ] Convertir item "Admin Web" de placeholder a navegable (link a `/admin-web`)
- [ ] Mantener Comercial intacto (no tocar)
- [x] `npm run check` pasa
- [ ] Smoke: desde Comercial navegar a Admin Web y volver

### T2.7 — Cascarones de Stock/Mystery/Site/Sistema (~60 min)
- [ ] StockShell.svelte con header + 3 tabs (Drops · Calendario · Universo) cada uno con placeholder text
- [ ] MysteryShell.svelte con header + icon ⚙ Reglas + 3 tabs (Pool · Calendario · Universo) placeholders
- [ ] SiteShell.svelte con header + 6 tabs (Páginas · Branding · Componentes · Comunicación · Comunidad · Meta+Tracking) placeholders
- [ ] SistemaShell.svelte con header + 4 tabs (Status · Operaciones · Configuración · Audit) placeholders
- [ ] Cada Shell maneja su tab state via prop + URL sync
- [x] `npm run check` pasa
- [ ] Smoke: entrar a cada cascarón, navegar tabs, URL actualiza

---

## FASE 3 — Home funcional (día 3, ~6h)

### T3.1 — Tauri commands para Home (~45 min)
- [ ] Implementar en Rust (`src-tauri/src/lib.rs`):
  - `get_admin_web_kpis()` → consulta KPIs de catalog.json + audit_decisions + stock_overrides + etc.
  - `get_module_stats(module)` → mini-stats por módulo
  - `list_inbox_events(filter)` → eventos no-dismissed
  - `dismiss_event(id)` → set dismissed_at
  - `resolve_event(id)` → set resolved_at
- [ ] Bridge en Python (`erp_rust_bridge.py`) para los queries SQL complejos
- [ ] Testear cada uno con `cargo test` o invoke manual
- [x] `npm run check` pasa

### T3.2 — KpisGrid.svelte (~45 min)
- [ ] Grid 4×2 con 8 KPIs según mockup-1-home.html
- [ ] Cada KPI usa `KpiCard.svelte` (icon, value, label, sparkline)
- [ ] Sparkline: lee de `kpi_snapshots` últimos 7 días, render con SVG simple
- [ ] Click en KPI → `goto(target_route)` (cada KPI tiene su drill)
- [x] `npm run check` pasa
- [ ] Smoke: ver Home, KPIs cargan con números reales

### T3.3 — AccesosTiles.svelte (~30 min)
- [ ] 5 tiles uniformes con icon + nombre + 2 mini-stats
- [ ] Mini-stats reactivos via `get_module_stats(module)`
- [ ] Click tile → entra al módulo (default tab)
- [ ] Hover effect (border verde + box-shadow glow)
- [x] `npm run check` pasa

### T3.4 — InboxFeed.svelte + EventCard.svelte (~60 min)
- [ ] InboxFeed: lista vertical con 5-7 eventos visibles
- [ ] Sort: priority (critical first) > recencia
- [ ] EventCard: border-left color según severity
- [ ] Action button → `goto(event.action_target)`
- [ ] Dismiss button (X en hover) → `dismiss_event(id)` + remove de lista (optimistic update)
- [ ] Footer "VER TODOS (N)" → tab modal/route con todos los eventos
- [ ] Auto-refresh cada 60s
- [x] `npm run check` pasa

### T3.5 — Detector de eventos (~75 min)
- [ ] Cron handler en worker o Rust local: corre cada hora
- [ ] Para cada `EventType`, ejecuta query de detección (ver `inbox-events-catalog.json`)
- [ ] Insert nuevo event si: query devuelve resultado AND no existe event no-dismissed del mismo type+entity
- [ ] Resolve eventos cuando query no detecta (ej. queue_pending se resolve cuando queue=0)
- [ ] Auto-expire según AUTO_DISMISS_DAYS
- [ ] Schedule en `scheduled_jobs` con cron `0 * * * *`
- [ ] Smoke: insertar 12 jerseys en queue manualmente → cron detecta → evento `queue_pending` aparece

### T3.6 — HomeView.svelte assembly (~30 min)
- [ ] Orquesta KpisGrid + AccesosTiles + InboxFeed
- [ ] Page header "HOME" + datetime
- [ ] Loading states con skeleton placeholders
- [x] `npm run check` pasa
- [ ] Smoke: abrir Home, todo carga, datos reales, click eventos funciona

---

## FASE 4 — Vault: Queue + Publicados (días 4-5, ~12h)

### T4.1 — VaultShell.svelte con tabs (~30 min)
- [ ] Container Vault con 4 tabs (Queue activo default)
- [ ] Tab routing via `[tab]` param
- [ ] Header con count badges
- [x] `npm run check` pasa

### T4.2 — QueueTab.svelte (~45 min)
- [ ] Wrap del Audit existente sin cambios
- [ ] Reutilizar el modal grande FM-style de `overhaul/src/lib/components/audit/`
- [ ] Atajos V/F/S siguen funcionando
- [ ] List view a la izquierda + detail (audit modal) inline a la derecha
- [x] `npm run check` pasa
- [ ] Smoke: Vault > Queue funciona como hoy

### T4.3 — Tauri commands de Vault Publicados (~45 min)
- [ ] `list_published(filter, pagination)` → 6 filters: all, attention, recent, scheduled, no_tags, old
- [ ] `toggle_dirty_flag(family_id, dirty, reason)`
- [ ] `archive_jersey(family_id)` → set archived_at
- [ ] `revive_archived(family_id, scheduled_at?)`
- [x] `npm run check` pasa

### T4.4 — PublicadosTab.svelte estructura (~45 min)
- [ ] Smart filters chips arriba
- [ ] Cards toolbar (toggle vista, sort, columnas)
- [ ] CardGrid con `PublishedCard.svelte`
- [ ] Loading + empty states
- [x] `npm run check` pasa

### T4.5 — PublishedCard.svelte (~60 min)
- [ ] Card según mockup-5-vault-publicados.html
- [ ] Thumb grande + badges (DIRTY, SCHEDULED, FEATURED)
- [ ] SKU + team + tags icons + override status + coverage
- [ ] 3 quick actions: PROMOVER (menú), ⚙ menú, 🗑 eliminar
- [ ] Click thumb → abrir modal grande (mismo del Audit, modo PUBLISHED)
- [x] `npm run check` pasa

### T4.6 — Modal grande extension para PUBLISHED state (~75 min)
- [ ] Reutilizar Audit modal, agregar variante para state=PUBLISHED
- [ ] Set de acciones según estado (ver tabla en spec)
- [ ] Botones: Promover Stock, Promover Mystery, Toggle dirty, Re-fetch, Despublicar temp, Archivar, Eliminar
- [ ] Header con badge de estado correcto
- [x] `npm run check` pasa

### T4.7 — DropCreatorModal.svelte (~75 min)
- [ ] Mini-modal inline con form para Stock/Mystery override
- [ ] Fields: producto target (Stock o Mystery o both), publish_at (date+time), unpublish_at (opt), price_override, badge, copy_override, priority
- [ ] Validación cliente (publish_at < unpublish_at, price > 0)
- [ ] Submit → Tauri `promote_to_stock` o `promote_to_mystery`
- [ ] Success → cerrar modal + actualizar card override status
- [x] `npm run check` pasa
- [ ] Smoke: promover una jersey a Stock con drop programado

### T4.8 — Smart filters lógica (~30 min)
- [ ] 6 filters: Todas, Atención, Recientes, Scheduled, Sin tags, Antiguas
- [ ] Cada filter aplica su SQL query específico
- [ ] Counts reactivos arriba de cada chip
- [ ] URL state: `?filter=attention`
- [x] `npm run check` pasa

### T4.9 — Toggle vista Cards/Tabla (~45 min)
- [ ] Toggle button cambia entre grid de cards y tabla densa
- [ ] LocalStorage persiste preferencia
- [ ] Tabla densa reutiliza lógica de UniversoTable (más adelante en T6.2)
- [x] `npm run check` pasa

---

## FASE 5 — Vault: Grupos (sistema de tags) (días 6-7, ~12h)

### T5.1 — Tauri commands de Tags (~75 min)
- [ ] `list_tag_types()` → lee `tag_types`
- [ ] `list_tags(filter)` → lee `tags` con count de uso (LEFT JOIN jersey_tags + GROUP BY)
- [ ] `create_tag(args)` → INSERT con validación de slug único por type
- [ ] `update_tag(id, updates)` → UPDATE
- [ ] `soft_delete_tag(id)` → SET is_deleted=1
- [x] `npm run check` pasa

### T5.2 — Tauri commands de Asignación (~75 min)
- [ ] `list_jersey_tags(family_id)` → lee jersey_tags JOIN tags
- [ ] `list_jerseys_by_tag(tag_id, pagination)`
- [ ] `validate_tag_assignment(family_id, tag_id)` → check cardinalidad + condicionales
- [ ] `assign_tag(family_id, tag_id, force_replace?)` → INSERT, si conflicto cardinality y force_replace=true entonces DELETE conflicting + INSERT
- [ ] `remove_tag(family_id, tag_id)` → DELETE
- [ ] Validación condicional cross-tipo: SQL helper que evalúa rules
- [x] `npm run check` pasa
- [ ] Smoke: violar cardinalidad → recibir conflict response con `conflicting_tags`

### T5.3 — Sincronización País ↔ meta_country (~45 min)
- [ ] Trigger SQL: cuando se asigna tag tipo `pais`, escribir `catalog.json:meta_country`
- [ ] Reverse: cuando script de scrap escribe meta_country, asignar tag País correspondiente automáticamente
- [ ] Tauri command `sync_country_tags()` para reconciliación batch
- [x] `npm run check` pasa

### T5.4 — GruposTab.svelte estructura (~30 min)
- [ ] Container con lista de tipos según mockup-6-vault-grupos.html
- [ ] Renderiza secciones por tipo con TagsSection.svelte
- [ ] Loading + empty state
- [x] `npm run check` pasa

### T5.5 — TagsSection.svelte (~45 min)
- [ ] Una sección por tipo: header con icon + nombre + cardinality badge + new btn
- [ ] Lista de tags del tipo en grid
- [x] `npm run check` pasa

### T5.6 — TagRow.svelte (~30 min)
- [ ] Row con icon + name + count + actions (VER, ⚙)
- [ ] Auto-derived mark si aplica
- [x] `npm run check` pasa

### T5.7 — Modal Crear/Editar Tag (~60 min)
- [ ] Form: name, slug (auto-generado), icon (selector emoji), color (hex picker), is_auto_derived (toggle)
- [ ] Si auto_derived: form adicional para `derivation_rule` (type + config)
- [ ] Submit → create_tag o update_tag
- [x] `npm run check` pasa

### T5.8 — Drill view del tag (modal o route) (~75 min)
- [ ] Click [VER] en un tag abre modal o navega a `/admin-web/vault/grupos/[tag_slug]`
- [ ] Lista de jerseys del tag con thumb + sku + team
- [ ] Drag-drop para reordenar (display_order del jersey en el tag) — v0.5 si pesado
- [ ] Botón "+ AGREGAR JERSEYS" abre selector con búsqueda
- [ ] Click thumbnail → modal grande del jersey
- [x] `npm run check` pasa

---

## FASE 6 — Vault: Universo (vista densa power-user) (días 8-10, ~18h)

### T6.1 — Tauri commands de Universo (~90 min)
- [ ] `list_universo(filters, sort, pagination)`:
  - Construye query dinámica con WHERE según filters
  - JOIN tags, overrides para datos derivados
  - ORDER BY según sort
  - LIMIT + OFFSET
  - SELECT también el COUNT total para pagination
- [ ] `list_universo_filter_counts(current_filters)` → counts reactivos para sidebar
- [ ] Performance: indexes ya creados en migration (idx_audit_status, idx_audit_dirty)
- [ ] Test con dataset de 1000+ jerseys, query bajo 100ms
- [x] `npm run check` pasa

### T6.2 — UniversoTable.svelte densa (~120 min)
- [ ] Header sticky con sort indicators
- [ ] Rows ~50px alto con thumbnail visible 40×55px
- [ ] Columnas según mockup-2-vault-universo.html
- [ ] Right-click header → menú toggle visibility
- [ ] Drag-drop para reordenar columnas (use `svelte-dnd-action` o similar)
- [ ] Multi-select con checkbox
- [ ] Hover row efecto + click row navega/abre modal
- [ ] Virtualization si >100 rows (svelte-virtual o similar)
- [x] `npm run check` pasa

### T6.3 — UniversoFilters.svelte sidebar (~75 min)
- [ ] Filter sections: Estado, Flags, Producto, Tags por tipo (10 sub-secciones), Coverage slider, Última acción
- [ ] Cada filter checkbox/radio con count reactivo al lado
- [ ] AND entre secciones, OR dentro
- [ ] "Limpiar filtros" button
- [ ] State sincronizado con URL query string
- [x] `npm run check` pasa

### T6.4 — UniversoPresets.svelte (~60 min)
- [ ] Lista de presets debajo de filters
- [ ] Botón "➕ NUEVA VISTA" abre modal: name, icon, current state como base
- [ ] Click preset aplica filters + sort + columns
- [ ] Right-click preset → menú edit/delete
- [ ] Highlight preset activo
- [x] `npm run check` pasa

### T6.5 — Toolbar superior (~30 min)
- [ ] Toggle Tabla/Grid + view-toggle button
- [ ] Info: "Mostrando X de Y · sort: COL ↓"
- [ ] Botones: Export CSV, Compartir vista, Configurar columnas
- [x] `npm run check` pasa

### T6.6 — BulkActionBar.svelte reactiva (~75 min)
- [ ] Aparece slide-up cuando hay multi-select
- [ ] Acciones según selection: + TAG, + GRUPO, PROMOVER STOCK, PROMOVER MYSTERY, RE-FETCH, ARCHIVAR, ELIMINAR
- [ ] Cada acción abre confirm dialog si destructivo
- [ ] Tauri `bulk_action(family_ids, action, payload)` ejecuta
- [ ] Progress bar si > 50 items
- [x] `npm run check` pasa
- [ ] Smoke: seleccionar 5 jerseys, asignar tag bulk, verify aplicado

### T6.7 — URL state full sync (~45 min)
- [ ] Filters + sort + columns serializados a query string compacto
- [ ] Restore on mount: parsea URL → aplica state
- [ ] Compartir URL → vista exacta
- [x] `npm run check` pasa
- [ ] Smoke: aplicar filtros, copiar URL, abrir incógnito → vista igual

### T6.8 — Export CSV (~30 min)
- [ ] Tauri command `export_universo_csv(filters)` → genera CSV en disco
- [ ] Download trigger (Tauri dialog)
- [ ] Notification on success
- [x] `npm run check` pasa

---

## FASE 7 — Power features cross-Admin Web (días 11-12, ~10h)

### T7.1 — CommandPalette.svelte (~120 min)
- [ ] Overlay modal con backdrop blur
- [ ] Atajo global ⌘K abre desde cualquier route del Admin Web
- [ ] Input con auto-focus
- [ ] Lista de items con fuzzy search (use `fuse.js`)
- [ ] Categorías: Navigation, Action, Search, Config
- [ ] Items navegación: ir a Home/Vault/Stock/Mystery/Site/Sistema
- [ ] Items acción: Crear tag, Programar drop, Toggle dirty, Re-fetch all
- [ ] Items search: jersey por SKU/team
- [ ] Keyboard nav (↑↓, Enter)
- [x] `npm run check` pasa
- [ ] Smoke: ⌘K, escribir "ARG", aparece jersey + acciones

### T7.2 — Atajos teclado Vim-style (~60 min)
- [ ] Hook global de keydown
- [ ] Atajos: `g h` Home, `g v` Vault, `g s` Stock, `g m` Mystery, `g w` Site, `g c` Sistema
- [ ] `n` (en Vault > Queue): jump al next jersey de queue
- [ ] `?` muestra modal con todos los atajos
- [ ] `Escape` cierra modal palette/cualquier overlay
- [ ] Excluir cuando focus en input/textarea
- [x] `npm run check` pasa
- [ ] Smoke: usar atajos en cada vista

### T7.3 — Audit log automático (~75 min)
- [ ] Hook en cada Tauri write command que llama `write_audit_log(entry)`
- [ ] Entry: timestamp, user='diego', module, action, entity_type, entity_id, diff (before/after JSON)
- [ ] Severity automático: 'critical' si delete/archive, 'warning' si bulk, 'info' default
- [ ] AuditTab.svelte (Sistema > Audit) muestra log con filters (fecha, módulo, severity)
- [ ] Export CSV
- [x] `npm run check` pasa
- [ ] Smoke: hacer 5 cambios, ver appear en audit log con diff correcto

### T7.4 — Notifications config + thresholds (~45 min)
- [ ] Modal config para `notifications.threshold` per severity
- [ ] Canales: Telegram (Diego), email
- [ ] Quiet hours setter
- [ ] Persiste a `admin_web_config` table
- [x] `npm run check` pasa

---

## FASE 8 — Polish + ship (días 13-15, ~8h)

### T8.1 — Sparklines reales (no mock) (~45 min)
- [ ] Cron `kpi-snapshot-daily` ya creado en T1.2 — verifica que corre
- [ ] KpisGrid usa `kpi_snapshots` últimos 7 días
- [ ] Si hay <7 días de data, fallback a placeholder text
- [x] `npm run check` pasa

### T8.2 — Loading states + error boundaries (~60 min)
- [ ] Skeleton placeholders en cada vista grande
- [ ] Error boundary component que muestra retry button
- [ ] Toast notifications para success/error de Tauri commands
- [x] `npm run check` pasa

### T8.3 — Branding heredado del ERP (~20 min)
- [ ] Verify visualmente: Admin Web usa misma paleta que Comercial
- [ ] Header del módulo dice "Admin Web" + breadcrumbs
- [ ] Sin variantes visuales propias
- [ ] Smoke: comparar visualmente con Comercial — mismo look

### T8.4 — Verification + version bump (~30 min)
- [ ] `npm run check` final pasa
- [ ] `npm run build` (Vite) pasa
- [ ] Bump version: `Cargo.toml` v0.1.X → v0.2.0, `tauri.conf.json` mismo
- [ ] Update changelog si existe

### T8.5 — Smoke test end-to-end (~75 min)
- [ ] Abrir ERP → Admin Web → Home con KPIs reales
- [ ] Vault > Queue → audit funciona como antes
- [ ] Vault > Publicados → ver cards, abrir modal, promover a Stock
- [ ] Vault > Grupos → crear tag nuevo, asignar a 3 jerseys
- [ ] Vault > Universo → aplicar 3 filters, sort, bulk archive
- [ ] Stock/Mystery/Site/Sistema → cascarones navegables sin error
- [ ] ⌘K command palette funciona
- [ ] Atajos `g v`, `g h`, `n`, `?` funcionan
- [ ] Audit log captura los cambios

### T8.6 — Build MSI + tag (~30 min)
- [ ] `npm run tauri build`
- [ ] Verify MSI generado en `src-tauri/target/release/bundle/`
- [ ] `git tag v0.2.0 -m "Admin Web R7 — Skeleton + Vault profundo"`
- [ ] Push branch + PR

### T8.7 — Release notes (~20 min)
- [ ] Documentar en LOG.md de elclub-catalogo-priv: tasks shipped, métricas, issues pendientes
- [ ] Update PROGRESS.md flag "Admin Web R7 SHIPPED"

---

## Acceptance criteria (R7 ship)

- [ ] Admin Web es navegable desde el sidebar global del ERP
- [ ] Home muestra 8 KPIs reales con sparklines, 5 tiles de accesos, Inbox con eventos detectados auto-dismissables
- [ ] Vault > Queue funciona como antes (Audit existente intacto)
- [ ] Vault > Publicados: cards + smart filters + modal extendido + drop creator funcional
- [ ] Vault > Grupos: 11 tipos, ~110 tags pre-poblados, CRUD funcional, asignación con validación cardinalidad
- [ ] Vault > Universo: tabla densa toggle a grid, 6+ filters, presets, bulk actions, URL state
- [ ] Stock/Mystery/Site/Sistema: cascarones navegables sin error
- [ ] Modelo de datos: 18 tablas + 4 columnas en `audit_decisions` + seed de 110 tags
- [ ] Command Palette ⌘K + atajos Vim funcionan
- [ ] Audit log captura mutations
- [ ] `npm run check` + `npm run build` + `npm run tauri build` pasan
- [ ] MSI build + smoke test end-to-end pasa
- [ ] Comercial R1 sigue funcionando sin regresiones

---

## Estimación de tiempo

| Fase | Tasks | Horas |
|---|---|---|
| F1 — Schema + Types | 4 | 6h |
| F2 — Shell + Routing + Cascarones | 7 | 5h |
| F3 — Home funcional | 6 | 6h |
| F4 — Vault Queue + Publicados | 9 | 12h |
| F5 — Vault Grupos | 8 | 12h |
| F6 — Vault Universo | 8 | 18h |
| F7 — Power features | 4 | 10h |
| F8 — Polish + ship | 7 | 8h |
| **TOTAL** | **53** | **~77h** |

**Estimación realista de calendario:** 7-10 días con Diego dedicado (8-10h/día). Con prep nocturno aplicado, las decisiones técnicas no consumen tiempo.

---

## Notas operativas

- Cada task es testeable independiente
- Commit por task (53 commits) con prefijo `[admin-web-r7]`
- Si una task se trabe >2x del estimado, parar y revisar scope
- Si schema migration falla mid-aplicación: rollback con backup (`cp elclub.backup-before-admin-web-r7.db elclub.db`)
- Branch: `admin-web-r7` — merge a main solo cuando T8.6 pase
