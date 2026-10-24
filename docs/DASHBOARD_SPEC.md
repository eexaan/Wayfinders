# Dashboard build spec

**Raajje Rebalancer · Greater Malé bus supply decision tool**
For the dashboard developers. Read `SPEC.md` for the findings and the story;
this document is the build contract.

Everything the dashboard needs is in `dashboard/data/`. No modelling, no
scraping, no data wrangling in the frontend — just read these tables.

---

## 0. Quick start

**You are building a static site. There is no backend, no database, no auth.**

```bash
# 1. serve it (fetch() is blocked over file://, so always serve)
cd dashboard
python -m http.server 8000
# open http://localhost:8000
```

Layout to build into:

```
dashboard/
  index.html          <- you create this
  app.js              <- you create this
  styles.css          <- you create this
  data/               <- ALREADY THERE. read-only. do not regenerate.
  build/              <- the scripts that produced data/. ignore them.
```

`dashboard/data/` currently holds **18 files, 280 KB total**. Copy nothing,
compute nothing: load them with `fetch('./data/<name>.csv')` and parse with
`d3-dsv` or `PapaParse` (both on CDN).

Two CDN dependencies only:

```html
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>
```

**If you need a field that is not in the tables below, do not derive it in JS.**
Ask whoever owns `dashboard/build/build_data.py` to add it and re-export. The
contract in §2 is frozen for that reason.

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

All files are in `dashboard/data/`, committed, CSVs, UTF-8, comma-separated,
built by `dashboard/build/build_data.py`.

### 2.1 `route_lines.geojson` — the map geometry

GeoJSON `FeatureCollection`, **15 features**, one per route.

```jsonc
{
  "type": "Feature",
  "properties": {
    "route_code": "R1",
    "route_name": "West Park to HM Phase 1",
    "colour": "#e9222a",       // official RTL colour - use it
    "n_stops": 18
  },
  "geometry": { "type": "LineString", "coordinates": [[73.504676, 4.169366], ...] }
}
```

- Coordinates are **[lon, lat]** (GeoJSON order). **Do not reverse them.**
- Already in stop order. Draw them as-is.
- Draw straight `LineString` polylines. **Do not snap to roads** — the map is
  schematic by design and snapping adds a dependency for no analytical gain.
- The first and last coordinate of R1/R2 are the same place (West Park and its
  opposite stop), so the line doubles back. That is correct, not a bug.

### 2.2 `route_stops.csv` — 184 rows (route-stop records), 7 columns

184 rows is **route × stop**, not unique stops: there are **97 unique
`stop_code` values** across the 15 routes. A stop that several routes serve
appears once per route, with its own `stop_order` on each.

| Column | Type | Example | Notes |
|---|---|---|---|
| `route_code` | str | `R1` | join key |
| `stop_order` | int | `1` | position along that route, 1-based |
| `stop_name` | str | `Maafannu Bus Terminal` | official English name |
| `stop_name_dv` | str | `މާފަންނު ބަސްޓާރމިނަލް` | official Dhivehi name (UTF-8) |
| `stop_code` | int | `103` | use this to de-duplicate stops across routes |
| `lat` | float | `4.169366` | |
| `lon` | float | `73.504676` | |

Real first three rows:

```csv
route_code,stop_order,stop_name,stop_name_dv,stop_code,lat,lon
R1,1,Maafannu Bus Terminal,މާފަންނު ބަސްޓާރމިނަލް,103,4.169366,73.504676
R1,2,Tow Yard,ޓޯޔާރޑް,304,4.169349,73.510249
```

### 2.3 `routes_master.csv` — 15 rows, one per route, OFFICIAL NAMING

This is the reference table. Use it for every route label in the UI.

