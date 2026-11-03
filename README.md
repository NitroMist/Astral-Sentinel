# Astral Sentinel v1.0.0 · Local Astrology Observatory

A free, open-source, offline-first, sci-fi-themed astrology program running in a local browser window. Inspired by futuristic observatories and planetary surveillance systems, it offers a fun, immersive way to explore astrology through interactive visualizations, natal charts, and planetary transits.

Astral Sentinel independently calculates natal positions and transits using Swiss Ephemeris and provides an *experimental, interpretive* pressure/difficulty index. The experience is designed primarily for entertainment, curiosity, and personal exploration. The index is **not** a forecast of physical danger or a validated predictor of life outcomes.

## Release 1.0.0

Stabilization release based on v0.2.5. No changes to astronomical ephemeris calculations or interpretive scoring weights. Hardens the local HTTP server against unexpected Host/Origin requests, prevents a stale calculation error from replacing a newer successful status, makes export concurrency guards stricter, and skips hidden-tab canvas painting. Includes test-suite and package hygiene checks. See `RELEASE_NOTES_v1.0.0.md`.

## Quick start

**Windows:** Extract the complete archive, then double-click `Launch_Astral_Sentinel.bat`. The launcher sets up Python dependencies when needed and opens `http://127.0.0.1:8765`. It supports Python 3.10–3.13 where the pinned Swiss Ephemeris packages have wheels. If needed, install Python 3.12. On first start it creates `.venv` locally.

**Linux/macOS:** Install Python 3.10–3.13 and run `launch_linux_mac.sh`, or use `python -m pip install -r requirements.txt` and `python server.py` in an appropriate virtual environment. The local-only API and frontend need no cloud login.

**New users:** The GitHub source starts with a built-in **DEMO chart**, not somebody's personal birth chart. Open **Natal Scan → Birth Chart Library → + New Chart** to enter yours. The demo can be deleted once you have created another chart.

## Birth Chart Library

- Store multiple personal birth charts on the same PC and select the active chart in **Natal Scan**. Observatory, Forecast, Natal Scan, advisory areas, auxiliary scoring, the timeline, and AI Export all recalculate for that active birth chart.
- Choose **+ New Chart** and enter a nickname, **birth date**, **local birth clock time**, and **birthplace**. Select a city from the small **offline city search** to fill latitude, longitude, and the IANA time zone. The bundled list contains about 440 representative time-zone and commonly used cities, not every locality worldwide. For an unlisted birthplace, manually enter coordinates and a valid IANA time-zone name.
- Existing charts can be edited and switched without modifying the original `data/profile.json`. New and edited charts live in `data/profiles.json` (created upon the first change).
- Use **↓ Export** to save a portable profile JSON, **↑ Import JSON** to load another, and **Delete** to remove a chart. You cannot delete the last chart.
- JSON imports contain **birth input values**, never ready-made ephemeris positions. Swiss Ephemeris recalculates the positions from the saved date, time, zone, and coordinates.
- No birth data is uploaded or sent to a service. Import, edit, delete, and export operate on the local host only. Individual AI exports and Joplin sends remain explicit user actions.

### Required birth information for reliable houses

| Input | Required? | Notes |
|---|---|---|
| Birth date | Yes | YYYY-MM-DD, currently 1900–2100 |
| Birth time | Yes | Local wall-clock time (24h HH:MM). Verify against a birth certificate if available; inaccurate time changes the Ascendant and houses |
| Birthplace | Yes | Latitude (north positive), longitude (east positive), and a descriptive label |
| Historical time zone | Yes | IANA zone, such as `America/New_York`; **not** a guessed current UTC offset |
| Name/nickname | Yes | Just for local display and saved-profile selection |
| Existing PDF, screenshot, or planet-position list | **No** | The app calculates from inputs, not by copying a potentially erroneous chart |

The program uses the historical IANA time-zone database to resolve daylight-saving changes. If a local birth clock time occurred twice when clocks were set back, the user must explicitly select its first or second occurrence. A non-existent spring-forward clock time is rejected. Historical civil-time rules before 1970 may require external confirmation in some jurisdictions; the app does not claim a birth record is correct merely because the calculations are deterministic.

### Portable profile JSON format

