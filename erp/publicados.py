"""Publicados — admin page para SKUs publicados en el vault live.

Permite a Diego:
  - Ver lista de families con `published=true` (visibles en vault.elclub.club)
  - Ver families "ocultas" (published=false pero con final_verified=1 = Diego
    alguna vez los aprobó, ahora despublicadas)
  - Editar fields top-level: title, description, historia, featured, keywords
  - Editar por modelo: price, sizes, variant_title
  - Ocultar (flip published=true → false) o re-publicar
  - Commit + push al repo para aplicar cambios en el vault live

No modifica audit_decisions — esta vista es read-only sobre el audit state.
Sólo muta catalog.json + git.
"""

import json
import os
import subprocess
from datetime import datetime

import streamlit as st

import audit_db
import audit_enrich


def render_page(conn):
    st.header("🚀 SKUs Publicados")

    catalog = audit_db.load_catalog()

    # Families publicadas vs ocultas
    # Published: published === true → visibles en vault live
    # Hidden (ex-publicadas): published === false Y tienen ≥1 SKU con final_verified=1
    #                         (fueron publicadas alguna vez, Diego las ocultó)
    pub_fams = [f for f in catalog if f.get("published") is True]

    # Build set of canonical family_ids que tienen algún SKU final_verified=1
    sku_idx = audit_db.build_sku_index(catalog)
    rows = conn.execute(
        "SELECT family_id FROM audit_decisions WHERE final_verified = 1"
    ).fetchall()
    ever_verified_canonicals = set()
    for r in rows:
        sku = r["family_id"]
        resolved = sku_idx.get(sku)
        if resolved:
            ever_verified_canonicals.add(resolved[0]["family_id"])
        else:
            ever_verified_canonicals.add(sku)

    hidden_fams = [
        f for f in catalog
        if f.get("published") is False and f["family_id"] in ever_verified_canonicals
    ]

    # Header stats
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Publicadas (live)", len(pub_fams))
    c2.metric("👁️‍🗨️ Ocultas (ex-publicadas)", len(hidden_fams))
    c3.metric("📦 Total catalog", len(catalog))

    # Toggle vista
    st.markdown("---")
    view = st.radio(
        "Vista",
        ["✅ Publicadas", "👁️‍🗨️ Ocultas", "🔀 Ambas"],
        horizontal=True,
        key="pub_view",
        label_visibility="collapsed",
    )

    items = []
    if view == "✅ Publicadas":
        items = [(f, "published") for f in pub_fams]
    elif view == "👁️‍🗨️ Ocultas":
        items = [(f, "hidden") for f in hidden_fams]
    else:
        items = [(f, "published") for f in pub_fams] + [(f, "hidden") for f in hidden_fams]

    st.caption(f"{len(items)} families en vista")

    # Search
    search = st.text_input("Buscar", placeholder="family_id, team, season…",
                            key="pub_search", label_visibility="collapsed")
    if search:
        s = search.lower()
        items = [
            (f, st_)
            for f, st_ in items
            if s in f.get("family_id", "").lower()
            or s in (f.get("team") or "").lower()
            or s in (f.get("season") or "").lower()
        ]

    # Detail view si hay family seleccionada
    current_fid = st.session_state.get("pub_current_fid")
    if current_fid:
        _render_detail(conn, current_fid, catalog)
        return

    # List view
    if not items:
        st.info("Nada para mostrar. Publicá SKUs desde Audit Catalog → Pending Review → ✅ PUBLISH.")
        return

    # Render grid (2 cols para density)
    for i, (fam, status) in enumerate(items):
        with st.container(border=True):
            cols = st.columns([1, 3, 2, 1, 1])
            hero = fam.get("hero_thumbnail")
            with cols[0]:
                if hero:
                    st.image(hero, width=100)
            with cols[1]:
                title = fam.get("title") or fam.get("family_id")
                st.markdown(f"**{title}**")
                team = fam.get("team") or ""
                season = fam.get("season") or ""
                variant_label = fam.get("variant_label") or fam.get("variant") or ""
                st.caption(f"`{fam['family_id']}` · {team} · {season} · {variant_label}")
                n_modelos = len(fam.get("modelos") or [])
                st.caption(f"📐 {n_modelos} modelos · {'⭐ featured' if fam.get('featured') else ''}")
            with cols[2]:
                if status == "published":
                    st.markdown("🟢 **Publicada**")
                else:
                    st.markdown("👁️‍🗨️ **Oculta**")
                live_url = f"https://vault.elclub.club/producto?id={fam['family_id']}"
                st.link_button("🔗 Ver live", live_url)
            with cols[3]:
                if st.button("✏️ Editar", key=f"pub_edit_{fam['family_id']}", type="primary"):
                    st.session_state["pub_current_fid"] = fam["family_id"]
                    st.rerun()
            with cols[4]:
                if status == "published":
                    if st.button("👁 Ocultar", key=f"pub_hide_{fam['family_id']}"):
                        _flip_published(fam["family_id"], False, motivo="Ocultado desde panel Publicados")
                        st.session_state["pub_toast"] = f"🙈 {fam['family_id']} ocultado. Recordá push para reflejar en live."
                        st.rerun()
                else:
                    if st.button("📤 Publicar", key=f"pub_show_{fam['family_id']}", type="primary"):
                        _flip_published(fam["family_id"], True, motivo="Re-publicado desde panel Publicados")
                        st.session_state["pub_toast"] = f"✅ {fam['family_id']} publicado. Recordá push para reflejar en live."
                        st.rerun()

    # Toast global
    toast = st.session_state.pop("pub_toast", None)
    if toast:
        st.success(toast)


