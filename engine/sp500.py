import pandas as pd

def fetch_sp500_tickers():
    # Public CSV of S&P 500 constituents (no HTML parsing needed)
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url)
    tickers = df["Symbol"].astype(str).str.upper().tolist()
    tickers = [t.replace(".", "-") for t in tickers]  # BRK.B -> BRK-B for FMP
    return tickers