| Column | Type | Example | Notes |
|---|---|---|---|
| `route_code` | str | `R1` | official RTL route number |
| `route_name` | str | `West Park to HM Phase 1` | **official English name** |
| `route_name_dv` | str | `އެޗްއެމް ފޭސް 1` | **official Dhivehi name** (UTF-8) |
| `colour` | str | `#e9222a` | official RTL route colour — use it on the map |
| `fare_mvr` | float | `10.0` | official fare |
| `is_minibus` | int | `0` | official flag (1 for R10–R15) |
| `depot` | str | `Greater Male'` | |
| `start_station` / `end_station` | str | `Maafannu Bus Terminal` | |
| `n_stops` | int | `18` | |
| `trips_per_day` | float | `61.0` | **official**; null for R10/R11/R12/R15 (feed returns no timings) |
| `trips_captured` | int | `40` | trips inside the captured window |
| `capture_first_departure` | str | `11:20:00` | null when nothing captured |
| `capture_last_departure` | str | `23:30:00` | |
| `bus_type` | str | `double decker bus` | from the team capacity table |
| `bus_model` | str | `Yutong ZK6116HGS` | |
| `seated_capacity` | int | `72` | **seats only** — the primary denominator |
| `max_passengers` | int | `84` | seats + permitted standing |
| `load_factor_comparable` | bool | `true` | `false` for R5/R6 (standing not stated) |
| `capacity_source` | str | `data/raw/mtcc_bus_capacity.csv (team, 2026-10-24)` | render as a tooltip badge |
| `corridor` | str | `male_hm1` | |
| `service_day` | str | `Saturday 2026-10-24 service day (feed is time-filtered)` | **render this somewhere visible** |

### 2.4 `demand_supply_gap.csv` — route × hour, the core table

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | |
| `hour` | int | 0–23 |
| `trips_in_hour` | int \| **null** | **null means "not captured", NOT zero** |
| `capture_status` | str | `captured` \| `before_capture_window` |
| `seated_capacity` | int | seats only — this table is seats-based |
| `seated_capacity_hour` | int \| null | `trips_in_hour × seated_capacity` |
| `demand_pax_est` | float \| null | modelled: MTCC level × Avas shape |
| `load_factor_pct` | float \| null | null where capacity is null |
| `unmet_pax_est` | float \| null | |
| `demand_source` | str | `NO DEMAND DATA` for the 10 routes without ridership |

> ⚠️ **Render `capture_status` explicitly.** Hours before ~11:00 are null. If
> you draw them as zero, the chart will claim there are no buses in the
> morning, which is false — we simply did not capture it.

### 2.5 `route_load.csv` — 15 rows, route-level

`route_code`, `route_name`, `bus_type`, `bus_model`, `seated_capacity`,
`max_passengers`, `load_factor_comparable`, `fare_mvr`, `trips_per_day`,
`seated_capacity_day`, `capacity_day_max`, `boardings_per_day`, `pax_per_trip`,
`load_factor_seats_upper_pct`, `load_factor_seats_avg_pct`,
`load_factor_capacity_upper_pct`, `load_factor_capacity_avg_pct`,
`demand_source`, `service_capture`.

> ⚠️ **Two denominators, and they disagree by a lot.** See ADR-0003.
> Lead with `load_factor_seats_*` (R1 = 104.4%). Show
> `load_factor_capacity_*` as secondary (R1 = 89.5%).
>
> Each pair is also a **band**: `_upper` assumes every boarding rides the full
> route, `_avg` assumes uniform alighting. Render the band, never one value.
>
> Where `load_factor_comparable` is `false` (R5, R6) all four load columns are
> null — show "not comparable", not zero. Routes with
> `demand_source = NO DEMAND DATA` likewise.

### 2.6 `service_departures.csv` — one row per captured trip

`route_code`, `trip_order` (official trip index, so you can see how many trips
are missing), `departure_time` (`"11:20:00"`), `departure_min`, `hour`.

Use for the timetable ribbon. `trip_order` starting at 22 for R1 is the visual
proof that the morning was not captured — show it, do not hide it.

### 2.7 `route_service_by_hour.csv` — route × hour

`route_code`, `hour`, `departures` (null if not captured), `captured` (bool),
`min_headway_min`.

### 2.8 `scenario_kpis.csv` — 5 rows

`scenario` (`S0_baseline`, `S2_airport_retimed`, `S3_rebalanced_to_corridor`,
`S4_express_peak`, `S5_recommended_package`), `mean_wait_min_captured`,
`boardings_over_capacity`, `unmet_share_pct`, `total_trips_captured`,
`demand_pax_captured`, `over_capacity_change`, `wait_change_min`,
`trips_change`.

