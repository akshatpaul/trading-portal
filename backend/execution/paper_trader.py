"""
execution/paper_trader.py — Paper trading simulation engine

Behaviour:
  - Uses real yfinance prices (15-min delayed)
  - Simulates fills with 0.05% slippage on entry only
  - Virtual capital starts at ₹10,000 (stored in app_settings)
  - All costs and taxes applied exactly as in calculator.py
  - All trades persisted to SQLite
  - Sends Telegram alerts for every action

Capital accounting:
  - place_paper_order : capital -= fill_price × quantity
  - close_paper_position: capital += exit_price × quantity − total_costs
  - Net round-trip change = net_pnl

This module is always active on startup.
Live trading is NOT enabled until the user explicitly switches.
"""

import logging
from datetime import datetime
from typing import Optional

from database import queries
from costs.calculator import calculate_costs, estimate_tax
from strategy.signals import calculate_targets
from utils.helpers import now_ist

log = logging.getLogger(__name__)

SLIPPAGE_PCT     = 0.0005   # 0.05% on entry only
_DEFAULT_CAPITAL = 10_000.0
_CAPITAL_KEY     = "paper_capital"
_MODE            = "paper"


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def place_paper_order(
    symbol: str,
    side: str,           # "BUY" | "SELL"
    quantity: int,
    price: float,
    signal_reason: str,
) -> dict:
    """
    Simulate an order fill with slippage.
    Persist position to DB, deduct capital, send Telegram alert.

    Returns:
        Order dict with fill details and remaining capital.
    """
    fill_price = _apply_slippage(price, side)
    target, stop_loss = calculate_targets(fill_price)
    ts = now_ist()

    position_id = queries.insert_position({
        "symbol":      symbol,
        "mode":        _MODE,
        "side":        side,
        "quantity":    quantity,
        "entry_price": fill_price,
        "target":      target,
        "stop_loss":   stop_loss,
        "entry_time":  ts.isoformat(),
        "signal_id":   None,
    })

    # Deduct capital (cash → shares)
    capital = get_paper_capital() - fill_price * quantity
    queries.set_setting(_CAPITAL_KEY, str(round(capital, 2)))

    log.info(
        "Paper BUY: %s ×%d @ ₹%.2f (slippage from ₹%.2f) | capital left ₹%.2f",
        symbol, quantity, fill_price, price, capital,
    )

    order = {
        "order_id":         position_id,
        "symbol":           symbol,
        "side":             side,
        "quantity":         quantity,
        "fill_price":       fill_price,
        "target":           target,
        "stop_loss":        stop_loss,
        "timestamp":        ts.isoformat(),
        "capital_remaining": round(capital, 2),
        "mode":             _MODE,
    }

    _send_entry_alert(order, signal_reason)

    from database.queries import log_activity
    log_activity(
        "trade_entry",
        f"BUY {symbol} ×{quantity} @ ₹{fill_price:.2f} | target ₹{target:.2f} | stop ₹{stop_loss:.2f}",
        symbol=symbol,
        data={"fill_price": fill_price, "quantity": quantity, "target": target, "stop_loss": stop_loss},
    )
    return order


def close_paper_position(
    position_id: int,
    exit_price: float,
    exit_reason: str,   # "TARGET" | "STOP_LOSS" | "FORCE_CLOSE" | "MANUAL"
) -> dict:
    """
    Close an open paper position, calculate P&L with all costs.
    Update DB capital and send Telegram alert.

    Returns:
        Closed trade dict with full P&L breakdown.

    Raises:
        ValueError: if position_id not found or already closed.
    """
    pos = queries.get_open_position()
    if pos is None or pos["id"] != position_id:
        raise ValueError(f"No open paper position with id={position_id}")

    symbol     = pos["symbol"]
    quantity   = pos["quantity"]
    entry_fill = float(pos["entry_price"])
    entry_time = pos["entry_time"]
    ts         = now_ist()

    # P&L calculation
    costs       = calculate_costs(entry_fill, exit_price, quantity)
    gross_pnl   = round((exit_price - entry_fill) * quantity, 2)
    net_pnl     = round(gross_pnl - costs.total_cost, 2)
    tax_est     = round(estimate_tax(net_pnl), 2)
    final_pnl   = round(net_pnl - tax_est, 2)

    trade = {
        "symbol":       symbol,
        "mode":         _MODE,
        "side":         pos["side"],
        "quantity":     quantity,
        "entry_price":  entry_fill,
        "exit_price":   exit_price,
        "entry_time":   entry_time,
        "exit_time":    ts.isoformat(),
        "exit_reason":  exit_reason,
        "gross_pnl":    gross_pnl,
        "brokerage":    costs.brokerage,
        "stt":          costs.stt,
        "exchange_fee": costs.exchange_fee,
        "sebi_charge":  costs.sebi_charge,
        "gst":          costs.gst,
        "stamp_duty":   costs.stamp_duty,
        "total_cost":   costs.total_cost,
        "net_pnl":      net_pnl,
        "tax_estimate": tax_est,
        "final_pnl":    final_pnl,
        "position_id":  position_id,
    }

    trade_id = queries.insert_trade(trade)
    queries.close_position(position_id, ts.isoformat())

    # Return capital (shares → cash, costs deducted)
    capital = get_paper_capital() + exit_price * quantity - costs.total_cost
    queries.set_setting(_CAPITAL_KEY, str(round(capital, 2)))

    log.info(
        "Paper CLOSE: %s ×%d @ ₹%.2f | net_pnl ₹%.2f | capital ₹%.2f [%s]",
        symbol, quantity, exit_price, net_pnl, capital, exit_reason,
    )

    _update_daily_summary(ts)

    result = {**trade, "trade_id": trade_id, "capital_after": round(capital, 2)}
    _send_exit_alert(result)

    from database.queries import log_activity
    reason_labels = {"TARGET": "Target hit", "STOP_LOSS": "Stop loss", "FORCE_CLOSE": "Force close", "MANUAL": "Manual close"}
    label = reason_labels.get(exit_reason, exit_reason)
    log_activity(
        "trade_exit",
        f"{label} — {symbol} ×{quantity} @ ₹{exit_price:.2f} | P&L ₹{final_pnl:+.2f}",
        symbol=symbol,
        data={"exit_price": exit_price, "exit_reason": exit_reason, "final_pnl": final_pnl},
    )
    return result


