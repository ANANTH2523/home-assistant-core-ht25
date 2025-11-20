"""Helper module returning GTFS-RT protobuf classes.

This integration prefers the real `gtfs-realtime-bindings` package. When it
is not available (for example, in offline demos or tests), we fall back to a
lightweight JSON-based stub that implements the subset of the API we need.
"""

from __future__ import annotations

try:
    from google.transit import gtfs_realtime_pb2  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - optional fallback for demo/testing
    from . import _gtfs_rt_stub as gtfs_realtime_pb2  # type: ignore[no-redef]

__all__ = ["gtfs_realtime_pb2"]
