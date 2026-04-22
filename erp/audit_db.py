"""Audit system — schemas + helpers para las 3 tablas nuevas.

Spec en elclub-catalogo-priv/docs/AUDIT-SYSTEM.md sección 6.

Las 3 tablas:
- audit_decisions: estado por family_id (pending/verified/flagged/skipped)
- audit_photo_actions: acciones por foto (keep/delete/flag_watermark/flag_regen/hero)
- pending_review: resultado post-Claude esperando OK final de Diego
"""

import json
import os
import re
import sqlite3
from datetime import datetime
from db import get_conn, BASE_DIR


# Ruta al catalog.json del repo público (fuente de verdad de families)
CATALOG_PATH = os.path.normpath(
    os.path.join(BASE_DIR, "..", "..", "elclub-catalogo-priv", "data", "catalog.json")
)


# ───────────────────────────────────────────
# Schema creation (idempotent)
# ───────────────────────────────────────────

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_decisions (
    family_id           TEXT PRIMARY KEY,
    tier                TEXT,
    status              TEXT DEFAULT 'pending',
    checks_json         TEXT,
    notes               TEXT,
    decided_at          TEXT,
    reviewed_at         TEXT,
    final_verified      INTEGER DEFAULT 0,
    final_verified_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_tier ON audit_decisions(tier);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_decisions(status);

CREATE TABLE IF NOT EXISTS audit_photo_actions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id           TEXT NOT NULL,
    original_url        TEXT,
    original_index      INTEGER,
    action              TEXT,
    new_index           INTEGER,
    is_new_hero         INTEGER DEFAULT 0,
    processed_url       TEXT,
    decided_at          TEXT,
    UNIQUE (family_id, original_index)
);

CREATE INDEX IF NOT EXISTS idx_photo_family ON audit_photo_actions(family_id);
CREATE INDEX IF NOT EXISTS idx_photo_action ON audit_photo_actions(action);

