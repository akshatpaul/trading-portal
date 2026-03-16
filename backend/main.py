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
from api.routes import router, health_router
from api.websocket import websocket_endpoint

# Auth router — no authentication required (login endpoint lives here)
app.include_router(auth_router)

# Main API router — all routes protected by JWT
app.include_router(router, dependencies=[Depends(verify_token)])

# Health router — unprotected (monitoring / load balancer checks)
app.include_router(health_router)


@app.websocket("/ws")
async def websocket_route(ws: WebSocket):
    await websocket_endpoint(ws)


# ── Lifecycle ─────────────────────────────────

@app.on_event("startup")
async def on_startup():
    """Initialise DB, start scheduler, send online alert."""
    from database.db import init_db
    from utils.scheduler import start as scheduler_start

    init_db()
    log.info("Database initialised")

    scheduler_start()
    log.info("Scheduler started")

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


