"""
================================================================================
Where people are going: points of interest as trip generators
================================================================================
Maldives Datathon 2026 | Team Wayfinders

A bus schedule is a guess about where people need to be and when. The demand
tables say how many boarded; they do not say *where those people were going*.
This script supplies the missing half: the schools, offices, hospitals, mosques
and markets that generate the trips, so a route can be judged on whether it
connects anything.

Source: OpenStreetMap via the Overpass API (ODbL, same source and method as
dashboard/build/build_basemap.py). Nothing here is hand-entered and nothing is
guessed - a POI either exists in OSM with coordinates or it is not in the file.

Output (Wayfinders/data/derived/):
    greater_male_pois.csv     one row per POI, with the category that sets its
                              time-of-day demand profile
    poi_access_gaps.csv       per category: how many POIs are beyond a walk of
                              the nearest bus stop

Categories are chosen so each maps to a distinct demand curve, which is what a
reallocation model needs:

    education  ~07:00 and ~14:00              two sharp school peaks
    work       ~07:30-08:30 and ~17:00-18:30  commute peaks, Sun-Thu only
    health     ~08:00-16:00, spread           all-day, low amplitude
    worship    ~11:45-13:30 Friday            Jumu'ah suppression, not a peak
    retail     ~16:00-21:00                   evening, later than work
    civic      ~08:00-15:00                   business hours
    transport  all day, flight-linked         the airport is its own curve

The Friday/Saturday weekend and the Jumu'ah window are Maldives facts, not
assumptions (see SCOPE.md); they apply to every category above.

Run:
    .venv/bin/python scripts/build_pois.py [saved_overpass_response.json]
"""

from __future__ import annotations

import collections
import csv
import json
import math
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
BASEMAP = ROOT / "dashboard" / "data" / "basemap.geojson"
STOPS = ROOT / "dashboard" / "data" / "route_stops.csv"

OUT_POIS = DERIVED / "greater_male_pois.csv"
OUT_GAPS = DERIVED / "poi_access_gaps.csv"

OVERPASS = "https://overpass-api.de/api/interpreter"

# The same pan limit the dashboard uses (web/src/mapArea.js), so a POI is
# either visible on the map or not in the file.
BBOX = "4.140,73.440,4.272,73.600"

# amenity/office/shop -> category. Anything not listed falls through to
# "other" and is kept, but is not used to build a demand curve.
CLASSIFY = {
    # education: two sharp peaks, starting earlier than work
    "school": "education",
    "college": "education",
    "university": "education",
    "kindergarten": "education",
    # work: the classic commute, Sunday-Thursday
    "government": "work",
    "administrative": "work",
    "company": "work",
    "ngo": "work",
    "association": "work",
    "financial": "work",
    "insurance": "work",
    "lawyer": "work",
    "notary": "work",
    "diplomatic": "work",
    "it": "work",
    "educational_institution": "work",
    # health: all day, low amplitude
    "hospital": "health",
    "clinic": "health",
    "doctors": "health",
    "dentist": "health",
    "pharmacy": "health",
    # worship: Jumu'ah suppresses travel 11:45-13:30, it is not a peak
    "place_of_worship": "worship",
    # retail: evening-weighted, the latest of any category
    "marketplace": "retail",
    "supermarket": "retail",
    "mall": "retail",
    "department_store": "retail",
    "convenience": "retail",
    "bank": "retail",
    # civic: business hours, administrative trips
    "police": "civic",
    "courthouse": "civic",
    "townhall": "civic",
    "post_office": "civic",
    "library": "civic",
    "community_centre": "civic",
    # transport: its own curve, flight-linked
    "bus_station": "transport",
}

# Walking distance beyond which a stop is not a realistic walk to a destination.
# 400 m is the usual planning rule of thumb for a local bus stop.
WALK_M = 400

QUERY = f"""[out:json][timeout:120];
(
  nwr["amenity"~"^(school|college|university|kindergarten|hospital|clinic|doctors|dentist|pharmacy|bank|marketplace|police|courthouse|townhall|post_office|library|community_centre|bus_station|place_of_worship)$"]({BBOX});
  nwr["office"]({BBOX});
  nwr["shop"~"^(supermarket|mall|department_store|convenience)$"]({BBOX});
);
out center tags;"""


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def fetch() -> dict:
    if len(sys.argv) > 1:  # reuse a saved Overpass response
        return json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = subprocess.run(
        ["curl", "-sSf", "--max-time", "180", "-A", "Wayfinders-datathon/1.0", "-G", OVERPASS,
         "--data-urlencode", f"data={QUERY}"],
        capture_output=True, check=True,
    ).stdout
    return json.loads(out)


def classify(tags: dict) -> tuple[str, str]:
    """(category, the tag that decided it)."""
    for key in ("amenity", "office", "shop"):
        value = tags.get(key)
        if value and value in CLASSIFY:
            return CLASSIFY[value], f"{key}={value}"
    if tags.get("office"):
        return "other", f"office={tags['office']}"
    return "other", f"{tags.get('amenity') or tags.get('shop') or '?'}"


