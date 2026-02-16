from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from temp_inversion_bot.domain import (
    CombinedAnalysis,
    InversionStatus,
    InversionStrength,
    StationAnalysis,
    StationProfile,
    VerticalPoint,
)

_GRID_MIN_M = 0.0
_GRID_MAX_M = 1000.0
_GRID_STEP_M = 25.0


@dataclass(slots=True)
class _LayerCandidate:
    start_z_m: float
    end_z_m: float
    depth_m: float
    delta_c: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _strength_from_delta(delta_c: float) -> InversionStrength:
    if delta_c >= 4.0:
        return InversionStrength.STRONG
    if delta_c >= 2.0:
        return InversionStrength.MODERATE
    if delta_c >= 1.0:
        return InversionStrength.WEAK
    return InversionStrength.NONE


def _is_inversion_like(status: InversionStatus) -> bool:
    return status in {InversionStatus.INVERSION, InversionStatus.LOCALIZED}


def _smooth_three_point(values: list[float]) -> list[float]:
    if len(values) < 3:
        return values[:]

    smoothed = [values[0]]
    for idx in range(1, len(values) - 1):
        smoothed.append((values[idx - 1] + values[idx] + values[idx + 1]) / 3.0)
    smoothed.append(values[-1])
    return smoothed


def _sorted_points(points: Iterable[VerticalPoint]) -> list[VerticalPoint]:
    deduped: dict[float, float] = {}
    for point in points:
        deduped[float(point.z_agl_m)] = float(point.temp_c)
    return [VerticalPoint(z, deduped[z]) for z in sorted(deduped)]


def _linear_interpolate(points: list[VerticalPoint], z_target_m: float) -> float:
    if z_target_m <= points[0].z_agl_m:
        return points[0].temp_c
    if z_target_m >= points[-1].z_agl_m:
        return points[-1].temp_c

    for idx in range(len(points) - 1):
        left = points[idx]
        right = points[idx + 1]
        if left.z_agl_m <= z_target_m <= right.z_agl_m:
            if right.z_agl_m == left.z_agl_m:
                return right.temp_c
            ratio = (z_target_m - left.z_agl_m) / (right.z_agl_m - left.z_agl_m)
            return left.temp_c + ratio * (right.temp_c - left.temp_c)

    return points[-1].temp_c


def _regular_grid() -> list[float]:
    size = int((_GRID_MAX_M - _GRID_MIN_M) / _GRID_STEP_M) + 1
    return [_GRID_MIN_M + idx * _GRID_STEP_M for idx in range(size)]


def _find_inversion_layer(z_grid: list[float], temp_grid: list[float]) -> _LayerCandidate | None:
    gradients = [temp_grid[idx + 1] - temp_grid[idx] for idx in range(len(temp_grid) - 1)]

    candidates: list[_LayerCandidate] = []
    run_start: int | None = None

    for idx, gradient in enumerate(gradients):
        if gradient > 0:
            if run_start is None:
                run_start = idx
            continue

        if run_start is not None:
            start_idx = run_start
            end_idx = idx
            start_z = z_grid[start_idx]
            end_z = z_grid[end_idx]
            depth = end_z - start_z
            delta = temp_grid[end_idx] - temp_grid[start_idx]
            if start_z <= 300.0 and depth >= 100.0 and delta >= 1.0:
                candidates.append(_LayerCandidate(start_z, end_z, depth, delta))
            run_start = None

    if run_start is not None:
        start_idx = run_start
        end_idx = len(z_grid) - 1
        start_z = z_grid[start_idx]
        end_z = z_grid[end_idx]
        depth = end_z - start_z
        delta = temp_grid[end_idx] - temp_grid[start_idx]
        if start_z <= 300.0 and depth >= 100.0 and delta >= 1.0:
            candidates.append(_LayerCandidate(start_z, end_z, depth, delta))

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate.delta_c, reverse=True)
    return candidates[0]


