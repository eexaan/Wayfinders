"""
================================================================================
Where people live and where they are going
================================================================================
Maldives Datathon 2026 | Team Wayfinders

WHY THIS EXISTS
    The reroute asks a different question from the submitted model. The
    submitted model asked "is today's supply matched to today's demand on
    today's stops?" This one asks "if we were laying out the network from
    scratch, where would the stops go?" That needs a *population surface* and
    an *attractor surface*, neither of which exists in the repo.

    This script builds both, on one 150 m grid, from three independent
    sources that are allowed to disagree.

METHOD (every weight is a column in the output, so it can be audited)
    Residential   OSM building footprint area x storeys, 1.3x inside a
                  residential landuse polygon, down-weighted for industrial,
                  storage, roof and construction footprints that house nobody.
                  Calibrated so the in-scope islands sum to the Census 2022
                  projection for Male' City (227,613).
    Revealed      Avas pickups between 22:00 and 06:00 per cell: the people who
                  were physically present in a place at night, by taxi origin.
                  A residential cross-check that does not come from OSM.
    Attractors    OSM hospitals, clinics, schools, colleges, universities,
                  markets, government, courts, police, ferry/bus terminals,
                  hotels and offices, each with a stated weight.

    combined_score = 0.5 x population share + 0.5 x night-taxi share.
    The 150 m grid, the weights and the blend are all in `reroute_params.json`,
    so the surface can be regenerated with different assumptions instead of
    being argued with.

HONEST LIMITS (also written to reroute_params.json)
    * Only 232 of 3,771 OSM buildings in the bbox carry `building:levels`.
      The rest get a storey count from their type (apartments 8, residential 4,
      house 2, yes 4). That is a proxy for floor area, not a measurement.
    * The census table names Male' City as one administrative unit; it does not
      publish a Male'/Hulhumale split. The total is therefore distributed by
      building volume and night taxi presence, not by a published island count.
    * Villimale' is out of scope (ADR-0015) and is not fetched or scored.

INPUT
    An Overpass response for buildings + POIs + landuse, either passed as
    argv[1] or fetched once and cached. The reduced cache is committed at
    data/derived/osm/greater_male_surface.json, so the app and every later
    build step are offline. Nothing here reads the network twice.

OUTPUT (dashboard/data/)
    pop_grid.csv                one row per 150 m cell
    reroute_hotspots.geojson    one point per hospital / office / school / ...
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from geo import (  # noqa: E402
    cell_centre,
    cell_id,
    cell_index,
    point_in_polygon,
    ring_area_m2,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "dashboard" / "data"
CACHE = ROOT / "data" / "derived" / "osm" / "greater_male_surface.json"

# Malé + Hulhulé (the airport island) + Hulhumalé. Villimalé (lon ~73.483) is
# deliberately outside this box: it is out of scope, so it is never fetched.
BBOX = "4.165,73.500,4.245,73.560"
OVERPASS = "https://overpass-api.de/api/interpreter"

QUERY = f"""[out:json][timeout:240];
(
  way["building"]({BBOX});
  node["amenity"~"^(hospital|clinic|doctors|dentist|school|college|university|marketplace|courthouse|townhall|police|fire_station)$"]({BBOX});
  way["amenity"~"^(hospital|clinic|doctors|dentist|school|college|university|marketplace|courthouse|townhall|police|fire_station)$"]({BBOX});
  node["office"]({BBOX});
  way["office"]({BBOX});
  node["tourism"~"^(hotel|guest_house)$"]({BBOX});
  way["tourism"~"^(hotel|guest_house)$"]({BBOX});
  way["landuse"~"^(residential|commercial|retail|industrial|construction)$"]({BBOX});
  relation["landuse"~"^(residential|commercial|retail|industrial|construction)$"]({BBOX});
);
out geom;"""

CELL_M = 150.0

# Census 2022 mid-year projection for Male' City, 2022 column of table 3.16.
# It is used only to scale the 2022 census counts forward. The split between
# islands is *published*, not derived: the 2022 census gives every district and
# phase separately (table 3.3, via `data/raw/observations.csv`), and this script
# reads them rather than hard-coding a guess.
CITY_POPULATION = 227_613.0

# Census 2022 locality -> the island the reroute models. Maafannu, Galolhu,
# Henveiru and Machchangolhi are the four districts of Malé island itself.
CENSUS_LOCALITY_ISLAND = {
    "Maafannu": "Malé",
    "Galolhu": "Malé",
    "Henveiru": "Malé",
    "Machchangolhi": "Malé",
    "Hulhumaale Phase 1": "Hulhumalé",
    "Hulhumaale Phase 2": "Hulhumalé",
    "Hulhule": "Hulhulé",
}

# Storeys by building type, used only where `building:levels` is absent. Values
# are the observed street character of Malé and Hulhumalé, not measurements.
DEFAULT_LEVELS = {
    "apartments": 8,
    "residential": 4,
    "house": 2,
    "dormitory": 6,
    "hotel": 6,
    "guest_house": 4,
    "office": 6,
    "commercial": 5,
    "retail": 2,
    "school": 2,
    "hospital": 4,
    "government": 4,
    "mosque": 1,
    "yes": 4,
}

# How much of a footprint is somewhere people sleep. A storage tank or a roof is
# a building in OSM and a resident count of zero here.
DWELLING_FACTOR = {
    "apartments": 1.0,
    "residential": 1.0,
    "house": 1.0,
    "dormitory": 1.0,
    "yes": 1.0,
    "hotel": 0.5,
    "guest_house": 0.5,
    "school": 0.15,
    "hospital": 0.15,
    "government": 0.2,
    "mosque": 0.1,
    "industrial": 0.05,
    "warehouse": 0.05,
    "storage_tank": 0.0,
    "roof": 0.0,
    "construction": 0.0,
    "garage": 0.0,
    "garages": 0.0,
    "shed": 0.05,
    "container": 0.0,
}

LANDUSE_FACTOR = {"residential": 1.3, "commercial": 0.7, "retail": 0.8, "industrial": 0.5, "construction": 0.4}

# Attractor weights. A hospital is the strongest single pull in the network; a
# guest-house is nearly none. Stated as data because a planner will want to
# change them.
POI_WEIGHTS = {
    "hospital": 12.0,
    "university": 9.0,
    "marketplace": 8.0,
    "ferry_terminal": 7.0,
    "college": 6.0,
    "clinic": 6.0,
    "school": 5.0,
    "townhall": 5.0,
    "office": 4.0,
    "courthouse": 4.0,
    "doctors": 4.0,
    "hospital_cluster": 10.0,
    "police": 2.0,
    "dentist": 2.5,
    "fire_station": 2.0,
    "hotel": 2.0,
    "place_of_worship": 2.0,
    "guest_house": 1.0,
    "bus_station": 6.0,
    "bank": 2.0,
    "government": 4.0,
}

# What counts as a workplace, for `job_score` (as opposed to a service that
# people visit once, like a courthouse).
EMPLOYMENT_KINDS = {"office", "hospital", "clinic", "marketplace", "government", "townhall", "ferry_terminal"}


def fetch() -> dict:
    out = subprocess.run(
        ["curl", "-sSf", "--max-time", "230", "-A", "Wayfinders-datathon/1.0", "-G", OVERPASS,
         "--data-urlencode", f"data={QUERY}"],
        capture_output=True, check=True,
    ).stdout
    return json.loads(out)


def centre(e: dict) -> tuple[float, float] | None:
    """Centroid of an Overpass element: node position, or way geometry mean."""
    if e["type"] == "node":
        return float(e["lat"]), float(e["lon"])
    geom = e.get("geometry") or []
    if not geom:
        # a relation: use the mean of its outer members
        pts = [p for m in e.get("members", []) for p in (m.get("geometry") or [])]
    else:
        pts = geom
    if not pts:
        return None
    return sum(p["lat"] for p in pts) / len(pts), sum(p["lon"] for p in pts) / len(pts)


def level_of(tags: dict) -> float:
    raw = tags.get("building:levels")
    if raw:
        try:
            v = float(str(raw).split(";")[0].replace(",", "."))
            if 0.5 <= v <= 60:
                return v
        except ValueError:
            pass
    return float(DEFAULT_LEVELS.get(tags.get("building", "yes"), 4))


def is_poi(tags: dict) -> str | None:
    """The single most important attractor kind on an element, if any."""
    if tags.get("amenity") in POI_WEIGHTS:
        return tags["amenity"]
    if tags.get("tourism") in POI_WEIGHTS:
        return tags["tourism"]
    if "office" in tags or tags.get("building") == "office":
        return "office"
    if tags.get("building") == "government":
        return "government"
    return None


def slim(raw: dict) -> dict:
    """Reduce an Overpass payload to what the build actually uses."""
    buildings, pois, landuse = [], [], []
    for e in raw["elements"]:
        tags = e.get("tags", {})
        if "building" in tags:
            c = centre(e)
            if c is None:
                continue
            geom = e.get("geometry") or []
            ring = [(p["lat"], p["lon"]) for p in geom]
            buildings.append({
                "lat": round(c[0], 6),
                "lon": round(c[1], 6),
                "area_m2": round(ring_area_m2(ring), 1) if len(ring) >= 3 else 0.0,
                "levels": level_of(tags),
                "kind": tags["building"],
                "name": tags.get("name"),
            })
        kind = is_poi(tags)
        if kind:
            c = centre(e)
            if c is not None:
                pois.append({
                    "lat": round(c[0], 6),
                    "lon": round(c[1], 6),
                    "kind": kind,
                    "name": tags.get("name") or tags.get("name:en") or "",
                    "_raw": raw_from(tags),
                })
        if tags.get("landuse") in LANDUSE_FACTOR:
            for member in ([e] if e["type"] == "way" else e.get("members", [])):
                geom = member.get("geometry") or []
                ring = [(p["lat"], p["lon"]) for p in geom]
                if len(ring) >= 3:
                    landuse.append({"kind": tags["landuse"], "ring": [[round(a, 6), round(b, 6)] for a, b in ring]})
                    break
    return {
        "queried_at": raw.get("osm3s", {}).get("timestamp_osm_base", ""),
        "bbox": BBOX,
        "attribution": "© OpenStreetMap contributors (ODbL 1.0)",
        "buildings": buildings,
        "pois": pois,
        "landuse": landuse,
    }


def raw_from(tags: dict) -> str:
    """One compact label per POI, so the map can say what the dot is."""
    for key in ("amenity", "tourism", "office"):
        if key in tags:
            return f"{key}={tags[key]}" if key != "office" else "office"
    return ""


def load_surface() -> dict:
    if len(sys.argv) > 1:
        data = slim(json.loads(pathlib.Path(sys.argv[1]).read_text()))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        print(f"cached {CACHE.relative_to(ROOT)}: {len(data['buildings']):,} buildings, "
              f"{len(data['pois']):,} POIs, {len(data['landuse']):,} landuse polygons")
        return data
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    print("no cache; querying Overpass once (this is the only network call)...")
    data = slim(fetch())
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return data


def island_targets() -> tuple[dict[str, float], float]:
    """Published 2022 population per in-scope island, scaled to the projection.

    The census table lists every administrative locality separately, so the
    Malé / Hulhumalé / Hulhulé split is observed rather than inferred from
    buildings. Only the *within*-island distribution needs a proxy.
    """
    obs = pd.read_csv(ROOT / "data" / "raw" / "observations.csv")
    table = obs["source_table"].astype(str)
    q = obs[
        (obs["date"].astype(str) == "2022")
        & (obs["metric"] == "census_population")
        & (table.str.startswith("3.3"))
    ]
    raw = {str(r.geo): float(r.value) for r in q.itertuples()}
    city_total = raw.get("Maale")
    if not city_total:
        raise SystemExit("census 3.3 rows are missing from data/raw/observations.csv")
    growth = CITY_POPULATION / city_total

    targets: dict[str, float] = {}
    for locality, island in CENSUS_LOCALITY_ISLAND.items():
        if locality not in raw:
            raise SystemExit(f"census locality not found: {locality}")
        targets[island] = targets.get(island, 0.0) + raw[locality] * growth
    return targets, growth


def islands() -> list[dict]:
    """The three in-scope islands, from the committed basemap."""
    base = json.loads((OUT / "basemap.geojson").read_text())
    out = []
    for f in base["features"]:
        if f["properties"].get("kind") != "land":
            continue
        name = (f["properties"].get("name") or "").strip()
        if name not in ("Malé", "Hulhulé", "Hulhumalé"):
            continue
        ring = [(lat, lon) for lon, lat in f["geometry"]["coordinates"][0]]
        out.append({"name": name, "ring": ring})
    return out


def island_of(lat: float, lon: float, polys: list[dict]) -> str:
    for p in polys:
        if point_in_polygon(lat, lon, [p["ring"]]):
            return p["name"]
    # Hulhulé's OSM outline is cut by the runway aprons; a building just off the
    # polygon is still on the airport island.
    if 4.183 <= lat <= 4.201 and 73.512 <= lon <= 73.535:
        return "Hulhulé"
    return ""


def main() -> None:
    surface = load_surface()
    polys = islands()
    if not polys:
        raise SystemExit("basemap has no Malé/Hulhulé/Hulhumalé polygons - rebuild the basemap first")

    # ---- cell level residential weight -----------------------------------
    cells: dict[tuple[int, int], dict] = {}
    island_cache: dict[tuple[int, int], str] = {}

    def island_at(lat: float, lon: float, key: tuple[int, int]) -> str:
        """Which in-scope island a cell belongs to, decided at the cell centre.

        Deciding per cell rather than per building keeps the point-in-polygon
        pass at ~500 tests instead of ~11,000, and a 150 m cell cannot straddle
        two islands here.
        """
        if key not in island_cache:
            island_cache[key] = island_of(*cell_centre(*key, CELL_M), polys)
        return island_cache[key]

    def cell(lat, lon) -> dict | None:
        key = cell_index(lat, lon, CELL_M)
        isl = island_at(lat, lon, key)
        if not isl:
            return None
        c = cells.get(key)
        if c is None:
            clat, clon = cell_centre(*key, CELL_M)
            c = cells[key] = {
                "cell_id": cell_id(*key),
                "lat": round(clat, 6),
                "lon": round(clon, 6),
                "island": isl,
                "weight": 0.0,
                "n_buildings": 0,
                "night_rides": 0.0,
                "attractor": 0.0,
                "jobs": 0.0,
                "landuse": 1.0,
            }
        return c

    # Pre-bin landuse: stamp the multiplier onto every cell whose centre falls
    # inside the polygon. One pass, then building assignment is a dict lookup.
    for lu in surface["landuse"]:
        ring = [(a, b) for a, b in lu["ring"]]
        if len(ring) < 3:
            continue
        lats = [a for a, _ in ring]
        lons = [b for _, b in ring]
        r0, c0 = cell_index(min(lats), min(lons), CELL_M)
        r1, c1 = cell_index(max(lats), max(lons), CELL_M)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                clat, clon = cell_centre(row, col, CELL_M)
                if point_in_polygon(clat, clon, [ring]):
                    isl = island_at(clat, clon, (row, col))
                    if not isl:
                        continue
                    c = cells.get((row, col))
                    if c is None:
                        c = cells[(row, col)] = {
                            "cell_id": cell_id(row, col),
                            "lat": round(clat, 6),
                            "lon": round(clon, 6),
                            "island": isl,
                            "weight": 0.0,
                            "n_buildings": 0,
                            "night_rides": 0.0,
                            "attractor": 0.0,
                            "jobs": 0.0,
                            "landuse": 1.0,
                        }
                    c["landuse"] = LANDUSE_FACTOR[lu["kind"]]

    # The airport island is 802 residents by census (mostly staff quarters) and
    # an employment cluster; its population target is small, so the attractor
    # surface - not the dwelling count - is what puts service there.
    for b in surface["buildings"]:
        c = cell(b["lat"], b["lon"])
        if c is None:
            continue
        dwelling = DWELLING_FACTOR.get(b["kind"], 0.5)
        if dwelling == 0.0:
            c["n_buildings"] += 1
            continue
        c["weight"] += b["area_m2"] * b["levels"] * dwelling * c["landuse"]
        c["n_buildings"] += 1

    # ---- revealed residential presence: Avas at night --------------------
    rides = pd.read_csv(ROOT / "data" / "raw" / "avas_rides_aug_sep_2026.csv")
    rides = rides[rides["status"] != "ride_expired"].copy()
    rides["ts"] = pd.to_datetime(rides["date_started"])
    days = max(1, rides["ts"].dt.date.nunique())
    night = rides[(rides["ts"].dt.hour >= 22) | (rides["ts"].dt.hour < 6)]
    for r in night.itertuples():
        c = cell(float(r.pickup_lat), float(r.pickup_lng))
        if c is not None:
            c["night_rides"] += 1.0

    # ---- attractors -------------------------------------------------------
    hotspot_feats = []
    for p in surface["pois"]:
        w = POI_WEIGHTS.get(p["kind"], 1.0)
        c = cell(p["lat"], p["lon"])
        if c is not None:
            c["attractor"] += w
            c["jobs"] += w if p["kind"] in EMPLOYMENT_KINDS else 0.0
        hotspot_feats.append({
            "type": "Feature",
            "properties": {
                "kind": p["kind"],
                "name": p["name"],
                "label": p["_raw"],
                "weight": w,
            },
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
        })

    # Office buildings are not individually tagged in Malé, but `building=office`
    # and `office=*` are. A cluster of them is still a workplace hotspot.
    for b in surface["buildings"]:
        if b["kind"] in ("office", "government", "commercial"):
            c = cell(b["lat"], b["lon"])
            if c is not None and b["area_m2"] > 200:
                c["attractor"] += 1.5
                c["jobs"] += 1.5

    # ---- calibrate population, blend, write -------------------------------
    # Each island is calibrated to its own published census count, so a dense
    # low-rise Malé and a newer tall-block Hulhumalé cannot be compared on
    # floor area alone.
    targets, growth = island_targets()
    weight_by_island: dict[str, float] = {}
    for c in cells.values():
        weight_by_island[c["island"]] = weight_by_island.get(c["island"], 0.0) + c["weight"]
    for isl in targets:
        if weight_by_island.get(isl, 0.0) <= 0:
            raise SystemExit(f"no residential weight on {isl} - check the building fetch")

    total_pop = 0.0
    for c in cells.values():
        c["population"] = targets[c["island"]] * c["weight"] / weight_by_island[c["island"]]
        total_pop += c["population"]
    total_night = sum(c["night_rides"] for c in cells.values())
    total_jobs = sum(c["jobs"] for c in cells.values()) or 1.0

    rows = []
    for c in cells.values():
        pop_share = c["population"] / total_pop
        night_share = c["night_rides"] / total_night if total_night else 0.0
        rows.append({
            "cell_id": c["cell_id"],
            "lat": c["lat"],
            "lon": c["lon"],
            "island": c["island"],
            "population": round(c["population"], 1),
            "night_taxi_rides_per_day": round(c["night_rides"] / days, 2),
            "residential_score": round(pop_share * 100, 4),
            "job_score": round(c["jobs"] / total_jobs * 100, 4),
            "attractor_score": round(c["attractor"], 2),
            "combined_score": round((0.5 * pop_share + 0.5 * night_share) * 100, 4),
        })

    grid = pd.DataFrame(rows).sort_values("combined_score", ascending=False).reset_index(drop=True)
    grid.to_csv(OUT / "pop_grid.csv", index=False)

    (OUT / "reroute_hotspots.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": hotspot_feats}, ensure_ascii=False)
    )

    by_island = grid.groupby("island").agg(
        cells=("cell_id", "size"),
        population=("population", "sum"),
        night_rides=("night_taxi_rides_per_day", "sum"),
        attractor=("attractor_score", "sum"),
    )
    params = json.loads((OUT / "reroute_params.json").read_text()) if (OUT / "reroute_params.json").exists() else {}
    params["population_surface"] = {
        "cell_m": CELL_M,
        "blend": {"population": 0.5, "night_taxi": 0.5},
        "calibration_total": CITY_POPULATION,
        "calibration_target": "Census 2022 (MBS yearbook 3.3) scaled to the 2022 mid-year projection for Male' City (table 3.16)",
        "census_growth_factor": round(growth, 4),
        "island_targets": {k: round(v, 1) for k, v in targets.items()},
        "bbox": BBOX,
        "osm_queried_at": surface["queried_at"],
        "osm_attribution": surface["attribution"],
        "in_scope_islands": [p["name"] for p in polys],
        "limitations": [
            "island totals are published census counts; the within-island split is a building-footprint x storeys proxy",
            "building:levels is present on a minority of footprints; storeys are inferred by type for the rest",
            "Villimale' is out of scope and is not fetched or scored",
        ],
        "island_totals": {k: {kk: round(float(vv), 1) for kk, vv in v.items()} for k, v in by_island.iterrows()},
    }
    (OUT / "reroute_params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 200)
    print("=" * 96)
    print(f"POPULATION + ATTRACTOR SURFACE  ({CELL_M:.0f} m cells, {len(grid)} cells)")
    print("=" * 96)
    print(by_island.to_string())
    print()
    print(f"buildings scored : {len(surface['buildings']):,}")
    print(f"attractor POIs   : {len(hotspot_feats):,}")
    print(f"census target    : {CITY_POPULATION:,.0f} (Male' City, 2022 projection)")
    print()
    print("top 12 cells by combined score")
    print(grid.head(12)[["cell_id", "island", "population", "night_taxi_rides_per_day", "attractor_score", "combined_score"]].to_string(index=False))
    print()
    print(f"wrote {OUT/'pop_grid.csv'} ({len(grid)} rows)")
    print(f"wrote {OUT/'reroute_hotspots.geojson'} ({len(hotspot_feats)} features)")


if __name__ == "__main__":
    main()
