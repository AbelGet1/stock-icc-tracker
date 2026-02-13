"""
DynamoDB-backed rate limiter with in-memory fallback.

Uses DynamoDB for persistent, cross-instance rate limiting.
Falls back to in-memory if DynamoDB is unavailable.
"""

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

RATE_LIMIT_TABLE_NAME = os.environ.get("RATE_LIMIT_TABLE_NAME", "stockscout-rate-limits")


class RateLimiter:
    """
    Rate limiter with DynamoDB backend and in-memory fallback.

    DynamoDB uses fixed-window counting with atomic increments and TTL cleanup.
    Falls back to in-memory sliding window if DynamoDB is unavailable.
    """

    def __init__(
        self,
        requests_per_window: int = 100,
        window_seconds: int = 3600,
        daily_limit: int = 500,
        dynamodb_resource=None,
        table_name: Optional[str] = None,
    ):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.daily_limit = daily_limit
        self.table_name = table_name or RATE_LIMIT_TABLE_NAME
        self.use_dynamodb = False
        self._dynamodb_table = None

        # In-memory fallback
        self._memory_store: Dict[str, list] = defaultdict(list)
        self._daily_count = {"count": 0, "date": datetime.now().date()}

        # Try to connect to DynamoDB
        if dynamodb_resource is not None:
            try:
                self._dynamodb_table = dynamodb_resource.Table(self.table_name)
                self._dynamodb_table.table_status
                self.use_dynamodb = True
                logger.info(f"DynamoDB rate limiter connected: {self.table_name}")
            except Exception as e:
                logger.warning(
                    f"DynamoDB rate limiter unavailable, using in-memory fallback: {e}"
                )
                self.use_dynamodb = False

    def check_rate_limit(self, client_ip: str) -> bool:
        """Check per-IP rate limit. Returns True if request is allowed."""
        if self.use_dynamodb:
            try:
                return self._check_rate_limit_dynamodb(client_ip)
            except Exception as e:
                logger.warning(f"DynamoDB rate check failed, falling back to memory: {e}")
                return self._check_rate_limit_memory(client_ip)
        return self._check_rate_limit_memory(client_ip)

    def check_daily_limit(self) -> bool:
        """Check global daily limit. Returns True if request is allowed."""
        if self.use_dynamodb:
            try:
                return self._check_daily_limit_dynamodb()
            except Exception as e:
                logger.warning(f"DynamoDB daily check failed, falling back to memory: {e}")
                return self._check_daily_limit_memory()
        return self._check_daily_limit_memory()

    # ---- DynamoDB implementations ----

    def _check_rate_limit_dynamodb(self, client_ip: str) -> bool:
        """Fixed-window rate limit check using DynamoDB atomic counter."""
        now = int(time.time())
        window_key = now // self.window_seconds
        item_key = f"ip#{client_ip}#{window_key}"
        ttl = now + self.window_seconds + 60  # window + 1 min buffer

        response = self._dynamodb_table.update_item(
            Key={"pk": item_key},
            UpdateExpression="SET request_count = if_not_exists(request_count, :zero) + :inc, #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":inc": 1,
                ":ttl": ttl,
            },
            ReturnValues="UPDATED_NEW",
        )

        count = int(response["Attributes"]["request_count"])
        return count <= self.requests_per_window

    def _check_daily_limit_dynamodb(self) -> bool:
        """Daily global limit check using DynamoDB atomic counter."""
        today = datetime.now().strftime("%Y-%m-%d")
        item_key = f"daily#{today}"
        now = int(time.time())
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1, hours=1)
        ttl = int(tomorrow.timestamp())

        response = self._dynamodb_table.update_item(
            Key={"pk": item_key},
            UpdateExpression="SET request_count = if_not_exists(request_count, :zero) + :inc, #ttl = :ttl",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":inc": 1,
                ":ttl": ttl,
            },
            ReturnValues="UPDATED_NEW",
        )

        count = int(response["Attributes"]["request_count"])
        return count <= self.daily_limit

    # ---- In-memory fallback implementations ----

    def _check_rate_limit_memory(self, client_ip: str) -> bool:
        """In-memory sliding window fallback."""
        now = time.time()
        window_start = now - self.window_seconds
        self._memory_store[client_ip] = [
            t for t in self._memory_store[client_ip] if t > window_start
        ]
        if len(self._memory_store[client_ip]) >= self.requests_per_window:
            return False
        self._memory_store[client_ip].append(now)
        return True

    def _check_daily_limit_memory(self) -> bool:
        """In-memory daily counter fallback."""
        today = datetime.now().date()
        if self._daily_count["date"] != today:
            self._daily_count["count"] = 0
            self._daily_count["date"] = today
        if self._daily_count["count"] >= self.daily_limit:
            return False
        self._daily_count["count"] += 1
        return True
