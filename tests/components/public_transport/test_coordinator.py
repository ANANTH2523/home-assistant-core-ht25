"""Tests for the Public Transport coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiohttp import ClientError
from custom_components.public_transport.const import DEFAULT_MAX_DEPARTURES
from custom_components.public_transport.coordinator import (
    PublicTransportDataUpdateCoordinator,
)
from custom_components.public_transport.models import GtfsConfig
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_parses_feed(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Verify the coordinator parses protobuf data."""

    now = datetime.now(UTC)
    feed_bytes = gtfs_trip_update(now=now, stop_id="STOP1", route_id="ROUTE1")
    aioclient_mock.get("https://example.com/feed", content=feed_bytes)

    config = GtfsConfig(
        feed_url="https://example.com/feed",
        stop_ids=["STOP1"],
        route_ids=None,
        max_departures=DEFAULT_MAX_DEPARTURES,
        scan_interval=timedelta(seconds=30),
    )

    coordinator = PublicTransportDataUpdateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data
    departures = coordinator.data["STOP1"]
    assert departures[0].route_id == "ROUTE1"
    assert departures[0].delay_seconds == 120
    assert coordinator.last_trip_count == 1
    assert coordinator.last_fetch is not None


async def test_coordinator_filters_routes(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Verify route filtering."""

    now = datetime.now(UTC)
    feed_bytes = gtfs_trip_update(now=now, stop_id="STOP1", route_id="ROUTE2")
    aioclient_mock.get("https://example.com/feed", content=feed_bytes)

    config = GtfsConfig(
        feed_url="https://example.com/feed",
        stop_ids=["STOP1"],
        route_ids={"ROUTE1"},
        max_departures=DEFAULT_MAX_DEPARTURES,
        scan_interval=timedelta(seconds=30),
    )

    coordinator = PublicTransportDataUpdateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {}


async def test_coordinator_handles_network_errors(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Ensure network failures raise UpdateFailed."""

    aioclient_mock.get("https://example.com/feed", exc=ClientError())

    config = GtfsConfig(
        feed_url="https://example.com/feed",
        stop_ids=["STOP1"],
        route_ids=None,
        max_departures=DEFAULT_MAX_DEPARTURES,
        scan_interval=timedelta(seconds=30),
    )
    coordinator = PublicTransportDataUpdateCoordinator(hass, config)

    with pytest.raises(UpdateFailed):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_empty_feed(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Ensure empty feeds produce no departures."""

    aioclient_mock.get("https://example.com/feed", content=b"")

    config = GtfsConfig(
        feed_url="https://example.com/feed",
        stop_ids=["STOP1"],
        route_ids=None,
        max_departures=DEFAULT_MAX_DEPARTURES,
        scan_interval=timedelta(seconds=30),
    )
    coordinator = PublicTransportDataUpdateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data == {}
    assert coordinator.last_trip_count == 0


async def test_coordinator_updates_with_new_data(
    hass: HomeAssistant,
    aioclient_mock,
    gtfs_trip_update,
) -> None:
    """Ensure subsequent refreshes update departures."""

    now = datetime.now(UTC)
    feed_first = gtfs_trip_update(now=now, arrival_offset=timedelta(minutes=5))
    feed_second = gtfs_trip_update(
        now=now + timedelta(minutes=1), arrival_offset=timedelta(minutes=3)
    )

    aioclient_mock.get("https://example.com/feed", content=feed_first)

    config = GtfsConfig(
        feed_url="https://example.com/feed",
        stop_ids=["STOP1"],
        route_ids=None,
        max_departures=DEFAULT_MAX_DEPARTURES,
        scan_interval=timedelta(seconds=30),
    )
    coordinator = PublicTransportDataUpdateCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    first_eta = coordinator.data["STOP1"][0].eta_minutes

    aioclient_mock.clear_requests()
    aioclient_mock.get("https://example.com/feed", content=feed_second)

    await coordinator.async_refresh()

    assert coordinator.data["STOP1"][0].eta_minutes <= first_eta
