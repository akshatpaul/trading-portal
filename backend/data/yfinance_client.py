"""
data/yfinance_client.py — yfinance market data client

Note: yfinance provides ~15-minute delayed data on live feeds.
      This is clearly labelled in the UI and is acceptable for POC.

Design decisions:
  - Ticker.history() for single-symbol fetches (reliable flat columns)
  - yf.download()    for batch screener fetches (one network round-trip)
  - All errors are caught and logged; functions return empty DataFrame / None
    so callers never crash due to a data blip.
"""

import logging
import yfinance as yf
import pandas as pd
from typing import Optional

from data.candle_builder import normalise_candles

log = logging.getLogger(__name__)

DATA_DELAY_MINUTES = 15  # yfinance live data lag

NIFTY50_SYMBOLS: list[str] = [
    "HDFCBANK.NS", "RELIANCE.NS", "TCS.NS", "INFY.NS",
    "ICICIBANK.NS", "HINDUNILVR.NS", "ITC.NS", "SBIN.NS",
    "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS",
    "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "NESTLEIND.NS", "BAJFINANCE.NS",
    "BAJAJFINSV.NS", "TECHM.NS", "SUNPHARMA.NS",
    "HCLTECH.NS", "ONGC.NS", "POWERGRID.NS", "NTPC.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "COALINDIA.NS", "DIVISLAB.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "INDUSINDBK.NS",
    "JSWSTEEL.NS", "M&M.NS", "CIPLA.NS", "APOLLOHOSP.NS",
    "BAJAJ-AUTO.NS", "BPCL.NS", "BRITANNIA.NS",
    "HDFCLIFE.NS", "SBILIFE.NS", "TATACONSUM.NS",
    "UPL.NS", "VEDL.NS",
]


def get_5min_candles(symbol: str, period: str = "5d") -> pd.DataFrame:
    """
    Fetch 5-minute OHLCV candles for a single NSE symbol.

    Args:
        symbol: e.g. "HDFCBANK.NS"
        period: yfinance period string — "1d", "5d", "60d", etc.
                Note: yfinance limits 5-min history to ~60 days.

    Returns:
        Normalised DataFrame (open, high, low, close, volume), IST index.
        Empty DataFrame on error.
    """
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            period=period,
            interval="5m",
            auto_adjust=True,
            prepost=False,
        )
        if raw.empty:
            log.warning("get_5min_candles: empty response for %s", symbol)
            return pd.DataFrame()
        return normalise_candles(raw)
    except Exception as exc:
        log.error("get_5min_candles failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def get_daily_candles(symbol: str, period: str = "30d") -> pd.DataFrame:
    """
    Fetch daily OHLCV candles for a single NSE symbol.
    Used by the pre-market screener.

    Args:
        symbol: e.g. "HDFCBANK.NS"
        period: e.g. "30d", "60d"

    Returns:
        Normalised daily DataFrame, IST index.
        Empty DataFrame on error.
    """
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            period=period,
            interval="1d",
            auto_adjust=True,
            prepost=False,
        )
        if raw.empty:
            log.warning("get_daily_candles: empty response for %s", symbol)
            return pd.DataFrame()
        return normalise_candles(raw)
    except Exception as exc:
        log.error("get_daily_candles failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def get_latest_price(symbol: str) -> Optional[float]:
    """
    Fetch the most recent available close price for a symbol.
    Data will be ~15 minutes delayed.

    Returns:
        Latest close price (float) or None on error.
    """
    try:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(period="1d", interval="5m", auto_adjust=True, prepost=False)
        if raw.empty:
            return None
        df = normalise_candles(raw)
        if df.empty:
            return None
        return float(df["close"].iloc[-1])
    except Exception as exc:
        log.error("get_latest_price failed for %s: %s", symbol, exc)
        return None


def get_multiple_daily(
    symbols: list[str],
    period: str = "25d",
) -> dict[str, pd.DataFrame]:
    """
    Batch-fetch daily candles for multiple NSE symbols in one network call.
    Used by the screener to pull all Nifty 50 stocks at once.

    Args:
        symbols: list of NSE symbols e.g. ["HDFCBANK.NS", "TCS.NS"]
        period:  e.g. "25d"

    Returns:
        Dict mapping symbol → normalised daily DataFrame.
        Symbols with errors are omitted from the result.
    """
    if not symbols:
        return {}

    try:
        raw = yf.download(
            tickers=symbols,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",   # MultiIndex: (Ticker, Price)
        )
    except Exception as exc:
        log.error("get_multiple_daily: yf.download failed: %s", exc)
        return {}

    result: dict[str, pd.DataFrame] = {}

    if raw.empty:
        return result

    # Single symbol edge-case: yf.download may return flat columns
    if not isinstance(raw.columns, pd.MultiIndex) and len(symbols) == 1:
        try:
            result[symbols[0]] = normalise_candles(raw)
        except Exception as exc:
            log.warning("get_multiple_daily: normalise failed for %s: %s", symbols[0], exc)
        return result

    # Multi-symbol: columns are (Ticker, Price) with group_by="ticker"
    for symbol in symbols:
        try:
            sym_df = raw[symbol].copy()         # slice by ticker → flat (Price) columns
            if sym_df.empty:
                continue
            result[symbol] = normalise_candles(sym_df)
        except KeyError:
            log.debug("get_multiple_daily: no data for %s", symbol)
        except Exception as exc:
            log.warning("get_multiple_daily: failed for %s: %s", symbol, exc)

    return result
