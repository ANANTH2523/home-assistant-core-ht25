"""Sensor platform for the Public Transport integration."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import PublicTransportDataUpdateCoordinator
from .models import Departure, summarize_departures

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.helpers.entity_platform import AddEntitiesCallback

type PublicTransportConfigEntry = ConfigEntry[PublicTransportDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PublicTransportConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = entry.runtime_data
    entities: list[PublicTransportBaseSensor] = []

    for stop_id in coordinator.config.stop_ids:
        entities.append(NextDepartureMinutesSensor(coordinator, entry, stop_id))
        entities.append(NextDepartureTimestampSensor(coordinator, entry, stop_id))
        entities.append(DeparturesSummarySensor(coordinator, entry, stop_id))

    # Additional helper sensors
    entities.append(StopsListSensor(coordinator, entry))
    entities.append(NextBusesLiveSensor(coordinator, entry))
    # Fixed pair sensor: Karlskrona Central -> Lyckeby centrum
    entities.append(FixedPairNextBusesSensor(coordinator, entry))

    async_add_entities(entities)


class PublicTransportBaseSensor(
    CoordinatorEntity[PublicTransportDataUpdateCoordinator],
    SensorEntity,
):
    """Base class for Public Transport sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
        stop_id: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Public transport feed",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_name = None

    @property
    def _departures(self) -> list[Departure]:
        """Return departures for the stop."""
        data = self.coordinator.data or {}
        return list(data.get(self._stop_id, []))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and bool(self.coordinator.last_fetch)

    def _base_attrs(self) -> dict[str, Any]:
        """Shared state attributes."""
        attrs: dict[str, Any] = {
            "stop_id": self._stop_id,
            "last_update": dt_util.as_local(self.coordinator.last_fetch).isoformat()
            if self.coordinator.last_fetch
            else None,
        }
        return attrs


class NextDepartureMinutesSensor(PublicTransportBaseSensor):
    """Sensor returning minutes until next departure."""

    _attr_translation_key = "next_departure_minutes"

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
        stop_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, stop_id)
        self._attr_unique_id = f"{entry.entry_id}_{stop_id}_next_minutes"
        self._attr_translation_placeholders = {"stop_id": stop_id}

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        if not (departure := self._next_departure()):
            return None
        return max(departure.eta_minutes, 0)

    def _next_departure(self) -> Departure | None:
        """Return the first departure."""
        departures = self._departures
        return departures[0] if departures else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs = self._base_attrs()
        departure = self._next_departure()
        if departure:
            attrs.update(
                {
                    "route_id": departure.route_id,
                    "headsign": departure.headsign,
                    "scheduled_time": dt_util.as_local(
                        departure.scheduled_time,
                    ).isoformat(),
                    "arrival_time": dt_util.as_local(
                        departure.arrival_time,
                    ).isoformat(),
                    "delay_seconds": departure.delay_seconds,
                    "vehicle_id": departure.vehicle_id,
                },
            )
        return attrs


class NextDepartureTimestampSensor(PublicTransportBaseSensor):
    """Sensor returning timestamp of next departure."""

    _attr_translation_key = "next_departure_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
        stop_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, stop_id)
        self._attr_unique_id = f"{entry.entry_id}_{stop_id}_next_timestamp"
        self._attr_translation_placeholders = {"stop_id": stop_id}

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp."""
        departure = self._departures[0] if self._departures else None
        if not departure:
            return None
        return departure.arrival_time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes."""
        attrs = self._base_attrs()
        departure = self._departures[0] if self._departures else None
        if departure:
            attrs.update(
                {
                    "route_id": departure.route_id,
                    "headsign": departure.headsign,
                    "delay_seconds": departure.delay_seconds,
                    "vehicle_id": departure.vehicle_id,
                },
            )
        return attrs


