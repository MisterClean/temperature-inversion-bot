from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from temp_inversion_bot.stations import STATIONS, StationDefinition

_PROFILE_SOURCE_ACTUAL = "actual"
_PROFILE_SOURCE_FORECAST = "forecast"


@dataclass(frozen=True, slots=True)
class BotConfig:
    timezone: str
    profile_source_mode: str
    primary_station: str
    secondary_station: str | None
    post_time_morning: str
    post_time_afternoon: str
    dry_run: bool
    max_posts_per_day: int
    afternoon_confidence_threshold: float
    state_file: Path
    open_meteo_url: str
    open_meteo_model: str | None
    wyoming_url: str
    wyoming_src: str
    bsky_handle: str | None
    bsky_app_password: str | None
    primary_station_def: StationDefinition | None = None
    secondary_station_def: StationDefinition | None = None

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class ConfigError(ValueError):
    pass


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    return int(raw)


def _parse_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    return float(raw)


def _parse_optional_float(raw: str | None, field_name: str) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{field_name} must be numeric") from exc


def _validate_hhmm(raw: str, field_name: str) -> str:
    pieces = raw.split(":")
    if len(pieces) != 2:
        raise ConfigError(f"{field_name} must be in HH:MM format")

    hour = int(pieces[0])
    minute = int(pieces[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError(f"{field_name} must be a valid 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def _parse_profile_source_mode(raw: str | None) -> str:
    mode = (raw or _PROFILE_SOURCE_ACTUAL).strip().lower()
    if mode not in {_PROFILE_SOURCE_ACTUAL, _PROFILE_SOURCE_FORECAST}:
        raise ConfigError("PROFILE_SOURCE_MODE must be 'actual' or 'forecast'")
    return mode


def _resolve_station_definition(
    *,
    station_id: str | None,
    latitude: float | None,
    longitude: float | None,
    elevation_m: float | None,
    env_prefix: str,
    required: bool,
    allow_unknown_without_coordinates: bool,
) -> StationDefinition | None:
    has_any_coordinate_override = any(value is not None for value in (latitude, longitude, elevation_m))

    if station_id is None:
        if has_any_coordinate_override:
            raise ConfigError(f"{env_prefix}_STATION is required when using coordinate overrides")
        return None

    if has_any_coordinate_override:
        if latitude is None or longitude is None:
            raise ConfigError(
                f"{env_prefix}_LATITUDE and {env_prefix}_LONGITUDE must both be set when overriding station location"
            )
        return StationDefinition(
            station_id=station_id,
            latitude=latitude,
            longitude=longitude,
            elevation_m=elevation_m if elevation_m is not None else 0.0,
        )

    station = STATIONS.get(station_id)
    if station is not None:
        return station

    if allow_unknown_without_coordinates:
        # Sounding station IDs are broader than the local built-in catalog.
        return StationDefinition(station_id=station_id, latitude=0.0, longitude=0.0, elevation_m=0.0)

    if required:
        raise ConfigError(
            f"Unknown {env_prefix}_STATION '{station_id}'. "
            f"Set {env_prefix}_LATITUDE and {env_prefix}_LONGITUDE for a custom location."
        )

    raise ConfigError(
        f"Unknown {env_prefix}_STATION '{station_id}'. "
        f"Set {env_prefix}_LATITUDE and {env_prefix}_LONGITUDE for a custom location."
    )


def load_config(force_dry_run: bool | None = None) -> BotConfig:
    load_dotenv()

    timezone = os.getenv("TZ", "America/Chicago")
    try:
        ZoneInfo(timezone)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid timezone: {timezone}") from exc

    profile_source_mode = _parse_profile_source_mode(os.getenv("PROFILE_SOURCE_MODE"))

    post_time_morning = _validate_hhmm(os.getenv("POST_TIME_MORNING", "07:30"), "POST_TIME_MORNING")
    post_time_afternoon = _validate_hhmm(
        os.getenv("POST_TIME_AFTERNOON", "15:30"),
        "POST_TIME_AFTERNOON",
    )

    dry_run = _parse_bool(os.getenv("DRY_RUN"), default=False)
    if force_dry_run is not None:
        dry_run = force_dry_run

    bsky_handle = os.getenv("BSKY_HANDLE")
    bsky_password = os.getenv("BSKY_APP_PASSWORD")
    if not dry_run and (not bsky_handle or not bsky_password):
        raise ConfigError("BSKY_HANDLE and BSKY_APP_PASSWORD are required when DRY_RUN=false")

    default_primary_station = "74560" if profile_source_mode == _PROFILE_SOURCE_ACTUAL else "KORD"
    default_secondary_station = "" if profile_source_mode == _PROFILE_SOURCE_ACTUAL else "KMDW"

    primary_station = os.getenv("PRIMARY_STATION", default_primary_station).strip().upper()
    if not primary_station:
        primary_station = default_primary_station

    secondary_station_raw = os.getenv("SECONDARY_STATION", default_secondary_station).strip().upper()
    secondary_station = secondary_station_raw if secondary_station_raw else None

    primary_latitude = _parse_optional_float(os.getenv("PRIMARY_LATITUDE"), "PRIMARY_LATITUDE")
    primary_longitude = _parse_optional_float(os.getenv("PRIMARY_LONGITUDE"), "PRIMARY_LONGITUDE")
    primary_elevation_m = _parse_optional_float(os.getenv("PRIMARY_ELEVATION_M"), "PRIMARY_ELEVATION_M")

    secondary_latitude = _parse_optional_float(os.getenv("SECONDARY_LATITUDE"), "SECONDARY_LATITUDE")
    secondary_longitude = _parse_optional_float(os.getenv("SECONDARY_LONGITUDE"), "SECONDARY_LONGITUDE")
    secondary_elevation_m = _parse_optional_float(os.getenv("SECONDARY_ELEVATION_M"), "SECONDARY_ELEVATION_M")

    if secondary_station is None and any(
        value is not None for value in (secondary_latitude, secondary_longitude, secondary_elevation_m)
    ):
        secondary_station = "SECONDARY"

    allow_unknown_station_ids = profile_source_mode == _PROFILE_SOURCE_ACTUAL

    primary_station_def = _resolve_station_definition(
        station_id=primary_station,
        latitude=primary_latitude,
        longitude=primary_longitude,
        elevation_m=primary_elevation_m,
        env_prefix="PRIMARY",
        required=True,
        allow_unknown_without_coordinates=allow_unknown_station_ids,
    )
    secondary_station_def = _resolve_station_definition(
        station_id=secondary_station,
        latitude=secondary_latitude,
        longitude=secondary_longitude,
        elevation_m=secondary_elevation_m,
        env_prefix="SECONDARY",
        required=False,
        allow_unknown_without_coordinates=allow_unknown_station_ids,
    )

    return BotConfig(
        timezone=timezone,
        profile_source_mode=profile_source_mode,
        primary_station=primary_station,
        secondary_station=secondary_station,
        post_time_morning=post_time_morning,
        post_time_afternoon=post_time_afternoon,
        dry_run=dry_run,
        max_posts_per_day=_parse_int(os.getenv("MAX_POSTS_PER_DAY"), default=2),
        afternoon_confidence_threshold=_parse_float(os.getenv("AFTERNOON_CONFIDENCE_THRESHOLD"), default=0.55),
        state_file=Path(os.getenv("STATE_FILE", "var/state.json")),
        open_meteo_url=os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/gfs"),
        open_meteo_model=os.getenv("OPEN_METEO_MODEL", "").strip() or None,
        wyoming_url=os.getenv("WYOMING_SOUNDING_URL", "https://weather.uwyo.edu/wsgi/sounding"),
        wyoming_src=os.getenv("WYOMING_SOURCE", "BUFR").strip() or "BUFR",
        bsky_handle=bsky_handle,
        bsky_app_password=bsky_password,
        primary_station_def=primary_station_def,
        secondary_station_def=secondary_station_def,
    )
