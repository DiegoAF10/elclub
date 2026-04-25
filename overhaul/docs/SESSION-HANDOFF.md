# ERP Redesign — Pain Points Backlog Priorizado

> **Generado:** 2026-04-24 PM · sesión P0 inline edit type/sleeve
>
> **Contexto:** Diego pidió overhaul UX del ERP. P0 (UI inline edit) entregado en
> v0.1.22 (`feat: edit modelo type/sleeve UI inline`). Este doc lista los demás
> pain points observados durante audit de Brazil home/away + lectura del código,
> priorizados para que Diego elija qué implementar próximo.
>
> **Cómo leer:** Cost = estimación honesta de implementación (Rust + frontend + smoke test).
> Impact = 1 (nice-to-have) a 5 (bloquea workflow diario). Risk = probabilidad de
> regresión silenciosa o scope creep.

---

## Backlog priorizado

| ID | Título | Cost (h) | Impact | Risk | Files |
|----|--------|---------:|:------:|:----:|-------|
| **B1** | "Ver en Yupoo" button per modelo (link al álbum) | 0.5 | 4 | low | `DetailPane.svelte` header |
| **A1** | Estandarizar `window.confirm`/`window.prompt` con modal reusable | 2 | 4 | low | nuevo `ConfirmModal.svelte` + 8 callsites |
| **E1** | Warning visual + "Auto-fix primary" si viola L16 priority | 1.5 | 4 | med | `FamilyPdpPane.svelte` + helper TS |
| **B2** | Badge "?Stale" si URLs no tienen `?v=` reciente (>48h) | 1 | 3 | low | `DetailPane.svelte` gallery render |
| **F1** | Dashboard "N photos pending watermark across catalog" | 3 | 3 | med | nueva ruta `/pending` o widget Sidebar |
| **D1** | "Refetch desde álbum" one-click per modelo | 4 | 4 | high | bridge Python nuevo cmd + Rust + UI |
| **B3** | "Verificar contra Yupoo" — MD5 binary diff inline | 5 | 3 | high | bridge Python + UI side panel |
| **G1** | Diff visualizer side-by-side (catalog vs álbum yupoo first photo) | 4 | 3 | med | nuevo `PhotoDiffPanel.svelte` |
| **L1** | Pre-publish check: warning si meta_country/conf falta o supplier_gap | 1 | 4 | low | `DetailPane.svelte` publish button |
| **K1** | Cleanup zombie families (`modelos: []`) post-`move_modelo absorb_all` | 1 | 2 | low | bridge Python + script Rust |
| **J1** | Backfill inline al publicar (`set_family_published` corre meta backfill) | 2 | 5 | med | `lib.rs` set_family_published |
| **I1** | Sync hero al reorder en TODOS los lugares (no solo update_gallery_order) | 1 | 3 | med | `lib.rs` audit otros callsites |
| **H1** | Hotkey `E` para abrir EditModeloPanel + `M` para Mover modal | 0.5 | 2 | low | `DetailPane.svelte` keydown handler |

**Total si se hace todo:** ~26h. Recomendado para v0.2: **B1 + A1 + E1 + L1 + J1** (~10h, alto impact-to-cost).

---

## Detalles

### B1 — "Ver en Yupoo" button (P0 candidato)

**Cost:** 0.5h · **Impact:** 4 · **Risk:** low

`modelo.album_id` y `modelo.store` ya existen en el catalog (post-Mundial parser).
URL pattern: `https://{store}.x.yupoo.com/albums/{album_id}?uid=1`. Falta solo un
botón que abra `window.open(url, '_blank')`.

Diego pasó las URLs manualmente en chat para los 6 SKUs Brazil. Ahorro: 30s × N
SKUs auditados = 5-10 min/sesión.

**Edge case:** modelos sin `album_id` (legacy pre-Mundial) → disabled state con
tooltip "Sin album_id (modelo legacy)". 5 LOC en `DetailPane.svelte` header.

---

### A1 — ConfirmModal reusable

**Cost:** 2h · **Impact:** 4 · **Risk:** low

8 callsites de `window.confirm`/`window.prompt` en `DetailPane.svelte`:
- L186: confirm "soft delete photo"
- L196: confirm "delete photo + R2"
- L232: prompt new size value
- L567: confirm delete SKU
- L627, 637, 658: handleEditModelo (ELIMINADAS en P0 ✓)
- L770: confirm batch clean

