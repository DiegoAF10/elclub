# Admin Web — Cheat Sheet + Diagramas

## 1. Atajos teclado completos

### Globales (cualquier vista)

| Atajo | Acción |
|---|---|
| `⌘K` / `Ctrl+K` | Abre Command Palette (búsqueda + acciones) |
| `g h` | Go to Home |
| `g v` | Go to Vault (último tab) |
| `g s` | Go to Stock |
| `g m` | Go to Mystery |
| `g w` | Go to Site (web) |
| `g c` | Go to Sistema (config) |
| `?` | Mostrar cheat sheet de atajos |
| `Esc` | Cerrar modal/overlay actual |
| `Cmd+B` | Toggle sidebar interno colapsado/expandido |
| `Cmd+,` | Configuración (Sistema > Configuración) |

### Vault > Queue (modo Audit)

| Atajo | Acción |
|---|---|
| `V` | Verify (aprobar la jersey actual) |
| `F` | Flag for ERP review |
| `S` | Skip a la siguiente sin decisión |
| `D` | Delete (con confirm) |
| `↑` / `↓` | Navegar entre jerseys de la queue |
| `j` / `k` | Alt navegar (Vim style) |
| `Tab` | Ciclar modelo primary entre los modelos disponibles |
| `E` | Editar specs panel inline |
| `Shift+T` | Asignar tag (abre modal) |
| `1-9` | Quick set tier (1=T1, 2=T2, etc.) |
| `R` | Re-fetch foto |

### Vault > Publicados / Universo

| Atajo | Acción |
|---|---|
| `/` | Focus search input |
| `Ctrl+A` | Select all visible |
| `Esc` | Deselect todo |
| `Space` | Toggle select item bajo cursor (en table) |
| `Enter` | Abrir modal del item activo |
| `Cmd+E` | Export selection a CSV |
| `Cmd+P` | Promover a Stock (en multi-select) |
| `Cmd+M` | Promover a Mystery (en multi-select) |
| `Cmd+T` | Toggle tag bulk |
| `Cmd+Shift+A` | Archivar bulk |
| `Cmd+Shift+D` | Eliminar bulk (con confirm fuerte) |

### Stock / Mystery — Calendario

| Atajo | Acción |
|---|---|
| `← / →` | Mes anterior / siguiente |
| `T` | Hoy (jump to current month) |
| `1` / `2` / `3` | Toggle Sem / Mes / Trim view |
| `N` | Nuevo drop (modal create) |
| `Click block` | Editar drop |
| `Shift+Click block` | Multi-select drops |
| `Drag block` | Mover fecha (con confirm) |

### Universo (table densa)

| Atajo | Acción |
|---|---|
| `↑↓` | Navegar rows |
| `→ / ←` | Navegar columnas |
| `Space` | Toggle checkbox row |
| `Enter` | Abrir modal del row |
| `Cmd+Click header` | Toggle visibility de columna |
| `Shift+Click header` | Multi-sort (sort secundario) |

### Reglas Mystery modal

| Atajo | Acción |
|---|---|
| `Cmd+S` | Guardar reglas |
| `Cmd+Z` | Reset a defaults |
| `Esc` | Cancelar (sin guardar) |

---

## 2. Diagrama Mermaid: Transiciones de estado del jersey

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Scrap + Parse (sin fetch)

    DRAFT --> QUEUE: FETCH OK + SEED (auto)
    DRAFT --> REJECTED: Decisión manual<br/>"esto no va"

    QUEUE --> PUBLISHED: Audit aprueba (V)
    QUEUE --> REJECTED: Audit rechaza (D)
    QUEUE --> QUEUE: Skip (S)<br/>(sin transición real)

    PUBLISHED --> ARCHIVED: Diego retira
    PUBLISHED --> PUBLISHED: Editar metadata,<br/>tags, overrides<br/>(sin transición)

    ARCHIVED --> PUBLISHED: Diego revive

    REJECTED --> QUEUE: Cambio de opinión<br/>(raro)

    note right of PUBLISHED
        Flag dirty es ortogonal:
        PUBLISHED + dirty=true
        → genera evento Inbox
        sin cambiar estado
    end note

    note left of DRAFT
        Flag scrap_fail aplica solo
        a DRAFT. Bloquea move-to-QUEUE
        hasta re-scrap exitoso.
    end note
