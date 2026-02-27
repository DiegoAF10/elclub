"""Seed the teams table from teams.json."""

import json
import os
from db import get_conn, init_db, count_teams

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_PATH = os.path.join(BASE_DIR, "data", "teams.json")


def seed_teams():
    """Load teams from JSON into SQLite."""
    init_db()
    conn = get_conn()

    existing = count_teams(conn)
    if existing > 0:
        print(f"Teams table already has {existing} rows. Skipping seed.")
        conn.close()
        return

    with open(TEAMS_PATH, "r", encoding="utf-8") as f:
        teams = json.load(f)

    conn.executemany(
        """INSERT INTO teams (name, short_name, league, country, tier)
           VALUES (:name, :short_name, :league, :country, :tier)""",
        teams,
    )
    conn.commit()
    print(f"Seeded {len(teams)} teams.")
    conn.close()


if __name__ == "__main__":
    seed_teams()
