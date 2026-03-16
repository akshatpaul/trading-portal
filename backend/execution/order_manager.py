"""
execution/order_manager.py — Unified order interface

Routes orders to either paper_trader or live_trader
based on the current APP_MODE.

This is the ONLY module that strategy code should call
to place or close orders — never call paper/live directly.

TODO (Step 9 / Step 11): Implement after both traders are done.
"""

from config import settings
from typing import Optional


def place_order(
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    signal_reason: str = "",
) -> dict:
    """
    Route an order to paper_trader or live_trader.

    Returns:
        Order result dict
    """
    if settings.is_paper_mode:
        from execution.paper_trader import place_paper_order
        return place_paper_order(symbol, side, quantity, price, signal_reason)
    else:
        from execution.live_trader import place_live_order
        return place_live_order(symbol, side, quantity)


def close_position(
    position_id: int,
    exit_price: float,
    exit_reason: str,
) -> dict:
    """
    Close an open position via the active trading mode.
    """
    if settings.is_paper_mode:
        from execution.paper_trader import close_paper_position
        return close_paper_position(position_id, exit_price, exit_reason)
    else:
        # TODO (Step 11): live close logic
        raise NotImplementedError("Live close not yet implemented")


def get_open_position() -> Optional[dict]:
    """Return the current open position, regardless of mode."""
    if settings.is_paper_mode:
        from execution.paper_trader import get_open_paper_position
        return get_open_paper_position()
    else:
        from execution.live_trader import get_live_positions
        positions = get_live_positions()
        return positions[0] if positions else None
