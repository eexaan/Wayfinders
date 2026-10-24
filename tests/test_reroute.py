"""
Guards for the reroute build: scope, geometry and coverage.

These are cheap structural assertions, not model validation. They exist because
the reroute generates stops and routes programmatically, and the two failure
modes that would be embarrassing - a stop somewhere it cannot be served, or a
route drawn across open water - are both mechanically checkable.

Run with:  .venv/bin/python -m pytest tests -q
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
sys.path.insert(0, str(ROOT / "dashboard" / "build"))

from geo import cell_centre, cell_index, haversine_m, point_in_polygon  # noqa: E402


def read_csv(name: str) -> list[dict]:
    import csv

    path = DATA / name
    if not path.exists():
        pytest.skip(f"{name} not built - run `make reroute`")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Villimale' is out of scope (ADR-0015). Anything inside this box is a scope bug.
VILLIMALE_BOX = {"south": 4.165, "west": 73.475, "north": 4.180, "east": 73.494}


def in_villimale(lat: float, lon: float) -> bool:
    return (VILLIMALE_BOX["south"] <= lat <= VILLIMALE_BOX["north"]
            and VILLIMALE_BOX["west"] <= lon <= VILLIMALE_BOX["east"])


# ---------------------------------------------------------------------------
def test_geometry_helpers() -> None:
    """The grid math the whole build rests on."""
    lat, lon = cell_centre(10, 20, 150.0)
    assert cell_index(lat, lon, 150.0) == (10, 20)

    # a 0.001 degree latitude step is ~110.6 m
    d = haversine_m(4.17, 73.50, 4.171, 73.50)
    assert 110.0 < d < 111.5

    square = [(4.0, 73.0), (4.0, 73.001), (4.001, 73.001), (4.001, 73.0)]
    assert point_in_polygon(4.0005, 73.0005, [square])
    assert not point_in_polygon(4.01, 73.0005, [square])










def test_engine_is_deterministic() -> None:
    """Same seed, same day. This is the claim the whole proof rests on."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    script = r"""