def _render_detail(conn, fid, catalog):
    """Detail editor para una family publicada/oculta."""
    fam = next((f for f in catalog if f["family_id"] == fid), None)
    if not fam:
        st.error(f"Family {fid} no encontrada en catalog")
        if st.button("← Volver"):
            st.session_state.pop("pub_current_fid", None)
            st.rerun()
        return

    # Header
    hc1, hc2, hc3 = st.columns([5, 1, 1])
    with hc1:
        is_pub = bool(fam.get("published"))
        badge = "🟢 Publicada" if is_pub else "👁️‍🗨️ Oculta"
        st.markdown(f"## Editar `{fid}` · {badge}")
    with hc2:
        if st.button("← Volver", use_container_width=True):
            st.session_state.pop("pub_current_fid", None)
            st.rerun()
    with hc3:
        live_url = f"https://vault.elclub.club/producto?id={fid}"
        st.link_button("🔗 Live", live_url, use_container_width=True)

    # Hero preview
    hero = fam.get("hero_thumbnail")
    if hero:
        pc1, pc2 = st.columns([1, 3])
        with pc1:
            st.image(hero, width=200)
        with pc2:
            st.markdown(f"**{fam.get('team', '')}** · {fam.get('season', '')} · {fam.get('variant_label') or fam.get('variant') or ''}")
            n = len(fam.get('modelos') or [])
            st.caption(f"📐 {n} modelo{'s' if n != 1 else ''} · {len(fam.get('gallery') or [])} fotos top-level gallery")

    st.markdown("---")

    # FORM: Top-level editable fields
    st.markdown("### 📝 Datos top-level")
    with st.form(key=f"pub_top_form_{fid}"):
        new_title = st.text_input("Title", value=fam.get("title") or "",
                                   help="Mostrado en grid/PDP")
        new_description = st.text_area("Description", value=fam.get("description") or "",
                                        height=80, help="2-3 oraciones breves")
        new_historia = st.text_area("Historia", value=fam.get("historia") or "",
                                     height=150, help="Narrativa 50-80 palabras · tono Midnight Stadium")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            new_featured = st.checkbox("⭐ Featured (TOP badge)", value=bool(fam.get("featured")))
        with col_b:
            new_meta_country = st.text_input("Meta country", value=fam.get("meta_country") or "")
        with col_c:
            new_meta_league = st.text_input("Meta league", value=fam.get("meta_league") or "")

        # Keywords
        current_kw = ", ".join(fam.get("keywords") or [])
        new_keywords = st.text_input("Keywords (comma-separated)", value=current_kw,
                                      help="Términos de búsqueda. Separar con coma.")

        submitted = st.form_submit_button("💾 Guardar cambios top-level", type="primary")
        if submitted:
            updates = {
                "title": new_title.strip() or None,
                "description": new_description.strip() or None,
                "historia": new_historia.strip() or None,
                "featured": bool(new_featured),
                "meta_country": new_meta_country.strip() or None,
                "meta_league": new_meta_league.strip() or None,
                "keywords": [k.strip() for k in new_keywords.split(",") if k.strip()],
            }
            changed = _apply_family_updates(fid, updates)
            st.success(f"✅ Guardado. Campos cambiados: {', '.join(changed) if changed else 'ninguno'}")
            st.rerun()

    # Per-modelo editor (price, sizes, sleeve, type corrections)
    st.markdown("---")
    st.markdown("### 📐 Modelos (editables por-item)")
    modelos = fam.get("modelos") or []

    # Primary modelo selector — el modelo que provee el HERO del family card
    # (fam.gallery + fam.hero_thumbnail top-level se sincronizan desde su gallery[0]).
    if modelos:
        current_primary = fam.get("primary_modelo_idx", 0) or 0
        primary_options = []
        for i, m in enumerate(modelos):
            lbl = f"modelo[{i}] · {m.get('sku', '?')} · {m.get('type', '?')}/{m.get('sleeve', '?')}"
            # Highlight fan_adult/short como recomendado
            if m.get("type") == "fan_adult" and m.get("sleeve") == "short":
                lbl += " ⭐ (recomendado)"
            primary_options.append(lbl)

        sel_idx = st.selectbox(
            "👑 Primary modelo (provee el Hero de la card)",
            range(len(primary_options)),
            index=current_primary if current_primary < len(primary_options) else 0,
            format_func=lambda i: primary_options[i],
            key=f"pub_primary_{fid}",
            help="Este modelo define fam.hero_thumbnail + fam.gallery (lo que el cliente ve primero en el grid). Recomendado: fan_adult/short si existe.",
        )
        if sel_idx != current_primary:
            _set_primary_modelo(fid, sel_idx)
            st.success(f"Primary cambiado a modelo[{sel_idx}]. Catalog actualizado.")
            st.rerun()

    if not modelos:
        st.info("Legacy family sin `modelos[]`. Price/sizes viven top-level o en `variants[]`.")
    else:
        for i, m in enumerate(modelos):
            with st.expander(
                f"modelo[{i}] · `{m.get('sku', '?')}` · {m.get('type', '?')}/{m.get('sleeve', '?')}",
                expanded=False,
            ):
                mhero = m.get("hero_thumbnail")
                if mhero:
                    st.image(mhero, width=120)

                with st.form(key=f"pub_mod_form_{fid}_{i}"):
                    fc1, fc2, fc3 = st.columns(3)
                    with fc1:
                        new_price = st.number_input(
                            "Price (Q)", value=int(m.get("price") or 0), step=5,
                            key=f"pub_price_{fid}_{i}",
                        )
                    with fc2:
                        new_sizes = st.text_input(
                            "Sizes", value=m.get("sizes") or "",
                            key=f"pub_sizes_{fid}_{i}",
                        )
                    with fc3:
                        modelo_types = ["fan_adult", "player_adult", "retro_adult", "woman", "kid", "baby"]
                        cur_type = m.get("type") or "fan_adult"
                        new_type = st.selectbox(
                            "Type",
                            modelo_types,
                            index=modelo_types.index(cur_type) if cur_type in modelo_types else 0,
                            key=f"pub_type_{fid}_{i}",
                        )

                    sc1, sc2 = st.columns(2)
                    with sc1:
                        sleeves = ["short", "long"]
                        cur_sleeve = m.get("sleeve") or "short"
                        new_sleeve = st.selectbox(
                            "Sleeve", sleeves,
                            index=sleeves.index(cur_sleeve) if cur_sleeve in sleeves else 0,
                            key=f"pub_sleeve_{fid}_{i}",
                        )
                    with sc2:
                        new_vtitle = st.text_input(
                            "Variant title (Yupoo)",
                            value=m.get("variant_title") or "",
                            key=f"pub_vtitle_{fid}_{i}",
                        )

                    save_btn = st.form_submit_button(f"💾 Guardar modelo[{i}]")
                    if save_btn:
                        updates = {
                            "price": int(new_price) if new_price > 0 else None,
                            "sizes": new_sizes.strip() or None,
                            "type": new_type,
                            "sleeve": new_sleeve,
                            "variant_title": new_vtitle.strip() or None,
                        }
                        changed = _apply_modelo_updates(fid, i, updates)
                        st.success(f"✅ modelo[{i}] guardado. Cambios: {', '.join(changed) if changed else 'ninguno'}")
                        st.rerun()

                # Editor de galería (post-publish, mutations directas sobre
                # catalog.gallery — no pasa por audit_photo_actions).
                _render_gallery_editor(fid, i, m)

    # Batch watermark processing — procesa TODAS las fotos sin cache-bust
    # del family con LaMa (OCR + template match fallback). Diego se ahorra
    # clickear una por una.
    st.markdown("---")
    st.markdown("### 🧹 Procesar watermarks en batch")
    import local_inpaint as _li_batch
    batch_c1, batch_c2 = st.columns([1, 3])
    with batch_c1:
        if st.button("🧹 Procesar toda la family",
                     key=f"pub_batch_{fid}",
                     type="primary", use_container_width=True,
                     disabled=not _li_batch.local_inpaint_available(),
                     help="Pasa LaMa + OCR/template sobre todas las fotos sin cache-bust (DIRTY). Si OCR+template no detectan, skip."):
            _batch_clean_family(fid)
            st.rerun()
    with batch_c2:
        # Count dirty
        n_dirty = 0
        for _m in fam.get("modelos") or []:
            for _u in _m.get("gallery") or []:
                if "?v=" not in _u:
                    n_dirty += 1
        st.caption(f"{n_dirty} fotos DIRTY (sin cache-bust) en esta family. Procesa con LaMa auto-detect.")

    # QA Review Post-Batch — aparece solo si hay items en session_state
    _render_batch_review(fid)

    # Acciones finales
    st.markdown("---")
    st.markdown("### ⚡ Acciones")
    ac1, ac2, ac3 = st.columns(3)
    is_pub = bool(fam.get("published"))
    with ac1:
        if is_pub:
            if st.button("👁 Ocultar del vault live", use_container_width=True):
                _flip_published(fid, False, motivo="Ocultado desde panel detalle")
                st.success("🙈 Oculto. Push para reflejar en live.")
                st.rerun()
        else:
            if st.button("📤 Re-publicar al vault live", type="primary", use_container_width=True):
                _flip_published(fid, True, motivo="Re-publicado desde panel detalle")
                st.success("✅ Publicada. Push para reflejar en live.")
                st.rerun()
    with ac2:
        if st.button("🚀 Commit + Push catalog", use_container_width=True,
                     help="Aplica los cambios al repo → auto-deploy vault.elclub.club en ~30s"):
            result = _commit_and_push(fid)
            if result.get("ok"):
                st.success(f"✅ Push OK. Auto-deploy en vault.elclub.club en ~30s.")
            else:
                st.error(f"⚠️ {result.get('error', 'git push falló')}")
    with ac3:
        if st.button("🔍 Abrir en Audit", use_container_width=True,
                     help="Jump al audit detail de este canonical (re-auditar fotos, etc.)"):
            # Reusa audit session_state para navegar
            primary = (fam.get("modelos") or [{}])[fam.get("primary_modelo_idx", 0) or 0]
            sku = primary.get("sku") or fid
            st.session_state["audit_view"] = "detail"
            st.session_state["current_family"] = sku
            st.session_state["_page_override"] = "audit"
            st.rerun()


