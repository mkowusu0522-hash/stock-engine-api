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

