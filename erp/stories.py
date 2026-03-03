"""Story management for El Club jerseys.

Usage from Claude Code:
  python erp/stories.py pending    → show jerseys without stories
  python erp/stories.py update JRS-001 "La historia..."
  python erp/stories.py sync       → regenerate products.json + push
"""

import sqlite3
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "elclub.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def pending():
    """Show jerseys that need stories."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT j.jersey_id, t.name as team, t.league, j.season, j.variant,
               j.player_name, j.player_number, j.patches, j.notes,
               j.published, j.status,
               CASE WHEN j.story IS NOT NULL AND j.story != '' THEN 1 ELSE 0 END as has_story
        FROM jerseys j JOIN teams t ON j.team_id = t.team_id
        WHERE j.status = 'available'
        ORDER BY has_story ASC, j.created_at DESC
    """).fetchall()
    conn.close()

    need = [r for r in rows if not r["has_story"]]
    have = [r for r in rows if r["has_story"]]

    if need:
        print(f"\n{'='*60}")
        print(f"  SIN HISTORIA ({len(need)} jerseys)")
        print(f"{'='*60}")
        for r in need:
            player = f" — {r['player_name']} #{r['player_number']}" if r["player_name"] else ""
            patches = f" | Parches: {r['patches']}" if r["patches"] else ""
            notes = f" | Notas: {r['notes']}" if r["notes"] else ""
            pub = " [PUBLICADA]" if r["published"] else ""
            print(f"  {r['jersey_id']}: {r['team']} {r['variant']} {r['season']}{player}{patches}{notes}{pub}")
    else:
        print("\n  Todas las camisetas tienen historia.")

    if have:
        print(f"\n  Con historia: {len(have)} jerseys")

    print()


def update_story(jersey_id, story):
    """Update a single jersey's story."""
    conn = get_conn()
    conn.execute("UPDATE jerseys SET story = ? WHERE jersey_id = ?", (story, jersey_id))
    conn.commit()
    conn.close()
    print(f"  {jersey_id}: historia actualizada")


def bulk_update(stories_dict):
    """Update multiple jerseys' stories at once. stories_dict = {jersey_id: story}"""
    conn = get_conn()
    for jersey_id, story in stories_dict.items():
        conn.execute("UPDATE jerseys SET story = ? WHERE jersey_id = ?", (story, jersey_id))
    conn.commit()
    conn.close()
    print(f"  {len(stories_dict)} historias actualizadas")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "pending":
        pending()
    elif sys.argv[1] == "update" and len(sys.argv) >= 4:
        update_story(sys.argv[2], sys.argv[3])
    else:
        print("Usage:")
        print("  python stories.py pending")
        print("  python stories.py update JRS-001 'La historia...'")
