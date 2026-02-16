from __future__ import annotations

import os

import pytest

from temp_inversion_bot.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def _disable_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("temp_inversion_bot.config.load_dotenv", lambda: None)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = [
        "BSKY_HANDLE",
        "BSKY_APP_PASSWORD",
        "PROFILE_SOURCE_MODE",
        "TZ",
        "PRIMARY_STATION",
        "SECONDARY_STATION",
        "PRIMARY_LATITUDE",
        "PRIMARY_LONGITUDE",
        "PRIMARY_ELEVATION_M",
        "SECONDARY_LATITUDE",
        "SECONDARY_LONGITUDE",
        "SECONDARY_ELEVATION_M",
        "POST_TIME_MORNING",
        "POST_TIME_AFTERNOON",
        "MAX_POSTS_PER_DAY",
        "HARD_MAX_POSTS_PER_DAY",
        "MIN_POST_INTERVAL_SECONDS",
        "DEDUPE_POST_WINDOW_SECONDS",
        "AFTERNOON_CONFIDENCE_THRESHOLD",
        "STATE_FILE",
        "OPEN_METEO_URL",
        "OPEN_METEO_MODEL",
        "OPEN_METEO_CACHE_TTL_SECONDS",
        "WYOMING_SOUNDING_URL",
        "WYOMING_SOURCE",
        "WYOMING_CACHE_TTL_SECONDS",
        "UPSTREAM_MIN_REQUEST_INTERVAL_SECONDS",
        "UPSTREAM_MAX_REQUESTS_PER_MINUTE",
        "UPSTREAM_CIRCUIT_FAILURE_THRESHOLD",
        "UPSTREAM_CIRCUIT_COOLDOWN_SECONDS",
        "DRY_RUN",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_requires_bluesky_credentials_when_not_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "false")

    with pytest.raises(ConfigError):
        load_config()


def test_dry_run_allows_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")

    cfg = load_config()
    assert cfg.dry_run is True
    assert cfg.bsky_handle is None


def test_defaults_to_actual_mode_and_lincoln_station(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")

    cfg = load_config()
    assert cfg.profile_source_mode == "actual"
    assert cfg.primary_station == "74560"
    assert cfg.secondary_station is None
    assert cfg.primary_station_def is not None
    assert cfg.primary_station_def.station_id == "74560"


def test_load_config_normalizes_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    _clear_env(monkeypatch)
    monkeypatch.setenv("PROFILE_SOURCE_MODE", "forecast")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BSKY_HANDLE", "test.bsky.social")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "abcd-efgh-ijkl-mnop")
    monkeypatch.setenv("POST_TIME_MORNING", "7:5")
    monkeypatch.setenv("POST_TIME_AFTERNOON", "15:30")
    monkeypatch.setenv("PRIMARY_STATION", "kord")
    monkeypatch.setenv("SECONDARY_STATION", "kmdw")
    monkeypatch.setenv("STATE_FILE", str(tmp_path / "state.json"))

    cfg = load_config()

    assert cfg.post_time_morning == "07:05"
    assert cfg.primary_station == "KORD"
    assert cfg.secondary_station == "KMDW"
    assert cfg.primary_station_def is not None
    assert cfg.secondary_station_def is not None
    assert os.fspath(cfg.state_file).endswith("state.json")


def test_invalid_time_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("POST_TIME_MORNING", "99:00")

    with pytest.raises(ConfigError):
        load_config()


def test_load_config_supports_custom_primary_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("PROFILE_SOURCE_MODE", "forecast")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("PRIMARY_STATION", "home")
    monkeypatch.setenv("PRIMARY_LATITUDE", "42.123")
    monkeypatch.setenv("PRIMARY_LONGITUDE", "-87.987")
    monkeypatch.setenv("PRIMARY_ELEVATION_M", "250")
    monkeypatch.setenv("SECONDARY_STATION", "")

    cfg = load_config()

    assert cfg.primary_station == "HOME"
    assert cfg.primary_station_def is not None
    assert cfg.primary_station_def.latitude == 42.123
    assert cfg.primary_station_def.longitude == -87.987
    assert cfg.primary_station_def.elevation_m == 250.0
    assert cfg.secondary_station is None
    assert cfg.secondary_station_def is None


def test_unknown_station_without_coordinates_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("PROFILE_SOURCE_MODE", "forecast")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("PRIMARY_STATION", "UNKNOWN")

    with pytest.raises(ConfigError):
        load_config()


def test_unknown_station_without_coordinates_allowed_in_actual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("PROFILE_SOURCE_MODE", "actual")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("PRIMARY_STATION", "72469")
    monkeypatch.setenv("SECONDARY_STATION", "")

    cfg = load_config()
    assert cfg.primary_station == "72469"
    assert cfg.primary_station_def is not None
    assert cfg.primary_station_def.station_id == "72469"


def test_rejects_hard_cap_below_soft_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("MAX_POSTS_PER_DAY", "2")
    monkeypatch.setenv("HARD_MAX_POSTS_PER_DAY", "1")

    with pytest.raises(ConfigError):
        load_config()
