"""One-shot: backfill metadata faltante en catalog.json.

Fills (solo si valor actual es None/0):
  - meta_country         ← match con wc2026-classified.json vía family_id prefix
  - meta_confederation   ← idem (CONMEBOL/CONCACAF/UEFA/AFC/CAF/OFC)
  - wc2026_eligible      ← True si el team está en classified[]
  - primary_modelo_idx   ← 0 (primer modelo del family)
  - modelo.price         ← default por type (adulto Q435, kid Q275, baby Q250, etc.)

Uso:
    cd erp && python scripts/backfill_catalog_meta.py [--dry-run]

Ejecuta ambos pasos: mutation in-place + save catalog. Backup previo automático.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CATALOG = Path(r"C:\Users\Diego\elclub-catalogo-priv\data\catalog.json")
WC_FILE = Path(r"C:\Users\Diego\elclub-catalogo-priv\data\wc2026-classified.json")
BACKUP_DIR = CATALOG.parent / "backups"

# Frontend (mundial.js MUNDIAL_CONFS, vault.js) espera Conmebol/Concacaf TitleCase
# pero source canonical wc2026-classified.json usa UPPERCASE. Map al display.
CONFEDERATION_DISPLAY = {
    "CONMEBOL": "Conmebol",
    "CONCACAF": "Concacaf",
    "UEFA": "UEFA",
    "AFC": "AFC",
    "CAF": "CAF",
    "OFC": "OFC",
}


DEFAULT_PRICE_BY_TYPE = {
    "fan_adult": 435,
    "player_adult": 435,
    "retro_adult": 435,
    "woman": 435,
    "goalkeeper": 435,
    "adult": 435,
    "kid": 275,
    "baby": 250,
    "polo": 435,
    "vest": 435,
    "training": 435,
    "sweatshirt": 435,
    "jacket": 435,
    "shorts": 435,
}


def fid_prefix(fid: str) -> str:
    """Extract team prefix before season: 'mexico-2026-home' -> 'mexico'."""
    import re
    m = re.match(r"^(.*?)-(\d{2,4}(?:-\d{2,4})?|noseason)", fid.lower())
    return m.group(1) if m else fid.lower()


def season_includes_2026(season: str, fid: str) -> bool:
    """Detecta si la season incluye el año 2026 — handles 4 formatos:
    - "2026"          → True
    - "26-27" / "25-26" cross-year → True (ambos cubren 2026)
    - fid con "-2026-" o termina en "-2026" → True
    - fid con "-25-26-" / "-26-27-" → True

    Sin esto, families con season cross-year (formato YY-YY) quedaban con
    wc2026_eligible=null porque el backfill solo matcheaba "2026" literal.
    Bug detectado 2026-04-25 con Ivory Coast + 19 families más.
    """
    import re
    season_lower = (season or "").lower()
    fid_lower = fid.lower()

    # Caso simple: "2026" en season o fid
    if "2026" in season_lower:
        return True
    if "-2026-" in fid_lower or fid_lower.endswith("-2026"):
        return True

    # Cross-year YY-YY: extraer ambos años y chequear si alguno es 2026
    for source in (season_lower, fid_lower):
        for m in re.finditer(r"(\d{2})-(\d{2})", source):
            try:
                y1 = 2000 + int(m.group(1))
                y2 = 2000 + int(m.group(2))
                if y1 == 2026 or y2 == 2026:
                    return True
            except ValueError:
                continue
    return False


def main(dry_run: bool = False):
    # 1. Load wc2026 classified teams
    with open(WC_FILE, "r", encoding="utf-8") as f:
        wc = json.load(f)
    # Build alias → (name, confederation)
    alias_map = {}
    for t in wc.get("classified", []):
        for alias in t.get("fid_aliases", []):
            alias_map[alias.lower()] = (t["name"], t["confederation"])

    # 2. Load catalog
    with open(CATALOG, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # 3. Iterate + backfill
    stats = {
        "families_total": len(catalog),
        "meta_country_set": 0,
        "meta_confederation_set": 0,
        "wc2026_eligible_set": 0,
        "primary_modelo_idx_set": 0,
        "prices_set": 0,
    }

    for fam in catalog:
        fid = fam.get("family_id") or ""
        prefix = fid_prefix(fid)

        # Match confederation?
        match = alias_map.get(prefix)
        if match:
            country, conf = match
            conf_display = CONFEDERATION_DISPLAY.get(conf, conf)
            if fam.get("meta_country") is None:
                fam["meta_country"] = country
                stats["meta_country_set"] += 1
            # Re-write meta_confederation incluso si ya estaba seteado, para
            # corregir casing UPPER→TitleCase (idempotente cuando ya está OK).
            if fam.get("meta_confederation") != conf_display:
                fam["meta_confederation"] = conf_display
                stats["meta_confederation_set"] += 1
            # Eligible si la season incluye 2026 (4 formatos soportados, ver helper).
            if season_includes_2026(fam.get("season") or "", fid) and fam.get("wc2026_eligible") is None:
                fam["wc2026_eligible"] = True
                stats["wc2026_eligible_set"] += 1

        # primary_modelo_idx default = 0 si hay modelos
        if fam.get("primary_modelo_idx") is None and (fam.get("modelos") or []):
            fam["primary_modelo_idx"] = 0
            stats["primary_modelo_idx_set"] += 1

        # Prices
        for m in (fam.get("modelos") or []):
            if not m.get("price") or m["price"] <= 0:
                t = m.get("type") or "fan_adult"
                m["price"] = DEFAULT_PRICE_BY_TYPE.get(t, 435)
                stats["prices_set"] += 1

    print("=" * 55)
    print("Backfill stats:")
    for k, v in stats.items():
        print(f"  {k:<28} {v}")
    print("=" * 55)

    if dry_run:
        print("\n(dry-run — no se escribió catalog)")
        return

    # 4. Backup
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = BACKUP_DIR / f"catalog.backup-pre-backfill-{ts}.json"
    shutil.copy2(CATALOG, bak)
    print(f"\nBackup: {bak.name}")

    # 5. Save
    tmp = CATALOG.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(CATALOG)
    print(f"Catalog actualizado: {CATALOG}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
