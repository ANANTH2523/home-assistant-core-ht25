"""Constants for the Public Transport integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "public_transport"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_MAX_DEPARTURES = 5

CONF_FEED_URL = "feed_url"
CONF_API_KEY_HEADER = "api_key_header_name"
CONF_API_KEY_VALUE = "api_key_value"
CONF_STOP_IDS = "stop_ids"
CONF_ROUTE_IDS = "route_ids"
CONF_MAX_DEPS = "max_departures"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEMO_RANDOM = "demo_random"

PLATFORMS: list[Platform] = [Platform.SENSOR]

MIN_SCAN_INTERVAL = timedelta(seconds=15)
MAX_SCAN_INTERVAL = timedelta(minutes=10)
