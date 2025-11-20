"""Test the config flow for the Public Transport integration."""

from __future__ import annotations

from datetime import UTC, datetime

from aiohttp import ClientError
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
import pytest

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("minimal_config_entry_data")
async def test_form_success(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Test that the config flow works."""

    now = datetime.now(UTC)
    aioclient_mock.get("https://example.com/gtfs-rt", content=gtfs_trip_update(now=now))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "",
            CONF_API_KEY_VALUE: "",
            CONF_STOP_IDS: "STOP1",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_STOP_IDS] == ["STOP1"]
    assert result2["data"][CONF_ROUTE_IDS] == []


async def test_form_invalid_payload(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Test errors when payload cannot be parsed."""

    aioclient_mock.get("https://example.com/gtfs-rt", content=b"not protobuf")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "",
            CONF_API_KEY_VALUE: "",
            CONF_STOP_IDS: "STOP1",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_payload"


async def test_form_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Test errors when HTTP request fails."""

    aioclient_mock.get("https://example.com/gtfs-rt", exc=ClientError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "",
            CONF_API_KEY_VALUE: "",
            CONF_STOP_IDS: "STOP1",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_form_rejects_empty_stop_ids(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Ensure stop IDs are validated."""

    aioclient_mock.get("https://example.com/gtfs-rt", content=b"")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "",
            CONF_API_KEY_VALUE: "",
            CONF_STOP_IDS: "   ",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"][CONF_STOP_IDS] == "invalid_stop_ids"


async def test_form_includes_api_header(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure optional API header is sent."""

    now = datetime.now(UTC)
    aioclient_mock.get("https://example.com/gtfs-rt", content=gtfs_trip_update(now=now))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "X-API-Key",
            CONF_API_KEY_VALUE: "secret",
            CONF_STOP_IDS: "STOP1",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    # Allow one or more calls; verify that at least one request to the feed URL
    # included the expected header.
    assert aioclient_mock.call_count >= 1
    calls_with_header = [
        c for c in aioclient_mock.mock_calls
        if c[1] == ("https://example.com/gtfs-rt",) and c[2].get("headers", {}).get("X-API-Key") == "secret"
    ]
    assert calls_with_header, "Expected X-API-Key header on at least one GET to the feed URL"


async def test_duplicate_entry_aborts(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure duplicate feeds are rejected."""

    now = datetime.now(UTC)
    aioclient_mock.get("https://example.com/gtfs-rt", content=gtfs_trip_update(now=now))

    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_STOP_IDS: ["STOP1"],
            CONF_ROUTE_IDS: [],
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_API_KEY_HEADER: None,
            CONF_API_KEY_VALUE: None,
        },
        unique_id=slugify("https://example.com/gtfs-rt"),
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FEED_URL: "https://example.com/gtfs-rt",
            CONF_API_KEY_HEADER: "",
            CONF_API_KEY_VALUE: "",
            CONF_STOP_IDS: "STOP1",
            CONF_ROUTE_IDS: "",
            CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow_updates_values(
    hass: HomeAssistant,
    aioclient_mock,
    minimal_config_entry_data,
    gtfs_trip_update,
) -> None:
    """Ensure the options flow allows updates."""

    now = datetime.now(UTC)
    aioclient_mock.get("https://example.com/gtfs-rt", content=gtfs_trip_update(now=now))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=minimal_config_entry_data,
        unique_id=slugify("https://example.com/gtfs-rt"),
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_STOP_IDS: "STOP1,STOP2",
            CONF_ROUTE_IDS: "ROUTE1",
            CONF_MAX_DEPS: 3,
            CONF_SCAN_INTERVAL: 45,
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_STOP_IDS] == ["STOP1", "STOP2"]
    assert result2["data"][CONF_ROUTE_IDS] == ["ROUTE1"]
    assert result2["data"][CONF_MAX_DEPS] == 3
    assert result2["data"][CONF_SCAN_INTERVAL] == 45
