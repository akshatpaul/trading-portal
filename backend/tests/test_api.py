"""
tests/test_api.py — FastAPI endpoint tests

Uses FastAPI TestClient (synchronous httpx).
All business-logic dependencies are mocked so no real DB or yfinance calls.

Run: pytest tests/test_api.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── App under test ────────────────────────────
# Import routes directly (avoids scheduler/DB side-effects from main.py)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router, health_router

_app = FastAPI()
_app.add_middleware(CORSMiddleware, allow_origins=["*"],
                    allow_methods=["*"], allow_headers=["*"])
_app.include_router(router)
_app.include_router(health_router)

client = TestClient(_app)


# ── Shared mock helpers ───────────────────────

def _status_mocks(mode="paper", capital=10_000.0, trades=0, final_pnl=0.0):
    summary = {
        "trades_count": trades, "wins": 0, "losses": 0,
        "final_pnl": final_pnl, "win_rate": 0.0,
        "gross_pnl": 0.0, "total_cost": 0.0, "net_pnl": 0.0,
        "tax_estimate": 0.0, "profit_factor": 0.0, "capital_end": capital,
        "date": "2026-03-16",
    }
    return (
        patch("api.routes.queries.get_setting",   return_value=mode),
        patch("api.routes.queries.set_setting"),
        patch("execution.paper_trader.queries.get_setting",  return_value=str(capital)),
        patch("execution.paper_trader.queries.get_trades",   return_value=[]),
        patch("execution.paper_trader.queries.upsert_daily_summary"),
    )


# ─────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────

class TestHealth:

    def test_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_status_ok(self):
        assert client.get("/health").json()["status"] == "ok"

    def test_has_mode(self):
        assert "mode" in client.get("/health").json()


# ─────────────────────────────────────────────
# GET /api/status
# ─────────────────────────────────────────────

class TestGetStatus:

    def test_returns_200(self):
        with patch("api.routes._current_mode", return_value="paper"), \
             patch("api.routes.is_market_open", return_value=True), \
             patch("api.routes.is_trading_day", return_value=True), \
             patch("execution.paper_trader.queries.get_setting", return_value="10000.0"), \
             patch("execution.paper_trader.queries.get_trades",  return_value=[]):
            r = client.get("/api/status")
        assert r.status_code == 200

    def test_has_required_keys(self):
        with patch("api.routes._current_mode", return_value="paper"), \
             patch("api.routes.is_market_open", return_value=False), \
             patch("api.routes.is_trading_day", return_value=True), \
             patch("execution.paper_trader.queries.get_setting", return_value="10000.0"), \
             patch("execution.paper_trader.queries.get_trades",  return_value=[]):
            data = client.get("/api/status").json()
        required = {"mode", "capital", "market_open", "trading_day",
                    "kite_configured", "telegram_configured",
                    "trading_allowed", "block_reason", "today"}
        assert required == set(data.keys())

    def test_mode_returned(self):
        with patch("api.routes._current_mode", return_value="paper"), \
             patch("api.routes.is_market_open", return_value=False), \
             patch("api.routes.is_trading_day", return_value=True), \
             patch("execution.paper_trader.queries.get_setting", return_value="10000.0"), \
             patch("execution.paper_trader.queries.get_trades",  return_value=[]):
            data = client.get("/api/status").json()
        assert data["mode"] == "paper"


# ─────────────────────────────────────────────
# GET /api/watchlist
# ─────────────────────────────────────────────

class TestGetWatchlist:

    def test_returns_200(self):
        with patch("api.routes.queries.get_watchlist", return_value=[]):
            r = client.get("/api/watchlist")
        assert r.status_code == 200

    def test_has_watchlist_key(self):
        with patch("api.routes.queries.get_watchlist", return_value=[]):
            data = client.get("/api/watchlist").json()
        assert "watchlist" in data

    def test_returns_rows(self):
        rows = [{"symbol": "HDFCBANK.NS", "rank": 1, "score": 2.5}]
        with patch("api.routes.queries.get_watchlist", return_value=rows):
            data = client.get("/api/watchlist").json()
        assert len(data["watchlist"]) == 1
        assert data["watchlist"][0]["symbol"] == "HDFCBANK.NS"


# ─────────────────────────────────────────────
# GET /api/positions
# ─────────────────────────────────────────────

class TestGetPositions:

    def test_returns_200(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None), \
             patch("data.yfinance_client.get_latest_price", return_value=None):
            r = client.get("/api/positions")
        assert r.status_code == 200

    def test_null_when_no_position(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None):
            data = client.get("/api/positions").json()
        assert data["position"] is None

    def test_returns_position_when_open(self):
        pos = {
            "id": 1, "symbol": "TCS.NS", "mode": "paper", "side": "BUY",
            "quantity": 3, "entry_price": 3000.0,
            "target": 3018.0, "stop_loss": 2991.0,
            "entry_time": "2026-03-16T10:00:00+05:30", "signal_id": None, "status": "open",
        }
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos), \
             patch("data.yfinance_client.get_latest_price", return_value=3010.0):
            data = client.get("/api/positions").json()
        assert data["position"]["symbol"] == "TCS.NS"
        assert data["position"]["ltp"] == 3010.0
        assert data["position"]["unrealised_pnl"] == pytest.approx(30.0)


# ─────────────────────────────────────────────
# GET /api/trades
# ─────────────────────────────────────────────

class TestGetTrades:

    def test_returns_200(self):
        with patch("api.routes.queries.get_trades", return_value=[]):
            r = client.get("/api/trades")
        assert r.status_code == 200

    def test_has_trades_and_count(self):
        with patch("api.routes.queries.get_trades", return_value=[]):
            data = client.get("/api/trades").json()
        assert "trades" in data
        assert "count" in data

    def test_limit_param_passed(self):
        with patch("api.routes.queries.get_trades", return_value=[]) as mock:
            client.get("/api/trades?limit=10")
        mock.assert_called_once_with(limit=10, mode=None)

    def test_count_matches_trades_length(self):
        trades = [{"id": 1}, {"id": 2}]
        with patch("api.routes.queries.get_trades", return_value=trades):
            data = client.get("/api/trades").json()
        assert data["count"] == 2


# ─────────────────────────────────────────────
# GET /api/candles/{symbol}
# ─────────────────────────────────────────────

class TestGetCandles:

    def test_returns_200(self):
        with patch("api.routes.queries.get_candles", return_value=[]):
            r = client.get("/api/candles/HDFCBANK.NS")
        assert r.status_code == 200

    def test_symbol_in_response(self):
        with patch("api.routes.queries.get_candles", return_value=[]):
            data = client.get("/api/candles/HDFCBANK.NS").json()
        assert data["symbol"] == "HDFCBANK.NS"

    def test_returns_candles_list(self):
        candles = [{"timestamp": "2026-03-16T09:35:00", "open": 1500.0}]
        with patch("api.routes.queries.get_candles", return_value=candles):
            data = client.get("/api/candles/HDFCBANK.NS").json()
        assert len(data["candles"]) == 1

    def test_interval_param(self):
        with patch("api.routes.queries.get_candles", return_value=[]) as mock:
            client.get("/api/candles/TCS.NS?interval=1d")
        mock.assert_called_once_with("TCS.NS", "1d", limit=200)


# ─────────────────────────────────────────────
# GET /api/performance
# ─────────────────────────────────────────────

class TestGetPerformance:

    def test_returns_200(self):
        with patch("api.routes.queries.get_performance_stats", return_value={}):
            r = client.get("/api/performance")
        assert r.status_code == 200


# ─────────────────────────────────────────────
# GET /api/risk-limits
# ─────────────────────────────────────────────

class TestGetRiskLimits:

    def test_returns_200(self):
        r = client.get("/api/risk-limits")
        assert r.status_code == 200

    def test_has_max_daily_loss(self):
        data = client.get("/api/risk-limits").json()
        assert "max_daily_loss" in data

    def test_max_daily_loss_value(self):
        data = client.get("/api/risk-limits").json()
        assert data["max_daily_loss"] == 300.0


# ─────────────────────────────────────────────
# POST /api/mode/live
# ─────────────────────────────────────────────

class TestSwitchToLive:

    def test_wrong_confirmation_returns_400(self):
        r = client.post("/api/mode/live", json={"confirmation": "wrong text"})
        assert r.status_code == 400

    def test_correct_confirmation_no_kite_returns_400(self):
        with patch("api.routes.settings") as cfg:
            cfg.kite_configured = False
            r = client.post(
                "/api/mode/live",
                json={"confirmation": "I understand this uses real money"}
            )
        assert r.status_code == 400

    def test_correct_confirmation_with_kite_returns_200(self):
        with patch("api.routes.settings") as cfg, \
             patch("api.routes._set_mode"):
            cfg.kite_configured = True
            r = client.post(
                "/api/mode/live",
                json={"confirmation": "I understand this uses real money"}
            )
        assert r.status_code == 200
        assert r.json()["mode"] == "live"

    def test_mode_set_in_db(self):
        with patch("api.routes.settings") as cfg, \
             patch("api.routes._set_mode") as mock_set:
            cfg.kite_configured = True
            client.post(
                "/api/mode/live",
                json={"confirmation": "I understand this uses real money"}
            )
        mock_set.assert_called_once_with("live")


# ─────────────────────────────────────────────
# POST /api/mode/paper
# ─────────────────────────────────────────────

class TestSwitchToPaper:

    def test_returns_200(self):
        with patch("api.routes._set_mode"):
            r = client.post("/api/mode/paper")
        assert r.status_code == 200

    def test_mode_is_paper(self):
        with patch("api.routes._set_mode"):
            data = client.post("/api/mode/paper").json()
        assert data["mode"] == "paper"

    def test_db_updated(self):
        with patch("api.routes._set_mode") as mock:
            client.post("/api/mode/paper")
        mock.assert_called_once_with("paper")


# ─────────────────────────────────────────────
# POST /api/emergency-stop
# ─────────────────────────────────────────────

class TestEmergencyStop:

    def test_returns_200_no_position(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None), \
             patch("api.routes.queries.set_setting"):
            r = client.post("/api/emergency-stop")
        assert r.status_code == 200

    def test_stopped_true(self):
        with patch("execution.paper_trader.queries.get_open_position", return_value=None), \
             patch("api.routes.queries.set_setting"):
            data = client.post("/api/emergency-stop").json()
        assert data["stopped"] is True

    def test_closes_open_position(self):
        pos = {
            "id": 1, "symbol": "TCS.NS", "mode": "paper", "side": "BUY",
            "quantity": 3, "entry_price": 3000.0,
            "target": 3018.0, "stop_loss": 2991.0,
            "entry_time": "2026-03-16T10:00:00+05:30",
            "signal_id": None, "status": "open",
        }
        with patch("execution.paper_trader.queries.get_open_position", return_value=pos), \
             patch("data.yfinance_client.get_latest_price", return_value=3005.0), \
             patch("execution.paper_trader.queries.get_setting", return_value="5000"), \
             patch("execution.paper_trader.queries.insert_trade", return_value=1), \
             patch("execution.paper_trader.queries.close_position"), \
             patch("execution.paper_trader.queries.set_setting"), \
             patch("execution.paper_trader.queries.upsert_daily_summary"), \
             patch("execution.paper_trader.queries.get_trades", return_value=[]), \
             patch("execution.paper_trader.now_ist", return_value=__import__("datetime").datetime(2026, 3, 16, 10, 30)), \
             patch("execution.paper_trader._send_exit_alert"), \
             patch("api.routes.queries.set_setting"):
            data = client.post("/api/emergency-stop").json()
        assert data["positions_closed"] == 1


# ─────────────────────────────────────────────
# GET /api/kite/login-url
# ─────────────────────────────────────────────

class TestKiteLoginUrl:

    def test_returns_200(self):
        mock_kite = MagicMock()
        mock_kite.return_value.login_url.return_value = "https://kite.zerodha.com/test"
        with patch("kiteconnect.KiteConnect", mock_kite):
            r = client.get("/api/kite/login-url")
        assert r.status_code == 200

    def test_has_url_key(self):
        mock_kite = MagicMock()
        mock_kite.return_value.login_url.return_value = "https://example.com"
        with patch("kiteconnect.KiteConnect", mock_kite):
            data = client.get("/api/kite/login-url").json()
        assert "url" in data
