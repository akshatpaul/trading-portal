"""
alerts/telegram.py — Telegram bot notification layer

All alert types:
  - system_online      : "🟢 Trading system online"
  - system_offline     : "⭕ System offline"
  - watchlist          : "📋 Today's watchlist: HDFC, TCS, INFY"
  - signal             : "⚡ Signal: HDFCBANK BUY @ ₹1,642"
  - trade_entry        : "📝 Paper: BUY 6 HDFCBANK @ ₹1,642.00 | target ₹1,651.85"
  - trade_exit         : routes to target/stop/force_close/manual detail
  - paper_order        : "📝 Paper: BUY 6 HDFCBANK @ ₹1,642"
  - live_order         : "✅ Live: BUY 6 HDFCBANK @ ₹1,642"
  - target_hit         : "🎯 Target: +₹340 net | HDFCBANK"
  - stop_hit           : "🛑 Stop: -₹180 net | HDFCBANK"
  - daily_limit        : "⚠️ Daily loss limit hit. Bot paused."
  - force_close        : "🔒 3:10 PM: Positions closed"
  - daily_summary      : full P&L summary at 3:45 PM
  - error              : "🔴 Error: [description]"

If Telegram not configured (no bot token/chat_id):
  - Log the message to console instead — never crash
"""

import logging

from config import settings

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Core send
# ─────────────────────────────────────────────

async def send_message(text: str) -> bool:
    """
    Send a message to the configured Telegram chat.

    Uses HTML parse mode. Trims to 4096 chars (Telegram limit).
    Returns True on success, False on any failure — never raises.
    """
    if not settings.telegram_configured:
        log.info("[telegram] (not configured) %s", text)
        return False

    try:
        from telegram import Bot
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text[:4096],
            parse_mode="HTML",
        )
        return True
    except Exception as exc:
        log.warning("telegram: send_message failed: %s", exc)
        return False


# ─────────────────────────────────────────────
# System events
# ─────────────────────────────────────────────

async def send_system_online() -> None:
    mode    = settings.app_mode.upper()
    capital = settings.starting_capital
    await send_message(
        f"🟢 <b>Trading Portal online</b>\n"
        f"Mode: <b>{mode}</b> | Capital: <b>₹{capital:,.0f}</b>"
    )


async def send_system_offline() -> None:
    await send_message("⭕ <b>Trading Portal offline</b>")


async def send_error(description: str) -> None:
    await send_message(f"🔴 <b>Error:</b> {description}")


# ─────────────────────────────────────────────
# Pre-market
# ─────────────────────────────────────────────

async def send_watchlist(symbols: list[str]) -> None:
    names = ", ".join(s.replace(".NS", "") for s in symbols)
    count = len(symbols)
    await send_message(
        f"📋 <b>Watchlist ({count} stocks)</b>\n{names}"
    )


async def send_screener_recovered(symbols: list[str]) -> None:
    """Alert when watchdog auto-recovers a missed screener."""
    names = ", ".join(s.replace(".NS", "") for s in symbols) if symbols else "none"
    await send_message(
        f"⚠️ <b>Screener was missed at 8:45 AM — auto-recovered</b>\n"
        f"Watchlist: {names}"
    )


async def send_screener_failed() -> None:
    """Alert when watchdog finds no watchlist and screener also produces nothing."""
    await send_message(
        "🔴 <b>Screener failed — no watchlist for today</b>\n"
        "No stocks passed filters. Bot will not trade today."
    )


# ─────────────────────────────────────────────
# Signals
# ─────────────────────────────────────────────

async def send_signal(symbol: str, side: str, price: float) -> None:
    name  = symbol.replace(".NS", "")
    emoji = "📈" if side == "BUY" else "📉"
    await send_message(
        f"{emoji} <b>Signal: {name} {side} @ ₹{price:,.2f}</b>"
    )


# ─────────────────────────────────────────────
# Trade lifecycle (used by paper_trader / live_trader)
# ─────────────────────────────────────────────

async def send_trade_entry(order: dict, signal_reason: str = "") -> None:
    """Alert on position open (paper or live)."""
    name   = order["symbol"].replace(".NS", "")
    mode   = order.get("mode", "paper").upper()
    side   = order["side"]
    qty    = order["quantity"]
    fill   = order["fill_price"]
    target = order.get("target", 0.0)
    stop   = order.get("stop_loss", 0.0)
    cap    = order.get("capital_remaining", 0.0)
    emoji  = "📝" if mode == "PAPER" else "✅"

    lines = [
        f"{emoji} <b>{mode}: {side} {qty}× {name} @ ₹{fill:,.2f}</b>",
        f"🎯 Target: ₹{target:,.2f}  |  🛑 Stop: ₹{stop:,.2f}",
        f"💰 Capital left: ₹{cap:,.2f}",
    ]
    if signal_reason:
        lines.append(f"<i>{signal_reason}</i>")

    await send_message("\n".join(lines))