def analyze_station_profile(profile: StationProfile) -> StationAnalysis:
    points = _sorted_points(profile.points)
    if len(points) < 2:
        return StationAnalysis(
            station_id=profile.station_id,
            status=InversionStatus.UNCERTAIN,
            strength=InversionStrength.NONE,
            confidence=0.0,
            reasoning="Profile data is too sparse to analyze.",
            source=profile.source,
            surface_wind_dir_deg=profile.surface_wind_dir_deg,
        )

    z_grid = _regular_grid()
    temps = [_linear_interpolate(points, z) for z in z_grid]
    smoothed = _smooth_three_point(temps)

    surface_temp = smoothed[0]
    deltas = [temp - surface_temp for temp in smoothed]
    max_delta = max(deltas)

    layer = _find_inversion_layer(z_grid, smoothed)

    confidence = 0.7
    if profile.is_high_res:
        confidence += 0.2
    if profile.from_pressure_levels:
        confidence -= 0.2

    has_low_level_observations = any(point.z_agl_m <= 300.0 for point in points)
    if profile.missing_low_level_values or not has_low_level_observations:
        confidence -= 0.3

    confidence = round(_clamp(confidence, 0.0, 1.0), 2)

    if layer is None:
        return StationAnalysis(
            station_id=profile.station_id,
            status=InversionStatus.NO_INVERSION,
            strength=InversionStrength.NONE,
            confidence=confidence,
            max_delta_c=round(max_delta, 2),
            reasoning="No contiguous near-surface warming layer met depth and strength criteria.",
            source=profile.source,
            surface_wind_dir_deg=profile.surface_wind_dir_deg,
        )

    strength = _strength_from_delta(layer.delta_c)
    mix_out_hint = None
    wind_kt = profile.surface_wind_kt
    if strength == InversionStrength.WEAK and wind_kt is not None and wind_kt >= 10.0:
        mix_out_hint = "Likely mixes out by late morning."
    elif strength == InversionStrength.STRONG and wind_kt is not None and wind_kt < 8.0:
        mix_out_hint = "May persist into afternoon."

    return StationAnalysis(
        station_id=profile.station_id,
        status=InversionStatus.INVERSION,
        strength=strength,
            confidence=confidence,
        max_delta_c=round(layer.delta_c, 2),
        inversion_top_m=round(layer.end_z_m),
        inversion_depth_m=round(layer.depth_m),
        mix_out_hint=mix_out_hint,
        reasoning="Detected contiguous warming layer in the lowest 1 km.",
        source=profile.source,
        surface_wind_dir_deg=profile.surface_wind_dir_deg,
    )


def _impact_text(status: InversionStatus) -> str:
    if status in {InversionStatus.INVERSION, InversionStatus.LOCALIZED}:
        return "Likely traps pollution/smoke and can keep haze around."
    if status == InversionStatus.NO_INVERSION:
        return "Mixing looks decent."
    return "Data incomplete today."


def combine_station_analyses(
    primary: StationAnalysis,
    secondary: StationAnalysis | None,
    secondary_station: str | None,
) -> CombinedAnalysis:
    status = primary.status
    strength = primary.strength
    confidence = primary.confidence
    max_delta_c = primary.max_delta_c
    inversion_top_m = primary.inversion_top_m
    inversion_depth_m = primary.inversion_depth_m
    mix_out_hint = primary.mix_out_hint
    cross_station_note = None

    if secondary is not None:
        primary_has = _is_inversion_like(primary.status)
        secondary_has = _is_inversion_like(secondary.status)
        if primary_has != secondary_has:
            confidence -= 0.2
            cross_station_note = f"{primary.station_id}/{secondary.station_id} differ today."

        easterly = (
            primary.surface_wind_dir_deg is not None
            and 45.0 <= primary.surface_wind_dir_deg <= 135.0
        )
        if (
            primary.status == InversionStatus.NO_INVERSION
            and secondary_has
            and easterly
        ):
            status = InversionStatus.LOCALIZED
            strength = secondary.strength
            max_delta_c = secondary.max_delta_c
            inversion_top_m = secondary.inversion_top_m
            inversion_depth_m = secondary.inversion_depth_m
            mix_out_hint = secondary.mix_out_hint or mix_out_hint
            cross_station_note = "Likely lake-influenced / localized inversion."

    confidence = _clamp(confidence, 0.0, 1.0)

    if status == InversionStatus.UNCERTAIN:
        reasoning = primary.reasoning or "Profile data missing for today."
    else:
        reasoning = None

    return CombinedAnalysis(
        primary_station=primary.station_id,
        secondary_station=secondary_station,
        status=status,
        strength=strength,
        confidence=round(confidence, 2),
        max_delta_c=max_delta_c,
        inversion_top_m=inversion_top_m,
        inversion_depth_m=inversion_depth_m,
        impact_text=_impact_text(status),
        mix_out_hint=mix_out_hint,
        cross_station_note=cross_station_note,
        reasoning=reasoning,
        source=primary.source,
    )
