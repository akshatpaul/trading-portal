"""
utils/scheduler.py — APScheduler job definitions

Schedule (all times IST / Asia/Kolkata):
  08:45  — run_screener()         : select today's watchlist
  09:15  — watchdog_screener()    : verify watchlist, auto-recover
  09:20  — market_snapshot()      : Telegram market open stats (Nifty/Sensex/BankNifty/VIX)
  09:15–15:10 every 5 min — refresh_candles() + check_signals()
  11:00  — late_watchdog()        : last-resort check — run screener if still no watchlist at 11 AM
  15:10  — force_close_all()      : close any open position
  15:45  — send_daily_summary()   : Telegram summary

Mon–Fri only. Skips public holidays (helpers.is_trading_day).
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")
log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=IST)


def start() -> None:
    """Register all jobs and start the scheduler."""
    # Kite login reminder at 08:30 (only if API key is configured)
    scheduler.add_job(
        job_kite_login_reminder,
        CronTrigger(hour=8, minute=30, timezone=IST, day_of_week="mon-fri"),
        id="kite_login_reminder", replace_existing=True,
    )

    # Pre-market screener at 08:45
    scheduler.add_job(
        job_run_screener,
        CronTrigger(hour=8, minute=45, timezone=IST, day_of_week="mon-fri"),
        id="screener", replace_existing=True,
    )

    # Watchdog at 09:15 — verify screener ran, auto-recover + alert if not
    scheduler.add_job(
        job_watchdog_screener,
        CronTrigger(hour=9, minute=15, timezone=IST, day_of_week="mon-fri"),
        id="watchdog_screener", replace_existing=True,
    )

    # Late watchdog at 11:00 — last-resort screener if still no watchlist
    scheduler.add_job(
        job_late_watchdog,
        CronTrigger(hour=11, minute=0, timezone=IST, day_of_week="mon-fri"),
        id="late_watchdog", replace_existing=True,
    )

    # Market snapshot at 09:20 — Telegram summary of index opens
    scheduler.add_job(
        job_market_snapshot,
        CronTrigger(hour=9, minute=20, timezone=IST, day_of_week="mon-fri"),
        id="market_snapshot", replace_existing=True,
    )

    # Candle refresh every 5 min during market hours
    scheduler.add_job(
        job_refresh_candles,
        CronTrigger(
            hour="9-15", minute="*/5",
            timezone=IST, day_of_week="mon-fri",
        ),
        id="candle_refresh", replace_existing=True,
    )

    # Signal check every 5 min during market hours
    scheduler.add_job(
        job_check_signals,
        CronTrigger(
            hour="9-15", minute="*/5",
            timezone=IST, day_of_week="mon-fri",
        ),
        id="signal_check", replace_existing=True,
    )

    # Force close at 15:10
    scheduler.add_job(
        job_force_close,
        CronTrigger(hour=15, minute=10, timezone=IST, day_of_week="mon-fri"),
        id="force_close", replace_existing=True,
    )

    # Daily summary at 15:45
    scheduler.add_job(
        job_daily_summary,
        CronTrigger(hour=15, minute=45, timezone=IST, day_of_week="mon-fri"),
        id="daily_summary", replace_existing=True,
    )

    # Purge old activity logs daily at 02:00
    scheduler.add_job(
        job_purge_activity,
        CronTrigger(hour=2, minute=0, timezone=IST),
        id="purge_activity", replace_existing=True,
    )

    scheduler.start()
    log.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")


# ── Job functions ─────────────────────────────

async def job_kite_login_reminder():
    """08:30 — Send Telegram reminder with direct Kite login link."""
    from utils.helpers import is_trading_day, today_ist
    if not is_trading_day(today_ist()):
        return
    from config import settings
    if not settings.kite_api_key:
        return  # Kite not configured at all
    try:
        from alerts.telegram import send_kite_login_reminder
        login_url = f"https://kite.zerodha.com/connect/login?api_key={settings.kite_api_key}&v=3"
        await send_kite_login_reminder(login_url)
        log.info("Kite login reminder sent")
    except Exception as exc:
        log.error("job_kite_login_reminder failed: %s", exc)


async def job_run_screener():
    """08:45 — Pre-market screener: select today's watchlist."""
    from utils.helpers import is_trading_day, today_ist
    if not is_trading_day(today_ist()):
        return
    try:
        from strategy.screener import run_screener
        from database.queries import log_activity
        symbols = run_screener()
        log.info("Screener complete: %s", symbols)
        if symbols:
            log_activity("screener", f"Watchlist selected: {', '.join(symbols)}", data={"symbols": symbols})
        else:
            log_activity("screener", "Screener ran — no stocks passed filters today")
        from api.websocket import manager
        await manager.broadcast("watchlist_update", {"symbols": symbols})
    except Exception as exc:
        log.error("job_run_screener failed: %s", exc)


