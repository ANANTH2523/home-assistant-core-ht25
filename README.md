# Public Transport (GTFS-RT)

Public Transport is a custom Home Assistant integration that consumes GTFS-Realtime (protobuf) feeds and exposes three sensor types per configured stop:

- Minutes until the next departure (with delay information).
- Timestamp for the next departure.
- A summary sensor listing the next _N_ departures in a human-friendly string with structured attributes.

The integration works with any transit agency that publishes a GTFS-RT Trip Updates or Vehicle Positions feed and optionally requires an API key header.

## Features

- UI-based configuration and reconfiguration (config entry + options flow).
- Asynchronous polling with `DataUpdateCoordinator`.
- Robust GTFS-RT parsing using `gtfs-realtime-bindings`.
- Diagnostics panel with redacted secrets.
- Tests covering coordinator logic, config flow, sensors, diagnostics, and reload behaviour.

## Installation & Setup

1. Copy the `custom_components/public_transport` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant or reload custom integrations.
3. Navigate to **Settings → Devices & services → Add integration** and pick **Public Transport (GTFS-RT)**.
4. Enter the feed URL, optional API key header/value, your target stop identifiers, and (optionally) route filters, maximum departures, and polling interval.

### Developer workflow

From your Home Assistant Core checkout (or this repository), run:

```bash
pip install -r requirements_test.txt
pytest -q tests/components/public_transport
hass --script check_config
```

## Example Lovelace View (Blekinge transit dashboard)

The sample view below assumes you are using the demo feed or your real Trafiklab data, with stops in Blekinge county. Add the helper template sensors and zones first, then paste the Lovelace view. This replaces the simpler card examples from earlier.

### 1. Travel time, delay, and route suggestion sensors

Update the `template:` block in `configuration.yaml` with the sensors shown in this repository (they calculate travel time, delay, and provide a recommended line based on your “from” and “to” selections).

### 2. Zones, selectors, and automation

Copy the `zone`, `input_select`, and automation sections from `configuration.yaml`. They add markers for Karlskrona stops, a Blekinge highlight, a placeholder user marker, and a persistent notification whenever delays exceed two minutes.

### 3. Lovelace view

Point Home Assistant at `config/dashboards/blekinge_transit.yaml` (already referenced via the `lovelace` configuration). The view contains the trip planner selectors, next departures grid, route cheat sheet, world map focused on Blekinge, delay history graph, and feed log.

## Example Lovelace Cards (legacy)

### Entities card

```yaml
type: entities
title: Bus stop 1234
entities:
  - entity: sensor.public_transport_next_departure_minutes_stop1
    name: Next bus in minutes
  - entity: sensor.public_transport_next_departure_time_stop1
    name: Next bus timestamp
  - entity: sensor.public_transport_departure_summary_stop1
    name: Upcoming departures
```

### Markdown card (structured list)

```yaml
type: markdown
title: Stop 1234 departures
content: >
  {% set departures = state_attr('sensor.public_transport_departure_summary_stop1', 'departures') or [] %}
  {% if departures %}
  | Route | Headsign | ETA | Delay |
  | ----- | -------- | --- | ----- |
  {% for dep in departures %}
  | {{ dep.route_id }} | {{ dep.headsign or '—' }} | {{ dep.eta_minutes }} min | {{ dep.delay_minutes }} min |
  {% endfor %}
  {% else %}
  No upcoming departures.
  {% endif %}
```

## Example Automation

Notify when the next departure is delayed by more than five minutes:

```yaml
alias: Alert when bus is delayed
mode: single
trigger:
  - platform: state
    entity_id: sensor.public_transport_next_departure_minutes_stop1
condition:
  - condition: numeric_state
    entity_id: sensor.public_transport_next_departure_minutes_stop1
    above: 0
  - condition: template
    value_template: >
      {{ (state_attr('sensor.public_transport_next_departure_minutes_stop1', 'delay_seconds') | int(0)) >= 300 }}
action:
  - service: notify.mobile_app_phone
    data:
      title: "Delay alert"
      message: >
        Next bus {{ state_attr('sensor.public_transport_next_departure_minutes_stop1', 'route_id') }}
        is delayed by {{ (state_attr('sensor.public_transport_next_departure_minutes_stop1', 'delay_seconds') / 60) | int }} minutes.
```

## Troubleshooting

- Ensure the GTFS-RT feed returns Trip Updates containing your stop identifiers.
- If you see `invalid payload`, confirm the endpoint returns GTFS-RT protobuf bytes (not JSON).
- Use the integration’s diagnostics to inspect the last fetch, parsed trip count, and a sample of departures. Secrets such as API keys are automatically redacted.
