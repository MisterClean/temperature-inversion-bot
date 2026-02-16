from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
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

    def latest_post(self) -> dict | None:
        state = self._read_state()
        latest: tuple[datetime, dict] | None = None
        for day_state in state["days"].values():
            for post in day_state.get("posts", []):
                timestamp_raw = post.get("timestamp_utc")
                if not timestamp_raw:
                    continue
                parsed = _parse_timestamp(timestamp_raw)
                if parsed is None:
                    continue
                if latest is None or parsed > latest[0]:
                    latest = (parsed, post)

        return latest[1] if latest is not None else None

    def has_post_with_text_since(self, text: str, since_utc: datetime) -> bool:
        state = self._read_state()
        since = since_utc.astimezone(UTC)
        for day_state in state["days"].values():
            for post in day_state.get("posts", []):
                if post.get("text") != text:
                    continue
                timestamp_raw = post.get("timestamp_utc")
                if not timestamp_raw:
                    continue
                timestamp = _parse_timestamp(timestamp_raw)
                if timestamp is not None and timestamp >= since:
                    return True
        return False

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


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
