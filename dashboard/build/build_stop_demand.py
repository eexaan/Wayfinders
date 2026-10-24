"""
================================================================================
Stop-level demand allocation and segment load factors
================================================================================
Maldives Datathon 2026 | Team Wayfinders  |  Dev B task 1

WHY THIS EXISTS
    `route_load.load_factor_peak_pct` was  daily_boardings / (trips_per_day * seats).
    That is an UPPER BOUND: it silently assumes every passenger rides the whole
    route. It is not a peak, and the label was wrong. A route-average upper bound
    of 89.5% tells a planner nothing about where the bus is full.

    This script distributes each route's measured daily boardings across that
    route's own stops, then walks the stop order accumulating on-minus-off to get
    a load for every stop-to-stop SEGMENT. A peak segment can honestly exceed
    100% while the route-day average is 45%.

METHOD (every choice is a column in the output, so it can be audited)
    Demand level    MTCC `bus_daily` 2025, Saturday service day  (observed)
    Demand shape    Avas taxi OD, Aug-Sep 2026, by hour of day   (revealed preference)
    Geography       official RTL 2026 stop list with lat/lon     (observed)
    Supply          official RTL 2026 departures per hour        (observed)

    1. Snap each Avas ride's ORIGIN to the nearest stop on the route's own stop
       list, within CATCHMENT_M. Same for DESTINATION. A ride that cannot be
       snapped at both ends is not evidence about this route and is dropped.
    2. Boardings at stop i  = rides whose origin snapped to i.
       Alightings at stop j = rides whose destination snapped to j.
       Alighting is therefore MEASURED from taxi destinations, not assumed
       symmetric to boardings.
    3. Scale the snapped ride counts so total boardings = the MTCC observed
       daily total for that route. The scale factor is reported, never hidden.
    4. Walk the stop order: a rider boarding at order i and alighting at order j
       loads every segment from i to j-1. On a closed circuit the path wraps.

ASSUMPTIONS THAT ARE *NOT* FREE — stated because they move the answer
    A. CATCHMENT_M = 600 m. Rides further than this from any stop on the route
       are excluded rather than force-assigned. Sensitivity at 400/600/800 m is
       written to segment_load_sensitivity.csv.
    B. A route whose first and last stop are within CLOSED_CIRCUIT_M (400 m) is
       treated as a circuit, so a trip from a late stop to an early one wraps.
       Routes whose terminals are genuinely far apart (R5/R6/R9, 781 m) are open:
       a backward ride is dropped and counted in `rides_dropped_backtrack`.
    C. Avas covers Malé, Hulhumalé and the airport. It does NOT cover Villimalé
       (no pickup east of 73.495), so R13/R14 cannot be allocated from it. They
       emit nulls, not zeros.
    D. Only R1, R2, R3, R4, R7 have a measured ridership level. The other ten
       routes get catchment counts and segment SHARES but a NULL level — the
       pipeline never invents a ridership number and never zero-fills.

KNOWN LIMITATION (inherited, unfixed here)
    The RTL feed is time-filtered from the moment of capture, so departures are
    only observed 11:00-24:00. Demand is known for all 24 hours, but capacity is
    not. Hours before the capture window carry `capacity_basis = "not_captured"`
    and a NULL load factor. Null is not zero.

OUTPUTS (dashboard/data/)
    demand_by_stop.csv          boardings + alightings per stop, daily and by hour
    load_by_segment.csv         passengers and load factor per segment per hour
    route_load.csv              UPDATED: segment-based peak replaces the old bound
    demand_supply_gap.csv       UPDATED: demand from stop allocation, not corridor shape
    segment_load_sensitivity.csv  peak segment load factor at 400/600/800 m
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "dashboard" / "data"

CATCHMENT_M = 600.0
SENSITIVITY_M = (400.0, 600.0, 800.0)
CLOSED_CIRCUIT_M = 400.0
EARTH_M = 6_371_000.0

# The service day the RTL feed was captured on. Demand level must match it.
SERVICE_DAYTYPE = "sat_holiday"
SERVICE_DAY_LABEL = "Saturday"

# MTCC gives a measured level for these only. Everything else stays null.
ROUTES_WITH_LEVEL = {"R1", "R2", "R3", "R4", "R7"}


# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres. Accepts scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_M * np.arcsin(np.sqrt(a))


def load_rides(day_name: str | None = None) -> pd.DataFrame:
    """Avas rides, filtered to completed trips, with the hour of day kept.

    `ride_expired` is excluded: the ride was requested but never paid for or
    delivered, so it is not evidence that anyone actually travelled.

    When `day_name` is given the rides are restricted to that weekday, so the
    demand SHAPE matches the service day whose ridership level we scale to.
    Mixing a weekday shape with a Saturday level would be an unforced error.
    """
    r = pd.read_csv(RAW / "avas_rides_aug_sep_2026.csv")
    before = len(r)
    r = r[r["status"] != "ride_expired"].copy()
    r["ts"] = pd.to_datetime(r["date_started"])
    r["hour"] = r["ts"].dt.hour
    r["dow"] = r["ts"].dt.day_name()
    kept = len(r)
    if day_name is not None:
        r = r[r["dow"] == day_name].copy()
    r.attrs["rows_in"] = before
    r.attrs["rows_kept"] = kept
    r.attrs["days"] = int(r["ts"].dt.date.nunique()) or 1
    return r


def classify_routes(stops: pd.DataFrame) -> pd.DataFrame:
    """Closed circuit vs open route, from the distance between its terminals."""
    rows = []
    for code, d in stops.groupby("route_code"):
        d = d.sort_values("stop_order")
        first, last = d.iloc[0], d.iloc[-1]
        gap = float(haversine(first.lat, first.lon, last.lat, last.lon))
        rows.append(
            {
                "route_code": code,
                "n_stops": len(d),
                "terminal_gap_m": round(gap, 1),
                "topology": "closed_circuit" if gap < CLOSED_CIRCUIT_M else "open",
            }
        )
    return pd.DataFrame(rows)


def snap(rides: pd.DataFrame, stops: pd.DataFrame, radius: float) -> pd.DataFrame:
    """Attach nearest origin and destination stop to every ride.

    Both ends must land within `radius`, and they must be different stops. A ride
    that starts and ends at the same stop is an intra-stop trip: it never enters
    a segment, so it carries no load and is dropped.
    """
    lat = stops["lat"].to_numpy()
    lon = stops["lon"].to_numpy()
    order = stops["stop_order"].to_numpy()

    def nearest(plat, plon):
        d = haversine(plat[:, None], plon[:, None], lat[None, :], lon[None, :])
        idx = d.argmin(axis=1)
        return order[idx], d[np.arange(len(plat)), idx]

    o_order, o_dist = nearest(rides["pickup_lat"].to_numpy(), rides["pickup_lng"].to_numpy())
    d_order, d_dist = nearest(rides["dropoff_lat"].to_numpy(), rides["dropoff_lng"].to_numpy())

    out = rides.copy()
    out["o_order"] = o_order
    out["d_order"] = d_order
    out["o_dist_m"] = o_dist
    out["d_dist_m"] = d_dist
    out["o_ok"] = o_dist <= radius
    out["d_ok"] = d_dist <= radius
    return out


def segment_path(o: int, d: int, n_stops: int, closed: bool) -> list[int]:
    """0-based segment indices traversed from stop order `o` to stop order `d`.

    Stop orders are 1-based in the RTL feed; segments are 0-based, with segment k
    joining stop k to stop k+1. On a closed circuit the final segment closes the
    loop, so there are n segments; on an open route there are n-1.
    """
    o0, d0 = o - 1, d - 1
    if o0 == d0:
        return []
    n_seg = n_stops if closed else n_stops - 1
    if closed:
        span = (d0 - o0) % n_stops
        return [(o0 + k) % n_seg for k in range(span)]
    if d0 > o0:
        return list(range(o0, d0))
    return []  # backward ride on an open route: cannot be served in this direction


def allocate(stops: pd.DataFrame, snapped: pd.DataFrame, closed: bool):
    """Return per-stop boardings/alightings and per-hour segment loads.

    Takes an already-snapped frame so the distance matrix is computed once per
    (route, radius) rather than once per call. Loads are in *rides* until scaled;
    the caller applies the MTCC factor.
    """
    usable = snapped[snapped["o_ok"] & snapped["d_ok"] & (snapped["o_order"] != snapped["d_order"])]

    n_stops = len(stops)
    order_to_idx = {int(o): i for i, o in enumerate(stops["stop_order"])}

    n_seg = n_stops if closed else n_stops - 1
    # segment x hour  ->  passenger trips traversing it
    seg_hour = np.zeros((n_seg, 24), dtype=float)
    board_hour = np.zeros((n_stops, 24), dtype=float)
    alight_hour = np.zeros((n_stops, 24), dtype=float)

    dropped_back = 0
    for row in usable.itertuples():
        o, d = int(row.o_order), int(row.d_order)
        path = segment_path(o, d, n_stops, closed)
        if not path:
            dropped_back += 1
            continue
        hi = int(row.hour)
        board_hour[order_to_idx[o], hi] += 1
        alight_hour[order_to_idx[d], hi] += 1
        for seg in path:
            seg_hour[seg, hi] += 1

    stats = {
        "rides_considered": int(len(snapped)),
        "rides_in_catchment": int(len(usable)),
        "rides_dropped_backtrack": dropped_back,
        "catchment_share_pct": round(100 * len(usable) / len(snapped), 1) if len(snapped) else 0.0,
    }
    return board_hour, alight_hour, seg_hour, stats


# ---------------------------------------------------------------------------
def main() -> None:
    stops_all = pd.read_csv(OUT / "route_stops.csv")
    master = pd.read_csv(OUT / "routes_master.csv")
    demand = pd.read_csv(OUT / "demand_by_daytype.csv")
    hourly = pd.read_csv(OUT / "route_service_by_hour.csv")

    rides = load_rides(SERVICE_DAY_LABEL)
    n_days = rides.attrs["days"]
    topology = classify_routes(stops_all)
    topo = topology.set_index("route_code")["topology"].to_dict()

    level = (
        demand[demand["day_type"] == SERVICE_DAYTYPE]
        .set_index("route_code")["boardings_per_day"]
        .to_dict()
    )

    h = hourly.set_index(["route_code", "hour"])

    stop_rows, seg_rows, sens_rows = [], [], []
    route_summary: dict[str, dict] = {}
    gap_demand: dict[tuple[str, int], float] = {}

    for r in master.itertuples():
        code = r.route_code
        stops = stops_all[stops_all["route_code"] == code].sort_values("stop_order").reset_index(drop=True)
        if stops.empty:
            continue
        closed = topo.get(code) == "closed_circuit"
        seats = int(getattr(r, "seated_capacity", getattr(r, "seats", 0)))
        has_level = code in ROUTES_WITH_LEVEL and code in level
        daily_target = float(level[code]) if has_level else np.nan

        # Snapping is the expensive step: do it once per radius, not per call.
        snapped_by_radius = {rad: snap(rides, stops, rad) for rad in SENSITIVITY_M}
        primary = snapped_by_radius[CATCHMENT_M]

        board_h, alight_h, seg_h, stats = allocate(stops, primary, closed)
        # Convert pooled multi-day counts to a per-day average, so the scale
        # factor below is interpretable as "bus boardings / observed taxi trips".
        board_h, alight_h, seg_h = board_h / n_days, alight_h / n_days, seg_h / n_days

        raw_total = float(board_h.sum())
        scale = daily_target / raw_total if (has_level and raw_total > 0) else np.nan

        board_d = board_h.sum(axis=1) * scale if has_level else np.full(len(stops), np.nan)
        alight_d = alight_h.sum(axis=1) * scale if has_level else np.full(len(stops), np.nan)

        share = board_h.sum(axis=1) / raw_total * 100 if raw_total > 0 else np.zeros(len(stops))

        for i, st in stops.iterrows():
            stop_rows.append(
                {
                    "route_code": code,
                    "stop_order": int(st.stop_order),
                    "stop_code": int(st.stop_code),
                    "stop_name": st.stop_name,
                    "lat": st.lat,
                    "lon": st.lon,
                    "daily_boardings": round(float(board_d[i]), 1) if has_level else None,
                    "daily_alightings": round(float(alight_d[i]), 1) if has_level else None,
                    "avas_rides_per_day": round(float(board_h[i].sum()), 1),
                    "boarding_share_pct": round(float(share[i]), 2),
                    "stop_role": "interchange" if float(share[i]) >= 10 else "",
                    "method": (
                        "Avas OD snapped to stop, scaled to MTCC daily total"
                        if has_level
                        else "Avas OD snapped to stop (no ridership level available)"
                    ),
                    "demand_source": "MTCC bus_daily 2025 Saturday" if has_level else "NO DEMAND DATA",
                    "catchment_m": CATCHMENT_M,
                }
            )

        # Capacity per hour from the captured service.
        cap_hour = {}
        basis_hour = {}
        for hour in range(24):
            key = (code, hour)
            if key in h.index and bool(h.loc[key, "captured"]):
                trips = float(h.loc[key, "departures"])
                cap_hour[hour] = trips * seats
                basis_hour[hour] = "observed"
            else:
                cap_hour[hour] = np.nan
                basis_hour[hour] = "not_captured"

        n_seg = len(seg_h)
        seg_loads = []
        for seg in range(n_seg):
            a = stops.iloc[seg]
            b = stops.iloc[(seg + 1) % len(stops)]
            seg_len = float(haversine(a.lat, a.lon, b.lat, b.lon))
            for hour in range(24):
                pax = seg_h[seg, hour] * scale if has_level else np.nan
                cap = cap_hour[hour]
                lf = (
                    round(pax / cap * 100, 1)
                    if (has_level and not np.isnan(cap) and cap > 0)
                    else None
                )
                seg_rows.append(
                    {
                        "route_code": code,
                        "segment_id": f"{code}-S{seg + 1:02d}",
                        "from_stop_order": int(a.stop_order),
                        "from_stop": a.stop_name,
                        "to_stop_order": int(b.stop_order),
                        "to_stop": b.stop_name,
                        "segment_km": round(seg_len / 1000, 3),
                        "hour": hour,
                        "passengers": round(float(pax), 1) if has_level else None,
                        "seated_capacity_hour": cap if not np.isnan(cap) else None,
                        "load_factor_pct": lf,
                        "capacity_basis": basis_hour[hour],
                        "demand_source": "stop-allocated MTCC level x Avas OD" if has_level else "NO DEMAND DATA",
                    }
                )
                if lf is not None:
                    seg_loads.append((lf, hour, seg, pax, cap))

        if has_level:
            # Demand by hour for the gap table comes from the same allocation, so
            # the two files cannot disagree.
            for hour in range(24):
                gap_demand[(code, hour)] = float(board_h[:, hour].sum() * scale)

            peak_lf, peak_hour, peak_seg, peak_pax, peak_cap = max(seg_loads)
            a = stops.iloc[peak_seg]
            b = stops.iloc[(peak_seg + 1) % len(stops)]

            # The max load factor often lands at a late hour where service has
            # thinned to one or two trips, not where demand is highest. Report the
            # demand peak separately so the headline cannot be read as
            # "the busiest hour is 22:00".
            hourly_board = board_h.sum(axis=0) * scale
            demand_peak_hour = int(np.argmax(hourly_board))
            at_peak = [x for x in seg_loads if x[1] == demand_peak_hour]
            peak_at_demand = max(at_peak)[0] if at_peak else None

            route_day_upper = (
                daily_target / (float(r.trips_per_day) * seats) * 100
                if r.trips_per_day and not np.isnan(r.trips_per_day)
                else np.nan
            )
            route_summary[code] = {
                "peak_segment_id": f"{code}-S{peak_seg + 1:02d}",
                "peak_segment_from": a.stop_name,
                "peak_segment_to": b.stop_name,
                "peak_segment_hour": peak_hour,
                "peak_segment_passengers": round(float(peak_pax), 1),
                "peak_segment_capacity": float(peak_cap),
                "load_factor_segment_peak_pct": peak_lf,
                "demand_peak_hour": demand_peak_hour,
                "load_factor_at_demand_peak_pct": peak_at_demand,
                "load_factor_segment_mean_pct": round(float(np.mean([x[0] for x in seg_loads])), 1),
                "load_factor_route_day_upper_pct": round(float(route_day_upper), 1),
                "scale_factor": round(float(scale), 4),
                **stats,
            }
        else:
            route_summary[code] = {
                "peak_segment_id": None,
                "peak_segment_from": None,
                "peak_segment_to": None,
                "peak_segment_hour": None,
                "load_factor_segment_peak_pct": None,
                "load_factor_segment_mean_pct": None,
                "load_factor_route_day_upper_pct": None,
                "demand_peak_hour": None,
                "load_factor_at_demand_peak_pct": None,
                "scale_factor": None,
                **stats,
            }

        # CATCHMENT SENSITIVITY: does the headline peak move with the radius?
        for rad in SENSITIVITY_M:
            b_h, _, s_h, _st = allocate(stops, snapped_by_radius[rad], closed)
            b_h, s_h = b_h / n_days, s_h / n_days
            raw = float(b_h.sum())
            sc = daily_target / raw if (has_level and raw > 0) else np.nan
            peaks = []
            for seg in range(len(s_h)):
                for hour in range(24):
                    cap = cap_hour[hour]
                    if has_level and not np.isnan(cap) and cap > 0:
                        peaks.append(float(s_h[seg, hour]) * sc / cap * 100)
            sens_rows.append(
                {
                    "route_code": code,
                    "catchment_m": rad,
                    "topology": "closed_circuit" if closed else "open",
                    "rides_in_catchment": int(
                        (snapped_by_radius[rad]["o_ok"] & snapped_by_radius[rad]["d_ok"]).sum()
                    ),
                    "peak_segment_load_pct": round(max(peaks), 1) if peaks else None,
                }
            )

    demand_stops = pd.DataFrame(stop_rows)
    segments = pd.DataFrame(seg_rows)
    sens = pd.DataFrame(sens_rows)

    demand_stops.to_csv(OUT / "demand_by_stop.csv", index=False)
    segments.to_csv(OUT / "load_by_segment.csv", index=False)
    sens.to_csv(OUT / "segment_load_sensitivity.csv", index=False)

    # ---- write route_load.csv: the base table plus the segment truth ----
    # This is the ONLY writer of route_load.csv. It reads route_load_base.csv
    # (written by build_data.py) rather than its own previous output, so
    # re-running is idempotent and build_data.py running alone can no longer
    # clobber the refined file.
    load = pd.read_csv(OUT / "route_load_base.csv")
    summary = pd.DataFrame.from_dict(route_summary, orient="index").rename_axis("route_code").reset_index()
    summary.to_csv(OUT / "route_segment_summary.csv", index=False)

    s_idx = summary.set_index("route_code")
    load["load_factor_route_day_upper_pct"] = load["route_code"].map(s_idx["load_factor_route_day_upper_pct"])
    load["peak_segment_id"] = load["route_code"].map(s_idx["peak_segment_id"])
    load["peak_segment"] = [
        f"{s_idx.loc[c, 'peak_segment_from']} \u2192 {s_idx.loc[c, 'peak_segment_to']}"
        if isinstance(s_idx.loc[c, "peak_segment_id"], str)
        else None
        for c in load["route_code"]
    ]
    load["peak_segment_hour"] = load["route_code"].map(s_idx["peak_segment_hour"])
    load["load_factor_peak_pct"] = load["route_code"].map(s_idx["load_factor_segment_peak_pct"])
    load["load_factor_avg_pct"] = load["route_code"].map(s_idx["load_factor_segment_mean_pct"])
    load.to_csv(OUT / "route_load.csv", index=False)

    # ---- update demand_supply_gap.csv so both files agree by construction ----
    gap = pd.read_csv(OUT / "demand_supply_gap_base.csv")
    gap["demand_pax_est_stop_allocated"] = [
        round(gap_demand.get((c, hh), np.nan), 1) if (c, hh) in gap_demand else None
        for c, hh in zip(gap["route_code"], gap["hour"])
    ]
    replaces = gap["demand_pax_est_stop_allocated"].notna()
    gap.loc[replaces, "demand_pax_est"] = gap.loc[replaces, "demand_pax_est_stop_allocated"]
    gap.loc[replaces, "demand_source"] = "MTCC level x Avas OD, stop-allocated"
    gap["load_factor_pct"] = [
        round(d / c * 100, 1) if (d is not None and not pd.isna(d) and c and not pd.isna(c)) else None
        for d, c in zip(gap["demand_pax_est"], gap["seated_capacity_hour"])
    ]
    gap["unmet_pax_est"] = [
        round(max(0.0, d - c), 1) if (d is not None and not pd.isna(d) and c and not pd.isna(c)) else None
        for d, c in zip(gap["demand_pax_est"], gap["seated_capacity_hour"])
    ]
    gap.drop(columns=["demand_pax_est_stop_allocated"]).to_csv(OUT / "demand_supply_gap.csv", index=False)

    # Scenarios were computed by build_data.py on the corridor-shape demand this
    # script has just replaced. Recompute them on the stop-allocated demand so
    # the scenario KPIs and demand_supply_gap.csv cannot disagree.
    spec = importlib.util.spec_from_file_location(
        "build_data", pathlib.Path(__file__).resolve().parent / "build_data.py"
    )
    build_data = importlib.util.module_from_spec(spec)
    sys.modules["build_data"] = build_data
    spec.loader.exec_module(build_data)
    kpis_s, corr_s, moves_s = build_data.build_scenarios(
        pd.read_csv(OUT / "demand_supply_gap.csv"))
    kpis_s.to_csv(OUT / "scenario_kpis.csv", index=False)
    corr_s.to_csv(OUT / "scenario_corridor_kpis.csv", index=False)
    moves_s.to_csv(OUT / "scenario_moves.csv", index=False)

    # ---- report ----
    pd.set_option("display.width", 220)
    print("=" * 110)
    print(f"STOP-LEVEL DEMAND ALLOCATION  (catchment {CATCHMENT_M:.0f} m, {SERVICE_DAY_LABEL} service day)")
    print("=" * 110)
    print(f"Avas rides in      : {rides.attrs['rows_in']:,}")
    print(f"Avas rides kept    : {rides.attrs['rows_kept']:,}  (ride_expired excluded)")
    print(f"Villimale coverage : {int((rides['pickup_lng'] < 73.495).sum())} rides  -> R13/R14 cannot be allocated")
    print()
    print(topology.to_string(index=False))
    print()
    print("=" * 110)
    print("PEAK SEGMENT vs ROUTE-DAY UPPER BOUND  (the reconciliation)")
    print("=" * 110)
    cols = ["route_code", "load_factor_route_day_upper_pct", "load_factor_segment_peak_pct",
            "peak_segment_id", "peak_segment_from", "peak_segment_to", "peak_segment_hour",
            "peak_segment_passengers", "peak_segment_capacity",
            "load_factor_segment_mean_pct", "scale_factor"]
    print(summary[summary["peak_segment_id"].notna()][cols].to_string(index=False))
    print()
    print("=" * 110)
    print("CATCHMENT SENSITIVITY")
    print("=" * 110)
    print(sens.pivot_table(index="route_code", columns="catchment_m",
                           values="peak_segment_load_pct").to_string())
    print()
    print(f"wrote {OUT/'demand_by_stop.csv'}          ({len(demand_stops)} rows)")
    print(f"wrote {OUT/'load_by_segment.csv'}         ({len(segments)} rows)")
    print(f"wrote {OUT/'route_segment_summary.csv'}   ({len(summary)} rows)")
    print(f"wrote {OUT/'segment_load_sensitivity.csv'} ({len(sens)} rows)")


if __name__ == "__main__":
    main()