class DeparturesSummarySensor(PublicTransportBaseSensor):
    """Sensor providing a textual summary of departures."""

    _attr_translation_key = "departures_summary"

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
        stop_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, stop_id)
        self._attr_unique_id = f"{entry.entry_id}_{stop_id}_summary"
        self._attr_translation_placeholders = {"stop_id": stop_id}

    @property
    def native_value(self) -> str:
        """Return the summary state."""
        summary, _ = summarize_departures(
            self._departures,
            self.coordinator.config.max_departures,
        )
        return summary

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return structured attribute data."""
        attrs = self._base_attrs()
        summary, structured = summarize_departures(
            self._departures,
            self.coordinator.config.max_departures,
        )
        attrs["departures"] = structured
        attrs["summary"] = summary
        return attrs


def _read_static_stops(hass: HomeAssistant) -> tuple[dict[str, str], dict[str, str]]:
    """Load stop name/id mapping from demo static GTFS if present.

    Returns (name_to_id, id_to_name).
    """
    # Try the demo path relative to config directory
    config_dir = Path(hass.config.path())
    repo_root = config_dir.parent
    static_stops = (
        repo_root / "demo_data" / "public_transport_demo" / "static" / "stops.txt"
    )

    cache = hass.data.setdefault(DOMAIN, {})
    if (cached := cache.get("_stops_cache")) is not None:
        return cached

    name_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}

    if static_stops.exists():
        # Read in executor to avoid blocking event loop
        content = static_stops.read_text(encoding="utf-8")
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            stop_id = (row.get("stop_id") or "").strip()
            stop_name = (row.get("stop_name") or stop_id).strip()
            if not stop_id:
                continue
            id_to_name[stop_id] = stop_name
            # Prefer title-case names consistently
            name_to_id[stop_name] = stop_id

    cache["_stops_cache"] = (name_to_id, id_to_name)
    return cache["_stops_cache"]


def _read_static_routes(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    """Return static routes mapping: route_id -> {short_name,long_name,route_type}.

    Cached in hass.data[DOMAIN]["_routes_cache"].
    """
    cache = hass.data.setdefault(DOMAIN, {})
    if (cached := cache.get("_routes_cache")) is not None:
        return cached

    config_dir = Path(hass.config.path())
    repo_root = config_dir.parent
    routes_path = (
        repo_root / "demo_data" / "public_transport_demo" / "static" / "routes.txt"
    )

    mapping: dict[str, dict[str, str]] = {}
    if routes_path.exists():
        content = routes_path.read_text(encoding="utf-8")
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            rid = (row.get("route_id") or "").strip()
            if not rid:
                continue
            mapping[rid] = {
                "route_short_name": (row.get("route_short_name") or "").strip(),
                "route_long_name": (row.get("route_long_name") or "").strip(),
                "route_type": (row.get("route_type") or "").strip(),
            }

    cache["_routes_cache"] = mapping
    return mapping


def _ascii_fold(s: str) -> str:
    """Return a best-effort ASCII-folded lower-case string for name matching."""
    return (
        s.lower()
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ö", "o")
        .replace("Ä", "a")
        .replace("Å", "a")
        .replace("Ö", "o")
    )


def _resolve_stop_id(
    hass: HomeAssistant,
    coordinator: PublicTransportDataUpdateCoordinator,
    name_or_id: str,
) -> str | None:
    """Resolve a human name or id to a stop_id using static mapping or fallbacks."""
    name_to_id, _ = _read_static_stops(hass)
    if name_or_id in name_to_id:
        return name_to_id[name_or_id]

    # Case-insensitive name match
    lower_map = {k.lower(): v for k, v in name_to_id.items()}
    lower_key = name_or_id.lower()
    if lower_key in lower_map:
        return lower_map[lower_key]

    # Diacritics-insensitive match (ASCII fold)
    folded_map = {_ascii_fold(k): v for k, v in name_to_id.items()}
    folded_key = _ascii_fold(name_or_id)
    if folded_key in folded_map:
        return folded_map[folded_key]

    # If already an id present in live data, accept it
    if name_or_id in getattr(coordinator, "all_stop_ids", set()):
        return name_or_id

    # Case-insensitive fallback match on names
    for stop_id in getattr(coordinator, "all_stop_ids", set()):
        if stop_id.lower() == lower_key or _ascii_fold(stop_id) == folded_key:
            return stop_id
    return None


class StopsListSensor(
    CoordinatorEntity[PublicTransportDataUpdateCoordinator],
    SensorEntity,
):
    """Sensor exposing all known stops from GTFS (static if available, else RT)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "stops"

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stops"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Public transport feed",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_name = "Public transport stops"

    @property
    def native_value(self) -> int | None:
        """Return the number of stops."""
        stops = self._collect_stops()
        return len(stops) if stops else None

    def _collect_stops(self) -> list[dict[str, str]]:
        hass = self.hass
        _name_to_id, id_to_name = _read_static_stops(hass)

        stops: list[dict[str, str]] = []
        if id_to_name:
            for stop_id, name in sorted(id_to_name.items(), key=lambda x: x[1].lower()):
                stops.append({"id": stop_id, "name": name})
        else:
            stops.extend(
                {"id": stop_id, "name": stop_id}
                for stop_id in sorted(getattr(self.coordinator, "all_stop_ids", set()))
            )
        return stops

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "stops": self._collect_stops(),
            "last_update": dt_util.as_local(self.coordinator.last_fetch).isoformat()
            if self.coordinator.last_fetch
            else None,
        }


