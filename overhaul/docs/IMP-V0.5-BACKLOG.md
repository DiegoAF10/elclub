# IMP Module · v0.5+ Backlog (21 asteriscos)

**Última actualización:** 2026-04-29 (post v0.4.5 ship)
**Status:** módulo IMP cerrado funcionalmente al 100% del scope original (R2-R6) en v0.4.5 · estos 21 items son scope **conscientemente deferido** a v0.5+ (no son gaps · son scope futuro).

---

## ⚠️ Para sesiones futuras de Claude · LEER PRIMERO

**Si arrancás una sesión que toca IMP** (Importaciones · `lib.rs` IMP commands · Svelte components en `importaciones/`): leé este doc completo · esto te ahorra 30 min de re-discovery.

**Si arrancás una sesión de Comercial / Inventario / FÉNIX / Vault:** revisá la sección "Cross-module dependencies" abajo · varios asteriscos requieren cambios en TU módulo (no IMP).

**Si arrancás v0.5 sprint planning para IMP:** este es el inventory completo para priorizar. Los items están agrupados por dependency type. Recomiendo arrancar por los blockers de funcionalidad Diego ya espera (1-3) antes de auto-integrations (14-18).

---

## Contexto cero · ¿qué se shippeó hasta v0.4.5?

| Tab | Funcionalidad | Status |
|-----|--------------|--------|
| **Pedidos** | list/detail/create/arrival/edit/cancel/close + delete · export CSV · mark_in_transit | ✅ |
| **Wishlist** | CRUD + D7=B SKU validation server-side + cascade picker Tipo→Equipo→Modelo + Promote-to-batch | ✅ |
| **Margen real** | cards per batch closed · revenue/landed/margen/stock pendiente · filtros · pulso | ✅ (con caveats · ver *11, *21) |
| **Free units** | ledger 4 destinos · auto-create al close `floor(N/10)` · idempotency-guarded | ✅ (con caveats · ver *21 free unit creator UI) |
| **Supplier** | Bond scorecard · bonus widget "más pedidos sin publicar" | ✅ |
| **Settings** | defaults · umbrales · migration log · integrations (con stubs disabled) | ✅ (con caveats · ver *8-10) |

**Decisión arquitectónica clave (Q2 SUPERSEDED 2026-04-28 ~19:00):** `import_items` es **single-source bridge table** entre wishlist promote y inventory/sale. NO se split en sale_items + jerseys. customer_id nullable distingue stock-future vs assigned. Estado state machine: `pending → arrived → sold | published | cancelled`.

**Schema actual:** `import_wishlist` · `import_free_unit` · `import_items` · `imp_settings` (4 tablas IMP-owned) + `imports` (R1 pre-existente).

---

## ⭐ 21 asteriscos · v0.5+ deferred

### 🔗 Cross-module follow-ups (3 · prioridad ALTA · cuando integre Comercial / Inventario)

#### *1 · Comercial sale flow → UPDATE `import_items.sale_item_id` + `status='sold'`

**Qué falta:** cuando Comercial vende un jersey (creates `sale` + `sale_items`), si el item tiene `import_id` matching un `import_items` row con status='arrived', debe UPDATE ese `import_items` row con `sale_item_id` = nueva sale_items.item_id Y `status='sold'`.

**Por qué:** sin este link, R3 Margen real nunca puede calcular revenue real per batch (solo ve cost). Diego lo describió: "por el momento no puedo conectar sales a esto".

**Ubicación del fix:** Comercial sale flow (probablemente `lib.rs` cmd_create_sale_item o similar · territorio Iteración Continuous · NO IMP territory).

**Decisión UX pendiente:** ¿auto-match silencioso por family_id+size+customer_id? ¿confirm modal "este sale es de qué import_item?"? ¿qué pasa si hay 5 items con mismo family_id en el batch · pick first? Diego debe definir antes de implementar.

**Estimate:** 2-3h · Comercial Rust + Svelte + smoke + cross-module test.

#### *2 · Inventario module futuro → materialize stock from `import_items WHERE status='arrived'`

**Qué falta:** cuando exista módulo Inventario (no existe aún), debe leer `import_items WHERE status='arrived' AND jersey_id_published IS NULL` para materializar stock físico. Cuando Diego publica al catálogo, UPDATE `import_items SET jersey_id_published = ?, status='published'`.

