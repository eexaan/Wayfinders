"""
================================================================================
Build the offline basemap from OpenStreetMap data
================================================================================
Maldives Datathon 2026 | Team Wayfinders

The dashboard draws its own basemap - island outlines and roads - instead of
loading map tiles. Commercial tile hosts need API keys, and OSM's own tile
servers forbid bulk downloads, but OSM *data* is open (ODbL) and this area is
tiny. One Overpass query, run once; the output is committed.

Output:
    dashboard/data/basemap.geojson
        land  : Polygon per island/islet (Malé, Hulhulé, Hulhumalé, ...)
        road  : LineString per road, with class "major" or "minor"

Attribution required wherever it is shown: © OpenStreetMap contributors.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "dashboard" / "data" / "basemap.geojson"
OVERPASS = "https://overpass-api.de/api/interpreter"

# a little wider than the map's pan limit (web/src/mapArea.js) so edges are not
# cut; must include Villimalé (lon ~73.483) or R13/R14 fall off the fallback map
BBOX = "4.145,73.465,4.258,73.572"
MAJOR = {"motorway", "trunk", "primary", "secondary"}
QUERY = f"""[out:json][timeout:90];
(
  way["place"~"island|islet"]({BBOX});
  relation["place"~"island|islet"]({BBOX});
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|pedestrian)$"]({BBOX});
);
out geom;"""


def fetch() -> dict:
    if len(sys.argv) > 1:  # reuse a saved Overpass response
        return json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = subprocess.run(
        ["curl", "-sSf", "--max-time", "150", "-A", "Wayfinders-datathon/1.0", "-G", OVERPASS,
         "--data-urlencode", f"data={QUERY}"],
        capture_output=True, check=True,
    ).stdout
    return json.loads(out)


def pts(geom: list) -> list:
    return [[round(p["lon"], 6), round(p["lat"], 6)] for p in geom]


def rings(ways: list[list]) -> list[list]:
    """Join a multipolygon's outer ways end to end into closed rings."""
    ways = [w[:] for w in ways if len(w) > 1]
    out = []
    while ways:
        ring = ways.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, w in enumerate(ways):
                if w[0] == ring[-1]:
                    ring += w[1:]
                elif w[-1] == ring[-1]:
                    ring += w[::-1][1:]
                elif w[-1] == ring[0]:
                    ring = w + ring[1:]
                elif w[0] == ring[0]:
                    ring = w[::-1] + ring[1:]
                else:
                    continue
                ways.pop(i)
                changed = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            out.append(ring)
    return out


def main() -> None:
    data = fetch()
    feats = []
    for e in data["elements"]:
        tags = e.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if "place" in tags:
            if e["type"] == "way":
                polys = rings([pts(e["geometry"])])
            else:
                polys = rings([pts(m["geometry"]) for m in e.get("members", [])
                               if m.get("role") == "outer" and m.get("geometry")])
            for ring in polys:
                feats.append({"type": "Feature", "properties": {"kind": "land", "name": name},
                              "geometry": {"type": "Polygon", "coordinates": [ring]}})
        elif tags.get("highway") not in (None, "service") and e["type"] == "way":
            feats.append({"type": "Feature",
                          "properties": {"kind": "road", "class": "major" if tags["highway"] in MAJOR else "minor"},
                          "geometry": {"type": "LineString", "coordinates": pts(e["geometry"])}})
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False,
                              separators=(",", ":")))
    land = sum(f["properties"]["kind"] == "land" for f in feats)
    print(f"wrote {OUT.name}: {land} land polygons, {len(feats) - land} roads, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
