# Admin Web — Documentación Maestra

> **Hub central** del proyecto Admin Web. Indexa todo el material producido (specs, plans, mockups, docs técnicos) generado en la sesión brainstorming + sesión nocturna del 2026-04-26 / 27.
>
> **Si vas a implementar Admin Web:** lee este README primero, después navega a los docs específicos según necesites.

---

## ¿Qué es Admin Web?

**Admin Web** es el módulo del ERP Tauri (`el-club/overhaul/`) donde Diego gestiona el **contenido completo del sitio web público** de El Club. CMS específico, multi-producto, identidad gamer (FM/CK3/EU4), densidad organizada por capas. Vive **dentro del ERP local**, no online.

**5 sub-módulos + Home:**
- 🏠 **Home** — KPIs + Accesos + Inbox de eventos accionables (CK3-style)
- 🗄️ **Vault** — catálogo Q435 (lo más urgente, 4 tabs: Queue · Publicados · Grupos · Universo)
- 📦 **Stock** — garantizadas Q475 con drops (cascarón, profundo en R7.1)
- 🎲 **Mystery** — pool sorpresa con drops temáticos (cascarón, profundo en R7.2)
- 🌐 **Site** — landing + branding + comunicación + comunidad + meta (cascarón, profundo en R7.3)
- ⚙️ **Sistema** — health + operaciones + config + audit (cascarón, profundo en R7.4)

**Scope estricto:** maneja qué/cómo aparece en el sitio. **NO toca** ventas, funnel, ads, customers, inbox cliente, pedidos físicos, inventario o finanzas — eso vive en módulos hermanos del ERP (Comercial, Operativa, Inventario, FÉNIX).

---

## Material producido (índice)

### 📋 Specs y diseño

| Doc | Path | Tamaño | Para qué |
|---|---|---|---|
| **Spec principal** | `specs/2026-04-26-admin-web-design.md` | ~700 líneas | Diseño completo aprobado · 14 secciones |
| **SQL Migration** | `specs/admin-web/schema-migration.sql` | 18 tablas + 4 columnas | Listo para aplicar a `elclub.db` |
| **TypeScript Types** | `specs/admin-web/types.ts` | ~600 líneas | Interfaces canonical para 60+ Tauri commands |
| **Tags Seed** | `specs/admin-web/tags-seed.json` | 11 tipos · 110 tags | Catálogo pre-poblado completo |
| **Inbox Events Catalog** | `specs/admin-web/inbox-events-catalog.json` | 36 eventos | Detector queries + auto-dismiss rules |
| **ADRs** | `specs/admin-web/adr-decisiones-tecnicas.md` | 32 decisiones | Stack + patterns pre-resueltos |
| **Storyboards** | `specs/admin-web/storyboards-user-journeys.md` | 10 journeys | Acceptance criteria funcional |
| **Cheat Sheet + Diagramas** | `specs/admin-web/cheat-sheet-y-diagramas.md` | Atajos + 7 diagramas mermaid | Reference rápido |

### 🎨 Mockups visuales (HTML interactivos)

Todos en `el-club/overhaul/.superpowers/brainstorm/508-1777229441/content/`:

| # | Mockup | Cubre |
|---|---|---|
| 1 | `mockup-1-home.html` | Home con KPIs + Accesos + Inbox |
| 2 | `mockup-2-vault-universo.html` | Tabla densa con filters + presets + bulk |
| 3 | `mockup-3-stock-calendario.html` | Timeline visual de drops 5 meses |
| 4 | `mockup-4-vault-queue.html` | Audit overlay FM-style |
| 5 | `mockup-5-vault-publicados.html` | Cards curatoriales con smart filters |
| 6 | `mockup-6-vault-grupos.html` | Tags manager + drill modal Mundial |
| 7 | `mockup-7-mystery-pool-reglas.html` | Pool con weights + Reglas modal funcional |
| 8 | `mockup-8-site-paginas-branding.html` | Branding con preview live + paleta |
| 9 | `mockup-9-sistema-status.html` | Health dashboard tipo Grafana |

