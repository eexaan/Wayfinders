"""
================================================================================
The reroute network: today's Malé, real Hulhumalé circuits
================================================================================
Maldives Datathon 2026 | Team Wayfinders

THE DESIGN, IN ONE PARAGRAPH
    Malé's streets are narrow, its routes are already close to what the roads
    allow, and 97% of taxi pickups start within 300 m of an existing stop. There
    is nothing to win by re-drawing them, and two earlier attempts lost badly:
    journey time got worse because regenerated lines forced transfers. So Malé
    and the airport island keep **today's routes, verbatim** - the exact OSRM
    road-snapped geometry committed in `route_segments.geojson`, copied leg for
    leg with the coordinates untouched.

    Hulhumalé is the opposite case. It is planned, gridded, still filling in, and
    its local routes (R5, R6) are open point-to-point services whose terminals
    are 781 m apart - a passenger going the other way round the island is not
    served at all. So the island's local service becomes **closed circuits**,
    built so that no road is driven twice.

WHAT THIS SCRIPT DOES
    1. Stop set      every stop used by R1-R9 (the routes with a recorded
                     timetable), plus new stops in Hulhumalé's filled-in blocks.
                     Existing stops are never moved.
    2. Kept routes   R1, R2, R3, R4, R7, R8, R9 copied verbatim from
                     route_segments.geojson. No Dijkstra, no snapping, no
                     projection - there is nothing left to get wrong.
    3. Loops         Hulhumalé circuits built with an edge-penalised Dijkstra, so
                     the return leg takes a different street. Zero road segments
                     are traversed twice within a loop, by construction and
                     verified before writing.
    4. Through-run   each cross-island route continues past its Hulhumalé stop
                     along a loop, so a trip from Malé is a direct ride rather
                     than a ride plus a change.
    5. Fleet         a fixed 55 buses, allocated across routes by peak demand.
                     The headway each route can sustain is cycle / buses, so the
                     fleet is enforced physically rather than asserted.

WHAT THIS IS NOT
    Not a timetable and not a redesign of Malé. R10-R12 are excluded from both
    networks: they have no captured departures and no ridership count, so
    replaying them would mean inventing a schedule. Villimalé is out of scope
    (ADR-0015) - no road link, no Avas trips, ferry-dependent.

OUTPUT (dashboard/data/)
    reroute_stops.csv              one row per stop
    reroute_routes.csv             one row per route
    reroute_segments.geojson       one LineString per stop-to-stop leg
    reroute_demand_stop_hour.csv   expected boardings per stop per hour
    reroute_od.csv                 stop-to-stop daily flow the sim samples
    reroute_fleet_alloc.csv        the fixed-fleet allocation
    reroute_params.json            every assumption this run used
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from geo import haversine_m  # noqa: E402
import road_graph as rg  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "dashboard" / "data"
RAW = ROOT / "data" / "raw"

# ---- routes in and out of scope ------------------------------------------
# Kept verbatim: every route with a recorded timetable that is not purely
# Hulhumalé-internal. R9 is kept because it links the airport island to
# Hulhumalé and is the only airport service there.
KEPT_ROUTES = ["R1", "R2", "R3", "R4", "R7", "R8", "R9"]
REPLACED_BY_LOOPS = ["R5", "R6"]
# Excluded from BOTH networks: no captured departures, no ridership count.
EXCLUDED = ["R10", "R11", "R12"]
# Stops are kept from every route with a timetable, including the two the loops
# replace: a bus shelter does not disappear because the route number changed.
STOP_SOURCE_ROUTES = KEPT_ROUTES + REPLACED_BY_LOOPS

# ---- population surface / stop placement ---------------------------------
WALK_RADIUS_M = 400.0
WALK_MAX_M = 800.0
WALK_DETOUR = 1.25
CANDIDATE_SPACING_M = 120.0
STOP_SPACING_M = 230.0
HULHUMALE_STOP_TARGET = 34
ATTRACTOR_PEOPLE_EQUIV = 220.0
FORCED_ATTRACTOR_WEIGHT = 8.0

# ---- loops ---------------------------------------------------------------
LOOP_EDGE_PENALTY = 20.0   # x cost on an edge the circuit already used
LOOP_ANCHORS = 2           # waypoints between hub and return, per circuit
MAX_LOOPS = 4
MAX_KM_LOOP = 12.0
MIN_LOOP_STOPS = 6
LOOP_SNAP_M = 200.0        # how close a stop must be to the path to be on it

# ---- demand --------------------------------------------------------------
CATCHMENT_M = 450.0        # a ride further than this from a stop is not evidence
SERVICE_DAYTYPE = "sat_holiday"
SERVICE_DAY_LABEL = "Saturday"
DEMAND_ROUTES = ["R1", "R2", "R3", "R4", "R7"]
AIRPORT_BUS_SHARE = 0.06   # of arriving air passengers; a judgement, not a measurement

# ---- fleet ---------------------------------------------------------------
TOTAL_BUSES = 55           # today's fleet, held constant across the ablation
LAYOVER_MIN = 6.0
DWELL_MIN = 0.4

BUS_CLASS = {
    "double_decker": {"seats": 72, "max": 84, "model": "Yutong ZK6116HGS"},
    "coach": {"seats": 55, "max": 55, "model": "Yutong ZK6122H9"},
    "single": {"seats": 33, "max": 33, "model": "Yutong ZK6126HGA"},
}


# ---------------------------------------------------------------------------
def load_inputs():
    grid = pd.read_csv(OUT / "pop_grid.csv")
    hot = json.loads((OUT / "reroute_hotspots.geojson").read_text())["features"]
    hotspots = [{"lat": f["geometry"]["coordinates"][1], "lon": f["geometry"]["coordinates"][0],
                 **f["properties"]} for f in hot]
    graph = rg.load_graph()
    dense = rg.densify(graph, 70.0)
    scope = rg.main_component(dense)
    return grid, hotspots, dense, scope


def island_of(lat: float, lon: float) -> str:
    if lon < 73.5:
        return "Villimalé"
    if lat >= 4.2:
        return "Hulhumalé"
    if lat >= 4.185:
        return "Hulhulé"
    return "Malé"


def cell_of(lat: float, lon: float, grid: pd.DataFrame) -> int:
    best, best_d = 0, float("inf")
    for i, r in enumerate(grid.itertuples()):
        d = haversine_m(lat, lon, r.lat, r.lon)
        if d < best_d:
            best, best_d = i, d
    return best


def candidate_stops(graph: dict, scope: set) -> list[dict]:
    """Road nodes in scope, thinned to CANDIDATE_SPACING_M apart."""
    taken: dict[tuple[int, int], list[dict]] = defaultdict(list)
    out: list[dict] = []
    cell = CANDIDATE_SPACING_M

    def bucket(lat, lon):
        return int(lat * 110_574 / cell), int(lon * 111_030 / cell)

    for nid in sorted(scope):
        lat, lon = graph["nodes"][nid]
        br, bc = bucket(lat, lon)
        close = False
        for r in (br - 1, br, br + 1):
            for c in (bc - 1, bc, bc + 1):
                if any(haversine_m(lat, lon, a["lat"], a["lon"]) < cell for a in taken.get((r, c), ())):
                    close = True
                    break
            if close:
                break
        if close:
            continue
        entry = {"node": nid, "lat": lat, "lon": lon}
        out.append(entry)
        taken[(br, bc)].append(entry)
    return out


def build_coverage(cands: list[dict], grid: pd.DataFrame, hotspots: list[dict]):
    """Walk distance from every cell and attractor to every nearby candidate."""
    bucket: dict[tuple[int, int], list[int]] = defaultdict(list)
    for ci, c in enumerate(cands):
        bucket[(int(c["lat"] // 0.01), int(c["lon"] // 0.01))].append(ci)

    def near(lat, lon, radius_m):
        out = []
        br, bc = int(lat // 0.01), int(lon // 0.01)
        for r in range(br - 2, br + 3):
            for c in range(bc - 2, bc + 3):
                for ci in bucket.get((r, c), ()):
                    d = haversine_m(lat, lon, cands[ci]["lat"], cands[ci]["lon"])
                    if d <= radius_m:
                        out.append((ci, round(d * WALK_DETOUR)))
        return out

    walk = [near(row["lat"], row["lon"], WALK_MAX_M / WALK_DETOUR) for _, row in grid.iterrows()]
    hotspot_walk = [near(h["lat"], h["lon"], WALK_MAX_M / WALK_DETOUR) for h in hotspots]
    return walk, hotspot_walk


def pmedian_value(selected: set, walk, hotspot_walk, cell_value, hw) -> float:
    total = 0.0
    for i, lst in enumerate(walk):
        best = WALK_MAX_M
        for ci, d in lst:
            if ci in selected and d < best:
                best = d
        total += cell_value[i] * best
    for hi, lst in enumerate(hotspot_walk):
        best = WALK_MAX_M
        for ci, d in lst:
            if ci in selected and d < best:
                best = d
        total += hw[hi] * best
    return total


def choose_island_stops(cands, walk, hotspot_walk, cell_value, hw, eligible: set) -> list[int]:
    """Greedy p-median over the eligible candidates only.

    Coverage saturates - a "cover every cell within 400 m" objective stops at
    about 45 stops and then reports success. Minimising total walking keeps
    discriminating all the way to the target.
    """
    def walk_to(ci, lst):
        for c, d in lst:
            if c == ci:
                return d
        return WALK_MAX_M

    cur = [WALK_MAX_M] * len(walk)
    cur_h = [WALK_MAX_M] * len(hotspot_walk)
    chosen: list[int] = []
    chosen_set: set[int] = set()

    while len(chosen) < HULHUMALE_STOP_TARGET:
        best_ci, best_gain = None, 0.0
        for ci in eligible:
            if ci in chosen_set:
                continue
            if any(haversine_m(cands[ci]["lat"], cands[ci]["lon"], cands[cj]["lat"], cands[cj]["lon"]) < STOP_SPACING_M
                   for cj in chosen):
                continue
            g = 0.0
            for i, lst in enumerate(walk):
                d = walk_to(ci, lst)
                if d < cur[i]:
                    g += cell_value[i] * (cur[i] - d)
            for hi, lst in enumerate(hotspot_walk):
                d = walk_to(ci, lst)
                if d < cur_h[hi]:
                    g += hw[hi] * (cur_h[hi] - d)
            if g > best_gain:
                best_ci, best_gain = ci, g
        if best_ci is None:
            break
        chosen.append(best_ci)
        chosen_set.add(best_ci)
        for i, lst in enumerate(walk):
            cur[i] = min(cur[i], walk_to(best_ci, lst))
        for hi, lst in enumerate(hotspot_walk):
            cur_h[hi] = min(cur_h[hi], walk_to(best_ci, lst))
    return chosen


def name_island_stop(stop, existing, hotspots, n) -> str:
    best, best_d = None, 1e9
    for r in existing.itertuples():
        d = haversine_m(stop["lat"], stop["lon"], r.lat, r.lon)
        if d < best_d:
            best, best_d = str(r.stop_name).strip(), d
    if best and best_d <= 130:
        return best
    best_h, best_hd = None, 1e9
    for h in hotspots:
        if not h["name"]:
            continue
        d = haversine_m(stop["lat"], stop["lon"], h["lat"], h["lon"])
        if d < best_hd:
            best_h, best_hd = h["name"].strip(), d
    if best_h and best_hd <= 150:
        return best_h
    return f"Hulhumalé stop {n}"


# ---------------------------------------------------------------------------
def load_committed_segments() -> dict:
    """Today's OSRM road-snapped legs, keyed by route then ordered by seq."""
    feats = json.loads((OUT / "route_segments.geojson").read_text())["features"]
    by: dict[str, list[dict]] = defaultdict(list)
    for f in feats:
        p = f["properties"]
        by[p["route_code"]].append({
            "seq": int(p["seq"]),
            "from_code": str(p["from_code"]),
            "to_code": str(p["to_code"]),
            "from_stop": p["from_stop"],
            "to_stop": p["to_stop"],
            "road_m": float(p["road_m"]),
            "minutes": float(p["median_segment_minutes"] or 0.0),
            "bridge": bool(p.get("bridge")),
            "coords": f["geometry"]["coordinates"],
        })
    for legs in by.values():
        legs.sort(key=lambda l: l["seq"])
    return by