> The Friday scenario (`S1`) has been **removed** — the feed returns a single
> service day, so a Friday service pattern cannot be observed. Do not add it.

### 2.9 `scenario_corridor_kpis.csv`

`scenario` × `route_code`, with `boardings_over_capacity`, `trips_captured`,
`mean_trips_per_hour`.

### 2.10 `demand_by_daytype.csv` — the demand-only day-type table

`route_code`, `day_type` (`weekday` \| `friday` \| `sat_holiday`),
`boardings_per_day`, `demand_source`. This is the F3 chart. **Demand only** —
say so in the caption; the matching service-side comparison is not available.

### 2.11 `bridge_segment_analysis.csv`

`route_code`, `from_stop`, `to_stop`, `median_segment_minutes`,
`median_end_to_end_minutes`, `n_trips`. The F1 chart. Highlight segments
≥ 10 min — they are the causeway crossings and the VIA terminal approach.

### 2.12 `airport_demand_profile.csv` — 24 rows

`hour`, `macl_share_pct`, plus the MBS Yearbook level columns and
`macl_coverage_of_intl_pct` (36.5). For F4, pair `macl_share_pct` against the
R4 departures share from `route_service_by_hour.csv`.

### 2.13 `taxi_od_by_hour.csv` — 2,387 rows

`zone_o`, `zone_d`, `hour`, `dow`, `rides`, `mean_km`, `mean_min`. Zones:
`Male City`, `Hulhumale Ph1`, `Hulhumale Ph2`, `Velana Airport`, `Villimale`,
`Other`.

### 2.14 `scenario_modal_shift.csv` — 36 rows (6 corridors × 6 scenarios)

The per-corridor generalised-cost comparison. Drives the F6 figure and the
"taxi capture" tile.

| Column | Type | Example | Notes |
|---|---|---|---|
| `scenario` | str | `S0_baseline` | six values, same keys as §2.8 |
| `corridor` | str | `male_hm1` | |
| `mean_wait_min` | float | `9.9` | demand-weighted |
| `bus_fare_mvr` | float | `10.0` | |
| `bus_ride_min` | float | `70.0` | observed end-to-end |
| `taxi_fare_mvr` | float | `85.0` | from the Avas fare matrix |
| `taxi_per_passenger_mvr` | float | `42.5` | fare ÷ sharing factor (2) |
| `taxi_ride_min` | float | `12.7` | observed median |
| `gc_bus_mvr` | float | `342.9` | fare + (wait + ride) × 250 MVR/h |
| `gc_taxi_mvr` | float | `116.2` | |
| `gc_gap_mvr` | float | `226.7` | bus minus taxi |
| `break_even_ride_min` | float | `15.6` | ride time at which the bus matches the taxi |
| `ride_min_to_shed` | float | `54.4` | **the headline number per corridor** |
| `p_taxi_to_bus_gc` | float | `0.0005` | logit probability on generalised cost |
| `p_taxi_to_bus_price_only` | float | `0.7471` | same logit with time valued at zero |
| `taxi_rides_per_day` | int | `1217` | observed |
| `capturable_rides_per_day` | float | `0.6` | `p × rides` |
| `capturable_rides_price_only` | float | `909.3` | |

> **Render `p_taxi_to_bus_gc` and `p_taxi_to_bus_price_only` side by side.**
> That pair is the whole argument: on price the bus wins (75%), on time it
> loses (0.05%). Showing only one of them would misrepresent the finding.

### 2.15 `scenario_modal_shift_summary.csv` — 6 rows

`scenario`, `taxi_rides_capturable_per_day`, `taxi_rides_capturable_price_only`,
`mean_gc_gap_mvr`, `min_ride_min_to_shed`, `taxi_rides_capturable_per_year`.
Use this for the "taxi capture" KPI tile: read
`taxi_rides_capturable_per_day` for the selected scenario.

### 2.16 `morning_service_inferred.csv` — 11 rows

A **route-day inference**, not hourly data. Morning departures were not
captured (the feed is server-clock filtered), so this bounds them instead.

