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

    cols_per_row = 4
    for row_start in range(0, len(gallery), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            p_idx = row_start + col_idx
            if p_idx >= len(gallery):
                break
            url = gallery[p_idx]
            with cols[col_idx]:
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


def _regen_watermark(fid, modelo_idx, photo_idx, mode="auto"):
    """Descarga foto de R2, pasa por inpaint (LaMa local o Gemini), sube
    resultado al mismo key + cache-bust URL en catalog.

    mode:
      "auto"  — OCR-based detection (default). Falla si OCR no detecta.
      "force" — mask hardcoded centro (dimensiones estándar Yupoo).
                Ignora OCR. Usar cuando Diego ve watermark pero OCR falla.
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

    # Watermark inpaint — modo auto (OCR+LaMa) o force (mask hardcoded).
    import local_inpaint as _li
    lama_ok = _li.local_inpaint_available()

    if mode == "force":
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
            return {"error": "OCR no detectó watermark. Probá con '🎯 Forzar' si ves uno."}
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
    backup_res = _backup_r2_before_overwrite(cur_url)
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

    return {"ok": True, "new_url": new_url}


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
