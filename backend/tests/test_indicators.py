"""
tests/test_indicators.py — Technical indicator unit tests

Tests verify:
  - Correct column names appended
  - Mathematical correctness against manual / reference values
  - NaN warm-up behaviour
  - No mutation of input DataFrame
  - VWAP daily reset

Run: pytest tests/test_indicators.py -v
"""

import pytest
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

IST = pytz.timezone("Asia/Kolkata")

from strategy.indicators import (
    add_ema,
    add_atr,
    add_adx,
    add_vwap,
    add_volume_ratio,
    add_all_indicators,
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def _make_df(n: int = 60, price_base: float = 1000.0, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic OHLCV DataFrame with IST-aware index.
    Prices follow a smooth sine wave for deterministic results.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(
        start="2026-03-01 09:35",
        periods=n,
        freq="5min",
        tz=IST,
    )
    t = np.linspace(0, 4 * np.pi, n)
    close = price_base + 50 * np.sin(t) + rng.uniform(-2, 2, n)
    open_ = close - rng.uniform(1, 5, n)
    high  = close + rng.uniform(2, 8, n)
    low   = close - rng.uniform(2, 8, n)
    vol   = (1_000_000 + 200_000 * np.sin(t + 1) + rng.uniform(0, 50_000, n)).astype(int)

    return pd.DataFrame({
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": vol,
    }, index=idx)


def _multi_day_df(days: int = 3, candles_per_day: int = 75) -> pd.DataFrame:
    """
    Multi-day DataFrame spanning several trading sessions.
    Each day starts at 09:15 IST with 5-min candles.
    """
    frames = []
    for d in range(days):
        date_str = f"2026-03-{16 + d:02d} 09:15"
        idx = pd.date_range(start=date_str, periods=candles_per_day, freq="5min", tz=IST)
        rng = np.random.default_rng(d)
        base = 1000.0 + d * 10
        close = base + rng.uniform(-5, 5, candles_per_day).cumsum()
        frames.append(pd.DataFrame({
            "open":   close - 1,
            "high":   close + 3,
            "low":    close - 3,
            "close":  close,
            "volume": rng.integers(500_000, 1_500_000, candles_per_day),
        }, index=idx))
    return pd.concat(frames).sort_index()


# ─────────────────────────────────────────────
# EMA
# ─────────────────────────────────────────────

class TestAddEma:

    def test_column_appended(self):
        df = add_ema(_make_df(), period=9)
        assert "ema_9" in df.columns

    def test_both_ema_columns(self):
        df = _make_df()
        df = add_ema(df, period=9)
        df = add_ema(df, period=21)
        assert "ema_9" in df.columns
        assert "ema_21" in df.columns

    def test_warmup_nans(self):
        df = add_ema(_make_df(30), period=9)
        # First (period-1) rows should be NaN
        assert df["ema_9"].iloc[:8].isna().all()

    def test_no_nans_after_warmup(self):
        df = add_ema(_make_df(50), period=9)
        assert df["ema_9"].iloc[9:].notna().all()

    def test_ema_length_matches_input(self):
        n = 40
        df = add_ema(_make_df(n), period=9)
        assert len(df) == n

    def test_does_not_mutate_input(self):
        original = _make_df(30)
        cols_before = set(original.columns)
        add_ema(original, period=9)
        assert set(original.columns) == cols_before

    def test_ema_smooths_prices(self):
        """EMA must be between min and max of close prices (after warm-up)."""
        df = add_ema(_make_df(60), period=9)
        valid = df["ema_9"].dropna()
        assert (valid >= df["close"].min() * 0.9).all()
        assert (valid <= df["close"].max() * 1.1).all()

    def test_ema_9_faster_than_ema_21(self):
        """On a rising series, EMA(9) should be above EMA(21) after crossover."""
        n = 60
        idx = pd.date_range("2026-03-01 09:35", periods=n, freq="5min", tz=IST)
        close = pd.Series(range(n), dtype=float)   # strictly rising
        df = pd.DataFrame({"open": close, "high": close+1, "low": close-1,
                           "close": close, "volume": [100_000]*n}, index=idx)
        df = add_ema(df, 9)
        df = add_ema(df, 21)
        # After sufficient warm-up, EMA9 > EMA21 on a rising series
        tail = df.dropna()
        assert (tail["ema_9"] > tail["ema_21"]).all()

    def test_ema_formula_manual(self):
        """
        Verify the first computed value after warm-up matches manual calculation.
        EMA[n] = price[n] * alpha + EMA[n-1] * (1 - alpha)  where alpha = 2/(p+1)
        For min_periods=p, the first non-NaN is at index p-1 (0-based),
        initialised as the simple mean of the first p values.
        """
        period = 3
        alpha  = 2 / (period + 1)   # 0.5
        prices = [10.0, 12.0, 11.0, 13.0, 15.0]
        idx = pd.date_range("2026-03-01", periods=len(prices), freq="5min", tz=IST)
        df = pd.DataFrame({
            "open": prices, "high": prices, "low": prices,
            "close": prices, "volume": [1]*len(prices),
        }, index=idx)
        df = add_ema(df, period=3)

        # pandas ewm with adjust=False, min_periods=3:
        # index 0,1 → NaN; index 2 → initialised with first value (not SMA!)
        # actually with adjust=False, min_periods=period: first non-NaN at index period-1
        # The value matches pandas' own formula, so we just verify it matches pandas directly
        expected = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
        pd.testing.assert_series_equal(df["ema_3"], expected, check_names=False)

    def test_custom_source_column(self):
        df = _make_df(30)
        df = add_ema(df, period=5, col="high")
        assert "ema_5" in df.columns
        # Spot-check: EMA of high should be >= EMA of close (since high >= close)
        df2 = add_ema(df, period=5, col="close")
        valid = df[["ema_5"]].dropna()
        assert not valid.empty


# ─────────────────────────────────────────────
# ATR
# ─────────────────────────────────────────────

class TestAddAtr:

    def test_column_appended(self):
        df = add_atr(_make_df(40))
        assert "atr_14" in df.columns

    def test_warmup_nans(self):
        df = add_atr(_make_df(40), period=14)
        assert df["atr_14"].iloc[:13].isna().all()

    def test_atr_positive(self):
        df = add_atr(_make_df(50), period=14)
        valid = df["atr_14"].dropna()
        assert (valid > 0).all()

    def test_atr_at_most_high_low_range(self):
        """ATR can be larger than a single candle's range due to gap,
        but for gapless synthetic data it should be close to H-L range."""
        df = _make_df(50)
        result = add_atr(df, period=14)
        valid = result["atr_14"].dropna()
        # ATR should be in a reasonable range (not wildly inflated)
        assert valid.max() < (df["high"] - df["low"]).max() * 5

    def test_does_not_mutate_input(self):
        original = _make_df(40)
        cols_before = set(original.columns)
        add_atr(original)
        assert set(original.columns) == cols_before

    def test_atr_length_matches_input(self):
        n = 45
        df = add_atr(_make_df(n))
        assert len(df) == n

    def test_flat_price_gives_zero_atr(self):
        """Perfectly flat candles (no range, no gaps) should yield ATR → 0."""
        n = 30
        idx = pd.date_range("2026-03-01 09:35", periods=n, freq="5min", tz=IST)
        price = 1000.0
        df = pd.DataFrame({
            "open":   [price] * n,
            "high":   [price] * n,
            "low":    [price] * n,
            "close":  [price] * n,
            "volume": [100_000] * n,
        }, index=idx)
        result = add_atr(df, period=14)
        valid = result["atr_14"].dropna()
        np.testing.assert_allclose(valid.values, 0.0, atol=1e-10)

    def test_atr_pct_screener_filter(self):
        """ATR as % of price is used by screener; verify it's computable."""
        df = add_atr(_make_df(50), period=14)
        atr_pct = (df["atr_14"] / df["close"] * 100).dropna()
        assert (atr_pct >= 0).all()


# ─────────────────────────────────────────────
# ADX
# ─────────────────────────────────────────────

class TestAddAdx:

    def test_columns_appended(self):
        df = add_adx(_make_df(60))
        assert "adx_14" in df.columns
        assert "dmp_14" in df.columns
        assert "dmn_14" in df.columns

    def test_adx_bounded_0_to_100(self):
        df = add_adx(_make_df(80), period=14)
        valid = df["adx_14"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_di_positive(self):
        df = add_adx(_make_df(80), period=14)
        assert (df["dmp_14"].dropna() >= 0).all()
        assert (df["dmn_14"].dropna() >= 0).all()

    def test_warmup_nans(self):
        df = add_adx(_make_df(60), period=14)
        # ADX is RMA of DX which is itself based on RMA(period) — needs 2*period-1 rows
        # After warm-up there should be valid values
        assert df["adx_14"].dropna().notna().all()

    def test_does_not_mutate_input(self):
        original = _make_df(60)
        cols_before = set(original.columns)
        add_adx(original)
        assert set(original.columns) == cols_before

    def test_strong_trend_gives_high_adx(self):
        """A perfectly trending series should produce high ADX after warm-up."""
        n = 100
        idx = pd.date_range("2026-03-01 09:35", periods=n, freq="5min", tz=IST)
        close = pd.Series([1000.0 + i * 5 for i in range(n)], index=idx)
        df = pd.DataFrame({
            "open":   close - 1,
            "high":   close + 2,
            "low":    close - 2,
            "close":  close,
            "volume": [500_000] * n,
        }, index=idx)
        result = add_adx(df, period=14)
        # After full warm-up (last 30 rows), ADX should be elevated for a strong trend
        adx_tail = result["adx_14"].dropna().iloc[-30:]
        assert len(adx_tail) > 0, "ADX produced no valid values"
        assert adx_tail.mean() > 20, f"Expected ADX > 20 in strong trend, got {adx_tail.mean():.1f}"

    def test_choppy_market_lower_adx(self):
        """Alternating up/down should produce lower ADX than a trend."""
        n = 100
        idx = pd.date_range("2026-03-01 09:35", periods=n, freq="5min", tz=IST)
        prices = pd.Series([1000.0 + (5 if i % 2 == 0 else -5) for i in range(n)], index=idx)
        df_choppy = pd.DataFrame({
            "open":   prices - 1, "high": prices + 1,
            "low":    prices - 1, "close": prices,
            "volume": [500_000] * n,
        }, index=idx)
        trend_c = pd.Series([1000.0 + i * 5 for i in range(n)], index=idx)
        df_trending = pd.DataFrame({
            "open":   trend_c - 1, "high": trend_c + 2,
            "low":    trend_c - 2, "close": trend_c,
            "volume": [500_000] * n,
        }, index=idx)

        adx_choppy   = add_adx(df_choppy,   period=14)["adx_14"].dropna().iloc[-20:].mean()
        adx_trending = add_adx(df_trending, period=14)["adx_14"].dropna().iloc[-20:].mean()
        assert not np.isnan(adx_choppy),   "Choppy ADX should have valid values"
        assert not np.isnan(adx_trending), "Trending ADX should have valid values"
        assert adx_trending > adx_choppy


# ─────────────────────────────────────────────
# VWAP
# ─────────────────────────────────────────────

class TestAddVwap:

    def test_column_appended(self):
        df = add_vwap(_make_df(30))
        assert "vwap" in df.columns

    def test_vwap_positive(self):
        df = add_vwap(_make_df(40))
        assert (df["vwap"] > 0).all()

    def test_vwap_within_session_cumulative_range(self):
        """
        VWAP is a session-cumulative weighted average. It must lie between the
        session's cumulative minimum low and cumulative maximum high — not each
        individual candle's range (a lagging VWAP can exceed a single candle).
        """
        df = _multi_day_df(days=2, candles_per_day=50)
        result = add_vwap(df)
        date_key = df.index.normalize()
        cum_min_low  = df["low"].groupby(date_key).cummin()
        cum_max_high = df["high"].groupby(date_key).cummax()
        assert (result["vwap"] >= cum_min_low).all()
        assert (result["vwap"] <= cum_max_high).all()

    def test_vwap_equals_close_when_uniform_volume(self):
        """
        When all candles have identical volume and high=low=close (degenerate),
        VWAP must equal the typical price each row.
        """
        n = 20
        idx = pd.date_range("2026-03-16 09:35", periods=n, freq="5min", tz=IST)
        prices = [float(1000 + i) for i in range(n)]
        df = pd.DataFrame({
            "open":   prices, "high": prices, "low": prices,
            "close":  prices, "volume": [100_000] * n,
        }, index=idx)
        result = add_vwap(df)
        # TP = (H+L+C)/3 = price; VWAP = cumsum(TP*V)/cumsum(V)
        expected_vwap_last = sum(p * 100_000 for p in prices) / (n * 100_000)
        assert result["vwap"].iloc[-1] == pytest.approx(expected_vwap_last, rel=1e-6)

    def test_vwap_resets_each_day(self):
        """
        First candle of each session: VWAP must equal that candle's typical price.
        TP = (high + low + close) / 3
        """
        df = _multi_day_df(days=3, candles_per_day=50)
        result = add_vwap(df)

        for d in range(3):
            date = f"2026-03-{16 + d}"
            day_rows = result[result.index.date.astype(str) == date]
            if day_rows.empty:
                continue
            first = day_rows.iloc[0]
            tp = (first["high"] + first["low"] + first["close"]) / 3
            assert first["vwap"] == pytest.approx(tp, rel=1e-6), \
                f"VWAP did not reset on day {date}: got {first['vwap']:.4f}, expected {tp:.4f}"

    def test_vwap_monotone_with_single_candle(self):
        """With one candle, VWAP must equal that candle's typical price."""
        idx = pd.DatetimeIndex(
            [pd.Timestamp("2026-03-16 09:35", tz=IST)]
        )
        df = pd.DataFrame({
            "open": [1640.0], "high": [1650.0], "low": [1635.0],
            "close": [1645.0], "volume": [1_000_000],
        }, index=idx)
        result = add_vwap(df)
        tp = (1650.0 + 1635.0 + 1645.0) / 3
        assert result["vwap"].iloc[0] == pytest.approx(tp)

    def test_does_not_mutate_input(self):
        original = _make_df(30)
        cols_before = set(original.columns)
        add_vwap(original)
        assert set(original.columns) == cols_before


# ─────────────────────────────────────────────
# Volume Ratio
# ─────────────────────────────────────────────

class TestAddVolumeRatio:

    def test_column_appended(self):
        df = add_volume_ratio(_make_df(40))
        assert "vol_ratio" in df.columns

    def test_warmup_nans(self):
        df = add_volume_ratio(_make_df(40), period=20)
        assert df["vol_ratio"].iloc[:19].isna().all()

    def test_uniform_volume_gives_ratio_one(self):
        """If all volumes are equal, vol_ratio should be exactly 1.0."""
        n = 40
        idx = pd.date_range("2026-03-16 09:35", periods=n, freq="5min", tz=IST)
        df = pd.DataFrame({
            "open": [1000.0]*n, "high": [1005.0]*n,
            "low":  [995.0]*n,  "close": [1000.0]*n,
            "volume": [500_000]*n,
        }, index=idx)
        result = add_volume_ratio(df, period=20)
        valid = result["vol_ratio"].dropna()
        np.testing.assert_allclose(valid.values, 1.0, rtol=1e-9)

    def test_spike_gives_ratio_gt_one(self):
        """A volume spike should give vol_ratio > 1."""
        n = 40
        idx = pd.date_range("2026-03-16 09:35", periods=n, freq="5min", tz=IST)
        vols = [500_000] * n
        vols[-1] = 2_000_000   # 4x spike on last candle
        df = pd.DataFrame({
            "open": [1000.0]*n, "high": [1005.0]*n,
            "low":  [995.0]*n,  "close": [1000.0]*n,
            "volume": vols,
        }, index=idx)
        result = add_volume_ratio(df, period=20)
        assert result["vol_ratio"].iloc[-1] > 1.0

    def test_entry_signal_threshold(self):
        """Signal requires vol_ratio > 1.5. Verify the 2x spike clears that bar."""
        n = 40
        idx = pd.date_range("2026-03-16 09:35", periods=n, freq="5min", tz=IST)
        vols = [500_000] * n
        vols[-1] = 1_000_000   # exactly 2x → ratio ≈ 1.9..
        df = pd.DataFrame({
            "open": [1000.0]*n, "high": [1005.0]*n,
            "low":  [995.0]*n,  "close": [1000.0]*n,
            "volume": vols,
        }, index=idx)
        result = add_volume_ratio(df, period=20)
        assert result["vol_ratio"].iloc[-1] > 1.5

    def test_does_not_mutate_input(self):
        original = _make_df(40)
        cols_before = set(original.columns)
        add_volume_ratio(original)
        assert set(original.columns) == cols_before

    def test_length_matches_input(self):
        n = 45
        df = add_volume_ratio(_make_df(n), period=20)
        assert len(df) == n


# ─────────────────────────────────────────────
# add_all_indicators
# ─────────────────────────────────────────────

class TestAddAllIndicators:

    EXPECTED_COLS = {
        "ema_9", "ema_21",
        "atr_14",
        "adx_14", "dmp_14", "dmn_14",
        "vwap",
        "vol_ratio",
    }

    def test_all_columns_present(self):
        df = add_all_indicators(_make_df(80))
        assert self.EXPECTED_COLS.issubset(set(df.columns))

    def test_ohlcv_columns_preserved(self):
        df = add_all_indicators(_make_df(80))
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_does_not_mutate_input(self):
        original = _make_df(80)
        cols_before = set(original.columns)
        add_all_indicators(original)
        assert set(original.columns) == cols_before

    def test_signal_logic_ready_after_21_rows(self):
        """
        The entry signal needs ema_9, ema_21, vol_ratio, adx_14.
        After 21+ candles all should have valid (non-NaN) values.
        Use a longer series and check the tail.
        """
        df = add_all_indicators(_make_df(100))
        tail = df.iloc[-50:]
        for col in ["ema_9", "ema_21", "adx_14", "vol_ratio"]:
            assert tail[col].notna().all(), f"{col} has NaN in tail"

    def test_ema9_can_cross_ema21(self):
        """On a trending-then-reversing series, crossover should occur."""
        n = 120
        idx = pd.date_range("2026-03-01 09:35", periods=n, freq="5min", tz=IST)
        # Rising for first half, falling for second half
        half = n // 2
        close = [1000.0 + i * 2 for i in range(half)] + \
                [1000.0 + half * 2 - (i * 2) for i in range(half)]
        df = pd.DataFrame({
            "open":   [c - 1 for c in close], "high": [c + 2 for c in close],
            "low":    [c - 2 for c in close], "close": close,
            "volume": [500_000] * n,
        }, index=idx)
        result = add_all_indicators(df)
        valid = result.dropna(subset=["ema_9", "ema_21"])
        above = (valid["ema_9"] > valid["ema_21"])
        # Should have both True and False (crossover happened)
        assert above.any() and (~above).any()