Cada `window.*` rompe flow porque el browser modal está fuera del design system,
no permite focus en form fields paralelos, y bloquea la app thread. Estandarizar
con `<ConfirmModal>` que acepta props `{title, body, confirmLabel, danger?, onConfirm}`.

**Pattern:** mismo que `MoveModeloModal.svelte`. Reusable para futuras ops.

---

### E1 — L16 primary priority validator

**Cost:** 1.5h · **Impact:** 4 · **Risk:** med (validar que el helper TS coincide con parser Python)

YUPOO-SCRAPING-PLAYBOOK.md L16 define la priority canonical:
```
fan_adult/short > player_adult/short > retro_adult > fan_adult/long > woman > kid > baby
```

Parser ya respeta esto post-2026-04-24 wipe. Pero ERP no valida — Diego puede
asignar primary a kid manualmente (crown click) y el catalog queda con primary
"sub-óptimo" sin warning.

**Implementación:**
- Helper TS `evaluatePrimaryPriority(modelos, currentIdx)` → `{ optimal: number, isViolation: boolean }`
- `FamilyPdpPane.svelte`: si `isViolation`, banner amarillo "Primary violates L16: should be {optimal}" + botón "Auto-fix"
- Auto-fix llama `adapter.setPrimaryModeloIdx(family.id, optimal)` (ya existe)

**Risk:** el helper TS debe matchear exactamente el orden Python. Test unitario
con 5 cases (todos los tipos) antes de mergear.

---

### B2 — Stale badge si URLs sin `?v=` reciente

**Cost:** 1h · **Impact:** 3 · **Risk:** low

L19 del playbook: CDN cache eternal sin cache-bust = ERP stale post-refetch.
Convención actual: post-watermark las URLs llevan `?v=YYYYMMDD-HHMMSS`. Modelos
audited recientemente tienen este queryparam.

Modelos SIN `?v=` o con `?v=` >48h indican que la R2 puede estar
desincronizada del catalog (caso L18 Brazil home). El ERP podría:
- Render badge "⚠ ?Stale" sobre la card del modelo en `ListPane`
- Tooltip: "URLs sin cache-bust reciente — verificar contra Yupoo si fotos sospechosas"

**Cuidado:** modelos legacy pre-watermark (sin watermark applied yet) NO son
stale, son DIRTY. Distinguir: stale = `?v=` ausente AND gallery populada vs
DIRTY = foto requiere watermark (campo separado).

---

### F1 — Dashboard "Pending watermark across catalog"

**Cost:** 3h · **Impact:** 3 · **Risk:** med

Hoy hay batchClean per-family (botón en gallery toolbar). Pero no hay vista
agregada de "cuántas fotos DIRTY hay total". Diego no sabe si tiene 50 o 500
fotos pendientes.

**Implementación:**
- Vista nueva `/pending` o widget en Sidebar
- Reads del catalog: `sum(modelo.fotos.filter(f => f.isDirty).length)` cross-family
- Tabla con columnas `family | modelo | N dirty | last touched | action`
- Botón "Limpiar TOP 20" → invoca batch_clean_family in sequence con progress

**Risk:** scope creep — fácil que se convierta en "dashboard general" con stats.
Mantener focused en watermarks pendientes solamente.

---

### D1 — "Refetch desde álbum" one-click

**Cost:** 4h · **Impact:** 4 · **Risk:** high (subprocess Python complejo + edge cases)

Workflow actual cuando Diego sospecha R2 stale (caso L18):
1. Abrir terminal
2. Editar `scripts/patch-bra-home-pre-refetch.mjs` (clear gallery + hero)
3. `node scripts/fetch-modelo-galleries.mjs --include-primary`
4. Cache-bust patch script

~3 min × N SKUs.

**Implementación:**
- Bridge Python new cmd `refetch_modelo_from_album(family_id, modelo_idx)` que:
  1. Backup catalog
  2. Clear `modelo.gallery` + `modelo.hero_thumbnail`
  3. Invoca `fetch-modelo-galleries.mjs` con scope filtrado a este modelo
  4. Apply cache-bust `?v=YYYYMMDD-HHMMSS` post-fetch
  5. Sync top-level si primary
- Rust command `refetch_modelo_from_album` (async + spawn_blocking)
- UI: botón "↻ Refetch desde álbum" en gallery toolbar con confirm (destructive)

