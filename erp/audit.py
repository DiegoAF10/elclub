"""Audit Catalog — Streamlit page.

Spec completo en elclub-catalogo-priv/docs/AUDIT-SYSTEM.md.

3 vistas:
1. Queue — lista paginada con filtros tier/status/categoría, 50/página
2. Audit Detail — vista por "producto madre" agrupando variantes
3. Pending Review — mock preview post-Claude

Features obligatorios:
- Hero selection via click
- Delete foto (soft, reversible)
- Reorder con input numérico
- Flag watermark por foto
- Flag regen con Gemini por foto (checkbox nuevo, pedido Diego)
- Checks globales
- Notas
- Verify/Flag por variante + Verify todas batch
- Next/Prev producto
- Keyboard shortcuts (JS injected)
- Shortcuts box visible (pedido Diego)
"""

import json
import os
import subprocess
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import audit_db
import audit_enrich


# ═══════════════════════════════════════
# Constants
# ═══════════════════════════════════════

PAGE_SIZE = 50
CATEGORIES = ["adult", "women", "kids", "baby", "jacket", "training",
              "polo", "vest", "sweatshirt"]
TIERS = ["T1", "T2", "T3", "T4", "T5"]
STATUSES = ["pending", "verified", "flagged", "skipped", "needs_rework"]
CATEGORY_LABELS = {
    "adult": "👤 Adulto", "women": "♀️ Mujer", "kids": "🧒 Niño",
    "baby": "👶 Bebé", "jacket": "🧥 Chaqueta", "training": "🏋️ Training",
    "polo": "👔 Polo", "vest": "🦺 Vest", "sweatshirt": "🧶 Sweatshirt",
}
TIER_LABELS = {
    "T1": "🟢 T1 · Mundial 2026",
    "T2": "🔵 T2 · Top-5 Europa actual",
    "T3": "🟡 T3 · Ligas importantes",
    "T4": "🟣 T4 · Retros icónicos",
    "T5": "⚫ T5 · Retros otros",
}

SHORTCUTS_HTML = """
<div style="background:#1C1C1C;border:1px solid #4DA8FF;border-radius:8px;padding:12px 16px;font-family:'Space Grotesk',monospace;font-size:12px;color:#F0F0F0;line-height:1.6;">
<b style="color:#4DA8FF;">⌨️ SHORTCUTS</b><br>
<span style="color:#999">Por foto (click primero):</span> <code>1-9</code> foco · <code>X</code> delete · <code>W</code> watermark (→Gemini auto) · <code>G</code> marcar regen manual · <code>Enter</code> set hero · <code>↑↓</code> reorder<br>
<span style="color:#999">Por variante:</span> <code>V</code> verify · <code>F</code> flag<br>
<span style="color:#999">Producto completo:</span> <code>Shift+V</code> verify todas · <code>Shift+F</code> flag todas · <code>S</code> skip · <code>Tab</code> next variante · <code>J/K</code> next/prev producto
</div>
"""

# JavaScript para shortcuts. Dispatchea clicks a buttons por data-audit-action.
KEYBOARD_JS = """
<script>
(function(){
  if (window.__auditShortcutsBound) return;
  window.__auditShortcutsBound = true;
  document.addEventListener('keydown', function(e){
    // No interferir si el user está tipeando en un input/textarea
    const tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return;

    const shift = e.shiftKey;
    const key = e.key;
    let action = null;

    if (shift && key === 'V') action = 'verify-all';
    else if (shift && key === 'F') action = 'flag-all';
    else if (key === 'S' || key === 's') action = 'skip';
    else if (key === 'V' || key === 'v') action = 'verify-current';
    else if (key === 'F' || key === 'f') action = 'flag-current';
    else if (key === 'J' || key === 'j') action = 'next';
    else if (key === 'K' || key === 'k') action = 'prev';

    if (!action) return;
    // Busca el button con data-audit-action dentro del parent streamlit
    const parentDoc = window.parent && window.parent.document;
    if (!parentDoc) return;
    const btn = parentDoc.querySelector('[data-audit-action="' + action + '"]');
    if (btn) {
      btn.click();
      e.preventDefault();
    }
  });
})();
</script>
"""


# ═══════════════════════════════════════
# Init
# ═══════════════════════════════════════

def _ensure_init():
    audit_db.init_audit_schema()
    if "audit_seeded" not in st.session_state:
        conn = audit_db.get_conn()
        count = conn.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
        conn.close()
        if count == 0:
            result = audit_db.seed_audit_queue()
            st.session_state.audit_seed_result = result
        st.session_state.audit_seeded = True


# ═══════════════════════════════════════
# Helpers
# ═══════════════════════════════════════