CREATE TABLE IF NOT EXISTS pending_review (
    family_id               TEXT PRIMARY KEY,
    claude_enriched_json    TEXT,
    new_gallery_json        TEXT,
    new_hero_url            TEXT,
    generated_at            TEXT,
    approved_at             TEXT,
    rejected_at             TEXT,
    rejection_notes         TEXT
);
"""


def init_audit_schema():
    conn = get_conn()
    conn.executescript(AUDIT_SCHEMA)
    conn.commit()
    conn.close()


# ───────────────────────────────────────────
# Tier assignment
# ───────────────────────────────────────────
#
# La lógica canónica está documentada en:
#   elclub-catalogo-priv/docs/AUDIT-TIER-LOGIC.md
#
# Resumen:
#   T1  → Mundial 2026 (selecciones con year 2026/2027 en season)
#   T2  → Top-5 Europa con temporada reciente (2023-2027)
#   T3  → Ligas Latam importantes (Argentina, Brasil, Liga MX) — temporada reciente
#   T4  → Retros icónicos (lista hardcoded T4_ICONIC_RETROS)
#   T5  → Fallback: cualquier family con season parseable o categoría válida
#         (retros viejos, clubes secundarios, selecciones no-Mundial)
#   None → Sólo si family rota (category=other o sin metadata mínima)
#
# Matching prefiere `family_id` prefix sobre `team` string porque el segundo
# viene con encoding roto en ~40 families (ej. "atl-tico-mineiro" → team="Atl Tico Mineiro").
# El prefix del slug es la fuente de verdad.

# Top 5 European leagues — teams clave por liga para lookup
# (lowercased, acepta substring match)
EPL_TEAMS = {
    "manchester united", "man united", "manchester city", "man city",
    "liverpool", "chelsea", "arsenal", "tottenham", "newcastle",
    "aston villa", "west ham", "brighton", "everton", "fulham", "crystal palace",
    "wolverhampton", "wolves", "bournemouth", "brentford", "leicester",
    "nottingham forest", "leeds",
}
LALIGA_TEAMS = {
    "real madrid", "barcelona", "atletico madrid", "atlético madrid",
    "athletic bilbao", "athletic club", "real sociedad", "real betis",
    "sevilla", "valencia", "villarreal", "girona", "osasuna", "getafe",
    "celta vigo", "mallorca", "espanyol", "rayo vallecano", "cadiz",
    "las palmas", "almeria", "alaves",
}
BUNDES_TEAMS = {
    "bayern munich", "bayern", "borussia dortmund", "dortmund",
    "leipzig", "rb leipzig", "leverkusen", "bayer leverkusen",
    "borussia monchengladbach", "gladbach", "eintracht frankfurt", "frankfurt",
    "wolfsburg", "stuttgart", "union berlin", "schalke", "hamburg",
}
SERIEA_TEAMS = {
    "ac milan", "milan", "inter milan", "inter", "juventus",
    "napoli", "roma", "as roma", "lazio", "atalanta", "fiorentina",
    "torino", "bologna", "sassuolo", "udinese", "sampdoria",
    "parma calcio", "parma", "verona", "cagliari", "lecce",
    "genoa", "empoli", "venezia", "pisa",
}
LIGUE1_TEAMS = {
    "paris saint germain", "psg", "marseille", "olympique marseille",
    "lyon", "olympique lyon", "monaco", "as monaco", "lille", "nice",
    "rennes", "strasbourg", "nantes", "saint-etienne", "saint etienne",
    "lens", "brest", "bordeaux", "montpellier", "toulouse",
}
TOP5_EUROPE = EPL_TEAMS | LALIGA_TEAMS | BUNDES_TEAMS | SERIEA_TEAMS | LIGUE1_TEAMS

# Matching por family_id prefix (kebab-case sin acentos, más estable que team string).
# Cada entry es el prefix del slug ANTES de la season; ej. 'real-madrid-25-26-home'
# tiene prefix 'real-madrid'.
TOP5_EUROPE_FID = {
    # EPL
    "manchester-united", "manchester-city", "liverpool", "chelsea", "arsenal",
    "tottenham", "tottenham-hotspur", "newcastle", "aston-villa", "west-ham",
    "brighton", "brighton-and-hove-albion", "everton", "fulham", "crystal-palace",
    "wolves", "wolverhampton", "bournemouth", "brentford", "leicester-city",
    "nottingham-forest", "leeds", "leeds-united",
    # La Liga
    "real-madrid", "barcelona", "atletico-madrid", "athletic-bilbao", "athletic-club",
    "real-sociedad", "real-betis", "sevilla", "valencia", "villarreal", "girona",
    "osasuna", "getafe", "celta-vigo", "mallorca", "espanyol", "rayo-vallecano",
    "cadiz", "las-palmas", "almeria", "alaves",
    # Bundesliga
    "bayern-munich", "borussia-dortmund", "rb-leipzig", "leverkusen", "bayer-leverkusen",
    "borussia-monchengladbach", "gladbach", "eintracht-frankfurt", "frankfurt",
    "wolfsburg", "stuttgart", "union-berlin", "schalke", "hamburg",
    # Serie A
    "ac-milan", "inter-milan", "juventus", "napoli", "roma", "as-roma", "lazio",
    "atalanta", "fiorentina", "torino", "bologna", "sassuolo", "udinese",
    "sampdoria", "parma", "parma-calcio", "verona", "cagliari", "lecce",
    "genoa", "empoli", "venezia", "pisa", "venice",
    # Ligue 1
    "paris-saint-germain", "psg", "marseille", "olympique-marseille", "lyon",
    "olympique-lyon", "monaco", "as-monaco", "lille", "nice", "rennes",
    "strasbourg", "nantes", "saint-etienne", "lens", "brest", "bordeaux",
    "montpellier", "toulouse",
}

# Selecciones nacionales (CONMEBOL, CONCACAF, UEFA, CAF, AFC, OFC).
# Incluye todos los clasificados y habituales al Mundial; usado para T1 detection.
# Incluye variantes de encoding roto (cura-ao ← Curaçao, etc.) y spellings alternos
# que aparecen en el catalog.json.
NATIONAL_TEAMS_FID = {
    # CONMEBOL
    "argentina", "brazil", "uruguay", "colombia", "columbia", "chile", "peru",
    "ecuador", "venezuela", "bolivia", "paraguay",
    # CONCACAF
    "mexico", "usa", "usmnt", "canada", "guatemala", "honduras", "costa-rica",
    "panama", "panam", "jamaica", "el-salvador", "nicaragua", "haiti",
    "trinidad-and-tobago", "curacao", "cura-ao", "dominican-republic",
    "puerto-rico", "martinique", "suriname",
    # UEFA
    "spain", "portugal", "france", "england", "germany", "italy", "netherlands",
    "holland", "belgium", "croatia", "denmark", "switzerland", "poland",
    "austria", "scotland", "wales", "serbia", "turkey", "norway", "sweden",
    "ukraine", "greece", "hungary", "czech-republic", "czechia", "romania",
    "slovakia", "slovenia", "albania", "bosnia", "bosnia-herzegovina",
    "bulgaria", "iceland", "ireland", "northern-ireland", "finland",
    "republic-of-ireland", "russia", "montenegro", "north-macedonia", "kosovo",
    "georgia", "moldova", "azerbaijan", "armenia", "estonia", "latvia",
    "lithuania", "cyprus", "luxembourg", "malta",
    # CAF
    "morocco", "senegal", "tunisia", "cameroon", "nigeria", "egypt", "ghana",
    "ivory-coast", "cote-d-ivoire", "south-africa", "algeria", "dr-congo",
    "congo", "mali", "burkina-faso", "cape-verde", "guinea", "equatorial-guinea",
    "zambia", "angola", "gabon", "kenya", "ethiopia", "mozambique",
    # AFC
    "japan", "south-korea", "korea", "saudi-arabia", "iran", "australia",
    "qatar", "iraq", "uae", "united-arab-emirates", "china", "north-korea",
    "uzbekistan", "jordan", "oman", "bahrain", "kuwait", "lebanon", "syria",
    "palestine", "india", "thailand", "vietnam", "malaysia", "indonesia",
    "philippines", "hong-kong", "singapore",
    # OFC
    "new-zealand", "fiji", "solomon-islands", "tahiti", "vanuatu",
}

# T3 — otras ligas importantes (teams en string, match por substring — compat legacy)
LATAM_LEAGUES_TEAMS = {
    # Argentina
    "boca juniors", "boca", "river plate", "river", "racing club",
    "independiente", "san lorenzo", "estudiantes", "velez sarsfield",
    "huracan", "newells", "rosario central", "talleres",
    # Brasileirão
    "flamengo", "palmeiras", "corinthians", "santos", "sao paulo",
    "são paulo", "fluminense", "gremio", "grêmio", "internacional",
    "cruzeiro", "atletico mineiro", "atlético mineiro", "botafogo",
    "vasco", "bahia", "fortaleza", "athletico paranaense", "red bull bragantino",
    # Liga MX
    "club america", "america", "chivas", "guadalajara", "cruz azul",
    "pumas", "tigres", "monterrey", "leon", "león", "santos laguna",
    "toluca", "necaxa", "pachuca", "queretaro", "querétaro",
    "atlas", "mazatlan", "juarez",
}

# LATAM por family_id prefix. Incluye variantes de encoding roto que aparecen
# realmente en el catalog.json (el parser pierde tildes/cedillas y queda espacio):
#   Atlético Mineiro → "atl-tico-mineiro"
#   Vitória → "vit-ria"
#   Grêmio → "gr-mio"
#   São Paulo → "s-o-paulo"  (observado cuando el scrape rompe el ã)
#   Universidad Católica → "universidad-cat-lica"
LATAM_FID = {
    # Argentina
    "boca-juniors", "river-plate", "racing-club", "independiente",
    "san-lorenzo", "estudiantes", "velez-sarsfield", "velez", "huracan",
    "newells", "newell-s", "rosario-central", "talleres", "lanus",
    "defensa-y-justicia", "argentinos-juniors", "colon", "union",
    # Brasileirão + série B/C relevantes
    "flamengo", "palmeiras", "corinthians", "santos", "sao-paulo", "s-o-paulo",
    "fluminense", "gremio", "gr-mio", "internacional", "cruzeiro",
    "atletico-mineiro", "atl-tico-mineiro", "botafogo", "vasco",
    "vasco-da-gama", "bahia", "fortaleza", "athletico-paranaense",
    "athletico", "red-bull-bragantino", "bragantino", "vitoria", "vit-ria",
    "nautico", "n-utico", "paysandu", "pays-ndu", "santa-cruz", "recife",
    "sport-recife", "sport", "ceara", "cear", "coritiba", "goias", "goi-s",
    "chapecoense", "juventude", "atletico-paranaense", "avai", "ava-",
    # Liga MX
    "club-america", "america", "chivas", "chivas-de-guadalajara",
    "guadalajara", "cruz-azul", "pumas", "tigres", "monterrey", "leon",
    "santos-laguna", "toluca", "necaxa", "pachuca", "queretaro",
    "quer-taro", "atlas", "mazatlan", "juarez", "ju-rez", "tijuana",
    "puebla", "xolos",
    # Copa Libertadores relevantes extra (Chile, Ecuador, Uruguay, Colombia, Paraguay)
    "colo-colo", "universidad-de-chile", "university-of-chile",
    "universidad-cat-lica", "universidad-catolica", "peñarol", "pe-arol",
    "nacional", "atletico-nacional", "atl-tico-nacional",
    "millonarios", "america-de-cali", "junior", "ldu", "ldu-quito",
    "barcelona-sc", "emelec", "olimpia", "cerro-porteno", "cerro-porte-o",
    "libertad",
}

# T4 — retros icónicos (hardcoded list)
T4_ICONIC_RETROS = {
    # AC Milan
    "ac-milan-02-03-away",      # Shevchenko 03
    "ac-milan-02-03-home",
    "ac-milan-06-07-home",      # Kaka
    "ac-milan-93-94-home",      # Motta
    # Bayern 01
    "bayern-munich-00-01-home",
    "bayern-munich-00-01-away",
    "bayern-munich-01-02-home",
    # Barça 08/09
    "barcelona-08-09-home",
    "barcelona-08-09-away",
    "barcelona-08-09-third",
    # Argentina retros históricas
    "argentina-1986-home",
    "argentina-1986-away",      # Maradona
    "argentina-1994-home",
    "argentina-1998-home",
    # Brasil 02
    "brazil-2002-home",         # Ronaldo
    "brazil-2002-away",
    # Francia 98
    "france-1998-home",         # Zidane
    "france-1998-away",
    # Inglaterra 90
    "england-1990-home",
    # Holanda 74/88
    "netherlands-1988-home",
    "netherlands-1974-home",
    # Alemania 90
    "germany-1990-home",        # Matthaus
    # Italia 82
    "italy-1982-home",           # Rossi
    # Uruguay retros
    "uruguay-1950-home",         # Maracanazo
    # Colombia 90
    "colombia-1990-home",        # Valderrama
    # Camerún 90
    "cameroon-1990-home",
    # USA 94
    "usa-1994-home",
    # Africa clásicas
    "nigeria-1994-home",         # Okocha
    # Inter triplete
    "inter-milan-09-10-home",    # Triplete Mourinho
    # Real Madrid galácticos
    "real-madrid-02-03-home",
    "real-madrid-10-11-home",
    # Manchester United 99
    "manchester-united-98-99-home",  # Treble
    # Liverpool 05
    "liverpool-04-05-home",      # Istanbul
    # Barcelona 11 Wembley
    "barcelona-10-11-home",
    "barcelona-10-11-away",
    # Boca Libertadores
    "boca-juniors-00-01-home",
    "boca-juniors-99-00-home",
}


def _team_key(team_name):
    """Normaliza team name para lookup."""
    if not team_name:
        return ""
    return team_name.lower().strip()


def _is_top5_europe(team):
    tk = _team_key(team)
    return any(t in tk or tk in t for t in TOP5_EUROPE)


def _is_latam_important(team):
    tk = _team_key(team)
    return any(t in tk or tk in t for t in LATAM_LEAGUES_TEAMS)


def _fid_prefix(fid):
    """Extrae el prefix 'team' de un family_id kebab-case.
    Corta en el primer segmento numérico (season): 'atl-tico-mineiro-25-26-home' → 'atl-tico-mineiro'.
    También corta en 'noseason'. 'real-madrid-2026-home-kids' → 'real-madrid'.
    """
    if not fid:
        return ""
    parts = fid.lower().split("-")
    out = []
    for p in parts:
        if p == "noseason":
            break
        if re.match(r"^\d{2,4}$", p):
            break
        out.append(p)
    return "-".join(out)


def _fid_prefix_match(fid, prefix_set):
    """True si algún prefix del set es ≤ al team-prefix de fid.
    Un prefix 'real-madrid' matchea 'real-madrid-25-26-home' pero NO 'real-madrid-casual-store'.
    """
    if not fid:
        return False
    fid_prefix = _fid_prefix(fid)
    if fid_prefix in prefix_set:
        return True
    # También: cualquier prefix del set que sea prefix exacto del team-prefix de fid
    # (ej. 'athletic-club' set entry matchea fid_prefix='athletic-club-bilbao')
    for p in prefix_set:
        if fid_prefix == p:
            return True
        if fid_prefix.startswith(p + "-"):
            # Verifica que lo que sigue sea continuación del nombre, no un tipo
            # Ej: 'athletic-club' debe aceptar 'athletic-club-bilbao' pero no descartable
            return True
    return False


def _extract_season_years(season):
    """De '25/26' o '2026' o '93/94' → lista de años int.
    '25/26' → [2025, 2026]; '93/94' → [1993, 1994]; '2026' → [2026].
    """
    if not season:
        return []
    s = season.strip()
    # Patrones: "NN/NN", "NN-NN", "NNNN"
    m = re.match(r"^(\d{2})[/\-](\d{2})$", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # Heurística: si < 50 es 2000s, si >= 50 es 1900s
        ya = 2000 + a if a < 50 else 1900 + a
        yb = 2000 + b if b < 50 else 1900 + b
        return [ya, yb]
    m = re.match(r"^(\d{4})$", s)
    if m:
        return [int(m.group(1))]
    m = re.match(r"^(\d{4})[/\-](\d{4})$", s)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    return []


def assign_tier(family):
    """Determina tier para una family. Lógica canónica — ver AUDIT-TIER-LOGIC.md.

    Orden de evaluación:
      1. category=='other'           → None (excluded)
      2. fid en T4_ICONIC_RETROS     → T4
      3. 2026/2027 en season o fid   → T1 si es selección nacional
                                       T2 si es club Top-5 Europa
                                       T3 si es club Latam
                                       T5 si es otro club (ajax, benfica, etc.)
      4. years incluye 2023-2025     → T2 si Top-5 Europa
                                       T3 si Latam
                                       (sigue abajo si ninguno matchea)
      5. Fallback T5                 → cualquier family con season parseable o
                                       categoría válida (adult/women/kids/baby/
                                       jacket/training/polo/vest/sweatshirt).
                                       Cubre retros viejos + clubes secundarios +
                                       selecciones no-Mundial + season='noseason'.
      6. None                        → solo si realmente no hay señal (rare).

    Cambios vs v1 (2026-04-22 AM):
      - Matching por family_id prefix en vez de team string (evita bugs de encoding).
      - NATIONAL_TEAMS_FID introduce detección explícita de selecciones (110+ países).
      - Fallback T5 absorbe ~580+ families que antes caían en None.
      - T2/T3 aceptan years 2023-2027 (antes solo 2025-2027 para T2).
    """
    cat = family.get("category")
    if cat == "other":
        return None   # excluded

    fid = (family.get("family_id") or "").lower()
    team = family.get("team") or ""
    season = family.get("season") or ""
    years = _extract_season_years(season)

    # T4: retros icónicos (hardcoded list) — prioridad máxima
    if fid in T4_ICONIC_RETROS:
        return "T4"

    # ── Señal Mundial 2026 ──────────────────────────────
    # season='2026' literal (selecciones que usan ese formato),
    # fid contiene '-2026-' (selecciones con año completo),
    # o years incluye 2026/2027 (clubes con 25/26, 26/27).
    is_world_cup = (
        ("2026" in season)
        or ("-2026-" in fid)
        or fid.endswith("-2026")
        or (bool(years) and (2026 in years or 2027 in years))
    )

    if is_world_cup:
        # Selección nacional → T1 (Mundial 2026 strict sense)
        if _fid_prefix_match(fid, NATIONAL_TEAMS_FID):
            return "T1"
        # Club Top-5 con temporada actual → T2
        if _fid_prefix_match(fid, TOP5_EUROPE_FID) or _is_top5_europe(team):
            return "T2"
        # Club Latam actual → T3
        if _fid_prefix_match(fid, LATAM_FID) or _is_latam_important(team):
            return "T3"
        # Club secundario con 25/26 o 26/27 (Ajax, Benfica, Celtic, Porto, etc.) → T5
        if cat:
            return "T5"

    # ── Temporadas actuales sin señal Mundial ────────────
    # Rango extendido 2023-2025 para absorber Premier 23/24, 24/25, etc.
    current_years = {2023, 2024, 2025}
    has_current = bool(years) and bool(set(years) & current_years)

    if has_current:
        if _fid_prefix_match(fid, TOP5_EUROPE_FID) or _is_top5_europe(team):
            return "T2"
        if _fid_prefix_match(fid, LATAM_FID) or _is_latam_important(team):
            return "T3"

    # ── Fallback T5 ──────────────────────────────────────
    # Cualquier family con season parseable (retros viejos, ligas secundarias,
    # selecciones no-Mundial) o categoría visible cae en T5. Evita None.
    visible_cats = {"adult", "women", "kids", "baby", "jacket", "training",
                    "polo", "vest", "sweatshirt"}
    if years or cat in visible_cats:
        return "T5"

    return None


def rebuild_tiers(catalog=None, dry_run=False):
    """Recalcula `tier` para todas las families de audit_decisions con la lógica
    vigente de assign_tier. Preserva status, checks, notes — solo actualiza `tier`.

    Uso típico tras cambiar la lógica de assign_tier o expandir los diccionarios
    de teams. Idempotente.

    Args:
      catalog: lista de familias (si None, carga desde catalog.json).
      dry_run: si True, no escribe cambios — solo retorna stats.

    Returns:
      dict con { before: {tier: count}, after: {tier: count}, changed: int, total: int }
    """
    from collections import Counter

    if catalog is None:
        catalog = load_catalog()
    by_id = {f["family_id"]: f for f in catalog}

    conn = get_conn()
    rows = conn.execute(
        "SELECT family_id, tier FROM audit_decisions"
    ).fetchall()

    before = Counter()
    after = Counter()
    changed = 0
    missing_from_catalog = 0

    for r in rows:
        fid = r["family_id"]
        old_tier = r["tier"]
        before[old_tier or "None"] += 1

        fam = by_id.get(fid)
        if not fam:
            missing_from_catalog += 1
            after[old_tier or "None"] += 1
            continue

        new_tier = assign_tier(fam)
        after[new_tier or "None"] += 1
        if new_tier != old_tier:
            changed += 1
            if not dry_run:
                conn.execute(
                    "UPDATE audit_decisions SET tier = ? WHERE family_id = ?",
                    (new_tier, fid),
                )

    if not dry_run:
        conn.commit()
    conn.close()

    return {
        "total": len(rows),
        "changed": changed,
        "missing_from_catalog": missing_from_catalog,
        "before": dict(before),
        "after": dict(after),
        "dry_run": dry_run,
    }


# ───────────────────────────────────────────
# Seed initial data from catalog.json
# ───────────────────────────────────────────

def seed_audit_queue():
    """Primera vez: popula audit_decisions con status=pending para todas las families
    que tengan hero_thumbnail != null. Tier asignado según heurísticas.
    Idempotente: si family_id ya existe, no la toca.
    """
    if not os.path.exists(CATALOG_PATH):
        return {"error": f"catalog.json no encontrado en {CATALOG_PATH}", "seeded": 0}

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    conn = get_conn()
    existing = set(
        r[0] for r in conn.execute("SELECT family_id FROM audit_decisions").fetchall()
    )

    seeded = 0
    skipped_no_hero = 0
    skipped_excluded = 0
    now = datetime.now().isoformat(timespec="seconds")

    for fam in catalog:
        fid = fam.get("family_id")
        if not fid or fid in existing:
            continue
        if not fam.get("hero_thumbnail"):
            skipped_no_hero += 1
            continue

        tier = assign_tier(fam)
        # Still include tier=None — Diego asigna manual.
        # Excluir solo si category=other
        if fam.get("category") == "other":
            skipped_excluded += 1
            continue

        conn.execute(
            """INSERT INTO audit_decisions (family_id, tier, status, decided_at)
               VALUES (?, ?, 'pending', ?)""",
            (fid, tier, now),
        )
        seeded += 1

    conn.commit()
    conn.close()

    return {
        "seeded": seeded,
        "skipped_no_hero": skipped_no_hero,
        "skipped_excluded_other": skipped_excluded,
        "total_in_catalog": len(catalog),
    }


# ───────────────────────────────────────────
# Family lookup helpers
# ───────────────────────────────────────────

def load_catalog():
    if not os.path.exists(CATALOG_PATH):
        return []
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_family(catalog, family_id):
    for f in catalog:
        if f.get("family_id") == family_id:
            return f
    return None


def find_related_variants(catalog, base_family_id):
    """Busca variantes relacionadas (women/kids/baby/jacket/etc) de una family base.
    base_family_id es adulto (sin sufijo), ej 'argentina-2026-home'.
    Retorna dict {category: family}.
    """
    result = {}
    fam_base = get_family(catalog, base_family_id)
    if fam_base:
        result["adult"] = fam_base

    suffixes_to_cat = {
        "-women": "women",
        "-kids": "kids",
        "-baby": "baby",
        "-jacket": "jacket",
        "-jacket-pants": "jacket",
        "-training": "training",
        "-polo": "polo",
        "-vest": "vest",
        "-sweatshirt": "sweatshirt",
    }
    for suffix, cat in suffixes_to_cat.items():
        fid = base_family_id + suffix
        fam = get_family(catalog, fid)
        if fam:
            result[cat] = fam

    return result


def mother_family_id(family_id):
    """Devuelve el family_id 'madre' (adulto sin sufijo). Ej:
    'argentina-2026-home-women' → 'argentina-2026-home'
    'argentina-2026-home-kids' → 'argentina-2026-home'
    'argentina-2026-home' → 'argentina-2026-home'
    """
    for suffix in ("-women", "-kids", "-baby", "-jacket-pants", "-jacket",
                   "-training", "-polo", "-vest", "-sweatshirt",
                   "-shorts", "-pants", "-set", "-set-kids", "-other"):
        if family_id.endswith(suffix):
            return family_id[: -len(suffix)]
    return family_id


# ───────────────────────────────────────────
# Audit decision CRUD
# ───────────────────────────────────────────

def get_decision(conn, family_id):
    row = conn.execute(
        "SELECT * FROM audit_decisions WHERE family_id = ?", (family_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_decision(conn, family_id, **fields):
    allowed = {"tier", "status", "checks_json", "notes",
               "decided_at", "reviewed_at", "final_verified", "final_verified_at"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    # Ensure row exists
    existing = conn.execute(
        "SELECT family_id FROM audit_decisions WHERE family_id = ?", (family_id,)
    ).fetchone()
    if existing is None:
        cols = ["family_id"] + list(clean.keys())
        vals = [family_id] + list(clean.values())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO audit_decisions ({','.join(cols)}) VALUES ({placeholders})",
            vals,
        )
    else:
        sets = ", ".join(f"{k}=?" for k in clean.keys())
        conn.execute(
            f"UPDATE audit_decisions SET {sets} WHERE family_id = ?",
            list(clean.values()) + [family_id],
        )
    conn.commit()


def get_photo_actions(conn, family_id):
    rows = conn.execute(
        "SELECT * FROM audit_photo_actions WHERE family_id = ? ORDER BY original_index",
        (family_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def clear_photo_actions(conn, family_id):
    conn.execute("DELETE FROM audit_photo_actions WHERE family_id = ?", (family_id,))
    conn.commit()


def set_photo_action(conn, family_id, original_url, original_index,
                     action="keep", new_index=None, is_new_hero=0, processed_url=None):
    """Upsert por (family_id, original_index)."""
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """INSERT OR REPLACE INTO audit_photo_actions
           (family_id, original_url, original_index, action, new_index, is_new_hero, processed_url, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (family_id, original_url, original_index, action, new_index, is_new_hero, processed_url, now),
    )
    conn.commit()


