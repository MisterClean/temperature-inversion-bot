from __future__ import annotations

from datetime import datetime
from typing import Protocol

from temp_inversion_bot.domain import StationProfile
from temp_inversion_bot.stations import StationDefinition


class ProfileSource(Protocol):
    def fetch_station_profile(self, station: StationDefinition, target_time_utc: datetime) -> StationProfile:
        """Fetch a vertical profile for a station near the requested UTC time."""


class DataFetchError(RuntimeError):
    pass
