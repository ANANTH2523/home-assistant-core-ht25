"""Create a synthetic GTFS static ZIP for the demo feed."""

from __future__ import annotations

from pathlib import Path
import zipfile


def main() -> None:
    """Package the static GTFS demo files into demo_gtfs_static.zip."""
    base_dir = Path(__file__).parent / "static"
    output = Path(__file__).parent / "demo_gtfs_static.zip"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(base_dir.iterdir()):
            if path.is_file() and path.suffix == ".txt":
                zf.write(path, arcname=path.name)



if __name__ == "__main__":
    main()
