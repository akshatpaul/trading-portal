"""
strategy/screener.py — Pre-market stock screener

Runs at 8:45 AM IST every trading day via APScheduler.

Process:
  1. Batch-fetch 25 days of daily data for all Nifty 50 symbols
  2. Filter: price ₹200–₹3000
  3. Filter: avg daily volume > 500,000
  4. Filter: 14-day ATR > 0.5% of price  (volatility — needs moves we can profit from)
  5. Filter: ADX > 20                      (trending — not choppy sideways)
  6. Score = normalised(ATR%) + normalised(ADX) + normalised(vol_ratio)
  7. Return top 3 by score
  8. Persist to watchlist table
  9. Send Telegram alert
"""

import logging
from datetime import date

from data.yfinance_client import get_multiple_daily, NIFTY50_SYMBOLS
from strategy.indicators import add_atr, add_adx, add_volume_ratio
from database import queries
from utils.helpers import today_ist

log = logging.getLogger(__name__)

# ── Filter thresholds ─────────────────────────
_MIN_PRICE          = 200.0      # ₹
_MAX_PRICE          = 3000.0     # ₹
_MIN_AVG_VOLUME     = 500_000    # shares/day
_MIN_ATR_PCT        = 0.3        # % of price
_MIN_ADX            = 15.0
_TOP_N              = 3          # symbols to select
_FETCH_PERIOD       = "35d"      # daily history for indicators (ADX(14) needs 27+ rows)


def run_screener() -> list[str]:
    """
    Run the full pre-market screener pipeline.

    Returns:
        List of up to _TOP_N NSE symbols selected for today.
        Persists results to DB watchlist table.
        Returns [] on complete failure (logged).
    """
    log.info("Screener: starting for %s", today_ist().isoformat())

    # ── 1. Batch-fetch daily data ─────────────
    log.info("Screener: fetching data for %d symbols", len(NIFTY50_SYMBOLS))
    daily_data = get_multiple_daily(NIFTY50_SYMBOLS, period=_FETCH_PERIOD)

    if not daily_data:
        log.error("Screener: no data returned from yfinance — aborting")
        return []

    log.info("Screener: received data for %d/%d symbols", len(daily_data), len(NIFTY50_SYMBOLS))

    # ── 2–5. Compute indicators + filter ──────
    scored: list[dict] = _score_symbols(daily_data)

    if not scored:
        log.warning("Screener: no symbols passed filters today")
        return []

    # ── 6. Top N ──────────────────────────────
    top = scored[:_TOP_N]
    symbols = [e["symbol"] for e in top]

    # ── 7. Persist to DB ──────────────────────
    date_str = today_ist().isoformat()
    queries.upsert_watchlist(date_str, top)
    log.info("Screener: watchlist saved → %s", symbols)

    # ── 8. Telegram alert (fire-and-forget) ───
    _send_watchlist_alert(symbols)

    return symbols


def _score_symbols(daily_data: dict) -> list[dict]:
    """
    Compute scores for all symbols that have enough data.
    Returns list of scored dicts sorted descending by score.
    """
    raw_scores: list[dict] = []

    for symbol, df in daily_data.items():
        if df.empty or len(df) < 30:
            log.debug("Screener: %s skipped — insufficient data (%d rows)", symbol, len(df))
            continue

        try:
            entry = _compute_symbol_stats(symbol, df)
            if entry is not None:
                raw_scores.append(entry)
        except Exception as exc:
            log.warning("Screener: error computing stats for %s: %s", symbol, exc)

    if not raw_scores:
        return []

    # ── Normalise each metric to [0, 1] then sum ──
    return _normalise_and_rank(raw_scores)