# ═══════════════════════════════════════════════
# Gallery editor (post-publish)
# ═══════════════════════════════════════════════

def _render_gallery_editor(fid, modelo_idx, modelo):
    """Grid de fotos con acciones por-foto: 👑 hero, ↑↓ reorder, ❌ delete,
    ⚠️ re-run Gemini watermark inpaint. Mutations directas sobre catalog.gallery
    (no audit_photo_actions — eso es pre-publish).
    """
    st.markdown("##### 📷 Galería")
    gallery = modelo.get("gallery") or []
    if not gallery:
        st.info("Sin galería. Agregar imágenes es vía re-fetch scripts (scope Operaciones).")
        return

    st.caption(f"{len(gallery)} fotos · foto #1 = hero (lo que ve el cliente primero)")

    # Section de fotos borradas (soft-delete) con restore
    deleted = modelo.get("deleted_gallery") or []
    if deleted:
        with st.expander(f"🗑 Fotos borradas ({len(deleted)}) · click para restaurar",
                          expanded=False):
            dcols = st.columns(min(4, len(deleted)))
            for di, entry in enumerate(deleted):
                with dcols[di % len(dcols)]:
                    try:
                        st.image(entry["url"], use_container_width=True)
                    except Exception:
                        st.caption("(img fail)")
                    st.caption(f"Borrada: {entry.get('deleted_at', '?')[:16]}")
                    if st.button("↺ Restaurar", key=f"pub_undel_{fid}_{modelo_idx}_{di}",
                                 use_container_width=True):
                        _gallery_restore(fid, modelo_idx, di)
                        st.toast("↺ Restaurada al final de la galería")
                        st.rerun()

    # Bulk multi-select state per (family, modelo). Set de p_idx seleccionados.
    # Permite marcar varias fotos y eliminarlas todas en 1 rerun.
    sel_key = f"sel_{fid}_{modelo_idx}"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = set()
    selected = st.session_state[sel_key]

    bulk_c1, bulk_c2, bulk_c3 = st.columns([3, 1, 1])
    with bulk_c1:
        if selected:
            if st.button(f"🗑️ Eliminar {len(selected)} seleccionada(s)",
                         key=f"bulk_del_{fid}_{modelo_idx}",
                         type="primary", use_container_width=True,
                         help="Soft-delete de todas las marcadas en un solo paso"):
                # Sort descending para no romper índices (gallery.pop shiftea)
                deleted_n = 0
                for pi in sorted(selected, reverse=True):
                    if 0 <= pi < len(gallery):
                        _gallery_delete(fid, modelo_idx, pi)
                        deleted_n += 1
                st.session_state[sel_key] = set()
                st.toast(f"🗑 {deleted_n} fotos eliminadas de m{modelo_idx}")
                st.rerun()
        else:
            st.caption(
                f"☑ Multi-select: marcá el checkbox de cada foto que querés eliminar "
                f"y usá 🗑️ para bulk delete (evita 1 rerun por foto)."
            )
    with bulk_c2:
        if st.button("☑ Todas", key=f"sel_all_{fid}_{modelo_idx}",
                     use_container_width=True,
                     disabled=(len(selected) == len(gallery))):
            st.session_state[sel_key] = set(range(len(gallery)))
            st.rerun()
    with bulk_c3:
        if st.button("☐ Ninguna", key=f"sel_none_{fid}_{modelo_idx}",
                     use_container_width=True,
                     disabled=not selected):
            st.session_state[sel_key] = set()
            st.rerun()

    cols_per_row = 4
    for row_start in range(0, len(gallery), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            p_idx = row_start + col_idx
            if p_idx >= len(gallery):
                break
            url = gallery[p_idx]
            with cols[col_idx]:
                # Header: checkbox multi-select + crown/numeración
                hdr_c1, hdr_c2 = st.columns([1, 3])
                with hdr_c1:
                    was_sel = p_idx in selected
                    is_sel = st.checkbox(
                        "sel", value=was_sel,
                        key=f"sel_cb_{fid}_{modelo_idx}_{p_idx}",
                        label_visibility="collapsed",
                        help="Marcar para bulk delete",
                    )
                    if is_sel != was_sel:
                        if is_sel:
                            selected.add(p_idx)
                        else:
                            selected.discard(p_idx)
                        st.session_state[sel_key] = selected
                with hdr_c2:
                    crown = "👑 HERO" if p_idx == 0 else f"#{p_idx + 1}"
                    st.caption(crown)
                try:
                    st.image(url, use_container_width=True)
                except Exception:
                    st.warning(f"⚠️ img load fail: {url[-40:]}")

                bc1, bc2, bc3, bc4 = st.columns(4)
                with bc1:
                    if st.button("👑", key=f"pub_hero_{fid}_{modelo_idx}_{p_idx}",
                                 help="Set as hero (move to #1)",
                                 disabled=(p_idx == 0)):
                        _gallery_set_hero(fid, modelo_idx, p_idx)
                        st.rerun()
                with bc2:
                    if st.button("↑", key=f"pub_up_{fid}_{modelo_idx}_{p_idx}",
                                 help="Move up",
                                 disabled=(p_idx == 0)):
                        _gallery_swap(fid, modelo_idx, p_idx, p_idx - 1)
                        st.rerun()
                with bc3:
                    if st.button("↓", key=f"pub_dn_{fid}_{modelo_idx}_{p_idx}",
                                 help="Move down",
                                 disabled=(p_idx == len(gallery) - 1)):
                        _gallery_swap(fid, modelo_idx, p_idx, p_idx + 1)
                        st.rerun()
                with bc4:
                    if st.button("❌", key=f"pub_del_{fid}_{modelo_idx}_{p_idx}",
                                 help="Delete foto (removes from gallery array)"):
                        _gallery_delete(fid, modelo_idx, p_idx)
                        st.toast(f"🗑 Foto #{p_idx + 1} eliminada de {fid} m{modelo_idx}")
                        st.rerun()

                # Check si hay backup disponible (R2 object `<path>.backup.jpg`)
                # para esta foto. Si sí, mostrar botón ↺ Restore original.
                import requests
                _base = url.split("?")[0]
                _backup_url = _base.rsplit(".", 1)[0] + ".backup.jpg" if "/families/" in _base else None
                _has_backup = False
                if _backup_url:
                    try:
                        _h = requests.head(_backup_url, timeout=3)
                        _has_backup = _h.status_code == 200
                    except Exception:
                        pass
                if _has_backup:
                    if st.button("↺ Restore original", key=f"pub_restore_{fid}_{modelo_idx}_{p_idx}",
                                 help="Restaurar bytes originales del R2 backup (pre-overwrite)",
                                 use_container_width=True):
                        with st.spinner("Restoring original..."):
                            rr = _restore_r2_from_backup(fid, modelo_idx, p_idx)
                        if rr.get("ok"):
                            st.toast(f"↺ Original restored #{p_idx + 1}")
                        else:
                            st.error(f"⚠️ {rr.get('error')}")
                        st.rerun()

                # Watermark row — 2 buttons:
                # ⚠️ Watermark = OCR-based (auto-detect + LaMa). Si OCR falla → error.
                # 🎯 Forzar = mask HARDCODED centro (ignora OCR, usa dimensiones
                # estándar del watermark Yupoo). Para los casos donde Diego ve
                # watermark pero OCR no lo detectó (text bajo textura difícil).
                import local_inpaint as _li
                lama_ok = _li.local_inpaint_available()
                backend_ok = lama_ok or audit_enrich.gemini_available()
                backend_label = "LaMa local" if lama_ok else "Gemini"
                wc1, wc2 = st.columns(2)
                with wc1:
                    if st.button("⚠️ Auto",
                                 key=f"pub_wm_{fid}_{modelo_idx}_{p_idx}",
                                 help=f"Inpaint auto-detect vía {backend_label}. Si OCR no detecta, usá 🎯 Forzar.",
                                 disabled=not backend_ok,
                                 use_container_width=True):
                        with st.spinner(f"{backend_label} inpainting…"):
                            res = _regen_watermark(fid, modelo_idx, p_idx, mode="auto")
                        if res.get("ok"):
                            st.toast(f"✅ Watermark cleaned #{p_idx + 1}")
                        else:
                            st.error(f"⚠️ {res.get('error', 'unknown')}")
                        st.rerun()
                with wc2:
                    if st.button("🎯 Forzar",
                                 key=f"pub_wm_force_{fid}_{modelo_idx}_{p_idx}",
                                 help="Inpaint con mask hardcoded centro (dimensiones estándar Yupoo). Usar cuando OCR no detectó pero vos ves watermark.",
                                 disabled=not lama_ok,
                                 use_container_width=True):
                        with st.spinner("LaMa forzado (mask centro)…"):
                            res = _regen_watermark(fid, modelo_idx, p_idx, mode="force")
                        if res.get("ok"):
                            st.toast(f"🎯 Forced inpaint #{p_idx + 1}")
                        else:
                            st.error(f"⚠️ {res.get('error', 'unknown')}")
                        st.rerun()

                # Nivel 4 — SD Inpaint (preserva logos/texturas mejor que LaMa).
                # Lento (~10s) pero mejor quality cuando LaMa daña detalles.
                _sd_ok = _li.sd_available() if lama_ok else False
                if st.button("🧠 SD Inpaint",
                             key=f"pub_wm_sd_{fid}_{modelo_idx}_{p_idx}",
                             help=("Stable Diffusion inpaint con prompt preservador. "
                                   "Último recurso si LaMa deja artefactos en logos/texturas. "
                                   "Requiere: iopaint download --model runwayml/stable-diffusion-inpainting"),
                             disabled=not _sd_ok,
                             use_container_width=True):
                    with st.spinner("SD Inpaint (~10s)…"):
                        res = _regen_watermark(fid, modelo_idx, p_idx, mode="sd")
                    if res.get("ok"):
                        st.toast(f"🧠 SD inpaint #{p_idx + 1}")
                    else:
                        st.error(f"⚠️ {res.get('error', 'unknown')}")
                    st.rerun()
                if not _sd_ok and lama_ok:
                    st.caption("🧠 SD no descargado. Correr: `iopaint download --model runwayml/stable-diffusion-inpainting`")

                # Nivel 5 — Gemini Rescue (texturas complejas: check patterns,
                # escudos metálicos, embroidery). ~$0.04/foto pero mejor quality
                # que LaMa/SD cuando hay branding conocido debajo del watermark.
                _gem_ok = audit_enrich.gemini_available()
                if st.button("🌟 Gemini Rescue",
                             key=f"pub_wm_gem_{fid}_{modelo_idx}_{p_idx}",
                             help=("Gemini 2.5 Flash Image con prompt preservador. "
                                   "Mejor para texturas complejas (adidas stripes, "
                                   "FIFA badges, escudos metálicos). ~$0.04/foto, ~5s. "
                                   "Usar cuando LaMa/SD dañan detalles finos."),
                             disabled=not _gem_ok,
                             use_container_width=True):
                    with st.spinner("🌟 Gemini Rescue (~5s)…"):
                        res = _regen_watermark(fid, modelo_idx, p_idx, mode="gemini")
                    if res.get("ok"):
                        diag = res.get("diagnostic") or {}
                        if diag.get("identical"):
                            st.error(
                                f"⚠️ Gemini devolvió imagen IDÉNTICA al input "
                                f"(hash match {diag.get('in_hash')}). El modelo no editó. "
                                f"Problema de prompt/modelo, NO de cache."
                            )
                        else:
                            delta = diag.get("delta_pct", 0)
                            st.toast(
                                f"🌟 Gemini #{p_idx + 1} · Δ {delta:.1f}% "
                                f"({diag.get('in_hash')} → {diag.get('out_hash')})"
                            )
                    else:
                        st.error(f"⚠️ {res.get('error', 'unknown')}")
                    st.rerun()
                if not _gem_ok:
                    st.caption("🌟 GEMINI_API_KEY no seteada en `.env`")

                # Nivel 6 — Pintar mask manual (safety net 100% efectivo).
                # Diego pinta con brush sobre el watermark y LaMa/SD procesa con
                # esa mask. Para casos donde auto/force/sd/gemini fallaron.
                _paint_key = f"paint_{fid}_{modelo_idx}_{p_idx}"
                painting = st.session_state.get(_paint_key, False)
                _paint_label = "❌ Cerrar canvas" if painting else "🖌️ Pintar mask"
                if st.button(_paint_label,
                             key=f"pub_wm_paint_{fid}_{modelo_idx}_{p_idx}",
                             help=("Canvas interactivo: pintá con brush sobre el "
                                   "watermark y LaMa/SD procesa SOLO esa área. "
                                   "100% confiable pero ~15s/foto."),
                             disabled=not lama_ok,
                             use_container_width=True):
                    st.session_state[_paint_key] = not painting
                    st.rerun()

                if painting:
                    _render_paint_canvas(fid, modelo_idx, p_idx, url, _paint_key)


def _render_paint_canvas(fid, modelo_idx, photo_idx, url, paint_key):
    """Canvas interactivo: Diego pinta brush sobre el watermark y LaMa/SD
    procesa con esa mask. Safety net 100% efectivo para cuando auto/force/
    sd/gemini fallan. ~15s por foto con brush strokes razonables."""
    try:
        from streamlit_drawable_canvas import st_canvas
    except ImportError:
        st.error(
            "`streamlit-drawable-canvas` no instalado. Correr: "
            "`pip install streamlit-drawable-canvas`"
        )
        return

    import requests
    from PIL import Image
    import io
    import numpy as np

    # Download foto original (dims reales)
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            st.error(f"DL fail: HTTP {resp.status_code}")
            return
        orig_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        st.error(f"DL fail: {e}")
        return

    orig_w, orig_h = orig_img.size
    # Scale para canvas display (max 600px wide). La mask se re-scale-a al tamaño
    # original en custom_mask_inpaint_bytes vía cv2.resize.
    max_display_w = 600
    if orig_w > max_display_w:
        scale = max_display_w / orig_w
        disp_w = max_display_w
        disp_h = int(orig_h * scale)
        disp_img = orig_img.resize((disp_w, disp_h), Image.LANCZOS)
    else:
        disp_w, disp_h = orig_w, orig_h
        disp_img = orig_img

    with st.container(border=True):
        st.markdown(f"**🖌️ Pintar mask · m{modelo_idx} foto #{photo_idx + 1}**")
        ctrl_a, ctrl_b, ctrl_c = st.columns([1, 1, 2])
        with ctrl_a:
            brush_size = st.slider(
                "Brush px", min_value=5, max_value=80, value=30,
                key=f"{paint_key}_brush",
                help="Grosor del brush. Ajustá según tamaño del watermark.",
            )
        with ctrl_b:
            backend = st.radio(
                "Backend",
                options=["LaMa", "SD"],
                horizontal=True,
                key=f"{paint_key}_backend",
                help="LaMa ~1-2s (rápido). SD ~10s (mejor quality en logos/texturas).",
            )
        with ctrl_c:
            st.caption(
                f"Pintá sobre TODAS las instancias del watermark con brush blanco. "
                f"Imagen orig: {orig_w}×{orig_h}px · display: {disp_w}×{disp_h}px "
                f"(la mask se re-escala automáticamente al original)."
            )

        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 0.0)",
            stroke_width=brush_size,
            stroke_color="#ffffff",
            background_image=disp_img,
            update_streamlit=False,  # acumula strokes local; no rerun por stroke
            height=disp_h,
            width=disp_w,
            drawing_mode="freedraw",
            key=f"{paint_key}_canvas",
        )

        btn_a, btn_b = st.columns(2)
        with btn_a:
            apply_clicked = st.button(
                "✅ Aplicar inpaint", key=f"{paint_key}_apply",
                type="primary", use_container_width=True,
            )
        with btn_b:
            cancel_clicked = st.button(
                "❌ Cancelar", key=f"{paint_key}_cancel",
                use_container_width=True,
            )

        if cancel_clicked:
            st.session_state[paint_key] = False
            st.rerun()

        if apply_clicked:
            if canvas_result.image_data is None:
                st.error("Canvas vacío. Pintá sobre el watermark primero.")
                return
            alpha = canvas_result.image_data[:, :, 3]
            if int(np.count_nonzero(alpha)) == 0:
                st.error("Nada pintado. Usá el brush blanco sobre el watermark.")
                return

            # PNG mask bytes (binarizada)
            mask_bin = (alpha > 0).astype(np.uint8) * 255
            pil_mask = Image.fromarray(mask_bin, mode="L")
            buf = io.BytesIO()
            pil_mask.save(buf, format="PNG")
            mask_bytes = buf.getvalue()

            use_sd = (backend == "SD")
            with st.spinner(f"🖌️ {'SD' if use_sd else 'LaMa'} inpainting…"):
                res = _regen_watermark(
                    fid, modelo_idx, photo_idx,
                    mode="manual",
                    mask_bytes=mask_bytes,
                    use_sd_for_manual=use_sd,
                )
            if res.get("ok"):
                st.toast(f"🖌️ Manual inpaint #{photo_idx + 1} listo")
                st.session_state[paint_key] = False
                st.rerun()
            else:
                st.error(f"⚠️ {res.get('error', 'unknown')}")