Abre cualquiera en browser para ver renderizado.

### 📅 Plans de implementación

| Plan | Path | Estimación | Cubre |
|---|---|---|---|
| **R7 — Skeleton + Vault** | `plans/2026-04-26-admin-web-r7-skeleton-plus-vault.md` | 10-15 días | Versión high-level |
| **R7 micro-tasks** | `plans/2026-04-26-admin-web-r7-micro-tasks.md` | 53 sub-tasks | Versión granular para ejecutar |
| **R7.1 — Stock profundo** | `plans/2026-04-26-admin-web-r7.1-stock-profundo.md` | 5-7 días · 28 tasks | Override engine, calendario, conflicts, templates |
| **R7.2 — Mystery profundo** | `plans/2026-04-26-admin-web-r7.2-mystery-profundo.md` | 5-7 días · 26 tasks | Algoritmo random ponderado + tests + integración |

---

## Orden recomendado de lectura

### Si querés entender el QUÉ (5-10 min)

1. Este README (visión general)
2. `specs/2026-04-26-admin-web-design.md` sección 1-3 (resumen ejecutivo + arquitectura)
3. Mockup-1-home.html (open en browser)

### Si querés entender el CÓMO (30-60 min)

1. Este README
2. `specs/2026-04-26-admin-web-design.md` completo (700 líneas)
3. `specs/admin-web/storyboards-user-journeys.md` (acceptance criteria)
4. Recorrer los 9 mockups HTML
5. `specs/admin-web/cheat-sheet-y-diagramas.md` (overview visual)

### Si vas a IMPLEMENTAR (revisión completa, 1-2 horas)

**Pre-flight:**
1. Confirmar que Comercial R1 está mergeado
2. Backup `elclub.db`
3. Crear branch `admin-web-r7`

**Lectura técnica:**
1. `specs/2026-04-26-admin-web-design.md` (spec completo)
2. `plans/2026-04-26-admin-web-r7-micro-tasks.md` (plan granular)
3. `specs/admin-web/adr-decisiones-tecnicas.md` (32 decisiones técnicas resueltas)
4. `specs/admin-web/types.ts` (interfaces)
5. `specs/admin-web/schema-migration.sql` (revisar antes de aplicar)
6. `specs/admin-web/inbox-events-catalog.json` (catálogo de eventos)
7. `specs/admin-web/tags-seed.json` (seed inicial)
8. `specs/admin-web/storyboards-user-journeys.md` (smoke tests post-build)

---

## Principios y mental model

### Diego como strategy gamer

Diego piensa como FM/CK3/EU4/SimCity — gestionar El Club es la versión adulta de esos juegos con réditos reales. El Admin Web traduce eso:

- **Densidad de información organizada por capas** — FM Squad detail style, no Notion minimalism
- **Drilldown infinito** — click en cualquier entidad revela ventana grande con TODO su detalle + acciones
- **Eventos demandan decisiones** — Inbox del Home tipo CK3 popup queue, prioriza acción sobre métricas
- **Múltiples lentes sobre la misma data** — vista por producto Y vista cross-producto, switchable
- **Causalidad visible** — del scrap al audit al published; del override al drop al sitio
- **Time control** — calendario de drops + audit log filtrable por tiempo
- **Sense of agency** — ninguna acción es "automágica", Diego puede tweak todo
- **Map / Ledger duality** — Calendario (visual) + Universo (tabla densa) son lentes de la misma data

### Estética visual: retro gaming / terminal

- **Dark mode default:** #0a0b0d background, #4ade80 terminal green accent, #fbbf24 amber warning, #f43f5e red alert
- **Monospace para SKUs/IDs/numbers:** tabular-nums para alineación
- **Display fonts UPPERCASE + letter-spacing 0.1em** para section labels
- **Status pills con dot prefix:** `● LIVE`, `● OFF`, `● PEND`
- **Density-friendly:** info por unidad de espacio alta, whitespace para separación no para "breathing"
- **NO Notion/Linear/Stripe minimalism**

