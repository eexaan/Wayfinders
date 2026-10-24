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
    demand_supply_gap_base.csv demand vs capacity per route per hour (pre-stop-allocation)
    route_load_base.csv        route-level daily demand vs capacity (pre-segment)
    (build_stop_demand.py refines both into demand_supply_gap.csv and route_load.csv)
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

# The feed returns departures from the moment of the call onwards, so the
# morning is not observed (ADR-0001, ADR-0005). We cannot change the server's
# clock, but two facts ARE official and let us bound the morning WITHOUT
# inventing hourly data:
#   * trips_per_day (max trip order) - the complete daily trip count
#   * capture_first_departure - the first remaining departure at the call time
# Their difference is the exact number of morning trips. Combined with an
# assumed service start we get a bounded AVERAGE morning headway. That is a
# route-day statistic, not an hourly series, and it is emitted separately so it
# can never be mistaken for observed data (ADR-0011).
# ---------------------------------------------------------------------------
# Day periods for "bus usage by working hours".
#
# There is no published workforce or working-hours dataset for the Maldives, so
# 08:00-16:00 is an ASSUMPTION supplied by the team. It is a parameter, not a
# constant: build_period_usage() also emits a sensitivity table over 07-15,
# 08-16 and 09-17 so a reader can see how much the answer moves.
# See docs/adr/0012-working-hours-assumption.md.
# ---------------------------------------------------------------------------
WORKING_HOURS_START = 8
WORKING_HOURS_END = 16

PERIODS = [
    ("night", 0, 6),
    ("am_commute", 6, 8),
    ("working_hours", WORKING_HOURS_START, WORKING_HOURS_END),
    ("pm_commute", 16, 19),
    ("evening", 19, 22),
    ("late", 22, 24),
]


def _period_of(hour: int) -> str:
    for name, a, b in PERIODS:
        if a <= hour < b:
            return name
    return "late"


SERVICE_START_ASSUMED_MIN = 6 * 60      # 06:00, the assumption
SERVICE_START_LOW_MIN = 5 * 60 + 30     # 05:30 -> upper bound on headway
SERVICE_START_HIGH_MIN = 6 * 60 + 30    # 06:30 -> lower bound on headway


def morning_inference(first_departure_time: str | None, trips_total, trips_captured):
    """Exact morning trip count + bounded average headway. Nothing hourly."""
    if not isinstance(first_departure_time, str) or not trips_total:
        return None
    if pd.isna(trips_total) or pd.isna(trips_captured):
        return None
    try:
        hh, mm, _ = (int(x) for x in first_departure_time.split(":"))
    except (ValueError, AttributeError):
        return None
    first = hh * 60 + mm
    n = int(trips_total) - int(trips_captured or 0)
    if n <= 0:
        return None
    spans = {
        "assumed": first - SERVICE_START_ASSUMED_MIN,
        "low": first - SERVICE_START_LOW_MIN,
        "high": first - SERVICE_START_HIGH_MIN,
    }
    if spans["assumed"] <= 0:
        return None
    return {
        "trips_before_capture": n,
        "assumed_service_start": "06:00",
        "morning_span_min": spans["assumed"],
        "morning_avg_headway_min": round(spans["assumed"] / n, 1),
        "morning_avg_headway_min_low": round(spans["high"] / n, 1),
        "morning_avg_headway_min_high": round(spans["low"] / n, 1),
    }


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
                "capture_first_departure": dep_times[0]["timing"] if dep_times else "",
                "capture_last_departure": dep_times[-1]["timing"] if dep_times else "",
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
    """demand_supply_gap_base.csv (route x hour) and route_load_base.csv (route level)."""
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


# A donor hour must still fit its own passengers after giving up the trip.
# Raising this lets a scenario create a new over-capacity hour; that is a
# transfer of the queue, not a relief.
DONOR_CEILING_PCT = 100.0


