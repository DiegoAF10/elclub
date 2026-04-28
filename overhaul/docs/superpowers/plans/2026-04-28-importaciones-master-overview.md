# Importaciones — Master Overview Plan (R1.5 + R2-R6 one-shot)

> **For agentic workers:** REQUIRED SUB-SKILL: This is a master overview document. Per release plans live alongside this file (`2026-04-28-importaciones-IMP-R{1.5,2,3,4,5,6}.md`). Use superpowers:subagent-driven-development to execute each release plan task-by-task. Steps within each release plan use checkbox (`- [ ]`) syntax.

**Goal:** Shippear el módulo Importaciones completo end-to-end · cerrar gap de R1 + completar R2-R6 según spec original · habilitar Diego a operar imports + wishlist + margen real + free units + supplier metrics + settings sin Streamlit.

**Architecture:** Worktree aislado `el-club-imp` · branch `imp-r2-r6-build` · DB snapshot aislada con `ERP_DB_PATH` override · 6 releases secuenciales con paralelización Svelte en R2-R4 · merge `--no-ff` final + tag `v0.3.0`.

**Tech Stack:** Rust + rusqlite + Tauri 2 + Svelte 5 + TypeScript + Tailwind + JetBrains Mono · cero deps nuevas.

---

## Releases overview

| # | Release | Outcome | Tasks est. | Blocker para | Spec ref |
|---|---|---|---|---|---|
| 1 | **R1.5 R1-completion** | Wirea 8 botones rotos del header IMP + detail toolbar · agrega 5 commands Rust + 4 modals · Diego puede crear/registrar/editar/cancelar/cerrar pedidos E2E | ~60 | TODOS los demás (los R2-R6 reusan modal patterns + commands) | sec 5 (Detail pane) + sec 8 (errores) |
| 2 | **R2 Wishlist** | Tab Wishlist funcional · D7=B SKU validation · Promote-to-batch crea import draft · Inbox events · ~14 wishlist items pueden migrar desde WA personal | ~50 | R3 (margen real necesita imports nuevos creados via wishlist promote) | sec 4.2 + sec 6 (D6/D7) |
| 3 | **R3 Margen real** | Tab Margen real cross-Comercial · queries sales × imports.total_landed_gtq · cards per batch closed con revenue/landed/margen/stock pendiente · feeds para FIN-R2 | ~30 | — | sec 4.3 + sec 7 (queries) |
| 4 | **R4 Free units** | Tab Free units ledger · 4 destinos (vip/mystery/garantizada/personal) · auto-create al close_import (`floor(n_paid/10)`) · regex parsing de `imports.notes` históricos | ~35 | — | sec 4.4 + sec 6 (D-FREE) |
| 5 | **R5 Supplier scorecard** | Tab Supplier · Bond card con métricas · multi-supplier scaffold para futuro (Yupoo direct, Aliexpress) · lead time avg/p50/p95 · price band | ~25 | — | sec 4.5 |
| 6 | **R6 Settings + polish** | Tab Settings · defaults FX/free ratio/wishlist target · umbrales inbox events · migration log · integrations placeholders · empty states pulidos en todos los tabs | ~25 | (último) | sec 4.6 |

**Total estimado:** ~225 tasks · ~6-8h ejecución end-to-end (subagent-driven con paralelización en PHASE 2)

---

## Decisiones cargadas (NO reabrir · per coord file + Diego confirmaciones)

| ID | Decisión | Resolución | Origen |
|---|---|---|---|
| Pre-D1..D7 | Spec sec 6 | Todas fijadas (D1=A naming · D2=B prorrateo · D6=A wishlist tab · D7=B SKU enforced · D-FREE=A unassigned default · D-FX=7.73 · D-MIG=N/A DB compartida) | Spec brainstorm 2026-04-27 |
| **Wishlist ID format** | (b) **manual prompt regex `IMP-\d{4}-\d{2}-\d{2}` enforced** | Diego 2026-04-28 11:50 |
| **Branch strategy** | Una sola `imp-r2-r6-build` · merge `--no-ff` final · tag `v0.3.0` | Coord file 2026-04-28 |
| **Worktree** | Aislado en `C:\Users\Diego\el-club-imp\` con DB snapshot · `ERP_DB_PATH` override | Coord file + audit lib.rs:64 |
| **MSI cadence** | 1 al final del ship (release LTO ~5min) | Coord file regla 4 |
| **TDD strictness** | Mixed · TDD para commands transaccionales destructivos · smoke-only para CRUD/list/get/stubs | Diego 2026-04-28 11:30 |
| **Subagent paralelism** | Híbrido · yo Rust secuencial en lib.rs · sub-agents Svelte paralelos en R2/R3/R4 (archivos separados, cero conflict) | Mi recomendación + spec sec 10 |
| **Schema migration script path** | `el-club/erp/scripts/apply_imp_schema.py` (idempotente · CREATE TABLE IF NOT EXISTS · ALTER ... preserved if exists) · committed en branch | Diego 2026-04-28 11:50 |

---

## Dependency graph entre releases

```
R1.5 ────┬───► R2 ────► R3 ─────┐
         │                       │
         ├───► R4 ───────────────┤───► R5 ─────► R6
         │                       │
         └───► (polish R5/R6 reuse R1.5 modal patterns)