async def job_watchdog_screener():
    """09:15 — Verify watchlist was populated; auto-recover and alert if not."""
    from utils.helpers import is_trading_day, today_ist
    if not is_trading_day(today_ist()):
        return
    try:
        from database.queries import get_watchlist, log_activity
        from alerts.telegram import send_screener_recovered, send_screener_failed
        rows = get_watchlist(today_ist().isoformat())
        if rows:
            symbols = [r["symbol"].replace(".NS", "") for r in rows]
            log_activity("system", f"Market open — monitoring {', '.join(symbols)}")
            return
        log.warning("Watchdog: no watchlist found at 9:15 AM — screener missed, recovering")
        log_activity("system", "Watchdog: screener was missed, running now")
        from strategy.screener import run_screener
        symbols = run_screener()
        if symbols:
            log.info("Watchdog: screener recovered — %s", symbols)
            await send_screener_recovered(symbols)
            from api.websocket import manager
            await manager.broadcast("watchlist_update", {"symbols": symbols})
        else:
            log.error("Watchdog: screener ran but no stocks passed filters")
            log_activity("system", "Watchdog: screener recovered but no stocks passed filters today")
            await send_screener_failed()
    except Exception as exc:
        log.error("job_watchdog_screener failed: %s", exc)


async def job_refresh_candles():
    """Every 5 min — Fetch latest 5-min candles for watchlist symbols."""
    from utils.helpers import is_trading_day, today_ist, is_market_open, now_ist
    if not is_trading_day(today_ist()) or not is_market_open(now_ist()):
        return
    try:
        from strategy.screener import get_todays_watchlist
        from data.historical import fetch_and_cache
        for sym in get_todays_watchlist():
            fetch_and_cache(sym, period="1d")
    except Exception as exc:
        log.error("job_refresh_candles failed: %s", exc)