def get_paper_capital() -> float:
    """Return current virtual capital balance (cash only, excludes open positions)."""
    val = queries.get_setting(_CAPITAL_KEY, str(_DEFAULT_CAPITAL))
    return float(val)


def get_open_paper_position() -> Optional[dict]:
    """Return the currently open paper position, or None."""
    pos = queries.get_open_position()
    if pos and pos.get("mode") == _MODE:
        return pos
    return None


def get_daily_paper_summary(date: Optional[datetime] = None) -> dict:
    """
    Return paper trading summary for a given day (default: today IST).

    Returns:
        {
          date, trades_count, wins, losses,
          gross_pnl, total_cost, net_pnl, tax_estimate, final_pnl,
          win_rate, profit_factor, capital_end
        }
    """
    from utils.helpers import today_ist
    d = date.date() if date else today_ist()

    trades = queries.get_trades(limit=200, mode=_MODE, date_filter=d)

    count    = len(trades)
    wins     = sum(1 for t in trades if t["final_pnl"] > 0)
    losses   = sum(1 for t in trades if t["final_pnl"] <= 0)
    gross    = round(sum(t["gross_pnl"]   for t in trades), 2)
    cost     = round(sum(t["total_cost"]  for t in trades), 2)
    net      = round(sum(t["net_pnl"]     for t in trades), 2)
    tax      = round(sum(t["tax_estimate"]for t in trades), 2)
    final    = round(sum(t["final_pnl"]   for t in trades), 2)

    win_rate      = round(wins / count, 4) if count else 0.0
    gross_wins    = sum(t["final_pnl"] for t in trades if t["final_pnl"] > 0)
    gross_losses  = abs(sum(t["final_pnl"] for t in trades if t["final_pnl"] < 0))
    profit_factor = (
        round(gross_wins / gross_losses, 4)
        if gross_losses else (float("inf") if gross_wins else 0.0)
    )

    return {
        "date":          d.isoformat(),
        "trades_count":  count,
        "wins":          wins,
        "losses":        losses,
        "gross_pnl":     gross,
        "total_cost":    cost,
        "net_pnl":       net,
        "tax_estimate":  tax,
        "final_pnl":     final,
        "win_rate":      win_rate,
        "profit_factor": profit_factor,
        "capital_end":   get_paper_capital(),
    }


# ── Private helpers ───────────────────────────

def _apply_slippage(price: float, side: str) -> float:
    """Apply slippage: BUY fills slightly higher, SELL slightly lower."""
    if side == "BUY":
        return round(price * (1 + SLIPPAGE_PCT), 2)
    return round(price * (1 - SLIPPAGE_PCT), 2)


def _update_daily_summary(ts: datetime) -> None:
    """Recompute and upsert today's daily summary after each trade close."""
    try:
        summary_data = get_daily_paper_summary(ts)
        queries.upsert_daily_summary({
            **summary_data,
            "mode":    _MODE,
            "streak":  0,   # streaks computed separately by gamification layer
        })
    except Exception as exc:
        log.warning("paper_trader: could not update daily summary: %s", exc)


def _send_entry_alert(order: dict, reason: str) -> None:
    """Fire-and-forget Telegram alert on trade entry."""
    import asyncio
    try:
        from alerts.telegram import send_trade_entry
        asyncio.get_event_loop().run_until_complete(
            send_trade_entry(order, reason)
        )
    except Exception as exc:
        log.debug("paper_trader: entry alert skipped: %s", exc)


def _send_exit_alert(trade: dict) -> None:
    """Fire-and-forget Telegram alert on trade exit."""
    import asyncio
    try:
        from alerts.telegram import send_trade_exit
        asyncio.get_event_loop().run_until_complete(
            send_trade_exit(trade)
        )
    except Exception as exc:
        log.debug("paper_trader: exit alert skipped: %s", exc)
