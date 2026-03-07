from fastapi import FastAPI
from .__main__ import run

app = FastAPI()

@app.get("/stock/{ticker}")
def stock_judgment(ticker: str):
    return run(ticker.upper())

@app.get("/scan")
def scan_market():
    from .scan import main
    return main()

@app.get("/allocations")
def allocations():
    from .scan import load_sp500, scan_tickers

    tickers = [t.replace(".", "-") for t in load_sp500()]
    results = scan_tickers(tickers)

    return [
        r for r in results
        if r.get("price_pass")
        and r.get("survivability_pass")
        and r.get("economic_quality_pass")
    ]
