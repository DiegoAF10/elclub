# Importaciones IMP-R1: Skeleton + Pedidos + Schema additions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the skeleton del módulo Importaciones dentro del ERP Tauri (sidebar nav, tabs container, pulso bar, list-detail in-place layout) + tab Pedidos funcional con detail pane (Overview/Items/Costos/Pagos/Timeline sub-tabs) + `close_import_proportional()` D2=B (prorrateo por valor USD) + schema additions sobre `elclub.db` compartida con Streamlit. Diego ya puede ver los 2 batches existentes con UX nueva, registrar arrival de IMP-2026-04-18, y cerrar batches con prorrateo proporcional.

**Architecture:** SvelteKit 5 (runes) + Tauri 2 (Rust backend) + SQLite local **compartida con Streamlit** (`C:\Users\Diego\el-club\erp\elclub.db`). Importaciones vive en `overhaul/src/routes/importaciones/` y `overhaul/src/lib/components/importaciones/`. **No hay migration de data** — la DB ya tiene los 2 imports + 51 sale_items + jerseys linkeados. Solo schema additions (ALTER + CREATE TABLE wishlist + free_unit) idempotentes. Detail pane in-place (no modal flotante) para trabajo sostenido sobre un batch.

**Tech Stack:**
- Frontend: Svelte 5 runes, Tailwind v4, lucide-svelte icons
- Backend: Rust (Tauri commands · `rusqlite`), schema en SQL puro
- Storage: SQLite compartida `el-club/erp/elclub.db`
- Verification: `npm run check` (svelte-check + tsc) + `cargo check` + smoke test manual + build MSI gate

**Spec base:** `el-club/overhaul/docs/superpowers/specs/2026-04-27-importaciones-design.md`

**Mockups HD reference:** `el-club/overhaul/.superpowers/brainstorm/1923-1777335894/content/06-mockup-a1-hd-v2.html` (canonical UI · open en browser para reference visual mientras construís componentes Svelte).

**Branch:** `importaciones-r1`

**Versionado al completar:** ERP v0.1.38 → v0.1.39

---

## Patrón de testing en este codebase

El overhaul **no tiene framework de tests automatizados** (no vitest/jest/cargo test instalado). El patrón canonical es:

1. **TypeScript types como contract** — definir tipos antes que implementación.
2. **`npm run check`** debe pasar después de cada step de código frontend (svelte-check + tsc).
3. **`cargo check --manifest-path src-tauri/Cargo.toml`** después de cada step de código Rust.
4. **Smoke test manual** al final de cada task (abrir el ERP en dev, hacer la acción, verificar visualmente).
5. **Build MSI** como gate final del release (`npm run tauri build`).

Cada task adopta este flow: definir types → check → implementar → check → smoke → commit.

**Smoke test entry point:** `cd C:\Users\Diego\el-club\overhaul && npm run tauri dev` (abre la app en hot-reload).

---

## File Structure

### Archivos NUEVOS

```
overhaul/src/lib/components/importaciones/
├── ImportShell.svelte              # Container principal (module-head + tabs + pulso + body)
├── ImportTabs.svelte               # Tab bar (6 tabs internos)
├── PulsoImportBar.svelte           # 6 KPIs persistentes (capital, closed YTD, avg landed, lead time, wishlist, free)
├── ImportListPane.svelte           # 320px sidebar con search + filter chips + rows
├── ImportRow.svelte                # Una row del list (id, cost, meta, status pill, mini-progress, lead time badge)
├── ImportDetailPane.svelte         # Detail container (head + sub-tabs + body)
├── ImportDetailHead.svelte         # detail-id-row + detail-meta + action toolbar arriba
├── ImportDetailSubtabs.svelte      # 5 sub-tabs (Overview/Items/Costos/Pagos/Timeline)
├── tabs/
│   ├── PedidosTab.svelte           # Tab Pedidos (default) — list-detail composition
│   ├── WishlistTab.svelte          # R1: placeholder "Próximamente en R2"
│   ├── MargenRealTab.svelte        # R1: placeholder
│   ├── FreeUnitsTab.svelte         # R1: placeholder
│   ├── SupplierTab.svelte          # R1: placeholder
│   └── ImportSettingsTab.svelte    # R1: solo "Defaults" section (FX, ratio, target size)
└── detail/
    ├── OverviewSubtab.svelte       # Stats strip 6 KPIs + items preview + timeline 6 stages
    ├── ItemsSubtab.svelte          # Tabla completa de items
    ├── CostosSubtab.svelte         # Cost flow detallado (movido del Overview por petición Diego)
    ├── PagosSubtab.svelte          # Lista de pagos al supplier
    └── TimelineSubtab.svelte       # Timeline expandido con custom events

overhaul/src/lib/data/
├── importaciones.ts                # Types: Import, ImportStatus, ImportItem, ImportPulso, ImportFilter
└── importPulso.ts                  # Pure helpers: computePulso(), formatLeadTime(), prorrateByUsd()

overhaul/src/routes/importaciones/
└── +page.svelte                    # Mount del ImportShell + handle navigation

el-club/erp/scripts/
└── apply_imports_schema.py         # Idempotent schema additions (ALTER + CREATE TABLE wishlist + free_unit)
```

### Archivos a MODIFICAR

```
overhaul/src/lib/components/Sidebar.svelte         # Agregar nav-item "Importaciones" (data section)
overhaul/src/routes/+page.svelte                   # Routing al modo Importaciones
overhaul/src/lib/adapter/types.ts                  # Re-export Import types
overhaul/src/lib/adapter/tauri.ts                  # Invocaciones para 6 commands nuevos
overhaul/src/lib/adapter/browser.ts                # NotAvailableInBrowser para writes
overhaul/src-tauri/src/lib.rs                      # 6 commands nuevos (list_imports, get_import, get_import_items, get_import_pulso, register_arrival, close_import_proportional)
overhaul/src-tauri/Cargo.toml                      # version bump 0.1.38 → 0.1.39
overhaul/src-tauri/tauri.conf.json                 # version bump
overhaul/package.json                              # version bump
```

### NOT modified (sagrado)

- `el-club/erp/comercial.py` (Streamlit) — sigue funcionando paralelo. Diego puede seguir usándolo durante validación.
- `el-club/erp/elclub.db` schema existente — solo se agregan columnas (ALTER) y tablas nuevas (CREATE), nada se borra ni renombra.
- `audit_decisions` schema — invariante sagrado del Vault.

---

## Tasks

### Task 1: Schema additions sobre elclub.db (ALTER + CREATE wishlist/free_unit)

**Files:**
- Create: `el-club/erp/scripts/apply_imports_schema.py`
- Modify: `el-club/erp/schema.sql` (documentar las nuevas columnas/tablas para futura referencia)
- Verify: `sqlite3 el-club/erp/elclub.db ".schema imports"` y `".schema import_wishlist"`

- [ ] **Step 1: Leer schema actual de imports + sale_items + jerseys**

```bash
cd C:/Users/Diego/el-club/erp
sqlite3 elclub.db ".schema imports"
sqlite3 elclub.db ".schema sale_items"
sqlite3 elclub.db ".schema jerseys"
```

Anotar columnas existentes para no duplicar.

- [ ] **Step 2: Crear `apply_imports_schema.py` idempotente**

```python
# C:/Users/Diego/el-club/erp/scripts/apply_imports_schema.py
"""IMP-R1 schema additions. Idempotente — re-runnable sin error."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"C:\Users\Diego\el-club\erp\elclub.db")

ALTERS = [
    # imports
    ("imports", "tracking_code", "TEXT"),
    ("imports", "carrier", "TEXT DEFAULT 'DHL'"),
    ("imports", "lead_time_days", "INTEGER"),
    # sale_items
    ("sale_items", "unit_cost_usd", "REAL"),
    # jerseys
    ("jerseys", "unit_cost_usd", "REAL"),
]

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS import_wishlist (
        wishlist_item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id             TEXT NOT NULL,
        jersey_id             TEXT,
        size                  TEXT,
        player_name           TEXT,
        player_number         INTEGER,
        patch                 TEXT,
        version               TEXT,
        customer_id           TEXT,
        expected_usd          REAL,
        status                TEXT DEFAULT 'active'
                              CHECK(status IN ('active','promoted','cancelled')),
        promoted_to_import_id TEXT,
        created_at            TEXT DEFAULT (datetime('now', 'localtime')),
        notes                 TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_free_unit (
        free_unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id         TEXT NOT NULL,
        family_id         TEXT,
        jersey_id         TEXT,
        destination       TEXT
                          CHECK(destination IN ('unassigned','vip','mystery','garantizada','personal')),
        destination_ref   TEXT,
        assigned_at       TEXT,
        assigned_by       TEXT,
        notes             TEXT,
        created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_wishlist_status ON import_wishlist(status)",
    "CREATE INDEX IF NOT EXISTS idx_wishlist_customer ON import_wishlist(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_free_unit_import ON import_free_unit(import_id)",
    "CREATE INDEX IF NOT EXISTS idx_free_unit_destination ON import_free_unit(destination)",
]


def column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def main():
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"📂 Applying schema to {DB_PATH}")

    # ALTERs idempotentes
    for table, col, decl in ALTERS:
        if column_exists(cur, table, col):
            print(f"  ↪ {table}.{col} already exists, skip")
        else:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            print(f"  ✓ added {table}.{col}")

    # Default FX → 7.73 (D-FX)
    # NOTA: SQLite no permite ALTER COLUMN para cambiar default. Documentamos el nuevo
    # default en código Rust (close_import_proportional usa 7.73 si fx is null).
    # Imports históricos quedan con fx=7.70.
    print("  ℹ FX default 7.73 enforced en Rust commands, no a nivel schema (SQLite limit)")

    # CREATE TABLEs
    for sql in CREATE_TABLES:
        cur.execute(sql)
    for sql in CREATE_INDEXES:
        cur.execute(sql)
    print(f"  ✓ created/verified {len(CREATE_TABLES)} tables + {len(CREATE_INDEXES)} indexes")

    conn.commit()
    conn.close()

    print("✅ Schema applied successfully (idempotente)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Ejecutar el script**

```bash
cd C:/Users/Diego/el-club/erp
python scripts/apply_imports_schema.py
```

Expected output:
```
📂 Applying schema to C:\Users\Diego\el-club\erp\elclub.db
  ✓ added imports.tracking_code
  ✓ added imports.carrier
  ✓ added imports.lead_time_days
  ✓ added sale_items.unit_cost_usd
  ✓ added jerseys.unit_cost_usd
  ℹ FX default 7.73 enforced en Rust commands, no a nivel schema (SQLite limit)
  ✓ created/verified 2 tables + 4 indexes