**Cross-module dependency:** módulo Inventario es nuevo · este asterisco arranca cuando se diseñe ese módulo.

**Estimate:** depende del scope del módulo Inventario · este es 1 hook adentro del flow.

#### *3 · Cross-module nav stubs en R3 BatchMarginCard

**Qué falta:** los botones "→ Ver ventas linkeadas" y "→ Ver items pendientes" en `BatchMarginCard.svelte` emiten `console.log + alert` placeholder. Necesitan routing infra cross-módulo (Comercial filter por sale_ids · IMP detail subtab drilldown por status='pending').

**Ubicación:** `el-club/overhaul/src/lib/components/importaciones/BatchMarginCard.svelte:72,78` (líneas con `// TODO future:` comments).

**Estimate:** 30-45 min cuando exista routing global.

---

### ⏰ Cron / automation (4 · thresholds ya almacenados · falta ejecutor)

R6 stores las thresholds en `imp_settings` table pero NO existe cron infra para emitirlas. Cuando se construya cron infra (cualquier módulo · probablemente Worker Cloudflare o background task en Tauri), estos eventos quedan automáticos:

#### *4 · Inbox event "wishlist > N items → consolidar batch"
- Threshold: `imp_settings.threshold_wishlist_unbatched_days` (default 30 days)
- Trigger: cron daily check `import_wishlist WHERE status='active' AND COUNT > N`
- Action: INSERT INTO `inbox_events` con type='wishlist_overflow'

#### *5 · Inbox event "wishlist item asignado > 30d sin batch"
- Threshold: `imp_settings.threshold_wishlist_unbatched_days`
- Trigger: cron daily check items con `customer_id IS NOT NULL AND created_at < NOW - threshold AND status='active'`

#### *6 · Inbox event "free unit sin asignar > 7d"
- Threshold: `imp_settings.threshold_free_unit_unassigned_days` (default 7)
- Trigger: cron daily check `import_free_unit WHERE destination IS NULL AND created_at < NOW - threshold`

#### *7 · Inbox event "batch paid sin arrived > 14d"
- Threshold: `imp_settings.threshold_paid_unarrived_days` (default 14)
- Trigger: cron daily check `imports WHERE status='paid' AND paid_at < NOW - threshold`

**Estimate (4 events combinados · UNA cron infra · 4 INSERT funcs):** 2-3h cuando exista la infra.

---

### 🔧 Cableado Settings → lógica (3 · UI editable pero no consumida)

Diego puede editar estos valores en Settings tab · pero **el código actual los hardcodea**. Cambiarlos en UI hoy NO afecta behavior.

#### *8 · `default_fx` · NewImportModal hardcoded `7.73`
- **Ubicación fix:** `lib.rs cmd_create_import` · leer de `imp_settings WHERE key='default_fx'` antes de validar input.fx
- **Y:** `NewImportModal.svelte` y `PromoteToBatchModal.svelte` que tienen `let fx = $state(7.73)` · cambiar a `$state<number | null>(null)` y popular en `$effect` desde `adapter.getImpSetting('default_fx')`.
- **LOC:** ~10

#### *9 · `default_free_ratio` · `impl_close_import_proportional` hardcoded `floor(n_paid/10)`
- **Ubicación fix:** `lib.rs:2815` línea `let n_free = n_paid / 10;` · leer de `imp_settings WHERE key='default_free_ratio'` parsed as i64
- **LOC:** ~10

#### *10 · `default_wishlist_target` · `WISHLIST_TARGET_SIZE` hardcoded `20`
- **Ubicación fix:** `el-club/overhaul/src/lib/data/wishlist.ts` (constante exportada `WISHLIST_TARGET_SIZE = 20`) · cambiar a fetch from settings
- **Y:** `WishlistTab.svelte` · `PromoteToBatchModal.svelte` · cualquier referencia a la constante
- **LOC:** ~15

**Estimate combined:** 30 min · 1 sweep + tests + smoke.

**Heads-up UX:** considerar mostrar un pill "● cableado en v0.5" en cada Setting field cuando el cableado no esté completo · evita la sorpresa del "cambié pero no pasa nada".

---

### 📊 Datos / valuación / migration (3 · semántica abierta o data histórica pendiente)

