from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StationDefinition:
    station_id: str
    latitude: float
    longitude: float
    elevation_m: float


STATIONS: dict[str, StationDefinition] = {
    "KORD": StationDefinition("KORD", 41.9742, -87.9073, 204.0),
    "KMDW": StationDefinition("KMDW", 41.7868, -87.7522, 188.0),
    "KGYY": StationDefinition("KGYY", 41.6163, -87.4128, 181.0),
    # Wyoming sounding station ID for Lincoln, IL (default "actual" profile source).
    "74560": StationDefinition("74560", 40.1514, -89.3368, 179.0),
}
