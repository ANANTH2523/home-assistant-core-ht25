"""Diagnostics support for the Public Transport integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_KEY_VALUE,
    CONF_FEED_URL,
    CONF_MAX_DEPS,
    CONF_ROUTE_IDS,
    CONF_SCAN_INTERVAL,
    CONF_STOP_IDS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import PublicTransportConfigEntry
    from .models import Departure

TO_REDACT = {CONF_API_KEY_VALUE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PublicTransportConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    departures_sample: dict[str, list[dict[str, Any]]] = {}
    for stop_id, departures in (coordinator.data or {}).items():
        departures_sample[stop_id] = [_departure_to_dict(dep) for dep in departures[:2]]

    diag: dict[str, Any] = {
        "config": {
            CONF_FEED_URL: coordinator.config.feed_url,
            CONF_STOP_IDS: coordinator.config.stop_ids,
            CONF_ROUTE_IDS: (
                sorted(coordinator.config.route_ids)
                if coordinator.config.route_ids
                else []
            ),
            CONF_MAX_DEPS: coordinator.config.max_departures,
            CONF_SCAN_INTERVAL: int(coordinator.config.scan_interval.total_seconds()),
            CONF_API_KEY_VALUE: coordinator.config.api_key_value,
        },
        "last_fetch": (
            dt_util.as_local(coordinator.last_fetch).isoformat()
            if coordinator.last_fetch
            else None
        ),
        "trip_count": coordinator.last_trip_count,
        "departure_sample": departures_sample,
    }

    return async_redact_data(diag, TO_REDACT)


def _departure_to_dict(departure: Departure) -> dict[str, Any]:
    """Convert a departure dataclass into a serialisable mapping."""
    return {
        "stop_id": departure.stop_id,
        "route_id": departure.route_id,
        "headsign": departure.headsign,
        "scheduled_time": dt_util.as_local(departure.scheduled_time).isoformat(),
        "arrival_time": dt_util.as_local(departure.arrival_time).isoformat(),
        "delay_seconds": departure.delay_seconds,
        "vehicle_id": departure.vehicle_id,
    }
