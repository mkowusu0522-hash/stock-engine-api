from fastapi import FastAPI
from .__main__ import run

app = FastAPI()

@app.get("/stock/{ticker}")
def stock_judgment(ticker: str):
    result = run(ticker.upper())
    return result