---

## Decisiones core (recap rápido)

13 decisiones aprobadas en sesión brainstorming (D1-D13):

| # | Decisión |
|---|---|
| D1 | Sidebar por producto: Vault · Stock · Mystery · Site · Sistema |
| D2 | Home híbrido: KPIs + Accesos + Inbox de eventos |
| D3 | Vault tiene 4 tabs: Queue · Publicados · Grupos · Universo |
| D4 | 5 estados primarios + flags + overrides Alt B (drops independientes por producto) |
| D5 | 10 tipos de tags + cardinalidad por tipo + mix manual/auto + país sincronizado |
| D6 | Universo: toggle tabla/grid, presets, bulk, URL state, thumb visible |
| D7 | Publicados: cards curatoriales, 6 smart filters, modal reutilizado, drop creator inline |
| D8 | Home: 8 KPIs sparkline + 5 tiles accesos + 5-7 inbox + ⌘K + atajos Vim |
| D9 | Stock: 3 tabs (Drops · Calendario · Universo) |
| D10 | Mystery: 3 tabs + Reglas modal (⚙) + 3 caminos al pool |
| D11 | Site: 6 tabs EXPANDIDO (Páginas + Branding + Componentes + Comunicación + Comunidad + Meta+Tracking) |
| D12 | Sistema: 4 tabs (Status · Operaciones · Configuración · Audit) sin Acceso (ERP autentica) |
| D13 | Naming "Admin Web" · vive en ERP Tauri local · sin auth web · branding heredado |

---

## Stack técnico (de los ADRs)

| Capa | Tecnología |
|---|---|
| Framework | SvelteKit 5 (runes) |
| Styling | Tailwind v4 + CSS variables (para branding dinámico) |
| Backend | Rust (Tauri 2) + Python bridge |
| DB | SQLite con WAL mode |
| Cache | KV de Cloudflare (worker existente) |
| Search | fuse.js |
| DnD | svelte-dnd-action |
| Virtualization | svelte-virtual |
| Validation | zod |
| Charts | SVG custom (sparklines) |
| Calendar | Custom Svelte (no fullcalendar) |
| Block editor | Custom v0, tiptap futuro |
| i18n | N/A v0 (single-user español) |
| Tests | TypeScript types + smoke manual + scripts standalone para Mystery algorithm |

---

## Releases planificados

```
✅ R7        Skeleton + Vault profundo (10-15d) → core funcional
⏳ R7.1      Stock profundo (5-7d) → drops engine + calendario interactivo
⏳ R7.2      Mystery profundo (5-7d) → algoritmo + integración wizard
⏳ R7.3      Site profundo (10-14d) → editor de bloques + comunicación + comunidad
⏳ R7.4      Sistema profundo (5-7d) → operaciones + audit completo
⏳ R7.5      Polish + Power features (3-5d) → ⌘K + atajos + animaciones
```

**Pre-requisito de R7:** Comercial R1 mergeado y deployed (✅ shipped 2026-04-26 v0.1.28).

---

## Cómo está organizado este folder

