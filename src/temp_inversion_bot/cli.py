from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

from temp_inversion_bot.config import ConfigError, load_config
from temp_inversion_bot.data_sources.open_meteo import OpenMeteoProfileSource
from temp_inversion_bot.data_sources.wyoming import WyomingSoundingProfileSource
from temp_inversion_bot.publishing.bluesky import BlueskyPublisher
from temp_inversion_bot.publishing.dry_run import DryRunPublisher
from temp_inversion_bot.scheduler import BotScheduler
from temp_inversion_bot.service import InversionBotService
from temp_inversion_bot.state import JsonStateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chicagoland temperature inversion bot")
    parser.add_argument("command", choices=["run-once", "schedule"], help="run mode")
    parser.add_argument(
        "--slot",
        choices=["morning", "afternoon", "manual", "auto"],
        default="auto",
        help="slot to run when using run-once",
    )
    parser.add_argument("--force", action="store_true", help="ignore state guards")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="print post instead of publishing to Bluesky",
    )
    parser.add_argument("--log-level", default="INFO", help="logging level")
    return parser


def _auto_slot(now: datetime, morning: str, afternoon: str) -> str:
    morning_h, morning_m = [int(part) for part in morning.split(":")]
    afternoon_h, afternoon_m = [int(part) for part in afternoon.split(":")]
    hm = (now.hour, now.minute)

    if hm < (afternoon_h, afternoon_m):
        return "morning"
    return "afternoon"


def _build_profile_source(config, logger):  # noqa: ANN001
    if config.profile_source_mode == "actual":
        logger.info(
            "Using Wyoming sounding source mode (station=%s src=%s)",
            config.primary_station,
            config.wyoming_src,
        )
        return WyomingSoundingProfileSource(
            base_url=config.wyoming_url,
            src=config.wyoming_src,
            logger=logger,
        )

    logger.info("Using Open-Meteo forecast source mode (model=%s)", config.open_meteo_model or "default")
    return OpenMeteoProfileSource(
        base_url=config.open_meteo_url,
        model=config.open_meteo_model,
        logger=logger,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("temp_inversion_bot")

    try:
        config = load_config(force_dry_run=args.dry_run)
    except ConfigError as exc:
        parser.error(str(exc))
        return

    source = _build_profile_source(config, logger)
    state_store = JsonStateStore(config.state_file)

    if config.dry_run:
        publisher = DryRunPublisher(logger=logger)
    else:
        publisher = BlueskyPublisher(
            handle=config.bsky_handle or "",
            app_password=config.bsky_app_password or "",
            logger=logger,
        )

    service = InversionBotService(
        config=config,
        source=source,
        publisher=publisher,
        state_store=state_store,
        logger=logger,
    )

    if args.command == "schedule":
        BotScheduler(config=config, service=service, logger=logger).run_forever()
        return

    now = datetime.now(config.tzinfo)
    slot = args.slot
    if slot == "auto":
        slot = _auto_slot(now, config.post_time_morning, config.post_time_afternoon)

    outcome = service.run_slot(slot=slot, now=datetime.now(UTC), force=args.force)
    if outcome.posted:
        logger.info("Post created (%s): %s", outcome.post_uri, outcome.post_text)
    else:
        logger.info("No post sent. reason=%s", outcome.reason)


if __name__ == "__main__":
    main()
