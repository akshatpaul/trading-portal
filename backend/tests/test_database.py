"""
tests/test_database.py — Database layer tests

Tests every query function with a temporary in-memory SQLite DB
so the real trading_portal.db is never touched.

Run: pytest tests/test_database.py -v
"""

import pytest
import sqlite3
from unittest.mock import patch
from pathlib import Path

# ── Point the DB at a temp file for tests ─────
import tempfile
import os

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TEST_DB = Path(_tmp.name)
_tmp.close()


# Patch DB_PATH before importing db/queries
import database.db as db_module
db_module.DB_PATH = _TEST_DB

import database.queries as q


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-create all tables before each test, clean up after."""
    db_module.init_db()
    yield
    # Drop all tables between tests for isolation
    with db_module.get_db() as conn:
        conn.executescript("""
            DELETE FROM trades;
            DELETE FROM positions;
            DELETE FROM candles;
            DELETE FROM daily_summary;
            DELETE FROM watchlist;
            DELETE FROM signals;
            DELETE FROM achievements;
            DELETE FROM app_settings;
        """)


# ── Helpers ───────────────────────────────────

def _make_trade(**overrides) -> dict:
    base = {
        "symbol": "HDFCBANK.NS", "mode": "paper", "side": "BUY",
        "quantity": 6,
        "entry_price": 1642.0, "exit_price": 1652.0,
        "entry_time": "2026-03-16T09:35:00+05:30",
        "exit_time":  "2026-03-16T10:15:00+05:30",
        "exit_reason": "TARGET",
        "gross_pnl": 60.0, "brokerage": 40.0, "stt": 2.48,
        "exchange_fee": 1.14, "sebi_charge": 0.02, "gst": 7.47,
        "stamp_duty": 0.30, "total_cost": 51.41,
        "net_pnl": 8.59, "tax_estimate": 2.58, "final_pnl": 6.01,
        "position_id": None,
    }
    return {**base, **overrides}


def _make_position(**overrides) -> dict:
    base = {
        "symbol": "HDFCBANK.NS", "mode": "paper", "side": "BUY",
        "quantity": 6, "entry_price": 1642.0,
        "target": 1651.85, "stop_loss": 1637.07,
        "entry_time": "2026-03-16T09:35:00+05:30",
        "signal_id": None,
    }
    return {**base, **overrides}


# ── init_db ───────────────────────────────────

def test_init_db_creates_tables():
    with db_module.get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in tables}
    expected = {
        "candles", "signals", "positions", "trades",
        "daily_summary", "watchlist", "achievements", "app_settings",
    }
    assert expected.issubset(names)


def test_init_db_idempotent():
    db_module.init_db()   # second call should not raise
    db_module.init_db()


# ── Trades ────────────────────────────────────

def test_insert_and_get_trade():
    trade_id = q.insert_trade(_make_trade())
    assert isinstance(trade_id, int) and trade_id > 0

    trades = q.get_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "HDFCBANK.NS"
    assert trades[0]["final_pnl"] == pytest.approx(6.01)


def test_get_trade_by_id():
    trade_id = q.insert_trade(_make_trade())
    trade = q.get_trade_by_id(trade_id)
    assert trade is not None
    assert trade["id"] == trade_id


def test_get_trade_by_id_missing():
    assert q.get_trade_by_id(999) is None


def test_get_trades_mode_filter():
    q.insert_trade(_make_trade(mode="paper"))
    q.insert_trade(_make_trade(mode="live"))
    paper = q.get_trades(mode="paper")
    assert len(paper) == 1
    assert paper[0]["mode"] == "paper"


def test_get_trades_date_filter():
    from datetime import date
    q.insert_trade(_make_trade(entry_time="2026-03-16T09:35:00+05:30",
                               exit_time="2026-03-16T10:00:00+05:30"))
    q.insert_trade(_make_trade(entry_time="2026-03-15T09:35:00+05:30",
                               exit_time="2026-03-15T10:00:00+05:30"))
    today = q.get_trades(date_filter=date(2026, 3, 16))
    assert len(today) == 1


def test_get_trades_count_today():
    q.insert_trade(_make_trade())
    q.insert_trade(_make_trade())
    count = q.get_trades_count_today("paper")
    assert count == 2


def test_get_daily_loss_today():
    q.insert_trade(_make_trade(final_pnl=-150.0, net_pnl=-150.0))
    q.insert_trade(_make_trade(final_pnl=50.0, net_pnl=50.0))
    loss = q.get_daily_loss_today("paper")
    assert loss == pytest.approx(150.0)


# ── Positions ─────────────────────────────────

def test_insert_and_get_open_position():
    pos_id = q.insert_position(_make_position())
    assert pos_id > 0

    pos = q.get_open_position()
    assert pos is not None
    assert pos["symbol"] == "HDFCBANK.NS"
    assert pos["status"] == "open"


def test_close_position():
    pos_id = q.insert_position(_make_position())
    q.close_position(pos_id, "2026-03-16T10:15:00+05:30")
    assert q.get_open_position() is None


def test_only_one_open_position_returned():
    q.insert_position(_make_position())
    q.insert_position(_make_position(symbol="TCS.NS"))
    # get_open_position returns LIMIT 1
    pos = q.get_open_position()
    assert pos is not None


# ── Candles ───────────────────────────────────

def test_upsert_candles():
    candles = [
        {"symbol": "HDFCBANK.NS", "interval": "5m",
         "timestamp": f"2026-03-16T09:{m:02d}:00+05:30",
         "open": 1640.0, "high": 1645.0, "low": 1638.0,
         "close": 1642.0, "volume": 100000}
        for m in range(35, 40)
    ]
    inserted = q.upsert_candles(candles)
    assert inserted == 5


def test_upsert_candles_deduplication():
    candle = {
        "symbol": "HDFCBANK.NS", "interval": "5m",
        "timestamp": "2026-03-16T09:35:00+05:30",
        "open": 1640.0, "high": 1645.0, "low": 1638.0,
        "close": 1642.0, "volume": 100000,
    }
    q.upsert_candles([candle])
    q.upsert_candles([candle])   # duplicate → ignored
    result = q.get_candles("HDFCBANK.NS", "5m")
    assert len(result) == 1


def test_get_candles_ordered_asc():
    candles = [
        {"symbol": "TCS.NS", "interval": "5m",
         "timestamp": f"2026-03-16T09:{m:02d}:00+05:30",
         "open": 3500.0, "high": 3510.0, "low": 3490.0,
         "close": 3505.0, "volume": 50000}
        for m in range(35, 45)
    ]
    q.upsert_candles(candles)
    rows = q.get_candles("TCS.NS", "5m")
    timestamps = [r["timestamp"] for r in rows]
    assert timestamps == sorted(timestamps)


def test_upsert_candles_empty():
    assert q.upsert_candles([]) == 0


# ── Daily Summary ─────────────────────────────

def _make_summary(**overrides) -> dict:
    base = {
        "date": "2026-03-16", "mode": "paper",
        "trades_count": 2, "wins": 1, "losses": 1,
        "gross_pnl": 100.0, "total_cost": 40.0,
        "net_pnl": 60.0, "tax_estimate": 18.0, "final_pnl": 42.0,
        "win_rate": 0.5, "profit_factor": 1.5,
        "capital_end": 10042.0, "streak": 0,
    }
    return {**base, **overrides}


def test_upsert_and_get_daily_summary():
    q.upsert_daily_summary(_make_summary())
    s = q.get_daily_summary("2026-03-16")
    assert s is not None
    assert s["final_pnl"] == pytest.approx(42.0)


def test_upsert_daily_summary_updates():
    q.upsert_daily_summary(_make_summary(final_pnl=42.0))
    q.upsert_daily_summary(_make_summary(final_pnl=99.0))  # update
    s = q.get_daily_summary("2026-03-16")
    assert s["final_pnl"] == pytest.approx(99.0)


def test_get_daily_summary_missing():
    assert q.get_daily_summary("1999-01-01") is None


def test_get_recent_summaries():
    for i in range(5):
        q.upsert_daily_summary(_make_summary(date=f"2026-03-{10+i:02d}"))
    rows = q.get_recent_summaries(days=3)
    assert len(rows) == 3


# ── Watchlist ─────────────────────────────────

def test_upsert_and_get_watchlist():
    entries = [
        {"symbol": "HDFCBANK.NS", "rank": 1, "score": 9.5,
         "atr_pct": 1.2, "adx": 28.0, "vol_ratio": 1.8, "price": 1642.0},
        {"symbol": "TCS.NS", "rank": 2, "score": 8.1,
         "atr_pct": 0.9, "adx": 24.0, "vol_ratio": 1.5, "price": 3520.0},
    ]
    q.upsert_watchlist("2026-03-16", entries)
    wl = q.get_watchlist("2026-03-16")
    assert len(wl) == 2
    assert wl[0]["symbol"] == "HDFCBANK.NS"
    assert wl[0]["rank"] == 1


def test_get_watchlist_empty():
    assert q.get_watchlist("2020-01-01") == []


# ── Signals ───────────────────────────────────

def test_insert_signal():
    sig = {
        "symbol": "HDFCBANK.NS", "side": "BUY",
        "price": 1642.0, "target": 1651.85, "stop_loss": 1637.07,
        "reason": "EMA crossover + volume", "timestamp": "2026-03-16T09:35:00+05:30",
    }
    sig_id = q.insert_signal(sig)
    assert sig_id > 0


def test_mark_signal_acted():
    sig = {
        "symbol": "HDFCBANK.NS", "side": "BUY",
        "price": 1642.0, "target": 1651.85, "stop_loss": 1637.07,
        "reason": "test", "timestamp": "2026-03-16T09:35:00+05:30",
    }
    sig_id = q.insert_signal(sig)
    q.mark_signal_acted(sig_id)
    with db_module.get_db() as conn:
        row = conn.execute(
            "SELECT acted_on FROM signals WHERE id = ?", (sig_id,)
        ).fetchone()
    assert row["acted_on"] == 1


# ── App Settings ──────────────────────────────

def test_set_and_get_setting():
    q.set_setting("foo", "bar")
    assert q.get_setting("foo") == "bar"


def test_get_setting_default():
    assert q.get_setting("nonexistent", "default_val") == "default_val"


def test_set_setting_updates():
    q.set_setting("capital", "10000")
    q.set_setting("capital", "10500")
    assert q.get_setting("capital") == "10500"


# ── Achievements ──────────────────────────────

def test_upsert_achievement():
    q.upsert_achievement("sharpshooter", "Sharpshooter", "🎯", "2026-03-16T10:00:00")
    achievements = q.get_achievements()
    assert len(achievements) == 1
    assert achievements[0]["key"] == "sharpshooter"


def test_achievement_times_earned():
    q.upsert_achievement("century", "Century", "📊", "2026-03-16T10:00:00")
    q.upsert_achievement("century", "Century", "📊", "2026-03-17T10:00:00")
    with db_module.get_db() as conn:
        row = conn.execute(
            "SELECT times_earned FROM achievements WHERE key = 'century'"
        ).fetchone()
    assert row["times_earned"] == 2


# ── Performance stats ─────────────────────────

def test_performance_stats_empty():
    stats = q.get_performance_stats()
    assert stats["total_trades"] == 0
    assert stats["win_rate"] == 0.0
    assert stats["profit_factor"] == 0.0
    assert stats["max_drawdown"] == 0.0


def test_performance_stats_with_trades():
    q.insert_trade(_make_trade(final_pnl=100.0, net_pnl=100.0, gross_pnl=120.0, total_cost=20.0))
    q.insert_trade(_make_trade(final_pnl=-50.0, net_pnl=-50.0, gross_pnl=-40.0, total_cost=10.0))
    q.insert_trade(_make_trade(final_pnl=80.0,  net_pnl=80.0,  gross_pnl=90.0,  total_cost=10.0))

    stats = q.get_performance_stats()
    assert stats["total_trades"] == 3
    assert stats["wins"] == 2
    assert stats["losses"] == 1
    assert stats["win_rate"] == pytest.approx(2 / 3, rel=1e-3)
    assert stats["profit_factor"] == pytest.approx(180 / 50, rel=1e-3)
    assert stats["max_drawdown"] >= 0.0


def test_max_drawdown_calculation():
    # Peak 100, then drops to 50 → 50% drawdown
    pnl = [100.0, -50.0]
    dd = q._calc_max_drawdown(pnl)
    assert dd == pytest.approx(0.5)


def test_max_drawdown_no_loss():
    pnl = [50.0, 30.0, 20.0]
    assert q._calc_max_drawdown(pnl) == 0.0


# ── Cleanup temp DB ───────────────────────────

def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_TEST_DB)
    except Exception:
        pass