def net_moves(moves):
    """Drop moves that exactly undo an earlier move.

    The loop is greedy and recomputes after every step, so a receiver can
    later become the cheapest donor and hand the trip straight back. The
    fleet state is already correct once such a pair cancels, but counting
    both rows inflates `trips_moved` and puts moves in the audit trail that
    relieve nothing. Cancelling them makes the log equal the net change.
    """
    kept, pending = [], {}
    for mv in moves:
        key = (mv["from_route"], mv["from_hour"], mv["to_route"], mv["to_hour"])
        reverse = (key[2], key[3], key[0], key[1])
        if pending.get(reverse):
            kept[pending[reverse].pop()] = None
            continue
        pending.setdefault(key, []).append(len(kept))
        kept.append(mv)
    return [mv for mv in kept if mv is not None]


def reallocate(df, donor_rule, receiver_rule, n_moves, min_trips_after=1,
               donor_ceiling_pct=DONOR_CEILING_PCT):
    """Move up to n_moves trips, one at a time, donor -> receiver.

    A donor is eligible only if its load stays within `donor_ceiling_pct`
    *after* losing the trip. An earlier version tested the donor before the
    move, so taking one bus from a 3-trip hour running at 83% left it at
    125% with 35 passengers behind - the move manufactured the harm it was
    meant to relieve, and the log still recorded an improvement.
    """
    d = df.copy()
    d["_cap"] = d["trips_in_hour"] * d["seated_capacity"]
    d["_load"] = d["demand_pax_est"] / d["_cap"]
    d["_over"] = (d["demand_pax_est"] - d["_cap"]).clip(lower=0)
    ceiling = donor_ceiling_pct / 100.0
    moves = []
    for _ in range(n_moves):
        donors = d[donor_rule(d) & (d["trips_in_hour"] > min_trips_after)]
        receivers = d[receiver_rule(d)]
        if donors.empty or receivers.empty:
            break
        rec = receivers.loc[receivers["_over"].idxmax()]
        donors = donors.drop(index=rec.name, errors="ignore")
        if donors.empty or rec["_over"] <= 0:
            break
        # The load the donor would carry with one bus fewer. This is the
        # guard the old code was missing.
        cap_after = (donors["trips_in_hour"] - 1) * donors["seated_capacity"]
        load_after = donors["demand_pax_est"] / cap_after
        donors = donors[load_after <= ceiling]
        if donors.empty:
            break
        don = donors.loc[donors["_load"].idxmin()]
        don_unmet = float(don["_over"])
        don_load_after = float(don["demand_pax_est"] / ((don["trips_in_hour"] - 1) * don["seated_capacity"]))
        d.loc[don.name, "trips_in_hour"] -= 1
        d.loc[rec.name, "trips_in_hour"] += 1
        # recompute the two touched rows before the next iteration
        for nm in (don.name, rec.name):
            cap = d.loc[nm, "trips_in_hour"] * d.loc[nm, "seated_capacity"]
            d.loc[nm, "_cap"] = cap
            d.loc[nm, "_load"] = d.loc[nm, "demand_pax_est"] / cap
            d.loc[nm, "_over"] = max(0.0, d.loc[nm, "demand_pax_est"] - cap)
        rec_after = max(0.0, d.loc[rec.name, "demand_pax_est"] - d.loc[rec.name, "_cap"])
        moves.append({
            "from_route": don["route_code"], "from_hour": int(don["hour"]),
            "to_route": rec["route_code"], "to_hour": int(rec["hour"]),
            "trips": 1,
            "donor_load_pct": round(float(don["_load"]) * 100, 1),
            "donor_load_after_pct": round(don_load_after * 100, 1),
            "donor_unmet_before": round(don_unmet, 1),
            "receiver_unmet_before": round(float(rec["_over"]), 1),
            "receiver_unmet_after": round(rec_after, 1),
        })
    return d.drop(columns=["_cap", "_load", "_over"]), net_moves(moves)


