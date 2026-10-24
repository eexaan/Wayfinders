"""
================================================================================
Snap the route lines to the road network
================================================================================
Maldives Datathon 2026 | Team Wayfinders

route_lines.geojson joins stops with straight lines, so the Malé -> Hulhumalé
legs cut across the sea instead of following the Sinamalé Bridge and the
airport-island road. This script routes every stop-to-stop leg over
OpenStreetMap roads with OSRM (the same approach as
github.com/Shinorkon/wayfinder) and writes one feature per leg.

Stdlib only. Needs network access to router.project-osrm.org. The output is
committed, so the dashboard never calls OSRM at runtime.

Output:
    dashboard/data/route_segments.geojson   one LineString per stop-to-stop leg
        properties: route_code, seq, from_stop, to_stop, from_code, to_code,
                    road_m, loop_removed_m, straight_m, snap_from_m, snap_to_m,
                    median_segment_minutes (from bridge_segment_analysis.csv),
                    causeway (bool: scheduled leg >= 10 min)
    dashboard/data/stop_snap_qa.csv         distance from each stop to the
                                            nearest road, for checking placement

Scope: Malé, the airport island and Hulhumalé only. Villimalé routes (R13, R14)
are left out of the map (see BBOX).
"""

from __future__ import annotations

import csv
import json
import math
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "dashboard" / "data"
OSRM = "https://router.project-osrm.org/route/v1/driving/"
# At the bridge interchange on the airport island, OSM's turn rules send the car
# profile from Hulhumalé to the VIA terminal (and back) via a U-turn in Malé or
# Hulhumalé. Buses take the interchange directly, so on detour legs we cut any
# excursion that returns to within LOOP_CLOSE_M of where it left.
DETOUR_RATIO, DETOUR_EXTRA_M = 2.0, 1000
LOOP_CLOSE_M, LOOP_MIN_M = 40, 1000

# Malé + airport island + Hulhumalé. Villimalé (lon ~73.484) is outside.
BBOX = {"south": 4.160, "west": 73.494, "north": 4.248, "east": 73.560}
CAUSEWAY_MIN = 10.0


def inside(lat: float, lon: float) -> bool:
    return BBOX["south"] <= lat <= BBOX["north"] and BBOX["west"] <= lon <= BBOX["east"]


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def path_m(coords: list) -> float:
    return sum(haversine_m((p[1], p[0]), (q[1], q[0])) for p, q in zip(coords, coords[1:]))


def cut_loops(coords: list) -> tuple[list, float]:
    """Remove out-and-back excursions: the first point i that the path later
    revisits (within LOOP_CLOSE_M) after more than LOOP_MIN_M of travel."""
    cum = [0.0]
    for p, q in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_m((p[1], p[0]), (q[1], q[0])))
    for i, p in enumerate(coords):
        for j in range(len(coords) - 1, i, -1):
            if cum[j] - cum[i] > LOOP_MIN_M and haversine_m((p[1], p[0]), (coords[j][1], coords[j][0])) < LOOP_CLOSE_M:
                rest, cut = cut_loops(coords[j:])
                return coords[: i + 1] + rest, cum[j] - cum[i] + cut
    return coords, 0.0


def osrm_leg(a: dict, b: dict) -> dict:
    coords = f"{a['lon']},{a['lat']};{b['lon']},{b['lat']}"
    url = f"{OSRM}{coords}?overview=full&geometries=geojson"
    # curl rather than urllib: python.org builds on macOS ship without CA certs
    for attempt in range(4):
        try:
            out = subprocess.run(["curl", "-sf", "--max-time", "30", "-A", "Wayfinders-datathon/1.0", url],
                                 capture_output=True, check=True).stdout
            body = json.loads(out)
            if body.get("code") == "Ok":
                return body
        except Exception:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"OSRM failed for {a['stop_name']} -> {b['stop_name']}")


def main() -> None:
    stops = list(csv.DictReader(open(DATA / "route_stops.csv", encoding="utf-8")))
    for s in stops:
        s["lat"], s["lon"] = float(s["lat"]), float(s["lon"])
        s["stop_order"] = int(s["stop_order"])

    seg_minutes = {}
    for r in csv.DictReader(open(DATA / "bridge_segment_analysis.csv", encoding="utf-8")):
        seg_minutes[(r["route_code"], r["from_stop"].strip(), r["to_stop"].strip())] = float(r["median_segment_minutes"])

    by_route: dict[str, list[dict]] = {}
    for s in stops:
        by_route.setdefault(s["route_code"], []).append(s)

    feats, qa, cache = [], {}, {}
    for code in sorted(by_route, key=lambda c: int(c[1:])):
        seq = sorted(by_route[code], key=lambda s: s["stop_order"])
        if not all(inside(s["lat"], s["lon"]) for s in seq):
            print(f"{code}: outside Malé/Hulhumalé, skipped")
            continue
        for i, (a, b) in enumerate(zip(seq, seq[1:]), start=1):
            key = (a["lat"], a["lon"], b["lat"], b["lon"])
            if key not in cache:
                cache[key] = osrm_leg(a, b)
                time.sleep(0.25)
            body = cache[key]
            straight = haversine_m((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            route, wps = body["routes"][0], body["waypoints"]
            geom, cut_m = route["geometry"], 0.0
            if route["distance"] > DETOUR_RATIO * straight and route["distance"] - straight > DETOUR_EXTRA_M:
                coords, cut_m = cut_loops(geom["coordinates"])
                geom = {"type": "LineString", "coordinates": coords}
                print(f"  {code} {a['stop_name'].strip()} -> {b['stop_name'].strip()}: "
                      f"{route['distance']:.0f} m -> {path_m(coords):.0f} m (U-turn loop removed)")
            mins = seg_minutes.get((code, a["stop_name"].strip(), b["stop_name"].strip()))
            feats.append({
                "type": "Feature",
                "properties": {
                    "route_code": code,
                    "seq": i,
                    "from_stop": a["stop_name"].strip(),
                    "to_stop": b["stop_name"].strip(),
                    "from_code": a["stop_code"],
                    "to_code": b["stop_code"],
                    "road_m": round(path_m(geom["coordinates"])),
                    "loop_removed_m": round(cut_m),
                    "straight_m": round(straight),
                    "snap_from_m": round(wps[0]["distance"], 1),
                    "snap_to_m": round(wps[1]["distance"], 1),
                    "median_segment_minutes": mins,
                    "causeway": bool(mins is not None and mins >= CAUSEWAY_MIN),
                },
                "geometry": geom,
            })
            for s, wp in ((a, wps[0]), (b, wps[1])):
                qa[s["stop_code"]] = (s["stop_name"].strip(), s["lat"], s["lon"], round(wp["distance"], 1),
                                      wp["location"][1], wp["location"][0])
        print(f"{code}: {len(seq) - 1} legs")

    (DATA / "route_segments.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
    )
    with open(DATA / "stop_snap_qa.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stop_code", "stop_name", "lat", "lon", "snap_distance_m", "road_lat", "road_lon"])
        for code, row in sorted(qa.items(), key=lambda kv: -kv[1][3]):
            w.writerow([code, *row])
    print(f"wrote {len(feats)} legs, {len(qa)} stops checked")


if __name__ == "__main__":
    main()
