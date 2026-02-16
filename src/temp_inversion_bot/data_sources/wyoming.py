from __future__ import annotations

import csv
import io
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx

from temp_inversion_bot.data_sources.base import DataFetchError
from temp_inversion_bot.data_sources.guard import RequestSafetyGuard
from temp_inversion_bot.domain import StationProfile, VerticalPoint
from temp_inversion_bot.retry import RetryError, retry_call
from temp_inversion_bot.stations import StationDefinition

_MPS_TO_KT = 1.9438444924406


class WyomingSoundingProfileSource:
    def __init__(
        self,
        *,
        base_url: str,
        src: str = "BUFR",
        sounding_type: str = "TEXT:CSV",
        timeout_s: float = 20.0,
        attempts: int = 3,
        cycle_lookback_count: int = 4,
        cache_ttl_s: int = 21600,
        min_request_interval_s: float = 1.0,
        max_requests_per_minute: int = 20,
        circuit_failure_threshold: int = 5,
        circuit_cooldown_s: int = 180,
        logger: logging.Logger | None = None,
    ) -> None:
        self._base_url = base_url
        self._src = src
        self._sounding_type = sounding_type
        self._timeout_s = timeout_s
        self._attempts = attempts
        self._cycle_lookback_count = max(1, cycle_lookback_count)
        self._logger = logger or logging.getLogger(__name__)
        self._cache_ttl_s = max(0, int(cache_ttl_s))
        self._csv_cache: dict[tuple[str, str], tuple[float, str]] = {}
        self._guard = RequestSafetyGuard(
            source_name="wyoming",
            min_request_interval_s=min_request_interval_s,
            max_requests_per_minute=max_requests_per_minute,
            circuit_failure_threshold=circuit_failure_threshold,
            circuit_cooldown_s=circuit_cooldown_s,
            logger=self._logger,
        )

    def fetch_station_profile(self, station: StationDefinition, target_time_utc: datetime) -> StationProfile:
        if target_time_utc.tzinfo is None:
            raise ValueError("target_time_utc must be timezone-aware")

        errors: list[str] = []
        for cycle_time in _candidate_synoptic_cycles(target_time_utc.astimezone(UTC), self._cycle_lookback_count):
            cache_key = (station.station_id, cycle_time.isoformat())
            cached_csv = self._cache_get(cache_key)
            if cached_csv is not None:
                return self._csv_to_profile(cached_csv, station=station, cycle_time_utc=cycle_time)
            try:
                csv_text = retry_call(
                    lambda: self._request_csv_text(station_id=station.station_id, cycle_time_utc=cycle_time),
                    attempts=self._attempts,
                    exceptions=(httpx.HTTPError, DataFetchError),
                    logger=self._logger,
                    context=f"uwyo sounding fetch for {station.station_id} at {cycle_time.isoformat()}",
                )
                self._cache_set(cache_key, csv_text)
                return self._csv_to_profile(csv_text, station=station, cycle_time_utc=cycle_time)
            except RetryError as exc:
                errors.append(f"{cycle_time.isoformat()}: {exc}")

        raise DataFetchError(
            f"Could not fetch usable Wyoming sounding for {station.station_id}. "
            f"Attempts: {' | '.join(errors)}"
        )

    def _request_csv_text(self, *, station_id: str, cycle_time_utc: datetime) -> str:
        self._guard.before_request()
        params = {
            "datetime": cycle_time_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "id": station_id,
            "src": self._src,
            "type": self._sounding_type,
        }
        try:
            response = httpx.get(self._base_url, params=params, timeout=self._timeout_s)
            response.raise_for_status()
            text = response.text
        except Exception as exc:
            self._guard.record_failure(exc)
            raise
        if "pressure_hPa" not in text or "temperature_C" not in text:
            err = DataFetchError("Wyoming response did not contain expected sounding CSV columns")
            self._guard.record_failure(err)
            raise err
        self._guard.record_success()
        return text

    def _csv_to_profile(
        self,
        csv_text: str,
        *,
        station: StationDefinition,
        cycle_time_utc: datetime,
    ) -> StationProfile:
        rows = csv.reader(io.StringIO(csv_text), skipinitialspace=True)
        header = next(rows, None)
        if not header:
            raise DataFetchError("Wyoming CSV missing header")

        normalized = {_normalize_header(name): idx for idx, name in enumerate(header)}

        height_idx = normalized.get("geopotential_height_m")
        temp_idx = normalized.get("temperature_c")
        time_idx = normalized.get("time")
        wind_dir_idx = normalized.get("wind_direction_degree")
        wind_speed_idx = normalized.get("wind_speed_m_s")

        if height_idx is None or temp_idx is None:
            raise DataFetchError("Wyoming CSV missing required height/temperature columns")

        points_raw: list[tuple[float, float]] = []
        observation_time_utc: datetime | None = None
        surface_wind_dir_deg: float | None = None
        surface_wind_kt: float | None = None

        for row in rows:
            if not row:
                continue
            if len(row) <= max(height_idx, temp_idx):
                continue

            height_m = _parse_float(row[height_idx])
            temp_c = _parse_float(row[temp_idx])
            if height_m is None or temp_c is None:
                continue

            points_raw.append((height_m, temp_c))

            if observation_time_utc is None and time_idx is not None and len(row) > time_idx:
                observation_time_utc = _parse_timestamp(row[time_idx])

            if surface_wind_dir_deg is None and wind_dir_idx is not None and len(row) > wind_dir_idx:
                surface_wind_dir_deg = _parse_float(row[wind_dir_idx])

            if surface_wind_kt is None and wind_speed_idx is not None and len(row) > wind_speed_idx:
                wind_speed_m_s = _parse_float(row[wind_speed_idx])
                if wind_speed_m_s is not None:
                    surface_wind_kt = wind_speed_m_s * _MPS_TO_KT

        if len(points_raw) < 2:
            raise DataFetchError("Wyoming sounding did not include enough vertical levels")

        points_raw.sort(key=lambda entry: entry[0])
        surface_height_m = points_raw[0][0]
        points = [VerticalPoint(z_agl_m=max(0.0, z_m - surface_height_m), temp_c=temp_c) for z_m, temp_c in points_raw]

        has_low_level = any(point.z_agl_m <= 300.0 for point in points)
        timestamp_utc = observation_time_utc or cycle_time_utc
        return StationProfile(
            station_id=station.station_id,
            timestamp_utc=timestamp_utc,
            points=points,
            source=f"uwyo:{self._src.lower()}",
            is_high_res=True,
            from_pressure_levels=False,
            missing_low_level_values=not has_low_level,
            surface_wind_kt=surface_wind_kt,
            surface_wind_dir_deg=surface_wind_dir_deg,
        )

    def _cache_get(self, key: tuple[str, str]) -> str | None:
        if self._cache_ttl_s <= 0:
            return None
        item = self._csv_cache.get(key)
        if item is None:
            return None

        expires_at, csv_text = item
        if time.monotonic() >= expires_at:
            self._csv_cache.pop(key, None)
            return None
        return csv_text

    def _cache_set(self, key: tuple[str, str], csv_text: str) -> None:
        if self._cache_ttl_s <= 0:
            return
        self._csv_cache[key] = (time.monotonic() + self._cache_ttl_s, csv_text)


def _candidate_synoptic_cycles(target_time_utc: datetime, count: int) -> list[datetime]:
    latest_hour = 12 if target_time_utc.hour >= 12 else 0
    latest = datetime(
        target_time_utc.year,
        target_time_utc.month,
        target_time_utc.day,
        latest_hour,
        0,
        tzinfo=UTC,
    )
    if latest > target_time_utc:
        latest -= timedelta(hours=12)

    return [latest - timedelta(hours=12 * idx) for idx in range(count)]


def _normalize_header(name: str) -> str:
    normalized = name.strip().lower()
    for token in (" ", "/", "%", "-", "."):
        normalized = normalized.replace(token, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _parse_float(raw: str) -> float | None:
    value = raw.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_timestamp(raw: str) -> datetime | None:
    value = raw.strip()
    if not value:
        return None

    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
