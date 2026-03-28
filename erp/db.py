"""Database helper — El Club ERP."""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "elclub.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
PHOTOS_DIR = os.path.join(BASE_DIR, "photos")

os.makedirs(PHOTOS_DIR, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()


def next_jersey_id(conn: sqlite3.Connection) -> str:
    """Generate next jersey ID like JRS-001, JRS-002..."""
    row = conn.execute(
        "SELECT jersey_id FROM jerseys ORDER BY jersey_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return "JRS-001"
    num = int(row["jersey_id"].split("-")[1]) + 1
    return f"JRS-{num:03d}"


def insert_jersey(conn, team_id, season, variant, size, tier,
                  player_name=None, player_number=None, patches=None,
                  cost=100, price=None, notes=None, position=None) -> str:
    """Insert a jersey and return its ID."""
    jersey_id = next_jersey_id(conn)
    conn.execute(
        """INSERT INTO jerseys
           (jersey_id, team_id, season, variant, size, tier,
            player_name, player_number, patches, cost, price, notes, position)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (jersey_id, team_id, season, variant, size, tier,
         player_name, player_number, patches, cost, price, notes, position),
    )
    conn.commit()
    return jersey_id


def insert_photo(conn, jersey_id, photo_type, filename) -> int:
    """Insert a photo record and return its ID."""
    cur = conn.execute(
        "INSERT INTO photos (jersey_id, photo_type, filename) VALUES (?, ?, ?)",
        (jersey_id, photo_type, filename),
    )
    conn.commit()
    return cur.lastrowid


def next_photo_seq(conn, jersey_id):
    """Get next photo sequence number for a jersey."""
    row = conn.execute(
        "SELECT MAX(CAST(photo_type AS INTEGER)) FROM photos WHERE jersey_id = ?",
        (jersey_id,),
    ).fetchone()
    return (row[0] or 0) + 1


def migrate_db(conn):
    """Run one-time migrations for schema changes."""
    # Drop view first (depends on photos table)
    conn.execute("DROP VIEW IF EXISTS v_photo_coverage")
    conn.commit()

    # Add published column to jerseys
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jerseys)").fetchall()]
    if "published" not in cols:
        conn.execute("ALTER TABLE jerseys ADD COLUMN published INTEGER DEFAULT 0")
        conn.commit()

    # Add story column to jerseys
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jerseys)").fetchall()]
    if "story" not in cols:
        conn.execute("ALTER TABLE jerseys ADD COLUMN story TEXT")
        conn.commit()

    # Add position column to jerseys
    cols = [r[1] for r in conn.execute("PRAGMA table_info(jerseys)").fetchall()]
    if "position" not in cols:
        conn.execute("ALTER TABLE jerseys ADD COLUMN position TEXT")
        conn.commit()

    # Remove CHECK constraint on photos.photo_type (was limited to front/back/detail)
    table_info = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='photos'"
    ).fetchone()
    if table_info and "'front'" in table_info["sql"]:
        conn.executescript("""
            CREATE TABLE photos_new (
                photo_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                jersey_id   TEXT NOT NULL REFERENCES jerseys(jersey_id) ON DELETE CASCADE,
                photo_type  TEXT NOT NULL,
                filename    TEXT NOT NULL,
                uploaded_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            INSERT INTO photos_new SELECT * FROM photos;
            DROP TABLE photos;
            ALTER TABLE photos_new RENAME TO photos;
            CREATE INDEX IF NOT EXISTS idx_photos_jersey ON photos(jersey_id);
        """)

    # Recreate view with updated schema
    conn.executescript("""
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
    """)


def update_jersey(conn, jersey_id, **fields):
    """Update jersey fields. Only updates provided keys."""
    allowed = {
        "team_id", "season", "variant", "size", "tier",
        "player_name", "player_number", "patches", "price", "notes", "status",
        "published", "story", "position",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [jersey_id]
    conn.execute(f"UPDATE jerseys SET {set_clause} WHERE jersey_id = ?", values)
    conn.commit()


def get_teams(conn):
    """Get all teams ordered by league then name."""
    return conn.execute(
        "SELECT * FROM teams ORDER BY league, name"
    ).fetchall()


def get_team_by_id(conn, team_id):
    """Get a single team by ID."""
    return conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()


def count_teams(conn) -> int:
    """Count loaded teams."""
    return conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]


def count_jerseys(conn, status=None) -> int:
    """Count jerseys, optionally filtered by status."""
    if status:
        return conn.execute(
            "SELECT COUNT(*) FROM jerseys WHERE status = ?", (status,)
        ).fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM jerseys").fetchone()[0]
