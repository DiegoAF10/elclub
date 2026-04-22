"""Comercial — Cross-channel sales tracking for El Club.

Modelo de venta en 2 ejes ortogonales:
  · modality:  mystery (Q350) · stock (vende camisa física) · ondemand (se ordena)
  · origin:    vault · catalogo · whatsapp · ads · ig · referral · walkin · directo

Sync-in idempotente desde vault_orders → sales (modality=ondemand, origin=vault).

Tablas: customers · sales · sale_items · sales_attribution
Views:  v_sales_by_day · v_cogs_by_day · v_top_skus
"""

from __future__ import annotations

import json
import os
from datetime import datetime, date, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

# ═══════════════════════════════════════
# CONFIG — landed costs GTQ
# Base factor: Q10/USD landed (incluye shipping/aduana).
# Diego Q110 fan ≈ $11 proveedor × 10 factor.
# ═══════════════════════════════════════

COST_DEFAULTS_GTQ = {
    "Fan":    110,   # $11
    "Player": 140,   # $14 Adidas default (Nike=150, Diego override)
    "Woman":  110,   # $11 (fan equivalent)
    "Retro":  160,   # $16
    "Kid":    130,   # $13 (kid set)
    "Baby":   110,   # $11
}

PERSONALIZATION_EXTRAS_GTQ = {
    "name": 10,
    "number": 10,
    "full": 30,      # full personalization package
    "patch": 10,
    "plus_size": 10, # 2XL / 3XL / 4XL
}

VERSION_OPTIONS = ["Fan", "Player", "Woman", "Retro", "Kid", "Baby"]

MODALITIES = ["mystery", "stock", "ondemand"]

MODALITY_LABELS = {
    "mystery":  "🎁 Mystery Box",
    "stock":    "📦 Stock actual",
    "ondemand": "🛠️ Pedido específico",
}

MODALITY_HELP = {
    "mystery":  "El cliente recibe una camisa sorpresa del stock. Precio fijo Q350.",
    "stock":    "Vende una camisa física del inventario. Precio libre por camisa.",
    "ondemand": "Pedido específico — se ordena al proveedor chino. Precio por canal.",
}

MODALITY_DEFAULT_PRICE_GTQ = {
    "mystery":  350,
    "stock":    400,  # default; Diego override per-item
    "ondemand": 425,  # default ondemand; vault=435, catalogo=450 si así lo marca origin
}

# Precios sugeridos según origin cuando modality=ondemand
ONDEMAND_ORIGIN_PRICE_GTQ = {
    "vault":    435,
    "catalogo": 450,
    "ads":      425,
    "whatsapp": 425,
    "ig":       425,
    "referral": 425,
    "walkin":   425,
    "directo":  425,
}

ORIGINS = ["vault", "catalogo", "whatsapp", "ads", "ig", "referral", "walkin", "f&f", "directo"]

ORIGIN_LABELS = {
    "vault":    "🏛️ Vault",
    "catalogo": "📇 Catálogo público",
    "whatsapp": "💬 WhatsApp directo",
    "ads":      "📣 Ads Meta",
    "ig":       "📷 Instagram orgánico",
    "referral": "🤝 Referido",
    "walkin":   "🚶 Walk-in",
    "f&f":      "👨‍👩‍👧 F&F (friends & family)",
    "directo":  "🧑 Directo (sin origen claro)",
}

PAYMENT_METHODS = ["contra_entrega", "transferencia", "recurrente", "efectivo", "otro"]

PAYMENT_LABELS = {
    "contra_entrega": "💵 Contra entrega",
    "transferencia":  "🏦 Transferencia",
    "recurrente":     "💳 Recurrente (tarjeta)",
    "efectivo":       "🧾 Efectivo",
    "otro":           "❓ Otro",
}

SHIPPING_METHODS = ["forza", "guatex", "in_person", "pickup", "otro"]

FULFILLMENT_STATUSES = ["pending", "sent_to_supplier", "in_production", "shipped", "delivered", "cancelled"]

FULFILLMENT_LABELS = {
    "pending":          "🟡 Pendiente",
    "sent_to_supplier": "📤 Enviado proveedor",
    "in_production":    "🏭 Producción",
    "shipped":          "🚢 Embarcado",
    "delivered":        "📦 Entregado",
    "cancelled":        "❌ Cancelado",
}

# "Ventas cerradas" = ya llegaron al cliente o están por entregarse.
# KPIs/revenue/COGS solo cuentan éstas.
CLOSED_STATUSES_SQL = "('shipped', 'delivered')"
PIPELINE_STATUSES_SQL = "('pending', 'sent_to_supplier', 'in_production')"

# Meta campaign ref (CAMPAIGN-STATUS.md)
AD_CAMPAIGNS = [
    ("120243340913290251", "Mystery Box Prueba Abril 26"),
    ("120243282439380251", "Catálogo El Club"),
    ("120243337946860251", "On Demand"),
    ("120243277635230251", "XDM - AG - WP (Legacy)"),
]

VAULT_TO_FULFILLMENT = {
    "new":                  "pending",
    "confirmed_with_client": "pending",
    "sent_to_supplier":     "sent_to_supplier",
    "in_production":        "in_production",
    "shipped":              "shipped",
    "arrived_gt":           "shipped",
    "delivered":            "delivered",
    "cancelled":            "cancelled",
}

PLUS_SIZES = {"2XL", "XXL", "3XL", "XXXL", "4XL", "XXXXL"}


# ═══════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════

def normalize_phone(raw: Optional[str]) -> str:
    """Guatemala phone: prepend 502 if 8-digit local number."""
    if not raw:
        return ""
    digits = "".join(c for c in str(raw) if c.isdigit())
    if len(digits) == 8:
        return "502" + digits
    if digits.startswith("00502"):
        return digits[2:]
    return digits


def compute_landed_cost_default(version: Optional[str], size: Optional[str] = None,
                                personalization: Optional[dict] = None) -> int:
    """Default landed cost in GTQ. Override manually per item if reality differs."""
    base = COST_DEFAULTS_GTQ.get(version or "Fan", 110)
    extras = 0
    if size and size.strip().upper() in PLUS_SIZES:
        extras += PERSONALIZATION_EXTRAS_GTQ["plus_size"]
    if personalization:
        has_name = bool((personalization.get("name") or "").strip())
        has_number = personalization.get("number") not in (None, "", 0)
        has_patch = bool((personalization.get("patch") or "").strip())
        if has_name and has_number:
            extras += PERSONALIZATION_EXTRAS_GTQ["full"]  # full package
        else:
            if has_name:
                extras += PERSONALIZATION_EXTRAS_GTQ["name"]
            if has_number:
                extras += PERSONALIZATION_EXTRAS_GTQ["number"]
        if has_patch:
            extras += PERSONALIZATION_EXTRAS_GTQ["patch"]
    return base + extras


def generate_sale_ref(conn, modality: str) -> str:
    prefix = {
        "mystery":  "MS",
        "stock":    "ST",
        "ondemand": "OD",
    }.get(modality, "MN")
    row = conn.execute(
        "SELECT ref FROM sales WHERE ref LIKE ? ORDER BY sale_id DESC LIMIT 1",
        (f"{prefix}-%",),
    ).fetchone()
    if row and row["ref"]:
        try:
            n = int(row["ref"].split("-")[1])
            return f"{prefix}-{n + 1:04d}"
        except (IndexError, ValueError):
            pass
    return f"{prefix}-0001"


# ═══════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════

