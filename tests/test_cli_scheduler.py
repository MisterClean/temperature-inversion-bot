from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from temp_inversion_bot.cli import _auto_slot
from temp_inversion_bot.scheduler import _parse_hhmm


def test_auto_slot_morning_before_afternoon_time() -> None:
    now = datetime(2026, 2, 16, 11, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert _auto_slot(now, "07:30", "15:30") == "morning"


def test_auto_slot_afternoon_after_afternoon_time() -> None:
    now = datetime(2026, 2, 16, 16, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert _auto_slot(now, "07:30", "15:30") == "afternoon"


def test_parse_hhmm() -> None:
    assert _parse_hhmm("07:30") == (7, 30)
