"""Tests for DynamoDB-backed rate limiter with in-memory fallback."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.utils.rate_limiter import RateLimiter


class TestInMemoryFallback:
    """Test the in-memory fallback rate limiter (no DynamoDB)."""

    def test_allows_requests_under_limit(self):
        limiter = RateLimiter(requests_per_window=5, window_seconds=3600, daily_limit=100)
        for _ in range(5):
            assert limiter.check_rate_limit("192.168.1.1") is True

    def test_blocks_requests_over_limit(self):
        limiter = RateLimiter(requests_per_window=3, window_seconds=3600, daily_limit=100)
        for _ in range(3):
            limiter.check_rate_limit("192.168.1.1")
        assert limiter.check_rate_limit("192.168.1.1") is False

    def test_different_ips_are_independent(self):
        limiter = RateLimiter(requests_per_window=2, window_seconds=3600, daily_limit=100)
        limiter.check_rate_limit("192.168.1.1")
        limiter.check_rate_limit("192.168.1.1")
        # IP 1 is at limit, IP 2 should still be allowed
        assert limiter.check_rate_limit("192.168.1.1") is False
        assert limiter.check_rate_limit("192.168.1.2") is True

    def test_daily_limit_blocks_after_exceeded(self):
        limiter = RateLimiter(requests_per_window=100, window_seconds=3600, daily_limit=3)
        for _ in range(3):
            assert limiter.check_daily_limit() is True
        assert limiter.check_daily_limit() is False

    def test_daily_limit_resets_on_new_day(self):
        limiter = RateLimiter(requests_per_window=100, window_seconds=3600, daily_limit=2)
        limiter.check_daily_limit()
        limiter.check_daily_limit()
        assert limiter.check_daily_limit() is False

        # Simulate day change
        limiter._daily_count["date"] = date(2020, 1, 1)
        assert limiter.check_daily_limit() is True


class TestDynamoDBRateLimiter:
    """Test the DynamoDB-backed rate limiter using mocks."""

    def _make_limiter_with_mock(self, count_to_return=1):
        """Create a limiter with a mocked DynamoDB table."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_table.table_status = "ACTIVE"
        mock_table.update_item.return_value = {
            "Attributes": {"request_count": count_to_return}
        }
        mock_resource.Table.return_value = mock_table

        limiter = RateLimiter(
            requests_per_window=5,
            window_seconds=3600,
            daily_limit=100,
            dynamodb_resource=mock_resource,
            table_name="test-rate-limits",
        )
        return limiter, mock_table

    def test_dynamodb_rate_limit_allowed(self):
        limiter, mock_table = self._make_limiter_with_mock(count_to_return=3)
        assert limiter.use_dynamodb is True
        assert limiter.check_rate_limit("192.168.1.1") is True
        mock_table.update_item.assert_called_once()

    def test_dynamodb_rate_limit_blocked(self):
        limiter, _ = self._make_limiter_with_mock(count_to_return=6)
        assert limiter.check_rate_limit("192.168.1.1") is False

    def test_dynamodb_daily_limit_allowed(self):
        limiter, _ = self._make_limiter_with_mock(count_to_return=50)
        assert limiter.check_daily_limit() is True

    def test_dynamodb_daily_limit_blocked(self):
        limiter, _ = self._make_limiter_with_mock(count_to_return=101)
        assert limiter.check_daily_limit() is False

    def test_fallback_to_memory_on_dynamodb_error(self):
        limiter, mock_table = self._make_limiter_with_mock(count_to_return=1)
        mock_table.update_item.side_effect = Exception("DynamoDB unavailable")

        # Should fall back to in-memory and still allow the request
        assert limiter.check_rate_limit("192.168.1.1") is True

    def test_fallback_daily_on_dynamodb_error(self):
        limiter, mock_table = self._make_limiter_with_mock(count_to_return=1)
        mock_table.update_item.side_effect = Exception("DynamoDB unavailable")

        assert limiter.check_daily_limit() is True

    def test_ttl_is_set_in_update_call(self):
        limiter, mock_table = self._make_limiter_with_mock(count_to_return=1)
        limiter.check_rate_limit("192.168.1.1")

        call_kwargs = mock_table.update_item.call_args[1]
        assert "#ttl" in call_kwargs["ExpressionAttributeNames"]
        assert ":ttl" in call_kwargs["ExpressionAttributeValues"]
        # TTL should be in the future
        ttl_value = call_kwargs["ExpressionAttributeValues"][":ttl"]
        import time
        assert ttl_value > int(time.time())

    def test_dynamodb_unavailable_at_init_uses_memory(self):
        """If DynamoDB table doesn't exist at init, falls back to memory."""
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_table.table_status = property(lambda self: (_ for _ in ()).throw(Exception("table not found")))
        type(mock_table).table_status = property(lambda self: (_ for _ in ()).throw(Exception("not found")))
        mock_resource.Table.return_value = mock_table

        limiter = RateLimiter(
            requests_per_window=5,
            dynamodb_resource=mock_resource,
        )
        assert limiter.use_dynamodb is False
        # Should still work with in-memory
        assert limiter.check_rate_limit("192.168.1.1") is True
