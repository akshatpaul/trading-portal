"""
tests/test_paper_trader.py — Paper trading engine unit tests

All DB calls, Telegram alerts, and clock reads are mocked.
Tests focus on slippage math, P&L calculation, capital accounting,
and correct DB interactions.

Run: pytest tests/test_paper_trader.py -v
"""

import pytest
import pytz
from datetime import datetime, date
from unittest.mock import patch, MagicMock, call

IST = pytz.timezone("Asia/Kolkata")

from execution.paper_trader import (
    place_paper_order,
    close_paper_position,
    get_paper_capital,
    get_open_paper_position,
    get_daily_paper_summary,
    _apply_slippage,
    SLIPPAGE_PCT,
    _DEFAULT_CAPITAL,
    _CAPITAL_KEY,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

_NOW = datetime(2026, 3, 16, 10, 30, 0, tzinfo=IST)


def _open_position(
    id: int = 1,
    symbol: str = "HDFCBANK.NS",
    quantity: int = 5,
    entry_price: float = 1500.5,
) -> dict:
    return {
        "id":          id,
        "symbol":      symbol,
        "mode":        "paper",
        "side":        "BUY",
        "quantity":    quantity,
        "entry_price": entry_price,
        "target":      round(entry_price * 1.006, 2),
        "stop_loss":   round(entry_price * 0.997, 2),
        "entry_time":  _NOW.isoformat(),
        "signal_id":   None,
        "status":      "open",
    }


# ─────────────────────────────────────────────
# _apply_slippage
# ─────────────────────────────────────────────

class TestApplySlippage:

    def test_buy_fills_higher(self):
        fill = _apply_slippage(1000.0, "BUY")
        assert fill > 1000.0

    def test_sell_fills_lower(self):
        fill = _apply_slippage(1000.0, "SELL")
        assert fill < 1000.0

    def test_buy_slippage_exact(self):
        fill = _apply_slippage(1000.0, "BUY")
        assert fill == pytest.approx(1000.0 * (1 + SLIPPAGE_PCT), rel=1e-6)

    def test_sell_slippage_exact(self):
        fill = _apply_slippage(1000.0, "SELL")
        assert fill == pytest.approx(1000.0 * (1 - SLIPPAGE_PCT), rel=1e-6)

    def test_result_rounded_to_2dp(self):
        fill = _apply_slippage(1234.56, "BUY")
        assert fill == round(fill, 2)


# ─────────────────────────────────────────────
# get_paper_capital
# ─────────────────────────────────────────────

class TestGetPaperCapital:

    def test_returns_float(self):
        with patch("execution.paper_trader.queries.get_setting", return_value="10000.0"):
            assert isinstance(get_paper_capital(), float)

    def test_reads_stored_value(self):
        with patch("execution.paper_trader.queries.get_setting", return_value="7500.0"):
            assert get_paper_capital() == pytest.approx(7500.0)

    def test_defaults_to_10000_when_not_set(self):
        with patch("execution.paper_trader.queries.get_setting",
                   return_value=str(_DEFAULT_CAPITAL)):
            assert get_paper_capital() == pytest.approx(_DEFAULT_CAPITAL)

    def test_uses_correct_key(self):
        with patch("execution.paper_trader.queries.get_setting", return_value="0") as mock:
            get_paper_capital()
        mock.assert_called_once_with(_CAPITAL_KEY, str(_DEFAULT_CAPITAL))


# ─────────────────────────────────────────────
# place_paper_order
# ─────────────────────────────────────────────

class TestPlacePaperOrder:

    def _place(self, price=1000.0, quantity=5, capital="10000.0"):
        with patch("execution.paper_trader.queries.get_setting",  return_value=capital), \
             patch("execution.paper_trader.queries.set_setting")  as mock_set, \
             patch("execution.paper_trader.queries.insert_position", return_value=1), \
             patch("execution.paper_trader.now_ist", return_value=_NOW), \
             patch("execution.paper_trader._send_entry_alert"):
            result = place_paper_order("HDFCBANK.NS", "BUY", quantity, price, "test signal")
        return result, mock_set

    def test_returns_dict(self):
        result, _ = self._place()
        assert isinstance(result, dict)

    def test_required_keys(self):
        result, _ = self._place()
        required = {"order_id", "symbol", "side", "quantity", "fill_price",
                    "target", "stop_loss", "timestamp", "capital_remaining", "mode"}
        assert required == set(result.keys())

    def test_fill_price_has_slippage(self):
        result, _ = self._place(price=1000.0)
        expected_fill = round(1000.0 * (1 + SLIPPAGE_PCT), 2)
        assert result["fill_price"] == expected_fill

    def test_mode_is_paper(self):
        result, _ = self._place()
        assert result["mode"] == "paper"

    def test_side_is_buy(self):
        result, _ = self._place()
        assert result["side"] == "BUY"

    def test_symbol_correct(self):
        result, _ = self._place()
        assert result["symbol"] == "HDFCBANK.NS"

    def test_quantity_correct(self):
        result, _ = self._place(quantity=3)
        assert result["quantity"] == 3

    def test_target_above_fill(self):
        result, _ = self._place(price=1000.0)
        assert result["target"] > result["fill_price"]

    def test_stop_below_fill(self):
        result, _ = self._place(price=1000.0)
        assert result["stop_loss"] < result["fill_price"]

    def test_capital_deducted(self):
        """capital_remaining = initial_capital - fill_price × quantity"""
        price, qty = 1000.0, 5
        fill = round(price * (1 + SLIPPAGE_PCT), 2)
        expected = round(10000.0 - fill * qty, 2)
        result, _ = self._place(price=price, quantity=qty, capital="10000.0")
        assert result["capital_remaining"] == pytest.approx(expected, rel=1e-6)

    def test_capital_saved_to_db(self):
        _, mock_set = self._place(price=1000.0, quantity=5, capital="10000.0")
        mock_set.assert_called_once()
        saved_key, saved_val = mock_set.call_args[0]
        assert saved_key == _CAPITAL_KEY
        assert float(saved_val) < 10000.0   # capital went down

    def test_position_inserted_to_db(self):
        with patch("execution.paper_trader.queries.get_setting", return_value="10000.0"), \
             patch("execution.paper_trader.queries.set_setting"), \
             patch("execution.paper_trader.queries.insert_position", return_value=42) as mock_ins, \
             patch("execution.paper_trader.now_ist", return_value=_NOW), \
             patch("execution.paper_trader._send_entry_alert"):
            result = place_paper_order("TCS.NS", "BUY", 2, 3000.0, "test")
        mock_ins.assert_called_once()
        assert result["order_id"] == 42


# ─────────────────────────────────────────────
# close_paper_position
# ─────────────────────────────────────────────

class TestClosePaperPosition:

    def _close(
        self,
        entry_price: float = 1000.5,
        exit_price: float = 1006.0,
        quantity: int = 5,
        capital: str = "4997.5",
        exit_reason: str = "TARGET",
    ):
        pos = _open_position(entry_price=entry_price, quantity=quantity)
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos), \
             patch("execution.paper_trader.queries.insert_trade", return_value=99), \
             patch("execution.paper_trader.queries.close_position"), \
             patch("execution.paper_trader.queries.get_setting", return_value=capital), \
             patch("execution.paper_trader.queries.set_setting"), \
             patch("execution.paper_trader.queries.upsert_daily_summary"), \
             patch("execution.paper_trader.queries.get_trades", return_value=[]), \
             patch("execution.paper_trader.now_ist", return_value=_NOW), \
             patch("execution.paper_trader._send_exit_alert"):
            return close_paper_position(1, exit_price, exit_reason)

    def test_returns_dict(self):
        assert isinstance(self._close(), dict)

    def test_has_trade_id(self):
        result = self._close()
        assert result["trade_id"] == 99

    def test_gross_pnl_correct(self):
        # (1006 - 1000.5) * 5 = 27.5
        result = self._close(entry_price=1000.5, exit_price=1006.0, quantity=5)
        assert result["gross_pnl"] == pytest.approx(27.5, rel=1e-4)

    def test_net_pnl_less_than_gross(self):
        """Costs always reduce net below gross."""
        result = self._close()
        assert result["net_pnl"] < result["gross_pnl"]

    def test_final_pnl_leq_net_pnl(self):
        """Tax estimate further reduces final P&L."""
        result = self._close()
        assert result["final_pnl"] <= result["net_pnl"]

    def test_exit_reason_stored(self):
        result = self._close(exit_reason="STOP_LOSS")
        assert result["exit_reason"] == "STOP_LOSS"

    def test_exit_price_stored(self):
        result = self._close(exit_price=1006.0)
        assert result["exit_price"] == 1006.0

    def test_entry_price_stored(self):
        result = self._close(entry_price=1000.5)
        assert result["entry_price"] == 1000.5

    def test_capital_returned_after_close(self):
        """Capital increases when position is closed at profit."""
        result = self._close(capital="4997.5", exit_price=1006.0)
        assert result["capital_after"] > 4997.5

    def test_raises_if_no_open_position(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None):
            with pytest.raises(ValueError):
                close_paper_position(1, 1000.0, "MANUAL")

    def test_raises_if_wrong_position_id(self):
        pos = _open_position(id=1)
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos):
            with pytest.raises(ValueError):
                close_paper_position(999, 1000.0, "MANUAL")   # wrong id

    def test_total_cost_positive(self):
        result = self._close()
        assert result["total_cost"] > 0

    def test_position_closed_in_db(self):
        pos = _open_position()
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos), \
             patch("execution.paper_trader.queries.insert_trade", return_value=1), \
             patch("execution.paper_trader.queries.close_position") as mock_close, \
             patch("execution.paper_trader.queries.get_setting", return_value="5000"), \
             patch("execution.paper_trader.queries.set_setting"), \
             patch("execution.paper_trader.queries.upsert_daily_summary"), \
             patch("execution.paper_trader.queries.get_trades", return_value=[]), \
             patch("execution.paper_trader.now_ist", return_value=_NOW), \
             patch("execution.paper_trader._send_exit_alert"):
            close_paper_position(1, 1006.0, "TARGET")
        mock_close.assert_called_once_with(1, _NOW.isoformat())

    def test_trade_inserted_in_db(self):
        pos = _open_position()
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos), \
             patch("execution.paper_trader.queries.insert_trade", return_value=1) as mock_ins, \
             patch("execution.paper_trader.queries.close_position"), \
             patch("execution.paper_trader.queries.get_setting", return_value="5000"), \
             patch("execution.paper_trader.queries.set_setting"), \
             patch("execution.paper_trader.queries.upsert_daily_summary"), \
             patch("execution.paper_trader.queries.get_trades", return_value=[]), \
             patch("execution.paper_trader.now_ist", return_value=_NOW), \
             patch("execution.paper_trader._send_exit_alert"):
            close_paper_position(1, 1006.0, "TARGET")
        mock_ins.assert_called_once()


