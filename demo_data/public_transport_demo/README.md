# Public Transport Demo Dataset

This folder provides a fully synthetic GTFS static dataset and a tiny GTFS-Realtime Trip Updates server so you can try the `public_transport` custom integration without needing access to a real feed.

## Contents

```
demo_data/public_transport_demo/
├── static/                     # Plain-text GTFS files
├── package_static.py           # Creates demo_gtfs_static.zip
└── run_fake_gtfs_rt.py         # Serves a GTFS-RT TripUpdates feed
```

### Static GTFS

Run the packaging script to create a ZIP:

```bash
cd demo_data/public_transport_demo
python package_static.py
# Result: demo_gtfs_static.zip in the same folder
```

The ZIP now contains Karlskrona city lines 1–8 plus the Karlskrona→Karlshamn train. Each route has weekday trips and approximate stop coordinates so you can draw routes on a map.

### GTFS-Realtime Server

Launch the synthetic GTFS-RT server (requires `aiohttp` and `gtfs-realtime-bindings`, both already listed in the integration’s requirements):

```bash
cd demo_data/public_transport_demo
python run_fake_gtfs_rt.py
```

This starts an HTTP server on port `8081` that serves TripUpdates at:

```
http://localhost:8081/gtfs-rt/TripUpdates.pb
```

It publishes TripUpdates for every synthetic line, each with predictable arrival offsets and delays. All buses call at `KRK_CENTRAL`; the train also serves `RONNEBY_STN` and `KARLSHAMN_STN`.

## Using with Home Assistant

1. Place the `public_transport` custom component in your Home Assistant config.
2. Run the demo GTFS-RT server as shown above.
3. In Home Assistant, add the integration with:
   - Feed URL: `http://host.docker.internal:8081/gtfs-rt/TripUpdates.pb` (adjust host if HA runs elsewhere)
   - Stop IDs: include `KRK_CENTRAL` plus any other demo stops you want dashboards for (e.g. `BRUNNSPARK`, `VERKO_TERMINAL`, `KARLSHAMN_STN`)
   - Route IDs (optional): leave blank to see every line
   - Max departures: `5`
   - Scan interval: `30`
4. For Lovelace map overlays, unzip `demo_gtfs_static.zip` and use `stops.txt` to plot markers at the provided coordinates.

This dataset is purely synthetic—use it only for testing or demonstrations. Replace the feed URL and stop IDs with your operator’s real GTFS data when available.