#### *11 · `valor_free_units_gtq` en R3 BatchMargenSummary

**Qué falta:** R3 reporta este field como `None` (Q—) hasta que Diego decida regla de valuación.

**3 opciones (Diego decide en v0.5):**
- (a) **Cost-based:** `valor = cost_per_unit × n_free` — refleja "cuánto te cuesta la generosidad del chino"
- (b) **Price-based:** `valor = price × n_free` — refleja "valor retail de los regalos"
- (c) **Avg unit_cost:** `valor = total_landed / n_paid × n_free` — proporcional al batch

**Ubicación fix:** `lib.rs impl_compute_batch_summary` · `valor_free_units_gtq` calc.

**LOC:** ~5 + decisión.

#### *12 · `cost_accuracy_pct` en R5 SupplierMetrics

**Qué falta:** muestra "Datos insuficientes" hasta que exista disputes log (tabla nueva `supplier_disputes` · v0.5+).

**Estimate:** depende del scope disputes · puede ser nuevo módulo de v0.6.

#### *13 · Migration histórica de free units desde `imports.notes`

**Qué falta:** los 2 imports históricos (IMP-2026-04-07 closed, IMP-2026-03-24 cancelled) tienen free units mencionadas en `notes` como string ("2 Argentina regalo"). Script regex parser pendiente.

**Workaround actual:** Diego puede crear las free units manualmente vía UI (cuando exista `+ agregar manualmente` · ver *21).

**Estimate:** 30 min script + 5 min input Diego confirmando destinos históricos.

---

### 🤖 Auto-integraciones externas (5 · todas v0.5+ · scope independiente)

#### *14 · PayPal screenshot OCR para auto-llenar `bruto_usd`

**Idea:** cuando Diego adjunta screenshot del PayPal en `NewImportModal`, OCR extracts el monto + fee.

**Estimate:** depende del provider · 4-8h · Tauri plugin OCR + UI.

#### *15 · DHL tracking webhook → auto-update `arrived_at`

**Idea:** webhook que cuando DHL marca paquete delivered, UPDATE `imports.arrived_at` automático.

**Estimate:** 2-3h · webhook endpoint en Worker Cloudflare + DHL API auth.

#### *16 · BANGUAT API → auto-fetch FX del día

**Idea:** cuando crea un import, FX default es la cotización Banguat del día (no el hardcoded 7.73).

**Estimate:** 1-2h · API call + caching + fallback.

#### *17 · Re-sync Streamlit ⇆ Tauri

**Estado actual:** botón en Settings tab está stub-disabled.

**Por qué deferred:** necesita merge logic clara · si Diego cierra batch en Streamlit, ¿el Tauri lo importa? ¿qué pasa si ambos tienen mismo `import_id` con status diferente? Resolución conflict no trivial.

**Estimate:** 4-6h · merge logic + UX modal de conflict resolution + testing.

#### *18 · Bot ManyChat → capture wishlist desde WA personal de Diego

**Idea:** Diego le manda "Argentina Messi 10 L" via WA (al chatbot), y el bot crea automatically el wishlist item.

**Estimate:** 3-4h · ManyChat flow + webhook handler + parsing NLP simple.

---

### 🏪 Multi-supplier real (2 · Bond es único hoy · scaffold ya existe)

#### *19 · Tabla `suppliers` proper

**Qué falta:** schema nuevo:
```sql
CREATE TABLE suppliers (
  supplier_id INTEGER PK,
  name TEXT NOT NULL UNIQUE,
  contact_name TEXT, contact_method TEXT, contact_value TEXT,
  payment_terms TEXT, default_carrier TEXT, default_fx REAL,
  notes TEXT, created_at TEXT
);
```

Y migration: `imports.supplier_id` FK que reemplaza `imports.supplier TEXT`.

**Estimate:** 2-3h · schema + migration + UI Settings.

#### *20 · Scorecards comparativos multi-supplier

**Qué falta:** UI que compara métricas (lead time · cost accuracy · price band) entre Bond y futuros suppliers.

**Estimate:** 1-2h · una vez existe tabla suppliers + ≥2 suppliers con data.

---

### 🩹 Migration debt sweep (1 · descubierto en v0.4.5 · IMPORTANTE)

#### *21 · Read paths que NO leen `import_items` table

