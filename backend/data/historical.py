"""
data/historical.py — Historical candle fetching for backtesting

yfinance limit: 5-minute data is available for ~60 days back only.

Strategy:
  - fetch_historical_5min: direct fetch for a date range (Backtest page)
  - fetch_and_cache: fetch + persist to SQLite, return merged result
                     so repeated calls don't re-download old data
"""

import logging
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import Optional

from data.candle_builder import normalise_candles, candles_to_records, records_to_dataframe
from database import queries

log = logging.getLogger(__name__)


def fetch_historical_5min(
    symbol: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Fetch 5-minute historical candles for a symbol between start and end dates.

    Args:
        symbol: e.g. "HDFCBANK.NS"
        start:  inclusive start date
        end:    inclusive end date (yfinance end is exclusive, we add 1 day)

    Returns:
        Normalised candle DataFrame (IST index, ascending).
        Empty DataFrame on error or if no data.

    Note:
        yfinance 5-min history is limited to ~60 days back.
        Requesting older data silently returns empty.
    """
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),   # yfinance end is exclusive
            interval="5m",
            auto_adjust=True,
            prepost=False,
        )
        if raw.empty:
            log.warning(
                "fetch_historical_5min: no data for %s %s→%s",
                symbol, start, end,
            )
            return pd.DataFrame()
        return normalise_candles(raw)
    except Exception as exc:
        log.error(
            "fetch_historical_5min failed for %s %s→%s: %s",
            symbol, start, end, exc,
        )
        return pd.DataFrame()


def fetch_and_cache(symbol: str, period: str = "60d") -> pd.DataFrame:
    """
    Fetch 5-minute candles and persist new ones to SQLite.

    On first call: downloads full period, stores all candles.
    On repeat calls: checks what's already cached, only fetches
    data newer than the latest cached timestamp.

    Returns:
        Complete candle DataFrame from cache (all stored history for symbol).
        Empty DataFrame if fetch fails and cache is empty.
    """
    # ── 1. Load what we already have ─────────
    cached_records = queries.get_candles(symbol, interval="5m", limit=10_000)
    cached_df = records_to_dataframe(cached_records)

    # ── 2. Determine fetch range ──────────────
    if not cached_df.empty:
        latest_cached = cached_df.index[-1].date()
        # Only fetch from the day after last cached date to avoid re-fetching
        # Use a small overlap (1 day) to catch any candles we may have missed
        fetch_start = latest_cached - timedelta(days=1)
        fetch_period = None  # will use start/end instead
    else:
        fetch_start = None
        fetch_period = period

    # ── 3. Fetch from yfinance ────────────────
    try:
        ticker = yf.Ticker(symbol)
        if fetch_period:
            raw = ticker.history(
                period=fetch_period,
                interval="5m",
                auto_adjust=True,
                prepost=False,
            )
        else:
            raw = ticker.history(
                start=fetch_start.isoformat(),
                end=(date.today() + timedelta(days=1)).isoformat(),
                interval="5m",
                auto_adjust=True,
                prepost=False,
            )
    except Exception as exc:
        log.error("fetch_and_cache: yfinance fetch failed for %s: %s", symbol, exc)
        return cached_df  # return what we have

    if raw.empty:
        log.warning("fetch_and_cache: empty response for %s", symbol)
        return cached_df

    # ── 4. Normalise and persist ──────────────
    new_df = normalise_candles(raw)
    if not new_df.empty:
        records = candles_to_records(new_df, symbol, interval="5m")
        inserted = queries.upsert_candles(records)
        log.info(
            "fetch_and_cache: %s — %d new candles stored (total fetched: %d)",
            symbol, inserted, len(records),
        )

    # ── 5. Return full cached history ─────────
    all_records = queries.get_candles(symbol, interval="5m", limit=10_000)
    return records_to_dataframe(all_records)
