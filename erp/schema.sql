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
    position        TEXT CHECK(position IN ('POR','DEF','MED','DEL')),
    published       INTEGER DEFAULT 0 CHECK(published IN (0, 1)),
    story           TEXT,
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
    photo_type  TEXT NOT NULL,
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
    COUNT(p.photo_id) as photo_count
FROM jerseys j
JOIN teams t ON j.team_id = t.team_id
LEFT JOIN photos p ON j.jersey_id = p.jersey_id
GROUP BY j.jersey_id;

-- ═══════════════════════════════════════
-- VAULT ORDERS (synced from Cloudflare Worker)
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS vault_orders (
    ref             TEXT PRIMARY KEY,
    received_at     TEXT,
    cliente_nombre  TEXT,
    cliente_tel     TEXT,
    cliente_email   TEXT,
    envio_json      TEXT,
    pago_metodo     TEXT,
    total           INTEGER,
    status          TEXT DEFAULT 'new',
    notas           TEXT,
    synced_at       TEXT,
    raw_json        TEXT
);

CREATE TABLE IF NOT EXISTS vault_order_items (
    item_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_ref            TEXT REFERENCES vault_orders(ref),
    family_id            TEXT,
    team                 TEXT,
    season               TEXT,
    variant_label        TEXT,
    version              TEXT,
    size                 TEXT,
    personalization_json TEXT,
    total_price          INTEGER,
    supplier_sent_at     TEXT,
    fulfillment_status   TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS vault_order_status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_ref    TEXT,
    from_status  TEXT,
    to_status    TEXT,
    changed_at   TEXT,
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_vault_orders_status ON vault_orders(status);
CREATE INDEX IF NOT EXISTS idx_vault_items_order ON vault_order_items(order_ref);
CREATE INDEX IF NOT EXISTS idx_vault_status_hist_ref ON vault_order_status_history(order_ref);

-- ═══════════════════════════════════════
-- COMERCIAL (cross-channel sales tracking — all of El Club)
-- Bucket "Comercial" — 2026-04-22
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS customers (
    customer_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    phone            TEXT,
    email            TEXT,
    tags_json        TEXT DEFAULT '[]',
    source           TEXT,
    first_order_at   TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_phone ON customers(phone) WHERE phone IS NOT NULL AND phone != '';
CREATE INDEX IF NOT EXISTS idx_customers_source ON customers(source);

CREATE TABLE IF NOT EXISTS sales (
    sale_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ref                 TEXT UNIQUE,
    occurred_at         TEXT NOT NULL,
    modality            TEXT NOT NULL CHECK(modality IN ('mystery','stock','ondemand')),
    origin              TEXT,
    customer_id         INTEGER REFERENCES customers(customer_id),
    payment_method      TEXT CHECK(payment_method IN ('recurrente','transferencia','contra_entrega','efectivo','otro') OR payment_method IS NULL),
    fulfillment_status  TEXT DEFAULT 'pending' CHECK(fulfillment_status IN ('pending','sent_to_supplier','in_production','shipped','delivered','cancelled')),
    shipping_method     TEXT,
    tracking_code       TEXT,
    subtotal            INTEGER,
    shipping_fee        INTEGER DEFAULT 0,
    discount            INTEGER DEFAULT 0,
    total               INTEGER NOT NULL,
    source_vault_ref    TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sales_modality ON sales(modality);
CREATE INDEX IF NOT EXISTS idx_sales_origin ON sales(origin);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_occurred ON sales(occurred_at);
CREATE INDEX IF NOT EXISTS idx_sales_vault_ref ON sales(source_vault_ref);

CREATE TABLE IF NOT EXISTS sale_items (
    item_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id              INTEGER NOT NULL REFERENCES sales(sale_id) ON DELETE CASCADE,
    family_id            TEXT,
    jersey_id            TEXT,
    team                 TEXT,
    season               TEXT,
    variant_label        TEXT,
    version              TEXT,
    size                 TEXT,
    personalization_json TEXT DEFAULT '{}',
    unit_price           INTEGER NOT NULL DEFAULT 0,
    unit_cost            INTEGER,
    notes                TEXT
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_family ON sale_items(family_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_team_season ON sale_items(team, season);

CREATE TABLE IF NOT EXISTS sales_attribution (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id           INTEGER NOT NULL REFERENCES sales(sale_id) ON DELETE CASCADE,
    ad_campaign_id    TEXT,
    ad_campaign_name  TEXT,
    source            TEXT,
    note              TEXT,
    created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_attribution_sale ON sales_attribution(sale_id);
CREATE INDEX IF NOT EXISTS idx_attribution_campaign ON sales_attribution(ad_campaign_id);

-- Views: revenue + COGS split to avoid JOIN multiplication.

CREATE VIEW IF NOT EXISTS v_sales_by_day AS
SELECT
    modality,
    origin,
    DATE(occurred_at) AS day,
    COUNT(*) AS n_sales,
    SUM(total) AS revenue,
    SUM(total - COALESCE(shipping_fee, 0) - COALESCE(discount, 0)) AS net_revenue
FROM sales
WHERE fulfillment_status != 'cancelled'
GROUP BY modality, origin, DATE(occurred_at);

CREATE VIEW IF NOT EXISTS v_cogs_by_day AS
SELECT
    s.modality,
    DATE(s.occurred_at) AS day,
    COUNT(i.item_id) AS n_items,
    SUM(COALESCE(i.unit_cost, 0)) AS cogs
FROM sales s
JOIN sale_items i ON i.sale_id = s.sale_id
WHERE s.fulfillment_status != 'cancelled'
GROUP BY s.modality, DATE(s.occurred_at);

CREATE VIEW IF NOT EXISTS v_top_skus AS
SELECT
    i.team,
    i.season,
    i.variant_label,
    i.version,
    COUNT(*) AS units_sold,
    SUM(COALESCE(i.unit_price, 0)) AS revenue_from_items,
    SUM(COALESCE(i.unit_cost, 0)) AS cogs
FROM sale_items i
JOIN sales s ON i.sale_id = s.sale_id
WHERE s.fulfillment_status != 'cancelled'
GROUP BY i.team, i.season, i.variant_label, i.version
ORDER BY units_sold DESC;

-- ═══════════════════════════════════════
-- IMPORTS (batches de pedidos al proveedor)
-- Bucket "Comercial" — 2026-04-22 PM
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS imports (
    import_id        TEXT PRIMARY KEY,   -- 'IMP-2026-04-07'
    paid_at          TEXT,
    arrived_at       TEXT,
    supplier         TEXT DEFAULT 'Bond Soccer Jersey',
    bruto_usd        REAL,
    shipping_gtq     REAL,
    fx               REAL DEFAULT 7.70,
    total_landed_gtq REAL,
    n_units          INTEGER,
    unit_cost        REAL,
    status           TEXT DEFAULT 'in_transit'
        CHECK(status IN ('draft','paid','in_transit','arrived','closed','cancelled')),
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_imports_status ON imports(status);
CREATE INDEX IF NOT EXISTS idx_imports_paid_at ON imports(paid_at);

-- ═══════════════════════════════════════
-- IMP-R1 schema additions (2026-04-27)
-- Aplicado vía scripts/apply_imports_schema.py (idempotente)
-- ═══════════════════════════════════════

-- ALTER TABLE imports ADD COLUMN tracking_code TEXT;
-- ALTER TABLE imports ADD COLUMN carrier TEXT DEFAULT 'DHL';
-- ALTER TABLE imports ADD COLUMN lead_time_days INTEGER;
-- ALTER TABLE sale_items ADD COLUMN unit_cost_usd REAL;
-- ALTER TABLE jerseys ADD COLUMN unit_cost_usd REAL;

-- (CREATE TABLE statements para import_wishlist y import_free_unit — ver scripts/apply_imports_schema.py)
