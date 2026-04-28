# Admin Web — Decisiones Técnicas Pre-Resueltas (ADR)

> Tipo Architecture Decision Records pero abreviado. El dev (vos o sesión futura) **NO** debe re-debatir estas decisiones al implementar — ya están resueltas. Si hay buena razón para cambiar, requiere actualizar este doc primero.

**Versión:** v0
**Fecha:** 2026-04-26
**Aplica a:** R7 + R7.1-R7.5

---

## ADR-001: SvelteKit 5 (runes) como framework

**Decisión:** Mantener SvelteKit 5 con runes ($state, $derived, $effect).

**Razón:** Comercial R1 ya está en SvelteKit 5. Cambiar de framework crea inconsistencia. Runes son power-feature de Svelte 5 que dan control fino sobre reactividad.

**Implicación:** Todo state mutable usa `$state()`, computeds usan `$derived()`, side effects usan `$effect()`. NO se usan stores writables tradicionales (`writable()`).

---

## ADR-002: Tabs como URL routing (no client-side state)

**Decisión:** Cada tab del Admin Web es una sub-route URL (`/admin-web/vault/queue`).

**Alternativa rechazada:** Tab state en localStorage o memoria, sin URL change.

**Razón:** Diego pidió URL state para todo (D6.5). Power user puede compartir links a vista exacta. Recargar la página restaura. Browser back/forward funciona.

**Implicación:** Cada tab tiene `+page.svelte`. Tabs container detecta route activa. Filters + sort + columns también van a query string (cuando aplique).

---

## ADR-003: Base de datos local SQLite (no migrar a PG)

**Decisión:** Mantener SQLite local en `el-club/erp/elclub.db` con WAL mode.

**Razón:** Tauri es app local de Diego (single user). Postgres requiere servicio externo, complica deployment. SQLite con índices apropiados maneja bien hasta ~1M rows.

**Implicación:** Schema migration via `audit_db.py:_ensure_schema()`. Backups via `cp` antes de cualquier operación destructiva. WAL mode permite concurrent reads.

---

## ADR-004: Modelo de overrides "referencia + override" (no clonado)

**Decisión:** Stock y Mystery NO clonan jerseys del Vault. Cada uno tiene tabla de overrides que referencia `family_id` del Vault.

**Alternativa rechazada:** Copiar jersey al promote ("clone").

**Razón:** Patrón Shopify variants. Cero drift en datos canónicos (foto, nombre, club). Una sola fuente de verdad. Decisión D4 del spec confirmada.

**Implicación:** Editar foto en Vault → propaga automático a Stock + Mystery. Editar precio en Stock NO afecta Vault (es override). UI debe indicar claramente qué campos son override vs heredados.

---

## ADR-005: Estados del jersey con SQL view computed

**Decisión:** El "estado" del jersey (DRAFT/QUEUE/PUBLISHED/REJECTED/ARCHIVED) NO es una columna explícita — se computa en SQL view `v_jersey_state` desde `audit_decisions.status` + `archived_at`.

**Razón:** Single source of truth. Cambiar transición = un solo lugar a tocar. No riesgo de desync entre `state` y campos primarios.

**Implicación:** Queries del Universo van contra `v_jersey_state`. Performance OK con indexes. Si se vuelve cuello de botella, materializamos.

**Tradeoff aceptado:** Hot-reload del view requiere DROP+CREATE (no afecta data).

---

## ADR-006: Override status también via SQL view computed

**Decisión:** `stock_overrides.computed_status` y `mystery_overrides.computed_status` se calculan en `v_stock_status` y `v_mystery_status` views, NO en columna persistente.

**Razón:** El status depende de `now()` vs `publish_at`/`unpublish_at`. Persistirlo requiere cron que recompute. View calcula always-fresh.

**Implicación:** Queries hit las views, no las tablas directamente. Triggers que dependan de status changes (ej. webhook CDN) usan polling cada N min, no triggers SQL en INSERT/UPDATE.

---

## ADR-007: Inbox events con detector cron centralizado (no triggers SQL)

**Decisión:** Detección de eventos del Inbox corre como cron job (Rust o worker), NO via triggers SQL on insert/update.

**Razón:** Triggers SQL son frágiles (cualquier write puede romper). Cron es testeable, debuggable, y desacopla lógica de detección de la persistencia. Performance: cron cada hora con queries optimizadas es más eficiente que triggers en cada write.

**Implicación:** Latencia de eventos hasta 1 hora (acceptable). Detector lee `inbox-events-catalog.json` para saber qué queries ejecutar. Auto-resolve cuando query no detecta.

