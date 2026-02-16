from __future__ import annotations

import logging
import time
from collections import deque

from temp_inversion_bot.data_sources.base import DataFetchError


class RequestSafetyGuard:
    """Protects upstream providers from bursty retries and runaway loops."""

    def __init__(
        self,
        *,
        source_name: str,
        min_request_interval_s: float,
        max_requests_per_minute: int,
        circuit_failure_threshold: int,
        circuit_cooldown_s: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._source_name = source_name
        self._min_request_interval_s = max(0.0, float(min_request_interval_s))
        self._max_requests_per_minute = max(1, int(max_requests_per_minute))
        self._circuit_failure_threshold = max(1, int(circuit_failure_threshold))
        self._circuit_cooldown_s = max(1, int(circuit_cooldown_s))
        self._logger = logger or logging.getLogger(__name__)

        self._request_times: deque[float] = deque()
        self._last_request_at: float | None = None
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def before_request(self) -> None:
        now = time.monotonic()
        if now < self._circuit_open_until:
            remaining = self._circuit_open_until - now
            raise DataFetchError(
                f"{self._source_name} circuit breaker open for {remaining:.1f}s; skipping upstream request"
            )

        self._prune_request_window(now)
        if len(self._request_times) >= self._max_requests_per_minute:
            raise DataFetchError(
                f"{self._source_name} rate limit reached ({self._max_requests_per_minute}/min); "
                "skipping upstream request"
            )

        if self._last_request_at is not None and self._min_request_interval_s > 0:
            sleep_s = self._min_request_interval_s - (now - self._last_request_at)
            if sleep_s > 0:
                time.sleep(sleep_s)
                now = time.monotonic()

        self._request_times.append(now)
        self._last_request_at = now

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self, error: Exception) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._circuit_failure_threshold:
            return

        self._circuit_open_until = time.monotonic() + self._circuit_cooldown_s
        self._consecutive_failures = 0
        self._logger.warning(
            "%s circuit breaker opened for %ss after repeated failures: %s",
            self._source_name,
            self._circuit_cooldown_s,
            error,
        )

    def _prune_request_window(self, now: float) -> None:
        window_start = now - 60.0
        while self._request_times and self._request_times[0] < window_start:
            self._request_times.popleft()
