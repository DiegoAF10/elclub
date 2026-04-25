# ERP Overhaul — Handoff técnico

> **Audiencia:** próximo Claude que recoja este trabajo. Asumí que no leíste el LOG ni el plan original.
>
> **Lectura sugerida en orden:**
> 1. Este doc (top-to-bottom, ~10 min)
> 2. `~/.claude/plans/sharded-swinging-fiddle.md` — plan original Fase 1+2 (referencia)
> 3. `elclub-catalogo-priv/docs/LOG.md` § "2026-04-23 noche → 2026-04-24 tarde" — bitácora cronológica
> 4. `elclub-catalogo-priv/docs/YUPOO-SCRAPING-PLAYBOOK.md` — invariantes del catalog
>
> **Última versión:** v0.1.20 (2026-04-24 ~18:00). 251 SKUs auditables.

---

## Qué es esto

Reemplazo Tauri del ERP Streamlit (`el-club/erp/app.py`). Single-user desktop app con:
- UI nativa (WebView2 en Windows, ~6 MB binary, ~3 MB MSI)
- Lee/escribe `catalog.json` del repo hermano `elclub-catalogo-priv` y `audit_decisions` SQLite local
- Invoca el stack Python preservado (`local_inpaint`, `audit_enrich`, `publicados._regen_watermark`) via subprocess para watermarks + R2 + git push
- 80% del trabajo diario de auditoría de Diego sucede acá; el Streamlit viejo solo para pipelines batch (Claude enrich, seed_audit_queue, etc.)

**No reemplaza al Streamlit todavía** — features de admin (inyect-scrapes, dashboards, batch operations) siguen ahí.

---

## Stack y arquitectura

```
┌─────────────────────────────────────────────────────────┐
│  SvelteKit UI (Svelte 5 runes + Tailwind v4)           │
│  src/lib/components/* + src/routes/*                    │
└──────────────────┬──────────────────────────────────────┘
                   │ adapter pattern
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Adapter facade (src/lib/adapter/index.ts)              │
│   ├─ browser.ts  → fetch a vite dev plugin (npm run dev)│
│   └─ tauri.ts    → invoke() native (npx tauri dev / msi)│
└──────────────────┬──────────────────────────────────────┘
                   │ Tauri invoke (cuando native)
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Rust commands (src-tauri/src/lib.rs)                   │
│   ├─ Direct: rusqlite (audit_decisions) + serde_json   │
│   │          (catalog.json mutate atomic + backup)     │
│   └─ Subprocess: Python bridge (UTF-8 stdin/stdout)    │
└──────────────────┬──────────────────────────────────────┘
                   │ child stdin: JSON cmd
                   │ child stdout: JSON result (último {)
                   │ child stderr: JSONL progress events
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Python bridge (erp/scripts/erp_rust_bridge.py)         │
│   COMMANDS = {ping, regen_watermark, batch_clean_family,│
│   delete_sku, edit_modelo_type, set_modelo_field,       │
│   set_family_variant, move_modelo, delete_r2_objects}   │
│   → invoca publicados.py / audit.py / audit_db.py /     │
│     audit_enrich.py existentes (NO reimplementa)        │
└─────────────────────────────────────────────────────────┘
```

**Decisión arquitectónica clave — preservación del stack Python:** torch+CUDA+iopaint+LaMa+easyocr son ~5GB de deps que Diego ya tenía instaladas. Reimplementar en JS/Rust sería meses de trabajo. El bridge subprocess es una shim de ~1KB que mantiene Python como source-of-truth de imagen processing.

**Decisión clave — adapter pattern:** dev experience rápido (`npm run dev` con hot reload) mientras producción usa Tauri (compile lento). Mismo código frontend, dos runtimes.

---

## Paths absolutos críticos

