"""
strategy/signals.py — Entry and exit signal generation

Supports multiple named strategies. Only one strategy is active at a time,
controlled by the 'active_strategy' key in app_settings (DB).

Strategies:
  ema_crossover  — EMA 9/21 crossover + ADX > 20 + volume > 1.5x (original)
  relaxed_ema    — EMA 9/21 crossover only, wider time window (9:30–15:00)
  rsi_bounce     — RSI(14) crosses below 35; exit when RSI > 65 or target/SL
  vwap_cross     — Close crosses above VWAP; exit when price falls below VWAP

Public API (unchanged):
  check_entry_signal(df, symbol)             → Optional[Signal]
  check_exit_signal(df, entry_price, since)  → Optional[str]
  calculate_targets(entry_price)             → (target, stop_loss)
  is_within_trading_hours(dt)               → bool
  generate_signals(df, symbol)               → list[Signal]   (ema_crossover only, for backtesting)
"""

import logging
import math
from datetime import datetime
from typing import Optional

import pandas as pd

from strategy.indicators import add_ema, add_atr, add_adx, add_volume_ratio, add_rsi, add_vwap

log = logging.getLogger(__name__)

# ── Shared thresholds ─────────────────────────
_EMA_FAST       = 9
_EMA_SLOW       = 21
_VOL_RATIO_MIN  = 1.5
_ADX_MIN        = 20.0
_TARGET_PCT     = 0.010    # +1.0%
_STOP_PCT       = 0.005    # -0.5%
_ENTRY_OPEN     = (9,  30)  # 09:30 IST
_ENTRY_CLOSE    = (14, 30)  # 14:30 IST
_ENTRY_CLOSE_RELAXED = (15, 0)  # 15:00 IST — relaxed_ema only
_FORCE_CLOSE    = (15, 10)  # 15:10 IST — all positions squared off
_RSI_OVERSOLD   = 35
_RSI_OVERBOUGHT = 65


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
        target    = entry * 1.010  (+1.0%)
        stop_loss = entry * 0.995  (-0.5%)
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

    if dt.weekday() >= 5:
        return False

    t = (dt.hour, dt.minute)
    return _ENTRY_OPEN <= t <= _ENTRY_CLOSE


