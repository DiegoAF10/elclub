"""Admin Web R7 — seed inicial (T1.2).

Pobla la base con:
- 11 tag_types + 122 tags desde overhaul/docs/superpowers/specs/admin-web/tags-seed.json
- 7 saved_views factory para vault.universo
- 3 scheduled_jobs (detect-inbox-events / kpi-snapshot / dirty-detector)
- 4 site_components defaults (header on, footer on, banner_top off, cookie_consent on)

Idempotente: usa INSERT OR IGNORE en todas las tablas con UNIQUE constraints.
Re-ejecutable sin error.

Uso:
    python -m seed_admin_web         # standalone
    from seed_admin_web import seed_admin_web; seed_admin_web()  # programatico

NOTA: el _meta del JSON dice "tags: 110" pero el archivo real contiene 122.
Confiamos en el archivo, no en la metadata. El verify del plan T1.2 dice "110"
pero la verdad es 122.
"""

import json
import os
import sqlite3
from db import get_conn, BASE_DIR


# Path al tags-seed.json del spec
TAGS_SEED_PATH = os.path.normpath(
    os.path.join(BASE_DIR, "..", "overhaul", "docs", "superpowers",
                 "specs", "admin-web", "tags-seed.json")
)


# ─── saved_views factory para vault.universo ───────────────────────
# Los `filters` son JSON descriptivos; el shape final se define cuando se
# construya la UI del Universo (T6.X). Este seed deja marcadores que la
# UI puede honrar o reinterpretar — lo importante es que los presets
# existan al abrir Vault > Universo por primera vez.
VAULT_UNIVERSO_PRESETS = [
    {
        "slug": "default",
        "display_name": "Default",
        "icon": "📋",
        "filters": {},
        "sort": {"field": "decided_at", "direction": "desc"},
        "is_factory": 1,
        "display_order": 0,
    },
    {
        "slug": "queue-del-dia",
        "display_name": "Queue del día",
        "icon": "⏳",
        "filters": {"state": ["QUEUE"]},
        "sort": {"field": "decided_at", "direction": "asc"},
        "is_factory": 1,
        "display_order": 1,
    },
    {
        "slug": "publicados-foto-rota",
        "display_name": "Publicados con foto rota",
        "icon": "📷",
        "filters": {"state": ["PUBLISHED"], "dirty_flag": 1},
        "sort": {"field": "dirty_detected_at", "direction": "desc"},
        "is_factory": 1,
        "display_order": 2,
    },
    {
        "slug": "retros-sin-era",
        "display_name": "Retros sin Era",
        "icon": "🕰️",
        "filters": {"category": "retro_adult", "missing_tag_type": "era"},
        "sort": {"field": "decided_at", "direction": "desc"},
        "is_factory": 1,
        "display_order": 3,
    },
    {
        "slug": "drops-proximos-7d",
        "display_name": "Drops próximos 7d",
        "icon": "🚀",
        "filters": {"stock_publish_at_within_days": 7},
        "sort": {"field": "stock_publish_at", "direction": "asc"},
        "is_factory": 1,
        "display_order": 4,
    },
    {
        "slug": "draft-scrap-fail",
        "display_name": "DRAFT con scrap fail",
        "icon": "⚠️",
        "filters": {"state": ["DRAFT"], "dirty_reason_like": "%scrap%"},
        "sort": {"field": "dirty_detected_at", "direction": "desc"},
        "is_factory": 1,
        "display_order": 5,
    },
    {
        "slug": "latam-mundial-2026",
        "display_name": "Latam Mundial 2026",
        "icon": "🏆",
        "filters": {
            "tag_slugs": ["mundial-2026"],
            "region_tag_slugs": ["sudamerica", "centroamerica", "norteamerica"],
        },
        "sort": {"field": "decided_at", "direction": "desc"},
        "is_factory": 1,
        "display_order": 6,
    },
]


# ─── scheduled_jobs (3) ────────────────────────────────────────────
SCHEDULED_JOBS = [
    {
        "slug": "detect-inbox-events",
        "display_name": "Detect inbox events",
        "cron_expression": "0 * * * *",       # cada hora
        "handler": "detect_inbox_events",
        "enabled": 1,
    },
    {
        "slug": "kpi-snapshot-daily",
        "display_name": "KPI snapshot diario",
        "cron_expression": "0 0 * * *",       # 00:00 UTC todos los días
        "handler": "snapshot_kpis",
        "enabled": 1,
    },
    {
        "slug": "dirty-detector",
        "display_name": "Dirty galleries detector",
        "cron_expression": "0 */4 * * *",     # cada 4 horas
        "handler": "detect_dirty_galleries",
        "enabled": 1,
    },
]


# ─── site_components defaults (4) ──────────────────────────────────
SITE_COMPONENTS = [
    {"type": "header",         "enabled": 1, "config": {}},
    {"type": "footer",         "enabled": 1, "config": {}},
    {"type": "banner_top",     "enabled": 0, "config": {}},
    {"type": "cookie_consent", "enabled": 1, "config": {}},
]


