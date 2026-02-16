from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from temp_inversion_bot.cli import _auto_slot, _build_profile_source, build_parser
from temp_inversion_bot.data_sources.open_meteo import OpenMeteoProfileSource
from temp_inversion_bot.data_sources.wyoming import WyomingSoundingProfileSource
from temp_inversion_bot.scheduler import _parse_hhmm


def test_auto_slot_morning_before_afternoon_time() -> None:
    now = datetime(2026, 2, 16, 11, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert _auto_slot(now, "07:30", "15:30") == "morning"


def test_auto_slot_afternoon_after_afternoon_time() -> None:
    now = datetime(2026, 2, 16, 16, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert _auto_slot(now, "07:30", "15:30") == "afternoon"


def test_parse_hhmm() -> None:
    assert _parse_hhmm("07:30") == (7, 30)


def test_build_profile_source_actual_mode() -> None:
    cfg = SimpleNamespace(
        profile_source_mode="actual",
        primary_station="74560",
        wyoming_src="BUFR",
        wyoming_url="https://weather.uwyo.edu/wsgi/sounding",
        open_meteo_model=None,
        open_meteo_url="https://api.open-meteo.com/v1/gfs",
    )
    source = _build_profile_source(cfg, logging.getLogger(__name__))
    assert isinstance(source, WyomingSoundingProfileSource)


def test_build_profile_source_forecast_mode() -> None:
    cfg = SimpleNamespace(
        profile_source_mode="forecast",
        primary_station="KORD",
        wyoming_src="BUFR",
        wyoming_url="https://weather.uwyo.edu/wsgi/sounding",
        open_meteo_model="hrrr_conus",
        open_meteo_url="https://api.open-meteo.com/v1/gfs",
    )
    source = _build_profile_source(cfg, logging.getLogger(__name__))
    assert isinstance(source, OpenMeteoProfileSource)


def test_cli_dry_run_flag_default_is_none() -> None:
    parser = build_parser()
    args = parser.parse_args(["run-once"])
    assert args.dry_run is None


def test_cli_dry_run_flag_sets_true_when_present() -> None:
    parser = build_parser()
    args = parser.parse_args(["run-once", "--dry-run"])
    assert args.dry_run is True
