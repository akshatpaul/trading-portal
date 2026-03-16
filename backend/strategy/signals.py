"""
strategy/signals.py — Entry and exit signal generation

Entry signal (all conditions must be true):
  - EMA9 crosses above EMA21 (bullish crossover)
  - vol_ratio > 1.5  (current volume > 1.5× 20-period average)
  - ADX > 20         (confirmed trend, not choppy)
  - Time between 9:30 AM and 2:30 PM IST
  - Applicable only for long (BUY) entries in this version

Exit triggers (checked on each new candle):
  - Price ≥ target     → "TARGET"      (+0.6% from entry)
  - Price ≤ stop_loss  → "STOP_LOSS"   (-0.3% from entry)
  - Time ≥ 3:10 PM IST → "FORCE_CLOSE" (end-of-day square-off)

Use generate_signals() to scan a full DataFrame for all crossovers.
Use check_entry_signal() to evaluate only the latest candle.
"""

import logging
import math
from datetime import datetime
from typing import Optional

import pandas as pd

from strategy.indicators import add_ema, add_atr, add_adx, add_volume_ratio

log = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────
_EMA_FAST       = 9
_EMA_SLOW       = 21
_VOL_RATIO_MIN  = 1.5
_ADX_MIN        = 20.0
_TARGET_PCT     = 0.006    # +0.6%
_STOP_PCT       = 0.003    # -0.3%
_ENTRY_OPEN     = (9,  30)  # 09:30 IST
_ENTRY_CLOSE    = (14, 30)  # 14:30 IST — no new entries after this
_FORCE_CLOSE    = (15, 10)  # 15:10 IST — all positions squared off


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

class Signal:
    """Represents a single trading signal."""

    def __init__(
        self,
        symbol: str,
        side: str,           # "BUY" | "SELL"
        price: float,
        target: float,
        stop_loss: float,
        timestamp: datetime,
        reason: str,
        ema_9: float,
        ema_21: float,
        adx: float,
        vol_ratio: float,
    ):
        self.symbol    = symbol
        self.side      = side
        self.price     = price
        self.target    = target
        self.stop_loss = stop_loss
        self.timestamp = timestamp
        self.reason    = reason
        self.ema_9     = ema_9
        self.ema_21    = ema_21
        self.adx       = adx
        self.vol_ratio = vol_ratio

    def to_dict(self) -> dict:
        return {
            "symbol":    self.symbol,
            "side":      self.side,
            "price":     self.price,
            "target":    self.target,
            "stop_loss": self.stop_loss,
            "timestamp": self.timestamp.isoformat(),
            "reason":    self.reason,
            "ema_9":     self.ema_9,
            "ema_21":    self.ema_21,
            "adx":       self.adx,
            "vol_ratio": self.vol_ratio,
        }


def calculate_targets(entry_price: float) -> tuple[float, float]:
    """
    Calculate target and stop loss from entry price.

    Returns:
        (target_price, stop_loss_price)
        target    = entry * 1.006  (+0.6%)
        stop_loss = entry * 0.997  (-0.3%)
    """
    target    = round(entry_price * (1 + _TARGET_PCT), 2)
    stop_loss = round(entry_price * (1 - _STOP_PCT),   2)
    return target, stop_loss


def is_within_trading_hours(dt: Optional[datetime] = None) -> bool:
    """
    Returns True if dt (default: now IST) is within 9:30–14:30 IST
    on a weekday (Mon–Fri). Does not check public holidays.

    Args:
        dt: timezone-aware datetime; if None uses current time.
    """
    if dt is None:
        from utils.helpers import now_ist
        dt = now_ist()

    # Weekday check: 0=Mon … 4=Fri
    if dt.weekday() >= 5:
        return False

    t = (dt.hour, dt.minute)
    return _ENTRY_OPEN <= t <= _ENTRY_CLOSE


