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

The interface is implemented in **`web/`** — React + TypeScript + Vite:

```
web/
  src/                <- App.tsx, components/, data.ts (the only data reader)
  scripts/sync-data.mjs  <- copies dashboard/data/ into the bundle before build
  dist/               <- build output (gitignored)
dashboard/
  data/               <- THE CONTRACT. read-only. do not edit by hand.
  build/              <- the scripts that produced data/. ignore them.
  index.html, app.js, styles.css   <- an earlier static prototype, NOT the app
```

`make web` builds it; `make serve` builds and serves it on :8000.

`src/data.ts` is the single reader of the contract. It joins on route code and
never hard-codes a figure; if a number on screen is wrong, the bug is there or
in the CSV, not in a component.

`dashboard/data/` currently holds **31 files, 756 KB total**. Copy nothing,
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

### 1.1 Panel → finding map

Every finding in `SPEC.md` must be *visible in the interface*, not only in the
README. If a panel does not carry its row, the story is not in the product.

| Finding | Where it must appear | The thing on screen |
|---|---|---|
| **F1** The Sinamalé Bridge is the journey (57% of R1's run) | Route panel, and the map | The two ≥ 10 min segments drawn heavier; a caption naming them and their 20 min each |
| **F2** Load is a segment, not a route | Route panel | The load band showing `load_factor_avg_pct` → `load_factor_peak_pct`, with the peak segment named and timed |
| **F2** The airport bus is full and hourly | Map + route panel for R3 | R3 in the ≥ 100% colour, with the headway ribbon showing one tick per hour |
| **F3** Demand by day type | Route panel | The day-type strip, labelled "demand only" (no service-side comparison exists) |
| **F4** Airport arrivals are tri-peaked, the bus is flat | Method drawer, or a toggle | Arrival share by hour against R4 departures by hour |
| **F5** Working hours carry 39% | Method drawer | The period bar with the working-hours window highlighted and the 37–42% band |
| **S5** Six trips remove 404 boardings | Scenario bar | The KPI tiles with deltas, and `trips_moved` — never a "trips added" figure |
| **Null results** (S2 −2, S4 one safe move) | Scenario bar | The failing scenarios must be selectable and must show their near-zero effect |

Two of these are negative results and one is a data gap. Show them anyway: a
tool that only displays the wins is a brochure, not a decision tool.

---

## 2. Data contract

All files are in `dashboard/data/`, committed, CSVs, UTF-8, comma-separated.
Rebuild with **`make data`** (or the scripts in this order):

```
build_data.py            -> *_base.csv  (raw route-level tables)
build_stop_demand.py     -> demand_supply_gap.csv, route_load.csv, §2.16-2.19
build_validation.py      -> validation_*.csv, airport_demand_profile.csv
build_schedule_crosscheck.py -> schedule_crosscheck*.csv
build_gtfs.py            -> data/derived/rtl_greater_male_gtfs.zip
build_figures.py         -> docs/figures/F1..F7.png
```

**`demand_supply_gap.csv` and `route_load.csv` each have exactly one writer**
(`build_stop_demand.py`). `build_data.py` writes `*_base.csv` instead, so running
it alone can no longer revert the refined demand and segment load factors. An
earlier version did exactly that, silently.

Verify the committed numbers reproduce from the raw sources with **`make check`**
(`build/verify_claims.py`, 92 independent checks, exit code 0 = all hold).

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
| `bus_type` | str | `Double decker` | team-provided |
| `seats` | int | `84` | team-provided — see `capacity_source` |
| `capacity_source` | str | `psmnews.mv/en/106008 (team-provided)` | render as a tooltip badge |
| `corridor` | str | `male_hm1` | |
| `service_day` | str | `Saturday 2026-10-24 service day (feed is time-filtered)` | **render this somewhere visible** |

### 2.4 `demand_supply_gap.csv` — route × hour, the core table

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | |
| `hour` | int | 0–23 |
| `trips_in_hour` | int \| **null** | **null means "not captured", NOT zero** |
| `capture_status` | str | `captured` \| `before_capture_window` |
| `seated_capacity` | int | seats per bus on this route |
| `seated_capacity_hour` | int \| null | `trips_in_hour × seated_capacity` |
| `demand_pax_est` | float \| null | modelled: MTCC level × Avas OD, **stop-allocated** (see §2.17) |
| `load_factor_pct` | float \| null | null where capacity is null |
| `unmet_pax_est` | float \| null | |
| `demand_source` | str | `NO DEMAND DATA` for the 10 routes without ridership |

> ⚠️ **Render `capture_status` explicitly.** Hours before ~11:00 are null. If
> you draw them as zero, the chart will claim there are no buses in the
> morning, which is false — we simply did not capture it.

### 2.5 `route_load.csv` — 15 rows, route-level

`route_code`, `route_name`, `bus_type`, `seated_capacity`, `max_passengers`,
`load_factor_comparable`, `fare_mvr`, `trips_per_day`,
`seated_capacity_day`, `boardings_per_day`, `pax_per_trip`,
`load_factor_peak_pct`, `load_factor_avg_pct`,
`load_factor_route_day_upper_pct`, `peak_segment_id`, `peak_segment`,
`peak_segment_hour`, `demand_source`,
`service_capture` (e.g. `40 of 61.0 trips captured`).

**These three load-factor columns mean different things — read them carefully:**

| Column | Meaning |
|---|---|
| `load_factor_route_day_upper_pct` | The **old, superseded** figure: `daily_boardings ÷ (trips_per_day × seats)`. Assumes every passenger rides the whole route. It is an upper bound, not a peak. Kept for reconciliation only. |
| `load_factor_peak_pct` | **The headline.** The fullest stop-to-stop segment in any captured hour, as a % of seats. |
| `load_factor_avg_pct` | Mean across all captured segment-hours. |

> ⚠️ **Changed on 2026-10-24 (Dev B task 1).** `load_factor_peak_pct` and
> `load_factor_avg_pct` are **no longer the route-day band** — they are
> segment-based. R1 moves from 104.4% / 44.7% to **90.1% / 63.2%**. The old
> number is preserved in `load_factor_route_day_upper_pct`, so the two cannot be
> confused. Use `peak_segment` + `peak_segment_hour` for the caption
> (`Hulhumale' Police Station → Amin Avenue, 22:00`).
>
> Note the peak hour is often **late**, because service thins out while demand
> persists — not because 22:00 is the busiest hour. R1's demand peaks at 16:00.
> If your chart implies "22:00 is the peak hour", use
> `route_segment_summary.csv` → `load_factor_at_demand_peak_pct` instead.

Routes with `demand_source = NO DEMAND DATA` must be shown as such, not as zero.

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
`demand_pax_captured`, `trips_moved`, `over_capacity_change`, `wait_change_min`,
`trips_change`.

> ⚠️ **Changed 2026-10-24 — scenarios are now fleet-neutral.** Every scenario
> *moves* trips instead of adding them, so **`trips_change` is 0 for all five**
> and `total_trips_captured` is 162 everywhere. Do not show a "trips added"
> figure: show **`trips_moved`**, which is 0 / 2 / 5 / 1 / 6. The build
> asserts neutrality, so a non-zero `trips_change` means a bug, not a result.

> ⚠️ **Changed again 2026-10-24 — donors are now guarded.** A trip may only be
> taken from an hour that stays within 100% of seats *after* losing it, and a
> move that is later undone is cancelled rather than counted. This is why the
> move counts are small: the corridor has almost no spare buses. Do not
> reintroduce an unguarded reallocator to make the numbers look better.

> ⚠️ **The recommended package changed content.** S5 was `S2 + S4`; it is now
> `S3 + S4`, because on measured data airport re-timing alone relieves only 2
> boardings while cross-corridor reallocation relieves 348. If any copy says
> "S5 = airport re-timing + express peak", update it.

> `total_trips_captured` counts only the **five routes with ridership data**
> (162 of the 430 trips captured network-wide). Label it "trips on evaluated
> routes" if space allows.

> The Friday scenario (`S1`) has been **removed** — the feed returns a single
> service day, so a Friday service pattern cannot be observed. Do not add it.

### 2.8.1 `scenario_moves.csv` — one row per individual trip move (NEW)

`scenario`, `from_route`, `from_hour`, `to_route`, `to_hour`, `trips`,
`donor_load_pct`, `donor_unmet_before`, `receiver_unmet_before`,
`receiver_unmet_after`.

This is the audit trail and the best animation source: each row is one bus
being taken off one hour and put on another, with what it fixed. Use it for the
"trips reassigned" table rather than inventing numbers.

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
≥ 10 min — they are the crossings of the Sinamalé Bridge and the VIA terminal approach.

### 2.12 `airport_demand_profile.csv` — 24 rows

`hour`, `macl_share_pct`, plus the MBS Yearbook level columns and
`macl_coverage_of_intl_pct` (40.2; the adult-only figure is 36.47 and lives in
`validation_airport.csv`, not here). For F4, pair `macl_share_pct` against the
R4 departures share from `route_service_by_hour.csv`.

### 2.13 `taxi_od_by_hour.csv` — 2,387 rows

`zone_o`, `zone_d`, `hour`, `dow`, `rides`, `mean_km`, `mean_min`. Zones:
`Male City`, `Hulhumale Ph1`, `Hulhumale Ph2`, `Velana Airport`, `Villimale`,
`Other`.

### 2.14 `scenario_modal_shift.csv` — 36 rows (6 corridors × 6 labels)

The per-corridor generalised-cost comparison. Drives the F6 figure and the
"taxi capture" tile.

> ⚠️ **The `scenario` keys do NOT match §2.8.** This file predates the
> fleet-neutral rebuild and still carries two labels that no longer exist in
> `scenario_kpis.csv`:
>
> | label in this file | status |
> |---|---|
> | `S0_baseline`, `S2_airport_retimed`, `S3_rebalanced_to_corridor` | current — safe to join |
> | `S4_express_added` | **superseded** by `S4_express_peak`; it assumed *added* trips, so its probabilities are not comparable to the fleet-neutral scenario |
> | `S1_friday_right_sized` | **withdrawn** (ADR-0009) — a Friday service pattern cannot be observed from a one-day capture |
>
> **Do not join S4 or S1 from this file to the scenario bar.** Show the S0
> row for the taxi-capture tile (190.6 rides/day). The two keys are a known gap:
> the file has no build script (see `DATA_SOURCES.md` §2b), so it cannot be
> regenerated on the current definitions without one.

| Column | Type | Example | Notes |
|---|---|---|---|
| `scenario` | str | `S0_baseline` | six labels — see the warning above |
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
Same six labels and the same caveat as §2.14: read the `S0_baseline` row
(190.6 rides/day) for the "taxi capture" tile; `S1` and `S4` are stale keys.

> The 190.6 and 210.2 figures in this table bracket the **taxi capture** claim
> (12–3,001 rides/day across the VOT × sharing sensitivity in METHODS §5), not
> the 62–76% price share, which comes from §2.14's probability columns.

### 2.16 `demand_by_stop.csv` — 184 rows, stop-level boardings (NEW)

Built by `dashboard/build/build_stop_demand.py`, which runs **after**
`build_data.py`. One row per route × stop.

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | |
| `stop_order` | int | 1-based, joins `route_stops.csv` |
| `stop_code` | int | official RTL code |
| `stop_name` / `lat` / `lon` | | |
| `daily_boardings` | float \| **null** | null for the 10 routes with no ridership level |
| `daily_alightings` | float \| **null** | measured from taxi **destinations**, not assumed symmetric |
| `avas_rides_per_day` | float | Saturday rides whose origin snapped to this stop |
| `boarding_share_pct` | float | share of the route's boardings |
| `stop_role` | str | `interchange` where share ≥ 10%, else empty |
| `method` / `demand_source` / `catchment_m` | | provenance, for a tooltip |

Sum of `daily_boardings` per route **equals** `demand_by_daytype` exactly
(verified to ±0.2 pax). Safe to use as the source of truth for stop sizing.

### 2.17 `load_by_segment.csv` — 4,344 rows, the real load factor (NEW)

route × segment × hour. This is what "load factor" should have meant.

| Column | Type | Notes |
|---|---|---|
| `route_code` | str | |
| `segment_id` | str | e.g. `R1-S12` |
| `from_stop_order` / `from_stop` / `to_stop_order` / `to_stop` | | the segment |
| `segment_km` | float | great-circle length |
| `hour` | int | 0–23 |
| `passengers` | float \| null | null where no ridership level exists |
| `seated_capacity_hour` | float \| **null** | **null = not captured** |
| `load_factor_pct` | float \| null | null where either side is null |
| `capacity_basis` | str | `observed` \| `not_captured` |
| `demand_source` | str | |

> Only 5 routes (R1, R2, R3, R4, R7) have load factors. 4,344 rows = 181
> segments × 24 hours.

### 2.18 `route_segment_summary.csv` — 15 rows, the reconciliation (NEW)

`route_code`, `peak_segment_id`, `peak_segment_from`, `peak_segment_to`,
`peak_segment_hour`, `peak_segment_passengers`, `peak_segment_capacity`,
`load_factor_segment_peak_pct`, `demand_peak_hour`,
`load_factor_at_demand_peak_pct`, `load_factor_segment_mean_pct`,
`load_factor_route_day_upper_pct`, `scale_factor`, `rides_considered`,
`rides_in_catchment`, `rides_dropped_backtrack`, `catchment_share_pct`.

`scale_factor` ≈ 2.7–3.4 means bus boardings are that many times the observed
taxi rides on the same corridor. It is a sanity check, not a result.

### 2.19 `segment_load_sensitivity.csv` — 45 rows (NEW)

`route_code`, `catchment_m` (400/600/800), `topology`, `rides_in_catchment`,
`peak_segment_load_pct`. Use this if a judge asks whether the 600 m catchment
drove the answer. It did not: R1 is 89.2 / 90.1 / 90.5%.

### 2.20 `validation_holdout.csv` — 13 rows, does the model predict reality (NEW)

Built by `dashboard/build/build_validation.py`. One row per model × route.

| Column | Type | Notes |
|---|---|---|
| `test` | str | `chronological_80_20` |
| `model` | str | `M0_route_mean`, `M1_route_x_daytype`, `M2_daytype_plus_trend` |
| `route_code` | str | `R1`, `R2`, `R4`, `ALL`, `ALL_SATURDAY_ONLY` |
| `mape_pct` / `mdape_pct` / `p90_ape_pct` | float | mean / median / 90th-percentile absolute % error |
| `bias_pct` | float | positive = model under-predicts |
| `n` | int | held-out route-days |

Use `model = M1_route_x_daytype` and `route_code = ALL` for the headline:
**9.91% MAPE against a 16.27% naive baseline**. Always show the baseline next
to it — a MAPE with no baseline proves nothing.

### 2.21 `validation_airport.csv` — 11 rows, the three-way reconciliation (NEW)

`test`, `quantity`, `sources`, `value`, `expected`, `mechanism`, `verdict`.

Read `verdict`: `PASS` / `PLAUSIBLE` / `INFO` / `FLAG` / `FAIL`. The `mechanism`
column exists so a judge can see *why* a number is not 100%, not just that it
is not.

### 2.22 `validation_summary.csv` — 15 rows, one line per check (NEW)

`check`, `scope`, `metric`, `value`, `baseline`, `verdict`. This is the tile:
"N checks, N pass, N flag". Do not hide the flags — the flags are the finding.

### 2.23 `airport_demand_profile.csv` — 24 rows, now reproducible

Rebuilt by `build_validation.py` from a stated definition: 2025 international
flights, hour = scheduled arrival, **passenger-weighted**.

> ⚠️ **This file changed on 2026-10-24.** `macl_share_pct` is now
> passenger-weighted 2025, not an unspecified 2019–25 basket. The
> 07:00–09:59 share moves 35.5% → **33.1%**. `macl_international_arrival_share`
> is retained as the flight-weighted share for the audit. If your chart says
> "35.5%", change it to 33.1% and state the weighting.

### 2.24 `schedule_crosscheck.csv` — 14 rows, feed vs published timetable (NEW)

Built by `dashboard/build/build_schedule_crosscheck.py`. Validates the supply
side against MTCC's own published PDFs.

`route_code`, `pdf_block_used`, `pdf_bands`, `pdf_vintage`,
`pdf_trips_per_day`, `pdf_trips_after_midnight`, `feed_trips_per_day`,
`diff_trips`, `diff_pct`, `pdf_trips_in_captured_window`,
`feed_trips_in_captured_window`, `hourly_mae_captured`,
`hourly_max_abs_diff`, `verdict`, `note`.

> ⚠️ **Read `verdict`, not `diff_pct`.** `diff_pct` is the *daily* difference
> and it is confounded: the PDFs are a Ramadan 2025 edition and the feed is a
> regular October 2026 day, so they are meant to differ. The verdict is based on
> `hourly_mae_captured` (≤ 1.0 trips/hour). All 11 checkable routes pass;
> median error is 0.27 trips/hour.
>
> If you show a chart, show **hourly MAE per route** with the threshold line. A
> daily-difference chart would look alarming and mean nothing.

### 2.25 `schedule_crosscheck_hourly.csv` — 140 rows (NEW)

`route_code`, `hour` (11–23 only), `pdf_departures`, `feed_departures`, `diff`.
This is the comparable series and the honest way to visualise the check.

> Only the captured window is present. Hours before 11:00 have no `feed` value,
> so they are absent rather than zero — do not interpolate across the gap.

### 2.27 `morning_service_inferred.csv` — 11 rows

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

### 2.28 `usage_by_period.csv` — route × period, plus an `ALL` row per period

Bus usage split by day period. Periods are non-overlapping and sum to the day.

| Column | Example | Notes |
|---|---|---|
| `route_code` | `R1` \| `ALL` | `ALL` is the network total |
| `period` | `working_hours` | `night`, `am_commute`, `working_hours`, `pm_commute`, `evening`, `late` |
| `hours_in_period` | `8` | |
| `hours_captured` | `5` | **service** hours observed in that period |
| `hours_not_captured` | `3` | demand exists, service does not |
| `boardings_est` | `1420.5` | modelled from the MTCC level × Avas shape |
| `trips_captured` | `41.0` | captured departures only |
| `seated_capacity` | `2952.0` | |
| `load_factor_seats_pct` | `48.1` | null where nothing was captured |
| `share_of_route_demand_pct` | `39.0` | share of that route's (or the network's) day |

