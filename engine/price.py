# price.py
from __future__ import annotations

import os
import requests


BASE = "https://financialmodelingprep.com/stable"
API_KEY = os.getenv("FMP_API_KEY")


def _key() -> str:
    if not API_KEY:
        raise ValueError("FMP_API_KEY environment variable is not set.")
    return API_KEY


def _get(path: str, params: dict) -> list | dict:
    params = dict(params or {})
    params["apikey"] = _key()
    r = requests.get(f"{BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_quote(ticker: str) -> dict:
    # stable quote endpoint
    j = _get("/quote", {"symbol": ticker})
    if not j:
        raise ValueError(f"No quote data returned for {ticker}.")
    return j[0]


def fetch_key_metrics_ttm(ticker: str) -> dict:
    # stable key-metrics-ttm endpoint
    j = _get("/key-metrics-ttm", {"symbol": ticker})
    if not j:
        raise ValueError(f"No key-metrics-ttm data returned for {ticker}.")
    return j[0]


def price_snapshot(ticker: str) -> dict:
    """
    Best-effort price snapshot from /stable endpoints.
    """
    try:
        q = fetch_quote(ticker)
        km = fetch_key_metrics_ttm(ticker)
        return {
            "price_ok": True,
            "price": q.get("price"),
            "market_cap": q.get("marketCap") or q.get("mktCap"),
            "enterprise_value_ttm": km.get("enterpriseValueTTM"),
            "free_cash_flow_ttm": km.get("freeCashFlowTTM"),
        }
    except Exception as e:
        return {
            "price_ok": False,
            "price_error": str(e),
            "price": None,
            "market_cap": None,
            "enterprise_value_ttm": None,
            "free_cash_flow_ttm": None,
        }