✅ Schema applied successfully (idempotente)
```

- [ ] **Step 4: Verificar idempotencia (re-run no falla)**

```bash
python scripts/apply_imports_schema.py
```

Expected: todas las columnas digan "already exists, skip", tables created/verified queda 2.

- [ ] **Step 5: Verificar manual con sqlite3**

```bash
sqlite3 elclub.db ".schema imports"
sqlite3 elclub.db ".schema import_wishlist"
sqlite3 elclub.db ".schema import_free_unit"
sqlite3 elclub.db "SELECT COUNT(*) FROM imports"  # debe ser 2
sqlite3 elclub.db "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' AND name LIKE '%wishlist%' OR name LIKE '%free_unit%'"
```

- [ ] **Step 6: Documentar el cambio en `schema.sql`** (no se aplica, solo es referencia)

Agregar al final de `schema.sql`:

```sql
-- ═══════════════════════════════════════
-- IMP-R1 schema additions (2026-04-27)
-- Aplicado vía scripts/apply_imports_schema.py (idempotente)
-- ═══════════════════════════════════════

-- ALTER TABLE imports ADD COLUMN tracking_code TEXT;
-- ALTER TABLE imports ADD COLUMN carrier TEXT DEFAULT 'DHL';
-- ALTER TABLE imports ADD COLUMN lead_time_days INTEGER;
-- ALTER TABLE sale_items ADD COLUMN unit_cost_usd REAL;
-- ALTER TABLE jerseys ADD COLUMN unit_cost_usd REAL;

-- (CREATE TABLE statements para import_wishlist y import_free_unit — ver scripts/apply_imports_schema.py)
```

- [ ] **Step 7: Commit**

```bash
git add el-club/erp/scripts/apply_imports_schema.py el-club/erp/schema.sql
git commit -m "feat(imp): IMP-R1 schema additions for Importaciones module

- ALTER imports: tracking_code, carrier (default DHL), lead_time_days
- ALTER sale_items: unit_cost_usd (for D2=B prorrateo proporcional)
- ALTER jerseys: unit_cost_usd
- CREATE TABLE import_wishlist (D6=A · tab propia · D7=B requiere SKU)
- CREATE TABLE import_free_unit (D-FREE=A · 5 destinations)
- 4 indexes nuevos

Idempotente. Re-runnable sin error.
Spec: docs/superpowers/specs/2026-04-27-importaciones-design.md sec 7"
```

---

### Task 2: TypeScript types — Import, ImportStatus, ImportItem, Pulso

**Files:**
- Create: `overhaul/src/lib/data/importaciones.ts`
- Modify: `overhaul/src/lib/adapter/types.ts` (re-exports)

- [ ] **Step 1: Crear `importaciones.ts` con types**

```typescript
// C:/Users/Diego/el-club/overhaul/src/lib/data/importaciones.ts

export type ImportStatus = 'draft' | 'paid' | 'in_transit' | 'arrived' | 'closed' | 'cancelled';

export interface Import {
  import_id: string;            // 'IMP-2026-04-07'
  paid_at: string | null;       // ISO date
  arrived_at: string | null;
  supplier: string;             // 'Bond Soccer Jersey'
  bruto_usd: number | null;
  shipping_gtq: number | null;
  fx: number;                   // default 7.73 (D-FX), legacy 7.70
  total_landed_gtq: number | null;
  n_units: number | null;
  unit_cost: number | null;     // GTQ post-prorrateo
  status: ImportStatus;
  notes: string | null;
  created_at: string;
  // R1 additions
  tracking_code: string | null;
  carrier: string;              // default 'DHL'
  lead_time_days: number | null;
}

export interface ImportItem {
  // Linkeable a sale_items o jerseys, polymorphic
  source_table: 'sale_items' | 'jerseys';
  source_id: number;
  import_id: string;
  family_id: string;
  jersey_id: string | null;
  size: string | null;
  player_name: string | null;
  player_number: number | null;
  patch: string | null;
  version: string | null;
  unit_cost_usd: number | null;     // USD del chino (de chat WA `11+2=13`)
  unit_cost: number | null;         // GTQ post-prorrateo
  customer_id: string | null;       // null = stock futuro
  customer_name: string | null;     // joined
  is_free_unit: boolean;
}

export interface ImportPulso {
  capital_amarrado_gtq: number;     // sum total_landed_gtq de batches paid + in_transit + arrived
  closed_ytd_landed_gtq: number;    // sum total_landed_gtq de batches closed YTD
  avg_landed_unit: number | null;   // avg unit_cost de batches closed
  lead_time_avg_days: number | null;// avg (arrived_at - paid_at) de batches closed
  wishlist_count: number;
  free_units_unassigned: number;
}

export interface ImportFilter {
  status?: ImportStatus | 'pipeline' | 'all';   // 'pipeline' = paid+in_transit+arrived
  supplier?: string;
  search?: string;
}

export const STATUS_LABELS: Record<ImportStatus, string> = {
  draft:      'DRAFT',
  paid:       'PAID',
  in_transit: 'TRANSIT',
  arrived:    'ARRIVED',
  closed:     'CLOSED',
  cancelled:  'CANCELLED',
};

export const STATUS_PROGRESS: Record<ImportStatus, number> = {
  draft:      1,
  paid:       2,
  in_transit: 3,
  arrived:    4,
  closed:     5,
  cancelled:  0,  // off-ramp
};
```

- [ ] **Step 2: Re-export en types.ts**

Buscar el export pattern existente en `overhaul/src/lib/adapter/types.ts` y agregar:

```typescript
// IMP-R1
export type { Import, ImportStatus, ImportItem, ImportPulso, ImportFilter } from '$lib/data/importaciones';
export { STATUS_LABELS as IMPORT_STATUS_LABELS, STATUS_PROGRESS as IMPORT_STATUS_PROGRESS } from '$lib/data/importaciones';
```

- [ ] **Step 3: Verificar `npm run check`**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add overhaul/src/lib/data/importaciones.ts overhaul/src/lib/adapter/types.ts
git commit -m "feat(imp): types canonical para Importaciones (Import, ImportItem, Pulso)"
```

---

### Task 3: Tauri Rust commands — list_imports, get_import, get_import_items, get_import_pulso

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs` (agregar al final del archivo, antes del `#[cfg_attr(...)]` de `run()`)

- [ ] **Step 1: Definir structs Rust en lib.rs**

Agregar en la sección de structs (después de `AuditDecision`):

```rust
// ─── Importaciones (IMP-R1) ────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct Import {
    pub import_id: String,
    pub paid_at: Option<String>,
    pub arrived_at: Option<String>,
    pub supplier: String,
    pub bruto_usd: Option<f64>,
    pub shipping_gtq: Option<f64>,
    pub fx: f64,
    pub total_landed_gtq: Option<f64>,
    pub n_units: Option<i64>,
    pub unit_cost: Option<f64>,
    pub status: String,
    pub notes: Option<String>,
    pub created_at: String,
    pub tracking_code: Option<String>,
    pub carrier: String,
    pub lead_time_days: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct ImportItem {
    pub source_table: String,        // 'sale_items' | 'jerseys'
    pub source_id: i64,
    pub import_id: String,
    pub family_id: String,
    pub jersey_id: Option<String>,
    pub size: Option<String>,
    pub player_name: Option<String>,
    pub player_number: Option<i64>,
    pub patch: Option<String>,
    pub version: Option<String>,
    pub unit_cost_usd: Option<f64>,
    pub unit_cost: Option<f64>,
    pub customer_id: Option<String>,
    pub customer_name: Option<String>,
    pub is_free_unit: bool,
}

#[derive(Debug, Serialize)]
pub struct ImportPulso {
    pub capital_amarrado_gtq: f64,
    pub closed_ytd_landed_gtq: f64,
    pub avg_landed_unit: Option<f64>,
    pub lead_time_avg_days: Option<f64>,
    pub wishlist_count: i64,
    pub free_units_unassigned: i64,
}
```

- [ ] **Step 2: Implementar `cmd_list_imports`**

Agregar antes del cierre del archivo (antes de `pub fn run()`):

```rust
#[tauri::command]
pub async fn cmd_list_imports(_app: tauri::AppHandle) -> Result<Vec<Import>> {
    let conn = rusqlite::Connection::open(db_path())?;
    let mut stmt = conn.prepare(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73) as fx, total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL') as carrier, lead_time_days
         FROM imports
         ORDER BY paid_at DESC NULLS LAST, created_at DESC"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        })
    })?;

    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}
```

- [ ] **Step 3: Implementar `cmd_get_import` (single batch)**

```rust
#[tauri::command]
pub async fn cmd_get_import(_app: tauri::AppHandle, import_id: String) -> Result<Import> {
    let conn = rusqlite::Connection::open(db_path())?;
    let imp = conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![import_id],
        |row| Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        }),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;
    Ok(imp)
}
```

- [ ] **Step 4: Implementar `cmd_get_import_items` (sale_items + jerseys polymorphic)**

```rust
#[tauri::command]
pub async fn cmd_get_import_items(_app: tauri::AppHandle, import_id: String) -> Result<Vec<ImportItem>> {
    let conn = rusqlite::Connection::open(db_path())?;

    // sale_items linked
    let mut stmt = conn.prepare(
        "SELECT 'sale_items' as source_table, i.id as source_id, i.import_id,
                i.family_id, i.jersey_id, i.size,
                json_extract(i.personalization_json, '$.name') as player_name,
                CAST(json_extract(i.personalization_json, '$.number') AS INTEGER) as player_number,
                json_extract(i.personalization_json, '$.patch') as patch,
                i.version,
                i.unit_cost_usd, i.unit_cost,
                s.customer_id, c.name as customer_name,
                CASE WHEN i.unit_cost_usd = 0 OR i.unit_cost = 0 THEN 1 ELSE 0 END as is_free_unit
         FROM sale_items i
         LEFT JOIN sales s ON s.sale_id = i.sale_id
         LEFT JOIN customers c ON c.customer_id = s.customer_id
         WHERE i.import_id = ?1
         UNION ALL
         SELECT 'jerseys' as source_table, j.rowid as source_id, j.import_id,
                j.family_id, j.jersey_id, j.size,
                NULL as player_name, NULL as player_number, NULL as patch, NULL as version,
                j.unit_cost_usd, j.cost as unit_cost,
                NULL as customer_id, NULL as customer_name,
                0 as is_free_unit
         FROM jerseys j
         WHERE j.import_id = ?1"
    )?;

    let rows = stmt.query_map(rusqlite::params![import_id], |row| {
        Ok(ImportItem {
            source_table:   row.get(0)?,
            source_id:      row.get(1)?,
            import_id:      row.get(2)?,
            family_id:      row.get(3)?,
            jersey_id:      row.get(4)?,
            size:           row.get(5)?,
            player_name:    row.get(6)?,
            player_number:  row.get(7)?,
            patch:          row.get(8)?,
            version:        row.get(9)?,
            unit_cost_usd:  row.get(10)?,
            unit_cost:      row.get(11)?,
            customer_id:    row.get(12)?,
            customer_name:  row.get(13)?,
            is_free_unit:   row.get::<_, i64>(14)? != 0,
        })
    })?;

    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}
```

- [ ] **Step 5: Implementar `cmd_get_import_pulso`**

