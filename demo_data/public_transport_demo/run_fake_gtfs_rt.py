"""Run a synthetic GTFS-RT server for the Blekinge demo."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

try:
    from aiohttp import web
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    web = None

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from google.transit import gtfs_realtime_pb2  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - optional fallback for demo/testing
    try:
        from custom_components.public_transport.gtfs import gtfs_realtime_pb2
    except (ModuleNotFoundError, SyntaxError):  # pragma: no cover - optional fallback
        import importlib.util

        stub_path = ROOT / "custom_components" / "public_transport" / "_gtfs_rt_stub.py"
        spec = importlib.util.spec_from_file_location(
            "public_transport_gtfs_stub",
            stub_path,
        )
        if spec is None or spec.loader is None:
            msg = f"Unable to load GTFS-RT stub from {stub_path}"
            raise RuntimeError(msg) from None  # pragma: no cover
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        gtfs_realtime_pb2 = module  # type: ignore[assignment]

PORT = 8081

ROUTE_UPDATES = [
    (
        "bus-r1",
        "R1_OUT",
        "R1",
        [
            ("KRK_CENTRAL", 3, 60),
            ("ALAMEDAN", 7, 60),
            ("SALTO", 12, 90),
        ],
    ),
    (
        "bus-r2",
        "R2_OUT",
        "R2",
        [
            ("KRK_CENTRAL", 4, 90),
            ("LYCKEBY_C", 12, 120),
            ("JAMJO", 24, 180),
        ],
    ),
    (
        "bus-r3",
        "R3_OUT",
        "R3",
        [
            ("KRK_CENTRAL", 5, 0),
            ("NORRA_HASSLEASG", 11, 60),
            ("BASTASJO", 17, 120),
        ],
    ),
    (
        "bus-r4",
        "R4_OUT",
        "R4",
        [
            ("KRK_CENTRAL", 6, 30),
            ("RODEBY_C", 16, 90),
            ("RODEBYHOLM", 20, 150),
        ],
    ),
    (
        "bus-r5",
        "R5_OUT",
        "R5",
        [
            ("KRK_CENTRAL", 4, 0),
            ("NATTRABY_C", 13, 60),
            ("SKARVIK", 18, 120),
        ],
    ),
    (
        "bus-r6",
        "R6_OUT",
        "R6",
        [
            ("KRK_CENTRAL", 3, 30),
            ("HOGALID", 7, 60),
            ("VERKO_TERMINAL", 13, 90),
        ],
    ),
    (
        "bus-r7",
        "R7_OUT",
        "R7",
        [
            ("KRK_CENTRAL", 2, 0),
            ("LANGO", 6, 30),
            ("STRANDGATAN", 9, 60),
        ],
    ),
    (
        "bus-r8",
        "R8_OUT",
        "R8",
        [
            ("KRK_CENTRAL", 3, 0),
            ("HASTO", 9, 45),
        ],
    ),
    (
        "train-t1",
        "T1_OUT",
        "T1",
        [
            ("KRK_CENTRAL", 10, 0),
            ("RONNEBY_STN", 35, 120),
            ("KARLSHAMN_STN", 65, 300),
        ],
    ),
]


def build_feed(now: datetime) -> bytes:
    """Generate TripUpdates for all demo routes."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"

    for entity_id, trip_id, route_id, stops in ROUTE_UPDATES:
        entity = feed.entity.add()
        entity.id = entity_id
        trip_update = entity.trip_update
        trip_update.trip.trip_id = trip_id
        trip_update.trip.route_id = route_id

        for sequence, (stop_id, minutes, delay) in enumerate(stops, start=1):
            update = trip_update.stop_time_update.add()
            update.stop_sequence = sequence
            update.stop_id = stop_id
            update.arrival.time = int((now + timedelta(minutes=minutes)).timestamp())
            if delay:
                update.arrival.delay = delay

    return feed.SerializeToString()


async def handle_trip_updates(request: web.Request) -> web.Response:  # noqa: ARG001
    """Handle GTFS-RT trip updates request."""
    now = datetime.now(UTC)
    body = build_feed(now)
    return web.Response(body=body, content_type="application/x-protobuf")


async def init_app() -> web.Application:
    """Initialize the aiohttp application."""
    app = web.Application()
    app.add_routes([web.get("/gtfs-rt/TripUpdates.pb", handle_trip_updates)])
    return app


def main() -> None:
    """Run the fake GTFS-RT server for demo/testing purposes."""
    if web is None:
        import contextlib  # noqa: PLC0415
        from http.server import (  # noqa: PLC0415
            BaseHTTPRequestHandler,
            ThreadingHTTPServer,
        )

        class TripUpdateHandler(BaseHTTPRequestHandler):
            """Minimal HTTP server fallback when aiohttp is unavailable."""

            def do_GET(self) -> None:  # type: ignore[override]
                if self.path != "/gtfs-rt/TripUpdates.pb":
                    self.send_response(404)
                    self.end_headers()
                    return

                now = datetime.now(UTC)
                body = build_feed(now)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(
                self,
                format: str,  # noqa: ARG002, A002
                *args: object,  # noqa: ARG002
            ) -> None:
                return

        server = ThreadingHTTPServer(
            ("0.0.0.0", PORT),  # noqa: S104
            TripUpdateHandler,
        )
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
        server.server_close()
        return

    app = asyncio.run(init_app())
    web.run_app(app, host="0.0.0.0", port=PORT)  # noqa: S104 - demo server


if __name__ == "__main__":
    main()