> ⚠️ The **demand** side of every period is complete (24 hours modelled). The
> **service** side is not: `hours_captured` < `hours_in_period` before ~11:00.
> Do not compute a load factor for a period with `hours_captured = 0`.

### 2.29 `working_hours_sensitivity.csv` — 5 rows

`working_window`, `share_of_daily_demand_pct`, `hours_captured_in_window`,
`hours_in_window`, `trips_captured_in_window`.

Use this to caption F7. The headline is 08:00–16:00 = **39%**, and the point
of the table is that 07:00–15:00 and 09:00–17:00 give 37% and 42% — the claim
survives an hour of slop either way.

### 2.32 `route_segments.geojson` — road-snapped legs (NEW)

`dashboard/build/snap_routes.py` routes every stop-to-stop leg over
OpenStreetMap roads with OSRM, so the Malé → Hulhumalé legs follow the
Sinamalé Bridge instead of cutting across the sea. Committed output; the script
needs network access, so it is **not** part of `make`.

One feature per leg. `route_code`, `seq` (1-based, joins `route_stops.stop_order`),
`from_stop`, `to_stop`, `from_code`, `to_code`, `road_m`, `straight_m`,
`loop_removed_m`, `snap_from_m`, `snap_to_m`, `median_segment_minutes`,
`bridge` (bool: the scheduled leg is ≥ 10 min, i.e. a crossing or the VIA
approach). Geometry is `[lon, lat]`.

