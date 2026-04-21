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