**Qué pasó:** decisión Q2 SUPERSEDED (single-source `import_items`) requirió update a TODOS los queries que iteran items. v0.4.4 y v0.4.5 fixearon 2 (`cmd_get_import_items` + `impl_close_import_proportional`). **Probablemente quedan más latentes.**

**Sospechosos a auditar (grep + verificar):**
- `cmd_get_import_pulso` (lib.rs:2570) · capital_amarrado calc · cuenta items?
- `cmd_get_margen_real` (R3) · revenue + stock pendiente queries
- `cmd_get_batch_margen_breakdown` (R3) · pending items per batch
- `cmd_get_margen_pulso` (R3) · global aggregates
- `cmd_get_supplier_metrics` (R5) · n_units total per supplier
- `cmd_get_most_requested_unpublished` (R5 bonus) · GROUP BY family_id

**También · el `+ Agregar free unit manualmente` UI:** descubierto que NO existe. Diego puede asignar destino a free units existentes pero no crear extras (caso: chino le da más free units que `floor(N/10)` calcula). Necesita modal `CreateFreeUnitModal.svelte` + `cmd_create_free_unit` Rust.

**Estimate sweep:** 2-3h · grep + audit + fix per query · regression test cross-cutting.

**Estimate `+ Agregar free unit` UI:** 30 min.

**Cómo descubrir más bugs:** Diego usa los tabs con batches reales closed. Cuando algo no muestre data esperada, es probable migration debt en read path.

---

## 📁 Cross-module dependencies (heads-up para otras sesiones)

### Para sesiones de Comercial

- **Crítico (asterisco *1):** sale flow debe UPDATE `import_items.sale_item_id` + `status='sold'` cuando se vende un jersey con `import_id` matching un import_items arrived. Esto cierra el loop de margen real R3.
- **Decisión UX pendiente:** auto-match silencioso vs confirm modal · Diego debe definir antes de implementar.
- **NO eliminar el field `sale_items.import_id`** · sigue usándose para items pre-promote (si los hubiera) y para close_import prorrateo.

### Para sesiones de Inventario (cuando ese módulo arranque)

- **Asterisco *2:** lee `import_items WHERE status='arrived' AND jersey_id_published IS NULL` para materializar stock disponible · UPDATE `jersey_id_published = ?, status='published'` al publicar.
- **NO crear tabla nueva de inventory** · `import_items` ya tiene los datos · usar como source.

### Para sesiones de FÉNIX (finanzas)

- **No hay asterisco directo** · pero el módulo IMP expone `imports.total_landed_gtq` + `import_items.unit_cost_gtq` para que FÉNIX consuma cash flow + P&L per batch.
- **Cross-bucket flag:** cuando se ejecute `close_import`, considerar emitir un `inbox_event` que FÉNIX consuma (capital amarrado se libera · debt outstanding · etc).

### Para sesiones de Vault / Catalog

- **Asterisco *2 + R5 bonus widget:** el módulo IMP queries `catalog.json` para validation D7=B (modelo SKU exists) y para el widget "más pedidos sin publicar". Schema del catalog es source-of-truth · NO modificar sin notificar IMP sessions.
- **Si cambia schema de modelos[].sku, modelos[].type, modelos[].sleeve:** IMP necesita update en `cmd_list_catalog_modelos` + `catalog_modelo_sku_exists` (ambos en lib.rs).

### Para sesiones de Cron infra (futura · cualquier módulo)

- **Asteriscos *4-7:** los thresholds ya están persistidos en `imp_settings`. Cron debe leer + emitir `inbox_events` con type específico (`wishlist_overflow` · `wishlist_assigned_stale` · `free_unit_unassigned` · `paid_unarrived`).
- **inbox_events table schema (verificado):** `id · type · severity (CHECK info/important/critical) · title NOT NULL · description · action_label · action_target · module NOT NULL · metadata TEXT · created_at INTEGER unixepoch · dismissed_at · resolved_at · expires_at`. Module = 'importaciones' para los IMP events.

---

## 🧠 Aprendizajes meta para sesiones futuras

### TS interface drift vs Rust serde rename_all

**Bug pattern observado en v0.4.1-v0.4.2:** TS interface declarado snake_case · Rust struct con `#[serde(rename_all = "camelCase")]` · TS check pasa pero runtime los fields son undefined porque el wire es camelCase.