def check_entry_signal(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """
    Check if an entry signal exists on the latest candle.

    Computes indicators internally; caller passes raw OHLCV DataFrame.
    Checks time window — returns None outside 9:30–14:30 IST.

    Args:
        df:     Normalised OHLCV DataFrame (DatetimeIndex in IST).
        symbol: NSE symbol e.g. "HDFCBANK.NS".

    Returns:
        Signal if BUY conditions met, else None.
    """
    if df.empty or len(df) < _EMA_SLOW + 2:
        return None

    df = _add_indicators(df)

    # Time gate — only generate entries during trading hours
    ts = df.index[-1]
    if not is_within_trading_hours(ts.to_pydatetime()):
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    if _crossover_type(prev, curr) != "BUY":
        return None

    if not _passes_filters(curr):
        return None

    return _build_signal(symbol, ts, curr)


def check_exit_signal(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
) -> Optional[str]:
    """
    Check whether an open position should be closed.

    Evaluates on the latest candle close price.

    Returns:
        "TARGET"      — price reached +0.6% target
        "STOP_LOSS"   — price hit -0.3% stop
        "FORCE_CLOSE" — time ≥ 15:10 IST
        None          — hold the position
    """
    if df.empty:
        return None

    ts    = df.index[-1]
    price = float(df["close"].iloc[-1])
    t     = (ts.hour, ts.minute)

    # Force square-off at end of day
    if t >= _FORCE_CLOSE:
        return "FORCE_CLOSE"

    target, stop_loss = calculate_targets(entry_price)

    if price >= target:
        return "TARGET"
    if price <= stop_loss:
        return "STOP_LOSS"

    return None


def generate_signals(df: pd.DataFrame, symbol: str) -> list[Signal]:
    """
    Scan a full candle DataFrame and return all crossover signals that pass
    filters. Useful for back-testing and historical API responses.

    Time window filter is NOT applied here (suitable for daily/historical data).

    Args:
        df:     Normalised OHLCV DataFrame.
        symbol: NSE symbol.

    Returns:
        List of Signal objects in chronological order.
    """
    if df.empty or len(df) < _EMA_SLOW + 2:
        return []

    df = _add_indicators(df)
    signals: list[Signal] = []

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]

        stype = _crossover_type(prev, curr)
        if stype is None:
            continue
        if not _passes_filters(curr):
            continue

        sig = _build_signal(symbol, df.index[i], curr, side=stype)
        signals.append(sig)

    log.debug("generate_signals: %s → %d signals", symbol, len(signals))
    return signals


# ── Private helpers ───────────────────────────

def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = add_ema(df, period=_EMA_FAST)
    df = add_ema(df, period=_EMA_SLOW)
    df = add_atr(df, period=14)
    df = add_adx(df, period=14)
    df = add_volume_ratio(df, period=20)
    return df


def _crossover_type(prev: pd.Series, curr: pd.Series) -> Optional[str]:
    """
    Detect EMA crossover between two consecutive rows.
    Returns 'BUY', 'SELL', or None (no crossover / NaN).
    """
    p9  = prev.get(f"ema_{_EMA_FAST}")
    p21 = prev.get(f"ema_{_EMA_SLOW}")
    c9  = curr.get(f"ema_{_EMA_FAST}")
    c21 = curr.get(f"ema_{_EMA_SLOW}")

    if any(v is None or math.isnan(v) for v in [p9, p21, c9, c21]):
        return None

    prev_above = p9 > p21
    curr_above = c9 > c21

    if not prev_above and curr_above:
        return "BUY"
    if prev_above and not curr_above:
        return "SELL"
    return None


def _passes_filters(row: pd.Series) -> bool:
    """True if ADX and vol_ratio thresholds are met."""
    adx = row.get("adx_14")
    vol = row.get("vol_ratio")

    if adx is None or vol is None:
        return False
    if math.isnan(adx) or math.isnan(vol):
        return False

    return float(adx) >= _ADX_MIN and float(vol) >= _VOL_RATIO_MIN


def _build_signal(
    symbol: str,
    ts,
    row: pd.Series,
    side: str = "BUY",
) -> Signal:
    """Assemble a Signal from a single candle row."""
    def _f(key: str, dp: int = 2) -> float:
        v = row.get(key)
        if v is None or math.isnan(v):
            return float("nan")
        return round(float(v), dp)

    price     = round(float(row["close"]), 2)
    target, stop_loss = calculate_targets(price)
    ema_9  = _f(f"ema_{_EMA_FAST}")
    ema_21 = _f(f"ema_{_EMA_SLOW}")
    adx    = _f("adx_14")
    vol    = _f("vol_ratio", 4)

    reason = (
        f"EMA{_EMA_FAST}/{_EMA_SLOW} {side} crossover | "
        f"ADX={adx:.1f} | vol_ratio={vol:.2f}"
    )

    return Signal(
        symbol=symbol,
        side=side,
        price=price,
        target=target,
        stop_loss=stop_loss,
        timestamp=ts.to_pydatetime(),
        reason=reason,
        ema_9=ema_9,
        ema_21=ema_21,
        adx=adx,
        vol_ratio=vol,
    )