---

## ADR-008: Tags como sistema relacional (no JSON column)

**Decisión:** `jersey_tags` es tabla many-to-many. Tags están en `tags`. NO se guarda lista de tags como JSON en `audit_decisions`.

**Razón:** Queries tipo "todas las jerseys con tag X" son trivial con índice. Filtros multi-tag (AND/OR) son SQL standard. Estadísticas (count por tag) directas.

**Tradeoff aceptado:** Joins en cada query (performance OK con indexes).

**Implicación:** UI de Universo joinéa `audit_decisions LEFT JOIN jersey_tags JOIN tags`. Sub-queries para "no tag de tipo X" usan `NOT IN`.

---

## ADR-009: Cardinalidad de tags se valida en aplicación, no en DB

**Decisión:** La regla "1 tag por tipo excluyente" se valida en Tauri command `validate_tag_assignment()`, NO en CHECK constraint SQL.

**Razón:** SQL CHECK constraints no pueden hacer queries cross-row del mismo tipo. La lógica involves: dado un family_id y un tag_id, ver si ya hay otro tag del mismo type asignado al family_id.

**Implicación:** Llamadas directas a INSERT en `jersey_tags` (sin pasar por validación) corrompen el invariante. Diego/dev DEBEN usar el Tauri command. Audit log captura quién violó si pasa.

**Mitigación a futuro:** Considerar AFTER INSERT trigger que rollback si valida fail.

---

## ADR-010: Tag conditional rules como JSON (flexible)

**Decisión:** `tag_types.conditional_rule` es JSON (`{applies_when, forbidden_when, required_when}`).

**Razón:** Reglas son varias (Liga aplica solo si Club Pro, etc.) y crecen. JSON evita esquema rígido. Validación corre en TS/Python parseando el JSON.

**Tradeoff aceptado:** No type-safety en DB. Mitigation: schema JSON validado en seed + tests.

---

## ADR-011: Audit log es write-only (no edit ni delete)

**Decisión:** `system_audit_log` no permite UPDATE ni DELETE. Solo INSERT.

**Razón:** Audit log debe ser inmutable para tener valor. Si Diego borrase un evento, defeats the purpose.

**Implicación:** Tabla crece monotónicamente. Plan retention policy: archive a un secondary file mensualmente. Implementar en R7.5+.

---

## ADR-012: Audit log se escribe sincrónicamente (no async queue)

**Decisión:** Cada Tauri command que muta data llama `write_audit_log()` sincrónicamente antes de COMMIT.

**Alternativa rechazada:** Queue async para escribir audit log fuera del path crítico.

**Razón:** Si la mutación falla y rollback, también queremos que audit log NO tenga el entry (consistency). Dentro de la misma transaction garantiza esto.

**Tradeoff aceptado:** Latencia +1ms por write. Negligible.

---

## ADR-013: Sparklines como SVG inline (no librería)

**Decisión:** Sparklines son SVG inline 60×20px renderizados en Svelte component custom.

**Alternativas rechazadas:**
- `react-sparklines` (no es Svelte)
- `chartist`/`chart.js` (overkill)
- `d3` (overkill)
- Canvas (más complejo para algo simple)

**Razón:** Sparkline es 7 puntos en una línea. SVG `<polyline>` es 5 líneas de código. Performance excelente (no JS lib).

**Implicación:** `Sparkline.svelte` componente reusable que toma array de números + max/min y renderiza polyline.

---

## ADR-014: Calendario visual: implementación custom, NO fullcalendar.io

**Decisión:** El calendario de Stock y Mystery se implementa custom en Svelte.

**Alternativas rechazadas:**
- `fullcalendar` (muy pesado, ~200KB, opinionated)
- `vue-cal` (no es Svelte)
- `svelte-calendar` (no soporta drag-drop bien)

**Razón:** Mockup-3 muestra layout muy específico (5 meses paralelos en columnas). Fullcalendar no soporta esto bien. Custom permite control total + retro gaming style.

**Implicación:** Implementación más larga (~120 min) pero exacto al diseño. Drag-drop con `@dnd-kit/core` (mismo lib de React, port a Svelte) o `svelte-dnd-action`.

---

## ADR-015: Búsqueda fuzzy con `fuse.js`

**Decisión:** Command Palette y otros search bars usan `fuse.js`.

**Alternativas rechazadas:**
- Custom Levenshtein (demasiado código)
- `fuzzysort` (similar performance, menos features)
- Server-side fuzzy con FTS5 SQLite (overkill para datasets <10K)

