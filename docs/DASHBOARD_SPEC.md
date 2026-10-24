# Dashboard build spec

**Raajje Rebalancer · Greater Malé bus supply decision tool**
For the dashboard developers. Read `SPEC.md` for the findings and the story;
this document is the build contract.

Everything the dashboard needs is in `dashboard/data/`. No modelling, no
scraping, no data wrangling in the frontend — just read these tables.

---

## 1. The one-paragraph brief

An interactive map of Greater Malé's 15 bus routes where an operator can
**see where the buses don't match the passengers** and **try moving them**.
Default view: a choropleth-free route map coloured by *load factor* (how full
each route is), with a demand-versus-service panel per route, and a
scenario bar that re-runs the KPIs live when you move buses. The pitch is
"move 6 trips and see what happens", so the scenario controls must be
instant and obviously reversible.

**Not** an analytics dashboard with 12 charts. Four panels, one map, one
scenario bar.

---

## 2. Data contract

All files are in `dashboard/data/`, committed, CSVs, UTF-8, comma-separated.

### 2.1 `route_lines.geojson` — the map geometry

GeoJSON `FeatureCollection`, 15 features, one per route.

```jsonc
{
  "type": "Feature",
  "properties": { "route_code": "R1", "corridor": "male_hm1", "n_stops": 18 },
  "geometry": { "type": "LineString", "coordinates": [[lon, lat], ...] }
}
```

Coordinates are **[lon, lat]** (GeoJSON order), already in stop order, already
clipped to Greater Malé. **Do not reverse them.** Draw straight
`LineString` polylines — do not snap to roads. The map is schematic by
design; snapping adds a dependency for no analytical gain.

### 2.2 `route_stops.csv` — 194 rows, 7 columns

| Column | Type | Example | Use |
|---|---|---|---|
| `route_code` | str | `R1` | join key |
| `stop_seq` | int | `1` | order along the route |
| `stop` | str | `Maafannu Bus Terminal` | label |
| `stop_id` | int | `103` | join key (a stop appears on many routes) |
| `lat` | float | `4.169366` | marker position |
| `lon` | float | `73.504676` | marker position |
| `corridors_served` | str | `male_airport,male_hm1,male_hm2` | which corridors reach this stop |

### 2.3 `route_fleet_capacity.csv` — 15 rows, one per route

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | `R1` … `R15` |
| `bus_type` | str | `Double decker` / `Airport bus` / `Regular bus` / `Minibus` / `E-minibus` |
| `seats` | int | 84 / 52 / 54 / 21 / 11 — **team-sourced, confirm with MTCC** |
| `capacity_source` | str | provenance flag; render as a tooltip badge |
| `live_trips_per_day_2026_10_10` | float | **may be null** (R10, R11, R12, R15) |
| `fare_mvr` | float | bus fare |
| `n_stops` | int | |
| `corridor` | str | `male_hm1`, `male_hm2`, `hm1_hm2`, `hm1_airport`, `hm2_airport`, `male_airport`, `hm_internal`, `male_internal`, `villimale` |
| `daily_seat_capacity` | float | trips × seats; null where trips are null |

### 2.4 `demand_supply_gap.csv` — 169 rows, the core table

Grain: **route × day-type × hour**. 12 columns.

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | join key |
| `day_group` | str | `weekday` \| `friday` \| `sat_holiday` |
| `hour` | int | 0–23 |
| `corridor` | str | as above |
| `trips_in_hour` | int | scheduled departures in that hour |
| `headway_min` | float | scheduled headway for that hour |
| `seats` | int | |
| `seat_capacity_hour` | int | `trips_in_hour × seats` |
| `demand_pax_est` | float | **modelled** — MTCC observed level × Avas observed shape |
| `load_factor_pct` | float | `demand_pax_est / seat_capacity_hour × 100` |
| `unmet_pax_est` | float | passengers who cannot board |
| `demand_source` | str | always `"MTCC observed (level) x Avas shape (modelled)"` — **render this in a tooltip** |

**Only 5 routes have demand data** (R1, R2, R3, R4, R7). The other 10 have
`NO DEMAND DATA`. The gap table simply omits them. **Do not render them as
zero** — render them as "no demand data" (grey, hatched, or omitted with a
count in the coverage panel).

### 2.5 `route_daytype_headline.csv` — 10 rows

Route × day-type summary. Use for the route panel headline.

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | |
| `bus_type` | str | |
| `seats` | int | |
| `day_type` | str | |
| `trips_per_day` | float | scheduled trips for that day-type |
| `daily_seat_capacity` | float | |
| `boardings_per_day` | float | observed (MTCC) |
| `pax_per_trip` | float | |
| `load_factor_peak_pct` | float | **upper bound** — every boarding rides the full route |
| `load_factor_avg_pct` | float | **lower bound** — uniform alighting |
| `demand_source` | str | `MTCC observed` or `MTCC bus_monthly (observed) x daily-data day-type index` |

