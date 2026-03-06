import os, math, requests
import pandas as pd

BASE = "https://financialmodelingprep.com/stable"
API_KEY = os.getenv("FMP_API_KEY")  # set this in your environment
WACC = 0.09                         # change per company/assumption
DEBUG = False                       # True = print sanity tables

EPS = 1e-6

def get_json(url: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def pull_quarterly(ticker: str, limit: int = 20):
    inc = get_json(f"{BASE}/income-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}")
    bal = get_json(f"{BASE}/balance-sheet-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}")
    cfs = get_json(f"{BASE}/cash-flow-statement?symbol={ticker}&period=quarter&limit={limit}&apikey={API_KEY}")
    return pd.DataFrame(inc), pd.DataFrame(bal), pd.DataFrame(cfs)

def compute_metrics(ticker: str) -> pd.DataFrame:
    inc, bal, cfs = pull_quarterly(ticker)

    # Base frame (oldest -> newest)
    df = pd.DataFrame({
        "ticker": ticker,
        "date": inc["date"],
        "ebit": inc["operatingIncome"],
        "pretax": inc["incomeBeforeTax"],
        "tax": inc["incomeTaxExpense"],

        "net_ppe": bal.get("propertyPlantEquipmentNet"),
        "tca": bal.get("totalCurrentAssets"),
        "cash": bal.get("cashAndCashEquivalents"),
        "tcl": bal.get("totalCurrentLiabilities"),
        "std": bal.get("shortTermDebt"),

        "capex": cfs.get("capitalExpenditure"),
        "da": cfs.get("depreciationAndAmortization"),
    }).copy()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # ---- NOPAT (computed here) ----
    tax_rate = (df["tax"] / df["pretax"]).replace([math.inf, -math.inf], pd.NA).fillna(0.25).clip(0, 0.35)
    df["nopat"] = df["ebit"] * (1 - tax_rate)

    # ---- Invested capital variants ----
    # OWC (ex cash and short-term debt)
    df["owc"] = (df["tca"] - df["cash"]) - (df["tcl"] - df["std"])

    # "Full" invested capital (PPE + OWC)
    df["invested_capital"] = df["net_ppe"] + df["owc"]

    # PPE-only capital (removes OWC noise)
    df["ic_ppe"] = df["net_ppe"] 

    # Flags
    df["float_flag"] = df["invested_capital"] < 0

    # ---- TTM building blocks (must be BEFORE any *_ttm ROIC) ----
    df["nopat_ttm"] = df["nopat"].rolling(4).sum()
    df["ic_avg_ttm"] = df["invested_capital"].rolling(4).mean()
    df["ic_ppe_avg_ttm"] = df["ic_ppe"].rolling(4).mean()

    # ---- ROIC (TTM) ----
    df["roic_ttm"] = df["nopat_ttm"] / df["ic_avg_ttm"].where(df["ic_avg_ttm"].abs() > EPS)
    df["roic_ppe_ttm"] = df["nopat_ttm"] / df["ic_ppe_avg_ttm"].where(df["ic_ppe_avg_ttm"].abs() > EPS)

    # ---- Incremental ROIC (TTM-to-TTM slopes) ----
    def slope_ttm(numer_col: str, denom_col: str, q: int) -> pd.Series:
        d_num = df[numer_col] - df[numer_col].shift(q)
        d_den = df[denom_col] - df[denom_col].shift(q)
        return d_num / d_den.where(d_den.abs() > EPS)

    # Full IC slopes
    df["incr_roic_ttm_5q"] = slope_ttm("nopat_ttm", "ic_avg_ttm", 5)
    df["incr_roic_ttm_8q"] = slope_ttm("nopat_ttm", "ic_avg_ttm", 8)

    # PPE-only slopes
    df["incr_roic_ppe_ttm_8q"] = slope_ttm("nopat_ttm", "ic_ppe_avg_ttm", 8)

    # ---- Spreads vs WACC ----
    df["spread_slope_5q"] = df["incr_roic_ttm_5q"] - WACC
    df["spread_slope_8q"] = df["incr_roic_ttm_8q"] - WACC
    df["spread_slope_ppe_8q"] = df["incr_roic_ppe_ttm_8q"] - WACC

    # Prefer 8q when available, else 5q
    has_8q = df["spread_slope_8q"].notna()
    df["destroying_value"] = has_8q & (df["spread_slope_8q"] < 0)
    df.loc[~has_8q, "destroying_value"] = df.loc[~has_8q, "spread_slope_5q"] < 0

    # ---- Quarter ROIC + incremental (quarter-to-quarter) ----
    df["roic"] = df["nopat"] / df["invested_capital"].where(df["invested_capital"].abs() > EPS)
    df["incr_roic"] = df["nopat"].diff() / df["invested_capital"].diff().where(df["invested_capital"].diff().abs() > EPS)

    if DEBUG:
        print("\nLast 8 quarters invested capital:")
        print(df[["date", "invested_capital", "ic_ppe", "owc"]].tail(8).to_string(index=False))
        print("\nLast 8 quarters NOPAT + IC (TTM):")
        print(df[["date", "nopat_ttm", "ic_avg_ttm", "ic_ppe_avg_ttm"]].tail(8).to_string(index=False))

    # Output columns (tight + signal-first)
    return df[[
        "ticker", "date",
        "float_flag",
        "roic_ttm", "incr_roic_ttm_5q", "incr_roic_ttm_8q", "spread_slope_5q", "spread_slope_8q",
        "roic_ppe_ttm", "incr_roic_ppe_ttm_8q", "spread_slope_ppe_8q",
        "destroying_value",
        "roic", "incr_roic"
    ]]

if __name__ == "__main__":
    t = "AAPL"  # change this
    out = compute_metrics(t)
    print(out.tail(3).to_string(index=False))