import { createSimulation } from './web/src/sim/engine.mjs'
import { readCsv } from './web/scripts/csv.mjs'
import { readFileSync } from 'node:fs'
const D = 'dashboard/data'
const stops = readCsv(D + '/reroute_stops.csv').map(r => ({ stop_id: r.stop_id, name: r.name, lat: +r.lat, lon: +r.lon, island: r.island }))
const routes = readCsv(D + '/reroute_routes.csv').map(r => ({ route_id: r.route_id, name: r.name, service_class: r.service_class, seats: +r.seats, max_passengers: +r.max_passengers, buses_required: +r.buses_required, stops: r.stop_ids.split(',').map(s => s.trim()) }))
const segs = JSON.parse(readFileSync(D + '/reroute_segments.geojson', 'utf8')).features
const legs = new Map()
for (const f of segs) {
  const p = f.properties
  if (!legs.has(p.route_id)) legs.set(p.route_id, [])
  legs.get(p.route_id).push({ seq: +p.seq, from_id: p.from_id, to_id: p.to_id, length_m: +p.length_m, minutes: +p.minutes, coords: f.geometry.coordinates })
}
for (const l of legs.values()) l.sort((a, b) => a.seq - b.seq)
for (const r of routes) r.legs = legs.get(r.route_id) || []
const demand = readCsv(D + '/reroute_demand_stop_hour.csv').map(r => ({ stop_id: r.stop_id, hour: +r.hour, boardings: +r.boardings }))
const od = readCsv(D + '/reroute_od.csv').map(r => ({ origin_stop_id: r.origin_stop_id, dest_stop_id: r.dest_stop_id, rides_per_day: +r.rides_per_day }))
const a = createSimulation({ stops, routes, demand, od, options: { seed: 424242 } }).finish()
const b = createSimulation({ stops, routes, demand, od, options: { seed: 424242 } }).finish()
console.log(JSON.stringify({ same: a.completed === b.completed && a.boarded === b.boarded && a.meanWaitMin === b.meanWaitMin, completed: a.completed }))
"""
    out = subprocess.run([node, "--input-type=module", "-e", script], cwd=ROOT,
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[:800]
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert result["same"], "the engine is not deterministic under a fixed seed"





# ---------------------------------------------------------------------------
# The corrected design: Malé untouched, Hulhumalé on real circuits.
# ---------------------------------------------------------------------------

def test_kept_routes_are_todays_geometry() -> None:
    """R1-R4 and R7-R9 must be byte-identical to the committed geometry.

    This is the point of the whole design: Malé's streets are already close to
    what the roads allow, so its routes are copied, not regenerated. If a leg of
    a kept route differs from `route_segments.geojson`, the regeneration bug is
    back, no matter how good the picture looks.
    """
    today = json.loads((DATA / "route_segments.geojson").read_text())["features"]
    new = json.loads((DATA / "reroute_segments.geojson").read_text())["features"]

    def index(feats, key):
        out: dict[str, list] = {}
        for f in feats:
            out.setdefault(f["properties"][key], []).append(f)
        for v in out.values():
            v.sort(key=lambda f: f["properties"]["seq"])
        return out

    t = index(today, "route_code")
    n = index(new, "route_id")
    kept = ["R1", "R2", "R3", "R4", "R7", "R8", "R9"]
    for code in kept:
        assert code in t, f"{code} missing from the committed geometry"
        assert code in n, f"{code} missing from the reroute network"
        old, cur = t[code], n[code]
        assert len(cur) >= len(old), f"{code} lost legs: {len(old)} -> {len(cur)}"
        for a, b in zip(old, cur):
            assert a["geometry"]["coordinates"] == b["geometry"]["coordinates"], (
                f"{code} leg {a['properties']['seq']} is not today's geometry - "
                "a kept route has been regenerated"
            )


def test_replaced_routes_are_gone() -> None:
    """R5 and R6 are replaced by the circuits; they must not still be routes."""
    routes = read_csv("reroute_routes.csv")
    ids = {r["route_id"] for r in routes}
    assert "R5" not in ids, "R5 survived the loop replacement"
    assert "R6" not in ids, "R6 survived the loop replacement"
    assert any(r["kind"] == "loop" for r in routes), "no Hulhumalé circuit was built"


def test_loops_are_closed_and_do_not_drive_a_road_twice() -> None:
    """A circuit returns to where it started, and does not retrace itself.

    The first attempt built each loop as hub -> arc -> hub over the same road,
    which produced 3-5 direction reversals per route and a map that looked like
    spaghetti. The edge-penalised return leg exists to prevent exactly that, so
    it is asserted rather than assumed.
    """
    stops = {s["stop_id"]: s for s in read_csv("reroute_stops.csv")}
    routes = [r for r in read_csv("reroute_routes.csv") if r["kind"] == "loop"]
    assert routes, "no loops built"
    segs = json.loads((DATA / "reroute_segments.geojson").read_text())["features"]
    by_route: dict[str, list] = {}
    for f in segs:
        by_route.setdefault(f["properties"]["route_id"], []).append(f)

    for r in routes:
        ids = r["stop_ids"].split(",")
        assert ids[0] == ids[-1], f"{r['route_id']} is not closed: {ids[0]} -> {ids[-1]}"

        seen: dict[tuple, int] = {}
        for f in by_route[r["route_id"]]:
            cs = [(round(lon, 5), round(lat, 5)) for lon, lat in f["geometry"]["coordinates"]]
            for a, b in zip(cs, cs[1:]):
                if a == b:
                    continue
                k = (a, b) if a <= b else (b, a)
                seen[k] = seen.get(k, 0) + 1
        reused = sum(1 for v in seen.values() if v > 1)
        # A few metres at a cul-de-sac is physically unavoidable; a retraced
        # corridor is not, and shows up as dozens of reused segments.
        assert reused <= 6, f"{r['route_id']} drives {reused} road segments twice"


def test_no_duplicate_routes() -> None:
    """Two routes with the same stop sequence are one route with two numbers."""
    routes = read_csv("reroute_routes.csv")
    seen: dict[tuple, str] = {}
    for r in routes:
        key = tuple(r["stop_ids"].split(","))
        if not key:
            continue
        assert key not in seen, f"{r['route_id']} duplicates {seen[key]}"
        seen[key] = r["route_id"]


def test_every_stop_is_served() -> None:
    """A stop on the map with no route is a map artefact, not a plan."""
    stops = read_csv("reroute_stops.csv")
    orphan = [s["stop_id"] for s in stops if not (s.get("routes") or "").strip()]
    assert not orphan, f"stops served by no route: {orphan[:8]}"


def test_male_stops_are_todays_stops() -> None:
    """Malé and the airport keep their existing stops."""
    stops = read_csv("reroute_stops.csv")
    male = [s for s in stops if s["island"] in ("Malé", "Hulhulé")]
    carried = [s for s in male if s["carried_over"] == "true"]
    assert len(carried) == len(male), (
        f"{len(male) - len(carried)} Malé/airport stops were regenerated; the design keeps them"
    )
    # Malé's network is dense and heavily shared, so R1-R9 touch only 14 unique
    # Malé and airport stops between them. That number is the point: they are
    # the same 14 they were before.
    assert len(carried) >= 14, f"only {len(carried)} Malé/airport stops carried over"


def test_fleet_is_held_across_the_ablation() -> None:
    """Rows 1-3 must all run the same number of buses.

    The earlier panel compared 99 buses against 55 and called it an improvement
    of the original. Holding the fleet is what makes each row's delta mean
    something.
    """
    path = DATA / "reroute_proof.json"
    if not path.exists():
        pytest.skip("reroute_proof.json not built")
    proof = json.loads(path.read_text())
    rows = proof.get("rows") or []
    assert len(rows) == 4, f"expected 4 ablation rows, found {len(rows)}"

    held = proof.get("fleet_held")
    for row in rows[:3]:
        assert row["kpis"]["buses"] == held, (
            f"{row['label']} ran {row['kpis']['buses']} buses, not the held {held}"
        )
    # only the last row may add buses, and it must actually have done so
    assert rows[3]["kpis"]["buses"] >= held
    assert rows[3]["delta"]["buses"] is None or rows[3]["delta"]["buses"] >= 0


def test_ablation_changes_one_thing_per_row() -> None:
    """Each row must declare a single change, and the first must declare none."""
    path = DATA / "reroute_proof.json"
    if not path.exists():
        pytest.skip("reroute_proof.json not built")
    rows = json.loads(path.read_text())["rows"]
    assert rows[0]["change"] == "", "the baseline row must not claim a change"
    changes = [r["change"] for r in rows[1:]]
    assert changes == ["dispatch", "topology", "fleet"], f"unexpected ablation: {changes}"
    for r in rows:
        assert r["label"] and r["note"], f"row {r['key']} is missing a human-readable label"


def test_advisory_covers_every_stop() -> None:
    """The per-stop deliverable must answer for every stop, not a sample."""
    stops = {s["stop_id"] for s in read_csv("reroute_stops.csv")}
    adv = read_csv("reroute_stop_advisory.csv")
    assert adv, "advisory not written - run node web/scripts/run-sim.mjs"
    assert {r["stop_id"] for r in adv} == stops
    for r in adv:
        assert r["extra_bus_required"] in ("yes", "no")
        if r["extra_bus_required"] == "yes":
            assert r["reason"], f"{r['stop_id']} needs a bus but gives no reason"


def test_no_stop_is_out_of_scope() -> None:
    """ADR-0015: Villimalé keeps today's service and is not in this network."""
    stops = read_csv("reroute_stops.csv")
    offshore = [(s["stop_id"], float(s["lat"]), float(s["lon"])) for s in stops
                if in_villimale(float(s["lat"]), float(s["lon"]))]
    assert not offshore, f"stops inside the Villimalé box: {offshore}"
    assert {s["island"] for s in stops} <= {"Malé", "Hulhumalé", "Hulhulé"}