| Path | Qué | Quién escribe |
|---|---|---|
| `C:\Users\Diego\elclub-catalogo-priv\data\catalog.json` | 139 families × N modelos | scraper, ERP nuevo, ERP viejo, scripts backfill |
| `C:\Users\Diego\el-club\erp\elclub.db` | SQLite con audit_decisions, audit_photo_actions, etc. | ERP nuevo + viejo |
| `C:\Users\Diego\el-club\overhaul\` | El ERP nuevo (este proyecto) | dev |
| `C:\Users\Diego\el-club\erp\scripts\erp_rust_bridge.py` | Bridge Python ↔ Rust | dev |
| `C:\Users\Diego\el-club\overhaul\src-tauri\target\release\bundle\msi\El Club ERP_0.1.X_x64_en-US.msi` | Build artifact | `npx tauri build` |

Configurables via env vars: `ERP_CATALOG_PATH`, `ERP_DB_PATH`, `ERP_CATALOG_REPO`, `ERP_SCRIPTS_DIR`, `ERP_PYTHON`, `ERP_MSI_FOLDER`. Sin override usan los paths hardcoded de Diego.

---

## Convenciones

### Versioning (MSI upgrades sin desinstalar)

`tauri.conf.json::version` + `Cargo.toml::version` deben coincidir. Bump SIEMPRE en cada release distribuida — Windows trata MSIs con misma version como reinstall (requiere uninstall manual). Bumps:
- **PATCH** (0.1.X → 0.1.Y): bug fix o pequeña feature retrocompatible
- **MINOR** (0.1.x → 0.2.0): feature grande, refactor UI mayor, o reemplazar el Streamlit
- **MAJOR** (0.x → 1.0.0): el ERP nuevo es estable, deprecación oficial del Streamlit

### Naming Rust commands

Snake_case en Rust struct fields y param names. Tauri auto-convierte JS `camelCase` → Rust `snake_case` solo en TOP-LEVEL invoke args. **Para args anidados (objetos dentro de objetos), agregar `#[serde(rename_all = "camelCase")]` al struct.** Bug ya pisado en `MoveModeloArgs` (v0.1.18).

### Catalog mutations

**Siempre** usar `write_catalog_atomic()` (escribe a `.tmp` + rename + backup timestamped). Nunca `fs::write` directo al `catalog.json` desde Rust.

**Después de cualquier mutation** llamar `invalidate_catalog(state)` para que el siguiente `load_catalog` re-lea desde disk. Adicionalmente, `load_catalog()` compara mtime del archivo en disk vs cached — si script externo modificó el catalog, se auto-invalida (fix v0.1.20).

### Audit DB UPSERT

Cualquier comando que escribe `audit_decisions` debe usar UPSERT (INSERT ON CONFLICT DO UPDATE), no UPDATE plain. Razón: scrapes nuevos no seedean audit_decisions automáticamente — la row puede no existir todavía. Bug pisado en v0.1.16.

### Async commands

**Cualquier** Tauri command que ejecuta subprocess (Python bridge, git) DEBE ser `async fn` + `tauri::async_runtime::spawn_blocking`. Sin esto, el command bloquea el main thread → Windows mata la app como "Not Responding" tras ~30s. Bug catastrófico pisado en v0.1.7. Aplicado a: `batch_clean_family`, `invoke_watermark`, `delete_sku`, `edit_modelo_type`, `move_modelo`, `commit_and_push`, `git_status`, `python_ping`, `set_modelo_field`, `set_family_variant`.

**Excepción OK:** SQLite-only commands (set_decision_status, set_final_verified, etc.) son rapidísimos, pueden quedar `fn` sync sin riesgo.

### Python bridge

- Stdin recibe **un solo** JSON con `{cmd, ...args}`.
- Stdout devuelve **una línea JSON** con el result (`{ok: bool, ...}`). Último `{` line de stdout gana.
- Stderr puede emitir **JSONL events** prefijados con `__progress__: true` que el Rust thread paralelo reemite como Tauri event `bridge-progress` para UI streaming.
- **UTF-8 forzado** al inicio del script: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`. Sin esto, emojis en error messages crashean en Windows cp1252. Bug pisado v0.1.13.

---

## Comandos comunes

```bash
# Dev mode (browser + vite plugin custom, sin Tauri)
cd C:/Users/Diego/el-club/overhaul && npm run dev
# → http://localhost:5173

# Type check + svelte-check
cd C:/Users/Diego/el-club/overhaul && npm run check

# Tauri dev (con hot reload + window nativa). Requiere Rust en PATH:
export PATH="$HOME/.cargo/bin:$PATH"
cd C:/Users/Diego/el-club/overhaul && npx tauri dev

# Build production .msi (toma 2-5 min con caches calientes, ~10 min cold)
export PATH="$HOME/.cargo/bin:$PATH"
cd C:/Users/Diego/el-club/overhaul && npx tauri build
# → src-tauri/target/release/bundle/msi/El Club ERP_0.1.X_x64_en-US.msi