Covers Malé, the airport island and Hulhumalé. R13/R14 (Villimalé) are absent,
which is why `routes_master` shows them as not on the map.

### 2.33 `basemap.geojson` — the offline basemap (NEW)

`dashboard/build/build_basemap.py`: one Overpass query, output committed. No
tile server, so the dashboard works with no network and no API key.
`FeatureCollection` where each feature has `properties.kind` = `land` or `road`
(with `properties.class` = `major` / `minor` for roads).
Attribution: **© OpenStreetMap contributors**, ODbL — it must stay visible.

### 2.34 `stop_snap_qa.csv` — stop placement check (NEW)

Distance from each stop to the nearest road, for auditing the snap. QA only;
the app does not read it.

### 2.30 Design precedent to follow

`https://data.pension.gov.mv/` is the Maldives Pension Administration Office
data portal — a Looker Studio dashboard embedded in a page. It is the nearest
thing to a house style for Maldives government data, and judges will recognise
it. Six things it does that we should copy:

1. **Hero numbers as plain text, not charts.** Three or four large figures
   (`30.3B`, `16.5M`, `124.7M`, `26,468`) with a one-line caption each. Our
   equivalent: **104.4%** of R1's seats · **39%** of demand in working hours ·
   **60 min** R3 headway · **10.04%** unmet demand.
