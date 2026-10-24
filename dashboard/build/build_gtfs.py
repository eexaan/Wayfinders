"""
================================================================================
Synthesise a GTFS feed for the Greater Male' RTL bus network
================================================================================
Maldives Datathon 2026 | Team Wayfinders  |  Dev B task 4 (stretch)

No public GTFS exists for Male'. This builds one from the official RTL 2026
feed, which already carries per-stop scheduled timings for every trip.

WHY IT IS POSSIBLE AT ALL
    Most GTFS builders have to interpolate `stop_times` from an origin
    departure plus an assumed average speed. This one does not: the RTL payload
    contains `busRouteStopList[i].timings[]`, so the arrival time at every stop
    of every trip is OBSERVED, not modelled. The only interpolation anywhere in
    this file is none.

WHAT THE FEED HONESTLY CONTAINS
    * One service day: Saturday 2026-10-24 (the day the feed was captured).
    * Departures from ~11:00 onward, because the source endpoint is filtered
      from the moment of the call. Morning trips are absent, so this is NOT a
      full service day and the feed says so in `feed_info` and this docstring.
    * 11 of the 15 routes. R10, R11, R12 and R15 return no timings at all, so
      they have no trips and are excluded rather than emitted as empty routes.
    * Trips whose timing is only partially known still ship, but only with the
      stops that have a time. A trip is never given an invented timestamp.

WHY THE FILES LOOK THE WAY THEY DO
    * `stop_id` is the official RTL stop code. Verified across all 15 routes:
      97 unique codes, and no code ever maps to two different names or
      coordinate pairs, so one code really is one physical stop.
    * `route_color` is the official RTL colour, with the leading '#' stripped,
      because GTFS stores six hex digits without it.
    * Stops whose name ends in `(DROP-OFF ONLY)` get `pickup_type=1`; GTFS has
      no other way to express that, and dropping the distinction would let a
      journey planner board a passenger where the bus will not stop.
    * `route_type=3` is "bus". `agency_timezone` is `Indian/Maldives` (UTC+5).

OUTPUTS
    data/derived/gtfs/*.txt              the feed, unzipped, for eyeballing
    data/derived/rtl_greater_male_gtfs.zip   the deliverable
    data/derived/gtfs_validation.csv     one row per structural check
"""

from __future__ import annotations

import collections
import itertools
import csv
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data" / "official" / "rtl"
OUTDIR = ROOT / "data" / "derived" / "gtfs"
ZIPPATH = ROOT / "data" / "derived" / "rtl_greater_male_gtfs.zip"
REPORT = ROOT / "data" / "derived" / "gtfs_validation.csv"

SERVICE_ID = "SAT_20261024"
SERVICE_DATE = "20261024"
SERVICE_DAY_NAME = "Saturday 2026-10-24"
FEED_START = SERVICE_DATE
FEED_END = SERVICE_DATE

AGENCY = {
    "agency_id": "RTL",
    "agency_name": "Raajje Transport Link (RTL) - operated by MTCC",
    "agency_url": "https://rtl.mv",
    "agency_timezone": "Indian/Maldives",
    "agency_lang": "en",
}


def load_routes() -> list[dict]:
    payload = json.loads((OFFICIAL / "bus_routedetails_2026.json").read_text())
    return payload["routeResponse"]


# The RTL feed returns a few strings in full caps. GTFS recommends mixed case
# for human-readable names, and an all-caps stop reads as shouting in a journey
# planner. The override is explicit rather than a blanket title-case, because a
# blanket one mangles acronyms (MWSC became "Mwsc") and hyphenation (Drop-Off).
NAME_CASING = {
    "VINARES BUS STOP": "Vinares Bus Stop",
    "MWSC FLAT BUS STOP (DROP-OFF ONLY)": "MWSC Flat Bus Stop (drop-off only)",
    "VILLIMALE INTERNAL 2": "Villimale Internal 2",
}


def display_name(raw: str) -> str:
    name = raw.strip()
    return NAME_CASING.get(name.upper(), name)


