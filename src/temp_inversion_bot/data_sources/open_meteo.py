from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from temp_inversion_bot.data_sources.base import DataFetchError
from temp_inversion_bot.domain import StationProfile, VerticalPoint
from temp_inversion_bot.retry import retry_call
from temp_inversion_bot.stations import StationDefinition

_PRESSURE_LEVELS = (1000, 975, 950, 925, 900, 850)
_DEFAULT_PRESSURE_HEIGHT_MSL_M = {
    1000: 110.0,
    975: 320.0,
    950: 540.0,
    925: 760.0,
    900: 1000.0,
    850: 1460.0,
}


class OpenMeteoProfileSource:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_s: float = 15.0,
        attempts: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s
        self._attempts = attempts
        self._logger = logger or logging.getLogger(__name__)

    def fetch_station_profile(self, station: StationDefinition, target_time_utc: datetime) -> StationProfile:
        if target_time_utc.tzinfo is None:
            raise ValueError("target_time_utc must be timezone-aware")

        payload = retry_call(
            lambda: self._request_payload(station),
            attempts=self._attempts,
            exceptions=(httpx.HTTPError, DataFetchError),
            logger=self._logger,
            context=f"open-meteo fetch for {station.station_id}",
        )
        return self._payload_to_profile(payload, station, target_time_utc)

    def _request_payload(self, station: StationDefinition) -> dict:
        hourly_fields = [
            "temperature_2m",
            "wind_speed_10m",
            "wind_direction_10m",
        ]
        for pressure in _PRESSURE_LEVELS:
            hourly_fields.append(f"temperature_{pressure}hPa")
            hourly_fields.append(f"geopotential_height_{pressure}hPa")

        params = {
            "latitude": station.latitude,
            "longitude": station.longitude,
            "hourly": ",".join(hourly_fields),
            "timezone": "UTC",
            "forecast_days": 2,
            "models": self._model,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kn",
        }

        response = httpx.get(self._base_url, params=params, timeout=self._timeout_s)
        response.raise_for_status()
        data = response.json()

        if "hourly" not in data or "time" not in data["hourly"]:
            raise DataFetchError("Open-Meteo response missing hourly time data")

        return data

    def _payload_to_profile(
        self,
        payload: dict,
        station: StationDefinition,
        target_time_utc: datetime,
    ) -> StationProfile:
        hourly = payload["hourly"]
        times = [datetime.fromisoformat(raw).replace(tzinfo=UTC) for raw in hourly["time"]]
        index = _nearest_time_index(times, target_time_utc.astimezone(UTC))
        ts_utc = times[index]

        points: list[VerticalPoint] = []

        surface_temp = _series_value(hourly, "temperature_2m", index)
        if surface_temp is not None:
            points.append(VerticalPoint(0.0, surface_temp))

        elevation_m = float(payload.get("elevation", station.elevation_m))
        for pressure in _PRESSURE_LEVELS:
            temp_c = _series_value(hourly, f"temperature_{pressure}hPa", index)
            if temp_c is None:
                continue

            gph_msl = _series_value(hourly, f"geopotential_height_{pressure}hPa", index)
            if gph_msl is None:
                gph_msl = _DEFAULT_PRESSURE_HEIGHT_MSL_M[pressure]

            z_agl_m = max(0.0, gph_msl - elevation_m)
            points.append(VerticalPoint(z_agl_m, temp_c))

        if len(points) < 2:
            raise DataFetchError(f"Not enough profile levels for {station.station_id}")

        has_low_level = any(point.z_agl_m <= 300.0 for point in points)
        source = f"open-meteo:{self._model}"
        return StationProfile(
            station_id=station.station_id,
            timestamp_utc=ts_utc,
            points=points,
            source=source,
            is_high_res=_is_high_res_model(self._model),
            from_pressure_levels=True,
            missing_low_level_values=not has_low_level,
            surface_wind_kt=_series_value(hourly, "wind_speed_10m", index),
            surface_wind_dir_deg=_series_value(hourly, "wind_direction_10m", index),
        )


def _series_value(payload: dict, key: str, index: int) -> float | None:
    series = payload.get(key)
    if not isinstance(series, list) or index >= len(series):
        return None
    value = series[index]
    if value is None:
        return None
    return float(value)


def _nearest_time_index(times: list[datetime], target: datetime) -> int:
    if not times:
        raise DataFetchError("No time values in response")

    return min(range(len(times)), key=lambda idx: abs((times[idx] - target).total_seconds()))


def _is_high_res_model(model: str) -> bool:
    lowered = model.strip().lower()
    return "hrrr" in lowered or lowered in {"icon-d2", "meteofrance_arpege"}