```rust
#[tauri::command]
pub async fn cmd_get_import_pulso(_app: tauri::AppHandle) -> Result<ImportPulso> {
    let conn = rusqlite::Connection::open(db_path())?;

    let capital: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status IN ('paid', 'in_transit', 'arrived')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let closed_ytd: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status = 'closed'
           AND substr(arrived_at, 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let avg_landed: Option<f64> = conn.query_row(
        "SELECT AVG(unit_cost) FROM imports WHERE status = 'closed' AND unit_cost IS NOT NULL",
        [], |r| r.get(0),
    ).ok().flatten();

    let lead_avg: Option<f64> = conn.query_row(
        "SELECT AVG(lead_time_days) FROM imports
         WHERE status = 'closed' AND lead_time_days IS NOT NULL",
        [], |r| r.get(0),
    ).ok().flatten();

    let wishlist: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_wishlist WHERE status = 'active'",
        [], |r| r.get(0),
    ).unwrap_or(0);

    let free_unassigned: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE destination = 'unassigned'",
        [], |r| r.get(0),
    ).unwrap_or(0);

    Ok(ImportPulso {
        capital_amarrado_gtq: capital,
        closed_ytd_landed_gtq: closed_ytd,
        avg_landed_unit: avg_landed,
        lead_time_avg_days: lead_avg,
        wishlist_count: wishlist,
        free_units_unassigned: free_unassigned,
    })
}
```

- [ ] **Step 6: Registrar commands en `tauri::generate_handler!`**

Buscar el `pub fn run()` cerca del final de `lib.rs`, dentro de `.invoke_handler(tauri::generate_handler![...])` agregar al final de la lista:

```rust
cmd_list_imports,
cmd_get_import,
cmd_get_import_items,
cmd_get_import_pulso,
```

- [ ] **Step 7: cargo check**

```bash
cd C:/Users/Diego/el-club/overhaul/src-tauri
cargo check
```

Expected: 0 errors. Si hay warnings de unused, ignorar (los commands se invocan desde JS).

- [ ] **Step 8: Commit**

```bash
git add overhaul/src-tauri/src/lib.rs
git commit -m "feat(imp): 4 read-only Tauri commands para Importaciones

- cmd_list_imports — list ordered by paid_at DESC
- cmd_get_import — single batch by ID
- cmd_get_import_items — polymorphic sale_items + jerseys via UNION
- cmd_get_import_pulso — 6 KPIs computados en SQL"
```

---

### Task 4: Adapter — invocaciones en tauri.ts + browser.ts

**Files:**
- Modify: `overhaul/src/lib/adapter/tauri.ts`
- Modify: `overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Agregar invocaciones en tauri.ts**

Buscar el patrón de invocaciones existentes y agregar:

```typescript
// Cerca de las otras invocaciones
import type { Import, ImportItem, ImportPulso } from '$lib/data/importaciones';

export async function listImports(): Promise<Import[]> {
  return invoke('cmd_list_imports');
}

export async function getImport(import_id: string): Promise<Import> {
  return invoke('cmd_get_import', { importId: import_id });
}

export async function getImportItems(import_id: string): Promise<ImportItem[]> {
  return invoke('cmd_get_import_items', { importId: import_id });
}

export async function getImportPulso(): Promise<ImportPulso> {
  return invoke('cmd_get_import_pulso');
}
```

- [ ] **Step 2: Browser fallback — NotAvailableInBrowser para writes**

En `browser.ts`, agregar reads que funcionan + writes que tiran:

```typescript
import type { Import, ImportItem, ImportPulso } from '$lib/data/importaciones';
import { NotAvailableInBrowser } from './errors';

// Reads — return empty / mock data en browser mode
export async function listImports(): Promise<Import[]> {
  return [];
}

export async function getImport(_import_id: string): Promise<Import> {
  throw new NotAvailableInBrowser('getImport requires Tauri (.exe)');
}

export async function getImportItems(_import_id: string): Promise<ImportItem[]> {
  return [];
}

export async function getImportPulso(): Promise<ImportPulso> {
  return {
    capital_amarrado_gtq: 0,
    closed_ytd_landed_gtq: 0,
    avg_landed_unit: null,
    lead_time_avg_days: null,
    wishlist_count: 0,
    free_units_unassigned: 0,
  };
}
```

- [ ] **Step 3: Re-exportar desde adapter index**

Buscar `overhaul/src/lib/adapter/index.ts` y agregar las exportaciones siguiendo el patrón existente.

- [ ] **Step 4: npm run check**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run check
```

- [ ] **Step 5: Commit**

```bash
git add overhaul/src/lib/adapter/
git commit -m "feat(imp): adapter invocations (tauri + browser fallback)"
```

---

### Task 5: Sidebar — agregar nav-item Importaciones

**Files:**
- Modify: `overhaul/src/lib/components/Sidebar.svelte`

- [ ] **Step 1: Importar icono Truck o Ship de lucide-svelte**

Buscar la línea de imports lucide-svelte (línea ~3) y agregar `Ship`:

```svelte
import {
  Inbox, Search, Trophy, Rocket, BarChart3, Package, DollarSign,
  Truck, Ship,  // ← ADD Ship
  Command, Upload, Loader2, CheckCircle2, AlertTriangle, RefreshCw, Download
} from 'lucide-svelte';
```

- [ ] **Step 2: Agregar item al array ITEMS**

Buscar el array `ITEMS` (línea ~137) y agregar entre `comercial` y `orders`:

```typescript
const ITEMS: NavItem[] = [
  { id: 'queue', label: 'Queue', icon: Inbox, section: 'workflow' },
  { id: 'audit', label: 'Audit', icon: Search, section: 'workflow' },
  { id: 'mundial', label: 'Mundial 2026', icon: Trophy, section: 'workflow' },
  { id: 'publicados', label: 'Publicados', icon: Rocket, section: 'workflow' },
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3, section: 'data' },
  { id: 'inventory', label: 'Inventario', icon: Package, section: 'data' },
  { id: 'comercial', label: 'Comercial', icon: DollarSign, section: 'data' },
  { id: 'importaciones', label: 'Importaciones', icon: Ship, section: 'data' },  // ← NEW
  { id: 'orders', label: 'Órdenes', icon: Truck, section: 'data' }
];
```

- [ ] **Step 3: npm run check**

- [ ] **Step 4: Smoke test visual**

```bash
cd C:/Users/Diego/el-club/overhaul
npm run tauri dev
```

Verificar: el nav-item "Importaciones" aparece en sección Data, ícono ship, click cambia `active` state pero todavía no rutea (Task 6 lo hace).

- [ ] **Step 5: Commit**

```bash
git add overhaul/src/lib/components/Sidebar.svelte
git commit -m "feat(imp): sidebar nav-item Importaciones (icon Ship)"
```

---

### Task 6: Routing — `/importaciones` route + handle navigation

**Files:**
- Create: `overhaul/src/routes/importaciones/+page.svelte`
- Modify: `overhaul/src/routes/+page.svelte` (handle navegación al click)

- [ ] **Step 1: Crear el route file con placeholder**

```svelte
<!-- overhaul/src/routes/importaciones/+page.svelte -->
<script lang="ts">
  import ImportShell from '$lib/components/importaciones/ImportShell.svelte';
</script>

<ImportShell />
```

- [ ] **Step 2: Buscar handler de navigation en `+page.svelte` raíz**

```bash
grep -n "onSelect\|active.*=.*'comercial'" overhaul/src/routes/+page.svelte
```

Identificar cómo se maneja el switch entre módulos (Comercial, Audit, etc.).

- [ ] **Step 3: Agregar case 'importaciones' siguiendo patrón existente**

Si el patrón es `goto('/comercial')`, entonces para importaciones es `goto('/importaciones')`. Adaptar al patrón actual.

- [ ] **Step 4: npm run check**

- [ ] **Step 5: Smoke test — click "Importaciones" navega**

Ejecutar `npm run tauri dev`, click en sidebar, verificar que aparece la pantalla (vacía por ahora porque ImportShell no existe aún · Task 7).

- [ ] **Step 6: Commit (puede fallar build si ImportShell no existe — crearlo en Task 7 antes de commitear)**

Diferir commit hasta Task 7 si build falla.

---

### Task 7: ImportShell.svelte — frame del módulo (module-head + tabs + pulso + body)

**Files:**
- Create: `overhaul/src/lib/components/importaciones/ImportShell.svelte`
- Create: `overhaul/src/lib/components/importaciones/ImportTabs.svelte`

**Reference visual:** abrir `el-club/overhaul/.superpowers/brainstorm/1923-1777335894/content/06-mockup-a1-hd-v2.html` en el browser. Copiar styles de `.module-head`, `.tabs`, `.pulso`.

- [ ] **Step 1: Crear ImportShell.svelte con structure básica**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportShell.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import ImportTabs from './ImportTabs.svelte';
  import PulsoImportBar from './PulsoImportBar.svelte';
  import PedidosTab from './tabs/PedidosTab.svelte';
  import WishlistTab from './tabs/WishlistTab.svelte';
  import MargenRealTab from './tabs/MargenRealTab.svelte';
  import FreeUnitsTab from './tabs/FreeUnitsTab.svelte';
  import SupplierTab from './tabs/SupplierTab.svelte';
  import ImportSettingsTab from './tabs/ImportSettingsTab.svelte';
  import { adapter } from '$lib/adapter';
  import type { ImportPulso } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  const STORAGE_KEY = 'imp.activeTab';

  let activeTab = $state<TabId>(
    (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY) as TabId) || 'pedidos'
  );
  let pulso = $state<ImportPulso | null>(null);

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, activeTab);
    }
  });

  onMount(async () => {
    pulso = await adapter.getImportPulso();
  });

  async function refreshPulso() {
    pulso = await adapter.getImportPulso();
  }
</script>

