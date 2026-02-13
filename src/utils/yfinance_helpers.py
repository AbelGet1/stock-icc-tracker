"""
Centralized yfinance data fetching with retry logic and rate limiting.

All yfinance API calls should go through this module to prevent rate limiting
issues and provide consistent error handling.
"""

import logging
import random
import time
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_DELAY_BETWEEN = 0.5


def fetch_ticker_data(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
) -> Optional[pd.DataFrame]:
    """
    Fetch yfinance data for a single ticker with exponential backoff.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        period: Data period (e.g., "1y", "2y", "3mo")
        interval: Data interval (e.g., "1d", "1h")
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        DataFrame with OHLCV data, or None on permanent failure.
    """
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)

            if data is not None and not data.empty:
                return data

            logger.warning(f"Empty data returned for {symbol} (attempt {attempt + 1}/{max_retries})")

        except Exception as e:
            logger.warning(
                f"Error fetching {symbol} (attempt {attempt + 1}/{max_retries}): {e}"
            )

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.info(f"Retrying {symbol} in {delay:.1f}s...")
            time.sleep(delay)

    logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
    return None


def fetch_multiple_tickers(
    symbols: List[str],
    period: str = "1y",
    interval: str = "1d",
    delay_between: float = DEFAULT_DELAY_BETWEEN,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Fetch data for multiple symbols with inter-request delays.

    Args:
        symbols: List of stock ticker symbols
        period: Data period
        interval: Data interval
        delay_between: Seconds to wait between requests
        max_retries: Maximum retries per symbol

    Returns:
        Dict mapping symbol to DataFrame (or None on failure).
    """
    results = {}

    for i, symbol in enumerate(symbols):
        if i > 0:
            time.sleep(delay_between)

        results[symbol] = fetch_ticker_data(
            symbol,
            period=period,
            interval=interval,
            max_retries=max_retries,
        )

    return results