# ───────────────────────────────────────────
# Pending review CRUD
# ───────────────────────────────────────────

def save_pending_review(conn, family_id, claude_json=None, gallery_json=None, new_hero=None):
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """INSERT OR REPLACE INTO pending_review
           (family_id, claude_enriched_json, new_gallery_json, new_hero_url, generated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (family_id, claude_json, gallery_json, new_hero, now),
    )
    conn.commit()


def get_pending_review(conn, family_id):
    row = conn.execute(
        "SELECT * FROM pending_review WHERE family_id = ?", (family_id,)
    ).fetchone()
    return dict(row) if row else None


def list_pending_reviews(conn):
    rows = conn.execute(
        """SELECT p.*, d.tier FROM pending_review p
           LEFT JOIN audit_decisions d ON p.family_id = d.family_id
           WHERE p.approved_at IS NULL AND p.rejected_at IS NULL
           ORDER BY p.generated_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def mark_approved(conn, family_id):
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE pending_review SET approved_at = ? WHERE family_id = ?",
        (now, family_id),
    )
    conn.execute(
        "UPDATE audit_decisions SET final_verified = 1, final_verified_at = ? WHERE family_id = ?",
        (now, family_id),
    )
    conn.commit()


def mark_rejected(conn, family_id, notes=""):
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE pending_review SET rejected_at = ?, rejection_notes = ? WHERE family_id = ?",
        (now, notes, family_id),
    )
    conn.execute(
        "UPDATE audit_decisions SET status = 'needs_rework' WHERE family_id = ?",
        (family_id,),
    )
    conn.commit()


