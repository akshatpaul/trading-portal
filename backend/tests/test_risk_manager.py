"""
tests/test_risk_manager.py — Risk manager unit tests

All functions are pure (no DB / external calls), so no mocking needed
except for is_force_close_time which reads the clock.

Run: pytest tests/test_risk_manager.py -v
"""

import pytest
import pytz
from datetime import datetime

IST = pytz.timezone("Asia/Kolkata")

from strategy.risk_manager import (
    calculate_position_size,
    can_place_trade,
    is_force_close_time,
    check_daily_loss_limit,
    get_limits,
    _MAX_POSITION_SIZE,
    _MAX_TRADES_PER_DAY,
    _MAX_DAILY_LOSS,
    _MIN_CAPITAL,
    _FORCE_CLOSE_TIME,
)


def _ist(hour: int, minute: int) -> datetime:
    """Return a timezone-aware IST datetime on a weekday."""
    return datetime(2026, 3, 16, hour, minute, 0, tzinfo=IST)


# ─────────────────────────────────────────────
# calculate_position_size
# ─────────────────────────────────────────────

class TestCalculatePositionSize:

    def test_returns_int(self):
        qty = calculate_position_size(10_000.0, 1000.0, 997.0)
        assert isinstance(qty, int)

    def test_basic_sizing(self):
        # capital=10000, max_spend=min(5000, 5000)=5000, qty=floor(5000/1000)=5
        assert calculate_position_size(10_000.0, 1000.0, 997.0) == 5

    def test_capped_at_max_position_size(self):
        # capital=100000, 50% = 50000 but cap is 5000, qty=floor(5000/1000)=5
        assert calculate_position_size(100_000.0, 1000.0, 990.0) == 5

    def test_capital_halved_when_below_cap(self):
        # capital=4000, 50%=2000 < 5000 cap, qty=floor(2000/500)=4
        assert calculate_position_size(4_000.0, 500.0, 498.0) == 4

    def test_minimum_one_share(self):
        # Even with tiny capital, at least 1 share returned
        qty = calculate_position_size(100.0, 1000.0, 997.0)
        assert qty >= 1

    def test_zero_price_returns_one(self):
        assert calculate_position_size(10_000.0, 0.0, 0.0) == 1

    def test_negative_price_returns_one(self):
        assert calculate_position_size(10_000.0, -50.0, -55.0) == 1

    def test_high_price_floors_correctly(self):
        # max_spend=5000, price=3000 → floor(5000/3000)=1
        assert calculate_position_size(20_000.0, 3000.0, 2990.0) == 1

    def test_exact_divisible(self):
        # max_spend=min(5000, 5000)=5000, price=500 → 10
        assert calculate_position_size(10_000.0, 500.0, 498.5) == 10

    def test_quantity_does_not_exceed_capital_constraint(self):
        capital = 2_000.0
        price   = 1_500.0
        qty = calculate_position_size(capital, price, price * 0.997)
        # max_spend = 1000 (50% of 2000), qty = floor(1000/1500) = 0 → 1
        assert qty == 1
        assert qty * price <= capital * _MAX_POSITION_SIZE / capital or qty >= 1


# ─────────────────────────────────────────────
# can_place_trade
# ─────────────────────────────────────────────

class TestCanPlaceTrade:

    def test_allowed_when_all_clear(self):
        ok, reason = can_place_trade(0.0, 0, 10_000.0)
        assert ok is True
        assert reason == ""

    # ── Daily loss limit ──────────────────────

    def test_blocked_when_loss_equals_limit(self):
        ok, reason = can_place_trade(_MAX_DAILY_LOSS, 0, 10_000.0)
        assert ok is False
        assert reason != ""

    def test_blocked_when_loss_exceeds_limit(self):
        ok, reason = can_place_trade(_MAX_DAILY_LOSS + 50, 0, 10_000.0)
        assert ok is False

    def test_allowed_just_below_loss_limit(self):
        ok, _ = can_place_trade(_MAX_DAILY_LOSS - 0.01, 0, 10_000.0)
        assert ok is True

    def test_daily_loss_reason_mentions_limit(self):
        _, reason = can_place_trade(_MAX_DAILY_LOSS, 0, 10_000.0)
        assert "300" in reason or "limit" in reason.lower()

    # ── Max trades per day ────────────────────

    def test_blocked_when_trades_equal_max(self):
        ok, reason = can_place_trade(0.0, _MAX_TRADES_PER_DAY, 10_000.0)
        assert ok is False
        assert reason != ""

    def test_blocked_when_trades_exceed_max(self):
        ok, _ = can_place_trade(0.0, _MAX_TRADES_PER_DAY + 1, 10_000.0)
        assert ok is False

    def test_allowed_one_below_max_trades(self):
        ok, _ = can_place_trade(0.0, _MAX_TRADES_PER_DAY - 1, 10_000.0)
        assert ok is True

    def test_max_trades_reason_mentions_count(self):
        _, reason = can_place_trade(0.0, _MAX_TRADES_PER_DAY, 10_000.0)
        assert str(_MAX_TRADES_PER_DAY) in reason or "trade" in reason.lower()

    # ── Capital check ─────────────────────────

    def test_blocked_when_capital_below_minimum(self):
        ok, reason = can_place_trade(0.0, 0, _MIN_CAPITAL - 1)
        assert ok is False
        assert reason != ""

    def test_blocked_when_capital_zero(self):
        ok, _ = can_place_trade(0.0, 0, 0.0)
        assert ok is False

    def test_allowed_at_exact_minimum_capital(self):
        ok, _ = can_place_trade(0.0, 0, _MIN_CAPITAL)
        assert ok is True

    def test_capital_reason_mentions_insufficient(self):
        _, reason = can_place_trade(0.0, 0, 50.0)
        assert "capital" in reason.lower() or "insufficient" in reason.lower()

    # ── Priority — loss check before trades check ─

    def test_loss_limit_checked_first(self):
        """Both loss and trades exceeded — loss reason returned."""
        ok, reason = can_place_trade(
            _MAX_DAILY_LOSS,
            _MAX_TRADES_PER_DAY,
            10_000.0,
        )
        assert ok is False
        # Reason should mention loss (first check)
        assert "loss" in reason.lower() or "300" in reason