2. **A narrative sentence per chart**, not a bare axis. Every panel gets a line
   of plain English saying what it shows and why it matters.
3. **Source under every figure.** The pension portal writes
   *"Census Source: Maldives Bureau of Statistics (2022), Table EC6"* directly
   beneath the chart. We already carry provenance in the data; surface it in
   the UI. This is the single strongest credibility signal available.
4. **A data-vintage line at the top.** Theirs: *"Data is updated on the 10th of
   each month."* Ours must say: *"Service captured 11:00–24:00, Saturday
   2026-10-24. Demand 2025."*
5. **Simple chart types only** — donut for composition, bar/line for series.
   No sankey, no radar, no 3D.
6. **Visible data access.** They have a "Request for Data" affordance. Our
   equivalent is the link to `DATA_SOURCES.md` and the repo.

**Do not copy** their lack of interactivity. Their charts are static images;
ours must respond to scenario selection, because that is the whole product.

### 2.31 Five traps that will silently break the UI

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

**3. Load factor is a segment, not a route.**
`route_load.load_factor_peak_pct` is now the fullest **stop-to-stop segment**,
not a route-day average. It is generally *lower* than
`load_factor_route_day_upper_pct` (R1: 90.1% vs 104.4%), because passengers get
off along the way. Do not add the two, average them, or treat the old bound as
a range — the upper bound is a superseded figure kept only for reconciliation.
For the "where is the bus full?" story use `load_by_segment.csv` and name the
segment and hour.

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