```

## 3. Diagrama Mermaid: Flujo de override (Stock/Mystery)

```mermaid
stateDiagram-v2
    [*] --> NoOverride: Jersey en Vault PUBLISHED

    NoOverride --> Draft: Diego clica<br/>Promover a Stock

    Draft --> Scheduled: Diego setea<br/>publish_at futuro

    Scheduled --> Live: publish_at ≤ now<br/>(automático cron)
    Scheduled --> Ended: Diego cancela<br/>(unpublish_at = now)
    Scheduled --> Draft: Diego limpia publish_at

    Live --> Ended: unpublish_at < now<br/>(automático)
    Live --> Live: Editar precio,<br/>badge, copy<br/>(sin transición)

    Ended --> Live: Diego revive<br/>(set new dates)
    Ended --> Draft: Diego edita<br/>(borra dates)

    Draft --> NoOverride: Diego elimina override

    note right of Live
        Webhook a worker dispara
        CDN invalidation cuando
        Live → Ended o cuando
        precio cambia
    end note
```

## 4. Diagrama Mermaid: Tag cardinality validation

```mermaid
flowchart TD
    A[Diego asigna tag X<br/>a jersey J] --> B{¿Tipo de tag X<br/>cardinality?}

    B -->|many<br/>no excluyente| C[INSERT directo<br/>jersey_tags]

    B -->|one<br/>excluyente| D{¿J ya tiene<br/>otro tag del<br/>mismo tipo?}

    D -->|No| C
    D -->|Sí| E[Validation FAIL<br/>retorna conflicting_tags]

    E --> F{Diego decide:<br/>force_replace?}

    F -->|Sí| G[DELETE old tag<br/>+ INSERT new]
    F -->|No / cancel| H[Operación abortada]

    C --> I{¿Tag X tiene<br/>conditional_rule?}
    G --> I

    I -->|No| J[OK · audit log entry]
    I -->|Sí applies_when| K{¿J cumple<br/>condición?}

    K -->|No| L[Validation FAIL<br/>tag no aplica]
    K -->|Sí| J

    I -->|Sí forbidden_when| M{¿J cumple<br/>forbidden?}
    M -->|Sí| L
    M -->|No| J
```

## 5. Diagrama Mermaid: Pipeline de scrap → Vault

```mermaid
flowchart LR
    A[Diego: Scrap: URL] --> B[Firecrawl Scrape]
    B --> C{¿Markdown<br/>vacío?}

    C -->|Sí L21| D[Fallback HTML directo<br/>scrape-yupoo-direct.mjs]
    C -->|No| E[Normalize Terms]
    D --> E

    E --> F[Wipe non-published<br/>L12 published sagrado]
    F --> G[Parse families]
    G --> H[Fix sleeve mis-labels]
    H --> I[Fetch galleries<br/>FETCH_CONCURRENCY=2]

    I --> J{¿Coverage ≥ 3?<br/>L20 assert}
    J -->|No| K[Add a refetch list]
    J -->|Sí| L[Seed audit_decisions<br/>status='pending']

    K --> M[Re-fetch missing]
    M --> L

    L --> N[Mark qa_priority<br/>desde whitelist]
    N --> O[Generate Pre-Audit HTML]
    O --> P[Diego: revisa flagged]

    P --> Q[Diego pega decisiones]
    Q --> R[Batch Apply<br/>apply-pre-audit-decisions]
    R --> S[ERP Audit Tool<br/>Diego verify/flag/delete]

    S --> T[PUBLISHED]
    S --> U[REJECTED]

    T --> V[vault.elclub.club<br/>público]