# Test bridge directamente (debug Python sin Tauri):
cd C:/Users/Diego/el-club/erp
echo '{"cmd":"ping"}' | python scripts/erp_rust_bridge.py

# Inspect catalog state:
python -c "import json; cat=json.load(open(r'C:\Users\Diego\elclub-catalogo-priv\data\catalog.json','r',encoding='utf-8')); print(len(cat),'families'); print(sum(1 for f in cat if f.get('published')),'published')"

# Backfill catalog meta + prices (dry run):
cd C:/Users/Diego/el-club/erp && python scripts/backfill_catalog_meta.py --dry-run
# Real run:
cd C:/Users/Diego/el-club/erp && python scripts/backfill_catalog_meta.py
```

---

## Estado actual (al cierre v0.1.20)

**Catalog (`elclub-catalogo-priv/data/catalog.json`):**
- 139 families, 251 SKUs
- Diego está en pleno proceso de audit fresh (post wipe del 23/04 noche)
- 101 families con meta_country/meta_confederation backfilled
- 81 marcados wc2026_eligible
- 251 modelos con price default (Q435 adult / Q275 kid / Q250 baby)
- Sin sagradas (final_verified=1) — Diego reseteó al inicio de sesión

**audit_decisions DB:**
- ~139 rows pending (post wipe)
- 0 final_verified
- audit_photo_actions, audit_telemetry, pending_review todos vacíos

**Vault live (`vault.elclub.club`):**
- Refresca via GitHub Pages, ~30s post-push
- Lee del catalog.json del repo hermano (público al vault repo? — verificar si privado, hay que ajustar)
- Sección "Mundial 2026" tiene 6 confederations: UEFA, CONMEBOL, CONCACAF, AFC, CAF, OFC

**El Streamlit ERP viejo:**
- Sigue funcional para inyect scrapes + Claude enrich pipeline + dashboards
- Misma DB y catalog que el ERP nuevo (lectura/escritura coexiste)
- Diego lo abre puntualmente cuando necesita features que el nuevo no tiene

---

## Features del ERP nuevo (al día)

| Feature | Estado | Donde |
|---|---|---|
| Audit Verify/Flag/Skip | ✅ keyboard + click | DetailPane header |
| Watermark per-photo (Auto/Force/Gemini) | ✅ hover sobre foto | DetailPane gallery |
| Watermark batch modelo / family | ✅ con progress streaming | DetailPane gallery toolbar |
| Lightbox foto fullscreen | ✅ click foto | DetailPane gallery |
| Multi-select fotos (ctrl/shift+click) | ✅ + batch delete + R2 cleanup | DetailPane gallery |
| Toggles (Publicado/Featured/SoldOut/Archivado) | ✅ click | DetailPane visibility section |
| Edit modelo type/sleeve | ✅ con SKU regen + DB migration | DetailPane header click "Fan adulto..." |
| Edit family variant | ✅ con SKU regen | DetailPane SPECS dropdown |
| Edit precio + sizes | ✅ auto-save on blur | DetailPane SPECS |
| Crown click primary_modelo_idx | ✅ | FamilyPdpPane variant cards |
| Drag-and-drop modelos cross-family | ✅ ListPane | ListPane buttons |
| Modal Mover (search + crear new family + absorb) | ✅ | DetailPane header "Mover" |
| Delete SKU soft | ✅ + git push | DetailPane header "Delete" |
| Publicar family completo | ✅ verified×modelos + published + price backfill + push | DetailPane bottom verde |
| Coverage modal Mundial 2026 | ✅ tabla expandible 48×6 | Sidebar "Mundial 2026" |
| Sync data (manual cache invalidate) | ✅ | Sidebar bottom |
| Buscar updates (abrir bundle/msi/) | ✅ | Sidebar bottom |
| Push vault button | ✅ con git status indicator | Sidebar bottom |
| Drag-to-reorder fotos en gallery | ✅ con override pattern | DetailPane gallery |

**Todo persiste en `catalog.json` y/o SQLite y se refleja en vault live tras push.**

---

## Issues conocidos / backlog priorizado

### v0.2 candidates (próximo MAJOR-ish bump)

1. **Auto-updater oficial** (~2h work)
   - Tauri plugin-updater + GitHub Releases manifest
   - Genera keypair para signing MSIs
   - App chequea al arranque, descarga + aplica
   - Requiere infra (host del manifest JSON)

2. **Dashboard view** — hoy es placeholder. Nice-to-have:
   - Stats live: N families pending audit, N publicadas, % cobertura Mundial 2026
   - Telemetría tiempo-por-audit (ya en `audit_telemetry` table, no surface)

3. **Inyect-scrapes desde la app** — hoy Diego va al Streamlit. Si lo migramos, el Streamlit muere.

4. **Inventario / Comercial / Órdenes** — items del Sidebar que llevan a páginas vacías. Stub para mantenerse alineado con el Streamlit pero sin contenido.

5. **Bulk-publish** — publicar N families con un click (ej. "publicar todas las CONCACAF verified")

### Nice-to-haves

- Sub-grouping por modelo type dentro del DnD del ListPane (lo quité en v0.1.10 al hacer drag, podés re-agregar con header pseudo-items dragDisabled)
- Editar `team` o `season` (afecta family_id, requiere migration de toda la family)
- Badge dinámico "N/96" del Mundial 2026 en Sidebar
- Photo selection: marker visual de cuál es hero al cambiar order
- Keyboard shortcut para abrir modal Mover (ej. M)

### Tech debts conocidos

- `write_catalog_atomic_keep_cache` está definido en lib.rs pero nunca usado (warning unused). Era para no invalidar cache después de write propio. Ya el mtime check lo hace OK; podés borrar.
- Algunos warnings a11y en CommandPalette + DetailPane (img clickeable, dialog sin tabindex). No críticos.
- `published.ts` (auto-generado por `migrate-published.mjs`) está dead code post-v0.1.1 pero lo mantengo como fallback. Plan: borrar cuando confianza alta.
- El stub `tauriAdapter` con `dynamic import('@tauri-apps/api/core')` pierde tipos (any cast). OK por la naturaleza del lazy import.

---

## Bugs históricos pisados (no repitas)

| Bug | Síntoma | Root cause | Fix |
|---|---|---|---|
| v0.1.0 pantalla negra | App abre con título pero WebView negro | Tauri adapter devolvía catalog rows raw, no Family transformados | Mover transform al adapter Tauri |
| Limpiar todo crashea app | Spinner eterno, app muere | Subprocess Python bloquea main thread Tauri | `async fn` + `spawn_blocking` |
| Limpiar nunca termina | Spinner eterno (más sutil) | Python bridge crashea con UnicodeEncodeError al escribir emoji a stdout cp1252 | `sys.stdout.reconfigure(encoding="utf-8")` |
| Verify no funciona | Click sin efecto | UPDATE audit_decisions cuando row no existe (scraper no seedea) | UPSERT con ON CONFLICT |
| DnD entre families no funciona | Click & drag no hace nada | svelte-dnd-action requiere items con `id`, modelos tienen `sku` | Map items a `{...m, id: m.sku}` |
| Move "missing field source_fid" | Error toast al mover | Tauri auto-convierte camelCase solo en TOP-LEVEL args | `#[serde(rename_all = "camelCase")]` en struct |
| QNaN en vault live | Cards mostraban "QNaN" en precio | catalog.json tiene `price: null`, vault hace Math.min → NaN | Backfill defaults + auto al Publicar family |
| Backfill se "pierde" | Después de backfill + publish, fields vuelven a null | Rust catalog cache stale; publish escribió version vieja | Auto-invalidate cache vía mtime comparison |
| Photos no aparecen | Gallery "0 fotos" pero check dice "(4)" | Race entre $effect y svelte-dnd-action: dndzone disparaba consider con items vacíos | Render directo de modelo.fotos via $derived |