> ⚠️ **The two load-factor columns are a band, not a point estimate.** Render
> both (a range bar or a shaded band). Never show one as "the" load factor.

### 2.6 `service_departures.csv` — 1,508 rows

Grain: one row per **scheduled departure**. `route_code`, `day_group`,
`departure_min` (minutes from midnight), `departure_hhmm` (`"0600"`),
`hour`, `headway_min`, `corridor`.

Use this to draw a **timetable ribbon** (a Gantt-style bar of departures per
route per hour) and to compute real headways in the browser.

### 2.7 `scenario_kpis.csv` — 6 rows

`scenario` (`S0_baseline` … `S5_recommended_package`), `mean_wait_min`,
`p95_wait_min`, `boardings_over_capacity`, `unmet_share_pct`,
`seat_capacity_per_hour`, `total_trips_per_day`, `demand_pax_per_day`, plus
deltas vs baseline (`mean_wait_change_min`, `over_capacity_change`,
`trips_change`).

**This is a lookup table, not a computation.** The scenario engine already ran
offline. The dashboard's job is to let the user *pick* a scenario and show
the row, plus let them *tweak* the headline parameters live.

### 2.8 `scenario_corridor_kpis.csv`

Same six scenarios × corridor, with `mean_wait_min`, `worst_hour_wait_min`,
`boardings_over_capacity`, `unmet_share_pct`, `trips_per_day`. **Use this for
the per-corridor before/after**, because the network-wide mean wait barely
moves (11.6 min) and showing only that would misrepresent the result.

### 2.9 `friday_responsiveness.csv` — 4 rows

`route_code`, `demand_friday_index_pct`, `service_friday_index_pct`,
`service_minus_demand_pp`, `verdict` (prose string). This is the F3 chart.

### 2.10 `bridge_segment_analysis.csv` — 125 rows

`route_code`, `from_stop`, `to_stop`, `median_segment_minutes`,
`median_end_to_end_minutes`, `n_trips`. **The F1 chart.** The two 20-minute
causeway rows for R1 and R2 are the story; highlight segments ≥ 10 min.

### 2.11 `airport_demand_profile.csv` — 24 rows

`hour`, `macl_international_arrival_share`, `macl_share_pct`, plus the
Yearbook level columns and `macl_coverage_of_intl_pct` (36.5). The F4 chart
needs `macl_share_pct` against the scheduled service share for R4 — derive
the latter from `service_departures.csv` by counting R4 weekday departures
per hour.

### 2.12 `taxi_od_by_hour.csv` — 2,387 rows

`zone_o`, `zone_d`, `hour`, `dow`, `rides`, `mean_km`, `mean_min`. Zone names:
`Male City`, `Hulhumale Ph1`, `Hulhumale Ph2`, `Velana Airport`, `Villimale`,
`Other`.

### 2.13 `schedule_vintage_divergence.csv` — 14 rows

`route_code`, `pdf_ramadan1446_trips_weekday`,
`live_trips_per_day_2026_10_10`, `divergence_pct`. **Put this in the
methodology/limitations panel.** It is a finding, not an embarrassment.

---

## 3. Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Raajje Rebalancer        Greater Malé · MTCC                          │
├────────────────────────────────────────────┬─────────────────────────────┤
│                                            │  ROUTE PANEL                │
│                                            │  R1  West Park – HM Ph1     │
│              MAP                           │  Double decker · 84 seats   │
│   (Leaflet / MapLibre)                     │  ┌───────────────────────┐  │
│                                            │  │ ▓▓▓▓▓▓▓▓▓▓░░░ 102%   │  │
│   • 15 route polylines                    │  │ load factor band      │  │
│     coloured by load factor               │  │ 51% ─────── 102%      │  │
│   • 194 stop markers                       │  └───────────────────────┘  │
│   • causeway segments highlighted          │  Trips/day 61  Boardings    │
│     (≥10 min, thick red)                  │  5,212   Fare 10 MVR        │
│                                            │                             │
│                                            │  ┌── demand vs service ──┐ │
│                                            │  │ hour-of-day bar chart │ │
│                                            │  │ (dual series)         │ │
│                                            │  └───────────────────────┘ │
│                                            │                             │
│                                            │  ┌── timetable ribbon ────┐ │
│                                            │  │ departures per hour    │ │
│                                            │  └────────────────────────┘ │
├────────────────────────────────────────────┴─────────────────────────────┤
│  SCENARIO BAR                                                                  │
│  [S0 Baseline] [S1 Friday] [S2 Airport] [S3 Rebalance] [S4 Express] [S5 All]│
│                                                                             │
│  Over-capacity ▓ 1,715   Unmet ▓ 8.00%   Mean wait ▓ 11.6 min   Trips ▓ 371  │
│  [───────────────●────────────────]  (trips slider)    Taxi capture ▓ 191/day │
└──────────────────────────────────────────────────────────────────────────┘
```

**Bottom bar is always visible** — it is the payoff, so it must never scroll
out of view. Scenario KPIs update in place with a 150 ms fade; do not
re-render the whole page.

---

## 4. Component specs

### C1 — Map

- **Library:** Leaflet 1.9 + `leaflet.markercluster` (or MapLibre GL if the
  team prefers vector tiles). OSM raster tiles via
  `https://tile.openstreetmap.org/{z}/{x}/{y}.png` — **attribute
  © OpenStreetMap contributors** in the footer.