def _gallery_set_hero(fid, modelo_idx, photo_idx):
    """Mueve photo_idx a la posición 0 (hero). Sync top-level si es primary modelo."""
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = list(modelo.get("gallery") or [])
    if photo_idx <= 0 or photo_idx >= len(gallery):
        return
    new_hero = gallery.pop(photo_idx)
    gallery.insert(0, new_hero)
    modelo["gallery"] = gallery
    modelo["hero_thumbnail"] = gallery[0]
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)


def _gallery_swap(fid, modelo_idx, pos_a, pos_b):
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = list(modelo.get("gallery") or [])
    if not (0 <= pos_a < len(gallery) and 0 <= pos_b < len(gallery)):
        return
    gallery[pos_a], gallery[pos_b] = gallery[pos_b], gallery[pos_a]
    modelo["gallery"] = gallery
    if 0 in (pos_a, pos_b):
        modelo["hero_thumbnail"] = gallery[0]
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)


def _gallery_delete(fid, modelo_idx, photo_idx):
    """Soft-delete: mueve URL de gallery[] → deleted_gallery[] para permitir
    restore. Los bytes R2 NO se tocan. UI muestra deleted_gallery separado
    con botón ↺ Restaurar."""
    from datetime import datetime
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = list(modelo.get("gallery") or [])
    if not (0 <= photo_idx < len(gallery)):
        return
    url = gallery.pop(photo_idx)
    # Append a deleted_gallery[] con timestamp
    deleted = list(modelo.get("deleted_gallery") or [])
    deleted.append({
        "url": url,
        "deleted_at": datetime.now().isoformat(timespec="seconds"),
        "original_idx": photo_idx,
    })
    modelo["gallery"] = gallery
    modelo["deleted_gallery"] = deleted
    modelo["hero_thumbnail"] = gallery[0] if gallery else None
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)


