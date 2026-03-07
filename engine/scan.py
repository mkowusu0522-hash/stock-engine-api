from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path

from .__main__ import run

ENGINE_DIR = Path(__file__).resolve().parent
TICKERS_FILE = ENGINE_DIR / "tickers.txt"
PORTFOLIO_LOG = ENGINE_DIR / "portfolio_log.csv"
ERROR_LOG = ENGINE_DIR / "scan_errors.csv"

import pandas as pd

def load_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)[0]
    return table["Symbol"].tolist()


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

def main() -> None:
    tickers = [t.replace(".", "-") for t in load_sp500()]

    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ensure_csv(
        PORTFOLIO_LOG,
        [
            "date", "timestamp", "ticker",
            "decision_alloc", "decision_stable", "price_pass", "judgement veridct",
            "price", "nopat_yield_on_ev"
        ],
    )

    ensure_csv(ERROR_LOG, ["date", "timestamp", "ticker", "error"])

    total_scanned = 0
    passes = []

    for t in tickers:
        total_scanned += 1
        try:
            out = run(t)
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
        except Exception as e:
            append_row(
                ERROR_LOG,
                {
                    "date": today,
                    "timestamp": ts,
                    "ticker": t,
                    "error": str(e),
                },
            )

    print("\n----- DAILY SCAN SUMMARY -----")
    print(f"Total Scanned: {total_scanned}")
    print(f"Total PASS (decision_alloc): {len(passes)}")

    if passes:
        print("Tickers:")
        for p in passes:
            print(f" - {p}")
    else:
        print("No allocation candidates today.")


if __name__ == "__main__":
    main()