---

## Workflow típico de Diego (referencia)

1. **Ops corre scraper** (separado, vive en `elclub-catalogo-priv/scripts/`) → `catalog.json` se actualiza con N family nuevos
2. Diego abre el ERP → click "Sincronizar datos" → ve las nuevas families en queue
3. Para cada family pending:
   - Click variant → ve PDP del family con N modelos
   - Click un modelo → ve gallery + specs
   - Si fotos DIRTY: click "Limpiar modelo" o per-photo Gemini
   - Si team mal nombrado: click "Mover" → seleccionar family destino o crear nueva
   - Click Verify (V keyboard) cuando OK
4. Cuando todos los modelos verified: click verde **"Publicar family"** → backfill prices + final_verified×N + published=true + commit + push
5. Vault live actualiza en ~30s
6. Repetir para próxima family

**Cadencia esperada:** ~1 album/día (Diego dijo). El ERP debe sostener ese ritmo sin friction.

---

## Entradas comunes para el próximo Claude

Si Diego dice...

| Quote | Probablemente significa |
|---|---|
| "no me funciona X botón" | Falta `onclick` wireado, o `disabled` por estado stale, o el handler crashea en error silently. F12 console primero. |
| "el vault live no muestra Y" | catalog.json en disk no tiene Y → push falló o backfill se "perdió" por cache stale. Chequear `git log` y catalog en HEAD. |
| "drag and drop no anda" | svelte-dnd-action requiere `id` field. Los modelos tienen `sku`. Mapear `{...m, id: m.sku}`. |
| "limpiar tarda eterno" | Subprocess Python bridge crashea silently. Test con `echo {} \| python scripts/erp_rust_bridge.py` directo. |
| "ningún modelo X funciona" | Probablemente UPDATE-only en una tabla que necesita UPSERT, o config check que falla para modelos nuevos. |
| "se cayó el ERP / Not Responding" | Comando Rust sync que llama subprocess. Async-ificar con `spawn_blocking`. |
| "ya están los datos en X pero el ERP no los lee" | Cache stale. Click "Sincronizar datos" o re-armar (mtime auto-invalidate ya está pero sirve check). |
| "nuevo bug" | Antes de codear: 1) F12 console + screenshot, 2) test el bridge/SQL/path/state directo en Python o sqlite3 para aislar, 3) recién después tocar TS/Rust. |