# ───────────────────────────────────────────
# Queue listing (para la vista principal)
# ───────────────────────────────────────────

def queue_families(conn, catalog, tier_filter=None, status_filter=None, category_filter=None):
    """Devuelve lista de families para el queue, aplicando filtros + agrupando
    por 'producto madre' (solo family_ids adulto/base, sin sufijo de categoría).

    Retorna: list of dicts { family_id, tier, status, category, team, season, variant, hero }
    """
    by_id = {f["family_id"]: f for f in catalog}

    # Default sort: T1 → T2 → T3 → T4 → T5 → None (via tier_rank), tiebreaker family_id ASC.
    # Asegura que la primera página del queue siempre muestre lo más prioritario
    # (Diego arranca por Mundial 2026, luego Europa top-5, etc.).
    q = """SELECT family_id, tier, status FROM audit_decisions WHERE 1=1"""
    params = []
    if tier_filter:
        q += " AND tier = ?"
        params.append(tier_filter)
    if status_filter:
        q += " AND status = ?"
        params.append(status_filter)
    q += """
        ORDER BY
          CASE tier
            WHEN 'T1' THEN 1
            WHEN 'T2' THEN 2
            WHEN 'T3' THEN 3
            WHEN 'T4' THEN 4
            WHEN 'T5' THEN 5
            ELSE 6
          END ASC,
          family_id ASC
    """
    rows = conn.execute(q, params).fetchall()

    out = []
    mother_seen = set()
    for r in rows:
        fid = r["family_id"]
        fam = by_id.get(fid)
        if not fam:
            continue
        if category_filter and fam.get("category") != category_filter:
            continue
        # Agrupa por 'producto madre' — mostramos solo el adulto base como entry del queue
        # El detail view muestra todas las variantes relacionadas
        mother = mother_family_id(fid)
        if mother != fid:
            # Es una variante, la saltamos (se ve dentro del detail del madre)
            continue
        if mother in mother_seen:
            continue
        mother_seen.add(mother)

        out.append({
            "family_id": fid,
            "tier": r["tier"],
            "status": r["status"],
            "category": fam.get("category"),
            "team": fam.get("team"),
            "season": fam.get("season"),
            "variant": fam.get("variant"),
            "hero": fam.get("hero_thumbnail"),
        })
    return out


def queue_stats(conn):
    """Stats de totales para el header."""
    r = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
             SUM(CASE WHEN status='verified' THEN 1 ELSE 0 END) as verified,
             SUM(CASE WHEN status='flagged' THEN 1 ELSE 0 END) as flagged,
             SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped,
             SUM(CASE WHEN final_verified=1 THEN 1 ELSE 0 END) as final_verified
           FROM audit_decisions"""
    ).fetchone()
    return dict(r) if r else {}
