"""
universe.py — Single source of truth for universe management.

Two clean data flows:

  1. AUTOMATIC UNIVERSE FLOW
     get_engine_universe()       → canonical S&P 500 from local JSON (no scraping)
     run_universe_scan(universe) → scans every ticker, stores shared snapshot
     get_universe_snapshot()     → returns the cached snapshot (read by all views)

  2. MANUAL TICKER FLOW
     analyze_single_ticker(ticker) → one-ticker analysis; does NOT touch the universe
                                     snapshot or portfolio logic

Map/radar, judgment board, portfolio eligibility, and alerts all read from the
shared snapshot produced by run_universe_scan().  No independent ticker loops.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
SP500_FILE = ENGINE_DIR / "sp500_tickers.json"

# ---------------------------------------------------------------------------
# Shared snapshot store (in-memory, thread-safe)
# ---------------------------------------------------------------------------
# All reads and writes to _universe_snapshot MUST be done under _snapshot_lock.
# ---------------------------------------------------------------------------

_snapshot_lock = threading.Lock()
_universe_snapshot: dict | None = None  # protected by _snapshot_lock


# ---------------------------------------------------------------------------
# 1. Universe source
# ---------------------------------------------------------------------------

def get_engine_universe() -> list[str]:
    """
    Return the canonical S&P 500 ticker list from the local JSON file.
    This is the ONLY place tickers enter the automatic universe flow.
    No web scraping, no CSV fetches at runtime.
    """
    if not SP500_FILE.exists():
        raise FileNotFoundError(
            f"Missing universe file: {SP500_FILE}. "
            "Ensure engine/sp500_tickers.json is present."
        )
    data = json.loads(SP500_FILE.read_text(encoding="utf-8"))
    tickers = data.get("tickers", [])
    if not tickers:
        raise ValueError("sp500_tickers.json contains no tickers.")
    return list(tickers)


# ---------------------------------------------------------------------------
# 2. Single-ticker analysis (manual / ad hoc path)
# ---------------------------------------------------------------------------

def analyze_single_ticker(ticker: str, wacc: float = 0.09) -> dict:
    """
    Analyze one ticker on demand.  Used by:
      - Manual/typed ticker input
      - GET /stock/{ticker} endpoint
      - Internally by run_universe_scan()

    Does NOT read from or write to the universe snapshot.
    """
    from .__main__ import run  # imported here to avoid circular imports
    return run(ticker.upper().strip(), wacc=wacc)


# ---------------------------------------------------------------------------
# 3. Universe scan (produces the shared snapshot)
# ---------------------------------------------------------------------------

def run_universe_scan(universe: list[str] | None = None) -> dict:
    """
    Scan every ticker in the universe and store the result as the shared
    snapshot.  All downstream views (map, board, portfolio, alerts, history)
    read from this single snapshot — no independent ticker loops.

    Returns the snapshot dict (also accessible via get_universe_snapshot()).
    """
    global _universe_snapshot

    if universe is None:
        universe = get_engine_universe()

    scan_time = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []
    errors: list[dict] = []

    for ticker in universe:
        try:
            r = analyze_single_ticker(ticker)
            results.append(r)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})

    # Sanity / debug counts surface silent failures instead of skipping them
    portfolio_eligible = [
        r for r in results
        if r.get("decision_alloc") == "PASS"
    ]
    verdict_yes = [r for r in results if r.get("judgment_verdict") == "Yes"]
    verdict_not_yet = [r for r in results if r.get("judgment_verdict") == "Not Yet"]
    verdict_no = [r for r in results if r.get("judgment_verdict") == "No"]

    snapshot = {
        "scan_time": scan_time,
        "results": results,
        "errors": errors,
        # Sanity counts — visible failures instead of silent skips
        "debug": {
            "total_universe_tickers": len(universe),
            "successful_scan_results": len(results),
            "failed_scans": len(errors),
            "verdict_yes": len(verdict_yes),
            "verdict_not_yet": len(verdict_not_yet),
            "verdict_no": len(verdict_no),
            "portfolio_eligible_tickers": len(portfolio_eligible),
        },
    }

    with _snapshot_lock:
        _universe_snapshot = snapshot

    return snapshot


# ---------------------------------------------------------------------------
# 4. Snapshot reader
# ---------------------------------------------------------------------------

def get_universe_snapshot() -> dict | None:
    """
    Return the most recent shared universe snapshot, or None if no scan
    has been run yet.  All views (map, board, portfolio, alerts) call this.
    """
    with _snapshot_lock:
        return _universe_snapshot
