from __future__ import annotations

from typing import Protocol


class Publisher(Protocol):
    def publish(self, text: str) -> str | None:
        """Publish content and optionally return a provider URI/ID."""
