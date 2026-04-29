# IMP-R6 Implementation Plan — Settings Tab + Polish Pass (último release)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans para ejecutar task-by-task. Steps usan checkbox (`- [ ]`) para tracking. R6 es el último release · ships en Wave 2 junto a R3/R4/R5 · NO blocker para los demás.

**Goal:** Cerrar el módulo IMP con (a) tab **Settings** completo (defaults editables + umbrales inbox + migration log read-only + integrations placeholders) y (b) **POLISH PASS** sobre TODOS los tabs (R2-R5 + Pedidos): empty states pulidos · loading skeletons consistentes · browser fallback completo · error states con visual language unificado. Además: shippear `apply_imp_schema.py` (script idempotente · corre 1 vez post-merge en main DB).

**Architecture:** Settings persiste en nueva tabla key/value `imp_settings` (NO existe sistema de settings previo en lib.rs · verificado con grep). 5 commands Rust nuevos (4 smoke-only · 1 TDD-light por validación). Tab Settings con 4 secciones colapsables. Polish pass es task-per-tab · sin nuevos componentes (refactor in-place). Re-sync button STUB-disabled (decision · ver Open Questions). Sin deps nuevas.

**Tech Stack:** Rust 1.70 + rusqlite 0.32 + Tauri 2 + Svelte 5 (`$state`/`$derived`/`$effect`) + TypeScript + Tailwind v4 + JetBrains Mono · Python 3 stdlib (sqlite3) para script · 0 deps nuevas.

---

## Cross-release dependencies

- **R2/R3/R5 → R6**: nada (ninguno lee settings en v0.4.0)
- **R4 → R6**: free_ratio default queda HARDCODED en 10 en R4 · NO se cablea a `imp_settings` en v0.4.0 (decisión escalada · ver Open Questions). En v0.5 se cablea.
- **R6 → ningún release**: R6 puede ejecutarse último sin bloquear nada
- **Inbox events plumbing**: R6 ALMACENA los thresholds; Comercial es responsable de CONSUMIRLOS (out of scope para v0.4.0). Documentado como follow-up.

---

## File Structure

### Files to create (10 nuevos)

| Path | Responsabilidad |
|---|---|
| `el-club-imp/erp/scripts/apply_imp_schema.py` | Script idempotente · CREATE TABLE IF NOT EXISTS para wishlist/free_unit/imp_settings/import_items (4 tablas) · CREATE INDEX IF NOT EXISTS (8 indexes) · seed defaults · backup MANDATORY pre-apply · safety prompt si --apply contra main DB |
| `el-club-imp/erp/scripts/smoke_apply_imp_schema.py` | Smoke del script anterior · ejecuta 2 veces sobre temp DB para verificar idempotencia |
| `el-club-imp/erp/scripts/smoke_imp_r6.py` | Smoke SQL post-implementation · ejercita 5 commands settings · verifica state DB |
| `el-club-imp/overhaul/src-tauri/tests/imp_r6_settings_test.rs` | TDD-light: cmd_update_imp_setting valida tipo per key · happy path + 4 invalid value cases |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/ImportSettingsTab.svelte` | REPLACE 6-line stub · ~280 LOC · 4 secciones colapsables (Defaults · Umbrales · Migration log · Integrations) |
| `el-club-imp/overhaul/src/lib/components/importaciones/SettingsSection.svelte` | Wrapper colapsable reusable · header con caret + title uppercase + body slot |
| `el-club-imp/overhaul/src/lib/components/importaciones/SettingsField.svelte` | Field genérico · label + input type=number/text + validation hint + save button (per row) |
| `el-club-imp/overhaul/src/lib/components/importaciones/MigrationLogPanel.svelte` | Read-only panel · table con timestamps + counts + "Re-sync" button DISABLED+title |
| `el-club-imp/overhaul/src/lib/components/importaciones/IntegrationsStatusPanel.svelte` | Read-only · 3 rows (elclub.db active · PayPal OCR disabled · DHL API disabled) |
| `el-club-imp/overhaul/src/lib/components/shared/EmptyState.svelte` | (Opcional · si polish pass lo requiere · cero LOC si los empty states ya están inline en cada tab) |

### Files to modify (12 existentes)

| Path | Cambio | Líneas afectadas est. |
|---|---|---|
| `el-club-imp/overhaul/src-tauri/src/lib.rs` | 5 commands (impl_X + cmd_X split per convention block lib.rs:2730-2742) + 3 structs · helper `get_setting_or_default` · wire `generate_handler!` | +220 |
| `el-club-imp/overhaul/src/lib/adapter/types.ts` | 3 interfaces (ImpSetting · MigrationLog · IntegrationsStatus) + 5 method signatures | +35 |
| `el-club-imp/overhaul/src/lib/adapter/tauri.ts` | 5 invocations | +40 |
| `el-club-imp/overhaul/src/lib/adapter/browser.ts` | 5 stub fallbacks (4 throw NotAvailableInBrowser · 1 returns hardcoded defaults para get_imp_settings dev preview) | +30 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte` (R2) | Polish pass · empty state per spec sec 8 line 621 + loading skeleton + error banner | +25 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte` (R3) | Polish pass · empty state ("Sin batches closed todavía...") + loading skeleton + error banner | +25 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte` (R4) | Polish pass · empty state ("Sin free units · se generan al close batch") + loading skeleton + error banner | +25 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte` (R5) | Polish pass · empty state ("Sin métricas · necesitás 1 batch closed") + loading skeleton + error banner | +20 |
| `el-club-imp/overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte` | Audit: ensure parity (canonical reference · expected ya bien · solo verify error banner present) | +5 |
| `el-club-imp/overhaul/src/lib/components/importaciones/NewImportModal.svelte` (R1.5) | Polish modal: verify ESC + click-outside + disabled-during-submitting consistente | +0-3 |
| `el-club-imp/overhaul/src/lib/components/importaciones/RegisterArrivalModal.svelte` + `EditImportModal.svelte` + `ConfirmCancelModal.svelte` (R1.5) + R2 wishlist modals + R4 AssignDestination + R2 PromoteToBatch | Audit checklist · fix solo si gap detectado | +0-10 (estimado) |
| `el-club-imp/overhaul/src/app.css` | (Opcional) tokens nuevos para skeleton shimmer animation si no existen · `--skeleton-bg` + `@keyframes shimmer` | +0-15 |

**Total estimado:** ~470 líneas net nuevas (Rust ~220 · TS ~105 · Svelte ~280 - 6 stub = +274 net + polish ~110 · CSS ~15 · Python ~170 + 110 smoke = ~280 · +30 LOC apply_imp_schema.py por import_items + safety prompt).

---

## Pre-flight (verify worktree state)

### Task 0: Pre-flight verification

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Verify worktree branch**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git status -sb
```
Expected: `## imp-r2-r6-build` · sin uncommitted (o solo R2-R5 en progreso)

- [ ] **Step 2: Verify NO existing settings table** (sanity)

Run:
```bash
python -c "import sqlite3; c=sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%settings%'\").fetchall()])"
```
Expected: `[]` (vacío · no hay settings table previa)

- [ ] **Step 3: Verify import_wishlist + import_free_unit YA existen** (R1)

Run:
```bash
python -c "import sqlite3; c=sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('import_wishlist','import_free_unit')\").fetchall()])"
```
Expected: `['import_wishlist', 'import_free_unit']` (creadas en R1)

- [ ] **Step 4: Verify R2-R5 ya merged a rama (si polish pass arranca después)**

Run:
```bash
cd C:/Users/Diego/el-club-imp && git log --oneline -20 | grep -E "imp-r[2345]"
```
Expected: commits de R2/R3/R4/R5 visibles (R6 es último · si NO están merged · pause y notify)

---

## Task Group 1: Schema migration script (HIGH PRIORITY · ships first)

R6 settings necesita la tabla `imp_settings` · y el script es deliverable separado del DoD del starter. Hacelo PRIMERO porque no depende de Rust ni Svelte.

### Task 1: Write `apply_imp_schema.py` script

**Files:**
- Create: `el-club-imp/erp/scripts/apply_imp_schema.py`

- [ ] **Step 1: Write the script**

Create `el-club-imp/erp/scripts/apply_imp_schema.py`:

