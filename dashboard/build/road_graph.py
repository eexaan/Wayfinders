"""
================================================================================
The drivable network, offline
================================================================================
Maldives Datathon 2026 | Team Wayfinders

WHY THIS EXISTS
    A generated bus route must never be a straight line between two stops. The
    committed `basemap.geojson` already contains every OSM road in the study
    area (828 ways, 4,261 edges), so the reroute can route over real roads with
    no network call, no OSRM, and no chance of drawing a line across open water.

    This module is the only thing that reads that geometry. `build_reroute_
    network.py` and the browser's leg timings both derive from it.

WHAT IT GIVES YOU
    load_graph()        undirected road graph: node -> [(neighbour, metres)]
    nearest_node()      snap a latitude/longitude onto the graph
    shortest_path()     Dijkstra, cached, returns (metres, [node, ...])
    in_scope_nodes()    the single component that contains Malé, the airport
                        island and Hulhumalé

    The graph has four disconnected pieces. Three are islets (Villimalé, a
    resort island west of Hulhumalé, a small one off Villimalé); only the
    largest contains the bridge. `in_scope_nodes()` is what enforces scope
    (ADR-0015): a stop can only be placed on a node in that component, so
    Villimalé cannot enter the network by accident.

Run this file directly for the diagnostics `make reroute` prints:

    .venv/bin/python dashboard/build/road_graph.py
"""

from __future__ import annotations

import heapq
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from geo import haversine_m  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASEMAP = ROOT / "dashboard" / "data" / "basemap.geojson"

# ~1.1 m. Coarse enough that two ways sharing an endpoint really do join (OSM
# writes the same coordinate on both), fine enough not to merge parallel streets.
NODE_DP = 5

# Cruise speeds, km/h, from the scheduled stop-to-stop times in
# bridge_segment_analysis.csv: the median implied speed across 116 observed legs
# is 13 km/h including dwell, and the bridge legs run at ~18-20 km/h. Minor
# Malé streets are narrow and congested; the bridge and the airport road are not.
SPEED_KMH = {"major": 20.0, "minor": 14.0}
DWELL_MIN = 0.4  # per stop, applied by the simulation, not here


def _key(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, NODE_DP), round(lon, NODE_DP)


def load_graph(path: pathlib.Path | None = None) -> dict:
    """Build the undirected graph from the committed basemap."""
    base = json.loads((path or BASEMAP).read_text())
    nodes: dict[tuple[float, float], tuple[float, float]] = {}
    adj: dict[tuple, list] = defaultdict(list)
    edges: list[dict] = []

    for f in base["features"]:
        if f["properties"].get("kind") != "road":
            continue
        cls = f["properties"].get("class", "minor")
        coords = f["geometry"]["coordinates"]
        if len(coords) < 2:
            continue
        ids = [_key(lat, lon) for lon, lat in coords]
        for i, (lon, lat) in zip(ids, coords):
            nodes[i] = (lat, lon)
        for a, b in zip(ids, ids[1:]):
            if a == b:
                continue
            d = haversine_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
            adj[a].append((b, d, cls))
            adj[b].append((a, d, cls))
            edges.append({"a": a, "b": b, "m": d, "class": cls})

    return {"nodes": nodes, "adj": adj, "edges": edges}


def components(graph: dict) -> dict[tuple, int]:
    """Connected-component id per node, labelled by the component's seed."""
    comp: dict[tuple, int] = {}
    cid = 0
    for start in graph["nodes"]:
        if start in comp:
            continue
        cid += 1
        comp[start] = cid
        stack = [start]
        while stack:
            u = stack.pop()
            for v, _d, _c in graph["adj"][u]:
                if v not in comp:
                    comp[v] = cid
                    stack.append(v)
    return comp