---

## Diego's voice / preferencias UX

- **No es programador.** Confía en el criterio del Claude. Espera explicaciones en criollo, no jerga.
- **"Hace todo lo necesario, te autorizo"** = OK explícito para destructive ops cuando ya discutimos el plan.
- Le gusta el dato de color al final (historia, fun fact, decisión técnica). Mantenerlo si flow lo permite.
- Prefiere **iteración rápida**: rompé algo? Recompilá. No vale la pena debuggear 3h cuando el rebuild es 2 min.
- Acepta que algunas features queden diferidas si el blocker está claro y el path forward concrete. **No invent**ar features sobre la marcha — solo lo que pidió.
- **Diego no testea siempre todos los caminos.** Si reportás "feature X agregada", asegurate que funciona end-to-end con un caso real (Python query, sqlite3, curl) antes de decírselo, no solo `npm run check` pasando.

---

## Cosas que NO debería hacer el próximo Claude

- ❌ Crear `*.md` docs sin que Diego lo pida (este doc es excepción porque LO PIDIÓ explícitamente).
- ❌ Reimplementar el stack Python de imagen processing en JS/Rust. Subprocess es la solución.
- ❌ Modificar `catalog.json` con scripts ad-hoc sin backup automático y sin invalidate del Rust cache.
- ❌ Tocar `published=true` families sin confirmación explícita — son sagradas.
- ❌ Skip the F12 console step cuando Diego reporta un bug. Siempre pedir el error real.
- ❌ Marcar tareas como completadas sin verificar end-to-end (con el catalog/DB real, no solo type check).
- ❌ Usar `wait_with_output()` blocking en commands sync — siempre `async fn` + `spawn_blocking` para subprocess.
- ❌ Asumir que `audit_decisions` tiene row para un SKU. Siempre UPSERT.

---

## Closure: filosofía de la maratón

Esta sesión fue 24h de iteración Tauri puro: 20 versiones, 20 builds, ~10 bugs serios pisados. Diego nunca abrió un IDE. Las decisiones fueron:

1. **Velocity > polish** — bump version on every release, mismo flow para Diego.
2. **Defensive coding** — UPSERT, mtime check, async by default. Cada bug pisado se tradujo en una guard contra clase entera de bugs.
3. **Subprocess Python over rewrite** — el stack de imagen es 5GB de torch+CUDA, no vale la pena rehacer.
4. **UI clear over clever** — botones que dicen exactamente qué hacen, toasts confirman cada acción, no hay magia.

El ERP nuevo es **production-ready para audit day-to-day**. Para reemplazar 100% al Streamlit faltan dashboards + inyect-scrapes + bulk ops. Eso es v0.2.

Suerte, próximo Claude.

— Claude (24/abril/2026, ~18:00)
