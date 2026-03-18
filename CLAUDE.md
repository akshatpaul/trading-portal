# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Trading Portal is a personal algorithmic trading system for Indian stock markets (Nifty 50). It runs paper trading by default with optional live trading via Zerodha Kite Connect, real market data via yfinance (15-min delayed), and a React dashboard with JWT authentication.

## Development Commands

### Starting the App

```bash
./run.sh          # Starts both backend (:8000) and frontend (:5173), handles venv + deps
```

Or start separately:
```bash
# Backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

### Frontend Scripts

```bash
cd frontend
npm run dev           # Vite dev server on :5173
npm run build         # Production build
npm run preview       # Preview production build
npm run test:e2e      # Playwright E2E tests (40 tests)
npm run test:e2e:ui   # Interactive Playwright test runner
```

### Backend Tests

```bash
cd backend
source venv/bin/activate
pytest                        # Run all tests (492 passing)
pytest tests/test_screener.py # Run single test file
```

### Smoke Test

```bash
./smoke_test.sh    # Full-stack validation (requires both servers running)
```

## Architecture

### Tech Stack

- **Backend**: FastAPI + Uvicorn, SQLite (no ORM, plain SQL), APScheduler, yfinance, pandas-ta
- **Frontend**: React 18 + Vite, TailwindCSS, TanStack React Query, TradingView Lightweight Charts
- **Auth**: JWT (PyJWT + bcrypt), single-user credentials in `.env`
- **Live Trading**: Zerodha Kite Connect (opt-in only)
- **Alerts**: python-telegram-bot

### Request Flow

```
Browser (:5173)
  └── Vite proxy → FastAPI (:8000)
        ├── /api/* → api/routes.py (13 REST endpoints)
        ├── /api/auth/* → api/auth.py (JWT login)
        └── /ws → api/websocket.py (real-time updates)
```

In development, Vite proxies `/api` and `/ws` to `localhost:8000`. In production, nginx handles this.

### Frontend State

- **React Query** (`AppContext.jsx`): Server state with polling — `status` (15s), `positions` (5s), `trades` (30s), `watchlist` (60s)
- **React Context** (`AppContext.jsx`): Wraps queries, exposes state + refetch fns to all pages
- **WebSocket** (`useWebSocket.js`): Receives `candle_update`, `position_update`, `signal`, `trade_complete` events → invalidates React Query caches
- **Zustand** (`tradingStore.js`): Exists but not fully integrated (TODO)

### Background Scheduler (APScheduler, Mon–Fri only)

| Time (IST) | Job |
|------------|-----|
| 08:45 AM | `run_screener()` — select top 3 Nifty 50 stocks |
| 09:15–15:10 every 5min | `refresh_candles()` + `check_signals()` |
| 15:10 PM | `force_close_all()` |
| 15:45 PM | `send_daily_summary()` |
| 02:00 AM daily | `purge_activity()` |

### Trading Strategy

**Entry** (all must be true on the same 5-min candle):
1. EMA 9 crosses above EMA 21
2. Volume ratio > 1.5× 20-bar average
3. ADX > 20
4. Time between 9:30 AM – 2:30 PM IST

**Exit**: Target = +0.6%, Stop loss = -0.3%, Force close at 3:10 PM IST

**Screener** (8:45 AM): Filters Nifty 50 by price range, volume, ATR, ADX → selects top 3 by composite score

**Risk limits** (hardcoded in `risk_manager.py` + `.env`): Max position ₹5,000, max 3 trades/day, max daily loss ₹300

### Database (SQLite — `trading_portal.db`)

9 tables defined in `database/models.py`, all queries in `database/queries.py`:
- `candles`, `signals`, `positions`, `trades`, `daily_summary` — core trading data
- `watchlist` — pre-market screener results
- `app_settings` — key-value store (trading_mode, bot_paused, kite_access_token_session)
- `activity_log` — chronological event log
- `achievements` — gamification badges

## Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
# Required for auth
TRADING_USERNAME=admin
TRADING_PASSWORD_HASH=   # bcrypt hash
JWT_SECRET=              # 64-char random string
SECRET_KEY=              # FastAPI secret key

# Capital & safety
STARTING_CAPITAL=10000
MAX_DAILY_LOSS=300
MAX_TRADES_PER_DAY=3
MAX_POSITION_SIZE=5000

# Optional — live trading
KITE_API_KEY=
KITE_API_SECRET=

# Optional — alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Backend loads config via Pydantic Settings in `config.py`.

## Key Files

| Path | Role |
|------|------|
| `backend/main.py` | FastAPI app entry point, startup/shutdown lifecycle |
| `backend/api/routes.py` | All 13 REST endpoints |
| `backend/api/websocket.py` | WebSocket connection manager |
| `backend/strategy/screener.py` | Pre-market stock selection |
| `backend/strategy/signals.py` | EMA crossover entry/exit signals |
| `backend/strategy/risk_manager.py` | Safety limits (hardcoded + env) |
| `backend/execution/paper_trader.py` | Paper trading simulation engine |
| `backend/execution/live_trader.py` | Kite Connect live trading |
| `backend/utils/scheduler.py` | APScheduler job definitions |
| `backend/costs/calculator.py` | Brokerage, STT, GST, stamp duty |
| `frontend/src/context/AppContext.jsx` | Global React state (React Query + WebSocket) |
| `frontend/src/api.js` | Axios client with JWT interceptors |
| `frontend/src/pages/Dashboard.jsx` | Main dashboard view |
| `frontend/vite.config.js` | Dev server + API proxy config |

## Production Deployment

- AWS EC2 (ap-south-1, Ubuntu 22.04), nginx reverse proxy, Cloudflare SSL
- Domain: alt.akshatpaul.com
- EC2 auto start/stop Mon–Fri 8:00 AM – 4:00 PM IST