| Column | Example | Notes |
|---|---|---|
| `route_code`, `route_name` | `R1` | |
| `trips_per_day` | `61` | official, complete |
| `trips_captured` | `40` | observed |
| `trips_before_capture` | `21` | **exact**: 61 − 40 |
| `assumed_service_start` | `06:00` | an assumption, tested in ADR-0011 |
| `morning_span_min` | `320` | first captured departure − 06:00 |
| `morning_avg_headway_min` | `15.2` | |
| `morning_avg_headway_min_low` / `_high` | `13.8` / `16.7` | band for a 06:30 / 05:30 start |
| `method`, `status` | | `status` starts with `INFERRED` |

> ⚠️ **Never plot this as hourly bars.** It is an average over 06:00–11:00 plus
> an assumption. Use it as a text statistic or a single range, and say
> "inferred". Putting it beside captured hourly bars would imply a resolution
> that does not exist. See ADR-0011.

### 2.17 Five traps that will silently break the UI

Read this before you write the chart layer. Each one produces a plausible but
wrong chart, which is worse than an error.

**1. `null` means "not captured", not "no bus".**
`demand_supply_gap.trips_in_hour` is null for every hour before ~11:00, because
the source feed is time-filtered (`capture_status` says so). If you plot those
as 0 the chart will claim there are no buses in the morning. Render them as a
gap — a shaded band, a dash, an explicit "not captured" label.

**2. `demand_pax_est` exists for hours that have no capacity.**
Demand is modelled for all 24 hours; service only for the captured ones. That
means you can legitimately show **24 hours of demand against 13 hours of
service** — and that juxtaposition is the clearest way to show the gap. Just
label the capacity series as partial.

**3. Load factor is a band, and there are two of them.**
`route_load` gives `load_factor_seats_upper_pct` / `_avg_pct` (seats, the
primary) and `load_factor_capacity_upper_pct` / `_avg_pct` (seats + standing).
Each pair differs by roughly 2×. Lead with seats; never present a single value.

**4. Ten routes have no ridership data at all.**
`demand_source = 'NO DEMAND DATA'` for R5, R6, R8, R9, R10, R11, R12, R13,
R14, R15. Do not render them as 0% — render them as unknown (grey, hatched,
or omitted with a count). Only 5 routes have any demand figure: R1, R2, R3,
R4, R7.

**5. Dhivehi needs a Thaana font.**
`route_name_dv` and `stop_name_dv` are Thaana script. Without a font that
carries the glyphs they render as empty boxes. Add to your CSS:

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thaana&display=swap');
.dv { font-family: 'Noto Sans Thaana', sans-serif; direction: rtl; }
```

Also verify in a browser, never in a terminal — terminals reorder RTL text and
make it look broken when it is fine.

**Minor:** `trips_in_hour` is a float (`2.0`), not an int. `hour` is 0–23 with
no zero-padding. `departure_time` is `"11:20:00"` (H:MM:SS), so slice it for
display.

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
│                                            │  │ ▓▓▓▓▓▓▓▓▓░░░░  90%   │  │
│   • 15 route polylines                    │  │ load factor band      │  │
│     coloured by load factor               │  │ 45% ──────── 90%      │  │
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
│  [S0 Baseline] [S2 Airport] [S3 Rebalance] [S4 Express] [S5 Package]        │
│                                                                             │
│  Over-capacity ▓ 360   Unmet ▓ 3.68%   Mean wait ▓ 10.9 min   Trips ▓ 162   │
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
- **Route metadata:** `routes_master.csv` is the lookup for every label on
  the map and in the panel — official English name, Dhivehi name, colour,
  fare, seats, trip counts.
- **Route lines:** from `route_lines.geojson` (which already carries
  `route_name` and the official `colour`). Default colour scheme:
  - `load_factor_seats_upper_pct` ≥ 100 → red `#e9222a` (over seat capacity)
  - 60–100 → orange `#ff7f0e`
  - < 60 → grey `#9aa0a6`
  - `NO DEMAND DATA` / not comparable → light grey, dashed
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
- **Optional demand layer:** a taxi-OD heat layer built from
  `taxi_od_by_hour.csv` (aggregate `rides` by pickup zone and hour) — this is
  the revealed-demand story and it is worth one toggle. Zone names are:
  `Male City`, `Hulhumale Ph1`, `Hulhumale Ph2`, `Velana Airport`, `Villimale`,
  `Other`. This table has **no coordinates** — place zones at the reference
  points you take from `route_stops.csv` (e.g. Maafannu Bus Terminal for
  Malé, Hiya Flats for HM Ph1, VIA Domestic Terminal for the airport).
