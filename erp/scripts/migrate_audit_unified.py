#!/usr/bin/env python3
"""Ops s13 — Migración audit_decisions + audit_photo_actions para schema unified.

Catalog nuevo tiene 4,744 families (vs 3,303 en audit DB). Las families viejas
(argentina-2026-home, argentina-2026-home-kids, argentina-2026-home-women)
colapsan en canonical (argentina-2026-home).

Pasos:
  1. BACKUP tables pre-migration (sufijo _pre_s13)
  2. ADD COLUMN audit_photo_actions.modelo_type si no existe
  3. Para cada unified family: mergear rows de audit_decisions de sus ancestros
     bajo un row nuevo con family_id=canonical
     - status: mayor progreso (verified > flagged > skipped > pending)
     - tier: max entre ancestros (en unified catalog ya lo computamos con max)
     - final_verified: 1 si ALGUNA ancestor tenía 1 (respeta publishes previos)
     - checks/notes: toma del adult (canonical) si existe
  4. audit_photo_actions: renombrar family_id a canonical + agregar
     modelo_type basado en source_family_id→modelo mapping
  5. pending_review: renombrar family_id a canonical (si colisión, preferir adult)
  6. audit_telemetry: renombrar family_id a canonical

Uso:
  python scripts/migrate_audit_unified.py              # dry-run
  python scripts/migrate_audit_unified.py --apply      # aplica

BACKUP DB obligatorio pre-apply (scripts/backup_audit.py ya corrido).
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ERP_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ERP_DIR / "elclub.db"
CATALOG_PATH = ERP_DIR.parent.parent / "elclub-catalogo-priv" / "data" / "catalog.json"

STATUS_RANK = {
    "final_verified": 5,  # synthetic rank para comparar
    "verified": 4,
    "needs_rework": 3,
    "flagged": 2,
    "skipped": 1,
    "pending": 0,
}


def pick_best_status(rows):
    """Devuelve el status de mayor progreso entre rows."""
    if not rows: return "pending"
    best = max(rows, key=lambda r: STATUS_RANK.get(r.get("status") or "pending", 0))
    return best.get("status") or "pending"


def pick_tier(rows):
    tiers = [r.get("tier") for r in rows if r.get("tier")]
    if not tiers: return None
    # Tier T1 > T2 > T3 > T4 > T5. "T1" < "T5" string-wise → min().
    return min(tiers)


def pick_first(rows, field):
    for r in rows:
        v = r.get(field)
        if v: return v
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    # Cargar catalog unificado para construir el mapa: old_fid → (canonical_fid, modelo_info)
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Mapeo old_family_id → {canonical_fid, modelo_types_available}
    fid_to_canonical = {}
    fid_to_modelo_type = {}  # old_fid → modelo_type dominante (para modelo_type de audit_photo_actions)

    for fam in catalog:
        cfid = fam["family_id"]
        src_list = fam.get("_unified_from") or [cfid]
        for old_fid in src_list:
            fid_to_canonical[old_fid] = cfid
            # modelo_type dominante: buscar en fam.modelos cuál tiene source_family_id = old_fid
            modelos = fam.get("modelos") or []
            matching = [m for m in modelos if m.get("source_family_id") == old_fid]
            if matching:
                # Si el old_fid tiene múltiples modelos (ej adult con fan_adult + player),
                # usar el primero para audit_photo_actions (foto global, no por modelo).
                fid_to_modelo_type[old_fid] = matching[0]["type"]
            elif modelos:
                fid_to_modelo_type[old_fid] = modelos[0]["type"]
            else:
                fid_to_modelo_type[old_fid] = None  # legacy family sin modelos

    print(f"Catalog unified: {len(catalog)} families")
    print(f"Mapeo old_fid→canonical: {len(fid_to_canonical)} entries")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ── Pre-flight: contar y validar ─────────────────
    n_dec = conn.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
    n_pa = conn.execute("SELECT COUNT(*) FROM audit_photo_actions").fetchone()[0]
    n_pr = conn.execute("SELECT COUNT(*) FROM pending_review").fetchone()[0]
    n_tel = conn.execute("SELECT COUNT(*) FROM audit_telemetry").fetchone()[0]
    print(f"\nPre-migration:")
    print(f"  audit_decisions:     {n_dec}")
    print(f"  audit_photo_actions: {n_pa}")
    print(f"  pending_review:      {n_pr}")
    print(f"  audit_telemetry:     {n_tel}")

    # ── Agrupar decisions por canonical ───────────────
    all_dec = [dict(r) for r in conn.execute("SELECT * FROM audit_decisions").fetchall()]
    by_canonical = {}
    unmapped = []
    for r in all_dec:
        old_fid = r["family_id"]
        canon = fid_to_canonical.get(old_fid)
        if not canon:
            unmapped.append(old_fid)
            continue
        by_canonical.setdefault(canon, []).append(r)

    print(f"\n  Unmapped old_fids (catalog nuevo no los tiene): {len(unmapped)}")
    if unmapped[:5]:
        print(f"    sample: {unmapped[:5]}")

    # Cuántos canonical tienen >=2 rows (merge real)
    merges = [c for c, rs in by_canonical.items() if len(rs) >= 2]
    print(f"  Canonical con >=2 rows a mergear: {len(merges)}")

    if not args.apply:
        # Dry-run: sample de merges
        print(f"\n[DRY RUN] No se escribió nada. Sample de merges:")
        for c in list(merges)[:3]:
            rs = by_canonical[c]
            statuses = [r.get("status") for r in rs]
            print(f"  {c}: {len(rs)} rows con statuses={statuses} → merged status={pick_best_status(rs)}")
        print(f"\nUse --apply para migrar.")
        return

    # ── Apply ─────────────────────────────────────────
    print(f"\n→ APPLY")

    # Step 1: Backup tables
    ts = "pre_s13"
    backup_tables = ["audit_decisions", "audit_photo_actions", "pending_review", "audit_telemetry"]
    for t in backup_tables:
        bk = f"{t}_{ts}"
        conn.execute(f"DROP TABLE IF EXISTS {bk}")
        conn.execute(f"CREATE TABLE {bk} AS SELECT * FROM {t}")
    conn.commit()
    print(f"  Backup tables creados: {', '.join(f'{t}_{ts}' for t in backup_tables)}")

    # Step 2: Add columna modelo_type si no existe
    cols = [c["name"] for c in conn.execute("PRAGMA table_info(audit_photo_actions)").fetchall()]
    if "modelo_type" not in cols:
        conn.execute("ALTER TABLE audit_photo_actions ADD COLUMN modelo_type TEXT")
        conn.commit()
        print("  ADD COLUMN audit_photo_actions.modelo_type")

    # Step 3: Migrate audit_decisions
    # Borro toda la tabla y re-inserto por canonical mergeado (respetando schema original).
    conn.execute("DELETE FROM audit_decisions")
    conn.commit()

    inserted = 0
    for canon, rows in by_canonical.items():
        # Elegir row canonical (si hay una para el fid canonical mismo, preferirla)
        canonical_row = next((r for r in rows if r["family_id"] == canon), rows[0])
        merged = {
            "family_id": canon,
            "tier": pick_tier(rows),
            "status": pick_best_status(rows),
            "checks_json": canonical_row.get("checks_json") or pick_first(rows, "checks_json"),
            "notes": canonical_row.get("notes") or pick_first(rows, "notes"),
            "decided_at": max((r.get("decided_at") or "") for r in rows) or None,
            "reviewed_at": max((r.get("reviewed_at") or "") for r in rows) or None,
            "final_verified": 1 if any(r.get("final_verified") for r in rows) else 0,
            "final_verified_at": max((r.get("final_verified_at") or "") for r in rows) or None,
        }
        conn.execute(
            """INSERT INTO audit_decisions
               (family_id, tier, status, checks_json, notes, decided_at, reviewed_at, final_verified, final_verified_at)
               VALUES (:family_id, :tier, :status, :checks_json, :notes, :decided_at, :reviewed_at, :final_verified, :final_verified_at)""",
            merged,
        )
        inserted += 1
    conn.commit()
    print(f"  audit_decisions: {inserted} rows (merge de {len(all_dec)} originales)")

    # Step 4: audit_photo_actions — renombrar family_id a canonical + set modelo_type
    pa_rows = [dict(r) for r in conn.execute("SELECT * FROM audit_photo_actions").fetchall()]
    pa_migrated = 0
    pa_unmapped = 0
    for r in pa_rows:
        old_fid = r["family_id"]
        canon = fid_to_canonical.get(old_fid)
        modelo_type = fid_to_modelo_type.get(old_fid)
        if not canon:
            pa_unmapped += 1
            continue
        conn.execute(
            "UPDATE audit_photo_actions SET family_id = ?, modelo_type = ? WHERE id = ?",
            (canon, modelo_type, r["id"]),
        )
        pa_migrated += 1
    conn.commit()
    print(f"  audit_photo_actions: {pa_migrated} migrated, {pa_unmapped} unmapped (kept as-is)")

    # Step 5: pending_review — merge por canonical
    pr_rows = [dict(r) for r in conn.execute("SELECT * FROM pending_review").fetchall()]
    pr_by_canon = {}
    for r in pr_rows:
        canon = fid_to_canonical.get(r["family_id"])
        if not canon: continue
        pr_by_canon.setdefault(canon, []).append(r)

    conn.execute("DELETE FROM pending_review")
    for canon, rs in pr_by_canon.items():
        # preferir el row con approved_at (ya publicado), luego con claude_enriched_json
        rs_sorted = sorted(rs, key=lambda r: (bool(r.get("approved_at")), bool(r.get("claude_enriched_json"))), reverse=True)
        best = rs_sorted[0]
        best["family_id"] = canon
        conn.execute(
            """INSERT OR REPLACE INTO pending_review
               (family_id, claude_enriched_json, new_gallery_json, new_hero_url, generated_at, approved_at, rejected_at, rejection_notes)
               VALUES (:family_id, :claude_enriched_json, :new_gallery_json, :new_hero_url, :generated_at, :approved_at, :rejected_at, :rejection_notes)""",
            best,
        )
    conn.commit()
    print(f"  pending_review: {len(pr_by_canon)} rows (merge de {len(pr_rows)} originales)")

    # Step 6: audit_telemetry — renombrar family_id a canonical (respeta idempotente)
    tel_rows = [dict(r) for r in conn.execute("SELECT * FROM audit_telemetry").fetchall()]
    tel_by_canon = {}
    for r in tel_rows:
        canon = fid_to_canonical.get(r["family_id"])
        if not canon: continue
        # Si hay >1 rows apuntando al mismo canonical, preferir la con verified_at
        existing = tel_by_canon.get(canon)
        if existing and existing.get("verified_at"):
            continue
        tel_by_canon[canon] = r

    conn.execute("DELETE FROM audit_telemetry")
    for canon, r in tel_by_canon.items():
        conn.execute(
            "INSERT INTO audit_telemetry (family_id, opened_at, verified_at, duration_sec) VALUES (?, ?, ?, ?)",
            (canon, r.get("opened_at"), r.get("verified_at"), r.get("duration_sec")),
        )
    conn.commit()
    print(f"  audit_telemetry: {len(tel_by_canon)} rows (merge de {len(tel_rows)} originales)")

    # Final counts
    print(f"\nPost-migration:")
    for t in ("audit_decisions", "audit_photo_actions", "pending_review", "audit_telemetry"):
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n}")

    conn.close()
    print("\n✅ Migration done. Rollback:")
    print(f"   DROP TABLE {', '.join(backup_tables)}; ALTER TABLE *_pre_s13 RENAME TO *;")
    print(f"   O restore desde backup/elclub.db.backup-YYYYMMDD-HHMMSS (recomendado).")


if __name__ == "__main__":
    main()