def _compute_symbol_stats(symbol: str, df) -> dict | None:
    """
    Compute ATR%, ADX, vol_ratio for one symbol and apply all filters.
    Returns a dict if the symbol passes, None otherwise.
    """
    import pandas as pd

    if df.empty:
        return None

    # Latest close price
    price = float(df["close"].iloc[-1])

    # ── Filter 1: price range ─────────────────
    if not (_MIN_PRICE <= price <= _MAX_PRICE):
        log.debug("Screener: %s filtered — price ₹%.2f out of range", symbol, price)
        return None

    # ── Filter 2: average daily volume ────────
    avg_vol = float(df["volume"].mean())
    if avg_vol < _MIN_AVG_VOLUME:
        log.debug("Screener: %s filtered — avg vol %.0f < %.0f", symbol, avg_vol, _MIN_AVG_VOLUME)
        return None

    # ── Indicators ────────────────────────────
    df = add_atr(df, period=14)
    df = add_adx(df, period=14)
    df = add_volume_ratio(df, period=20)

    last = df.iloc[-1]

    atr_val   = last.get("atr_14",   float("nan"))
    adx_val   = last.get("adx_14",   float("nan"))
    vol_ratio = last.get("vol_ratio", float("nan"))

    import math
    if any(math.isnan(v) for v in [atr_val, adx_val]):
        log.debug("Screener: %s skipped — NaN indicators (insufficient history)", symbol)
        return None

    atr_pct = (atr_val / price) * 100

    # ── Filter 3: ATR% ────────────────────────
    if atr_pct < _MIN_ATR_PCT:
        log.debug("Screener: %s filtered — ATR%% %.3f < %.1f%%", symbol, atr_pct, _MIN_ATR_PCT)
        return None

    # ── Filter 4: ADX ────────────────────────
    if adx_val < _MIN_ADX:
        log.debug("Screener: %s filtered — ADX %.1f < %.1f", symbol, adx_val, _MIN_ADX)
        return None

    vr = float(vol_ratio) if not math.isnan(vol_ratio) else 1.0

    return {
        "symbol":    symbol,
        "price":     round(price,    2),
        "atr_pct":   round(atr_pct,  4),
        "adx":       round(adx_val,  2),
        "vol_ratio": round(vr,       4),
        "score":     0.0,   # filled in by normaliser
        "rank":      0,     # filled in by normaliser
    }


def _normalise_and_rank(entries: list[dict]) -> list[dict]:
    """
    Normalise atr_pct, adx, vol_ratio each to [0,1] then sum as composite score.
    Sort descending and assign ranks.
    """
    if not entries:
        return []

    import numpy as np

    def _norm(values: list[float]) -> list[float]:
        arr = np.array(values, dtype=float)
        lo, hi = arr.min(), arr.max()
        if hi == lo:
            return [1.0] * len(arr)
        return ((arr - lo) / (hi - lo)).tolist()

    atr_norm = _norm([e["atr_pct"]   for e in entries])
    adx_norm = _norm([e["adx"]       for e in entries])
    vol_norm = _norm([e["vol_ratio"] for e in entries])

    for i, entry in enumerate(entries):
        entry["score"] = round(atr_norm[i] + adx_norm[i] + vol_norm[i], 4)

    entries.sort(key=lambda e: e["score"], reverse=True)

    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank

    return entries


def filter_universe(symbols: list[str]) -> list[str]:
    """
    Apply all filters and return symbols that pass.
    Fetches fresh daily data for the given symbol list.

    Useful for testing a custom subset of symbols.
    """
    daily_data = get_multiple_daily(symbols, period=_FETCH_PERIOD)
    scored = _score_symbols(daily_data)
    return [e["symbol"] for e in scored]


def rank_symbols(symbols: list[str]) -> list[dict]:
    """
    Fetch data, apply filters, rank by composite score.

    Returns:
        List of scored dicts sorted descending — empty if no data.
    """
    daily_data = get_multiple_daily(symbols, period=_FETCH_PERIOD)
    return _score_symbols(daily_data)


def get_todays_watchlist() -> list[str]:
    """
    Return today's pre-selected watchlist symbols from DB.
    Returns [] if the screener has not run yet today.
    """
    date_str = today_ist().isoformat()
    rows = queries.get_watchlist(date_str)
    return [r["symbol"] for r in rows]


def _send_watchlist_alert(symbols: list[str]) -> None:
    """Fire-and-forget Telegram alert. Never raises."""
    import asyncio
    try:
        from alerts.telegram import send_watchlist
        asyncio.get_event_loop().run_until_complete(send_watchlist(symbols))
    except Exception as exc:
        log.debug("Screener: telegram alert skipped: %s", exc)