- **Basemap note:** Malé is tiny (4 km). Default zoom 14, centre
  `4.195, 73.525`. Set `maxBounds` to the Greater Malé extent so the user
  cannot pan into the ocean.

### C2 — Route panel

Populated on route click. Contains:
1. **Header:** route code, official name, bus type, seats, fare, trips/day.
2. **Load-factor band:** a horizontal range bar showing
   `load_factor_seats_avg_pct` → `load_factor_seats_upper_pct`, with 100%
   marked. Label
   both ends. **Never render a single value.**
3. **Demand vs service chart** (the F2 chart, per route): dual-series bar
   chart by hour of day for the selected day-type:
   - bar 1 = `demand_pax_est` from `demand_supply_gap.csv`
   - bar 2 = `seated_capacity_hour` from the same table
   - a horizontal line at the point where demand exceeds capacity
   - day-type switcher: `weekday` / `friday` / `sat_holiday`
4. **Timetable ribbon:** for each hour, a small vertical tick per departure
   (from `service_departures.csv`), so the headway profile is visible.
5. **Day-type strip** (from `demand_by_daytype.csv`): boardings indexed to a
   weekday. Label it "demand only" — the service-side comparison is not
   available from a single-day capture.

### C3 — Scenario bar

- **Five** buttons: **S0 Baseline · S2 Airport re-timed · S3 Rebalanced to
  corridor · S4 Express peak · S5 Recommended package**. There is no S1 — the
  Friday scenario was withdrawn when the supply source changed (§2.8).
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
- The **capture window**: which hours were captured and which were not, and why (the feed is time-filtered).
- The **inferred morning** (`morning_service_inferred.csv`): one line stating
  that 06:00–11:00 is inferred, not observed (ADR-0011).
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
| S2 | Airport re-timed | +1 departure per hour for R3/R4/R9 in 11:00–15:00, −1 in 22:00–23:00. The peak-hour shift matters most for R3, which is currently an hourly bus |
| S3 | Rebalanced to corridor | 6 trips off the airport routes in the 13:00–14:00 lull, 6 onto R1/R2 at 16:00–18:00 (fleet-neutral) |
| S4 | Express peak | One extra R1/R2 departure in each hour 15:00–18:00, from the faster cycle a skip-stop service allows |
| S5 | **Recommended package** | S2 + S4. 118 fewer boardings over capacity, 1.2 points less unmet demand, 14 more trips inside the captured window — all re-timings, no new buses |

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
| **C** | C4 Methodology drawer + the six F1–F6 figures as static images | `docs/figures/*.png`, `DATA_SOURCES.md` |

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
   the load factor is shown as a **band on seats** (`load_factor_seats_upper_pct`
   and `_avg_pct`), with the seats+standing pair as secondary, never as a
   single number, and R5/R6 shown as "not comparable".
7. Routes without demand data are visibly marked as such — not drawn as 0%.
8. Hours outside the capture window are visibly marked as "not captured", not
   drawn as zero, and the captured window is stated on screen somewhere.
9. A Dhivehi route name renders as Thaana script, not as empty boxes.
10. The OSM attribution is in the footer.
11. It works at 1366×768 and projected at 1920×1080 (the pitch will be
    projected, and projector colour is worse than your monitor — check the
    red/orange/grey legend is still distinguishable).
12. Someone who did not build it can explain, in one sentence, what the red
    lines mean.

---

## 10. Where the numbers came from

| Figure | Source table(s) |
|---|---|
| F1 bridge | `bridge_segment_analysis.csv` |
| F2 load factors | `route_load.csv` |
| F3 day type | `demand_by_daytype.csv` |
| F4 airport | `airport_demand_profile.csv` + `route_service_by_hour.csv` |
| F5 scenarios | `scenario_kpis.csv` |
| F6 generalised cost | `scenario_modal_shift.csv` |

Pre-rendered PNGs of all six are in `docs/figures/` — you can drop them in
while the interactive versions are being built, and they are already sized
for slides.
