"""Common fixtures for the Public Transport integration tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

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
)
from custom_components.public_transport.gtfs import gtfs_realtime_pb2
import pytest

TEST_FEED_URL = "https://example.com/gtfs-rt"


@pytest.fixture
def gtfs_trip_update() -> Callable[..., bytes]:
    """Return a factory generating GTFS-RT trip updates."""

    def _factory(
        *,
        now: datetime,
        stop_id: str = "STOP1",
        route_id: str = "ROUTE1",
        headsign: str = "Downtown",
        arrival_offset: timedelta = timedelta(minutes=5),
        delay: timedelta = timedelta(minutes=2),
        trip_id: str = "trip-1",
        vehicle_id: str = "vehicle-1",
    ) -> bytes:
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        entity = feed.entity.add()
        entity.id = f"entity-{trip_id}"
        trip_update = entity.trip_update
        trip_update.trip.trip_id = trip_id
        trip_update.trip.route_id = route_id
        trip_update.vehicle.id = vehicle_id

        update = trip_update.stop_time_update.add()
        update.stop_id = stop_id
        update.stop_sequence = 1
        update.arrival.time = int((now + arrival_offset).timestamp())
        update.arrival.delay = int(delay.total_seconds())

        return feed.SerializeToString()

    return _factory


@pytest.fixture
def minimal_config_entry_data() -> dict[str, Any]:
    """Return minimal configuration payload."""

    return {
        CONF_FEED_URL: TEST_FEED_URL,
        CONF_STOP_IDS: ["STOP1"],
        CONF_ROUTE_IDS: [],
        CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_API_KEY_HEADER: None,
        CONF_API_KEY_VALUE: None,
    }


@pytest.fixture
def mock_options() -> dict[str, Any]:
    """Return default options."""

    return {
        CONF_STOP_IDS: ["STOP1"],
        CONF_ROUTE_IDS: [],
        CONF_MAX_DEPS: DEFAULT_MAX_DEPARTURES,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }
