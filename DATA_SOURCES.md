# Data sources register

**Maldives Datathon 2026 · Team Wayfinders · Raajje Rebalancer**

Every dataset used in this project is listed here with a direct link, its
publisher, how it is used, and its licence/provenance. The datathon rules
require all sources to be public and properly credited; nothing private or
proprietary has been used.

---

## 1. Official datathon datasets (Maldives Bureau of Statistics)

Release: <https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/tag/v1.0>

| # | Dataset | Direct link | Used for | Status |
|---|---|---|---|---|
| D1 | **MTCC** — bus & ferry ridership | [`MTCC.zip`](https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/download/v1.0/MTCC.zip) | **Demand levels.** `bus_daily` (R1/R2/R4, every day of 2025), `bus_monthly` (R1/R2/R3/R4/R7, 2023–2025), `ferry_monthly` (not used) | ✅ used |
| D2 | **Avas Ride** — taxi trips | [`Avas_Ride.zip`](https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/download/v1.0/Avas_Ride.zip) | **Demand shape + mode shift.** 371,788 trip records, Aug–Sep 2026, with pickup/dropoff coordinates, distance, duration, status; plus `car_fare_matrix.csv` (zone-to-zone fares) | ✅ used |
| D3 | **MACL** — Velana airport traffic | [`MACL.zip`](https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/download/v1.0/MACL.zip) | **Airport arrival shape by hour.** 168,959 movements, 2012–2026. Also used to *document its own coverage gap* (see §4) | ✅ used, with caveat |
| D4 | **FollowMe** — vessel GPS | [`FollowMe.zip`](https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/download/v1.0/FollowMe.zip) | 17.46M GPS rows, Aug 2025. **Excluded from scope** — the problem statement is about Greater Malé bus supply, and this is marine traffic | ⛔ not used |
| D5 | **Team Kandu** — team-shared extract | [`Team_Kandu.zip`](https://raw.githubusercontent.com/mbs-datathon/maldives-datathon-2026-datasets/main/team-shared-datasets/Team_Kandu.zip) | **Supply + geometry + official statistics.** `rtl_bus_routes` (route attributes, trips/day), `rtl_bus_stops` (613 stops, lat/lon), `rtl_bus_departures` (live per-stop timings), `observations.csv` (MBS Statistical Yearbook extract) | ✅ used |

---

## 2. Publicly acquirable official sources (not in the datathon release)

These are public web sources. They were *not* provided in the dataset release
and are the analytical backbone of the project.

| # | Source | Direct link | Used for | Notes |
|---|---|---|---|---|
| S1 | **RTL official bus feed (2026)** | <https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails> · saved as [`data/official/rtl/bus_routedetails_2026.json`](data/official/rtl/bus_routedetails_2026.json) | **The supply model.** Official naming (English + Dhivehi), route colour, fare, minibus flag, and every stop with coordinates and its scheduled departure times | Public, no auth. **Time-filtered** — see §5 |
| S2 | **RTL bus route map (CMS API)** | <https://rtl.mv:7781/maldives/cms/CMSGetAllBusRouteMap> | Cross-check of the official route list, colours and per-route map PDFs | Public, no auth required |
| S3 | **RTL per-route map PDFs** | e.g. <https://rtl.mv:7781/BusRouteMap/R1%20final.pdf> | Official route maps with stop names (EN + Dhivehi); used to validate the stop sequence and as report figures | |
| S4 | **MBS Statistical Yearbook 11.13** | <https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/07/11.13.xlsx> · **local copy: [`data/official/mbs/11.13.xlsx`](data/official/mbs/11.13.xlsx)** | **Velana airport passengers, domestic vs international**, monthly, 2014–2025. Reached via D5 `observations.csv` | This is where the *domestic* aviation data lives |
| S5 | **MBS Statistical Yearbook 11.18** | <https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/07/11.18.xlsx> | Aircraft movements by type (domestic/international, scheduled/non-scheduled/charter) | |
| S6 | **MBS Statistical Yearbook 3.30** | <https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/04/3.3.xlsx> | Census 2022 + registered population for Malé, Hulhumale Ph1/Ph2, Villimale | |
| S7 | **MBS Statistical Yearbook 10.12** | <https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/06/10.12.xlsx> | Resort beds in Malé Atoll (K), 2009–2025 — tourism demand driver | |
| S8 | **MBS Statistical Yearbook 11.3** | <https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/07/11.3.xlsx> | Registered vehicle fleet, including registered **buses** (national: 222 in 2023) | |
| S9 | **MBS yearbook mirror** | <https://github.com/ajmals/maldives-statistics> | Clean CSV versions of every yearbook table — used to cross-check S4–S8 independently | Community mirror of official data |

### 2a. Official sources uploaded by the team (`data/official/mbs/`)

| # | File | Original source | Used for |
|---|---|---|---|
| T1 | [`11.13.xlsx`](data/official/mbs/11.13.xlsx) | MBS Statistical Yearbook 2026, table 11.13 | Local copy of S4 — Velana passengers, domestic vs international |
| T2 | [`3.15.xlsx`](data/official/mbs/3.15.xlsx) | MBS Census 2022 | Population by locality — demand denominators |
| T3 | [`3.16.xlsx`](data/official/mbs/3.16.xlsx) | MBS Census 2022 | Population by locality (companion table) |
| T4 | [`Population-Projection-2022-2026-16-Feb-2026.pdf`](data/official/mbs/Population-Projection-2022-2026-16-Feb-2026.pdf) | <https://statisticsmaldives.gov.mv/maldives-population-projection-2022-2062/> | Forward population for the Greater Malé catchments |
| T5 | [`LFS-Report-2024-2025.pdf`](data/official/mbs/LFS-Report-2024-2025.pdf) | MBS Labour Force Survey | Employment and youth commuting context |
| T6 | [`1.5.xlsx`](data/official/mbs/1.5.xlsx) | MBS Statistical Yearbook 2026, table 1.5 | Geography reference (not used in the model) |
| T7 | [`notes.txt`](data/official/notes.txt) | Team | Source links, including the **bus capacity** reference |

**Bus capacity source (team-provided).** The seat capacities in
`dashboard/data/route_fleet_capacity.csv` come from
<https://www.psmnews.mv/en/106008> (linked in `data/official/notes.txt`), combined
with the `minibus` flag in Team Kandu's route table. That article is behind a
Cloudflare challenge and could not be machine-read here, so the capacities are
recorded as team-provided rather than automatically verified. **Confirm the
seats per route before any absolute load-factor claim is published.**

---



## 3. Open data and tooling

| # | Source | Direct link | Used for | Licence |
|---|---|---|---|---|
| O1 | **OpenStreetMap** | <https://www.openstreetmap.org/> · Overpass API <https://overpass-api.de/api/interpreter> | Basemap, road network, POIs (schools, hospitals, hotels, markets) for catchment analysis | **ODbL** — attribution required: © OpenStreetMap contributors |
| O2 | **OSRM demo server** | <https://router.project-osrm.org/> | Bus travel-time estimation, stop-gap analysis | BSD / OSRM |
| O3 | **pdftotext** (Poppler) | <https://poppler.freedesktop.org/> | Parsing the MTCC schedule PDFs into structured service patterns | GPL |
| O4 | **FIS (Ferry Information System)** | <https://www.fis.mv/> | Marine timetable reference (out of scope; recorded for completeness) | Public |
| O5 | **PSM News — bus capacity** | <https://www.psmnews.mv/en/106008> | Reported seat capacity of the MTCC Malé fleet | Public news; **not machine-verified** |

---

## 4. A note on MACL's coverage (a finding, not a defect)

We cross-checked the provided MACL airport dataset against the MBS Statistical
Yearbook (S4/S5) and found a material coverage gap:

| Measure (2025) | MACL (D3) | MBS Yearbook (S4) | MACL coverage |
|---|---|---|---|
| International arriving passengers | 984,629 (adults) | 2,699,225 (all) | **≈ 40%** |
| International aircraft movements | 6,396 (17.5/day) | 34,808 (95/day) | **≈ 18%** |
| Domestic arriving passengers | — | 1,455,156 (3,987/day) | **0%** |

**MACL contains no domestic flights.** We tested four hypotheses to establish
this: the `region` field has no "Domestic" value; the `Turboprop` category
contains 40–50 pax regional services to South Asia, not Twin-Otter island
hops; low-pax flights are wide-body empty repositioning legs (0 arriving,
186–223 departing at 22:00–23:59); and the daily movement count (17.5) is
far below the yearbook's ~95 international plus ~587 domestic movements.

**Consequence for the project:** MACL is used only for the *shape* of the
intraday arrival profile. *Levels* come from the Yearbook (S4). This is
reported as a finding and as a data request to MBS.

---

## 5. Vintage and coverage caveats (publish these)

| Caveat | Detail | Mitigation |
|---|---|---|
| **The RTL feed is time-filtered** | It returns each stop's departures **from the moment of the call onwards**. Our capture was ~11:00 on Saturday 2026-10-24, so the window is ~11:00–24:00 and the **morning peak is missing**. Trip counts per day (the max trip `order`) are still complete | Hours outside the window are written as `null` with `capture_status` set, never 0, and are excluded from every KPI. Re-run `dashboard/build/build_data.py` just after midnight for a full day; run on a Friday and a weekday to restore the day-type comparison |
| Route R3 | No published weekday pattern (only Friday and Saturday/Public Holidays) | Use the Saturday pattern, flag it, do not present it as a weekday figure |
| Routes R10, R11, R12, R15 | No `trips_per_day` in the live extract, and no ridership data in MTCC | Marked `NO DEMAND DATA`; excluded from the gap table rather than zero-filled |
| Routes R13, R14 | `trips_per_day` present but no ridership data | Capacity computed, demand left blank |
| MTCC counts | The MTCC README labels `paid_pax`/`foc_pax` as "sample value" | Stated in the limitations; MTCC is used as the *anchor* and cross-checked against Avas |
| Team Kandu timetable | A single live snapshot, **19:54–23:59 on Sat 2026-10-10**. Superseded by S1; kept only as an independent cross-check of the evening headways | Not used in the build |
| Avas | 61 days, Aug–Sep 2026, one operator | Used as a demand *shape* and as a revealed-preference bound, not as a census of trips |
| **Route naming** | Official English and Dhivehi names come from S1. The Dhivehi strings in `routes_master.csv` are UTF-8; check they render in the dashboard's font | Verify in the browser, not in a terminal |

---

## 6. Where the derived tables live

The tables the dashboard reads are in `dashboard/data/`, built by
`dashboard/build/build_data.py`, and the schema of each one is documented in
`docs/DASHBOARD_SPEC.md` §2.

Inputs are in `data/`: `data/raw/` holds the datathon release files and
`data/official/` holds the public official sources (the RTL feed, and the MBS
yearbook tables the team uploaded).

| Derived table | Built from |
|---|---|
| `routes_master.csv` | S1 (official naming, fare, minibus flag, colour, trip counts) + fleet seats (team, T-source) |
| `route_stops.csv`, `route_lines.geojson` | S1 stop list (coordinates, order, EN + Dhivehi names) |
| `service_departures.csv` | S1 per-stop `timings` at the route origin |
| `route_service_by_hour.csv` | S1 departures aggregated to the hour |
| `demand_supply_gap.csv` | D1 (demand level) × D2 (demand shape) × S1 (capacity) × fleet seats |
| `route_load.csv` | D1 × S1 × fleet seats |
| `demand_by_daytype.csv` | D1 |
| `bridge_segment_analysis.csv` | S1 per-stop scheduled timings |
| `scenario_kpis.csv`, `scenario_corridor_kpis.csv` | the gap table + the scenario definitions in `SPEC.md` §5 |
| `scenario_modal_shift*.csv` | D2 taxi OD + Avas fare matrix + observed bus ride times |
| `airport_demand_profile.csv` | D3 (hourly shape) + S4 (levels, incl. domestic) |
| `taxi_od_by_hour.csv` | D2 |
