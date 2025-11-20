"""Minimal GTFS-RT protobuf stub used when real bindings are unavailable."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any


@dataclass
class _StopTimeEvent:
    time: int = 0
    delay: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"time": self.time, "delay": self.delay}

    def from_dict(self, data: dict[str, Any]) -> None:
        self.time = int(data.get("time", 0))
        self.delay = int(data.get("delay", 0))


@dataclass
class _StopTimeUpdate:
    stop_id: str = ""
    stop_sequence: int = 0
    stop_headsign: str = ""
    arrival: _StopTimeEvent = field(default_factory=_StopTimeEvent)
    departure: _StopTimeEvent = field(default_factory=_StopTimeEvent)

    def HasField(self, field: str) -> bool:  # noqa: N802
        if field == "arrival":
            return bool(self.arrival.time or self.arrival.delay)
        if field == "departure":
            return bool(self.departure.time or self.departure.delay)
        if field == "stop_headsign":
            return self.stop_headsign != ""
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_id": self.stop_id,
            "stop_sequence": self.stop_sequence,
            "stop_headsign": self.stop_headsign,
            "arrival": self.arrival.to_dict(),
            "departure": self.departure.to_dict(),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self.stop_id = data.get("stop_id", "")
        self.stop_sequence = int(data.get("stop_sequence", 0))
        self.stop_headsign = data.get("stop_headsign", "")
        self.arrival.from_dict(data.get("arrival", {}))
        self.departure.from_dict(data.get("departure", {}))


class _StopTimeUpdateList(list[_StopTimeUpdate]):
    def add(self) -> _StopTimeUpdate:
        update = _StopTimeUpdate()
        self.append(update)
        return update


@dataclass
class _TripDescriptor:
    trip_id: str = ""
    route_id: str = ""
    trip_headsign: str = ""


@dataclass
class _VehicleDescriptor:
    id: str = ""


@dataclass
class _TripUpdate:
    trip: _TripDescriptor = field(default_factory=_TripDescriptor)
    stop_time_update: _StopTimeUpdateList = field(default_factory=_StopTimeUpdateList)
    vehicle: _VehicleDescriptor = field(default_factory=_VehicleDescriptor)

    def HasField(self, field: str) -> bool:  # noqa: N802
        if field == "vehicle":
            return self.vehicle.id != ""
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "trip": {
                "trip_id": self.trip.trip_id,
                "route_id": self.trip.route_id,
                "trip_headsign": self.trip.trip_headsign,
            },
            "vehicle": {"id": self.vehicle.id},
            "stop_time_update": [stu.to_dict() for stu in self.stop_time_update],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        trip_data = data.get("trip", {})
        self.trip.trip_id = trip_data.get("trip_id", "")
        self.trip.route_id = trip_data.get("route_id", "")
        self.trip.trip_headsign = trip_data.get("trip_headsign", "")
        vehicle_data = data.get("vehicle", {})
        self.vehicle.id = vehicle_data.get("id", "")
        self.stop_time_update = _StopTimeUpdateList()
        for update_data in data.get("stop_time_update", []):
            update = self.stop_time_update.add()
            update.from_dict(update_data)


@dataclass
class _FeedEntity:
    id: str = ""
    trip_update: _TripUpdate = field(default_factory=_TripUpdate)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "trip_update": self.trip_update.to_dict()}

    def from_dict(self, data: dict[str, Any]) -> None:
        self.id = data.get("id", "")
        self.trip_update.from_dict(data.get("trip_update", {}))


class _EntityList(list[_FeedEntity]):
    def add(self) -> _FeedEntity:
        entity = _FeedEntity()
        self.append(entity)
        return entity


@dataclass
class _Header:
    gtfs_realtime_version: str = ""


class FeedMessage:
    """Simplified replacement for the GTFS-RT FeedMessage."""

    def __init__(self) -> None:
        self.header = _Header()
        self.entity = _EntityList()

    def SerializeToString(self) -> bytes:  # noqa: N802
        payload = {
            "header": {"gtfs_realtime_version": self.header.gtfs_realtime_version},
            "entity": [entity.to_dict() for entity in self.entity],
        }
        return json.dumps(payload).encode()

    def ParseFromString(self, payload: bytes) -> None:  # noqa: N802
        if not payload:
            self.header = _Header()
            self.entity = _EntityList()
            return

        data = json.loads(payload.decode())
        self.header = _Header()
        self.header.gtfs_realtime_version = data.get("header", {}).get(
            "gtfs_realtime_version", "",
        )
        self.entity = _EntityList()
        for entity_data in data.get("entity", []):
            entity = self.entity.add()
            entity.from_dict(entity_data)
