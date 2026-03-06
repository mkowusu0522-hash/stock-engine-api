# economic_law.py
import os
import math
import requests
import pandas as pd

BASE = "https://financialmodelingprep.com/stable"
API_KEY = os.getenv("FMP_API_KEY")  # set in env
EPS = 1e-6


def get_json(url: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def pull_quarterly(ticker: str, limit: int = 24):
    inc = get_json(
        f"{BASE}/income-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}"
    )
    bal = get_json(
        f"{BASE}/balance-sheet-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}"
    )
    cfs = get_json(
        f"{BASE}/cash-flow-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}"
    )
    return pd.DataFrame(inc), pd.DataFrame(bal), pd.DataFrame(cfs)


def _safe_tax_rate(pretax: pd.Series, tax: pd.Series, fallback: float = 0.25) -> pd.Series:
    tr = (tax / pretax).replace([math.inf, -math.inf], pd.NA)
    tr = tr.fillna(fallback).clip(0.0, 0.35)
    return tr


def compute_metrics(
    ticker: str,
    wacc: float = 0.09,
    limit: int = 24,
    debug: bool = False
) -> pd.DataFrame:
    """
    Economic Law (single source of truth):
    - Pulls quarterly statements (income, balance sheet, cash flow)
    - Builds NOPAT
    - Builds Invested Capital in two tracks:
        FULL  = Net PPE + Operating Working Capital
        PPE   = Net PPE only (used when FULL IC < 0)
    - Computes ROIC (TTM) and Incremental ROIC slopes (5q & 8q, TTM-to-TTM)
    - Computes spreads vs WACC
    - Flags value destruction using slope spread (< 0), preferring 8q else 5q
    """
    if not API_KEY:
        raise RuntimeError("Missing FMP_API_KEY environment variable.")

    inc, bal, cfs = pull_quarterly(ticker, limit=limit)

    df = pd.DataFrame({
        "ticker": ticker,
        "date": inc["date"],

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

        # Cash flow (kept for future layers; not required for law decision)
        "capex": cfs.get("capitalExpenditure"),
        "da": cfs.get("depreciationAndAmortization"),
    }).copy()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # --- NOPAT ---
    tax_rate = _safe_tax_rate(df["pretax"], df["tax"])
    df["nopat"] = df["ebit"] * (1.0 - tax_rate)

    # --- Invested Capital ---
    # Operating working capital:
    # (Current Assets - Cash) - (Current Liabilities - Short-term debt)
    df["owc"] = (df["tca"] - df["cash"]) - (df["tcl"] - df["std"])

    df["invested_capital"] = df["net_ppe"] + df["owc"]
    df["ic_ppe"] = df["net_ppe"]

    # --- Flags ---
    df["float_flag"] = df["invested_capital"] < 0

    # --- TTM ---
    df["nopat_ttm"] = df["nopat"].rolling(4).sum()
    df["ic_avg_ttm"] = df["invested_capital"].rolling(4).mean()
    df["ic_ppe_avg_ttm"] = df["ic_ppe"].rolling(4).mean()

    # --- ROIC (TTM) ---
    df["roic_ttm"] = df["nopat_ttm"] / df["ic_avg_ttm"].where(df["ic_avg_ttm"].abs() > EPS)
    df["roic_ppe_ttm"] = df["nopat_ttm"] / df["ic_ppe_avg_ttm"].where(df["ic_ppe_avg_ttm"].abs() > EPS)

    # --- Incremental ROIC slopes (TTM-to-TTM) ---
    def slope_ttm(numer_col: str, denom_col: str, q: int) -> pd.Series:
        d_num = df[numer_col] - df[numer_col].shift(q)
        d_den = df[denom_col] - df[denom_col].shift(q)
        return d_num / d_den.where(d_den.abs() > EPS)

    df["incr_roic_ttm_5q"] = slope_ttm("nopat_ttm", "ic_avg_ttm", 5)
    df["incr_roic_ttm_8q"] = slope_ttm("nopat_ttm", "ic_avg_ttm", 8)
    df["incr_roic_ppe_ttm_5q"] = slope_ttm("nopat_ttm", "ic_ppe_avg_ttm", 5)
    df["incr_roic_ppe_ttm_8q"] = slope_ttm("nopat_ttm", "ic_ppe_avg_ttm", 8)

    # --- Spreads vs WACC ---
    df["roic_spread_ttm"] = df["roic_ttm"] - wacc
    df["roic_spread_ppe_ttm"] = df["roic_ppe_ttm"] - wacc

    df["spread_slope_5q"] = df["incr_roic_ttm_5q"] - wacc
    df["spread_slope_8q"] = df["incr_roic_ttm_8q"] - wacc
    df["spread_slope_ppe_5q"] = df["incr_roic_ppe_ttm_5q"] - wacc
    df["spread_slope_ppe_8q"] = df["incr_roic_ppe_ttm_8q"] - wacc

    # --- Value destruction flag (prefer 8q else 5q; PPE track if float_flag) ---
    has_8q_full = df["spread_slope_8q"].notna()
    has_8q_ppe = df["spread_slope_ppe_8q"].notna()

    df["destroying_value_full"] = False
    df.loc[has_8q_full, "destroying_value_full"] = df.loc[has_8q_full, "spread_slope_8q"] < 0
    df.loc[~has_8q_full, "destroying_value_full"] = df.loc[~has_8q_full, "spread_slope_5q"] < 0

    df["destroying_value_ppe"] = False
    df.loc[has_8q_ppe, "destroying_value_ppe"] = df.loc[has_8q_ppe, "spread_slope_ppe_8q"] < 0
    df.loc[~has_8q_ppe, "destroying_value_ppe"] = df.loc[~has_8q_ppe, "spread_slope_ppe_5q"] < 0

    df["destroying_value"] = df["destroying_value_full"]
    df.loc[df["float_flag"], "destroying_value"] = df.loc[df["float_flag"], "destroying_value_ppe"]

    if debug:
        print(
            df[[
                "date", "invested_capital", "ic_ppe", "owc", "float_flag",
                "roic_ttm", "roic_ppe_ttm",
                "incr_roic_ttm_8q", "incr_roic_ppe_ttm_8q"
            ]].tail(10).to_string(index=False)
        )

    # Signal-first output (law primitives)
    return df[[
        "ticker", "date",
        "float_flag",
        "roic_ttm", "roic_spread_ttm",
        "roic_ppe_ttm", "roic_spread_ppe_ttm",
        "incr_roic_ttm_5q", "incr_roic_ttm_8q", "spread_slope_5q", "spread_slope_8q",
        "incr_roic_ppe_ttm_5q", "incr_roic_ppe_ttm_8q", "spread_slope_ppe_5q", "spread_slope_ppe_8q",
        "destroying_value",
    ]]


def latest_snapshot(ticker: str, wacc: float = 0.09) -> dict:
    """
    One-row law verdict:
      PASS if (ROIC TTM spread >= 0) AND (Incremental ROIC spread >= 0)
      Incremental prefers 8q else 5q
      If float_flag => uses PPE track for ROIC and incremental
    """
    df = compute_metrics(ticker, wacc=wacc, limit=24, debug=False)
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}.")

    r = df.iloc[-1].to_dict()

    use_ppe = bool(r.get("float_flag", False))

    roic_used = r["roic_ppe_ttm"] if use_ppe else r["roic_ttm"]
    roic_spread_used = r["roic_spread_ppe_ttm"] if use_ppe else r["roic_spread_ttm"]

    # pick 8q else 5q
    if use_ppe:
        incr_8 = r.get("incr_roic_ppe_ttm_8q")
        incr_5 = r.get("incr_roic_ppe_ttm_5q")
        spread_8 = r.get("spread_slope_ppe_8q")
        spread_5 = r.get("spread_slope_ppe_5q")
    else:
        incr_8 = r.get("incr_roic_ttm_8q")
        incr_5 = r.get("incr_roic_ttm_5q")
        spread_8 = r.get("spread_slope_8q")
        spread_5 = r.get("spread_slope_5q")

    incr_used = incr_8 if pd.notna(incr_8) else incr_5
    incr_spread_used = spread_8 if pd.notna(spread_8) else spread_5
    incr_horizon = "8q" if pd.notna(incr_8) else "5q"

    pass_roic = (roic_spread_used is not None) and (pd.notna(roic_spread_used)) and (roic_spread_used >= 0)
    pass_incr = (incr_spread_used is not None) and (pd.notna(incr_spread_used)) and (incr_spread_used >= 0)
    decision = "PASS" if (pass_roic and pass_incr) else "FAIL"

    return {
        "ticker": ticker,
        "date": str(r["date"]),
        "wacc": wacc,
        "track": "PPE" if use_ppe else "FULL",
        "roic_ttm": float(roic_used) if pd.notna(roic_used) else None,
        "roic_spread": float(roic_spread_used) if pd.notna(roic_spread_used) else None,
        "incr_roic_ttm": float(incr_used) if pd.notna(incr_used) else None,
        "incr_spread": float(incr_spread_used) if pd.notna(incr_spread_used) else None,
        "incr_horizon": incr_horizon,
        "float_flag": bool(r.get("float_flag", False)),
        "destroying_value": bool(r.get("destroying_value", False)),
        "decision": decision,
    }


if __name__ == "__main__":
    import sys
    t = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    print(latest_snapshot(t, wacc=0.09))



