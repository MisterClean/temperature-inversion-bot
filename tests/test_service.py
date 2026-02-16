from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from temp_inversion_bot.config import BotConfig
from temp_inversion_bot.domain import StationProfile, VerticalPoint
from temp_inversion_bot.service import InversionBotService
from temp_inversion_bot.state import JsonStateStore
from temp_inversion_bot.stations import STATIONS


class StubSource:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_station_profile(self, station, target_time_utc):  # noqa: ANN001
        self.calls.append(station.station_id)
        if station.station_id == "KORD":
            return StationProfile(
                station_id="KORD",
                timestamp_utc=target_time_utc,
                points=[
                    VerticalPoint(0.0, -2.0),
                    VerticalPoint(100.0, -1.0),
                    VerticalPoint(200.0, 0.2),
                    VerticalPoint(350.0, -0.2),
                ],
                source="stub",
                is_high_res=True,
                from_pressure_levels=False,
                missing_low_level_values=False,
                surface_wind_kt=6.0,
                surface_wind_dir_deg=80.0,
            )

        return StationProfile(
            station_id=station.station_id,
            timestamp_utc=target_time_utc,
            points=[
                VerticalPoint(0.0, -2.5),
                VerticalPoint(100.0, -1.3),
                VerticalPoint(200.0, -0.1),
                VerticalPoint(350.0, -0.6),
            ],
            source="stub",
            is_high_res=True,
            from_pressure_levels=False,
            missing_low_level_values=False,
            surface_wind_kt=8.0,
            surface_wind_dir_deg=90.0,
        )


class StubPublisher:
    def __init__(self) -> None:
        self.posts: list[str] = []

    def publish(self, text: str) -> str | None:
        self.posts.append(text)
        return "dry-run://test"


def _config(state_file: Path) -> BotConfig:
    return BotConfig(
        timezone="America/Chicago",
        primary_station="KORD",
        secondary_station="KMDW",
        post_time_morning="07:30",
        post_time_afternoon="15:30",
        dry_run=True,
        max_posts_per_day=2,
        afternoon_confidence_threshold=0.95,
        state_file=state_file,
        open_meteo_url="https://api.open-meteo.com/v1/forecast",
        open_meteo_model="hrrr_conus",
        bsky_handle=None,
        bsky_app_password=None,
    )


def test_run_slot_posts_once_and_skips_duplicate_morning(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    service = InversionBotService(
        config=_config(state_file),
        source=StubSource(),
        publisher=StubPublisher(),
        state_store=JsonStateStore(state_file),
    )

    first = service.run_slot("morning", now=datetime(2026, 2, 16, 13, 30, tzinfo=UTC))
    second = service.run_slot("morning", now=datetime(2026, 2, 16, 14, 30, tzinfo=UTC))

    assert first.posted is True
    assert second.posted is False
    assert second.reason == "morning_already_posted"


def test_afternoon_only_posts_when_status_changes_and_confidence_low(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    source = StubSource()
    publisher = StubPublisher()
    service = InversionBotService(
        config=_config(state_file),
        source=source,
        publisher=publisher,
        state_store=JsonStateStore(state_file),
    )

    morning = service.run_slot("morning", now=datetime(2026, 2, 16, 13, 30, tzinfo=UTC))
    assert morning.posted is True

    afternoon = service.run_slot("afternoon", now=datetime(2026, 2, 16, 21, 30, tzinfo=UTC))
    assert afternoon.posted is False
    assert afternoon.reason == "afternoon_status_unchanged"

    assert len(publisher.posts) == 1


def test_state_store_counts_posts(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    store = JsonStateStore(state_file)

    assert store.post_count(datetime(2026, 2, 16, tzinfo=UTC).date()) == 0

    source = StubSource()
    publisher = StubPublisher()
    service = InversionBotService(
        config=_config(state_file),
        source=source,
        publisher=publisher,
        state_store=store,
    )

    service.run_slot("morning", now=datetime(2026, 2, 16, 13, 30, tzinfo=UTC))
    assert store.post_count(datetime(2026, 2, 16, tzinfo=UTC).date()) == 1
    assert store.has_morning_post(datetime(2026, 2, 16, tzinfo=UTC).date()) is True

    assert "KORD" in STATIONS
