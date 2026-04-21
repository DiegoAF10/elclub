"""El Club ERP — Inventory Management System."""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import shutil
import subprocess
from datetime import datetime, date
from collections import defaultdict
from db import (
    get_conn, init_db, migrate_db, count_jerseys, count_teams,
    insert_jersey, insert_photo, next_jersey_id, next_photo_seq,
    update_jersey, get_team_by_id,
    PHOTOS_DIR, BASE_DIR,
)
import vault_orders

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
    "📬 Ordenes Vault": "vault_orders",
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

POSITIONS = ["POR", "DEF", "MED", "DEL"]
POSITION_LABELS = {
    "POR": "Portero", "DEF": "Defensa",
    "MED": "Mediocampista", "DEL": "Delantero",
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


def _swap_photo_order(conn, jersey_id, photo_a, photo_b):
    """Swap the order of two photos: update DB photo_type and rename files on disk."""
    pos_a = photo_a["photo_type"]
    pos_b = photo_b["photo_type"]
    file_a = os.path.join(PHOTOS_DIR, photo_a["filename"])
    file_b = os.path.join(PHOTOS_DIR, photo_b["filename"])

    # Rename files via temp to avoid collision
    # photo_a: JRS-001/JRS-001-01.png → gets position 02
    # photo_b: JRS-001/JRS-001-02.png → gets position 01
    ext_a = photo_a["filename"].rsplit(".", 1)[-1]
    ext_b = photo_b["filename"].rsplit(".", 1)[-1]
    new_name_a = f"{jersey_id}/{jersey_id}-{int(pos_b):02d}.{ext_a}"
    new_name_b = f"{jersey_id}/{jersey_id}-{int(pos_a):02d}.{ext_b}"
    new_path_a = os.path.join(PHOTOS_DIR, new_name_a)
    new_path_b = os.path.join(PHOTOS_DIR, new_name_b)

    # Use temp file to avoid overwrite
    tmp_path = file_a + ".tmp"
    if os.path.exists(file_a):
        os.rename(file_a, tmp_path)
    if os.path.exists(file_b):
        os.rename(file_b, new_path_b)
    if os.path.exists(tmp_path):
        os.rename(tmp_path, new_path_a)

    # Update DB
    conn.execute(
        "UPDATE photos SET photo_type = ?, filename = ? WHERE photo_id = ?",
        (pos_b, new_name_a, photo_a["photo_id"]),
    )
    conn.execute(
        "UPDATE photos SET photo_type = ?, filename = ? WHERE photo_id = ?",
        (pos_a, new_name_b, photo_b["photo_id"]),
    )
    conn.commit()


def render_photo_grid_with_reorder(conn, jersey_id, key_prefix=""):
    """Display photos in a grid with reorder arrows and delete buttons.

    Used in both page_photos() and page_inventory().
    Returns the list of photos (for caller to check if empty).
    """
    photos = conn.execute(
        "SELECT * FROM photos WHERE jersey_id = ? ORDER BY photo_type",
        (jersey_id,),
    ).fetchall()

    if not photos:
        st.caption("Sin fotos todavía.")
        return photos

    total = len(photos)
    st.markdown(f"**Fotos ({total}/7):**")
    cols_count = min(total, 4)
    pcols = st.columns(cols_count)

    for i, photo in enumerate(photos):
        col = pcols[i % cols_count]
        fpath = os.path.join(PHOTOS_DIR, photo["filename"])

        if not os.path.exists(fpath):
            col.warning(f"{photo['filename']}: no encontrado")
            continue

        # Badge: HERO for first photo, position number for rest
        badge = "⭐ HERO" if i == 0 else f"#{i + 1}"
        col.image(fpath, caption=f"{badge} — {jersey_id}-{photo['photo_type']}")

        # Arrow buttons row
        btn_cols = col.columns(3)

        # Move up (not for first photo)
        if i > 0:
            if btn_cols[0].button("⬆️", key=f"{key_prefix}up_{photo['photo_id']}"):
                _swap_photo_order(conn, jersey_id, photos[i - 1], photos[i])
                st.rerun()
        else:
            btn_cols[0].write("")

        # Delete
        if btn_cols[1].button("🗑️", key=f"{key_prefix}del_{photo['photo_id']}"):
            if os.path.exists(fpath):
                os.remove(fpath)
            conn.execute("DELETE FROM photos WHERE photo_id = ?", (photo["photo_id"],))
            conn.commit()
            st.rerun()

        # Move down (not for last photo)
        if i < total - 1:
            if btn_cols[2].button("⬇️", key=f"{key_prefix}down_{photo['photo_id']}"):
                _swap_photo_order(conn, jersey_id, photos[i], photos[i + 1])
                st.rerun()
        else:
            btn_cols[2].write("")

    return photos


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

    published = conn.execute(
        "SELECT COUNT(*) FROM jerseys WHERE status = 'available' AND published = 1"
    ).fetchone()[0]

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Camisetas", total)
    c2.metric("Disponibles", available)
    c3.metric("Publicadas", published)
    c4.metric("Reservadas", reserved)
    c5.metric("Vendidas", sold)

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


def _do_sync(conn):
    """Generate products.json from published jerseys and copy photos. Returns (products_count, photos_count)."""
    products_path = os.path.join(BASE_DIR, "..", "content", "products.json")
    website_photos_dir = os.path.join(BASE_DIR, "..", "assets", "img", "products")
    os.makedirs(website_photos_dir, exist_ok=True)

    jerseys = conn.execute(
        """SELECT j.jersey_id, j.season, j.variant, j.size, j.price,
                  j.player_name, j.player_number, j.patches, j.tier, j.notes,
                  j.story, j.position,
                  t.name as team_name, t.short_name, t.league, t.country
           FROM jerseys j
           JOIN teams t ON j.team_id = t.team_id
           WHERE j.status = 'available' AND j.published = 1
           ORDER BY t.league, t.name, j.size"""
    ).fetchall()

    # Group by team+season+variant → one website product with sizes array
    grouped = defaultdict(list)
    for j in jerseys:
        key = (j["team_name"], j["short_name"], j["league"],
               j["season"], j["variant"], j["country"])
        grouped[key].append(j)

    copied_photos = 0
    products = []
    for (team, short, league, season, variant, country), items in grouped.items():
        sizes = sorted(
            set(i["size"] for i in items),
            key=lambda s: SIZE_ORDER.get(s, 99),
        )
        stock = len(items)
        price = items[0]["price"] or 200

        # Collect ALL photos from all jerseys in this group, ordered by photo_type
        all_photos = []
        for item in items:
            photos = conn.execute(
                "SELECT filename FROM photos WHERE jersey_id = ? ORDER BY photo_type",
                (item["jersey_id"],),
            ).fetchall()
            for p in photos:
                all_photos.append(p["filename"])

        # Copy photos to website assets and build image paths
        images = []
        for photo_filename in all_photos:
            src = os.path.join(PHOTOS_DIR, photo_filename)
            if os.path.exists(src):
                dest_name = photo_filename.replace("/", "-")
                dest = os.path.join(website_photos_dir, dest_name)
                shutil.copy2(src, dest)
                images.append(f"/assets/img/products/{dest_name}")
                copied_photos += 1

        image = images[0] if images else "/assets/img/products/placeholder.svg"

        display = short or team
        variant_es = VARIANT_MAP.get(variant, variant)
        safe_name = display.upper().replace(" ", "").replace(".", "")[:12]
        product_id = f"JRS-{safe_name}-{season.replace('/', '')}-{variant[0].upper()}"

        # Player info (from first jersey that has it)
        player_name = None
        player_number = None
        patches = None
        story = None
        position = None
        for item in items:
            if item["player_name"] and not player_name:
                player_name = item["player_name"]
                player_number = item["player_number"]
            if item["patches"] and not patches:
                patches = item["patches"]
            if item["story"] and not story:
                story = item["story"]
            if item["position"] and not position:
                position = item["position"]

        name_suffix = f" — {player_name}" if player_name else ""

        # Use story if available, otherwise auto-generate
        if story:
            description = story
        else:
            desc_parts = [f"Camiseta del {team} temporada {season}. Versión {variant_es.lower()}."]
            if player_name:
                num = f" (#{player_number})" if player_number else ""
                desc_parts.append(f"Con nombre y número de {player_name}{num}.")
            if patches:
                desc_parts.append(f"Parches de {patches}.")
            description = " ".join(desc_parts)

        products.append({
            "id": product_id,
            "type": "jersey",
            "name": f"{display} {variant_es} {season}{name_suffix}",
            "description": description,
            "price": price,
            "image": image,
            "images": images if images else ["/assets/img/products/placeholder.svg"],
            "league": league,
            "team": display,
            "season": season,
            "variant": variant_es,
            "player_name": player_name,
            "player_number": player_number,
            "patches": patches,
            "position": position,
            "country": country,
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
    final = mystery_boxes + products

    with open(products_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    # Auto-deploy to GitHub Pages
    repo_dir = os.path.join(BASE_DIR, "..")
    try:
        subprocess.run(
            ["git", "add", "content/products.json", "assets/img/products/"],
            cwd=repo_dir, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Sync: {len(products)} jerseys publicados"],
            cwd=repo_dir, capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
    except Exception:
        pass  # silently continue — products.json is updated locally either way

    return len(products), copied_photos


def _sync_to_website(conn):
    """Dashboard sync with preview UI — shows diff before writing."""
    products_path = os.path.join(BASE_DIR, "..", "content", "products.json")

    # Current state
    current = []
    if os.path.exists(products_path):
        with open(products_path, "r", encoding="utf-8") as f:
            current = json.load(f)
    mystery_boxes = [p for p in current if p.get("type") == "mystery-box"]
    current_jerseys = [p for p in current if p.get("type") == "jersey"]

    # Count what will be synced
    published_count = conn.execute(
        "SELECT COUNT(*) FROM jerseys WHERE status = 'available' AND published = 1"
    ).fetchone()[0]

    st.info(
        f"**Actual en sitio:** {len(current_jerseys)} jerseys + {len(mystery_boxes)} mystery boxes\n\n"
        f"**Publicadas en ERP:** {published_count} jerseys → se sincronizarán"
    )

    if st.button("✅ Confirmar y escribir", key="confirm_sync"):
        products_count, photos_count = _do_sync(conn)
        st.success(
            f"✅ `products.json` actualizado — {products_count} jerseys + {len(mystery_boxes)} mystery boxes, "
            f"{photos_count} fotos copiadas"
        )


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
    if "last_saved_ids" not in st.session_state:
        st.session_state.last_saved_ids = []

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

        # Row 2: Size(s) + Quantity + Tier
        r2c1, r2c2, r2c3 = st.columns([3, 1, 1])
        with r2c1:
            sizes_selected = st.multiselect(
                "Talla(s) *  — seleccioná todas las que tengas",
                SIZES,
                default=[],
                placeholder="S, M, L, XL...",
            )
        with r2c2:
            quantity = st.number_input(
                "Cantidad (por talla)", min_value=1, max_value=20, value=1, step=1,
            )
        with r2c3:
            tier = st.selectbox("Tier", ["A", "B", "C"], index=default_tier_idx)

        # Row 3: Player + Number + Position
        r3c1, r3c2, r3c3 = st.columns(3)
        with r3c1:
            player_name = st.text_input("Jugador (opcional)")
        with r3c2:
            player_number = st.number_input(
                "Número (opcional)", min_value=0, max_value=99, value=None, step=1,
            )
        with r3c3:
            pos_options = ["—"] + POSITIONS
            position_sel = st.selectbox(
                "Posición (opcional)",
                pos_options,
                format_func=lambda p: POSITION_LABELS.get(p, "Sin posición"),
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
        elif not sizes_selected:
            st.error("⚠️ Seleccioná al menos una talla.")
        else:
            team = team_options[selected_label]
            variant_key = VARIANT_REVERSE[variant_es]
            display = team.get("short_name") or team["name"]

            created_ids = []
            for sz in sorted(sizes_selected, key=lambda s: SIZE_ORDER.get(s, 99)):
                for _q in range(quantity):
                    jersey_id = insert_jersey(
                        conn,
                        team_id=team["team_id"],
                        season=season,
                        variant=variant_key,
                        size=sz,
                        tier=tier,
                        player_name=player_name.strip() if player_name else None,
                        player_number=int(player_number) if player_number else None,
                        patches=patches.strip() if patches else None,
                        notes=notes.strip() if notes else None,
                        position=position_sel if position_sel != "—" else None,
                    )
                    created_ids.append((jersey_id, sz))

                    # Save photos only to first jersey (avoid duplicates)
                    if photos_uploaded and len(created_ids) == 1:
                        for idx, pfile in enumerate(photos_uploaded[:7]):
                            seq = idx + 1
                            rel_path = save_photo_file(jersey_id, pfile, seq)
                            insert_photo(conn, jersey_id, f"{seq:02d}", rel_path)

            st.session_state.reg_count += len(created_ids)
            sizes_str = ", ".join(sz for _, sz in created_ids)
            ids_str = ", ".join(jid for jid, _ in created_ids)
            st.session_state.last_saved = (
                f"{ids_str} — {display} {variant_es} {season} ({sizes_str})"
            )
            st.session_state.last_saved_ids = [jid for jid, _ in created_ids]
            st.rerun()

    # Confirmation + publish button
    if st.session_state.last_saved:
        st.success(
            f"✅ **{st.session_state.last_saved}**  ·  "
            f"Camiseta #{st.session_state.reg_count} de la sesión"
        )

        saved_ids = st.session_state.get("last_saved_ids", [])
        if saved_ids:
            # Check if already published
            already = conn.execute(
                f"SELECT COUNT(*) FROM jerseys WHERE jersey_id IN ({','.join('?' * len(saved_ids))}) AND published = 1",
                saved_ids,
            ).fetchone()[0]
            if already == len(saved_ids):
                st.caption("🟢 Ya publicada en la página")
            elif st.button("🚀 Publicar en la página", key="publish_after_save"):
                conn.execute(
                    f"UPDATE jerseys SET published = 1 WHERE jersey_id IN ({','.join('?' * len(saved_ids))})",
                    saved_ids,
                )
                conn.commit()
                _do_sync(conn)
                st.success("✅ Publicada — products.json actualizado")
                st.rerun()

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
               j.published,
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
        df["web"] = df["published"].apply(lambda x: "🟢" if x == 1 else "⚫")

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
                "web": st.column_config.TextColumn("🌐", width=40),
                "fotos": st.column_config.NumberColumn("📸", width=40),
                "published": None,  # hide raw value
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
                    # Auto-unpublish when sold or reserved
                    if new_status in ("sold", "reserved") and jersey["published"]:
                        conn.execute(
                            "UPDATE jerseys SET status = ?, published = 0 WHERE jersey_id = ?",
                            (new_status, selected_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE jerseys SET status = ? WHERE jersey_id = ?",
                            (new_status, selected_id),
                        )
                    conn.commit()
                    if new_status in ("sold", "reserved") and jersey["published"]:
                        _do_sync(conn)
                    st.rerun()

            # Publish / Unpublish
            if jersey["published"]:
                st.caption("🟢 Publicada en la página")
                if st.button("📴 Despublicar", key=f"unpub_{selected_id}"):
                    update_jersey(conn, selected_id, published=0)
                    _do_sync(conn)
                    st.rerun()
            else:
                if jersey["status"] == "available":
                    if st.button("🚀 Publicar", key=f"pub_{selected_id}"):
                        update_jersey(conn, selected_id, published=1)
                        _do_sync(conn)
                        st.rerun()
                else:
                    st.caption("⚫ No disponible para publicar")

            # Edit jersey
            with st.expander("✏️ Editar camiseta"):
                # Load teams for dropdown
                edit_teams_raw = conn.execute(
                    "SELECT team_id, name, short_name, league, tier FROM teams ORDER BY league, name"
                ).fetchall()
                edit_team_options = {}
                edit_current_idx = 0
                for idx_t, t in enumerate(edit_teams_raw):
                    label = f"{t['league']} — {t['name']}"
                    edit_team_options[label] = dict(t)
                    if t["team_id"] == jersey["team_id"]:
                        edit_current_idx = idx_t

                edit_team_labels = list(edit_team_options.keys())

                with st.form(f"edit_form_{selected_id}"):
                    edit_team = st.selectbox(
                        "Equipo", edit_team_labels,
                        index=edit_current_idx,
                        key=f"eteam_{selected_id}",
                    )

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        edit_season = st.selectbox(
                            "Temporada", SEASONS,
                            index=SEASONS.index(jersey["season"]) if jersey["season"] in SEASONS else 0,
                            key=f"eseason_{selected_id}",
                        )
                    with ec2:
                        variant_vals = list(VARIANT_MAP.values())
                        cur_variant_es = VARIANT_MAP.get(jersey["variant"], "Local")
                        edit_variant = st.radio(
                            "Tipo", variant_vals, horizontal=True,
                            index=variant_vals.index(cur_variant_es),
                            key=f"evariant_{selected_id}",
                        )

                    ec3, ec4 = st.columns(2)
                    with ec3:
                        edit_size = st.radio(
                            "Talla", SIZES, horizontal=True,
                            index=SIZES.index(jersey["size"]) if jersey["size"] in SIZES else 0,
                            key=f"esize_{selected_id}",
                        )
                    with ec4:
                        edit_tier = st.selectbox(
                            "Tier", ["A", "B", "C"],
                            index=["A", "B", "C"].index(jersey["tier"]),
                            key=f"etier_{selected_id}",
                        )

                    ec5, ec6 = st.columns(2)
                    with ec5:
                        edit_player = st.text_input(
                            "Jugador", value=jersey["player_name"] or "",
                            key=f"eplayer_{selected_id}",
                        )
                    with ec6:
                        edit_number = st.number_input(
                            "Número", min_value=0, max_value=99,
                            value=jersey["player_number"] if jersey["player_number"] else 0,
                            key=f"enum_{selected_id}",
                        )

                    ec7, ec8 = st.columns(2)
                    with ec7:
                        edit_patches = st.text_input(
                            "Parches", value=jersey["patches"] or "",
                            key=f"epatches_{selected_id}",
                        )
                    with ec8:
                        pos_options = ["—"] + POSITIONS
                        cur_pos = jersey["position"] if jersey["position"] in POSITIONS else "—"
                        edit_position = st.selectbox(
                            "Posición",
                            pos_options,
                            index=pos_options.index(cur_pos),
                            format_func=lambda p: POSITION_LABELS.get(p, "Sin posición"),
                            key=f"epos_{selected_id}",
                        )
                    edit_story = st.text_area(
                        "Historia (se muestra en la página)",
                        value=jersey["story"] or "",
                        key=f"estory_{selected_id}", height=100,
                        placeholder="La historia detrás de esta camiseta...",
                    )
                    edit_notes = st.text_area(
                        "Notas internas",
                        value=jersey["notes"] or "",
                        key=f"enotes_{selected_id}", height=68,
                    )

                    if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                        edit_team_data = edit_team_options[edit_team]
                        update_jersey(
                            conn, selected_id,
                            team_id=edit_team_data["team_id"],
                            season=edit_season,
                            variant=VARIANT_REVERSE[edit_variant],
                            size=edit_size,
                            tier=edit_tier,
                            player_name=edit_player.strip() or None,
                            player_number=int(edit_number) if edit_number else None,
                            patches=edit_patches.strip() or None,
                            position=edit_position if edit_position != "—" else None,
                            story=edit_story.strip() or None,
                            notes=edit_notes.strip() or None,
                        )
                        st.success(f"✅ {selected_id} actualizado")
                        st.rerun()

            # Add units (same or different size)
            with st.expander("➕ Agregar unidades"):
                # Show current stock per size for this design
                size_counts = conn.execute(
                    """SELECT size, COUNT(*) as cnt FROM jerseys
                       WHERE team_id = ? AND season = ? AND variant = ? AND status = 'available'
                       GROUP BY size ORDER BY size""",
                    (jersey["team_id"], jersey["season"], jersey["variant"]),
                ).fetchall()
                if size_counts:
                    stock_str = " · ".join(f"{r['size']}: {r['cnt']}" for r in size_counts)
                    st.caption(f"Stock actual: {stock_str}")

                ac1, ac2 = st.columns([3, 1])
                with ac1:
                    new_sizes = st.multiselect(
                        "Talla(s)",
                        SIZES,
                        key=f"newsize_{selected_id}",
                    )
                with ac2:
                    add_qty = st.number_input(
                        "Cantidad",
                        min_value=1, max_value=20, value=1, step=1,
                        key=f"addqty_{selected_id}",
                    )
                if st.button("Crear", key=f"addsize_{selected_id}", type="primary"):
                    if new_sizes:
                        created = []
                        for sz in sorted(new_sizes, key=lambda s: SIZE_ORDER.get(s, 99)):
                            for _q in range(add_qty):
                                new_id = insert_jersey(
                                    conn,
                                    team_id=jersey["team_id"],
                                    season=jersey["season"],
                                    variant=jersey["variant"],
                                    size=sz,
                                    tier=jersey["tier"],
                                    player_name=jersey["player_name"],
                                    player_number=jersey["player_number"],
                                    patches=jersey["patches"],
                                    notes=jersey["notes"],
                                    position=jersey["position"],
                                )
                                if jersey["story"]:
                                    update_jersey(conn, new_id, story=jersey["story"])
                                created.append(f"{new_id} ({sz})")
                        st.success(f"✅ Creadas: {', '.join(created)}")
                        st.rerun()
                    else:
                        st.warning("Seleccioná al menos una talla.")

            # Delete jersey
            with st.expander("⚠️ Eliminar camiseta"):
                st.warning("Esta acción no se puede deshacer.")
                if st.button("🗑️ Eliminar", key=f"del_{selected_id}", type="secondary"):
                    # Delete photos from disk
                    jersey_photo_dir = os.path.join(PHOTOS_DIR, selected_id)
                    if os.path.exists(jersey_photo_dir):
                        shutil.rmtree(jersey_photo_dir)
                    conn.execute("DELETE FROM photos WHERE jersey_id = ?", (selected_id,))
                    conn.execute("DELETE FROM jerseys WHERE jersey_id = ?", (selected_id,))
                    conn.commit()
                    st.rerun()

        with dc2:
            inv_photos = render_photo_grid_with_reorder(conn, selected_id, key_prefix="inv_")
            if not inv_photos:
                st.info("📸 Sin fotos todavía.")

            # Inline photo upload
            total_photos = len(inv_photos) if inv_photos else 0
            remaining = 7 - total_photos
            if remaining > 0:
                with st.form(f"inv_photo_upload_{selected_id}", clear_on_submit=True):
                    new_photos = st.file_uploader(
                        f"Subir fotos ({remaining} disponibles)",
                        type=["jpg", "jpeg", "png"],
                        accept_multiple_files=True,
                        key=f"inv_up_{selected_id}",
                    )
                    if st.form_submit_button("📸 Subir", type="primary", use_container_width=True):
                        if new_photos:
                            start_seq = next_photo_seq(conn, selected_id)
                            saved = 0
                            for idx, pfile in enumerate(new_photos[:remaining]):
                                seq = start_seq + idx
                                rel_path = save_photo_file(selected_id, pfile, seq)
                                insert_photo(conn, selected_id, f"{seq:02d}", rel_path)
                                saved += 1
                            st.success(f"✅ {saved} foto(s) guardada(s)")
                            st.rerun()

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

    # Current photos with reorder
    existing = render_photo_grid_with_reorder(conn, jersey_id, key_prefix="photos_")
    total_photos = len(existing)
    remaining = 7 - total_photos

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
elif page_key == "vault_orders":
    _vault_conn = get_conn()
    try:
        vault_orders.render_page(_vault_conn)
    finally:
        _vault_conn.close()
