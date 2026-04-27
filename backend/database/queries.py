"""
database/queries.py — All database query functions

Every DB read/write goes through this module.
No raw SQL anywhere else in the codebase.
"""

from datetime import date, datetime
from typing import Optional

from database.db import get_db


# ── Helpers ───────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── Trades ────────────────────────────────────

def insert_trade(trade: dict) -> int:
    """Insert a completed trade. Returns new trade ID."""
    sql = """
        INSERT INTO trades (
            symbol, mode, side, quantity,
            entry_price, exit_price, entry_time, exit_time, exit_reason,
            gross_pnl, brokerage, stt, exchange_fee, sebi_charge,
            gst, stamp_duty, total_cost, net_pnl, tax_estimate, final_pnl,
            position_id
        ) VALUES (
            :symbol, :mode, :side, :quantity,
            :entry_price, :exit_price, :entry_time, :exit_time, :exit_reason,
            :gross_pnl, :brokerage, :stt, :exchange_fee, :sebi_charge,
            :gst, :stamp_duty, :total_cost, :net_pnl, :tax_estimate, :final_pnl,
            :position_id
        )
    """
    with get_db() as conn:
        cur = conn.execute(sql, trade)
        return cur.lastrowid


def get_trades(
    limit: int = 50,
    mode: Optional[str] = None,
    date_filter: Optional[date] = None,
) -> list[dict]:
    """Fetch recent trades, newest first."""
    conditions = []
    params: list = []

    if mode:
        conditions.append("mode = ?")
        params.append(mode)
    if date_filter:
        conditions.append("date(entry_time) = ?")
        params.append(date_filter.isoformat())

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM trades {where} ORDER BY exit_time DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_list(rows)


def get_trade_by_id(trade_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return _row_to_dict(row)


def get_trades_count_today(mode: str) -> int:
    """Count trades placed today in the given mode."""
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE mode = ? AND date(entry_time) = ?",
            (mode, today),
        ).fetchone()
    return row["cnt"] if row else 0


def get_daily_loss_today(mode: str) -> float:
    """
    Return total loss realised today (positive number = loss).
    Only counts negative final_pnl trades.
    """
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(final_pnl), 0) as total
               FROM trades
               WHERE mode = ? AND date(exit_time) = ? AND final_pnl < 0""",
            (mode, today),
        ).fetchone()
    return abs(row["total"]) if row else 0.0


# ── Positions ─────────────────────────────────

def insert_position(position: dict) -> int:
    """Insert an open position. Returns new position ID."""
    sql = """
        INSERT INTO positions (
            symbol, mode, side, quantity,
            entry_price, target, stop_loss,
            entry_time, signal_id, status, strategy
        ) VALUES (
            :symbol, :mode, :side, :quantity,
            :entry_price, :target, :stop_loss,
            :entry_time, :signal_id, 'open', :strategy
        )
    """
    position.setdefault("strategy", "ema_crossover")
    with get_db() as conn:
        cur = conn.execute(sql, position)
        return cur.lastrowid


def get_open_position() -> Optional[dict]:
    """Return the first open position (any mode), or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE status = 'open' LIMIT 1"
        ).fetchone()
    return _row_to_dict(row)


def get_open_positions(mode: str) -> list[dict]:
    """Return all open positions for the given mode."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM positions WHERE status = 'open' AND mode = ?",
            (mode,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_position_by_id(position_id: int) -> Optional[dict]:
    """Return a position by its ID regardless of status."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        ).fetchone()
    return _row_to_dict(row)


def close_position(position_id: int, exit_time: str) -> None:
    """Mark a position as closed."""
    with get_db() as conn:
        conn.execute(
            "UPDATE positions SET status = 'closed' WHERE id = ?",
            (position_id,),
        )


# ── Candles ───────────────────────────────────

def upsert_candles(candles: list[dict]) -> int:
    """
    Insert or ignore candle records (deduplication by unique constraint).
    Returns count of rows inserted.
    """
    if not candles:
        return 0

    sql = """
        INSERT OR IGNORE INTO candles
            (symbol, interval, timestamp, open, high, low, close, volume)
        VALUES
            (:symbol, :interval, :timestamp, :open, :high, :low, :close, :volume)
    """
    with get_db() as conn:
        cur = conn.executemany(sql, candles)
        return cur.rowcount


def get_candles(
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[dict]:
    """
    Fetch candles for a symbol, oldest first (ready for charting).
    Internally fetches newest N rows, then reverses.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM (
                SELECT * FROM candles
                WHERE symbol = ? AND interval = ?
                ORDER BY timestamp DESC LIMIT ?
               ) ORDER BY timestamp ASC""",
            (symbol, interval, limit),
        ).fetchall()
    return _rows_to_list(rows)