```

## 6. Diagrama Mermaid: Inbox events lifecycle

```mermaid
sequenceDiagram
    participant Cron as Cron Detector
    participant DB as SQLite DB
    participant Inbox as Inbox UI
    participant Diego

    loop Cada hora
        Cron->>DB: Para cada EventType:<br/>execute detector_sql
        alt Trigger threshold met
            Cron->>DB: ¿Existe event activo<br/>del mismo type+entity?
            alt No existe
                Cron->>DB: INSERT inbox_events<br/>con metadata + expires_at
            else Existe
                Cron->>DB: skip (no duplicate)
            end
        else Threshold no met
            Cron->>DB: ¿Existe event activo?
            alt Existe
                Cron->>DB: UPDATE resolved_at = now
            end
        end
    end

    Note over DB: Auto-expire según severity:<br/>info: 3d · important: 7d · critical: hasta resolverse

    Diego->>Inbox: Abre Home
    Inbox->>DB: SELECT events activos<br/>WHERE dismissed_at IS NULL<br/>AND resolved_at IS NULL
    DB-->>Inbox: Lista de events
    Inbox-->>Diego: Render con buckets de prioridad

    alt Diego dismisses event
        Diego->>Inbox: Click X
        Inbox->>DB: UPDATE dismissed_at = now
        Inbox-->>Diego: Optimistic remove
    else Diego clica acción
        Diego->>Inbox: Click [ACCIÓN]
        Inbox-->>Diego: Navega a action_target
    end
```

## 7. Diagrama Mermaid: Mystery algorithm flow

```mermaid
flowchart TD
    Start[Order Mystery placed<br/>customer_id] --> A[Load mystery rules<br/>de admin_web_config]

    A --> B[Query active pool<br/>v_mystery_status<br/>computed_status='live']

    B --> C{Pool empty?}
    C -->|Sí| Z[PoolEmptyError<br/>+ Inbox event critical]

    C -->|No| D[Apply exclusions<br/>coverage, dirty, supplier_gap]

    D --> E{Drop temático activo?}
    E -->|Sí substitute| F[Pool ← solo subset del drop]
    E -->|Sí restrict| G[Pool intacto<br/>boost weight subset bias_multiplier]
    E -->|No| H[Pool intacto]

    F --> I
    G --> I
    H --> I[Apply anti-repeat<br/>filter: jerseys recientes a customer]

    I --> J{Pool empty after anti-repeat?}
    J -->|Sí| K[Relax: log warning,<br/>ignore anti-repeat este round]
    K --> L
    J -->|No| L[Apply fairness boost<br/>x2 si never delivered<br/>x1.5 si low deliveries]

    L --> M{Algorithm mode?}
    M -->|preferences/hybrid| N[Filter por wizard prefs<br/>avoided teams/jerseys]
    M -->|uniform/weighted| O

    N --> P{Pool empty after prefs?}
    P -->|Sí| Q[Fallback: ignorar prefs<br/>+ Inbox event critical]
    Q --> O
    P -->|No| O[Selección final]

    O --> R{Mode?}
    R -->|uniform| S[random.choice]
    R -->|weighted/preferences/hybrid| T[random.choices<br/>weights=effective_weight]

    S --> U[Insert mystery_deliveries<br/>algorithm + weight + pool_size]
    T --> U

    U --> V[Return family_id]