```python
#!/usr/bin/env python3
"""
apply_imp_schema.py — idempotent IMP schema applicator.

Crea (IF NOT EXISTS) las tablas + indexes que IMP necesita en main elclub.db:
- import_wishlist (R2)
- import_free_unit (R4)
- imp_settings (R6) + seed defaults
- 4 indexes (per spec sec 7)

Safe to re-run. Backup obligatorio cuando --apply (no --dry-run).

Usage:
  python apply_imp_schema.py --dry-run                 # preview cambios
  python apply_imp_schema.py --apply                   # apply + backup pre-change
  python apply_imp_schema.py --apply --db-path X.db    # explicit DB
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = os.environ.get(
    "ERP_DB_PATH",
    r"C:/Users/Diego/el-club/erp/elclub.db",
)

# ── Schema definitions (MUST stay in sync with spec sec 7 lines 499-535) ─────

WISHLIST_SCHEMA = """
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
);
"""

FREE_UNIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS import_free_unit (
  free_unit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id        TEXT NOT NULL,
  family_id        TEXT,
  jersey_id        TEXT,
  destination      TEXT
                   CHECK(destination IS NULL OR destination IN ('vip','mystery','garantizada','personal')),
  destination_ref  TEXT,
  assigned_at      TEXT,
  assigned_by      TEXT,
  notes            TEXT,
  created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);
"""
# NOTA: la convención NULL (no string 'unassigned') fue ratificada Diego 2026-04-28 ~19:00.
# La tabla R1 NO se creó con CHECK · este IF NOT EXISTS solo aplica si la tabla aún no existe en main DB.
# Si la tabla ya existe en main DB sin CHECK (como en worktree), NO se altera (SQLite no soporta ADD CHECK
# vía ALTER · requeriría re-create destructivo · skip en v0.4.0 · enforced en Rust via VALID_FREE_DESTINATIONS).

IMPORT_ITEMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS import_items (
  import_item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id           TEXT NOT NULL REFERENCES imports(import_id),
  wishlist_item_id    INTEGER REFERENCES import_wishlist(wishlist_item_id),
  family_id           TEXT NOT NULL,
  jersey_id           TEXT,
  size                TEXT,
  player_name         TEXT,
  player_number       INTEGER,
  patch               TEXT,
  version             TEXT,
  customer_id         TEXT,
  expected_usd        REAL,
  unit_cost_usd       REAL,
  unit_cost_gtq       REAL,
  status              TEXT DEFAULT 'pending'
                      CHECK(status IN ('pending','arrived','sold','published','cancelled')),
  sale_item_id        INTEGER REFERENCES sale_items(item_id),
  jersey_id_published TEXT REFERENCES jerseys(jersey_id),
  notes               TEXT,
  created_at          TEXT DEFAULT (datetime('now', 'localtime'))
);
"""
# customer_id NO se agrega a sale_items · Diego eligió usar import_items (nueva tabla) para tracking
# pre-venta · sale_items se llena solo cuando hay venta real (Comercial flow). Ver Open Question Q6.

IMP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS imp_settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT DEFAULT (datetime('now', 'localtime')),
  updated_by  TEXT
);
"""

INDEXES = [
    ("idx_wishlist_status", "CREATE INDEX IF NOT EXISTS idx_wishlist_status ON import_wishlist(status);"),
    ("idx_wishlist_customer", "CREATE INDEX IF NOT EXISTS idx_wishlist_customer ON import_wishlist(customer_id);"),
    ("idx_free_unit_import", "CREATE INDEX IF NOT EXISTS idx_free_unit_import ON import_free_unit(import_id);"),
    ("idx_free_unit_destination", "CREATE INDEX IF NOT EXISTS idx_free_unit_destination ON import_free_unit(destination);"),
    # import_items indexes (R6 NEW · 4 indexes para query patterns esperados)
    ("idx_import_items_import_id", "CREATE INDEX IF NOT EXISTS idx_import_items_import_id ON import_items(import_id);"),
    ("idx_import_items_family_id", "CREATE INDEX IF NOT EXISTS idx_import_items_family_id ON import_items(family_id);"),
    ("idx_import_items_customer_id", "CREATE INDEX IF NOT EXISTS idx_import_items_customer_id ON import_items(customer_id);"),
    ("idx_import_items_status", "CREATE INDEX IF NOT EXISTS idx_import_items_status ON import_items(status);"),
]

DEFAULT_SETTINGS = [
    ("default_fx", "7.73"),
    ("default_free_ratio", "10"),
    ("default_wishlist_target", "20"),
    ("threshold_wishlist_unbatched_days", "30"),
    ("threshold_paid_unarrived_days", "14"),
    ("threshold_cost_overrun_pct", "30"),
    ("threshold_free_unit_unassigned_days", "7"),
]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def index_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def setting_exists(conn: sqlite3.Connection, key: str) -> bool:
    if not table_exists(conn, "imp_settings"):
        return False
    cur = conn.execute("SELECT 1 FROM imp_settings WHERE key=?", (key,))
    return cur.fetchone() is not None


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.backup-pre-imp-r6-schema-{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_schema(db_path: Path, dry_run: bool) -> dict:
    summary = {
        "tables_created": [],
        "tables_skipped": [],
        "indexes_created": [],
        "indexes_skipped": [],
        "settings_inserted": [],
        "settings_skipped": [],
        "alters_applied": [],
        "alters_skipped": [],
    }

    conn = sqlite3.connect(str(db_path))
    try:
        # Tables
        for name, schema in [
            ("import_wishlist", WISHLIST_SCHEMA),
            ("import_free_unit", FREE_UNIT_SCHEMA),
            ("imp_settings", IMP_SETTINGS_SCHEMA),
            ("import_items", IMPORT_ITEMS_SCHEMA),  # R6 NEW · tabla nueva para promoted items (Diego dec 2026-04-28)
        ]:
            if table_exists(conn, name):
                summary["tables_skipped"].append(name)
            else:
                if not dry_run:
                    conn.executescript(schema)
                summary["tables_created"].append(name)

        # Indexes
        for idx_name, idx_sql in INDEXES:
            if index_exists(conn, idx_name):
                summary["indexes_skipped"].append(idx_name)
            else:
                if not dry_run:
                    conn.execute(idx_sql)
                summary["indexes_created"].append(idx_name)

        # Settings seed (requires imp_settings table to exist · in dry-run we still report what WOULD insert)
        for key, value in DEFAULT_SETTINGS:
            already = setting_exists(conn, key) if not dry_run else False
            # In dry-run if table didn't exist before, treat all as would-insert
            if already:
                summary["settings_skipped"].append(key)
            else:
                if not dry_run:
                    conn.execute(
                        "INSERT OR IGNORE INTO imp_settings (key, value, updated_by) VALUES (?, ?, 'apply_imp_schema')",
                        (key, value),
                    )
                summary["settings_inserted"].append(key)

        # Optional ALTER (notes_extra) · DEFERRED v0.5 (master overview line 70 mentions; spec doesn't require)
        # Skipping to avoid noise. If needed, uncomment:
        # try:
        #     if not dry_run:
        #         conn.execute("ALTER TABLE imports ADD COLUMN notes_extra TEXT")
        #     summary["alters_applied"].append("imports.notes_extra")
        # except sqlite3.OperationalError as e:
        #     if "duplicate column" in str(e).lower():
        #         summary["alters_skipped"].append("imports.notes_extra (already exists)")
        #     else:
        #         raise

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    return summary


def print_summary(summary: dict, dry_run: bool):
    label = "[DRY-RUN · would do]" if dry_run else "[APPLIED]"
    print(f"\n{label} schema apply summary:")
    print(f"  Tables created:    {summary['tables_created'] or '(none)'}")
    print(f"  Tables skipped:    {summary['tables_skipped'] or '(none)'}")
    print(f"  Indexes created:   {summary['indexes_created'] or '(none)'}")
    print(f"  Indexes skipped:   {summary['indexes_skipped'] or '(none)'}")
    print(f"  Settings seeded:   {summary['settings_inserted'] or '(none)'}")
    print(f"  Settings skipped:  {summary['settings_skipped'] or '(none)'}")


MAIN_DB_PATH = r"C:/Users/Diego/el-club/erp/elclub.db"  # ⚠️  PRODUCTION main DB


def confirm_main_db_safety(db_path: Path, default_used: bool):
    """
    Safety prompt cuando --apply va a tocar la main DB de producción.
    Bypassed si DB resuelta es claramente una worktree/temp/test (ej. el-club-imp).
    """
    db_str = str(db_path).replace("\\", "/").lower()
    is_main = ("el-club/erp" in db_str) and ("el-club-imp" not in db_str)
    if not is_main:
        return  # safe path · skip prompt

    if default_used:
        warn = f"⚠️  About to apply schema to MAIN DB ({db_path}). This is the production database. Confirm? (yes/no): "
    else:
        warn = f"⚠️  --db-path resolves to MAIN DB ({db_path}). Confirm? (yes/no): "
    if input(warn).strip().lower() != "yes":
        print("Aborted by user.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without changes")
    group.add_argument("--apply", action="store_true", help="Apply changes (with backup)")
    parser.add_argument("--db-path", default=DEFAULT_DB, help=f"DB path (default: {DEFAULT_DB})")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        sys.exit(2)

    print(f"DB: {db_path}")

    # ── Safety prompt before any --apply against MAIN production DB ────────
    if args.apply:
        default_used = (args.db_path == DEFAULT_DB)
        confirm_main_db_safety(db_path, default_used)

    # Backup MANDATORY when --apply (even if user says yes a la safety prompt)
    if args.apply:
        backup = backup_db(db_path)
        print(f"Backup written: {backup}")

    summary = apply_schema(db_path, dry_run=args.dry_run)
    print_summary(summary, dry_run=args.dry_run)

    print("\nOK." if not args.dry_run else "\nDry-run complete · re-run with --apply to commit.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify script syntactically valid**

Run:
```bash
python -c "import ast; ast.parse(open(r'C:/Users/Diego/el-club-imp/erp/scripts/apply_imp_schema.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/apply_imp_schema.py && \
  git commit -m "feat(imp-r6): apply_imp_schema.py · idempotent schema applicator

- Creates wishlist/free_unit/imp_settings/import_items tables IF NOT EXISTS (4 tablas)
- import_items: nueva tabla para promoted items con customer_id (Diego dec 2026-04-28)
- Creates 8 indexes IF NOT EXISTS (4 originales + 4 import_items)
- Seeds 7 default settings (FX 7.73, free ratio 10, etc.)
- import_free_unit CHECK convención NULL (no string 'unassigned')
- Backup MANDATORY pre-apply when --apply
- Safety prompt si --apply contra main DB (production)
- NO ALTER sale_items (rechazado · Diego eligió tabla nueva import_items)
- Supports --dry-run + --db-path overrides
- Will be run ONCE post-merge on main DB"
```

---

### Task 2: Write `smoke_apply_imp_schema.py` + verify idempotency

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_apply_imp_schema.py`

- [ ] **Step 1: Write smoke**

Create `el-club-imp/erp/scripts/smoke_apply_imp_schema.py`:

