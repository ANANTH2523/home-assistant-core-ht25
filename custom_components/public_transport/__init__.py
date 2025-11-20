"""Public Transport (GTFS-RT) integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_API_KEY_HEADER,
    CONF_API_KEY_VALUE,
    CONF_DEMO_RANDOM,
    CONF_MAX_DEPS,
    CONF_ROUTE_IDS,
    CONF_SCAN_INTERVAL,
    CONF_STOP_IDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import PublicTransportDataUpdateCoordinator
from .models import GtfsConfig

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

type PublicTransportConfigEntry = ConfigEntry[PublicTransportDataUpdateCoordinator]


async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,  # noqa: ARG001
) -> bool:
    """Set up the Public Transport integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: PublicTransportConfigEntry,
) -> bool:
    """Set up Public Transport from a config entry."""
    coordinator = PublicTransportDataUpdateCoordinator(hass, _config_from_entry(entry))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PublicTransportConfigEntry,
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_options_updated(
    hass: HomeAssistant, entry: PublicTransportConfigEntry,
) -> None:
    """Handle config entry options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


def _config_from_entry(entry: PublicTransportConfigEntry) -> GtfsConfig:
    """Create a GtfsConfig object from the config entry."""
    data = entry.data
    options = entry.options

    stop_ids_raw = options.get(CONF_STOP_IDS, data[CONF_STOP_IDS])
    stop_ids = list(stop_ids_raw)

    route_ids_option = options.get(CONF_ROUTE_IDS, data.get(CONF_ROUTE_IDS))
    route_ids = set(route_ids_option) if route_ids_option else None

    max_departures = int(options.get(CONF_MAX_DEPS, data.get(CONF_MAX_DEPS)))
    scan_seconds = int(options.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL)))

    # Enable demo mode by default for the local demo feed
    default_demo = "localhost:8081" in data.get("feed_url", "")

    return GtfsConfig(
        feed_url=data["feed_url"],
        api_key_header_name=data.get(CONF_API_KEY_HEADER),
        api_key_value=data.get(CONF_API_KEY_VALUE),
        stop_ids=stop_ids,
        route_ids=route_ids,
        max_departures=max_departures,
        scan_interval=timedelta(seconds=scan_seconds),
        demo_random=bool(
            options.get(CONF_DEMO_RANDOM, data.get(CONF_DEMO_RANDOM, default_demo)),
        ),
    )