def _seed_tags(conn: sqlite3.Connection) -> dict:
    """Inserta tag_types + tags desde el JSON del spec.

    Returns: {'tag_types': N, 'tags': M, 'tag_types_existed': N2, 'tags_existed': M2}
    """
    with open(TAGS_SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Pre-counts para reportar inserts vs ya-existentes
    pre_types = conn.execute("SELECT COUNT(*) FROM tag_types").fetchone()[0]
    pre_tags = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]

    # 1) tag_types (UNIQUE en slug → INSERT OR IGNORE)
    for tt in data["tag_types"]:
        conditional_rule_json = json.dumps(tt["conditional_rule"]) if tt.get("conditional_rule") else None
        conn.execute(
            """
            INSERT OR IGNORE INTO tag_types
                (slug, display_name, icon, cardinality, display_order,
                 conditional_rule, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tt["slug"], tt["display_name"], tt.get("icon"),
                tt["cardinality"], tt.get("display_order", 0),
                conditional_rule_json, tt.get("description"),
            ),
        )

    # Mapa slug → id para resolver foreign keys de tags
    type_id_by_slug = {
        row[0]: row[1]
        for row in conn.execute("SELECT slug, id FROM tag_types").fetchall()
    }

    # 2) tags (UNIQUE en (type_id, slug) → INSERT OR IGNORE)
    for section in data["tags"]:
        type_slug = section["type_slug"]
        type_id = type_id_by_slug.get(type_slug)
        if type_id is None:
            raise RuntimeError(f"tag_type slug '{type_slug}' no existe — el JSON tiene una sección huérfana")
        for tag in section["tags"]:
            derivation_rule_json = json.dumps(tag["derivation_rule"]) if tag.get("derivation_rule") else None
            conn.execute(
                """
                INSERT OR IGNORE INTO tags
                    (type_id, slug, display_name, icon, color,
                     is_auto_derived, derivation_rule, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_id, tag["slug"], tag["display_name"],
                    tag.get("icon"), tag.get("color"),
                    1 if tag.get("is_auto_derived") else 0,
                    derivation_rule_json,
                    tag.get("display_order", 0),
                ),
            )

    post_types = conn.execute("SELECT COUNT(*) FROM tag_types").fetchone()[0]
    post_tags = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    return {
        "tag_types_inserted": post_types - pre_types,
        "tag_types_total": post_types,
        "tags_inserted": post_tags - pre_tags,
        "tags_total": post_tags,
    }


def _seed_saved_views(conn: sqlite3.Connection) -> dict:
    """Inserta presets factory de vault.universo (UNIQUE module, slug)."""
    pre = conn.execute("SELECT COUNT(*) FROM saved_views WHERE module = 'vault.universo'").fetchone()[0]
    for preset in VAULT_UNIVERSO_PRESETS:
        conn.execute(
            """
            INSERT OR IGNORE INTO saved_views
                (module, slug, display_name, icon, filters, sort,
                 is_factory, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "vault.universo", preset["slug"], preset["display_name"],
                preset.get("icon"),
                json.dumps(preset.get("filters") or {}),
                json.dumps(preset.get("sort")) if preset.get("sort") else None,
                preset.get("is_factory", 1),
                preset.get("display_order", 0),
            ),
        )
    post = conn.execute("SELECT COUNT(*) FROM saved_views WHERE module = 'vault.universo'").fetchone()[0]
    return {"inserted": post - pre, "total": post}


def _seed_scheduled_jobs(conn: sqlite3.Connection) -> dict:
    """Inserta jobs default (UNIQUE slug)."""
    pre = conn.execute("SELECT COUNT(*) FROM scheduled_jobs").fetchone()[0]
    for job in SCHEDULED_JOBS:
        conn.execute(
            """
            INSERT OR IGNORE INTO scheduled_jobs
                (slug, display_name, cron_expression, handler, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job["slug"], job["display_name"], job["cron_expression"],
             job["handler"], job["enabled"]),
        )
    post = conn.execute("SELECT COUNT(*) FROM scheduled_jobs").fetchone()[0]
    return {"inserted": post - pre, "total": post}


def _seed_site_components(conn: sqlite3.Connection) -> dict:
    """Inserta componentes default (NO tiene UNIQUE — check previo por type).

    Patrón: si ya existe al menos 1 row con ese type, skip. Esto permite
    a Diego crear múltiples instancias de un componente custom sin que
    el seed las pisotee.
    """
    pre = conn.execute("SELECT COUNT(*) FROM site_components").fetchone()[0]
    for comp in SITE_COMPONENTS:
        existing = conn.execute(
            "SELECT 1 FROM site_components WHERE type = ? LIMIT 1",
            (comp["type"],),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO site_components (type, config, enabled)
            VALUES (?, ?, ?)
            """,
            (comp["type"], json.dumps(comp["config"]), comp["enabled"]),
        )
    post = conn.execute("SELECT COUNT(*) FROM site_components").fetchone()[0]
    return {"inserted": post - pre, "total": post}


def seed_admin_web(conn: sqlite3.Connection = None) -> dict:
    """Aplica todos los seeds. Idempotente.

    Returns: dict con stats {tags, views, jobs, components} para reporting.
    """
    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True

    stats = {}
    try:
        stats["tags"] = _seed_tags(conn)
        stats["saved_views"] = _seed_saved_views(conn)
        stats["scheduled_jobs"] = _seed_scheduled_jobs(conn)
        stats["site_components"] = _seed_site_components(conn)
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()
    return stats


if __name__ == "__main__":
    print(f"Seeding desde: {TAGS_SEED_PATH}")
    if not os.path.exists(TAGS_SEED_PATH):
        raise SystemExit(f"ERROR: tags-seed.json no existe en {TAGS_SEED_PATH}")
    stats = seed_admin_web()
    print()
    print("=== Stats ===")
    print(f"  tag_types:       inserted={stats['tags']['tag_types_inserted']}, total={stats['tags']['tag_types_total']}")
    print(f"  tags:            inserted={stats['tags']['tags_inserted']}, total={stats['tags']['tags_total']}")
    print(f"  saved_views:     inserted={stats['saved_views']['inserted']}, total={stats['saved_views']['total']}")
    print(f"  scheduled_jobs:  inserted={stats['scheduled_jobs']['inserted']}, total={stats['scheduled_jobs']['total']}")
    print(f"  site_components: inserted={stats['site_components']['inserted']}, total={stats['site_components']['total']}")