**Risk:**
- Rate limit Yupoo si Diego refetcha 10 modelos rápido. Necesita cooldown.
- Si el álbum cambió en Yupoo, las URLs nuevas pueden no matchear el SKU original
- L18 fix sistémico (`album_id_at_fetch`) ayudaría — pero está PARKED

**Pre-requisito recomendado:** implementar el fix sistémico de L18 antes (fetch
script trackea `album_id_at_fetch`), sino este botón hereda el mismo bug.

---

### B3 — "Verificar contra Yupoo" — MD5 binary diff

**Cost:** 5h · **Impact:** 3 · **Risk:** high

Template existe en `elclub-catalogo-priv/scripts/diagnose-brazil.mjs`: descarga
foto del álbum Yupoo + foto de R2 actual + compara MD5. Si difieren → R2 stale.

**Implementación:**
- Bridge Python new cmd `verify_modelo_against_yupoo(family_id, modelo_idx)`
- UI: botón "✓ Verificar" en gallery toolbar
- Output: panel side con "✓ N/M match", "⚠ X mismatch (URLs en R2 stale)"

**Risk:**
- Network-bound, lento (~10s × N fotos)
- Yupoo rate-limit cascade (L10) — usar mismo `FETCH_CONCURRENCY` env
- Si Yupoo serves diferentes JPEG quality on each request, MD5 puede divergir
  sin que R2 esté stale → false positive. Considerar threshold de bytes en vez
  de MD5 strict.

---

### G1 — Diff visualizer side-by-side

**Cost:** 4h · **Impact:** 3 · **Risk:** med

Cuando Diego sospecha "Brazil 2026 Women's Home" tiene foto wrong, hace round-trip
mental: abre Yupoo álbum (manual) + ERP gallery + compara visualmente.

**Implementación:**
- Side panel que muestra:
  - Izquierda: `gallery[0]` actual del modelo (R2 URL)
  - Derecha: thumbnail del álbum Yupoo (scrape on-demand via WebFetch)
  - Footer: "✓ Match" o "⚠ Probable mismatch — refetch?"

**Risk:**
- Yupoo no permite hotlink → tendríamos que descargar la imagen y re-servir
  (puede caer en TOS issues si el usuario no es Diego). Solo en .exe local OK.
- WebFetch desde el browser/Tauri requiere CORS handling.

---

### L1 — Pre-publish meta validation

**Cost:** 1h · **Impact:** 4 · **Risk:** low

Bug pisado en sesión 2026-04-24 noche: Czech Republic 2026 home se publicó sin
meta_confederation porque no estaba en `wc2026-classified.json`. Vault le mostró
sin bandera + no aparecía en confederation cards.

**Implementación:**
- Antes de aplicar `set_family_published(true)`, validar:
  - `meta_country !== null`
  - `meta_confederation !== null`
  - Si season incluye 2026 → `wc2026_eligible !== null`
  - `modelos[primary].price > 0`
- Si alguno falla, mostrar warning bloqueante con botón "Backfill ahora" que
  invoca `backfill_catalog_meta.py` via bridge

**Risk:** low — es validation, no muta. Si backfill falla (country no en
classified), el warning persiste y Diego sabe que tiene que agregar el alias.

---

### K1 — Cleanup zombie families post-absorb

**Cost:** 1h · **Impact:** 2 · **Risk:** low

`move_modelo --absorb_all` deja la family fuente con `modelos: []` (zombie). Hoy
no se borra. Ningún problema funcional pero contamina counts y aparece en
listings vacíos.

**Implementación:**
- Bridge Python: en `cmd_move_modelo` después de absorb, si `source_left_empty`
  AND `source_fam.published === false`, borrar la entry del catalog
- Migration: query `delete_log` para soft-deletear zombies existentes

---

### J1 — Backfill inline al publicar

**Cost:** 2h · **Impact:** 5 · **Risk:** med

Bug recurrente documentado en handoff prev: cada `wipe + re-import + publish` deja
families sin `meta_confederation/price` porque `set_family_published` no llama
backfill. Diego notó precios `QNaN` post-publish hoy.

**Implementación opciones:**
- **(a)** Inline en Rust `set_family_published`: leer `wc2026-classified.json` +
  fill missing meta antes del write atomic. Sin subprocess.
