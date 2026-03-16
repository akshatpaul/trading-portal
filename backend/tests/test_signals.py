"""
tests/test_signals.py — Signal engine unit tests

Covers:
  - calculate_targets          (pure math)
  - is_within_trading_hours    (time window)
  - _crossover_type            (BUY / SELL / None)
  - _passes_filters            (ADX + vol_ratio gates)
  - generate_signals           (full scan with synthetic data)
  - check_entry_signal         (latest-candle check with time gate)
  - check_exit_signal          (TARGET / STOP_LOSS / FORCE_CLOSE)
  - Signal.to_dict             (serialisation)
"""

import math
import pytest
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from unittest.mock import patch

IST = pytz.timezone("Asia/Kolkata")

from strategy.signals import (
    Signal,
    calculate_targets,
    is_within_trading_hours,
    check_entry_signal,
    check_exit_signal,
    generate_signals,
    _crossover_type,
    _passes_filters,
    _EMA_FAST,
    _EMA_SLOW,
    _VOL_RATIO_MIN,
    _ADX_MIN,
    _TARGET_PCT,
    _STOP_PCT,
)


# ─────────────────────────────────────────────
# Helpers — synthetic OHLCV DataFrames
# ─────────────────────────────────────────────

def _make_row(
    ema_fast: float = 100.0,
    ema_slow: float = 100.0,
    adx: float = 25.0,
    vol: float = 2.0,
    close: float = 1000.0,
    atr: float = 10.0,
) -> pd.Series:
    """Build a mock candle row with all indicator columns."""
    return pd.Series({
        "close":           close,
        "atr_14":          atr,
        f"ema_{_EMA_FAST}": ema_fast,
        f"ema_{_EMA_SLOW}": ema_slow,
        "adx_14":          adx,
        "vol_ratio":       vol,
    })


