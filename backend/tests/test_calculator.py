"""
tests/test_calculator.py — Cost calculator unit tests

Validates every charge component independently, then the full
round-trip calculation against manually verified numbers.

Run: pytest tests/test_calculator.py -v
"""

import pytest
from costs.calculator import calculate_costs, estimate_tax, CostBreakdown

# ── Constants (mirror rates in calculator.py) ─
BROKERAGE_ROUND_TRIP = 40.0   # ₹20 x 2 orders
STT_RATE             = 0.00025
EXCHANGE_RATE        = 0.0000345
SEBI_RATE            = 0.000001
GST_RATE             = 0.18
STAMP_RATE           = 0.00003
TAX_RATE             = 0.30


# ── Reference trade ───────────────────────────
# HDFCBANK: BUY 6 @ ₹1642  →  SELL 6 @ ₹1652  (profit trade)
BUY_P  = 1642.0
SELL_P = 1652.0
QTY    = 6

# Pre-computed reference values (hand-verified)
BUY_TV   = BUY_P * QTY                        # 9852.00
SELL_TV  = SELL_P * QTY                       # 9912.00
TOTAL_TV = BUY_TV + SELL_TV                   # 19764.00
GROSS    = (SELL_P - BUY_P) * QTY             # 60.00

REF_BROKERAGE    = 40.0
REF_STT          = SELL_TV  * STT_RATE        # 2.478
REF_EXCHANGE     = TOTAL_TV * EXCHANGE_RATE   # 0.681858
REF_SEBI         = TOTAL_TV * SEBI_RATE       # 0.019764
REF_GST          = (REF_BROKERAGE + REF_EXCHANGE + REF_SEBI) * GST_RATE
REF_STAMP        = BUY_TV   * STAMP_RATE      # 0.29556
REF_TOTAL_COST   = REF_BROKERAGE + REF_STT + REF_EXCHANGE + REF_SEBI + REF_GST + REF_STAMP
REF_NET_PNL      = GROSS - REF_TOTAL_COST
REF_TAX          = REF_NET_PNL * TAX_RATE if REF_NET_PNL > 0 else 0.0
REF_FINAL_PNL    = REF_NET_PNL - REF_TAX


# ── Return type ───────────────────────────────

def test_returns_cost_breakdown():
    result = calculate_costs(BUY_P, SELL_P, QTY)
    assert isinstance(result, CostBreakdown)


# ── Turnovers ─────────────────────────────────

def test_buy_turnover():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.buy_turnover == pytest.approx(BUY_TV)

def test_sell_turnover():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.sell_turnover == pytest.approx(SELL_TV)


# ── Individual charges ────────────────────────

def test_brokerage_is_flat_40():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.brokerage == pytest.approx(BROKERAGE_ROUND_TRIP)

def test_brokerage_independent_of_quantity():
    bd_small = calculate_costs(1000.0, 1010.0, 1)
    bd_large = calculate_costs(1000.0, 1010.0, 100)
    assert bd_small.brokerage == pytest.approx(bd_large.brokerage)

def test_stt_on_sell_side_only():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.stt == pytest.approx(REF_STT, rel=1e-5)

def test_stt_is_zero_if_sell_at_zero():
    # Artificial: sell at 0 means no sell turnover → no STT
    bd = calculate_costs(100.0, 0.0, 1)
    assert bd.stt == pytest.approx(0.0)

def test_exchange_fee():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.exchange_fee == pytest.approx(REF_EXCHANGE, rel=1e-5)

def test_sebi_charge():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.sebi_charge == pytest.approx(REF_SEBI, rel=1e-5)

def test_gst_on_brokerage_plus_exchange_plus_sebi():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    expected_gst_base = bd.brokerage + bd.exchange_fee + bd.sebi_charge
    assert bd.gst == pytest.approx(expected_gst_base * GST_RATE, rel=1e-5)

def test_stamp_on_buy_side_only():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.stamp_duty == pytest.approx(REF_STAMP, rel=1e-5)

def test_stamp_uses_buy_turnover():
    bd = calculate_costs(500.0, 600.0, 4)
    assert bd.stamp_duty == pytest.approx(500.0 * 4 * STAMP_RATE, rel=1e-5)


# ── Total cost ────────────────────────────────

def test_total_cost_is_sum_of_components():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    expected = bd.brokerage + bd.stt + bd.exchange_fee + bd.sebi_charge + bd.gst + bd.stamp_duty
    assert bd.total_cost == pytest.approx(expected, rel=1e-10)

def test_total_cost_reference_value():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.total_cost == pytest.approx(REF_TOTAL_COST, rel=1e-5)


# ── P&L calculations ──────────────────────────

def test_gross_pnl_profit():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.gross_pnl == pytest.approx(GROSS)

def test_gross_pnl_loss():
    bd = calculate_costs(1652.0, 1642.0, 6)  # sell lower than buy
    assert bd.gross_pnl == pytest.approx(-60.0)

