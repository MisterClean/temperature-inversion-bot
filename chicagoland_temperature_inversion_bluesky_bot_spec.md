# Chicagoland Temperature Inversion Bluesky Bot — Specification

## 1. Purpose
Create a **Bluesky bot** that posts once per day indicating whether a **temperature inversion** is present over the **Chicagoland** area *today*, plus brief context (strength, approximate depth, confidence, and why it matters).

The bot should be similar in spirit to `@frenchgrid.bsky.social` (short, data-driven daily posts), and should be deployable on **AWS Lightsail** with **PM2** process orchestration.

---

## 2. User-facing behavior

### 2.1 Posting cadence
- **Default**: 1 post per day.
- **Post time**: **07:30 local time** (America/Chicago).
- **Optional**: A second “afternoon update” post at **15:30 local time** *only if* the morning confidence was low and new data changes the inversion status.

### 2.2 Post content (example templates)

**Inversion detected (strong):**
> Chicagoland inversion ✅
> ~3.5°C warming from surface to 450 m (strong). Likely traps pollution/smoke + keeps haze around. Next check tomorrow.

**Inversion detected (weak / shallow):**
> Chicagoland inversion ⚠️
> Shallow (~1.2°C) inversion in the lowest ~150 m. May increase morning haze; should mix out by late morning.

**No inversion:**
> Chicagoland inversion ❌
> No meaningful near-surface inversion in today’s profile. Mixing looks decent.

**Low confidence / missing data:**
> Chicagoland inversion: uncertain 🤷
> Data incomplete today (METAR/forecast profile missing). Will retry later.

### 2.3 Constraints
- Keep posts **< 280 characters**.
- Use a consistent emoji indicator: ✅ / ⚠️ / ❌ / 🤷.
- Mention “Chicagoland” explicitly.
- Avoid overly technical jargon; include one quantitative number when available (°C/°F and depth).

---

## 3. Definition of “Chicagoland”
Use a representative point and stations:
- Primary reference: **Chicago O’Hare (KORD)** area.
- Secondary validation: **Midway (KMDW)** and optionally **Gary (KGYY)**.

The bot should compute inversion status for **KORD**, and optionally adjust confidence if KMDW differs significantly.

---

## 4. Data sources

### 4.1 Preferred: Forecast vertical profile (most reliable daily)
Use a model-derived forecast sounding/profile for the Chicago area.

**Option A (recommended): NOAA/NWS NBM or HRRR-derived forecast soundings**
- Use a stable endpoint that provides temperature by height (AGL) or pressure levels.
- Target time window: **today 12Z–15Z** (morning) for “today” call.

**Option B: Open-Meteo (fallback)**
- Use Open-Meteo API for hourly temperature at multiple heights if available, or pressure-level temps.

### 4.2 Secondary: Observations
Use observations to confirm low-level inversion when possible.

- **METAR** temperatures/dewpoints + wind for KORD/KMDW.
- **Nearby surface stations** (e.g., lakefront vs inland) can hint at lake-influenced inversions.

### 4.3 Stretch goal: Radiosonde
- Radiosonde is only twice daily and may not represent micro-scale lake effects.
- If accessible (e.g., ILX / DTX / DVN), use as an “extra confidence” input, not as primary.

### 4.4 Source selection logic
- If forecast profile is available and passes validation → use it.
- Else if fallback profile available → use it with reduced confidence.
- Else → post “uncertain” and retry later.

---

## 5. Inversion detection algorithm

### 5.1 Core concept
A **near-surface temperature inversion** exists if temperature **increases with height** over a sufficiently deep layer near the ground.

### 5.2 Inputs
A vertical profile consisting of points:
- `z_agl_m` (height above ground, meters)
- `temp_c` (temperature in °C)

If data is provided on pressure levels, convert to approximate height AGL using standard atmosphere or hypsometric approximation; note reduced confidence.

### 5.3 Pre-processing
- Interpolate temperature onto a regular height grid: **0–1000 m AGL** at **25 m** increments.
- Smooth with a light rolling mean (e.g., 3-point) to reduce noise.

### 5.4 Detection rules
Compute `ΔT(z) = T(z) - T(0)`.

A profile is considered to have an inversion if any contiguous layer starting at or above the surface satisfies:
- **Depth criterion:** layer thickness ≥ **100 m**
- **Strength criterion:** `max(ΔT)` within 0–1000 m ≥ **1.0°C**

Classify strength:
- **Weak:** 1.0–2.0°C
- **Moderate:** 2.0–4.0°C
- **Strong:** ≥ 4.0°C