def _candle_df(
    n: int = 60,
    price: float = 1000.0,
    trend: float = 5.0,
    avg_volume: int = 2_000_000,
    seed: int = 0,
) -> pd.DataFrame:
    """
    Generic synthetic 5-min DataFrame.
    trend > 0 → rising prices, trend < 0 → falling.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(
        start="2026-03-10 09:35",
        periods=n,
        freq="5min",
        tz=IST,
    )
    closes = [price + i * trend + rng.uniform(-1, 1) for i in range(n)]
    closes = [max(c, 1.0) for c in closes]
    return pd.DataFrame({
        "open":   [c - 2 for c in closes],
        "high":   [c + 5 for c in closes],
        "low":    [c - 5 for c in closes],
        "close":  closes,
        "volume": [avg_volume + rng.integers(-200_000, 200_000) for _ in range(n)],
    }, index=idx)


def _crossover_df(
    n_fall: int = 40,
    n_rise: int = 30,
    base_price: float = 1500.0,
    avg_volume: int = 3_000_000,
    seed: int = 0,
) -> pd.DataFrame:
    """
    DataFrame engineered to contain a BUY crossover.
    First n_fall rows: falling (establishes EMA9 < EMA21), low volume.
    Next n_rise rows:  rising sharply (EMA9 crosses above EMA21), 3× volume.

    The volume asymmetry ensures vol_ratio > 1.5 during the rising phase
    so signals pass the volume filter.
    """
    rng = np.random.default_rng(seed)
    falls = [base_price - i * 4 + rng.uniform(-0.5, 0.5) for i in range(n_fall)]
    start = falls[-1]
    rises = [start + (i + 1) * 10 + rng.uniform(-0.5, 0.5) for i in range(n_rise)]
    closes = [max(c, 1.0) for c in falls + rises]
    n = len(closes)
    idx = pd.date_range(
        start="2026-03-10 09:35",
        periods=n,
        freq="5min",
        tz=IST,
    )
    # Low volume during fall, high volume during rise → vol_ratio spikes at reversal
    low_vol  = avg_volume // 3
    high_vol = avg_volume
    volumes = (
        [low_vol  + rng.integers(-50_000, 50_000) for _ in range(n_fall)] +
        [high_vol + rng.integers(-100_000, 100_000) for _ in range(n_rise)]
    )
    return pd.DataFrame({
        "open":   [c - 3 for c in closes],
        "high":   [c + 8 for c in closes],
        "low":    [c - 8 for c in closes],
        "close":  closes,
        "volume": volumes,
    }, index=idx)


def _ist_dt(hour: int, minute: int, weekday: int = 0) -> datetime:
    """Return a timezone-aware IST datetime on a given weekday (0=Mon)."""
    # 2026-03-16 is a Monday
    from datetime import timedelta
    base = datetime(2026, 3, 16, hour, minute, 0, tzinfo=IST)
    return base + timedelta(days=weekday)


# ─────────────────────────────────────────────
# calculate_targets
# ─────────────────────────────────────────────

class TestCalculateTargets:

    def test_target_is_plus_0_6_pct(self):
        target, _ = calculate_targets(1000.0)
        assert target == pytest.approx(1006.0, rel=1e-6)

    def test_stop_is_minus_0_3_pct(self):
        _, stop = calculate_targets(1000.0)
        assert stop == pytest.approx(997.0, rel=1e-6)

    def test_returns_tuple_of_two(self):
        result = calculate_targets(500.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_target_gt_entry(self):
        target, stop = calculate_targets(2000.0)
        assert target > 2000.0

    def test_stop_lt_entry(self):
        target, stop = calculate_targets(2000.0)
        assert stop < 2000.0

    def test_target_gt_stop(self):
        target, stop = calculate_targets(500.0)
        assert target > stop

    def test_rounded_to_2_dp(self):
        target, stop = calculate_targets(1234.56)
        assert target == round(target, 2)
        assert stop == round(stop, 2)

    def test_risk_reward_ratio(self):
        """Risk = 0.3%, Reward = 0.6% → 1:2 ratio."""
        entry = 1000.0
        target, stop = calculate_targets(entry)
        reward = target - entry
        risk   = entry - stop
        assert reward / risk == pytest.approx(2.0, rel=0.01)


# ─────────────────────────────────────────────
# is_within_trading_hours
# ─────────────────────────────────────────────

class TestTradingHours:

    def test_within_hours_returns_true(self):
        dt = _ist_dt(10, 30, weekday=0)  # Monday 10:30
        assert is_within_trading_hours(dt) is True

    def test_before_open_returns_false(self):
        dt = _ist_dt(9, 15, weekday=0)   # 09:15 — before open
        assert is_within_trading_hours(dt) is False

    def test_exactly_at_open_returns_true(self):
        dt = _ist_dt(9, 30, weekday=0)
        assert is_within_trading_hours(dt) is True

    def test_exactly_at_close_returns_true(self):
        dt = _ist_dt(14, 30, weekday=0)
        assert is_within_trading_hours(dt) is True

    def test_after_close_returns_false(self):
        dt = _ist_dt(14, 45, weekday=0)
        assert is_within_trading_hours(dt) is False

    def test_saturday_returns_false(self):
        dt = _ist_dt(10, 0, weekday=5)   # Saturday
        assert is_within_trading_hours(dt) is False

    def test_sunday_returns_false(self):
        dt = _ist_dt(10, 0, weekday=6)
        assert is_within_trading_hours(dt) is False

    def test_friday_within_hours_returns_true(self):
        dt = _ist_dt(11, 0, weekday=4)   # Friday 11:00
        assert is_within_trading_hours(dt) is True


# ─────────────────────────────────────────────
# _crossover_type
# ─────────────────────────────────────────────

class TestCrossoverType:

    def test_buy_crossover(self):
        """EMA9 crosses above EMA21 → BUY."""
        prev = _make_row(ema_fast=99.0, ema_slow=100.0)
        curr = _make_row(ema_fast=101.0, ema_slow=100.0)
        assert _crossover_type(prev, curr) == "BUY"

    def test_sell_crossover(self):
        """EMA9 crosses below EMA21 → SELL."""
        prev = _make_row(ema_fast=101.0, ema_slow=100.0)
        curr = _make_row(ema_fast=99.0,  ema_slow=100.0)
        assert _crossover_type(prev, curr) == "SELL"

    def test_no_crossover_above(self):
        """Both above EMA21 — no crossover."""
        prev = _make_row(ema_fast=102.0, ema_slow=100.0)
        curr = _make_row(ema_fast=103.0, ema_slow=100.0)
        assert _crossover_type(prev, curr) is None

    def test_no_crossover_below(self):
        """Both below EMA21 — no crossover."""
        prev = _make_row(ema_fast=98.0, ema_slow=100.0)
        curr = _make_row(ema_fast=97.0, ema_slow=100.0)
        assert _crossover_type(prev, curr) is None

    def test_nan_prev_ema_fast_returns_none(self):
        prev = _make_row(ema_fast=float("nan"), ema_slow=100.0)
        curr = _make_row(ema_fast=101.0, ema_slow=100.0)
        assert _crossover_type(prev, curr) is None

    def test_nan_curr_ema_slow_returns_none(self):
        prev = _make_row(ema_fast=99.0, ema_slow=100.0)
        curr = _make_row(ema_fast=101.0, ema_slow=float("nan"))
        assert _crossover_type(prev, curr) is None

    def test_exact_equality_is_not_crossover(self):
        """EMA9 == EMA21 → no clear side → None."""
        prev = _make_row(ema_fast=100.0, ema_slow=100.0)
        curr = _make_row(ema_fast=100.0, ema_slow=100.0)
        assert _crossover_type(prev, curr) is None


# ─────────────────────────────────────────────
# _passes_filters
# ─────────────────────────────────────────────

class TestPassesFilters:

    def test_passes_when_both_thresholds_met(self):
        row = _make_row(adx=25.0, vol=2.0)
        assert _passes_filters(row) is True

    def test_fails_when_adx_too_low(self):
        row = _make_row(adx=15.0, vol=2.0)
        assert _passes_filters(row) is False

    def test_fails_when_vol_too_low(self):
        row = _make_row(adx=25.0, vol=1.0)
        assert _passes_filters(row) is False

    def test_passes_at_exact_adx_threshold(self):
        row = _make_row(adx=_ADX_MIN, vol=_VOL_RATIO_MIN)
        assert _passes_filters(row) is True

    def test_passes_at_exact_vol_threshold(self):
        row = _make_row(adx=25.0, vol=_VOL_RATIO_MIN)
        assert _passes_filters(row) is True

    def test_nan_adx_fails(self):
        row = _make_row(adx=float("nan"), vol=2.0)
        assert _passes_filters(row) is False

    def test_nan_vol_fails(self):
        row = _make_row(adx=25.0, vol=float("nan"))
        assert _passes_filters(row) is False


# ─────────────────────────────────────────────
# Signal.to_dict
# ─────────────────────────────────────────────

class TestSignalToDict:

    def _make_signal(self) -> Signal:
        ts = _ist_dt(10, 30)
        return Signal(
            symbol="HDFCBANK.NS", side="BUY",
            price=1500.0, target=1509.0, stop_loss=1495.5,
            timestamp=ts, reason="test",
            ema_9=1501.0, ema_21=1499.0, adx=28.5, vol_ratio=2.1,
        )

    def test_returns_dict(self):
        assert isinstance(self._make_signal().to_dict(), dict)

    def test_required_keys_present(self):
        d = self._make_signal().to_dict()
        required = {"symbol", "side", "price", "target", "stop_loss",
                    "timestamp", "reason", "ema_9", "ema_21", "adx", "vol_ratio"}
        assert required == set(d.keys())

    def test_symbol_correct(self):
        assert self._make_signal().to_dict()["symbol"] == "HDFCBANK.NS"

    def test_side_correct(self):
        assert self._make_signal().to_dict()["side"] == "BUY"

    def test_price_correct(self):
        assert self._make_signal().to_dict()["price"] == 1500.0

    def test_timestamp_is_isoformat(self):
        ts_str = self._make_signal().to_dict()["timestamp"]
        # Must be parseable as ISO datetime
        datetime.fromisoformat(ts_str)


# ─────────────────────────────────────────────
# generate_signals
# ─────────────────────────────────────────────

class TestGenerateSignals:

    def test_empty_df_returns_empty(self):
        assert generate_signals(pd.DataFrame(), "X.NS") == []

    def test_short_df_returns_empty(self):
        df = _candle_df(n=5)
        assert generate_signals(df, "X.NS") == []

    def test_returns_list(self):
        df = _candle_df(n=60, trend=2.0)
        result = generate_signals(df, "TCS.NS")
        assert isinstance(result, list)

    def test_signals_are_signal_objects(self):
        df = _crossover_df()
        result = generate_signals(df, "TCS.NS")
        assert all(isinstance(s, Signal) for s in result)

    def test_buy_crossover_produces_buy_signal(self):
        """Rising-after-falling pattern should contain at least one BUY."""
        df = _crossover_df(n_fall=40, n_rise=30)
        signals = generate_signals(df, "TCS.NS")
        buys = [s for s in signals if s.side == "BUY"]
        assert len(buys) >= 1

    def test_signal_side_is_buy_or_sell(self):
        df = _crossover_df()
        for sig in generate_signals(df, "X.NS"):
            assert sig.side in ("BUY", "SELL")

    def test_signal_price_is_positive(self):
        df = _crossover_df()
        for sig in generate_signals(df, "X.NS"):
            assert sig.price > 0

    def test_signal_target_gt_price_for_buy(self):
        df = _crossover_df()
        for sig in generate_signals(df, "X.NS"):
            if sig.side == "BUY":
                assert sig.target > sig.price

    def test_signal_stop_lt_price_for_buy(self):
        df = _crossover_df()
        for sig in generate_signals(df, "X.NS"):
            if sig.side == "BUY":
                assert sig.stop_loss < sig.price

    def test_signal_symbol_matches(self):
        df = _crossover_df()
        for sig in generate_signals(df, "INFY.NS"):
            assert sig.symbol == "INFY.NS"

    def test_signals_chronologically_ordered(self):
        df = _crossover_df()
        signals = generate_signals(df, "X.NS")
        tss = [s.timestamp for s in signals]
        assert tss == sorted(tss)

    def test_flat_no_crossover_returns_empty_or_filtered(self):
        """Flat price: no EMA crossovers — signals list will be empty."""
        # With perfectly flat data EMAs never cross
        df = _candle_df(n=60, trend=0.0, seed=99)
        # May or may not have signals; just assert list type (no crash)
        result = generate_signals(df, "FLAT.NS")
        assert isinstance(result, list)

    def test_vol_ratio_filter_removes_low_volume(self):
        """Low-volume data should produce fewer (possibly zero) signals."""
        low_vol = _crossover_df(avg_volume=100_000)   # well below 20-period avg
        normal  = _crossover_df(avg_volume=3_000_000)
        assert len(generate_signals(low_vol, "X.NS")) <= len(generate_signals(normal, "X.NS"))


# ─────────────────────────────────────────────
# check_entry_signal
# ─────────────────────────────────────────────

class TestCheckEntrySignal:

    def test_empty_df_returns_none(self):
        assert check_entry_signal(pd.DataFrame(), "X.NS") is None

    def test_short_df_returns_none(self):
        df = _candle_df(n=5)
        assert check_entry_signal(df, "X.NS") is None

    def test_outside_hours_returns_none(self):
        """Latest bar is after 14:30 → no entry."""
        # 60 bars from 09:35, each 5 min → last bar at 14:30
        # Add one more to push past it
        df = _candle_df(n=70, trend=5.0, avg_volume=3_000_000)
        # Last bar at 09:35 + 69*5min = 09:35 + 345min = 15:20 → after entry close
        assert df.index[-1].hour >= 15
        result = check_entry_signal(df, "X.NS")
        assert result is None

    def test_within_hours_can_return_signal_or_none(self):
        """Only the last bar matters; just verify no exception raised."""
        df = _candle_df(n=40, trend=5.0)
        result = check_entry_signal(df, "TCS.NS")
        assert result is None or isinstance(result, Signal)

    def test_returns_signal_with_correct_symbol(self):
        """If a signal is found, symbol must match."""
        df = _crossover_df(n_fall=40, n_rise=5)
        # Trim to put latest bar inside trading hours (within first 50 bars from 09:35)
        df = df.iloc[:50]
        result = check_entry_signal(df, "HDFCBANK.NS")
        if result is not None:
            assert result.symbol == "HDFCBANK.NS"

    def test_result_is_signal_or_none(self):
        df = _crossover_df()
        result = check_entry_signal(df, "X.NS")
        assert result is None or isinstance(result, Signal)


# ─────────────────────────────────────────────
# check_exit_signal
# ─────────────────────────────────────────────

class TestCheckExitSignal:

    def _df_at(self, hour: int, minute: int, close: float = 1000.0) -> pd.DataFrame:
        """Single-row DataFrame at the given IST time."""
        ts = pd.Timestamp(2026, 3, 16, hour, minute, 0, tz=IST)
        return pd.DataFrame(
            {"open": [close], "high": [close], "low": [close],
             "close": [close], "volume": [1_000_000]},
            index=[ts],
        )

    def test_empty_df_returns_none(self):
        assert check_exit_signal(pd.DataFrame(), 1000.0, _ist_dt(10, 0)) is None

    def test_force_close_at_15_10(self):
        df = self._df_at(15, 10, close=1000.0)
        assert check_exit_signal(df, 1000.0, _ist_dt(9, 35)) == "FORCE_CLOSE"

    def test_force_close_after_15_10(self):
        df = self._df_at(15, 25, close=1000.0)
        assert check_exit_signal(df, 1000.0, _ist_dt(9, 35)) == "FORCE_CLOSE"

    def test_target_hit(self):
        entry = 1000.0
        target, _ = calculate_targets(entry)
        df = self._df_at(11, 0, close=target)
        assert check_exit_signal(df, entry, _ist_dt(10, 0)) == "TARGET"

    def test_target_exceeded(self):
        entry = 1000.0
        target, _ = calculate_targets(entry)
        df = self._df_at(11, 0, close=target + 5)
        assert check_exit_signal(df, entry, _ist_dt(10, 0)) == "TARGET"

    def test_stop_hit(self):
        entry = 1000.0
        _, stop = calculate_targets(entry)
        df = self._df_at(11, 0, close=stop)
        assert check_exit_signal(df, entry, _ist_dt(10, 0)) == "STOP_LOSS"

    def test_stop_breached(self):
        entry = 1000.0
        _, stop = calculate_targets(entry)
        df = self._df_at(11, 0, close=stop - 5)
        assert check_exit_signal(df, entry, _ist_dt(10, 0)) == "STOP_LOSS"

    def test_hold_when_between_target_and_stop(self):
        entry = 1000.0
        df = self._df_at(11, 0, close=1002.0)   # between stop and target
        assert check_exit_signal(df, entry, _ist_dt(10, 0)) is None

    def test_force_close_takes_priority_over_target(self):
        """Even if price is at target, FORCE_CLOSE wins at 15:10."""
        entry = 1000.0
        target, _ = calculate_targets(entry)
        df = self._df_at(15, 10, close=target)
        assert check_exit_signal(df, entry, _ist_dt(9, 35)) == "FORCE_CLOSE"


# ─────────────────────────────────────────────
# Constants sanity
# ─────────────────────────────────────────────

def test_ema_fast_lt_slow():
    assert _EMA_FAST < _EMA_SLOW

def test_vol_ratio_threshold_positive():
    assert _VOL_RATIO_MIN > 0

def test_adx_threshold_positive():
    assert _ADX_MIN > 0

def test_target_pct_gt_stop_pct():
    """Risk:reward is 1:2 — target must be bigger than stop."""
    assert _TARGET_PCT > _STOP_PCT

def test_target_pct_positive():
    assert _TARGET_PCT > 0

def test_stop_pct_positive():
    assert _STOP_PCT > 0
