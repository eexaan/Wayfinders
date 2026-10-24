"""
================================================================================
Build the dashboard data from the OFFICIAL RTL 2026 bus feed
================================================================================
Maldives Datathon 2026 | Team Wayfinders

Source of supply (replaces the MTCC "Ramadan 1446" PDF schedules):
    https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails
    saved as data/official/rtl/bus_routedetails_2026.json

That endpoint is public (no auth) and returns, for all 15 Greater Malé routes:
    routeNumber, name (official EN), dvname (official Dhivehi), color, fare,
    isMiniBusRoute, depot, start/end station, and the full stop list with
    latitude/longitude and per-stop departure timings.

IMPORTANT LIMITATION — read before using the output
    The feed is time-filtered: it returns the stops' departures from the
    moment of the call onwards. Our capture was taken at ~11:00 on Saturday
    2026-10-24, so the timetable window is roughly 11:00-24:00 and the
    morning peak (06:00-10:59) is NOT captured.

    Two things are still complete and official:
      * the total number of trips per route per day (the maximum trip `order`)
      * the departure times of every trip from the capture time onwards

    Hours before the capture window are emitted with trips_in_hour = null,
    never 0. Re-running this script shortly after 00:00 would capture the
    whole service day.

Outputs (dashboard/data/):
    routes_master.csv          official naming + attributes + capacity
    route_stops.csv            official stops, EN + Dhivehi, with coordinates
    route_lines.geojson        route polylines from the official coordinates
    service_departures.csv     every captured trip departure
    route_service_by_hour.csv  departures and headway per route per hour
    demand_supply_gap.csv      demand vs capacity per route per hour
    route_load.csv             route-level daily demand vs capacity
    bridge_segment_analysis.csv scheduled stop-to-stop segment times
    scenario_kpis.csv          scenarios recomputed on the official service
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data" / "official"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Fleet: bus type and capacity per route, loaded from the team's capacity table.
#
# Source: data/raw/mtcc_bus_capacity.csv (team fleet guidance, 2026-10-24).
# It carries TWO capacity numbers per route, and the difference matters:
#   seated_capacity  - seats only
#   max_passengers   - seats + permitted standing
# For R1 they are 72 and 84, so the same ridership is 104% of seats but 89.5%
# of total capacity. See docs/adr/0003-load-factor-on-seats.md for why the
# headline is the seats figure.
#
# `load_factor_comparable` is False where the operator gave seats but not
# standing capacity (R5, R6): a load factor cannot be formed there.
# ---------------------------------------------------------------------------
CAPACITY_CSV = RAW / "mtcc_bus_capacity.csv"


def load_capacity() -> pd.DataFrame:
    cap = pd.read_csv(CAPACITY_CSV)
    cap = cap[cap["area"] == "Greater Malé"].copy()
    cap = cap.rename(columns={"route_number": "route_code"})
    keep = [
        "route_code", "bus_type", "bus_model", "seated_capacity", "wheelchair_bays",
        "max_passengers", "capacity_basis", "load_factor_comparable", "confidence",
        "seated_capacity_source", "notes",
    ]
    cap = cap[[c for c in keep if c in cap.columns]]
    # max_passengers is blank where standing capacity was not stated: fall back
    # to seats so the column is always usable, but keep the flag honest.
    cap["max_passengers"] = cap["max_passengers"].fillna(cap["seated_capacity"])
    cap["load_factor_comparable"] = (
        cap["load_factor_comparable"].astype(str).str.upper().eq("TRUE")
    )
    cap["capacity_source"] = "data/raw/mtcc_bus_capacity.csv (team, 2026-10-24)"
    return cap


# Which corridor each route serves -> used to attach the Avas demand shape.
ROUTE_CORRIDOR = {
    "R1": "male_hm1", "R2": "male_hm1", "R15": "male_hm1",
    "R3": "male_airport",
    "R4": "hm1_airport",
    "R5": "hm_internal",
    "R6": "hm1_hm2",
    "R7": "male_hm2", "R8": "male_hm2",
    "R9": "hm2_airport",
    "R10": "male_internal", "R11": "male_internal", "R12": "male_internal",
    "R13": "villimale", "R14": "villimale",
}

AIRPORT_CORRIDORS = {"male_airport", "hm1_airport", "hm2_airport"}

AIRCRAFT_DAY_NOTE = "Saturday 2026-10-24 service day (feed is time-filtered)"


def load_routes() -> list[dict]:
    payload = json.loads((OFFICIAL / "rtl" / "bus_routedetails_2026.json").read_text())
    return payload["routeResponse"]


def route_sort_key(code: str) -> tuple[int, str]:
    digits = "".join(c for c in code if c.isdigit())
    return (int(digits) if digits else 999, code)


# ---------------------------------------------------------------------------
def build_master(
    routes: list[dict], capacity: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """routes_master.csv, route_stops.csv, service_departures.csv"""
    master_rows, stop_rows, dep_rows = [], [], []
    cap = capacity.set_index("route_code")

    for r in routes:
        code = r["routeNumber"]
        stops = r.get("busRouteStopList") or []
        origin = min(stops, key=lambda s: s["order"]) if stops else None
        dep_times = sorted(
            (t for t in (origin.get("timings") or [])), key=lambda t: t["order"]
        ) if origin else []

        trips_captured = len(dep_times)
        trips_total = max((t["order"] for t in dep_times), default=None)

        if code in cap.index:
            c = cap.loc[code]
            bus_type = c["bus_type"]
            bus_model = c.get("bus_model")
            seated = int(c["seated_capacity"])
            maxpax = int(c["max_passengers"])
            comparable = bool(c["load_factor_comparable"])
            cap_source = c["capacity_source"]
        else:
            bus_type, bus_model, seated, maxpax, comparable = "?", None, 0, 0, False
            cap_source = "NOT IN CAPACITY TABLE"

        seats = seated  # kept for the hourly gap table, which is seats-based

        master_rows.append(
            {
                "route_code": code,
                "route_name": r["name"],
                "route_name_dv": r["dvname"],
                "colour": r["color"],
                "fare_mvr": r["fare"],
                "is_minibus": int(r["isMiniBusRoute"]),
                "depot": r["depotName"],
                "start_station": r["startStationName"],
                "end_station": r["endStationName"],
                "start_code": r["startStationCode"],
                "end_code": r["endStationCode"],
                "n_stops": len(stops),
                "trips_per_day": trips_total,
                "trips_captured": trips_captured,
                "capture_first_departure": dep_times[0]["timing"] if dep_times else None,
                "capture_last_departure": dep_times[-1]["timing"] if dep_times else None,
                "bus_type": bus_type,
                "bus_model": bus_model,
                "seated_capacity": seated,
                "wheelchair_bays": None,
                "max_passengers": maxpax,
                "load_factor_comparable": comparable,
                "seats": seated,
                "capacity_source": cap_source,
                "corridor": ROUTE_CORRIDOR.get(code),
                "service_day": AIRCRAFT_DAY_NOTE,
            }
        )

        for s in stops:
            stop_rows.append(
                {
                    "route_code": code,
                    "stop_order": s["order"],
                    "stop_name": s["name"],
                    "stop_name_dv": s["dvname"],
                    "stop_code": s["code"],
                    "lat": float(s["latitude"]),
                    "lon": float(s["longitude"]),
                }
            )

        for t in dep_times:
            hh, mm, _ss = (int(x) for x in t["timing"].split(":"))
            dep_rows.append(
                {
                    "route_code": code,
                    "trip_order": t["order"],
                    "departure_time": t["timing"],
                    "departure_min": hh * 60 + mm,
                    "hour": hh,
                }
            )

    master = pd.DataFrame(master_rows).sort_values(
        "route_code", key=lambda s: s.map(route_sort_key)
    )
    stops_df = pd.DataFrame(stop_rows).sort_values(["route_code", "stop_order"])
    deps = pd.DataFrame(dep_rows).sort_values(["route_code", "trip_order"])
    return master, stops_df, deps


def build_geojson(stops_df: pd.DataFrame, master: pd.DataFrame) -> None:
    colour = dict(zip(master["route_code"], master["colour"]))
    name = dict(zip(master["route_code"], master["route_name"]))
    feats = []
    for code, g in stops_df.groupby("route_code"):
        g = g.sort_values("stop_order")
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "route_code": code,
                    "route_name": name.get(code),
                    "colour": colour.get(code),
                    "n_stops": int(len(g)),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[float(r.lon), float(r.lat)] for r in g.itertuples()],
                },
            }
        )
    path = OUT / "route_lines.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
    )


def build_hourly_service(deps: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    """Departures per route per hour, plus the smallest observed headway."""
    rows = []
    for code, g in deps.groupby("route_code"):
        by_hour = g.groupby("hour").size()
        times = g.sort_values("departure_min")["departure_min"].to_numpy()
        headways = np.diff(times) if len(times) > 1 else np.array([])
        for h in range(24):
            n = int(by_hour.get(h, 0))
            rows.append(
                {
                    "route_code": code,
                    "hour": h,
                    "departures": n if n > 0 else None,
                    "captured": bool(n > 0),
                    "min_headway_min": (
                        int(np.min(headways[(times[:-1] >= h * 60) & (times[:-1] < (h + 1) * 60)]))
                        if len(headways)
                        and np.any((times[:-1] >= h * 60) & (times[:-1] < (h + 1) * 60))
                        else None
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_bridge(stops_df: pd.DataFrame, routes: list[dict]) -> pd.DataFrame:
    """Scheduled stop-to-stop run times, from the official per-stop timings."""
    rows = []
    for r in routes:
        code = r["routeNumber"]
        stops = sorted(r.get("busRouteStopList") or [], key=lambda s: s["order"])
        # Build trip -> ordered (stop, minute) using times present at each stop
        per_stop = {}
        for s in stops:
            for t in s.get("timings") or []:
                hh, mm, _ = (int(x) for x in t["timing"].split(":"))
                per_stop.setdefault(t["order"], []).append(
                    (s["order"], s["name"], hh * 60 + mm)
                )
        for trip, seq in per_stop.items():
            seq.sort()
            if len(seq) < 2:
                continue
            span = seq[-1][2] - seq[0][2]
            for (o1, n1, t1), (o2, n2, t2) in zip(seq, seq[1:]):
                if o2 == o1 + 1:
                    rows.append(
                        {
                            "route_code": code,
                            "from_stop": n1,
                            "to_stop": n2,
                            "segment_minutes": t2 - t1,
                            "end_to_end_minutes": span,
                        }
                    )
    df = pd.DataFrame(rows)
    return (
        df.groupby(["route_code", "from_stop", "to_stop"])
        .agg(
            median_segment_minutes=("segment_minutes", "median"),
            median_end_to_end_minutes=("end_to_end_minutes", "median"),
            n_trips=("segment_minutes", "size"),
        )
        .reset_index()
        .sort_values(["route_code", "median_segment_minutes"], ascending=[True, False])
    )


# ---------------------------------------------------------------------------
def load_demand() -> pd.DataFrame:
    """MTCC observed daily boardings by route (2025). Day-type split where available."""
    xl = pd.ExcelFile(RAW / "MTCC.xlsx")
    daily = pd.read_excel(xl, sheet_name="bus_daily")
    monthly = pd.read_excel(xl, sheet_name="bus_monthly")

    daily["date"] = pd.to_datetime(daily["date"])
    daily["dow"] = daily["date"].dt.day_name()
    daily["day_type"] = np.where(
        daily["dow"] == "Friday", "friday",
        np.where(daily["dow"] == "Saturday", "sat_holiday", "weekday"),
    )
    by = (
        daily.groupby(["route_id", "day_type"])["total_pax"]
        .mean()
        .reset_index()
        .rename(columns={"route_id": "route_code", "total_pax": "boardings_per_day"})
    )
    by["demand_source"] = "MTCC bus_daily 2025 (observed)"

    # R3 and R7 only have monthly data: split with the day-type index measured
    # on the routes that do have daily data.
    monthly["days"] = pd.PeriodIndex(monthly["month"].astype(str), freq="M").days_in_month
    monthly["pax_day"] = monthly["total_pax"] / monthly["days"]
    idx = daily.groupby([daily["date"].dt.to_period("M"), "day_type"])["total_pax"].mean().unstack()
    idx = idx.fillna(0.0)
    mean_all = idx.mean(axis=1)
    for dt in ("weekday", "friday", "sat_holiday"):
        if dt not in idx:
            idx[dt] = np.nan
    monthly["ym"] = pd.PeriodIndex(monthly["month"].astype(str), freq="M")
    fill = []
    for route in monthly["route_id"].unique():
        if route in set(daily["route_id"].unique()):
            continue
        sub = monthly[monthly["route_id"] == route]
        for dt in ("weekday", "friday", "sat_holiday"):
            rel = sub["ym"].map((idx[dt] / mean_all)).fillna(1.0)
            fill.append(
                {
                    "route_code": route,
                    "day_type": dt,
                    "boardings_per_day": float((sub["pax_day"] * rel.to_numpy()).mean()),
                    "demand_source": "MTCC bus_monthly x daily-data day-type index",
                }
            )
    return pd.concat([by, pd.DataFrame(fill)], ignore_index=True)


def taxi_shapes() -> dict[str, pd.Series]:
    od = pd.read_csv(OUT / "taxi_od_by_hour.csv")
    pairs = {
        "male_hm1": [("Male City", "Hulhumale Ph1"), ("Hulhumale Ph1", "Male City")],
        "male_hm2": [("Male City", "Hulhumale Ph2"), ("Hulhumale Ph2", "Male City")],
        "hm1_hm2": [("Hulhumale Ph1", "Hulhumale Ph2"), ("Hulhumale Ph2", "Hulhumale Ph1")],
        "male_airport": [("Male City", "Velana Airport"), ("Velana Airport", "Male City")],
        "hm1_airport": [("Hulhumale Ph1", "Velana Airport"), ("Velana Airport", "Hulhumale Ph1")],
        "hm2_airport": [("Hulhumale Ph2", "Velana Airport"), ("Velana Airport", "Hulhumale Ph2")],
        "hm_internal": [("Hulhumale Ph1", "Hulhumale Ph1")],
        "male_internal": [("Male City", "Male City")],
        "villimale": [("Villimale", "Villimale")],
    }
    out = {}
    for corridor, prs in pairs.items():
        s = pd.Series(0.0, index=range(24))
        for a, b in prs:
            hit = od[(od["zone_o"] == a) & (od["zone_d"] == b)]
            if not hit.empty:
                s = s.add(hit.groupby("hour")["rides"].sum(), fill_value=0)
        out[corridor] = s / s.sum() if s.sum() > 0 else pd.Series(1 / 24, index=range(24))
    return out


def build_gap(master, hourly, demand, shapes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """demand_supply_gap.csv (route x hour) and route_load.csv (route level)."""
    rows, load_rows = [], []
    for r in master.itertuples():
        code = r.route_code
        seats = int(r.seats)
        corridor = r.corridor
        shape = shapes.get(corridor, pd.Series(1 / 24, index=range(24)))

        # Daily demand: use the captured service day if we know it, else weekday.
        d = demand[demand["route_code"] == code]
        daily_pax = (
            float(d[d["day_type"] == "sat_holiday"]["boardings_per_day"].iloc[0])
            if not d[d["day_type"] == "sat_holiday"].empty
            else (float(d["boardings_per_day"].iloc[0]) if not d.empty else np.nan)
        )
        has_demand = not d.empty

        h = hourly[hourly["route_code"] == code].set_index("hour")
        captured = h[h["captured"]]
        for hour in range(24):
            trips = int(h.loc[hour, "departures"]) if hour in h.index and h.loc[hour, "captured"] else None
            demand_h = round(daily_pax * shape.get(hour, 0.0), 1) if has_demand else None
            cap = trips * seats if trips is not None else None
            rows.append(
                {
                    "route_code": code,
                    "hour": hour,
                    "trips_in_hour": trips,
                    "capture_status": "captured" if trips is not None else "before_capture_window",
                    "seated_capacity": seats,
                    "seated_capacity_hour": cap,
                    "demand_pax_est": demand_h,
                    "load_factor_pct": round(demand_h / cap * 100, 1) if (demand_h is not None and cap) else None,
                    "unmet_pax_est": round(max(0.0, demand_h - cap), 1) if (demand_h is not None and cap) else None,
                    "demand_source": "MTCC observed (level) x Avas shape (modelled)" if has_demand else "NO DEMAND DATA",
                }
            )

        # Two denominators per ADR-0003: seats (primary) and seats+standing.
        maxpax = int(getattr(r, "max_passengers", seats) or seats)
        comparable = bool(getattr(r, "load_factor_comparable", False))
        cap_day = (r.trips_per_day or 0) * seats if r.trips_per_day else None
        cap_day_max = (r.trips_per_day or 0) * maxpax if r.trips_per_day else None
        usable = has_demand and comparable and cap_day
        load_rows.append(
            {
                "route_code": code,
                "route_name": r.route_name,
                "bus_type": r.bus_type,
                "bus_model": getattr(r, "bus_model", None),
                "seated_capacity": seats,
                "max_passengers": maxpax,
                "load_factor_comparable": comparable,
                "fare_mvr": r.fare_mvr,
                "trips_per_day": r.trips_per_day,
                "seated_capacity_day": cap_day,
                "capacity_day_max": cap_day_max,
                "boardings_per_day": round(daily_pax, 0) if has_demand else None,
                "pax_per_trip": round(daily_pax / r.trips_per_day, 1) if (has_demand and r.trips_per_day) else None,
                # Primary: load on SEATS. Upper bound assumes every boarding rides
                # the full route; avg assumes uniform alighting (halved).
                "load_factor_seats_upper_pct": round(daily_pax / cap_day * 100, 1) if usable else None,
                "load_factor_seats_avg_pct": round(daily_pax * 0.5 / cap_day * 100, 1) if usable else None,
                # Secondary: load on seats + permitted standing.
                "load_factor_capacity_upper_pct": round(daily_pax / cap_day_max * 100, 1)
                if (has_demand and comparable and cap_day_max) else None,
                "load_factor_capacity_avg_pct": round(daily_pax * 0.5 / cap_day_max * 100, 1)
                if (has_demand and comparable and cap_day_max) else None,
                "demand_source": (
                    "MTCC observed" if has_demand
                    else "NO DEMAND DATA"
                ) if comparable else (
                    "CAPACITY NOT COMPARABLE (standing capacity not stated)"
                    if not comparable else "MTCC observed"
                ),
                "service_capture": f"{r.trips_captured} of {r.trips_per_day} trips captured"
                if r.trips_captured
                else "no timings returned",
            }
        )
    gap = pd.DataFrame(rows)
    load = pd.DataFrame(load_rows).sort_values("route_code", key=lambda s: s.map(route_sort_key))
    return gap, load


def build_scenarios(gap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recompute the scenarios on the official captured service.

    Scenarios are expressed as explicit TRIP MOVES, not percentage factors:
    at 1-3 trips per route per hour a 12% change rounds to zero, so factors are
    misleading. A trip is added or removed from a named route-hour.

    Only captured hours are touched. Hours before the capture window keep
    trips_in_hour = NaN and are excluded from every KPI, so "not captured" is
    never silently treated as "no bus".

    The Friday scenario is dropped: the feed returns a single service day, so
    a Friday service pattern cannot be observed from this source.
    """
    AIRPORT = ["R3", "R4", "R9"]
    CORRIDOR = ["R1", "R2"]

    def move(df, routes, hours, delta):
        m = df["route_code"].isin(routes) & df["hour"].isin(hours) & df["trips_in_hour"].notna()
        df.loc[m, "trips_in_hour"] = np.maximum(0, df.loc[m, "trips_in_hour"] + delta)
        return df

    def kpis(df, label):
        d = df.dropna(subset=["trips_in_hour", "demand_pax_est"]).copy()
        d = d[d["trips_in_hour"] > 0]
        d["capacity"] = d["trips_in_hour"] * d["seated_capacity"]
        d["over"] = (d["demand_pax_est"] - d["capacity"]).clip(lower=0)
        w = d["demand_pax_est"].clip(lower=0)
        tot = float(w.sum())
        wait = 60 / d["trips_in_hour"] / 2
        mw = float((w * wait).sum() / tot) if tot else 0.0
        return {
            "scenario": label,
            "mean_wait_min_captured": round(mw, 1),
            "boardings_over_capacity": int(d["over"].sum()),
            "unmet_share_pct": round(d["over"].sum() / tot * 100, 2) if tot else 0.0,
            "total_trips_captured": int(d["trips_in_hour"].sum()),
            "demand_pax_captured": round(tot, 0),
        }

    scenarios = [("S0_baseline", gap.copy())]

    # S2 - airport buses re-timed onto the arrival peaks.
    # Doubles the afternoon airport frequency, halves the late evening. The
    # arrival peak hours available in the captured window are 11:00-15:00.
    s2 = gap.copy()
    for h in [11, 12, 13, 14, 15]:
        move(s2, AIRPORT, [h], +1)
    for h in [22, 23]:
        move(s2, AIRPORT, [h], -1)
    scenarios.append(("S2_airport_retimed", s2))

    # S3 - fleet-neutral reallocation: 6 trips off the airport routes in the
    # mid-afternoon lull, 6 onto R1/R2 in the evening peak.
    s3 = gap.copy()
    for h in [13, 14]:
        move(s3, AIRPORT, [h], -1)
    for h in [16, 17, 18]:
        move(s3, CORRIDOR, [h], +1)
    scenarios.append(("S3_rebalanced_to_corridor", s3))

    # S4 - express overlay on R1/R2: one extra departure in each evening
    # peak hour (the express runs the same vehicle on a faster cycle).
    s4 = gap.copy()
    for h in [15, 16, 17, 18]:
        move(s4, CORRIDOR, [h], +1)
    scenarios.append(("S4_express_peak", s4))

    # S5 - recommended package: S2 + S4.
    s5 = s2.copy()
    for h in [15, 16, 17, 18]:
        move(s5, CORRIDOR, [h], +1)
    scenarios.append(("S5_recommended_package", s5))

    k = pd.DataFrame([kpis(df, label) for label, df in scenarios])
    b = k.iloc[0]
    k["over_capacity_change"] = k["boardings_over_capacity"] - b["boardings_over_capacity"]
    k["wait_change_min"] = (k["mean_wait_min_captured"] - b["mean_wait_min_captured"]).round(1)
    k["trips_change"] = k["total_trips_captured"] - b["total_trips_captured"]

    corr = []
    for label, df in scenarios:
        d = df.dropna(subset=["trips_in_hour", "demand_pax_est"])
        d = d[d["trips_in_hour"] > 0]
        for route, g in d.groupby("route_code"):
            cap = g["trips_in_hour"] * g["seated_capacity"]
            over = (g["demand_pax_est"] - cap).clip(lower=0)
            corr.append(
                {
                    "scenario": label,
                    "route_code": route,
                    "boardings_over_capacity": int(over.sum()),
                    "trips_captured": int(g["trips_in_hour"].sum()),
                    "mean_trips_per_hour": round(float(g["trips_in_hour"].mean()), 2),
                }
            )
    return k, pd.DataFrame(corr)


