#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Trading Portal — Smoke Test
# Validates the full stack without real money / real APIs.
#
# Usage: ./smoke_test.sh
# Exit:  0 = all checks passed, 1 = at least one failed
# ─────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV_DIR="$ROOT/venv"
PYTEST="$VENV_DIR/bin/pytest"

GREEN='\033[0;32m'
RED='\033[0;31m'
AMBER='\033[0;33m'
BOLD='\033[1m'
RESET='\033[0m'

PASS=0
FAIL=0
BACKEND_PID=""

ok()   { echo -e "  ${GREEN}✔${RESET}  $1"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}✖${RESET}  $1"; FAIL=$((FAIL+1)); }
step() { echo -e "\n${BOLD}▶ $1${RESET}"; }

# ── Cleanup ───────────────────────────────────
cleanup() {
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# ─────────────────────────────────────────────
# STEP 1 — Check system dependencies
# ─────────────────────────────────────────────
step "1/5  Checking system dependencies"

if command -v python3 &>/dev/null; then
  ok "python3 found ($(python3 --version 2>&1))"
else
  fail "python3 not found"
fi

if command -v node &>/dev/null; then
  ok "node found ($(node --version))"
else
  fail "node not found"
fi

if command -v npm &>/dev/null; then
  ok "npm found ($(npm --version))"
else
  fail "npm not found"
fi

if [ -d "$VENV_DIR" ]; then
  ok "Python venv found at $VENV_DIR"
else
  fail "Python venv missing — run ./run.sh first to create it"
fi

if [ -d "$FRONTEND_DIR/node_modules" ]; then
  ok "Node modules found"
else
  fail "Node modules missing — run: cd frontend && npm install"
fi

if [ -f "$PYTEST" ]; then
  ok "pytest found"
else
  fail "pytest not found in venv"
fi

# ─────────────────────────────────────────────
# STEP 2 — Start backend + health check
# ─────────────────────────────────────────────
step "2/5  Starting backend + health check"

cd "$BACKEND_DIR"
PYTHONPATH="$BACKEND_DIR" "$VENV_DIR/bin/uvicorn" main:app \
  --host 127.0.0.1 --port 18765 \
  --log-level warning \
  2>/tmp/trading_smoke_backend.log &
BACKEND_PID=$!
cd "$ROOT"

echo -e "  ${AMBER}…${RESET}  Waiting for backend (up to 15s)..."
READY=0
for i in $(seq 1 15); do
  sleep 1
  if curl -sf http://127.0.0.1:18765/health >/dev/null 2>&1; then
    READY=1
    break
  fi
done

if [ "$READY" -eq 1 ]; then
  HEALTH=$(curl -s http://127.0.0.1:18765/health)
  STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "")
  if [ "$STATUS" = "ok" ]; then
    ok "Backend healthy (GET /health → status=ok)"
  else
    fail "Backend returned unexpected health response: $HEALTH"
  fi
else
  fail "Backend did not start within 15s (see /tmp/trading_smoke_backend.log)"
  cat /tmp/trading_smoke_backend.log | tail -20 || true
fi

# ─────────────────────────────────────────────
# STEP 3 — Pytest unit + integration tests
# ─────────────────────────────────────────────
step "3/5  Running pytest (unit + integration tests)"

set +e
PYTHONPATH="$BACKEND_DIR" "$PYTEST" "$BACKEND_DIR/tests/" \
  --tb=short -q 2>&1 | tail -20
PYTEST_EXIT=$?
set -e

if [ "$PYTEST_EXIT" -eq 0 ]; then
  NPASS=$(PYTHONPATH="$BACKEND_DIR" "$PYTEST" "$BACKEND_DIR/tests/" -q --no-header 2>&1 \
    | grep -E "^[0-9]+ passed" | grep -oE "^[0-9]+" || echo "?")
  ok "All pytest tests passed ($NPASS tests)"
else
  fail "pytest exited with code $PYTEST_EXIT"
fi

# ─────────────────────────────────────────────
# STEP 4 — Frontend production build
# ─────────────────────────────────────────────
step "4/5  Building frontend (Vite production build)"

set +e
cd "$FRONTEND_DIR"
npm run build --silent 2>&1 | tail -10
BUILD_EXIT=$?
cd "$ROOT"
set -e

if [ "$BUILD_EXIT" -eq 0 ]; then
  BUNDLE_SIZE=$(du -sh "$FRONTEND_DIR/dist/assets/"*.js 2>/dev/null | awk '{print $1}' | head -1 || echo "?")
  ok "Frontend build succeeded (bundle ~$BUNDLE_SIZE)"
else
  fail "Frontend build failed (exit $BUILD_EXIT)"
fi

# ─────────────────────────────────────────────
# STEP 5 — Playwright E2E tests
# ─────────────────────────────────────────────
step "5/5  Running Playwright E2E tests (headless Chromium)"

set +e
cd "$FRONTEND_DIR"
npx playwright test --reporter=line 2>&1 | tail -15
E2E_EXIT=$?
cd "$ROOT"
set -e

if [ "$E2E_EXIT" -eq 0 ]; then
  E2E_COUNT=$(cd "$FRONTEND_DIR" && npx playwright test --list 2>/dev/null | grep -c " › " || echo "?")
  ok "All Playwright E2E tests passed ($E2E_COUNT tests)"
else
  fail "Playwright E2E tests failed (exit $E2E_EXIT)"
fi

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}  ✔  All $PASS checks passed${RESET}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  exit 0
else
  echo -e "${RED}${BOLD}  ✖  $FAIL check(s) failed, $PASS passed${RESET}"
  echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  exit 1
fi