<div class="flex h-full flex-col">
  <!-- Module head -->
  <div class="flex items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-3">
    <div>
      <div class="text-[18px] font-semibold text-[var(--color-text-primary)]">Importaciones</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        módulo de costeo · seguimiento de pedidos al supplier · alimenta FIN-Rx
      </div>
    </div>
    <div class="ml-auto flex gap-2">
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
        ⇣ Export CSV
      </button>
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]">
        ↻ Sync DHL
      </button>
      <button class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]">
        + Nuevo pedido
      </button>
    </div>
  </div>

  <!-- Tabs -->
  <ImportTabs bind:activeTab pulsoCount={pulso} />

  <!-- Pulso bar -->
  {#if pulso}
    <PulsoImportBar {pulso} />
  {/if}

  <!-- Body -->
  <div class="flex flex-1 min-h-0">
    {#if activeTab === 'pedidos'}
      <PedidosTab onPulsoRefresh={refreshPulso} />
    {:else if activeTab === 'wishlist'}
      <WishlistTab />
    {:else if activeTab === 'margen'}
      <MargenRealTab />
    {:else if activeTab === 'free'}
      <FreeUnitsTab />
    {:else if activeTab === 'supplier'}
      <SupplierTab />
    {:else if activeTab === 'settings'}
      <ImportSettingsTab />
    {/if}
  </div>
</div>
```

- [ ] **Step 2: Crear ImportTabs.svelte**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportTabs.svelte -->
<script lang="ts">
  import type { ImportPulso } from '$lib/data/importaciones';

  type TabId = 'pedidos' | 'wishlist' | 'margen' | 'free' | 'supplier' | 'settings';

  interface Props {
    activeTab: TabId;
    pulsoCount: ImportPulso | null;
  }

  let { activeTab = $bindable(), pulsoCount }: Props = $props();

  const TABS: Array<{id: TabId; label: string; countKey?: keyof ImportPulso}> = [
    { id: 'pedidos',  label: 'Pedidos' },
    { id: 'wishlist', label: 'Wishlist',     countKey: 'wishlist_count' },
    { id: 'margen',   label: 'Margen real' },
    { id: 'free',     label: 'Free units',   countKey: 'free_units_unassigned' },
    { id: 'supplier', label: 'Supplier' },
    { id: 'settings', label: 'Settings' },
  ];
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each TABS as tab}
    {@const count = tab.countKey && pulsoCount ? pulsoCount[tab.countKey] : null}
    {@const isLast = tab.id === 'settings'}
    <button
      class="text-mono inline-flex items-baseline gap-1.5 border-b-2 border-transparent px-4 py-2.5 text-[11px] uppercase transition-colors"
      class:ml-auto={isLast}
      class:text-[var(--color-text-secondary)]={activeTab !== tab.id}
      class:!text-[var(--color-accent)]={activeTab === tab.id}
      class:!border-[var(--color-accent)]={activeTab === tab.id}
      style="letter-spacing: 0.05em;"
      onclick={() => activeTab = tab.id}
    >
      {tab.label}
      {#if count !== null && count !== undefined && (typeof count === 'number') && count > 0}
        <span class="text-[10px] opacity-70">· {count}</span>
      {/if}
    </button>
  {/each}
</div>
```

- [ ] **Step 3: Crear placeholders para los 5 tabs no-Pedidos**

```svelte
<!-- overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte -->
<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  <div class="text-center">
    <div class="text-mono text-[11px] uppercase mb-2" style="letter-spacing: 0.08em;">Próximamente</div>
    <div class="text-sm">Wishlist viene en IMP-R2</div>
  </div>
</div>
```

Repetir el mismo patrón con título distinto para `MargenRealTab.svelte` (R3), `FreeUnitsTab.svelte` (R4), `SupplierTab.svelte` (R5), `ImportSettingsTab.svelte` (R6).

- [ ] **Step 4: Crear PedidosTab.svelte placeholder (Task 8 lo llena)**

```svelte
<!-- overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte -->
<script lang="ts">
  interface Props {
    onPulsoRefresh: () => void;
  }
  let { onPulsoRefresh }: Props = $props();
</script>

<div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
  Loading list-detail…
</div>
```

- [ ] **Step 5: npm run check + smoke**

```bash
npm run check
npm run tauri dev
```

Verificar: click en Importaciones rutea, módulo se ve con header + tabs + pulso bar (con valores reales calculados de la DB), body muestra "Loading list-detail" para Pedidos default tab. Tabs cambian estado activo OK.

- [ ] **Step 6: Commit**

```bash
git add overhaul/src/lib/components/importaciones/ overhaul/src/routes/importaciones/ overhaul/src/routes/+page.svelte
git commit -m "feat(imp): ImportShell + tabs + pulso (skeleton renderable)"
```

---

### Task 8: PulsoImportBar.svelte — 6 KPIs

**Files:**
- Create: `overhaul/src/lib/components/importaciones/PulsoImportBar.svelte`

**Reference visual:** mockup HD v2 `.pulso` section (líneas con `Capital amarrado`, `Closed YTD`, `Avg landed/u`, `Lead time avg supplier`, `Wishlist activa`, `Free units disponibles`).

- [ ] **Step 1: Crear el componente**

```svelte
<!-- overhaul/src/lib/components/importaciones/PulsoImportBar.svelte -->
<script lang="ts">
  import type { ImportPulso } from '$lib/data/importaciones';

  interface Props { pulso: ImportPulso; }
  let { pulso }: Props = $props();

  function fmtQ(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `Q${Math.round(n).toLocaleString('es-GT')}`;
  }
  function fmtDays(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `${Math.round(n)} días`;
  }
</script>

<div class="flex items-stretch gap-0 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-2.5">
  <!-- Capital amarrado -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Capital amarrado
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-warning)]">
      ~{fmtQ(pulso.capital_amarrado_gtq)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">paid · sin cerrar</div>
  </div>

  <!-- Closed YTD landed -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Closed YTD landed
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-live)]">
      {fmtQ(pulso.closed_ytd_landed_gtq)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">batches cerrados {new Date().getFullYear()}</div>
  </div>

  <!-- Avg landed -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Avg landed/u
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-primary)]">
      {fmtQ(pulso.avg_landed_unit)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">de batches closed</div>
  </div>

  <!-- Lead time avg -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Lead time avg
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-accent)]">
      {fmtDays(pulso.lead_time_avg_days)}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">paid → arrived</div>
  </div>

  <!-- Wishlist -->
  <div class="flex-1 border-r border-[var(--color-surface-2)] px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Wishlist activa
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-secondary)]">
      {pulso.wishlist_count}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">items pre-pedido</div>
  </div>

  <!-- Free units -->
  <div class="flex-1 px-4">
    <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
      Free disponibles
    </div>
    <div class="text-mono text-[17px] font-bold tabular-nums leading-tight text-[var(--color-text-primary)]">
      {pulso.free_units_unassigned}
    </div>
    <div class="text-mono text-[9.5px] text-[var(--color-text-tertiary)] mt-0.5">sin asignar destino</div>
  </div>
</div>
```

- [ ] **Step 2: npm run check**

- [ ] **Step 3: Smoke test — verificar valores reales**

`npm run tauri dev` → tab Pedidos default → Pulso bar muestra:
- Capital amarrado ~Q3,915 (de IMP-2026-04-18 con bruto $372 × 7.7 + estimación de DHL)
- Closed YTD Q3,182 (IMP-2026-04-07)
- Avg landed Q145
- Lead time 8 días
- Wishlist 0
- Free units 0

Si todos muestran 0 o "—" sospechar query SQL — revisar `cmd_get_import_pulso`.

- [ ] **Step 4: Commit**

```bash
git add overhaul/src/lib/components/importaciones/PulsoImportBar.svelte
git commit -m "feat(imp): PulsoImportBar con 6 KPIs computados desde DB"
```

---

### Task 9: ImportListPane + ImportRow — list pane 320px con search/filters/rows

**Files:**
- Create: `overhaul/src/lib/components/importaciones/ImportListPane.svelte`
- Create: `overhaul/src/lib/components/importaciones/ImportRow.svelte`

**Reference visual:** mockup HD v2 `.list-pane` (320px) con `.list-search`, `.filter-chips`, `.row` con mini-progress bars + lead time badges.

- [ ] **Step 1: Crear `ImportRow.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportRow.svelte -->
<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  import { STATUS_LABELS, STATUS_PROGRESS } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    isActive: boolean;
    onSelect: (id: string) => void;
  }

  let { imp, isActive, onSelect }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let costLabel = $derived(computeCostLabel(imp));
  let progressTicks = $derived(STATUS_PROGRESS[imp.status as keyof typeof STATUS_PROGRESS] || 0);

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function computeCostLabel(i: Import): {text: string; color: 'green' | 'amber' | 'muted'} {
    if (i.status === 'closed' && i.unit_cost) {
      return { text: `Q${Math.round(i.unit_cost)}/u`, color: 'green' };
    }
    if (i.status === 'paid' || i.status === 'in_transit' || i.status === 'arrived') {
      return { text: '~Q145?', color: 'amber' };
    }
    return { text: 'acumulando', color: 'muted' };
  }

  function statusPillClass(status: string): string {
    return {
      closed:     'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      arrived:    'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      paid:       'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      draft:      'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled:  'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] || 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>

<button
  type="button"
  class="block w-full border-b border-[var(--color-surface-2)] px-3.5 py-2.5 text-left transition-colors hover:bg-[var(--color-surface-1)]"
  class:bg-[var(--color-surface-2)]={isActive}
  class:border-l-2={isActive}
  class:border-l-[var(--color-accent)]={isActive}
  class:!pl-3={isActive}
  onclick={() => onSelect(imp.import_id)}
>
  <!-- Top row: ID + cost label -->
  <div class="flex items-baseline justify-between mb-1">
    <span class="text-mono text-[12px] font-semibold text-[var(--color-text-primary)]">{imp.import_id}</span>
    <span class="text-mono text-[11px] font-semibold tabular-nums {
      costLabel.color === 'green'
        ? 'text-[var(--color-live)]'
        : costLabel.color === 'amber'
          ? 'text-[var(--color-warning)]'
          : 'text-[var(--color-text-tertiary)]'
    }">{costLabel.text}</span>
  </div>

  <!-- Meta row: supplier · usd · units + status pill -->
  <div class="flex justify-between items-center gap-2 mb-1">
    <span class="text-[11px] text-[var(--color-text-secondary)] truncate">
      {imp.supplier} · ${imp.bruto_usd?.toFixed(0) ?? '—'} · {imp.n_units ?? 0}u
    </span>
    <span class="text-mono text-[9px] uppercase tracking-wider rounded-[2px] px-1.5 py-0.5 inline-flex items-center gap-1 {statusPillClass(imp.status)}">
      <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
      {STATUS_LABELS[imp.status as keyof typeof STATUS_LABELS]}
    </span>
  </div>

  <!-- Bottom: mini-progress + lead time -->
  <div class="flex items-center gap-2">
    <div class="flex gap-0.5 flex-1">
      {#each [1,2,3,4,5] as i}
        <div class="h-[3px] flex-1 rounded-[1px] {
          i < progressTicks ? 'bg-[var(--color-live)]' :
          i === progressTicks ? 'bg-[var(--color-warning)]' :
          'bg-[var(--color-surface-2)]'
        }"></div>
      {/each}
    </div>
    {#if leadDays !== null}
      <span class="text-mono text-[9.5px] {
        imp.status === 'closed' ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'
      }">
        {leadDays}d{imp.status === 'closed' ? ' ✓' : ''}
      </span>
    {/if}
  </div>
</button>
```

- [ ] **Step 2: Crear `ImportListPane.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportListPane.svelte -->
<script lang="ts">
  import { Search } from 'lucide-svelte';
  import ImportRow from './ImportRow.svelte';
  import type { Import, ImportFilter } from '$lib/data/importaciones';

  interface Props {
    imports: Import[];
    activeId: string | null;
    onSelect: (id: string) => void;
  }

  let { imports, activeId, onSelect }: Props = $props();

  let filter = $state<ImportFilter>({ status: 'all' });
  let search = $state('');

  let filtered = $derived(applyFilter(imports, filter, search));

  function applyFilter(list: Import[], f: ImportFilter, q: string): Import[] {
    let out = list;
    if (f.status === 'pipeline') {
      out = out.filter(i => ['paid', 'in_transit', 'arrived'].includes(i.status));
    } else if (f.status === 'closed') {
      out = out.filter(i => i.status === 'closed');
    }
    if (f.supplier) {
      out = out.filter(i => i.supplier === f.supplier);
    }
    if (q.trim()) {
      const ql = q.toLowerCase();
      out = out.filter(i =>
        i.import_id.toLowerCase().includes(ql) ||
        i.supplier.toLowerCase().includes(ql) ||
        i.notes?.toLowerCase().includes(ql)
      );
    }
    return out;
  }

  function countByStatus(s: string): number {
    if (s === 'all') return imports.length;
    if (s === 'pipeline') return imports.filter(i => ['paid','in_transit','arrived'].includes(i.status)).length;
    return imports.filter(i => i.status === s).length;
  }
</script>

<aside class="w-[320px] flex-shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface-1)] flex flex-col">
  <!-- Search -->
  <div class="p-3 border-b border-[var(--color-border)]">
    <div class="flex items-center gap-2 px-2.5 py-1.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px]">
      <Search size={13} class="text-[var(--color-text-tertiary)]" strokeWidth={1.8} />
      <input
        type="text"
        bind:value={search}
        placeholder="ID pedido, SKU, cliente, supplier..."
        class="flex-1 bg-transparent border-0 outline-none text-mono text-[11.5px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]"
      />
    </div>
  </div>

  <!-- Filter chips -->
  <div class="flex gap-1.5 px-3 py-2 border-b border-[var(--color-border)] flex-wrap">
    {#each [{id:'all',label:'Todos'}, {id:'pipeline',label:'Pipeline'}, {id:'closed',label:'Closed'}] as chip}
      <button
        type="button"
        class="text-mono text-[9.5px] px-2 py-0.5 rounded-[2px] border transition-colors"
        class:bg-[rgba(91,141,239,0.14)]={filter.status === chip.id}
        class:text-[var(--color-accent)]={filter.status === chip.id}
        class:border-[rgba(91,141,239,0.3)]={filter.status === chip.id}
        class:bg-[var(--color-surface-2)]={filter.status !== chip.id}
        class:text-[var(--color-text-secondary)]={filter.status !== chip.id}
        class:border-[var(--color-border)]={filter.status !== chip.id}
        style="letter-spacing: 0.05em;"
        onclick={() => filter = { ...filter, status: chip.id as ImportFilter['status'] }}
      >
        {chip.label}<span class="ml-1 text-[var(--color-text-tertiary)]">{countByStatus(chip.id)}</span>
      </button>
    {/each}
  </div>

  <!-- Rows -->
  <div class="flex-1 overflow-y-auto">
    {#each filtered as imp (imp.import_id)}
      <ImportRow {imp} isActive={imp.import_id === activeId} {onSelect} />
    {:else}
      <div class="p-6 text-center text-[var(--color-text-tertiary)] text-sm">
        Sin batches que matcheen los filtros.
      </div>
    {/each}
  </div>
</aside>
```

- [ ] **Step 3: npm run check**

- [ ] **Step 4: Commit (sin smoke aún · Task 10 lo conecta)**

```bash
git add overhaul/src/lib/components/importaciones/ImportListPane.svelte overhaul/src/lib/components/importaciones/ImportRow.svelte
git commit -m "feat(imp): ImportListPane + ImportRow con search + filter chips + mini-progress + lead time"
```

---

### Task 10: PedidosTab.svelte — composition list-detail + load imports

**Files:**
- Modify: `overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte`
- Create: `overhaul/src/lib/components/importaciones/ImportDetailPane.svelte` (placeholder · Task 11 lo llena)

- [ ] **Step 1: Implementar PedidosTab.svelte**

```svelte
<!-- overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import ImportListPane from '../ImportListPane.svelte';
  import ImportDetailPane from '../ImportDetailPane.svelte';
  import { adapter } from '$lib/adapter';
  import type { Import } from '$lib/data/importaciones';

  interface Props {
    onPulsoRefresh: () => void;
  }
  let { onPulsoRefresh }: Props = $props();

  let imports = $state<Import[]>([]);
  let activeId = $state<string | null>(null);
  let activeImport = $derived(imports.find(i => i.import_id === activeId) ?? null);
  let loading = $state(true);

  onMount(load);

  async function load() {
    loading = true;
    imports = await adapter.listImports();
    if (imports.length > 0 && !activeId) {
      activeId = imports[0].import_id;  // default: most recent
    }
    loading = false;
  }

  function handleSelect(id: string) {
    activeId = id;
  }

  async function handleBatchUpdated() {
    await load();
    onPulsoRefresh();
  }
</script>

<div class="flex flex-1 min-h-0">
  {#if loading}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Cargando batches…
    </div>
  {:else}
    <ImportListPane {imports} {activeId} onSelect={handleSelect} />
    <ImportDetailPane imp={activeImport} onUpdated={handleBatchUpdated} />
  {/if}
</div>
```

- [ ] **Step 2: Crear ImportDetailPane.svelte placeholder (Task 11 lo llena)**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportDetailPane.svelte -->
<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }
  let { imp, onUpdated }: Props = $props();
</script>

<div class="flex-1 flex flex-col min-w-0">
  {#if !imp}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Seleccioná un batch del panel izquierdo
    </div>
  {:else}
    <!-- Detail head + sub-tabs vienen en Task 11 -->
    <div class="p-6 text-mono text-sm text-[var(--color-text-secondary)]">
      Batch {imp.import_id} · {imp.status}
    </div>
  {/if}
</div>
```

- [ ] **Step 3: npm run check + smoke**

`npm run tauri dev` → tab Pedidos → list pane muestra los 2 batches reales (IMP-2026-04-18 + IMP-2026-04-07) con valores correctos. Click cambia activeId. Detail pane muestra placeholder con el ID seleccionado.

- [ ] **Step 4: Commit**

```bash
git add overhaul/src/lib/components/importaciones/
git commit -m "feat(imp): PedidosTab list-detail composition · loads 2 imports reales"
```

---

### Task 11: ImportDetailPane completo — head + action toolbar + sub-tabs + Overview

**Files:**
- Modify: `overhaul/src/lib/components/importaciones/ImportDetailPane.svelte`
- Create: `overhaul/src/lib/components/importaciones/ImportDetailHead.svelte`
- Create: `overhaul/src/lib/components/importaciones/ImportDetailSubtabs.svelte`
- Create: `overhaul/src/lib/components/importaciones/detail/OverviewSubtab.svelte`

**Reference visual:** mockup HD v2 `.detail-head`, `.detail-actions` (toolbar arriba), `.detail-tabs`, `.stats-strip`, `.timeline`, `.items-table`.

- [ ] **Step 1: Crear `ImportDetailHead.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportDetailHead.svelte -->
<script lang="ts">
  import type { Import } from '$lib/data/importaciones';
  import { STATUS_LABELS } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    onRegisterArrival: () => void;
    onClose: () => void;
    onCancel: () => void;
  }

  let { imp, onRegisterArrival, onClose, onCancel }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let canClose = $derived(imp.arrived_at !== null && imp.shipping_gtq !== null && imp.status !== 'closed');

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function statusPillClass(status: string): string {
    return {
      closed:  'bg-[rgba(74,222,128,0.14)] text-[var(--color-live)]',
      paid:    'bg-[rgba(245,165,36,0.16)] text-[var(--color-warning)]',
      arrived: 'bg-[rgba(167,243,208,0.10)] text-[var(--color-ready)]',
      in_transit: 'bg-[rgba(91,141,239,0.16)] text-[var(--color-accent)]',
      draft:   'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]',
      cancelled: 'bg-[rgba(244,63,94,0.14)] text-[var(--color-danger)]',
    }[status] ?? 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)]';
  }
