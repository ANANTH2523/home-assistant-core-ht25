"""Tests for reload handling."""

from __future__ import annotations

from datetime import UTC, datetime

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

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from tests.common import MockConfigEntry


async def test_reload_restores_entities(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure unloading and reloading restores sensors."""

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
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
        unique_id=slugify("https://example.com/feed"),
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_STOP1_next_minutes"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert entry.state is ConfigEntryState.NOT_LOADED

    aioclient_mock.clear_requests()
    aioclient_mock.get("https://example.com/feed", content=feed_bytes)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is not None
    assert entry.state is ConfigEntryState.LOADED