def _gallery_restore(fid, modelo_idx, deleted_idx):
    """Restore de deleted_gallery[] → gallery[] (al final del array)."""
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return
    modelo = (fam.get("modelos") or [])[modelo_idx]
    deleted = list(modelo.get("deleted_gallery") or [])
    if not (0 <= deleted_idx < len(deleted)):
        return
    entry = deleted.pop(deleted_idx)
    gallery = list(modelo.get("gallery") or [])
    gallery.append(entry["url"])
    modelo["gallery"] = gallery
    modelo["deleted_gallery"] = deleted
    if not modelo.get("hero_thumbnail"):
        modelo["hero_thumbnail"] = gallery[0]
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)


def _restore_r2_from_backup(fid, modelo_idx, photo_idx):
    """Descarga el backup R2 del path `.backup.jpg` y lo sube al key original.
    Actualiza URL del catalog (cache-bust nuevo para invalidar CDN).
    El backup key NO se borra — puede restaurarse de nuevo si se re-edita."""
    import requests
    from datetime import datetime
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return {"error": "family not found"}
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = list(modelo.get("gallery") or [])
    if not (0 <= photo_idx < len(gallery)):
        return {"error": "photo idx OOB"}

    cur_url = gallery[photo_idx]
    base_url = cur_url.split("?")[0]
    if "/families/" not in base_url:
        return {"error": "URL no es R2"}
    key = "families/" + base_url.split("/families/", 1)[1]
    backup_key = key.rsplit(".", 1)[0] + ".backup.jpg"
    backup_url = f"https://img.elclub.club/{backup_key}"

    # Download backup
    try:
        resp = requests.get(backup_url, timeout=20)
        if resp.status_code != 200:
            return {"error": f"backup no existe (HTTP {resp.status_code} en {backup_key})"}
    except Exception as e:
        return {"error": f"download backup: {e}"}

    # Upload backup bytes al key original (overwrite con el backup)
    up = audit_enrich.upload_image_to_r2(resp.content, key, content_type="image/jpeg")
    if not up.get("ok"):
        return {"error": f"R2 upload: {up.get('error')}"}

    # Cache-bust URL
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_url = f"{base_url}?v={ts}"
    gallery[photo_idx] = new_url
    modelo["gallery"] = gallery
    if photo_idx == 0:
        modelo["hero_thumbnail"] = new_url
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)
    return {"ok": True}


def _backup_r2_before_overwrite(url):
    """Descarga el R2 object actual y lo sube a `<path>.backup.jpg`.
    Se llama ANTES de cualquier overwrite (watermark auto/forzar).
    Si el backup ya existe (previous edit), NO se sobreescribe — preserva
    el original más antiguo."""
    import requests
    base_url = url.split("?")[0]
    if "/families/" not in base_url:
        return {"ok": False, "error": "URL no es R2"}
    key = "families/" + base_url.split("/families/", 1)[1]
    backup_key = key.rsplit(".", 1)[0] + ".backup.jpg"

    # HEAD al backup — si ya existe, no sobreescribimos (preservamos más antiguo)
    try:
        import os, boto3
        account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
        access_key = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        bucket = os.getenv("R2_BUCKET", "elclub-vault-images").strip()
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
        try:
            client.head_object(Bucket=bucket, Key=backup_key)
            return {"ok": True, "status": "already_exists", "backup_key": backup_key}
        except Exception:
            pass  # 404 → proceed to create backup
    except Exception as e:
        return {"ok": False, "error": f"R2 check: {e}"}

    # Download current R2 object
    try:
        resp = requests.get(base_url, timeout=20)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code} descargando original"}
    except Exception as e:
        return {"ok": False, "error": f"download: {e}"}

    # Upload a .backup.jpg
    up = audit_enrich.upload_image_to_r2(resp.content, backup_key, content_type="image/jpeg")
    if not up.get("ok"):
        return {"ok": False, "error": f"R2 upload backup: {up.get('error')}"}

    return {"ok": True, "status": "created", "backup_key": backup_key}