**Razón:** Standard, bien mantenido, configurable. Bundle size razonable (~10KB).

**Implicación:** `import Fuse from 'fuse.js'` en `CommandPalette.svelte`. Configurar weights (label > description > keywords).

---

## ADR-016: Tablas densas con virtualization usando `svelte-virtual`

**Decisión:** Universo table con > 100 rows usa virtualization.

**Alternativas rechazadas:**
- Sin virtualization (lag con 1000+ rows)
- `tanstack-virtual` (no Svelte native)

**Razón:** SvelteKit standard library para virtualization. Performance excelente.

**Implicación:** Hasta 100 rows: render normal. > 100: virtualize. Auto-detect por count del query result.

---

## ADR-017: Drag-drop con `svelte-dnd-action`

**Decisión:** Drag-drop interactions (calendar dates, columnas reorder, tags assignment) usan `svelte-dnd-action`.

**Alternativa rechazada:** `@dnd-kit/core` (es React-first, ports son inestables).

**Razón:** Native Svelte. Comunidad activa. Soporta touch.

---

## ADR-018: Editor de bloques de páginas: implementación custom v0, futuro tiptap/blocknote

**Decisión:** v0 implementa block editor custom simple (drag-drop bloques con config inline). v0.5+ migrar a `@blocknote/core` o `tiptap` si se necesita rich editing.

**Razón:** v0 cascarón solo necesita 5-6 bloques pre-definidos. Editor rico es overkill. Migración futura cuando Diego lo pida.

---

## ADR-019: Validation en formularios: Zod en cliente, validation en Tauri

**Decisión:** Schemas Zod definen forms en Svelte. Tauri commands también validan (defense in depth).

**Razón:** Cliente validation = UX (instant feedback). Server validation = security (no podés confiar en cliente).

**Implicación:** Cada form tiene un schema Zod. Mismos schemas exportados desde `lib/data/` se reusan en Tauri.

---

## ADR-020: ⌘K como atajo global, NO context-aware

**Decisión:** ⌘K abre Command Palette desde cualquier ruta del Admin Web (incluso desde dentro de modals).

**Alternativa rechazada:** Atajos diferentes por contexto.

**Razón:** Power user expectation (Linear, Notion, Raycast). Diego ya está acostumbrado.

**Implicación:** Hook global `keydown` con preventDefault si Cmd+K. Excluir solo cuando focus en input editable critical (ej. password field).

---

## ADR-021: Tipografía monospace para SKUs/IDs/numbers, sans-serif para todo lo demás

**Decisión:** Aplicar `font-family: monospace, font-variant-numeric: tabular-nums` a SKUs, IDs, family_ids, números, timestamps, prices, coverage.

**Razón:** Legibilidad. Diego visualmente parsea SKUs por shape. Tabular-nums alinea columnas en tablas.

**Implicación:** CSS class utility `.mono` definida en global.css. Aplicada en components donde corresponde.

---

## ADR-022: Sin tests unitarios automatizados (mantenemos patrón Audit)

**Decisión:** No instalar vitest/jest. Mantenemos patrón actual: TypeScript types como contract + `npm run check` + smoke test manual.

**Alternativa rechazada:** Setup vitest, escribir unit tests.

**Razón:** Comercial R1 lo decidió así. Cambiar setup requiere migración. Para Mystery algorithm SÍ escribimos tests porque es business-critical (R7.2 T1.3) — pero como scripts standalone, no framework.

**Tradeoff aceptado:** Bugs pueden pasar test manual. Mitigation: smoke test riguroso, audit log para detectar.

---

## ADR-023: Color palette y design tokens en CSS variables (no Tailwind theme)

**Decisión:** Branding Tab del Site escribe a `site_branding` table que se inyecta como CSS variables al `<html>` element. Tailwind config usa `var(--color-accent)` etc.

**Razón:** Diego puede cambiar paleta sin redeploy de código. Cambios live preview en iframe.

**Implicación:** Tailwind config con custom colors mapped a CSS vars. Component styles usan `bg-[--color-accent]` o similar.

---

## ADR-024: i18n out de R7 (todo en español)

**Decisión:** Admin Web en español únicamente. Multi-idioma se considera en R7.5+ si Diego incorpora colaboradores.

**Razón:** Diego es el único usuario del Admin Web por ahora. i18n agrega complejidad sin valor.

**Implicación:** Strings hardcoded en español en components. Si futuro multi-idioma, refactor extracting a JSON.

---