- **Route lines:** from `route_lines.geojson`. Default colour scheme:
  - `load_factor_peak_pct` ≥ 100 → red `#e9222a` (over capacity)
  - 60–100 → orange `#ff7f0e`
  - < 60 → grey `#9aa0a6`
  - no demand data → light grey, dashed
- **Line weight:** 4 px for the selected route, 2 px otherwise.
- **Stops:** circle markers, radius 3 (2 when zoomed out), white fill, grey
  stroke. Tooltip = stop name + which routes serve it.
- **Causeway segments:** render segments with `median_segment_minutes` ≥ 10
  in a heavier red stroke on top of the route line. These are the two
  20-minute crossings on R1/R2 and the 15-minute VIA terminal segments.
- **Interactions:** hover a route → highlight + tooltip (route, bus type,
  load band, fare); click → select and populate the route panel; click a
  stop → show the stop's routes.
- **Basemap note:** Malé is tiny (4 km). Default zoom 14, centre
  `4.195, 73.525`. Set `maxBounds` to the Greater Malé extent so the user
  cannot pan into the ocean.

### C2 — Route panel

Populated on route click. Contains:
1. **Header:** route code, official name, bus type, seats, fare, trips/day.
2. **Load-factor band:** a horizontal range bar showing
   `load_factor_avg_pct` → `load_factor_peak_pct`, with 100% marked. Label
   both ends. **Never render a single value.**
3. **Demand vs service chart** (the F2 chart, per route): dual-series bar
   chart by hour of day for the selected day-type:
   - bar 1 = `demand_pax_est` from `demand_supply_gap.csv`
   - bar 2 = `seat_capacity_hour` from the same table
   - a horizontal line at the point where demand exceeds capacity
   - day-type switcher: `weekday` / `friday` / `sat_holiday`
4. **Timetable ribbon:** for each hour, a small vertical tick per departure
   (from `service_departures.csv`), so the headway profile is visible.
5. **Friday responsiveness strip** (if the route is in
   `friday_responsiveness.csv`): demand index vs service index with the
   gap in percentage points.

### C3 — Scenario bar

- Six buttons: **S0 Baseline · S1 Friday right-sized · S2 Airport re-timed ·
  S3 Rebalanced to corridor · S4 Express added · S5 Recommended package**.
- Clicking a button loads the row from `scenario_kpis.csv` into the KPI
  tiles and the corridor breakdown from `scenario_corridor_kpis.csv`.
- Also expose **one live slider**: "trips reassigned from the airport routes
  to the Malé–Hulhumale corridor, 0–12". This is S3, live, and it is the
  best demo because the trade-off is real. Interpolate the KPI tiles
  linearly between the S0 and S3 rows and label it clearly as an
  *interpolation* so nobody mistakes it for a model output.
- KPI tiles: `boardings_over_capacity`, `unmet_share_pct`, `mean_wait_min`,
  `total_trips_per_day`, `taxi_rides_capturable_per_day` (from
  `scenario_modal_shift_summary.csv`).
- **Show the delta vs S0** on every tile (e.g. `−200`, `−0.93 pp`). The
  numbers are only interesting as deltas.

### C4 — Methodology / coverage panel

A collapsible drawer. Contents:
- The dataset register (link to `DATA_SOURCES.md` in the repo).
- The **load-factor band explanation** — why there are two numbers.
- The **schedule vintage** table (`schedule_vintage_divergence.csv`).
- The **coverage matrix**: route × what we have (demand data yes/no, live
  trip count yes/no, published schedule yes/no). This is a *feature* — the
  datathon asks for data-gap identification, so make the gaps visible.
- The **MACL coverage** number (36.5% of international arrivals; 0% domestic)
  with a link to MBS Yearbook 11.13.

---

## 5. Scenario definitions (for the tooltip text)

