from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from temp_inversion_bot.config import BotConfig
from temp_inversion_bot.service import InversionBotService


class BotScheduler:
    def __init__(
        self,
        *,
        config: BotConfig,
        service: InversionBotService,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._service = service
        self._logger = logger or logging.getLogger(__name__)

    def run_forever(self) -> None:
        scheduler = BlockingScheduler(timezone=self._config.timezone)

        morning_hour, morning_minute = _parse_hhmm(self._config.post_time_morning)
        afternoon_hour, afternoon_minute = _parse_hhmm(self._config.post_time_afternoon)

        scheduler.add_job(
            lambda: self._run_slot_with_logging("morning"),
            trigger="cron",
            hour=morning_hour,
            minute=morning_minute,
            id="morning-post",
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            lambda: self._run_slot_with_logging("afternoon"),
            trigger="cron",
            hour=afternoon_hour,
            minute=afternoon_minute,
            id="afternoon-check",
            coalesce=True,
            max_instances=1,
        )

        self._logger.info(
            "Scheduler active for %s and %s (%s)",
            self._config.post_time_morning,
            self._config.post_time_afternoon,
            self._config.timezone,
        )
        scheduler.start()

    def _run_slot_with_logging(self, slot: str) -> None:
        outcome = self._service.run_slot(slot)
        self._logger.info(
            "Scheduler slot=%s posted=%s reason=%s",
            slot,
            outcome.posted,
            outcome.reason,
        )


def _parse_hhmm(raw: str) -> tuple[int, int]:
    hour, minute = raw.split(":")
    return int(hour), int(minute)