```
el-club/overhaul/docs/superpowers/
├── specs/
│   ├── 2026-04-26-admin-web-design.md          ← spec principal (aprobado)
│   ├── 2026-04-26-comercial-design.md          ← spec hermano (Comercial)
│   └── admin-web/                              ← sub-folder con material técnico
│       ├── README.md                            ← este doc
│       ├── schema-migration.sql                 ← SQL listo para aplicar
│       ├── types.ts                             ← TypeScript types canonical
│       ├── tags-seed.json                       ← 110 tags pre-poblados
│       ├── inbox-events-catalog.json            ← 36 eventos detector queries
│       ├── adr-decisiones-tecnicas.md           ← 32 ADRs
│       ├── storyboards-user-journeys.md         ← 10 user flows
│       └── cheat-sheet-y-diagramas.md           ← atajos + 7 mermaid diagrams
└── plans/
    ├── 2026-04-26-admin-web-r7-skeleton-plus-vault.md   ← plan high-level R7
    ├── 2026-04-26-admin-web-r7-micro-tasks.md           ← plan granular R7
    ├── 2026-04-26-admin-web-r7.1-stock-profundo.md      ← plan R7.1
    └── 2026-04-26-admin-web-r7.2-mystery-profundo.md    ← plan R7.2

el-club/overhaul/.superpowers/brainstorm/508-1777229441/content/
├── mockup-1-home.html
├── mockup-2-vault-universo.html
├── mockup-3-stock-calendario.html
├── mockup-4-vault-queue.html
├── mockup-5-vault-publicados.html
├── mockup-6-vault-grupos.html
├── mockup-7-mystery-pool-reglas.html
├── mockup-8-site-paginas-branding.html
└── mockup-9-sistema-status.html

elclub-catalogo-priv/docs/
├── LOG.md                                       ← entry de sesión brainstorming + nocturna
└── PROGRESS.md                                  ← flag "Admin Web spec done, build post-R1"
```

---

## Próximos pasos

### Para Diego (review)

1. ☐ Recorrer los 9 mockups HTML (15-30 min)
2. ☐ Leer storyboards de user journeys (15 min) — confirmar que los 10 flows son correctos
3. ☐ Revisar ADRs si hay alguna decisión técnica que querés cambiar (10 min skim)
4. ☐ Aprobar el plan R7 micro-tasks o pedir ajustes
5. ☐ Cuando Comercial R1 esté shipped (✅) y banda mental disponible: arrancar R7

### Para implementación (cuando Diego dé luz verde)

1. ☐ `git checkout -b admin-web-r7`
2. ☐ `cp el-club/erp/elclub.db el-club/erp/elclub.backup-before-admin-web-r7.db`
3. ☐ Aplicar `schema-migration.sql` (T1.1 del plan micro-tasks)
4. ☐ Ejecutar `tags-seed.json` (T1.2)
5. ☐ Continuar con T1.3 (TypeScript types)
6. ☐ ... seguir las 53 micro-tasks en orden

### Sesiones futuras

- R7.1 (Stock profundo) cuando R7 shipped
- R7.2 (Mystery profundo) cuando R7.1 shipped
- R7.3 (Site profundo) — el más grande, posiblemente dividir en R7.3.1 y R7.3.2
- R7.4 (Sistema profundo)
- R7.5 (Polish + Power features)

---

## Contactos / Coordinación

- **Owner del proyecto:** Diego Arriaza Flores
- **Strategy session:** elclub-catalogo-priv repo (LOG.md, PROGRESS.md, HANDOFF.md)
- **Cross-bucket dependencies:**
  - Comercial (módulo hermano del ERP) — coordinar via PROGRESS.md
  - elclub-catalogo-priv (Vault frontend) — schema sync requerido
  - ventus-system/backoffice (worker) — webhooks + cron handlers

---

## Métricas de la sesión que produjo todo esto

```
Sesión brainstorming (~2h interactivas):
  - 13 decisiones core aprobadas
  - 1 spec principal (~700 líneas)
  - 3 mockups HTML iniciales

Sesión nocturna preparatoria (~9h autónomas):
  - 6 mockups HTML adicionales (total 9)
  - 3 plans de implementación (R7, R7.1, R7.2)
  - 8 docs técnicos (SQL, types, seed, eventos, ADRs, storyboards, cheat sheet, README)
  - ~80 sub-tasks granulares

Output total:
  - 9 mockups HTML interactivos
  - 4 plans (1 high-level + 1 micro + 2 sub-releases)
  - 8 docs técnicos standalone
  - 1 spec principal
  - ~6,500 líneas de markdown + ~600 líneas TypeScript + ~300 líneas SQL + JSON

Estimación de tiempo ahorrado en R7:
  3-5 días (de 10-15d a 7-10d)
```

---

**Última actualización:** 2026-04-27 (sesión nocturna preparatoria)

**Status del proyecto:** SPEC + PREP COMPLETOS · pendiente arrancar implementación R7 cuando Diego decida.