```python
#!/usr/bin/env python3
"""
smoke_apply_imp_schema.py — verifies apply_imp_schema.py is idempotent.

Strategy: temp DB with bare imports table → run apply twice → assert second run is all-skip.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "apply_imp_schema.py"


def setup_temp_db() -> Path:
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="smoke_imp_r6_schema_")
    os.close(fd)
    path = Path(tmp)
    conn = sqlite3.connect(str(path))
    # Bare schema · solo las tablas referenced por FOREIGN KEYs en import_items
    conn.executescript("""
        CREATE TABLE imports (import_id TEXT PRIMARY KEY, paid_at TEXT, status TEXT);
        CREATE TABLE sale_items (item_id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id TEXT NOT NULL);
        CREATE TABLE jerseys (jersey_id TEXT PRIMARY KEY);
    """)
    conn.commit()
    conn.close()
    return path


def run_apply(db: Path) -> str:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--apply", "--db-path", str(db)],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def main():
    db = setup_temp_db()
    try:
        # Run 1: should create everything
        out1 = run_apply(db)
        assert "import_wishlist" in out1 and "Tables created" in out1, f"Run 1 didn't create:\n{out1}"
        assert "default_fx" in out1, f"Run 1 didn't seed settings:\n{out1}"

        # Run 2: should skip everything
        out2 = run_apply(db)
        assert "Tables skipped:" in out2, f"Run 2 missing skip line:\n{out2}"
        # Tables created should be empty/(none)
        for line in out2.splitlines():
            if line.startswith("  Tables created:"):
                assert "(none)" in line, f"Run 2 RE-CREATED tables · NOT idempotent: {line}"
            if line.startswith("  Indexes created:"):
                assert "(none)" in line, f"Run 2 RE-CREATED indexes · NOT idempotent: {line}"
            if line.startswith("  Settings seeded:"):
                assert "(none)" in line, f"Run 2 RE-INSERTED settings · NOT idempotent: {line}"

        # Verify final DB state
        conn = sqlite3.connect(str(db))
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            assert "import_wishlist" in tables
            assert "import_free_unit" in tables
            assert "imp_settings" in tables
            assert "import_items" in tables, "import_items table missing (R6 NEW)"

            # import_items expected columns
            cols = {r[1] for r in conn.execute("PRAGMA table_info(import_items)").fetchall()}
            expected_cols = {
                "import_item_id", "import_id", "wishlist_item_id", "family_id", "jersey_id",
                "size", "player_name", "player_number", "patch", "version",
                "customer_id", "expected_usd", "unit_cost_usd", "unit_cost_gtq",
                "status", "sale_item_id", "jersey_id_published", "notes", "created_at",
            }
            missing = expected_cols - cols
            assert not missing, f"import_items missing cols: {missing}"

            # import_items expected indexes
            idxs = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='import_items'"
            ).fetchall()}
            for needed in ("idx_import_items_import_id", "idx_import_items_family_id",
                           "idx_import_items_customer_id", "idx_import_items_status"):
                assert needed in idxs, f"missing index: {needed}"

            settings = {r[0]: r[1] for r in conn.execute("SELECT key, value FROM imp_settings").fetchall()}
            assert settings.get("default_fx") == "7.73"
            assert settings.get("default_free_ratio") == "10"
            assert settings.get("threshold_wishlist_unbatched_days") == "30"
        finally:
            conn.close()

        print("✅ ALL SMOKE TESTS PASS · script is idempotent + seeds defaults correctly · import_items + 4 indexes verified")
    finally:
        # Cleanup temp db + backups
        for p in db.parent.glob(f"{db.name}*"):
            try:
                p.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && python scripts/smoke_apply_imp_schema.py
```
Expected: `✅ ALL SMOKE TESTS PASS`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_apply_imp_schema.py && \
  git commit -m "test(imp-r6): smoke for apply_imp_schema.py · verifies idempotency twice-run"
```

- [ ] **Step 4: Apply to worktree DB so subsequent R6 work has imp_settings ready**

Run:
```bash
cd C:/Users/Diego/el-club-imp/erp && python scripts/apply_imp_schema.py --apply --db-path C:/Users/Diego/el-club-imp/erp/elclub.db
```
Expected: tables_skipped includes wishlist+free_unit (R1 already created) · tables_created includes `imp_settings` · 7 settings seeded.

**No commit** (DB not tracked).

---

## Task Group 2: Rust commands (yo · secuencial · lib.rs)

### Task 3: Helper `get_setting_or_default` + `cmd_get_imp_settings`

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add struct + helper + cmd (smoke-only · no TDD per matrix · CRUD/list)**

Add in IMP section of lib.rs (after R5 commands · before R5 closing or after the supplier section · use grep to locate "// ─── IMPORTACIONES" or similar marker · if absent · insert before final `pub fn run()`):

```rust
// ─── IMP-R6 Settings ────────────────────────────────────────────

#[derive(serde::Serialize, serde::Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ImpSetting {
    pub key: String,
    pub value: String,
    pub updated_at: Option<String>,
    pub updated_by: Option<String>,
}

/// Default values per key · returned if row doesn't exist in imp_settings.
fn imp_setting_default(key: &str) -> Option<&'static str> {
    match key {
        "default_fx" => Some("7.73"),
        "default_free_ratio" => Some("10"),
        "default_wishlist_target" => Some("20"),
        "threshold_wishlist_unbatched_days" => Some("30"),
        "threshold_paid_unarrived_days" => Some("14"),
        "threshold_cost_overrun_pct" => Some("30"),
        "threshold_free_unit_unassigned_days" => Some("7"),
        _ => None,
    }
}

const ALL_IMP_SETTING_KEYS: &[&str] = &[
    "default_fx",
    "default_free_ratio",
    "default_wishlist_target",
    "threshold_wishlist_unbatched_days",
    "threshold_paid_unarrived_days",
    "threshold_cost_overrun_pct",
    "threshold_free_unit_unassigned_days",
];

pub fn impl_get_imp_settings(conn: &rusqlite::Connection) -> rusqlite::Result<Vec<ImpSetting>> {
    let mut out: Vec<ImpSetting> = Vec::with_capacity(ALL_IMP_SETTING_KEYS.len());
    let mut stmt = conn.prepare(
        "SELECT key, value, updated_at, updated_by FROM imp_settings WHERE key = ?1"
    )?;
    for &key in ALL_IMP_SETTING_KEYS {
        let row: Option<ImpSetting> = stmt
            .query_row([key], |r| {
                Ok(ImpSetting {
                    key: r.get(0)?,
                    value: r.get(1)?,
                    updated_at: r.get(2)?,
                    updated_by: r.get(3)?,
                })
            })
            .ok();
        match row {
            Some(s) => out.push(s),
            None => out.push(ImpSetting {
                key: key.to_string(),
                value: imp_setting_default(key).unwrap_or("").to_string(),
                updated_at: None,
                updated_by: None,
            }),
        }
    }
    Ok(out)
}

#[tauri::command]
fn cmd_get_imp_settings() -> Result<Vec<ImpSetting>, String> {
    let conn = rusqlite::Connection::open(db_path()).map_err(|e| e.to_string())?;
    impl_get_imp_settings(&conn).map_err(|e| e.to_string())
}
```

- [ ] **Step 2: Wire into `generate_handler!`**

Locate `tauri::generate_handler![` and add `cmd_get_imp_settings,` to the list.

- [ ] **Step 3: cargo check**

Run:
```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -10
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r6): cmd_get_imp_settings · returns 7 settings with defaults fallback

- Reads imp_settings table per key
- Falls back to hardcoded defaults if row missing
- Always returns 7 entries (one per known key)
- impl_X + cmd_X split per convention block lib.rs:2730-2742"
```

---

### Task 4: `cmd_update_imp_setting` (TDD-light · validates value type per key)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`
- Create: `el-club-imp/overhaul/src-tauri/tests/imp_r6_settings_test.rs`

- [ ] **Step 1: Write failing test**

Create `el-club-imp/overhaul/src-tauri/tests/imp_r6_settings_test.rs`:

```rust
// Integration test for cmd_update_imp_setting · validates per-key value types.
use std::env;
use std::path::PathBuf;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_LOCK: Mutex<()> = Mutex::new(());

fn setup_temp_db() -> PathBuf {
    let path = env::temp_dir().join(format!("imp_r6_settings_test_{}.db", std::process::id()));
    if path.exists() { std::fs::remove_file(&path).unwrap(); }
    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(r#"
        CREATE TABLE imp_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT,
          updated_by TEXT
        );
    "#).unwrap();
    path
}

fn with_db<F: FnOnce()>(f: F) {
    let _g = DB_LOCK.lock().unwrap();
    let path = setup_temp_db();
    env::set_var("ERP_DB_PATH", &path);
    f();
    let _ = std::fs::remove_file(&path);
}

#[test]
fn test_update_default_fx_happy() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "7.85",
        );
        assert!(result.is_ok(), "Expected OK, got {:?}", result);
        let s = result.unwrap();
        assert_eq!(s.value, "7.85");
    });
}

#[test]
fn test_update_default_fx_rejects_negative() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "-1.0",
        );
        assert!(result.is_err(), "Expected ERR for negative FX");
    });
}

#[test]
fn test_update_default_fx_rejects_non_numeric() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "default_fx",
            "abc",
        );
        assert!(result.is_err());
    });
}

#[test]
fn test_update_threshold_days_rejects_zero() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "threshold_wishlist_unbatched_days",
            "0",
        );
        assert!(result.is_err(), "Expected ERR for zero threshold");
    });
}

#[test]
fn test_update_unknown_key_rejected() {
    with_db(|| {
        let result = el_club_erp_lib::impl_update_imp_setting_at(
            &Connection::open(env::var("ERP_DB_PATH").unwrap()).unwrap(),
            "made_up_key",
            "1",
        );
        assert!(result.is_err(), "Expected ERR for unknown key");
    });
}
```