def get_or_create_customer(conn, *, name: str, phone: Optional[str], email: Optional[str] = None,
                           source: Optional[str] = None, tags: Optional[list] = None,
                           notes: Optional[str] = None) -> int:
    phone_norm = normalize_phone(phone) if phone else ""
    if phone_norm:
        row = conn.execute(
            "SELECT customer_id, tags_json FROM customers WHERE phone = ?",
            (phone_norm,),
        ).fetchone()
        if row:
            # Merge tags non-destructively
            if tags:
                try:
                    existing = set(json.loads(row["tags_json"] or "[]"))
                except json.JSONDecodeError:
                    existing = set()
                existing.update(tags)
                conn.execute(
                    "UPDATE customers SET tags_json = ? WHERE customer_id = ?",
                    (json.dumps(sorted(existing)), row["customer_id"]),
                )
                conn.commit()
            return row["customer_id"]

    cur = conn.execute(
        """INSERT INTO customers (name, phone, email, tags_json, source, first_order_at, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name or "(sin nombre)", phone_norm or None, email,
         json.dumps(tags or []), source,
         datetime.utcnow().isoformat() + "Z", notes),
    )
    conn.commit()
    return cur.lastrowid


def list_customers(conn) -> list:
    rows = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════
# SALES — CRUD
# ═══════════════════════════════════════

def create_sale(conn, *, modality: str, origin: Optional[str], occurred_at: str,
                customer_id: Optional[int],
                payment_method: Optional[str], shipping_method: Optional[str],
                shipping_fee: int, discount: int, total: int,
                items: list, attribution: Optional[dict] = None,
                tracking_code: Optional[str] = None,
                source_vault_ref: Optional[str] = None,
                notes: Optional[str] = None,
                ref: Optional[str] = None,
                fulfillment_status: str = "pending") -> tuple:
    """Atomic insert of sale + items + attribution. Returns (sale_id, ref)."""
    if modality not in MODALITIES:
        raise ValueError(f"modality inválida: {modality}. Esperado: {MODALITIES}")

    sale_ref = ref or generate_sale_ref(conn, modality)

    # Mystery handling: items unit_price forced to 0, revenue lives on sale.total
    if modality == "mystery":
        for it in items:
            it["unit_price"] = 0

    subtotal = sum(int(it.get("unit_price") or 0) for it in items)
    # If mystery or items had no price, subtotal = total - shipping + discount
    if subtotal == 0 and total:
        subtotal = max(0, int(total) - int(shipping_fee or 0) + int(discount or 0))

    cur = conn.execute(
        """INSERT INTO sales (ref, occurred_at, modality, origin, customer_id, payment_method,
                              fulfillment_status, shipping_method, tracking_code,
                              subtotal, shipping_fee, discount, total,
                              source_vault_ref, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sale_ref, occurred_at, modality, origin, customer_id, payment_method,
         fulfillment_status, shipping_method, tracking_code,
         subtotal, int(shipping_fee or 0), int(discount or 0), int(total),
         source_vault_ref, notes),
    )
    sale_id = cur.lastrowid

    for it in items:
        conn.execute(
            """INSERT INTO sale_items (sale_id, family_id, jersey_id, team, season,
                                       variant_label, version, size,
                                       personalization_json, unit_price, unit_cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sale_id, it.get("family_id"), it.get("jersey_id"),
             it.get("team"), it.get("season"), it.get("variant_label"),
             it.get("version"), it.get("size"),
             json.dumps(it.get("personalization") or {}, ensure_ascii=False),
             int(it.get("unit_price") or 0),
             int(it["unit_cost"]) if it.get("unit_cost") is not None else None,
             it.get("notes")),
        )
        # Link to physical inventory if jersey_id provided
        if it.get("jersey_id"):
            conn.execute(
                "UPDATE jerseys SET status = 'sold' WHERE jersey_id = ? AND status != 'sold'",
                (it["jersey_id"],),
            )

    if attribution and (attribution.get("campaign_id") or attribution.get("source")):
        conn.execute(
            """INSERT INTO sales_attribution (sale_id, ad_campaign_id, ad_campaign_name, source, note)
               VALUES (?, ?, ?, ?, ?)""",
            (sale_id, attribution.get("campaign_id"),
             attribution.get("campaign_name"),
             attribution.get("source"), attribution.get("note")),
        )

    conn.commit()
    return sale_id, sale_ref


def update_fulfillment(conn, sale_id: int, status: str) -> None:
    conn.execute(
        "UPDATE sales SET fulfillment_status = ? WHERE sale_id = ?",
        (status, sale_id),
    )
    conn.commit()


def delete_sale(conn, sale_id: int) -> None:
    """Hard delete (cascade drops items + attribution)."""
    conn.execute("DELETE FROM sales WHERE sale_id = ?", (sale_id,))
    conn.commit()


# ═══════════════════════════════════════
# SYNC from vault_orders (idempotent)
# ═══════════════════════════════════════

def sync_vault_sales(conn) -> dict:
    """Insert a `sales` row for each vault_order not yet synced. Returns {created, skipped}."""
    unsynced = conn.execute(
        """SELECT vo.* FROM vault_orders vo
           WHERE NOT EXISTS (
               SELECT 1 FROM sales s WHERE s.source_vault_ref = vo.ref
           )
           ORDER BY vo.received_at ASC"""
    ).fetchall()

    created = 0
    errors = []
    for vo in unsynced:
        try:
            envio = json.loads(vo["envio_json"] or "{}") if vo["envio_json"] else {}
        except json.JSONDecodeError:
            envio = {}

        customer_id = get_or_create_customer(
            conn,
            name=vo["cliente_nombre"] or "(sin nombre)",
            phone=vo["cliente_tel"],
            email=vo["cliente_email"],
            source="vault",
            tags=["vault"],
        )

        items_rows = conn.execute(
            "SELECT * FROM vault_order_items WHERE order_ref = ?",
            (vo["ref"],),
        ).fetchall()

        items = []
        for ir in items_rows:
            try:
                pers = json.loads(ir["personalization_json"] or "{}")
            except json.JSONDecodeError:
                pers = {}
            items.append({
                "family_id": ir["family_id"],
                "team": ir["team"],
                "season": ir["season"],
                "variant_label": ir["variant_label"],
                "version": ir["version"],
                "size": ir["size"],
                "personalization": pers,
                "unit_price": ir["total_price"] or 0,
                "unit_cost": compute_landed_cost_default(ir["version"], ir["size"], pers),
            })

        fulfillment = VAULT_TO_FULFILLMENT.get(vo["status"] or "new", "pending")

        try:
            create_sale(
                conn,
                modality="ondemand",
                origin="vault",
                occurred_at=vo["received_at"] or datetime.utcnow().isoformat() + "Z",
                customer_id=customer_id,
                payment_method=vo["pago_metodo"],
                shipping_method=envio.get("modalidad"),
                shipping_fee=0,
                discount=0,
                total=vo["total"] or sum(it["unit_price"] for it in items),
                items=items,
                source_vault_ref=vo["ref"],
                notes=vo["notas"],
                ref=f"VO-{vo['ref']}",
                fulfillment_status=fulfillment,
            )
            created += 1
        except Exception as err:
            errors.append({"ref": vo["ref"], "error": str(err)})

    return {"ok": True, "created": created, "errors": errors}


# ═══════════════════════════════════════
# QUERIES for dashboard
# ═══════════════════════════════════════

def get_kpis(conn, date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict:
    """Return revenue, cogs, margin, n_sales, n_items, avg_ticket.

    Solo cuenta ventas cerradas (shipped/delivered). Pipeline y cancelled excluidos.
    """
    where = f"fulfillment_status IN {CLOSED_STATUSES_SQL}"
    params = []
    if date_from:
        where += " AND DATE(occurred_at) >= DATE(?)"
        params.append(date_from)
    if date_to:
        where += " AND DATE(occurred_at) <= DATE(?)"
        params.append(date_to)

    rev_row = conn.execute(
        f"SELECT COALESCE(SUM(total), 0) AS rev, COUNT(*) AS n FROM sales WHERE {where}",
        params,
    ).fetchone()
    revenue = rev_row["rev"] or 0
    n_sales = rev_row["n"] or 0

    cogs_row = conn.execute(
        f"""SELECT COALESCE(SUM(i.unit_cost), 0) AS cogs, COUNT(i.item_id) AS n_items
            FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
            WHERE {where.replace("occurred_at", "s.occurred_at").replace("fulfillment_status", "s.fulfillment_status")}""",
        params,
    ).fetchone()
    cogs = cogs_row["cogs"] or 0
    n_items = cogs_row["n_items"] or 0

    gross_margin = revenue - cogs
    margin_pct = (gross_margin / revenue * 100) if revenue else 0
    avg_ticket = (revenue / n_sales) if n_sales else 0

    return {
        "revenue": revenue,
        "cogs": cogs,
        "gross_margin": gross_margin,
        "margin_pct": margin_pct,
        "n_sales": n_sales,
        "n_items": n_items,
        "avg_ticket": avg_ticket,
    }


def get_pipeline_kpis(conn) -> dict:
    """Ventas en pipeline: pending + sent_to_supplier + in_production."""
    row = conn.execute(
        f"""SELECT
                COUNT(*) AS n_sales,
                COALESCE(SUM(total), 0) AS total_expected
            FROM sales WHERE fulfillment_status IN {PIPELINE_STATUSES_SQL}"""
    ).fetchone()
    items_row = conn.execute(
        f"""SELECT
                COUNT(i.item_id) AS n_items,
                COALESCE(SUM(i.unit_cost), 0) AS cost_committed
            FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
            WHERE s.fulfillment_status IN {PIPELINE_STATUSES_SQL}"""
    ).fetchone()
    return {
        "n_sales": row["n_sales"] or 0,
        "total_expected": row["total_expected"] or 0,
        "n_items": items_row["n_items"] or 0,
        "cost_committed": items_row["cost_committed"] or 0,
    }


# ═══════════════════════════════════════
# P&L — Estado de Resultados
# ═══════════════════════════════════════

def get_pnl(conn) -> dict:
    """Full P&L breakdown.

    - realized:   revenue/cogs de shipped/delivered (Cerradas)
    - pipeline:   revenue potencial + cost estimado en pipeline
    - sunken:     cost hundido (jerseys sold con venta cancelled)
    - internal:   consumo interno/regalos (total=0, con jersey linked o items con cost futuro)
    """
    # Realized (cerradas)
    realized = conn.execute(
        f"""SELECT
                COALESCE(SUM(s.total), 0) AS revenue,
                COUNT(DISTINCT s.sale_id) AS n_sales
            FROM sales s
            WHERE s.fulfillment_status IN {CLOSED_STATUSES_SQL}"""
    ).fetchone()
    realized_cogs = conn.execute(
        f"""SELECT COALESCE(SUM(i.unit_cost), 0) AS cogs
            FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
            WHERE s.fulfillment_status IN {CLOSED_STATUSES_SQL}"""
    ).fetchone()

    # Cash (cash basis)
    cash = conn.execute(
        """SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS n
           FROM sales
           WHERE payment_method IS NOT NULL AND fulfillment_status != 'cancelled'"""
    ).fetchone()
    pending = conn.execute(
        """SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS n
           FROM sales
           WHERE payment_method IS NULL AND fulfillment_status != 'cancelled'"""
    ).fetchone()

    # Pipeline (potencial si todo entrega)
    pipe = conn.execute(
        f"""SELECT COALESCE(SUM(s.total), 0) AS revenue,
                   COALESCE(SUM(i.unit_cost), 0) AS cost,
                   COUNT(DISTINCT s.sale_id) AS n
            FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
            WHERE s.fulfillment_status IN {PIPELINE_STATUSES_SQL}"""
    ).fetchone()

    # Sunken costs: items de sales cancelled con unit_cost > 0 o con jersey_id sold
    sunken_items = conn.execute(
        """SELECT COALESCE(SUM(i.unit_cost), 0) AS cost,
                  COUNT(DISTINCT s.sale_id) AS n
           FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
           WHERE s.fulfillment_status = 'cancelled' AND i.jersey_id IS NOT NULL"""
    ).fetchone()

    # Internal consumption: items de sales con total=0 non-cancelled
    internal = conn.execute(
        f"""SELECT COUNT(*) AS n,
                   COALESCE(SUM(i.unit_cost), 0) AS cost_realized
            FROM sales s JOIN sale_items i ON i.sale_id = s.sale_id
            WHERE s.total = 0 AND s.fulfillment_status != 'cancelled'"""
    ).fetchone()

    revenue = realized["revenue"] or 0
    cogs = realized_cogs["cogs"] or 0
    margin = revenue - cogs
    margin_pct = (margin / revenue * 100) if revenue else 0

    # Potential scenario (if all pipeline converts and closes)
    pipeline_revenue = pipe["revenue"] or 0
    pipeline_cost = pipe["cost"] or 0
    potential_revenue = revenue + pipeline_revenue
    potential_cost = cogs + pipeline_cost
    potential_margin = potential_revenue - potential_cost
    potential_margin_pct = (potential_margin / potential_revenue * 100) if potential_revenue else 0

    return {
        "realized_revenue": revenue,
        "realized_cogs": cogs,
        "realized_margin": margin,
        "realized_margin_pct": margin_pct,
        "realized_n_sales": realized["n_sales"] or 0,

        "cash_collected": cash["amount"] or 0,
        "cash_n": cash["n"] or 0,
        "pending_collection": pending["amount"] or 0,
        "pending_n": pending["n"] or 0,

        "pipeline_revenue": pipeline_revenue,
        "pipeline_cost": pipeline_cost,
        "pipeline_n": pipe["n"] or 0,

        "sunken_cost": sunken_items["cost"] or 0,
        "sunken_n": sunken_items["n"] or 0,

        "internal_n": internal["n"] or 0,
        "internal_cost_realized": internal["cost_realized"] or 0,

        "potential_revenue": potential_revenue,
        "potential_cost": potential_cost,
        "potential_margin": potential_margin,
        "potential_margin_pct": potential_margin_pct,
    }


def get_pnl_by_import(conn) -> pd.DataFrame:
    """P&L per import batch."""
    rows = conn.execute(
        f"""SELECT
                imp.import_id,
                imp.status,
                imp.total_landed_gtq,
                imp.n_units,
                imp.unit_cost AS q_unit,
                COUNT(DISTINCT i.sale_id) AS n_sales_linked,
                COALESCE(SUM(CASE WHEN s.fulfillment_status IN {CLOSED_STATUSES_SQL}
                                  THEN s.total ELSE 0 END), 0) AS revenue_realized,
                COALESCE(SUM(CASE WHEN s.payment_method IS NOT NULL
                                       AND s.fulfillment_status != 'cancelled'
                                  THEN s.total ELSE 0 END), 0) AS cash_collected,
                COALESCE(SUM(CASE WHEN s.fulfillment_status IN {CLOSED_STATUSES_SQL}
                                  THEN i.unit_cost ELSE 0 END), 0) AS cogs_realized,
                COALESCE(SUM(CASE WHEN s.fulfillment_status IN {PIPELINE_STATUSES_SQL}
                                  THEN s.total ELSE 0 END), 0) AS revenue_pipeline,
                COALESCE(SUM(CASE WHEN s.fulfillment_status IN {PIPELINE_STATUSES_SQL}
                                  THEN i.unit_cost ELSE 0 END), 0) AS cost_pipeline
            FROM imports imp
            LEFT JOIN sale_items i ON i.import_id = imp.import_id
            LEFT JOIN sales s ON i.sale_id = s.sale_id
            GROUP BY imp.import_id
            ORDER BY imp.paid_at DESC"""
    ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return df
    df["margen_realizado"] = df["revenue_realized"] - df["cogs_realized"]
    df["margen_potencial"] = (df["revenue_realized"] + df["revenue_pipeline"]) - (df["cogs_realized"] + df["cost_pipeline"])
    df["margen_pct"] = (df["margen_realizado"] / df["revenue_realized"] * 100).where(df["revenue_realized"] > 0, 0).round(1)
    return df


def get_cash_kpis(conn) -> dict:
    """Cash basis: plata que ya entró (payment_method NOT NULL) vs pendiente."""
    cash = conn.execute(
        """SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS n
           FROM sales
           WHERE payment_method IS NOT NULL AND fulfillment_status != 'cancelled'"""
    ).fetchone()
    pending = conn.execute(
        """SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS n
           FROM sales
           WHERE payment_method IS NULL AND fulfillment_status != 'cancelled'"""
    ).fetchone()
    return {
        "cash_n": cash["n"] or 0,
        "cash_amount": cash["amount"] or 0,
        "pending_n": pending["n"] or 0,
        "pending_amount": pending["amount"] or 0,
    }


# ═══════════════════════════════════════
# IMPORTS — batches de pedidos al proveedor
# ═══════════════════════════════════════

IMPORT_STATUSES = ["draft", "paid", "in_transit", "arrived", "closed", "cancelled"]

IMPORT_STATUS_LABELS = {
    "draft":      "📝 Borrador",
    "paid":       "💰 Pagada al proveedor",
    "in_transit": "✈️ En tránsito",
    "arrived":    "🇬🇹 Llegó a GT",
    "closed":     "✅ Cerrada (costos aplicados)",
    "cancelled":  "❌ Cancelada",
}


def create_import(conn, *, import_id: str, paid_at: Optional[str] = None,
                  arrived_at: Optional[str] = None, supplier: str = "Bond Soccer Jersey",
                  bruto_usd: Optional[float] = None, shipping_gtq: Optional[float] = None,
                  fx: float = 7.70, status: str = "in_transit",
                  notes: Optional[str] = None) -> str:
    """Create an import batch row. Returns import_id."""
    total_landed = None
    if bruto_usd is not None and shipping_gtq is not None:
        total_landed = bruto_usd * fx + shipping_gtq
    conn.execute(
        """INSERT INTO imports (import_id, paid_at, arrived_at, supplier,
                                bruto_usd, shipping_gtq, fx, total_landed_gtq,
                                status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(import_id) DO UPDATE SET
               paid_at = excluded.paid_at, arrived_at = excluded.arrived_at,
               supplier = excluded.supplier, bruto_usd = excluded.bruto_usd,
               shipping_gtq = excluded.shipping_gtq, fx = excluded.fx,
               total_landed_gtq = excluded.total_landed_gtq,
               status = excluded.status, notes = excluded.notes""",
        (import_id, paid_at, arrived_at, supplier,
         bruto_usd, shipping_gtq, fx, total_landed,
         status, notes),
    )
    conn.commit()
    _refresh_import_unit_cost(conn, import_id)
    return import_id


def _refresh_import_unit_cost(conn, import_id: str) -> None:
    """Recompute n_units + unit_cost from current items/jerseys."""
    n_items = conn.execute(
        "SELECT COUNT(*) FROM sale_items WHERE import_id = ?", (import_id,)
    ).fetchone()[0]
    n_jerseys = conn.execute(
        "SELECT COUNT(*) FROM jerseys WHERE import_id = ?", (import_id,)
    ).fetchone()[0]
    n_total = n_items + n_jerseys
    row = conn.execute(
        "SELECT total_landed_gtq FROM imports WHERE import_id = ?", (import_id,)
    ).fetchone()
    landed = row["total_landed_gtq"] if row else None
    unit_cost = round(landed / n_total) if (landed and n_total) else None
    conn.execute(
        "UPDATE imports SET n_units = ?, unit_cost = ? WHERE import_id = ?",
        (n_total, unit_cost, import_id),
    )
    conn.commit()


def close_import(conn, import_id: str) -> dict:
    """Finalize: prorrateo unit_cost to all items + jerseys linked, mark closed."""
    row = conn.execute(
        "SELECT total_landed_gtq FROM imports WHERE import_id = ?", (import_id,)
    ).fetchone()
    if not row or not row["total_landed_gtq"]:
        return {"ok": False, "error": "Import sin total_landed_gtq."}

    _refresh_import_unit_cost(conn, import_id)
    row = conn.execute(
        "SELECT unit_cost FROM imports WHERE import_id = ?", (import_id,)
    ).fetchone()
    unit_cost = row["unit_cost"]
    if not unit_cost:
        return {"ok": False, "error": "No hay units linked."}

    n_items = conn.execute(
        "UPDATE sale_items SET unit_cost = ? WHERE import_id = ?",
        (unit_cost, import_id),
    ).rowcount
    n_jerseys = conn.execute(
        "UPDATE jerseys SET cost = ? WHERE import_id = ?",
        (unit_cost, import_id),
    ).rowcount
    conn.execute(
        "UPDATE imports SET status = 'closed' WHERE import_id = ?", (import_id,)
    )
    conn.commit()
    return {"ok": True, "n_items": n_items, "n_jerseys": n_jerseys, "unit_cost": unit_cost}


def list_imports(conn) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT i.*,
                  (SELECT COUNT(*) FROM sale_items WHERE import_id = i.import_id) AS n_sale_items,
                  (SELECT COUNT(*) FROM jerseys    WHERE import_id = i.import_id) AS n_jerseys
           FROM imports i ORDER BY COALESCE(i.paid_at, i.created_at) DESC"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_import_items_df(conn, import_id: str) -> pd.DataFrame:
    """Build the editable data_editor DataFrame for an import."""
    rows = conn.execute(
        """SELECT s.ref AS ref,
                  i.item_id,
                  s.sale_id,
                  i.item_type,
                  i.team, i.season, i.variant_label, i.version, i.size,
                  i.personalization_json,
                  c.name AS customer, c.phone AS phone,
                  s.total, s.payment_method, s.fulfillment_status,
                  s.notes AS sale_notes, i.notes AS item_notes
           FROM sale_items i
           JOIN sales s ON i.sale_id = s.sale_id
           LEFT JOIN customers c ON s.customer_id = c.customer_id
           WHERE i.import_id = ?
           ORDER BY s.ref""",
        (import_id,),
    ).fetchall()
    records = []
    for r in rows:
        r = dict(r)
        pers = {}
        try:
            pers = json.loads(r["personalization_json"] or "{}")
        except json.JSONDecodeError:
            pass
        records.append({
            "ref": r["ref"],
            "item_type": r["item_type"] or "jersey",
            "team": r["team"] or "",
            "variant": r["variant_label"] or "home",
            "version": r["version"] or "Fan",
            "size": r["size"] or "",
            "pers_name": pers.get("name") or "",
            "pers_number": pers.get("number") or "",
            "customer": r["customer"] or "",
            "phone": r["phone"] or "",
            "total_Q": int(r["total"] or 0),
            "paid": bool(r["payment_method"]),
            "status": r["fulfillment_status"] or "pending",
            "notes": r["item_notes"] or r["sale_notes"] or "",
            "_item_id": r["item_id"],
            "_sale_id": r["sale_id"],
        })
    return pd.DataFrame(records)


def apply_import_edits(conn, import_id: str, edited_df: pd.DataFrame) -> dict:
    """Apply data_editor changes to DB. Returns summary."""
    updated_sales = 0
    updated_items = 0
    new_customers = 0

    for _, row in edited_df.iterrows():
        item_id = row.get("_item_id")
        sale_id = row.get("_sale_id")
        if pd.isna(item_id) or pd.isna(sale_id):
            continue

        # Resolve or create customer
        cust_name = str(row.get("customer") or "").strip()
        cust_phone = str(row.get("phone") or "").strip() or None
        customer_id = None
        if cust_name:
            # Check existing
            existing = conn.execute(
                "SELECT customer_id FROM customers WHERE name = ?", (cust_name,)
            ).fetchone()
            if existing:
                customer_id = existing["customer_id"]
                if cust_phone:
                    conn.execute(
                        "UPDATE customers SET phone = ? WHERE customer_id = ? AND (phone IS NULL OR phone = '')",
                        (normalize_phone(cust_phone), customer_id),
                    )
            else:
                customer_id = get_or_create_customer(
                    conn, name=cust_name, phone=cust_phone, source="f&f", tags=["f&f"],
                )
                new_customers += 1

        # Update sale
        paid = bool(row.get("paid"))
        payment = "transferencia" if paid else None
        total = int(row.get("total_Q") or 0)
        status = str(row.get("status") or "pending")

        conn.execute(
            """UPDATE sales
               SET customer_id = ?, total = ?, payment_method = ?, fulfillment_status = ?
               WHERE sale_id = ?""",
            (customer_id, total, payment, status, int(sale_id)),
        )
        updated_sales += 1

        # Update item
        pers = {
            "name": str(row.get("pers_name") or "").strip() or None,
            "number": row.get("pers_number") if row.get("pers_number") not in (None, "", 0) else None,
        }
        conn.execute(
            """UPDATE sale_items
               SET item_type = ?, team = ?, variant_label = ?, version = ?, size = ?,
                   personalization_json = ?, notes = ?
               WHERE item_id = ?""",
            (
                str(row.get("item_type") or "jersey"),
                str(row.get("team") or ""),
                str(row.get("variant") or "home"),
                str(row.get("version") or "Fan"),
                str(row.get("size") or ""),
                json.dumps({k: v for k, v in pers.items() if v}, ensure_ascii=False),
                str(row.get("notes") or "") or None,
                int(item_id),
            ),
        )
        updated_items += 1

    conn.commit()
    # Clean up any now-orphan placeholder customers
    conn.execute(
        """DELETE FROM customers
           WHERE name LIKE 'F&F Pre-order%'
             AND NOT EXISTS (SELECT 1 FROM sales WHERE sales.customer_id = customers.customer_id)"""
    )
    conn.commit()
    return {
        "updated_sales": updated_sales,
        "updated_items": updated_items,
        "new_customers": new_customers,
    }


def apply_batch_cost_prorrateo(conn, *, ref_prefix: str, bruto_usd: float,
                               shipping_gtq: float, fx: float = 7.70,
                               extra_jersey_ids: Optional[list] = None,
                               include_cancelled: bool = False) -> dict:
    """Prorratear costo del batch uniformemente entre sale_items matching + jerseys extras.

    Retorna dict con {n_items, n_jerseys, unit_cost, total_landed}.
    """
    where_cancel = "" if include_cancelled else " AND s.fulfillment_status != 'cancelled'"
    item_rows = conn.execute(
        f"""SELECT i.item_id
            FROM sale_items i JOIN sales s ON i.sale_id = s.sale_id
            WHERE s.ref LIKE ?{where_cancel}""",
        (f"{ref_prefix}%",),
    ).fetchall()
    n_items = len(item_rows)

    extra_jersey_ids = extra_jersey_ids or []
    jersey_rows = []
    if extra_jersey_ids:
        qs = ",".join("?" * len(extra_jersey_ids))
        jersey_rows = conn.execute(
            f"SELECT jersey_id FROM jerseys WHERE jersey_id IN ({qs})",
            extra_jersey_ids,
        ).fetchall()
    n_jerseys = len(jersey_rows)

    total_units = n_items + n_jerseys
    if total_units == 0:
        return {"n_items": 0, "n_jerseys": 0, "unit_cost": 0, "total_landed": 0}

    total_landed = bruto_usd * fx + shipping_gtq
    unit_cost = round(total_landed / total_units)

    if n_items:
        conn.execute(
            f"""UPDATE sale_items SET unit_cost = ?
                WHERE item_id IN (
                    SELECT i.item_id FROM sale_items i JOIN sales s ON i.sale_id = s.sale_id
                    WHERE s.ref LIKE ?{where_cancel}
                )""",
            (unit_cost, f"{ref_prefix}%"),
        )
    if n_jerseys:
        qs = ",".join("?" * len(extra_jersey_ids))
        conn.execute(
            f"UPDATE jerseys SET cost = ? WHERE jersey_id IN ({qs})",
            [unit_cost] + list(extra_jersey_ids),
        )
    conn.commit()

    return {
        "n_items": n_items,
        "n_jerseys": n_jerseys,
        "unit_cost": unit_cost,
        "total_landed": total_landed,
    }


def get_modality_mix(conn) -> pd.DataFrame:
    rows = conn.execute(
        f"""SELECT modality, COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS n_sales
            FROM sales WHERE fulfillment_status IN {CLOSED_STATUSES_SQL}
            GROUP BY modality ORDER BY revenue DESC"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_origin_mix(conn) -> pd.DataFrame:
    rows = conn.execute(
        f"""SELECT COALESCE(origin, 'sin_origen') AS origin,
                   COALESCE(SUM(total), 0) AS revenue,
                   COUNT(*) AS n_sales
            FROM sales WHERE fulfillment_status IN {CLOSED_STATUSES_SQL}
            GROUP BY origin ORDER BY revenue DESC"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_revenue_timeline(conn) -> pd.DataFrame:
    rows = conn.execute(
        f"""SELECT DATE(occurred_at) AS day, modality, COALESCE(SUM(total), 0) AS revenue
            FROM sales WHERE fulfillment_status IN {CLOSED_STATUSES_SQL}
            GROUP BY DATE(occurred_at), modality
            ORDER BY day"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_available_jerseys(conn) -> list:
    """Return jerseys from physical inventory that are available for sale.

    Note: `jerseys` table has `variant` (home/away/...) but no `version` column.
    We infer version='Fan' as default since most stock is fan-tier.
    """
    rows = conn.execute(
        """SELECT j.jersey_id, t.name AS team, j.season, j.variant,
                  'Fan' AS version,
                  j.size, j.player_name, j.player_number, j.patches,
                  j.cost, j.price, j.tier
           FROM jerseys j
           JOIN teams t ON j.team_id = t.team_id
           WHERE j.status = 'available'
           ORDER BY t.name, j.season, j.size"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_skus(conn, limit: int = 10) -> pd.DataFrame:
    """Top SKUs of closed sales only."""
    rows = conn.execute(
        f"""SELECT i.team, i.season, i.variant_label, i.version,
                   COUNT(*) AS units_sold,
                   SUM(COALESCE(i.unit_price, 0)) AS revenue_from_items,
                   SUM(COALESCE(i.unit_cost, 0)) AS cogs
            FROM sale_items i
            JOIN sales s ON i.sale_id = s.sale_id
            WHERE s.fulfillment_status IN {CLOSED_STATUSES_SQL}
            GROUP BY i.team, i.season, i.variant_label, i.version
            ORDER BY units_sold DESC
            LIMIT {int(limit)}"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_cac_by_campaign(conn) -> pd.DataFrame:
    """Attribution counts per campaign. Spend column stays NULL until Meta API integration v2."""
    rows = conn.execute(
        f"""SELECT a.ad_campaign_id, a.ad_campaign_name,
                   COUNT(DISTINCT a.sale_id) AS n_attributed_sales,
                   COALESCE(SUM(s.total), 0) AS revenue_attributed
            FROM sales_attribution a
            JOIN sales s ON s.sale_id = a.sale_id
            WHERE s.fulfillment_status IN {CLOSED_STATUSES_SQL}
              AND a.ad_campaign_id IS NOT NULL
            GROUP BY a.ad_campaign_id, a.ad_campaign_name
            ORDER BY n_attributed_sales DESC"""
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def list_sales(conn, modality: Optional[str] = None,
               origin: Optional[str] = None,
               date_from: Optional[str] = None,
               date_to: Optional[str] = None,
               customer_id: Optional[int] = None) -> pd.DataFrame:
    sql = """SELECT s.sale_id, s.ref, s.occurred_at, s.modality, s.origin,
                    c.name AS cliente, c.phone AS telefono,
                    s.payment_method, s.total, s.fulfillment_status,
                    s.shipping_method, s.tracking_code,
                    (SELECT COUNT(*) FROM sale_items WHERE sale_id = s.sale_id) AS n_items
             FROM sales s
             LEFT JOIN customers c ON s.customer_id = c.customer_id
             WHERE 1=1"""
    params = []
    if modality and modality != "all":
        sql += " AND s.modality = ?"
        params.append(modality)
    if origin and origin != "all":
        sql += " AND s.origin = ?"
        params.append(origin)
    if date_from:
        sql += " AND DATE(s.occurred_at) >= DATE(?)"
        params.append(date_from)
    if date_to:
        sql += " AND DATE(s.occurred_at) <= DATE(?)"
        params.append(date_to)
    if customer_id:
        sql += " AND s.customer_id = ?"
        params.append(customer_id)
    sql += " ORDER BY s.occurred_at DESC, s.sale_id DESC"
    rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_teams_list(conn) -> list:
    rows = conn.execute("SELECT name FROM teams ORDER BY name").fetchall()
    return [r[0] for r in rows]


# ═══════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════

def render_page(conn) -> None:
    st.markdown("# 💰 Comercial")
    st.caption("Tracking central de ventas · TODO El Club · mystery · stock · ondemand")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Registrar venta",
        "📊 Dashboard",
        "📜 Histórico",
        "📦 Importaciones",
    ])
    with tab1:
        _render_registrar_tab(conn)
    with tab2:
        _render_dashboard_tab(conn)
    with tab3:
        _render_historico_tab(conn)
    with tab4:
        _render_importaciones_tab(conn)


# ─── Tab 4: Importaciones ─────────────────────────

def _render_importaciones_tab(conn):
    st.markdown("### 📦 Importaciones al proveedor")
    st.caption("Cada importación agrupa un pedido con N unidades. "
               "Editás las filas en la tabla → guardás cambios → cerrás la importación cuando tengas los costos finales.")

    # Lista de imports
    df_imports = list_imports(conn)
    if df_imports.empty:
        st.info("No hay importaciones. Usá el botón abajo para crear una.")
    else:
        display = df_imports.copy()
        display["status_label"] = display["status"].map(lambda s: IMPORT_STATUS_LABELS.get(s, s))
        display["total_landed_gtq"] = display["total_landed_gtq"].apply(
            lambda q: f"Q{q:,.0f}" if pd.notna(q) else "—"
        )
        display["unit_cost"] = display["unit_cost"].apply(
            lambda q: f"Q{q:,.0f}" if pd.notna(q) else "—"
        )
        display["bruto_usd"] = display["bruto_usd"].apply(
            lambda q: f"${q:,.2f}" if pd.notna(q) else "—"
        )
        display["shipping_gtq"] = display["shipping_gtq"].apply(
            lambda q: f"Q{q:,.0f}" if pd.notna(q) else "—"
        )
        display = display[[
            "import_id", "paid_at", "arrived_at", "status_label",
            "bruto_usd", "shipping_gtq", "total_landed_gtq",
            "n_units", "unit_cost", "n_sale_items", "n_jerseys",
        ]]
        display.columns = ["ID", "Pagada", "Llegó a GT", "Status",
                           "Bruto USD", "Shipping GTQ", "Total landed",
                           "Units", "Q/unit", "# items (sales)", "# jerseys (stock)"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")
    # Selector para abrir una importación
    import_ids = df_imports["import_id"].tolist() if not df_imports.empty else []
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_import = st.selectbox(
            "Abrir importación para editar items",
            [""] + import_ids,
            format_func=lambda x: x or "— seleccioná —",
        )
    with col2:
        with st.popover("➕ Nueva importación", use_container_width=True):
            _render_new_import_form(conn)

    if selected_import:
        st.markdown("---")
        _render_import_detail(conn, selected_import)


def _render_new_import_form(conn):
    st.markdown("### Nueva importación")
    new_id = st.text_input("Import ID (ej. `IMP-2026-05-15`)", key="new_imp_id")
    new_paid = st.date_input("Fecha pago proveedor", value=date.today(), key="new_imp_paid")
    col1, col2 = st.columns(2)
    with col1:
        new_bruto = st.number_input("Bruto USD (opcional)", min_value=0.0, step=10.0,
                                    value=0.0, key="new_imp_bruto")
    with col2:
        new_ship = st.number_input("Shipping GTQ (opcional)", min_value=0.0, step=10.0,
                                   value=0.0, key="new_imp_ship")
    new_fx = st.number_input("FX", value=7.70, step=0.05, format="%.2f", key="new_imp_fx")
    new_notes = st.text_area("Notas", key="new_imp_notes")

    if st.button("Crear", type="primary", key="new_imp_create"):
        if not new_id.strip():
            st.error("Import ID requerido.")
            return
        create_import(
            conn,
            import_id=new_id.strip(),
            paid_at=new_paid.isoformat(),
            bruto_usd=new_bruto if new_bruto > 0 else None,
            shipping_gtq=new_ship if new_ship > 0 else None,
            fx=new_fx,
            status="paid",
            notes=new_notes or None,
        )
        st.success(f"✓ Creada {new_id}")
        st.rerun()


def _render_import_detail(conn, import_id: str):
    row = conn.execute(
        "SELECT * FROM imports WHERE import_id = ?", (import_id,)
    ).fetchone()
    if not row:
        st.error("Importación no encontrada.")
        return
    imp = dict(row)

    st.markdown(f"## {import_id}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", IMPORT_STATUS_LABELS.get(imp["status"], imp["status"]))
    c2.metric("Units", imp["n_units"] or 0)
    c3.metric("Total landed",
              f"Q{imp['total_landed_gtq']:,.0f}" if imp["total_landed_gtq"] else "—")
    c4.metric("Q/unit", f"Q{imp['unit_cost']:,.0f}" if imp["unit_cost"] else "—")

    # Metadata editor (expander)
    with st.expander("⚙️ Metadata de la importación"):
        col1, col2 = st.columns(2)
        with col1:
            e_paid = st.date_input(
                "Fecha pago", key=f"e_paid_{import_id}",
                value=date.fromisoformat(imp["paid_at"]) if imp["paid_at"] else date.today(),
            )
            e_bruto = st.number_input(
                "Bruto USD", key=f"e_bruto_{import_id}",
                min_value=0.0, step=10.0, format="%.2f",
                value=float(imp["bruto_usd"] or 0),
            )
            e_fx = st.number_input(
                "FX", key=f"e_fx_{import_id}",
                value=float(imp["fx"] or 7.70), step=0.05, format="%.2f",
            )
        with col2:
            e_arrived = st.date_input(
                "Fecha llegada GT", key=f"e_arr_{import_id}",
                value=date.fromisoformat(imp["arrived_at"]) if imp["arrived_at"] else None,
            )
            e_ship = st.number_input(
                "Shipping GTQ", key=f"e_ship_{import_id}",
                min_value=0.0, step=10.0, format="%.2f",
                value=float(imp["shipping_gtq"] or 0),
            )
            e_status = st.selectbox(
                "Status", IMPORT_STATUSES, key=f"e_status_{import_id}",
                index=IMPORT_STATUSES.index(imp["status"]),
                format_func=lambda s: IMPORT_STATUS_LABELS[s],
            )
        e_notes = st.text_area("Notas", key=f"e_notes_{import_id}",
                               value=imp["notes"] or "")
        if st.button("💾 Guardar metadata", key=f"btn_meta_{import_id}"):
            create_import(
                conn, import_id=import_id,
                paid_at=e_paid.isoformat() if e_paid else None,
                arrived_at=e_arrived.isoformat() if e_arrived else None,
                bruto_usd=e_bruto if e_bruto > 0 else None,
                shipping_gtq=e_ship if e_ship > 0 else None,
                fx=e_fx, status=e_status, notes=e_notes or None,
            )
            st.success("✓ Metadata actualizada.")
            st.rerun()

    # Data editor con los items
    st.markdown("#### 🧾 Items (editar directamente)")
    st.caption("Editá cada fila → click «Guardar cambios» al final. "
               "Si cambiás `customer`, el cliente se crea automáticamente. "
               "El tick `paid` se mapea a `payment_method=transferencia`.")

    df = get_import_items_df(conn, import_id)
    if df.empty:
        st.warning("Esta importación no tiene items. Agregalos desde «Registrar venta» con ref manual `{import_id}-NNN`.")
        return

    edited = st.data_editor(
        df,
        key=f"editor_{import_id}",
        use_container_width=True,
        num_rows="fixed",  # fixed para no permitir delete/add desde acá (evita confusión)
        column_config={
            "ref": st.column_config.TextColumn("Ref", disabled=True, width="small"),
            "item_type": st.column_config.SelectboxColumn(
                "Tipo",
                options=["jersey", "jacket", "hat", "shorts", "socks", "set"],
                width="small",
            ),
            "team": st.column_config.TextColumn("Equipo", width="medium"),
            "variant": st.column_config.SelectboxColumn(
                "Variant",
                options=["home", "away", "third", "special", "retro-home", "retro-away"],
                width="small",
            ),
            "version": st.column_config.SelectboxColumn(
                "Version",
                options=["Fan", "Player", "Women Fan", "Retro", "Kid", "Baby"],
                width="small",
            ),
            "size": st.column_config.TextColumn("Talla", width="small"),
            "pers_name": st.column_config.TextColumn("Nombre camisa", width="medium"),
            "pers_number": st.column_config.TextColumn("Número", width="small"),
            "customer": st.column_config.TextColumn("Cliente", width="medium"),
            "phone": st.column_config.TextColumn("Tel", width="small"),
            "total_Q": st.column_config.NumberColumn("Total Q", min_value=0, step=10),
            "paid": st.column_config.CheckboxColumn("Pagado"),
            "status": st.column_config.SelectboxColumn(
                "Fulfillment",
                options=FULFILLMENT_STATUSES,
                width="small",
            ),
            "notes": st.column_config.TextColumn("Notas", width="large"),
            "_item_id": None,  # hide
            "_sale_id": None,  # hide
        },
        column_order=["ref", "team", "size", "version", "variant",
                      "pers_name", "pers_number", "customer", "phone",
                      "total_Q", "paid", "status", "item_type", "notes"],
    )

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("💾 Guardar cambios", type="primary",
                     key=f"save_{import_id}", use_container_width=True):
            result = apply_import_edits(conn, import_id, edited)
            _refresh_import_unit_cost(conn, import_id)
            st.success(
                f"✓ {result['updated_sales']} sales + {result['updated_items']} items actualizados · "
                f"{result['new_customers']} customers nuevos creados."
            )
            st.rerun()

    with col2:
        # Close import (apply prorrateo)
        can_close = imp["total_landed_gtq"] is not None and imp["status"] != "closed"
        if st.button(
            "🔒 Cerrar (aplicar prorrateo)",
            key=f"close_{import_id}",
            disabled=not can_close,
            use_container_width=True,
            help="Aplica unit_cost prorrateado a todos los items + jerseys linkeados, marca status=closed.",
        ):
            res = close_import(conn, import_id)
            if res.get("ok"):
                st.success(
                    f"✓ Cerrada. {res['n_items']} items + {res['n_jerseys']} jerseys → Q{res['unit_cost']}/unit."
                )
                st.rerun()
            else:
                st.error(res.get("error"))

    with col3:
        st.caption(f"Editado en Streamlit data_editor. "
                   f"Para agregar items a esta importación: creá venta manual en tab «Registrar» con origin `f&f`.")


# ─── Tab 1: Registrar venta ─────────────────────────

def _ensure_items_state():
    if "comercial_items" not in st.session_state:
        st.session_state.comercial_items = [_empty_item()]


def _empty_item() -> dict:
    return {
        "team": "",
        "season": "",
        "variant_label": "home",
        "version": "Fan",
        "size": "M",
        "pers_name": "",
        "pers_number": "",
        "pers_patch": "",
        "unit_price": 0,
        "unit_cost": 110,
        "family_id": "",
        "jersey_id": "",
    }


def _render_sync_banner(conn):
    n_pending = conn.execute(
        """SELECT COUNT(*) FROM vault_orders vo
           WHERE NOT EXISTS (SELECT 1 FROM sales s WHERE s.source_vault_ref = vo.ref)"""
    ).fetchone()[0]

    col1, col2 = st.columns([2, 1])
    with col1:
        if n_pending:
            st.info(f"🔄 Hay **{n_pending}** pedido(s) del vault sin sincronizar a Comercial.")
        else:
            st.caption("✅ Sin pedidos del vault pendientes de sync.")
    with col2:
        if st.button("🔄 Sync desde Vault", use_container_width=True, disabled=(n_pending == 0)):
            with st.spinner("Sincronizando..."):
                res = sync_vault_sales(conn)
            st.success(f"✓ {res['created']} venta(s) creada(s).")
            if res.get("errors"):
                st.error(f"Errores: {res['errors']}")
            st.rerun()


def _render_registrar_tab(conn):
    _render_sync_banner(conn)
    st.markdown("---")
    _ensure_items_state()

    # ─── MODALIDAD (selección primaria, fuera del form para que cambie la UI) ───
    st.markdown("### 🎯 Modalidad de venta")
    c1, c2, c3 = st.columns(3)
    current = st.session_state.get("comercial_modality", "mystery")
    with c1:
        if st.button(
            f"{MODALITY_LABELS['mystery']}\nQ{MODALITY_DEFAULT_PRICE_GTQ['mystery']}",
            use_container_width=True,
            type="primary" if current == "mystery" else "secondary",
            key="btn_mod_mystery",
        ):
            st.session_state.comercial_modality = "mystery"
            st.rerun()
    with c2:
        if st.button(
            f"{MODALITY_LABELS['stock']}\nInventario físico",
            use_container_width=True,
            type="primary" if current == "stock" else "secondary",
            key="btn_mod_stock",
        ):
            st.session_state.comercial_modality = "stock"
            st.rerun()
    with c3:
        if st.button(
            f"{MODALITY_LABELS['ondemand']}\nSe ordena al proveedor",
            use_container_width=True,
            type="primary" if current == "ondemand" else "secondary",
            key="btn_mod_ondemand",
        ):
            st.session_state.comercial_modality = "ondemand"
            st.rerun()

    modality = st.session_state.get("comercial_modality", "mystery")
    st.caption(f"ℹ️ {MODALITY_HELP[modality]}")
    st.markdown("---")

    # ─── Dispatch a la función específica por modalidad ───
    if modality == "mystery":
        _render_form_mystery(conn)
    elif modality == "stock":
        _render_form_stock(conn)
    elif modality == "ondemand":
        _render_form_ondemand(conn)


# ─── Shared partials ─────────────────────────

def _render_origin_picker(default_idx: int = 8) -> str:
    origin = st.selectbox(
        "Origen (de dónde vino el cliente)",
        ORIGINS,
        index=default_idx,
        format_func=lambda o: ORIGIN_LABELS[o],
    )
    return origin


def _render_customer_section():
    st.markdown("### 👤 Cliente")
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        cust_name = st.text_input("Nombre*", placeholder="Eswin")
    with c2:
        cust_phone = st.text_input("Teléfono", placeholder="5555-1234")
    with c3:
        cust_email = st.text_input("Email", placeholder="(opcional)")
    c1, c2 = st.columns(2)
    with c1:
        tag_opts = st.multiselect("Tags", ["first", "repeat", "ads", "f&f", "walkin", "vip"])
    with c2:
        customer_source = st.selectbox(
            "Source del cliente (canal de adquisición)",
            ["", "ads_meta", "ig_organic", "whatsapp", "referral", "walkin", "f&f"],
        )
    return {
        "name": cust_name.strip(),
        "phone": cust_phone.strip() or None,
        "email": cust_email.strip() or None,
        "tags": tag_opts,
        "source": customer_source or None,
    }


def _render_payment_section():
    st.markdown("### 💳 Pago y envío")
    c1, c2, c3 = st.columns(3)
    with c1:
        payment = st.selectbox("Pago", PAYMENT_METHODS, format_func=lambda p: PAYMENT_LABELS[p])
    with c2:
        shipping_method = st.selectbox("Envío", SHIPPING_METHODS)
    with c3:
        tracking = st.text_input("Tracking", placeholder="ej. Forza guide #")
    c1, c2 = st.columns(2)
    with c1:
        shipping_fee = st.number_input("Costo envío (Q)", min_value=0, step=5, value=0)
    with c2:
        discount = st.number_input("Descuento (Q)", min_value=0, step=5, value=0)
    fulfillment = st.selectbox(
        "Estado fulfillment", FULFILLMENT_STATUSES,
        format_func=lambda s: FULFILLMENT_LABELS[s],
    )
    return {
        "payment_method": payment,
        "shipping_method": shipping_method,
        "tracking_code": tracking or None,
        "shipping_fee": int(shipping_fee),
        "discount": int(discount),
        "fulfillment_status": fulfillment,
    }


def _render_attribution_section(origin: str, default_campaign_for_modality: Optional[str] = None):
    st.markdown("### 📈 Attribution (opcional)")
    attr_on = st.checkbox("Venía de ad Meta", value=(origin == "ads"))
    campaign_selected = ""
    if attr_on:
        # Smart default campaign picker based on modality
        options = [""] + [f"{cid} — {name}" for cid, name in AD_CAMPAIGNS]
        default_idx = 0
        if default_campaign_for_modality:
            for i, (cid, _) in enumerate(AD_CAMPAIGNS):
                if cid == default_campaign_for_modality:
                    default_idx = i + 1
                    break
        campaign_selected = st.selectbox("Campaña", options, index=default_idx)
    if not attr_on:
        return None
    attribution = {"source": "meta_ads"}
    if campaign_selected:
        cid = campaign_selected.split(" — ")[0]
        cname = campaign_selected.split(" — ", 1)[1] if " — " in campaign_selected else ""
        attribution["campaign_id"] = cid
        attribution["campaign_name"] = cname
    return attribution


def _resolve_customer(conn, cust: dict) -> Optional[int]:
    if not cust["name"]:
        return None
    return get_or_create_customer(
        conn,
        name=cust["name"],
        phone=cust["phone"],
        email=cust["email"],
        source=cust["source"],
        tags=cust["tags"] or None,
    )


# ─── Form: MYSTERY BOX ─────────────────────────

def _render_form_mystery(conn):
    st.markdown("### 🎁 Mystery Box — detalles")
    c1, c2, c3 = st.columns(3)
    with c1:
        occurred_date = st.date_input("Fecha venta", value=date.today(), key="my_date")
    with c2:
        origin = _render_origin_picker()
    with c3:
        ref_input = st.text_input("Ref (vacío = auto MS-XXXX)", key="my_ref")

    cust = _render_customer_section()
    pay = _render_payment_section()

    st.markdown("### 🧾 Camisa(s) que salieron del stock (opcional)")
    st.caption("Podés link a jerseys del inventario para trackear el costo real. "
               "Si no linkás, ingresás estimado de costo abajo.")

    available = get_available_jerseys(conn)
    jersey_options = ["(no linkar)"] + [
        f"{j['jersey_id']} · {j['team']} {j['season']} {j['variant']} {j['size']} · {j['version'] or 'Fan'} · costo Q{j['cost'] or 110}"
        for j in available
    ]
    selected_jerseys = st.multiselect(
        "Link a jerseys del inventario",
        jersey_options[1:],
        key="my_jerseys",
    )

    # Manual cost if no jerseys linked
    total_cost_manual = 0
    if not selected_jerseys:
        total_cost_manual = st.number_input(
            "Costo landed total estimado (Q)",
            min_value=0, step=10, value=220,
            help="Default: Q220 = 2 camisas Fan × Q110. Ajustá según salió.",
        )

    attribution = _render_attribution_section(
        origin,
        default_campaign_for_modality="120243340913290251",  # Mystery Box Apr 26
    )

    st.markdown("### 💰 Total cobrado")
    total = st.number_input(
        "TOTAL cobrado al cliente (Q)",
        min_value=0, step=5,
        value=MODALITY_DEFAULT_PRICE_GTQ["mystery"],
        help="Mystery Box estándar: Q350. Items se registran con unit_price=0.",
    )
    notes = st.text_area("Notas", placeholder="Ej. sacó Napoli + PSG · cliente eligió packaging premium")

    if st.button("💾 GUARDAR MYSTERY BOX", type="primary", use_container_width=True, key="my_save"):
        if not cust["name"]:
            st.error("Nombre de cliente requerido.")
            return

        customer_id = _resolve_customer(conn, cust)

        items_payload = []
        if selected_jerseys:
            # Re-lookup from available list
            for sel in selected_jerseys:
                jid = sel.split(" · ")[0]
                j = next((x for x in available if x["jersey_id"] == jid), None)
                if j:
                    items_payload.append({
                        "jersey_id": j["jersey_id"],
                        "team": j["team"],
                        "season": j["season"],
                        "variant_label": j["variant"],
                        "version": j["version"] or "Fan",
                        "size": j["size"],
                        "personalization": {},
                        "unit_price": 0,  # mystery enforces this anyway
                        "unit_cost": int(j["cost"] or 110),
                    })
        else:
            # Single synthetic item with aggregated cost, so margin is computable
            items_payload.append({
                "team": "(mystery)", "season": "", "variant_label": "mystery",
                "version": "Fan", "size": "",
                "personalization": {},
                "unit_price": 0,
                "unit_cost": int(total_cost_manual),
                "notes": "Synthetic mystery box item — costo agregado",
            })

        try:
            sid, saved_ref = create_sale(
                conn,
                modality="mystery",
                origin=origin,
                occurred_at=occurred_date.isoformat(),
                customer_id=customer_id,
                payment_method=pay["payment_method"],
                shipping_method=pay["shipping_method"],
                shipping_fee=pay["shipping_fee"],
                discount=pay["discount"],
                total=int(total),
                items=items_payload,
                attribution=attribution,
                tracking_code=pay["tracking_code"],
                notes=notes or None,
                ref=ref_input.strip() or None,
                fulfillment_status=pay["fulfillment_status"],
            )
            st.success(f"✅ Mystery Box guardada: **{saved_ref}** (sale_id={sid})")
        except Exception as err:
            st.error(f"Error: {err}")


# ─── Form: STOCK ─────────────────────────

def _render_form_stock(conn):
    st.markdown("### 📦 Stock — detalles")
    c1, c2, c3 = st.columns(3)
    with c1:
        occurred_date = st.date_input("Fecha venta", value=date.today(), key="st_date")
    with c2:
        origin = _render_origin_picker()
    with c3:
        ref_input = st.text_input("Ref (vacío = auto ST-XXXX)", key="st_ref")

    cust = _render_customer_section()
    pay = _render_payment_section()

    st.markdown("### 🧾 Camisa(s) del inventario físico")
    available = get_available_jerseys(conn)
    if not available:
        st.warning("No hay jerseys `available` en el inventario. "
                   "Registrá inventario en la página «Registrar Camiseta».")
        return

    st.caption(f"**{len(available)}** camisas disponibles en stock.")
    jersey_options = [
        f"{j['jersey_id']} · {j['team']} {j['season']} {j['variant']} {j['size']} · {j['version'] or 'Fan'}"
        for j in available
    ]
    selected_labels = st.multiselect("Seleccionar camisas", jersey_options, key="st_jerseys")

    if not selected_labels:
        st.info("Seleccioná al menos una camisa.")
        return

    items_payload = []
    st.markdown("#### Precio y costo por camisa")
    total_subtotal = 0
    for label in selected_labels:
        jid = label.split(" · ")[0]
        j = next((x for x in available if x["jersey_id"] == jid), None)
        if not j:
            continue
        with st.container(border=True):
            default_price = int(j["price"] or MODALITY_DEFAULT_PRICE_GTQ["stock"])
            default_cost = int(j["cost"] or compute_landed_cost_default(
                j["version"] or "Fan", j["size"], {}
            ))
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"**{jid}** · {j['team']} {j['season']} "
                            f"{j['variant']} {j['size']} {j['version'] or 'Fan'}")
                if j.get("player_name") or j.get("player_number"):
                    st.caption(f"Jugador: {j.get('player_name') or ''} "
                               f"#{j.get('player_number') or ''}")
            with c2:
                price = st.number_input(f"Precio {jid}", min_value=0, step=5,
                                        value=default_price, key=f"stp_{jid}")
            with c3:
                cost = st.number_input(f"Costo {jid}", min_value=0, step=5,
                                       value=default_cost, key=f"stc_{jid}")
            items_payload.append({
                "jersey_id": jid,
                "team": j["team"],
                "season": j["season"],
                "variant_label": j["variant"],
                "version": j["version"] or "Fan",
                "size": j["size"],
                "personalization": {
                    "name": j.get("player_name") or None,
                    "number": j.get("player_number"),
                    "patch": j.get("patches") or None,
                },
                "unit_price": int(price),
                "unit_cost": int(cost),
            })
            total_subtotal += int(price)

    attribution = _render_attribution_section(origin)

    st.markdown("### 💰 Total")
    default_total = total_subtotal + pay["shipping_fee"] - pay["discount"]
    total = st.number_input("TOTAL cobrado (Q)", min_value=0, step=5,
                            value=int(default_total), key="st_total")
    notes = st.text_area("Notas", key="st_notes")

    if st.button("💾 GUARDAR VENTA DE STOCK", type="primary",
                 use_container_width=True, key="st_save"):
        if not cust["name"]:
            st.error("Nombre de cliente requerido.")
            return
        customer_id = _resolve_customer(conn, cust)
        try:
            sid, saved_ref = create_sale(
                conn,
                modality="stock",
                origin=origin,
                occurred_at=occurred_date.isoformat(),
                customer_id=customer_id,
                payment_method=pay["payment_method"],
                shipping_method=pay["shipping_method"],
                shipping_fee=pay["shipping_fee"],
                discount=pay["discount"],
                total=int(total),
                items=items_payload,
                attribution=attribution,
                tracking_code=pay["tracking_code"],
                notes=notes or None,
                ref=ref_input.strip() or None,
                fulfillment_status=pay["fulfillment_status"],
            )
            st.success(f"✅ Venta de stock guardada: **{saved_ref}** · "
                       f"{len(items_payload)} camisa(s) marcadas `sold`.")
        except Exception as err:
            st.error(f"Error: {err}")


# ─── Form: ONDEMAND ─────────────────────────

def _render_form_ondemand(conn):
    st.markdown("### 🛠️ Pedido específico — detalles")
    c1, c2, c3 = st.columns(3)
    with c1:
        occurred_date = st.date_input("Fecha venta", value=date.today(), key="od_date")
    with c2:
        origin = _render_origin_picker()
    with c3:
        ref_input = st.text_input("Ref (vacío = auto OD-XXXX · ej. CE-JTZZ)", key="od_ref")

    cust = _render_customer_section()
    pay = _render_payment_section()

    st.markdown("### 🧾 Items (cada camisa que se ordena al proveedor)")
    teams = get_teams_list(conn)
    seasons = ["2005/06", "2006/07", "2007/08", "2008/09", "2009/10", "2010/11", "2011/12",
               "2012/13", "2013/14", "2014/15", "2015/16", "2016/17", "2017/18", "2018/19",
               "2019/20", "2020/21", "2021/22", "2022/23", "2023/24", "2024/25", "2025/26",
               "2026/27", "Mundial 2026", "1986", "1998", "2002", "Retro-otro"]
    sizes = ["XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL",
             "Kids-S", "Kids-M", "Kids-L", "Baby"]
    variants = ["home", "away", "third", "special", "retro-home", "retro-away",
                "player-version"]

    items_to_render = st.session_state.comercial_items
    default_price = ONDEMAND_ORIGIN_PRICE_GTQ.get(origin, 425)

    for idx, it in enumerate(items_to_render):
        with st.container(border=True):
            st.markdown(f"**Ítem {idx + 1}**")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                it["team"] = st.selectbox(
                    f"Team #{idx + 1}", [""] + teams,
                    index=(teams.index(it["team"]) + 1) if it["team"] in teams else 0,
                    key=f"od_team_{idx}",
                )
            with c2:
                it["season"] = st.selectbox(
                    f"Season #{idx + 1}", seasons,
                    index=seasons.index(it["season"]) if it["season"] in seasons else 20,
                    key=f"od_season_{idx}",
                )
            with c3:
                it["variant_label"] = st.selectbox(
                    f"Variant #{idx + 1}", variants,
                    index=variants.index(it["variant_label"]) if it["variant_label"] in variants else 0,
                    key=f"od_variant_{idx}",
                )
            c1, c2, c3 = st.columns(3)
            with c1:
                it["version"] = st.selectbox(
                    f"Versión #{idx + 1}", VERSION_OPTIONS,
                    index=VERSION_OPTIONS.index(it["version"]) if it["version"] in VERSION_OPTIONS else 0,
                    key=f"od_version_{idx}",
                )
            with c2:
                it["size"] = st.selectbox(
                    f"Talla #{idx + 1}", sizes,
                    index=sizes.index(it["size"]) if it["size"] in sizes else 2,
                    key=f"od_size_{idx}",
                )
            with c3:
                it["family_id"] = st.text_input(
                    f"family_id #{idx + 1}",
                    value=it["family_id"], key=f"od_family_{idx}",
                    placeholder="opcional",
                )

            c1, c2, c3 = st.columns(3)
            with c1:
                it["pers_name"] = st.text_input(f"Nombre #{idx + 1}",
                                                value=it["pers_name"], key=f"od_pname_{idx}")
            with c2:
                it["pers_number"] = st.text_input(f"Número #{idx + 1}",
                                                  value=it["pers_number"], key=f"od_pnum_{idx}")
            with c3:
                it["pers_patch"] = st.text_input(f"Patch #{idx + 1}",
                                                 value=it["pers_patch"], key=f"od_ppatch_{idx}")

            pers_preview = {"name": it["pers_name"], "number": it["pers_number"],
                            "patch": it["pers_patch"]}
            computed_cost = compute_landed_cost_default(it["version"], it["size"], pers_preview)

            c1, c2, c3 = st.columns(3)
            with c1:
                it["unit_price"] = st.number_input(
                    f"Precio venta #{idx + 1} (Q)", min_value=0, step=5,
                    value=int(it.get("unit_price") or default_price),
                    key=f"od_price_{idx}",
                    help=f"Sugerido por origin ({origin}): Q{default_price}",
                )
            with c2:
                it["unit_cost"] = st.number_input(
                    f"Costo landed #{idx + 1} (Q)", min_value=0, step=5,
                    value=int(it.get("unit_cost") or computed_cost),
                    key=f"od_cost_{idx}",
                    help=f"Default auto: Q{computed_cost}",
                )
            with c3:
                margin = max(0, int(it["unit_price"] or 0) - int(it["unit_cost"] or 0))
                st.metric("Margen", f"Q{margin}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Agregar otro ítem", use_container_width=True, key="od_add"):
            st.session_state.comercial_items.append(_empty_item())
            st.rerun()
    with c2:
        if st.button("🗑️ Quitar último", use_container_width=True, key="od_rm"):
            if len(st.session_state.comercial_items) > 1:
                st.session_state.comercial_items.pop()
                st.rerun()

    attribution = _render_attribution_section(origin)

    st.markdown("### 💰 Total")
    subtotal = sum(int(it.get("unit_price") or 0) for it in items_to_render)
    default_total = subtotal + pay["shipping_fee"] - pay["discount"]
    total = st.number_input("TOTAL cobrado (Q)", min_value=0, step=5,
                            value=int(default_total), key="od_total")
    notes = st.text_area("Notas", key="od_notes")

    if st.button("💾 GUARDAR PEDIDO ESPECÍFICO", type="primary",
                 use_container_width=True, key="od_save"):
        if not cust["name"]:
            st.error("Nombre de cliente requerido.")
            return
        if not any(it.get("team") for it in items_to_render):
            st.error("Al menos un ítem con team requerido.")
            return
        customer_id = _resolve_customer(conn, cust)

        items_payload = []
        for it in items_to_render:
            if not it.get("team"):
                continue
            items_payload.append({
                "family_id": it["family_id"] or None,
                "team": it["team"], "season": it["season"],
                "variant_label": it["variant_label"],
                "version": it["version"], "size": it["size"],
                "personalization": {
                    "name": it["pers_name"] or None,
                    "number": it["pers_number"] or None,
                    "patch": it["pers_patch"] or None,
                },
                "unit_price": int(it["unit_price"] or 0),
                "unit_cost": int(it["unit_cost"] or 0),
            })
        try:
            sid, saved_ref = create_sale(
                conn,
                modality="ondemand",
                origin=origin,
                occurred_at=occurred_date.isoformat(),
                customer_id=customer_id,
                payment_method=pay["payment_method"],
                shipping_method=pay["shipping_method"],
                shipping_fee=pay["shipping_fee"],
                discount=pay["discount"],
                total=int(total),
                items=items_payload,
                attribution=attribution,
                tracking_code=pay["tracking_code"],
                notes=notes or None,
                ref=ref_input.strip() or None,
                fulfillment_status=pay["fulfillment_status"],
            )
            st.success(f"✅ Pedido específico guardado: **{saved_ref}** (sale_id={sid})")
            st.session_state.comercial_items = [_empty_item()]
        except Exception as err:
            st.error(f"Error: {err}")


# ─── Tab 2: Dashboard ─────────────────────────

def _render_dashboard_tab(conn):
    st.markdown("### Periodo")
    c1, c2, c3 = st.columns(3)
    with c1:
        preset = st.selectbox("Rango", ["Todo", "Últimos 7d", "Últimos 30d",
                                        "Últimos 90d", "Este mes", "YTD"])
    today = date.today()
    if preset == "Últimos 7d":
        date_from, date_to = today - timedelta(days=7), today
    elif preset == "Últimos 30d":
        date_from, date_to = today - timedelta(days=30), today
    elif preset == "Últimos 90d":
        date_from, date_to = today - timedelta(days=90), today
    elif preset == "Este mes":
        date_from, date_to = today.replace(day=1), today
    elif preset == "YTD":
        date_from, date_to = today.replace(month=1, day=1), today
    else:
        date_from = date_to = None

    kpis = get_kpis(conn,
                    date_from.isoformat() if date_from else None,
                    date_to.isoformat() if date_to else None)

    st.caption("KPIs cuentan solo ventas cerradas (shipped/delivered). Pipeline abajo.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Revenue", f"Q{kpis['revenue']:,}")
    c2.metric("📈 Margen bruto", f"Q{kpis['gross_margin']:,}",
              f"{kpis['margin_pct']:.1f}%")
    c3.metric("🛒 # Ventas cerradas", f"{kpis['n_sales']}",
              f"{kpis['n_items']} ítems")
    c4.metric("🎟️ Ticket prom.", f"Q{kpis['avg_ticket']:,.0f}")

    # Cash basis panel
    cash = get_cash_kpis(conn)
    st.markdown("#### 💵 Cash basis (plata en cuenta)")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("💰 Cash en cuenta", f"Q{cash['cash_amount']:,}",
               f"{cash['cash_n']} ventas pagadas")
    cc2.metric("⏳ Por cobrar", f"Q{cash['pending_amount']:,}",
               f"{cash['pending_n']} pendientes", delta_color="inverse")
    total_expected = cash["cash_amount"] + cash["pending_amount"]
    collection_rate = (cash["cash_amount"] / total_expected * 100) if total_expected else 0
    cc3.metric("Tasa de cobro", f"{collection_rate:.0f}%",
               f"Q{total_expected:,} facturado")

    # Pipeline panel
    pipe = get_pipeline_kpis(conn)
    if pipe["n_sales"] > 0:
        st.markdown("#### 🔄 Pipeline (pending · sent · in_production)")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Pedidos en vuelo", pipe["n_sales"])
        p2.metric("Revenue esperado", f"Q{pipe['total_expected']:,}")
        p3.metric("Items", pipe["n_items"])
        p4.metric("Costo comprometido", f"Q{pipe['cost_committed']:,}")

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎯 Mix por modalidad")
        mix = get_modality_mix(conn)
        if mix.empty:
            st.info("Sin data aún.")
        else:
            mix["label"] = mix["modality"].map(lambda c: MODALITY_LABELS.get(c, c))
            fig = px.pie(mix, values="revenue", names="label", hole=0.4)
            fig.update_layout(showlegend=True, height=350,
                              margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("#### 🌐 Mix por origen")
        omix = get_origin_mix(conn)
        if omix.empty:
            st.info("Sin data aún.")
        else:
            omix["label"] = omix["origin"].map(
                lambda c: ORIGIN_LABELS.get(c, c) if c != "sin_origen" else "❓ Sin origen"
            )
            fig = px.pie(omix, values="revenue", names="label", hole=0.4)
            fig.update_layout(showlegend=True, height=350,
                              margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 📅 Revenue por día (stacked por modalidad)")
    tl = get_revenue_timeline(conn)
    if tl.empty:
        st.info("Sin data aún.")
    else:
        tl["label"] = tl["modality"].map(lambda c: MODALITY_LABELS.get(c, c))
        fig = px.bar(tl, x="day", y="revenue", color="label",
                     labels={"day": "Día", "revenue": "Q"})
        fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10),
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 🏆 Top SKUs")
    top = get_top_skus(conn, limit=15)
    if top.empty:
        st.info("Sin ventas registradas.")
    else:
        st.dataframe(top, use_container_width=True, hide_index=True)

    st.markdown("#### 📣 Attribution a campañas Meta")
    cac = get_cac_by_campaign(conn)
    if cac.empty:
        st.caption("Ninguna venta con attribution a campaña. Tildar al registrar → se acumula acá.")
    else:
        st.dataframe(cac, use_container_width=True, hide_index=True)

    # ═══ Estado de Resultados ═══
    st.markdown("---")
    st.markdown("## 📈 Estado de Resultados")
    pnl = get_pnl(conn)

    st.markdown("### 💰 Ingresos")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("Revenue cerrado",
              f"Q{pnl['realized_revenue']:,}",
              f"{pnl['realized_n_sales']} sales delivered")
    i2.metric("Cash real en cuenta",
              f"Q{pnl['cash_collected']:,}",
              f"{pnl['cash_n']} pagadas")
    i3.metric("Por cobrar",
              f"Q{pnl['pending_collection']:,}",
              f"{pnl['pending_n']} pendientes", delta_color="inverse")
    i4.metric("Pipeline expected",
              f"Q{pnl['pipeline_revenue']:,}",
              f"{pnl['pipeline_n']} pedidos")

    st.markdown("### 💸 COGS (Costo de Mercadería)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("COGS realizado", f"Q{pnl['realized_cogs']:,}")
    c2.metric("Cost pipeline (estimado)", f"Q{pnl['pipeline_cost']:,}")
    c3.metric("Sunken cost",
              f"Q{pnl['sunken_cost']:,}",
              f"{pnl['sunken_n']} ventas fallidas",
              delta_color="inverse")
    c4.metric("Consumo interno",
              f"Q{pnl['internal_cost_realized']:,}",
              f"{pnl['internal_n']} items Q0")

    st.markdown("### 🎯 Margen Bruto")
    m1, m2, m3 = st.columns(3)
    m1.metric("Margen realizado",
              f"Q{pnl['realized_margin']:,}",
              f"{pnl['realized_margin_pct']:.1f}%")
    m2.metric("Margen potencial (si todo entrega + cobra)",
              f"Q{pnl['potential_margin']:,}",
              f"{pnl['potential_margin_pct']:.1f}%")
    # Riesgo de no cobrar
    at_risk = pnl["pending_collection"] + pnl["pipeline_revenue"]
    m3.metric("En riesgo (por cobrar + pipeline)",
              f"Q{at_risk:,}",
              delta_color="inverse")

    st.markdown("### 📦 P&L por importación")
    df_imp = get_pnl_by_import(conn)
    if df_imp.empty:
        st.info("Sin importaciones registradas.")
    else:
        display = df_imp.copy()
        display["status"] = display["status"].map(lambda s: IMPORT_STATUS_LABELS.get(s, s))
        for col in ["total_landed_gtq", "q_unit", "revenue_realized", "cash_collected",
                    "cogs_realized", "revenue_pipeline", "cost_pipeline",
                    "margen_realizado", "margen_potencial"]:
            display[col] = display[col].apply(
                lambda q: f"Q{q:,.0f}" if pd.notna(q) and q != 0 else ("—" if pd.isna(q) else "Q0")
            )
        display["margen_pct"] = display["margen_pct"].apply(lambda p: f"{p:.1f}%" if p else "—")
        display = display[[
            "import_id", "status", "n_units", "q_unit", "total_landed_gtq",
            "revenue_realized", "cogs_realized", "margen_realizado", "margen_pct",
            "revenue_pipeline", "cost_pipeline", "margen_potencial",
            "cash_collected",
        ]]
        display.columns = [
            "Import", "Status", "Units", "Q/unit", "Landed",
            "Rev. real", "COGS real", "Margen real", "%",
            "Rev. pipe", "Cost pipe", "Margen pot.",
            "Cash in",
        ]
        st.dataframe(display, use_container_width=True, hide_index=True)

    # Caveats
    with st.expander("ℹ️ Cómo leer este P&L"):
        st.markdown("""
- **Revenue cerrado** = ventas con status `shipped` o `delivered` (contabilidad accrual).
- **Cash real en cuenta** = plata efectivamente cobrada (`payment_method IS NOT NULL`), independiente de entrega.
- **Pipeline** = ventas aún en `pending/sent/in_production`. No es revenue real — es expectativa.
- **Sunken cost** = costo de jerseys que se perdieron (ej. Forza no entregó → venta cancelled pero jersey sold).
- **Consumo interno** = items con Q0 revenue (regalos familia, consumo personal). El cost se absorbe cuando cierres la importación. **Pérdida operativa intencional**.
- **Margen potencial** = suma optimista: si todo el pipeline entrega y cobra. Límite teórico.
- **En riesgo** = cuánta plata depende de que cobres pendientes + entreguen pipeline. Si nada entra → perdés este monto en expected revenue.
        """)

    # ═══ Batch cost adjustment tool ═══
    st.markdown("---")
    with st.expander("⚙️ Ajustar costos de batch importación"):
        st.caption("Aplica costo landed prorrateado uniformemente sobre todas las sales "
                   "con un prefijo de ref + jerseys extras opcionales (regalos proveedor).")

        col1, col2 = st.columns(2)
        with col1:
            batch_prefix = st.text_input("Prefijo ref (ej. `FF-` para F&F)",
                                         value="FF-", key="batch_prefix")
        with col2:
            batch_fx = st.number_input("FX rate USD→GTQ", value=7.70, step=0.05,
                                       format="%.2f", key="batch_fx")

        col1, col2 = st.columns(2)
        with col1:
            batch_usd = st.number_input("Bruto proveedor (USD)", min_value=0.0,
                                        step=10.0, format="%.2f", key="batch_usd")
        with col2:
            batch_shipping = st.number_input("Shipping + impuestos (GTQ)",
                                             min_value=0.0, step=10.0, format="%.2f",
                                             key="batch_shipping")

        batch_extras = st.text_input(
            "Jerseys extras en prorrateo (regalos proveedor, coma-separados)",
            value="", placeholder="JRS-032,JRS-033,JRS-034", key="batch_extras",
            help="Si no hay regalos ni jerseys adicionales, dejar vacío.",
        )
        batch_include_cancelled = st.checkbox(
            "Incluir sales `cancelled` en el prorrateo", value=False, key="batch_incl_cancel",
        )

        # Preview
        if batch_prefix and (batch_usd or batch_shipping):
            extras_list = [x.strip() for x in batch_extras.split(",") if x.strip()]
            where_cancel = "" if batch_include_cancelled else " AND s.fulfillment_status != 'cancelled'"
            n_items = conn.execute(
                f"""SELECT COUNT(*) FROM sale_items i JOIN sales s ON i.sale_id=s.sale_id
                    WHERE s.ref LIKE ?{where_cancel}""",
                (f"{batch_prefix}%",),
            ).fetchone()[0]
            n_jerseys = 0
            if extras_list:
                qs = ",".join("?" * len(extras_list))
                n_jerseys = conn.execute(
                    f"SELECT COUNT(*) FROM jerseys WHERE jersey_id IN ({qs})",
                    extras_list,
                ).fetchone()[0]
            total_units = n_items + n_jerseys
            total_landed = batch_usd * batch_fx + batch_shipping
            unit = round(total_landed / total_units) if total_units else 0

            st.info(
                f"**Preview:** {n_items} sale_items + {n_jerseys} jerseys = **{total_units} units**.  \n"
                f"Total landed Q{total_landed:,.2f} → **Q{unit}/unit**"
            )

            if st.button("✅ APLICAR prorrateo", type="primary", key="batch_apply"):
                result = apply_batch_cost_prorrateo(
                    conn,
                    ref_prefix=batch_prefix,
                    bruto_usd=batch_usd,
                    shipping_gtq=batch_shipping,
                    fx=batch_fx,
                    extra_jersey_ids=extras_list,
                    include_cancelled=batch_include_cancelled,
                )
                st.success(
                    f"✓ Aplicado: {result['n_items']} items + {result['n_jerseys']} jerseys "
                    f"→ Q{result['unit_cost']}/unit (total landed Q{result['total_landed']:,.2f})"
                )
                st.rerun()


# ─── Tab 3: Histórico ─────────────────────────

def _render_historico_tab(conn):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        modality_filter = st.selectbox(
            "Modalidad", ["all"] + MODALITIES,
            format_func=lambda c: "Todas" if c == "all" else MODALITY_LABELS[c],
        )
    with c2:
        origin_filter = st.selectbox(
            "Origen", ["all"] + ORIGINS,
            format_func=lambda c: "Todos" if c == "all" else ORIGIN_LABELS.get(c, c),
        )
    with c3:
        date_from = st.date_input("Desde", value=None, key="hist_from")
    with c4:
        date_to = st.date_input("Hasta", value=None, key="hist_to")

    df = list_sales(
        conn,
        modality=modality_filter,
        origin=origin_filter,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    st.caption(f"**{len(df)}** venta(s)")

    if df.empty:
        st.info("Sin ventas. Cargá alguna en la tab «Registrar venta».")
        return

    display_df = df.copy()
    display_df["modality"] = display_df["modality"].map(lambda c: MODALITY_LABELS.get(c, c))
    display_df["origin"] = display_df["origin"].map(
        lambda c: ORIGIN_LABELS.get(c, c) if c else "—"
    )
    display_df["fulfillment_status"] = display_df["fulfillment_status"].map(
        lambda s: FULFILLMENT_LABELS.get(s, s)
    )
    display_df["total"] = display_df["total"].apply(
        lambda q: f"Q{q:,}" if pd.notna(q) else "—"
    )
    display_df = display_df[[
        "ref", "occurred_at", "modality", "origin", "cliente", "telefono",
        "payment_method", "total", "n_items", "fulfillment_status", "tracking_code",
    ]]
    display_df.columns = ["Ref", "Fecha", "Modalidad", "Origen", "Cliente", "Tel",
                          "Pago", "Total", "Items", "Estado", "Tracking"]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export CSV", csv,
                       f"ventas_{date.today().isoformat()}.csv",
                       "text/csv", use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🔍 Detalle")
    refs = [""] + df["ref"].tolist()
    selected_ref = st.selectbox("Abrir ref", refs)
    if selected_ref:
        _render_sale_detail(conn, selected_ref)


def _render_sale_detail(conn, ref: str):
    sale = conn.execute(
        """SELECT s.*, c.name AS cust_name, c.phone AS cust_phone, c.email AS cust_email
           FROM sales s LEFT JOIN customers c ON s.customer_id = c.customer_id
           WHERE s.ref = ?""",
        (ref,),
    ).fetchone()
    if not sale:
        st.error(f"Sale {ref} no encontrado.")
        return
    sale = dict(sale)

    items = conn.execute(
        "SELECT * FROM sale_items WHERE sale_id = ? ORDER BY item_id",
        (sale["sale_id"],),
    ).fetchall()
    items = [dict(i) for i in items]

    attribution = conn.execute(
        "SELECT * FROM sales_attribution WHERE sale_id = ?",
        (sale["sale_id"],),
    ).fetchall()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modalidad", MODALITY_LABELS.get(sale["modality"], sale["modality"]))
    c2.metric("Origen", ORIGIN_LABELS.get(sale["origin"], sale["origin"] or "—"))
    c3.metric("Total", f"Q{sale['total']:,}")
    c4.metric("Estado", FULFILLMENT_LABELS.get(sale["fulfillment_status"], sale["fulfillment_status"]))

    st.write(f"**Cliente:** {sale['cust_name']} · {sale['cust_phone'] or '—'} · {sale['cust_email'] or '—'}")
    st.write(f"**Pago:** {sale['payment_method']} · **Envío:** {sale['shipping_method']} · **Tracking:** {sale['tracking_code'] or '—'}")
    if sale["notes"]:
        st.caption(f"_Notas: {sale['notes']}_")

    st.markdown("**Items:**")
    for it in items:
        try:
            pers = json.loads(it["personalization_json"] or "{}")
        except json.JSONDecodeError:
            pers = {}
        pers_str = " · ".join(f"{k}={v}" for k, v in pers.items() if v) or "—"
        margin = (it["unit_price"] or 0) - (it["unit_cost"] or 0)
        st.write(
            f"· **{it['team']}** {it['season']} {it['variant_label']} "
            f"{it['version']} {it['size']} · pers: {pers_str} · "
            f"precio Q{it['unit_price']} · costo Q{it['unit_cost']} · margen Q{margin}"
        )

    if attribution:
        st.markdown("**Attribution:**")
        for a in attribution:
            a = dict(a)
            st.caption(f"· {a['source']} · {a.get('ad_campaign_name') or a.get('ad_campaign_id') or ''}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        new_status = st.selectbox(
            "Cambiar fulfillment",
            FULFILLMENT_STATUSES,
            index=FULFILLMENT_STATUSES.index(sale["fulfillment_status"]),
            format_func=lambda s: FULFILLMENT_LABELS.get(s, s),
            key=f"ff_{ref}",
        )
        if st.button("Aplicar cambio estado", key=f"ffbtn_{ref}"):
            update_fulfillment(conn, sale["sale_id"], new_status)
            st.success("Estado actualizado.")
            st.rerun()
    with c2:
        if st.button("🗑️ Eliminar venta (irreversible)", key=f"del_{ref}"):
            delete_sale(conn, sale["sale_id"])
            st.warning(f"Venta {ref} eliminada.")
            st.rerun()