</script>

<div class="px-6 pt-4 pb-3 border-b border-[var(--color-border)]">
  <!-- ID row -->
  <div class="flex items-center gap-3 mb-2.5">
    <span class="text-mono text-[22px] font-bold text-[var(--color-text-primary)]" style="letter-spacing: -0.01em;">
      {imp.import_id}
    </span>
    <span class="text-mono text-[10px] uppercase tracking-wider rounded-[2px] px-2.5 py-1 {statusPillClass(imp.status)}">
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1.5"></span>
      {STATUS_LABELS[imp.status as keyof typeof STATUS_LABELS]}
    </span>
  </div>

  <!-- Meta row -->
  <div class="flex items-center gap-3 flex-wrap text-mono text-[11px] text-[var(--color-text-secondary)] mb-3">
    <strong class="text-[var(--color-text-primary)]">{imp.supplier}</strong>
    <span class="text-[var(--color-border-strong)]">·</span>
    <span>paid {imp.paid_at ?? 'pendiente'}</span>
    {#if leadDays !== null && imp.status !== 'closed'}
      <span class="text-[var(--color-border-strong)]">·</span>
      <span class="text-[var(--color-warning)]">{leadDays} días en pipeline</span>
    {/if}
    <span class="text-[var(--color-border-strong)]">·</span>
    <span>{imp.n_units ?? 0} units</span>
    <a href="#comercial-link" class="text-[var(--color-accent)] inline-flex items-center gap-1 px-2 py-0.5 border border-[rgba(91,141,239,0.3)] rounded-[2px] bg-[rgba(91,141,239,0.06)] hover:bg-[rgba(91,141,239,0.14)] no-underline">
      → Vínculo Comercial
    </a>
  </div>

  <!-- Action toolbar — ARRIBA (D-Diego v2) -->
  <div class="flex items-center gap-2 pt-3 border-t border-[var(--color-surface-2)]">
    <span class="text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] mr-1" style="letter-spacing: 0.08em;">Acciones:</span>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]" onclick={onRegisterArrival}>
      📥 Registrar arrival
    </button>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]">
      📋 Ver invoice PayPal
    </button>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]">
      📋 Ver tracking DHL
    </button>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
      📝 Editar
    </button>
    <span class="flex-1"></span>
    <button class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] bg-transparent border border-[rgba(244,63,94,0.3)] text-[var(--color-danger)] hover:bg-[rgba(244,63,94,0.10)]" onclick={onCancel}>
      🚫 Cancelar batch
    </button>
    <button
      class="text-mono text-[11px] px-3 py-1.5 rounded-[3px] font-semibold transition-colors"
      class:bg-[var(--color-accent)]={canClose}
      class:text-[var(--color-bg)]={canClose}
      class:hover:bg-[var(--color-accent-hover)]={canClose}
      class:bg-[var(--color-surface-2)]={!canClose}
      class:text-[var(--color-text-tertiary)]={!canClose}
      class:cursor-not-allowed={!canClose}
      disabled={!canClose}
      title={canClose ? 'Cerrar batch · prorrateo proporcional D2=B' : 'Disponible cuando arrived_at + shipping_gtq estén llenos'}
      onclick={onClose}
    >
      ✅ Cerrar batch
    </button>
  </div>
