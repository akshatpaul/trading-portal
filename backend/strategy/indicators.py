"""
strategy/indicators.py — Technical indicator calculations

All indicators implemented from scratch for reliability and transparency.
No pandas-ta dependency — avoids pandas version compatibility issues.

Smoothing methods:
  - EMA   : alpha = 2 / (period + 1)  — standard exponential MA
  - RMA   : alpha = 1 / period         — Wilder's smoothing (ATR, ADX, DI)

All functions:
  - Accept a normalised OHLCV DataFrame
  - Return a new DataFrame with indicator columns appended
  - Never modify the input DataFrame (always copy)
  - Produce NaN for the warm-up rows before enough data is available

Note: columns are appended via pd.concat to avoid pandas Copy-on-Write issues.
"""

import pandas as pd
import numpy as np


# ── EMA ───────────────────────────────────────

def add_ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.DataFrame:
    """
    Append EMA column: ema_{period}

    Uses standard EMA: alpha = 2 / (period + 1)
    Matches TradingView's EMA indicator.

    Args:
        df:     candle DataFrame with the source column present
        period: EMA period e.g. 9 or 21
        col:    source column (default 'close')

    Returns:
        df with new column  ema_{period}
    """
    ema = (
        df[col]
        .ewm(span=period, adjust=False, min_periods=period)
        .mean()
        .rename(f"ema_{period}")
    )
    return pd.concat([df, ema], axis=1)


# ── ATR ───────────────────────────────────────

def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Append ATR column: atr_{period}

    True Range = max(high - low,
                     |high - prev_close|,
                     |low  - prev_close|)
    ATR = Wilder's RMA(TR, period)   alpha = 1/period
    Matches TradingView's ATR indicator.

    Returns:
        df with new column  atr_{period}
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = (
        tr
        .ewm(alpha=1.0 / period, adjust=False, min_periods=period)
        .mean()
        .rename(f"atr_{period}")
    )
    return pd.concat([df, atr], axis=1)


# ── ADX ───────────────────────────────────────

def add_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Append ADX columns: adx_{period}, dmp_{period}, dmn_{period}

    +DM = high - prev_high  if > max(0, prev_low - low)  else 0
    -DM = prev_low - low    if > max(0, high - prev_high) else 0
    +DI = 100 * RMA(+DM, period) / ATR
    -DI = 100 * RMA(-DM, period) / ATR
    DX  = 100 * |+DI - -DI| / (+DI + -DI)
    ADX = RMA(DX, period)

    All smoothing uses Wilder's RMA (alpha = 1/period).
    Matches TradingView's DMI/ADX indicator.

    Returns:
        df with new columns  adx_{period}, dmp_{period}, dmn_{period}
        dmp = +DI,  dmn = -DI
    """
    alpha = 1.0 / period

    # ── Directional movements ──────────────────
    high_diff = df["high"] - df["high"].shift(1)
    low_diff  = df["low"].shift(1) - df["low"]

    plus_dm  = high_diff.where((high_diff > low_diff)  & (high_diff > 0), 0.0)
    minus_dm = low_diff.where( (low_diff  > high_diff) & (low_diff  > 0), 0.0)

    # ── True Range ────────────────────────────
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)

    # ── Wilder's smoothing ────────────────────
    smooth_tr  = tr.ewm(      alpha=alpha, adjust=False, min_periods=period).mean()
    smooth_pdm = plus_dm.ewm( alpha=alpha, adjust=False, min_periods=period).mean()
    smooth_ndm = minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

    # ── Directional indices ───────────────────
    plus_di  = (100 * smooth_pdm / smooth_tr).rename(f"dmp_{period}")
    minus_di = (100 * smooth_ndm / smooth_tr).rename(f"dmn_{period}")

    # ── DX and ADX ────────────────────────────
    di_sum = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / di_sum).where(di_sum != 0, 0.0)
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean().rename(f"adx_{period}")

    return pd.concat([df, adx, plus_di, minus_di], axis=1)


# ── RSI ───────────────────────────────────────

def add_rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.DataFrame:
    """
    Append RSI column: rsi_{period}

    Uses Wilder's smoothed RS (RMA):
        gain = max(close - prev_close, 0)
        loss = max(prev_close - close, 0)
        RS   = RMA(gain, period) / RMA(loss, period)
        RSI  = 100 - (100 / (1 + RS))

    Returns:
        df with new column  rsi_{period}
    """
    delta    = df[col].diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    alpha    = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, float("nan"))
    rsi      = (100 - (100 / (1 + rs))).rename(f"rsi_{period}")
    return pd.concat([df, rsi], axis=1)


# ── VWAP ──────────────────────────────────────

def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append intraday VWAP column: vwap

    VWAP = cumsum(typical_price * volume) / cumsum(volume)
    typical_price = (high + low + close) / 3

    Resets at midnight IST (start of each new trading session).
    The DataFrame index must be a timezone-aware DatetimeIndex (IST).

    Returns:
        df with new column  vwap
    """
    tp   = (df["high"] + df["low"] + df["close"]) / 3
    tpv  = tp * df["volume"]

    # Group by calendar date in IST so VWAP resets each session
    date_key = df.index.normalize()   # midnight of each day, same tz

    vwap = (
        tpv.groupby(date_key).cumsum()
        / df["volume"].groupby(date_key).cumsum()
    ).rename("vwap")

    return pd.concat([df, vwap], axis=1)


# ── Volume ratio ──────────────────────────────

def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Append volume ratio column: vol_ratio

    vol_ratio = current_volume / rolling_mean(volume, period)

    A ratio > 1.5 means current candle has 50%+ above-average volume.
    The entry signal requires vol_ratio > 1.5.

    Returns:
        df with new column  vol_ratio
    """
    rolling_avg = df["volume"].rolling(window=period, min_periods=period).mean()
    vol_ratio   = (df["volume"] / rolling_avg).rename("vol_ratio")
    return pd.concat([df, vol_ratio], axis=1)


# ── Convenience ───────────────────────────────

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all indicators in one call.

    Appended columns:
        ema_9, ema_21,
        atr_14,
        adx_14, dmp_14, dmn_14,
        rsi_14,
        vwap,
        vol_ratio

    Returns:
        df with all indicator columns appended.
    """
    df = add_ema(df, period=9)
    df = add_ema(df, period=21)
    df = add_atr(df, period=14)
    df = add_adx(df, period=14)
    df = add_rsi(df, period=14)
    df = add_vwap(df)
    df = add_volume_ratio(df, period=20)
    return df
