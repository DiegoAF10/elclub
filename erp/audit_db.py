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

-- Ops s11 — log estructurado de errores en Claude/Gemini retries
CREATE TABLE IF NOT EXISTS audit_api_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id       TEXT,
    photo_index     INTEGER,          -- null para errores de Claude (texto, no foto)
    api             TEXT,              -- 'claude' | 'gemini'
    error           TEXT,
    attempt_n       INTEGER,           -- 1, 2, 3... dónde empezó a fallar
    final_failure   INTEGER DEFAULT 0, -- 1 si agotó todos los retries
    timestamp       TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_err_family ON audit_api_errors(family_id);
CREATE INDEX IF NOT EXISTS idx_api_err_api ON audit_api_errors(api);
CREATE INDEX IF NOT EXISTS idx_api_err_final ON audit_api_errors(final_failure);

-- Ops s11 — telemetry tiempo-por-item para medir velocidad del audit
CREATE TABLE IF NOT EXISTS audit_telemetry (
    family_id       TEXT PRIMARY KEY,
    opened_at       TEXT,
    verified_at     TEXT,
    duration_sec    INTEGER           -- computed al verify
);

CREATE INDEX IF NOT EXISTS idx_telemetry_verified ON audit_telemetry(verified_at);

-- Ops s14 — log append-only de SKUs borrados via botón 🗑 BORRAR en audit UI.
-- Soft-delete: audit_decisions.status='deleted' + el SKU sale del queue default,
-- pero audit_photo_actions permanece (recovery manual posible).
-- family_deleted=1 si el family entero quedó sin modelos post-delete.
CREATE TABLE IF NOT EXISTS audit_delete_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id       TEXT NOT NULL,     -- SKU borrado (PK de audit_decisions)
    canonical_fid   TEXT,               -- family canonical en catalog
    source_fid      TEXT,               -- modelo.source_family_id (para audit_photo_actions lookup)
    motivo          TEXT NOT NULL,
    photo_count     INTEGER,            -- len(modelo.gallery) al borrar
    actions_count   INTEGER,            -- # audit_photo_actions registradas
    was_only_modelo INTEGER DEFAULT 0,  -- 1 si era el único modelo del family
    family_deleted  INTEGER DEFAULT 0,  -- 1 si family completo se marcó deleted
    was_published   INTEGER DEFAULT 0,  -- 1 si final_verified=1 antes del borrar
    timestamp       TEXT
);

