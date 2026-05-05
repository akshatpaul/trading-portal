"""
strategy/risk_manager.py — Position sizing and safety limits

HARDCODED SAFETY RULES (UI cannot override these):
  - Max capital per trade:  ₹50,000
  - Max leverage:           2x
  - Max trades per day:     6
  - Max daily loss:         ₹2,000
  - Min capital to trade:   ₹200
  - No trading 9:15–9:30 AM IST
  - Force close at 3:10 PM IST

These limits exist independently of .env settings as a second
layer of protection. If both disagree, the stricter value wins.
"""

import math
from datetime import datetime
from typing import Optional

# ── Hardcoded limits — DO NOT change without explicit user instruction ──
_MAX_POSITION_SIZE  = 2_00_000.0 # ₹ max capital deployed per trade (₹10L ÷ 5 stocks)
_MAX_LEVERAGE       = 2.0
_MAX_TRADES_PER_DAY = 6
_MAX_DAILY_LOSS     = 10_000.0  # ₹ — 1% of ₹10L capital
_MIN_CAPITAL        = 200.0     # ₹ — floor of Nifty 50 price range
_FORCE_CLOSE_TIME   = (15, 10)  # HH:MM IST


def calculate_position_size(
    capital: float,
    price: float,
    stop_loss: float,
) -> int:
    """
    Calculate quantity to buy given risk parameters.

    Logic:
      - Max spend = min(capital, _MAX_POSITION_SIZE)
      - Quantity  = floor(max_spend / price)
      - Minimum   = 1  (always trade at least one share)

    stop_loss is accepted for API consistency but position sizing
    uses the capital-capped approach rather than a risk-per-share model.

    Args:
        capital:   available capital in ₹
        price:     entry price per share
        stop_loss: stop-loss price (not used in sizing formula)

    Returns:
        Integer quantity ≥ 1.
    """
    if price <= 0:
        return 1

    max_spend = min(capital, _MAX_POSITION_SIZE)
    quantity  = math.floor(max_spend / price)
    return max(quantity, 1)


def can_place_trade(
    daily_loss: float,
    trades_today: int,
    capital: float,
) -> tuple[bool, str]:
    """
    Check all safety rules before placing a trade.

    Checks (in order):
      1. Daily loss limit not exceeded
      2. Max trades per day not exceeded
      3. Sufficient capital available

    Returns:
        (allowed: bool, reason: str)
        reason is empty string when allowed=True.
    """
    if daily_loss >= _MAX_DAILY_LOSS:
        return False, (
            f"Daily loss limit of ₹{_MAX_DAILY_LOSS:.0f} reached "
            f"(₹{daily_loss:.2f} lost today)"
        )

    if trades_today >= _MAX_TRADES_PER_DAY:
        return False, (
            f"Max {_MAX_TRADES_PER_DAY} trades per day reached "
            f"({trades_today} placed today)"
        )

    if capital < _MIN_CAPITAL:
        return False, (
            f"Insufficient capital: ₹{capital:.2f} "
            f"(minimum ₹{_MIN_CAPITAL:.0f} required)"
        )

    return True, ""


def is_force_close_time(dt: Optional[datetime] = None) -> bool:
    """
    Returns True if IST time is at or past 3:10 PM (force square-off).
    """
    if dt is None:
        from utils.helpers import now_ist
        dt = now_ist()

    return (dt.hour, dt.minute) >= _FORCE_CLOSE_TIME


def check_daily_loss_limit(daily_loss: float) -> bool:
    """
    Returns True if the daily loss limit has been hit.
    daily_loss should be a positive number representing total loss today.
    """
    return daily_loss >= _MAX_DAILY_LOSS


def get_limits() -> dict:
    """Return hardcoded limits as a dict (for API/UI display)."""
    return {
        "max_position_size":  _MAX_POSITION_SIZE,
        "max_leverage":       _MAX_LEVERAGE,
        "max_trades_per_day": _MAX_TRADES_PER_DAY,
        "max_daily_loss":     _MAX_DAILY_LOSS,
        "min_capital":        _MIN_CAPITAL,
        "force_close_time":   f"{_FORCE_CLOSE_TIME[0]:02d}:{_FORCE_CLOSE_TIME[1]:02d}",
    }
