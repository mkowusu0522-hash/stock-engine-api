"""
api.py — FastAPI application with two clean data flows.

AUTOMATIC UNIVERSE FLOW (S&P 500):
  GET /scan          → run_universe_scan()  → stores shared snapshot
  GET /snapshot      → get_universe_snapshot()  → read shared snapshot
  GET /allocations   → portfolio-eligible tickers from shared snapshot
  GET /alerts        → structural + judgment alerts from shared snapshot

MANUAL TICKER FLOW (single ticker, ad hoc):
  GET /stock/{ticker} → analyze_single_ticker()  — does NOT affect universe snapshot

Data contracts are defined by the return values of analyze_single_ticker()
(universe snapshot entries) and the explicit /snapshot / /allocations shapes.
"""

from fastapi import FastAPI, HTTPException

from .universe import (
    analyze_single_ticker,
    get_engine_universe,
    get_universe_snapshot,
    run_universe_scan,
)
from .alerts import extract_structural_alerts, extract_judgment_alerts
from .context import get_ticker_context

app = FastAPI(
    title="Stock Engine API",
    description=(
        "Capital allocation engine. "
        "Universe flow: /scan → /snapshot → /allocations. "
        "Single-ticker flow: /stock/{ticker}."
    ),
    version="2.0.0",
)


# ---------------------------------------------------------------------------
# MANUAL TICKER FLOW
# ---------------------------------------------------------------------------

@app.get("/stock/{ticker}", summary="Analyze a single ticker (manual / ad hoc)")
def stock_judgment(ticker: str):
    """
    Single-ticker analysis path.  Safe to call for any ticker.
    Does NOT read from or write to the shared universe snapshot.

    Returns the full judgment contract for one ticker, including an optional
    'context' block if business context is available.
    """
    result = analyze_single_ticker(ticker.upper().strip())
    ctx = get_ticker_context(ticker)
    if ctx:
        result["context"] = ctx
    return result


# ---------------------------------------------------------------------------
# AUTOMATIC UNIVERSE FLOW
# ---------------------------------------------------------------------------

@app.get("/scan", summary="Run the full S&P 500 universe scan")
def scan_market():
    """
    Scans every ticker in the canonical S&P 500 universe (engine/sp500_tickers.json).
    Stores the result as the shared snapshot consumed by /snapshot, /allocations,
    and /alerts.  No independent ticker loops in downstream views.

    Returns the full snapshot including sanity/debug counts.
    """
    universe = get_engine_universe()
    snapshot = run_universe_scan(universe)
    return {
        "status": "ok",
        "scan_time": snapshot["scan_time"],
        "debug": snapshot["debug"],
        "errors": snapshot.get("errors", []),
    }


@app.get("/snapshot", summary="Return the shared universe snapshot")
def snapshot():
    """
    Returns the full universe snapshot produced by the last /scan call.
    All downstream views (map, board, portfolio, alerts) read from this
    single store — no independent ticker loops.

    Returns 404 if no scan has been run yet.
    """
    s = get_universe_snapshot()
    if s is None:
        raise HTTPException(
            status_code=404,
            detail="No universe snapshot available. Call GET /scan first.",
        )
    return s


@app.get("/allocations", summary="Portfolio-eligible tickers from the shared snapshot")
def allocations():
    """
    Returns tickers where decision_alloc == 'PASS' (all 4 layers pass).
    Reads from the shared snapshot — does NOT re-run the scan.

    Returns 404 if no scan has been run yet.
    """
    s = get_universe_snapshot()
    if s is None:
        raise HTTPException(
            status_code=404,
            detail="No universe snapshot available. Call GET /scan first.",
        )
    eligible = [r for r in s.get("results", []) if r.get("decision_alloc") == "PASS"]
    return {
        "count": len(eligible),
        "scan_time": s.get("scan_time"),
        "allocations": eligible,
    }


@app.get("/alerts", summary="Structural and judgment alerts from the shared snapshot")
def alerts(alert_type: str | None = None):
    """
    Returns alerts derived from the last universe snapshot.

    ?alert_type=structural  → economic-reality boundary crossings only
    ?alert_type=judgment    → decision/board-state signals only
    (omit)                  → all alerts

    Returns 404 if no scan has been run yet.
    """
    s = get_universe_snapshot()
    if s is None:
        raise HTTPException(
            status_code=404,
            detail="No universe snapshot available. Call GET /scan first.",
        )

    if alert_type == "structural":
        result = extract_structural_alerts(s)
    elif alert_type == "judgment":
        result = extract_judgment_alerts(s)
    else:
        structural = extract_structural_alerts(s)
        judgment = extract_judgment_alerts(s)
        result = structural + judgment

    return {
        "count": len(result),
        "scan_time": s.get("scan_time"),
        "alerts": result,
    }


@app.get("/universe", summary="Return the canonical S&P 500 ticker list")
def universe():
    """Returns the current ticker list from engine/sp500_tickers.json."""
    tickers = get_engine_universe()
    return {"count": len(tickers), "tickers": tickers}


@app.get("/context/{ticker}", summary="Return business context for a ticker")
def ticker_context(ticker: str):
    """
    Returns business context (name, value driver, risk factors, capital pattern)
    for a ticker.  Returns 404 if no context is available.
    """
    ctx = get_ticker_context(ticker.upper().strip())
    if ctx is None:
        raise HTTPException(
            status_code=404,
            detail=f"No business context available for {ticker.upper()}.",
        )
    return {"ticker": ticker.upper(), **ctx}