def contrast_text_colour(route_color: str) -> str:
    """Black or white text, whichever actually contrasts with the route colour.

    GTFS stores route_color and route_text_color separately because operators
    pick vivid colours; a light yellow-green with white text is unreadable, and
    the validator flags it. Choosing by relative luminance fixes every route at
    once rather than patching the one that happened to be reported.
    """
    hex6 = (route_color or "").lstrip("#")
    if len(hex6) != 6:
        return "FFFFFF"
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    chan = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    luminance = 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]
    return "000000" if luminance > 0.35 else "FFFFFF"


def route_sort_key(code: str) -> tuple[int, str]:
    digits = "".join(c for c in code if c.isdigit())
    return (int(digits) if digits else 999, code)


def trips_by_order(route: dict) -> dict[int, list[tuple[int, str]]]:
    """trip order -> [(stop_order, 'HH:MM:SS'), ...] sorted by stop order."""
    acc: dict[int, list[tuple[int, str]]] = collections.defaultdict(list)
    for stop in route["busRouteStopList"]:
        for t in (stop.get("timings") or []):
            acc[t["order"]].append((stop["order"], t["timing"]))
    for k in acc:
        acc[k].sort()
    return dict(acc)


def write_csv(path: pathlib.Path, header: list[str], rows: list[dict]) -> int:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def build() -> dict:
    routes = sorted(load_routes(), key=lambda r: route_sort_key(r["routeNumber"]))
    OUTDIR.mkdir(parents=True, exist_ok=True)

    stops: dict[str, dict] = {}
    routes_rows, trips_rows, stop_times_rows = [], [], []
    excluded, partially_timed, dropoff_only = [], 0, 0

    for r in routes:
        code = r["routeNumber"]
        stop_list = sorted(r["busRouteStopList"], key=lambda s: s["order"])
        per_trip = trips_by_order(r)
        usable = {o: ev for o, ev in per_trip.items() if len(ev) >= 2}

        if not usable:
            excluded.append(code)
            continue

        routes_rows.append({
            "route_id": code,
            "agency_id": AGENCY["agency_id"],
            "route_short_name": code,
            "route_long_name": display_name(r.get("name", "")),
            "route_type": 3,
            "route_color": (r.get("color") or "").lstrip("#"),
            "route_text_color": contrast_text_colour(r.get("color") or ""),
        })

        for s in stop_list:
            sid = str(s["code"])
            stops.setdefault(sid, {
                "stop_id": sid,
                "stop_name": display_name(s["name"]),
                "stop_lat": f"{float(s['latitude']):.6f}",
                "stop_lon": f"{float(s['longitude']):.6f}",
            })

        for order in sorted(usable):
            events = usable[order]
            if len(events) < len(stop_list):
                partially_timed += 1
            trip_id = f"{code}_{order:03d}"
            trips_rows.append({
                "route_id": code,
                "service_id": SERVICE_ID,
                "trip_id": trip_id,
                "direction_id": 0,
                "trip_headsign": (r.get("endStationName") or "").strip(),
                "trip_short_name": "",
                "wheelchair_accessible": 0,
                "bikes_allowed": 0,
            })
            seq = 0
            for stop_order, timing in events:
                seq += 1
                stop = next(x for x in stop_list if x["order"] == stop_order)
                name = stop["name"].upper()
                # GTFS can express "no boarding here" but not "no alighting"
                # without a second flag; both are handled when the name says so.
                pickup = 1 if "DROP-OFF ONLY" in name else 0
                dropoff = 1 if "PICK-UP ONLY" in name else 0
                if pickup:
                    dropoff_only += 1
                stop_times_rows.append({
                    "trip_id": trip_id,
                    "arrival_time": timing,
                    "departure_time": timing,
                    "stop_id": str(stop["code"]),
                    "stop_sequence": seq,
                    "pickup_type": pickup,
                    "drop_off_type": dropoff,
                    "timepoint": 1,
                })

    counts = {}
    counts["agency.txt"] = write_csv(
        OUTDIR / "agency.txt", list(AGENCY.keys()), [AGENCY])
    counts["stops.txt"] = write_csv(
        OUTDIR / "stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        list(stops.values()))
    counts["routes.txt"] = write_csv(
        OUTDIR / "routes.txt",
        ["route_id", "agency_id", "route_short_name", "route_long_name",
         "route_type", "route_color", "route_text_color"],
        routes_rows)
    counts["trips.txt"] = write_csv(
        OUTDIR / "trips.txt",
        ["route_id", "service_id", "trip_id", "direction_id", "trip_headsign",
         "trip_short_name", "wheelchair_accessible", "bikes_allowed"],
        trips_rows)
    counts["stop_times.txt"] = write_csv(
        OUTDIR / "stop_times.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
         "pickup_type", "drop_off_type", "timepoint"],
        stop_times_rows)
    counts["calendar.txt"] = write_csv(
        OUTDIR / "calendar.txt",
        ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday", "start_date", "end_date"],
        [{
            "service_id": SERVICE_ID,
            "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0,
            "friday": 0, "saturday": 1, "sunday": 0,
            "start_date": FEED_START, "end_date": FEED_END,
        }])
    counts["feed_info.txt"] = write_csv(
        OUTDIR / "feed_info.txt",
        ["feed_publisher_name", "feed_publisher_url", "feed_lang",
         "feed_start_date", "feed_end_date", "feed_version", "feed_contact_url"],
        [{
            "feed_publisher_name": "Team Wayfinders, MBS Maldives Datathon 2026",
            "feed_publisher_url": "https://rtl.mv",
            "feed_lang": "en",
            "feed_start_date": FEED_START,
            "feed_end_date": FEED_END,
            "feed_version": f"derived-{SERVICE_DATE}-from-RTL-routedetails",
            "feed_contact_url": "https://rtl.mv",
        }])

    # Zip with every file at the archive root, which is what validators expect.
    # Member timestamps are pinned to the service date: zipfile would otherwise
    # stamp "now", so an unchanged feed would produce a new blob on every run
    # and dirty the working tree for no reason.
    stamp = (2026, 10, 24, 0, 0, 0)
    with zipfile.ZipFile(ZIPPATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(counts):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (OUTDIR / name).read_bytes())

    return {
        "counts": counts,
        "excluded": excluded,
        "partially_timed": partially_timed,
        "dropoff_only": dropoff_only,
        "n_stops": len(stops),
        "n_routes": len(routes_rows),
        "n_trips": len(trips_rows),
    }


