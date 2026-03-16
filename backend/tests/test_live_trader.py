"""
tests/test_live_trader.py — Kite Connect live trader unit tests

All KiteConnect API calls are mocked — no real network calls.
Tests verify:
  - _get_kite raises when not configured
  - place_live_order constructs the correct Kite call and returns the right dict
  - get_live_positions / get_live_orders return safe empty list on error
  - cancel_live_order returns bool correctly
  - get_live_ltp extracts price correctly
  - ns_to_kite_symbol strips .NS
  - _map_order_type maps correctly

Run: pytest tests/test_live_trader.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from execution.live_trader import (
    place_live_order,
    get_live_positions,
    get_live_orders,
    cancel_live_order,
    get_live_ltp,
    get_kite_profile,
    ns_to_kite_symbol,
    _get_kite,
    _map_order_type,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _mock_kite(order_id="ORDER123"):
    """Return a mock KiteConnect instance."""
    kite = MagicMock()
    kite.place_order.return_value = order_id
    kite.positions.return_value   = {"day": [{"symbol": "HDFCBANK", "quantity": 5}]}
    kite.orders.return_value      = [{"order_id": order_id, "status": "COMPLETE"}]
    kite.ltp.return_value         = {"NSE:HDFCBANK": {"last_price": 1542.5}}
    kite.profile.return_value     = {"user_id": "AB1234", "user_name": "Test User"}
    return kite


def _patch_kite(kite=None):
    """Context manager that patches _get_kite to return a mock."""
    mock = kite or _mock_kite()
    return patch("execution.live_trader._get_kite", return_value=mock)


# ─────────────────────────────────────────────
# ns_to_kite_symbol
# ─────────────────────────────────────────────

class TestNsToKiteSymbol:

    def test_strips_ns_suffix(self):
        assert ns_to_kite_symbol("HDFCBANK.NS") == "HDFCBANK"

    def test_no_suffix_unchanged(self):
        assert ns_to_kite_symbol("HDFCBANK") == "HDFCBANK"

    def test_multiple_symbols(self):
        symbols = ["TCS.NS", "INFY.NS", "RELIANCE.NS"]
        expected = ["TCS", "INFY", "RELIANCE"]
        assert [ns_to_kite_symbol(s) for s in symbols] == expected


# ─────────────────────────────────────────────
# _map_order_type
# ─────────────────────────────────────────────

class TestMapOrderType:

    def test_market(self):
        assert _map_order_type("MARKET") == "MARKET"

    def test_limit(self):
        assert _map_order_type("LIMIT") == "LIMIT"

    def test_case_insensitive(self):
        assert _map_order_type("market") == "MARKET"

    def test_unknown_defaults_to_market(self):
        assert _map_order_type("FOO") == "MARKET"


# ─────────────────────────────────────────────
# _get_kite
# ─────────────────────────────────────────────

class TestGetKite:

    def test_raises_when_not_configured(self):
        with patch("execution.live_trader.settings") as mock_cfg:
            mock_cfg.kite_configured = False
            with pytest.raises(RuntimeError, match="not configured"):
                _get_kite()

    def test_returns_kite_when_configured(self):
        mock_kite_cls = MagicMock()
        mock_instance = MagicMock()
        mock_kite_cls.return_value = mock_instance

        with patch("execution.live_trader.settings") as mock_cfg, \
             patch("kiteconnect.KiteConnect", mock_kite_cls):
            mock_cfg.kite_configured    = True
            mock_cfg.kite_api_key       = "test_key"
            mock_cfg.kite_access_token  = "test_token"
            result = _get_kite()

        mock_kite_cls.assert_called_once_with(api_key="test_key")
        mock_instance.set_access_token.assert_called_once_with("test_token")


# ─────────────────────────────────────────────
# place_live_order
# ─────────────────────────────────────────────

class TestPlaceLiveOrder:

    def _place(self, symbol="HDFCBANK", side="BUY", qty=5, order_type="MARKET"):
        kite = _mock_kite()
        with _patch_kite(kite), \
             patch("execution.live_trader._fire_order_alert"):
            result = place_live_order(symbol, side, qty, order_type)
        return result, kite

    def test_returns_dict(self):
        result, _ = self._place()
        assert isinstance(result, dict)

    def test_required_keys(self):
        result, _ = self._place()
        required = {"order_id", "symbol", "side", "quantity",
                    "order_type", "status", "exchange", "product", "mode"}
        assert required == set(result.keys())

    def test_order_id_from_kite(self):
        result, _ = self._place()
        assert result["order_id"] == "ORDER123"

    def test_symbol_stored(self):
        result, _ = self._place(symbol="TCS")
        assert result["symbol"] == "TCS"

    def test_side_stored(self):
        result, _ = self._place(side="BUY")
        assert result["side"] == "BUY"

    def test_quantity_stored(self):
        result, _ = self._place(qty=3)
        assert result["quantity"] == 3

    def test_mode_is_live(self):
        result, _ = self._place()
        assert result["mode"] == "live"

    def test_product_is_mis(self):
        result, _ = self._place()
        assert result["product"] == "MIS"

    def test_exchange_is_nse(self):
        result, _ = self._place()
        assert result["exchange"] == "NSE"

    def test_kite_place_order_called_with_correct_args(self):
        result, kite = self._place(symbol="INFY", side="BUY", qty=4)
        kite.place_order.assert_called_once()
        kwargs = kite.place_order.call_args.kwargs
        assert kwargs["tradingsymbol"] == "INFY"
        assert kwargs["transaction_type"] == "BUY"
        assert kwargs["quantity"] == 4
        assert kwargs["product"] == "MIS"
        assert kwargs["exchange"] == "NSE"

    def test_not_configured_raises(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            with pytest.raises(RuntimeError):
                place_live_order("HDFCBANK", "BUY", 5)


# ─────────────────────────────────────────────
# get_live_positions
# ─────────────────────────────────────────────

class TestGetLivePositions:

    def test_returns_list(self):
        with _patch_kite():
            result = get_live_positions()
        assert isinstance(result, list)

    def test_returns_day_positions(self):
        with _patch_kite():
            result = get_live_positions()
        assert len(result) == 1
        assert result[0]["symbol"] == "HDFCBANK"

    def test_not_configured_returns_empty(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            result = get_live_positions()
        assert result == []

    def test_kite_error_returns_empty(self):
        kite = _mock_kite()
        kite.positions.side_effect = Exception("API error")
        with _patch_kite(kite):
            result = get_live_positions()
        assert result == []

    def test_kite_error_does_not_raise(self):
        kite = _mock_kite()
        kite.positions.side_effect = Exception("timeout")
        with _patch_kite(kite):
            get_live_positions()  # must not raise


# ─────────────────────────────────────────────
# get_live_orders
# ─────────────────────────────────────────────

class TestGetLiveOrders:

    def test_returns_list(self):
        with _patch_kite():
            result = get_live_orders()
        assert isinstance(result, list)

    def test_returns_orders(self):
        with _patch_kite():
            result = get_live_orders()
        assert len(result) == 1
        assert result[0]["order_id"] == "ORDER123"

    def test_not_configured_returns_empty(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            assert get_live_orders() == []

    def test_kite_error_returns_empty(self):
        kite = _mock_kite()
        kite.orders.side_effect = Exception("network error")
        with _patch_kite(kite):
            assert get_live_orders() == []


# ─────────────────────────────────────────────
# cancel_live_order
# ─────────────────────────────────────────────

class TestCancelLiveOrder:

    def test_returns_true_on_success(self):
        with _patch_kite():
            assert cancel_live_order("ORDER123") is True

    def test_calls_kite_cancel(self):
        kite = _mock_kite()
        with _patch_kite(kite):
            cancel_live_order("ORDER123")
        kite.cancel_order.assert_called_once()

    def test_not_configured_returns_false(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            assert cancel_live_order("X") is False

    def test_kite_error_returns_false(self):
        kite = _mock_kite()
        kite.cancel_order.side_effect = Exception("order already executed")
        with _patch_kite(kite):
            assert cancel_live_order("ORDER123") is False

    def test_kite_error_does_not_raise(self):
        kite = _mock_kite()
        kite.cancel_order.side_effect = Exception("boom")
        with _patch_kite(kite):
            cancel_live_order("ORDER123")   # must not raise


# ─────────────────────────────────────────────
# get_live_ltp
# ─────────────────────────────────────────────

class TestGetLiveLtp:

    def test_returns_float(self):
        with _patch_kite():
            result = get_live_ltp("HDFCBANK")
        assert isinstance(result, float)

    def test_returns_correct_price(self):
        with _patch_kite():
            result = get_live_ltp("HDFCBANK")
        assert result == pytest.approx(1542.5)

    def test_not_configured_returns_none(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            assert get_live_ltp("HDFCBANK") is None

    def test_kite_error_returns_none(self):
        kite = _mock_kite()
        kite.ltp.side_effect = Exception("symbol not found")
        with _patch_kite(kite):
            assert get_live_ltp("UNKNOWN") is None

    def test_ltp_called_with_nse_prefix(self):
        kite = _mock_kite()
        with _patch_kite(kite):
            get_live_ltp("HDFCBANK")
        kite.ltp.assert_called_once_with(["NSE:HDFCBANK"])


# ─────────────────────────────────────────────
# get_kite_profile
# ─────────────────────────────────────────────

class TestGetKiteProfile:

    def test_returns_dict_when_configured(self):
        with _patch_kite():
            result = get_kite_profile()
        assert isinstance(result, dict)
        assert result["user_id"] == "AB1234"

    def test_not_configured_returns_none(self):
        with patch("execution.live_trader._get_kite",
                   side_effect=RuntimeError("not configured")):
            assert get_kite_profile() is None

    def test_kite_error_returns_none(self):
        kite = _mock_kite()
        kite.profile.side_effect = Exception("token expired")
        with _patch_kite(kite):
            assert get_kite_profile() is None