CREATE INDEX IF NOT EXISTS idx_delete_log_fid ON audit_delete_log(family_id);
CREATE INDEX IF NOT EXISTS idx_delete_log_ts ON audit_delete_log(timestamp);
"""


# ═══════════════════════════════════════════════════════════════════════
# SKU generator (Ops s13 post-normalize) — identificador semántico legible.
# Formato: {TEAM}-{SEASON}-{VARIANT}-{MODELO}[-N]
#   TEAM    → 2-4 letras uppercase del prefix del family_id, override para famous
#   SEASON  → compact year(s): 2026 (selecciones) o 2526 (YY/YY compacto)
#   VARIANT → 1 letra: L=home V=away R=third E=special G=goalkeeper T=training
#   MODELO  → FS=fan short, FL=fan long, PS=player short, PL=player long,
#             RE=retro, W=woman, K=kid, B=baby. Legacy cats → 3 letras del slug.
#   -N      → sufijo colisión dentro del mismo (team,season,variant) si hay
#             duplicados de (type, sleeve).
# ═══════════════════════════════════════════════════════════════════════

TEAM_ABBR_OVERRIDES = {
    # UEFA top-5
    "manchester-united": "MU", "manchester-city": "MC",
    "paris-saint-germain": "PSG", "psg": "PSG",
    "real-madrid": "RM", "bayern-munich": "BAY",
    "barcelona": "BAR", "ac-milan": "ACM",
    "inter-milan": "INT",  # Inter Milan = "INT"
    "boca-juniors": "BOC", "river-plate": "RIV",
    "club-america": "AME", "atletico-madrid": "ATM",
    "athletic-bilbao": "ATH", "borussia-dortmund": "BVB",
    "juventus": "JUV", "chelsea": "CHE", "liverpool": "LIV",
    "arsenal": "ARS", "tottenham": "TOT",
    "napoli": "NAP", "roma": "ROM", "as-roma": "ROM",
    "lazio": "LAZ", "fiorentina": "FIO", "atalanta": "ATA",
    "flamengo": "FLA", "palmeiras": "PAL", "corinthians": "COR",
    "santos": "SAN", "sao-paulo": "SAO", "s-o-paulo": "SAO",
    "porto": "POR", "benfica": "BEN", "sporting": "SCP",
    "ajax": "AJA", "psv": "PSV",
    "celtic": "CEL", "rangers": "RAN",
    "villarreal": "VLL", "valencia": "VAL", "sevilla": "SEV",
    "real-betis": "BET", "betis": "BET",
    "leicester": "LEI", "leicester-city": "LEI",
    "newcastle": "NEW", "newcastle-united": "NEW",
    "west-ham": "WHU", "west-ham-united": "WHU",
    "inter-miami": "MIA", "inter-miami-cf": "MIA",
    # Disambiguation overrides (collisions detectados)
    "atl-tico-mineiro": "MIN",       # Atlético Mineiro (vs Atlético Madrid=ATM)
    "atletico-mineiro": "MIN",
    "internacional": "POA",           # Internacional Porto Alegre (vs Inter Milan=INT)
    "coritiba": "CTB",                # Coritiba (vs Corinthians=COR, Córdoba=CDB)
    "cordoba": "CDB", "c-rdoba": "CDB",  # Córdoba CF
    "braga": "BRG", "sc-braga": "BRG",   # Braga (vs Brazil=BRA)
    "americas": "AMS",                # Americas (vs América=AME)
    "atletico-nacional": "ATN",       # Atlético Nacional (Colombia)
    "atl-tico-nacional": "ATN",
    "universidad-catolica": "UCA",    # U. Católica Chile
    "universidad-cat-lica": "UCA",
    "universidad-de-chile": "UCH", "u-de-chile": "UCH",
    "universidad-chile": "UCH",
    "chivas-de-guadalajara": "CHI", "chivas": "CHI", "guadalajara": "CHI",
    "cruz-azul": "CRZ",
    "pumas": "PUM", "pumas-unam": "PUM",
    "tigres": "TIG", "tigres-uanl": "TIG",
    "monterrey": "MTY",
}

_CATEGORY_SUFFIXES = (
    "-women", "-kids", "-baby", "-jacket-pants", "-jacket",
    "-training", "-polo", "-vest", "-sweatshirt", "-shorts",
)

_VARIANT_SKU_LETTER = {
    "home": "L", "away": "V", "third": "R",
    "special": "E", "goalkeeper": "G", "training": "T",
    "fourth": "4",
    # Non-táctico (históricos/ediciones) — letters no conflictivas con el
    # modelo code ni con home/away/third.
    "anniversary": "AN",
    "windbreaker": "WB",
    "retro": "RT",     # ≠ third (R) y ≠ retro_adult modelo (RE)
    "originals": "OG",
    "concept": "CC",
    "limited": "LI",
}

_MODELO_SKU_CODE = {
    ("fan_adult", "short"): "FS",
    ("fan_adult", "long"): "FL",
    ("player_adult", "short"): "PS",
    ("player_adult", "long"): "PL",
    ("retro_adult", "short"): "RE",
    ("retro_adult", "long"): "RL",
    ("woman", "short"): "W",
    ("woman", "long"): "WL",
    ("kid", "short"): "K",
    ("kid", "long"): "KL",
    ("baby", "short"): "B",
}


def _strip_category_suffix(prefix):
    for s in _CATEGORY_SUFFIXES:
        if prefix.endswith(s):
            return prefix[: -len(s)]
    return prefix


def _derive_team_code(family_id):
    """Extrae el prefix del slug + genera código 2-4 letras."""
    import re
    m = re.match(r"^(.*?)-(\d{2,4}(?:-\d{2,4})?|noseason)", (family_id or "").lower())
    prefix = m.group(1) if m else (family_id or "").lower()
    prefix = _strip_category_suffix(prefix)
    if prefix in TEAM_ABBR_OVERRIDES:
        return TEAM_ABBR_OVERRIDES[prefix]
    words = [w for w in prefix.split("-") if w]
    if not words:
        return "XXX"
    if len(words) == 1:
        return words[0][:3].upper()
    # Multi-word: primera letra de cada palabra (max 4)
    abbr = "".join(w[0] for w in words)[:4].upper()
    return abbr if len(abbr) >= 2 else words[0][:3].upper()


def _compact_season(season):
    """'2026' → '2026', '25-26' → '2526', '25/26' → '2526'. noseason → NS."""
    if not season: return "NS"
    s = str(season).strip()
    if s == "noseason" or not s: return "NS"
    # YYYY (selecciones): devolver tal cual
    if len(s) == 4 and s.isdigit():
        return s
    # YY-YY o YY/YY: 4 dígitos
    parts = s.replace("/", "-").split("-")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return f"{parts[0].zfill(2)}{parts[1].zfill(2)}"
    # fallback: solo dígitos
    digits = "".join(c for c in s if c.isdigit())
    return digits[:4] if digits else "NS"


def _variant_letter(variant):
    if not variant: return "X"
    return _VARIANT_SKU_LETTER.get(variant.lower(), variant[0].upper())


def _modelo_code(modelo_type, sleeve):
    """Código de modelo. Para tipos unificados usa map fijo; fallback a 2 letras."""
    key = (modelo_type or "", sleeve or "short")
    if key in _MODELO_SKU_CODE:
        return _MODELO_SKU_CODE[key]
    # Legacy/extraño: primeras 2 letras del type
    t = (modelo_type or "XX").replace("_", "")[:2].upper()
    sl = "L" if sleeve == "long" else ""
    return t + sl


def sku_base(family, modelo=None):
    """SKU base sin disambiguador de colisión. Es responsabilidad del caller
    verificar duplicados dentro de la family y agregar sufijo -N.

    Si modelo=None (legacy family sin modelos[]), usa el `category` del family
    como "modelo".
    """
    team = _derive_team_code(family.get("family_id", ""))
    season = _compact_season(family.get("season", ""))
    variant = _variant_letter(family.get("variant", ""))
    if modelo is None:
        # Legacy: category como modelo code
        cat = (family.get("category") or "OTH")[:3].upper()
        modelo_code = cat
    else:
        modelo_code = _modelo_code(modelo.get("type"), modelo.get("sleeve"))
    return f"{team}-{season}-{variant}-{modelo_code}"


def generate_skus_for_family(family):
    """Asigna SKU único a cada modelo de una family (o UN SKU si legacy).

    Retorna lista de SKUs en el mismo orden que family.modelos (o 1 elemento
    si legacy). Maneja colisiones dentro del mismo (team,season,variant) con
    sufijo -2, -3...

    NOTA: este método solo maneja colisiones INTRA-family. Colisiones
    cross-family (ej. 2 teams con mismo abbr) se detectan al nivel de catalog
    completo — ver `resolve_catalog_skus(catalog)`.
    """
    modelos = family.get("modelos") or []
    if not modelos:
        return [sku_base(family, None)]
    bases = [sku_base(family, m) for m in modelos]
    seen = {}
    result = []
    for base in bases:
        if base not in seen:
            seen[base] = 1
            result.append(base)
        else:
            seen[base] += 1
            result.append(f"{base}-{seen[base]}")
    return result


def resolve_sku(catalog, sku):
    """Busca un SKU en el catalog. Retorna (family, modelo) donde:
    - family = la family (unified o legacy) que contiene el SKU
    - modelo = el modelo dict si es unified, o None si legacy

    Retorna (None, None) si el SKU no existe.

    Optimización: si el caller va a hacer muchos lookups, conviene construir
    un índice en una sola pasada. Esta función es O(N × avg_modelos_per_family).
    """
    for fam in catalog:
        modelos = fam.get("modelos") or []
        if modelos:
            for m in modelos:
                if m.get("sku") == sku:
                    return fam, m
        else:
            if fam.get("sku") == sku:
                return fam, None
    return None, None


def build_sku_index(catalog):
    """Retorna dict SKU → (family, modelo | None) para lookups O(1).
    Usar esto al inicio de render_queue / render_detail."""
    idx = {}
    for fam in catalog:
        modelos = fam.get("modelos") or []
        if modelos:
            for m in modelos:
                if m.get("sku"):
                    idx[m["sku"]] = (fam, m)
        else:
            if fam.get("sku"):
                idx[fam["sku"]] = (fam, None)
    return idx


def resolve_catalog_skus(catalog):
    """Asigna SKUs finales a todo el catalog, resolviendo colisiones cross-family
    con sufijo estable `-Xn` (X=collision marker) basado en orden del family_id.

    Retorna dict: {family_id: [skus...]}. Modifica fam/modelos in-place si
    encuentra modelos[] (setea m['sku']) o top-level (setea fam['sku']).
    """
    # Pass 1: generar SKUs base por family
    per_family = {}
    for fam in catalog:
        per_family[fam["family_id"]] = generate_skus_for_family(fam)

    # Pass 2: detectar colisiones cross-family y resolver con sufijo -Xn
    # Ordenamos families por family_id para determinismo. El primero en aparecer
    # mantiene el SKU base; los siguientes obtienen sufijo -X1, -X2, ...
    import collections
    sku_to_families = collections.defaultdict(list)
    ordered_fids = sorted(per_family.keys())
    for fid in ordered_fids:
        for s in per_family[fid]:
            sku_to_families[s].append(fid)

    # Para cada SKU con ≥2 families, los 2nd+ se renombran
    reassignments = {}  # (family_id, original_sku) → new_sku
    for sku, fids in sku_to_families.items():
        if len(fids) <= 1: continue
        for i, fid in enumerate(fids[1:], start=1):
            reassignments[(fid, sku)] = f"{sku}-X{i}"

    # Apply reassignments
    final = {}
    for fid, skus in per_family.items():
        final[fid] = [reassignments.get((fid, s), s) for s in skus]

    # Pass 3: escribir al catalog in-place
    for fam in catalog:
        skus = final[fam["family_id"]]
        modelos = fam.get("modelos") or []
        if modelos:
            for m, s in zip(modelos, skus):
                m["sku"] = s
        else:
            fam["sku"] = skus[0] if skus else None

    return final


def init_audit_schema():
    conn = get_conn()
    conn.executescript(AUDIT_SCHEMA)
    # Ops s14d — ADD COLUMN qa_priority (idempotente — check si ya existe).
    # Identifica SKUs TOP que Diego debe validar visualmente post-refetch
    # (Mundial 48 × home/away fan short + Top-20 clubs 25/26 × home/away fan short).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_decisions)").fetchall()}
    if "qa_priority" not in cols:
        conn.execute("ALTER TABLE audit_decisions ADD COLUMN qa_priority INTEGER DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_qa_priority ON audit_decisions(qa_priority)")
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
    """Ops s13+ — Devuelve lista de items auditables (per-SKU) con metadata
    derivada de catalog. audit_decisions.family_id ahora contiene un SKU (ej
    ARG-2026-L-FS), que resolvemos vía build_sku_index.

    Retorna: list of dicts {
      family_id (=SKU), tier, status, category, team, season, variant, variant_label,
      modelo_type, sleeve, hero, sizes, price, canonical_fid, source_family_id
    }
    """
    sku_idx = build_sku_index(catalog)
    # Compat legacy: algunas rows pueden seguir con family_id tradicional.
    by_id = {f["family_id"]: f for f in catalog}

    # Default sort: T1 → T2 → T3 → T4 → T5 → None (via tier_rank), tiebreaker family_id ASC.
    # Asegura que la primera página del queue siempre muestre lo más prioritario
    # (Diego arranca por Mundial 2026, luego Europa top-5, etc.).
    q = """SELECT family_id, tier, status, COALESCE(qa_priority, 0) AS qa_priority FROM audit_decisions WHERE 1=1"""
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
    for r in rows:
        sku = r["family_id"]  # Ahora es SKU, no family_id tradicional
        resolved = sku_idx.get(sku)
        fam = None
        modelo = None
        if resolved:
            fam, modelo = resolved
        else:
            # Compat: row legacy con family_id tradicional (pre-migration)
            fam = by_id.get(sku)
            modelo = None

        if not fam:
            continue  # audit_decisions row sin match en catalog (huérfano)

        if category_filter and fam.get("category") != category_filter:
            continue

        # Extract display fields
        modelo_type = (modelo or {}).get("type") if modelo else None
        sleeve = (modelo or {}).get("sleeve") if modelo else None
        # Hero del modelo si unified, sino del family
        hero = (modelo or {}).get("hero_thumbnail") if modelo else None
        if not hero:
            hero = fam.get("hero_thumbnail")
        # Gallery length (para badge de # fotos en card)
        gallery = (modelo or {}).get("gallery") if modelo else fam.get("gallery")
        n_photos = len(gallery) if gallery else 0

        out.append({
            "family_id": sku,                       # SKU como PK (nombre del campo preservado por compat)
            "sku": sku,                              # redundant pero explícito
            "tier": r["tier"],
            "status": r["status"],
            "qa_priority": bool(r["qa_priority"]) if "qa_priority" in r.keys() else False,
            "category": fam.get("category"),
            "team": fam.get("team"),
            "season": fam.get("season"),
            "variant": fam.get("variant"),
            "variant_label": fam.get("variant_label") or fam.get("variant"),
            "modelo_type": modelo_type,
            "sleeve": sleeve,
            "hero": hero,
            "n_photos": n_photos,
            "sizes": (modelo or {}).get("sizes") if modelo else None,
            "price": (modelo or {}).get("price") if modelo else None,
            "canonical_fid": fam["family_id"],
            "source_family_id": (modelo or {}).get("source_family_id") if modelo else fam["family_id"],
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
             SUM(CASE WHEN status='needs_rework' THEN 1 ELSE 0 END) as needs_rework,
             SUM(CASE WHEN status='deleted' THEN 1 ELSE 0 END) as deleted,
             SUM(CASE WHEN final_verified=1 THEN 1 ELSE 0 END) as final_verified
           FROM audit_decisions"""
    ).fetchone()
    return dict(r) if r else {}


