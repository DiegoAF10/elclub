"""Config del Mundial 2026 — 48 selecciones clasificadas (sorteo final).

Source of truth para:
  - Filtro '🏆 Solo Mundial 2026' en el queue
  - Dashboard '🏆 Mundial 2026 Progress' con checklist de las 96 SKUs MVP

MVP (Diego, abril 2026):
  - Cada selección: Home Fan + Away Fan (ambos manga corta) = OBLIGATORIO
  - Total: 48 × 2 = 96 SKUs para Mundial shipeable
  - Resto (long, player, third, kid, mujer, GK): nice-to-have post-ship

Cada team tiene:
  - canonical: nombre en inglés (formato del catalog)
  - aliases: variantes en español y otras lenguas para matching robusto
  - group: A-L (los 12 grupos del torneo, útil para ordenar el dashboard)
"""

MUNDIAL_2026_TEAMS = [
    # ═══ Grupo A ═══
    {"canonical": "Mexico",            "group": "A", "aliases": ["mexico", "méxico"]},
    {"canonical": "South Africa",      "group": "A", "aliases": ["south africa", "sudáfrica", "sudafrica"]},
    {"canonical": "South Korea",       "group": "A", "aliases": ["south korea", "corea del sur", "korea republic", "republic of korea", "corea"]},
    {"canonical": "Czech Republic",    "group": "A", "aliases": ["czech republic", "república checa", "republica checa", "czechia", "chequia"]},

    # ═══ Grupo B ═══
    {"canonical": "Canada",            "group": "B", "aliases": ["canada", "canadá"]},
    {"canonical": "Bosnia and Herzegovina", "group": "B", "aliases": ["bosnia and herzegovina", "bosnia y herzegovina", "bosnia", "bih"]},
    {"canonical": "Qatar",             "group": "B", "aliases": ["qatar", "catar"]},
    {"canonical": "Switzerland",       "group": "B", "aliases": ["switzerland", "suiza"]},

    # ═══ Grupo C ═══
    {"canonical": "Brazil",            "group": "C", "aliases": ["brazil", "brasil"]},
    {"canonical": "Morocco",           "group": "C", "aliases": ["morocco", "marruecos"]},
    {"canonical": "Haiti",             "group": "C", "aliases": ["haiti", "haití"]},
    {"canonical": "Scotland",          "group": "C", "aliases": ["scotland", "escocia"]},

    # ═══ Grupo D ═══
    {"canonical": "United States",     "group": "D", "aliases": ["united states", "usa", "estados unidos", "u.s.a.", "us"]},
    {"canonical": "Paraguay",          "group": "D", "aliases": ["paraguay"]},
    {"canonical": "Australia",         "group": "D", "aliases": ["australia"]},
    {"canonical": "Turkey",            "group": "D", "aliases": ["turkey", "turquía", "turquia", "türkiye"]},

    # ═══ Grupo E ═══
    {"canonical": "Germany",           "group": "E", "aliases": ["germany", "alemania"]},
    {"canonical": "Curacao",           "group": "E", "aliases": ["curacao", "curazao", "curaçao"]},
    {"canonical": "Ivory Coast",       "group": "E", "aliases": ["ivory coast", "costa de marfil", "côte d'ivoire", "cote d'ivoire"]},
    {"canonical": "Ecuador",           "group": "E", "aliases": ["ecuador"]},

    # ═══ Grupo F ═══
    {"canonical": "Netherlands",       "group": "F", "aliases": ["netherlands", "países bajos", "paises bajos", "holanda", "holland"]},
    {"canonical": "Japan",             "group": "F", "aliases": ["japan", "japón", "japon"]},
    {"canonical": "Sweden",            "group": "F", "aliases": ["sweden", "suecia"]},
    {"canonical": "Tunisia",           "group": "F", "aliases": ["tunisia", "túnez", "tunez"]},

    # ═══ Grupo G ═══
    {"canonical": "Belgium",           "group": "G", "aliases": ["belgium", "bélgica", "belgica"]},
    {"canonical": "Egypt",             "group": "G", "aliases": ["egypt", "egipto"]},
    {"canonical": "Iran",              "group": "G", "aliases": ["iran", "irán"]},
    {"canonical": "New Zealand",       "group": "G", "aliases": ["new zealand", "nueva zelanda", "nueva zelandia"]},

    # ═══ Grupo H ═══
    {"canonical": "Spain",             "group": "H", "aliases": ["spain", "españa", "espana"]},
    {"canonical": "Cape Verde",        "group": "H", "aliases": ["cape verde", "cabo verde", "cabo-verde"]},
    {"canonical": "Saudi Arabia",      "group": "H", "aliases": ["saudi arabia", "arabia saudita", "arabia saudí", "arabia saudi"]},
    {"canonical": "Uruguay",           "group": "H", "aliases": ["uruguay"]},

    # ═══ Grupo I ═══
    {"canonical": "France",            "group": "I", "aliases": ["france", "francia"]},
    {"canonical": "Senegal",           "group": "I", "aliases": ["senegal"]},
    {"canonical": "Iraq",              "group": "I", "aliases": ["iraq", "irak"]},
    {"canonical": "Norway",            "group": "I", "aliases": ["norway", "noruega"]},

    # ═══ Grupo J ═══
    {"canonical": "Argentina",         "group": "J", "aliases": ["argentina"]},
    {"canonical": "Algeria",           "group": "J", "aliases": ["algeria", "argelia"]},
    {"canonical": "Austria",           "group": "J", "aliases": ["austria"]},
    {"canonical": "Jordan",            "group": "J", "aliases": ["jordan", "jordania"]},

    # ═══ Grupo K ═══
    {"canonical": "Portugal",          "group": "K", "aliases": ["portugal"]},
    {"canonical": "DR Congo",          "group": "K", "aliases": ["dr congo", "rd congo", "democratic republic of congo", "república democrática del congo", "republica democratica del congo", "congo dr"]},
    {"canonical": "Uzbekistan",        "group": "K", "aliases": ["uzbekistan", "uzbekistán"]},
    {"canonical": "Colombia",          "group": "K", "aliases": ["colombia"]},

    # ═══ Grupo L ═══
    {"canonical": "England",           "group": "L", "aliases": ["england", "inglaterra"]},
    {"canonical": "Croatia",           "group": "L", "aliases": ["croatia", "croacia"]},
    {"canonical": "Ghana",             "group": "L", "aliases": ["ghana"]},
    {"canonical": "Panama",            "group": "L", "aliases": ["panama", "panamá"]},
]

