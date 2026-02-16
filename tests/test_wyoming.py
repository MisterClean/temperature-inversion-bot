from __future__ import annotations

from datetime import UTC, datetime

import pytest

from temp_inversion_bot.data_sources.base import DataFetchError
from temp_inversion_bot.data_sources.wyoming import WyomingSoundingProfileSource
from temp_inversion_bot.stations import STATIONS


class FakeResponse:
    def __init__(self, text: str, *, status_ok: bool = True) -> None:
        self.text = text
        self._status_ok = status_ok

    def raise_for_status(self) -> None:
        if not self._status_ok:
            raise RuntimeError("status error")


def _sample_csv() -> str:
    return "\n".join(
        [
            "time,longitude,latitude,pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,ice point temperature_C,relative humidity_%,humidity wrt ice_%,mixing ratio_g/kg,wind direction_degree,wind speed_m/s",
            "2026-02-16 11:02:45,-89.3368,40.1514,994.1,179,1.1,1.1,1.1,100,100,4.17,180,2.1",
            "2026-02-16 11:02:46,-89.3361,40.1517,990.9,205,1.4,1.1,1.1,97,97,4.17,241,9.4",
            "2026-02-16 11:02:47,-89.3354,40.1519,987.7,231,1.8,1.0,1.0,95,95,4.17,241,9.4",
            "2026-02-16 11:02:48,-89.3348,40.1522,984.6,257,2.1,1.0,1.0,92,92,4.16,241,9.4",
        ]
    )


def test_fetch_station_profile_parses_wyoming_csv(monkeypatch) -> None:  # noqa: ANN001
    def fake_get(url, params, timeout):  # noqa: ANN001
        assert params["id"] == "74560"
        assert params["type"] == "TEXT:CSV"
        return FakeResponse(_sample_csv())

    monkeypatch.setattr("temp_inversion_bot.data_sources.wyoming.httpx.get", fake_get)

    source = WyomingSoundingProfileSource(base_url="https://weather.uwyo.edu/wsgi/sounding", src="BUFR")
    profile = source.fetch_station_profile(STATIONS["74560"], datetime(2026, 2, 16, 13, 0, tzinfo=UTC))

    assert profile.station_id == "74560"
    assert profile.source == "uwyo:bufr"
    assert profile.from_pressure_levels is False
    assert profile.points[0].z_agl_m == 0.0
    assert round(profile.points[-1].z_agl_m, 1) == 78.0
    assert profile.surface_wind_dir_deg == 180.0
    assert profile.surface_wind_kt is not None and profile.surface_wind_kt > 4.0


def test_fetch_station_profile_tries_previous_cycle_when_current_unusable(monkeypatch) -> None:  # noqa: ANN001
    calls: list[str] = []

    def fake_get(url, params, timeout):  # noqa: ANN001
        calls.append(params["datetime"])
        if len(calls) == 1:
            return FakeResponse("<html>No data</html>")
        return FakeResponse(_sample_csv())

    monkeypatch.setattr("temp_inversion_bot.data_sources.wyoming.httpx.get", fake_get)

    source = WyomingSoundingProfileSource(base_url="https://weather.uwyo.edu/wsgi/sounding", src="BUFR", attempts=1)
    profile = source.fetch_station_profile(STATIONS["74560"], datetime(2026, 2, 16, 13, 0, tzinfo=UTC))

    assert profile.station_id == "74560"
    assert len(calls) >= 2
    assert calls[0].endswith("12:00:00")
    assert calls[1].endswith("00:00:00")


def test_fetch_station_profile_raises_when_no_usable_csv(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "temp_inversion_bot.data_sources.wyoming.httpx.get",
        lambda url, params, timeout: FakeResponse("<html>bad</html>"),
    )

    source = WyomingSoundingProfileSource(base_url="https://weather.uwyo.edu/wsgi/sounding", src="BUFR", attempts=1)
    with pytest.raises(DataFetchError):
        source.fetch_station_profile(STATIONS["74560"], datetime(2026, 2, 16, 13, 0, tzinfo=UTC))
