"""
database/db.py — SQLite connection and schema initialisation

Database file: trading_portal.db (created in backend/ directory)

Tables:
  - candles        : OHLCV data cache
  - signals        : generated entry/exit signals
  - trades         : completed trade records with full P&L
  - positions      : currently open positions
  - daily_summary  : end-of-day aggregates
  - watchlist      : daily pre-market selected stocks
  - achievements   : earned gamification achievements
  - app_settings   : key-value app settings (capital, mode)
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from database.models import ALL_TABLES

DB_PATH = Path(__file__).parent.parent / "trading_portal.db"


def get_connection() -> sqlite3.Connection:
    """
    Return a SQLite connection with row_factory set to Row
    (allows dict-like column access).
    WAL mode for better concurrent read performance.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """
    Context manager for safe DB access with automatic commit/rollback.

    Usage:
        with get_db() as conn:
            conn.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Create all tables if they don't exist.
    Safe to call on every startup — uses IF NOT EXISTS.
    Also seeds default app_settings if not present.
    """
    with get_db() as conn:
        for ddl in ALL_TABLES:
            conn.execute(ddl)

    # Migrate existing DBs: add strategy column to positions if missing
    import logging as _log
    _mlog = _log.getLogger(__name__)
    with get_db() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(positions)").fetchall()}
        if "strategy" not in existing:
            conn.execute(
                "ALTER TABLE positions ADD COLUMN strategy TEXT DEFAULT 'ema_crossover'"
            )
            _mlog.info("DB migration: added strategy column to positions")

    # Seed default settings (only if missing)
    _seed_defaults()


def _seed_defaults() -> None:
    """Insert default key-value settings on first run."""
    from config import settings as app_settings

    defaults = {
        "capital": str(app_settings.starting_capital),
        "mode":    app_settings.app_mode,
        "streak":  "0",
    }
    with get_db() as conn:
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def close_connection(conn: sqlite3.Connection) -> None:
    """Safely close a DB connection."""
    try:
        conn.close()
    except Exception:
        pass
