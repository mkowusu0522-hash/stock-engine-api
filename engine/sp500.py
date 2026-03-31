"""
sp500.py — Deprecated.

Use engine.universe.get_engine_universe() instead.

This module previously fetched S&P 500 tickers via web scraping (datahub.io).
It is retained here to avoid breaking any external callers, but now delegates
to get_engine_universe() which reads from the local sp500_tickers.json file
with no runtime scraping.
"""

import warnings


def fetch_sp500_tickers() -> list[str]:
    """
    Deprecated: use get_engine_universe() from engine.universe instead.
    Retained for backward compatibility only.
    """
    warnings.warn(
        "fetch_sp500_tickers() is deprecated. "
        "Use engine.universe.get_engine_universe() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .universe import get_engine_universe
    return get_engine_universe()
