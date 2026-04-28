"""FIN-R1 schema additions. Idempotente — re-runnable sin error."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"C:\Users\Diego\el-club\erp\elclub.db")

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS expenses (
      expense_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq        REAL NOT NULL,
      amount_native     REAL,
      currency          TEXT DEFAULT 'GTQ' CHECK(currency IN ('GTQ','USD')),
      fx_used           REAL DEFAULT 7.73,
      category          TEXT NOT NULL CHECK(category IN ('variable','tech','marketing','operations','owner_draw','other')),
      payment_method    TEXT NOT NULL CHECK(payment_method IN ('tdc_personal','cuenta_business')),
      paid_at           TEXT NOT NULL,
      notes             TEXT,
      source            TEXT DEFAULT 'manual' CHECK(source IN ('manual','recurring_template','auto_sale_derived','auto_marketing_pull')),
      source_ref        TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recurring_expenses (
      template_id       INTEGER PRIMARY KEY AUTOINCREMENT,
      name              TEXT NOT NULL,
      amount_native     REAL NOT NULL,
      currency          TEXT DEFAULT 'GTQ',
      category          TEXT NOT NULL,
      payment_method    TEXT NOT NULL,
      day_of_month      INTEGER CHECK(day_of_month BETWEEN 1 AND 28),
      notes_template    TEXT,
      active            INTEGER DEFAULT 1,
      started_at        TEXT NOT NULL,
      ended_at          TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_balance_history (
      balance_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      account           TEXT NOT NULL DEFAULT 'el_club_business',
      balance_gtq       REAL NOT NULL,
      synced_at         TEXT NOT NULL,
      source            TEXT NOT NULL CHECK(source IN ('manual_via_claude','manual_via_telegram','manual_direct','api_recurrente','reconciliation')),
      notes             TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shareholder_loan_movements (
      movement_id        INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq         REAL NOT NULL,
      source_type        TEXT NOT NULL CHECK(source_type IN ('expense_tdc','recoupment','adjustment')),
      source_ref         TEXT,
      movement_date      TEXT NOT NULL,
      loan_balance_after REAL NOT NULL,
      notes              TEXT,
      created_at         TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_draws (
      draw_id           INTEGER PRIMARY KEY AUTOINCREMENT,
      amount_gtq        REAL NOT NULL,
      draw_date         TEXT NOT NULL,
      was_recoupment    INTEGER DEFAULT 0,
      recoupment_amount REAL DEFAULT 0,
      pure_draw_amount  REAL,
      notes             TEXT,
      created_at        TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """,
]

CREATE_VIEWS = [
    """
    DROP VIEW IF EXISTS v_monthly_profit
    """,
    """
    CREATE VIEW v_monthly_profit AS
    SELECT
      strftime('%Y-%m', COALESCE(s.shipped_at, s.occurred_at)) AS month,
      SUM(s.total) AS revenue,
      SUM(COALESCE(si.unit_cost, 0)) AS cogs,
      (SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
        WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', COALESCE(s.shipped_at, s.occurred_at))
        AND category = 'marketing') AS marketing_logged,
      (SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
        WHERE strftime('%Y-%m', paid_at) = strftime('%Y-%m', COALESCE(s.shipped_at, s.occurred_at))
        AND category NOT IN ('marketing', 'owner_draw')) AS opex
    FROM sales s
    LEFT JOIN sale_items si ON si.sale_id = s.sale_id
    WHERE s.fulfillment_status IN ('shipped','delivered')
    GROUP BY strftime('%Y-%m', COALESCE(s.shipped_at, s.occurred_at))
    """,
    """
    DROP VIEW IF EXISTS v_shareholder_loan_balance
    """,
    """
    CREATE VIEW v_shareholder_loan_balance AS
    SELECT
      COALESCE(SUM(amount_gtq), 0) AS current_balance,
      MAX(movement_date) AS last_movement_date
    FROM shareholder_loan_movements
    """,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_expenses_paid_at ON expenses(paid_at)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_payment_method ON expenses(payment_method)",
    "CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_expenses(active)",
    "CREATE INDEX IF NOT EXISTS idx_cash_synced_at ON cash_balance_history(synced_at)",
    "CREATE INDEX IF NOT EXISTS idx_loan_date ON shareholder_loan_movements(movement_date)",
    "CREATE INDEX IF NOT EXISTS idx_draw_date ON owner_draws(draw_date)",
]


def main():
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"Applying FIN-R1 schema to {DB_PATH}")

    for sql in CREATE_TABLES:
        cur.execute(sql)
    print(f"  created/verified {len(CREATE_TABLES)} tables")

    for sql in CREATE_VIEWS:
        cur.execute(sql)
    print(f"  recreated {len(CREATE_VIEWS)//2} views")

    for sql in CREATE_INDEXES:
        cur.execute(sql)
    print(f"  created/verified {len(CREATE_INDEXES)} indexes")

    conn.commit()
    conn.close()
    print("FIN-R1 schema applied successfully (idempotente)")


if __name__ == "__main__":
    main()
