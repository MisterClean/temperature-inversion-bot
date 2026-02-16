from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryError(RuntimeError):
    pass


def retry_call(
    func: Callable[[], T],
    *,
    attempts: int,
    initial_delay_s: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: logging.Logger | None = None,
    context: str = "operation",
) -> T:
    delay = initial_delay_s
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except exceptions as exc:
            last_error = exc
            if attempt == attempts:
                break

            if logger is not None:
                logger.warning(
                    "%s failed on attempt %s/%s: %s",
                    context,
                    attempt,
                    attempts,
                    exc,
                )
            time.sleep(delay)
            delay *= backoff_factor

    raise RetryError(f"{context} failed after {attempts} attempts") from last_error
