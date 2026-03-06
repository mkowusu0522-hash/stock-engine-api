# decision.py
# Measurement + decision layer (imports immutable economic_law.py)
# Windows CMD usage:
#   python decision.py TICKER
# Example:
#   python decision.py AAPL

import sys
import pandas as pd
from . import economic_law
from . import stability  # only if decision.py imports stability

EPS = 1e-6


def normalize_metrics(
    ticker: str,
    wacc: float = 0.09,
    limit: int = 24,
    # --- OWC stabilization ---
    owc_smooth_q: int = 4,          # trailing avg window for OWC smoothing
    owc_cap_mult: float = 1.0,      # cap |OWC| to this multiple of |PPE|
    # --- IC floors (denominator compression guards) ---
    ic_floor_pct_ppe: float = 0.15,     # min IC as % of |PPE|
    ic_floor_assets_pct: float = 0.03,  # min IC as % of |Total Assets|
    # --- ROIC denominator smoothing ---
    ic_avg_q_short: int = 4,        # short avg window (quarters)
    ic_avg_q_long: int = 8,         # long avg window (quarters)
    # --- incremental ROIC handling ---
    incr_requires_positive_dIC: bool = True,  # only compute incremental if ΔIC > 0
    prefer_8q: bool = True,
) -> pd.DataFrame:
    """
    Measurement layer (does NOT change economic_law):
    - Stabilizes invested capital to reduce accounting/quarter noise
    - Produces normalized ROIC and normalized incremental ROIC spreads vs WACC

    Decision rule (room for capital returners):
      PASS if:
        ROIC_norm_spread >= 0
        AND (
              incr_spread_norm_used >= 0
              OR dIC_norm_used <= 0   # capital returning / no reinvestment to test
            )
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    ticker = ticker.upper().strip()

    inc, bal, _cfs = economic_law.pull_quarterly(ticker, limit=limit)

    if inc is None or len(inc) == 0:
        raise RuntimeError(f"No income statement data returned for {ticker}.")
    if bal is None or len(bal) == 0:
        raise RuntimeError(f"No balance sheet data returned for {ticker}.")

    df = pd.DataFrame({
        "ticker": ticker,
        "date": pd.to_datetime(inc["date"]),

        # Income
        "ebit": inc.get("operatingIncome"),
        "pretax": inc.get("incomeBeforeTax"),
        "tax": inc.get("incomeTaxExpense"),

        # Balance sheet
        "net_ppe": bal.get("propertyPlantEquipmentNet"),
        "tca": bal.get("totalCurrentAssets"),
        "cash": bal.get("cashAndCashEquivalents"),
        "tcl": bal.get("totalCurrentLiabilities"),
        "std": bal.get("shortTermDebt"),
        "total_assets": bal.get("totalAssets"),
    }).copy()

    df = df.sort_values("date").reset_index(drop=True)

    # --- NOPAT (same construction as law) ---
    tax_rate = economic_law._safe_tax_rate(df["pretax"], df["tax"])
    df["nopat"] = df["ebit"] * (1.0 - tax_rate)

    # --- OWC (raw + smoothed) ---
    df["owc_raw"] = (df["tca"] - df["cash"]) - (df["tcl"] - df["std"])
    df["owc_smooth"] = df["owc_raw"].rolling(owc_smooth_q).mean()

    # --- Cap OWC contribution relative to PPE to prevent it dwarfing/erasing PPE ---
    ppe_abs = df["net_ppe"].abs()
    cap = ppe_abs * owc_cap_mult
    df["owc_smooth_capped"] = df["owc_smooth"].clip(lower=-cap, upper=cap)

    # Durable IC
    df["ic_durable"] = df["net_ppe"] + df["owc_smooth_capped"]

    # --- Floors to prevent denominator compression ---
    df["ic_floor_ppe"] = ppe_abs * ic_floor_pct_ppe
    df["ic_floor_assets"] = df["total_assets"].abs() * ic_floor_assets_pct

    # Max floor available (handles tiny/zero PPE via assets floor)
    df["ic_floor"] = pd.concat([df["ic_floor_ppe"], df["ic_floor_assets"]], axis=1).max(axis=1)

    df["ic_norm"] = df["ic_durable"].copy()
    df.loc[df["ic_norm"].abs() < df["ic_floor"].fillna(0), "ic_norm"] = df["ic_floor"]

    # --- TTM NOPAT + IC averages ---
    df["nopat_ttm"] = df["nopat"].rolling(4).sum()

    df["ic_avg_short"] = df["ic_norm"].rolling(ic_avg_q_short).mean()
    df["ic_avg_long"] = df["ic_norm"].rolling(ic_avg_q_long).mean()

    # Blend short + long for stability
    df["ic_avg_used"] = (df["ic_avg_short"] + df["ic_avg_long"]) / 2.0

    # --- Normalized ROIC (TTM) ---
    df["roic_norm_ttm"] = df["nopat_ttm"] / df["ic_avg_used"].where(df["ic_avg_used"].abs() > EPS)
    df["roic_norm_spread"] = df["roic_norm_ttm"] - wacc

    # --- Incremental ROIC slopes (TTM-to-TTM) with ΔIC tracking ---
    def slope_ttm(numer_col: str, denom_col: str, q: int):
        d_num = df[numer_col] - df[numer_col].shift(q)
        d_den = df[denom_col] - df[denom_col].shift(q)  # ΔIC over horizon
        slope = d_num / d_den.where(d_den.abs() > EPS)

        # Only treat as reinvestment when ΔIC > 0 (optional)
        if incr_requires_positive_dIC:
            slope = slope.where(d_den > 0)

        return slope, d_den

    df["incr_roic_norm_5q"], df["dIC_norm_5q"] = slope_ttm("nopat_ttm", "ic_avg_used", 5)
    df["incr_roic_norm_8q"], df["dIC_norm_8q"] = slope_ttm("nopat_ttm", "ic_avg_used", 8)

    df["incr_spread_norm_5q"] = df["incr_roic_norm_5q"] - wacc
    df["incr_spread_norm_8q"] = df["incr_roic_norm_8q"] - wacc

    # Choose horizon (prefer 8q else 5q) and carry ΔIC with it
    if prefer_8q:
        use_8 = df["incr_roic_norm_8q"].notna()
        df["incr_roic_norm_used"] = df["incr_roic_norm_8q"].where(use_8, df["incr_roic_norm_5q"])
        df["incr_spread_norm_used"] = df["incr_spread_norm_8q"].where(
            df["incr_spread_norm_8q"].notna(), df["incr_spread_norm_5q"]
        )
        df["dIC_norm_used"] = df["dIC_norm_8q"].where(use_8, df["dIC_norm_5q"])
        df["incr_horizon_used"] = use_8.map(lambda x: "8q" if x else "5q")
    else:
        use_5 = df["incr_roic_norm_5q"].notna()
        df["incr_roic_norm_used"] = df["incr_roic_norm_5q"].where(use_5, df["incr_roic_norm_8q"])
        df["incr_spread_norm_used"] = df["incr_spread_norm_5q"].where(
            df["incr_spread_norm_5q"].notna(), df["incr_spread_norm_8q"]
        )
        df["dIC_norm_used"] = df["dIC_norm_5q"].where(use_5, df["dIC_norm_8q"])
        df["incr_horizon_used"] = use_5.map(lambda x: "5q" if x else "8q")

    # --- Decision gate (room for capital returners) ---
    df["survivability_pass"] = df["roic_norm_spread"].notna()

    df["pass_roic_norm"] = df["roic_norm_spread"].notna() & (df["roic_norm_spread"] >= 0)
    df["pass_incr_norm"] = df["incr_spread_norm_used"].notna() & (df["incr_spread_norm_used"] >= 0)

    df["capital_returning_or_no_reinvest"] = df["dIC_norm_used"].notna() & (df["dIC_norm_used"] <= 0)

    df["economic_quality_pass"] = (
    df["pass_roic_norm"] & (df["pass_incr_norm"] | df["capital_returning_or_no_reinvest"])
    )

    df["decision_norm"] = df["economic_quality_pass"].map(lambda x: "PASS" if x else "FAIL")

    return df


def latest_normalized_snapshot(
    ticker: str,
    wacc: float = 0.09,
    stability_window_q: int = 12,
    min_hit_rate: float = 0.75,
) -> dict:
    base = normalize_metrics(ticker, wacc=wacc)
    df = stability.add_stability_gate(base, stability_window_q=stability_window_q, min_hit_rate=min_hit_rate)
    r = df.iloc[-1].to_dict()

    def f(x):
        return float(x) if pd.notna(x) else None

    return {
        "ticker": r["ticker"],
        "date": str(r["date"]),
        "wacc": wacc,

        "roic_norm_ttm": f(r["roic_norm_ttm"]),
        "roic_norm_spread": f(r["roic_norm_spread"]),

        "incr_roic_norm": f(r["incr_roic_norm_used"]),
        "incr_norm_spread": f(r["incr_spread_norm_used"]),
        "incr_horizon": r["incr_horizon_used"],

        "dIC_used": f(r["dIC_norm_used"]),
        "capital_returning_or_no_reinvest": bool(r["capital_returning_or_no_reinvest"])
        if pd.notna(r["capital_returning_or_no_reinvest"]) else False,

        "decision": r["decision_norm"],
        "roic_hit_rate": f(r.get("roic_hit_rate")),
        "incr_hit_rate": f(r.get("incr_hit_rate")),
        "decision_stable": r.get("decision_stable"),
        "stability_window_q": stability_window_q,
        "min_hit_rate": min_hit_rate,
        "survivability_pass": bool(r["survivability_pass"]) if pd.notna(r["survivability_pass"]) else False,
        "economic_quality_pass": bool(r["economic_quality_pass"]) if pd.notna(r["economic_quality_pass"]) else False,
    }



if __name__ == "__main__":
    t = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    print(latest_normalized_snapshot(t, wacc=0.09))
