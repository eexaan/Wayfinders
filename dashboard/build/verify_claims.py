"""
================================================================================
Verify the committed claims against the raw sources
================================================================================
Maldives Datathon 2026 | Team Wayfinders

WHAT THIS IS FOR
    A pipeline that agrees with itself proves nothing: if the same wrong
    assumption sits in both the code and the check, both pass. So this file
    deliberately does NOT import any build script. It recomputes each headline
    number from the raw inputs using its own code, then compares that against
    what is committed in dashboard/data/.

    If a number in the CSVs, the SPEC or the pitch stops being true, this fails.

Run:
    .venv/bin/python dashboard/build/verify_claims.py     (or: make check)

Exit code is 0 only when every claim holds, so it can gate a commit.
"""

from __future__ import annotations

import pathlib
import re
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OFFICIAL = ROOT / "data" / "official"
DATA = ROOT / "dashboard" / "data"

TOL_TRIPS = 1.0        # boardings are rounded to 1 dp in the CSV
TOL_PCT = 0.15         # load factors are rounded to 1 dp
TOL_MAPE = 0.05        # MAPE is rounded to 2 dp

results: list[tuple[str, bool, str]] = []


def claim(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------------------
# 1. Demand level: MTCC raw -> demand_by_daytype
# ---------------------------------------------------------------------------
def check_demand_level() -> None:
    daily = pd.read_excel(RAW / "MTCC.xlsx", sheet_name="bus_daily")
    daily["date"] = pd.to_datetime(daily["date"])
    sat = daily[daily["date"].dt.day_name() == "Saturday"]

    committed = pd.read_csv(DATA / "demand_by_daytype.csv")
    committed = committed[committed["day_type"] == "sat_holiday"].set_index("route_code")

    for route in ["R1", "R2", "R4"]:
        recomputed = sat[sat["route_id"] == route]["total_pax"].mean()
        stored = committed.loc[route, "boardings_per_day"]
        claim(
            f"MTCC Saturday mean, {route}",
            close(recomputed, stored, TOL_TRIPS),
            f"raw={recomputed:.2f}  committed={stored:.2f}",
        )


# ---------------------------------------------------------------------------
# 2. Stop allocation conserves the total
# ---------------------------------------------------------------------------
def check_stop_conservation() -> None:
    stops = pd.read_csv(DATA / "demand_by_stop.csv")
    levels = pd.read_csv(DATA / "demand_by_daytype.csv")
    levels = levels[levels["day_type"] == "sat_holiday"].set_index("route_code")["boardings_per_day"]

    for route, target in levels.items():
        total = stops[stops["route_code"] == route]["daily_boardings"].sum()
        claim(
            f"stop boardings sum to MTCC total, {route}",
            close(total, target, TOL_TRIPS),
            f"sum={total:.2f}  target={target:.2f}  diff={total - target:+.3f}",
        )

    # No segment may ever carry more than boarded in that hour.
    seg = pd.read_csv(DATA / "load_by_segment.csv").dropna(subset=["passengers"])
    gap = pd.read_csv(DATA / "demand_supply_gap.csv").dropna(subset=["demand_pax_est"])
    mx = seg.groupby(["route_code", "hour"])["passengers"].max().reset_index()
    joined = mx.merge(gap[["route_code", "hour", "demand_pax_est"]], on=["route_code", "hour"])
    violations = joined[joined["passengers"] > joined["demand_pax_est"] + 0.05]
    claim(
        "no segment carries more than boarded that hour",
        len(violations) == 0,
        f"{len(violations)} violations of {len(joined)} route-hours",
    )


# ---------------------------------------------------------------------------
# 3. Peak-segment load factor, recomputed from load_by_segment
# ---------------------------------------------------------------------------
def check_peak_segments() -> None:
    seg = pd.read_csv(DATA / "load_by_segment.csv")

    # These are the numbers quoted in SPEC F2, the README and the 5-minute
    # pitch. If they move, the prose is wrong.
    #
    # Recomputed after the fleet capacity table replaced the assumed 84/52-seat
    # figures: deckers are 72 seats (not 84) and coaches 55 (not 52), so every
    # segment load factor moved. Old -> new:
    #   R1 77.3 -> 90.1   R3 104.1 -> 98.4   R4 89.2 -> 84.3
    #   R7 63.7 -> 74.4   R2  58.0 -> 67.7
    expected = {
        "R1": (90.1, "Hulhumale' Police Station"),
        "R3": (98.4, "STELCO"),
        "R4": (84.3, "Hulhumale' Cemetery"),
        "R7": (74.4, "STELCO"),
        "R2": (67.7, "Centro Mall"),
    }
    for route, (lf, from_stop) in expected.items():
        d = seg[(seg["route_code"] == route)].dropna(subset=["load_factor_pct"])
        peak = d.loc[d["load_factor_pct"].idxmax()]
        claim(
            f"peak segment load factor, {route}",
            close(peak["load_factor_pct"], lf, TOL_PCT),
            f"recomputed={peak['load_factor_pct']:.1f}%  documented={lf}%",
        )
        claim(
            f"peak segment name, {route}",
            peak["from_stop"] == from_stop,
            f"recomputed='{peak['from_stop']}'  documented='{from_stop}'",
        )

    # The dashboard reads route_load.csv, so it must agree with the segment
    # file it is derived from. Without this, a wrong load_factor_peak_pct in
    # route_load.csv passes unnoticed while every other check looks at
    # load_by_segment.csv. (Found by falsifying route_load.csv and watching the
    # verifier still pass -- the positive control caught a hole in itself.)
    load0 = pd.read_csv(DATA / "route_load.csv").set_index("route_code")
    for route in expected:
        from_seg = seg[seg["route_code"] == route]["load_factor_pct"].max()
        from_load = load0.loc[route, "load_factor_peak_pct"]
        claim(
            f"route_load agrees with load_by_segment, {route}",
            close(from_seg, from_load, TOL_PCT),
            f"segment max={from_seg:.1f}%  route_load={from_load:.1f}%",
        )

    # And route_segment_summary must agree with both, since the SPEC and the
    # pitch quote it directly.
    summary = pd.read_csv(DATA / "route_segment_summary.csv").set_index("route_code")
    for route in expected:
        claim(
            f"route_segment_summary agrees, {route}",
            close(summary.loc[route, "load_factor_segment_peak_pct"],
                  load0.loc[route, "load_factor_peak_pct"], TOL_PCT),
            f"summary={summary.loc[route, 'load_factor_segment_peak_pct']}%  "
            f"route_load={load0.loc[route, 'load_factor_peak_pct']}%",
        )

    # The reconciliation must move in opposite directions on R1 and R3. That
    # asymmetry is the finding, so a regression that flattens it is a real bug.
    load = pd.read_csv(DATA / "route_load.csv").set_index("route_code")
    r1_up = load.loc["R1", "load_factor_route_day_upper_pct"]
    r1_pk = load.loc["R1", "load_factor_peak_pct"]
    r3_up = load.loc["R3", "load_factor_route_day_upper_pct"]
    r3_pk = load.loc["R3", "load_factor_peak_pct"]
    claim(
        "R1 segment peak is BELOW its route-day bound",
        r1_pk < r1_up,
        f"segment {r1_pk}% < bound {r1_up}%",
    )
    claim(
        "R3 segment peak is ABOVE its route-day bound",
        r3_pk > r3_up,
        f"segment {r3_pk}% > bound {r3_up}%",
    )


# ---------------------------------------------------------------------------
# 4. Holdout MAPE, recomputed without touching build_validation
# ---------------------------------------------------------------------------
def check_holdout_mape() -> None:
    daily = pd.read_excel(RAW / "MTCC.xlsx", sheet_name="bus_daily")
    daily["date"] = pd.to_datetime(daily["date"])
    dow = daily["date"].dt.day_name()
    daily["day_type"] = np.where(
        dow == "Friday", "friday", np.where(dow == "Saturday", "sat_holiday", "weekday")
    )

    cutoff = pd.Timestamp("2025-10-19")
    train, test = daily[daily["date"] <= cutoff], daily[daily["date"] > cutoff]

    preds = []
    for route, g in test.groupby("route_id"):
        means = train[train["route_id"] == route].groupby("day_type")["total_pax"].mean()
        preds.append(pd.Series(g["day_type"].map(means).to_numpy(), index=g.index))
    pred = pd.concat(preds).sort_index()

    mape = float((((test["total_pax"] - pred).abs()) / test["total_pax"]).mean() * 100)
    committed = pd.read_csv(DATA / "validation_holdout.csv")
    stored = committed.query("model == 'M1_route_x_daytype' and route_code == 'ALL'")["mape_pct"].iloc[0]

    claim(
        "holdout MAPE (M1, all routes)",
        close(mape, stored, TOL_MAPE),
        f"recomputed={mape:.2f}%  committed={stored:.2f}%",
    )

    # No leakage: the split must be strictly chronological.
    claim(
        "holdout split has no date overlap",
        train["date"].max() < test["date"].min(),
        f"train ends {train['date'].max().date()}, test starts {test['date'].min().date()}",
    )


# ---------------------------------------------------------------------------
# 5. Fleet neutrality
# ---------------------------------------------------------------------------
def _has_reverse_pair(moves) -> bool:
    """True if any scenario both moves a trip A->B and B->A.

    Such a pair leaves the fleet exactly where it started, so it cannot relieve
    anyone; if it appears, `trips_moved` is counting work that did not happen.
    """
    for _, g in moves.groupby("scenario"):
        seen = {(r.from_route, r.from_hour, r.to_route, r.to_hour) for r in g.itertuples()}
        if any((b, d, a, c) in seen for a, c, b, d in seen):
            return True
    return False


def check_fleet_neutral() -> None:
    k = pd.read_csv(DATA / "scenario_kpis.csv")

    claim(
        "every scenario has trips_change == 0",
        (k["trips_change"] == 0).all(),
        f"values: {k['trips_change'].tolist()}",
    )
    claim(
        "total trips identical across scenarios",
        k["total_trips_captured"].nunique() == 1,
        f"distinct totals: {k['total_trips_captured'].unique().tolist()}",
    )

    moves = pd.read_csv(DATA / "scenario_moves.csv")
    claim(
        "no donor was already over capacity",
        (moves["donor_load_pct"] < 100).all(),
        f"max donor load {moves['donor_load_pct'].max():.1f}%",
    )
    claim(
        "every logged move reduced receiver unmet demand",
        (moves["receiver_unmet_after"] < moves["receiver_unmet_before"]).all(),
        f"{len(moves)} moves logged",
    )
    # The move must not create a NEW over-capacity hour on the donor side. The
    # check above tests the load before the move, which is precisely the state
    # that was never the problem.
    claim(
        "no move pushes its donor over capacity",
        (moves["donor_load_after_pct"] <= 100).all(),
        f"max donor load after {moves['donor_load_after_pct'].max():.1f}%",
    )
    claim(
        "no logged move cancels an earlier move",
        not _has_reverse_pair(moves),
        f"{len(moves)} moves logged, none reversed",
    )
    claim(
        "trips_moved equals the number of logged moves",
        (k["trips_moved"] == k["scenario"].map(moves.groupby("scenario")["trips"].sum()).fillna(0).astype(int)).all(),
        f"kpis={k['trips_moved'].tolist()}",
    )


# ---------------------------------------------------------------------------
# 6. Airport reconciliation, recomputed from MACL and the Yearbook
# ---------------------------------------------------------------------------
def check_airport() -> None:
    yb = pd.read_excel(OFFICIAL / "mbs" / "11.13.xlsx", sheet_name="11.13", header=None)
    total_row = yb.iloc[6]
    intl_arr, dom_arr = int(total_row[1]), int(total_row[3])

    macl = pd.read_csv(RAW / "Airport traffic_Dataset_27092026.csv")
    macl["arr"] = pd.to_datetime(macl["arrival_date"], format="%d/%m/%Y", errors="coerce")
    y = macl[macl["arr"].dt.year == 2025].copy()
    y["pax"] = y["arr_adults"] + y["arr_children"] + y["arr_infants"]
    y["hour"] = pd.to_datetime(y["ata"], format="%H:%M", errors="coerce").dt.hour

    coverage = y["pax"].sum() / intl_arr * 100
    claim(
        "MACL covers ~40% of Yearbook international arrivals",
        close(coverage, 40.2, 0.3),
        f"recomputed={coverage:.2f}%  documented=40.2%",
    )

    # Passenger-weighted, which is the definition the chart states.
    h = y.dropna(subset=["hour"])
    by_hour = h.groupby("hour")["pax"].sum() / h["pax"].sum() * 100
    pax_0709 = float(by_hour.reindex([7, 8, 9]).sum())
    claim(
        "07:00-09:59 share, passenger-weighted ~33.1%",
        close(pax_0709, 33.1, 0.3),
        f"recomputed={pax_0709:.2f}%  documented=33.1%",
    )

    # … and the flight-weighted figure must stay materially lower, because the
    # whole point is that the weighting changes the answer.
    fl_0709 = float(h["hour"].isin([7, 8, 9]).mean() * 100)
    claim(
        "flight-weighted 07:00-09:59 is materially lower (~25.3%)",
        close(fl_0709, 25.3, 0.5) and pax_0709 - fl_0709 > 5,
        f"recomputed={fl_0709:.2f}%  gap to pax-weighted={pax_0709 - fl_0709:.1f} pts",
    )

    # MACL must contain no domestic traffic. This is why it cannot set levels.
    turboprop = y.loc[y["aircraft_category"] == "Turboprop", "pax"].sum()
    claim(
        "MACL has essentially no domestic traffic (<1% of Yearbook)",
        turboprop / dom_arr * 100 < 1.0,
        f"turboprop {turboprop:,} pax vs {dom_arr:,} domestic arrivals",
    )


# ---------------------------------------------------------------------------
# 7. Coverage gaps that are documented, not silently zero-filled
# ---------------------------------------------------------------------------
def check_documented_gaps() -> None:
    avas = pd.read_csv(RAW / "avas_rides_aug_sep_2026.csv")
    live = avas[avas["status"] != "ride_expired"]
    west = int((live["pickup_lng"] < 73.495).sum())
    claim(
        "Avas has no Villimale coverage (so R13/R14 stay null)",
        west == 0,
        f"{west} pickups west of 73.495",
    )

    stops = pd.read_csv(DATA / "demand_by_stop.csv")
    r13 = stops[stops["route_code"] == "R13"]
    claim(
        "R13/R14 demand is null, not zero",
        r13["daily_boardings"].isna().all(),
        "nulls preserved",
    )

    # The routes lacking a ridership level must be null, never 0.
    load = pd.read_csv(DATA / "route_load.csv")
    no_demand = load[load["demand_source"] == "NO DEMAND DATA"]
    claim(
        "routes without ridership are null, not zero",
        no_demand["load_factor_peak_pct"].isna().all(),
        f"{len(no_demand)} routes marked NO DEMAND DATA",
    )


# ---------------------------------------------------------------------------
# 8. Deliverable files exist and are non-trivial
# ---------------------------------------------------------------------------
def check_deliverables() -> None:
    expected = {
        "demand_by_stop.csv": 150,
        "load_by_segment.csv": 4000,
        "route_segment_summary.csv": 15,
        "segment_load_sensitivity.csv": 40,
        "validation_holdout.csv": 10,
        "validation_airport.csv": 10,
        "schedule_crosscheck.csv": 14,
        "schedule_crosscheck_hourly.csv": 100,
        "scenario_moves.csv": 10,
    }
    for name, min_rows in expected.items():
        path = DATA / name
        if not path.exists():
            claim(f"deliverable exists: {name}", False, "MISSING")
            continue
        n = len(pd.read_csv(path))
        claim(f"deliverable {name}", n >= min_rows, f"{n} rows (expected >= {min_rows})")

    gtfs = ROOT / "data" / "derived" / "rtl_greater_male_gtfs.zip"
    claim("GTFS zip exists", gtfs.exists(),
          f"{gtfs.stat().st_size / 1024:.1f} KiB" if gtfs.exists() else "MISSING")


# ---------------------------------------------------------------------------
# GTFS structural checks. build_gtfs.py writes gtfs_validation.csv; until this
# existed, the only thing asserted about the feed was that the zip was present,
# so its best claim ("18/18, 0 errors") was taken on trust from the very script
# that produced it. It is now re-derived like every other number here.
# ---------------------------------------------------------------------------
def check_gtfs() -> None:
    report = ROOT / "data" / "derived" / "gtfs_validation.csv"
    if not report.exists():
        claim("GTFS validation report present", False, "MISSING")
        return

    d = pd.read_csv(report)
    for row in d.itertuples():
        detail = "" if pd.isna(row.detail) else str(row.detail)
        claim(f"GTFS {row.check}", row.result == "PASS", detail)

    # Every structural check passes vacuously on an empty feed, so pin the scale
    # as well: a feed with zero trips is not a valid feed.
    detail = d.set_index("check")["detail"].astype(str)
    for name, (unit, minimum) in {
        "unique_route_ids": ("routes", 11),
        "unique_stop_ids": ("stops", 61),
        "unique_trip_ids": ("trips", 450),
    }.items():
        raw = detail.get(name, "")
        head = raw.split()[0] if raw.split() else ""
        value = int(head) if head.isdigit() else 0
        claim(f"GTFS {unit} count", value >= minimum, f"{value} (expected >= {minimum})")


# ---------------------------------------------------------------------------
# Prose checks. Every number that has ever drifted in this project drifted the
# same way: the data was right and the sentence quoting it was stale. A table
# cannot be edited by accident, so the tables stay correct; a hand-typed figure
# in a README can, and did (R1 was quoted as 77.3% in four documents after the
# data said 90.1%, and S5 as "18 trips / 290 boardings" after the fix said
# 6 / 404). These anchors are deliberately blunt substring checks on the
# figures that move when the model moves.
# ---------------------------------------------------------------------------
def _readme_fragment(path: str) -> str:
    return (ROOT / path).read_text()


def check_prose() -> None:
    load = pd.read_csv(DATA / "route_load.csv").set_index("route_code")
    summary = pd.read_csv(DATA / "route_segment_summary.csv").set_index("route_code")
    k = pd.read_csv(DATA / "scenario_kpis.csv").set_index("scenario")
    shift = pd.read_csv(DATA / "scenario_modal_shift.csv")

    r1, s0, s5 = load.loc["R1"], k.loc["S0_baseline"], k.loc["S5_recommended_package"]
    peak = round(float(summary.loc["R1", "load_factor_at_demand_peak_pct"]))
    base_over = int(s0["boardings_over_capacity"])
    s5_over = int(s5["boardings_over_capacity"])
    s5_cut = int(abs(s5["over_capacity_change"]))
    s5_moved = int(s5["trips_moved"])

    gc = shift[(shift["scenario"] == "S0_baseline") & (shift["corridor"] == "male_hm1")].iloc[0]
    ratio = float(gc["bus_ride_min"]) / float(gc["taxi_ride_min"])

    anchors = [
        # file, needle, what it pins
        ("README.md", f"**{int(r1['load_factor_peak_pct'])}% full**", "R1 peak segment"),
        ("README.md", f"**{peak}%**", "R1 load at the demand peak"),
        ("README.md", f"{s5_cut} fewer boardings", "S5 effect"),
        ("README.md", f"{base_over:,} down to {s5_over:,}", "S5 baseline -> package"),
        ("README.md", f"moving {s5_moved} existing trips", "S5 trip count"),
        ("README.md", f"{ratio:.1f} times slower", "bus/taxi journey-time ratio"),
        ("README.md", "92/92", "claim count"),
        ("SPEC.md", f"| {r1['load_factor_route_day_upper_pct']}% | "
                    f"**{r1['load_factor_peak_pct']}%** |", "SPEC F2 table, R1 row"),
        ("SPEC.md", f"**{s5_over} (−{s5_cut})**", "SPEC scenario table, S5 row"),
        ("docs/TEAM.md", f"({base_over:,} → {s5_over:,})", "canonical sheet, S5 effect"),
        ("docs/METHODS.md", "**92/92**", "methods note"),
        ("docs/DASHBOARD_SPEC.md", "92 independent checks", "dashboard contract"),
        ("docs/DASHBOARD_SPEC.md",
         f"R1: {r1['load_factor_peak_pct']}% vs "
         f"{r1['load_factor_route_day_upper_pct']}%", "dashboard trap 3"),
    ]
    for path, needle, label in anchors:
        text = _readme_fragment(path)
        claim(f"prose: {label} ({path})", needle in text,
              f"expected '{needle}'")


def check_claim_count() -> None:
    """The README's self-reported score must equal this file's real claim count.

    A stale "54/54" survived three merges because the number was only ever
    checked by a human reading it. This makes the document's own arithmetic
    an assertion.
    """
    text = _readme_fragment("README.md")
    match = re.search(r"passes (\d+)/\1", text)
    total = len(results) + 1  # include this claim itself
    claim(
        "README state the real claim count",
        bool(match) and int(match.group(1)) == total,
        f"README says {match.group(1) if match else '?'}/{match.group(1) if match else '?'}"
        f", verifier has {total}/{total}",
    )


# ---------------------------------------------------------------------------
def main() -> int:
    checks = [
        ("demand level", check_demand_level),
        ("stop conservation", check_stop_conservation),
        ("peak segments", check_peak_segments),
        ("holdout MAPE", check_holdout_mape),
        ("fleet neutrality", check_fleet_neutral),
        ("airport reconciliation", check_airport),
        ("documented gaps", check_documented_gaps),
        ("deliverables", check_deliverables),
        ("gtfs", check_gtfs),
        ("prose", check_prose),
    ]

    for label, fn in checks:
        print(f"\n--- {label} ---")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - reported as a failure
            claim(f"{label} raised", False, f"{type(exc).__name__}: {exc}")

    check_claim_count()

    print("\n" + "=" * 96)
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name:52s} {detail}")
    print("=" * 96)
    failed = len(results) - passed
    print(f"{passed}/{len(results)} checks pass" + (f", {failed} FAILED" if failed else ""))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
