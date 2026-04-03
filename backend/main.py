"""
main.py — FastAPI application entry point

Startup sequence:
  1. Load config / validate .env
  2. Initialise database
  3. Start scheduler (screener, data refresh, signal check)
  4. Mount API routes
  5. Mount WebSocket endpoint
  6. Send Telegram "system online" alert
"""

import logging

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logger import setup_logging

setup_logging()
log = logging.getLogger(__name__)

app = FastAPI(
    title="Trading Portal",
    description="Personal algorithmic trading system for Indian stock markets",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────
from api.auth import router as auth_router, verify_token
from api.routes import router, health_router, kite_public_router
from api.websocket import websocket_endpoint

# Auth router — no authentication required (login endpoint lives here)
app.include_router(auth_router)

# Main API router — all routes protected by JWT
app.include_router(router, dependencies=[Depends(verify_token)])

# Health router — unprotected (monitoring / load balancer checks)
app.include_router(health_router)

# Kite OAuth callback — unprotected (Zerodha redirects here, no JWT available)
app.include_router(kite_public_router)


@app.websocket("/ws")
async def websocket_route(ws: WebSocket):
    await websocket_endpoint(ws)


# ── Lifecycle ─────────────────────────────────

def _stop_ec2() -> None:
    """Shut down the OS — on EBS-backed EC2 this stops the instance."""
    import subprocess
    subprocess.Popen(["sudo", "shutdown", "-h", "+1"])
    log.info("OS shutdown scheduled in 1 minute")


@app.on_event("startup")
async def on_startup():
    """Initialise DB, start scheduler, send online alert."""
    from utils.helpers import is_trading_day, today_ist, now_ist

    # ── Holiday guard — shut down EC2 if today is not a trading day ──
    if not is_trading_day():
        date_str = today_ist().strftime("%a %d %b %Y")
        log.info("Market holiday today (%s) — shutting down EC2", date_str)
        try:
            from alerts.telegram import send_holiday_shutdown
            await send_holiday_shutdown(date_str)
        except Exception as exc:
            log.debug("Holiday alert skipped: %s", exc)
        _stop_ec2()
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)
        return

    from database.db import init_db
    from utils.scheduler import start as scheduler_start

    init_db()
    log.info("Database initialised")

    scheduler_start()
    log.info("Scheduler started")

    # If the screener was missed (server started after 8:45 AM), run it now
    from datetime import time as _time
    _now = now_ist()
    if is_trading_day(_now.date()) and _now.time() >= _time(8, 45):
        from database import queries as _q
        if not _q.get_watchlist(today_ist().isoformat()):
            log.info("No watchlist for today — running screener on startup")
            import asyncio
            from utils.scheduler import job_run_screener
            from alerts.telegram import send_screener_recovered

            async def _recover():
                from strategy.screener import run_screener
                symbols = run_screener()
                if symbols:
                    await send_screener_recovered(symbols)

            asyncio.ensure_future(_recover())

    mode = settings.app_mode.upper()
    log.info("Trading Portal starting in %s mode", mode)

    if not settings.kite_configured:
        log.warning(
            "Kite credentials missing — running in data-only mode. "
            "Login URL: https://kite.zerodha.com/connect/login?api_key=%s",
            settings.kite_api_key or "<not set>",
        )

    # Telegram alert (fire-and-forget)
    import asyncio
    try:
        from alerts.telegram import send_system_online
        asyncio.ensure_future(send_system_online())
    except Exception as exc:
        log.debug("Startup alert skipped: %s", exc)


@app.on_event("shutdown")
async def on_shutdown():
    """Stop scheduler, send offline alert."""
    from utils.scheduler import stop as scheduler_stop
    scheduler_stop()

    import asyncio
    try:
        from alerts.telegram import send_system_offline
        await send_system_offline()
    except Exception as exc:
        log.debug("Shutdown alert skipped: %s", exc)

    log.info("Trading Portal shut down")


