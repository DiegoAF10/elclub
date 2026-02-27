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
                  cost=100, price=None, notes=None) -> str:
    """Insert a jersey and return its ID."""
    jersey_id = next_jersey_id(conn)
    conn.execute(
        """INSERT INTO jerseys
           (jersey_id, team_id, season, variant, size, tier,
            player_name, player_number, patches, cost, price, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (jersey_id, team_id, season, variant, size, tier,
         player_name, player_number, patches, cost, price, notes),
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
