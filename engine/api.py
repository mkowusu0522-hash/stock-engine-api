from fastapi import FastAPI
from .__main__ import run

app = FastAPI()

@app.get("/stock/{ticker}")
def stock_judgment(ticker: str):
    result = run(ticker.upper())
    return result

@app.get("/scan")
def scan_market():
    from .scan import read_tickers, TICKERS_FILE, scan_tickers
    tickers = read_tickers(TICKERS_FILE)
    return scan_tickers(tickers)

@app.get("/allocations")
def allocations():
    from .scan import read_tickers, TICKERS_FILE, scan_tickers

    tickers = read_tickers(TICKERS_FILE)
    results = scan_tickers(tickers)

    return [
        r for r in results
        if r.get("price_pass")
        and r.get("survivability_pass")
        and r.get("economic_quality_pass")
    ]




