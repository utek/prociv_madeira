# /// script
# requires-python = ">=3.14"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the integration's brand icons from the MDI weather-cloudy-alert glyph.

Run with: uv run scripts/render_brand.py
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from pathlib import Path

import resvg_py

SOURCE = "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/weather-cloudy-alert.svg"
# So that a changed download can't silently change the icons.
SOURCE_SHA256 = "088ae41caeb9b4922b9a9655fbe331ecf6a1e7a6d844f8b0c0b921251788deeb"
COLOR = "#1E88E5"
# The glyph only uses x 1-23 of its 24x24 canvas; crop to a trimmed square.
VIEW_BOX = "1 1 22 22"
BRAND_DIR = (
    Path(__file__).parent.parent / "custom_components" / "prociv_madeira" / "brand"
)
SIZES = {"icon.png": 256, "icon@2x.png": 512}


def main() -> None:
    """Download the glyph and write the PNG icons."""
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        glyph = response.read()
    if hashlib.sha256(glyph).hexdigest() != SOURCE_SHA256:
        raise SystemExit(f"{SOURCE} does not have the expected SHA-256")
    paths = re.findall(r'<path d="([^"]+)"', glyph.decode())
    if len(paths) != 1:
        raise SystemExit(f"Expected one path in {SOURCE}, found {len(paths)}")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEW_BOX}">'
        f'<path fill="{COLOR}" d="{paths[0]}"/></svg>'
    )

    BRAND_DIR.mkdir(exist_ok=True)
    for name, size in SIZES.items():
        png = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)
        (BRAND_DIR / name).write_bytes(bytes(png))
        print(f"Wrote {BRAND_DIR / name} ({size}x{size})")


if __name__ == "__main__":
    main()