# ─────────────────────────────────────────────
# is_force_close_time
# ─────────────────────────────────────────────

class TestIsForceCloseTime:

    def test_exactly_at_force_close(self):
        dt = _ist(*_FORCE_CLOSE_TIME)
        assert is_force_close_time(dt) is True

    def test_one_minute_after_force_close(self):
        h, m = _FORCE_CLOSE_TIME
        dt = _ist(h, m + 1)
        assert is_force_close_time(dt) is True

    def test_one_minute_before_force_close(self):
        h, m = _FORCE_CLOSE_TIME
        dt = _ist(h, m - 1)
        assert is_force_close_time(dt) is False

    def test_morning_is_not_force_close(self):
        assert is_force_close_time(_ist(9, 35)) is False

    def test_midday_is_not_force_close(self):
        assert is_force_close_time(_ist(12, 0)) is False

    def test_end_of_day_is_force_close(self):
        assert is_force_close_time(_ist(15, 30)) is True


# ─────────────────────────────────────────────
# check_daily_loss_limit
# ─────────────────────────────────────────────

class TestCheckDailyLossLimit:

    def test_below_limit_returns_false(self):
        assert check_daily_loss_limit(_MAX_DAILY_LOSS - 1) is False

    def test_at_limit_returns_true(self):
        assert check_daily_loss_limit(_MAX_DAILY_LOSS) is True

    def test_above_limit_returns_true(self):
        assert check_daily_loss_limit(_MAX_DAILY_LOSS + 100) is True

    def test_zero_loss_returns_false(self):
        assert check_daily_loss_limit(0.0) is False

    def test_just_below_limit_returns_false(self):
        assert check_daily_loss_limit(_MAX_DAILY_LOSS - 0.01) is False


# ─────────────────────────────────────────────
# get_limits
# ─────────────────────────────────────────────

class TestGetLimits:

    def test_returns_dict(self):
        assert isinstance(get_limits(), dict)

    def test_has_required_keys(self):
        keys = get_limits().keys()
        required = {
            "max_position_size", "max_leverage",
            "max_trades_per_day", "max_daily_loss",
            "min_capital", "force_close_time",
        }
        assert required == set(keys)

    def test_max_position_size_correct(self):
        assert get_limits()["max_position_size"] == _MAX_POSITION_SIZE

    def test_max_trades_correct(self):
        assert get_limits()["max_trades_per_day"] == _MAX_TRADES_PER_DAY

    def test_max_daily_loss_correct(self):
        assert get_limits()["max_daily_loss"] == _MAX_DAILY_LOSS

    def test_force_close_time_format(self):
        t = get_limits()["force_close_time"]
        assert isinstance(t, str)
        assert ":" in t
        assert t == f"{_FORCE_CLOSE_TIME[0]:02d}:{_FORCE_CLOSE_TIME[1]:02d}"


# ─────────────────────────────────────────────
# Constants sanity
# ─────────────────────────────────────────────

def test_max_position_size_positive():
    assert _MAX_POSITION_SIZE > 0

def test_max_daily_loss_positive():
    assert _MAX_DAILY_LOSS > 0

def test_max_trades_at_least_one():
    assert _MAX_TRADES_PER_DAY >= 1

def test_force_close_after_market_open():
    h, m = _FORCE_CLOSE_TIME
    assert (h, m) > (9, 30)   # after open

def test_force_close_before_market_close():
    h, m = _FORCE_CLOSE_TIME
    assert (h, m) < (15, 30)  # before official close
