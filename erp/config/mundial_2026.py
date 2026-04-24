"""Config del Mundial 2026 — 48 selecciones + requisitos mínimos.

Source of truth para:
  - Filtro '🏆 Solo Mundial 2026' en el queue (corta el ruido de 4281 items
    a ~200-300 que realmente importan durante el sprint pre-Mundial)
  - Dashboard de progreso '🏆 Mundial 2026' con checklist de las 48 × 2 SKUs

Decisión de MVP (Diego, abril 2026):
  - Cada selección debe tener MÍNIMO: Home Fan + Away Fan (ambos manga corta)
  - Total minimum viable: 48 × 2 = 96 SKUs para "Mundial listo a shipear"
  - Cualquier variante extra (long, player, retro, kid, mujer, GK, third)
    es nice-to-have pero no bloquea shipping

Ajustar la lista conforme se confirman repechajes. Torneo confirma 48 teams
finales cierca de 1 mes antes del kickoff (junio 2026).
"""

# 48 selecciones. Mix de hosts + clasificados directos + repechajes probables.
# Ajustar manualmente si alguno queda fuera o entra uno nuevo.
MUNDIAL_2026_TEAMS = [
    # Hosts (clasificados automáticamente)
    "USA", "Canada", "Mexico",
    # AFC — 8 directos + 1 repechaje (9 total)
    "Japan", "Iran", "South Korea", "Australia", "Saudi Arabia",
    "Uzbekistan", "Qatar", "UAE", "Iraq",
    # CAF — 9 directos
    "Morocco", "Senegal", "Tunisia", "Egypt", "Ghana",
    "Cameroon", "Algeria", "Ivory Coast", "Nigeria",
    # CONCACAF — 3 directos adicionales (hosts aparte)
    "Costa Rica", "Jamaica", "Panama",
    # CONMEBOL — 6 directos + 1 repechaje
    "Argentina", "Brazil", "Uruguay", "Colombia", "Paraguay",
    "Ecuador", "Peru",
    # OFC — 1 directo
    "New Zealand",
    # UEFA — 16 directos
    "Spain", "France", "England", "Netherlands", "Portugal",
    "Germany", "Italy", "Croatia", "Belgium", "Switzerland",
    "Denmark", "Norway", "Poland", "Serbia", "Austria", "Turkey",
]

# MVP obligatorio: cada team debe tener estas 2 variantes
MUNDIAL_MIN_VARIANTS = [
    # (variant, modelo_type, sleeve)
    ("home", "fan_adult", "short"),
    ("away", "fan_adult", "short"),
]

# Nice-to-have: shipean pero no bloquean. Para dashboard extendido post-MVP.
MUNDIAL_OPTIONAL_VARIANTS = [
    ("home", "fan_adult", "long"),
    ("away", "fan_adult", "long"),
    ("home", "player_adult", "short"),
    ("away", "player_adult", "short"),
    ("third", "fan_adult", "short"),
    ("home", "kid", None),
    ("home", "woman", None),
    ("home", "goalkeeper", None),
]


# Normalización para matching case-insensitive.
# Usamos fuzzy relaxado (lower + strip) — el catalog puede tener "Argentina ",
# "argentina", "ARGENTINA" y todas son la misma.
_TEAMS_NORM = {t.lower().strip() for t in MUNDIAL_2026_TEAMS}


def is_mundial_team(team_name):
    """True si el team matchea una selección del Mundial 2026."""
    if not team_name:
        return False
    return team_name.lower().strip() in _TEAMS_NORM


def matches_min_variant(item):
    """True si el item (queue row) cumple al menos una variante MÍNIMA.
    Args:
        item: dict con keys variant, modelo_type, sleeve (formato queue_families)
    """
    variant = (item.get("variant") or "").lower().strip()
    modelo_type = item.get("modelo_type") or ""
    sleeve = item.get("sleeve")
    for v, mt, sl in MUNDIAL_MIN_VARIANTS:
        if variant == v and modelo_type == mt:
            if sl is None or sleeve == sl:
                return True
    return False


def item_is_mundial_mvp(item):
    """True si el item es parte del Mundial 2026 MVP (team + variante mínima).
    Combinación de is_mundial_team + matches_min_variant.
    Aplicar este filter con `items = [i for i in items if item_is_mundial_mvp(i)]`.
    """
    return is_mundial_team(item.get("team")) and matches_min_variant(item)
