"""
tests/test_telegram.py — Telegram alert unit tests

Strategy:
  - send_message is always mocked — no real network calls
  - Tests verify:
      1. send_message is called (alert actually fires)
      2. Message text contains expected substrings
      3. Not-configured path logs and returns False without calling Bot
      4. Errors in Bot.send_message are caught — never raise

Run: pytest tests/test_telegram.py -v
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# ── run async helpers ─────────────────────────
def run(coro):
    return asyncio.run(coro)


# We import the module functions directly so patches are applied correctly
from alerts import telegram as tg


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def _patch_send(mock_return=True):
    """Patch send_message and return the mock."""
    return patch("alerts.telegram.send_message", new_callable=AsyncMock, return_value=mock_return)


# ─────────────────────────────────────────────
# send_message — core behaviour
# ─────────────────────────────────────────────

class TestSendMessage:

    def test_not_configured_returns_false(self):
        with patch("alerts.telegram.settings") as mock_cfg:
            mock_cfg.telegram_configured = False
            result = run(tg.send_message("hello"))
        assert result is False

    def test_not_configured_does_not_call_bot(self):
        with patch("alerts.telegram.settings") as mock_cfg, \
             patch("telegram.Bot") as mock_bot:
            mock_cfg.telegram_configured = False
            run(tg.send_message("hello"))
        mock_bot.assert_not_called()

    def test_configured_calls_bot(self):
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_message = AsyncMock()
        with patch("alerts.telegram.settings") as mock_cfg, \
             patch("telegram.Bot", return_value=mock_bot_instance):
            mock_cfg.telegram_configured = True
            mock_cfg.telegram_bot_token  = "fake-token"
            mock_cfg.telegram_chat_id    = "123"
            result = run(tg.send_message("hello"))
        mock_bot_instance.send_message.assert_called_once()
        assert result is True

    def test_bot_exception_returns_false(self):
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_message = AsyncMock(side_effect=Exception("network error"))
        with patch("alerts.telegram.settings") as mock_cfg, \
             patch("telegram.Bot", return_value=mock_bot_instance):
            mock_cfg.telegram_configured = True
            mock_cfg.telegram_bot_token  = "token"
            mock_cfg.telegram_chat_id    = "123"
            result = run(tg.send_message("hello"))
        assert result is False

    def test_bot_exception_does_not_raise(self):
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("alerts.telegram.settings") as mock_cfg, \
             patch("telegram.Bot", return_value=mock_bot_instance):
            mock_cfg.telegram_configured = True
            mock_cfg.telegram_bot_token  = "token"
            mock_cfg.telegram_chat_id    = "123"
            # Must not raise
            run(tg.send_message("hello"))

    def test_long_message_trimmed_to_4096(self):
        captured = {}
        mock_bot_instance = MagicMock()

        async def capture_call(**kwargs):
            captured["text"] = kwargs.get("text", "")
        mock_bot_instance.send_message = AsyncMock(side_effect=capture_call)

        with patch("alerts.telegram.settings") as mock_cfg, \
             patch("telegram.Bot", return_value=mock_bot_instance):
            mock_cfg.telegram_configured = True
            mock_cfg.telegram_bot_token  = "token"
            mock_cfg.telegram_chat_id    = "123"
            run(tg.send_message("x" * 5000))

        assert len(captured["text"]) <= 4096


# ─────────────────────────────────────────────
# System events
# ─────────────────────────────────────────────

class TestSystemAlerts:

    def test_system_online_fires(self):
        with patch("alerts.telegram.settings") as cfg, _patch_send() as mock_send:
            cfg.app_mode = "paper"
            cfg.starting_capital = 10000.0
            run(tg.send_system_online())
        mock_send.assert_called_once()

    def test_system_online_contains_mode(self):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.settings") as cfg, \
             patch("alerts.telegram.send_message", side_effect=capture):
            cfg.app_mode = "paper"
            cfg.starting_capital = 10000.0
            run(tg.send_system_online())
        assert "PAPER" in texts[0] or "paper" in texts[0].lower()

    def test_system_offline_fires(self):
        with _patch_send() as mock_send:
            run(tg.send_system_offline())
        mock_send.assert_called_once()

    def test_send_error_fires(self):
        with _patch_send() as mock_send:
            run(tg.send_error("something broke"))
        mock_send.assert_called_once()

    def test_send_error_contains_description(self):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.send_message", side_effect=capture):
            run(tg.send_error("disk full"))
        assert "disk full" in texts[0]


# ─────────────────────────────────────────────
# Pre-market
# ─────────────────────────────────────────────

class TestWatchlistAlert:

    def _texts(self, symbols):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.send_message", side_effect=capture):
            run(tg.send_watchlist(symbols))
        return texts

    def test_fires(self):
        with _patch_send() as mock_send:
            run(tg.send_watchlist(["HDFCBANK.NS"]))
        mock_send.assert_called_once()

    def test_symbol_name_without_ns_suffix(self):
        texts = self._texts(["HDFCBANK.NS", "TCS.NS"])
        assert "HDFCBANK" in texts[0]
        assert ".NS" not in texts[0]

    def test_count_in_message(self):
        texts = self._texts(["HDFCBANK.NS", "TCS.NS", "INFY.NS"])
        assert "3" in texts[0]

    def test_empty_list_still_fires(self):
        with _patch_send() as mock_send:
            run(tg.send_watchlist([]))
        mock_send.assert_called_once()


# ─────────────────────────────────────────────
# Trade entry / exit
# ─────────────────────────────────────────────

class TestTradeEntryAlert:

    def _order(self):
        return {
            "symbol": "HDFCBANK.NS", "mode": "paper",
            "side": "BUY", "quantity": 5,
            "fill_price": 1500.5, "target": 1509.5,
            "stop_loss": 1496.0, "capital_remaining": 2500.0,
        }

    def test_fires(self):
        with _patch_send() as mock_send:
            run(tg.send_trade_entry(self._order(), "EMA crossover"))
        mock_send.assert_called_once()

    def test_contains_symbol(self):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.send_message", side_effect=capture):
            run(tg.send_trade_entry(self._order()))
        assert "HDFCBANK" in texts[0]

    def test_contains_price(self):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.send_message", side_effect=capture):
            run(tg.send_trade_entry(self._order()))
        assert "1,500" in texts[0] or "1500" in texts[0]

    def test_signal_reason_included_when_provided(self):
        texts = []
        async def capture(text):
            texts.append(text)
        with patch("alerts.telegram.send_message", side_effect=capture):
            run(tg.send_trade_entry(self._order(), "EMA9/21 crossover"))
        assert "EMA9/21 crossover" in texts[0]


class TestTradeExitAlert:

    def _trade(self, reason="TARGET", net_pnl=45.0):
        return {
            "symbol": "HDFCBANK.NS", "exit_reason": reason,
            "net_pnl": net_pnl, "quantity": 5,
            "entry_price": 1500.5, "exit_price": 1509.5,
        }

    def test_target_routes_to_target_hit(self):
        with patch("alerts.telegram.send_target_hit", new_callable=AsyncMock) as mock_t:
            run(tg.send_trade_exit(self._trade(reason="TARGET")))
        mock_t.assert_called_once()

    def test_stop_routes_to_stop_hit(self):
        with patch("alerts.telegram.send_stop_hit", new_callable=AsyncMock) as mock_s:
            run(tg.send_trade_exit(self._trade(reason="STOP_LOSS")))
        mock_s.assert_called_once()

    def test_force_close_routes_correctly(self):
        with patch("alerts.telegram.send_force_close", new_callable=AsyncMock) as mock_f:
            run(tg.send_trade_exit(self._trade(reason="FORCE_CLOSE")))
        mock_f.assert_called_once()

    def test_manual_fires_send_message(self):
        with _patch_send() as mock_send:
            run(tg.send_trade_exit(self._trade(reason="MANUAL")))
        mock_send.assert_called_once()


# ─────────────────────────────────────────────
# Trade outcomes
# ─────────────────────────────────────────────

class TestOutcomeAlerts:

    def test_target_hit_fires(self):
        with _patch_send() as m:
            run(tg.send_target_hit("HDFCBANK.NS", 45.0))
        m.assert_called_once()

    def test_target_hit_positive_has_plus_sign(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_target_hit("HDFCBANK.NS", 45.0))
        assert "+" in texts[0]

    def test_stop_hit_fires(self):
        with _patch_send() as m:
            run(tg.send_stop_hit("HDFCBANK.NS", -30.0))
        m.assert_called_once()

    def test_force_close_fires(self):
        with _patch_send() as m:
            run(tg.send_force_close("HDFCBANK.NS"))
        m.assert_called_once()

    def test_force_close_symbol_without_ns(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_force_close("TCS.NS"))
        assert "TCS" in texts[0]
        assert ".NS" not in texts[0]

    def test_daily_limit_fires(self):
        with _patch_send() as m:
            run(tg.send_daily_limit_hit())
        m.assert_called_once()


# ─────────────────────────────────────────────
# Daily summary
# ─────────────────────────────────────────────

class TestDailySummaryAlert:

    def _summary(self):
        return {
            "date": "2026-03-16",
            "trades_count": 2, "wins": 1, "losses": 1,
            "gross_pnl": 80.0, "total_cost": 12.0,
            "net_pnl": 68.0, "tax_estimate": 0.0,
            "final_pnl": 68.0,
            "win_rate": 0.5, "profit_factor": 2.0,
            "capital_end": 10068.0,
        }

    def test_fires(self):
        with _patch_send() as m:
            run(tg.send_daily_summary(self._summary()))
        m.assert_called_once()

    def test_contains_date(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_daily_summary(self._summary()))
        assert "2026-03-16" in texts[0]

    def test_contains_trade_count(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_daily_summary(self._summary()))
        assert "2" in texts[0]

    def test_contains_final_pnl(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_daily_summary(self._summary()))
        assert "68" in texts[0]

    def test_infinite_profit_factor_shows_symbol(self):
        s = {**self._summary(), "profit_factor": float("inf")}
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_daily_summary(s))
        assert "∞" in texts[0]

    def test_negative_final_pnl_no_plus_sign(self):
        s = {**self._summary(), "final_pnl": -30.0, "net_pnl": -30.0}
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_daily_summary(s))
        # No leading "+" for negative
        # Find the final pnl line
        assert "+₹-30" not in texts[0]


# ─────────────────────────────────────────────
# Signal alert
# ─────────────────────────────────────────────

class TestSignalAlert:

    def test_fires(self):
        with _patch_send() as m:
            run(tg.send_signal("HDFCBANK.NS", "BUY", 1500.0))
        m.assert_called_once()

    def test_buy_contains_symbol_and_price(self):
        texts = []
        async def c(t): texts.append(t)
        with patch("alerts.telegram.send_message", side_effect=c):
            run(tg.send_signal("TCS.NS", "BUY", 3450.0))
        assert "TCS" in texts[0]
        assert "3,450" in texts[0] or "3450" in texts[0]