def _tag_button_js(action):
    """Genera un attribute para que el botón pueda ser invocado por el shortcut."""
    # Streamlit no permite data-* attrs directos. Workaround: usamos el label
    # único y ejecutamos JS para taggearlo por posición. Aquí sólo retornamos
    # el action como sufijo del key.
    return action


def _inject_tag_script(button_keys_actions):
    """JS que tagguea buttons en Streamlit por key → data-audit-action."""
    if not button_keys_actions:
        return
    mappings = []
    for key, action in button_keys_actions.items():
        mappings.append(f"'{key}': '{action}'")
    js = f"""
<script>
(function(){{
  const map = {{ {', '.join(mappings)} }};
  const parentDoc = window.parent && window.parent.document;
  if (!parentDoc) return;
  Object.entries(map).forEach(([key, action]) => {{
    // Streamlit genera buttons con el key en atributos internos.
    // Los identificamos por el texto/label — acá por selector fallback.
    const selector = '[data-testid="stButton"] button[kind="secondary"], [data-testid="stButton"] button[kind="primary"]';
    const buttons = parentDoc.querySelectorAll(selector);
    buttons.forEach(b => {{
      if (b.textContent && b.textContent.includes(key)) {{
        b.setAttribute('data-audit-action', action);
      }}
    }});
  }});
}})();
</script>
"""
    components.html(js, height=0)


def _render_shortcuts_box():
    st.markdown(SHORTCUTS_HTML, unsafe_allow_html=True)


def _render_stats_header(conn):
    stats = audit_db.queue_stats(conn)
    total = stats.get("total", 0) or 0
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total", total)
    c2.metric("Pending", stats.get("pending", 0) or 0)
    c3.metric("Verified", stats.get("verified", 0) or 0)
    c4.metric("Flagged", stats.get("flagged", 0) or 0)
    c5.metric("Skipped", stats.get("skipped", 0) or 0)
    c6.metric("✅ Publicadas", stats.get("final_verified", 0) or 0)


# ═══════════════════════════════════════
# VIEW 1: Queue
# ═══════════════════════════════════════