| Key | Label | What it does |
|---|---|---|
| S0 | Baseline | — |
| S1 | Friday right-sized | Cut Friday service on R1, R2, R4 to match Friday demand (demand falls 37%, service was falling only 9–22%) |
| S2 | Airport re-timed | R4/R9: 30→15 min during the 07:00–09:59 / 11:00 / 14:00 arrival peaks; R3: 60→30 min. Night service (22:00–06:00) halved, where 22:00–00:00 carries 0.25% of arrivals against 5.6% of service |
| S3 | Rebalanced to corridor | Move 15% of airport-route weekday trips to the Malé–Hulhumale Ph1 corridor, weighted to the 16:00–18:00 peak |
| S4 | Express added | Skip-stop Hulhumale service on R1/R2: journey 70→45 min, +15% departures |
| S5 | **Recommended package** | S1 + S2 + S4. 200 fewer boardings over capacity, ~1 point less unmet demand, 26 more trips/day — all re-timings, no new buses |

---

## 6. Tech stack recommendation

**Recommended (lowest risk, fastest to build):**

- **Static site, no build step.** A single `index.html` + `app.js` + `styles.css`
  that reads the CSVs with `d3.csvParse` or `PapaParse`.
- **Why:** the datathon has a hard technical/code check, and a zero-dependency
  static site that runs by opening a file is the most robust thing to
  demonstrate. No build failures, no `npm install` at demo time.
- **Charts:** hand-rolled SVG or Chart.js. Only four chart types are needed
  (range bar, dual-series bar, ribbon, stat tile) — a charting library is
  optional.
- **Map:** Leaflet from CDN.
- **Data:** copy `dashboard/data/*.csv` + `.geojson` into a `dashboard/data/`
  folder, load via `fetch`. (If you open `index.html` over `file://`, the
  browser will block `fetch` — either run `python -m http.server` or inline
  the data as JS constants. **Test this early.**)

**If the team prefers React:** Vite + React + Leaflet, with the CSVs in
`public/data/`. Fine, but budget 30–45 minutes for setup before writing any
component.

**Do not use:** any React-leaflet wrapper that pulls in a heavy GIS stack
(Mapbox GL needs a token; Deck.gl is overkill for 15 lines and 194 points).

---

## 7. Scope guard — what NOT to build

Cut these without discussion. Time is the binding constraint.

- ❌ A login, a backend, a database. Everything is static.
- ❌ User-uploaded data, editable tables, or a data-entry form.
- ❌ A live-data refresh from the RTL API (needs a JWT; see the research
  notes for the endpoint if someone has time).
- ❌ A camera/crowd-detection feature. It is a *validation appendix*, not a
  dashboard panel.
- ❌ A second basemap layer, terrain, 3D buildings, or satellite tiles.
- ❌ Animated vehicles on the map. There is no live vehicle data.
- ❌ More than 4 panels. If you have time, add the per-corridor before/after
  view, not a fifth panel.

---

## 8. Suggested split for the dashboard developers

| Dev | Build | Depends on |
|---|---|---|
| **A** | C1 Map + C2 Route panel | `route_lines.geojson`, `route_stops.csv`, `demand_supply_gap.csv` |
| **B** | C3 Scenario bar + KPI tiles | `scenario_kpis.csv`, `scenario_corridor_kpis.csv`, `scenario_modal_shift_summary.csv` |
| **C** | C4 Methodology drawer + the six F1–F6 figures as static images | `docs/figures/*.png`, `schedule_vintage_divergence.csv`, `DATA_SOURCES.md` |

**Agree on the file names and column names before starting** — the tables
above are the contract. If you need a column that is not there, add it to
whoever owns the model, then re-export to `dashboard/data/`. Do not compute
it in the frontend.

---

## 9. Acceptance criteria

The dashboard is done when:

1. It opens with **no console errors** and no network calls other than tiles
   and local data files.
2. Clicking a route fills the route panel within 100 ms.
3. Switching the day-type updates the demand-vs-service chart.
4. Clicking each of the six scenario buttons updates every KPI tile, with
   deltas.
5. The live "trips reassigned" slider moves the over-capacity tile and is
   labelled as an interpolation.
6. Every modelled number carries a tooltip explaining it is modelled, and
   the load factor is shown as a **band**.
7. Routes without demand data are visibly marked as such.
8. The OSM attribution is in the footer.
9. It works at 1366×768 and on a projector (the pitch may be projected).
10. Someone who did not build it can explain, in one sentence, what the
    red lines mean.

---

## 10. Where the numbers came from

| Figure | Source table(s) |
|---|---|
| F1 bridge | `bridge_segment_analysis.csv` |
| F2 load factors | `route_daytype_headline.csv` |
| F3 Friday | `friday_responsiveness.csv` |
| F4 airport | `airport_demand_profile.csv` + `service_departures.csv` |
| F5 scenarios | `scenario_kpis.csv` |
| F6 generalised cost | `scenario_modal_shift.csv` |

Pre-rendered PNGs of all six are in `docs/figures/` — you can drop them in
while the interactive versions are being built, and they are already sized
for slides.
