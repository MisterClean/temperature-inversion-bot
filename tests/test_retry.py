from __future__ import annotations

import pytest

from temp_inversion_bot.retry import RetryError, retry_call


def test_retry_call_eventually_succeeds() -> None:
    state = {"count": 0}

    def flaky() -> str:
        state["count"] += 1
        if state["count"] < 3:
            raise ValueError("transient")
        return "ok"

    result = retry_call(flaky, attempts=3, initial_delay_s=0.0, exceptions=(ValueError,))
    assert result == "ok"
    assert state["count"] == 3


def test_retry_call_raises_after_attempts() -> None:
    def always_fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RetryError):
        retry_call(always_fail, attempts=2, initial_delay_s=0.0, exceptions=(RuntimeError,))
