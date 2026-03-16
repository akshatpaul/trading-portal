# Trading Portal

Personal algorithmic trading system for Indian stock markets (Nifty 50).

**Live at:** https://alt.akshatpaul.com

---

## Overview

- **Paper trading** by default — safe simulation with real market prices via yfinance
- **Live trading** via Zerodha Kite Connect (explicit opt-in, confirmation required)
- **Market data** — yfinance (free, no account needed); Kite Connect when configured
- **Strategy** — EMA 9/21 crossover + volume confirmation on 5-min candles
- **Alerts** — Telegram bot notifications for signals, trades, daily summary
- **UI** — React + TailwindCSS dark-theme dashboard with TradingView charts
- **Auth** — JWT login (single user, credentials in `.env`)
- **Deployed** — AWS EC2 (ap-south-1) + Cloudflare SSL + nginx

---

## Quick Start (Local Development)

```bash
# 1. Enter the project
cd trading-portal

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env — set TRADING_USERNAME, TRADING_PASSWORD_HASH, JWT_SECRET at minimum

# 3. Start everything
chmod +x run.sh
./run.sh
```

- Backend API: http://localhost:8000
- Frontend:    http://localhost:5173
- API docs:    http://localhost:8000/docs

---

## Strategy — EMA 9/21 Crossover

### Pre-market Screener (8:45 AM IST)
Scans all Nifty 50 stocks and filters by:

| Filter | Condition |
|--------|-----------|
| Price | ₹200 – ₹3,000 |
| Avg daily volume | > 5 lakh shares |
| ATR% | > 0.5% of price (needs volatility) |
| ADX | > 20 (trending, not sideways) |

Top 3 stocks by composite score (ATR + ADX + Volume) become the **daily watchlist**.

### Entry (9:30 AM – 2:30 PM IST)
All three must be true on the same 5-min candle:
- EMA 9 crosses above EMA 21 (bullish momentum)
- Volume ratio > 1.5× 20-bar average
- ADX > 20

### Exit
| Condition | Action |
|-----------|--------|
| Price +0.6% from entry | Target hit |
| Price −0.3% from entry | Stop loss |
| 3:10 PM IST | Force close (end of day) |

---

## Build Status

| Step | Component | Status |
|------|-----------|--------|
| 1  | Project structure + config | ✅ |
| 2  | Database (SQLite + models) | ✅ |
| 3  | Cost calculator (STT, brokerage, GST) | ✅ |
| 4  | yfinance data client | ✅ |
| 5  | Technical indicators (EMA, ATR, ADX, volume ratio) | ✅ |
| 6  | Stock screener (Nifty 50 pre-market scan) | ✅ |
| 7  | Signal engine (entry + exit logic) | ✅ |
| 8  | Risk manager (daily loss limits, position sizing) | ✅ |
| 9  | Paper trading engine | ✅ |
| 10 | Telegram alerts | ✅ |
| 11 | Kite Connect client (live trading) | ✅ |
| 12 | FastAPI backend (492 pytest tests passing) | ✅ |
| 13 | React frontend (dark theme, TradingView charts) | ✅ |
| 14 | smoke_test.sh (full-stack validation) | ✅ |
| 15 | Playwright E2E tests (40 browser tests) | ✅ |
| 16 | JWT authentication (login page, protected routes) | ✅ |
| 17 | AWS EC2 deployment (ap-south-1, Ubuntu 22.04) | ✅ |
| 18 | Cloudflare SSL (alt.akshatpaul.com) | ✅ |
| 19 | Telegram notifications (live on EC2) | ✅ |
| 20 | EC2 auto start/stop (Mon–Fri trading hours only) | ✅ |
| 21 | Strategies page (multi-strategy UI foundation) | ✅ |

---

## Safety Rules

- Always starts in **PAPER mode** — live mode requires typing confirmation
- Safety limits are **hardcoded** in `risk_manager.py` — UI cannot override
- `KITE_ACCESS_TOKEN` missing → runs in data-only mode, no crash
- All times in **IST (Asia/Kolkata)**
- `.env` is excluded from rsync and git — credentials never leave the server

---

## Environment Variables

See `.env.example` for all required variables. Key ones:

```bash
TRADING_USERNAME=admin
TRADING_PASSWORD_HASH=<bcrypt hash>   # generate with venv python + bcrypt
JWT_SECRET=<random hex>               # generate with secrets.token_hex(32)
TELEGRAM_BOT_TOKEN=<bot token>
TELEGRAM_CHAT_ID=<your chat id>
KITE_API_KEY=<zerodha key>            # optional — needed for live trading only
KITE_API_SECRET=<zerodha secret>      # optional
```

Generate password hash:
```bash
/opt/trading-portal/venv/bin/python3.12 -c \
  "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

---

## Deployment

See `infra/README.md` for full step-by-step AWS deployment guide.

Quick deploy after any code change:
```bash
./infra/deploy.sh 52.66.125.241 ~/.ssh/trading-key.pem
```

### Architecture

```
Browser → Cloudflare (SSL) → EC2:80 (nginx)
                                  ├── /          → frontend/dist (React)
                                  ├── /api/      → localhost:8000 (FastAPI)
                                  ├── /health    → localhost:8000 (unauthenticated)
                                  └── /ws        → localhost:8000 (WebSocket)
```

### EC2 Auto Start/Stop (EventBridge Scheduler)
- **Start:** 8:30 AM IST Mon–Fri (3:00 AM UTC)
- **Stop:**  4:15 PM IST Mon–Fri (10:45 AM UTC)

---

## Tech Stack

**Backend:** Python 3.12, FastAPI, uvicorn, yfinance, pandas-ta, kiteconnect, SQLite, APScheduler, python-jose, bcrypt, httpx

**Frontend:** React 18, Vite, TailwindCSS, TradingView Lightweight Charts, Recharts, React Query, Axios

**Infra:** AWS EC2 t3.small (ap-south-1), nginx, systemd, Cloudflare, EventBridge Scheduler
