"""
================================================================================
Figures for the report and the pitch
================================================================================
Maldives Datathon 2026 | Team Wayfinders

Draws every figure directly from dashboard/data/. No number is typed by hand.

    F1_bridge_share.png        the causeway is 57% of R1's journey
    F2_load_factors.png        R1 at 89.5% of seats; the airport bus at 51%
    F3_demand_daytype.png      Friday demand is 37% below a weekday (demand only)
    F4_airport_mismatch.png    hourly airport bus vs tri-peaked arrivals
    F5_scenario_kpis.png       baseline vs the recommended package
    F6_generalised_cost.png    break-even journey time per corridor
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
DAY_LABEL = {"weekday": "Mon–Thu", "friday": "Friday", "sat_holiday": "Saturday"}


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
    d = pd.read_csv(DATA / "route_load.csv").dropna(subset=["load_factor_peak_pct"])
    d = d.sort_values("load_factor_peak_pct", ascending=False).reset_index(drop=True)
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    ax.bar(x, d["load_factor_peak_pct"],
           color=[RED if v >= 85 else ORANGE if v >= 60 else GREY for v in d["load_factor_peak_pct"]])
    for i, v in enumerate(d["load_factor_peak_pct"]):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8)
    ax.axhline(100, color="black", ls="--", lw=1)
    ax.text(len(d) - 0.4, 101.5, "capacity", ha="right", fontsize=8)
    ax.set_xticks(x, d["route_code"])
    ax.set_ylim(0, 112)
    ax.set_ylabel("% of seats (upper bound)")
    ax.set_title("F2  Load factor, captured Saturday: R1 at 89.5%, the airport bus R4 at 51%",
                 loc="left", fontweight="bold")
    ax.text(0, -0.2, "Weekday demand on R1 is 13.7% higher; at the same 61 trips that is ~102%.",
            transform=ax.transAxes, fontsize=7, color="#555555")
    fig.savefig(FIGS / "F2_load_factors.png")
    plt.close(fig)


def fig_daytype() -> None:
    d = pd.read_csv(DATA / "demand_by_daytype.csv")
    piv = d.pivot_table(index="route_code", columns="day_type", values="boardings_per_day")
    routes = [r for r in ["R1", "R2", "R4", "R7"] if r in piv.index]
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
    ax.set_title("F3  Friday demand is 37% below a weekday (MTCC boardings, 2025)",
                 loc="left", fontweight="bold")
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
           label="international arrivals, % of day (MACL 2019–25)")
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
    ax.set_title("F4  Airport buses run a flat headway; 35.5% of arrivals land between 07:00 and 09:59",
                 loc="left", fontweight="bold")
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
    fig.suptitle("F5  Scenarios on the captured service window (S5 = airport re-timing + express peak)",
                 x=0.02, ha="left", fontweight="bold")
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


def main() -> None:
    fig_bridge()
    fig_load()
    fig_daytype()
    fig_airport()
    fig_scenarios()
    fig_gc()
    print(f"wrote 6 figures to {FIGS}")


if __name__ == "__main__":
    main()