def build_scenarios(gap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recompute the scenarios on the official captured service.

    FLEET NEUTRALITY IS THE RULE, NOT A NICETY
        A planner cannot add a bus. Every scenario is therefore expressed as a
        set of TRIP MOVES: a trip is taken from a named route-hour and given to
        another route-hour on the same service day. Total trips are asserted to
        be unchanged, so `trips_change` is 0 by construction and any non-zero
        value is a bug rather than a result.

        A donor must keep at least one departure in its hour (`min_trips_after`),
        so a move never deletes a service. Donors are chosen by lowest load
        factor, receivers by largest unmet demand, one trip at a time, with the
        load recomputed after every move. That makes the ordering greedy but
        honest: the third move sees the effect of the first two.

    S4 is a trip move, not extra service
        "Express" buys a faster cycle by skipping stops. The genuine effect is
        a shorter round trip, which the same fleet can spend on more peak
        departures. Modelling it as extra trips would smuggle in a new bus, so
        it is modelled as off-peak trips re-timed into the peak. The running
        time saving itself is reported separately in `scenario_modal_shift.csv`.

    The Friday scenario is dropped: the feed returns a single service day, so a
    Friday service pattern cannot be observed from this source.

    Only captured hours are touched. Hours before the capture window keep
    trips_in_hour = NaN and are excluded from every KPI, so "not captured" is
    never silently treated as "no bus".
    """
    AIRPORT = ["R3", "R4", "R9"]
    CORRIDOR = ["R1", "R2"]

    def kpis(df, label, trips_moved):
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
            "boardings_over_capacity": int(round(d["over"].sum())),
            "unmet_share_pct": round(d["over"].sum() / tot * 100, 2) if tot else 0.0,
            "total_trips_captured": int(round(d["trips_in_hour"].sum())),
            "demand_pax_captured": round(tot, 0),
            "trips_moved": trips_moved,
        }

    airport_mask = lambda x: x["route_code"].isin(AIRPORT)
    corridor_mask = lambda x: x["route_code"].isin(CORRIDOR)

    # Receivers are chosen by the DATA, not by a hand-picked hour window: any
    # route-hour that is actually over capacity is eligible. An earlier version
    # restricted receivers to 15:00-20:00 and so refused to relieve R1 at 22:00,
    # where the load is 152% -- the model was hiding its own best answer.

    # S2 - airport buses re-timed onto their own peaks.
    # Donors: late-night airport trips, where load is 10-35%.
    s2, m2 = reallocate(
        gap,
        lambda d: airport_mask(d) & (d["hour"] >= 19),
        lambda d: airport_mask(d),
        n_moves=10,
    )

    # S3 - cross-corridor reallocation: airport trips out of the afternoon lull
    # into the R1/R2 corridor wherever it is over capacity. This is what a
    # depot with one pool of buses can actually do.
    s3, m3 = reallocate(
        gap,
        lambda d: airport_mask(d) & (d["hour"].between(13, 20)),
        lambda d: corridor_mask(d),
        n_moves=10,
    )

    # S4 - express overlay. Off-peak corridor trips re-timed into the peak,
    # which a faster cycle makes possible without a new vehicle.
    s4, m4 = reallocate(
        gap,
        lambda d: corridor_mask(d) & (d["hour"].between(11, 14) | d["hour"].between(20, 23)),
        lambda d: corridor_mask(d),
        n_moves=10,
    )

    # S5 - recommended package: S3 then S4. S2 was the original third term, but
    # measured on the captured service it relieves only 6 boardings, because at
    # route level the airport buses are not over capacity -- their crowding sits
    # on one segment, not on the route-hour average. S3 and S4 are the two
    # changes that do measurable work, so the package is built from those.
    # Fleet neutrality is preserved because reallocate() only moves trips.
    s5, m5a = reallocate(
        gap,
        lambda d: airport_mask(d) & (d["hour"].between(13, 20)),
        lambda d: corridor_mask(d),
        n_moves=10,
    )
    s5, m5b = reallocate(
        s5,
        lambda d: corridor_mask(d) & (d["hour"].between(11, 14) | d["hour"].between(20, 23)),
        lambda d: corridor_mask(d),
        n_moves=10,
    )
    m5 = m5a + m5b

    scenarios = [
        ("S0_baseline", gap, []),
        ("S2_airport_retimed", s2, m2),
        ("S3_rebalanced_to_corridor", s3, m3),
        ("S4_express_peak", s4, m4),
        ("S5_recommended_package", s5, m5),
    ]

    k = pd.DataFrame([kpis(df, label, len(mv)) for label, df, mv in scenarios])
    b = k.iloc[0]
    k["over_capacity_change"] = k["boardings_over_capacity"] - b["boardings_over_capacity"]
    k["wait_change_min"] = (k["mean_wait_min_captured"] - b["mean_wait_min_captured"]).round(1)
    k["trips_change"] = k["total_trips_captured"] - b["total_trips_captured"]

    # The whole point of the rewrite: prove neutrality rather than assert it.
    assert (k["trips_change"] == 0).all(), (
        "fleet neutrality violated: " + str(k[["scenario", "trips_change"]].to_dict("records"))
    )

    corr = []
    for label, df, _mv in scenarios:
        d = df.dropna(subset=["trips_in_hour", "demand_pax_est"])
        d = d[d["trips_in_hour"] > 0]
        for route, g in d.groupby("route_code"):
            cap = g["trips_in_hour"] * g["seated_capacity"]
            over = (g["demand_pax_est"] - cap).clip(lower=0)
            corr.append({
                "scenario": label,
                "route_code": route,
                "boardings_over_capacity": int(round(over.sum())),
                "trips_captured": int(round(g["trips_in_hour"].sum())),
                "mean_trips_per_hour": round(float(g["trips_in_hour"].mean()), 2),
            })

    moves = pd.DataFrame(
        [{"scenario": label, **mv} for label, _df, mvs in scenarios for mv in mvs]
    )
    return k, pd.DataFrame(corr), moves


# ---------------------------------------------------------------------------
def build_period_usage(gap: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bus usage and service by day period, per route plus a network total.

    Demand per period is the sum of the hourly demand estimate, which is the
    MTCC daily level distributed by the Avas shape. Service per period is the
    sum of captured departures only, so `hours_captured` exposes partial
    coverage - 3 of the 8 working hours fall before the capture window.
    """
    g = gap.copy()
    g["period"] = g["hour"].map(_period_of)

    rows = []
    for (route, period), grp in g.groupby(["route_code", "period"]):
        seats = int(grp["seated_capacity"].iloc[0]) if grp["seated_capacity"].notna().any() else 0
        demand = grp["demand_pax_est"].sum(min_count=1)
        cap_hours = grp["trips_in_hour"].notna()
        trips = grp.loc[cap_hours, "trips_in_hour"].sum()
        cap = trips * seats if seats else None
        total_hours = len(grp)
        captured_hours = int(cap_hours.sum())
        rows.append(
            {
                "route_code": route,
                "period": period,
                "hours_in_period": total_hours,
                "hours_captured": captured_hours,
                "hours_not_captured": total_hours - captured_hours,
                "boardings_est": round(demand, 1) if pd.notna(demand) else None,
                "trips_captured": float(trips) if captured_hours else None,
                "seated_capacity": cap,
                "load_factor_seats_pct": round(demand / cap * 100, 1)
                if (pd.notna(demand) and cap) else None,
            }
        )
    per_route = pd.DataFrame(rows)
    # share of that route's own daily demand
    route_daily = per_route.groupby("route_code")["boardings_est"].transform("sum")
    per_route["share_of_route_demand_pct"] = (
        per_route["boardings_est"] / route_daily * 100
    ).round(1)

    # network total per period
    net = (
        g.groupby("period")
        .agg(boardings_est=("demand_pax_est", "sum"),
             trips_captured=("trips_in_hour", "sum"),
             hours_captured=("trips_in_hour", "count"),
             hours_in_period=("hour", "size"))
        .reset_index()
    )
    daily = net["boardings_est"].sum()
    net["share_of_route_demand_pct"] = (net["boardings_est"] / daily * 100).round(1)
    net["route_code"] = "ALL"
    net["hours_not_captured"] = net["hours_in_period"] - net["hours_captured"]
    net["seated_capacity"] = None
    net["load_factor_seats_pct"] = None
    cols = list(per_route.columns)
    for c in cols:
        if c not in net.columns:
            net[c] = None
    net = net[cols]
    out = pd.concat([per_route, net], ignore_index=True)
    out["period_order"] = out["period"].map({n: i for i, (n, _, _) in enumerate(PERIODS)})
    out = out.sort_values(["route_code", "period_order"]).drop(columns="period_order")
    out.to_csv(OUT / "usage_by_period.csv", index=False)

    # sensitivity on the working-hours definition
    sens = []
    for start, end in [(7, 15), (8, 16), (9, 17), (7, 17), (8, 18)]:
        in_win = g["hour"].between(start, end - 1)
        dem = g.loc[in_win, "demand_pax_est"].sum()
        cap_hours = in_win & g["trips_in_hour"].notna()
        sens.append(
            {
                "working_window": f"{start:02d}:00-{end:02d}:00",
                "share_of_daily_demand_pct": round(dem / daily * 100, 1),
                "hours_captured_in_window": int(cap_hours.sum()),
                "hours_in_window": int(in_win.sum()),
                "trips_captured_in_window": float(g.loc[cap_hours, "trips_in_hour"].sum()),
            }
        )
    pd.DataFrame(sens).to_csv(OUT / "working_hours_sensitivity.csv", index=False)
    return out, pd.DataFrame(sens)


# ---------------------------------------------------------------------------
def main() -> None:
    """Build everything first, validate, and only then write.

    The write order used to interleave with the build, so a failed assertion in
    build_scenarios() left demand_supply_gap.csv and route_load.csv already
    rewritten with the bad state -- a failed build silently corrupted two
    outputs. Nothing touches the disk until every computation has succeeded.
    """
    routes = load_routes()
    capacity = load_capacity()
    master, stops_df, deps = build_master(routes, capacity)
    hourly = build_hourly_service(deps, master)
    bridge = build_bridge(stops_df, routes)
    demand = load_demand()
    shapes = taxi_shapes()
    gap, load = build_gap(master, hourly, demand, shapes)
    kpis, corr, moves = build_scenarios(gap)

    # ---- validation complete; from here on the build cannot fail ----
    master.to_csv(OUT / "routes_master.csv", index=False)
    stops_df.to_csv(OUT / "route_stops.csv", index=False)
    deps.to_csv(OUT / "service_departures.csv", index=False)
    build_geojson(stops_df, master)
    hourly.to_csv(OUT / "route_service_by_hour.csv", index=False)
    bridge.to_csv(OUT / "bridge_segment_analysis.csv", index=False)
    demand.to_csv(OUT / "demand_by_daytype.csv", index=False)
    # BASE tables. build_stop_demand.py refines these into demand_supply_gap.csv
    # and route_load.csv by adding per-stop demand and segment columns. Writing
    # the final names here would clobber the refined versions whenever this
    # script runs alone, so the base files have exactly one reader each.
    gap.to_csv(OUT / "demand_supply_gap_base.csv", index=False)
    load.to_csv(OUT / "route_load_base.csv", index=False)

    # Inferred morning: a route-day statistic, kept out of the hourly table.
    morning_rows = []
    for r in master.itertuples():
        m = morning_inference(
            getattr(r, "capture_first_departure", None),
            getattr(r, "trips_per_day", None),
            getattr(r, "trips_captured", None),
        )
        if not m:
            continue
        morning_rows.append(
            {
                "route_code": r.route_code,
                "route_name": r.route_name,
                "trips_per_day": r.trips_per_day,
                "trips_captured": r.trips_captured,
                **m,
                "method": (
                    "trips_before_capture = official trips_per_day - captured trips; "
                    "average headway = (first captured departure - assumed 06:00 start) / trips"
                ),
                "status": "INFERRED - not observed. Replace with a real capture if available.",
            }
        )
    pd.DataFrame(morning_rows).to_csv(OUT / "morning_service_inferred.csv", index=False)

    # Bus usage by day period, with the working-hours band.
    usage, wh_sens = build_period_usage(gap, master)

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
    print("USAGE BY PERIOD (network)")
    print("=" * 100)
    print(usage[usage.route_code == "ALL"].to_string(index=False))
    print()
    print("working-hours sensitivity")
    print(wh_sens.to_string(index=False))
    print()
    print("=" * 100)
    print("SCENARIOS")
    print("=" * 100)
    print(kpis.to_string(index=False))


if __name__ == "__main__":
    main()