def check_entry_signal(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """
    Check if an entry signal exists on the latest candle.
    Delegates to the active strategy's entry function.

    Args:
        df:     Normalised OHLCV DataFrame (DatetimeIndex in IST).
        symbol: NSE symbol e.g. "HDFCBANK.NS".

    Returns:
        Signal if entry conditions met, else None.
    """
    name = _get_active_strategy()
    entry_fn, _ = _REGISTRY.get(name, _REGISTRY[_DEFAULT_STRATEGY])
    return entry_fn(df, symbol)


def check_exit_signal(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
) -> Optional[str]:
    """
    Check whether an open position should be closed.
    Delegates to the active strategy's exit function.

    Returns:
        "TARGET"      — price reached +0.6% target
        "STOP_LOSS"   — price hit -0.3% stop
        "FORCE_CLOSE" — time ≥ 15:10 IST
        "RSI_EXIT"    — RSI recovered above 65 (rsi_bounce strategy)
        "VWAP_EXIT"   — price fell below VWAP (vwap_cross strategy)
        None          — hold the position
    """
    name = _get_active_strategy()
    _, exit_fn = _REGISTRY.get(name, _REGISTRY[_DEFAULT_STRATEGY])
    return exit_fn(df, entry_price, open_since)


def generate_signals(df: pd.DataFrame, symbol: str) -> list[Signal]:
    """
    Scan a full candle DataFrame and return all ema_crossover signals.
    Useful for back-testing and historical API responses.
    Time window filter is NOT applied here.

    Args:
        df:     Normalised OHLCV DataFrame.
        symbol: NSE symbol.

    Returns:
        List of Signal objects in chronological order.
    """
    if df.empty or len(df) < _EMA_SLOW + 2:
        return []

    df = _add_ema_indicators(df)
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


# ─────────────────────────────────────────────
# Strategy: ema_crossover
# ─────────────────────────────────────────────

def _entry_ema_crossover(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """EMA 9/21 crossover + ADX > 20 + volume > 1.5x. Entry window 9:30–14:30."""
    if df.empty or len(df) < _EMA_SLOW + 2:
        return None

    df = _add_ema_indicators(df)

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


def _exit_price_targets(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
) -> Optional[str]:
    """Standard price target exit: force close → target → stop loss."""
    if df.empty:
        return None

    ts    = df.index[-1]
    price = float(df["close"].iloc[-1])
    t     = (ts.hour, ts.minute)

    if t >= _FORCE_CLOSE:
        return "FORCE_CLOSE"

    target, stop_loss = calculate_targets(entry_price)

    if price >= target:
        return "TARGET"
    if price <= stop_loss:
        return "STOP_LOSS"

    return None


# ─────────────────────────────────────────────
# Strategy: relaxed_ema
# ─────────────────────────────────────────────

def _entry_relaxed_ema(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """EMA 9/21 crossover only — no ADX or volume filter. Entry window 9:30–15:00."""
    if df.empty or len(df) < _EMA_SLOW + 2:
        return None

    df = add_ema(df, period=_EMA_FAST)
    df = add_ema(df, period=_EMA_SLOW)

    ts = df.index[-1]
    t  = (ts.hour, ts.minute)
    if ts.weekday() >= 5 or not (_ENTRY_OPEN <= t <= _ENTRY_CLOSE_RELAXED):
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    if _crossover_type(prev, curr) != "BUY":
        return None

    price     = round(float(curr["close"]), 2)
    target, stop_loss = calculate_targets(price)
    ema_9  = round(float(curr[f"ema_{_EMA_FAST}"]), 2)
    ema_21 = round(float(curr[f"ema_{_EMA_SLOW}"]), 2)
    reason = f"Relaxed EMA{_EMA_FAST}/{_EMA_SLOW} BUY crossover"

    return Signal(
        symbol=symbol, side="BUY", price=price,
        target=target, stop_loss=stop_loss,
        timestamp=ts.to_pydatetime(), reason=reason,
        ema_9=ema_9, ema_21=ema_21, adx=float("nan"), vol_ratio=float("nan"),
    )


# ─────────────────────────────────────────────
# Strategy: rsi_bounce
# ─────────────────────────────────────────────

def _entry_rsi_bounce(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """Enter when RSI(14) freshly crosses below 35 (oversold). Window 9:30–14:30."""
    _RSI_WARMUP = 16  # 14 period + 2 rows for crossover detection
    if df.empty or len(df) < _RSI_WARMUP:
        return None

    df = add_rsi(df, period=14)

    ts = df.index[-1]
    if not is_within_trading_hours(ts.to_pydatetime()):
        return None

    prev_rsi = df[f"rsi_14"].iloc[-2]
    curr_rsi = df[f"rsi_14"].iloc[-1]

    if math.isnan(prev_rsi) or math.isnan(curr_rsi):
        return None

    # Fresh cross INTO oversold: prev was above threshold, curr is below
    if not (prev_rsi >= _RSI_OVERSOLD and curr_rsi < _RSI_OVERSOLD):
        return None

    price = round(float(df["close"].iloc[-1]), 2)
    target, stop_loss = calculate_targets(price)
    reason = f"RSI bounce BUY | RSI crossed below {_RSI_OVERSOLD} (RSI={curr_rsi:.1f})"

    return Signal(
        symbol=symbol, side="BUY", price=price,
        target=target, stop_loss=stop_loss,
        timestamp=ts.to_pydatetime(), reason=reason,
        ema_9=float("nan"), ema_21=float("nan"),
        adx=float("nan"), vol_ratio=float("nan"),
    )


def _exit_rsi_bounce(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
) -> Optional[str]:
    """Exit: force close → price targets → RSI recovered above 65."""
    if df.empty:
        return None

    ts    = df.index[-1]
    price = float(df["close"].iloc[-1])
    t     = (ts.hour, ts.minute)

    if t >= _FORCE_CLOSE:
        return "FORCE_CLOSE"

    target, stop_loss = calculate_targets(entry_price)
    if price >= target:
        return "TARGET"
    if price <= stop_loss:
        return "STOP_LOSS"

    # RSI recovery exit
    df = add_rsi(df, period=14)
    curr_rsi = df["rsi_14"].iloc[-1]
    if not math.isnan(curr_rsi) and curr_rsi > _RSI_OVERBOUGHT:
        return "RSI_EXIT"

    return None


# ─────────────────────────────────────────────
# Strategy: vwap_cross
# ─────────────────────────────────────────────

def _entry_vwap_cross(df: pd.DataFrame, symbol: str) -> Optional[Signal]:
    """Enter when close freshly crosses above VWAP. Window 9:30–14:30."""
    if df.empty or len(df) < 3:
        return None

    df = add_vwap(df)

    ts = df.index[-1]
    if not is_within_trading_hours(ts.to_pydatetime()):
        return None

    prev_close = float(df["close"].iloc[-2])
    curr_close = float(df["close"].iloc[-1])
    prev_vwap  = float(df["vwap"].iloc[-2])
    curr_vwap  = float(df["vwap"].iloc[-1])

    if any(math.isnan(v) for v in [prev_close, curr_close, prev_vwap, curr_vwap]):
        return None

    # Fresh cross above VWAP
    if not (prev_close < prev_vwap and curr_close > curr_vwap):
        return None

    price = round(curr_close, 2)
    target, stop_loss = calculate_targets(price)
    reason = f"VWAP cross BUY | price crossed above VWAP={curr_vwap:.2f}"

    return Signal(
        symbol=symbol, side="BUY", price=price,
        target=target, stop_loss=stop_loss,
        timestamp=ts.to_pydatetime(), reason=reason,
        ema_9=float("nan"), ema_21=float("nan"),
        adx=float("nan"), vol_ratio=float("nan"),
    )


def _exit_vwap_cross(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
) -> Optional[str]:
    """Exit: force close → price targets → price fell back below VWAP."""
    if df.empty:
        return None

    ts    = df.index[-1]
    price = float(df["close"].iloc[-1])
    t     = (ts.hour, ts.minute)

    if t >= _FORCE_CLOSE:
        return "FORCE_CLOSE"

    target, stop_loss = calculate_targets(entry_price)
    if price >= target:
        return "TARGET"
    if price <= stop_loss:
        return "STOP_LOSS"

    # VWAP invalidation exit
    df = add_vwap(df)
    curr_vwap = float(df["vwap"].iloc[-1])
    if not math.isnan(curr_vwap) and price < curr_vwap:
        return "VWAP_EXIT"

    return None


# ─────────────────────────────────────────────
# Strategy registry + dispatcher helpers
# ─────────────────────────────────────────────

_DEFAULT_STRATEGY = "ema_crossover"

_REGISTRY: dict[str, tuple] = {
    "ema_crossover": (_entry_ema_crossover, _exit_price_targets),
    "relaxed_ema":   (_entry_relaxed_ema,   _exit_price_targets),
    "rsi_bounce":    (_entry_rsi_bounce,     _exit_rsi_bounce),
    "vwap_cross":    (_entry_vwap_cross,     _exit_vwap_cross),
}

VALID_STRATEGIES = list(_REGISTRY.keys())

# Fixed priority order for parallel execution: first match on a stock wins
STRATEGY_PRIORITY: list[str] = [
    "ema_crossover",
    "relaxed_ema",
    "rsi_bounce",
    "vwap_cross",
]


def check_entry_signal_for(df: pd.DataFrame, symbol: str, strategy_name: str) -> Optional[Signal]:
    """Check entry signal for a specific strategy (bypasses active_strategy setting)."""
    entry_fn, _ = _REGISTRY.get(strategy_name, _REGISTRY[_DEFAULT_STRATEGY])
    return entry_fn(df, symbol)


def check_exit_signal_for(
    df: pd.DataFrame,
    entry_price: float,
    open_since: datetime,
    strategy_name: str,
) -> Optional[str]:
    """Check exit signal for a specific strategy (bypasses active_strategy setting)."""
    _, exit_fn = _REGISTRY.get(strategy_name, _REGISTRY[_DEFAULT_STRATEGY])
    return exit_fn(df, entry_price, open_since)


def _get_active_strategy() -> str:
    from database.queries import get_setting
    return get_setting("active_strategy", _DEFAULT_STRATEGY) or _DEFAULT_STRATEGY


# ─────────────────────────────────────────────
# Private helpers (ema_crossover / generate_signals)
# ─────────────────────────────────────────────

def _add_ema_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = add_ema(df, period=_EMA_FAST)
    df = add_ema(df, period=_EMA_SLOW)
    df = add_atr(df, period=14)
    df = add_adx(df, period=14)
    df = add_volume_ratio(df, period=20)
    return df


def _crossover_type(prev: pd.Series, curr: pd.Series) -> Optional[str]:
    """Detect EMA crossover between two consecutive rows."""
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
    """Assemble a Signal from a single candle row (ema_crossover style)."""
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