async def job_check_signals():
    """Every 5 min — Check entry/exit signals and act."""
    from utils.helpers import is_trading_day, today_ist, now_ist, is_entry_window
    if not is_trading_day(today_ist()):
        return
    from database import queries as q
    if q.get_setting("bot_paused") == "1":
        return

    try:
        # Last-resort recovery: if watchlist still missing, run screener now
        from strategy.screener import get_todays_watchlist
        if not get_todays_watchlist():
            from strategy.screener import run_screener
            from database.queries import log_activity
            from alerts.telegram import send_screener_recovered, send_screener_failed
            log.warning("Signal check: no watchlist — running screener now")
            log_activity("system", "Signal check: no watchlist found, running screener")
            symbols = run_screener()
            if symbols:
                await send_screener_recovered(symbols)
                from api.websocket import manager as _ws
                await _ws.broadcast("watchlist_update", {"symbols": symbols})
            else:
                await send_screener_failed()
                return  # nothing to trade

        from strategy.screener import get_todays_watchlist
        from data.historical import fetch_and_cache
        from strategy.signals import check_exit_signal_for, check_entry_signal_for, STRATEGY_PRIORITY
        from strategy.risk_manager import can_place_trade, calculate_position_size
        from execution.paper_trader import (
            get_open_paper_positions, place_paper_order,
            close_paper_position, get_paper_capital, get_daily_paper_summary,
        )
        from api.websocket import manager
        from database.queries import log_activity

        now          = now_ist()
        open_positions = get_open_paper_positions()
        open_symbols   = {p["symbol"] for p in open_positions}

        # ── EXIT: check all open positions ───────────────────────
        for pos in open_positions:
            sym      = pos["symbol"]
            entry    = float(pos["entry_price"])
            target   = float(pos["target"])
            stop     = float(pos["stop_loss"])
            strategy = pos.get("strategy") or "ema_crossover"
            df       = fetch_and_cache(sym, period="1d")
            if df.empty:
                continue
            ltp    = float(df["close"].iloc[-1])
            unreal = round((ltp - entry) * pos["quantity"], 2)
            sign   = "+" if unreal >= 0 else ""
            reason = check_exit_signal_for(df, entry, now, strategy)
            if reason:
                result = close_paper_position(pos["id"], ltp, reason)
                open_symbols.discard(sym)
                await manager.broadcast("trade_complete", result)
                log.info("Exit: %s [%s]", sym, reason)
            else:
                name = sym.replace(".NS", "")
                log_activity(
                    "signal",
                    f"Holding {name} [{strategy}] — LTP ₹{ltp:,.2f} | Target ₹{target:,.2f} | Stop ₹{stop:,.2f} | P&L {sign}₹{unreal:,.2f}",
                    symbol=sym,
                )

        # ── ENTRY: check free watchlist stocks ───────────────────
        if not is_entry_window(now):
            return

        capital = get_paper_capital()
        free_stocks = [s for s in get_todays_watchlist() if s not in open_symbols]

        for sym in free_stocks:
            # Re-check risk gate before each trade (count updates in real time)
            summary = get_daily_paper_summary()
            allowed, block_reason = can_place_trade(
                daily_loss   = abs(min(summary["final_pnl"], 0.0)),
                trades_today = summary["trades_count"],
                capital      = capital,
            )
            if not allowed:
                log_activity("risk_block", f"Trade blocked: {block_reason}")
                break

            df = fetch_and_cache(sym, period="1d")
            if df.empty:
                continue

            sig              = None
            matched_strategy = None
            for strategy_name in STRATEGY_PRIORITY:
                sig = check_entry_signal_for(df, sym, strategy_name)
                if sig:
                    matched_strategy = strategy_name
                    break

            if sig:
                qty   = calculate_position_size(capital, sig.price, sig.stop_loss)
                order = place_paper_order(sym, "BUY", qty, sig.price, sig.reason,
                                          strategy=matched_strategy)
                open_symbols.add(sym)
                await manager.broadcast("signal", sig.to_dict())
                await manager.broadcast("position_update", order)
                log.info("Entry: %s ×%d @ %.2f [%s]", sym, qty, sig.price, matched_strategy)
            else:
                log_activity("signal", f"No entry signal for {sym}", symbol=sym)

    except Exception as exc:
        log.error("job_check_signals failed: %s", exc)


async def job_late_watchdog():
    """11:00 — If still no watchlist, run screener as last resort and alert."""
    from utils.helpers import is_trading_day, today_ist
    if not is_trading_day(today_ist()):
        return
    try:
        from database.queries import get_watchlist, log_activity
        rows = get_watchlist(today_ist().isoformat())
        if rows:
            return  # all good, nothing to do
        log.warning("Late watchdog (11 AM): no watchlist found — running screener now")
        log_activity("system", "Late watchdog (11 AM): no watchlist, running screener")
        from strategy.screener import run_screener
        from alerts.telegram import send_screener_recovered, send_screener_failed
        symbols = run_screener()
        if symbols:
            log.info("Late watchdog: screener recovered — %s", symbols)
            await send_screener_recovered(symbols)
            from api.websocket import manager
            await manager.broadcast("watchlist_update", {"symbols": symbols})
        else:
            log.error("Late watchdog: screener ran but no stocks passed filters")
            log_activity("system", "Late watchdog: screener ran but no stocks passed filters")
            await send_screener_failed()
    except Exception as exc:
        log.error("job_late_watchdog failed: %s", exc)


