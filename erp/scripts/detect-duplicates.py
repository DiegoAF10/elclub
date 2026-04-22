"""Diagnostic — detecta duplicados potenciales en el audit queue.

3 heurísticas, ordenadas de más específica a más ruidosa:
  1. Mismo tuple (team_key, season_compact, variant, modelo.type, modelo.sleeve)
     → duplicado casi seguro (mismo jersey, mismo demographic, misma sleeve).
  2. Canonical family_id similar (Levenshtein ≤ 2)
     → posible sibling mal-mergeado ('argentina-26-home' vs 'argentina-2026-home').
  3. hero_thumbnail URL idéntico
     → copia directa o gallery artifact (ver PARKED.md P1).

Scope: items con audit_decisions.status != 'deleted'.

Output: ../../elclub-catalogo-priv/docs/duplicate-audit-report.md

Uso: `cd el-club/erp && python scripts/detect-duplicates.py`
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ERP = SCRIPT.parent.parent
sys.path.insert(0, str(ERP))

import audit_db  # noqa: E402

REPORT_PATH = (
    Path(audit_db.CATALOG_PATH).parent.parent / "docs" / "duplicate-audit-report.md"
)


def levenshtein(a, b, max_dist=3):
    """Levenshtein pure-Python con early-exit si excede max_dist.
    Retorna la distancia o max_dist+1 si early-exit."""
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        min_row = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            min_row = min(min_row, curr[j])
        if min_row > max_dist:
            return max_dist + 1
        prev = curr
    return prev[len(b)]


def collect_queue_items(conn, catalog):
    """Items del audit_decisions con metadata resuelta via sku_idx."""
    sku_idx = audit_db.build_sku_index(catalog)
    by_id = {f["family_id"]: f for f in catalog}
    rows = conn.execute(
        "SELECT family_id, tier, status FROM audit_decisions "
        "WHERE status != 'deleted'"
    ).fetchall()
    items = []
    for r in rows:
        sku = r["family_id"]
        resolved = sku_idx.get(sku)
        fam = modelo = None
        if resolved:
            fam, modelo = resolved
        else:
            fam = by_id.get(sku)  # legacy row con family_id tradicional
        if not fam:
            continue
        items.append({
            "sku": sku,
            "tier": r["tier"],
            "status": r["status"],
            "fam": fam,
            "modelo": modelo,
        })
    return items


def group_exact_tuple(items):
    """Heur 1: agrupa por (fid_prefix, season_compact, variant, modelo.type, sleeve)."""
    groups = defaultdict(list)
    for it in items:
        fam = it["fam"]
        modelo = it["modelo"]
        team_key = audit_db._fid_prefix(fam.get("family_id") or "")
        season = audit_db._compact_season(fam.get("season") or "")
        variant = (fam.get("variant") or "").lower()
        mt = (modelo or {}).get("type") or fam.get("category") or ""
        sl = (modelo or {}).get("sleeve") or "short"
        key = (team_key, season, variant, mt, sl)
        groups[key].append(it)
    return {k: v for k, v in groups.items() if len(v) > 1}


def group_by_hero(items):
    """Heur 3: mismo hero_thumbnail URL → ≥2 SKUs apuntan a misma foto."""
    groups = defaultdict(list)
    for it in items:
        fam = it["fam"]
        modelo = it["modelo"]
        hero = (modelo or {}).get("hero_thumbnail") or fam.get("hero_thumbnail")
        if not hero:
            continue
        groups[hero].append(it)
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_similar_canonical(items, max_dist=2):
    """Heur 2: pares de canonical family_ids con Levenshtein ≤ max_dist.
    Bucket por primeros 3 chars para reducir comparaciones O(N²) a O(bucket²)."""
    canonicals = {}
    for it in items:
        cfid = it["fam"].get("family_id")
        if cfid and cfid not in canonicals:
            canonicals[cfid] = it["tier"]
    fids = list(canonicals.keys())
    buckets = defaultdict(list)
    for fid in fids:
        bucket_key = fid[:3] if fid else ""
        buckets[bucket_key].append(fid)

    similar = []
    for bkey, fs in buckets.items():
        for i, a in enumerate(fs):
            for b in fs[i + 1:]:
                d = levenshtein(a, b, max_dist=max_dist)
                if 0 < d <= max_dist:
                    similar.append((a, b, d, canonicals.get(a), canonicals.get(b)))
    return similar


def build_report(items, groups_exact, groups_hero, similar):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_exact_groups = len(groups_exact)
    total_exact_skus = sum(len(v) for v in groups_exact.values())
    total_hero_groups = len(groups_hero)
    total_hero_skus = sum(len(v) for v in groups_hero.values())

    lines = [
        "# Duplicate Audit Report",
        f"Generado: {now}",
        "Script: `el-club/erp/scripts/detect-duplicates.py`",
        "",
        f"**Items analizados:** {len(items)} (audit_decisions.status != 'deleted')",
        "",
        "---",
        "",
        "## Heurística 1 — Mismo tuple (team, season, variant, modelo type, sleeve)",
        "",
        f"**{total_exact_groups}** grupos · **{total_exact_skus}** SKUs afectados.",
        "",
        "Key: `(fid_prefix, season_compact, variant, modelo.type, modelo.sleeve)`. "
        "Duplicados casi seguros — mismo jersey, mismo demographic, misma sleeve.",
        "",
    ]

    if groups_exact:
        tier_dist = defaultdict(int)
        for g in groups_exact.values():
            for it in g:
                tier_dist[it["tier"] or "None"] += 1
        lines.append("**Distribución por tier:** " + " · ".join(
            f"{t}: {n}" for t, n in sorted(tier_dist.items())
        ))
        lines.append("")
        lines.append("| Grupo | SKUs | Tier | Canonical(s) |")
        lines.append("|---|---|---|---|")
        # Priorizar grupos T1 al top
        sorted_groups = sorted(
            groups_exact.items(),
            key=lambda kv: (
                0 if any(it["tier"] == "T1" for it in kv[1]) else 1,
                kv[0],
            ),
        )
        for (team, season, variant, mt, sl), items_in_g in sorted_groups:
            skus = ", ".join(f"`{it['sku']}`" for it in items_in_g)
            tiers = ", ".join(sorted({it["tier"] or "—" for it in items_in_g}))
            canonicals = ", ".join(sorted({it["fam"]["family_id"] for it in items_in_g}))
            label = f"{team} {season} {variant} · {mt}/{sl}"
            lines.append(f"| {label} | {skus} | {tiers} | {canonicals} |")
    else:
        lines.append("✅ **Ningún duplicado exact-tuple.**")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Heurística 3 — Hero thumbnail URL idéntico",
        "",
        f"**{total_hero_groups}** grupos · **{total_hero_skus}** SKUs afectados.",
        "",
        "≥ 2 SKUs apuntan a la misma foto. Copia directa o gallery artifact "
        "(ver PARKED.md P1 — fan short/player short comparten fotos por el fetcher viejo).",
        "",
    ])
    if groups_hero:
        lines.append("| SKUs | Tier | Hero URL |")
        lines.append("|---|---|---|")
        sorted_hero = sorted(
            groups_hero.items(),
            key=lambda kv: (0 if any(it["tier"] == "T1" for it in kv[1]) else 1,),
        )
        for hero, items_in_g in sorted_hero[:50]:
            skus = ", ".join(f"`{it['sku']}`" for it in items_in_g)
            tiers = ", ".join(sorted({it["tier"] or "—" for it in items_in_g}))
            hero_short = "..." + hero[-60:] if len(hero) > 60 else hero
            lines.append(f"| {skus} | {tiers} | {hero_short} |")
        if len(groups_hero) > 50:
            lines.append(f"\n_+ {len(groups_hero) - 50} grupos más — truncado a top 50._")
    else:
        lines.append("✅ **Ningún hero URL compartido.**")
    lines.append("")

    lines.extend([
        "---",
        "",
        "## Heurística 2 — Canonical similar (Levenshtein ≤ 2)",
        "",
        f"**{len(similar)}** pares con edit distance ≤ 2.",
        "",
        "Posibles siblings mal-mergeados (`argentina-26-home` vs `argentina-2026-home`). "
        "Revisar manualmente — algunos son falsos positivos "
        "(ej. `home` vs `away` difieren en 2 chars).",
        "",
    ])
    if similar:
        lines.append("| Canonical A | Canonical B | Dist | Tiers |")
        lines.append("|---|---|---|---|")
        for a, b, d, ta, tb in sorted(similar, key=lambda x: (x[2], x[0]))[:100]:
            tier_pair = f"{ta or '—'} / {tb or '—'}"
            lines.append(f"| `{a}` | `{b}` | {d} | {tier_pair} |")
        if len(similar) > 100:
            lines.append(f"\n_+ {len(similar) - 100} pares más — truncado a top 100._")
    else:
        lines.append("✅ **Ningún canonical similar detectado.**")
    lines.append("")

    # Recomendación Strategy
    t1_affected_exact = sum(
        1 for g in groups_exact.values() if any(it["tier"] == "T1" for it in g)
    )
    lines.extend(["---", "", "## Interpretación (Ops s14)", ""])
    if t1_affected_exact >= 50:
        lines.append(
            f"⚠️ **Pattern sistémico:** {t1_affected_exact} grupos T1 con duplicado "
            "exact-tuple. Vale re-run del scraper con mejor key de unificación antes "
            "de seguir audit. **Recomendación:** construir merge tool (s15) antes "
            "que borrar manualmente."
        )
    elif t1_affected_exact > 10:
        lines.append(
            f"🟡 **Moderado:** {t1_affected_exact} grupos T1 con duplicado exact-tuple. "
            "Si hay 20+ casos, evaluar merge tool (s15). Si no, Diego borra "
            "manualmente con botón s14 (🗑 BORRAR SKU)."
        )
    else:
        lines.append(
            f"✅ **Casos aislados:** {t1_affected_exact} grupos T1 con duplicado "
            "exact-tuple. Diego los borra manualmente con botón s14 (🗑 BORRAR SKU). "
            "Merge tool (s15) no es prioritario."
        )
    lines.append("")
    lines.append("_Auto-generado. Re-ejecutá `python scripts/detect-duplicates.py` para refresh._")
    lines.append("")
    return "\n".join(lines)


def main():
    conn = audit_db.get_conn()
    catalog = audit_db.load_catalog()
    if not catalog:
        print(f"ERROR: catalog.json vacío en {audit_db.CATALOG_PATH}", file=sys.stderr)
        sys.exit(1)

    items = collect_queue_items(conn, catalog)
    print(f"Items analizados: {len(items)} (status != 'deleted')")

    groups_exact = group_exact_tuple(items)
    print(f"Heur 1 - exact tuple: {len(groups_exact)} grupos / "
          f"{sum(len(v) for v in groups_exact.values())} SKUs")

    groups_hero = group_by_hero(items)
    print(f"Heur 3 - hero URL: {len(groups_hero)} grupos / "
          f"{sum(len(v) for v in groups_hero.values())} SKUs")

    print("Heur 2 - canonical Levenshtein (puede tardar)...")
    similar = find_similar_canonical(items, max_dist=2)
    print(f"Heur 2 - similar canonical: {len(similar)} pares (dist <= 2)")

    conn.close()

    report = build_report(items, groups_exact, groups_hero, similar)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"\nReporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