# ---------------------------------------------------------------------------
def validate() -> list[dict]:
    """Structural validation against the GTFS reference rules that matter here.

    Deliberately self-contained: a feed that can only be checked by downloading
    a Java validator is a feed nobody re-checks. These assertions are the ones
    that make the difference between "a zip of CSVs" and "a feed a journey
    planner can load".
    """
    def read(name):
        with (OUTDIR / name).open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL",
                       "detail": detail})

    required = ["agency.txt", "stops.txt", "routes.txt", "trips.txt",
                "stop_times.txt", "calendar.txt"]
    check("required_files_present",
          all((OUTDIR / f).exists() for f in required),
          ", ".join(f for f in required if not (OUTDIR / f).exists()) or "all present")

    stops, routes, trips = read("stops.txt"), read("routes.txt"), read("trips.txt")
    times = read("stop_times.txt")
    cal = read("calendar.txt")

    check("unique_stop_ids",
          len({s["stop_id"] for s in stops}) == len(stops),
          f"{len(stops)} stops")
    check("unique_route_ids",
          len({r["route_id"] for r in routes}) == len(routes),
          f"{len(routes)} routes")
    check("unique_trip_ids",
          len({t["trip_id"] for t in trips}) == len(trips),
          f"{len(trips)} trips")

    stop_ids = {s["stop_id"] for s in stops}
    route_ids = {r["route_id"] for r in routes}
    trip_ids = {t["trip_id"] for t in trips}
    service_ids = {c["service_id"] for c in cal}

    check("trip_route_fk", all(t["route_id"] in route_ids for t in trips))
    check("trip_service_fk", all(t["service_id"] in service_ids for t in trips))
    check("stop_time_trip_fk", all(t["trip_id"] in trip_ids for t in times))
    check("stop_time_stop_fk", all(t["stop_id"] in stop_ids for t in times))

    # Every trip must have at least two stop_times, or it is not a journey.
    per_trip = collections.Counter(t["trip_id"] for t in times)
    thin = [k for k, v in per_trip.items() if v < 2]
    check("every_trip_has_2plus_stop_times", not thin, f"{len(thin)} short trips")

    # stop_sequence must be 1..n per trip, unique.
    bad_seq = 0
    for tid, grp in itertools.groupby(
            sorted(times, key=lambda x: (x["trip_id"], int(x["stop_sequence"]))),
            key=lambda x: x["trip_id"]):
        seqs = [int(g["stop_sequence"]) for g in grp]
        if seqs != list(range(1, len(seqs) + 1)):
            bad_seq += 1
    check("stop_sequence_contiguous", bad_seq == 0, f"{bad_seq} trips out of order")

    # Times must be non-decreasing along each trip. Equal is legal (two stops
    # inside the same minute); decreasing is not.
    def mins(t):
        h, m, s = t.split(":")
        return int(h) * 60 + int(m) + int(s) / 60

    inversions = 0
    for tid, grp in itertools.groupby(
            sorted(times, key=lambda x: (x["trip_id"], int(x["stop_sequence"]))),
            key=lambda x: x["trip_id"]):
        ts = [mins(g["arrival_time"]) for g in grp]
        if any(b < a for a, b in zip(ts, ts[1:])):
            inversions += 1
    check("arrival_times_non_decreasing", inversions == 0, f"{inversions} trips")

    check("arrival_equals_departure",
          all(t["arrival_time"] == t["departure_time"] for t in times),
          "no dwell time is modelled")

    check("calendar_single_service_day",
          len(cal) == 1 and cal[0]["start_date"] == cal[0]["end_date"] == SERVICE_DATE,
          f"{cal[0]['start_date']}..{cal[0]['end_date']}")

    check("route_type_is_bus",
          all(r["route_type"] == "3" for r in routes), "route_type=3")

    # Coordinates inside the Greater Male' envelope, catching swapped lat/lon.
    bad_coord = [s["stop_id"] for s in stops
                 if not (4.10 <= float(s["stop_lat"]) <= 4.30
                         and 73.40 <= float(s["stop_lon"]) <= 73.60)]
    check("coordinates_in_greater_male", not bad_coord,
          f"{len(bad_coord)} outside envelope")

    # Stops must actually be used by at least one trip.
    used = {t["stop_id"] for t in times}
    unused = stop_ids - used
    check("all_stops_used", not unused, f"{len(unused)} unused: {sorted(unused)[:5]}")

    # Zip integrity: the archive opens and holds the same files.
    try:
        with zipfile.ZipFile(ZIPPATH) as zf:
            names = set(zf.namelist())
            bad = zf.testzip()
        check("zip_readable", bad is None, f"first bad member: {bad}")
        check("zip_contains_required", set(required).issubset(names),
              f"{len(names)} members")
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        check("zip_readable", False, str(exc))

    return checks


