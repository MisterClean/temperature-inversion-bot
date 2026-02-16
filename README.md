# Temperature Inversion Bot (Python)

A modular bot that posts daily Chicagoland temperature inversion updates to microblogging services.

First adapter included: **Bluesky** via Python `atproto` (`0.0.65+`).

## What it does

- Runs a **morning post** at `07:30` America/Chicago.
- Runs an **afternoon check** at `15:30` America/Chicago.
- Afternoon post is sent only when:
  - the morning confidence was low, and
  - the latest status changed from the morning status.
- Enforces max `2` posts/day.
- Keeps posts under `280` chars with deterministic trimming rules.

## Architecture

- `src/temp_inversion_bot/data_sources/`
  - `open_meteo.py`: fetches vertical profile + wind fields for KORD/KMDW.
- `src/temp_inversion_bot/analysis.py`
  - interpolation, smoothing, inversion detection, confidence scoring.
- `src/temp_inversion_bot/composer.py`
  - message generation with emoji/status/character budget handling.
- `src/temp_inversion_bot/publishing/`
  - `base.py`: generic publisher protocol.
  - `bluesky.py`: Bluesky adapter.
  - `dry_run.py`: no-post adapter for safe testing.
- `src/temp_inversion_bot/service.py`
  - end-to-end orchestration and decision logic.
- `src/temp_inversion_bot/state.py`
  - JSON state store (`last posted`, morning summary, daily caps).
- `src/temp_inversion_bot/scheduler.py`
  - APScheduler process for recurring runs.

This design is microblog-platform agnostic: add another adapter by implementing `Publisher.publish(text)`.

## Quick start

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

### 2. Configure

```bash
cp .env.example .env
```

Required values:

- `BSKY_HANDLE`
- `BSKY_APP_PASSWORD`

Optional key settings:

- `TZ` (default `America/Chicago`)
- `PRIMARY_STATION` (default `KORD`)
- `SECONDARY_STATION` (default `KMDW`)
- `POST_TIME_MORNING` (default `07:30`)
- `POST_TIME_AFTERNOON` (default `15:30`)
- `OPEN_METEO_URL` (default `https://api.open-meteo.com/v1/gfs`)
- `OPEN_METEO_MODEL` (optional; leave empty for GFS endpoint default)
- `DRY_RUN` (`true`/`false`)

### 3. Run once (safe)

```bash
.venv/bin/temp-inversion-bot run-once --slot morning --dry-run
```

### 4. Run once (real Bluesky post)

```bash
.venv/bin/temp-inversion-bot run-once --slot morning --force
```

### 5. Run scheduler (long-lived process)

```bash
.venv/bin/temp-inversion-bot schedule
```

## Testing

```bash
.venv/bin/pytest
```

Current coverage focus:

- inversion detection unit tests (no inversion, weak, strong, low-quality profile)
- message composition snapshot tests for each status
- service/state integration tests with stub publisher (no real posts)

## AWS Lightsail + PM2

Use PM2 to keep scheduler alive and auto-restart:

```bash
pm2 start ".venv/bin/temp-inversion-bot schedule" --name chicagoland-inversion-bot
pm2 save
pm2 startup
```

If you use `.env`, load it in the shell/session before `pm2 start`.

## Extending to new microblog services

1. Create `src/temp_inversion_bot/publishing/<service>.py`.
2. Implement:

```python
class MyServicePublisher:
    def publish(self, text: str) -> str | None:
        ...
```

3. Wire selection in `cli.py` (or via env/config flag).

## Notes on data source

- Current implementation uses Open-Meteo GFS pressure-level temperatures/geopotential heights.
- Confidence is reduced when low-level data is sparse or pressure-level conversion is used.
- KORD is primary, KMDW cross-check can reduce confidence and trigger localized/lake-influenced status.