def _regen_watermark(fid, modelo_idx, photo_idx, mode="auto",
                     mask_bytes=None, use_sd_for_manual=False):
    """Descarga foto de R2, pasa por inpaint (LaMa local o Gemini), sube
    resultado al mismo key + cache-bust URL en catalog.

    mode:
      "auto"   — LaMa + OCR/template (default). Falla si OCR+template no detectan.
      "force"  — LaMa + mask hardcoded centro (dimensiones estándar Yupoo).
      "sd"     — Stable Diffusion inpaint (preserva logos/texturas mejor que LaMa).
      "gemini" — Gemini 2.5 Flash Image con prompt preservador quirúrgico.
      "manual" — Custom mask pintada por Diego en canvas Streamlit.
                 Requiere `mask_bytes` (PNG). Usa LaMa o SD según use_sd_for_manual.
                 Safety net 100% efectivo para casos extremos (auto/force/sd/gemini
                 fallaron). Latency ~1-2s (LaMa) o ~10s (SD).
    """
    import requests
    from datetime import datetime

    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return {"error": "family not found"}
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = list(modelo.get("gallery") or [])
    if not (0 <= photo_idx < len(gallery)):
        return {"error": "photo index OOB"}

    current_url = gallery[photo_idx]
    base_url = current_url.split("?")[0]
    # Derivar R2 key desde el URL público (https://img.elclub.club/<key>)
    if "/families/" not in base_url:
        return {"error": f"URL no reconocida como R2 path: {base_url}"}
    key = "families/" + base_url.split("/families/", 1)[1]

    # Download
    try:
        resp = requests.get(current_url, timeout=30)
    except Exception as e:
        return {"error": f"download fail: {e}"}
    if resp.status_code != 200:
        return {"error": f"download http {resp.status_code}"}
    img_bytes = resp.content

    # Watermark inpaint — modo auto (OCR+LaMa), force (mask hardcoded), sd (SD inpaint).
    import local_inpaint as _li
    lama_ok = _li.local_inpaint_available()

    if mode == "manual":
        if not mask_bytes:
            return {"error": "mode=manual requiere mask_bytes (pintá la mask primero)"}
        if not lama_ok:
            return {"error": "LaMa local no disponible (torch.cuda?)"}
        gem = _li.custom_mask_inpaint_bytes(
            img_bytes, mask_bytes, mime_type="image/jpeg",
            use_sd=use_sd_for_manual,
            family_id=fid, photo_index=photo_idx,
        )
    elif mode == "gemini":
        if not audit_enrich.gemini_available():
            return {"error": "GEMINI_API_KEY no seteada — revisar .env"}
        gem = audit_enrich.gemini_regen_image(
            img_bytes, mime_type="image/jpeg", prompt_variant="preserve",
            family_id=fid, photo_index=photo_idx,
        )
        # Diagnóstico: comparar bytes input vs output. Si similarity>95% → Gemini
        # devolvió la imagen sin editar (failure mode del modelo cuando el prompt
        # es ambiguo). Si diff grande pero visualmente igual → CDN cache.
        if gem.get("ok"):
            import hashlib
            in_size = len(img_bytes)
            out_size = len(gem.get("image_bytes") or b"")
            in_hash = hashlib.md5(img_bytes).hexdigest()[:8]
            out_hash = hashlib.md5(gem.get("image_bytes") or b"").hexdigest()[:8]
            delta_pct = abs(out_size - in_size) / max(in_size, 1) * 100
            identical = (in_hash == out_hash)
            gem["_diagnostic"] = {
                "in_size": in_size, "out_size": out_size,
                "in_hash": in_hash, "out_hash": out_hash,
                "delta_pct": round(delta_pct, 2),
                "identical": identical,
            }
            print(f"[GEMINI DIAG] m{modelo_idx} idx={photo_idx} "
                  f"in={in_size}b ({in_hash}) → out={out_size}b ({out_hash}) "
                  f"Δ={delta_pct:.1f}% {'IDENTICAL' if identical else 'CHANGED'}")
    elif mode == "sd":
        if not lama_ok or not _li.sd_available():
            return {"error": "SD Inpaint requiere LaMa local + SD model descargado"}
        gem = _li.sd_inpaint_bytes(
            img_bytes, mime_type="image/jpeg",
            use_ocr_mask=True, force_mask=True,  # OCR primero, fallback a hardcoded
            family_id=fid, photo_index=photo_idx,
        )
    elif mode == "force":
        if not lama_ok:
            return {"error": "Forzar requiere LaMa local (no Gemini fallback)"}
        gem = _li.force_inpaint_center_bytes(
            img_bytes, mime_type="image/jpeg",
            family_id=fid, photo_index=photo_idx,
        )
    elif lama_ok:
        gem = _li.watermark_inpaint_bytes(
            img_bytes, mime_type="image/jpeg",
            family_id=fid, photo_index=photo_idx,
        )
        if gem.get("skipped") == "no_watermark_detected":
            return {"error": "OCR+template no detectaron watermark. Probá '🎯 Forzar' o '🧠 SD'."}
    else:
        gem = audit_enrich.gemini_regen_image(
            img_bytes, mime_type="image/jpeg", prompt_variant="watermark",
            family_id=fid, photo_index=photo_idx,
        )
    if not gem.get("ok"):
        return {"error": gem.get("error", "inpaint fail")}

    # Backup del original ANTES de overwrite. Si ya existe backup previo (por
    # edit anterior), se preserva el más antiguo — eso permite ir "más atrás"
    # en caso de múltiples ediciones consecutivas.
    backup_res = _backup_r2_before_overwrite(current_url)
    # No bloqueamos si backup falla — solo log y seguimos
    if not backup_res.get("ok"):
        print(f"[WARN] backup pre-overwrite fail: {backup_res.get('error')}")

    # Upload back to same key (overwrite)
    up = audit_enrich.upload_image_to_r2(
        gem["image_bytes"], key, content_type=gem.get("mime_type", "image/jpeg"),
    )
    if not up.get("ok"):
        return {"error": up.get("error", "upload fail")}

    # Cache-bust: update URL en catalog con ?v={ts}
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    new_url = f"{base_url}?v={ts}"
    gallery[photo_idx] = new_url
    modelo["gallery"] = gallery
    if photo_idx == 0:
        modelo["hero_thumbnail"] = new_url
    _sync_top_level_if_primary(fam, modelo_idx)
    _save_catalog(catalog)

    result = {"ok": True, "new_url": new_url}
    if gem.get("_diagnostic"):
        result["diagnostic"] = gem["_diagnostic"]
    return result