class NextBusesLiveSensor(
    CoordinatorEntity[PublicTransportDataUpdateCoordinator],
    SensorEntity,
):
    """Sensor that exposes the next 2 buses between selected from/to stops."""

    _attr_should_poll = False
    # We want a stable entity_id: sensor.next_buses_live
    _attr_has_entity_name = False
    _attr_translation_key = "next_buses_live"

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_next_buses"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Public transport feed",
            entry_type=DeviceEntryType.SERVICE,
        )
        # Use a fixed name so entity_id becomes sensor.next_buses_live
        self._attr_name = "next_buses_live"

    async def async_added_to_hass(self) -> None:
        """Register state change listeners."""
        await super().async_added_to_hass()

        @callback
        def _inputs_changed(event) -> None:  # noqa: ARG001, ANN001
            # Recompute immediately when selections change
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                {"input_select.transit_from_stop", "input_select.transit_to_stop"},
                _inputs_changed,
            ),
        )

    @property
    def native_value(self) -> str:
        """Return the number of departures."""
        from_name = self.hass.states.get("input_select.transit_from_stop")
        to_name = self.hass.states.get("input_select.transit_to_stop")
        if not from_name or not to_name:
            return "0 departures"

        from_stop = _resolve_stop_id(self.hass, self.coordinator, str(from_name.state))
        to_stop = _resolve_stop_id(self.hass, self.coordinator, str(to_name.state))
        if not from_stop or not to_stop:
            return "0 departures"

        rows = self.coordinator.compute_next_buses(
            from_stop,
            to_stop,
            limit=5,
            only_buses=True,
        )
        return f"{len(rows)} departures"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        from_name = self.hass.states.get("input_select.transit_from_stop")
        to_name = self.hass.states.get("input_select.transit_to_stop")
        formatted_lines: list[str] = []
        buses: list[dict[str, Any]] = []

        # Helpers for label formatting
        _, _id_to_name = _read_static_stops(self.hass)
        routes_map = _read_static_routes(self.hass)

        def _route_label(route_id: str) -> str:
            r = routes_map.get(route_id)
            if not r:
                return route_id
            short = r.get("route_short_name") or ""
            rtype = r.get("route_type") or ""
            if rtype == "3":  # bus
                return f"City Bus {short or route_id}"
            if rtype == "2":  # rail
                return f"Train {short or route_id}"
            return short or route_id

        def _fmt_hm(iso_string: str) -> str:
            dt = dt_util.parse_datetime(iso_string)
            if dt is None:
                return iso_string
            return dt_util.as_local(dt).strftime("%H:%M")

        if from_name and to_name:
            from_stop = _resolve_stop_id(
                self.hass,
                self.coordinator,
                str(from_name.state),
            )
            to_stop = _resolve_stop_id(self.hass, self.coordinator, str(to_name.state))
            if from_stop and to_stop:
                rows = self.coordinator.compute_next_buses(
                    from_stop,
                    to_stop,
                    limit=5,
                    only_buses=True,
                )
                for row in rows:
                    route_id_raw = str(row["line"])  # underlying route id like R1, R2
                    line_label = _route_label(route_id_raw)
                    platform = row.get("platform") or "—"
                    planned_hm = _fmt_hm(str(row["planned_dep"]))
                    real_hm = _fmt_hm(str(row["real_dep"]))
                    arrival_hm = _fmt_hm(str(row["arrival"]))

                    # Compute ETA in minutes from now until real departure
                    eta_min: int | None = None
                    try:
                        real_dt = dt_util.parse_datetime(str(row["real_dep"]))
                        if real_dt is not None:
                            now = dt_util.now()
                            # Ensure both are timezone-aware in local tz
                            real_local = dt_util.as_local(real_dt)
                            delta = real_local - now
                            eta_min = max(round(delta.total_seconds() / 60), 0)
                    except Exception:  # noqa: BLE001 - defensive fallback
                        eta_min = None

                    # One-line format as requested
                    formatted_lines.append(
                        f"{real_hm} (was {planned_hm}) → {arrival_hm} | "
                        f"{line_label} | {platform} | {row['duration_min']} min | "
                        f"Delay {row['delay_min']} min",
                    )

                    # Provide HH:MM values in attributes
                    buses.append(
                        {
                            "planned_dep": planned_hm,
                            "real_dep": real_hm,
                            "arrival": arrival_hm,
                            "duration_min": row["duration_min"],
                            "line": line_label,
                            "route_id": route_id_raw,
                            "platform": platform,
                            "delay_min": row["delay_min"],
                            "eta_min": eta_min,
                        },
                    )

        formatted = "\n".join(formatted_lines) if formatted_lines else "No buses"
        return {
            "buses": buses,
            "formatted": formatted,
        }