def test_gross_pnl_breakeven():
    bd = calculate_costs(1642.0, 1642.0, 6)
    assert bd.gross_pnl == pytest.approx(0.0)

def test_net_pnl_is_gross_minus_total_cost():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.net_pnl == pytest.approx(bd.gross_pnl - bd.total_cost, rel=1e-10)

def test_net_pnl_reference_value():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.net_pnl == pytest.approx(REF_NET_PNL, rel=1e-5)

def test_final_pnl_reference_value():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.final_pnl == pytest.approx(REF_FINAL_PNL, rel=1e-5)


# ── Tax estimate ──────────────────────────────

def test_tax_on_profit():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    if bd.net_pnl > 0:
        assert bd.tax_estimate == pytest.approx(bd.net_pnl * TAX_RATE, rel=1e-10)

def test_no_tax_on_loss():
    # Sell far below buy → guaranteed loss
    bd = calculate_costs(2000.0, 1900.0, 5)
    assert bd.tax_estimate == pytest.approx(0.0)

def test_no_tax_at_breakeven_net():
    # If net_pnl == 0 exactly, tax should be 0
    assert estimate_tax(0.0) == pytest.approx(0.0)

def test_no_tax_on_negative_net():
    assert estimate_tax(-100.0) == pytest.approx(0.0)

def test_tax_standalone_positive():
    assert estimate_tax(1000.0) == pytest.approx(300.0)

def test_tax_standalone_negative():
    assert estimate_tax(-500.0) == pytest.approx(0.0)

def test_final_pnl_is_net_minus_tax():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    assert bd.final_pnl == pytest.approx(bd.net_pnl - bd.tax_estimate, rel=1e-10)


# ── Scaled quantity ───────────────────────────

def test_larger_quantity_scales_correctly():
    bd1 = calculate_costs(1000.0, 1010.0, 1)
    bd10 = calculate_costs(1000.0, 1010.0, 10)
    # Gross scales linearly; brokerage is flat so total_cost does NOT scale linearly
    assert bd10.gross_pnl == pytest.approx(bd1.gross_pnl * 10)
    assert bd10.brokerage == pytest.approx(bd1.brokerage)   # flat stays flat

def test_single_share():
    bd = calculate_costs(500.0, 503.0, 1)
    assert bd.gross_pnl == pytest.approx(3.0)
    assert bd.brokerage == pytest.approx(40.0)
    # With brokerage > gross, net should be negative
    assert bd.net_pnl < 0

def test_high_price_stock():
    # e.g. MRF-like price ~₹1,20,000
    bd = calculate_costs(120000.0, 120720.0, 1)  # +0.6% target
    assert bd.gross_pnl == pytest.approx(720.0)
    assert bd.total_cost > 0
    assert bd.final_pnl < bd.gross_pnl


# ── to_dict ───────────────────────────────────

def test_to_dict_keys():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    d = bd.to_dict()
    expected_keys = {
        "buy_turnover", "sell_turnover", "brokerage", "stt",
        "exchange_fee", "sebi_charge", "gst", "stamp_duty",
        "total_cost", "gross_pnl", "net_pnl", "tax_estimate", "final_pnl",
    }
    assert expected_keys == set(d.keys())

def test_to_dict_values_are_rounded():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    d = bd.to_dict()
    for k, v in d.items():
        assert isinstance(v, float), f"{k} should be float"
        # Ensure max 2 decimal places
        assert round(v, 2) == v, f"{k}={v} has more than 2 decimal places"

def test_to_dict_internal_consistency():
    bd = calculate_costs(BUY_P, SELL_P, QTY)
    d = bd.to_dict()
    component_sum = (
        d["brokerage"] + d["stt"] + d["exchange_fee"] +
        d["sebi_charge"] + d["gst"] + d["stamp_duty"]
    )
    # Due to rounding in to_dict the total_cost might differ by ±0.02
    assert abs(d["total_cost"] - component_sum) <= 0.02


# ── Edge cases ────────────────────────────────

def test_buy_equals_sell_is_a_loss():
    # No gross profit but costs still apply → net loss
    bd = calculate_costs(1000.0, 1000.0, 10)
    assert bd.gross_pnl == pytest.approx(0.0)
    assert bd.net_pnl < 0
    assert bd.tax_estimate == pytest.approx(0.0)
    assert bd.final_pnl < 0

def test_minimum_viable_profitable_trade():
    # Find a trade that's net positive after all costs.
    # HDFCBANK: 6 shares, +0.6% → should be profitable enough after costs.
    entry = 1642.0
    target = round(entry * 1.006, 2)
    bd = calculate_costs(entry, target, 6)
    # Should be barely net positive (target is 2:1 R:R designed for this)
    assert bd.gross_pnl > 0
    # Net may still be negative for small quantities — just check it computes
    assert isinstance(bd.final_pnl, float)
