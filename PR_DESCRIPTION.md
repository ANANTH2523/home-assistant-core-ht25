# Public Transport (GTFS-RT) – New Integration

## What & Why
This integration fetches GTFS-Realtime data (protobuf) and exposes Home Assistant sensors showing upcoming departures, ETAs, and delays for selected stop(s)/route(s). It supports a GTFS-RT feed URL, optional API key header, polling interval, and the number of departures to display.

- Live departures & delay display on Lovelace.
- Reusable for any city/operator that exposes GTFS-RT.
- No hardware required; cloud polling via DataUpdateCoordinator.

## Implementation Notes
- Config & Options Flow.
- Robust parsing with `gtfs-realtime-bindings`.
- Entities: next departure minutes, timestamp, and a summary.
- Diagnostics with redacted secrets.
- Comprehensive tests: config flow, coordinator, sensors, diagnostics, reload.

## Group Member Contributions
- Member A: Config/Options Flow, translations, diagnostics.
- Member B: Coordinator parsing, sensor entities, error handling.
- Member C: Test suite (config flow, coordinator, sensors, diagnostics), CI.
- Member D: README, example dashboard/automations, video walkthrough.

## Test Evidence
- Command run: `pytest -q tests/components/public_transport`
- Include screenshot or summary of passed tests and coverage.
