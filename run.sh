#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Trading Portal — Single command startup
# Usage: ./run.sh
# ─────────────────────────────────────────────

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$ROOT/venv"

GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

log()  { echo -e "${GREEN}[run.sh]${RESET} $1"; }
warn() { echo -e "${AMBER}[run.sh]${RESET} $1"; }
err()  { echo -e "${RED}[run.sh]${RESET} $1"; }

# ── 1. Validate .env ──────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  warn ".env not found — copying from .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn "Please fill in .env before running live/Telegram features"
fi

# ── 2. Python virtual environment ─────────────
if [ ! -d "$VENV_DIR" ]; then
  log "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

log "Activating virtual environment..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 3. Python dependencies ────────────────────
log "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet pandas-ta --no-deps   # numba incompatible with Python 3.14
pip install --quiet -r "$BACKEND_DIR/requirements.txt"

# ── 4. Node dependencies ──────────────────────
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  log "Installing Node dependencies..."
  cd "$FRONTEND_DIR" && npm install --silent
  cd "$ROOT"
else
  log "Node modules already installed — skipping"
fi

# ── 5. Start backend ──────────────────────────
log "Starting FastAPI backend on http://localhost:8000 ..."
cd "$BACKEND_DIR"
uvicorn main:app --host localhost --port 8000 --reload &
BACKEND_PID=$!
cd "$ROOT"

# ── 6. Start frontend ─────────────────────────
log "Starting React frontend on http://localhost:5173 ..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

# ── 7. Open browser ───────────────────────────
sleep 3
log "Opening browser..."
open "http://localhost:5173" 2>/dev/null || true

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  Trading Portal is running${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  Frontend : http://localhost:5173"
echo -e "  Backend  : http://localhost:8000"
echo -e "  API Docs : http://localhost:8000/docs"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${AMBER}  Mode: PAPER TRADING (15-min delayed data)${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "Press Ctrl+C to stop all services"

# ── 8. Cleanup on exit ────────────────────────
cleanup() {
  echo ""
  log "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  log "Done. Goodbye."
}
trap cleanup SIGINT SIGTERM

wait
