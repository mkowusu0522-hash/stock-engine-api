import sys
import pandas as pd
from . import decision
from . import stability
from . import price


def run(ticker: str, wacc: float = 0.09, stability_window_q: int = 12, min_hit_rate: float = 0.75):
    layer0 = decision.normalize_metrics(ticker, wacc=wacc)
    full = stability.add_stability_gate(layer0, stability_window_q=stability_window_q, min_hit_rate=min_hit_rate)
    r = full.iloc[-1]

    px = price.price_snapshot(ticker)

    nopat_ttm = float(r["nopat_ttm"]) if pd.notna(r["nopat_ttm"]) else None

    nopat_yield_on_ev = (
        nopat_ttm / px["enterprise_value_ttm"]
        if (nopat_ttm is not None and px.get("enterprise_value_ttm"))
        else None
    )

    margin_of_safety = 0.04
    required_return = wacc + margin_of_safety  # binding hurdle for price
    price_pass = (nopat_yield_on_ev is not None) and (nopat_yield_on_ev >= required_return)

    decision_alloc = "PASS" if (r["decision_stable"] == "PASS" and price_pass) else "FAIL"

    judgment_verdict = (
        "No" if not r["survivability_pass"]
        else "Not Yet" if r["roic_hit_rate"] < 0.75
        else "No" if not r["economic_quality_pass"]
        else "Not Yet" if not price_pass
        else "Yes"
    )

    return {
        "ticker": str(r["ticker"]),
        "date": str(r["date"]),
        "wacc": wacc,

        "price": px.get("price"),
        "market_cap": px.get("market_cap"),
        "enterprise_value_ttm": px.get("enterprise_value_ttm"),
        "free_cash_flow_ttm": px.get("free_cash_flow_ttm"),

        "nopat_ttm": nopat_ttm,
        "nopat_yield_on_ev": nopat_yield_on_ev,
        "fcf_yield_on_mcap": (
            px["free_cash_flow_ttm"] / px["market_cap"]
            if (px.get("free_cash_flow_ttm") and px.get("market_cap"))
            else None
        ),

        "roic_norm_spread": float(r["roic_norm_spread"]) if pd.notna(r["roic_norm_spread"]) else None,
        "incr_norm_spread": float(r["incr_spread_norm_used"]) if pd.notna(r["incr_spread_norm_used"]) else None,
        "dIC_used": float(r["dIC_norm_used"]) if pd.notna(r["dIC_norm_used"]) else None,
        "capital_returning_or_no_reinvest": bool(r["capital_returning_or_no_reinvest"]),

        "roic_hit_rate": float(r["roic_hit_rate"]) if pd.notna(r["roic_hit_rate"]) else None,
        "incr_hit_rate": float(r["incr_hit_rate"]) if pd.notna(r["incr_hit_rate"]) else None,

        "survivability_pass": bool(r["survivability_pass"]),
        "economic_quality_pass": bool(r["economic_quality_pass"]),
        "price_pass": price_pass,
        "required_return": required_return,
        "judgment_verdict": judgment_verdict,
    }


if __name__ == "__main__":
    t = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    out = run(t)
    print()
    print(f"Ticker: {out['ticker']}")
    print()
    print(f"Layer 0  Survivability        {'PASS' if out['survivability_pass'] else 'FAIL'}")
    print(f"Layer 1  Structure            {'PASS' if out['roic_hit_rate'] >= 0.75 else 'FAIL'}")
    print(f"Layer 2  Economic Quality     {'PASS' if out['economic_quality_pass'] else 'FAIL'}")
    print(f"Layer 3  Required Return      {'PASS' if out['price_pass'] else 'FAIL'}")
    print()
    print(f"Verdict: {out['judgment_verdict']}")
    print()