# ───────────────────────────────────────────
# Ops s11 — API error log (Claude/Gemini retries)
# ───────────────────────────────────────────

def log_api_error(family_id, photo_index, api, error, attempt_n, final_failure=False):
    """Inserta una row en audit_api_errors. Abre su propia conn para no
    interferir con transacciones del caller."""
    from datetime import datetime
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO audit_api_errors
               (family_id, photo_index, api, error, attempt_n, final_failure, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                family_id, photo_index, api,
                str(error)[:500],  # truncar stacks largos
                int(attempt_n), int(bool(final_failure)),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_api_errors(family_id=None, api=None, only_final=False, limit=50):
    conn = get_conn()
    try:
        where = []
        args = []
        if family_id:
            where.append("family_id = ?")
            args.append(family_id)
        if api:
            where.append("api = ?")
            args.append(api)
        if only_final:
            where.append("final_failure = 1")
        sql = "SELECT * FROM audit_api_errors"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ───────────────────────────────────────────
# Ops s11 — telemetry tiempo-por-item
# ───────────────────────────────────────────

def telemetry_open(family_id):
    """Marca apertura de un family en audit. Idempotente: si ya tiene
    `opened_at` no lo sobreescribe (respeta el primer open)."""
    from datetime import datetime
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT opened_at FROM audit_telemetry WHERE family_id = ?", (family_id,)
        ).fetchone()
        if row and row["opened_at"]:
            return  # ya tiene open — respetar
        conn.execute(
            """INSERT INTO audit_telemetry (family_id, opened_at)
               VALUES (?, ?)
               ON CONFLICT(family_id) DO UPDATE SET opened_at = excluded.opened_at
               WHERE audit_telemetry.opened_at IS NULL""",
            (family_id, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def telemetry_verify(family_id):
    """Marca verify y computa duration_sec desde opened_at."""
    from datetime import datetime
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT opened_at FROM audit_telemetry WHERE family_id = ?", (family_id,)
        ).fetchone()
        if not row or not row["opened_at"]:
            # Sin opened_at — insertar con duration 0 para registrar al menos verify
            conn.execute(
                """INSERT OR REPLACE INTO audit_telemetry
                   (family_id, opened_at, verified_at, duration_sec)
                   VALUES (?, ?, ?, 0)""",
                (family_id, datetime.now().isoformat(timespec="seconds"),
                 datetime.now().isoformat(timespec="seconds")),
            )
        else:
            opened = datetime.fromisoformat(row["opened_at"])
            now = datetime.now()
            dur = int((now - opened).total_seconds())
            conn.execute(
                """UPDATE audit_telemetry
                   SET verified_at = ?, duration_sec = ?
                   WHERE family_id = ?""",
                (now.isoformat(timespec="seconds"), dur, family_id),
            )
        conn.commit()
    finally:
        conn.close()


# ───────────────────────────────────────────
# Ops s14 — delete log (soft-delete de SKUs duplicados/erróneos)
# ───────────────────────────────────────────

def log_delete(conn, sku, canonical_fid, source_fid, motivo,
               photo_count=0, actions_count=0,
               was_only_modelo=False, family_deleted=False, was_published=False):
    """Append-only log de un SKU borrado. Ver audit_delete_log schema en AUDIT_SCHEMA."""
    conn.execute(
        """INSERT INTO audit_delete_log
           (family_id, canonical_fid, source_fid, motivo, photo_count, actions_count,
            was_only_modelo, family_deleted, was_published, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sku, canonical_fid, source_fid,
            (motivo or "")[:500],
            int(photo_count or 0),
            int(actions_count or 0),
            int(bool(was_only_modelo)),
            int(bool(family_deleted)),
            int(bool(was_published)),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


def deleted_count_since(conn, days=7):
    """Cantidad de SKUs borrados en los últimos N días (sidebar counter)."""
    row = conn.execute(
        """SELECT COUNT(*) FROM audit_delete_log
           WHERE timestamp >= datetime('now', ?)""",
        (f"-{int(days)} days",),
    ).fetchone()
    return row[0] if row else 0


def telemetry_stats(last_n=50):
    """Stats sobre los últimos N items verified: avg / median / P90 / count.
    Retorna dict con claves: count, avg_sec, median_sec, p90_sec, items (list[dict])."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT family_id, duration_sec, verified_at
               FROM audit_telemetry
               WHERE verified_at IS NOT NULL AND duration_sec > 0
               ORDER BY verified_at DESC
               LIMIT ?""",
            (int(last_n),),
        ).fetchall()
        durations = sorted([r["duration_sec"] for r in rows])
        n = len(durations)
        if n == 0:
            return {"count": 0, "avg_sec": None, "median_sec": None, "p90_sec": None, "items": []}
        avg = sum(durations) / n
        median = durations[n // 2] if n % 2 == 1 else (durations[n // 2 - 1] + durations[n // 2]) / 2
        p90_idx = max(0, int(n * 0.9) - 1)
        p90 = durations[p90_idx]
        return {
            "count": n,
            "avg_sec": round(avg, 1),
            "median_sec": round(median, 1),
            "p90_sec": p90,
            "items": [dict(r) for r in rows[:10]],
        }
    finally:
        conn.close()
