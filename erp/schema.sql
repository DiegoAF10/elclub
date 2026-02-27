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
