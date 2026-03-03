"""El Club ERP — Inventory Management System."""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime, date
from collections import defaultdict
from db import (
    get_conn, init_db, migrate_db, count_jerseys, count_teams,
    insert_jersey, insert_photo, next_jersey_id, next_photo_seq,
    PHOTOS_DIR, BASE_DIR,
)

# ═══════════════════════════════════════
# INIT
# ═══════════════════════════════════════

init_db()
_mig_conn = get_conn()
migrate_db(_mig_conn)
_mig_conn.close()

# Seed teams if empty
_conn_check = get_conn()
if count_teams(_conn_check) == 0:
    from seed import seed_teams
    seed_teams()
_conn_check.close()

# ═══════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════

st.set_page_config(
    page_title="El Club ERP",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Midnight Stadium CSS
st.markdown("""
<style>
    .stApp { font-family: 'Space Grotesk', sans-serif; }
    div[data-testid="stMetric"] {
        background-color: #1C1C1C;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label { color: #999999; font-size: 13px; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #F0F0F0; }
    .success-card {
        background: #1C1C1C;
        border: 1px solid #22C55E;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════

PAGES = {
    "📊 Dashboard": "dashboard",
    "📝 Registrar Camiseta": "register",
    "📦 Inventario": "inventory",
    "📸 Agregar Fotos": "photos",
}

# Logo in sidebar
logo_path = os.path.join(BASE_DIR, "..", "assets", "img", "brand", "logo.png")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)
else:
    st.sidebar.markdown("## ⚽ El Club ERP")

st.sidebar.markdown("---")
page = st.sidebar.radio("", list(PAGES.keys()), label_visibility="collapsed")

# World Cup countdown
wc_date = date(2026, 6, 11)
days_to_wc = (wc_date - date.today()).days
st.sidebar.markdown("---")
st.sidebar.markdown("**⚽ World Cup 2026**")
if days_to_wc > 0:
    st.sidebar.markdown(f"### {days_to_wc} días")
else:
    st.sidebar.markdown("### 🏆 EN CURSO")

# Quick stats in sidebar
_conn_sb = get_conn()
_total = count_jerseys(_conn_sb)
_avail = count_jerseys(_conn_sb, "available")
_conn_sb.close()
st.sidebar.markdown("---")
st.sidebar.caption(f"📦 {_total} camisetas ({_avail} disponibles)")


# ═══════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════

VARIANT_MAP = {
    "home": "Local",
    "away": "Visita",
    "third": "Reserva",
    "special": "Especial",
}

VARIANT_REVERSE = {v: k for k, v in VARIANT_MAP.items()}

SEASONS = [
    "2025/26", "2024/25", "2023/24", "2022/23", "2021/22",
    "2020/21", "2019/20", "2018/19", "2017/18", "2016/17",
    "2015/16", "2014/15", "2013/14", "2012/13", "2011/12",
    "2010/11", "2009/10", "2008/09", "2007/08", "2006/07",
    "2005/06", "Retro (pre-2005)",
]

SIZES = ["S", "M", "L", "XL"]
SIZE_ORDER = {s: i for i, s in enumerate(SIZES)}

PLOTLY_LAYOUT = dict(
    plot_bgcolor="#0D0D0D",
    paper_bgcolor="#0D0D0D",
    font_color="#F0F0F0",
    showlegend=False,
    margin=dict(l=20, r=20, t=30, b=20),
)

ICE_BLUE = "#4DA8FF"


def save_photo_file(jersey_id, photo_file, seq_num):
    """Save an uploaded photo to disk as SKU-NN and return the relative filename."""
    jersey_dir = os.path.join(PHOTOS_DIR, jersey_id)
    os.makedirs(jersey_dir, exist_ok=True)
    ext = photo_file.name.rsplit(".", 1)[-1].lower()
    filename = f"{jersey_id}-{seq_num:02d}.{ext}"
    filepath = os.path.join(jersey_dir, filename)
    with open(filepath, "wb") as f:
        f.write(photo_file.getbuffer())
    return f"{jersey_id}/{filename}"


# ═══════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════

def page_dashboard():
    st.title("⚽ El Club ERP")

    conn = get_conn()
    total = count_jerseys(conn)
    available = count_jerseys(conn, "available")
    reserved = count_jerseys(conn, "reserved")
    sold = count_jerseys(conn, "sold")

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Camisetas", total)
    c2.metric("Disponibles", available)
    c3.metric("Reservadas", reserved)
    c4.metric("Vendidas", sold)

    if total == 0:
        st.info("📝 No hay camisetas registradas. Andá a **Registrar Camiseta** para empezar el inventario.")
        conn.close()
        return

    # Charts row
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
            fig = px.bar(
                df_size, x="size", y="count",
                color_discrete_sequence=[ICE_BLUE],
                labels={"size": "Talla", "count": "Cantidad"},
            )
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_traces(text=df_size["count"], textposition="outside")
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
            fig = px.bar(
                df_league, x="count", y="league", orientation="h",
                color_discrete_sequence=[ICE_BLUE],
                labels={"league": "Liga", "count": "Cantidad"},
            )
            fig.update_layout(**PLOTLY_LAYOUT, yaxis=dict(autorange="reversed"))
            fig.update_traces(text=df_league["count"], textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    # Tier distribution
    col_tier, col_photo = st.columns(2)

    with col_tier:
        st.subheader("Por Tier")
        df_tier = pd.read_sql_query(
            """SELECT tier, COUNT(*) as count FROM jerseys
               WHERE status = 'available' GROUP BY tier ORDER BY tier""",
            conn,
        )
        if not df_tier.empty:
            colors = {"A": "#4DA8FF", "B": "#999999", "C": "#666666"}
            fig = px.pie(
                df_tier, values="count", names="tier",
                color="tier",
                color_discrete_map=colors,
            )
            fig.update_layout(
                plot_bgcolor="#0D0D0D", paper_bgcolor="#0D0D0D",
                font_color="#F0F0F0",
                margin=dict(l=20, r=20, t=30, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_photo:
        st.subheader("Cobertura de Fotos")
        photo_stats = conn.execute(
            """SELECT
                COUNT(DISTINCT j.jersey_id) as total,
                COUNT(DISTINCT CASE WHEN p.photo_id IS NOT NULL THEN j.jersey_id END) as with_photos
               FROM jerseys j LEFT JOIN photos p ON j.jersey_id = p.jersey_id
               WHERE j.status = 'available'"""
        ).fetchone()
        wp = photo_stats["with_photos"]
        ta = photo_stats["total"]
        pct = (wp / ta * 100) if ta > 0 else 0
        st.progress(pct / 100, text=f"{wp} de {ta} camisetas con fotos ({pct:.0f}%)")

        # Breakdown
        full_coverage = conn.execute(
            """SELECT COUNT(*) FROM (
                SELECT j.jersey_id, COUNT(p.photo_id) as cnt
                FROM jerseys j JOIN photos p ON j.jersey_id = p.jersey_id
                WHERE j.status = 'available'
                GROUP BY j.jersey_id HAVING cnt >= 2
            )"""
        ).fetchone()[0]
        st.caption(f"📸 {full_coverage} con 2+ fotos")

    # Sync button
    st.markdown("---")
    st.subheader("🔄 Sync al Sitio")
    st.caption("Genera products.json desde la base de datos para actualizar la tienda web.")

    if st.button("Generar products.json", type="primary"):
        _sync_to_website(conn)

    conn.close()


def _sync_to_website(conn):
    """Generate products.json from database."""
    products_path = os.path.join(BASE_DIR, "..", "content", "products.json")

    jerseys = conn.execute(
        """SELECT j.jersey_id, j.season, j.variant, j.size, j.price,
                  j.player_name, j.player_number,
                  t.name as team_name, t.short_name, t.league
           FROM jerseys j
           JOIN teams t ON j.team_id = t.team_id
           WHERE j.status = 'available'
           ORDER BY t.league, t.name, j.size"""
    ).fetchall()

    # Group by team+season+variant → one website product with sizes array
    grouped = defaultdict(list)
    for j in jerseys:
        key = (j["team_name"], j["short_name"], j["league"],
               j["season"], j["variant"])
        grouped[key].append(j)

    products = []
    for (team, short, league, season, variant), items in grouped.items():
        sizes = sorted(
            set(i["size"] for i in items),
            key=lambda s: SIZE_ORDER.get(s, 99),
        )
        stock = len(items)
        price = items[0]["price"] or 200

        # Photo
        first_id = items[0]["jersey_id"]
        photo = conn.execute(
            "SELECT filename FROM photos WHERE jersey_id = ? ORDER BY photo_type LIMIT 1",
            (first_id,),
        ).fetchone()
        image = f"/erp/photos/{photo['filename']}" if photo else "/assets/img/products/placeholder.svg"

        display = short or team
        variant_es = VARIANT_MAP.get(variant, variant)
        safe_name = display.upper().replace(" ", "").replace(".", "")[:12]
        product_id = f"JRS-{safe_name}-{season.replace('/', '')}-{variant[0].upper()}"

        # Player info
        player = ""
        for item in items:
            if item["player_name"]:
                player = f" — {item['player_name']}"
                break

        products.append({
            "id": product_id,
            "type": "jersey",
            "name": f"{display} {variant_es} {season}{player}",
            "description": f"Camiseta del {team} temporada {season}.",
            "price": price,
            "image": image,
            "league": league,
            "team": display,
            "season": season,
            "sizes": sizes,
            "stock": stock,
            "featured": stock >= 2,
            "tags": [
                league.lower().replace(" ", "-"),
                display.lower().replace(" ", "-"),
            ],
        })

    # Keep mystery boxes from current file
    current = []
    if os.path.exists(products_path):
        with open(products_path, "r", encoding="utf-8") as f:
            current = json.load(f)

    mystery_boxes = [p for p in current if p.get("type") == "mystery-box"]
    current_jerseys = [p for p in current if p.get("type") == "jersey"]
    final = mystery_boxes + products

    st.info(
        f"**Actual en sitio:** {len(current_jerseys)} jerseys + {len(mystery_boxes)} mystery boxes\n\n"
        f"**Nuevo desde ERP:** {len(products)} jerseys + {len(mystery_boxes)} mystery boxes (sin cambio)"
    )

    if st.button("✅ Confirmar y escribir", key="confirm_sync"):
        with open(products_path, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        st.success(f"✅ `products.json` actualizado — {len(final)} productos totales")


# ═══════════════════════════════════════
# PAGE: REGISTER
# ═══════════════════════════════════════

def page_register():
    st.title("📝 Registrar Camiseta")

    conn = get_conn()

    # Show next correlative ID
    next_id = next_jersey_id(conn)
    st.info(f"🏷️ **Próximo correlativo:** {next_id}")

    # Load teams for dropdown
    teams_raw = conn.execute(
        "SELECT team_id, name, short_name, league, tier FROM teams ORDER BY league, name"
    ).fetchall()

    # Build searchable options: "Liga — Equipo"
    team_options = {}
    for t in teams_raw:
        label = f"{t['league']} — {t['name']}"
        team_options[label] = dict(t)

    team_labels = list(team_options.keys())

    # Session state
    if "reg_count" not in st.session_state:
        st.session_state.reg_count = 0
    if "last_saved" not in st.session_state:
        st.session_state.last_saved = None

    # The form
    with st.form("jersey_form", clear_on_submit=True):
        # Team
        selected_label = st.selectbox(
            "Equipo *",
            team_labels,
            index=None,
            placeholder="Buscá un equipo...",
        )

        # Auto-fill info
        default_tier_idx = 1  # B
        if selected_label:
            team = team_options[selected_label]
            st.caption(f"**Liga:** {team['league']}  ·  **Tier default:** {team['tier']}")
            default_tier_idx = ["A", "B", "C"].index(team["tier"])

        # Row 1: Season + Variant
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            season = st.selectbox("Temporada *", SEASONS)
        with r1c2:
            variant_es = st.radio(
                "Tipo *", list(VARIANT_MAP.values()), horizontal=True,
            )

        # Row 2: Size + Tier
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            size = st.radio("Talla *", SIZES, horizontal=True)
        with r2c2:
            tier = st.selectbox("Tier", ["A", "B", "C"], index=default_tier_idx)

        # Row 3: Player + Number
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            player_name = st.text_input("Jugador (opcional)")
        with r3c2:
            player_number = st.number_input(
                "Número (opcional)", min_value=0, max_value=99, value=None, step=1,
            )

        # Row 4: Patches + Notes
        r4c1, r4c2 = st.columns(2)
        with r4c1:
            patches = st.text_input("Parches (opcional)")
        with r4c2:
            notes = st.text_area("Notas (opcional)", height=68)

        # Photos
        st.markdown("##### 📸 Fotos (opcional — máximo 7)")
        photos_uploaded = st.file_uploader(
            "Subí las fotos de la camiseta",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="photos",
        )
        if photos_uploaded and len(photos_uploaded) > 7:
            st.warning("⚠️ Máximo 7 fotos. Solo se guardarán las primeras 7.")

        submitted = st.form_submit_button(
            "💾 Guardar y Siguiente",
            type="primary",
            use_container_width=True,
        )

    # Process submission
    if submitted:
        if not selected_label:
            st.error("⚠️ Seleccioná un equipo.")
        else:
            team = team_options[selected_label]
            variant_key = VARIANT_REVERSE[variant_es]

            jersey_id = insert_jersey(
                conn,
                team_id=team["team_id"],
                season=season,
                variant=variant_key,
                size=size,
                tier=tier,
                player_name=player_name.strip() if player_name else None,
                player_number=int(player_number) if player_number else None,
                patches=patches.strip() if patches else None,
                notes=notes.strip() if notes else None,
            )

            # Save photos (sequential: 01, 02, 03...)
            if photos_uploaded:
                for idx, pfile in enumerate(photos_uploaded[:7]):
                    seq = idx + 1
                    rel_path = save_photo_file(jersey_id, pfile, seq)
                    insert_photo(conn, jersey_id, f"{seq:02d}", rel_path)

            st.session_state.reg_count += 1
            display = team.get("short_name") or team["name"]
            st.session_state.last_saved = (
                f"{jersey_id} — {display} {variant_es} {season} ({size})"
            )
            st.rerun()

    # Confirmation
    if st.session_state.last_saved:
        st.success(
            f"✅ **{st.session_state.last_saved}**  ·  "
            f"Camiseta #{st.session_state.reg_count} de la sesión"
        )

    # Quick stats
    total = count_jerseys(conn)
    st.caption(f"📊 Total en base de datos: **{total}** camisetas")
    conn.close()


# ═══════════════════════════════════════
# PAGE: INVENTORY
# ═══════════════════════════════════════

def page_inventory():
    st.title("📦 Inventario")

    conn = get_conn()

    # Filters
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        leagues = [r[0] for r in conn.execute(
            "SELECT DISTINCT league FROM teams ORDER BY league"
        ).fetchall()]
        f_league = st.selectbox("Liga", ["Todas"] + leagues)
    with fc2:
        f_size = st.selectbox("Talla", ["Todas"] + SIZES)
    with fc3:
        f_status = st.selectbox("Status", ["Todos", "available", "reserved", "sold"])
    with fc4:
        f_tier = st.selectbox("Tier", ["Todos", "A", "B", "C"])
    with fc5:
        f_search = st.text_input("Buscar", placeholder="Equipo, jugador...")

    # Query
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

    # Metrics
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Resultados", len(df))
    if not df.empty:
        mc2.metric("Con Fotos", int((df["fotos"] > 0).sum()))
        mc3.metric("Sin Fotos", int((df["fotos"] == 0).sum()))
        df["tipo"] = df["tipo"].map(VARIANT_MAP)

    # Table
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
                "talla": st.column_config.TextColumn("Talla", width=55),
                "jugador": st.column_config.TextColumn("Jugador", width=100),
                "numero": st.column_config.NumberColumn("#", width=40),
                "parches": st.column_config.TextColumn("Parches", width=100),
                "tier": st.column_config.TextColumn("Tier", width=50),
                "status": st.column_config.TextColumn("Status", width=80),
                "fotos": st.column_config.NumberColumn("📸", width=40),
                "created_at": None,  # hide
            },
        )

    # Detail section
    if not df.empty:
        st.markdown("---")
        st.subheader("Detalle de Camiseta")

        jersey_ids = df["jersey_id"].tolist()
        display_labels = [
            f"{row['jersey_id']} — {row['equipo']} {row['tipo']} {row['temporada']} ({row['talla']})"
            for _, row in df.iterrows()
        ]
        selected_idx = st.selectbox("Seleccionar", range(len(display_labels)),
                                     format_func=lambda i: display_labels[i])
        selected_id = jersey_ids[selected_idx]

        jersey = conn.execute(
            """SELECT j.*, t.name as team_name, t.league
               FROM jerseys j JOIN teams t ON j.team_id = t.team_id
               WHERE j.jersey_id = ?""",
            (selected_id,),
        ).fetchone()

        photos = conn.execute(
            "SELECT * FROM photos WHERE jersey_id = ? ORDER BY photo_type",
            (selected_id,),
        ).fetchall()

        dc1, dc2 = st.columns([1, 2])

        with dc1:
            st.markdown(f"**{jersey['team_name']}** — {jersey['league']}")
            st.markdown(
                f"Temporada: {jersey['season']}  ·  "
                f"Tipo: {VARIANT_MAP.get(jersey['variant'], jersey['variant'])}"
            )
            st.markdown(f"Talla: **{jersey['size']}**  ·  Tier: **{jersey['tier']}**")
            if jersey["player_name"]:
                num = f" #{jersey['player_number']}" if jersey["player_number"] else ""
                st.markdown(f"Jugador: {jersey['player_name']}{num}")
            if jersey["patches"]:
                st.markdown(f"Parches: {jersey['patches']}")
            if jersey["notes"]:
                st.markdown(f"Notas: _{jersey['notes']}_")

            st.markdown(f"Status: **{jersey['status']}**")

            # Status change
            new_status = st.selectbox(
                "Cambiar status",
                ["available", "reserved", "sold"],
                index=["available", "reserved", "sold"].index(jersey["status"]),
                key=f"st_{selected_id}",
            )
            if new_status != jersey["status"]:
                if st.button(f"Actualizar a {new_status}", key=f"btn_{selected_id}"):
                    conn.execute(
                        "UPDATE jerseys SET status = ? WHERE jersey_id = ?",
                        (new_status, selected_id),
                    )
                    conn.commit()
                    st.rerun()

            # Delete jersey
            with st.expander("⚠️ Eliminar camiseta"):
                st.warning("Esta acción no se puede deshacer.")
                if st.button("🗑️ Eliminar", key=f"del_{selected_id}", type="secondary"):
                    # Delete photos from disk
                    jersey_photo_dir = os.path.join(PHOTOS_DIR, selected_id)
                    if os.path.exists(jersey_photo_dir):
                        import shutil
                        shutil.rmtree(jersey_photo_dir)
                    conn.execute("DELETE FROM photos WHERE jersey_id = ?", (selected_id,))
                    conn.execute("DELETE FROM jerseys WHERE jersey_id = ?", (selected_id,))
                    conn.commit()
                    st.rerun()

        with dc2:
            if photos:
                cols_count = min(len(photos), 4)
                pcols = st.columns(cols_count)
                for i, photo in enumerate(photos):
                    fpath = os.path.join(PHOTOS_DIR, photo["filename"])
                    if os.path.exists(fpath):
                        pcols[i % cols_count].image(fpath, caption=f"Foto {photo['photo_type']}")
            else:
                st.info("📸 Sin fotos. Usá **Agregar Fotos** para subir.")

    conn.close()


# ═══════════════════════════════════════
# PAGE: PHOTOS
# ═══════════════════════════════════════

def page_photos():
    st.title("📸 Agregar Fotos")
    st.caption("Optimizado para celular — abrí esta página desde el browser de tu cel.")

    conn = get_conn()

    # Jerseys without complete photos first
    jerseys_no_photos = pd.read_sql_query(
        """SELECT j.jersey_id, t.short_name as equipo, j.season, j.variant, j.size,
                  COUNT(p.photo_id) as fotos
           FROM jerseys j
           JOIN teams t ON j.team_id = t.team_id
           LEFT JOIN photos p ON j.jersey_id = p.jersey_id
           WHERE j.status = 'available'
           GROUP BY j.jersey_id
           HAVING fotos < 2
           ORDER BY fotos ASC, j.created_at DESC""",
        conn,
    )

    if jerseys_no_photos.empty:
        st.success("✅ Todas las camisetas disponibles tienen al menos 2 fotos.")
    else:
        st.warning(f"📷 {len(jerseys_no_photos)} camisetas necesitan fotos")

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

    options = {}
    for j in all_jerseys:
        v = VARIANT_MAP.get(j["variant"], j["variant"])
        label = f"{j['jersey_id']} — {j['equipo']} {v} {j['season']} ({j['size']})"
        options[label] = j["jersey_id"]

    selected = st.selectbox("Seleccionar camiseta", list(options.keys()))
    jersey_id = options[selected]

    # Current photos
    existing = conn.execute(
        "SELECT * FROM photos WHERE jersey_id = ? ORDER BY photo_type",
        (jersey_id,),
    ).fetchall()

    total_photos = len(existing)
    remaining = 7 - total_photos

    if existing:
        st.markdown(f"**Fotos actuales ({total_photos}/7):**")
        cols_count = min(total_photos, 4)
        pcols = st.columns(cols_count)
        for i, photo in enumerate(existing):
            fpath = os.path.join(PHOTOS_DIR, photo["filename"])
            col = pcols[i % cols_count]
            if os.path.exists(fpath):
                col.image(fpath, caption=f"{jersey_id}-{photo['photo_type']}")
                if col.button("🗑️", key=f"del_photo_{photo['photo_id']}"):
                    # Delete from disk and DB
                    if os.path.exists(fpath):
                        os.remove(fpath)
                    conn.execute(
                        "DELETE FROM photos WHERE photo_id = ?",
                        (photo["photo_id"],),
                    )
                    conn.commit()
                    st.rerun()
            else:
                col.warning(f"{photo['filename']}: no encontrado")
    else:
        st.caption("Sin fotos todavía.")

    # Upload form
    if remaining > 0:
        st.markdown("---")
        st.markdown(f"**Subir fotos nuevas ({remaining} disponibles):**")

        with st.form(f"photo_upload_{jersey_id}", clear_on_submit=True):
            new_photos = st.file_uploader(
                "Seleccioná las fotos",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"up_{jersey_id}",
            )
            if new_photos and len(new_photos) > remaining:
                st.warning(f"⚠️ Solo hay espacio para {remaining} fotos más.")

            if st.form_submit_button("📸 Subir Fotos", type="primary", use_container_width=True):
                if new_photos:
                    start_seq = next_photo_seq(conn, jersey_id)
                    saved = 0
                    for idx, pfile in enumerate(new_photos[:remaining]):
                        seq = start_seq + idx
                        rel_path = save_photo_file(jersey_id, pfile, seq)
                        insert_photo(conn, jersey_id, f"{seq:02d}", rel_path)
                        saved += 1
                    st.success(f"✅ {saved} foto(s) guardada(s) para {jersey_id}")
                    st.rerun()
                else:
                    st.warning("No seleccionaste ninguna foto.")
    else:
        st.info("📸 Esta camiseta ya tiene 7 fotos (máximo).")

    conn.close()


# ═══════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════

page_key = PAGES[page]

if page_key == "dashboard":
    page_dashboard()
elif page_key == "register":
    page_register()
elif page_key == "inventory":
    page_inventory()
elif page_key == "photos":
    page_photos()
