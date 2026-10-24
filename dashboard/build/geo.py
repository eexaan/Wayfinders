"""
================================================================================
Shared geometry helpers for the reroute build
================================================================================
Maldives Datathon 2026 | Team Wayfinders

Small, dependency-free helpers used by `build_population.py`,
`road_graph.py` and `build_reroute_network.py`. Stdlib only, so a reroute
rebuild never depends on a geospatial stack.

Nothing here reads a file or writes a result: these are pure functions on
coordinates, and they are unit-tested in `tests/test_reroute.py`.
"""

from __future__ import annotations

import math

EARTH_M = 6_371_000.0

# One degree of latitude, and of longitude at the latitude of Malé. Malé sits at
# 4.17 N, where a degree of longitude is ~0.997 of a degree of latitude; using
# the local value keeps a 150 m cell square instead of 150 x 150.4 m.
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(4.17))

# Lattice origin for the population grid. South-west of every in-scope island,
# so no cell index is negative.
GRID_LAT0 = 4.160
GRID_LON0 = 73.496


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(h))


def cell_index(lat: float, lon: float, size_m: float) -> tuple[int, int]:
    """Grid cell containing a point, at `size_m` metres square."""
    return (
        int(math.floor((lat - GRID_LAT0) * M_PER_DEG_LAT / size_m)),
        int(math.floor((lon - GRID_LON0) * M_PER_DEG_LON / size_m)),
    )


def cell_centre(row: int, col: int, size_m: float) -> tuple[float, float]:
    """Lat/lon at the centre of a grid cell."""
    lat = GRID_LAT0 + (row + 0.5) * size_m / M_PER_DEG_LAT
    lon = GRID_LON0 + (col + 0.5) * size_m / M_PER_DEG_LON
    return lat, lon


def cell_id(row: int, col: int) -> str:
    return f"g{row:03d}_{col:03d}"


def ring_area_m2(ring: list[tuple[float, float]]) -> float:
    """Planar area of a lat/lon ring, in square metres, at Malé's latitude."""
    if len(ring) < 3:
        return 0.0
    xs = [lon * M_PER_DEG_LON for _lat, lon in ring]
    ys = [lat * M_PER_DEG_LAT for lat, _lon in ring]
    s = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        s += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(s) / 2.0


def point_in_ring(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting containment test. `ring` is [(lat, lon), ...]."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lon: float, rings: list[list[tuple[float, float]]]) -> bool:
    """First ring is the outer boundary; a point in any later ring is excluded."""
    if not rings or not point_in_ring(lat, lon, rings[0]):
        return False
    return not any(point_in_ring(lat, lon, hole) for hole in rings[1:])
