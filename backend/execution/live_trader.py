"""
execution/live_trader.py — Live order execution via Zerodha Kite Connect

⚠️  WARNING: This module places REAL orders with REAL money.
    It is only activated when:
      1. APP_MODE=live in .env
      2. User types confirmation text in the UI modal
      3. KITE_ACCESS_TOKEN is valid

All live orders send Telegram alerts.
All safety limits from risk_manager.py are enforced.

Kite Connect MIS (intraday) is used for all orders.
Symbol format: NSE exchange, no .NS suffix (e.g. "HDFCBANK", not "HDFCBANK.NS").
"""

import logging
from typing import Optional

from config import settings

log = logging.getLogger(__name__)

# ── Kite constants ────────────────────────────
_EXCHANGE   = "NSE"
_PRODUCT    = "MIS"      # intraday — auto square-off by broker
_VARIETY    = "regular"


# ─────────────────────────────────────────────
# Kite client factory
# ─────────────────────────────────────────────

def _get_access_token() -> str:
    """Return access token: DB session token takes precedence over .env value."""
    from database import queries
    return queries.get_setting("kite_access_token_session", "") or settings.kite_access_token


def kite_ready() -> bool:
    """Runtime check — True if API key + access token are both available."""
    return bool(settings.kite_api_key and _get_access_token())


def _get_kite():
    """
    Return an authenticated KiteConnect instance.

    Raises:
        RuntimeError: if Kite credentials are not configured.
    """
    if not settings.kite_api_key:
        raise RuntimeError(
            "Kite Connect not configured — set KITE_API_KEY and "
            "KITE_API_SECRET in .env"
        )
    access_token = _get_access_token()
    if not access_token:
        raise RuntimeError(
            "No Kite access token — log in via Settings → Open Kite Login"
        )
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=settings.kite_api_key)
    kite.set_access_token(access_token)
    return kite


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def place_live_order(
    symbol: str,
    side: str,          # "BUY" | "SELL"
    quantity: int,
    order_type: str = "MARKET",
) -> dict:
    """
    Place a real intraday (MIS) order via Kite Connect.

    Args:
        symbol:     Exchange symbol without .NS suffix (e.g. "HDFCBANK")
        side:       "BUY" or "SELL"
        quantity:   Number of shares
        order_type: "MARKET" or "LIMIT"

    Returns:
        dict with at least:
          order_id, symbol, side, quantity, order_type, status, exchange

    Raises:
        RuntimeError: if Kite not configured
        Exception:    propagates Kite API errors (caller should handle)
    """
    kite       = _get_kite()
    kite_type  = _map_order_type(order_type)
    kite_side  = side.upper()

    order_id = kite.place_order(
        variety       = _VARIETY,
        exchange      = _EXCHANGE,
        tradingsymbol = symbol,
        transaction_type = kite_side,
        quantity      = quantity,
        product       = _PRODUCT,
        order_type    = kite_type,
    )

    log.info(
        "Live order placed: %s %s ×%d | order_id=%s",
        side, symbol, quantity, order_id,
    )

    _fire_order_alert(symbol, side, quantity)

    return {
        "order_id":   order_id,
        "symbol":     symbol,
        "side":       side,
        "quantity":   quantity,
        "order_type": order_type,
        "status":     "placed",
        "exchange":   _EXCHANGE,
        "product":    _PRODUCT,
        "mode":       "live",
    }


def get_live_positions() -> list[dict]:
    """
    Fetch open intraday positions from Kite.

    Returns:
        List of position dicts (MIS day positions only).
        Empty list if Kite not configured or on error.
    """
    try:
        kite = _get_kite()
        all_pos = kite.positions()
        # day = current intraday (MIS) positions
        return all_pos.get("day", [])
    except RuntimeError:
        return []
    except Exception as exc:
        log.warning("get_live_positions: Kite error: %s", exc)
        return []


def get_live_orders() -> list[dict]:
    """
    Fetch today's order book from Kite.

    Returns:
        List of order dicts.
        Empty list if Kite not configured or on error.
    """
    try:
        kite = _get_kite()
        return kite.orders() or []
    except RuntimeError:
        return []
    except Exception as exc:
        log.warning("get_live_orders: Kite error: %s", exc)
        return []


def cancel_live_order(order_id: str) -> bool:
    """
    Cancel a pending Kite order.

    Returns:
        True if cancellation succeeded, False otherwise.
    """
    try:
        kite = _get_kite()
        kite.cancel_order(variety=_VARIETY, order_id=order_id)
        log.info("Live order cancelled: order_id=%s", order_id)
        return True
    except RuntimeError:
        return False
    except Exception as exc:
        log.warning("cancel_live_order: failed for %s: %s", order_id, exc)
        return False


def get_live_ltp(symbol: str) -> Optional[float]:
    """
    Fetch the last traded price for a symbol.

    Args:
        symbol: Kite exchange symbol e.g. "HDFCBANK"

    Returns:
        Float price, or None on error.
    """
    try:
        kite      = _get_kite()
        key       = f"{_EXCHANGE}:{symbol}"
        response  = kite.ltp([key])
        return float(response[key]["last_price"])
    except RuntimeError:
        return None
    except Exception as exc:
        log.warning("get_live_ltp: failed for %s: %s", symbol, exc)
        return None


def get_kite_profile() -> Optional[dict]:
    """
    Fetch the authenticated Kite user profile.
    Useful for verifying that the access token is still valid.

    Returns:
        Profile dict, or None on error / not configured.
    """
    try:
        kite = _get_kite()
        return kite.profile()
    except RuntimeError:
        return None
    except Exception as exc:
        log.warning("get_kite_profile: %s", exc)
        return None


def ns_to_kite_symbol(ns_symbol: str) -> str:
    """Convert yfinance symbol to Kite symbol. e.g. HDFCBANK.NS → HDFCBANK"""
    return ns_symbol.replace(".NS", "")


# ─────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────

def _map_order_type(order_type: str) -> str:
    """Map plain string to Kite order type constant."""
    mapping = {
        "MARKET": "MARKET",
        "LIMIT":  "LIMIT",
    }
    return mapping.get(order_type.upper(), "MARKET")


def _fire_order_alert(symbol: str, side: str, quantity: int) -> None:
    """Fire-and-forget Telegram alert for live order placement."""
    import asyncio
    try:
        from alerts.telegram import send_live_order
        asyncio.get_event_loop().run_until_complete(
            send_live_order(symbol, side, quantity, 0.0)
        )
    except Exception as exc:
        log.debug("live_trader: order alert skipped: %s", exc)
