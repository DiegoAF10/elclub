#!/usr/bin/env python3
"""Ops s13+ — migra audit DB a per-modelo (audit_key = SKU).

Cambio fundamental: el item auditable es el MODELO, no la family unificada.
Cada modelo de una unified family = 1 row en audit_decisions, identificado por
su SKU. Legacy families = 1 row (con SKU derivado de category).

Flujo:
  1. Restaura DB desde backup pre-s13 (3,303 rows originales)
  2. Por cada row en audit_decisions_pre_s13:
     - Encuentra la family o families en catalog que incluyen este family_id
       en su `_unified_from` (puede ser 1 canonical si fue pre-unify).
     - Para cada SKU de modelo cuyo `source_family_id` == el pre-s13 family_id:
       emite un row en audit_decisions con family_id = SKU.
     - Copia status/tier del row pre-s13.
  3. audit_photo_actions: renombra family_id al SKU correspondiente usando la
     relación source_family_id → modelo. Si una foto action apunta a un source
     con múltiples modelos (caso adult con fan+player+retro), DUPLICAR la action
     para cada modelo (comparten galería pre-fix de fetcher).
  4. pending_review + audit_telemetry: renombrar family_id → SKU primary modelo.

Uso:
  python scripts/migrate_audit_per_modelo.py              # dry-run
  python scripts/migrate_audit_per_modelo.py --apply
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ERP_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ERP_DIR / "elclub.db"
CATALOG_PATH = ERP_DIR.parent.parent / "elclub-catalogo-priv" / "data" / "catalog.json"
sys.path.insert(0, str(ERP_DIR))


def build_fid_to_skus_map(catalog):
    """Retorna dict: source_family_id → [(sku, modelo_info, canonical_fid)] list."""
    mapping = defaultdict(list)
    for fam in catalog:
        modelos = fam.get("modelos") or []
        if modelos:
            for m in modelos:
                src = m.get("source_family_id") or fam["family_id"]
                mapping[src].append({
                    "sku": m.get("sku"),
                    "type": m.get("type"),
                    "sleeve": m.get("sleeve"),
                    "canonical_fid": fam["family_id"],
                })
        else:
            # Legacy
            sku = fam.get("sku")
            if sku:
                mapping[fam["family_id"]].append({
                    "sku": sku,
                    "type": None,
                    "sleeve": None,
                    "canonical_fid": fam["family_id"],
                })
    return mapping


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    fid_to_skus = build_fid_to_skus_map(catalog)
    print(f"Catalog: {len(catalog)} families → {sum(len(v) for v in fid_to_skus.values())} audit items (SKUs)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Pre-flight: tablas _pre_s13 deben existir
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    missing = [t for t in ("audit_decisions_pre_s13", "audit_photo_actions_pre_s13", "pending_review_pre_s13", "audit_telemetry_pre_s13") if t not in tables]
    if missing:
        print(f"❌ Faltan backup tables: {missing}. Rollback NO disponible — abortando.")
        sys.exit(1)

    # Carga del estado pre-s13
    pre_dec = [dict(r) for r in conn.execute("SELECT * FROM audit_decisions_pre_s13").fetchall()]
    pre_pa = [dict(r) for r in conn.execute("SELECT * FROM audit_photo_actions_pre_s13").fetchall()]
    pre_pr = [dict(r) for r in conn.execute("SELECT * FROM pending_review_pre_s13").fetchall()]
    pre_tel = [dict(r) for r in conn.execute("SELECT * FROM audit_telemetry_pre_s13").fetchall()]

    print(f"\nPre-s13 backup tables:")
    print(f"  audit_decisions:     {len(pre_dec)}")
    print(f"  audit_photo_actions: {len(pre_pa)}")
    print(f"  pending_review:      {len(pre_pr)}")
    print(f"  audit_telemetry:     {len(pre_tel)}")

    # Expand a per-modelo: por cada decision row pre-s13, 1+ rows post
    new_decisions = []
    unmapped = []
    for row in pre_dec:
        src_fid = row["family_id"]
        targets = fid_to_skus.get(src_fid, [])
        if not targets:
            unmapped.append(src_fid)
            continue
        for t in targets:
            new_decisions.append({
                "family_id": t["sku"],  # SKU como audit key
                "tier": row.get("tier"),
                "status": row.get("status"),
                "checks_json": row.get("checks_json"),
                "notes": row.get("notes"),
                "decided_at": row.get("decided_at"),
                "reviewed_at": row.get("reviewed_at"),
                "final_verified": row.get("final_verified") or 0,
                "final_verified_at": row.get("final_verified_at"),
            })

    print(f"\nExpansión audit_decisions: {len(pre_dec)} → {len(new_decisions)}")
    print(f"  Unmapped (src_fid sin catalog match): {len(unmapped)}")
    if unmapped[:5]:
        print(f"    sample: {unmapped[:5]}")

    # audit_photo_actions: renombrar family_id → SKU. Si el source tiene múltiples
    # modelos (adult con fan+player+retro), duplicamos la row para cada modelo
    # (comparten gallery al momento, separarán cuando fetcher fixee gallery por album).
    new_pa = []
    for row in pre_pa:
        src = row["family_id"]
        targets = fid_to_skus.get(src, [])
        if not targets: continue
        for t in targets:
            new_pa.append({
                "family_id": t["sku"],
                "original_url": row["original_url"],
                "original_index": row["original_index"],
                "action": row.get("action"),
                "new_index": row.get("new_index"),
                "is_new_hero": row.get("is_new_hero") or 0,
                "processed_url": row.get("processed_url"),
                "decided_at": row.get("decided_at"),
                "modelo_type": t["type"],
            })

    print(f"  audit_photo_actions: {len(pre_pa)} → {len(new_pa)}")

    # pending_review: mismo renombre (keep primary)
    new_pr = []
    for row in pre_pr:
        src = row["family_id"]
        targets = fid_to_skus.get(src, [])
        if not targets: continue
        # Solo escribimos al primer modelo (evita duplicar Claude output)
        t = targets[0]
        row["family_id"] = t["sku"]
        new_pr.append(row)
    print(f"  pending_review:      {len(pre_pr)} → {len(new_pr)}")

    # audit_telemetry: mismo (primary)
    new_tel = []
    for row in pre_tel:
        src = row["family_id"]
        targets = fid_to_skus.get(src, [])
        if not targets: continue
        t = targets[0]
        row["family_id"] = t["sku"]
        new_tel.append(row)
    print(f"  audit_telemetry:     {len(pre_tel)} → {len(new_tel)}")

    if not args.apply:
        print("\n[DRY RUN] Use --apply.")
        return

    # ── Apply ──────────────────────────────────────────
    print("\n→ APPLY")

    # Delete current tables, re-create via schema, insert new rows
    import audit_db as ad

    # Drop current working tables (preserve _pre_s13 backup)
    for t in ("audit_decisions", "audit_photo_actions", "pending_review", "audit_telemetry"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()

    # Re-init via audit_db schema (recreate con indexes)
    ad.init_audit_schema()

    # Insert new rows
    with_mt = [c["name"] for c in conn.execute("PRAGMA table_info(audit_photo_actions)").fetchall()]
    if "modelo_type" not in with_mt:
        conn.execute("ALTER TABLE audit_photo_actions ADD COLUMN modelo_type TEXT")
        conn.commit()

    for r in new_decisions:
        conn.execute(
            """INSERT OR REPLACE INTO audit_decisions
               (family_id, tier, status, checks_json, notes, decided_at, reviewed_at, final_verified, final_verified_at)
               VALUES (:family_id, :tier, :status, :checks_json, :notes, :decided_at, :reviewed_at, :final_verified, :final_verified_at)""",
            r,
        )
    for r in new_pa:
        conn.execute(
            """INSERT OR REPLACE INTO audit_photo_actions
               (family_id, original_url, original_index, action, new_index, is_new_hero, processed_url, decided_at, modelo_type)
               VALUES (:family_id, :original_url, :original_index, :action, :new_index, :is_new_hero, :processed_url, :decided_at, :modelo_type)""",
            r,
        )
    for r in new_pr:
        conn.execute(
            """INSERT OR REPLACE INTO pending_review
               (family_id, claude_enriched_json, new_gallery_json, new_hero_url, generated_at, approved_at, rejected_at, rejection_notes)
               VALUES (:family_id, :claude_enriched_json, :new_gallery_json, :new_hero_url, :generated_at, :approved_at, :rejected_at, :rejection_notes)""",
            r,
        )
    for r in new_tel:
        conn.execute(
            """INSERT OR REPLACE INTO audit_telemetry
               (family_id, opened_at, verified_at, duration_sec)
               VALUES (:family_id, :opened_at, :verified_at, :duration_sec)""",
            r,
        )
    conn.commit()

    # Post-counts
    print(f"\nPost-migration:")
    for t in ("audit_decisions", "audit_photo_actions", "pending_review", "audit_telemetry"):
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n}")
    conn.close()
    print("\n✅ Done. Rollback: restore DB desde backup file (backups/elclub.db.backup-*).")


if __name__ == "__main__":
    main()
