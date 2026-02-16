from __future__ import annotations

import logging
from datetime import UTC, datetime


class DryRunPublisher:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def publish(self, text: str) -> str | None:
        token = datetime.now(UTC).isoformat()
        uri = f"dry-run://{token}"
        self._logger.info("DRY_RUN publish: %s", text)
        return uri
