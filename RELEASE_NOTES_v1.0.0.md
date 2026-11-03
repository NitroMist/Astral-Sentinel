# Astral Sentinel 1.0.0 · Release notes

## Scope

This release freezes the main v0.2.5 feature set and focuses on stability, packaging, and privacy. It does **not** change birth-chart astronomy, planetary scoring weights, or how interpretive warnings are classified.

### Improvements

- Full version labeling updated to 1.0.0 across engine, server, UI and JSON exports.
- Reject unexpected `Host` and `Origin` headers on local GET and POST requests, reducing local-service DNS rebinding exposure.
- Add explicit no-referrer and deny-framing security headers.
- Ignore stale errors from earlier calculation requests that finish after a newer request succeeds.
- Reject forecast-inclusive exports if settings, loaded profile, or chart request changed mid-export.
- Skip Canvas 2D drawing while another tab or browser page is active; return to normal rendering when Observatory is visible.
- Public edition contains only a demo profile; update patch excludes all user-specific `data` and `ephe` files.

### Install and update

**Existing installation:** Back up the entire `data` folder, stop the server, then extract `Astral_Sentinel_v1.0.0_Private_Update_Patch.zip` over the application root. The ZIP has no `data/` folder and does not touch `.venv` or `ephe/`. Restart `Launch_Astral_Sentinel.bat` and refresh Firefox with Ctrl+Shift+R. Your saved charts, reference-chart comparison and observations remain in place.

**New / shareable installation:** Extract `Astral_Sentinel_v1.0.0_Shareable_Complete.zip`, open its `astral_sentinel_v1_0_0` folder and run `Launch_Astral_Sentinel.bat`. Python and a one-time online dependency install are required. Create your own profile under Natal Scan → Birth Chart Library. The app itself runs locally afterwards.

**Not a native Windows EXE:** This is a source-and-launcher ZIP. Python 3.10–3.13 is needed; the first run installs dependency wheels and uses a local `.venv`.

### Security / privacy

The web server binds to `127.0.0.1` and saves its journal and chart library locally. Joplin sync only occurs after an explicit Send action. Don't distribute the contents of your used `data` folder or personal exports; the public ZIP contains only a generic London demonstration chart. The model's score is a qualitative experiment and should not be treated as an objective real-world danger forecast.

### Known limits

- Browsers on Windows/Firefox still require a final machine-specific smoke test; automated tests run in a Linux-based environment.
- Location autocomplete uses a limited offline city catalog, not a complete place database.
- Birth-time validity depends on the supplied birth record and historical IANA timezone data, some of which is uncertain in older eras.
- First setup needs an internet connection to install Python packages; Joplin connectivity requires the desktop Web Clipper to be enabled.
- Forecast extrema are sampled, not guaranteed exact event times.

### License

AGPL-3.0-or-later; bundled Swiss Ephemeris asteroid data and Python Swiss Ephemeris bindings retain their upstream licensing terms. See LICENSE and ephe/README.txt.
