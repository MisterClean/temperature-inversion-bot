from __future__ import annotations

from datetime import datetime, timezone

from temp_inversion_bot.analysis import analyze_station_profile, combine_station_analyses
from temp_inversion_bot.domain import InversionStatus, InversionStrength, StationAnalysis, StationProfile, VerticalPoint


def _profile_from_pairs(
    station: str,
    pairs: list[tuple[float, float]],
    *,
    high_res: bool = True,
    pressure_levels: bool = False,
    missing_low: bool = False,
    wind_kt: float | None = None,
    wind_dir_deg: float | None = None,
) -> StationProfile:
    return StationProfile(
        station_id=station,
        timestamp_utc=datetime(2026, 2, 16, 13, 0, tzinfo=timezone.utc),
        points=[VerticalPoint(z, t) for z, t in pairs],
        source="synthetic",
        is_high_res=high_res,
        from_pressure_levels=pressure_levels,
        missing_low_level_values=missing_low,
        surface_wind_kt=wind_kt,
        surface_wind_dir_deg=wind_dir_deg,
    )


def test_no_inversion_profile_returns_no_inversion() -> None:
    profile = _profile_from_pairs(
        "KORD",
        [(0, 7.0), (100, 6.4), (200, 5.8), (400, 4.6), (800, 2.5)],
    )
    result = analyze_station_profile(profile)

    assert result.status == InversionStatus.NO_INVERSION
    assert result.strength == InversionStrength.NONE
    assert result.confidence == 0.9


def test_shallow_weak_inversion_detected() -> None:
    profile = _profile_from_pairs(
        "KORD",
        [(0, -1.0), (50, -0.4), (100, 0.3), (150, 0.8), (220, 0.1), (400, -1.2)],
        wind_kt=12.0,
    )
    result = analyze_station_profile(profile)

    assert result.status == InversionStatus.INVERSION
    assert result.strength == InversionStrength.WEAK
    assert result.inversion_depth_m is not None and result.inversion_depth_m >= 100
    assert result.mix_out_hint == "Likely mixes out by late morning."


def test_deep_strong_inversion_detected() -> None:
    profile = _profile_from_pairs(
        "KORD",
        [(0, -4.5), (100, -2.5), (200, 0.0), (300, 1.8), (450, 2.2), (700, -1.0)],
        wind_kt=4.0,
    )
    result = analyze_station_profile(profile)

    assert result.status == InversionStatus.INVERSION
    assert result.strength == InversionStrength.STRONG
    assert result.max_delta_c is not None and result.max_delta_c >= 4.0
    assert result.mix_out_hint == "May persist into afternoon."


def test_confidence_penalty_for_pressure_level_and_missing_low_data() -> None:
    profile = _profile_from_pairs(
        "KORD",
        [(350, -2.0), (500, -1.0), (700, 0.0)],
        high_res=False,
        pressure_levels=True,
        missing_low=True,
    )
    result = analyze_station_profile(profile)

    assert result.status in {InversionStatus.NO_INVERSION, InversionStatus.INVERSION}
    assert result.confidence == 0.2


def test_lake_influenced_localized_inversion() -> None:
    primary = StationAnalysis(
        station_id="KORD",
        status=InversionStatus.NO_INVERSION,
        strength=InversionStrength.NONE,
        confidence=0.9,
        source="synthetic",
        surface_wind_dir_deg=90.0,
    )
    secondary = StationAnalysis(
        station_id="KMDW",
        status=InversionStatus.INVERSION,
        strength=InversionStrength.WEAK,
        confidence=0.8,
        max_delta_c=1.5,
        inversion_top_m=150,
        inversion_depth_m=150,
        source="synthetic",
    )

    combined = combine_station_analyses(primary, secondary, secondary_station="KMDW")

    assert combined.status == InversionStatus.LOCALIZED
    assert combined.strength == InversionStrength.WEAK
    assert combined.cross_station_note == "Likely lake-influenced / localized inversion."
    assert combined.confidence == 0.7