# ── Daily Summary ─────────────────────────────

def upsert_daily_summary(summary: dict) -> None:
    """Insert or update a daily summary row (keyed on date)."""
    sql = """
        INSERT INTO daily_summary (
            date, mode, trades_count, wins, losses,
            gross_pnl, total_cost, net_pnl, tax_estimate, final_pnl,
            win_rate, profit_factor, capital_end, streak
        ) VALUES (
            :date, :mode, :trades_count, :wins, :losses,
            :gross_pnl, :total_cost, :net_pnl, :tax_estimate, :final_pnl,
            :win_rate, :profit_factor, :capital_end, :streak
        )
        ON CONFLICT(date) DO UPDATE SET
            trades_count  = excluded.trades_count,
            wins          = excluded.wins,
            losses        = excluded.losses,
            gross_pnl     = excluded.gross_pnl,
            total_cost    = excluded.total_cost,
            net_pnl       = excluded.net_pnl,
            tax_estimate  = excluded.tax_estimate,
            final_pnl     = excluded.final_pnl,
            win_rate      = excluded.win_rate,
            profit_factor = excluded.profit_factor,
            capital_end   = excluded.capital_end,
            streak        = excluded.streak
    """
    with get_db() as conn:
        conn.execute(sql, summary)


def get_daily_summary(date_str: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_summary WHERE date = ?", (date_str,)
        ).fetchone()
    return _row_to_dict(row)


def get_recent_summaries(days: int = 30) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return _rows_to_list(rows)


# ── Watchlist ─────────────────────────────────

def upsert_watchlist(date_str: str, entries: list[dict]) -> None:
    """Replace today's watchlist entries (deletes stale rows first)."""
    rows = [{**e, "date": date_str} for e in entries]
    sql = """
        INSERT INTO watchlist (date, symbol, rank, score, atr_pct, adx, vol_ratio, price)
        VALUES (:date, :symbol, :rank, :score, :atr_pct, :adx, :vol_ratio, :price)
    """
    with get_db() as conn:
        conn.execute("DELETE FROM watchlist WHERE date = ?", (date_str,))
        conn.executemany(sql, rows)


def get_watchlist(date_str: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE date = ? ORDER BY rank ASC",
            (date_str,),
        ).fetchall()
    return _rows_to_list(rows)


# ── Signals ───────────────────────────────────

def insert_signal(signal: dict) -> int:
    sql = """
        INSERT INTO signals (symbol, side, price, target, stop_loss, reason, timestamp)
        VALUES (:symbol, :side, :price, :target, :stop_loss, :reason, :timestamp)
    """
    with get_db() as conn:
        cur = conn.execute(sql, signal)
        return cur.lastrowid


def mark_signal_acted(signal_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE signals SET acted_on = 1 WHERE id = ?", (signal_id,)
        )


# ── App Settings ──────────────────────────────

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ── Achievements ──────────────────────────────

def upsert_achievement(key: str, name: str, emoji: str, earned_at: str) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO achievements (key, name, emoji, earned_at, times_earned)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(key) DO UPDATE SET
                   earned_at    = excluded.earned_at,
                   times_earned = times_earned + 1""",
            (key, name, emoji, earned_at),
        )


def get_achievements() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM achievements ORDER BY earned_at DESC"
        ).fetchall()
    return _rows_to_list(rows)


# ── Activity Log ──────────────────────────────

def log_activity(
    event_type: str,
    message: str,
    symbol: Optional[str] = None,
    data: Optional[dict] = None,
) -> None:
    """Insert an activity log entry. Never raises — fire and forget."""
    import json
    from utils.helpers import now_ist
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO activity_log (timestamp, event_type, symbol, message, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    now_ist().isoformat(),
                    event_type,
                    symbol,
                    message,
                    json.dumps(data) if data else None,
                ),
            )
    except Exception:
        pass


def get_activity_log(limit: int = 200, date_str: Optional[str] = None) -> list[dict]:
    """Fetch activity log entries, newest first."""
    if date_str:
        sql = """SELECT * FROM activity_log WHERE date(timestamp) = ?
                 ORDER BY timestamp DESC LIMIT ?"""
        params = (date_str, limit)
    else:
        sql = "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?"
        params = (limit,)
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_list(rows)


def purge_old_activity(days: int = 90) -> int:
    """Delete activity log entries older than `days` days. Returns deleted count."""
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM activity_log WHERE timestamp < datetime('now', ?)",
            (f"-{days} days",),
        )
        return cur.rowcount


# ── Monthly P&L ───────────────────────────────

def get_monthly_pnl(mode: str = "paper") -> dict:
    """Return P&L aggregates for the current calendar month."""
    from datetime import date as _date
    today = _date.today()
    month_start = f"{today.year}-{today.month:02d}-01"
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)                        AS trades_count,
                COALESCE(SUM(gross_pnl), 0)     AS gross_pnl,
                COALESCE(SUM(total_cost), 0)    AS total_cost,
                COALESCE(SUM(net_pnl),   0)     AS net_pnl,
                COALESCE(SUM(tax_estimate), 0)  AS tax_estimate,
                COALESCE(SUM(final_pnl), 0)     AS final_pnl,
                MAX(exit_time)                  AS last_trade_time
            FROM trades
            WHERE mode = ? AND date(exit_time) >= ?
            """,
            (mode, month_start),
        ).fetchone()
    return _row_to_dict(row) or {}


