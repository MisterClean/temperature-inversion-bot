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
        "TZ",
        "PRIMARY_STATION",
        "SECONDARY_STATION",
        "POST_TIME_MORNING",
        "POST_TIME_AFTERNOON",
        "MAX_POSTS_PER_DAY",
        "AFTERNOON_CONFIDENCE_THRESHOLD",
        "STATE_FILE",
        "OPEN_METEO_URL",
        "OPEN_METEO_MODEL",
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


def test_load_config_normalizes_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    _clear_env(monkeypatch)
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
    assert os.fspath(cfg.state_file).endswith("state.json")


def test_invalid_time_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("POST_TIME_MORNING", "99:00")

    with pytest.raises(ConfigError):
        load_config()
