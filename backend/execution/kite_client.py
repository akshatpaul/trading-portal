"""
execution/kite_client.py — Zerodha Kite Connect wrapper

Handles:
  - Authentication (login URL generation, access token storage)
  - Order placement (BUY / SELL MIS)
  - Position and order book queries
  - Graceful degradation when token is missing/expired

If KITE_ACCESS_TOKEN is missing or expired:
  - Print login URL to terminal
  - Expose login URL via /api/kite/login-url endpoint
  - Continue running in data-only / paper mode (no crash)

TODO (Step 11): Implement all functions below.
"""

from typing import Optional
from config import settings


def get_login_url() -> str:
    """
    Generate the Kite Connect login URL for the user to authenticate.

    Returns:
        Login URL string
    """
    # TODO (Step 11): implement
    raise NotImplementedError


def set_access_token(request_token: str) -> str:
    """
    Exchange a request_token for an access_token.
    Save the access_token to .env and in-memory settings.

    Returns:
        The new access_token
    """
    # TODO (Step 11): implement
    raise NotImplementedError


def is_token_valid() -> bool:
    """
    Check if the stored access token is still valid by making a profile API call.
    Returns False (not True) — never raises.
    """
    # TODO (Step 11): implement
    return False


def get_kite_client():
    """
    Return an authenticated KiteConnect instance, or None if not configured.
    Callers must handle None gracefully.
    """
    # TODO (Step 11): implement
    return None
