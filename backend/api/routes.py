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
  GET  /api/market-ticker       — Sensex, Gold 24k/10g, GoldBees live prices
  POST /api/mode/live           — switch to live mode (needs confirmation)
  POST /api/mode/paper          — switch back to paper
  POST /api/emergency-stop      — close all positions, pause bot
  GET  /api/kite/login-url      — Kite Connect auth URL
  GET  /api/kite/callback       — handle Kite OAuth callback
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config import settings
from database import queries
from utils.helpers import is_market_open, is_trading_day, now_ist

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
health_router = APIRouter()
kite_public_router = APIRouter(prefix="/api")


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

    from execution.live_trader import kite_ready
    return {
        "mode":                mode,
        "capital":             round(capital, 2),
        "market_open":         is_market_open(dt),
        "trading_day":         is_trading_day(dt.date()),
        "kite_configured":     kite_ready(),
        "kite_api_key_set":    bool(settings.kite_api_key),
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


@router.post("/screener/run")
async def trigger_screener():
    """Manually trigger the pre-market screener to populate today's watchlist."""
    from utils.scheduler import job_run_screener
    from utils.helpers import today_ist
    await job_run_screener()
    rows = queries.get_watchlist(today_ist().isoformat())
    return {"triggered": True, "symbols": [r["symbol"] for r in rows], "watchlist": rows}


# ─────────────────────────────────────────────
# Positions
# ─────────────────────────────────────────────

@router.get("/positions")
async def get_positions():
    """
    All currently open positions with live P&L estimates.
    Returns positions=[] when flat.
    """
    from execution.paper_trader import get_open_paper_positions
    from data.yfinance_client import get_latest_price

    open_positions = get_open_paper_positions()
    enriched = []
    for pos in open_positions:
        ltp = get_latest_price(pos["symbol"])
        unrealised_pnl = round((ltp - float(pos["entry_price"])) * pos["quantity"], 2) if ltp else None
        enriched.append({**pos, "ltp": ltp, "unrealised_pnl": unrealised_pnl})

    return {"positions": enriched}


# ─────────────────────────────────────────────
# Activity Log
# ─────────────────────────────────────────────

@router.get("/activity")
async def get_activity(
    limit: int = Query(default=200, ge=1, le=500),
    date:  Optional[str] = Query(default=None, description="YYYY-MM-DD filter"),
):
    """Chronological activity log — screener, signals, trades, risk blocks."""
    entries = queries.get_activity_log(limit=limit, date_str=date)
    return {"activity": entries}


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


@router.get("/capital-stats")
async def get_capital_stats():
    """
    Capital metadata: starting capital, floor, total return, monthly P&L,
    last trade time, and when capital was last auto-reset.
    """
    from execution.paper_trader import get_capital_stats
    return get_capital_stats()


@router.post("/capital/reset")
async def reset_paper_capital():
    """
    Reset paper capital to the default starting amount.
    Blocked if any position is currently open.
    """
    from execution.paper_trader import get_open_paper_positions, _DEFAULT_CAPITAL, _CAPITAL_KEY, _CAPITAL_RESET_KEY
    from database.queries import log_activity

    open_positions = get_open_paper_positions()
    if open_positions:
        raise HTTPException(
            status_code=409,
            detail="Cannot reset capital while positions are open. Close them first.",
        )

    queries.set_setting(_CAPITAL_KEY, str(_DEFAULT_CAPITAL))
    queries.set_setting(_CAPITAL_RESET_KEY, now_ist().isoformat())
    log_activity("system", f"Paper capital manually reset to ₹{_DEFAULT_CAPITAL:,.0f}")
    log.info("Paper capital reset to ₹%.0f", _DEFAULT_CAPITAL)
    return {"capital": _DEFAULT_CAPITAL, "message": f"Paper capital reset to ₹{_DEFAULT_CAPITAL:,.0f}"}


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


@router.get("/market-ticker")
async def market_ticker():
    """
    Live market ticker using yfinance fast_info (avoids history API stale-data issues):
      - Sensex (^BSESN): last_price + previous_close for accurate intraday change
      - Gold 24k per 10g INR: GOLDIETF.NS × 10 (1 unit ≈ 1g, domestic price incl. duty/GST)
      - GOLDIETF (GOLDIETF.NS): ICICI Prudential Gold ETF per unit
    """
    import yfinance as yf

    def _stats(sym: str, price_scale: float = 1.0) -> dict | None:
        """
        Use fast_info to get last_price and previous_close directly.
        This avoids the history() API returning stale previous-session data
        for indices like ^BSESN that don't have reliable 5-min intraday on yfinance.
        Falls back to history-based approach if fast_info is unavailable.
        """
        try:
            fi = yf.Ticker(sym).fast_info
            price      = fi.last_price
            prev_close = fi.previous_close
            if price is not None and prev_close is not None:
                change = (price - prev_close) * price_scale
                pct    = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
                return {
                    "price":  round(price * price_scale, 2),
                    "change": round(change, 2),
                    "pct":    round(pct, 2),
                }
        except Exception as exc:
            log.warning("market_ticker fast_info(%s): %s — falling back to history", sym, exc)

        # Fallback: use daily history, compare latest vs completed prev day
        try:
            from data.yfinance_client import get_daily_candles
            from utils.helpers import today_ist
            import pandas as pd
            today = today_ist()
            df = get_daily_candles(sym, period="5d")
            if df.empty:
                return None
            completed = df[pd.DatetimeIndex(df.index).date < today]
            if completed.empty or len(df) < 2:
                return None
            current    = float(df["close"].iloc[-1])
            prev_close = float(completed["close"].iloc[-1])
            change     = (current - prev_close) * price_scale
            pct        = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
            return {
                "price":  round(current * price_scale, 2),
                "change": round(change, 2),
                "pct":    round(pct, 2),
            }
        except Exception as exc:
            log.warning("market_ticker history fallback(%s): %s", sym, exc)
            return None

    sensex   = _stats("^BSESN")
    gold_10g = _stats("GOLDIETF.NS", price_scale=10)  # 1 unit ≈ 1g → ×10 = per 10g
    goldietf = _stats("GOLDIETF.NS")

    return {"sensex": sensex, "gold_24k_per_10g": gold_10g, "goldietf": goldietf}


@router.get("/risk-limits")
async def get_risk_limits():
    """Return hardcoded safety limits (read-only — UI display only)."""
    from strategy.risk_manager import get_limits
    return get_limits()


# ─────────────────────────────────────────────
# Journal
# ─────────────────────────────────────────────

@router.get("/journal")
async def get_journal(days: int = Query(default=90, ge=1, le=365)):
    """List of trading days with daily P&L summary for the journal view."""
    return {"days": queries.get_journal_days(days)}


@router.get("/journal/{date_str}")
async def get_journal_day(date_str: str):
    """Full detail for one trading day: summary, watchlist, trades with strategy."""
    summary  = queries.get_daily_summary(date_str)
    watchlist = queries.get_watchlist(date_str)
    trades   = queries.get_journal_day_trades(date_str)
    strategies_used = sorted({t["strategy"] for t in trades if t.get("strategy")})
    return {
        "date":             date_str,
        "summary":          summary,
        "watchlist":        watchlist,
        "trades":           trades,
        "strategies_used":  strategies_used,
    }


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
    from execution.live_trader import kite_ready
    if not kite_ready():
        raise HTTPException(
            status_code=400,
            detail="Kite Connect not ready — set KITE_API_KEY/KITE_API_SECRET in .env and log in via Settings"
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
# Strategy switching
# ─────────────────────────────────────────────

@router.get("/strategy")
async def get_strategy():
    """Return active strategy, valid strategies, and whether switching is locked today."""
    from strategy.signals import VALID_STRATEGIES
    from execution.paper_trader import get_open_paper_position

    mode         = _current_mode()
    active       = queries.get_setting("active_strategy", "orb") or "orb"
    trades_today = queries.get_trades_count_today(mode)
    open_pos     = get_open_paper_position()
    locked       = trades_today > 0 or open_pos is not None
    lock_reason  = (
        "trade fired today" if trades_today > 0
        else "position open" if open_pos
        else None
    )
    from strategy.signals import get_disabled_strategies
    return {
        "active_strategy":    active,
        "valid_strategies":   VALID_STRATEGIES,
        "disabled_strategies": get_disabled_strategies(),
        "locked":             locked,
        "lock_reason":        lock_reason,
    }


@router.post("/strategy/{name}")
async def set_strategy(name: str):
    """
    Switch active strategy.
    Blocked if any trade has fired today OR a position is currently open.
    Lock resets at midnight (trades query filters by today's date).
    """
    from strategy.signals import VALID_STRATEGIES
    from execution.paper_trader import get_open_paper_position

    if name not in VALID_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{name}'. Valid: {VALID_STRATEGIES}",
        )

    mode         = _current_mode()
    trades_today = queries.get_trades_count_today(mode)
    if trades_today > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot switch strategy: a trade has already fired today. Lock resets at midnight.",
        )

    open_pos = get_open_paper_position()
    if open_pos:
        raise HTTPException(
            status_code=409,
            detail="Cannot switch strategy: a position is currently open.",
        )

    queries.set_setting("active_strategy", name)
    log.info("Strategy switched to: %s", name)
    return {"active_strategy": name, "message": f"Strategy set to {name}."}