```

## 8. Layout visual de los módulos

```
┌──────────────────────────────────────────────────────────────────────┐
│ ERP TAURI (binario local)                                            │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Sidebar global: 📦 Admin Web · 💰 Comercial · 📊 Inventario · ...│ │
│ ├──────────────────────────────────────────────────────────────────┤ │
│ │                                                                    │ │
│ │  ADMIN WEB                                                        │ │
│ │  ┌─────────────────┬────────────────────────────────────────────┐│ │
│ │  │ Sidebar interno │  Body activo                                ││ │
│ │  │  🏠 Home        │                                              ││ │
│ │  │  🗄️ Vault       │  ┌──────────────────────────────────────┐  ││ │
│ │  │   ├ Queue       │  │ Module Header + Tabs                 │  ││ │
│ │  │   ├ Publicados  │  ├──────────────────────────────────────┤  ││ │
│ │  │   ├ Grupos      │  │                                        │  ││ │
│ │  │   └ Universo    │  │  Tab content                          │  ││ │
│ │  │  📦 Stock       │  │  (Cards / Tabla densa / Calendario / │  ││ │
│ │  │   ├ Drops       │  │   Editor / etc.)                      │  ││ │
│ │  │   ├ Calendario  │  │                                        │  ││ │
│ │  │   └ Universo    │  └──────────────────────────────────────┘  ││ │
│ │  │  🎲 Mystery     │                                              ││ │
│ │  │   ├ Pool        │  Modal grande FM-style se invoca           ││ │
│ │  │   ├ Calendario  │  desde cualquier jersey row/card           ││ │
│ │  │   └ Universo    │                                              ││ │
│ │  │  🌐 Site        │  Bulk Action Bar slide-up cuando            ││ │
│ │  │   ├ Páginas     │  multi-select activo                         ││ │
│ │  │   ├ Branding    │                                              ││ │
│ │  │   ├ Componentes │                                              ││ │
│ │  │   ├ Comunicación│                                              ││ │
│ │  │   ├ Comunidad   │                                              ││ │
│ │  │   └ Meta+Track  │                                              ││ │
│ │  │  ⚙️ Sistema     │                                              ││ │
│ │  │   ├ Status      │                                              ││ │
│ │  │   ├ Operaciones │                                              ││ │
│ │  │   ├ Configurac. │                                              ││ │
│ │  │   └ Audit       │                                              ││ │
│ │  └─────────────────┴────────────────────────────────────────────┘│ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘

⌘K Command Palette (overlay) — accesible desde cualquier vista
```

## 9. Color codes leyenda

```
ESTADO PRIMARIO JERSEY:
🟢 PUBLISHED    Verde    Live en sitio público
📥 QUEUE        Amarillo Esperando audit
📝 DRAFT        Gris     Pre-pipeline / scrap_fail
⛔ REJECTED     Rojo     Rechazada definitivamente
💤 ARCHIVED     Gris     Fue published, retirada

OVERRIDE STATUS:
🟢 LIVE         publish_at ≤ now < unpublish_at
⏰ SCHEDULED    publish_at > now
⏸ ENDED        unpublish_at < now
📝 DRAFT        sin publish_at

EVENT SEVERITY (Inbox):
🔴 CRITICAL     Border-left rojo · requiere acción del día
🟠 IMPORTANT    Border-left ámbar · esta semana
🔵 INFO         Border-left azul · sugerencias

FLAGS:
⚠ DIRTY         Jersey publicada con foto rota
🌟 BOOST        Mystery weight con fairness boost activo
🔒 LIMITED      Edición limitada
🎁 EXCLUSIVE    Exclusivo Vault
```

## 10. Comandos de comando palette más comunes

```
⌘K → escribe...

NAVEGACIÓN:
"home"           → Go to Home
"queue"          → Go to Vault > Queue
"publicados"    → Go to Vault > Publicados
"drops"          → Go to Stock > Drops
"calendar"       → Go to Stock > Calendario
"reglas"         → Go to Mystery > Reglas modal
"branding"       → Go to Site > Branding
"status"         → Go to Sistema > Status
"audit log"      → Go to Sistema > Audit

ACCIÓN:
"scrap"          → Trigger scrap nueva categoría
"crear tag"      → Open create tag modal
"crear página"   → Open create page modal
"nuevo drop"     → Open drop creator
"backup ya"      → Trigger backup manual
"deploy"         → Trigger deploy worker

BÚSQUEDA:
"ARG-2026"       → Lista jerseys que matchean
"argentina"      → Jerseys + tag + customer
"mundial"        → Tags + grupos + páginas
"messi"          → Tag narrativa cultural

CONFIG:
"theme"          → Open Branding tab
"shortcuts"      → Open atajos cheat sheet
"logout"         → (a futuro)
```