assert len(MUNDIAL_2026_TEAMS) == 48, f"Mundial 2026 tiene 48 selecciones, got {len(MUNDIAL_2026_TEAMS)}"

# MVP obligatorio: cada team debe tener estas 2 variantes → 48 × 2 = 96 SKUs
MUNDIAL_MIN_VARIANTS = [
    # (variant, modelo_type, sleeve, display_label)
    ("home", "fan_adult", "short", "Home Fan"),
    ("away", "fan_adult", "short", "Away Fan"),
]

# Nice-to-have (dashboard extendido post-MVP)
MUNDIAL_OPTIONAL_VARIANTS = [
    ("home", "fan_adult", "long", "Home Fan L/S"),
    ("away", "fan_adult", "long", "Away Fan L/S"),
    ("home", "player_adult", "short", "Home Player"),
    ("away", "player_adult", "short", "Away Player"),
    ("third", "fan_adult", "short", "Third Fan"),
    ("home", "kid", None, "Home Kid"),
    ("home", "woman", None, "Home Mujer"),
    ("home", "goalkeeper", None, "Home GK"),
]


# ══════════════════════════════════════════════════════
# Alias index para matching rápido (construido al load)
# ══════════════════════════════════════════════════════
_ALIAS_TO_CANONICAL = {}
for _team in MUNDIAL_2026_TEAMS:
    for _alias in _team["aliases"]:
        _ALIAS_TO_CANONICAL[_alias.lower().strip()] = _team["canonical"]


def is_mundial_team(team_name):
    """True si el team matchea alguna selección del Mundial 2026 (vía aliases)."""
    if not team_name:
        return False
    return team_name.lower().strip() in _ALIAS_TO_CANONICAL


def get_mundial_canonical(team_name):
    """Retorna el nombre canonical en inglés si el team matchea, sino None.
    Útil para agrupar SKUs del mismo team bajo un nombre consistente."""
    if not team_name:
        return None
    return _ALIAS_TO_CANONICAL.get(team_name.lower().strip())


def matches_min_variant(item):
    """True si el item cumple al menos una variante MÍNIMA (home/away fan short)."""
    variant = (item.get("variant") or "").lower().strip()
    modelo_type = item.get("modelo_type") or ""
    sleeve = item.get("sleeve")
    for v, mt, sl, _label in MUNDIAL_MIN_VARIANTS:
        if variant == v and modelo_type == mt:
            if sl is None or sleeve == sl:
                return True
    return False


def item_is_mundial_mvp(item):
    """True si item es parte del Mundial MVP (team + variante mínima)."""
    return is_mundial_team(item.get("team")) and matches_min_variant(item)


def team_by_group():
    """Agrupa los 48 teams por grupo A-L. Útil para dashboard ordenado."""
    groups = {}
    for t in MUNDIAL_2026_TEAMS:
        groups.setdefault(t["group"], []).append(t)
    return dict(sorted(groups.items()))
