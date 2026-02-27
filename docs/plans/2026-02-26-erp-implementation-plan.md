# El Club ERP — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Streamlit + SQLite ERP for jersey inventory management, with a fast entry form, inventory views, photo upload, dashboard, and website sync.

**Architecture:** Streamlit multipage app with SQLite backend, following the ClanTrack pattern (same stack Diego already uses). Pre-loaded teams database (~200 teams). Photos stored as files, paths in DB. Serves on 0.0.0.0:8502 for mobile access.

**Tech Stack:** Python 3.11, Streamlit 1.54, SQLite3, Pandas, Plotly, Pillow

**Design doc:** `el-club/docs/plans/2026-02-26-erp-stock-system-design.md`

---

## Task 1: Project Scaffolding + .gitignore

**Files:**
- Create: `el-club/erp/.streamlit/config.toml`
- Create: `el-club/erp/data/` (directory)
- Create: `el-club/erp/photos/` (directory)
- Modify: `el-club/.gitignore`

**Step 1: Create directory structure**

```bash
cd C:/Users/Diego/el-club
mkdir -p erp/.streamlit erp/data erp/photos
```

**Step 2: Create Streamlit config with Midnight Stadium theme**

Create `el-club/erp/.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#4DA8FF"
backgroundColor = "#0D0D0D"
secondaryBackgroundColor = "#1C1C1C"
textColor = "#F0F0F0"
font = "sans serif"

[server]
headless = true
port = 8502
address = "0.0.0.0"
maxUploadSize = 10

[browser]
gatherUsageStats = false
```

**Step 3: Update .gitignore**

Append to `el-club/.gitignore`:

```
# ERP
erp/elclub.db
erp/photos/
erp/__pycache__/
```

**Step 4: Commit**

```bash
git add .gitignore erp/.streamlit/config.toml
git commit -m "scaffold: ERP directory structure and Streamlit config"
```

---

## Task 2: Database Schema

**Files:**
- Create: `el-club/erp/schema.sql`
- Create: `el-club/erp/db.py` (database helper module)

**Step 1: Write schema.sql**

Create `el-club/erp/schema.sql`:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════
-- TEAMS (pre-loaded reference)
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    short_name  TEXT,
    league      TEXT NOT NULL,
    country     TEXT,
    tier        TEXT DEFAULT 'B' CHECK(tier IN ('A', 'B', 'C'))
);

CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- ═══════════════════════════════════════
-- JERSEYS (main inventory — 1 row = 1 physical jersey)
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS jerseys (
    jersey_id       TEXT PRIMARY KEY,
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    season          TEXT NOT NULL,
    variant         TEXT NOT NULL CHECK(variant IN ('home', 'away', 'third', 'special')),
    player_name     TEXT,
    player_number   INTEGER,
    size            TEXT NOT NULL CHECK(size IN ('S', 'M', 'L', 'XL')),
    patches         TEXT,
    tier            TEXT DEFAULT 'B' CHECK(tier IN ('A', 'B', 'C')),
    cost            REAL DEFAULT 100,
    price           REAL,
    status          TEXT DEFAULT 'available' CHECK(status IN ('available', 'reserved', 'sold')),
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_jerseys_team ON jerseys(team_id);
CREATE INDEX IF NOT EXISTS idx_jerseys_size ON jerseys(size);
CREATE INDEX IF NOT EXISTS idx_jerseys_status ON jerseys(status);
CREATE INDEX IF NOT EXISTS idx_jerseys_tier ON jerseys(tier);

-- ═══════════════════════════════════════
-- PHOTOS
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS photos (
    photo_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    jersey_id   TEXT NOT NULL REFERENCES jerseys(jersey_id) ON DELETE CASCADE,
    photo_type  TEXT NOT NULL CHECK(photo_type IN ('front', 'back', 'detail')),
    filename    TEXT NOT NULL,
    uploaded_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_photos_jersey ON photos(jersey_id);

-- ═══════════════════════════════════════
-- VIEWS
-- ═══════════════════════════════════════

CREATE VIEW IF NOT EXISTS v_inventory_summary AS
SELECT
    t.league,
    j.size,
    j.tier,
    j.status,
    COUNT(*) as count
FROM jerseys j
JOIN teams t ON j.team_id = t.team_id
GROUP BY t.league, j.size, j.tier, j.status;

CREATE VIEW IF NOT EXISTS v_stock_by_team AS
SELECT
    t.name as team_name,
    t.league,
    t.tier as team_tier,
    j.size,
    j.variant,
    j.status,
    COUNT(*) as count
FROM jerseys j
JOIN teams t ON j.team_id = t.team_id
GROUP BY t.name, t.league, t.tier, j.size, j.variant, j.status;

CREATE VIEW IF NOT EXISTS v_photo_coverage AS
SELECT
    j.jersey_id,
    t.short_name as team,
    j.season,
    j.variant,
    j.size,
    COUNT(p.photo_id) as photo_count,
    SUM(CASE WHEN p.photo_type = 'front' THEN 1 ELSE 0 END) as has_front,
    SUM(CASE WHEN p.photo_type = 'back' THEN 1 ELSE 0 END) as has_back,
    SUM(CASE WHEN p.photo_type = 'detail' THEN 1 ELSE 0 END) as has_detail
FROM jerseys j
JOIN teams t ON j.team_id = t.team_id
LEFT JOIN photos p ON j.jersey_id = p.jersey_id
GROUP BY j.jersey_id;
```

**Step 2: Write db.py helper**

Create `el-club/erp/db.py`:

```python
"""Database helper — El Club ERP."""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "elclub.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")

os.makedirs(PHOTOS_DIR, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()


def next_jersey_id(conn: sqlite3.Connection) -> str:
    """Generate next jersey ID like JRS-001, JRS-002..."""
    row = conn.execute(
        "SELECT jersey_id FROM jerseys ORDER BY jersey_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return "JRS-001"
    num = int(row["jersey_id"].split("-")[1]) + 1
    return f"JRS-{num:03d}"


def insert_jersey(conn, team_id, season, variant, size, tier,
                  player_name=None, player_number=None, patches=None,
                  cost=100, price=None, notes=None) -> str:
    """Insert a jersey and return its ID."""
    jersey_id = next_jersey_id(conn)
    conn.execute(
        """INSERT INTO jerseys
           (jersey_id, team_id, season, variant, size, tier,
            player_name, player_number, patches, cost, price, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (jersey_id, team_id, season, variant, size, tier,
         player_name, player_number, patches, cost, price, notes),
    )
    conn.commit()
    return jersey_id


def insert_photo(conn, jersey_id, photo_type, filename) -> int:
    """Insert a photo record and return its ID."""
    cur = conn.execute(
        "INSERT INTO photos (jersey_id, photo_type, filename) VALUES (?, ?, ?)",
        (jersey_id, photo_type, filename),
    )
    conn.commit()
    return cur.lastrowid


def get_teams(conn):
    """Get all teams ordered by league then name."""
    return conn.execute(
        "SELECT * FROM teams ORDER BY league, name"
    ).fetchall()


def get_team_by_id(conn, team_id):
    """Get a single team by ID."""
    return conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()


def count_teams(conn) -> int:
    """Count loaded teams."""
    return conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]


def count_jerseys(conn, status=None) -> int:
    """Count jerseys, optionally filtered by status."""
    if status:
        return conn.execute(
            "SELECT COUNT(*) FROM jerseys WHERE status = ?", (status,)
        ).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM jerseys").fetchone()[0]
```

**Step 3: Verify schema loads**

```bash
cd C:/Users/Diego/el-club/erp
python -c "from db import init_db, get_conn, count_teams; init_db(); print('DB OK, teams:', count_teams(get_conn()))"
```

Expected: `DB OK, teams: 0`

**Step 4: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/schema.sql erp/db.py
git commit -m "feat(erp): database schema and helper module"
```

---

## Task 3: Pre-loaded Teams Database

**Files:**
- Create: `el-club/erp/data/teams.json`
- Create: `el-club/erp/seed.py` (seed script)

**Step 1: Create teams.json**

Create `el-club/erp/data/teams.json` with ~200 teams. Structure:

```json
[
  {"name": "Manchester City", "short_name": "Man City", "league": "Premier League", "country": "Inglaterra", "tier": "A"},
  {"name": "Arsenal", "short_name": "Arsenal", "league": "Premier League", "country": "Inglaterra", "tier": "A"},
  ...
]
```

Full team list by league:

**Premier League (20):** Man City, Arsenal, Liverpool, Chelsea, Man United, Tottenham (Tier A); Newcastle, Aston Villa, Brighton, West Ham, Crystal Palace, Wolves, Fulham, Bournemouth, Brentford, Everton, Nottingham Forest, Leicester, Ipswich, Southampton (Tier B)

**La Liga (20):** Barcelona, Real Madrid, Atlético de Madrid (Tier A); Athletic Bilbao, Real Sociedad, Villarreal, Betis, Sevilla, Valencia, Celta de Vigo, Osasuna, Getafe, Rayo Vallecano, Mallorca, Girona, Alavés, Las Palmas, Real Valladolid, Espanyol, Leganés (Tier B)

**Serie A (20):** Juventus, Inter, Milan, Napoli (Tier A); Roma, Lazio, Atalanta, Fiorentina, Bologna, Torino, Udinese, Genoa, Cagliari, Empoli, Parma, Hellas Verona, Como, Venezia, Lecce, Monza (Tier B)

**Bundesliga (18):** Bayern Munich, Borussia Dortmund (Tier A); RB Leipzig, Bayer Leverkusen, Eintracht Frankfurt, Wolfsburg, Freiburg, Stuttgart, Union Berlin, Werder Bremen, Hoffenheim, Mainz, Augsburg, Borussia Mönchengladbach, Köln, Heidenheim, Darmstadt, Bochum (Tier B)

**Ligue 1 (18):** PSG (Tier A); Marseille, Monaco, Lyon, Lille, Nice, Rennes, Lens, Strasbourg, Toulouse, Montpellier, Nantes, Reims, Brest, Le Havre, Metz, Lorient, Clermont (Tier B)

**Liga MX (18):** América, Chivas, Cruz Azul, Tigres, Monterrey (Tier A); Pumas, Santos, León, Toluca, Pachuca, Atlas, Puebla, Querétaro, Necaxa, Mazatlán, San Luis, Tijuana, Juárez (Tier B)

**Liga Nacional Guatemala (6):** Municipal, Comunicaciones (Tier B); Xelajú, Antigua GFC, Cobán Imperial, Santa Lucía Cotz. (Tier C)

**Argentina (10):** Boca Juniors, River Plate (Tier A); Racing, Independiente, San Lorenzo, Vélez, Estudiantes, Talleres, Huracán, Rosario Central (Tier B)

**Brasil (10):** Flamengo, Palmeiras, Corinthians (Tier A); São Paulo, Santos, Grêmio, Internacional, Atlético Mineiro, Botafogo, Fluminense (Tier B)

**Colombia (6):** Millonarios, Atlético Nacional, América de Cali (Tier B); Junior, Deportivo Cali, Santa Fe (Tier B)

**Selecciones (~40):** Argentina, Brasil, Francia, Alemania, España, Inglaterra (Tier A); México, Portugal, Países Bajos, Italia, Bélgica, Croacia, Uruguay, Colombia, USA, Japón, Corea del Sur, Marruecos, Senegal, Ghana, Camerún, Nigeria, Australia, Canadá, Ecuador, Chile, Perú, Paraguay, Costa Rica, Panamá, Honduras, Guatemala, El Salvador, Arabia Saudita, Qatar, Irán, Gales, Suiza, Dinamarca, Polonia, Serbia (Tier B)

**Step 2: Create seed.py**

Create `el-club/erp/seed.py`:

```python
"""Seed the teams table from teams.json."""

import json
import os
from db import get_conn, init_db, count_teams

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_PATH = os.path.join(BASE_DIR, "data", "teams.json")


def seed_teams():
    """Load teams from JSON into SQLite."""
    init_db()
    conn = get_conn()

    existing = count_teams(conn)
    if existing > 0:
        print(f"Teams table already has {existing} rows. Skipping seed.")
        conn.close()
        return

    with open(TEAMS_PATH, "r", encoding="utf-8") as f:
        teams = json.load(f)

    conn.executemany(
        """INSERT INTO teams (name, short_name, league, country, tier)
           VALUES (:name, :short_name, :league, :country, :tier)""",
        teams,
    )
    conn.commit()
    print(f"Seeded {len(teams)} teams.")
    conn.close()


if __name__ == "__main__":
    seed_teams()
```

**Step 3: Run seed and verify**

```bash
cd C:/Users/Diego/el-club/erp
python seed.py
python -c "from db import get_conn, count_teams; print('Teams:', count_teams(get_conn()))"
```

Expected: `Seeded ~200 teams.` then `Teams: ~200`

**Step 4: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/data/teams.json erp/seed.py
git commit -m "feat(erp): pre-loaded teams database (~200 teams, 11 leagues)"
```

---

## Task 4: Streamlit App Shell + Dashboard Page

**Files:**
- Create: `el-club/erp/app.py`

**Step 1: Write app.py with multipage navigation and dashboard**

Create `el-club/erp/app.py`:

```python
"""El Club ERP — Inventory Management System."""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, date
from db import get_conn, init_db, count_jerseys, count_teams, PHOTOS_DIR, BASE_DIR

# ═══════════════════════════════════════
# INIT
# ═══════════════════════════════════════

init_db()

# Check if teams are seeded
conn_check = get_conn()
if count_teams(conn_check) == 0:
    from seed import seed_teams
    seed_teams()
conn_check.close()

# ═══════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════

st.set_page_config(
    page_title="El Club ERP",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Midnight Stadium feel
st.markdown("""
<style>
    .stApp { font-family: 'Space Grotesk', sans-serif; }
    div[data-testid="stMetric"] {
        background-color: #1C1C1C;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label { color: #999999; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #F0F0F0; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════

PAGES = {
    "Dashboard": "dashboard",
    "Registrar Camiseta": "register",
    "Inventario": "inventory",
    "Agregar Fotos": "photos",
}

st.sidebar.image(
    os.path.join(BASE_DIR, "..", "assets", "img", "brand", "logo.png"),
    width=120,
)
st.sidebar.markdown("---")
page = st.sidebar.radio("Navegación", list(PAGES.keys()), label_visibility="collapsed")

# World Cup countdown in sidebar
wc_date = date(2026, 6, 11)
days_to_wc = (wc_date - date.today()).days
st.sidebar.markdown("---")
st.sidebar.markdown(f"### ⚽ World Cup 2026")
st.sidebar.markdown(f"## {days_to_wc} días")

# ═══════════════════════════════════════
# PAGES — Each page is a function
# ═══════════════════════════════════════

# Import page functions (defined below or in separate modules)
# For now all in one file for simplicity


def page_dashboard():
    """Main dashboard with inventory metrics."""
    st.title("⚽ El Club ERP")

    conn = get_conn()

    # Top metrics
    total = count_jerseys(conn)
    available = count_jerseys(conn, "available")
    reserved = count_jerseys(conn, "reserved")
    sold = count_jerseys(conn, "sold")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Camisetas", total)
    col2.metric("Disponibles", available)
    col3.metric("Reservadas", reserved)
    col4.metric("Vendidas", sold)

    if total == 0:
        st.info("No hay camisetas registradas. Andá a **Registrar Camiseta** para empezar.")
        conn.close()
        return

    # Charts
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Por Talla")
        df_size = pd.read_sql_query(
            """SELECT size, COUNT(*) as count FROM jerseys
               WHERE status = 'available' GROUP BY size
               ORDER BY CASE size WHEN 'S' THEN 1 WHEN 'M' THEN 2
               WHEN 'L' THEN 3 WHEN 'XL' THEN 4 END""",
            conn,
        )
        if not df_size.empty:
            fig = px.bar(df_size, x="size", y="count",
                        color_discrete_sequence=["#4DA8FF"],
                        labels={"size": "Talla", "count": "Cantidad"})
            fig.update_layout(
                plot_bgcolor="#0D0D0D", paper_bgcolor="#0D0D0D",
                font_color="#F0F0F0", showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Por Liga")
        df_league = pd.read_sql_query(
            """SELECT t.league, COUNT(*) as count FROM jerseys j
               JOIN teams t ON j.team_id = t.team_id
               WHERE j.status = 'available'
               GROUP BY t.league ORDER BY count DESC""",
            conn,
        )
        if not df_league.empty:
            fig = px.bar(df_league, x="count", y="league", orientation="h",
                        color_discrete_sequence=["#4DA8FF"],
                        labels={"league": "Liga", "count": "Cantidad"})
            fig.update_layout(
                plot_bgcolor="#0D0D0D", paper_bgcolor="#0D0D0D",
                font_color="#F0F0F0", showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Photo coverage
    st.subheader("Cobertura de Fotos")
    photo_stats = conn.execute(
        """SELECT
            COUNT(DISTINCT j.jersey_id) as total,
            COUNT(DISTINCT CASE WHEN p.photo_id IS NOT NULL THEN j.jersey_id END) as with_photos
           FROM jerseys j LEFT JOIN photos p ON j.jersey_id = p.jersey_id
           WHERE j.status = 'available'"""
    ).fetchone()
    with_photos = photo_stats["with_photos"]
    total_avail = photo_stats["total"]
    pct = (with_photos / total_avail * 100) if total_avail > 0 else 0
    st.progress(pct / 100, text=f"{with_photos} de {total_avail} camisetas con fotos ({pct:.0f}%)")

    # Sync button
    st.markdown("---")
    st.subheader("Sync al Sitio")
    if st.button("🔄 Generar products.json", type="primary"):
        sync_to_website(conn)

    conn.close()


def page_register():
    """Jersey registration form — the star of the show."""
    st.title("📝 Registrar Camiseta")

    conn = get_conn()
    teams = conn.execute(
        "SELECT team_id, name, short_name, league, tier FROM teams ORDER BY league, name"
    ).fetchall()

    # Build team options: "League — Team Name"
    team_options = {f"{t['league']} — {t['name']}": t for t in teams}
    team_labels = list(team_options.keys())

    # Session counter
    if "session_count" not in st.session_state:
        st.session_state.session_count = 0
    if "last_saved" not in st.session_state:
        st.session_state.last_saved = None

    with st.form("jersey_form", clear_on_submit=True):
        # Team selection (searchable)
        selected_label = st.selectbox(
            "Equipo *",
            team_labels,
            index=None,
            placeholder="Buscá un equipo...",
        )

        # Show auto-filled league
        if selected_label:
            team = team_options[selected_label]
            st.caption(f"**Liga:** {team['league']}  |  **Tier:** {team['tier']}")
            default_tier_idx = ["A", "B", "C"].index(team["tier"])
        else:
            default_tier_idx = 1

        col1, col2 = st.columns(2)
        with col1:
            season = st.selectbox(
                "Temporada *",
                ["2025/26", "2024/25", "2023/24", "2022/23", "2021/22",
                 "2020/21", "2019/20", "Retro", "Clásica"],
            )
            variant = st.radio(
                "Tipo *",
                ["home", "away", "third", "special"],
                format_func=lambda x: {"home": "Local", "away": "Visita",
                                       "third": "Reserva", "special": "Especial"}[x],
                horizontal=True,
            )
        with col2:
            size = st.radio("Talla *", ["S", "M", "L", "XL"], horizontal=True)
            tier = st.selectbox("Tier", ["A", "B", "C"], index=default_tier_idx)

        col3, col4 = st.columns(2)
        with col3:
            player_name = st.text_input("Jugador (opcional)")
            player_number = st.number_input(
                "Número (opcional)", min_value=0, max_value=99,
                value=None, step=1,
            )
        with col4:
            patches = st.text_input("Parches (opcional)")
            notes = st.text_area("Notas (opcional)", height=68)

        # Photo uploads
        st.markdown("##### 📸 Fotos (opcional — podés agregarlas después)")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            photo_front = st.file_uploader("Frente", type=["jpg", "jpeg", "png"], key="pf")
        with pcol2:
            photo_back = st.file_uploader("Atrás", type=["jpg", "jpeg", "png"], key="pb")
        with pcol3:
            photo_detail = st.file_uploader("Detalle", type=["jpg", "jpeg", "png"], key="pd")

        submitted = st.form_submit_button(
            "💾 Guardar y Siguiente",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not selected_label:
            st.error("Seleccioná un equipo.")
        else:
            team = team_options[selected_label]
            from db import insert_jersey, insert_photo

            jersey_id = insert_jersey(
                conn,
                team_id=team["team_id"],
                season=season,
                variant=variant,
                size=size,
                tier=tier,
                player_name=player_name if player_name else None,
                player_number=player_number if player_number else None,
                patches=patches if patches else None,
                notes=notes if notes else None,
            )

            # Save photos if provided
            for photo_file, photo_type in [
                (photo_front, "front"), (photo_back, "back"), (photo_detail, "detail")
            ]:
                if photo_file is not None:
                    jersey_dir = os.path.join(PHOTOS_DIR, jersey_id)
                    os.makedirs(jersey_dir, exist_ok=True)
                    ext = photo_file.name.split(".")[-1].lower()
                    filename = f"{photo_type}.{ext}"
                    filepath = os.path.join(jersey_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(photo_file.getbuffer())
                    insert_photo(conn, jersey_id, photo_type,
                                f"{jersey_id}/{filename}")

            st.session_state.session_count += 1
            variant_es = {"home": "Local", "away": "Visita",
                         "third": "Reserva", "special": "Especial"}[variant]
            st.session_state.last_saved = (
                f"{jersey_id} — {team['short_name'] or team['name']} "
                f"{variant_es} {season} ({size})"
            )
            st.rerun()

    # Show last saved and session count
    if st.session_state.last_saved:
        st.success(
            f"✅ **{st.session_state.last_saved}**  "
            f"(Camiseta #{st.session_state.session_count} de la sesión)"
        )

    # Quick stats
    total = count_jerseys(conn)
    st.caption(f"📊 Total en base de datos: {total} camisetas")
    conn.close()


def page_inventory():
    """Inventory view with filters and management."""
    st.title("📦 Inventario")

    conn = get_conn()

    # Filters in columns
    fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)
    with fcol1:
        leagues = [r[0] for r in conn.execute(
            "SELECT DISTINCT league FROM teams ORDER BY league"
        ).fetchall()]
        f_league = st.selectbox("Liga", ["Todas"] + leagues)
    with fcol2:
        f_size = st.selectbox("Talla", ["Todas", "S", "M", "L", "XL"])
    with fcol3:
        f_status = st.selectbox("Status", ["Todos", "available", "reserved", "sold"])
    with fcol4:
        f_tier = st.selectbox("Tier", ["Todos", "A", "B", "C"])
    with fcol5:
        f_search = st.text_input("Buscar", placeholder="Equipo, jugador...")

    # Build query
    query = """
        SELECT j.jersey_id, t.short_name as equipo, t.league as liga,
               j.season as temporada, j.variant as tipo, j.size as talla,
               j.player_name as jugador, j.player_number as numero,
               j.patches as parches, j.tier, j.status,
               j.created_at,
               COUNT(p.photo_id) as fotos
        FROM jerseys j
        JOIN teams t ON j.team_id = t.team_id
        LEFT JOIN photos p ON j.jersey_id = p.jersey_id
        WHERE 1=1
    """
    params = []

    if f_league != "Todas":
        query += " AND t.league = ?"
        params.append(f_league)
    if f_size != "Todas":
        query += " AND j.size = ?"
        params.append(f_size)
    if f_status != "Todos":
        query += " AND j.status = ?"
        params.append(f_status)
    if f_tier != "Todos":
        query += " AND j.tier = ?"
        params.append(f_tier)
    if f_search:
        query += " AND (t.short_name LIKE ? OR t.name LIKE ? OR j.player_name LIKE ?)"
        params.extend([f"%{f_search}%"] * 3)

    query += " GROUP BY j.jersey_id ORDER BY j.created_at DESC"

    df = pd.read_sql_query(query, conn, params=params)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Resultados", len(df))
    if not df.empty:
        col2.metric("Con Fotos", int((df["fotos"] > 0).sum()))
        col3.metric("Sin Fotos", int((df["fotos"] == 0).sum()))

    # Variant display names
    variant_map = {"home": "Local", "away": "Visita", "third": "Reserva", "special": "Especial"}
    if not df.empty:
        df["tipo"] = df["tipo"].map(variant_map)

    # Display table
    if df.empty:
        st.info("No hay camisetas que coincidan con los filtros.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "jersey_id": st.column_config.TextColumn("ID", width=80),
                "equipo": st.column_config.TextColumn("Equipo", width=120),
                "liga": st.column_config.TextColumn("Liga", width=130),
                "temporada": st.column_config.TextColumn("Temp.", width=80),
                "tipo": st.column_config.TextColumn("Tipo", width=80),
                "talla": st.column_config.TextColumn("Talla", width=60),
                "jugador": st.column_config.TextColumn("Jugador", width=100),
                "numero": st.column_config.NumberColumn("#", width=40),
                "parches": st.column_config.TextColumn("Parches", width=100),
                "tier": st.column_config.TextColumn("Tier", width=50),
                "status": st.column_config.TextColumn("Status", width=80),
                "fotos": st.column_config.NumberColumn("📸", width=40),
            },
        )

    # Jersey detail expander
    if not df.empty:
        st.markdown("---")
        st.subheader("Detalle de Camiseta")
        jersey_ids = df["jersey_id"].tolist()
        selected_id = st.selectbox("Seleccionar camiseta", jersey_ids)
        if selected_id:
            jersey = conn.execute(
                """SELECT j.*, t.name as team_name, t.league
                   FROM jerseys j JOIN teams t ON j.team_id = t.team_id
                   WHERE j.jersey_id = ?""",
                (selected_id,)
            ).fetchone()
            photos = conn.execute(
                "SELECT * FROM photos WHERE jersey_id = ?", (selected_id,)
            ).fetchall()

            dcol1, dcol2 = st.columns([1, 2])
            with dcol1:
                st.markdown(f"**{jersey['team_name']}** — {jersey['league']}")
                st.markdown(f"Temporada: {jersey['season']}  |  Tipo: {variant_map.get(jersey['variant'], jersey['variant'])}")
                st.markdown(f"Talla: {jersey['size']}  |  Tier: {jersey['tier']}")
                if jersey["player_name"]:
                    st.markdown(f"Jugador: {jersey['player_name']} #{jersey['player_number'] or ''}")
                if jersey["patches"]:
                    st.markdown(f"Parches: {jersey['patches']}")
                st.markdown(f"Status: **{jersey['status']}**")

                # Status change
                new_status = st.selectbox(
                    "Cambiar status",
                    ["available", "reserved", "sold"],
                    index=["available", "reserved", "sold"].index(jersey["status"]),
                    key=f"status_{selected_id}",
                )
                if new_status != jersey["status"]:
                    if st.button(f"Actualizar a {new_status}"):
                        conn.execute(
                            "UPDATE jerseys SET status = ? WHERE jersey_id = ?",
                            (new_status, selected_id),
                        )
                        conn.commit()
                        st.rerun()

            with dcol2:
                if photos:
                    pcols = st.columns(len(photos))
                    for i, photo in enumerate(photos):
                        fpath = os.path.join(PHOTOS_DIR, photo["filename"])
                        if os.path.exists(fpath):
                            pcols[i].image(fpath, caption=photo["photo_type"])
                else:
                    st.info("Sin fotos. Usá la página **Agregar Fotos** para subir.")

    conn.close()


def page_photos():
    """Photo upload page — optimized for mobile."""
    st.title("📸 Agregar Fotos")

    conn = get_conn()

    # Show jerseys needing photos first
    tab1, tab2 = st.tabs(["Sin Fotos", "Todas las Camisetas"])

    with tab1:
        jerseys_no_photos = pd.read_sql_query(
            """SELECT j.jersey_id, t.short_name as equipo, j.season, j.variant, j.size
               FROM jerseys j
               JOIN teams t ON j.team_id = t.team_id
               LEFT JOIN photos p ON j.jersey_id = p.jersey_id
               WHERE j.status = 'available'
               GROUP BY j.jersey_id
               HAVING COUNT(p.photo_id) = 0
               ORDER BY j.created_at DESC""",
            conn,
        )
        if jerseys_no_photos.empty:
            st.success("Todas las camisetas tienen al menos una foto.")
        else:
            st.warning(f"{len(jerseys_no_photos)} camisetas sin fotos")

    with tab2:
        pass  # Handled below

    # Jersey selector
    all_jerseys = conn.execute(
        """SELECT j.jersey_id, t.short_name as equipo, j.season, j.variant, j.size
           FROM jerseys j JOIN teams t ON j.team_id = t.team_id
           WHERE j.status = 'available'
           ORDER BY j.created_at DESC"""
    ).fetchall()

    if not all_jerseys:
        st.info("No hay camisetas registradas.")
        conn.close()
        return

    variant_map = {"home": "Local", "away": "Visita", "third": "Reserva", "special": "Especial"}
    options = {
        f"{j['jersey_id']} — {j['equipo']} {variant_map.get(j['variant'], j['variant'])} {j['season']} ({j['size']})": j['jersey_id']
        for j in all_jerseys
    }

    selected = st.selectbox("Seleccionar camiseta", list(options.keys()))
    jersey_id = options[selected]

    # Show existing photos
    existing = conn.execute(
        "SELECT * FROM photos WHERE jersey_id = ?", (jersey_id,)
    ).fetchall()

    if existing:
        st.markdown("**Fotos actuales:**")
        pcols = st.columns(3)
        for photo in existing:
            fpath = os.path.join(PHOTOS_DIR, photo["filename"])
            col_idx = {"front": 0, "back": 1, "detail": 2}.get(photo["photo_type"], 0)
            if os.path.exists(fpath):
                pcols[col_idx].image(fpath, caption=photo["photo_type"])

    # Upload form
    st.markdown("**Subir fotos:**")
    with st.form(f"photo_upload_{jersey_id}", clear_on_submit=True):
        ucol1, ucol2, ucol3 = st.columns(3)
        with ucol1:
            front = st.file_uploader("Frente", type=["jpg", "jpeg", "png"], key=f"front_{jersey_id}")
        with ucol2:
            back = st.file_uploader("Atrás", type=["jpg", "jpeg", "png"], key=f"back_{jersey_id}")
        with ucol3:
            detail = st.file_uploader("Detalle", type=["jpg", "jpeg", "png"], key=f"detail_{jersey_id}")

        if st.form_submit_button("📸 Subir Fotos", type="primary", use_container_width=True):
            from db import insert_photo
            saved = 0
            for photo_file, photo_type in [(front, "front"), (back, "back"), (detail, "detail")]:
                if photo_file is not None:
                    jersey_dir = os.path.join(PHOTOS_DIR, jersey_id)
                    os.makedirs(jersey_dir, exist_ok=True)
                    ext = photo_file.name.split(".")[-1].lower()
                    filename = f"{photo_type}.{ext}"
                    filepath = os.path.join(jersey_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(photo_file.getbuffer())
                    # Remove old photo of same type if exists
                    conn.execute(
                        "DELETE FROM photos WHERE jersey_id = ? AND photo_type = ?",
                        (jersey_id, photo_type),
                    )
                    insert_photo(conn, jersey_id, photo_type, f"{jersey_id}/{filename}")
                    saved += 1

            if saved > 0:
                st.success(f"✅ {saved} foto(s) guardada(s) para {jersey_id}")
                st.rerun()
            else:
                st.warning("No seleccionaste ninguna foto.")

    conn.close()


def sync_to_website(conn):
    """Generate products.json from database for the website."""
    products_path = os.path.join(BASE_DIR, "..", "content", "products.json")

    # Query available jerseys
    jerseys = conn.execute(
        """SELECT j.jersey_id, j.season, j.variant, j.size, j.price,
                  j.player_name, j.player_number, j.status,
                  t.name as team_name, t.short_name, t.league
           FROM jerseys j
           JOIN teams t ON j.team_id = t.team_id
           WHERE j.status = 'available'
           ORDER BY t.league, t.name, j.size"""
    ).fetchall()

    # Group jerseys by team+season+variant to create website products
    # (website shows one product per team/season/variant with sizes array)
    from collections import defaultdict
    grouped = defaultdict(list)
    for j in jerseys:
        key = (j["team_name"], j["short_name"], j["league"],
               j["season"], j["variant"])
        grouped[key].append(j)

    import json
    products = []
    variant_names = {"home": "Local", "away": "Visita",
                    "third": "Reserva", "special": "Especial"}

    for (team, short, league, season, variant), items in grouped.items():
        sizes = sorted(set(i["size"] for i in items),
                      key=lambda s: ["S", "M", "L", "XL"].index(s))
        stock = len(items)
        price = items[0]["price"] or 200  # default if not set

        # Check for photos of first jersey
        first_id = items[0]["jersey_id"]
        photo = conn.execute(
            "SELECT filename FROM photos WHERE jersey_id = ? AND photo_type = 'front' LIMIT 1",
            (first_id,)
        ).fetchone()
        image = f"/erp/photos/{photo['filename']}" if photo else "/assets/img/products/placeholder.svg"

        display_name = short or team
        variant_es = variant_names.get(variant, variant)
        product_id = f"JRS-{display_name.upper().replace(' ', '')}-{season.replace('/', '')}-{variant[0].upper()}"

        player_info = ""
        for item in items:
            if item["player_name"]:
                player_info = f" — {item['player_name']}"
                break

        products.append({
            "id": product_id,
            "type": "jersey",
            "name": f"{display_name} {variant_es} {season}{player_info}",
            "description": f"Camiseta del {team} temporada {season}.",
            "price": price,
            "image": image,
            "league": league,
            "team": display_name,
            "season": season,
            "sizes": sizes,
            "stock": stock,
            "featured": stock >= 2,
            "tags": [
                league.lower().replace(" ", "-"),
                display_name.lower().replace(" ", "-"),
            ],
        })

    # Read current file for diff
    current = []
    if os.path.exists(products_path):
        with open(products_path, "r", encoding="utf-8") as f:
            current = json.load(f)

    current_count = len([p for p in current if p.get("type") == "jersey"])
    new_count = len(products)

    st.info(f"📊 Productos actuales en sitio: {current_count} jerseys\n\n"
            f"📊 Nuevos desde ERP: {new_count} jerseys")

    # Keep mystery box products from current file (not managed by ERP yet)
    mystery_boxes = [p for p in current if p.get("type") == "mystery-box"]
    final = mystery_boxes + products

    if st.button("✅ Confirmar y escribir products.json"):
        with open(products_path, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        st.success(f"✅ products.json actualizado con {len(final)} productos ({len(mystery_boxes)} mystery boxes + {new_count} jerseys)")


# ═══════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════

if PAGES[page] == "dashboard":
    page_dashboard()
elif PAGES[page] == "register":
    page_register()
elif PAGES[page] == "inventory":
    page_inventory()
elif PAGES[page] == "photos":
    page_photos()
```

**Step 2: Test the app launches**

```bash
cd C:/Users/Diego/el-club/erp
streamlit run app.py --server.port 8502
```

Expected: App opens at http://localhost:8502, shows dashboard with "No hay camisetas registradas" message.

**Step 3: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/app.py
git commit -m "feat(erp): Streamlit app with dashboard, registration, inventory, and photos"
```

---

## Task 5: Launcher Script

**Files:**
- Create: `el-club/erp/ElClub-ERP.bat`

**Step 1: Write launcher**

Create `el-club/erp/ElClub-ERP.bat`:

```bat
@echo off
title El Club ERP
cd /d "%~dp0"

:: Kill any existing Streamlit on port 8502
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8502" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Seed teams if needed
python -c "from seed import seed_teams; seed_teams()" 2>nul

:: Launch Streamlit
start "" "C:\Users\Diego\AppData\Local\Programs\Python\Python311\Scripts\streamlit.exe" run app.py --server.port 8502 --server.address 0.0.0.0 --server.headless true

:: Wait for server
timeout /t 4 /nobreak >nul

:: Open as standalone app window
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8502 --window-size=1400,900

echo.
echo El Club ERP running at http://localhost:8502
echo Para acceso desde celular: http://[tu-ip-local]:8502
echo.
echo Press any key to stop...
pause >nul
```

**Step 2: Commit**

```bash
cd C:/Users/Diego/el-club
git add erp/ElClub-ERP.bat
git commit -m "feat(erp): launcher script (Chrome app mode, port 8502)"
```

---

## Task 6: Smoke Test — Full Registration Flow

**Step 1: Start the app**

```bash
cd C:/Users/Diego/el-club/erp
streamlit run app.py --server.port 8502
```

**Step 2: Test registration**

1. Navigate to "Registrar Camiseta"
2. Search and select "Barcelona" from the dropdown
3. Verify league auto-shows "La Liga" and tier shows "A"
4. Select season "2023/24", variant "Local", size "M"
5. Click "Guardar y Siguiente"
6. Verify success message shows "JRS-001 — Barcelona Local 2023/24 (M)"
7. Verify form clears and counter shows "Camiseta #1 de la sesión"

**Step 3: Test inventory view**

1. Navigate to "Inventario"
2. Verify JRS-001 appears in the table
3. Test filters: select "La Liga" → should show JRS-001
4. Select "Premier League" → should show empty

**Step 4: Test dashboard**

1. Navigate to "Dashboard"
2. Verify metrics show: Total 1, Disponibles 1, Reservadas 0, Vendidas 0
3. Verify size chart shows 1 bar for "M"
4. Verify league chart shows 1 bar for "La Liga"

**Step 5: Register 2 more jerseys and test sync**

1. Register: Real Madrid, Away, 2023/24, L
2. Register: Liverpool, Home, 2023/24, M
3. Navigate to Dashboard
4. Click "Generar products.json"
5. Verify diff shows new products
6. Click confirm
7. Verify `content/products.json` was updated

**Step 6: Final commit**

```bash
cd C:/Users/Diego/el-club
git add -A
git commit -m "feat(erp): El Club ERP Phase 1 complete — inventory management system"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Scaffolding + gitignore | config.toml, .gitignore |
| 2 | DB schema + helpers | schema.sql, db.py |
| 3 | Teams database (~200) | data/teams.json, seed.py |
| 4 | Streamlit app (all pages) | app.py |
| 5 | Launcher script | ElClub-ERP.bat |
| 6 | Smoke test full flow | — |

**Total new files:** 7 (config.toml, schema.sql, db.py, teams.json, seed.py, app.py, ElClub-ERP.bat)
**Estimated build time:** Tasks 1-5 sequential, Task 6 is verification.