# ---------------------------------------------------------------------------
def main() -> None:
    routes = load_routes()
    capacity = load_capacity()
    master, stops_df, deps = build_master(routes, capacity)
    master.to_csv(OUT / "routes_master.csv", index=False)
    stops_df.to_csv(OUT / "route_stops.csv", index=False)
    deps.to_csv(OUT / "service_departures.csv", index=False)
    build_geojson(stops_df, master)

    hourly = build_hourly_service(deps, master)
    hourly.to_csv(OUT / "route_service_by_hour.csv", index=False)

    bridge = build_bridge(stops_df, routes)
    bridge.to_csv(OUT / "bridge_segment_analysis.csv", index=False)

    demand = load_demand()
    demand.to_csv(OUT / "demand_by_daytype.csv", index=False)
    shapes = taxi_shapes()
    gap, load = build_gap(master, hourly, demand, shapes)
    gap.to_csv(OUT / "demand_supply_gap.csv", index=False)
    load.to_csv(OUT / "route_load.csv", index=False)

    kpis, corr = build_scenarios(gap)
    kpis.to_csv(OUT / "scenario_kpis.csv", index=False)
    corr.to_csv(OUT / "scenario_corridor_kpis.csv", index=False)

    pd.set_option("display.width", 200)
    print("=" * 100)
    print("ROUTES (official RTL naming)")
    print("=" * 100)
    print(
        master[
            ["route_code", "route_name", "route_name_dv", "fare_mvr", "n_stops",
             "trips_per_day", "trips_captured", "bus_type", "seats"]
        ].to_string(index=False)
    )
    print()
    print("=" * 100)
    print("ROUTE LOAD (daily)")
    print("=" * 100)
    print(load.to_string(index=False))
    print()
    print("=" * 100)
    print("SCENARIOS")
    print("=" * 100)
    print(kpis.to_string(index=False))


if __name__ == "__main__":
    main()