- [ ] **Step 2: Run test to verify it fails (function not implemented)**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r6_settings_test 2>&1 | tail -15
```
Expected: compile error (`cannot find function impl_update_imp_setting_at`)

- [ ] **Step 3: Implement `impl_update_imp_setting_at` + `cmd_update_imp_setting`**

Add in lib.rs after `impl_get_imp_settings`:

```rust
/// Validates a setting value against its key's expected type.
fn validate_setting_value(key: &str, value: &str) -> Result<(), String> {
    match key {
        "default_fx" => {
            let v: f64 = value.parse().map_err(|_| format!("'{}' debe ser numérico", key))?;
            if v <= 0.0 || v > 50.0 {
                return Err(format!("'{}' fuera de rango (0,50]", key));
            }
        }
        "default_free_ratio" | "default_wishlist_target" => {
            let v: i64 = value.parse().map_err(|_| format!("'{}' debe ser entero", key))?;
            if v <= 0 {
                return Err(format!("'{}' debe ser > 0", key));
            }
        }
        "threshold_wishlist_unbatched_days"
        | "threshold_paid_unarrived_days"
        | "threshold_free_unit_unassigned_days" => {
            let v: i64 = value.parse().map_err(|_| format!("'{}' debe ser entero", key))?;
            if v <= 0 || v > 365 {
                return Err(format!("'{}' fuera de rango (0,365]", key));
            }
        }
        "threshold_cost_overrun_pct" => {
            let v: f64 = value.parse().map_err(|_| format!("'{}' debe ser numérico", key))?;
            if v <= 0.0 || v > 500.0 {
                return Err(format!("'{}' fuera de rango (0,500]", key));
            }
        }
        _ => return Err(format!("Key desconocida: '{}'", key)),
    }
    Ok(())
}

pub fn impl_update_imp_setting_at(
    conn: &rusqlite::Connection,
    key: &str,
    value: &str,
) -> Result<ImpSetting, String> {
    validate_setting_value(key, value)?;
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    conn.execute(
        "INSERT INTO imp_settings (key, value, updated_at, updated_by)
         VALUES (?1, ?2, ?3, 'diego')
         ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        rusqlite::params![key, value, now],
    ).map_err(|e| e.to_string())?;
    Ok(ImpSetting {
        key: key.to_string(),
        value: value.to_string(),
        updated_at: Some(now),
        updated_by: Some("diego".to_string()),
    })
}

#[tauri::command]
fn cmd_update_imp_setting(key: String, value: String) -> Result<ImpSetting, String> {
    let conn = rusqlite::Connection::open(db_path()).map_err(|e| e.to_string())?;
    impl_update_imp_setting_at(&conn, &key, &value)
}
```

Wire `cmd_update_imp_setting` into `generate_handler!`.

- [ ] **Step 4: Run tests to verify pass**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo test --test imp_r6_settings_test 2>&1 | tail -10
```
Expected: `5 passed; 0 failed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs overhaul/src-tauri/tests/imp_r6_settings_test.rs && \
  git commit -m "feat(imp-r6): cmd_update_imp_setting · upsert with per-key value validation

- TDD-light: 5 tests (happy + 4 invalid value rejections)
- validate_setting_value() guards type + range per key
- ON CONFLICT(key) DO UPDATE upsert pattern
- impl_X + cmd_X split per convention"
```

---

### Task 5: `cmd_get_migration_log` (smoke-only)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add struct + impl + cmd**

```rust
#[derive(serde::Serialize, serde::Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MigrationLog {
    pub last_migration_run_at: Option<String>,
    pub imports_count: i64,
    pub sale_items_linked: i64,
    pub jerseys_linked: i64,
    pub wishlist_count: i64,
    pub free_units_count: i64,
}

pub fn impl_get_migration_log(conn: &rusqlite::Connection) -> rusqlite::Result<MigrationLog> {
    let last: Option<String> = conn
        .query_row(
            "SELECT MAX(created_at) FROM imports",
            [],
            |r| r.get::<_, Option<String>>(0),
        )
        .unwrap_or(None);

    let imports_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM imports", [], |r| r.get(0))
        .unwrap_or(0);
    let sale_items_linked: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM sale_items WHERE import_id IS NOT NULL",
            [],
            |r| r.get(0),
        )
        .unwrap_or(0);
    let jerseys_linked: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM jerseys WHERE import_id IS NOT NULL",
            [],
            |r| r.get(0),
        )
        .unwrap_or(0);
    let wishlist_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM import_wishlist", [], |r| r.get(0))
        .unwrap_or(0);
    let free_units_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM import_free_unit", [], |r| r.get(0))
        .unwrap_or(0);

    Ok(MigrationLog {
        last_migration_run_at: last,
        imports_count,
        sale_items_linked,
        jerseys_linked,
        wishlist_count,
        free_units_count,
    })
}

#[tauri::command]
fn cmd_get_migration_log() -> Result<MigrationLog, String> {
    let conn = rusqlite::Connection::open(db_path()).map_err(|e| e.to_string())?;
    impl_get_migration_log(&conn).map_err(|e| e.to_string())
}
```

Wire `cmd_get_migration_log` into `generate_handler!`.

- [ ] **Step 2: cargo check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5
```
Expected: ok

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r6): cmd_get_migration_log · counts + last_run_at proxy

- last_migration_run_at = MAX(imports.created_at) (proxy · no schema_migrations table)
- 5 counts: imports, sale_items linked, jerseys linked, wishlist, free_units
- Uses .unwrap_or(0) for graceful degradation on missing tables (browser preview safety)"
```

---

### Task 6: `cmd_get_integrations_status` (smoke-only · hardcoded structure)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add struct + cmd**

```rust
#[derive(serde::Serialize, serde::Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct IntegrationStatus {
    pub name: String,
    pub status: String,    // 'active' | 'disabled'
    pub last_read_at: Option<String>,
    pub note: Option<String>,
}

#[derive(serde::Serialize, serde::Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct IntegrationsStatus {
    pub integrations: Vec<IntegrationStatus>,
}

#[tauri::command]
fn cmd_get_integrations_status() -> Result<IntegrationsStatus, String> {
    // Last DB modification timestamp as proxy for "last read"
    let last_read = std::fs::metadata(db_path())
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| {
            let dt = chrono::DateTime::<chrono::Local>::from(
                std::time::UNIX_EPOCH + d
            );
            dt.format("%Y-%m-%d %H:%M:%S").to_string()
        });

    Ok(IntegrationsStatus {
        integrations: vec![
            IntegrationStatus {
                name: "elclub.db (SQLite local)".to_string(),
                status: "active".to_string(),
                last_read_at: last_read,
                note: Some("Source-of-truth compartido con Streamlit (read-only allá)".to_string()),
            },
            IntegrationStatus {
                name: "PayPal screenshot OCR".to_string(),
                status: "disabled".to_string(),
                last_read_at: None,
                note: Some("v0.5 future · captura bruto_usd automática".to_string()),
            },
            IntegrationStatus {
                name: "DHL tracking API".to_string(),
                status: "disabled".to_string(),
                last_read_at: None,
                note: Some("v0.5 future · webhook DHL para arrived_at + shipping_gtq".to_string()),
            },
        ],
    })
}
```

Wire `cmd_get_integrations_status` into `generate_handler!`.

- [ ] **Step 2: cargo check + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && \
  cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r6): cmd_get_integrations_status · hardcoded 3 rows

- elclub.db active (last_read_at = file mtime)
- PayPal OCR disabled (v0.5 future)
- DHL API disabled (v0.5 future)
- UI consumes for read-only Integrations panel"
```

---

### Task 7: `cmd_resync_migration` STUB (escalated · disabled-by-design)

**Files:**
- Modify: `el-club-imp/overhaul/src-tauri/src/lib.rs`

- [ ] **Step 1: Add stub returning explicit error**

```rust
#[tauri::command]
fn cmd_resync_migration() -> Result<String, String> {
    // INTENTIONAL STUB · v0.4.0 doesn't re-run Streamlit migration (would risk overwriting
    // Tauri-authoritative state). Re-enable in v0.5 with proper merge logic.
    Err("Re-sync deshabilitado en v0.4.0 · Streamlit migration ya corrió en R1. Para v0.5 con merge logic.".to_string())
}
```

Wire `cmd_resync_migration` into `generate_handler!`.

- [ ] **Step 2: cargo check + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && cargo check 2>&1 | tail -5 && \
  cd C:/Users/Diego/el-club-imp && git add overhaul/src-tauri/src/lib.rs && \
  git commit -m "feat(imp-r6): cmd_resync_migration STUB-disabled · v0.5 deferred

- Returns explicit error · UI button shown disabled with tooltip
- Re-enabling requires merge logic (Tauri vs Streamlit state diff)
- Escalated decision: doc'd in plan Open Questions"
```

---

## Task Group 3: Adapter wires (TS · 3 files)

### Task 8: Extend `types.ts`

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/types.ts`

- [ ] **Step 1: Add types + interface methods**

Add at appropriate section (search for existing IMP types · group together):

```typescript
// ─── IMP-R6 Settings ────────────────────────────────────────────────────

export interface ImpSetting {
  key: string;
  value: string;
  updatedAt: string | null;
  updatedBy: string | null;
}

export interface MigrationLog {
  lastMigrationRunAt: string | null;
  importsCount: number;
  saleItemsLinked: number;
  jerseysLinked: number;
  wishlistCount: number;
  freeUnitsCount: number;
}

export interface IntegrationStatus {
  name: string;
  status: 'active' | 'disabled';
  lastReadAt: string | null;
  note: string | null;
}

