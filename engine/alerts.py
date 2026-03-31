"""
alerts.py — Structural alerts vs. judgment alerts.

STRUCTURAL alerts  = what changed in economic reality (ROIC, IC, value destruction).
                     Tied to real boundary crossings, not board state.

JUDGMENT alerts    = what changed in the decision/allocation board state
                     (verdict changes, allocation candidates, priced-out candidates).

Both are derived from the shared universe snapshot produced by run_universe_scan().
"""

from __future__ import annotations

from typing import Any


def _float_or_none(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def extract_structural_alerts(snapshot: dict) -> list[dict]:
    """
    Structural alerts: boundary crossings in economic reality.

    Reason codes:
      ROIC_BELOW_WACC       — ROIC spread is negative (earning below cost of capital)
      UNSTABLE_ROIC_HISTORY — Hit rate below 75% threshold (inconsistent quality)
      VALUE_DESTRUCTION     — Incremental ROIC spread negative AND actively reinvesting
      NO_DATA               — Ticker failed entirely (silent failure surfaced)
    """
    alerts: list[dict] = []

    for r in snapshot.get("results", []):
        ticker = r.get("ticker", "UNKNOWN")

        survivability = r.get("survivability_pass", False)
        economic_quality = r.get("economic_quality_pass", False)
        roic_spread = _float_or_none(r.get("roic_norm_spread"))
        roic_hit_rate = _float_or_none(r.get("roic_hit_rate"))
        incr_spread = _float_or_none(r.get("incr_norm_spread"))
        dIC = _float_or_none(r.get("dIC_used"))
        capital_returning = r.get("capital_returning_or_no_reinvest", False)

        # Structural: ROIC below WACC (earning below cost of capital)
        if survivability and roic_spread is not None and roic_spread < 0:
            alerts.append({
                "ticker": ticker,
                "type": "structural",
                "reason_code": "ROIC_BELOW_WACC",
                "severity": "high",
                "message": (
                    f"ROIC spread {roic_spread:+.3f}: "
                    "company earning below its cost of capital"
                ),
                "value": roic_spread,
            })

        # Structural: ROIC history below 75% hit-rate threshold
        if roic_hit_rate is not None and roic_hit_rate < 0.75:
            alerts.append({
                "ticker": ticker,
                "type": "structural",
                "reason_code": "UNSTABLE_ROIC_HISTORY",
                "severity": "medium",
                "message": (
                    f"ROIC hit rate {roic_hit_rate:.0%} over trailing 12 quarters "
                    "— quality has been inconsistent"
                ),
                "value": roic_hit_rate,
            })

        # Structural: Incremental ROIC negative while actively reinvesting
        if (
            incr_spread is not None
            and incr_spread < 0
            and not capital_returning
            and dIC is not None
            and dIC > 0
        ):
            alerts.append({
                "ticker": ticker,
                "type": "structural",
                "reason_code": "VALUE_DESTRUCTION",
                "severity": "high",
                "message": (
                    f"Incremental ROIC spread {incr_spread:+.3f} while actively "
                    f"reinvesting (ΔIC {dIC:+,.0f}) — reinvestment destroying value"
                ),
                "value": incr_spread,
            })

    # Surface silent failures (tickers that errored during scan)
    for err in snapshot.get("errors", []):
        alerts.append({
            "ticker": err.get("ticker", "UNKNOWN"),
            "type": "structural",
            "reason_code": "NO_DATA",
            "severity": "low",
            "message": f"Scan failed: {err.get('error', 'unknown error')}",
            "value": None,
        })

    return alerts


def extract_judgment_alerts(snapshot: dict) -> list[dict]:
    """
    Judgment alerts: decision/board state signals.

    Reason codes:
      ALLOCATION_CANDIDATE  — All 4 layers pass; ready for capital allocation
      NOT_YET_PRICE         — Quality passes but price above required return
      QUALITY_FAIL          — Survivable but economic quality does not pass
    """
    alerts: list[dict] = []

    for r in snapshot.get("results", []):
        ticker = r.get("ticker", "UNKNOWN")
        verdict = r.get("judgment_verdict")
        survivability = r.get("survivability_pass", False)
        economic_quality = r.get("economic_quality_pass", False)
        roic_hit_rate = _float_or_none(r.get("roic_hit_rate"))
        price_pass = r.get("price_pass", False)
        nopat_yield = _float_or_none(r.get("nopat_yield_on_ev"))
        required_return = _float_or_none(r.get("required_return"))

        if verdict == "Yes":
            alerts.append({
                "ticker": ticker,
                "type": "judgment",
                "reason_code": "ALLOCATION_CANDIDATE",
                "severity": "info",
                "message": (
                    "All 4 layers pass — allocation candidate. "
                    f"NOPAT yield: {nopat_yield:.1%}" if nopat_yield else
                    "All 4 layers pass — allocation candidate."
                ),
                "value": nopat_yield,
            })

        elif (
            survivability
            and economic_quality
            and roic_hit_rate is not None
            and roic_hit_rate >= 0.75
            and not price_pass
        ):
            gap = (required_return - nopat_yield) if (required_return is not None and nopat_yield is not None) else None
            alerts.append({
                "ticker": ticker,
                "type": "judgment",
                "reason_code": "NOT_YET_PRICE",
                "severity": "low",
                "message": (
                    "Quality passes but priced above required return — "
                    f"yield gap {gap:+.1%}" if gap is not None else
                    "Quality passes but priced above required return"
                ),
                "value": nopat_yield,
            })

        elif survivability and not economic_quality:
            alerts.append({
                "ticker": ticker,
                "type": "judgment",
                "reason_code": "QUALITY_FAIL",
                "severity": "medium",
                "message": "Survivable but economic quality gate failed",
                "value": None,
            })

    return alerts