- **(b)** Subprocess `backfill_catalog_meta.py` pre-commit en publish.

Recomendado: (a). Más simple, sin overhead.

**Risk:** lock contention si publish + backfill corren a la vez en sesiones
paralelas. `invalidate_catalog` post-write debe ser sufficient.

---

### I1 — Sync hero al reorder en TODOS los lugares

**Cost:** 1h · **Impact:** 3 · **Risk:** med

v0.1.21 fixeó `update_gallery_order` para sincronizar hero. Falta auditar:
- `move_modelo` cuando target tiene primary diferente — ¿hero correcto post-move?
- `edit_modelo_type` si cambia primary order
- `set_family_variant` si afecta SKU del primary

**Implementación:** audit grep `gallery.*\[0\]\|primary_modelo_idx` en lib.rs +
asegurar que todos los callsites sincronizan family.hero_thumbnail.

**Risk:** silent breakage si se introduce nuevo callsite y no se actualiza el
sync. Considerar helper `fn sync_family_hero_from_primary(fam: &mut Value)` que
todos los commands llamen al final.

---

### H1 — Hotkeys

**Cost:** 0.5h · **Impact:** 2 · **Risk:** low

Diego ya tiene `V/F/S` para Verify/Flag/Skip. Faltan:
- `E` → toggle EditModeloPanel
- `M` → abrir Mover modal
- `R` → refetch desde álbum (post D1)
- `Y` → "Ver en Yupoo" (post B1)

Single line per binding en el keydown handler de `DetailPane.svelte`. Tooltip
update en chip + botón.

---

## Pain points adicionales detectados durante implementación P0

### N — `state_referenced_locally` warnings en componentes con initial state

Svelte 5 warns en `let x = $state(props.foo)` patterns. Es intencional cuando
querés capturar initial value y el parent garantiza desmontaje al cambiar
props. Pero el warning es molesto — appears en `EditModeloPanel.svelte` líneas
37-38 + posiblemente otros componentes.

**Acción:** documentar el pattern en `docs/svelte-patterns.md` (NO existe) o
silenciar con comentario `// svelte-ignore state_referenced_locally`.

### O — Dead code: `write_catalog_atomic_keep_cache`

Cargo warning desde v0.1.20: función definida en `lib.rs:218` nunca usada. Era
para no invalidar cache después de write propio. Ya el mtime check lo hace OK.
Borrar = -10 LOC.

### P — `published.ts` legacy fallback dead code

Auto-generated por `migrate-published.mjs` (script de bootstrap inicial). Post-v0.1.1
nunca leído porque el adapter `listFamilies()` reads del catalog directo. ~22 families
hardcoded. Borrar = simplifica + permite eliminar el script de migración.

### Q — Type duplicación entre Rust y TS

`MoveModeloArgs`, `EditModeloTypeResult`, etc. están definidos 2 veces (Rust struct
+ TS interface). Drift potencial — si alguien cambia el Rust struct pero olvida el
TS, el invoke falla en runtime. Considerar:
- Generar types desde Rust con `tauri-bindgen` o similar
- O documentar invariante "Rust + TS son source-of-truth paralelos, sync manual"

---

## Cómo elegir cuál implementar próximo

**Si tenés 1 hora suelta:** B1 (link Yupoo) + L1 (pre-publish validation) + H1 (hotkeys)
→ alto impact, mínimo risk, tres wins en una pasada. **Total: 2h, Impact: 10**.

**Si tenés tarde libre:** A1 (ConfirmModal) — refactor que paga dividendos cada
sesión futura. **2h, Impact: 4**.

**Si encontrás otro bug L18-style mañana:** D1 + B3 (refetch + verify). El
trabajo se justifica solo si el bug recurre. **9h, Impact: 7**.

**Si Diego se queja de "tengo que correr backfill manual":** J1 + L1.
**3h, Impact: 9**.

---

## Notas para la próxima sesión

- **NO romper adapter browser.ts** — todos los nuevos commands deben tirar
  `NotAvailableInBrowser` en el browser fallback.
- **Mantener V/F/S keyboard** — no shadowear con nuevos hotkeys.
- **Test pattern:** `npm run check` PASS antes de commit. Smoke `npm run dev` +
  click manual antes de declarar done.
- **Version bump siempre** en cada release (Cargo.toml + tauri.conf.json en sync).
  Windows trata MSIs misma version como reinstall.