@router.post("/strategy/{name}/toggle")
async def toggle_strategy(name: str):
    """Enable or disable a strategy in parallel execution."""
    from strategy.signals import VALID_STRATEGIES, get_disabled_strategies

    if name not in VALID_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Unknown strategy '{name}'.")

    disabled = get_disabled_strategies()
    if name in disabled:
        disabled.remove(name)
        action = "enabled"
    else:
        disabled.append(name)
        action = "disabled"

    queries.set_setting("disabled_strategies", ",".join(disabled))
    log.info("Strategy %s: %s", name, action)
    return {"strategy": name, "action": action, "disabled_strategies": disabled}


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

@router.get("/kite/profile")
async def kite_profile():
    """Kite user profile — name, email, exchanges, products."""
    from execution.live_trader import kite_ready, get_kite_profile
    if not kite_ready():
        raise HTTPException(status_code=400, detail="Kite not connected")
    profile = get_kite_profile()
    if not profile:
        raise HTTPException(status_code=502, detail="Failed to fetch profile from Kite")
    return profile


@router.get("/kite/funds")
async def kite_funds():
    """Available funds and margins from Zerodha."""
    from execution.live_trader import kite_ready, _get_kite
    if not kite_ready():
        raise HTTPException(status_code=400, detail="Kite not connected")
    try:
        kite = _get_kite()
        return kite.margins()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/kite/holdings")