class FixedPairNextBusesSensor(
    CoordinatorEntity[PublicTransportDataUpdateCoordinator],
    SensorEntity,
):
    """Next 2 live departures from Karlskrona Central -> Lyckeby centrum."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "next_buses"

    FROM_ID = "KRK_CENTRAL"
    TO_ID = "LYCKEBY_C"

    def __init__(
        self,
        coordinator: PublicTransportDataUpdateCoordinator,
        entry: PublicTransportConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.entry_id}_{self.FROM_ID}_{self.TO_ID}_next_buses"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Public transport feed",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_name = "Karlskrona to Lyckeby next buses"

    @property
    def native_value(self) -> str:
        """Return the number of departures."""
        rows = self.coordinator.compute_next_buses(
            self.FROM_ID,
            self.TO_ID,
            limit=2,
            only_buses=True,
        )
        return f"{len(rows)} departures"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        formatted_lines: list[str] = []
        buses: list[dict[str, Any]] = []

        routes_map = _read_static_routes(self.hass)

        def _route_label(route_id: str) -> str:
            r = routes_map.get(route_id)
            if not r:
                return route_id
            short = r.get("route_short_name") or ""
            rtype = r.get("route_type") or ""
            if rtype == "3":
                return f"City Bus {short or route_id}"
            if rtype == "2":
                return f"Train {short or route_id}"
            return short or route_id

        def _fmt_hm(iso_string: str) -> str:
            dt = dt_util.parse_datetime(iso_string)
            if dt is None:
                return iso_string
            return dt_util.as_local(dt).strftime("%H:%M")

        rows = self.coordinator.compute_next_buses(
            self.FROM_ID,
            self.TO_ID,
            limit=2,
            only_buses=True,
        )
        for row in rows:
            line_label = _route_label(str(row["line"]))
            platform = row.get("platform") or "—"
            planned_hm = _fmt_hm(str(row["planned_dep"]))
            real_hm = _fmt_hm(str(row["real_dep"]))
            arrival_hm = _fmt_hm(str(row["arrival"]))

            formatted_lines.append(
                f"{real_hm} (was {planned_hm}) → {arrival_hm} | "
                f"{line_label} | {platform} | {row['duration_min']} min | "
                f"Delay {row['delay_min']} min",
            )
            buses.append(
                {
                    "planned_dep": planned_hm,
                    "real_dep": real_hm,
                    "arrival": arrival_hm,
                    "duration_min": row["duration_min"],
                    "line": line_label,
                    "platform": platform,
                    "delay_min": row["delay_min"],
                },
            )

        formatted = (
            "\n".join(formatted_lines) if formatted_lines else "No upcoming departures"
        )
        return {
            "buses": buses,
            "formatted": formatted,
        }