</div>
```

- [ ] **Step 2: Crear `ImportDetailSubtabs.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportDetailSubtabs.svelte -->
<script lang="ts">
  type SubtabId = 'overview' | 'items' | 'costos' | 'pagos' | 'timeline';

  interface Props {
    activeSubtab: SubtabId;
    itemsCount: number;
    paymentsCount: number;
  }

  let { activeSubtab = $bindable(), itemsCount, paymentsCount }: Props = $props();

  const SUBTABS: Array<{id: SubtabId; label: string; count?: number}> = [
    { id: 'overview', label: 'Overview' },
    { id: 'items',    label: 'Items',    count: itemsCount },
    { id: 'costos',   label: 'Costos' },
    { id: 'pagos',    label: 'Pagos',    count: paymentsCount },
    { id: 'timeline', label: 'Timeline' },
  ];
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each SUBTABS as st}
    <button
      class="text-mono inline-flex items-baseline gap-1.5 border-b-2 border-transparent px-3.5 py-2.5 text-[10.5px] uppercase transition-colors"
      class:!text-[var(--color-accent)]={activeSubtab === st.id}
      class:!border-[var(--color-accent)]={activeSubtab === st.id}
      class:text-[var(--color-text-secondary)]={activeSubtab !== st.id}
      style="letter-spacing: 0.05em;"
      onclick={() => activeSubtab = st.id}
    >
      {st.label}
      {#if st.count !== undefined && st.count > 0}
        <span class="text-[9.5px] opacity-70">{st.count}</span>
      {/if}
    </button>
  {/each}
</div>
```

- [ ] **Step 3: Crear `OverviewSubtab.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/detail/OverviewSubtab.svelte -->
<script lang="ts">
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    items: ImportItem[];
  }

  let { imp, items }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let totalLandedEst = $derived(imp.total_landed_gtq ?? estimateLanded(imp));
  let landedPerUnit = $derived(imp.unit_cost ?? estimatePerUnit(imp));

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function estimateLanded(i: Import): number | null {
    if (!i.bruto_usd || !i.fx) return null;
    return i.bruto_usd * i.fx + (i.shipping_gtq ?? 0);
  }

  function estimatePerUnit(i: Import): number | null {
    const total = estimateLanded(i);
    if (!total || !i.n_units) return null;
    return total / i.n_units;
  }

  function fmtUsd(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `$${n.toFixed(2)}`;
  }

  function fmtQ(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `Q${Math.round(n).toLocaleString('es-GT')}`;
  }
</script>