# Helpers compartidos
def _load_catalog_fresh():
    with open(audit_db.CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_catalog(catalog):
    with open(audit_db.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _find_fam(catalog, fid):
    for f in catalog:
        if f.get("family_id") == fid:
            return f
    return None


def _batch_clean_family(fid):
    """Procesa todas las fotos sin cache-bust del family con LaMa auto-detect.
    Mismo flow que scripts/clean-all-published.py pero inline Streamlit con
    progress bar. Hace backup pre-overwrite de cada foto."""
    import requests
    from datetime import datetime
    import local_inpaint

    if not local_inpaint.local_inpaint_available():
        st.error("LaMa local no disponible (torch.cuda?)")
        return

    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        st.error(f"Family {fid} no encontrada")
        return

    # Collect dirty photos
    dirty = []
    for mi, m in enumerate(fam.get("modelos") or []):
        for pi, url in enumerate(m.get("gallery") or []):
            if "?v=" not in url:
                dirty.append((mi, pi, url))
    total = len(dirty)
    if total == 0:
        st.info("Sin fotos DIRTY. Todo ya procesado.")
        return

    progress = st.progress(0.0, text=f"Batch clean: 0/{total}")
    log = st.empty()
    log_lines = []
    review_items = []  # accumulador para QA review post-batch
    ok_count = 0
    skip_count = 0
    fail_count = 0

    def _record(mi, pi, url_now, status, note, method):
        review_items.append({
            "mi": mi, "pi": pi, "url": url_now,
            "status": status, "note": note, "method": method,
        })

    for i, (mi, pi, url) in enumerate(dirty, 1):
        base_url = url.split("?")[0]
        if "/families/" not in base_url:
            log_lines.append(f"[{i}/{total}] m{mi} idx={pi} SKIP (URL no R2)")
            log.code("\n".join(log_lines[-10:]))
            skip_count += 1
            _record(mi, pi, url, "skip", "URL no R2", "skipped")
            progress.progress(i / total, text=f"Batch clean: {i}/{total}")
            continue
        key = "families/" + base_url.split("/families/", 1)[1]

        # Download
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")
            img_bytes = resp.content
        except Exception as e:
            log_lines.append(f"[{i}/{total}] m{mi} idx={pi} DL fail: {e}")
            fail_count += 1
            _record(mi, pi, url, "fail", f"DL: {e}", "download_error")
            progress.progress(i / total, text=f"Batch clean: {i}/{total}")
            continue

        # LaMa with OCR + template match fallback
        result = local_inpaint.watermark_inpaint_bytes(img_bytes, family_id=fid, photo_index=pi)
        if result.get("skipped") == "no_watermark_detected":
            log_lines.append(f"[{i}/{total}] m{mi} idx={pi} SKIP (no watermark)")
            skip_count += 1
            _record(mi, pi, url, "skip", "OCR+template no detectaron watermark", "no_watermark")
            log.code("\n".join(log_lines[-10:]))
            progress.progress(i / total, text=f"Batch clean: {i}/{total}")
            continue
        if not result.get("ok"):
            err = result.get("error", "inpaint fail")
            log_lines.append(f"[{i}/{total}] m{mi} idx={pi} FAIL: {err}")
            fail_count += 1
            _record(mi, pi, url, "fail", err, "inpaint_error")
            log.code("\n".join(log_lines[-10:]))
            progress.progress(i / total, text=f"Batch clean: {i}/{total}")
            continue

        # Backup pre-overwrite
        _backup_r2_before_overwrite(url)

        # Upload cleaned
        up = audit_enrich.upload_image_to_r2(
            result["image_bytes"], key,
            content_type=result.get("mime_type", "image/jpeg"),
        )
        if not up.get("ok"):
            err = up.get("error", "R2 upload fail")
            log_lines.append(f"[{i}/{total}] m{mi} idx={pi} R2 fail: {err}")
            fail_count += 1
            _record(mi, pi, url, "fail", err, "r2_upload_error")
            log.code("\n".join(log_lines[-10:]))
            progress.progress(i / total, text=f"Batch clean: {i}/{total}")
            continue

        # Update catalog in-memory with cache-bust URL
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_url = f"{base_url}?v={ts}"
        fam["modelos"][mi]["gallery"][pi] = new_url
        if pi == 0:
            fam["modelos"][mi]["hero_thumbnail"] = new_url
        _sync_top_level_if_primary(fam, mi)
        # Save incremental (en caso de kill)
        _save_catalog(catalog)
        catalog = _load_catalog_fresh()  # reload por si hubo concurrent changes
        fam = _find_fam(catalog, fid)

        method = result.get("detection_method", "?")
        log_lines.append(f"[{i}/{total}] m{mi} idx={pi} OK ({method})")
        ok_count += 1
        _record(mi, pi, new_url, "ok", f"Procesada ({method})", method)
        log.code("\n".join(log_lines[-10:]))
        progress.progress(i / total, text=f"Batch clean: {i}/{total}")

    progress.progress(1.0, text=f"Done: {ok_count} OK · {skip_count} SKIP · {fail_count} FAIL")
    st.success(f"🧹 Batch terminó. OK: {ok_count} · SKIP: {skip_count} · FAIL: {fail_count}. No olvides click 🚀 Commit+Push.")

    # Push a session_state → el panel _render_batch_review lo lee en el next rerun
    st.session_state[f"batch_review_{fid}"] = review_items


# ═══════════════════════════════════════════════
# QA Review Post-Batch (modal tipo panel expandible)
# ═══════════════════════════════════════════════

def _br_update_item(key, mi, pi, res, method):
    """Actualiza un item del review tras re-procesar (auto/force/sd/restore)."""
    items = st.session_state.get(key) or []
    for it in items:
        if it["mi"] == mi and it["pi"] == pi:
            if res.get("ok"):
                it["status"] = "ok"
                it["note"] = f"Re-procesada ({method})"
                it["method"] = method
                new_url = res.get("new_url")
                if new_url:
                    it["url"] = new_url
            else:
                it["status"] = "fail"
                it["note"] = (res.get("error") or "unknown")[:120]
                it["method"] = f"{method}_error"
            break


def _br_remove_item(key, mi, pi):
    """Remueve item del review (tras delete). Shift de pi>deleted para preservar
    apuntadores al catalog post-delete del mismo modelo."""
    items = st.session_state.get(key) or []
    remaining = [it for it in items if not (it["mi"] == mi and it["pi"] == pi)]
    for it in remaining:
        if it["mi"] == mi and it["pi"] > pi:
            it["pi"] -= 1
    st.session_state[key] = remaining


def _render_batch_review(fid):
    """Panel QA post-batch. Aparece tras _batch_clean_family, auto-expand.
    Muestra thumbnails con action buttons (reutiliza handlers del gallery
    editor). Default filter: FAIL+SKIP. Toggle 'Ver todas' para OK.
    Persiste en session_state hasta que user cierre con ✅."""
    key = f"batch_review_{fid}"
    items = st.session_state.get(key)
    if not items:
        return

    ok_n = sum(1 for it in items if it["status"] == "ok")
    fail_n = sum(1 for it in items if it["status"] == "fail")
    skip_n = sum(1 for it in items if it["status"] == "skip")
    attention_n = fail_n + skip_n

    with st.expander(
        f"🔍 QA Review Post-Batch · {len(items)} fotos "
        f"(✅ {ok_n} · ⚠️ {fail_n} FAIL · 🔍 {skip_n} SKIP)",
        expanded=True,
    ):
        cc1, cc2, cc3 = st.columns([2, 2, 1])
        with cc1:
            show_all = st.toggle(
                f"Ver todas ({len(items)}) · default: solo {attention_n} FAIL+SKIP",
                key=f"br_show_all_{fid}",
                value=False,
            )
        with cc2:
            st.caption(
                "⚠️ Auto = LaMa+OCR · 🎯 Force = mask centro · "
                "🧠 SD = Stable Diffusion · ↺ Restore backup · 🗑️ Delete"
            )
        with cc3:
            if st.button("✅ Cerrar review", key=f"br_close_{fid}",
                         use_container_width=True,
                         help="Cierra el panel. La lista se pierde, pero las fotos siguen en catalog."):
                st.session_state.pop(key, None)
                st.session_state.pop(f"br_show_all_{fid}", None)
                st.rerun()

        visible = items if show_all else [it for it in items if it["status"] in ("fail", "skip")]

        if not visible:
            st.success(
                "🎉 0 fotos FAIL/SKIP. El batch cubrió todo. "
                "Si querés revisar las OK por artefactos de LaMa, activá 'Ver todas'."
            )
            return

        import local_inpaint as _li
        lama_ok = _li.local_inpaint_available()
        sd_ok = _li.sd_available() if lama_ok else False
        gem_ok = audit_enrich.gemini_available()

        cols_per_row = 4
        for row_start in range(0, len(visible), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                idx = row_start + col_idx
                if idx >= len(visible):
                    break
                it = visible[idx]
                mi, pi, url = it["mi"], it["pi"], it["url"]
                status = it["status"]
                badge = {"ok": "✅", "fail": "⚠️", "skip": "🔍"}[status]
                with cols[col_idx]:
                    st.caption(f"{badge} m{mi} · #{pi + 1} · {it.get('method', '?')}")
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        st.caption("(img fail)")
                    note = (it.get("note") or "")[:80]
                    if note:
                        st.caption(note)

                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("⚠️", key=f"br_auto_{fid}_{mi}_{pi}",
                                     help="Re-run Auto (LaMa + OCR + template)",
                                     disabled=not lama_ok,
                                     use_container_width=True):
                            res = _regen_watermark(fid, mi, pi, mode="auto")
                            _br_update_item(key, mi, pi, res, "auto")
                            st.rerun()
                    with b2:
                        if st.button("🎯", key=f"br_force_{fid}_{mi}_{pi}",
                                     help="Force (mask hardcoded centro)",
                                     disabled=not lama_ok,
                                     use_container_width=True):
                            res = _regen_watermark(fid, mi, pi, mode="force")
                            _br_update_item(key, mi, pi, res, "force")
                            st.rerun()
                    with b3:
                        if st.button("🧠", key=f"br_sd_{fid}_{mi}_{pi}",
                                     help="SD Inpaint (preserva logos)",
                                     disabled=not sd_ok,
                                     use_container_width=True):
                            res = _regen_watermark(fid, mi, pi, mode="sd")
                            _br_update_item(key, mi, pi, res, "sd")
                            st.rerun()
                    with b4:
                        if st.button("🌟", key=f"br_gem_{fid}_{mi}_{pi}",
                                     help="Gemini Rescue — mejor para texturas complejas (~$0.04/foto)",
                                     disabled=not gem_ok,
                                     use_container_width=True):
                            res = _regen_watermark(fid, mi, pi, mode="gemini")
                            _br_update_item(key, mi, pi, res, "gemini")
                            st.rerun()

                    b5, b6 = st.columns(2)
                    with b5:
                        if st.button("↺ Original", key=f"br_restore_{fid}_{mi}_{pi}",
                                     help="Restore backup R2 (revierte al original pre-watermark)",
                                     use_container_width=True):
                            rr = _restore_r2_from_backup(fid, mi, pi)
                            if rr.get("ok"):
                                cat = _load_catalog_fresh()
                                fam_ = _find_fam(cat, fid)
                                try:
                                    new_url = fam_["modelos"][mi]["gallery"][pi]
                                except Exception:
                                    new_url = None
                                _br_update_item(key, mi, pi,
                                                {"ok": True, "new_url": new_url},
                                                "restored")
                            else:
                                st.error(rr.get("error", "restore fail"))
                            st.rerun()
                    with b6:
                        if st.button("🗑️ Delete", key=f"br_del_{fid}_{mi}_{pi}",
                                     help="Soft-delete (mueve a deleted_gallery)",
                                     use_container_width=True):
                            _gallery_delete(fid, mi, pi)
                            _br_remove_item(key, mi, pi)
                            st.toast(f"🗑 Foto m{mi} #{pi + 1} eliminada")
                            st.rerun()


def _set_primary_modelo(fid, new_idx):
    """Cambia primary_modelo_idx del family y re-syncea fam.gallery+hero."""
    catalog = _load_catalog_fresh()
    fam = _find_fam(catalog, fid)
    if not fam:
        return
    modelos = fam.get("modelos") or []
    if new_idx >= len(modelos):
        return
    fam["primary_modelo_idx"] = new_idx
    primary = modelos[new_idx]
    gal = primary.get("gallery") or []
    if gal:
        fam["gallery"] = list(gal)
        fam["hero_thumbnail"] = gal[0]
    _save_catalog(catalog)


def _sync_top_level_if_primary(fam, modelo_idx):
    """Si modelo_idx es primary, sync fam.gallery + fam.hero_thumbnail."""
    primary_idx = fam.get("primary_modelo_idx", 0) or 0
    if modelo_idx != primary_idx:
        return
    modelo = (fam.get("modelos") or [])[modelo_idx]
    gallery = modelo.get("gallery") or []
    fam["gallery"] = list(gallery)
    fam["hero_thumbnail"] = gallery[0] if gallery else None


# ═══════════════════════════════════════════════
# Catalog mutations
# ═══════════════════════════════════════════════

def _apply_family_updates(fid, updates):
    """Patch top-level fields de una family. Retorna lista de campos cambiados."""
    catalog_path = audit_db.CATALOG_PATH
    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"catalog.json no existe en {catalog_path}")
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    changed = []
    for fam in catalog:
        if fam.get("family_id") != fid:
            continue
        for key, new_val in updates.items():
            old_val = fam.get(key)
            if old_val != new_val:
                fam[key] = new_val
                changed.append(key)
        break

    if changed:
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return changed


def _apply_modelo_updates(fid, modelo_idx, updates):
    """Patch fields de un modelo específico."""
    catalog_path = audit_db.CATALOG_PATH
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    changed = []
    for fam in catalog:
        if fam.get("family_id") != fid:
            continue
        modelos = fam.get("modelos") or []
        if modelo_idx >= len(modelos):
            break
        m = modelos[modelo_idx]
        for key, new_val in updates.items():
            if m.get(key) != new_val:
                m[key] = new_val
                changed.append(key)
        break

    if changed:
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return changed


def _flip_published(fid, value, motivo=""):
    """Flip published=True/False. Registra timestamp + motivo."""
    catalog_path = audit_db.CATALOG_PATH
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    for fam in catalog:
        if fam.get("family_id") != fid:
            continue
        fam["published"] = bool(value)
        # Registrar meta
        if value:
            fam["republished_at"] = datetime.now().isoformat(timespec="seconds")
        else:
            fam["unpublished_at"] = datetime.now().isoformat(timespec="seconds")
        if motivo:
            fam["unpublish_motivo" if not value else "republish_motivo"] = motivo
        break
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _commit_and_push(fid):
    """Git add + commit + push del catalog.json. Mensaje referencia la family."""
    catalog_path = audit_db.CATALOG_PATH
    repo_dir = os.path.dirname(os.path.dirname(catalog_path))
    msg = f"publicados: update {fid}"
    try:
        subprocess.run(["git", "add", "data/catalog.json"],
                       cwd=repo_dir, capture_output=True, timeout=30)
        commit_res = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        # Si no hay cambios, commit_res.returncode = 1 (no error real)
        push_res = subprocess.run(
            ["git", "push"], cwd=repo_dir, capture_output=True, timeout=60,
        )
        if push_res.returncode == 0:
            return {"ok": True}
        return {"ok": False, "error": push_res.stderr.decode("utf-8", errors="ignore")[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