```

- **R1.5 es blocker absoluto** porque define modal patterns + Rust command patterns que R2-R6 reusan
- **R2-R4 paralelizables en frontend** (componentes Svelte independientes · lib.rs sigue secuencial)
- **R5/R6 secuenciales** porque Settings (R6) se nutre de defaults usados en R5 supplier card

---

## Schema additions plan (script `apply_imp_schema.py`)

Idempotente · corre 1 vez en main DB post-merge antes de instalar v0.3.0:

```sql
-- R2 wishlist (CREATE TABLE IF NOT EXISTS)
-- Schema completo en spec sec 7 línea 499-515

-- R4 free units ledger (CREATE TABLE IF NOT EXISTS)
-- Schema completo en spec sec 7 línea 518-535

-- R6 imports.notes_extra (TEXT) si no existe — para migration log
-- ALTER TABLE imports ADD COLUMN notes_extra TEXT (try/except IGNORE if duplicate)

-- Indexes (idempotentes)
-- CREATE INDEX IF NOT EXISTS idx_wishlist_status ON import_wishlist(status);
-- ... (4 indexes total per spec sec 7)
```

**NOTA:** las tablas `import_wishlist` e `import_free_unit` ya existen en main DB (creadas en IMP-R1 schema migration). El script solo asegura indexes y agregados R6 si necesario.

---

## Cross-module verification matrix (smoke test post-ship)

| Módulo afectado | Test | Expected |
|---|---|---|
| **Comercial** (R6 Sales Attribution loop) | `cmd_compute_profit_snapshot` antes/después de close_import nuevo | profit_snapshot.cogs cambia · revenue/marketing/opex idem |
| **Finanzas** Home | Hero "¿cuánto llevo ganado?" con sales reales · COGS feed desde imports closed | Q calculado correctamente (sales linkeadas · landed cost prorrateado) |
| **Vault catalog** | `family_id` lookups en wishlist (D7=B) · validation contra catalog.json | Wishlist insert bloquea si SKU no existe · permite si existe |
| **Admin Web Universe** | Audit decisions sin cambios | 520 audit_decisions intactas |

---

## Per release · invocar sub-skills

| Release | Skills aplicables |
|---|---|
| R1.5 | `superpowers:test-driven-development` (commands transaccionales) · `superpowers:subagent-driven-development` (executor) |
| R2 | TDD para `cmd_promote_wishlist_to_batch` (transactional · crea imports row + vincula items) |
| R3 | smoke-only (queries de lectura) |
| R4 | TDD para `cmd_assign_free_unit` (transactional UPDATE) |
| R5 | smoke-only (queries de lectura) |
| R6 | smoke-only (settings = config, no business logic) |
| (post R6) | `superpowers:verification-before-completion` antes de claim shipped |

---

## Output esperado al cierre del ship

1. **6 plans** en `docs/superpowers/plans/` (este overview + 6 release plans)
2. **Branch `imp-r2-r6-build`** con ~120-180 commits segmentados (1 por task agentic)
3. **Merge `--no-ff` a main** con commit summary "IMPORTACIONES E2E SHIPPED v0.3.0"
4. **Tag local `v0.3.0`**
5. **MSI artifact** en `bundle/msi/El Club ERP_0.3.0_x64_en-US.msi`
6. **Schema migration aplicada** en main DB
7. **Smoke test report** cross-module (4 módulos verificados intactos · IMP funcional E2E)
8. **LOG.md entry** en `elclub-catalogo-priv/docs/`
9. **PROGRESS.md update** con módulo IMP marcado como 🟢 100%
10. **SESSION-COORDINATION.md** entry final con merge details

---

## Riesgos identificados + mitigación

| Riesgo | Mitigación |
|---|---|
| `lib.rs` 5,296 líneas + N commits paralelos = merge hell | Yo (sesión IMP) hago TODOS los Rust commits secuencial · sub-agents solo tocan Svelte |
| `cargo build --release LTO` toma 5+ min · timing | 1 build al final · checkpoint con Diego antes |
| Sub-agents pueden divergir patrones visuales | Cada sub-agent recibe `app.css` tokens + ejemplo de modal R1.5 como reference |
| Schema migration falla en main DB | Script idempotente · backup pre-run · rollback path documentado |
| Diego sigue usando ERP main mientras yo trabajo · DB diverge | Snapshot fijado en mi worktree · cero contaminación cross |
| Browser fallback rompe (adapter `browser.ts`) | Cada Tauri command tiene stub `NotAvailableInBrowser` con mensaje claro |
| Spec ambiguity mid-flow | Per spec sec 11 línea 813: pausar · editar spec · commit · reanudar |

---

## Plan execution flow

```
1. Lee R1.5 plan completo (este turn output #2)
   ↓
2. Diego confirma execution mode (subagent-driven recomendado)
   ↓
3. Ejecuto R1.5 task-by-task (subagent fresh per task · review entre tasks)
   ↓
4. R1.5 ship · smoke local · commit batch
   ↓
5. Escribo R2 plan (próximo turn) · ejecuto R2
   ↓
6. R3 + R4 plans paralelos (yo escribo · sub-agents ejecutan Svelte)
   ↓
7. R5 plan + execute
   ↓
8. R6 plan + execute
   ↓
9. PHASE 4: verification skill · cross-module smoke
   ↓
10. PHASE 5: schema migration main DB · MSI rebuild · merge · tag
   ↓
11. Append SESSION-COORDINATION.md ship entry · ping Diego
```

---

**Next:** R1.5 plan en `2026-04-28-importaciones-IMP-R1.5.md` con ~60 tasks detallados.
