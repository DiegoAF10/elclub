"""Vault Orders — sync + management for El Club Vault leads.

Syncs leads from the Cloudflare Worker (ventus-backoffice) into the local
SQLite `vault_orders` / `vault_order_items` / `vault_order_status_history`
tables, and exposes a Streamlit page for Diego to drive the state machine
and generate supplier WhatsApp messages.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════

WORKER_URL = os.environ.get(
    "VAULT_WORKER_URL",
    "https://ventus-backoffice.ventusgt.workers.dev",
).rstrip("/")

VAULT_FAMILY_IMG_BASE = os.environ.get(
    "VAULT_FAMILY_IMG_BASE",
    "https://vault.elclub.club/img/families",
).rstrip("/")

SUPPLIER_NUMBER = "8615361409693"
SUPPLIER_NAME = "Bond Soccer Jersey"

STATUS_TRANSITIONS = {
    "new": ["confirmed_with_client", "cancelled"],
    "confirmed_with_client": ["sent_to_supplier", "cancelled"],
    "sent_to_supplier": ["in_production", "cancelled"],
    "in_production": ["shipped", "cancelled"],
    "shipped": ["arrived_gt", "cancelled"],
    "arrived_gt": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

STATUS_LABELS = {
    "new": "🆕 Nueva",
    "confirmed_with_client": "✅ Confirmada con cliente",
    "sent_to_supplier": "📤 Enviada a proveedor",
    "in_production": "🏭 En producción",
    "shipped": "🚢 Embarcada",
    "arrived_gt": "🇬🇹 Llegó a GT",
    "delivered": "📦 Entregada",
    "cancelled": "❌ Cancelada",
}

VALID_VERSIONS = {"Fan", "Player", "Woman", "Baby", "Kid", "Retro"}


# ═══════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════

def _get_api_key() -> Optional[str]:
    """Resolve DASHBOARD_KEY from env or Streamlit session state."""
    env_key = os.environ.get("DASHBOARD_KEY")
    if env_key:
        return env_key.strip()
    return st.session_state.get("vault_dashboard_key")


def _auth_headers() -> dict:
    key = _get_api_key()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


# ═══════════════════════════════════════
# SUPPLIER MESSAGE HELPERS
# ═══════════════════════════════════════

def normalize_version(raw: Optional[str]) -> str:
    if not raw:
        return "Fan"
    capped = raw.strip()
    capped = capped[:1].upper() + capped[1:].lower()
    return capped if capped in VALID_VERSIONS else "Fan"


def format_supplier_message(item: dict) -> str:
    """Build the supplier WhatsApp message — English, exact format."""
    p = item.get("personalization") or {}
    name = (p.get("name") or "-").strip() or "-"
    number_raw = p.get("number")
    number = str(number_raw) if number_raw not in (None, "") else "-"
    patch = (p.get("patch") or "-").strip() or "-"
    size = (item.get("size") or "-").strip() or "-"
    version = normalize_version(item.get("version"))

    header_bits = [x for x in [item.get("team"), item.get("season"), item.get("variant_label")] if x]
    header = (" ".join(header_bits) + "\n") if header_bits else ""

    return (
        f"{header}"
        f"Name: {name}\n"
        f"Number: {number}\n"
        f"Patch: {patch}\n"
        f"Size: {size}\n"
        f"Version: {version}"
    )


def build_wa_link(message: str) -> str:
    return f"https://wa.me/{SUPPLIER_NUMBER}?text={urllib.parse.quote(message)}"


# ═══════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════

def _upsert_order(conn, lead: dict) -> None:
    """Insert or update a single order from a worker lead payload."""
    ref = lead.get("ref")
    if not ref:
        return

    cliente = lead.get("cliente") or {}
    envio = lead.get("envio") or {}
    pago = lead.get("pago") or {}

    conn.execute(
        """
        INSERT INTO vault_orders (
            ref, received_at, cliente_nombre, cliente_tel, cliente_email,
            envio_json, pago_metodo, total, status, notas, synced_at, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ref) DO UPDATE SET
            received_at    = excluded.received_at,
            cliente_nombre = excluded.cliente_nombre,
            cliente_tel    = excluded.cliente_tel,
            cliente_email  = excluded.cliente_email,
            envio_json     = excluded.envio_json,
            pago_metodo    = excluded.pago_metodo,
            total          = excluded.total,
            status         = excluded.status,
            notas          = excluded.notas,
            synced_at      = excluded.synced_at,
            raw_json       = excluded.raw_json
        """,
        (
            ref,
            lead.get("saved_at") or lead.get("timestamp"),
            cliente.get("nombre"),
            cliente.get("telefono"),
            cliente.get("email"),
            json.dumps(envio, ensure_ascii=False),
            pago.get("metodo"),
            lead.get("total"),
            lead.get("status") or "new",
            lead.get("notas"),
            datetime.utcnow().isoformat() + "Z",
            json.dumps(lead, ensure_ascii=False),
        ),
    )

    # Replace items — simplest + correct for idempotent sync
    conn.execute("DELETE FROM vault_order_items WHERE order_ref = ?", (ref,))
    productos = lead.get("productos") or []
    for item in productos:
        conn.execute(
            """
            INSERT INTO vault_order_items (
                order_ref, family_id, team, season, variant_label, version,
                size, personalization_json, total_price, fulfillment_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                ref,
                item.get("family_id"),
                item.get("team"),
                item.get("season"),
                item.get("variant_label"),
                normalize_version(item.get("version")),
                item.get("size"),
                json.dumps(item.get("personalization") or {}, ensure_ascii=False),
                item.get("total_price") or item.get("precio") or item.get("price"),
            ),
        )

    conn.commit()


