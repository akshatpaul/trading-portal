"""
api/routes.py — All FastAPI REST endpoints

Endpoints:
  GET  /api/status              — system status, mode, capital
  GET  /api/watchlist           — today's screener results
  GET  /api/positions           — open position(s)
  GET  /api/trades              — trade log (paginated)
  GET  /api/daily-summary       — today's P&L summary
  GET  /api/candles/{symbol}    — OHLCV data for chart
  GET  /api/performance         — aggregate stats
  GET  /api/risk-limits         — hardcoded safety limits
  POST /api/mode/live           — switch to live mode (needs confirmation)
  POST /api/mode/paper          — switch back to paper
  POST /api/emergency-stop      — close all positions, pause bot
  GET  /api/kite/login-url      — Kite Connect auth URL
  GET  /api/kite/callback       — handle Kite OAuth callback
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from database import queries
from utils.helpers import is_market_open, is_trading_day, now_ist

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
health_router = APIRouter()


@health_router.get("/health")
async def health():
    return {
        "status":               "ok",
        "mode":                 settings.app_mode,
        "kite_configured":      settings.kite_configured,
        "telegram_configured":  settings.telegram_configured,
    }

_LIVE_CONFIRMATION = "I understand this uses real money"


# ── Request/Response models ───────────────────

class LiveModeRequest(BaseModel):
    confirmation: str  # must equal _LIVE_CONFIRMATION


# ── Helpers ───────────────────────────────────

def _current_mode() -> str:
    """Read trading mode from DB (overrides .env at runtime)."""
    return queries.get_setting("trading_mode", settings.app_mode)


def _set_mode(mode: str) -> None:
    queries.set_setting("trading_mode", mode)


# ─────────────────────────────────────────────
# System status
# ─────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """
    System status snapshot:
      mode, capital, market state, daily P&L, risk gate status.
    """
    from execution.paper_trader import get_paper_capital, get_daily_paper_summary
    from strategy.risk_manager import can_place_trade

    mode    = _current_mode()
    capital = get_paper_capital()
    dt      = now_ist()
    summary = get_daily_paper_summary()

    allowed, block_reason = can_place_trade(
        daily_loss   = abs(min(summary["final_pnl"], 0.0)),
        trades_today = summary["trades_count"],
        capital      = capital,
    )

    return {
        "mode":                mode,
        "capital":             round(capital, 2),
        "market_open":         is_market_open(dt),
        "trading_day":         is_trading_day(dt.date()),
        "kite_configured":     settings.kite_configured,
        "telegram_configured": settings.telegram_configured,
        "trading_allowed":     allowed,
        "block_reason":        block_reason,
        "today": {
            "trades":    summary["trades_count"],
            "wins":      summary["wins"],
            "losses":    summary["losses"],
            "final_pnl": summary["final_pnl"],
            "win_rate":  summary["win_rate"],
        },
    }


# ─────────────────────────────────────────────
# Watchlist
# ─────────────────────────────────────────────

@router.get("/watchlist")
async def get_watchlist():
    """Today's pre-market selected stocks with scores."""
    from utils.helpers import today_ist
    date_str = today_ist().isoformat()
    rows = queries.get_watchlist(date_str)
    return {"date": date_str, "watchlist": rows}


# ─────────────────────────────────────────────
# Positions
# ─────────────────────────────────────────────

@router.get("/positions")
async def get_positions():
    """
    Currently open position with live P&L estimate.
    Returns position=None when flat.
    """
    from execution.paper_trader import get_open_paper_position
    from data.yfinance_client import get_latest_price

    pos = get_open_paper_position()
    if pos is None:
        return {"position": None}

    symbol     = pos["symbol"]
    entry_fill = float(pos["entry_price"])
    qty        = pos["quantity"]

    ltp = get_latest_price(symbol)
    unrealised_pnl = round((ltp - entry_fill) * qty, 2) if ltp else None

    return {
        "position": {
            **pos,
            "ltp":             ltp,
            "unrealised_pnl":  unrealised_pnl,
        }
    }


# ─────────────────────────────────────────────
# Trades
# ─────────────────────────────────────────────

@router.get("/trades")
async def get_trades(
    limit: int = Query(default=50, ge=1, le=200),
    mode:  Optional[str] = Query(default=None),
):
    """Paginated trade log, newest first."""
    trades = queries.get_trades(limit=limit, mode=mode)
    return {"trades": trades, "count": len(trades)}


@router.get("/daily-summary")
async def get_daily_summary():
    """Today's P&L summary (trades, costs, net, final)."""
    from execution.paper_trader import get_daily_paper_summary
    return get_daily_paper_summary()


