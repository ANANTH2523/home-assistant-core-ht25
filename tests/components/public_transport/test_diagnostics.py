"""Tests for diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.public_transport import diagnostics
from custom_components.public_transport.const import (
    CONF_API_KEY_HEADER,
    CONF_API_KEY_VALUE,
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
from homeassistant.util import slugify

from tests.common import MockConfigEntry


async def test_diagnostics_redacts_api_key(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure diagnostics return structured output with redactions."""

    now = datetime.now(UTC)
    aioclient_mock.get(
        "https://example.com/feed", content=gtfs_trip_update(now=now, stop_id="STOP1")
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FEED_URL: "https://example.com/feed",
            CONF_STOP_IDS: ["STOP1"],
            CONF_ROUTE_IDS: [],
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_API_KEY_HEADER: "X-Key",
            CONF_API_KEY_VALUE: "super-secret",
        },
        unique_id=slugify("https://example.com/feed"),
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    data = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert data["config"][CONF_FEED_URL] == "https://example.com/feed"
    assert data["config"][CONF_MAX_DEPS] == DEFAULT_MAX_DEPARTURES
    assert data["config"][CONF_API_KEY_VALUE] == "REDACTED"
    assert data["departure_sample"]
