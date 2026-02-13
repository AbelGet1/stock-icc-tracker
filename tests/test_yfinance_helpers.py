"""Tests for yfinance helper module with retry and rate limiting."""

import time
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.utils.yfinance_helpers import fetch_ticker_data, fetch_multiple_tickers


@pytest.fixture
def sample_dataframe():
    """Create a sample stock data DataFrame."""
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [103.0, 104.0, 105.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000000, 1100000, 1200000],
        },
        index=pd.date_range("2024-01-01", periods=3),
    )


class TestFetchTickerData:
    @patch("src.utils.yfinance_helpers.yf")
    def test_success(self, mock_yf, sample_dataframe):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_dataframe
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_ticker_data("AAPL", period="1y")

        assert result is not None
        assert len(result) == 3
        mock_yf.Ticker.assert_called_once_with("AAPL")

    @patch("src.utils.yfinance_helpers.time.sleep")
    @patch("src.utils.yfinance_helpers.yf")
    def test_retry_on_error(self, mock_yf, mock_sleep, sample_dataframe):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = [
            ConnectionError("rate limited"),
            sample_dataframe,
        ]
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_ticker_data("AAPL", max_retries=3, base_delay=0.01)

        assert result is not None
        assert mock_ticker.history.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.utils.yfinance_helpers.time.sleep")
    @patch("src.utils.yfinance_helpers.yf")
    def test_returns_none_after_max_retries(self, mock_yf, mock_sleep):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ConnectionError("always fails")
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_ticker_data("AAPL", max_retries=3, base_delay=0.01)

        assert result is None
        assert mock_ticker.history.call_count == 3

    @patch("src.utils.yfinance_helpers.yf")
    def test_returns_none_on_empty_dataframe(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_ticker_data("INVALID", max_retries=1)

        assert result is None


class TestFetchMultipleTickers:
    @patch("src.utils.yfinance_helpers.time.sleep")
    @patch("src.utils.yfinance_helpers.fetch_ticker_data")
    def test_fetches_all_symbols(self, mock_fetch, mock_sleep, sample_dataframe):
        mock_fetch.return_value = sample_dataframe

        results = fetch_multiple_tickers(
            ["AAPL", "MSFT", "GOOG"], delay_between=0.01
        )

        assert len(results) == 3
        assert all(symbol in results for symbol in ["AAPL", "MSFT", "GOOG"])
        assert mock_fetch.call_count == 3

    @patch("src.utils.yfinance_helpers.time.sleep")
    @patch("src.utils.yfinance_helpers.fetch_ticker_data")
    def test_delays_between_requests(self, mock_fetch, mock_sleep, sample_dataframe):
        mock_fetch.return_value = sample_dataframe

        fetch_multiple_tickers(["AAPL", "MSFT", "GOOG"], delay_between=0.5)

        # Should sleep between requests (not before the first one)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.5)

    @patch("src.utils.yfinance_helpers.time.sleep")
    @patch("src.utils.yfinance_helpers.fetch_ticker_data")
    def test_handles_partial_failures(self, mock_fetch, mock_sleep, sample_dataframe):
        mock_fetch.side_effect = [sample_dataframe, None, sample_dataframe]

        results = fetch_multiple_tickers(["AAPL", "MSFT", "GOOG"], delay_between=0.01)

        assert results["AAPL"] is not None
        assert results["MSFT"] is None
        assert results["GOOG"] is not None
