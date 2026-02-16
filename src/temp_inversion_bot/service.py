from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from temp_inversion_bot.analysis import analyze_station_profile, combine_station_analyses
from temp_inversion_bot.composer import compose_post
from temp_inversion_bot.config import BotConfig
from temp_inversion_bot.data_sources.base import DataFetchError, ProfileSource
from temp_inversion_bot.domain import CombinedAnalysis, InversionStatus, InversionStrength, StationAnalysis
from temp_inversion_bot.publishing.base import Publisher
from temp_inversion_bot.state import JsonStateStore
from temp_inversion_bot.stations import STATIONS


@dataclass(slots=True)
class RunOutcome:
    slot: str
    posted: bool
    reason: str
    post_text: str | None = None
    post_uri: str | None = None
    analysis: CombinedAnalysis | None = None


class InversionBotService:
    def __init__(
        self,
        *,
        config: BotConfig,
        source: ProfileSource,
        publisher: Publisher,
        state_store: JsonStateStore,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._source = source
        self._publisher = publisher
        self._state_store = state_store
        self._logger = logger or logging.getLogger(__name__)

    def run_slot(self, slot: str, now: datetime | None = None, force: bool = False) -> RunOutcome:
        slot = slot.lower()
        if slot not in {"morning", "afternoon", "manual"}:
            raise ValueError("slot must be morning, afternoon, or manual")

        now_utc = (now or datetime.now(UTC)).astimezone(UTC)
        now_local = now_utc.astimezone(self._config.tzinfo)
        local_day = now_local.date()

        if not force and self._state_store.post_count(local_day) >= self._config.max_posts_per_day:
            return RunOutcome(slot=slot, posted=False, reason="max_posts_reached")

        if slot == "morning" and not force and self._state_store.has_morning_post(local_day):
            return RunOutcome(slot=slot, posted=False, reason="morning_already_posted")

        if slot == "afternoon" and not force:
            summary = self._state_store.morning_summary(local_day)
            if summary is None:
                return RunOutcome(slot=slot, posted=False, reason="missing_morning_post")
            if float(summary.get("confidence", 1.0)) >= self._config.afternoon_confidence_threshold:
                return RunOutcome(slot=slot, posted=False, reason="morning_confidence_not_low")

        analysis_time_utc = self._analysis_target_time_utc(slot, local_day, now_utc)
        analysis = self._build_analysis(analysis_time_utc)

        if slot == "afternoon" and not force:
            summary = self._state_store.morning_summary(local_day)
            if summary is not None and summary.get("status") == analysis.status.value:
                return RunOutcome(slot=slot, posted=False, reason="afternoon_status_unchanged", analysis=analysis)

        post_text = compose_post(analysis)
        post_uri = self._publisher.publish(post_text)

        self._state_store.record_post(
            day=local_day,
            slot=slot,
            analysis=analysis,
            text=post_text,
            uri=post_uri,
            posted_at_utc=now_utc,
        )
        self._logger.info(
            "Posted %s update status=%s confidence=%.2f uri=%s",
            slot,
            analysis.status.value,
            analysis.confidence,
            post_uri,
        )

        return RunOutcome(
            slot=slot,
            posted=True,
            reason="posted",
            post_text=post_text,
            post_uri=post_uri,
            analysis=analysis,
        )

    def _analysis_target_time_utc(self, slot: str, local_day: date, now_utc: datetime) -> datetime:
        if slot == "morning":
            return datetime(local_day.year, local_day.month, local_day.day, 13, 0, tzinfo=UTC)
        if slot == "afternoon":
            return now_utc.replace(minute=0, second=0, microsecond=0)
        return now_utc

    def _build_analysis(self, target_time_utc: datetime) -> CombinedAnalysis:
        primary_station = STATIONS[self._config.primary_station]

        try:
            primary_profile = self._source.fetch_station_profile(primary_station, target_time_utc)
            primary = analyze_station_profile(primary_profile)
        except DataFetchError as exc:
            self._logger.error("Primary profile fetch failed: %s", exc)
            return _uncertain_analysis(
                primary_station=self._config.primary_station,
                secondary_station=self._config.secondary_station,
                reason="Data incomplete today (forecast profile missing). Will retry later.",
            )

        secondary: StationAnalysis | None = None
        secondary_station = self._config.secondary_station
        if secondary_station and secondary_station in STATIONS:
            try:
                secondary_profile = self._source.fetch_station_profile(STATIONS[secondary_station], target_time_utc)
                secondary = analyze_station_profile(secondary_profile)
            except DataFetchError as exc:
                self._logger.warning("Secondary profile fetch failed for %s: %s", secondary_station, exc)

        return combine_station_analyses(primary, secondary, secondary_station)


def _uncertain_analysis(primary_station: str, secondary_station: str | None, reason: str) -> CombinedAnalysis:
    return CombinedAnalysis(
        primary_station=primary_station,
        secondary_station=secondary_station,
        status=InversionStatus.UNCERTAIN,
        strength=InversionStrength.NONE,
        confidence=0.2,
        max_delta_c=None,
        inversion_top_m=None,
        inversion_depth_m=None,
        impact_text="Data incomplete today.",
        reasoning=reason,
    )