**Prevención:** cuando creés un nuevo struct Rust con `rename_all`, el TS interface debe usar camelCase. Considerar agregar test integration que serialize Rust → deserialize TS → assert shape matches (catch this class of bug).

### Migration debt en read paths

**Cuando cambies decisión arquitectónica de schema** (e.g. Q2 SUPERSEDED single-source), grep ALL queries que iteran items afectados:

```bash
grep -n "FROM sale_items\|FROM jerseys\|FROM import_items" lib.rs
```

Cada uno necesita actualizarse. Bugs latentes se acumulan si no se hace sweep proactivo.

### Plan + audit técnico ≠ acceptance test humano

**Lección de v0.4.0 → v0.4.5:** plan-vs-execution audit declaró "shipped == DoD" al 100% pero MISSED 8 bugs UX que solo Diego acceptance test agarró (cascade gap · render snake/camel · promote bruto · select toggle confusion · items linkeados invisible · edit fechas · hard delete · close_import migration debt).

**Patrón correcto:** después de mission-complete técnica, build MSI intermedio + Diego acceptance test ANTES de declarar mission-complete real. 6 iterations en este sprint validaron el patrón.

### Tauri 2 macro footgun

**`pub async fn cmd_X` con `#[tauri::command]`** macro genera name conflict en Tauri 2 setup de El Club. Solution: `cmd_X` MUST be non-pub · `impl_X` SÍ pub (testable). Documentado en convention block lib.rs:2730-2742.

---

## 🗺️ Quick reference · ¿dónde está cada cosa?

| Cosa | Path |
|------|------|
| Specs original IMP-R1 | `el-club/overhaul/docs/superpowers/specs/2026-04-27-importaciones-design.md` |
| Plans R2-R6 (5 archivos) | `el-club/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R{2,3,4,5,6}.md` |
| Plan-vs-execution audit | `el-club/overhaul/docs/superpowers/plans/2026-04-28-importaciones-PLAN-VS-EXECUTION-AUDIT.md` |
| Peer review | `el-club/overhaul/docs/superpowers/plans/2026-04-28-importaciones-PEER-REVIEW.md` |
| Schema migration script | `el-club/erp/scripts/apply_imp_schema.py` |
| Smoke tests | `el-club/erp/scripts/smoke_imp_r{2,6,r15}.py` |
| Rust commands IMP | `el-club/overhaul/src-tauri/src/lib.rs` (~30 commands · grep `cmd_.*import\|cmd_.*wishlist\|cmd_.*free_unit\|cmd_.*supplier\|cmd_.*imp_settings\|cmd_.*catalog_modelos`) |
| Adapter wires | `el-club/overhaul/src/lib/adapter/{types,tauri,browser}.ts` |
| Svelte components | `el-club/overhaul/src/lib/components/importaciones/` (18 archivos) |
| Sesión coord file | `elclub-catalogo-priv/docs/SESSION-COORDINATION.md` (Strategy ledger · IMP final entry 2026-04-29 noche) |
| LOG histórico | `elclub-catalogo-priv/docs/LOG.md` (entry 2026-04-29 noche IMP-R2-R6 SHIPPED) |
| **ESTE doc** | `el-club/overhaul/docs/IMP-V0.5-BACKLOG.md` |

---

## 📌 Para v0.5 sprint planning

**Top 5 priorities recomendadas (según valor para Diego workflow):**

1. **Asterisco *1** (Comercial sale → import_items link) — desbloquea margen real automático · valor inmediato
2. **Asterisco *21 sweep** (read paths migration debt) — antes que más bugs latentes aparezcan
3. **Asteriscos *8-10** (Settings → lógica wiring) — consistencia entre UI y behavior
4. **Asterisco *21 free unit creator UI** — quality of life · 30 min
5. **Asterisco *2** (Inventario module hook) — cuando se diseñe módulo Inventario

Los demás (cron, OCR, webhooks, multi-supplier) son scope grande individual · scheduling per-item según urgencia.

---

**Fin del backlog.** Última sesión cerrada: IMP-R2-R6 BUILD (2026-04-29 noche) · Diego accepted v0.4.5 · merge commit `6d0f514` · tag local `v0.4.5`.
