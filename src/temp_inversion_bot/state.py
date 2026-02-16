from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from temp_inversion_bot.domain import CombinedAnalysis


@dataclass(slots=True)
class PostRecord:
    timestamp_utc: str
    slot: str
    status: str
    confidence: float
    uri: str | None
    text: str


class JsonStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def post_count(self, day: date) -> int:
        state = self._read_state()
        day_state = state["days"].get(day.isoformat(), {})
        return len(day_state.get("posts", []))

    def has_morning_post(self, day: date) -> bool:
        state = self._read_state()
        day_state = state["days"].get(day.isoformat(), {})
        return "morning" in day_state

    def morning_summary(self, day: date) -> dict | None:
        state = self._read_state()
        day_state = state["days"].get(day.isoformat(), {})
        return day_state.get("morning")

    def record_post(
        self,
        *,
        day: date,
        slot: str,
        analysis: CombinedAnalysis,
        text: str,
        uri: str | None,
        posted_at_utc: datetime,
    ) -> None:
        state = self._read_state()
        day_key = day.isoformat()
        day_state = state["days"].setdefault(day_key, {})
        posts = day_state.setdefault("posts", [])

        record = PostRecord(
            timestamp_utc=posted_at_utc.isoformat(),
            slot=slot,
            status=analysis.status.value,
            confidence=analysis.confidence,
            uri=uri,
            text=text,
        )
        posts.append(asdict(record))

        if slot == "morning":
            day_state["morning"] = {
                "status": analysis.status.value,
                "confidence": analysis.confidence,
            }

        self._write_state(state)

    def _read_state(self) -> dict:
        if not self._path.exists():
            return {"days": {}}

        with self._path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_state(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
