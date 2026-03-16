"""
data/candle_builder.py — Candle assembly and storage

Responsibilities:
  - Normalise raw yfinance DataFrames (column names, timezone, types)
  - Convert timestamps to IST (Asia/Kolkata)
  - Convert to DB-ready records and back
"""

import pandas as pd
from typing import Optional

IST_TIMEZONE = "Asia/Kolkata"

_OHLCV = ["open", "high", "low", "close", "volume"]


def _empty_candle_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_OHLCV)


def normalise_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise a yfinance DataFrame into a clean OHLCV DataFrame.

    Handles:
      - Ticker.history() output  → flat columns (Open, High, …, Dividends, …)
      - yf.download() single     → flat or (Price, Ticker) MultiIndex
      - yf.download() already xs → flat (Price) columns

    Returns:
        DataFrame with lowercase columns: open, high, low, close, volume
        Index: DatetimeIndex in IST timezone, ascending.
    """
    if df is None or df.empty:
        return _empty_candle_df()

    df = df.copy()

    # ── 1. Flatten MultiIndex if present ─────
    if isinstance(df.columns, pd.MultiIndex):
        # yf.download multi-ticker: levels are (Price, Ticker)
        # yf.download single-ticker new API: same structure, one ticker
        # We want the Price level (whichever level contains OHLCV names)
        ohlcv_set = {"open", "high", "low", "close", "volume"}
        l0 = {str(c).lower() for c in df.columns.get_level_values(0)}
        l1 = {str(c).lower() for c in df.columns.get_level_values(1)}

        if len(l0 & ohlcv_set) >= 4:
            df.columns = df.columns.get_level_values(0)
        elif len(l1 & ohlcv_set) >= 4:
            df.columns = df.columns.get_level_values(1)
        else:
            # Last resort: flatten to level 0
            df.columns = df.columns.get_level_values(0)

    # ── 2. Lowercase all column names ─────────
    df.columns = [str(c).lower() for c in df.columns]

    # ── 3. Keep only OHLCV ───────────────────
    missing = [c for c in _OHLCV if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns after normalisation: {missing}. "
            f"Got: {list(df.columns)}"
        )
    df = df[_OHLCV].copy()

    # ── 4. Convert index to IST ───────────────
    if hasattr(df.index, "tz"):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(IST_TIMEZONE)
        else:
            df.index = df.index.tz_convert(IST_TIMEZONE)

    # ── 5. Drop bad rows ──────────────────────
    df = df.dropna(subset=_OHLCV)
    df = df[df["volume"] > 0]

    # ── 6. Enforce dtypes ─────────────────────
    for col in ["open", "high", "low", "close"]:
        df.loc[:, col] = df[col].astype(float)
    df.loc[:, "volume"] = df["volume"].astype(int)

    return df.sort_index()


def candles_to_records(
    df: pd.DataFrame,
    symbol: str,
    interval: str = "5m",
) -> list[dict]:
    """
    Convert a normalised candle DataFrame to a list of dicts for DB insertion.

    Returns:
        List of dicts: {symbol, interval, timestamp, open, high, low, close, volume}
        timestamp is ISO-8601 string in IST with offset.
    """
    if df.empty:
        return []

    records = []
    for ts, row in df.iterrows():
        records.append({
            "symbol":    symbol,
            "interval":  interval,
            "timestamp": ts.isoformat(),
            "open":      round(float(row["open"]),  2),
            "high":      round(float(row["high"]),  2),
            "low":       round(float(row["low"]),   2),
            "close":     round(float(row["close"]), 2),
            "volume":    int(row["volume"]),
        })
    return records


def records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert DB records (from queries.get_candles) back to a candle DataFrame.
    Index is DatetimeIndex in IST, ascending.
    """
    if not records:
        return _empty_candle_df()

    df = pd.DataFrame(records)
    df.loc[:, "timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(IST_TIMEZONE)
    df = df.set_index("timestamp").sort_index()

    # Keep only OHLCV (drop symbol, interval, id if present)
    keep = [c for c in _OHLCV if c in df.columns]
    return df[keep]