**6. Villimalé has no taxi data, so R13/R14 have no segment demand.**
Avas has zero pickups west of 73.495; the Villimalé stops sit at 73.483–73.486.
R13/R14 therefore have `daily_boardings = null` and no rows with a load factor.
This is a **coverage gap in the source**, not a modelling failure. Say so on the
chart rather than greying them out with the same treatment as R5/R6 (which lack
a ridership *level*, a different reason).

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
│   • 184 route-stop records                 │  └───────────────────────┘  │
│   • bridge segments highlighted            │  Trips/day 61  Boardings    │
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
│  Over-capacity ▓ 1,009  Unmet ▓ 10.04%  Mean wait ▓ 10.8 min  Trips ▓ 162  │
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
  - `load_factor_peak_pct` ≥ 100 → red `#e9222a` (over capacity)
  - 60–100 → orange `#ff7f0e`
  - < 60 → grey `#9aa0a6`
  - no demand data → light grey, dashed
- **Line weight:** 4 px for the selected route, 2 px otherwise.
- **Stops:** circle markers, radius 3 (2 when zoomed out), white fill, grey
  stroke. Tooltip = stop name + which routes serve it.
- **Bridge segments:** render segments with `median_segment_minutes` ≥ 10
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
- **Rendered basemap (React app, `web/src/mapArea.js`):** OSM raster tiles as
  the base, `HOME_BOUNDS` fit to the **whole network including Villimalé**
  (`R13`/`R14`, lon ~73.483 — a box that stops at 73.497 silently loses two
  routes). Pan limit `PAN_BOUNDS` is deliberately wider than the fit so the
  coast and the Sinamalé Bridge read as context; `MIN_ZOOM` 12. A committed
  OSM-derived vector outline (`dashboard/build/build_basemap.py`) is the
  offline fallback and a manual toggle: if no tile loads and three tile
  requests fail, the map switches itself rather than showing an empty box.
  Every route must be drawn, including the ten with no passenger counts —
  "dashed" means *no counts*, never *not there*.

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
- The **coverage matrix**: route × what we have (demand data yes/no, live
  trip count yes/no, published schedule yes/no). This is a *feature* — the
  datathon asks for data-gap identification, so make the gaps visible.