def sync_from_worker(conn, limit: int = 200) -> dict:
    """Pull recent leads from the worker and upsert them. Returns counts."""
    key = _get_api_key()
    if not key:
        return {"ok": False, "error": "DASHBOARD_KEY no configurado (sidebar o env var)."}

    try:
        res = requests.get(
            f"{WORKER_URL}/api/vault/leads",
            params={"limit": limit},
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except requests.RequestException as err:
        return {"ok": False, "error": f"Error de red: {err}"}

    if res.status_code != 200:
        return {"ok": False, "error": f"Worker respondió {res.status_code}: {res.text[:200]}"}

    data = res.json()
    leads = data.get("leads") or []
    for lead in leads:
        _upsert_order(conn, lead)

    return {"ok": True, "count": len(leads)}


def list_orders(conn, status_filter: Optional[str] = None) -> list:
    if status_filter and status_filter != "all":
        rows = conn.execute(
            "SELECT * FROM vault_orders WHERE status = ? ORDER BY received_at DESC",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM vault_orders ORDER BY received_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_order(conn, ref: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM vault_orders WHERE ref = ?", (ref,)).fetchone()
    if not row:
        return None
    order = dict(row)
    items = conn.execute(
        "SELECT * FROM vault_order_items WHERE order_ref = ? ORDER BY item_id",
        (ref,),
    ).fetchall()
    order["items"] = [dict(i) for i in items]

    history = conn.execute(
        "SELECT * FROM vault_order_status_history WHERE order_ref = ? ORDER BY changed_at DESC",
        (ref,),
    ).fetchall()
    order["history"] = [dict(h) for h in history]

    return order


def change_status_remote(ref: str, new_status: str, note: Optional[str] = None, force: bool = False) -> dict:
    """PATCH the worker; returns parsed response dict."""
    key = _get_api_key()
    if not key:
        return {"ok": False, "error": "DASHBOARD_KEY no configurado."}

    try:
        res = requests.patch(
            f"{WORKER_URL}/api/vault/lead/{ref}/status",
            json={"status": new_status, "note": note, "force": force},
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except requests.RequestException as err:
        return {"ok": False, "error": f"Error de red: {err}"}

    try:
        payload = res.json()
    except ValueError:
        payload = {"ok": False, "error": res.text[:200]}

    if res.status_code >= 400 and "error" not in payload:
        payload = {"ok": False, "error": f"HTTP {res.status_code}"}
    return payload


def record_status_change_local(conn, ref: str, from_status: str, to_status: str, note: Optional[str]) -> None:
    conn.execute(
        """
        INSERT INTO vault_order_status_history (order_ref, from_status, to_status, changed_at, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ref, from_status, to_status, datetime.utcnow().isoformat() + "Z", note),
    )
    conn.execute("UPDATE vault_orders SET status = ? WHERE ref = ?", (to_status, ref))
    conn.commit()


def cross_reference_stock(conn, item: dict) -> Optional[dict]:
    """Check whether a matching jersey exists in local inventory (best-effort match)."""
    team = item.get("team")
    size = item.get("size")
    season = item.get("season")
    if not team or not size:
        return None

    row = conn.execute(
        """
        SELECT j.jersey_id, j.status
        FROM jerseys j
        JOIN teams t ON j.team_id = t.team_id
        WHERE (t.name = ? OR t.short_name = ?)
          AND j.size = ?
          AND (? IS NULL OR j.season = ?)
          AND j.status = 'available'
        LIMIT 1
        """,
        (team, team, size, season, season),
    ).fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════

def _render_auth_gate() -> bool:
    """Ensure DASHBOARD_KEY is available; prompt if missing. Return True if ready."""
    if _get_api_key():
        return True

    st.warning("Falta `DASHBOARD_KEY` para conectar con el Worker.")
    key = st.text_input(
        "Pegá tu DASHBOARD_KEY",
        type="password",
        key="vault_dashboard_key_input",
        help="Se guarda solo en esta sesión de Streamlit. Alternativa: export DASHBOARD_KEY en el .bat launcher.",
    )
    if key:
        st.session_state["vault_dashboard_key"] = key.strip()
        st.rerun()
    return False


def _render_sync_bar(conn) -> None:
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔄 Sync desde Worker", use_container_width=True):
            with st.spinner("Sincronizando..."):
                result = sync_from_worker(conn)
            if result.get("ok"):
                st.success(f"✓ {result['count']} leads sincronizados.")
            else:
                st.error(f"Error: {result.get('error')}")
    with col2:
        if st.button("🔑 Cambiar API key", use_container_width=True):
            st.session_state.pop("vault_dashboard_key", None)
            st.rerun()
    with col3:
        st.caption(f"Worker: `{WORKER_URL}`")


def _render_status_filter() -> str:
    options = ["all"] + list(STATUS_TRANSITIONS.keys())
    labels = {"all": "Todas"} | STATUS_LABELS
    return st.radio(
        "Filtrar por estado",
        options,
        format_func=lambda s: labels.get(s, s),
        horizontal=True,
        label_visibility="collapsed",
    )


def _render_order_list(orders: list) -> Optional[str]:
    if not orders:
        st.info("No hay pedidos para mostrar. Probá sincronizar.")
        return None

    # Build a compact table for quick scan + selection
    rows = []
    for o in orders:
        rows.append({
            "Ref": o["ref"],
            "Recibido": (o.get("received_at") or "")[:16].replace("T", " "),
            "Cliente": o.get("cliente_nombre") or "—",
            "Tel": o.get("cliente_tel") or "—",
            "Pago": o.get("pago_metodo") or "—",
            "Total": f"Q{o.get('total')}" if o.get("total") else "—",
            "Estado": STATUS_LABELS.get(o.get("status") or "new", o.get("status") or "—"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Selection via explicit selectbox (dataframe selection is fiddly)
    refs = [o["ref"] for o in orders]
    selected = st.selectbox(
        "Abrir pedido",
        [""] + refs,
        format_func=lambda r: r if r else "— seleccioná un ref —",
    )
    return selected or None


def _render_item_card(conn, ref: str, item: dict) -> None:
    with st.container(border=True):
        header_bits = [x for x in [item.get("team"), item.get("season"), item.get("variant_label")] if x]
        st.markdown(f"**{' · '.join(header_bits) if header_bits else '(sin datos de equipo)'}**")

        p = {}
        try:
            p = json.loads(item.get("personalization_json") or "{}")
        except json.JSONDecodeError:
            p = {}

        img_col, meta_col, msg_col = st.columns([1, 1, 2])
        with img_col:
            family_id = item.get("family_id")
            if family_id:
                st.image(
                    f"{VAULT_FAMILY_IMG_BASE}/{family_id}.jpg",
                    use_container_width=True,
                )
            else:
                st.caption("Sin imagen")
        with meta_col:
            st.caption(f"Talla {item.get('size') or '—'} · {item.get('version') or 'Fan'}")
            st.caption(f"Name: {p.get('name') or '—'}")
            st.caption(f"Number: {p.get('number') if p.get('number') not in (None, '') else '—'}")
            st.caption(f"Patch: {p.get('patch') or '—'}")
            if item.get("total_price"):
                st.caption(f"Precio: Q{item['total_price']}")

            # Stock cross-reference
            stock = cross_reference_stock(conn, {
                "team": item.get("team"),
                "size": item.get("size"),
                "season": item.get("season"),
            })
            if stock:
                st.success(f"🟢 EN STOCK — {stock['jersey_id']}")
            else:
                st.caption("🔴 No hay en inventario local")

        with msg_col:
            message = format_supplier_message({
                "team": item.get("team"),
                "season": item.get("season"),
                "variant_label": item.get("variant_label"),
                "size": item.get("size"),
                "version": item.get("version"),
                "personalization": p,
            })
            st.code(message, language=None)
            wa_link = build_wa_link(message)
            st.link_button(
                "📤 Enviar a proveedor (WhatsApp)",
                wa_link,
                use_container_width=True,
            )


def _render_status_controls(conn, order: dict) -> None:
    current = order.get("status") or "new"
    st.markdown(f"**Estado actual:** {STATUS_LABELS.get(current, current)}")

    next_options = STATUS_TRANSITIONS.get(current, [])
    if not next_options:
        st.caption("Este pedido está en estado terminal.")
        return

    cols = st.columns(len(next_options))
    for idx, target in enumerate(next_options):
        with cols[idx]:
            if st.button(
                f"→ {STATUS_LABELS.get(target, target)}",
                key=f"status_btn_{order['ref']}_{target}",
                use_container_width=True,
            ):
                with st.spinner("Actualizando..."):
                    result = change_status_remote(order["ref"], target)
                if result.get("ok"):
                    record_status_change_local(conn, order["ref"], current, target, None)
                    st.success(f"✓ {current} → {target}")
                    st.rerun()
                else:
                    st.error(f"No se pudo cambiar: {result.get('error')}")

    with st.expander("⚠️ Forzar cambio (ignorar state machine)"):
        all_statuses = list(STATUS_TRANSITIONS.keys())
        forced_target = st.selectbox(
            "Nuevo estado",
            all_statuses,
            index=all_statuses.index(current),
            key=f"forced_{order['ref']}",
        )
        note = st.text_input(
            "Nota (opcional)",
            key=f"forced_note_{order['ref']}",
        )
        if st.button("Forzar", key=f"forced_btn_{order['ref']}"):
            result = change_status_remote(order["ref"], forced_target, note=note or None, force=True)
            if result.get("ok"):
                record_status_change_local(conn, order["ref"], current, forced_target, note or None)
                st.success("✓ Estado forzado.")
                st.rerun()
            else:
                st.error(f"Error: {result.get('error')}")


def _render_order_detail(conn, order: dict) -> None:
    st.markdown(f"## 📋 {order['ref']}")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Cliente", order.get("cliente_nombre") or "—")
    col_b.metric("Total", f"Q{order.get('total')}" if order.get("total") else "—")
    col_c.metric("Pago", order.get("pago_metodo") or "—")

    # Contact + shipping
    with st.expander("📞 Contacto y envío", expanded=True):
        st.write(f"**Tel:** {order.get('cliente_tel') or '—'}")
        if order.get("cliente_email"):
            st.write(f"**Email:** {order['cliente_email']}")
        try:
            envio = json.loads(order.get("envio_json") or "{}")
        except json.JSONDecodeError:
            envio = {}
        st.write(f"**Modalidad:** {envio.get('modalidad') or '—'}")
        st.write(f"**Ubicación:** {envio.get('depto', '')} — {envio.get('municipio', '')}")
        st.write(f"**Dirección:** {envio.get('direccion') or '—'}")
        if envio.get("referencias"):
            st.caption(f"_Ref: {envio['referencias']}_")
        if order.get("notas"):
            st.caption(f"_Notas: {order['notas']}_")

    # Status controls
    st.markdown("---")
    _render_status_controls(conn, order)

    # Items
    st.markdown("---")
    st.markdown(f"### 🧾 Items ({len(order.get('items', []))})")
    for item in order.get("items", []):
        _render_item_card(conn, order["ref"], item)

    # History
    if order.get("history"):
        st.markdown("---")
        with st.expander("📜 Historial de estados"):
            for h in order["history"]:
                line = f"{h.get('changed_at', '')[:19].replace('T', ' ')} · {h.get('from_status')} → **{h.get('to_status')}**"
                if h.get("note"):
                    line += f" _({h['note']})_"
                st.markdown(line)


def render_page(conn) -> None:
    """Main entry called from app.py."""
    st.markdown("# 📦 Ordenes Vault")
    st.caption("Pedidos recibidos desde `vault.elclub.club` · sync desde el Worker → SQLite local")

    if not _render_auth_gate():
        return

    _render_sync_bar(conn)
    st.markdown("---")

    status_filter = _render_status_filter()
    orders = list_orders(conn, status_filter)

    st.caption(f"**{len(orders)}** pedido(s)")
    selected_ref = _render_order_list(orders)

    if selected_ref:
        st.markdown("---")
        order = get_order(conn, selected_ref)
        if order:
            _render_order_detail(conn, order)
        else:
            st.error("Pedido no encontrado en la DB local — probá sincronizar.")