<div class="p-6 overflow-y-auto">
  <!-- Stats strip 6 KPIs -->
  <div class="grid grid-cols-6 gap-px bg-[var(--color-border)] border border-[var(--color-border)] rounded-[4px] overflow-hidden mb-6">
    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Bruto USD</div>
      <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{fmtUsd(imp.bruto_usd)}</div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">PayPal · 4.4% incl.</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">DHL door-to-door</div>
      {#if imp.shipping_gtq !== null}
        <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{fmtQ(imp.shipping_gtq)}</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">arrived ✓</div>
      {:else}
        <div class="text-mono text-[16px] font-bold text-[var(--color-warning)]">— pendiente</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">cuando arrive</div>
      {/if}
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Días desde paid</div>
      {#if leadDays !== null}
        <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-accent)]">{leadDays}d</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.status === 'closed' ? 'lead time real' : 'en pipeline'}</div>
      {:else}
        <div class="text-mono text-[16px] font-bold text-[var(--color-text-tertiary)]">—</div>
      {/if}
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Total landed est</div>
      <div class="text-mono text-[16px] font-bold tabular-nums {imp.total_landed_gtq !== null ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'}">
        {imp.total_landed_gtq !== null ? fmtQ(imp.total_landed_gtq) : `~${fmtQ(totalLandedEst)}?`}
      </div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.total_landed_gtq !== null ? 'real · post-close' : 'est · sin DHL real'}</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Units</div>
      <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{imp.n_units ?? 0}</div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">items linkeados</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Landed / unidad</div>
      <div class="text-mono text-[16px] font-bold tabular-nums {imp.unit_cost !== null ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'}">
        {imp.unit_cost !== null ? fmtQ(imp.unit_cost) : `~${fmtQ(landedPerUnit)}`}
      </div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.unit_cost !== null ? 'prorrateo D2=B' : 'estimado pre-cierre'}</div>
    </div>
  </div>

  <!-- Items preview (5 first) -->
  <div class="mb-6">
    <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-2.5 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
      ▸ Items del batch · preview <span class="text-[var(--color-text-tertiary)] normal-case">(ver todo en tab Items)</span>
    </div>

    {#if items.length === 0}
      <div class="text-sm text-[var(--color-text-tertiary)] italic py-4 text-center">Sin items linkeados a este batch</div>
    {:else}
      <table class="w-full text-[11.5px] border-collapse">
        <thead>
          <tr>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">SKU</th>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Spec</th>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Cliente</th>
            <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">USD</th>
            <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Landed Q</th>
          </tr>
        </thead>
        <tbody>
          {#each items.slice(0, 5) as item}
            <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
              <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-primary)]">{item.family_id}{item.is_free_unit ? ' 🎁' : ''}</td>
              <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">
                {item.size ?? ''} · {item.player_name ?? '—'}{item.player_number ? ` ${item.player_number}` : ''}
              </td>
              <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.customer_name ?? '—'}</td>
              <td class="py-1.5 px-2.5 text-right text-mono">{fmtUsd(item.unit_cost_usd)}</td>
              <td class="py-1.5 px-2.5 text-right text-mono text-[var(--color-live)] font-semibold">{fmtQ(item.unit_cost)}</td>
            </tr>
          {/each}
          {#if items.length > 5}
            <tr><td colspan="5" class="text-center py-2 text-[var(--color-text-tertiary)] italic text-xs">+ {items.length - 5} items más · ver tab Items</td></tr>
          {/if}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Timeline (6 stages) -->
  <div class="mb-6">
    <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-2.5 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
      ▸ Timeline del batch
    </div>

    <div class="pl-1.5">
      <!-- DRAFT -->
      <div class="flex gap-3 py-2 relative">
        <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
        <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
        <div class="flex-1">
          <div class="flex items-baseline gap-2.5">
            <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">DRAFT creado</span>
            <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.created_at?.split(' ')[0] ?? '—'}</span>
          </div>
        </div>
      </div>

      <!-- PAID -->
      {#if imp.paid_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">PAID</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.paid_at}</span>
            </div>
            <div class="text-[11px] text-[var(--color-text-secondary)] mt-0.5">PayPal · {fmtUsd(imp.bruto_usd)}</div>
          </div>
        </div>
      {/if}

      <!-- IN_TRANSIT (active si paid sin arrived) -->
      {#if imp.paid_at && !imp.arrived_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-warning)] border-2 border-[var(--color-warning)] flex-shrink-0 mt-1.5 z-10 pulse-live"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-primary)] font-semibold">IN_TRANSIT</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">esperando DHL</span>
              <span class="text-mono text-[10px] text-[var(--color-warning)] px-1.5 py-0.5 bg-[rgba(245,165,36,0.10)] rounded-[2px]">{leadDays}d desde paid</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- ARRIVED -->
      {#if imp.arrived_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full {imp.status === 'closed' ? 'bg-[var(--color-live)] border-2 border-[var(--color-live)]' : 'bg-[var(--color-warning)] border-2 border-[var(--color-warning)] pulse-live'} flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] {imp.status === 'closed' ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-primary)]'} font-semibold">ARRIVED</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.arrived_at}</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- CLOSED -->
      {#if imp.status === 'closed'}
        <div class="flex gap-3 py-2 relative">
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">CLOSED</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">prorrateo aplicado</span>
            </div>
            <div class="text-[11px] text-[var(--color-text-secondary)] mt-0.5">unit_cost {fmtQ(imp.unit_cost)} aplicado a sale_items + jerseys</div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>
```

- [ ] **Step 4: Update ImportDetailPane.svelte para componer**

```svelte
<!-- overhaul/src/lib/components/importaciones/ImportDetailPane.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import ImportDetailHead from './ImportDetailHead.svelte';
  import ImportDetailSubtabs from './ImportDetailSubtabs.svelte';
  import OverviewSubtab from './detail/OverviewSubtab.svelte';
  import { adapter } from '$lib/adapter';
  import type { Import, ImportItem } from '$lib/data/importaciones';

  type SubtabId = 'overview' | 'items' | 'costos' | 'pagos' | 'timeline';

  interface Props {
    imp: Import | null;
    onUpdated: () => void;
  }

  let { imp, onUpdated }: Props = $props();

  let items = $state<ImportItem[]>([]);
  let activeSubtab = $state<SubtabId>('overview');

  $effect(() => {
    if (imp) loadItems(imp.import_id);
    else items = [];
  });

  async function loadItems(id: string) {
    items = await adapter.getImportItems(id);
  }

  function handleRegisterArrival() {
    // R1.x: modal de registro · por ahora prompt simple
    alert('Registrar arrival viene en R1.x — flow: input arrived_at + shipping_gtq');
  }

  function handleClose() {
    if (!imp) return;
    if (!confirm(`Cerrar batch ${imp.import_id}?\nEsto aplica prorrateo proporcional D2=B a ${items.length} items.`)) return;
    // Implementar en Task 13
    alert('Close batch viene en Task 13 (close_import_proportional)');
  }

  function handleCancel() {
    alert('Cancelar batch viene en R1.x');
  }
</script>

<div class="flex-1 flex flex-col min-w-0 overflow-hidden">
  {#if !imp}
    <div class="flex flex-1 items-center justify-center text-[var(--color-text-tertiary)]">
      Seleccioná un batch del panel izquierdo
    </div>
  {:else}
    <ImportDetailHead {imp} onRegisterArrival={handleRegisterArrival} onClose={handleClose} onCancel={handleCancel} />
    <ImportDetailSubtabs bind:activeSubtab itemsCount={items.length} paymentsCount={imp.bruto_usd ? 1 : 0} />

    <div class="flex-1 overflow-y-auto">
      {#if activeSubtab === 'overview'}
        <OverviewSubtab {imp} {items} />
      {:else if activeSubtab === 'items'}
        <!-- Task 12 lo llena -->
        <div class="p-6 text-[var(--color-text-tertiary)]">Items table viene en Task 12</div>
      {:else if activeSubtab === 'costos'}
        <div class="p-6 text-[var(--color-text-tertiary)]">Cost flow detallado viene en Task 12</div>
      {:else if activeSubtab === 'pagos'}
        <div class="p-6 text-[var(--color-text-tertiary)]">Lista de pagos viene en R1.x</div>
      {:else if activeSubtab === 'timeline'}
        <div class="p-6 text-[var(--color-text-tertiary)]">Timeline expandido viene en R1.x</div>
      {/if}
    </div>
  {/if}
</div>
```

- [ ] **Step 5: npm run check + smoke**

`npm run tauri dev` → tab Pedidos → click batch → detail pane completo con head + action toolbar arriba + sub-tabs + Overview con stats strip 6 KPIs + items preview (4-5 rows) + timeline 4-5 stages segun status del batch.

Smoke check específico para IMP-2026-04-07:
- Stats: $345.38 · Q523 · 8d · Q3,182 · 22u · Q145 (todos verdes/normal porque CLOSED)
- Items preview con 5 rows (al menos 1 con cliente)
- Timeline mostrando DRAFT/PAID/ARRIVED/CLOSED

Para IMP-2026-04-18:
- Stats: $372.64 · "— pendiente" amber · 9d · "~Q2,869?" amber · 27u · "~Q106" amber
- Timeline mostrando DRAFT/PAID/IN_TRANSIT (con pulse-live)

- [ ] **Step 6: Commit**

```bash
git add overhaul/src/lib/components/importaciones/
git commit -m "feat(imp): ImportDetailPane completo · head con action toolbar arriba · subtabs · Overview con stats strip + items preview + timeline"
```

---

### Task 12: ItemsSubtab + CostosSubtab — full table + cost flow detallado

**Files:**
- Create: `overhaul/src/lib/components/importaciones/detail/ItemsSubtab.svelte`
- Create: `overhaul/src/lib/components/importaciones/detail/CostosSubtab.svelte`
- Modify: `overhaul/src/lib/components/importaciones/ImportDetailPane.svelte` (wire los subtabs)

**Reference visual:** mockup HD v2 `.items-table` (full table con SKU/Variante/Spec/Asignado/Status/USD/Landed/Margen) y la sección "Cost flow detallado" que se sacó del Overview.

- [ ] **Step 1: Crear `ItemsSubtab.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/detail/ItemsSubtab.svelte -->
<script lang="ts">
  import type { ImportItem } from '$lib/data/importaciones';

  interface Props { items: ImportItem[]; }
  let { items }: Props = $props();

  let sortBy = $state<'sku' | 'usd' | 'landed' | 'customer'>('sku');
  let sortDesc = $state(false);

  let sorted = $derived([...items].sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'sku') cmp = a.family_id.localeCompare(b.family_id);
    else if (sortBy === 'usd') cmp = (a.unit_cost_usd ?? 0) - (b.unit_cost_usd ?? 0);
    else if (sortBy === 'landed') cmp = (a.unit_cost ?? 0) - (b.unit_cost ?? 0);
    else if (sortBy === 'customer') cmp = (a.customer_name ?? '').localeCompare(b.customer_name ?? '');
    return sortDesc ? -cmp : cmp;
  }));

  function setSort(col: typeof sortBy) {
    if (sortBy === col) sortDesc = !sortDesc;
    else { sortBy = col; sortDesc = false; }
  }

  function fmtUsd(n: number | null | undefined): string {
    return n === null || n === undefined ? '—' : `$${n.toFixed(2)}`;
  }
  function fmtQ(n: number | null | undefined): string {
    return n === null || n === undefined ? '—' : `Q${Math.round(n).toLocaleString('es-GT')}`;
  }
</script>

<div class="p-6 overflow-y-auto">
  <table class="w-full text-[11.5px] border-collapse">
    <thead class="bg-[var(--color-bg)] sticky top-0">
      <tr>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('sku')}>
          SKU {#if sortBy === 'sku'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Variante</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Spec (player)</th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('customer')}>
          Asignado {#if sortBy === 'customer'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]">Source</th>
        <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('usd')}>
          USD chino {#if sortBy === 'usd'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
        <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)] cursor-pointer" onclick={() => setSort('landed')}>
          Landed Q {#if sortBy === 'landed'}{sortDesc ? '↓' : '↑'}{/if}
        </th>
      </tr>
    </thead>
    <tbody>
      {#each sorted as item (item.source_table + ':' + item.source_id)}
        <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
          <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-primary)]">
            {item.family_id}
            {#if item.is_free_unit}
              <span class="ml-1 text-mono text-[9px] px-1.5 py-0.5 bg-[rgba(167,243,208,0.12)] text-[var(--color-ready)] rounded-[2px]">FREE</span>
            {/if}
          </td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.size ?? '—'} · {item.version ?? '—'}</td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">
            {#if item.player_name}{item.player_name}{:else}—{/if}
            {#if item.player_number}<span class="text-[var(--color-text-tertiary)]"> #{item.player_number}</span>{/if}
            {#if item.patch}<span class="text-[var(--color-text-tertiary)]"> · {item.patch}</span>{/if}
          </td>
          <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.customer_name ?? (item.customer_id ? '(loading)' : 'stock')}</td>
          <td class="py-1.5 px-2.5 text-mono text-[10px] text-[var(--color-text-tertiary)] uppercase">{item.source_table === 'sale_items' ? 'sale' : 'jersey'}</td>
          <td class="py-1.5 px-2.5 text-right text-mono">{fmtUsd(item.unit_cost_usd)}</td>
          <td class="py-1.5 px-2.5 text-right text-mono text-[var(--color-live)] font-semibold">{fmtQ(item.unit_cost)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
```

- [ ] **Step 2: Crear `CostosSubtab.svelte`**

```svelte
<!-- overhaul/src/lib/components/importaciones/detail/CostosSubtab.svelte -->
<script lang="ts">
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props { imp: Import; items: ImportItem[]; }
  let { imp, items }: Props = $props();

  let totalUsd = $derived(items.reduce((s, i) => s + (i.unit_cost_usd ?? 0), 0));
  let payPalFee = $derived(imp.bruto_usd ? imp.bruto_usd * 0.044 : 0);
  let totalLanded = $derived(imp.total_landed_gtq ?? (imp.bruto_usd && imp.fx ? imp.bruto_usd * imp.fx + (imp.shipping_gtq ?? 0) : null));

  function fmtUsd(n: number | null | undefined): string { return n === null || n === undefined ? '—' : `$${n.toFixed(2)} USD`; }
  function fmtQ(n: number | null | undefined): string { return n === null || n === undefined ? '—' : `Q${Math.round(n).toLocaleString('es-GT')}`; }
</script>

<div class="p-6 max-w-[800px]">
  <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-3 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
    ▸ Cost flow · cómo se llega al landed cost
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-4">
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">PayPal bruto al supplier</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">{fmtUsd(imp.bruto_usd)}</span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">PayPal fee (~4.4% incluido en bruto)</span>
      <span class="text-mono text-[var(--color-text-tertiary)] tabular-nums">~{fmtUsd(payPalFee)}</span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">DHL door-to-door (shipping + impuestos GT)</span>
      <span class="text-mono tabular-nums {imp.shipping_gtq !== null ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-warning)]'}">
        {imp.shipping_gtq !== null ? fmtQ(imp.shipping_gtq) : '— pendiente'}
      </span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">FX USD → GTQ</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">× {imp.fx.toFixed(2)}</span>
    </div>

    <div class="flex justify-between pt-2.5 mt-1.5 border-t border-dashed border-[var(--color-border)] text-[12px]">
      <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] italic">{fmtUsd(imp.bruto_usd)} × {imp.fx.toFixed(2)} + DHL = total_landed</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">{fmtUsd(imp.bruto_usd)} × {imp.fx.toFixed(2)} = {fmtQ(imp.bruto_usd ? imp.bruto_usd * imp.fx : null)}</span>
    </div>

    <div class="flex justify-between pt-2.5 mt-1 border-t border-[var(--color-border)] text-[12px]">
      <span class="text-[var(--color-text-primary)] font-semibold">
        Total landed batch <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] font-normal">(D2=B prorrateo proporcional al USD per item)</span>
      </span>
      <span class="text-mono text-[14px] font-bold text-[var(--color-live)] tabular-nums">{fmtQ(totalLanded)}</span>
    </div>
  </div>

  <div class="mt-4 text-mono text-[10.5px] text-[var(--color-text-tertiary)] italic">
    Nota: prorrateo D2=B aplicado al close usa el USD chino per item (de chat WA `11+2=13`). Items con USD null reciben default uniforme = bruto/n_units.
  </div>
</div>
```

- [ ] **Step 3: Wire los subtabs en ImportDetailPane**

Modificar `ImportDetailPane.svelte` reemplazando los placeholders de items y costos con los componentes reales:

```svelte
<!-- En ImportDetailPane.svelte, importar -->
<script>
  import ItemsSubtab from './detail/ItemsSubtab.svelte';
  import CostosSubtab from './detail/CostosSubtab.svelte';
  // … resto igual
</script>

<!-- Reemplazar placeholders -->
{:else if activeSubtab === 'items'}
  <ItemsSubtab {items} />
{:else if activeSubtab === 'costos'}
  <CostosSubtab {imp} {items} />
```

- [ ] **Step 4: npm run check + smoke**

Verificar tab Items muestra todos los 22 items del IMP-04-07 (sortable). Tab Costos muestra el cost flow con valores reales.

- [ ] **Step 5: Commit**

```bash
git add overhaul/src/lib/components/importaciones/detail/
git commit -m "feat(imp): ItemsSubtab full sortable table + CostosSubtab cost flow detallado"
```

---

### Task 13: close_import_proportional() — Rust command D2=B

**Files:**
- Modify: `overhaul/src-tauri/src/lib.rs`
- Modify: `overhaul/src/lib/adapter/tauri.ts`
- Modify: `overhaul/src/lib/adapter/browser.ts`
- Modify: `overhaul/src/lib/components/importaciones/ImportDetailPane.svelte` (wire close)

- [ ] **Step 1: Implementar `cmd_close_import_proportional` en Rust**

```rust
// En lib.rs, después de cmd_get_import_pulso

#[derive(Debug, Serialize)]
pub struct CloseImportResult {
    pub ok: bool,
    pub n_items_updated: usize,
    pub n_jerseys_updated: usize,
    pub total_landed_gtq: f64,
    pub avg_unit_cost: f64,
    pub method: &'static str,
}

#[tauri::command]
pub async fn cmd_close_import_proportional(
    _app: tauri::AppHandle,
    import_id: String,
) -> Result<CloseImportResult> {
    let mut conn = rusqlite::Connection::open(db_path())?;
    let tx = conn.transaction()?;

    // 1. Read import
    let (bruto_usd, shipping_gtq, fx, status): (Option<f64>, Option<f64>, f64, String) = tx.query_row(
        "SELECT bruto_usd, shipping_gtq, COALESCE(fx, 7.73), status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    if status == "closed" {
        return Err(ErpError::Other(format!("Import {} ya está closed", import_id)));
    }

    let bruto = bruto_usd.ok_or_else(|| ErpError::Other("bruto_usd is null".into()))?;
    let shipping = shipping_gtq.ok_or_else(|| ErpError::Other(
        "shipping_gtq is null · necesita registrar arrival con DHL invoice antes de cerrar".into()
    ))?;

    let total_landed = bruto * fx + shipping;

    // 2. Read all items (sale_items + jerseys) con sus unit_cost_usd
    let mut sale_items: Vec<(i64, Option<f64>)> = tx.prepare(
        "SELECT id, unit_cost_usd FROM sale_items WHERE import_id = ?1"
    )?.query_map(rusqlite::params![&import_id], |r| Ok((r.get(0)?, r.get(1)?)))?
       .collect::<std::result::Result<Vec<_>, _>>()?;

    let mut jerseys: Vec<(i64, Option<f64>)> = tx.prepare(
        "SELECT rowid, unit_cost_usd FROM jerseys WHERE import_id = ?1"
    )?.query_map(rusqlite::params![&import_id], |r| Ok((r.get(0)?, r.get(1)?)))?
       .collect::<std::result::Result<Vec<_>, _>>()?;

    let n_total = sale_items.len() + jerseys.len();
    if n_total == 0 {
        return Err(ErpError::Other("No items linkeados a este import".into()));
    }

    // 3. Compute total USD (D2=B). Si algún item tiene unit_cost_usd null, default uniforme
    let usd_default = bruto / n_total as f64;
    let total_usd_present: f64 = sale_items.iter().chain(jerseys.iter())
        .map(|(_, usd)| usd.unwrap_or(usd_default)).sum();

    // 4. Aplicar prorrateo proporcional
    for (id, usd_opt) in &sale_items {
        let usd = usd_opt.unwrap_or(usd_default);
        let landed_gtq = (usd / total_usd_present) * total_landed;
        tx.execute(
            "UPDATE sale_items SET unit_cost = ? WHERE id = ?",
            rusqlite::params![landed_gtq.round() as i64, id],
        )?;
    }
    for (rowid, usd_opt) in &jerseys {
        let usd = usd_opt.unwrap_or(usd_default);
        let landed_gtq = (usd / total_usd_present) * total_landed;
        tx.execute(
            "UPDATE jerseys SET cost = ? WHERE rowid = ?",
            rusqlite::params![landed_gtq.round() as i64, rowid],
        )?;
    }

    // 5. Update imports row
    let avg_unit = total_landed / n_total as f64;
    let lead_time = tx.query_row(
        "SELECT CAST((julianday(arrived_at) - julianday(paid_at)) AS INTEGER)
         FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |r| r.get::<_, Option<i64>>(0),
    ).unwrap_or(None);

    tx.execute(
        "UPDATE imports SET
            status = 'closed',
            total_landed_gtq = ?,
            n_units = ?,
            unit_cost = ?,
            lead_time_days = ?
         WHERE import_id = ?",
        rusqlite::params![total_landed, n_total as i64, avg_unit.round(), lead_time, import_id],
    )?;

    tx.commit()?;

    Ok(CloseImportResult {
        ok: true,
        n_items_updated: sale_items.len(),
        n_jerseys_updated: jerseys.len(),
        total_landed_gtq: total_landed,
        avg_unit_cost: avg_unit,
        method: "D2=B (proportional by USD)",
    })
}
```

- [ ] **Step 2: Registrar el command**

En el `tauri::generate_handler!` agregar:

```rust
cmd_close_import_proportional,
```

- [ ] **Step 3: cargo check**

```bash
cd overhaul/src-tauri
cargo check
```

- [ ] **Step 4: Adapter — agregar invocación**

```typescript
// tauri.ts
export interface CloseImportResult {
  ok: boolean;
  n_items_updated: number;
  n_jerseys_updated: number;
  total_landed_gtq: number;
  avg_unit_cost: number;
  method: string;
}

export async function closeImportProportional(import_id: string): Promise<CloseImportResult> {
  return invoke('cmd_close_import_proportional', { importId: import_id });
}
```

```typescript
// browser.ts
export async function closeImportProportional(_id: string): Promise<CloseImportResult> {
  throw new NotAvailableInBrowser('closeImportProportional requires Tauri');
}
```

- [ ] **Step 5: Wire en ImportDetailPane.svelte**

```svelte
async function handleClose() {
  if (!imp) return;
  if (!confirm(`Cerrar batch ${imp.import_id}?\nProrrateo D2=B aplicado a ${items.length} items.`)) return;

  try {
    const res = await adapter.closeImportProportional(imp.import_id);
    alert(`Batch cerrado · ${res.n_items_updated} sale_items + ${res.n_jerseys_updated} jerseys actualizados\nLanded total: Q${Math.round(res.total_landed_gtq)} · Avg/u: Q${Math.round(res.avg_unit_cost)}`);
    onUpdated();
  } catch (e) {
    alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
  }
}
```

- [ ] **Step 6: npm run check + cargo check + smoke**

**WARNING destructivo:** smoke test del close debe hacerse en una **copia de la DB**, no en producción. Antes de probar:

```bash
cp C:/Users/Diego/el-club/erp/elclub.db C:/Users/Diego/el-club/erp/elclub.db.backup-pre-close-test
```

Después: smoke test con IMP-2026-04-18 simulando arrival (entrar `arrived_at` y `shipping_gtq` directamente en SQL, o mejor diferir el smoke hasta R1.x cuando exista el flow de "Registrar arrival" en UI). Para R1, basta con verificar que el botón está disabled correctamente cuando arrived_at está null.

Si querés testear el cálculo: cerrar IMP-2026-04-07 está prohibido porque ya está closed. Crear un import test con `INSERT INTO imports (...)` y dummy items para validar.

- [ ] **Step 7: Commit**

```bash
git add overhaul/src-tauri/src/lib.rs overhaul/src/lib/adapter/ overhaul/src/lib/components/importaciones/ImportDetailPane.svelte
git commit -m "feat(imp): close_import_proportional D2=B (prorrateo por USD)

- Tauri command transaccional · ACID
- Loop por sale_items + jerseys con weight = item.usd / sum(usd)
- Default uniforme bruto/n para items con USD null
- Auto-update lead_time_days desde paid_at→arrived_at
- Wire en detail pane con confirm dialog"
```

---

### Task 14: Verification + version bump v0.1.39 + build MSI

**Files:**
- Modify: `overhaul/src-tauri/Cargo.toml`
- Modify: `overhaul/src-tauri/tauri.conf.json`
- Modify: `overhaul/package.json`

- [ ] **Step 1: Bump version 0.1.38 → 0.1.39 en los 3 archivos**

```bash
# Cargo.toml
sed -i 's/version = "0.1.38"/version = "0.1.39"/' overhaul/src-tauri/Cargo.toml

# tauri.conf.json (buscar el "version" field)
sed -i 's/"version": "0.1.38"/"version": "0.1.39"/' overhaul/src-tauri/tauri.conf.json

# package.json
sed -i 's/"version": "0.1.38"/"version": "0.1.39"/' overhaul/package.json
```

Verificar manualmente que los 3 reflejan 0.1.39.

- [ ] **Step 2: Full check**

```bash
cd overhaul
npm run check
cd src-tauri && cargo check && cd ..
```

Expected: 0 errors en ambos.

- [ ] **Step 3: Build MSI (gate final)**

```bash
npm run tauri build
```

Expected: build exitoso, MSI generado en `src-tauri/target/release/bundle/msi/`.

- [ ] **Step 4: Smoke test full**

Instalar el MSI nuevo (o ejecutar `npm run tauri dev`) y verificar:

1. Sidebar tiene "Importaciones" con icono Ship
2. Click → módulo carga
3. Pulso bar muestra valores reales (Q3,182 closed YTD, Q145 avg, 8 días lead time)
4. List pane muestra 2 batches reales con mini-progress correcto
5. Click batch → detail pane con head + action toolbar arriba + 5 sub-tabs
6. Overview muestra stats strip 6 KPIs + items preview + timeline
7. Tab Items muestra todos los items linkeados con USD/Landed
8. Tab Costos muestra cost flow detallado
9. Otros tabs (Wishlist, Margen, Free, Supplier, Settings) muestran placeholders "Próximamente"
10. Cerrar batch (botón) está disabled para IMP-04-18 hasta que tenga arrived_at + shipping_gtq

- [ ] **Step 5: Tag y push**

```bash
git tag v0.1.39
git push origin importaciones-r1
git push origin v0.1.39
```

- [ ] **Step 6: Commit final + merge to main**

```bash
git add overhaul/src-tauri/Cargo.toml overhaul/src-tauri/tauri.conf.json overhaul/package.json
git commit -m "chore(imp): bump version to v0.1.39 · IMP-R1 ship

- Schema additions sobre elclub.db compartida (ALTER + 2 tables nuevas)
- 5 commands Rust nuevos (list/get/items/pulso/close_proportional)
- Module Importaciones con 6 tabs (Pedidos funcional · 5 placeholders R2-R6)
- Detail pane in-place con head + action toolbar arriba + 5 sub-tabs
- D2=B prorrateo proporcional implementado
- Lead time observability (3 niveles: row badge + pulso + timeline)
- 2 imports históricos visibles con UX nueva

Spec: docs/superpowers/specs/2026-04-27-importaciones-design.md
Plan: docs/superpowers/plans/2026-04-27-importaciones-IMP-R1.md
Brainstorm: .superpowers/brainstorm/1923-1777335894/"

# Después de merge approval
git checkout main
git merge --no-ff importaciones-r1
git push origin main --tags
```

---

## Self-Review checklist

Después de completar las 14 tasks, verificar contra el spec:

**1. Spec coverage:**
- [ ] Sec 4 Tab Pedidos · list-detail in-place — Tasks 8-12 ✓
- [ ] Sec 4 Tab Wishlist — placeholder R2 ✓
- [ ] Sec 4 Tab Margen real — placeholder R3 ✓
- [ ] Sec 4 Tab Free units — placeholder R4 ✓
- [ ] Sec 4 Tab Supplier — placeholder R5 ✓
- [ ] Sec 4 Tab Settings — placeholder R6 ✓
- [ ] Sec 5 Detail pane in-place + action toolbar arriba — Task 11 ✓
- [ ] Sec 5 Stats strip 6 KPIs · sin FX — Task 11 ✓
- [ ] Sec 5 close_import_proportional D2=B — Task 13 ✓
- [ ] Sec 5 Lead time 3 niveles (row · pulso · stage) — Tasks 8-9 ✓
- [ ] Sec 6 D-FX 7.73 — Task 1 step 2 (Rust enforces · default) + Task 3 (COALESCE 7.73) ✓
- [ ] Sec 7 Schema additions — Task 1 ✓
- [ ] Sec 7 Tablas wishlist + free_unit creadas — Task 1 step 2 ✓
- [ ] Sec 9 Tokens visuales heredados — todos los componentes usan `var(--color-*)` ✓
- [ ] Sec 10 R1 scope — todas las tasks ✓

**2. Placeholder scan:** ningún task tiene "TBD", "TODO", "fill in details" — fix si aparecen.

**3. Type consistency:** verificar que `closeImportProportional` (camelCase JS) ↔ `cmd_close_import_proportional` (snake Rust) ↔ `cmd_close_import_proportional` registrado en handler. ✓

**4. Mockup HD reference:** todos los componentes Svelte deben tener match visual con `06-mockup-a1-hd-v2.html`. Smoke test final compara lado a lado.

---

## Execution Handoff

**Plan complete and saved to `el-club/overhaul/docs/superpowers/plans/2026-04-27-importaciones-IMP-R1.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - dispatch fresh subagent per task · review entre tasks · fast iteration. Necesario para R1 dado el tamaño (14 tasks).

**2. Inline Execution** - executar tasks en sesión current con executing-plans · batch execution con checkpoints. Útil si Diego quiere observar cada task en vivo.

Diego elegirá al lanzar la sesión paralela vía starter (`docs/starters/2026-04-27-imp-r1-build-starter.md`).