export interface IntegrationsStatus {
  integrations: IntegrationStatus[];
}
```

Extend the `Adapter` interface (or equivalent) with:

```typescript
  // IMP-R6 Settings
  getImpSettings(): Promise<ImpSetting[]>;
  updateImpSetting(key: string, value: string): Promise<ImpSetting>;
  getMigrationLog(): Promise<MigrationLog>;
  getIntegrationsStatus(): Promise<IntegrationsStatus>;
  resyncMigration(): Promise<string>;  // throws on call (stub) · UI displays error
```

- [ ] **Step 2: npm check**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5
```
Expected: errors solo en tauri.ts/browser.ts (sin implementar) · OK temporalmente

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/adapter/types.ts && \
  git commit -m "feat(imp-r6): adapter types · ImpSetting + MigrationLog + IntegrationsStatus + 5 methods"
```

---

### Task 9: Implement `tauri.ts` invocations

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/tauri.ts`

- [ ] **Step 1: Add 5 invocations**

```typescript
  async getImpSettings(): Promise<ImpSetting[]> {
    return invoke<ImpSetting[]>('cmd_get_imp_settings');
  },

  async updateImpSetting(key: string, value: string): Promise<ImpSetting> {
    return invoke<ImpSetting>('cmd_update_imp_setting', { key, value });
  },

  async getMigrationLog(): Promise<MigrationLog> {
    return invoke<MigrationLog>('cmd_get_migration_log');
  },

  async getIntegrationsStatus(): Promise<IntegrationsStatus> {
    return invoke<IntegrationsStatus>('cmd_get_integrations_status');
  },

  async resyncMigration(): Promise<string> {
    return invoke<string>('cmd_resync_migration');  // throws "Re-sync deshabilitado..."
  },
```

- [ ] **Step 2: npm check + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && \
  cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/adapter/tauri.ts && \
  git commit -m "feat(imp-r6): tauri adapter · 5 invocations for settings/migration-log/integrations"
```

---

### Task 10: Implement `browser.ts` stubs

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/adapter/browser.ts`

- [ ] **Step 1: Add 5 stubs**

For 4 of them (writes + integrations/migration log) throw `NotAvailableInBrowser`. For `getImpSettings()` return hardcoded defaults so dev preview can render the form:

```typescript
  async getImpSettings(): Promise<ImpSetting[]> {
    // Browser dev preview: return defaults so SettingsTab renders
    return [
      { key: 'default_fx', value: '7.73', updatedAt: null, updatedBy: null },
      { key: 'default_free_ratio', value: '10', updatedAt: null, updatedBy: null },
      { key: 'default_wishlist_target', value: '20', updatedAt: null, updatedBy: null },
      { key: 'threshold_wishlist_unbatched_days', value: '30', updatedAt: null, updatedBy: null },
      { key: 'threshold_paid_unarrived_days', value: '14', updatedAt: null, updatedBy: null },
      { key: 'threshold_cost_overrun_pct', value: '30', updatedAt: null, updatedBy: null },
      { key: 'threshold_free_unit_unassigned_days', value: '7', updatedAt: null, updatedBy: null },
    ];
  },

  async updateImpSetting(): Promise<ImpSetting> {
    throw new Error('NotAvailableInBrowser: requiere el .exe (no dev server)');
  },

  async getMigrationLog(): Promise<MigrationLog> {
    throw new Error('NotAvailableInBrowser: requiere el .exe (no dev server)');
  },

  async getIntegrationsStatus(): Promise<IntegrationsStatus> {
    throw new Error('NotAvailableInBrowser: requiere el .exe (no dev server)');
  },

  async resyncMigration(): Promise<string> {
    throw new Error('NotAvailableInBrowser: requiere el .exe (no dev server)');
  },
```

- [ ] **Step 2: npm check + commit**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && \
  cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/adapter/browser.ts && \
  git commit -m "feat(imp-r6): browser stubs · 4 throw NotAvailableInBrowser · getImpSettings returns defaults for dev preview"
```

---

## Task Group 4: Settings tab Svelte components

### Task 11: `SettingsSection.svelte` (collapsible wrapper)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/SettingsSection.svelte`

- [ ] **Step 1: Write component**

```svelte
<script lang="ts">
  let { title, defaultOpen = true, children } = $props<{
    title: string;
    defaultOpen?: boolean;
    children: any;
  }>();

  let open = $state(defaultOpen);
</script>

<section class="settings-section">
  <button class="settings-section__head" onclick={() => (open = !open)} aria-expanded={open}>
    <span class="caret" class:open>▸</span>
    <span class="title">{title}</span>
  </button>
  {#if open}
    <div class="settings-section__body">
      {@render children()}
    </div>
  {/if}
</section>

<style>
  .settings-section {
    border: 1px solid var(--border, #22222a);
    border-radius: 4px;
    margin-bottom: 12px;
    background: var(--surface-1, #0f0f12);
  }
  .settings-section__head {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: transparent;
    border: 0;
    cursor: pointer;
    text-align: left;
    color: inherit;
  }
  .settings-section__head:hover {
    background: var(--surface-2, #16161b);
  }
  .caret {
    display: inline-block;
    transition: transform 0.15s;
    color: var(--accent, #5b8def);
  }
  .caret.open { transform: rotate(90deg); }
  .title {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 12px;
    font-weight: 600;
  }
  .settings-section__body {
    padding: 8px 16px 16px;
    border-top: 1px solid var(--border, #22222a);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/SettingsSection.svelte && \
  git commit -m "feat(imp-r6): SettingsSection.svelte · collapsible wrapper for settings tab"
```

---

### Task 12: `SettingsField.svelte` (single editable field with save)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/SettingsField.svelte`

- [ ] **Step 1: Write component**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ImpSetting } from '$lib/adapter/types';

  let { setting, label, hint = '', inputType = 'number', step = '0.01', onSaved } = $props<{
    setting: ImpSetting;
    label: string;
    hint?: string;
    inputType?: 'number' | 'text';
    step?: string;
    onSaved?: (s: ImpSetting) => void;
  }>();

  let draft = $state(setting.value);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let savedOk = $state(false);

  let dirty = $derived(draft !== setting.value);

  async function save() {
    if (!dirty || saving) return;
    saving = true;
    error = null;
    savedOk = false;
    try {
      const updated = await adapter.updateImpSetting(setting.key, draft);
      onSaved?.(updated);
      savedOk = true;
      setTimeout(() => (savedOk = false), 2000);
    } catch (e: any) {
      error = e?.message ?? String(e);
    } finally {
      saving = false;
    }
  }
</script>