- The **MACL coverage** number (40% of international arrivals, 0% domestic) and that it carries no seasonal signal
  with a link to MBS Yearbook 11.13.

---

## 5. Scenario definitions (for the tooltip text)

| Key | Label | What it does |
|---|---|---|
| S0 | Baseline | — |
| S2 | Airport re-timed | 2 trips from the airport routes' late-night hours into their own under-served hours (R4 22:00/23:00 → R4 11:00, R3 13:00). Measures near-null at route-hour level: the crowding is on one segment |
| S3 | Rebalanced to corridor | 5 trips off the airport routes' afternoon lull onto R1 wherever it is over capacity (fleet-neutral) |
| S4 | Express peak | Corridor off-peak trips re-timed into the corridor peak — but with the donor ceiling enforced only **one** move is safe (R2 12:00 → R1 16:00), because every other R1/R2 off-peak hour is already at 83–166% load |
| S5 | **Recommended package** | S3 + S4. 404 fewer boardings over capacity (1,009 → 605), unmet demand 10.0% → 6.0%, six trips re-timed — no new buses |

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
(Mapbox GL needs a token; Deck.gl is overkill for 15 lines and 184 route-stop points).

---

## 7. Scope guard — what NOT to build

Cut these without discussion. Time is the binding constraint.