# ─────────────────────────────────────────────
# get_open_paper_position
# ─────────────────────────────────────────────

class TestGetOpenPaperPosition:

    def test_returns_position_when_open(self):
        pos = _open_position()
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos):
            result = get_open_paper_position()
        assert result == pos

    def test_returns_none_when_no_position(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None):
            assert get_open_paper_position() is None

    def test_returns_none_for_live_position(self):
        """Paper trader ignores positions from live mode."""
        live_pos = {**_open_position(), "mode": "live"}
        with patch("execution.paper_trader.queries.get_open_position", return_value=live_pos):
            assert get_open_paper_position() is None


# ─────────────────────────────────────────────
# get_daily_paper_summary
# ─────────────────────────────────────────────

class TestGetDailyPaperSummary:

    def _summary(self, trades: list):
        with patch("execution.paper_trader.queries.get_trades", return_value=trades), \
             patch("execution.paper_trader.queries.get_setting", return_value="10000.0"):
            return get_daily_paper_summary()

    def _trade(self, gross=50.0, total_cost=5.0, net=45.0, tax=0.0, final=45.0):
        return {
            "gross_pnl":    gross,
            "total_cost":   total_cost,
            "net_pnl":      net,
            "tax_estimate": tax,
            "final_pnl":    final,
        }

    def test_returns_dict(self):
        assert isinstance(self._summary([]), dict)

    def test_required_keys(self):
        keys = self._summary([]).keys()
        required = {"date", "trades_count", "wins", "losses",
                    "gross_pnl", "total_cost", "net_pnl",
                    "tax_estimate", "final_pnl",
                    "win_rate", "profit_factor", "capital_end"}
        assert required == set(keys)

    def test_empty_trades_zeros(self):
        s = self._summary([])
        assert s["trades_count"] == 0
        assert s["gross_pnl"]    == 0.0
        assert s["win_rate"]     == 0.0

    def test_counts_correctly(self):
        trades = [
            self._trade(final=50.0),
            self._trade(final=-20.0),
            self._trade(final=30.0),
        ]
        s = self._summary(trades)
        assert s["trades_count"] == 3
        assert s["wins"]   == 2
        assert s["losses"] == 1

    def test_win_rate_calculation(self):
        trades = [self._trade(final=50.0), self._trade(final=-20.0)]
        s = self._summary(trades)
        assert s["win_rate"] == pytest.approx(0.5, rel=1e-6)

    def test_gross_pnl_summed(self):
        trades = [self._trade(gross=50.0), self._trade(gross=30.0)]
        s = self._summary(trades)
        assert s["gross_pnl"] == pytest.approx(80.0, rel=1e-6)

    def test_final_pnl_summed(self):
        trades = [self._trade(final=45.0), self._trade(final=-15.0)]
        s = self._summary(trades)
        assert s["final_pnl"] == pytest.approx(30.0, rel=1e-6)

    def test_profit_factor_all_wins(self):
        trades = [self._trade(final=50.0), self._trade(final=30.0)]
        s = self._summary(trades)
        assert s["profit_factor"] == float("inf")

    def test_profit_factor_mixed(self):
        trades = [self._trade(final=60.0), self._trade(final=-20.0)]
        s = self._summary(trades)
        assert s["profit_factor"] == pytest.approx(3.0, rel=1e-4)

    def test_capital_end_included(self):
        s = self._summary([])
        assert s["capital_end"] == pytest.approx(10000.0)