def render_queue(conn, catalog):
    st.header("📋 Queue de Audit")
    _render_shortcuts_box()
    st.markdown("")

    # Filters
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        tier_filter = st.selectbox(
            "Tier", ["(todos)", "(sin tier)"] + TIERS,
            format_func=lambda t: t if t.startswith("(") else TIER_LABELS.get(t, t),
        )
    with fc2:
        status_filter = st.selectbox(
            "Status", ["(todos)"] + STATUSES,
        )
    with fc3:
        category_filter = st.selectbox(
            "Categoría (madre)", ["(todas)"] + CATEGORIES,
            format_func=lambda c: c if c.startswith("(") else CATEGORY_LABELS.get(c, c),
        )
    with fc4:
        search = st.text_input("Buscar", placeholder="team, family_id…")

    tf = tier_filter if tier_filter not in ("(todos)", "(sin tier)") else None
    sf = status_filter if status_filter != "(todos)" else None
    cf = category_filter if category_filter != "(todas)" else None

    items = audit_db.queue_families(conn, catalog, tf, sf, cf)

    # Tier "(sin tier)": items cuyo tier is NULL
    if tier_filter == "(sin tier)":
        items = [i for i in items if not i.get("tier")]

    if search:
        s = search.lower()
        items = [
            i for i in items
            if s in (i.get("family_id", "").lower())
            or s in (i.get("team", "") or "").lower()
        ]

    st.caption(f"**{len(items)} productos madre** en queue (post-filtros)")

    # Pagination
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    if "queue_page" not in st.session_state:
        st.session_state.queue_page = 1
    page = min(st.session_state.queue_page, total_pages)

    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("← Prev page", disabled=page <= 1, key="queue_prev"):
            st.session_state.queue_page = max(1, page - 1)
            st.rerun()
    with pc2:
        st.markdown(f"<div style='text-align:center'>Página <b>{page}</b> de <b>{total_pages}</b></div>", unsafe_allow_html=True)
    with pc3:
        if st.button("Next page →", disabled=page >= total_pages, key="queue_next"):
            st.session_state.queue_page = min(total_pages, page + 1)
            st.rerun()

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = items[start:end]

    # Render list
    for i, it in enumerate(page_items):
        with st.container(border=True):
            row = st.columns([1, 3, 2, 1, 1, 1])
            hero = it.get("hero")
            with row[0]:
                if hero:
                    st.image(hero, width=80)
            with row[1]:
                tier_badge = TIER_LABELS.get(it.get("tier"), "❓ Sin tier")
                st.markdown(f"**{it['family_id']}**  \n{tier_badge}")
                team = it.get("team") or ""
                season = it.get("season") or ""
                variant = it.get("variant") or ""
                st.caption(f"{team} · {season} · {variant}")
            with row[2]:
                status = it.get("status", "pending")
                emoji = {"pending": "⏳", "verified": "🟢", "flagged": "🔴",
                         "skipped": "⏭️", "needs_rework": "⚠️"}.get(status, "?")
                st.markdown(f"{emoji} **{status}**")
            with row[3]:
                if st.button("Abrir", key=f"open_{it['family_id']}", type="primary"):
                    st.session_state.audit_view = "detail"
                    st.session_state.current_family = it["family_id"]
                    st.rerun()
            with row[4]:
                # Quick tier change (para families sin tier)
                current_tier = it.get("tier") or "(sin)"
                new_tier = st.selectbox(
                    "Tier",
                    ["(sin)"] + TIERS,
                    index=(["(sin)"] + TIERS).index(current_tier) if current_tier in (["(sin)"] + TIERS) else 0,
                    key=f"tier_{it['family_id']}",
                    label_visibility="collapsed",
                )
                if new_tier != current_tier:
                    audit_db.upsert_decision(
                        conn, it["family_id"],
                        tier=None if new_tier == "(sin)" else new_tier,
                    )
                    st.rerun()
            with row[5]:
                if st.button("⏭️", key=f"skip_{it['family_id']}", help="Skip"):
                    audit_db.upsert_decision(
                        conn, it["family_id"],
                        status="skipped",
                        decided_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    st.rerun()


# ═══════════════════════════════════════
# VIEW 2: Audit Detail (producto madre)
# ═══════════════════════════════════════

def render_detail(conn, catalog):
    fid = st.session_state.get("current_family")
    if not fid:
        st.warning("No hay family seleccionada.")
        if st.button("← Volver al queue"):
            st.session_state.audit_view = "queue"
            st.rerun()
        return

    mother_id = audit_db.mother_family_id(fid)
    variants = audit_db.find_related_variants(catalog, mother_id)
    if not variants:
        st.error(f"Family {mother_id} no encontrada en catalog.json")
        return

    # Header
    base = variants.get("adult") or next(iter(variants.values()))
    deci = audit_db.get_decision(conn, mother_id) or {}
    tier = deci.get("tier")

    hc1, hc2, hc3 = st.columns([3, 1, 1])
    with hc1:
        team = base.get("team") or ""
        season = base.get("season") or ""
        variant = base.get("variant") or ""
        st.markdown(f"## {team} {season} — {variant}")
        st.caption(f"`{mother_id}` · {TIER_LABELS.get(tier, 'Sin tier')}")
    with hc2:
        if st.button("← Queue", key="back_queue"):
            st.session_state.audit_view = "queue"
            st.rerun()
    with hc3:
        # Tier change
        tiers = ["(sin)"] + TIERS
        idx = tiers.index(tier) if tier in tiers else 0
        new_tier = st.selectbox("Tier", tiers, index=idx, key="detail_tier")
        if new_tier != (tier or "(sin)"):
            audit_db.upsert_decision(
                conn, mother_id,
                tier=None if new_tier == "(sin)" else new_tier,
            )
            st.rerun()

    _render_shortcuts_box()
    st.markdown("")

    # Variants summary row
    st.markdown("### Variantes del producto madre")
    var_cols = st.columns(len(variants))
    for idx, (cat, fam) in enumerate(variants.items()):
        with var_cols[idx]:
            label = CATEGORY_LABELS.get(cat, cat)
            hero = fam.get("hero_thumbnail")
            if hero:
                st.image(hero, use_container_width=True)
            st.markdown(f"**{label}**")
            st.caption(f"`{fam.get('family_id')}`")
            fam_dec = audit_db.get_decision(conn, fam["family_id"]) or {}
            status_emoji = {"pending": "⏳", "verified": "🟢", "flagged": "🔴",
                            "skipped": "⏭️", "needs_rework": "⚠️"}.get(
                fam_dec.get("status", "pending"), "⏳")
            st.caption(f"{status_emoji} {fam_dec.get('status', 'pending')}")

    st.markdown("---")
    st.markdown("### 🔍 Audit por variante")

    # Expandable section per variant
    for cat, fam in variants.items():
        with st.expander(f"{CATEGORY_LABELS.get(cat, cat)} — `{fam['family_id']}`", expanded=(cat == "adult")):
            _render_variant_form(conn, fam)

    st.markdown("---")

    # Global action bar
    st.markdown("### Acciones globales")
    ac1, ac2, ac3, ac4, ac5 = st.columns(5)
    with ac1:
        if st.button("🟢 VERIFY TODAS (⇧V)", key="verify_all", type="primary", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="verified",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.success("Todas las variantes verificadas.")
            st.rerun()
    with ac2:
        if st.button("🔴 FLAG TODAS (⇧F)", key="flag_all", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="flagged",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.rerun()
    with ac3:
        if st.button("⏭️ SKIP (S)", key="skip_prod", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="skipped",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.rerun()
    with ac4:
        if st.button("← Prev (K)", key="prev_prod", use_container_width=True):
            _jump_product(conn, catalog, direction=-1)
    with ac5:
        if st.button("Next → (J)", key="next_prod", use_container_width=True):
            _jump_product(conn, catalog, direction=1)

    # Inject shortcut bindings
    components.html(KEYBOARD_JS, height=0)
    _inject_tag_script({
        "VERIFY TODAS": "verify-all",
        "FLAG TODAS": "flag-all",
        "SKIP (S)": "skip",
        "Prev (K)": "prev",
        "Next → (J)": "next",
    })


def _jump_product(conn, catalog, direction=1):
    """Next/prev producto madre (solo Tier pending)."""
    items = audit_db.queue_families(conn, catalog)
    items = [i for i in items if i.get("status") == "pending"]
    current = st.session_state.get("current_family")
    if not items:
        return
    ids = [i["family_id"] for i in items]
    current_mother = audit_db.mother_family_id(current) if current else None
    if current_mother in ids:
        idx = ids.index(current_mother)
        new_idx = (idx + direction) % len(ids)
    else:
        new_idx = 0
    st.session_state.current_family = ids[new_idx]
    st.rerun()


def _render_variant_form(conn, fam):
    """Form para auditar UNA variant. Fotos + checks + notes + verify/flag."""
    fid = fam["family_id"]
    gallery = fam.get("gallery") or []
    current_hero = fam.get("hero_thumbnail")

    # Cargar acciones existentes
    saved_actions = {a["original_index"]: a for a in audit_db.get_photo_actions(conn, fid)}

    if not gallery:
        st.warning("Esta variante no tiene galería. Hero único:")
        if current_hero:
            st.image(current_hero, width=240)
        st.info("Las acciones por foto requieren galería. Solo se puede verificar/flaggear la variante.")

    # Decoder UI para cada foto
    if gallery:
        st.caption(f"{len(gallery)} fotos en galería · click para ampliar · set hero vía botón")
        cols_per_row = 4
        for row_start in range(0, len(gallery), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                i = row_start + col_idx
                if i >= len(gallery):
                    break
                with cols[col_idx]:
                    _render_photo_card(conn, fid, i, gallery[i], saved_actions.get(i), current_hero)

    st.markdown("")
    # Checks globales
    st.markdown("##### Checks globales")
    deci = audit_db.get_decision(conn, fid) or {}
    checks = {}
    try:
        checks = json.loads(deci.get("checks_json") or "{}")
    except Exception:
        checks = {}

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        fotos_ok = st.checkbox("✓ Fotos equipo correcto", value=bool(checks.get("fotos_equipo_ok")),
                                key=f"fotos_ok_{fid}")
    with cc2:
        cat_ok = st.checkbox("✓ Categoría correcta", value=bool(checks.get("categoria_ok")),
                              key=f"cat_ok_{fid}")
    with cc3:
        vers_ok = st.checkbox("✓ Versiones OK", value=bool(checks.get("versiones_ok")),
                               key=f"vers_ok_{fid}")

    notes = st.text_input("Notas", value=deci.get("notes", "") or "",
                          key=f"notes_{fid}", placeholder="Observaciones libres…")

    # Variant action buttons
    ba1, ba2 = st.columns(2)
    with ba1:
        if st.button(f"🟢 VERIFY {fid} (V)", key=f"verify_{fid}", type="primary", use_container_width=True):
            _save_variant_decision(conn, fid, "verified", fotos_ok, cat_ok, vers_ok, notes)
            st.success(f"Variante verificada: {fid}")
            st.rerun()
    with ba2:
        if st.button(f"🔴 FLAG {fid} (F)", key=f"flag_{fid}", use_container_width=True):
            _save_variant_decision(conn, fid, "flagged", fotos_ok, cat_ok, vers_ok, notes)
            st.rerun()


def _render_photo_card(conn, fid, index, url, saved_action, current_hero):
    """Una foto con controles: delete, watermark, regen-Gemini, hero, reorder."""
    action = (saved_action or {}).get("action", "keep")
    new_index = (saved_action or {}).get("new_index")
    is_hero = bool((saved_action or {}).get("is_new_hero")) or (url == current_hero)

    # Position visible
    display_pos = new_index if new_index is not None else index + 1
    crown = "👑" if is_hero else f"#{display_pos}"

    # Image
    st.image(url, use_container_width=True)

    # Status badge
    badge_map = {
        "keep": "", "delete": "❌ delete",
        "flag_watermark": "⚠️ watermark",
        "flag_regen": "🎨 regen",
    }
    badge = badge_map.get(action, "")
    st.caption(f"{crown} {badge}")

    # Controls row
    bc = st.columns(4)
    with bc[0]:
        if st.button("👑", key=f"hero_{fid}_{index}", help="Set hero"):
            _set_hero(conn, fid, url, index)
            st.rerun()
    with bc[1]:
        if st.button("❌", key=f"del_{fid}_{index}", help="Delete foto"):
            audit_db.set_photo_action(conn, fid, url, index, action="delete")
            st.rerun()
    with bc[2]:
        if st.button("⚠️", key=f"wm_{fid}_{index}", help="Flag watermark"):
            audit_db.set_photo_action(conn, fid, url, index, action="flag_watermark")
            st.rerun()
    with bc[3]:
        if st.button("🎨", key=f"regen_{fid}_{index}", help="Flag regen manual (calidad mala, Diego la rehace aparte)"):
            audit_db.set_photo_action(conn, fid, url, index, action="flag_regen")
            st.rerun()

    # Reorder input
    new_pos = st.number_input(
        "Pos", min_value=1, max_value=20,
        value=int(display_pos),
        key=f"pos_{fid}_{index}",
        step=1, label_visibility="collapsed",
    )
    if new_pos != display_pos:
        audit_db.set_photo_action(
            conn, fid, url, index,
            action=action if action in ("delete", "flag_watermark", "flag_regen") else "keep",
            new_index=int(new_pos) - 1,
        )
        st.rerun()

    # Reset a keep
    if action in ("delete", "flag_watermark", "flag_regen"):
        if st.button("↺ reset", key=f"reset_{fid}_{index}"):
            audit_db.set_photo_action(conn, fid, url, index, action="keep")
            st.rerun()


def _set_hero(conn, fid, url, index):
    """Marca una foto como hero. Desmarca las demás."""
    # Clear previous hero flags
    conn.execute(
        "UPDATE audit_photo_actions SET is_new_hero = 0 WHERE family_id = ?", (fid,)
    )
    conn.commit()
    # Upsert new
    audit_db.set_photo_action(
        conn, fid, url, index,
        action="keep", is_new_hero=1,
    )


def _save_variant_decision(conn, fid, status, fotos_ok, cat_ok, vers_ok, notes):
    checks = {
        "fotos_equipo_ok": bool(fotos_ok),
        "categoria_ok": bool(cat_ok),
        "versiones_ok": bool(vers_ok),
    }
    audit_db.upsert_decision(
        conn, fid,
        status=status,
        checks_json=json.dumps(checks),
        notes=(notes or "").strip(),
        decided_at=datetime.now().isoformat(timespec="seconds"),
    )


# ═══════════════════════════════════════
# VIEW 3: Pending Review (post-Claude)
# ═══════════════════════════════════════

def render_pending_review(conn, catalog):
    st.header("🤖 Pending Review (post-Claude)")
    st.caption("Items procesados por Claude esperando tu OK final antes de publicar.")

    # Button para correr batch Claude sobre los verified sin procesar
    br1, br2 = st.columns([1, 3])
    with br1:
        if st.button("▶️ Procesar batch con Claude", type="primary",
                     disabled=not audit_enrich.claude_available()):
            _run_claude_batch(conn, catalog)
            st.rerun()
    with br2:
        if not audit_enrich.claude_available():
            st.warning("⚠️ ANTHROPIC_API_KEY no configurada. Seteá en `erp/.env`.")
        else:
            # Count verified sin pending review
            cnt = conn.execute(
                """SELECT COUNT(*) FROM audit_decisions d
                   LEFT JOIN pending_review p ON d.family_id = p.family_id
                   WHERE d.status = 'verified' AND p.family_id IS NULL"""
            ).fetchone()[0]
            st.info(f"{cnt} verified esperando enriquecimiento Claude")

    pending = audit_db.list_pending_reviews(conn)
    st.caption(f"{len(pending)} items en pending review.")

    if not pending:
        st.info("Vacío. Verificá items en el queue y procesa con Claude.")
        return

    for item in pending:
        fid = item["family_id"]
        fam = audit_db.get_family(catalog, fid)
        if not fam:
            continue

        with st.expander(f"{fid}  ·  {TIER_LABELS.get(item.get('tier'), 'Sin tier')}",
                          expanded=False):
            _render_pending_preview(conn, fam, item)


def _run_claude_batch(conn, catalog):
    """Procesa todos los verified sin pending review."""
    rows = conn.execute(
        """SELECT d.family_id, d.checks_json, d.notes FROM audit_decisions d
           LEFT JOIN pending_review p ON d.family_id = p.family_id
           WHERE d.status = 'verified' AND p.family_id IS NULL
           LIMIT 50"""
    ).fetchall()

    if not rows:
        st.info("Nada para procesar.")
        return

    families_ctx = []
    for r in rows:
        fam = audit_db.get_family(catalog, r["family_id"])
        if not fam:
            continue
        checks = {}
        try:
            checks = json.loads(r["checks_json"] or "{}")
        except Exception:
            pass
        families_ctx.append({
            "family": fam,
            "checks": checks,
            "notes": r["notes"] or "",
        })

    with st.spinner(f"Procesando {len(families_ctx)} items con Claude…"):
        results = audit_enrich.claude_enrich_batch(families_ctx, concurrency=5)

    ok_count = 0
    err_count = 0
    for fid, result in results.items():
        if result.get("ok"):
            # Aplicamos actions a gallery para preview
            fam = audit_db.get_family(catalog, fid)
            new_gallery = _apply_photo_actions_to_gallery(conn, fam)
            audit_db.save_pending_review(
                conn, fid,
                claude_json=json.dumps(result["data"], ensure_ascii=False),
                gallery_json=json.dumps(new_gallery, ensure_ascii=False),
                new_hero=new_gallery[0] if new_gallery else fam.get("hero_thumbnail"),
            )
            ok_count += 1
        else:
            err_count += 1

    st.success(f"Claude procesó {ok_count} ok · {err_count} errores.")


def _apply_photo_actions_to_gallery(conn, fam, run_gemini_watermark=False):
    """Aplica las actions del audit_photo_actions a la gallery[] original.
    Retorna la nueva lista de URLs.

    Si run_gemini_watermark=True:
      - Para cada foto con action=flag_watermark sin processed_url:
        - Descarga original de R2
        - Pasa por Gemini (remove watermark)
        - Sube processed a R2 con suffix -cleaned.jpg
        - Actualiza processed_url en audit_photo_actions
    Si run_gemini_watermark=False (preview mode): usa processed_url existente o url original.

    flag_regen NO dispara Gemini — es solo un marcador manual. Diego rehace
    esas fotos aparte y reemplaza el asset en R2 manualmente cuando tenga.
    """
    import requests
    original = fam.get("gallery") or []
    actions_by_idx = {
        a["original_index"]: a for a in audit_db.get_photo_actions(conn, fam["family_id"])
    }

    # Build list of (new_index, url) skipping deletes
    kept = []
    hero_url = None
    for i, url in enumerate(original):
        a = actions_by_idx.get(i, {})
        action = a.get("action", "keep")
        if action == "delete":
            continue

        # Gemini watermark processing (solo al publicar, no al generar preview)
        processed = a.get("processed_url")
        if run_gemini_watermark and action == "flag_watermark" and not processed:
            processed = _process_watermark_with_gemini(conn, fam["family_id"], url, i)

        final_url = processed or url

        # Si está marcada hero, la ponemos primero
        if a.get("is_new_hero"):
            hero_url = final_url

        new_idx = a.get("new_index")
        kept.append((new_idx if new_idx is not None else i, final_url))

    # Sort por new_index (mismos índices preservan orden estable)
    kept.sort(key=lambda x: (x[0] if x[0] is not None else 999))
    new_gallery = [u for _, u in kept]

    # Si hay hero explícito, ponerlo primero
    if hero_url and hero_url in new_gallery:
        new_gallery.remove(hero_url)
        new_gallery.insert(0, hero_url)

    return new_gallery


def _process_watermark_with_gemini(conn, family_id, original_url, original_index):
    """Descarga foto, pasa por Gemini para remover watermark, sube processed a R2.
    Retorna el processed_url o None si falló.
    """
    import requests

    if not audit_enrich.gemini_available():
        return None

    # Strip query string (e.g. ?v=2026-04-22) para download raw
    clean_url = original_url.split("?")[0]

    try:
        resp = requests.get(clean_url, timeout=30)
        if resp.status_code != 200:
            return None
        image_bytes = resp.content
    except Exception:
        return None

    result = audit_enrich.gemini_regen_image(image_bytes, mime_type="image/jpeg",
                                              prompt_variant="watermark")
    if not result.get("ok"):
        return None

    # Key en R2: families/<fid>/<NN>-cleaned.jpg
    ord_str = f"{original_index + 1:02d}"
    key = f"families/{family_id}/{ord_str}-cleaned.jpg"
    upload = audit_enrich.upload_image_to_r2(result["image_bytes"], key,
                                              content_type=result.get("mime_type", "image/jpeg"))
    if not upload.get("ok"):
        return None

    new_url = upload["public_url"]
    # Save processed_url en la audit_photo_actions row
    audit_db.set_photo_action(
        conn, family_id, original_url, original_index,
        action="flag_watermark", processed_url=new_url,
    )
    return new_url


def _render_pending_preview(conn, fam, item):
    fid = fam["family_id"]
    try:
        claude_data = json.loads(item.get("claude_enriched_json") or "{}")
    except Exception:
        claude_data = {}
    try:
        new_gallery = json.loads(item.get("new_gallery_json") or "[]")
    except Exception:
        new_gallery = []

    # Surface de fotos flaggeadas pendientes (watermark va auto al publicar,
    # regen queda como tarea manual de Diego)
    actions = audit_db.get_photo_actions(conn, fid)
    wm_pending = [a for a in actions if a.get("action") == "flag_watermark" and not a.get("processed_url")]
    regen_pending = [a for a in actions if a.get("action") == "flag_regen"]
    if wm_pending:
        st.info(f"💧 {len(wm_pending)} fotos con watermark → Gemini las procesa al click PUBLISH")
    if regen_pending:
        st.warning(
            f"🎨 {len(regen_pending)} fotos flaggeadas para REGEN MANUAL. "
            f"Diego: rehacelas aparte y sube a R2 con mismo path antes de publicar."
        )

    pc1, pc2 = st.columns([2, 3])
    with pc1:
        st.markdown("##### 📷 Gallery preview (post-audit)")
        if new_gallery:
            st.image(new_gallery[0], caption="Hero (01)", use_container_width=True)
            if len(new_gallery) > 1:
                thumb_cols = st.columns(min(4, len(new_gallery) - 1))
                for idx, url in enumerate(new_gallery[1:5]):
                    with thumb_cols[idx % len(thumb_cols)]:
                        st.image(url, caption=f"#{idx+2}", use_container_width=True)
    with pc2:
        st.markdown("##### 🤖 Claude suggested")
        st.markdown(f"**Title:** {claude_data.get('title', '—')}")
        st.markdown(f"**Description:** {claude_data.get('description', '—')}")
        hist = claude_data.get("historia") or fam.get("historia") or "—"
        st.markdown(f"**Historia:**  \n> {hist}")
        st.markdown(f"**SKU:** `{claude_data.get('sku', '—')}`")
        kw = claude_data.get("keywords", [])
        st.markdown(f"**Keywords:** {', '.join(kw) if kw else '—'}")
        val = claude_data.get("validation_issues", [])
        if val:
            st.warning(f"Validation: {', '.join(val)}")

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button(f"✅ PUBLISH", key=f"publish_{fid}", type="primary", use_container_width=True):
            _publish_family(conn, fam, claude_data, new_gallery)
            st.rerun()
    with ac2:
        if st.button(f"❌ REJECT", key=f"reject_{fid}", use_container_width=True):
            st.session_state[f"rejecting_{fid}"] = True
            st.rerun()
    with ac3:
        if st.button(f"🔄 Re-run Claude", key=f"rerun_{fid}", use_container_width=True):
            # Regenera para este family
            deci = audit_db.get_decision(conn, fid) or {}
            checks = json.loads(deci.get("checks_json") or "{}")
            r = audit_enrich.claude_enrich(fam, checks, deci.get("notes", ""))
            if r.get("ok"):
                audit_db.save_pending_review(
                    conn, fid,
                    claude_json=json.dumps(r["data"], ensure_ascii=False),
                    gallery_json=item.get("new_gallery_json"),
                    new_hero=item.get("new_hero_url"),
                )
            else:
                st.error(r.get("error", "Error"))
            st.rerun()

    # Rejection notes
    if st.session_state.get(f"rejecting_{fid}"):
        reason = st.text_area(f"Razón del reject de {fid}", key=f"reason_{fid}")
        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("Confirmar reject", key=f"confirm_reject_{fid}"):
                audit_db.mark_rejected(conn, fid, reason)
                st.session_state[f"rejecting_{fid}"] = False
                st.rerun()
        with rc2:
            if st.button("Cancelar", key=f"cancel_reject_{fid}"):
                st.session_state[f"rejecting_{fid}"] = False
                st.rerun()


# ═══════════════════════════════════════
# COMPONENT 4: Publish flow
# ═══════════════════════════════════════

def _publish_family(conn, fam, claude_data, new_gallery):
    """Aplica cambios al catalog.json + git commit + push."""
    catalog_path = audit_db.CATALOG_PATH
    if not os.path.exists(catalog_path):
        st.error(f"catalog.json no encontrado en {catalog_path}")
        return

    # Cargar catalog fresh
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Find and update family
    target = None
    for f_ in catalog:
        if f_.get("family_id") == fam["family_id"]:
            target = f_
            break
    if not target:
        st.error(f"Family {fam['family_id']} no encontrada en catalog.json")
        return

    # Apply Claude enrichment
    if claude_data.get("title"):
        target["title"] = claude_data["title"]
    if claude_data.get("description"):
        target["description"] = claude_data["description"]
    if claude_data.get("historia") and not target.get("historia"):
        target["historia"] = claude_data["historia"]
    if claude_data.get("sku"):
        target["sku"] = claude_data["sku"]
    if claude_data.get("keywords"):
        target["keywords"] = claude_data["keywords"]

    # Re-compute gallery ACTIVANDO Gemini para watermarks (solo al publicar).
    # En el preview se usa la gallery cacheada; aquí refrescamos con procesamiento real.
    new_gallery = _apply_photo_actions_to_gallery(conn, fam, run_gemini_watermark=True)

    # Apply gallery + hero
    if new_gallery:
        target["gallery"] = new_gallery
        target["hero_thumbnail"] = new_gallery[0]

    # Save catalog
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Mark approved
    audit_db.mark_approved(conn, fam["family_id"])

    # Git commit + push
    repo_dir = os.path.dirname(os.path.dirname(catalog_path))
    try:
        subprocess.run(
            ["git", "add", "data/catalog.json"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", f"audit: {fam['family_id']} verified by Diego"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        push_result = subprocess.run(
            ["git", "push"],
            cwd=repo_dir, capture_output=True, timeout=60,
        )
        if push_result.returncode == 0:
            st.success(f"✅ {fam['family_id']} publicada. Auto-deploy en vault.elclub.club.")
        else:
            st.warning(
                f"⚠️ {fam['family_id']} guardada local y marcada verified, pero git push falló: "
                f"{push_result.stderr.decode('utf-8', errors='ignore')[:200]}"
            )
    except Exception as e:
        st.warning(f"⚠️ git push falló: {e}. catalog.json actualizado localmente.")


# ═══════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════

def render_page(conn):
    _ensure_init()

    # Sub-navigation
    view = st.session_state.get("audit_view", "queue")

    # Header con tabs + stats
    _render_stats_header(conn)
    st.markdown("")

    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        if st.button("📋 Queue", use_container_width=True, type="primary" if view == "queue" else "secondary"):
            st.session_state.audit_view = "queue"
            st.rerun()
    with tc2:
        if st.button("🔍 Audit Detail", use_container_width=True, type="primary" if view == "detail" else "secondary",
                     disabled=not st.session_state.get("current_family")):
            st.session_state.audit_view = "detail"
            st.rerun()
    with tc3:
        if st.button("🤖 Pending Review", use_container_width=True, type="primary" if view == "pending" else "secondary"):
            st.session_state.audit_view = "pending"
            st.rerun()

    # Status messages from seed
    seed_result = st.session_state.get("audit_seed_result")
    if seed_result:
        st.info(
            f"**Audit queue inicializada:** {seed_result.get('seeded', 0)} families "
            f"(skipped sin foto: {seed_result.get('skipped_no_hero', 0)} · "
            f"skipped category=other: {seed_result.get('skipped_excluded_other', 0)})"
        )
        del st.session_state.audit_seed_result

    # Diagnostics
    with st.sidebar:
        st.markdown("---")
        st.markdown("**🔍 Audit Status**")
        st.caption(f"Claude: {'✅' if audit_enrich.claude_available() else '❌ set ANTHROPIC_API_KEY'}")
        st.caption(f"Gemini: {'✅' if audit_enrich.gemini_available() else '❌ set GEMINI_API_KEY'}")
        st.markdown("---")

    st.markdown("")

    catalog = audit_db.load_catalog()
    if not catalog:
        st.error(f"catalog.json no encontrado en {audit_db.CATALOG_PATH}")
        st.info("El audit tool necesita el catalog.json del repo privado `elclub-catalogo-priv`. "
                "Verificá que el directorio existe.")
        return

    if view == "queue":
        render_queue(conn, catalog)
    elif view == "detail":
        render_detail(conn, catalog)
    elif view == "pending":
        render_pending_review(conn, catalog)
    else:
        render_queue(conn, catalog)
