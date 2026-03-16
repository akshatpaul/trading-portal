"""
costs/calculator.py — Brokerage, charges, and tax calculation

All charges for an intraday MIS trade on NSE:

  Brokerage   : ₹20 flat per order (buy + sell = ₹40 total)
  STT         : 0.025% on SELL turnover only
  Exchange fee: 0.00345% on total turnover
  SEBI charge : 0.0001% on total turnover
  GST         : 18% on (brokerage + exchange charges + SEBI)
  Stamp duty  : 0.003% on BUY turnover only

Total cost    = sum of all above
Net P&L       = Gross P&L - Total cost
Tax estimate  = Net P&L * 0.30  (only if Net P&L > 0)
Final P&L     = Net P&L - Tax estimate
"""

from dataclasses import dataclass

# ── Charge rates ──────────────────────────────
_BROKERAGE_PER_ORDER = 20.0          # ₹ flat per order leg
_STT_RATE            = 0.00025       # 0.025% on sell turnover
_EXCHANGE_RATE       = 0.0000345     # 0.00345% on total turnover
_SEBI_RATE           = 0.000001      # 0.0001% on total turnover
_GST_RATE            = 0.18          # 18% on (brokerage + exchange + SEBI)
_STAMP_RATE          = 0.00003       # 0.003% on buy turnover
_TAX_RATE            = 0.30          # 30% income tax on net profit


@dataclass
class CostBreakdown:
    """Full cost breakdown for a round-trip trade."""
    buy_turnover: float
    sell_turnover: float
    brokerage: float
    stt: float
    exchange_fee: float
    sebi_charge: float
    gst: float
    stamp_duty: float
    total_cost: float
    gross_pnl: float
    net_pnl: float
    tax_estimate: float
    final_pnl: float

    def to_dict(self) -> dict:
        return {
            "buy_turnover":  round(self.buy_turnover,  2),
            "sell_turnover": round(self.sell_turnover, 2),
            "brokerage":     round(self.brokerage,     2),
            "stt":           round(self.stt,           2),
            "exchange_fee":  round(self.exchange_fee,  2),
            "sebi_charge":   round(self.sebi_charge,   2),
            "gst":           round(self.gst,           2),
            "stamp_duty":    round(self.stamp_duty,    2),
            "total_cost":    round(self.total_cost,    2),
            "gross_pnl":     round(self.gross_pnl,     2),
            "net_pnl":       round(self.net_pnl,       2),
            "tax_estimate":  round(self.tax_estimate,  2),
            "final_pnl":     round(self.final_pnl,     2),
        }


def calculate_costs(
    buy_price: float,
    sell_price: float,
    quantity: int,
) -> CostBreakdown:
    """
    Calculate full cost breakdown for a round-trip intraday MIS trade on NSE.

    Args:
        buy_price:  entry fill price per share (₹)
        sell_price: exit fill price per share (₹)
        quantity:   number of shares traded

    Returns:
        CostBreakdown with every charge itemised and final P&L after tax.

    Example:
        >>> bd = calculate_costs(buy_price=1642.0, sell_price=1652.0, quantity=6)
        >>> bd.gross_pnl   # 60.0
        >>> bd.final_pnl   # ~6.0 after all charges + 30% tax
    """
    buy_turnover  = buy_price  * quantity
    sell_turnover = sell_price * quantity
    total_turnover = buy_turnover + sell_turnover

    brokerage    = _BROKERAGE_PER_ORDER * 2              # buy leg + sell leg
    stt          = sell_turnover * _STT_RATE             # sell side only
    exchange_fee = total_turnover * _EXCHANGE_RATE
    sebi_charge  = total_turnover * _SEBI_RATE
    gst          = (brokerage + exchange_fee + sebi_charge) * _GST_RATE
    stamp_duty   = buy_turnover * _STAMP_RATE            # buy side only

    total_cost = brokerage + stt + exchange_fee + sebi_charge + gst + stamp_duty

    gross_pnl    = (sell_price - buy_price) * quantity
    net_pnl      = gross_pnl - total_cost
    tax_estimate = estimate_tax(net_pnl)
    final_pnl    = net_pnl - tax_estimate

    return CostBreakdown(
        buy_turnover=buy_turnover,
        sell_turnover=sell_turnover,
        brokerage=brokerage,
        stt=stt,
        exchange_fee=exchange_fee,
        sebi_charge=sebi_charge,
        gst=gst,
        stamp_duty=stamp_duty,
        total_cost=total_cost,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        tax_estimate=tax_estimate,
        final_pnl=final_pnl,
    )


def estimate_tax(net_pnl: float) -> float:
    """
    Estimate income tax on trading profit at 30% flat rate.
    Returns 0 if net_pnl <= 0 (no tax on losses).
    """
    return net_pnl * _TAX_RATE if net_pnl > 0 else 0.0
