"""Tests for Public Transport sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiohttp import ClientError
from custom_components.public_transport.const import (
    CONF_FEED_URL,
    CONF_MAX_DEPS,
    CONF_ROUTE_IDS,
    CONF_SCAN_INTERVAL,
    CONF_STOP_IDS,
    DEFAULT_MAX_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_setup_and_attributes(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure sensors are created and populated."""

    now = datetime.now(UTC)
    feed_bytes = gtfs_trip_update(
        now=now,
        stop_id="STOP1",
        route_id="ROUTE1",
        headsign="Downtown",
        delay=timedelta(minutes=3),
        vehicle_id="BUS-1",
    )
    aioclient_mock.get("https://example.com/feed", content=feed_bytes)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FEED_URL: "https://example.com/feed",
            CONF_STOP_IDS: ["STOP1"],
            CONF_ROUTE_IDS: [],
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
        unique_id=slugify("https://example.com/feed"),
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    minutes_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_STOP1_next_minutes",
    )
    assert minutes_entity_id is not None
    state = hass.states.get(minutes_entity_id)
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["route_id"] == "ROUTE1"
    assert state.attributes["delay_seconds"] == 180

    timestamp_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_STOP1_next_timestamp",
    )
    ts_state = hass.states.get(timestamp_entity_id)
    assert ts_state is not None
    assert ts_state.attributes["route_id"] == "ROUTE1"
    assert ts_state.attributes["delay_seconds"] == 180

    summary_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_STOP1_summary",
    )
    summary_state = hass.states.get(summary_entity_id)
    assert summary_state is not None
    assert "ROUTE1" in summary_state.state
    assert isinstance(summary_state.attributes["departures"], list)


async def test_sensor_availability_on_error(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure sensors become unavailable after update failure."""

    now = datetime.now(UTC)
    feed_bytes = gtfs_trip_update(now=now, stop_id="STOP1")
    aioclient_mock.get("https://example.com/feed", content=feed_bytes)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FEED_URL: "https://example.com/feed",
            CONF_STOP_IDS: ["STOP1"],
            CONF_ROUTE_IDS: [],
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: 30,
        },
        unique_id=slugify("https://example.com/feed"),
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    minutes_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_STOP1_next_minutes",
    )
    assert minutes_entity_id is not None

    # Force subsequent refresh to fail
    aioclient_mock.clear_requests()
    aioclient_mock.get("https://example.com/feed", exc=ClientError())

    async_fire_time_changed(hass, datetime.now(UTC) + timedelta(seconds=31))
    await hass.async_block_till_done()

    state = hass.states.get(minutes_entity_id)
    assert state is not None
    assert state.state == "unavailable"