<div class="settings-field">
  <label for={`fld-${setting.key}`}>
    <span class="lbl">{label}</span>
    {#if hint}<span class="hint">{hint}</span>{/if}
  </label>
  <div class="row">
    <input
      id={`fld-${setting.key}`}
      type={inputType}
      step={inputType === 'number' ? step : undefined}
      bind:value={draft}
      disabled={saving}
    />
    <button onclick={save} disabled={!dirty || saving} class="save-btn">
      {saving ? '...' : 'Guardar'}
    </button>
    {#if savedOk}<span class="ok">✓</span>{/if}
  </div>
  {#if error}
    <div class="err">⚠️ {error}</div>
  {/if}
  {#if setting.updatedAt}
    <div class="meta">Última actualización: {setting.updatedAt}{setting.updatedBy ? ` · ${setting.updatedBy}` : ''}</div>
  {/if}
</div>

<style>
  .settings-field { margin-bottom: 14px; }
  label { display: flex; flex-direction: column; gap: 2px; margin-bottom: 4px; }
  .lbl { text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; color: var(--text-2, #aaa); }
  .hint { font-size: 11px; color: var(--text-3, #777); }
  .row { display: flex; gap: 8px; align-items: center; }
  input {
    background: var(--surface-2, #16161b);
    border: 1px solid var(--border, #22222a);
    color: inherit;
    padding: 6px 10px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    width: 140px;
    font-variant-numeric: tabular-nums;
  }
  input:focus { outline: 1px solid var(--accent, #5b8def); border-color: var(--accent, #5b8def); }
  .save-btn {
    background: var(--accent, #5b8def);
    color: #fff;
    border: 0;
    padding: 6px 12px;
    border-radius: 3px;
    cursor: pointer;
    font-size: 12px;
  }
  .save-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .ok { color: var(--terminal, #4ade80); }
  .err { margin-top: 4px; color: var(--alert, #f43f5e); font-size: 12px; }
  .meta { margin-top: 4px; font-size: 11px; color: var(--text-3, #777); font-family: 'JetBrains Mono', monospace; }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/SettingsField.svelte && \
  git commit -m "feat(imp-r6): SettingsField.svelte · single editable field + per-row save + error/ok states"
```

---

### Task 13: `MigrationLogPanel.svelte` (read-only)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/MigrationLogPanel.svelte`

- [ ] **Step 1: Write component**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { MigrationLog } from '$lib/adapter/types';

  let log = $state<MigrationLog | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    (async () => {
      try {
        log = await adapter.getMigrationLog();
      } catch (e: any) {
        error = e?.message ?? String(e);
      } finally {
        loading = false;
      }
    })();
  });
</script>

{#if loading}
  <div class="skeleton">Cargando migration log…</div>
{:else if error}
  <div class="err">⚠️ {error}</div>
{:else if log}
  <table class="log-table">
    <tbody>
      <tr><td>Última migración (proxy)</td><td class="num">{log.lastMigrationRunAt ?? '—'}</td></tr>
      <tr><td>Imports</td><td class="num">{log.importsCount}</td></tr>
      <tr><td>Sale items linked</td><td class="num">{log.saleItemsLinked}</td></tr>
      <tr><td>Jerseys linked</td><td class="num">{log.jerseysLinked}</td></tr>
      <tr><td>Wishlist rows</td><td class="num">{log.wishlistCount}</td></tr>
      <tr><td>Free units rows</td><td class="num">{log.freeUnitsCount}</td></tr>
    </tbody>
  </table>
  <button class="resync-btn" disabled title="Deshabilitado en v0.4.0 · v0.5 future con merge logic">
    Re-sync ahora (disabled)
  </button>
  {#if log.importsCount === 0}
    <p class="empty">Sin migraciones todavía. R1 ya migró schema initial · counts crecen al usar el módulo.</p>
  {/if}
{/if}

<style>
  .skeleton { padding: 12px; color: var(--text-3, #777); font-style: italic; }
  .err { color: var(--alert, #f43f5e); padding: 8px; }
  .log-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .log-table td { padding: 6px 8px; border-bottom: 1px solid var(--border, #22222a); }
  .log-table td:first-child { color: var(--text-2, #aaa); text-transform: uppercase; letter-spacing: 0.05em; font-size: 11px; }
  .num { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; text-align: right; }
  .resync-btn {
    margin-top: 12px; padding: 6px 12px; background: var(--surface-2, #16161b);
    border: 1px solid var(--border, #22222a); color: var(--text-3, #777);
    border-radius: 3px; cursor: not-allowed;
  }
  .empty { margin-top: 8px; font-size: 11px; color: var(--text-3, #777); font-style: italic; }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/MigrationLogPanel.svelte && \
  git commit -m "feat(imp-r6): MigrationLogPanel.svelte · read-only counts + disabled re-sync btn"
```

---

### Task 14: `IntegrationsStatusPanel.svelte` (read-only)

**Files:**
- Create: `el-club-imp/overhaul/src/lib/components/importaciones/IntegrationsStatusPanel.svelte`

- [ ] **Step 1: Write component**

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { IntegrationsStatus } from '$lib/adapter/types';

  let status = $state<IntegrationsStatus | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    (async () => {
      try {
        status = await adapter.getIntegrationsStatus();
      } catch (e: any) {
        error = e?.message ?? String(e);
      } finally {
        loading = false;
      }
    })();
  });
</script>

{#if loading}
  <div class="skeleton">Cargando integraciones…</div>
{:else if error}
  <div class="err">⚠️ {error}</div>
{:else if status}
  <div class="rows">
    {#each status.integrations as int}
      <div class="int-row">
        <span class="pill" class:active={int.status === 'active'}>● {int.status.toUpperCase()}</span>
        <div class="body">
          <div class="name">{int.name}</div>
          {#if int.lastReadAt}<div class="meta">Last read: {int.lastReadAt}</div>{/if}
          {#if int.note}<div class="note">{int.note}</div>{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .skeleton { padding: 12px; color: var(--text-3, #777); font-style: italic; }
  .err { color: var(--alert, #f43f5e); padding: 8px; }
  .rows { display: flex; flex-direction: column; gap: 10px; }
  .int-row {
    display: flex; gap: 12px; align-items: flex-start;
    padding: 10px; background: var(--surface-2, #16161b);
    border-radius: 3px; border: 1px solid var(--border, #22222a);
  }
  .pill {
    font-size: 10px; padding: 2px 8px; border-radius: 10px;
    background: var(--surface-3, #1e1e24); color: var(--text-3, #777);
    text-transform: uppercase; letter-spacing: 0.06em; flex-shrink: 0;
  }
  .pill.active { color: var(--terminal, #4ade80); }
  .name { font-weight: 600; font-size: 13px; }
  .meta, .note { font-size: 11px; color: var(--text-3, #777); margin-top: 2px; }
  .meta { font-family: 'JetBrains Mono', monospace; }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/IntegrationsStatusPanel.svelte && \
  git commit -m "feat(imp-r6): IntegrationsStatusPanel.svelte · 3 rows with active/disabled pills"
```

---

### Task 15: REPLACE `ImportSettingsTab.svelte` (orchestrator)

**Files:**
- Modify (REPLACE): `el-club-imp/overhaul/src/lib/components/importaciones/tabs/ImportSettingsTab.svelte`

- [ ] **Step 1: Write the tab**

Overwrite the 6-line stub with:

```svelte
<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ImpSetting } from '$lib/adapter/types';
  import SettingsSection from '../SettingsSection.svelte';
  import SettingsField from '../SettingsField.svelte';
  import MigrationLogPanel from '../MigrationLogPanel.svelte';
  import IntegrationsStatusPanel from '../IntegrationsStatusPanel.svelte';

  let settings = $state<ImpSetting[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      settings = await adapter.getImpSettings();
    } catch (e: any) {
      error = e?.message ?? String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  function settingByKey(key: string): ImpSetting | undefined {
    return settings.find((s) => s.key === key);
  }

  function onSaved(updated: ImpSetting) {
    settings = settings.map((s) => (s.key === updated.key ? updated : s));
  }
</script>

<div class="settings-tab">
  <header class="tab-head">
    <h2>Settings</h2>
    <p class="sub">Defaults, umbrales para inbox events, y status de integraciones.</p>
  </header>

  {#if loading}
    <div class="skeleton-block">
      <div class="line w-30"></div>
      <div class="line w-50"></div>
      <div class="line w-40"></div>
    </div>
  {:else if error}
    <div class="err-banner">⚠️ Error cargando settings: {error}</div>
  {:else}
    <SettingsSection title="Defaults">
      {@const fx = settingByKey('default_fx')}
      {@const ratio = settingByKey('default_free_ratio')}
      {@const target = settingByKey('default_wishlist_target')}
      {#if fx}<SettingsField setting={fx} label="FX default" hint="Tipo de cambio default (Q por USD)" {onSaved} />{/if}
      {#if ratio}<SettingsField setting={ratio} label="Free unit ratio" hint="1 free cada N paid units (R4 hardcoded en v0.4.0 · cablea en v0.5)" {onSaved} />{/if}
      {#if target}<SettingsField setting={target} label="Wishlist target" hint="Tamaño target para sugerir promote-to-batch" {onSaved} />{/if}
      <div class="ro-row">
        <span class="lbl">Lead time supplier (auto)</span>
        <span class="val">— calculado del scorecard</span>
      </div>
    </SettingsSection>

    <SettingsSection title="Umbrales (Inbox events)" defaultOpen={false}>
      {@const t1 = settingByKey('threshold_wishlist_unbatched_days')}
      {@const t2 = settingByKey('threshold_paid_unarrived_days')}
      {@const t3 = settingByKey('threshold_cost_overrun_pct')}
      {@const t4 = settingByKey('threshold_free_unit_unassigned_days')}
      {#if t1}<SettingsField setting={t1} label="Wishlist sin batch" hint="Días sin promote → inbox alert" {onSaved} />{/if}
      {#if t2}<SettingsField setting={t2} label="Batch paid sin arrived" hint="Días en pipeline → inbox alert" {onSaved} />{/if}
      {#if t3}<SettingsField setting={t3} label="Cost overrun %" hint="% sobre avg → inbox alert" {onSaved} />{/if}
      {#if t4}<SettingsField setting={t4} label="Free unit sin asignar" hint="Días unassigned → inbox alert" {onSaved} />{/if}
      <p class="muted-note">Nota: los thresholds se almacenan acá pero el módulo Comercial es responsable de consumir los valores y emitir los inbox events. Follow-up post v0.4.0.</p>
    </SettingsSection>

    <SettingsSection title="Migration log" defaultOpen={false}>
      <MigrationLogPanel />
    </SettingsSection>

    <SettingsSection title="Integrations" defaultOpen={false}>
      <IntegrationsStatusPanel />
    </SettingsSection>
  {/if}
</div>

<style>
  .settings-tab { padding: 16px; max-width: 760px; }
  .tab-head { margin-bottom: 16px; }
  .tab-head h2 { margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; }
  .sub { font-size: 12px; color: var(--text-3, #777); margin: 4px 0 0; }
  .skeleton-block { padding: 12px; background: var(--surface-1, #0f0f12); border-radius: 4px; border: 1px solid var(--border, #22222a); }
  .skeleton-block .line {
    height: 10px; background: linear-gradient(90deg, var(--surface-2, #16161b), var(--surface-3, #1e1e24), var(--surface-2, #16161b));
    background-size: 200% 100%; border-radius: 2px; margin-bottom: 8px;
    animation: shimmer 1.4s infinite;
  }
  .w-30 { width: 30%; } .w-40 { width: 40%; } .w-50 { width: 50%; }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .err-banner { padding: 10px 14px; background: rgba(244,63,94,0.1); border: 1px solid var(--alert, #f43f5e); border-radius: 3px; color: var(--alert, #f43f5e); }
  .ro-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 12px; }
  .ro-row .lbl { text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2, #aaa); font-size: 11px; }
  .ro-row .val { color: var(--text-3, #777); font-style: italic; }
  .muted-note { margin-top: 8px; font-size: 11px; color: var(--text-3, #777); font-style: italic; padding: 6px; background: var(--surface-2, #16161b); border-radius: 2px; }
</style>
```

- [ ] **Step 2: npm check + build sanity**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/ImportSettingsTab.svelte && \
  git commit -m "feat(imp-r6): ImportSettingsTab.svelte · 4 collapsible sections (defaults/umbrales/log/integrations)

- Replaces 6-line stub
- Uses SettingsSection wrapper + SettingsField per editable
- MigrationLogPanel + IntegrationsStatusPanel for read-only sections
- Skeleton loading + error banner
- Per-row save (no auto-save · explicit user action)
- Note documenting Comercial follow-up for inbox events consumption"
```

---

## Task Group 5: Polish pass · empty states · loading skeletons · browser fallback

Each task ~10-15 min. Run AFTER R2-R5 components exist (verify in Task 0 step 4 that branches are merged into `imp-r2-r6-build`).

### Task 16: PedidosTab audit (canonical reference)

**Files:**
- Modify (potentially): `el-club-imp/overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte`

- [ ] **Step 1: Read current file** + verify it has:
  - `loading = $state(true)` with skeleton block (NOT empty `{#if loading}…{/if}`)
  - Empty state when `imports.length === 0` per spec line 619: "No hay imports todavía. [+ Nuevo pedido] o [Migrar desde Streamlit]"
  - Error banner (try/catch around adapter call · `⚠️` prefix)

- [ ] **Step 2: Fix only deltas detected** (no full rewrite). If PedidosTab already passes, skip to commit.

- [ ] **Step 3: Commit (only if changes)**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/PedidosTab.svelte && \
  git commit -m "polish(imp-r6): PedidosTab audit · ensure empty/loading/error states canonical"
```

---

### Task 17: WishlistTab polish (R2)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte`

- [ ] **Step 1: Add empty state**

When `wishlist.length === 0` after loading:

```svelte
{#if !loading && wishlist.length === 0 && !error}
  <div class="empty-state">
    <div class="icon">📋</div>
    <h3>Sin pre-pedidos</h3>
    <p>Cuando un cliente pida algo, agregá item acá.<br>
    <small>Recordatorio: D7=B · SKU debe existir en catalog.</small></p>
    <button onclick={() => (newItemModalOpen = true)} class="cta-btn">+ Agregar item</button>
  </div>
{/if}
```

- [ ] **Step 2: Add loading skeleton** (same shimmer pattern as ImportSettingsTab):

```svelte
{#if loading}
  <div class="skeleton-list">
    {#each Array(3) as _}
      <div class="skeleton-row"></div>
    {/each}
  </div>
{/if}
```

- [ ] **Step 3: Add error banner**

```svelte
{#if error}
  <div class="err-banner">⚠️ Error: {error} <button onclick={load}>Reintentar</button></div>
{/if}
```

- [ ] **Step 4: Verify browser fallback** — open in dev server (`npm run dev`), navigate to Wishlist tab, confirm `NotAvailableInBrowser` shown clearly via error banner.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/WishlistTab.svelte && \
  git commit -m "polish(imp-r6): WishlistTab empty state + loading skeleton + error banner

- Empty state per spec sec 8 line 621 · CTA '+ Agregar item'
- Shimmer skeleton (3 rows) during loading
- Error banner with retry button
- Browser fallback verified · NotAvailableInBrowser surfaces via banner"
```

---

### Task 18: MargenRealTab polish (R3)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte`

- [ ] **Step 1: Add empty state**

When no closed batches yet:

```svelte
{#if !loading && batches.length === 0 && !error}
  <div class="empty-state">
    <div class="icon">📊</div>
    <h3>Sin batches closed</h3>
    <p>El margen real se calcula al cerrar un batch.<br>
    <small>Cerrá un batch desde Pedidos para ver métricas.</small></p>
  </div>
{/if}
```

- [ ] **Step 2: Add loading skeleton (card shimmer · 2 cards)**

- [ ] **Step 3: Add error banner**

- [ ] **Step 4: Verify browser fallback**

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/MargenRealTab.svelte && \
  git commit -m "polish(imp-r6): MargenRealTab empty/loading/error · canonical states"
```

---

### Task 19: FreeUnitsTab polish (R4)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte`

- [ ] **Step 1: Add empty state**

```svelte
{#if !loading && freeUnits.length === 0 && !error}
  <div class="empty-state">
    <div class="icon">🎁</div>
    <h3>Sin free units</h3>
    <p>Las free units se generan automáticamente al close batch (1 cada 10 paid).<br>
    <small>Cerrá un batch para ver free units acá.</small></p>
  </div>
{/if}
```

- [ ] **Step 2: Add loading skeleton + error banner + browser fallback verify**

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/FreeUnitsTab.svelte && \
  git commit -m "polish(imp-r6): FreeUnitsTab empty/loading/error · canonical states"
```

---

### Task 20: SupplierTab polish (R5)

**Files:**
- Modify: `el-club-imp/overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte`

- [ ] **Step 1: Add empty state**

```svelte
{#if !loading && !card && !error}
  <div class="empty-state">
    <div class="icon">🏢</div>
    <h3>Sin métricas de supplier</h3>
    <p>El scorecard requiere al menos 1 batch closed.<br>
    <small>Cerrá un batch desde Pedidos para activar métricas.</small></p>
  </div>
{/if}
```

- [ ] **Step 2: Add loading skeleton (card shimmer) + error banner + browser fallback verify**

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/tabs/SupplierTab.svelte && \
  git commit -m "polish(imp-r6): SupplierTab empty/loading/error · canonical states"
```

---

### Task 21: Modals audit (consistency check across R1.5 + R2 + R4 modals)

**Files:**
- Modify (potentially): NewImportModal · RegisterArrivalModal · EditImportModal · ConfirmCancelModal · WishlistAddItem (R2) · WishlistEditItem (R2) · PromoteToBatchModal (R2) · AssignDestinationModal (R4)

- [ ] **Step 1: Audit checklist per modal**:
  - ESC key closes (`onkeydown` handler with `key === 'Escape'`)
  - Click-outside closes (overlay onclick)
  - Submit button shows `disabled={submitting}` during async
  - Submit button shows loading text (e.g., `{submitting ? 'Guardando...' : 'Guardar'}`)
  - Error banner with `⚠️` prefix on failure (NOT alert())
  - Self-clean on close (`$effect(() => { if (!open) reset(); })`)

- [ ] **Step 2: Fix gaps detected · 1 commit per modal touched (or single batch commit if minor)**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/lib/components/importaciones/*.svelte && \
  git commit -m "polish(imp-r6): modals audit · ESC/click-outside/disabled-during-submitting parity across IMP modals"
```

---

### Task 22: Cross-tab visual consistency sweep

**Files:**
- Modify (potentially): `el-club-imp/overhaul/src/app.css`

- [ ] **Step 1: Verify `.empty-state` style is shared** (define once in app.css if duplicated across tabs):

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
  color: var(--text-2, #aaa);
}
.empty-state .icon { font-size: 32px; opacity: 0.5; }
.empty-state h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; margin: 0; }
.empty-state p { font-size: 12px; color: var(--text-3, #777); margin: 0; }
.empty-state small { font-size: 11px; opacity: 0.7; }
.empty-state .cta-btn {
  margin-top: 12px; padding: 8px 16px; background: var(--accent, #5b8def);
  color: #fff; border: 0; border-radius: 3px; cursor: pointer; font-size: 12px;
}
```

- [ ] **Step 2: Verify `.err-banner` style is shared**:

```css
.err-banner {
  padding: 10px 14px;
  background: rgba(244, 63, 94, 0.1);
  border: 1px solid var(--alert, #f43f5e);
  border-radius: 3px;
  color: var(--alert, #f43f5e);
  display: flex; gap: 12px; align-items: center; justify-content: space-between;
  font-size: 12px;
}
.err-banner button {
  background: var(--alert, #f43f5e); color: #fff; border: 0;
  padding: 4px 10px; border-radius: 2px; cursor: pointer; font-size: 11px;
}
```

- [ ] **Step 3: Refactor tabs to use shared classes (remove duplicated CSS)**

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add overhaul/src/app.css overhaul/src/lib/components/importaciones/tabs/*.svelte && \
  git commit -m "polish(imp-r6): shared .empty-state + .err-banner styles in app.css · DRY across tabs"
```

---

## Task Group 6: Smoke + verification

### Task 23: Write `smoke_imp_r6.py`

**Files:**
- Create: `el-club-imp/erp/scripts/smoke_imp_r6.py`

- [ ] **Step 1: Write smoke**

```python
#!/usr/bin/env python3
"""
smoke_imp_r6.py — exercises IMP-R6 settings flow end-to-end via SQL.
Verifies: get_settings returns defaults, update persists, invalid values rejected (via Rust),
migration_log returns counts, integrations_status hardcoded structure.

Note: Rust validation tested in cargo tests. This smoke validates DB state contract only.
"""
import os
import sqlite3
import sys
from pathlib import Path

DB = Path(os.environ.get("ERP_DB_PATH", r"C:/Users/Diego/el-club-imp/erp/elclub.db"))


def assert_(cond, msg):
    if not cond:
        print(f"❌ FAIL: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ {msg}")


def main():
    print(f"DB: {DB}")
    conn = sqlite3.connect(str(DB))
    try:
        # Test 1: imp_settings table exists with 7 default rows
        rows = conn.execute("SELECT key, value FROM imp_settings").fetchall()
        keys = {r[0] for r in rows}
        expected = {
            "default_fx", "default_free_ratio", "default_wishlist_target",
            "threshold_wishlist_unbatched_days", "threshold_paid_unarrived_days",
            "threshold_cost_overrun_pct", "threshold_free_unit_unassigned_days",
        }
        assert_(expected.issubset(keys), f"All 7 default keys present (have: {keys})")

        values = {r[0]: r[1] for r in rows}
        assert_(values.get("default_fx") == "7.73", "default_fx == 7.73")
        assert_(values.get("default_free_ratio") == "10", "default_free_ratio == 10")
        assert_(values.get("threshold_wishlist_unbatched_days") == "30", "threshold_wishlist_unbatched_days == 30")

        # Test 2: Manual upsert simulating cmd_update_imp_setting
        conn.execute(
            "INSERT INTO imp_settings (key, value, updated_by) VALUES (?, ?, 'smoke') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by",
            ("default_fx", "7.85"),
        )
        conn.commit()
        new_fx = conn.execute("SELECT value FROM imp_settings WHERE key='default_fx'").fetchone()[0]
        assert_(new_fx == "7.85", "Upsert to 7.85 persisted")

        # Restore
        conn.execute(
            "INSERT INTO imp_settings (key, value, updated_by) VALUES (?, ?, 'smoke') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("default_fx", "7.73"),
        )
        conn.commit()

        # Test 3: migration_log query (proxy via MAX created_at + counts)
        last = conn.execute("SELECT MAX(created_at) FROM imports").fetchone()[0]
        imports_n = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
        wishlist_n = conn.execute("SELECT COUNT(*) FROM import_wishlist").fetchone()[0]
        free_units_n = conn.execute("SELECT COUNT(*) FROM import_free_unit").fetchone()[0]
        print(f"  · migration_log: last={last} imports={imports_n} wishlist={wishlist_n} free={free_units_n}")
        assert_(imports_n >= 0, "imports count queryable")
        assert_(wishlist_n >= 0, "wishlist count queryable")

        # Test 4: indexes present
        idx_names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' "
            "AND tbl_name IN ('import_wishlist','import_free_unit')"
        ).fetchall()}
        for expected_idx in ["idx_wishlist_status", "idx_wishlist_customer",
                             "idx_free_unit_import", "idx_free_unit_destination"]:
            assert_(expected_idx in idx_names, f"Index {expected_idx} present")

        print("\n✅ ALL SMOKE TESTS PASS")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke**

```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r6.py
```
Expected: `✅ ALL SMOKE TESTS PASS`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Diego/el-club-imp && git add erp/scripts/smoke_imp_r6.py && \
  git commit -m "test(imp-r6): SQL smoke · settings + migration_log + indexes verification"
```

---

### Task 24: Final verification (cargo + npm + svelte)

**Files:** ninguno

- [ ] **Step 1: Cargo check + tests**

```bash
cd C:/Users/Diego/el-club-imp/overhaul/src-tauri && \
  cargo check --release 2>&1 | tail -5 && \
  cargo test 2>&1 | tail -15
```
Expected: 0 errors · `imp_r6_settings_test` 5/5 pass + all R1.5/R2/R4 tests still green

- [ ] **Step 2: npm check + build**

```bash
cd C:/Users/Diego/el-club-imp/overhaul && npm run check 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
Expected: 0 errors

- [ ] **Step 3: All smokes**

```bash
cd C:/Users/Diego/el-club-imp/erp && \
  ERP_DB_PATH=C:/Users/Diego/el-club-imp/erp/elclub.db python scripts/smoke_imp_r6.py && \
  python scripts/smoke_apply_imp_schema.py
```
Expected: 2x `ALL SMOKE TESTS PASS`

- [ ] **Step 4: Manual UI verification**

  - Open Tauri ERP (or `npm run tauri dev`)
  - Navigate to Importaciones → Settings tab
  - Verify: 4 sections render · Defaults expanded by default · others collapsed
  - Edit `default_fx` from 7.73 → 7.80 → click Guardar → ✓ check shows
  - Edit `default_fx` to "abc" → click Guardar → red error banner with validation msg
  - Open Migration log section · counts display
  - Open Integrations section · 3 rows with pills (1 active green, 2 disabled gray)
  - Test Re-sync button: hover shows tooltip "Deshabilitado en v0.4.0..."
  - Open WishlistTab (R2) → with 0 rows shows empty state with CTA
  - Open MargenRealTab/FreeUnitsTab/SupplierTab → empty states render
  - Force an error (kill DB temporarily): error banner shows with retry

---

## Self-Review

Before declaring R6 complete, run this mental checklist:

**Spec coverage (sec 4.6):**
- [x] Defaults section: FX, free ratio, wishlist target, lead time read-only → Task 15 ✓
- [x] Umbrales section: 4 thresholds editable → Task 15 ✓
- [x] Migration log read-only with timestamps + counts + Re-sync button → Task 13 + 7 ✓
- [x] Integrations status: elclub.db active + PayPal disabled + DHL disabled → Task 14 + 6 ✓
- [x] Re-sync button STUB-disabled (escalated · documented) → Task 7 ✓

**Schema migration script (DoD line):**
- [x] `apply_imp_schema.py` shipped → Task 1 ✓
- [x] Idempotent (CREATE TABLE IF NOT EXISTS · CREATE INDEX IF NOT EXISTS · INSERT OR IGNORE) → Task 1 ✓
- [x] Tablas: import_wishlist (R1) + import_free_unit (R1) + imp_settings (R6 NEW) + **import_items (R6 NEW · 4 indexes)** → Task 1 ✓
- [x] Backup MANDATORY pre-apply (no opt-out) → Task 1 ✓
- [x] Safety prompt si --apply contra main DB (production) → Task 1 ✓
- [x] CHECK destination convención NULL (no string 'unassigned') → Task 1 ✓
- [x] NO ALTER sale_items (rechazado · Diego eligió import_items en su lugar · ver Open Q #6) → Task 1 ✓
- [x] Verified idempotent + import_items columnas/indexes via smoke (twice-run) → Task 2 ✓
- [x] Applied to worktree DB → Task 2 step 4 ✓

**Polish coverage (DoD line "empty states pulidos"):**
- [x] PedidosTab audit → Task 16 ✓
- [x] WishlistTab empty + loading + error → Task 17 ✓
- [x] MargenRealTab empty + loading + error → Task 18 ✓
- [x] FreeUnitsTab empty + loading + error → Task 19 ✓
- [x] SupplierTab empty + loading + error → Task 20 ✓
- [x] Modals audit (8 modals: 4 R1.5 + R2 + R4) → Task 21 ✓
- [x] Shared empty-state + err-banner CSS → Task 22 ✓

**Placeholder scan:** ningún `TODO` / `implement later` / `add validation` / `similar to Task N` en steps. ✓

**Type consistency:**
- `ImpSetting` / `MigrationLog` / `IntegrationsStatus` ─ camelCase serde rename ✓
- Adapter method names match Rust commands (`getImpSettings`, `updateImpSetting`, etc.) ✓
- Browser stub for `getImpSettings` returns hardcoded defaults (dev preview parity) ✓

**Cross-module impact (per master overview):**
- COM (Sales): cero touch ✓
- FIN (cash flow): cero touch ✓
- ADM Universe: cero touch ✓
- catalog.json: cero touch ✓
- Worker Cloudflare: cero touch ✓
- R4 free_ratio NOT cabled to settings · stays hardcoded (escalated) ✓

**Convention block applied:**
- All 5 commands use `impl_X (pub) + cmd_X (#[tauri::command])` split per lib.rs:2730-2742 ✓

---

## Open questions for Diego

1. **Re-sync migration button**: implementé STUB-disabled con tooltip explicativo (decisión: re-running Streamlit migration podría sobreescribir Tauri-authoritative state · seguro = no implementar v0.4.0). ¿Aceptás o querés behaviour distinto (ej: `--force` flag)?

2. **R4 free_ratio cableado a settings**: en R4 queda HARDCODED `floor(n/10)`. R6 almacena el valor en `imp_settings.default_free_ratio` pero NO lo lee R4 en v0.4.0. Cablearlo sería 1 task extra en R4 (leer setting al close_import). Recomendación: defer a v0.5 para no expandir scope ahora. ¿Confirmás?

3. **Inbox events plumbing**: R6 GUARDA los thresholds (4 valores) pero el módulo Comercial (donde vive el Inbox feature) es responsable de CONSUMIRLOS y emitir alerts. Documenté como follow-up en la note del SettingsTab. ¿Querés que abra ticket separado para Comercial post v0.4.0?

4. **`imports.notes_extra` ALTER**: master overview menciona pero spec no lo requiere. Skip en v0.4.0 (commented out en `apply_imp_schema.py`). ¿OK o lo agregás vos?

5. **Auto-save vs explicit save per field**: implementé explicit "Guardar" button por field (no surprise mutations). Diego puede tunear FX y olvidar guardar otros · trade-off claro. Alternativa: auto-save on blur con debounce. ¿Preferís?

6. **sale_items.customer_id NO se agrega — RESOLVED 2026-04-28 ~19:00.** Peer review sugirió `ALTER TABLE sale_items ADD COLUMN customer_id TEXT` para soportar el split assigned/stock-future. Diego eligió Opción 1 mejorada (tabla nueva `import_items`) que ya tiene `customer_id` como columna nullable + status workflow + FK a wishlist/sale_items/jerseys. `sale_items` NO se modifica · queda como source-of-truth de ventas reales (semantics `sale_id NOT NULL` intactas · evita ambiguity). El ALTER previo está ELIMINADO de `apply_imp_schema.py` · comentario inline documenta la decisión.

---

## Execution Handoff

Plan complete and saved to `el-club-imp/overhaul/docs/superpowers/plans/2026-04-28-importaciones-IMP-R6.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks. Best for `lib.rs` changes + Svelte component creation in parallel where independent.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, checkpoints for review. Best for the polish pass tasks (16-22) since they require visual judgment.

If subagent-driven chosen: REQUIRED SUB-SKILL `superpowers:subagent-driven-development`.
If inline: REQUIRED SUB-SKILL `superpowers:executing-plans`.

---

## After R6 ships

1. Append commit hashes + smoke results to `SESSION-COORDINATION.md` activity log
2. Run `apply_imp_schema.py --apply` on **main DB** (NOT worktree) post-merge:
   ```bash
   python C:/Users/Diego/el-club-imp/erp/scripts/apply_imp_schema.py --apply --db-path C:/Users/Diego/el-club/erp/elclub.db
   ```
3. Verify backup created: `elclub.db.backup-pre-imp-r6-schema-{timestamp}` exists in `el-club/erp/`
4. MSI rebuild + merge `--no-ff` to main + tag `v0.4.0` (per master overview ship plan)
5. Diego acceptance gate #5: "¿Podés tunear defaults + umbrales en Settings?" — must pass before mission-complete declaration
6. LOG.md entry: "IMP-R6 SHIPPED · Settings + polish · 24 tasks · ~430 LOC · script idempotente apply_imp_schema.py applied to main DB"