## ADR-025: Estado de UI en componentes (no global store)

**Decisión:** Filters, sort, selected items son estado local del componente que los usa. No hay Redux-like global store.

**Alternativa rechazada:** Pinia/Zustand pattern para state global.

**Razón:** Svelte 5 con runes hace state local poderoso. URL state cubre persistence. Global store agrega indirection sin valor para single-user app.

**Implicación:** Pasar state via props hacia abajo. Si componente lejano necesita state, usa context API de Svelte (`setContext`/`getContext`).

---

## ADR-026: KPI snapshots persistidos diariamente, no on-demand

**Decisión:** Cron `kpi-snapshot-daily` corre cada día 00:00 GMT-6 y persiste 8 KPIs a `kpi_snapshots`. Sparklines del Home leen de esta tabla.

**Razón:** Computar sparklines on-demand cada vez que abres Home requiere queries complejas. Persistir snapshots es O(1) lookup.

**Implicación:** Sparklines siempre muestran data hasta ayer. Acceptable para gestión.

---

## ADR-027: No autenticación dentro del Admin Web

**Decisión:** Admin Web NO tiene login. Asume que el ERP Tauri ya autenticó a Diego globalmente.

**Razón:** Diego es único user. Tauri runs local. Doble auth es fricción.

**Implicación:** No hay login screen. No hay 2FA. Audit log marca user='diego' siempre. Si futuro hay colaboradores, agregar capa de auth (probablemente OS-level del ERP).

---

## ADR-028: Webhooks a worker async, NO sync con timeout

**Decisión:** Cuando Admin Web necesita disparar webhook a worker (ej. CDN invalidation), usa fire-and-forget async. NO bloquea el UI esperando confirmación.

**Razón:** UX. Si worker está lento, Diego no debería esperar. Audit log captura qué se intentó.

**Tradeoff aceptado:** Webhook puede fallar silenciosamente. Mitigation: dead-letter queue + retry policy.

---

## ADR-029: Performance budget para queries

**Decisión:** Todas las queries del Admin Web deben completar en <100ms en máquina típica de Diego (mid-range laptop).

**Implicación:** Cada query nueva requiere EXPLAIN QUERY PLAN. Indexes para casos comunes. Pagination siempre (no SELECT * sin LIMIT).

**Mitigación si se rompe:** Background processing + KPI snapshots, materialized views.

---

## ADR-030: Branch strategy y commits

**Decisión:**
- Branch por release: `admin-web-r7`, `admin-web-r7.1`, etc.
- Commits granulares (1 por task del plan), prefijo `[admin-web-r7]`
- PR a main solo cuando smoke test pase
- NO merge a main si Comercial tiene branch activa con conflict potential

**Razón:** Aislar trabajo + permite revert granular si algo se rompe.

---

## ADR-031: Manejo de errores: toast notifications + audit log

**Decisión:** Errores de Tauri commands se muestran como toasts (top-right). Severity dicta color (rojo critical, amarillo warning). Auto-dismiss después de 5s. Persisten en system_audit_log con severity=warning.

**Razón:** UX no-intrusiva. Diego puede continuar trabajando. Audit captura para debug futuro.

---

## ADR-032: Loading states con skeleton placeholders, no spinners

**Decisión:** Componentes loading muestran skeleton placeholders (gray boxes con shimmer animation) en lugar de spinner.

**Razón:** Skeleton da context visual (Diego ve forma del contenido). Spinners son ambiguos.

**Implicación:** Skeleton component reutilizable per-shape (card, row, kpi).

---

## Anexo: Stack final del Admin Web

| Capa | Tecnología | Razón |
|---|---|---|
| Framework | SvelteKit 5 (runes) | Comercial R1 ya lo usa |
| Styling | Tailwind v4 + CSS vars | Permite branding dinámico |
| Backend | Rust (Tauri 2) + Python bridge | Existente |
| DB | SQLite con WAL mode | Existente |
| Cache layer | KV de Cloudflare (worker) | Existente |
| Search | fuse.js | Light, suficiente |
| DnD | svelte-dnd-action | Native Svelte |
| Virtualization | svelte-virtual | Native Svelte |
| Validation | zod | Standard, type-safe |
| Charts | SVG custom | Sparklines simples |
| Calendar | Custom Svelte | Diseño exacto |
| Block editor | Custom Svelte (v0), tiptap (v0.5+) | Crece con necesidad |
| i18n | N/A v0 | Single-user español |
| Tests | TypeScript types + smoke manual | Patrón Audit/Comercial |
