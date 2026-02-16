# Temperature Inversion Bot (Python)

A modular bot that posts daily temperature inversion updates to microblogging services.

First adapter included: **Bluesky** via Python `atproto` (`0.0.65+`).

## What it does

- Runs a **morning post** at `07:30` America/Chicago.
- Runs an **afternoon check** at `15:30` America/Chicago.
- Afternoon post is sent only when:
  - the morning confidence was low, and
  - the latest status changed from the morning status.
- Enforces max `2` posts/day.
- Keeps posts under `280` chars with deterministic trimming rules.

## Data source modes

Set `PROFILE_SOURCE_MODE` to choose how profiles are fetched:

- `actual` (default): observed Wyoming radiosonde data (`weather.uwyo.edu`)  
  - default station: `74560` (Lincoln, IL)
- `forecast`: Open-Meteo pressure-level forecast profiles (GFS by default)

## Architecture

- `src/temp_inversion_bot/data_sources/`
  - `wyoming.py`: fetches and parses observed sounding CSV profiles.
  - `open_meteo.py`: fetches forecast profile + wind fields.
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

- `PROFILE_SOURCE_MODE` (`actual` or `forecast`, default `actual`)
- `TZ` (default `America/Chicago`)
- `PRIMARY_STATION`
  - `actual` default: `74560` (Lincoln, IL)
  - `forecast` default: `KORD`
- `SECONDARY_STATION`
  - `actual` default: empty (disabled)
  - `forecast` default: `KMDW`
- `PRIMARY_LATITUDE`, `PRIMARY_LONGITUDE`, `PRIMARY_ELEVATION_M` (optional override)
- `SECONDARY_LATITUDE`, `SECONDARY_LONGITUDE`, `SECONDARY_ELEVATION_M` (optional override)
- `POST_TIME_MORNING` (default `07:30`)
- `POST_TIME_AFTERNOON` (default `15:30`)
- `MAX_POSTS_PER_DAY` (soft cap for normal scheduled flow)
- `HARD_MAX_POSTS_PER_DAY` (hard cap applied even with `--force`)
- `MIN_POST_INTERVAL_SECONDS` (minimum time between posts)
- `DEDUPE_POST_WINDOW_SECONDS` (suppresses identical reposts in this window)
- `WYOMING_SOUNDING_URL` (default `https://weather.uwyo.edu/wsgi/sounding`)
- `WYOMING_SOURCE` (default `BUFR`)
- `WYOMING_CACHE_TTL_SECONDS` (default `21600`)
- `OPEN_METEO_URL` (default `https://api.open-meteo.com/v1/gfs`)
- `OPEN_METEO_MODEL` (optional; leave empty for GFS endpoint default)
- `OPEN_METEO_CACHE_TTL_SECONDS` (default `900`)
- `UPSTREAM_MIN_REQUEST_INTERVAL_SECONDS` (default `1.0`)
- `UPSTREAM_MAX_REQUESTS_PER_MINUTE` (default `20`)
- `UPSTREAM_CIRCUIT_FAILURE_THRESHOLD` (default `5`)
- `UPSTREAM_CIRCUIT_COOLDOWN_SECONDS` (default `180`)
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

## Contributing

Please see `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

## Security

Please see `SECURITY.md` for responsible disclosure guidance.

## License

MIT. See `LICENSE`.

## Notes on data source

- `actual` mode pulls observed soundings from Wyoming (`TEXT:CSV`) at 00Z/12Z cycles, with fallback to earlier cycles.
- `forecast` mode uses Open-Meteo GFS pressure-level temperatures/geopotential heights.
- Both data sources include request throttling, per-minute request caps, retry backoff, circuit breaker cooldowns, and in-memory response caching.
- Confidence is reduced when low-level data is sparse or pressure-level conversion is used.
- Built-in station IDs include `74560` (Lincoln, IL), `KORD`, `KMDW`, and `KGYY`.

## Anti-Spam Safeguards

- Hard daily post cap is enforced even with `--force`.
- Minimum interval between posts prevents rapid accidental repeats.
- Duplicate post suppression blocks reposting identical text within a configurable window.