```json
{
  "format": "astral-sentinel-birth-profile",
  "version": 1,
  "profile": {
    "label": "Example London Chart",
    "birth": {
      "date": "2000-01-01",
      "time": "12:00",
      "timezone": "Europe/London",
      "latitude": 51.5074,
      "longitude": -0.1278,
      "location_label": "London, GB"
    },
    "default_house_system": "placidus",
    "default_zodiac": "tropical"
  }
}
```

The optional `"fold": 0` or `"fold": 1` belongs inside `birth` and selects the first or second occurrence of a repeated local hour. Another Astral Sentinel AI export containing a `birth_profile` object may also be imported as a new chart.

**Privacy note:** Birth dates, times, and locations are personal information. Keep exported JSON profiles and copied local `data` folders private unless the person has consented to sharing them.

## Upgrading an existing installation

The **v1.0.0 update patch** replaces application code but does **not** overwrite `.venv`, `data/profile.json`, `data/profiles.json`, `data/observations.json`, `data/reference_chart.json`, or `ephe/`. Your saved charts, private PDF cross-check, observation log, and Chiron file remain on your PC. **Back up the entire `data` folder before patching.** The patch itself contains no personal chart data. Use the **public complete package** for new users; avoid giving someone a ZIP of your already-used installation, since it may contain saved personal charts and journals.

For a completely fresh GitHub checkout, the engine uses a built-in London demonstration chart until you create your own. A sample is provided at `data/profile.example.json`; live profile and journal files are excluded by `.gitignore`. No individual user's birth record or PDF comparison data is shipped.

## Other features

- **Planetary and auxiliary positions:** Sun through Pluto, Chiron, North and South Nodes, mean/true lunar nodes, Black Moon Lilith, natal Part of Fortune and Vertex.
- **Zodiac projection:** Geocentric ecliptic longitudes, clickable planets and symbolic lunar/asteroid markers; optional aspect lines, natal overlay, labels, and solar-system projection.
- **House methods:** Placidus, Whole Sign, Equal House; conventional longitude house placement and optional 3D Placidus placement; tropical or Lahiri sidereal zodiacs.
- **Transit forecasting:** 7/30/90-day sampled index graph, interactive timeline and date simulation, return to live.
- **Interpretive advisory areas:** Expandable warning/opportunity cards list ranked traditional themes. These are not event probabilities.
- **Experimental difficulty score:** Planetary baseline plus an optional capped ±0.65 auxiliary modifier. Node-axis contributions are deduplicated; changing overlay settings does not change scoring.
- **Observation Log:** Local experience journal kept in `data/observations.json`, Markdown and JSON exports, and optional explicit Joplin desktop Web Clipper note creation. Entries made in v0.2.5+ also capture which birth profile generated the comparison.
- **AI interoperability:** Portable Markdown/JSON calculation reports for ChatGPT or locally running LLMs. User decides what to share.

## Offline city list and time-zone provenance

The included lightweight city file derives largely from the public IANA time-zone database's `zone.tab` reference-place positions, with a curated list of additional approximate city centers. These are good starting coordinates for ordinary chart calculations; double-check them when the exact birth location is known. This is **not** a comprehensive gazetteer or an online geolocation service. IANA time-zone handling uses the Python `zoneinfo` API with `tzdata` fallback on platforms such as Windows. If you change birth coordinates or time zone after a chart was created, the saved chart recalculates independently.

## Technical and licensing information

- Engine: Python + `pysweph` / `pyswisseph` Swiss Ephemeris, Moshier calculations for major planets and lunar points, local Swiss asteroid ephemeris for Chiron (`ephe/seas_18.se1`).
- UI: HTML/CSS/JavaScript + Canvas 2D. Local HTTP server listens only on `127.0.0.1`.
- Files: `engine.py` calculations, `profile_manager.py` local birth-chart library and validation, `city_lookup.py` offline search, `server.py` API, `observation_log.py` local journal/Joplin bridge, `static/app.js` / `static/profiles.js` / `static/index.html` / `static/style.css` interface.
- `python -m unittest discover` runs tests. All local storage files and exports remain human-readable JSON/Markdown.
- Licensed under **AGPL-3.0-or-later**; see `LICENSE`. This project uses Swiss Ephemeris as a library in accordance with its licensing terms. Consult the upstream Swiss Ephemeris licensing conditions before redistributing modified builds for other licensing arrangements.