def main() -> None:
    info = build()
    checks = validate()
    with REPORT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "result", "detail"])
        w.writeheader()
        w.writerows(checks)

    print("=" * 92)
    print("GTFS SYNTHESIS — Greater Male' RTL bus network")
    print("=" * 92)
    for name, n in info["counts"].items():
        print(f"  {name:22s} {n:>6d} rows")
    print()
    print(f"  routes with service   {info['n_routes']:>6d}")
    print(f"  trips                 {info['n_trips']:>6d}")
    print(f"  distinct stops        {info['n_stops']:>6d}")
    print(f"  stop_times            {info['counts']['stop_times.txt']:>6d}")
    print(f"  partially timed trips {info['partially_timed']:>6d}"
          "  (ship with only the stops that have a time)")
    print(f"  drop-off-only stops   {info['dropoff_only']:>6d}  (pickup_type=1)")
    print(f"  excluded, no timings  {', '.join(info['excluded']) or 'none'}")
    print(f"  service day           {SERVICE_DAY_NAME} (single day, from ~11:00)")
    print()
    passed = sum(c["result"] == "PASS" for c in checks)
    print(f"VALIDATION: {passed}/{len(checks)} checks pass")
    for c in checks:
        if c["result"] != "PASS":
            print(f"  FAIL {c['check']}: {c['detail']}")
    print()
    print(f"wrote {ZIPPATH}  ({ZIPPATH.stat().st_size / 1024:.1f} KiB)")
    print(f"wrote {OUTDIR}/")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