def point_in_ring(lat: float, lon: float, ring: list) -> bool:
    inside = False
    closed = ring + ring[:1]
    for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def load_islands() -> list[tuple[str, list]]:
    """(name, outer ring) from the committed OSM basemap - not guessed geography."""
    data = json.loads(BASEMAP.read_text())
    out = []
    for f in data["features"]:
        if f["properties"].get("kind") != "land":
            continue
        if f["geometry"]["type"] != "Polygon":
            continue
        ring = f["geometry"]["coordinates"][0]
        if len(ring) >= 4:
            out.append((f["properties"].get("name") or "unnamed", ring))
    return out


def island_of(lat: float, lon: float, islands: list[tuple[str, list]]) -> str:
    for name, ring in islands:
        if point_in_ring(lat, lon, ring):
            return name
    return "outside"


def load_stops() -> list[dict]:
    """Unique stops with their routes, from the dashboard contract."""
    by_code: dict[str, dict] = {}
    for r in csv.DictReader(open(STOPS, encoding="utf-8")):
        st = by_code.setdefault(r["stop_code"], {
            "code": r["stop_code"],
            "name": r["stop_name"].strip(),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "routes": [],
        })
        if r["route_code"] not in st["routes"]:
            st["routes"].append(r["route_code"])
    return list(by_code.values())


def main() -> None:
    if not STOPS.exists():
        raise SystemExit(f"{STOPS} is missing - rebuild the dashboard data first")

    data = fetch()
    islands = load_islands()
    stops = load_stops()

    rows, skipped = [], 0
    for e in data["elements"]:
        tags = e.get("tags", {})
        if "lat" in e:
            lat, lon = e["lat"], e["lon"]
        elif "center" in e:
            lat, lon = e["center"]["lat"], e["center"]["lon"]
        else:
            skipped += 1
            continue

        name = tags.get("name:en") or tags.get("name") or ""
        if not name:
            skipped += 1
            continue

        category, decided_by = classify(tags)
        nearest = min(stops, key=lambda s: haversine_m((lat, lon), (s["lat"], s["lon"])))
        walk = haversine_m((lat, lon), (nearest["lat"], nearest["lon"]))
        rows.append({
            "name": name,
            "category": category,
            "osm_tag": decided_by,
            "island": island_of(lat, lon, islands),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "nearest_stop": nearest["name"],
            "nearest_stop_code": nearest["code"],
            "nearest_routes": " ".join(nearest["routes"]),
            "walk_m": round(walk),
            "served_400m": "yes" if walk <= WALK_M else "no",
            "name_dv": tags.get("name:dv", ""),
            "opening_hours": tags.get("opening_hours", ""),
        })

    # deterministic order, so a rebuild produces no diff when nothing changed
    rows.sort(key=lambda r: (r["category"], r["name"], r["lat"], r["lon"]))

    DERIVED.mkdir(parents=True, exist_ok=True)
    with open(OUT_POIS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    by_cat: dict[str, collections.Counter] = {}
    by_island: dict[tuple[str, str], collections.Counter] = {}
    for r in rows:
        by_cat.setdefault(r["category"], collections.Counter())["total"] += 1
        by_cat[r["category"]]["within_400m"] += r["served_400m"] == "yes"
        key = (r["island"], r["category"])
        by_island.setdefault(key, collections.Counter())["total"] += 1
        by_island[key]["within_400m"] += r["served_400m"] == "yes"

    with open(OUT_GAPS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "island", "category", "pois", "within_400m", "beyond_400m", "unserved_pct", "walk_m_cutoff"])
        for cat in sorted(by_cat, key=lambda c: -by_cat[c]["total"]):
            c = by_cat[cat]
            out = c["total"] - c["within_400m"]
            w.writerow(["network", "", cat, c["total"], c["within_400m"], out, round(100 * out / c["total"], 1), WALK_M])
        for island, cat in sorted(by_island):
            c = by_island[(island, cat)]
            out = c["total"] - c["within_400m"]
            w.writerow([island, island, cat, c["total"], c["within_400m"], out, round(100 * out / c["total"], 1), WALK_M])

    landed = sum(1 for r in rows if r["island"] != "outside")
    print(f"wrote {OUT_POIS.name}: {len(rows)} POIs ({landed} on a mapped island), {skipped} skipped (no name or no point)")
    for cat in sorted(by_cat, key=lambda c: -by_cat[c]["total"]):
        c = by_cat[cat]
        out = c["total"] - c["within_400m"]
        print(f"  {cat:10s} {c['total']:3d} POIs, {out:3d} beyond {WALK_M} m of a stop ({100 * out / c['total']:.0f}%)")
    print(f"wrote {OUT_GAPS.name}")


if __name__ == "__main__":
    main()
