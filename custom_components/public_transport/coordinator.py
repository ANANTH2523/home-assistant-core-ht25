"""DataUpdateCoordinator for the Public Transport integration."""

from __future__ import annotations

from collections import defaultdict
import logging
from typing import TYPE_CHECKING

from aiohttp import ClientError, ClientResponseError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .gtfs import gtfs_realtime_pb2
from .models import Departure, GtfsConfig

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PublicTransportData = dict[str, list[Departure]]


class PublicTransportDataUpdateCoordinator(DataUpdateCoordinator[PublicTransportData]):
    """Coordinator that retrieves GTFS-RT data."""

    config: GtfsConfig
    last_fetch: datetime | None
    last_trip_count: int

    def __init__(self, hass: HomeAssistant, config: GtfsConfig) -> None:
        """Initialize the coordinator."""
        self.config = config
        self._session = async_get_clientsession(hass)
        self.last_fetch = None
        self.last_trip_count = 0

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=config.scan_interval,
        )

    async def _async_update_data(self) -> PublicTransportData:  # noqa: PLR0915
        """Fetch GTFS-RT data and compile departures."""
        headers: dict[str, str] = {}
        if self.config.api_key_header_name and self.config.api_key_value:
            headers[self.config.api_key_header_name] = self.config.api_key_value

        try:
            async with self._session.get(
                self.config.feed_url, headers=headers, raise_for_status=True,
            ) as response:
                payload = await response.read()
        except ClientResponseError as err:
            msg = f"HTTP error {err.status}"
            raise UpdateFailed(msg) from err
        except ClientError as err:
            msg = f"Network error: {err}"
            raise UpdateFailed(msg) from err

        feed_message = gtfs_realtime_pb2.FeedMessage()
        try:
            feed_message.ParseFromString(payload)
        except Exception as err:
            msg = f"Could not parse GTFS-RT payload: {err}"
            raise UpdateFailed(msg) from err

        departures_by_stop: defaultdict[str, list[Departure]] = defaultdict(list)

        now = dt_util.utcnow()
        stop_filter = set(self.config.stop_ids)
        route_filter = self.config.route_ids
        trip_count = 0

        for entity in feed_message.entity:
            trip_update = getattr(entity, "trip_update", None)
            if not trip_update or not trip_update.stop_time_update:
                continue

            trip_count += 1
            route_id = trip_update.trip.route_id or "unknown"

            if route_filter and route_id not in route_filter:
                continue

            headsign = getattr(trip_update.trip, "trip_headsign", None)
            vehicle_id = (
                trip_update.vehicle.id if trip_update.HasField("vehicle") else None
            )

            for update in trip_update.stop_time_update:
                stop_id = update.stop_id
                if stop_id not in stop_filter:
                    continue

                arrival_event = update.arrival if update.HasField("arrival") else None
                departure_event = (
                    update.departure if update.HasField("departure") else None
                )

                event = arrival_event or departure_event
                if event is None or not event.time:
                    continue

                arrival_time = dt_util.utc_from_timestamp(event.time)
                delay_seconds = event.delay if event.delay else 0

                scheduled_epoch = (
                    event.time - delay_seconds if delay_seconds else event.time
                )
                scheduled_time = dt_util.utc_from_timestamp(scheduled_epoch)

                stop_headsign = getattr(update, "stop_headsign", None)
                departure = Departure(
                    stop_id=stop_id,
                    route_id=route_id,
                    headsign=stop_headsign or headsign,
                    scheduled_time=scheduled_time,
                    arrival_time=arrival_time,
                    delay_seconds=delay_seconds,
                    vehicle_id=vehicle_id,
                )

                departures_by_stop[stop_id].append(departure)

        max_departures = self.config.max_departures
        for stop_id in list(departures_by_stop):
            departures_by_stop[stop_id].sort(key=lambda dep: dep.arrival_time)
            departures_by_stop[stop_id] = departures_by_stop[stop_id][:max_departures]

        for stop_id in self.config.stop_ids:
            departures_by_stop.setdefault(stop_id, [])

        self.last_fetch = now
        self.last_trip_count = trip_count

        return dict(departures_by_stop)