Estimate inversion “top” as the height of maximum `ΔT` before temperature resumes decreasing.

### 5.5 Confidence scoring (0–1)
Start at 0.7 and adjust:
- +0.2 if using a high-res forecast profile (e.g., HRRR-like)
- -0.2 if using pressure-level-only conversion
- -0.2 if O’Hare vs Midway disagree on inversion presence
- -0.3 if any missing values in 0–300 m range
Cap to [0, 1].

### 5.6 Special cases
- **Lake breeze / shoreline inversions**: if KORD says “no” but KMDW says “yes” and winds are easterly, treat as **localized inversion** and post ⚠️ with note “lake-influenced / localized”.
- **Nocturnal inversions**: If the bot posts at 07:30, the inversion may mix out later. Provide a simple “mix-out likely by X” estimate using surface wind and lapse rate (optional, see §5.7).

### 5.7 Optional: Mix-out estimate
Heuristic:
- If inversion is weak and surface winds ≥ 10 kt → “likely mixes out by late morning”.
- If strong and winds < 8 kt → “may persist into afternoon”.

---

## 6. Message generation

### 6.1 Units
- Use **°C** by default.
- Optionally include °F in parentheses only if space allows.

### 6.2 Required fields in post
- Status emoji + “Chicagoland inversion” phrase
- Strength (°C) and depth/top height (m)
- One short impact sentence (pollution/haze/smoke trapping; reduced mixing)

### 6.3 Character budget enforcement
- Hard cap at 280 chars.
- If too long, drop secondary clauses in this order:
  1) remove mix-out estimate
  2) remove station cross-check note
  3) drop parentheses/extra units

---

## 7. Bot identity & Bluesky integration

### 7.1 Account
- Bot runs under an existing Bluesky account the user controls.

### 7.2 Posting via AT Protocol
- Use official AT Protocol libraries for Node.js or Python.
- Authenticate via app password.
- Maintain a simple `last_posted_date` state to avoid duplicates.

---

## 8. System architecture

### 8.1 Runtime
- Recommended: **Node.js** (fits well with PM2), but Python is acceptable.

### 8.2 Components
1) **Scheduler**
   - Cron-like schedule at 07:30 America/Chicago (and optional 15:30 conditional rerun).
2) **Fetcher**
   - Pull forecast profile data + METAR.
3) **Analyzer**
   - Run inversion detection + confidence.
4) **Composer**
   - Build the post text.
5) **Poster**
   - Send to Bluesky.
6) **State store**
   - Lightweight JSON file on disk, or SQLite.

### 8.3 Config
Environment variables:
- `BSKY_HANDLE`
- `BSKY_APP_PASSWORD`
- `TZ=America/Chicago`
- `PRIMARY_STATION=KORD`
- `SECONDARY_STATION=KMDW`
- `POST_TIME_MORNING=07:30`
- `POST_TIME_AFTERNOON=15:30`
- Data source API keys if needed.

---

## 9. Deployment on AWS Lightsail + PM2

### 9.1 Process
- App runs as a long-lived process managed by **PM2**.
- Use `pm2 startup` to auto-start.
- Use `pm2 save` to persist.

### 9.2 Scheduling
Two options:
- **Option A:** Use `node-cron` (or equivalent) inside the app.
- **Option B:** Use system cron to run a one-shot script; PM2 manages environment. (Prefer A for simplicity.)

### 9.3 Logging
- Log to stdout/stderr (PM2 captures).
- Include structured logs for:
  - data fetch success/failure
  - inversion computed values
  - post ID returned by Bluesky

---

## 10. Reliability & safety

### 10.1 Retries
- Data fetch: retry 3 times with exponential backoff.
- Posting: retry once if transient error.

### 10.2 Rate limits
- Never post more than **2 times/day**.
- Avoid calling external APIs more than necessary; cache fetched profiles for the day.

### 10.3 Failure modes
- If data missing → post 🤷 (uncertain) *once*, then retry later (do not spam).
- If Bluesky auth fails → log loudly and do not retry continuously.

---

## 11. Testing

### 11.1 Unit tests
- Inversion detection given synthetic profiles:
  - no inversion
  - shallow weak inversion
  - deep strong inversion
  - noisy profile

### 11.2 Snapshot tests
- Post text generation for each status.

### 11.3 Integration tests
- Dry-run mode (`DRY_RUN=true`) prints post instead of publishing.

---

## 12. Future enhancements (optional)
- Include a small plot (image) of the lowest 1 km temperature profile.
- Add “air quality tie-in” by pulling current AQI and mentioning when inversion + high AQI coincide.
- Add geo-variation: “shoreline vs inland” summary.