async def send_trade_exit(trade: dict) -> None:
    """Alert on position close — routes to appropriate formatter."""
    reason  = trade.get("exit_reason", "MANUAL")
    net_pnl = trade.get("net_pnl", 0.0)
    symbol  = trade.get("symbol", "")

    if reason == "TARGET":
        await send_target_hit(symbol, net_pnl)
    elif reason == "STOP_LOSS":
        await send_stop_hit(symbol, net_pnl)
    elif reason == "FORCE_CLOSE":
        await send_force_close(symbol)
    else:
        await _send_close_detail(trade)


async def send_paper_order(symbol: str, side: str, qty: int, price: float) -> None:
    name = symbol.replace(".NS", "")
    await send_message(f"📝 <b>Paper: {side} {qty} {name} @ ₹{price:,.2f}</b>")


async def send_live_order(symbol: str, side: str, qty: int, price: float) -> None:
    name = symbol.replace(".NS", "")
    await send_message(f"✅ <b>Live: {side} {qty} {name} @ ₹{price:,.2f}</b>")


# ─────────────────────────────────────────────
# Trade outcomes
# ─────────────────────────────────────────────

async def send_target_hit(symbol: str, net_pnl: float) -> None:
    name = symbol.replace(".NS", "")
    sign = "+" if net_pnl >= 0 else ""
    await send_message(
        f"🎯 <b>Target hit: {name}</b>\n"
        f"Net P&L: <b>{sign}₹{net_pnl:,.2f}</b>"
    )


async def send_stop_hit(symbol: str, net_pnl: float) -> None:
    name = symbol.replace(".NS", "")
    await send_message(
        f"🛑 <b>Stop loss: {name}</b>\n"
        f"Net P&L: <b>₹{net_pnl:,.2f}</b>"
    )


async def send_force_close(symbol: str) -> None:
    name = symbol.replace(".NS", "")
    await send_message(
        f"🔒 <b>3:10 PM force close: {name}</b>\nAll positions squared off."
    )


async def send_daily_limit_hit() -> None:
    await send_message(
        "⚠️ <b>Daily loss limit reached</b>\n"
        "Bot paused for the day. Restart tomorrow morning."
    )


# ─────────────────────────────────────────────
# End-of-day summary
# ─────────────────────────────────────────────

async def send_daily_summary(summary: dict) -> None:
    """
    Full P&L summary message sent at 3:45 PM.

    summary keys (from get_daily_paper_summary):
        date, trades_count, wins, losses,
        gross_pnl, total_cost, net_pnl, tax_estimate, final_pnl,
        win_rate, profit_factor, capital_end
    """
    d        = summary.get("date", "")
    count    = summary.get("trades_count", 0)
    wins     = summary.get("wins", 0)
    losses   = summary.get("losses", 0)
    gross    = summary.get("gross_pnl", 0.0)
    cost     = summary.get("total_cost", 0.0)
    net      = summary.get("net_pnl", 0.0)
    tax      = summary.get("tax_estimate", 0.0)
    final    = summary.get("final_pnl", 0.0)
    win_rate = summary.get("win_rate", 0.0) * 100
    pf       = summary.get("profit_factor", 0.0)
    cap_end  = summary.get("capital_end", 0.0)

    pf_str     = f"{pf:.2f}" if pf != float("inf") else "∞"
    final_sign = "+" if final >= 0 else ""
    emoji      = "✅" if final >= 0 else "❌"

    await send_message(
        f"📊 <b>Daily Summary — {d}</b>\n"
        f"\n"
        f"Trades: {count}  |  ✅ {wins}W  ❌ {losses}L  |  Win rate: {win_rate:.0f}%\n"
        f"Profit factor: {pf_str}\n"
        f"\n"
        f"Gross P&L:   ₹{gross:>10,.2f}\n"
        f"Costs:      -₹{cost:>10,.2f}\n"
        f"Net P&L:     ₹{net:>10,.2f}\n"
        f"Tax est.:   -₹{tax:>10,.2f}\n"
        f"{'─' * 28}\n"
        f"{emoji} Final P&L: <b>{final_sign}₹{final:,.2f}</b>\n"
        f"\n"
        f"💰 Capital: <b>₹{cap_end:,.2f}</b>"
    )


# ─────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────

async def _send_close_detail(trade: dict) -> None:
    """Fallback: full trade detail on manual/unknown close."""
    name   = trade.get("symbol", "").replace(".NS", "")
    qty    = trade.get("quantity", 0)
    entry  = trade.get("entry_price", 0.0)
    exit_p = trade.get("exit_price", 0.0)
    net    = trade.get("net_pnl", 0.0)
    reason = trade.get("exit_reason", "MANUAL")
    sign   = "+" if net >= 0 else ""

    await send_message(
        f"🔄 <b>Closed: {name} ×{qty}</b>\n"
        f"Entry: ₹{entry:,.2f}  →  Exit: ₹{exit_p:,.2f}\n"
        f"Net P&L: <b>{sign}₹{net:,.2f}</b>  [{reason}]"
    )
