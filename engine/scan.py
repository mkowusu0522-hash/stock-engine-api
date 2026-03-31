from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

from .__main__ import run
from .notify import send_text
from .universe import get_engine_universe  # single source of truth for universe

ENGINE_DIR = Path(__file__).resolve().parent
TICKERS_FILE = ENGINE_DIR / "tickers.txt"
PORTFOLIO_LOG = ENGINE_DIR / "portfolio_log.csv"
ERROR_LOG = ENGINE_DIR / "scan_errors.csv"


# ---------------------------------------------------------------------------
# Legacy helpers kept for backward compatibility
# ---------------------------------------------------------------------------

def load_sp500() -> list[str]:
    """
    Deprecated: use get_engine_universe() from universe.py instead.
    Retained here to avoid breaking any external callers.
    Reads from the local sp500_tickers.json — no web scraping.
    """
    return get_engine_universe()


def ensure_csv(path: Path, headers: list[str]) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)


def append_row(path: Path, row: dict) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)


def read_tickers(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    out = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip().upper()
        if not t or t.startswith("#"):
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def scan_tickers(tickers: list[str]) -> list[dict]:
    results = []

    for t in tickers:
        try:
            out = run(t)
            results.append({
                "ticker": t,
                "judgment_verdict": out.get("judgment_verdict"),
                "price_pass": out.get("price_pass"),
                "survivability_pass": out.get("survivability_pass"),
                "economic_quality_pass": out.get("economic_quality_pass"),
                "roic_hit_rate": out.get("roic_hit_rate"),
            })
        except Exception as e:
            results.append({
                "ticker": t,
                "error": str(e),
            })

    return results

def main() -> dict:
    """
    Daily scan: uses run_universe_scan() to populate the shared snapshot, then
    logs allocation candidates and errors to CSV and sends an SMS alert.

    Returns a summary dict (so the FastAPI /scan route gets a JSON response).
    """
    from .universe import run_universe_scan

    snapshot = run_universe_scan()  # populates the shared in-memory snapshot

    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ensure_csv(
        PORTFOLIO_LOG,
        [
            "date", "timestamp", "ticker",
            "decision_alloc", "decision_stable", "price_pass", "judgment_verdict",
            "price", "nopat_yield_on_ev"
        ],
    )

    ensure_csv(ERROR_LOG, ["date", "timestamp", "ticker", "error"])

    passes: list[str] = []
    scan_errors: list[str] = []

    for out in snapshot.get("results", []):
        t = out.get("ticker", "UNKNOWN")
        verdict = out.get("judgment_verdict")
        if out.get("decision_alloc") == "PASS":
            append_row(
                PORTFOLIO_LOG,
                {
                    "date": today,
                    "timestamp": ts,
                    "ticker": t,
                    "decision_alloc": out.get("decision_alloc"),
                    "decision_stable": out.get("decision_stable"),
                    "price_pass": out.get("price_pass"),
                    "price": out.get("price"),
                    "nopat_yield_on_ev": out.get("nopat_yield_on_ev"),
                    "judgment_verdict": verdict,
                },
            )
            passes.append(t)

    for err in snapshot.get("errors", []):
        t = err.get("ticker", "UNKNOWN")
        scan_errors.append(t)
        append_row(
            ERROR_LOG,
            {
                "date": today,
                "timestamp": ts,
                "ticker": t,
                "error": err.get("error", "unknown"),
            },
        )

    debug = snapshot.get("debug", {})
    summary = {
        "date": today,
        "scan_time": snapshot.get("scan_time"),
        "total_scanned": debug.get("successful_scan_results", 0),
        "total_universe": debug.get("total_universe_tickers", 0),
        "pass_count": len(passes),
        "error_count": len(scan_errors),
        "passes": passes,
        "errors": scan_errors,
    }

    print("\n----- DAILY SCAN SUMMARY -----")
    print(f"Universe      : {summary['total_universe']}")
    print(f"Total Scanned : {summary['total_scanned']}")
    print(f"Total PASS    : {len(passes)}")
    print(f"Total Errors  : {len(scan_errors)}")
    for p in passes:
        print(f"  PASS: {p}")

    if passes:
        # Keep the SMS under ~160 chars; show up to 5 tickers then a count
        MAX_IN_MSG = 5
        shown = passes[:MAX_IN_MSG]
        remainder = len(passes) - len(shown)
        ticker_str = ", ".join(shown) + (f" +{remainder} more" if remainder else "")
        msg = f"ENGINE SCAN {today}: {len(passes)} candidate(s): {ticker_str}"
        send_text(msg)

    return summary


if __name__ == "__main__":
    main()




