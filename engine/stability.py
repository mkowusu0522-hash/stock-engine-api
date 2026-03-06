import pandas as pd

def add_stability_gate(
    df: pd.DataFrame,
    stability_window_q: int = 12,
    min_hit_rate: float = 0.75,
) -> pd.DataFrame:
    out = df.copy()

    roic_hit = (out["roic_norm_spread"] >= 0).where(out["roic_norm_spread"].notna())
    out["roic_hit_rate"] = roic_hit.rolling(stability_window_q).mean()

    incr_hit = (out["incr_spread_norm_used"] >= 0).where(out["incr_spread_norm_used"].notna())
    out["incr_hit_rate"] = incr_hit.rolling(stability_window_q).mean()

    out["stability_pass"] = (out["roic_hit_rate"] >= min_hit_rate) & (
        (out["incr_hit_rate"] >= min_hit_rate) | out["capital_returning_or_no_reinvest"]
    )

    out["decision_stable"] = (out["decision_norm"].eq("PASS") & out["stability_pass"])\
        .map(lambda x: "PASS" if x else "FAIL")

    return out