async def kite_holdings():
    """Long-term portfolio holdings from Zerodha demat account."""
    from execution.live_trader import kite_ready, _get_kite
    if not kite_ready():
        raise HTTPException(status_code=400, detail="Kite not connected")
    try:
        kite = _get_kite()
        return {"holdings": kite.holdings()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/kite/mf-holdings")
async def kite_mf_holdings():
    """Mutual fund holdings from Zerodha."""
    from execution.live_trader import kite_ready, _get_kite
    if not kite_ready():
        raise HTTPException(status_code=400, detail="Kite not connected")
    try:
        kite = _get_kite()
        return {"mf_holdings": kite.mf_holdings()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/kite/login-url")
async def kite_login_url():
    """Return the Zerodha OAuth login URL."""
    if not settings.kite_api_key:
        raise HTTPException(
            status_code=400,
            detail="KITE_API_KEY not set in backend .env"
        )
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=settings.kite_api_key)
    return {"url": kite.login_url()}


@kite_public_router.get("/kite/callback")
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
        log.info("Kite access token set for session — user: %s", data.get("user_name", ""))
        return RedirectResponse(url="/settings?kite=success")
    except Exception as exc:
        log.error("Kite callback failed: %s", exc)
        return RedirectResponse(url=f"/settings?kite=error&detail={exc}")
