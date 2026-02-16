from __future__ import annotations

from datetime import UTC, datetime

import pytest

from temp_inversion_bot.data_sources.base import DataFetchError
from temp_inversion_bot.data_sources.open_meteo import OpenMeteoProfileSource
from temp_inversion_bot.stations import STATIONS


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._payload


def test_fetch_station_profile_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "elevation": 204,
        "hourly": {
            "time": ["2026-02-16T12:00", "2026-02-16T13:00"],
            "temperature_2m": [-2.5, -2.0],
            "wind_speed_10m": [8.0, 7.0],
            "wind_direction_10m": [100, 90],
            "temperature_1000hPa": [-1.7, -1.1],
            "temperature_975hPa": [-1.0, -0.4],
            "temperature_950hPa": [-0.5, 0.0],
            "temperature_925hPa": [0.2, 0.8],
            "temperature_900hPa": [0.1, 0.3],
            "temperature_850hPa": [-1.2, -1.0],
            "geopotential_height_1000hPa": [240, 240],
            "geopotential_height_975hPa": [330, 330],
            "geopotential_height_950hPa": [520, 520],
            "geopotential_height_925hPa": [780, 780],
            "geopotential_height_900hPa": [1030, 1030],
            "geopotential_height_850hPa": [1500, 1500],
        },
    }

    def fake_get(url, params, timeout):  # noqa: ANN001
        assert "hourly" in params
        return FakeResponse(payload)

    monkeypatch.setattr("temp_inversion_bot.data_sources.open_meteo.httpx.get", fake_get)

    source = OpenMeteoProfileSource(base_url="https://example.test", model="hrrr_conus")
    profile = source.fetch_station_profile(STATIONS["KORD"], datetime(2026, 2, 16, 13, 10, tzinfo=UTC))

    assert profile.station_id == "KORD"
    assert profile.is_high_res is True
    assert profile.source == "open-meteo:hrrr_conus"
    assert len(profile.points) >= 4
    assert profile.surface_wind_kt == 7.0


def test_fetch_station_profile_raises_for_missing_hourly(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"hourly": {}}

    monkeypatch.setattr(
        "temp_inversion_bot.data_sources.open_meteo.httpx.get",
        lambda url, params, timeout: FakeResponse(payload),
    )

    source = OpenMeteoProfileSource(base_url="https://example.test", model="hrrr_conus")
    with pytest.raises(DataFetchError):
        source.fetch_station_profile(STATIONS["KORD"], datetime(2026, 2, 16, 13, 0, tzinfo=UTC))
