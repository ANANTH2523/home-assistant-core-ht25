"""Data models for the Public Transport integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class GtfsConfig:
    """Configuration for the GTFS-RT feed."""

    feed_url: str
    stop_ids: list[str]
    max_departures: int
    scan_interval: timedelta
    api_key_header_name: str | None = None
    api_key_value: str | None = None
    route_ids: set[str] | None = None
    demo_random: bool = False


@dataclass(slots=True)
class Departure:
    """Representation of an upcoming departure."""

    stop_id: str
    route_id: str
    headsign: str | None
    scheduled_time: datetime
    arrival_time: datetime
    delay_seconds: int
    vehicle_id: str | None

    @property
    def eta(self) -> timedelta:
        """Return the ETA as a timedelta."""
        now = dt_util.utcnow()
        return max(self.arrival_time - now, timedelta())

    @property
    def delay_minutes(self) -> int:
        """Return the delay rounded to minutes."""
        return round(self.delay_seconds / 60)

    @property
    def eta_minutes(self) -> int:
        """Return the ETA rounded to minutes."""
        return round(self.eta.total_seconds() / 60)


def summarize_departures(
    departures: Iterable[Departure],
    max_items: int,
) -> tuple[str, list[dict[str, Any]]]:
    """Summarize a list of departures for use in sensor attributes."""
    structured: list[dict[str, Any]] = []
    summary_segments: list[str] = []

    for departure in list(departures)[:max_items]:
        structured.append(
            {
                "route_id": departure.route_id,
                "headsign": departure.headsign,
                "eta_minutes": departure.eta_minutes,
                "delay_minutes": departure.delay_minutes,
                "travel_time_minutes": departure.eta_minutes,
                "arrival_time": dt_util.as_local(departure.arrival_time).isoformat(),
            },
        )
        summary_segments.append(
            (
                f"{departure.route_id} {departure.headsign or ''} in "
                f"{departure.eta_minutes} min (delay {departure.delay_minutes} min)"
            ).strip(),
        )

    summary = (
        "; ".join(summary_segments) if summary_segments else "No upcoming departures"
    )
    return summary, structured


@dataclass(slots=True)
class StopTimeInfo:
    """Timing info for a stop within a trip."""

    stop_id: str
    sequence: int | None
    arrival_time: datetime
    scheduled_time: datetime
    delay_seconds: int
    platform: str | None = None


@dataclass(slots=True)
class TripData:
    """Representation of a single trip with timings for multiple stops."""

    trip_id: str
    route_id: str
    headsign: str | None
    stops: dict[str, StopTimeInfo]