# ── Performance stats ─────────────────────────

def get_performance_stats() -> dict:
    """
    Aggregate stats across all completed trades:
      - total_trades, wins, losses, win_rate
      - total_net_pnl, total_final_pnl
      - profit_factor, max_drawdown
      - best_day, best_week, longest_streak
    """
    with get_db() as conn:
        # Core trade aggregates
        agg = conn.execute("""
            SELECT
                COUNT(*)                                        AS total_trades,
                SUM(CASE WHEN final_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN final_pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                COALESCE(SUM(gross_pnl),  0)                   AS total_gross_pnl,
                COALESCE(SUM(total_cost), 0)                   AS total_cost,
                COALESCE(SUM(net_pnl),   0)                    AS total_net_pnl,
                COALESCE(SUM(final_pnl), 0)                    AS total_final_pnl,
                COALESCE(SUM(CASE WHEN final_pnl > 0 THEN final_pnl ELSE 0 END), 0) AS gross_wins,
                COALESCE(ABS(SUM(CASE WHEN final_pnl < 0 THEN final_pnl ELSE 0 END)), 0) AS gross_losses
            FROM trades
        """).fetchone()

        # Best single day (from daily_summary)
        best_day = conn.execute(
            "SELECT date, final_pnl FROM daily_summary ORDER BY final_pnl DESC LIMIT 1"
        ).fetchone()

        # Best week: group daily_summary by ISO week
        best_week = conn.execute("""
            SELECT
                strftime('%Y-W%W', date) AS week,
                SUM(final_pnl)           AS week_pnl
            FROM daily_summary
            GROUP BY week
            ORDER BY week_pnl DESC
            LIMIT 1
        """).fetchone()

        # Longest streak (max streak value recorded in daily_summary)
        longest_streak = conn.execute(
            "SELECT COALESCE(MAX(streak), 0) AS max_streak FROM daily_summary"
        ).fetchone()

        # Max drawdown: peak-to-trough on cumulative final_pnl
        equity_rows = conn.execute(
            "SELECT final_pnl FROM trades ORDER BY exit_time ASC"
        ).fetchall()

    total = agg["total_trades"] or 0
    wins  = agg["wins"] or 0
    gross_wins   = agg["gross_wins"] or 0.0
    gross_losses = agg["gross_losses"] or 0.0

    win_rate      = round(wins / total, 4) if total else 0.0
    profit_factor = round(gross_wins / gross_losses, 4) if gross_losses else (float("inf") if gross_wins else 0.0)
    max_drawdown  = _calc_max_drawdown([r["final_pnl"] for r in equity_rows])

    return {
        "total_trades":    total,
        "wins":            wins,
        "losses":          agg["losses"] or 0,
        "win_rate":        win_rate,
        "total_gross_pnl": round(agg["total_gross_pnl"], 2),
        "total_cost":      round(agg["total_cost"], 2),
        "total_net_pnl":   round(agg["total_net_pnl"], 2),
        "total_final_pnl": round(agg["total_final_pnl"], 2),
        "profit_factor":   profit_factor,
        "max_drawdown":    round(max_drawdown, 4),
        "best_day":        _row_to_dict(best_day),
        "best_week":       _row_to_dict(best_week),
        "longest_streak":  longest_streak["max_streak"] if longest_streak else 0,
    }


def _calc_max_drawdown(pnl_series: list[float]) -> float:
    """
    Calculate maximum drawdown from a list of per-trade P&L values.
    Drawdown is expressed as a positive fraction of peak equity.
    Returns 0.0 if insufficient data.
    """
    if not pnl_series:
        return 0.0

    peak = 0.0
    equity = 0.0
    max_dd = 0.0

    for pnl in pnl_series:
        equity += pnl
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

    return max_dd
