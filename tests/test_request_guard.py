from __future__ import annotations

import pytest

from temp_inversion_bot.data_sources.base import DataFetchError
from temp_inversion_bot.data_sources.guard import RequestSafetyGuard


def test_guard_enforces_max_requests_per_minute() -> None:
    guard = RequestSafetyGuard(
        source_name="test-source",
        min_request_interval_s=0,
        max_requests_per_minute=1,
        circuit_failure_threshold=5,
        circuit_cooldown_s=60,
    )

    guard.before_request()
    with pytest.raises(DataFetchError):
        guard.before_request()


def test_guard_opens_circuit_after_repeated_failures() -> None:
    guard = RequestSafetyGuard(
        source_name="test-source",
        min_request_interval_s=0,
        max_requests_per_minute=10,
        circuit_failure_threshold=2,
        circuit_cooldown_s=60,
    )

    guard.record_failure(RuntimeError("boom1"))
    guard.record_failure(RuntimeError("boom2"))

    with pytest.raises(DataFetchError):
        guard.before_request()


def test_guard_success_resets_failure_counter() -> None:
    guard = RequestSafetyGuard(
        source_name="test-source",
        min_request_interval_s=0,
        max_requests_per_minute=10,
        circuit_failure_threshold=2,
        circuit_cooldown_s=60,
    )

    guard.record_failure(RuntimeError("boom"))
    guard.record_success()
    guard.record_failure(RuntimeError("boom"))

    # No circuit yet because failures were reset by success.
    guard.before_request()
