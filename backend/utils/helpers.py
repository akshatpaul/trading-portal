"""
utils/helpers.py — Shared utility functions

Includes:
  - IST datetime helpers
  - Market hours check
  - 2026 NSE public holiday list
  - Number formatting
"""

from datetime import datetime, date, time
from typing import Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── NSE Public Holidays 2026 ──────────────────
# Source: NSE India official calendar
NSE_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 19),   # Holi
    date(2026, 4, 2),    # Ram Navami (tentative)
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Ambedkar Jayanti
    date(2026, 4, 29),   # Mahavir Jayanti (tentative)
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 10, 22),  # Diwali Laxmi Pujan (tentative)
    date(2026, 10, 23),  # Diwali Balipratipada (tentative)
    date(2026, 11, 4),   # Gurunanak Jayanti (tentative)
    date(2026, 12, 25),  # Christmas
    # TODO: verify exact 2026 dates on official NSE calendar
}


def now_ist() -> datetime:
    """Return current datetime in IST."""
    return datetime.now(IST)


def today_ist() -> date:
    """Return today's date in IST."""
    return now_ist().date()


def is_trading_day(d: Optional[date] = None) -> bool:
    """
    Returns True if d (default: today IST) is a trading day:
      - Monday through Friday
      - Not in NSE_HOLIDAYS_2026
    """
    d = d or today_ist()
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in NSE_HOLIDAYS_2026


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """
    Returns True if dt (default: now IST) is within market hours:
      9:15 AM – 3:30 PM IST, on a trading day.
    """
    dt = dt or now_ist()
    if not is_trading_day(dt.date()):
        return False
    t = dt.time()
    return time(9, 15) <= t <= time(15, 30)


def is_entry_window(dt: Optional[datetime] = None) -> bool:
    """
    Returns True if new entries are allowed:
      9:30 AM – 2:30 PM IST, on a trading day.
    """
    dt = dt or now_ist()
    if not is_trading_day(dt.date()):
        return False
    t = dt.time()
    return time(9, 30) <= t <= time(14, 30)


def format_inr(amount: float) -> str:
    """Format a number as Indian Rupees. e.g. 12345.67 → '₹12,345.67'"""
    return f"₹{amount:,.2f}"


def pct(value: float, decimals: int = 2) -> str:
    """Format as percentage string. e.g. 0.1234 → '12.34%'"""
    return f"{value * 100:.{decimals}f}%"