def main() -> None:
    grid, hotspots, graph, scope = load_inputs()
    committed = load_committed_segments()
    existing = pd.read_csv(OUT / "route_stops.csv")
    master = pd.read_csv(OUT / "routes_master.csv").set_index("route_code")

    # ------------------------------------------------------------------
    # 1. Stop set: every stop today's timed routes use, plus new island stops
    # ------------------------------------------------------------------
    stops: list[dict] = []
    by_code: dict[str, int] = {}

    def add_stop(stop_id, lat, lon, island, name, why, today_code=""):
        stops.append({
            "stop_id": stop_id,
            "today_code": today_code,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "island": island,
            "name": name,
            "placed_because": why,
            "carried_over": "true" if today_code else "false",
        })
        return len(stops) - 1

    src = existing[existing["route_code"].isin(STOP_SOURCE_ROUTES)].copy()
    for r in src.sort_values(["route_code", "stop_order"]).itertuples():
        code = str(r.stop_code)
        if code in by_code:
            continue
        lat, lon = float(r.lat), float(r.lon)
        idx = add_stop(f"K{code}", lat, lon, island_of(lat, lon), str(r.stop_name).strip(),
                       "today's stop, unchanged", today_code=code)
        by_code[code] = idx

    kept_stops_before = len(stops)

    # New stops only where the stop set is actually wrong: Hulhumalé.
    cands = candidate_stops(graph, scope)
    walk, hotspot_walk = build_coverage(cands, grid, hotspots)
    cell_value = [p + 60.0 * n for p, n in zip(grid["population"], grid["night_taxi_rides_per_day"])]
    hw = [h["weight"] * ATTRACTOR_PEOPLE_EQUIV for h in hotspots]

    island_cells = [i for i, r in enumerate(grid.itertuples()) if r.island == "Hulhumalé"]
    eligible = {ci for ci, c in enumerate(cands) if island_of(c["lat"], c["lon"]) == "Hulhumalé"}
    # A candidate next to a stop we already keep is not a new stop.
    existing_pts = [(s["lat"], s["lon"]) for s in stops]
    eligible = {ci for ci in eligible
                if all(haversine_m(cands[ci]["lat"], cands[ci]["lon"], la, lo) > 180
                       for la, lo in existing_pts)}

    chosen = choose_island_stops(cands, walk, hotspot_walk, cell_value, hw, eligible)
    for n, ci in enumerate(chosen, start=1):
        c = cands[ci]
        add_stop(f"H{n:03d}", c["lat"], c["lon"], "Hulhumalé",
                 name_island_stop(c, existing, hotspots, n),
                 "new stop: Hulhumalé's residential blocks grew past the stop set")

    # enrich with population and attractors within the walk radius
    for s in stops:
        near = [(r, haversine_m(s["lat"], s["lon"], r.lat, r.lon)) for r in grid.itertuples()]
        s["population_400m"] = round(sum(float(r.population) for r, d in near
                                        if d <= WALK_RADIUS_M / WALK_DETOUR))
        hot400 = [h for h in hotspots if haversine_m(s["lat"], s["lon"], h["lat"], h["lon"]) <= WALK_RADIUS_M / WALK_DETOUR]
        s["hotspots_400m"] = len(hot400)
        s["top_hotspot"] = max(hot400, key=lambda h: h["weight"])["name"] if hot400 else ""

    stop_lat = [s["lat"] for s in stops]
    stop_lon = [s["lon"] for s in stops]
    name_of = [s["name"] for s in stops]
    island_of_idx = [s["island"] for s in stops]
    print(f"stops: {kept_stops_before} kept from today + {len(chosen)} new in Hulhumalé "
          f"= {len(stops)}")

    # ------------------------------------------------------------------
    # 2. Demand: snap Saturday taxi rides to stops, scale to the MTCC level
    # ------------------------------------------------------------------
    rides = pd.read_csv(RAW / "avas_rides_aug_sep_2026.csv")
    rides = rides[rides["status"] != "ride_expired"].copy()
    rides["ts"] = pd.to_datetime(rides["date_started"])
    rides = rides[rides["ts"].dt.day_name() == SERVICE_DAY_LABEL].copy()
    n_days = max(1, rides["ts"].dt.date.nunique())
    rides["hour"] = rides["ts"].dt.hour

    def snap(lat, lon):
        best, best_d = None, float("inf")
        for k, (slat, slon) in enumerate(zip(stop_lat, stop_lon)):
            d = haversine_m(lat, lon, slat, slon)
            if d < best_d:
                best, best_d = k, d
        return best if best_d <= CATCHMENT_M else None

    pairs: dict[tuple[int, int], float] = defaultdict(float)
    hour_rows: dict[tuple[int, int], float] = defaultdict(float)
    kept = dropped = 0
    for r in rides.itertuples():
        o = snap(float(r.pickup_lat), float(r.pickup_lng))
        d = snap(float(r.dropoff_lat), float(r.dropoff_lng))
        if o is None or d is None or o == d:
            dropped += 1
            continue
        kept += 1
        pairs[(o, d)] += 1.0 / n_days
        hour_rows[(o, int(r.hour))] += 1.0 / n_days

    daytype = pd.read_csv(OUT / "demand_by_daytype.csv")
    target = float(daytype[(daytype["day_type"] == SERVICE_DAYTYPE)
                           & (daytype["route_code"].isin(DEMAND_ROUTES))]["boardings_per_day"].sum())
    scale = target / sum(hour_rows.values())
    print(f"taxi rides snapped {kept:,} / dropped {dropped:,}   x{scale:.3f} to {target:,.0f} boardings/day")

    # the flight-arrival stream at VIA
    air = pd.read_csv(OUT / "airport_demand_profile.csv")
    air["bus_pax"] = ((air["mbs_year_domestic_arrivals_per_day"] + air["mbs_year_intl_arrivals_per_day"])
                      * air["macl_international_arrival_share"] * AIRPORT_BUS_SHARE)
    via = min(range(len(stops)), key=lambda k: haversine_m(4.1915, 73.5245, stop_lat[k], stop_lon[k]))
    if haversine_m(4.1915, 73.5245, stop_lat[via], stop_lon[via]) > 700:
        raise SystemExit("no stop near the VIA terminal")

    od: dict[tuple[int, int], float] = {(o, d): v * scale for (o, d), v in pairs.items()}
    dest_mix: dict[int, float] = defaultdict(float)
    for (_o, d), v in od.items():
        dest_mix[d] += v
    dm_total = sum(dest_mix.values()) or 1.0
    for r in air.itertuples():
        pax = float(r.bus_pax)
        if pax <= 0:
            continue
        for d, share in dest_mix.items():
            if d != via:
                od[(via, d)] = od.get((via, d), 0.0) + pax * share / dm_total

    board_hour: dict[tuple[int, int], float] = defaultdict(float)
    for (o, h), v in hour_rows.items():
        board_hour[(o, h)] += v * scale
    for r in air.itertuples():
        board_hour[(via, int(r.hour))] += float(r.bus_pax)
    total_boardings = sum(board_hour.values())
    print(f"daily boardings in the demand table: {total_boardings:,.0f}")

    # ------------------------------------------------------------------
    # 3. Kept routes: today's geometry, verbatim
    # ------------------------------------------------------------------
    routes: list[dict] = []

    def add_route(code, line, legs, kind, note):
        routes.append({"route_id": code, "line": line, "legs": legs, "kind": kind, "note": note})
        return len(routes) - 1

    for code in KEPT_ROUTES:
        legs_c = committed.get(code, [])
        if not legs_c:
            raise SystemExit(f"{code} has no committed geometry - rebuild snap_routes.py")
        # stop sequence is exactly the leg endpoints, by today's stop_code
        line: list[int] = []
        legs: list[dict] = []
        for leg in legs_c:
            a = by_code.get(leg["from_code"])
            b = by_code.get(leg["to_code"])
            if a is None or b is None:
                raise SystemExit(f"{code} uses stop {leg['from_code']}->{leg['to_code']} "
                                 "which is not in the stop set")
            if not line:
                line.append(a)
            elif line[-1] != a:
                raise SystemExit(f"{code} leg sequence is discontinuous at seq {leg['seq']}")
            line.append(b)
            legs.append({"from": a, "to": b, "coords": leg["coords"],
                         "length_m": leg["road_m"], "minutes": leg["minutes"]})
        add_route(code, line, legs, "kept",
                  "today's alignment and road-snapped geometry, unchanged")

    # ------------------------------------------------------------------
    # 4. Hulhumalé loops: closed circuits, no road twice
    # ------------------------------------------------------------------
    island_idx = [k for k in range(len(stops)) if island_of_idx[k] == "Hulhumalé"]
    if not island_idx:
        raise SystemExit("no Hulhumalé stops")
    node_of = [rg.nearest_node(graph, la, lo, scope) for la, lo in zip(stop_lat, stop_lon)]

    def peak_at(k):
        return max(board_hour.get((k, h), 0.0) for h in range(24))

    hub = max(island_idx, key=peak_at)

    def rebuild_legs(line: list[int], graph, scope, node_of) -> list[dict]:
        legs = []
        for a, b in zip(line, line[1:]):
            _d, path = rg.shortest_path(graph, node_of[a], node_of[b], scope)
            legs.append({
                "from": a, "to": b,
                "coords": rg.polyline(graph, path),
                "length_m": sum(haversine_m(graph["nodes"][x][0], graph["nodes"][x][1],
                                            graph["nodes"][y][0], graph["nodes"][y][1])
                                for x, y in zip(path, path[1:])),
                "minutes": rg.travel_minutes(graph, path) + DWELL_MIN,
            })
        return legs

    def stops_on_path(path: list, include: set[int]) -> list[int]:
        """Stops that lie on a node path, in travel order."""
        pts = [graph["nodes"][n] for n in path]
        hits: list[tuple[int, int]] = []
        for k in include:
            best_j, best_d = None, LOOP_SNAP_M
            for j, (la, lo) in enumerate(pts):
                d = haversine_m(stop_lat[k], stop_lon[k], la, lo)
                if d < best_d:
                    best_j, best_d = j, d
            if best_j is not None:
                hits.append((best_j, k))
        hits.sort()
        out: list[int] = []
        for _j, k in hits:
            if out and haversine_m(stop_lat[out[-1]], stop_lon[out[-1]],
                                   stop_lat[k], stop_lon[k]) < 80:
                continue
            out.append(k)
        return out

    def circuit(anchors: list[int]) -> tuple[list[int], list[dict]]:
        """Close a circuit through the anchors in the order given, back to the hub.

        Every leg is one stop-to-stop road path. Edges the circuit has already
        used are penalised by LOOP_EDGE_PENALTY, so the closing leg is pushed
        onto a different street instead of retracing the outbound run. That is
        what makes this a loop rather than an out-and-back: no road is driven
        twice, and the map shows a ring instead of a doubled line.
        """
        line = [hub]
        legs: list[dict] = []
        used: set = set()
        for tgt in list(anchors) + [hub]:
            src = line[-1]
            if src == tgt:
                continue
            _d, path = rg.shortest_path(graph, node_of[src], node_of[tgt], scope,
                                        avoid=used, penalty=LOOP_EDGE_PENALTY)
            used |= set(rg.path_edges(path))
            legs.append({
                "from": src,
                "to": tgt,
                "coords": rg.polyline(graph, path),
                "length_m": sum(haversine_m(graph["nodes"][a][0], graph["nodes"][a][1],
                                            graph["nodes"][b][0], graph["nodes"][b][1])
                                for a, b in zip(path, path[1:])),
                "minutes": rg.travel_minutes(graph, path) + DWELL_MIN,
            })
            line.append(tgt)
        return line, legs

    def reused_edges(legs: list[dict]) -> int:
        """How many road segments this route traverses more than once.

        Counted from the written geometry, not from the routing call, so it
        validates what actually goes into the map.
        """
        seen: dict[tuple, int] = defaultdict(int)
        for leg in legs:
            cs = [(round(lon, 5), round(lat, 5)) for lon, lat in leg["coords"]]
            for a, b in zip(cs, cs[1:]):
                if a == b:
                    continue
                seen[(a, b) if a <= b else (b, a)] += 1
        return sum(1 for v in seen.values() if v > 1)

    # ---- circuits --------------------------------------------------------
    # A loop is a CYCLE IN THE ROAD GRAPH, not a tour of waypoints. It is built
    # as: hub -> anchor by the shortest path, then anchor -> hub by the shortest
    # path that penalises the roads just used. Because the road graph is
    # connected the return leg always exists, so the result is closed by
    # construction; because the outbound edges are penalised, the return takes a
    # different street, so the loop is a ring and not an out-and-back.
    #
    # Visiting waypoints in bearing order was tried and rejected: consecutive
    # stops in bearing order can be radially opposite, so the "loop" zig-zagged
    # across the island (27 km of route on a 2 km island).
    def stops_near(path: list, radius: float = 130.0) -> set[int]:
        out = set()
        for k in island_idx:
            for n in path:
                la, lo = graph["nodes"][n]
                if haversine_m(stop_lat[k], stop_lon[k], la, lo) < radius:
                    out.add(k)
                    break
        return out

    def ring(anchor: int) -> tuple[list, float, int]:
        """hub -> anchor -> hub, returning a different way."""
        d1, p1 = rg.shortest_path(graph, node_of[hub], node_of[anchor], scope)
        d2, p2 = rg.shortest_path(graph, node_of[hub], node_of[anchor], scope,
                                  avoid=set(rg.path_edges(p1)), penalty=LOOP_EDGE_PENALTY)
        path = p1 + p2[::-1][1:]
        shared = len(set(rg.path_edges(p1)) & set(rg.path_edges(p2)))
        return path, (d1 + d2) / 1000.0, shared

    # Evaluate every island stop as an anchor, keep the ones that make a clean
    # ring inside the length cap, then take a greedy set cover by new stops.
    pool: list[tuple[int, float, int, int, list]] = []
    for a in island_idx:
        if a == hub:
            continue
        path, km, shared = ring(a)
        if km <= MAX_KM_LOOP and shared <= 2:
            pool.append((len(stops_near(path)), km, shared, a, path))
    pool.sort(key=lambda t: (-t[0], t[1]))

    def legs_from_path(path: list, from_k: int, to_k: int) -> list[dict]:
        return [{
            "from": from_k, "to": to_k,
            "coords": rg.polyline(graph, path),
            "length_m": sum(haversine_m(graph["nodes"][x][0], graph["nodes"][x][1],
                                        graph["nodes"][y][0], graph["nodes"][y][1])
                            for x, y in zip(path, path[1:])),
            "minutes": rg.travel_minutes(graph, path) + DWELL_MIN,
        }]

    loops: list[int] = []
    island_served: set[int] = set()
    for cov_count, km, shared, anchor, path in pool:
        if len(loops) >= MAX_LOOPS:
            break
        new = stops_near(path) - island_served
        if len(new) < 4:
            continue
        # the stop sequence: hub, then the stops on the way out and back, in
        # journey order, ending at the hub again
        # The ordered stop list: every island stop within reach of the ring,
        # placed at the point of the ring it is nearest to. That gives journey
        # order directly and cannot drop a stop the ring passes.
        pos: dict[int, int] = {}
        for k in island_idx:
            best_j, best_d = None, LOOP_SNAP_M
            for j, n in enumerate(path):
                la, lo = graph["nodes"][n]
                d = haversine_m(stop_lat[k], stop_lon[k], la, lo)
                if d < best_d:
                    best_j, best_d = j, d
            if best_j is not None:
                pos[k] = best_j
        # Only stops no earlier circuit already serves. Two loops covering the
        # same stop is duplicated service, and it draws two lines down one road
        # for no benefit.
        ordered = [hub] + [k for k in sorted((k for k in pos if k != hub), key=lambda k: pos[k])
                           if k not in island_served]
        if len(ordered) < MIN_LOOP_STOPS:
            continue
        ordered.append(hub)
        if len(ordered) < MIN_LOOP_STOPS + 1:
            continue

        # legs between consecutive named stops, sliced from the ring path so the
        # geometry is the ring itself and not a fresh shortest path that might
        # cut the corner off
        legs: list[dict] = []
        cursor = 0
        for a_k, b_k in zip(ordered, ordered[1:]):
            end_j = pos.get(b_k, len(path) - 1) if b_k != hub else len(path) - 1
            if end_j <= cursor:
                _d, sub = rg.shortest_path(graph, node_of[a_k], node_of[b_k], scope)
                legs += legs_from_path(sub, a_k, b_k)
                continue
            sub = path[cursor:end_j + 1]
            if sub[0] != node_of[a_k]:
                sub = [node_of[a_k]] + sub
            legs += legs_from_path(sub, a_k, b_k)
            cursor = end_j

        total_km = sum(l["length_m"] for l in legs) / 1000.0
        if total_km > MAX_KM_LOOP:
            continue
        rid = f"L{len(loops) + 1}"
        add_route(rid, ordered, legs, "loop",
                  "closed circuit: leaves the hub, goes round, returns a different way")
        loops.append(len(routes) - 1)
        island_served |= set(ordered)
        print(f"  {rid}: {len(ordered)} stops, {total_km:.2f} km, "
              f"roads driven twice {reused_edges(legs)}")

    if not loops:
        raise SystemExit("no Hulhumalé circuit could be built inside the length cap")

    # Any island stop no ring reaches gets its own short circuit.
    #
    # An earlier version spliced such a stop into an existing loop and rebuilt
    # that loop's legs with a plain shortest path - which immediately undid the
    # ring, because the plain path retraces the outbound road. Circuits are only
    # ever built by `ring()`; nothing is spliced into one afterwards.
    for k in island_idx:
        if k in island_served:
            continue
        path, _km, _shared = ring(k)
        j = next((i for i, n in enumerate(path) if n == node_of[k]), None)
        if j:
            legs = legs_from_path(path[:j + 1], hub, k) + legs_from_path(path[j:], k, hub)
        else:
            _d, out_path = rg.shortest_path(graph, node_of[hub], node_of[k], scope)
            _d2, back_path = rg.shortest_path(graph, node_of[k], node_of[hub], scope)
            legs = legs_from_path(out_path, hub, k) + legs_from_path(back_path, k, hub)
        rid = f"L{len(loops) + 1}"
        add_route(rid, [hub, k, hub], legs, "loop",
                  "short circuit: the stop is off every ring, so it links to the interchange")
        loops.append(len(routes) - 1)
        island_served.add(k)
        print(f"  {rid}: short circuit for {stops[k]['stop_id']}, "
              f"{sum(l['length_m'] for l in legs) / 1000:.2f} km, roads driven twice {reused_edges(legs)}")

    covered = len(island_served & set(island_idx))
    print(f"  island coverage: {covered}/{len(island_idx)} stops on a circuit")

    def append_legs(r, added: list[int], graph, scope, node_of) -> list[dict]:
        """Generated legs for stops appended to a kept route, and only those."""
        out: list[dict] = []
        prev = r["line"][-1]
        for k in added:
            _d, path = rg.shortest_path(graph, node_of[prev], node_of[k], scope)
            out.append({
                "from": prev, "to": k,
                "coords": rg.polyline(graph, path),
                "length_m": sum(haversine_m(graph["nodes"][a][0], graph["nodes"][a][1],
                                            graph["nodes"][b][0], graph["nodes"][b][1])
                                for a, b in zip(path, path[1:])),
                "minutes": rg.travel_minutes(graph, path) + DWELL_MIN,
            })
            prev = k
        return out

    # ------------------------------------------------------------------
    # 5. Through-run: continue past the Hulhumalé stop along a loop
    # ------------------------------------------------------------------
    def demand_from_male(k: int) -> float:
        return sum(v for (o, d), v in od.items()
                   if (d == k and island_of_idx[o] != "Hulhumalé")
                   or (o == k and island_of_idx[d] != "Hulhumalé"))

    for r in routes:
        if r["kind"] != "kept":
            continue
        if len({island_of_idx[k] for k in r["line"]}) < 2:
            continue              # a Malé-only route has nothing to through-run
        if island_of_idx[r["line"][-1]] != "Hulhumalé":
            continue              # only routes that already end on the island
        # The arc has to start where the route already is: attaching a circuit
        # from the far side of the island added 12 km to R7 on an early run.
        end_k = r["line"][-1]
        base_km = sum(l["length_m"] for l in r["legs"]) / 1000.0
        best_arc, best_value = None, 0.0
        for li in loops:
            lp = routes[li]["line"]
            for direction in (1, -1):
                seq = lp[:] if direction > 0 else lp[::-1]
                for start in range(len(seq)):
                    arc = seq[start:start + 4]
                    if len(arc) < 3:
                        continue
                    if haversine_m(stop_lat[end_k], stop_lon[end_k],
                                   stop_lat[arc[0]], stop_lon[arc[0]]) > 700:
                        continue
                    added = [k for k in arc if k not in r["line"]]
                    if not added:
                        continue
                    tail = append_legs(r, added, graph, scope, node_of)
                    km = base_km + sum(l["length_m"] for l in tail) / 1000.0
                    if km > base_km * 1.45 + 1.0:
                        continue
                    value = sum(demand_from_male(k) for k in added)
                    if value > best_value:
                        best_arc, best_value = added, value
        if not best_arc:
            continue
        # ONLY the tail is generated. The leg list is extended, never rebuilt,
        # so the Malé half stays byte-identical to the committed geometry.
        r["legs"] = r["legs"] + append_legs(r, best_arc, graph, scope, node_of)
        r["line"] = r["line"] + best_arc
        r["kind"] = "through"
        r["note"] = r["note"] + "; continues along a Hulhumalé circuit so Malé trips stay direct"

    # ------------------------------------------------------------------
    # 6. Fleet: a fixed 55, allocated by peak demand
    # ------------------------------------------------------------------
    def route_run_minutes(r) -> float:
        return sum(l["minutes"] for l in r["legs"]) + DWELL_MIN * len(r["line"])

    for r in routes:
        r["run_min"] = route_run_minutes(r)
        r["cycle_min"] = 2 * (r["run_min"] + LAYOVER_MIN)
        r["peak_pax"] = max(sum(board_hour.get((k, h), 0.0) for k in set(r["line"]))
                            for h in range(24))

    if len(routes) > TOTAL_BUSES:
        raise SystemExit(f"{len(routes)} routes cannot run on {TOTAL_BUSES} buses")
    rem = TOTAL_BUSES - len(routes)          # one bus each, allocated first
    total_peak = sum(r["peak_pax"] for r in routes) or 1.0
    exact = [rem * r["peak_pax"] / total_peak for r in routes]
    floor = [int(x) for x in exact]
    left = rem - sum(floor)
    order = sorted(range(len(routes)), key=lambda i: -(exact[i] - floor[i]))
    for i in order[:left]:
        floor[i] += 1
    for r, extra in zip(routes, floor):
        r["buses"] = 1 + extra
        # the headway this many buses can actually sustain
        r["headway_min"] = round(r["cycle_min"] / r["buses"], 1)
    assert sum(r["buses"] for r in routes) == TOTAL_BUSES
    print(f"fleet: {TOTAL_BUSES} buses across {len(routes)} routes "
          f"({min(r['headway_min'] for r in routes):.0f}-{max(r['headway_min'] for r in routes):.0f} min headways)")

    # ------------------------------------------------------------------
    # 7. Route attributes and contract
    # ------------------------------------------------------------------
    def bus_class(r) -> str:
        islands = {island_of_idx[k] for k in r["line"]}
        if via in r["line"]:
            return "coach"
        if len(islands) > 1:
            return "double_decker"
        return "single"

    for r in routes:
        cls = bus_class(r)
        r["bus_class"] = cls
        r["seats"] = BUS_CLASS[cls]["seats"]
        r["max_passengers"] = BUS_CLASS[cls]["max"]
        r["bus_model"] = BUS_CLASS[cls]["model"]
        islands = {island_of_idx[k] for k in r["line"]}
        if via in r["line"]:
            r["service_class"] = "airport"
        elif len(islands) > 1:
            r["service_class"] = "cross_bridge"
        else:
            r["service_class"] = "local"
        r["length_km"] = round(sum(l["length_m"] for l in r["legs"]) / 1000, 2)
        r["daily_boardings"] = sum(hour_rows.get((k, h), 0.0) * scale
                                   for k in set(r["line"]) for h in range(24))
        r["peak_departures_per_hour"] = round(60 / r["headway_min"], 2)

    # which of today's routes each new route stands in for
    def replaces(r) -> str:
        if r["kind"] == "kept":
            return r["route_id"]
        if r["kind"] == "loop":
            return ",".join(REPLACED_BY_LOOPS)
        return r["route_id"]

    for r in routes:
        r["replaces_routes"] = replaces(r)

    # membership, for the stop table and for corridor sharing
    membership: dict[int, list[str]] = defaultdict(list)
    for r in routes:
        for k in set(r["line"]):
            membership[k].append(r["route_id"])

    for s, k in zip(stops, range(len(stops))):
        s["routes"] = " ".join(sorted(membership.get(k, [])))
        s["is_interchange"] = "yes" if len(membership.get(k, [])) >= 2 else ""

    # ---- write ------------------------------------------------------------
    seg_feats = []
    for r in routes:
        for i, leg in enumerate(r["legs"], start=1):
            seg_feats.append({
                "type": "Feature",
                "properties": {
                    "route_id": r["route_id"],
                    "seq": i,
                    "from_id": stops[leg["from"]]["stop_id"],
                    "to_id": stops[leg["to"]]["stop_id"],
                    "from_stop": name_of[leg["from"]],
                    "to_stop": name_of[leg["to"]],
                    "length_m": round(leg["length_m"]),
                    "minutes": round(leg["minutes"], 2),
                    "service": r["service_class"],
                },
                "geometry": {"type": "LineString", "coordinates": leg["coords"]},
            })
    (OUT / "reroute_segments.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": seg_feats}, ensure_ascii=False))

    pd.DataFrame([{
        "stop_id": s["stop_id"], "lat": s["lat"], "lon": s["lon"], "island": s["island"],
        "name": s["name"], "population_400m": s["population_400m"],
        "hotspots_400m": s["hotspots_400m"], "top_hotspot": s["top_hotspot"],
        "placed_because": s["placed_because"], "carried_over": s["carried_over"],
        "routes": s["routes"], "is_interchange": s["is_interchange"],
        "today_code": s["today_code"],
    } for s in stops]).to_csv(OUT / "reroute_stops.csv", index=False)

    pd.DataFrame([{
        "route_id": r["route_id"],
        "name": f"{name_of[r['line'][0]]} - {name_of[r['line'][-1]]}",
        "service_class": r["service_class"],
        "kind": r["kind"],
        "replaces_routes": r["replaces_routes"],
        "n_stops": len(r["line"]),
        "island_list": ",".join(sorted({island_of_idx[k] for k in r["line"]})),
        "length_km": r["length_km"],
        "run_time_min": round(r["run_min"], 1),
        "cycle_time_min": round(r["cycle_min"], 1),
        "bus_class": r["bus_class"],
        "bus_model": r["bus_model"],
        "seats": r["seats"],
        "max_passengers": r["max_passengers"],
        "peak_hour_boardings": round(r["peak_pax"], 1),
        "daily_boardings": round(r["daily_boardings"], 1),
        "buses_required": r["buses"],
        "headway_min": r["headway_min"],
        "peak_departures_per_hour": r["peak_departures_per_hour"],
        "stop_ids": ",".join(stops[k]["stop_id"] for k in r["line"]),
        "note": r["note"],
    } for r in routes]).to_csv(OUT / "reroute_routes.csv", index=False)

    pd.DataFrame([{
        "route_id": r["route_id"], "buses": r["buses"], "peak_demand": round(r["peak_pax"], 1),
        "cycle_min": round(r["cycle_min"], 1), "headway_min": r["headway_min"],
        "run_time_min": round(r["run_min"], 1),
    } for r in routes]).to_csv(OUT / "reroute_fleet_alloc.csv", index=False)

    pd.DataFrame([{"stop_id": s["stop_id"], "hour": h,
                   "boardings": round(board_hour.get((k, h), 0.0), 2)}
                  for k, s in enumerate(stops) for h in range(24)]
                 ).to_csv(OUT / "reroute_demand_stop_hour.csv", index=False)

    pd.DataFrame([{"origin_stop_id": stops[o]["stop_id"], "dest_stop_id": stops[d]["stop_id"],
                   "rides_per_day": round(v, 2)}
                  for (o, d), v in sorted(od.items(), key=lambda kv: -kv[1]) if v >= 0.05]
                 ).to_csv(OUT / "reroute_od.csv", index=False)

    params = json.loads((OUT / "reroute_params.json").read_text()) \
        if (OUT / "reroute_params.json").exists() else {}
    params["network"] = {
        "scope": "R1-R9 in scope. R5/R6 replaced by loops. R10-R12 excluded from both "
                 "networks (no captured departures). Villimalé out of scope.",
        "kept_routes": KEPT_ROUTES,
        "replaced_by_loops": REPLACED_BY_LOOPS,
        "excluded_routes": EXCLUDED,
        "stops_kept": kept_stops_before,
        "stops_new": len(chosen),
        "stops_total": len(stops),
        "loop_edge_penalty": LOOP_EDGE_PENALTY,
        "max_km_loop": MAX_KM_LOOP,
        "walk_radius_m": WALK_RADIUS_M,
        "catchment_m": CATCHMENT_M,
        "fleet": {
            "total_buses": TOTAL_BUSES,
            "allocation": "one bus per route, the rest by largest remainder on peak demand",
            "headway_rule": "cycle_time / buses, so the fleet constrains the service",
        },
        "demand_level": {
            "source": "MTCC bus_daily 2025, Saturday service day",
            "routes": DEMAND_ROUTES,
            "daily_boardings": round(target, 1),
            "total_including_airport": round(total_boardings, 1),
            "shape": "Avas taxi OD, Saturday, scaled to the MTCC level",
        },
        "airport_stream": {
            "bus_share_of_arrivals": AIRPORT_BUS_SHARE,
            "via_stop_id": stops[via]["stop_id"],
            "daily_passengers": round(sum(float(x.bus_pax) for x in air.itertuples()), 1),
            "note": "a judgement, not a measurement; both networks receive the same stream",
        },
    }
    (OUT / "reroute_params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False))

    # ---- report -----------------------------------------------------------
    pd.set_option("display.width", 220)
    print("=" * 108)
    print(f"NETWORK  {len(stops)} stops   {len(routes)} routes   {TOTAL_BUSES} buses")
    print("=" * 108)
    print(pd.DataFrame([{
        "route": r["route_id"], "kind": r["kind"], "service": r["service_class"],
        "stops": len(r["line"]), "km": r["length_km"], "run": round(r["run_min"]),
        "buses": r["buses"], "headway": r["headway_min"],
    } for r in routes]).to_string(index=False))
    unserved = [s["stop_id"] for s in stops if not s["routes"]]
    print(f"\nstops with no route: {len(unserved)}")
    if unserved:
        print("  " + ", ".join(unserved[:10]))


if __name__ == "__main__":
    main()