# ─────────────────────────────────────────────
# Candles
# ─────────────────────────────────────────────

@router.get("/candles/{symbol}")
async def get_candles(
    symbol:   str,
    interval: str = Query(default="5m"),
    limit:    int = Query(default=200, ge=1, le=500),
):
    """
    OHLCV candles for the TradingView Lightweight Chart.
    Returns newest `limit` candles, oldest first.
    """
    candles = queries.get_candles(symbol, "5m", limit=10_000)
    if not candles:
        # Not in DB yet — fetch live from yfinance and cache
        try:
            from data.historical import fetch_and_cache
            fetch_and_cache(symbol, period="5d")
            candles = queries.get_candles(symbol, "5m", limit=10_000)
        except Exception as exc:
            log.warning("on-demand fetch failed for %s: %s", symbol, exc)

    # Resample to requested interval if not 5m
    if interval != "5m" and candles:
        try:
            import pandas as pd
            df = pd.DataFrame(candles)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()
            rule = "15min" if interval == "15m" else "1D"
            df = df.resample(rule).agg({
                "open": "first", "high": "max",
                "low": "min", "close": "last", "volume": "sum",
            }).dropna()
            candles = [
                {**row, "timestamp": str(ts)}
                for ts, row in df.iterrows()
            ]
        except Exception as exc:
            log.warning("resample failed for %s %s: %s", symbol, interval, exc)

    return {"symbol": symbol, "interval": interval, "candles": candles[-limit:]}


# ─────────────────────────────────────────────
# Performance
# ─────────────────────────────────────────────

@router.get("/performance")
async def get_performance():
    """Aggregate performance stats + personal bests."""
    return queries.get_performance_stats()


@router.get("/risk-limits")
async def get_risk_limits():
    """Return hardcoded safety limits (read-only — UI display only)."""
    from strategy.risk_manager import get_limits
    return get_limits()


# ─────────────────────────────────────────────
# Mode switching
# ─────────────────────────────────────────────

@router.post("/mode/live")
async def switch_to_live(body: LiveModeRequest):
    """
    Switch to live trading.
    Requires exact typed confirmation and valid Kite credentials.
    """
    if body.confirmation != _LIVE_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation text does not match. Required: '{_LIVE_CONFIRMATION}'"
        )
    if not settings.kite_configured:
        raise HTTPException(
            status_code=400,
            detail="Kite Connect not configured — set KITE_API_KEY and KITE_ACCESS_TOKEN in .env"
        )
    _set_mode("live")
    log.warning("Switched to LIVE trading mode")
    return {"mode": "live", "message": "Now trading with real money. Stay disciplined."}


@router.post("/mode/paper")
async def switch_to_paper():
    """Switch back to paper (simulation) trading."""
    _set_mode("paper")
    log.info("Switched to PAPER trading mode")
    return {"mode": "paper", "message": "Back to paper trading."}


# ─────────────────────────────────────────────
# Emergency stop
# ─────────────────────────────────────────────

@router.post("/emergency-stop")
async def emergency_stop():
    """
    Force-close all open positions and pause automated trading.
    Records a bot_paused flag in app_settings.
    """
    from execution.paper_trader import get_open_paper_position, close_paper_position
    from data.yfinance_client import get_latest_price

    closed = []
    pos = get_open_paper_position()
    if pos:
        symbol = pos["symbol"]
        ltp    = get_latest_price(symbol) or float(pos["entry_price"])
        result = close_paper_position(pos["id"], ltp, "MANUAL")
        closed.append(result)

    queries.set_setting("bot_paused", "1")
    log.warning("Emergency stop triggered — bot paused")

    return {
        "stopped":           True,
        "positions_closed":  len(closed),
        "message":           "Bot paused. Clear 'bot_paused' setting to resume.",
    }


# ─────────────────────────────────────────────
# Kite Connect auth
# ─────────────────────────────────────────────

@router.get("/kite/login-url")
async def kite_login_url():
    """Return the Zerodha OAuth login URL."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=settings.kite_api_key)
    return {"url": kite.login_url()}


@router.get("/kite/callback")
async def kite_callback(request_token: str = Query(...)):
    """
    Handle Kite Connect OAuth callback.
    Exchanges request_token for access_token and persists it to DB.
    """
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=settings.kite_api_key)
        data = kite.generate_session(
            request_token,
            api_secret=settings.kite_api_secret,
        )
        access_token = data["access_token"]
        queries.set_setting("kite_access_token_session", access_token)
        log.info("Kite access token set for session")
        return {"access_token_set": True, "user": data.get("user_name", "")}
    except Exception as exc:
        log.error("Kite callback failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
