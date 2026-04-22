#!/usr/bin/env python3
"""Backup del audit DB (`elclub.db`) con retention de 20 copias.

Uso:
  python scripts/backup_audit.py                  # CLI
  from scripts.backup_audit import run_backup     # desde Streamlit sidebar

Política:
  - Copia `elclub.db` → `backups/elclub.db.backup-YYYYMMDD-HHMMSS`
  - Mantiene solo los 20 más recientes (elimina los más viejos)
  - Idempotente: si corrés dos veces en el mismo segundo, sobreescribe
    (naming lleva segundos de precisión → improbable en práctica).
"""
from __future__ import annotations
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ERP_DIR = Path(__file__).resolve().parent.parent  # erp/
DB_PATH = ERP_DIR / "elclub.db"
BACKUP_DIR = ERP_DIR / "backups"
RETENTION = 20


def run_backup(retention: int = RETENTION) -> dict:
    """Ejecuta el backup. Retorna dict con resultado para UI o CLI.

    Keys:
      ok:        bool — éxito del copy
      backup:    str  — path absoluto del archivo creado (si ok)
      size_mb:   float — tamaño del backup
      retained:  int  — cuántos backups quedan post-retention
      deleted:   list[str] — nombres de los que se eliminaron
      error:     str  — presente solo si ok=False
    """
    if not DB_PATH.exists():
        return {"ok": False, "error": f"DB no existe en {DB_PATH}"}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"elclub.db.backup-{ts}"

    try:
        shutil.copy2(DB_PATH, dest)
    except Exception as exc:
        return {"ok": False, "error": f"copy fail: {exc}"}

    size_mb = dest.stat().st_size / (1024 * 1024)

    # Retention: ordenar por mtime desc, deletar los que exceden
    backups = sorted(
        BACKUP_DIR.glob("elclub.db.backup-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = []
    for old in backups[retention:]:
        try:
            old.unlink()
            deleted.append(old.name)
        except Exception:
            pass  # tolerar fallos de delete (lock, etc.)

    retained = len([p for p in BACKUP_DIR.glob("elclub.db.backup-*")])

    return {
        "ok": True,
        "backup": str(dest),
        "size_mb": round(size_mb, 2),
        "retained": retained,
        "deleted": deleted,
    }


def cli():
    result = run_backup()
    if result["ok"]:
        print(f"✅ Backup OK: {result['backup']}")
        print(f"   Tamaño: {result['size_mb']} MB")
        print(f"   Total backups retenidos: {result['retained']}/{RETENTION}")
        if result["deleted"]:
            print(f"   Eliminados (over retention): {len(result['deleted'])}")
            for name in result["deleted"]:
                print(f"     - {name}")
    else:
        print(f"❌ Backup falló: {result.get('error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Windows cp1252 no tolera emoji — forzar utf-8
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    cli()
