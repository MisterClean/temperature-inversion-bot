from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class BotConfig:
    timezone: str
    primary_station: str
    secondary_station: str | None
    post_time_morning: str
    post_time_afternoon: str
    dry_run: bool
    max_posts_per_day: int
    afternoon_confidence_threshold: float
    state_file: Path
    open_meteo_url: str
    open_meteo_model: str
    bsky_handle: str | None
    bsky_app_password: str | None

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


def _validate_hhmm(raw: str, field_name: str) -> str:
    pieces = raw.split(":")
    if len(pieces) != 2:
        raise ConfigError(f"{field_name} must be in HH:MM format")

    hour = int(pieces[0])
    minute = int(pieces[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError(f"{field_name} must be a valid 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def load_config(force_dry_run: bool | None = None) -> BotConfig:
    load_dotenv()

    timezone = os.getenv("TZ", "America/Chicago")
    try:
        ZoneInfo(timezone)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid timezone: {timezone}") from exc

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

    secondary_station = os.getenv("SECONDARY_STATION", "KMDW").strip().upper()
    if not secondary_station:
        secondary_station = None

    return BotConfig(
        timezone=timezone,
        primary_station=os.getenv("PRIMARY_STATION", "KORD").strip().upper(),
        secondary_station=secondary_station,
        post_time_morning=post_time_morning,
        post_time_afternoon=post_time_afternoon,
        dry_run=dry_run,
        max_posts_per_day=_parse_int(os.getenv("MAX_POSTS_PER_DAY"), default=2),
        afternoon_confidence_threshold=_parse_float(os.getenv("AFTERNOON_CONFIDENCE_THRESHOLD"), default=0.55),
        state_file=Path(os.getenv("STATE_FILE", "var/state.json")),
        open_meteo_url=os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"),
        open_meteo_model=os.getenv("OPEN_METEO_MODEL", "hrrr_conus"),
        bsky_handle=bsky_handle,
        bsky_app_password=bsky_password,
    )
