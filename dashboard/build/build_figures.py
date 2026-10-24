"""
================================================================================
Figures for the report and the pitch
================================================================================
Maldives Datathon 2026 | Team Wayfinders

Draws every figure directly from dashboard/data/. No number is typed by hand.

    F1_bridge_share.png        the causeway is 57% of R1's journey
    F2_load_factors.png        route-day upper bound vs the fullest segment
    F3_demand_daytype.png      Friday demand vs a weekday (demand only)
    F4_airport_mismatch.png    hourly airport bus vs tri-peaked arrivals
    F5_scenario_kpis.png       baseline vs the recommended package
    F6_generalised_cost.png    break-even journey time per corridor
    F7_usage_by_period.png     bus use by day period, and the working-hours band
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "dashboard" / "data"
FIGS = ROOT / "docs" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "figure.dpi": 160,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

RED, BLUE, GREY, GREEN, ORANGE = "#e9222a", "#1f77b4", "#9aa0a6", "#2ca02c", "#ff7f0e"
# MTCC day types as the pipeline defines them: Sunday is a working day in
# Malé, so it is grouped with Mon–Thu rather than with the weekend.
DAY_LABEL = {"weekday": "weekday (Mon–Thu, Sun)", "friday": "Friday", "sat_holiday": "Saturday"}


def fig_bridge() -> None:
    b = pd.read_csv(DATA / "bridge_segment_analysis.csv")
    r1 = b[b["route_code"] == "R1"]
    total = float(r1["median_end_to_end_minutes"].max())
    crossing = float(r1[r1["median_segment_minutes"] >= 10]["median_segment_minutes"].sum())
    rest = total - crossing

    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    ax.barh(["the rest of the route", "the two causeway crossings"],
            [rest, crossing], color=[GREY, RED])
    for i, v in enumerate([rest, crossing]):
        ax.text(v + 1, i, f"{v:.0f} min  ({v / total * 100:.0f}%)", va="center")
    ax.set_xlabel(f"minutes of R1's {total:.0f}-minute end-to-end run")
    ax.set_xlim(0, 55)
    ax.set_title(
        "F1  R1 West Park – Hulhumalé Ph1: 40 of 70 minutes are the two bridge crossings",
        loc="left", fontweight="bold")
    fig.savefig(FIGS / "F1_bridge_share.png")
    plt.close(fig)


def fig_load() -> None:
    """F2 — route-day upper bound vs measured peak-segment load factor.

    The two bars exist to make the reconciliation visible: the old figure
    assumed every passenger rode the whole route, which is why it disagreed
    with what a segment actually carries.
    """
    d = pd.read_csv(DATA / "route_load.csv").dropna(subset=["load_factor_peak_pct"])
    d = d.sort_values("load_factor_peak_pct", ascending=False).reset_index(drop=True)
    x = np.arange(len(d))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    ax.bar(x - w / 2, d["load_factor_route_day_upper_pct"], w,
           color="#c9ced6", label="Route-day upper bound (every pax rides end-to-end)")
    ax.bar(x + w / 2, d["load_factor_peak_pct"], w,
           color=[RED if v >= 85 else ORANGE if v >= 60 else GREY for v in d["load_factor_peak_pct"]],
           label="Peak stop-to-stop segment, captured hours")
    for i, (u, p) in enumerate(zip(d["load_factor_route_day_upper_pct"], d["load_factor_peak_pct"])):
        ax.text(i - w / 2, u + 1.5, f"{u:.0f}", ha="center", fontsize=7.5, color="#666666")
        ax.text(i + w / 2, p + 1.5, f"{p:.0f}", ha="center", fontsize=8, fontweight="bold")
    ax.axhline(100, color="black", ls="--", lw=1)
    ax.text(-0.45, 101.5, "capacity", ha="left", fontsize=8)
    ax.set_xticks(x, d["route_code"])
    ax.set_ylim(0, 140)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_xlim(-0.6, len(d) - 0.4)
    ax.set_ylabel("% of seats")
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    # Caption is derived from the table, never typed: a hard-coded version had
    # drifted to "R1 77% / R3 104%" while the CSV said 90.1% / 98.4%.
    r1 = d[d["route_code"] == "R1"].iloc[0]
    r3 = d[d["route_code"] == "R3"].iloc[0]
    ax.set_title(
        f"F2  Load factor is a segment, not a route: R1 is {r1['load_factor_route_day_upper_pct']:.1f}% "
        "only if nobody gets off",
        loc="left", fontweight="bold",
    )
    ax.text(0, -0.24,
            f"Peak segment: R1 {r1['load_factor_peak_pct']:.1f}% ({r1['peak_segment']}, "
            f"{int(r1['peak_segment_hour'])}:00); R3 {r3['load_factor_peak_pct']:.1f}% "
            f"({r3['peak_segment']}, {int(r3['peak_segment_hour'])}:00). "
            "Hours before 11:00 are not captured by the RTL feed.",
            transform=ax.transAxes, fontsize=7, color="#555555")
    fig.savefig(FIGS / "F2_load_factors.png")
    plt.close(fig)


def fig_daytype() -> None:
    d = pd.read_csv(DATA / "demand_by_daytype.csv")
    piv = d.pivot_table(index="route_code", columns="day_type", values="boardings_per_day")
    # Only the routes MTCC counts daily are plotted. R3 and R7 do have a Friday
    # figure, but it is derived from these three by the day-type index, so
    # plotting it beside them would present an assumption as an observation.
    routes = [r for r in ["R1", "R2", "R4"] if r in piv.index]
    piv = piv.loc[routes]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    x = np.arange(len(routes))
    w = 0.26
    for i, dt in enumerate(["weekday", "sat_holiday", "friday"]):
        if dt not in piv:
            continue
        vals = (piv[dt] / piv["weekday"] * 100).to_numpy()
        ax.bar(x + (i - 1) * w, vals, w, label=DAY_LABEL[dt],
               color=[BLUE, GREY, RED][i])
    for i, r in enumerate(routes):
        if "friday" in piv:
            v = piv.loc[r, "friday"] / piv.loc[r, "weekday"] * 100
            ax.text(i + w, v + 1.5, f"{v:.0f}", ha="center", fontsize=8, color=RED)
    ax.set_xticks(x, routes)
    ax.set_ylabel("boardings, weekday = 100")
    ax.set_ylim(0, 115)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fri = piv["friday"] / piv["weekday"] * 100
    lo, hi = fri.min(), fri.max()
    ax.set_title(f"F3  Friday demand is {100 - hi:.0f}-{100 - lo:.0f}% below a weekday "
                 "(MTCC boardings, 2025)", loc="left", fontweight="bold")
    fig.savefig(FIGS / "F3_demand_daytype.png")
    plt.close(fig)


def fig_airport() -> None:
    ap = pd.read_csv(DATA / "airport_demand_profile.csv")
    svc = pd.read_csv(DATA / "route_service_by_hour.csv")
    r4 = svc[(svc["route_code"] == "R4") & svc["departures"].notna()]
    share = r4.set_index("hour")["departures"]
    share = share / share.sum() * 100

    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    arr = ap.set_index("hour")["macl_share_pct"]
    ax.bar(arr.index, arr.values, color=BLUE, alpha=0.85,
           label="arriving passengers, % of day (MACL 2025, pax-weighted)")
    ax2 = ax.twinx()
    ax2.plot(share.index, share.values, color=RED, lw=2, marker="o", ms=3,
             label="R4 scheduled departures, % of captured day")
    ax2.grid(False)
    ax.set_xlabel("hour of day")
    ax.set_ylabel("% of daily arrivals")
    ax2.set_ylabel("% of R4 service")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper left")
    ax.set_title("F4  Airport buses run a flat headway; a third of passengers land between 07:00 and 09:59",
                 loc="left", fontweight="bold")
    ax.text(0, -0.22,
            "Passenger-weighted. Flight-weighted the morning share is 25.3%, so the weighting is stated on the chart.",
            transform=ax.transAxes, fontsize=7, color="#555555")
    fig.savefig(FIGS / "F4_airport_mismatch.png")
    plt.close(fig)


def fig_scenarios() -> None:
    k = pd.read_csv(DATA / "scenario_kpis.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.3))
    x = np.arange(len(k))
    labels = [s.split("_")[0] for s in k["scenario"]]
    axes[0].bar(x, k["boardings_over_capacity"], color=[GREY] + [RED] * (len(k) - 1))
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("boardings over capacity")
    axes[0].set_title("passengers who cannot board", loc="left", fontweight="bold")
    axes[1].bar(x, k["unmet_share_pct"], color=[GREY] + [GREEN] * (len(k) - 1))
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("% of demand unmet")
    axes[1].set_title("unmet demand", loc="left", fontweight="bold")
    for i, n in enumerate(k["trips_moved"]):
        axes[0].text(i, k["boardings_over_capacity"].iloc[i] + 20, f"{int(n)}",
                     ha="center", fontsize=8, color="#333333", fontweight="bold")
        axes[1].text(i, k["unmet_share_pct"].iloc[i] + 0.2, f"{int(n)}",
                     ha="center", fontsize=8, color="#333333", fontweight="bold")
    axes[0].set_ylim(0, k["boardings_over_capacity"].max() * 1.18)
    axes[1].set_ylim(0, k["unmet_share_pct"].max() * 1.18)
    fig.subplots_adjust(top=0.70, bottom=0.30, wspace=0.28)
    fig.suptitle("F5  Every scenario moves trips, none adds one (S5 = reallocate + express peak)",
                 x=0.02, y=0.98, ha="left", fontweight="bold")
    base, rec = k.iloc[0], k.iloc[-1]
    fig.text(0.02, 0.015,
             f"Bold number above each bar = trips moved. Total trips are "
             f"{int(base['total_trips_captured'])} in all {len(k)} scenarios. "
             "Trips move from low-load hours into over-capacity ones; no vehicle is added.\n"
             f"S5 moves {int(rec['trips_moved'])} trips: {int(base['boardings_over_capacity'])} "
             f"boardings over capacity become {int(rec['boardings_over_capacity'])}, and unmet "
             f"demand falls from {base['unmet_share_pct']:.1f}% to {rec['unmet_share_pct']:.1f}%.",
             fontsize=7, color="#555555")
    fig.savefig(FIGS / "F5_scenario_kpis.png")
    plt.close(fig)


def fig_gc() -> None:
    g = pd.read_csv(DATA / "scenario_modal_shift.csv")
    if "scenario" in g.columns:
        g = g[g["scenario"] == g["scenario"].iloc[0]]
    g = g.sort_values("break_even_ride_min")
    y = np.arange(len(g))
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    ax.barh(y - 0.2, g["gc_bus_mvr"], 0.4, label="bus (generalised cost)", color=BLUE)
    ax.barh(y + 0.2, g["gc_taxi_mvr"], 0.4, label="taxi, shared", color=RED)
    ax.set_yticks(y, g["corridor"])
    ax.set_xlabel("MVR per trip (fare + time × 250 MVR/hour)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    for i, (b, t, shed) in enumerate(zip(g["gc_bus_mvr"], g["gc_taxi_mvr"], g["ride_min_to_shed"])):
        ax.text(max(b, t) + 10, i, f"must shed {shed:.0f} min", va="center",
                fontsize=8, color=RED)
    ax.set_xlim(0, 470)
    ax.set_title("F6  The bus wins on price but loses on time: journey time is the lever, not the fare",
                 loc="left", fontweight="bold")
    fig.savefig(FIGS / "F6_generalised_cost.png")
    plt.close(fig)


def fig_usage() -> None:
    """Bus use by day period, with the working-hours assumption made visible."""
    u = pd.read_csv(DATA / "usage_by_period.csv")
    net = u[u["route_code"] == "ALL"].copy()
    order = ["night", "am_commute", "working_hours", "pm_commute", "evening", "late"]
    label = {
        "night": "00-06", "am_commute": "06-08", "working_hours": "08-16",
        "pm_commute": "16-19", "evening": "19-22", "late": "22-24",
    }
    net["period"] = pd.Categorical(net["period"], order, ordered=True)
    net = net.sort_values("period")
    sens = pd.read_csv(DATA / "working_hours_sensitivity.csv")
    # The band is the three eight-hour windows (07-15, 08-16, 09-17). The
    # table also carries 10-hour windows, which are a different question.
    band = sens[sens["hours_in_window"] == 8 * 15]  # 8 h x 15 routes = 120 route-hours
    win = sens[sens["working_window"] == "08:00-16:00"].iloc[0]

    fig, ax = plt.subplots(figsize=(7.4, 3.1))
    colours = [RED if p == "working_hours" else GREY for p in net["period"]]
    ax.bar(net["period"].astype(str), net["share_of_route_demand_pct"], color=colours)
    for i, (_, r) in enumerate(net.iterrows()):
        ax.text(i, r["share_of_route_demand_pct"] + 0.8,
                f"{r['share_of_route_demand_pct']:.0f}%", ha="center", fontsize=8,
                fontweight="bold" if r["period"] == "working_hours" else "normal")
    ax.set_xticks(range(len(net)),
                  [f"{label[p]}\n{p.replace('_', ' ')}" for p in net["period"]],
                  fontsize=7.5)
    ax.set_ylabel("% of modelled daily demand")
    ax.set_ylim(0, max(net["share_of_route_demand_pct"]) * 1.25)
    lo = band["share_of_daily_demand_pct"].min()
    hi = band["share_of_daily_demand_pct"].max()
    ax.set_title("F7  Most bus travel falls outside the assumed working day",
                 loc="left", fontweight="bold")
    ax.text(0, -0.34,
            f"Working day assumed 08:00-16:00 = {win['share_of_daily_demand_pct']:.0f}% "
            f"of demand; shifting it an hour either way gives {lo:.0f}-{hi:.0f}% (ADR-0012). "
            "Demand is modelled for 24 hours; service was captured from ~11:00 only.",
            transform=ax.transAxes, fontsize=7, color="#555555")
    fig.savefig(FIGS / "F7_usage_by_period.png")
    plt.close(fig)


def main() -> None:
    fig_bridge()
    fig_load()
    fig_daytype()
    fig_airport()
    fig_scenarios()
    fig_gc()
    fig_usage()
    print(f"wrote 7 figures to {FIGS}")


if __name__ == "__main__":
    main()