- ❌ A login, a backend, a database. Everything is static.
- ❌ User-uploaded data, editable tables, or a data-entry form.
- ❌ A live-data refresh from the RTL API (needs a JWT; see the research
  notes for the endpoint if someone has time).
- ❌ A camera/crowd-detection feature. It is not a dashboard panel; sensor-based
  counting is a separate later phase with its own entry conditions
  (`docs/ROADMAP.md` §2, ADR-0013).
- ❌ A second basemap layer, terrain, 3D buildings, or satellite tiles. (The
  committed vector outline is a fallback for the same canvas, not a second
  selectable commercial basemap.)
- ❌ Animated vehicles on the map. There is no live vehicle data.
- ❌ More than 4 panels. If you have time, add the per-corridor before/after
  view, not a fifth panel.

---

## 8. Suggested split for the dashboard developers

| Dev | Build | Depends on |
|---|---|---|
| **A** | C1 Map + C2 Route panel | `route_lines.geojson`, `route_stops.csv`, `demand_supply_gap.csv` |
| **B** | C3 Scenario bar + KPI tiles | `scenario_kpis.csv`, `scenario_corridor_kpis.csv`, `scenario_modal_shift_summary.csv` |
| **C** | C4 Methodology drawer + the seven F1–F7 figures as static images | `docs/figures/*.png`, `DATA_SOURCES.md` |

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
4. Clicking each of the five scenario buttons updates every KPI tile, with
   deltas.
5. The live "trips reassigned" slider moves the over-capacity tile and is
   labelled as an interpolation.
6. Every modelled number carries a tooltip explaining it is modelled, and
   the load factor is shown as a **peak segment**, named and timed
   (`load_factor_peak_pct` + `peak_segment` + `peak_segment_hour`), never as a
   single unattributed route percentage.
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