async def job_market_snapshot():
    """09:20 — Fetch Nifty 50 / Sensex / Bank Nifty / India VIX and send Telegram snapshot."""
    from utils.helpers import is_trading_day, today_ist
    if not is_trading_day(today_ist()):
        return
    try:
        from data.yfinance_client import get_daily_candles
        from alerts.telegram import send_market_snapshot

        INDICES = [
            ("^NSEI",    "Nifty 50"),
            ("^BSESN",   "Sensex"),
            ("^NSEBANK", "Bank Nifty"),
            ("^INDIAVIX","India VIX"),
        ]

        snapshot = []
        for sym, name in INDICES:
            df = get_daily_candles(sym, period="2d")
            if df.empty or len(df) < 2:
                log.warning("market_snapshot: not enough data for %s", sym)
                continue
            prev_close = float(df["close"].iloc[-2])
            today_open = float(df["open"].iloc[-1])
            today_high = float(df["high"].iloc[-1])
            today_low  = float(df["low"].iloc[-1])
            change     = today_open - prev_close
            pct        = (change / prev_close) * 100 if prev_close else 0.0
            is_vix     = sym == "^INDIAVIX"
            snapshot.append({
                "name":   name,
                "price":  today_open,
                "change": change,
                "pct":    pct,
                "high":   None if is_vix else today_high,
                "low":    None if is_vix else today_low,
            })

        if snapshot:
            await send_market_snapshot(snapshot)
            log.info("Market snapshot sent (%d indices)", len(snapshot))
        else:
            log.warning("market_snapshot: no data fetched, skipping Telegram message")
    except Exception as exc:
        log.error("job_market_snapshot failed: %s", exc)


async def job_force_close():
    """15:10 — Force close any open position."""
    try:
        from execution.paper_trader import get_open_paper_position, close_paper_position
        from data.yfinance_client import get_latest_price
        from api.websocket import manager
        from database.queries import log_activity

        pos = get_open_paper_position()
        if pos:
            sym    = pos["symbol"]
            ltp    = get_latest_price(sym) or float(pos["entry_price"])
            result = close_paper_position(pos["id"], ltp, "FORCE_CLOSE")
            await manager.broadcast("trade_complete", result)
            log.info("Force close: %s @ %.2f", sym, ltp)
        else:
            log_activity("system", "3:10 PM — market close, no open positions")
    except Exception as exc:
        log.error("job_force_close failed: %s", exc)


async def job_daily_summary():
    """15:45 — Compute and send daily P&L summary via Telegram + WebSocket."""
    try:
        from execution.paper_trader import get_daily_paper_summary
        from alerts.telegram import send_daily_summary
        from api.websocket import manager
        from database.queries import log_activity

        summary = get_daily_paper_summary()
        await send_daily_summary(summary)
        await manager.broadcast("daily_summary", summary)
        pnl = summary.get("final_pnl", 0)
        wr  = summary.get("win_rate", 0)
        cnt = summary.get("trades_count", 0)
        log_activity(
            "daily_summary",
            f"Day complete — {cnt} trades | P&L ₹{pnl:+.2f} | WR {wr*100:.0f}%",
            data=summary,
        )
        log.info("Daily summary sent")
    except Exception as exc:
        log.error("job_daily_summary failed: %s", exc)


async def job_purge_activity():
    """02:00 daily — Delete activity log entries older than 90 days."""
    try:
        from database.queries import purge_old_activity
        deleted = purge_old_activity(days=90)
        if deleted:
            log.info("Purged %d old activity log entries", deleted)
    except Exception as exc:
        log.error("job_purge_activity failed: %s", exc)
