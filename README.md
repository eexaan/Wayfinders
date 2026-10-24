# Raajje Rebalancer

**A data-driven bus supply decision tool for Greater Malé.**
Maldives Datathon 2026 · Team Wayfinders

> *Raajje* is the Maldivian name for the Hulhumalé causeway — the bottleneck
> under every number in this repository.

---

## What this is

Public transport data for Greater Malé is fragmented: the bus ridership
series covers 3 routes daily and 5 monthly, the only complete timetable is
published as scanned PDFs, the live departure feed is a single evening
snapshot, and the airport dataset covers 36% of the traffic it appears to.
**Nobody can answer "how many passengers does this route carry, at which
hour, and is that matched to the buses running?"**

This repository joins them and turns the answer into decisions.

| Document | What it is |
|---|---|
| **[SPEC.md](SPEC.md)** | The build plan: architecture, findings, scenarios, dashboard spec, team roles, timeline, risks, pitch |
| **[RESEARCH.md](RESEARCH.md)** | The full research log — what was tested, what was rejected and why, with every number reproducible |
| **[DATA_SOURCES.md](DATA_SOURCES.md)** | Every dataset with a direct link, publisher, use, licence, and caveats |

---

## The three findings

**1. The causeway is the journey time.** R1's 70-minute end-to-end run
spends **40 minutes (57%) in two causeway crossings**; every stop-to-stop
segment is a uniform 2 minutes. Internal Hulhumalé routes run 3–5 min per
segment. A taxi does the same trip in 12.7 minutes. The bus is **4.4×
slower than a taxi** and 8.5× cheaper — which is why people take taxis.

**2. One corridor carries nearly all the load; the airport buses do not.**
On the captured Saturday, **R1's fullest segment runs at 77%** of an 84-seat
double-decker, against **58% on R2** and **64% on R7**. The airport buses look
light on a route average (R4 51%) but their **airport segment is the busiest
thing in the network at 104%** — STELCO to VIA at 13:00 — because every
airport passenger funnels through it on a single trip. **R3 is an hourly bus
with a 30-minute expected wait**, and the airport buses run the same frequency
at 03:00 as at 08:00 while a third of arriving passengers (33.1%,
passenger-weighted) land in a three-hour window.

> Load factor is measured **per stop-to-stop segment**, not per route. The
> older route-level figure (R1 at 89.5%) assumed every passenger rode the whole
> route and overstated crowding on R1 by ~12 points; it is retained as
> `load_factor_route_day_upper_pct` for reconciliation.

**3. The bus already wins on price and loses on time.** On fare alone,
62–76% of taxi riders on every corridor would take the bus. On generalised
cost (VOT 250 MVR/h, taxis shared by two), only 0.05–9.3% would switch.
**A fare discount is the wrong instrument** — it discounts the dimension
where the bus already wins. The break-even table shows which corridors express
service can fix (16–20 min to shed) and which needs the causeway solved
(54 min).

---

## The tool

A reconciled demand–supply dataset (route × day-type × hour, every row
labelled *observed* / *derived* / *modelled*) feeding a scenario engine that
recomputes passenger-level KPIs for named schedule changes, wrapped in an
interactive GIS dashboard.

```
S0 baseline             381 boardings over capacity   3.79% unmet   162 trips
S5 recommended package   91                           0.91%         162 trips
                        (18 trips moved, none added)
```

Every scenario is **fleet-neutral**: trips are moved between hours, never added.
`trips_change` is 0 in all five scenarios and the build asserts it.

---

## Repository layout

```
SPEC.md                     project spec: findings, architecture, roles, timeline, pitch
RESEARCH.md                 research log: what was tested, what was rejected and why
DATA_SOURCES.md             every source, with links, publisher and licence
docs/
  DASHBOARD_SPEC.md         build contract for the dashboard team
  figures/F1..F6.png        the six report figures
dashboard/
  build/build_data.py       rebuilds every table from the official inputs
  build/build_stop_demand.py  stop-level demand + segment load (runs AFTER build_data.py)
  build/build_validation.py holdout MAPE + airport reconciliation; rebuilds the airport profile
  build/build_gtfs.py       synthesises a GTFS feed from the official per-stop timings
  build/build_schedule_crosscheck.py  validates supply against the published PDFs
  build/build_figures.py    rebuilds F1..F6
  data/                     the tables the dashboard reads (see DASHBOARD_SPEC §2)
data/
  raw/                      datathon release files (MTCC, Avas, MACL, Team Kandu)
  official/
    rtl/                    official RTL 2026 bus feed
    mbs/                    MBS yearbook tables, population, LFS report
  derived/
    rtl_greater_male_gtfs.zip   synthesised GTFS feed (0 validator errors)
    gtfs/                       the same feed unzipped, for inspection
```

## Where the numbers come from

Supply is the **official RTL 2026 bus feed** —
`bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails` — which is public and
needs no key. It gives the official English and Dhivehi route names, colours,
fares, and every stop's scheduled departure times. Demand is MTCC ridership,
shape is Avas taxi OD, and airport arrivals are MACL plus MBS Yearbook 11.13.

> **Known gap:** the RTL feed is time-filtered from the moment of the call, so
> our capture covers roughly 11:00–24:00 of one service day. The morning peak
> and the Friday/weekday comparison are not captured. Hours outside the window
> are emitted as null, never as zero. Re-running the build just after midnight
> fixes it.

Every figure in `SPEC.md` and `RESEARCH.md` is inlined as a table, so both can
be checked by hand. Sources and licences: [DATA_SOURCES.md](DATA_SOURCES.md).

## Credits

- **Maldives Bureau of Statistics** — MACL, Avas Ride, MTCC datasets; Statistical
  Yearbook tables 3.30, 10.12, 11.3, 11.13, 11.18
- **MTCC plc** — published bus schedules and route maps
- **RTL (Raajje Transport Link)** — public route map CMS
- **Team Kandu** — team-shared extract (bus routes/stops/departures, yearbook
  observations)
- **OpenStreetMap** contributors — basemap and road network (ODbL)

All data is public. No private or restricted sources were used.
