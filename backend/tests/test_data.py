"""
tests/test_data.py — Data client and candle builder tests

All yfinance calls are mocked — no network required.
candle_builder tests use real DataFrames to exercise normalisation logic.

Run: pytest tests/test_data.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────
# Helpers — build synthetic DataFrames that
# mimic what yfinance actually returns
# ─────────────────────────────────────────────

def _make_ist_index(n: int, freq: str = "5min", start: str = "2026-03-16 09:35") -> pd.DatetimeIndex:
    """Build an IST-aware DatetimeIndex with n periods."""
    idx = pd.date_range(start=start, periods=n, freq=freq, tz=IST)
    return idx


def _ticker_history_df(
    n: int = 20,
    price_base: float = 1642.0,
    freq: str = "5min",
    start: str = "2026-03-16 09:35",
) -> pd.DataFrame:
    """
    Simulate yf.Ticker().history() output:
    flat columns Open, High, Low, Close, Volume, Dividends, Stock Splits
    Index: IST DatetimeIndex
    """
    idx = _make_ist_index(n, freq=freq, start=start)
    closes = [price_base + i * 0.5 for i in range(n)]
    df = pd.DataFrame({
        "Open":         [c - 2 for c in closes],
        "High":         [c + 3 for c in closes],
        "Low":          [c - 3 for c in closes],
        "Close":        closes,
        "Volume":       [100_000 + i * 1000 for i in range(n)],
        "Dividends":    [0.0] * n,
        "Stock Splits": [0.0] * n,
    }, index=idx)
    return df


def _multi_ticker_download_df(symbols: list[str], n: int = 10) -> pd.DataFrame:
    """
    Simulate yf.download() with group_by='ticker' output:
    MultiIndex columns (Ticker, Price)
    """
    idx = _make_ist_index(n, freq="1D", start="2026-03-01 15:30")
    arrays = []
    for symbol in symbols:
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            arrays.append((symbol, col))

    midx = pd.MultiIndex.from_tuples(arrays)
    data = {}
    for symbol in symbols:
        base = 1000.0 if symbol != "TCS.NS" else 3500.0
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col == "Volume":
                data[(symbol, col)] = [500_000 + i * 1000 for i in range(n)]
            else:
                data[(symbol, col)] = [base + i for i in range(n)]

    df = pd.DataFrame(data, index=idx)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


# ─────────────────────────────────────────────
# candle_builder — normalise_candles
# ─────────────────────────────────────────────

from data.candle_builder import normalise_candles, candles_to_records, records_to_dataframe


class TestNormaliseCandles:

    def test_flat_columns_are_lowercased(self):
        raw = _ticker_history_df(10)
        df = normalise_candles(raw)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_extra_columns_dropped(self):
        raw = _ticker_history_df(10)
        assert "Dividends" in raw.columns
        df = normalise_candles(raw)
        assert "dividends" not in df.columns
        assert "stock splits" not in df.columns

    def test_index_is_ist(self):
        raw = _ticker_history_df(5)
        df = normalise_candles(raw)
        assert str(df.index.tz) == "Asia/Kolkata"

    def test_utc_index_converted_to_ist(self):
        raw = _ticker_history_df(5)
        raw.index = raw.index.tz_convert("UTC")
        df = normalise_candles(raw)
        assert str(df.index.tz) == "Asia/Kolkata"

    def test_naive_index_localised_as_utc_then_converted(self):
        raw = _ticker_history_df(5)
        raw.index = raw.index.tz_localize(None)
        df = normalise_candles(raw)
        assert str(df.index.tz) == "Asia/Kolkata"

    def test_volume_is_int(self):
        raw = _ticker_history_df(5)
        df = normalise_candles(raw)
        assert df["volume"].dtype == int

    def test_prices_are_float(self):
        raw = _ticker_history_df(5)
        df = normalise_candles(raw)
        for col in ["open", "high", "low", "close"]:
            assert df[col].dtype == float

    def test_nan_rows_dropped(self):
        raw = _ticker_history_df(10)
        raw.iloc[3, raw.columns.get_loc("Close")] = float("nan")
        df = normalise_candles(raw)
        assert len(df) == 9

    def test_zero_volume_rows_dropped(self):
        raw = _ticker_history_df(10)
        raw.iloc[5, raw.columns.get_loc("Volume")] = 0
        df = normalise_candles(raw)
        assert len(df) == 9

    def test_index_is_sorted_ascending(self):
        raw = _ticker_history_df(10)
        raw = raw.iloc[::-1]    # reverse order
        df = normalise_candles(raw)
        assert df.index.is_monotonic_increasing

    def test_empty_input_returns_empty_df(self):
        df = normalise_candles(pd.DataFrame())
        assert df.empty

    def test_none_input_returns_empty_df(self):
        df = normalise_candles(None)
        assert df.empty

    def test_multiindex_columns_price_first(self):
        """MultiIndex with (Price, Ticker) — from new yfinance download API."""
        raw = _ticker_history_df(5)
        raw.columns = pd.MultiIndex.from_tuples(
            [(c, "HDFCBANK.NS") for c in raw.columns]
        )
        # normalise should detect Price level (level 0) has OHLCV names
        # but here level 0 has them all — should flatten correctly
        raw_ohlcv = raw[["Open", "High", "Low", "Close", "Volume"]]
        raw_ohlcv.columns = pd.MultiIndex.from_tuples(
            [(c, "HDFCBANK.NS") for c in ["Open", "High", "Low", "Close", "Volume"]]
        )
        df = normalise_candles(raw_ohlcv)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_missing_ohlcv_column_raises(self):
        raw = _ticker_history_df(5).drop(columns=["Close"])
        with pytest.raises(ValueError, match="Missing columns"):
            normalise_candles(raw)


# ─────────────────────────────────────────────
# candle_builder — candles_to_records
# ─────────────────────────────────────────────

class TestCandlesToRecords:

    def _normalised(self, n=5):
        return normalise_candles(_ticker_history_df(n))

    def test_returns_list_of_dicts(self):
        df = self._normalised()
        records = candles_to_records(df, "HDFCBANK.NS")
        assert isinstance(records, list)
        assert all(isinstance(r, dict) for r in records)

    def test_record_count_matches_rows(self):
        df = self._normalised(8)
        assert len(candles_to_records(df, "HDFCBANK.NS")) == 8

    def test_required_keys_present(self):
        df = self._normalised(3)
        rec = candles_to_records(df, "HDFCBANK.NS")[0]
        assert {"symbol", "interval", "timestamp", "open", "high", "low", "close", "volume"} == set(rec.keys())

    def test_symbol_and_interval_correct(self):
        df = self._normalised(2)
        rec = candles_to_records(df, "TCS.NS", interval="1d")[0]
        assert rec["symbol"] == "TCS.NS"
        assert rec["interval"] == "1d"

    def test_timestamp_is_iso_string(self):
        df = self._normalised(2)
        rec = candles_to_records(df, "HDFCBANK.NS")[0]
        ts = rec["timestamp"]
        assert isinstance(ts, str)
        # Should be parseable
        pd.Timestamp(ts)

    def test_prices_rounded_to_2_decimals(self):
        df = self._normalised(3)
        for rec in candles_to_records(df, "HDFCBANK.NS"):
            for col in ["open", "high", "low", "close"]:
                assert round(rec[col], 2) == rec[col]

    def test_volume_is_int(self):
        df = self._normalised(3)
        for rec in candles_to_records(df, "HDFCBANK.NS"):
            assert isinstance(rec["volume"], int)

    def test_empty_df_returns_empty_list(self):
        assert candles_to_records(pd.DataFrame(), "HDFCBANK.NS") == []


# ─────────────────────────────────────────────
# candle_builder — records_to_dataframe
# ─────────────────────────────────────────────

class TestRecordsToDataframe:

    def _round_trip_records(self, n=5):
        df = normalise_candles(_ticker_history_df(n))
        return candles_to_records(df, "HDFCBANK.NS")

    def test_round_trip_preserves_row_count(self):
        records = self._round_trip_records(7)
        df = records_to_dataframe(records)
        assert len(df) == 7

    def test_round_trip_preserves_columns(self):
        records = self._round_trip_records(3)
        df = records_to_dataframe(records)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_index_is_ist(self):
        records = self._round_trip_records(3)
        df = records_to_dataframe(records)
        assert str(df.index.tz) == "Asia/Kolkata"

    def test_index_is_ascending(self):
        records = self._round_trip_records(5)
        df = records_to_dataframe(records)
        assert df.index.is_monotonic_increasing

    def test_close_values_preserved(self):
        original = normalise_candles(_ticker_history_df(5))
        records = candles_to_records(original, "HDFCBANK.NS")
        restored = records_to_dataframe(records)
        pd.testing.assert_series_equal(
            original["close"].reset_index(drop=True),
            restored["close"].reset_index(drop=True),
            check_names=False,
        )

    def test_empty_records_returns_empty_df(self):
        df = records_to_dataframe([])
        assert df.empty

    def test_extra_db_columns_ignored(self):
        """DB records include id, symbol, interval — these should be dropped."""
        records = self._round_trip_records(3)
        for r in records:
            r["id"] = 99
            r["symbol"] = "HDFCBANK.NS"
            r["interval"] = "5m"
        df = records_to_dataframe(records)
        assert "id" not in df.columns
        assert "symbol" not in df.columns


# ─────────────────────────────────────────────
# yfinance_client — mocked network calls
# ─────────────────────────────────────────────

from data import yfinance_client as yfc


class TestGet5MinCandles:

    def _mock_ticker(self, df):
        mock = MagicMock()
        mock.history.return_value = df
        return mock

    def test_returns_normalised_dataframe(self):
        raw = _ticker_history_df(20)
        with patch("data.yfinance_client.yf.Ticker", return_value=self._mock_ticker(raw)):
            df = yfc.get_5min_candles("HDFCBANK.NS")
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 20

    def test_calls_history_with_5m_interval(self):
        raw = _ticker_history_df(5)
        mock_ticker = self._mock_ticker(raw)
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            yfc.get_5min_candles("HDFCBANK.NS", period="3d")
        mock_ticker.history.assert_called_once()
        call_kwargs = mock_ticker.history.call_args.kwargs
        assert call_kwargs["interval"] == "5m"
        assert call_kwargs["period"] == "3d"

    def test_empty_response_returns_empty_df(self):
        mock_ticker = self._mock_ticker(pd.DataFrame())
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            df = yfc.get_5min_candles("HDFCBANK.NS")
        assert df.empty

    def test_exception_returns_empty_df(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("network error")
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            df = yfc.get_5min_candles("HDFCBANK.NS")
        assert isinstance(df, pd.DataFrame)
        assert df.empty


class TestGetDailyCandles:

    def _mock_ticker(self, df):
        mock = MagicMock()
        mock.history.return_value = df
        return mock

    def test_returns_normalised_dataframe(self):
        raw = _ticker_history_df(20, freq="1D", start="2026-02-01 15:30")
        mock_ticker = self._mock_ticker(raw)
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            df = yfc.get_daily_candles("HDFCBANK.NS")
        assert not df.empty
        assert "close" in df.columns

    def test_calls_history_with_1d_interval(self):
        raw = _ticker_history_df(10, freq="1D", start="2026-03-01 15:30")
        mock_ticker = self._mock_ticker(raw)
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            yfc.get_daily_candles("HDFCBANK.NS", period="20d")
        call_kwargs = mock_ticker.history.call_args.kwargs
        assert call_kwargs["interval"] == "1d"

    def test_exception_returns_empty_df(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = RuntimeError("timeout")
        with patch("data.yfinance_client.yf.Ticker", return_value=mock_ticker):
            df = yfc.get_daily_candles("TCS.NS")
        assert df.empty


class TestGetLatestPrice:

    def test_returns_float(self):
        raw = _ticker_history_df(5)
        mock = MagicMock()
        mock.history.return_value = raw
        with patch("data.yfinance_client.yf.Ticker", return_value=mock):
            price = yfc.get_latest_price("HDFCBANK.NS")
        assert isinstance(price, float)
        assert price > 0

    def test_returns_last_close(self):
        raw = _ticker_history_df(5, price_base=1642.0)
        mock = MagicMock()
        mock.history.return_value = raw
        with patch("data.yfinance_client.yf.Ticker", return_value=mock):
            price = yfc.get_latest_price("HDFCBANK.NS")
        expected = 1642.0 + (5 - 1) * 0.5   # last close in our synthetic data
        assert price == pytest.approx(expected)

    def test_returns_none_on_empty(self):
        mock = MagicMock()
        mock.history.return_value = pd.DataFrame()
        with patch("data.yfinance_client.yf.Ticker", return_value=mock):
            assert yfc.get_latest_price("HDFCBANK.NS") is None

    def test_returns_none_on_exception(self):
        mock = MagicMock()
        mock.history.side_effect = Exception("err")
        with patch("data.yfinance_client.yf.Ticker", return_value=mock):
            assert yfc.get_latest_price("HDFCBANK.NS") is None


class TestGetMultipleDaily:

    def test_returns_dict_of_dataframes(self):
        symbols = ["HDFCBANK.NS", "TCS.NS"]
        raw = _multi_ticker_download_df(symbols, n=15)
        with patch("data.yfinance_client.yf.download", return_value=raw):
            result = yfc.get_multiple_daily(symbols)
        assert isinstance(result, dict)
        for sym in symbols:
            assert sym in result
            assert isinstance(result[sym], pd.DataFrame)
            assert not result[sym].empty

    def test_normalised_columns(self):
        symbols = ["HDFCBANK.NS", "TCS.NS"]
        raw = _multi_ticker_download_df(symbols, n=10)
        with patch("data.yfinance_client.yf.download", return_value=raw):
            result = yfc.get_multiple_daily(symbols)
        for sym, df in result.items():
            assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_empty_symbols_returns_empty_dict(self):
        result = yfc.get_multiple_daily([])
        assert result == {}

    def test_download_exception_returns_empty_dict(self):
        with patch("data.yfinance_client.yf.download", side_effect=Exception("network")):
            result = yfc.get_multiple_daily(["HDFCBANK.NS"])
        assert result == {}

    def test_empty_download_returns_empty_dict(self):
        with patch("data.yfinance_client.yf.download", return_value=pd.DataFrame()):
            result = yfc.get_multiple_daily(["HDFCBANK.NS"])
        assert result == {}


# ─────────────────────────────────────────────
# historical.py — mocked
# ─────────────────────────────────────────────

from data.historical import fetch_historical_5min

class TestFetchHistorical5min:

    def _mock_ticker(self, df):
        mock = MagicMock()
        mock.history.return_value = df
        return mock

    def test_returns_normalised_df(self):
        raw = _ticker_history_df(30)
        mock_ticker = self._mock_ticker(raw)
        with patch("data.historical.yf.Ticker", return_value=mock_ticker):
            df = fetch_historical_5min(
                "HDFCBANK.NS",
                start=date(2026, 3, 10),
                end=date(2026, 3, 14),
            )
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 30

    def test_end_date_shifted_by_one(self):
        """yfinance end is exclusive; we must add 1 day."""
        raw = _ticker_history_df(10)
        mock_ticker = self._mock_ticker(raw)
        with patch("data.historical.yf.Ticker", return_value=mock_ticker):
            fetch_historical_5min(
                "HDFCBANK.NS",
                start=date(2026, 3, 10),
                end=date(2026, 3, 14),
            )
        call_kwargs = mock_ticker.history.call_args.kwargs
        assert call_kwargs["end"] == date(2026, 3, 15).isoformat()

    def test_empty_response_returns_empty_df(self):
        mock_ticker = self._mock_ticker(pd.DataFrame())
        with patch("data.historical.yf.Ticker", return_value=mock_ticker):
            df = fetch_historical_5min(
                "HDFCBANK.NS",
                start=date(2026, 3, 10),
                end=date(2026, 3, 14),
            )
        assert df.empty

    def test_exception_returns_empty_df(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("timeout")
        with patch("data.historical.yf.Ticker", return_value=mock_ticker):
            df = fetch_historical_5min(
                "HDFCBANK.NS",
                start=date(2026, 3, 10),
                end=date(2026, 3, 14),
            )
        assert df.empty


# ─────────────────────────────────────────────
# NIFTY50 symbol list sanity checks
# ─────────────────────────────────────────────

def test_nifty50_has_50_symbols():
    assert len(yfc.NIFTY50_SYMBOLS) == 50

def test_nifty50_symbols_have_ns_suffix():
    for sym in yfc.NIFTY50_SYMBOLS:
        assert sym.endswith(".NS"), f"{sym} missing .NS suffix"

def test_nifty50_no_duplicates():
    assert len(yfc.NIFTY50_SYMBOLS) == len(set(yfc.NIFTY50_SYMBOLS))