def _buckets(graph: dict) -> dict[tuple[int, int], list[tuple]]:
    """A ~550 m lat/lon bucket index, built once per graph.

    `nearest_node` is called thousands of times while the network is generated
    (once per candidate, per extension, per stop re-snap). Scanning 3,594 nodes
    each time is the difference between a 2 s build and a 40 s one.
    """
    if "_buckets" not in graph:
        idx: dict[tuple[int, int], list[tuple]] = defaultdict(list)
        for nid, (lat, lon) in graph["nodes"].items():
            idx[(int(lat // 0.005), int(lon // 0.005))].append(nid)
        graph["_buckets"] = idx
    return graph["_buckets"]


def densify(graph: dict, step_m: float = 70.0) -> dict:
    """Split every road edge into <= `step_m` pieces.

    The basemap stores one feature per OSM way, so its nodes sit only at way
    endpoints and junctions - 3,594 of them over the whole study area, far
    coarser than the 150 m grid the population surface uses. A stop must be
    able to go *anywhere along a road*, not only at a junction, so the network
    builder walks this densified copy. Routing results are unchanged; only the
    set of legal stop positions grows.
    """
    nodes = dict(graph["nodes"])
    adj: dict[tuple, list] = defaultdict(list)

    def link(a, b, cls):
        d = haversine_m(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
        adj[a].append((b, d, cls))
        adj[b].append((a, d, cls))

    for e in graph["edges"]:
        a, b, cls = e["a"], e["b"], e["class"]
        (lat1, lon1), (lat2, lon2) = graph["nodes"][a], graph["nodes"][b]
        pieces = max(1, int(e["m"] // step_m))
        prev = a
        for k in range(1, pieces):
            f = k / pieces
            nid = _key(lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f)
            nodes[nid] = nid
            link(prev, nid, cls)
            prev = nid
        link(prev, b, cls)

    return {"nodes": nodes, "adj": adj, "edges": graph["edges"]}


def nearest_node(graph: dict, lat: float, lon: float, allowed: set | None = None) -> tuple:
    """Closest graph node to a coordinate, optionally restricted to a subset."""
    idx = _buckets(graph)
    brow, bcol = int(lat // 0.005), int(lon // 0.005)
    best, best_d = None, float("inf")
    # Expand square rings until a hit is closer than everything still unscanned.
    for ring in range(0, 40):
        for r in range(brow - ring, brow + ring + 1):
            for c in range(bcol - ring, bcol + ring + 1):
                if ring and abs(r - brow) != ring and abs(c - bcol) != ring:
                    continue  # only the ring's edge; the inside was scanned
                for nid in idx.get((r, c), ()):
                    if allowed is not None and nid not in allowed:
                        continue
                    nlat, nlon = graph["nodes"][nid]
                    d = haversine_m(lat, lon, nlat, nlon)
                    if d < best_d:
                        best, best_d = nid, d
        # a ring is 0.005 deg ~ 550 m; stop once the hit is inside the scanned square
        if best is not None and best_d <= ring * 550.0:
            break
    if best is None:
        raise ValueError("no node available")
    return best


def main_component(graph: dict) -> set:
    """Nodes of the component that contains Malé, the airport and Hulhumalé.

    Anchored on three points rather than assumed: if the bridge ever disappears
    from the basemap, this raises instead of silently returning Malé only.
    """
    comp = components(graph)
    anchors = [(4.1747, 73.5075), (4.1915, 73.5245), (4.2265, 73.5410)]  # Malé, VIA, Hulhumalé
    ids = [comp[nearest_node(graph, la, lo)] for la, lo in anchors]
    if len(set(ids)) != 1:
        raise SystemExit(
            "the road graph is split: Malé, the airport island and Hulhumalé are not "
            f"connected (component ids {ids}). Rebuild basemap.geojson with the bridge ways."
        )
    cid = ids[0]
    return {n for n, c in comp.items() if c == cid}


def edge_key(a: tuple, b: tuple) -> tuple:
    """Direction-free identity for a road segment, so a path there and back
    counts as the same piece of road."""
    return (a, b) if a <= b else (b, a)


def path_edges(path: list) -> list[tuple]:
    """The road segments a node path traverses."""
    return [edge_key(a, b) for a, b in zip(path, path[1:])]


def shortest_path(
    graph: dict,
    a: tuple,
    b: tuple,
    allowed: set | None = None,
    avoid: set | None = None,
    penalty: float = 1.0,
) -> tuple[float, list]:
    """Dijkstra over road length. Returns (metres, node list). Cached by caller.

    `avoid` is a set of `edge_key`s whose cost is multiplied by `penalty`. This
    is what makes a circuit possible: routing the return leg with the outbound
    edges penalised pushes the bus onto a different street instead of driving
    the same road back the way it came. The returned distance is the true
    length, not the penalised cost.
    """
    dist: dict[tuple, float] = {a: 0.0}
    real: dict[tuple, float] = {a: 0.0}
    prev: dict[tuple, tuple] = {}
    pq = [(0.0, a)]
    seen = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        if u == b:
            break
        for v, w, _cls in graph["adj"][u]:
            if allowed is not None and v not in allowed:
                continue
            cost = w * penalty if (avoid and edge_key(u, v) in avoid) else w
            nd = d + cost
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                real[v] = real[u] + w
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if b not in dist:
        raise ValueError("no road path between the two nodes")
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    path.reverse()
    return real[b], path


def polyline(graph: dict, path: list) -> list[list[float]]:
    """GeoJSON coordinates ([lon, lat]) for a node path, rounded for the bundle."""
    return [[round(graph["nodes"][n][1], 6), round(graph["nodes"][n][0], 6)] for n in path]


def travel_minutes(graph: dict, path: list) -> float:
    """Scheduled-free running time over a node path, at the observed speeds."""
    total = 0.0
    for a, b in zip(path, path[1:]):
        cls = "minor"
        for v, _d, c in graph["adj"][a]:
            if v == b:
                cls = c
                break
        d = haversine_m(graph["nodes"][a][0], graph["nodes"][a][1], graph["nodes"][b][0], graph["nodes"][b][1])
        total += d / 1000 / SPEED_KMH.get(cls, SPEED_KMH["minor"]) * 60
    return total


if __name__ == "__main__":
    g = load_graph()
    comp = components(g)
    sizes = defaultdict(int)
    for c in comp.values():
        sizes[c] += 1
    print("=" * 96)
    print("ROAD GRAPH (from dashboard/data/basemap.geojson)")
    print("=" * 96)
    print(f"nodes {len(g['nodes']):,}   edges {len(g['edges']):,}   components {len(sizes)}")
    main_nodes = main_component(g)
    print(f"in-scope component: {len(main_nodes):,} nodes  (Malé + airport island + Hulhumalé)")
    for label, (la, lo) in [("Malé centre", (4.1747, 73.5075)), ("VIA terminal", (4.1915, 73.5245)),
                            ("Hulhumalé", (4.2265, 73.5410))]:
        print(f"  {label:<14} snaps to {nearest_node(g, la, lo)}")
    d, p = shortest_path(g, nearest_node(g, 4.1747, 73.5075), nearest_node(g, 4.2265, 73.5410), main_nodes)
    print(f"  Malé -> Hulhumalé: {d/1000:.2f} km by road, {travel_minutes(g, p):.1f} min")
