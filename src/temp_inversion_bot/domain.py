from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class InversionStatus(str, Enum):
    INVERSION = "inversion"
    NO_INVERSION = "no_inversion"
    UNCERTAIN = "uncertain"
    LOCALIZED = "localized"


class InversionStrength(str, Enum):
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass(slots=True)
class VerticalPoint:
    z_agl_m: float
    temp_c: float


@dataclass(slots=True)
class StationProfile:
    station_id: str
    timestamp_utc: datetime
    points: list[VerticalPoint]
    source: str
    is_high_res: bool = False
    from_pressure_levels: bool = True
    missing_low_level_values: bool = False
    surface_wind_kt: float | None = None
    surface_wind_dir_deg: float | None = None


@dataclass(slots=True)
class StationAnalysis:
    station_id: str
    status: InversionStatus
    strength: InversionStrength
    confidence: float
    max_delta_c: float | None = None
    inversion_top_m: float | None = None
    inversion_depth_m: float | None = None
    mix_out_hint: str | None = None
    reasoning: str | None = None
    source: str | None = None
    surface_wind_dir_deg: float | None = None


@dataclass(slots=True)
class CombinedAnalysis:
    primary_station: str
    secondary_station: str | None
    status: InversionStatus
    strength: InversionStrength
    confidence: float
    max_delta_c: float | None
    inversion_top_m: float | None
    inversion_depth_m: float | None
    impact_text: str
    mix_out_hint: str | None = None
    cross_station_note: str | None = None
    reasoning: str | None = None
    source: str | None = None
