# SPEC — *Raajje Rebalancer*
## A data-driven bus supply decision tool for Greater Malé

**Maldives Datathon 2026 · Team Wayfinders (3 dev + 1 report) · 10-hour build**

> *Raajje* is the Maldivian name for the Hulhumalé causeway. It is the
> bottleneck under every number in this document, and it is the reason this
> project is not about fares.

---

## 1. The problem, restated precisely

Greater Malé's bus network is not short of passengers. It is short of the
**right bus, in the right place, at the right hour**. Three things go wrong
simultaneously:

1. **The busiest corridor runs over capacity** while airport buses run at
   58–80% of their seats.
2. **The schedule is static while demand is not.** Friday demand is 37% below
   a weekday, but Friday service falls only 9–22%.
3. **The journey itself is the competitive problem.** A taxi is 8.5× the fare
   and still wins, because the bus spends 57% of its journey time in two
   causeway crossings.

The deliverable is a **decision tool**: an operator can move buses between
routes, hours and days, and see the passenger-level consequences before
committing a single vehicle.

---

## 2. What we are building

```
RAJJE REBALANCER
├── RECONCILED DATASET   route × day-type × hour demand vs supply, with
│                        per-row provenance (observed / derived / modelled)
├── SCENARIO ENGINE      6 named scenarios, each producing passenger KPIs
├── MODAL-SHIFT LAYER    will a young Maldivian actually leave the taxi?
└── DASHBOARD            interactive GIS map + scenario sliders + before/after
```

**Success = a planner can open it, move 6 trips, and read the consequence.**
Not a dataset with a slide attached.

### 2.1 GTFS feed (deliverable)

`data/derived/rtl_greater_male_gtfs.zip` is a synthesised GTFS feed for the
Greater Malé bus network. **No public GTFS exists for Malé**, so this is the
first one.

Built by `dashboard/build/build_gtfs.py` directly from the official RTL 2026
payload, which carries per-stop timings for every trip — so `stop_times` is
**rounded to the observed schedule, not interpolated from an assumed speed**.

| | |
|---|---|
| Service day | Saturday 2026-10-24 (single day, from ~11:00 — the capture window) |
| Routes with service | 11 of 15 (R10/R11/R12/R15 return no timings) |
| Trips | 450 |
| Stops | 61 distinct (official RTL stop codes) |
| `stop_times` | 5,538 |
| Drop-off-only stops | 112, encoded as `pickup_type=1` |

**Validated with the official MobilityData `gtfs-validator` 6.0.0: 0 errors,
2 warnings.** Both warnings are inherent to a one-day feed rather than defects:
`feed_expiration_date7_days` and `trip_coverage_not_active_for_next7_days`. The
full report is committed as `data/derived/gtfs_validator_report.json`.

Honest limitations, all visible in the feed rather than hidden: the morning
peak is absent because the source endpoint is filtered from the moment of the
call; 32 trips are only partially timed and ship with only the stops that have a
real timestamp; and four routes have no service in the feed at all because the
operator publishes no timings for them through this endpoint.

---

## 3. Architecture

| Layer | Grain | Method | Data |
|---|---|---|---|
| **Supply** | route × hour | official RTL 2026 departures per stop | RTL `v2/bus/routedetails` (S1) |
| **Demand — level** | route × day-type | observed boardings | MTCC `bus_daily` (R1/R2/R4, 2025) + `bus_monthly` (R3/R7) × day-type index |
| **Demand — shape** | hour of day | revealed preference on the same corridor | Avas taxi OD × hour (D2) |
| **Demand — airport** | hour of day | observed arrival profile | MACL hourly (D3) for shape; MBS Yearbook 11.13 (S4) for level, incl. **domestic** |
| **Capacity** | route | vehicle type × seats | team domain knowledge (see §7) |
| **Geometry** | stop | lat/lon, route order | official RTL stop list (S1) |

**Every output row carries `source` and `method`**, so a judge can audit any
cell and see whether it is observed or modelled. This is deliberate: the
datathon's judges are statisticians.

---

## 4. Findings (all computed, all reproducible)

### F1 — The causeway is the journey time

From the official RTL 2026 feed, R1's end-to-end scheduled run
(West Park → Hulhumalé Phase 1) is **70 minutes**:

| | |
|---|---|
| R1 end-to-end (18 stops) | **70 min** |
| STELCO → Hulhumale' Cemetery (Malé → Hulhumalé crossing) | **20 min** |
| Hulhumale' Cemetery OPP → Male' Swimming Track (return crossing) | **20 min** |
| the other 16 stop-to-stop segments | mostly 2 min each |
| **share of the journey spent in the two crossings** | **40 of 70 min = 57%** |
| R2 end-to-end | 67 min, **40 min (60%) in the two crossings** |
| R7 end-to-end | 40 min, one 20-min crossing |
| same journey by taxi (observed median, Avas) | **12.7 min** |

Internal Hulhumalé routes that never cross (R5, R6) show 3–5 min per segment.
The contrast is the evidence: the causeway, not the stop spacing, is the
bottleneck. The bus is **4.4× slower than a taxi** on the corridor where it is
also 8.5× cheaper.

### F2 — One corridor carries nearly all the load; the airport buses do not

**Load factor at the segment, not the route** (captured Saturday, 11:00–24:00):

| Route | Official RTL name | Bus type | Seats | Trips/day | Boardings/day | Route-day upper bound | **Peak segment** | Where |
|---|---|---|---|---|---|---|---|---|
| **R1** | West Park to HM Phase 1 | Double decker | 84 | 61 | 4,585 | 89.5% | **77.3%** | Hulhumalé Police Stn → Amin Ave, 22:00 |
| **R3** | West Park to VIA | Airport bus | 52 | 20 | 752 | 72.3% | **104.1%** | STELCO → VIA, 13:00 |
| R4 | HM Phase 1 to VIA | Airport bus | 52 | 38 | 1,014 | 51.3% | 89.2% | HM Cemetery → VIA, 11:00 |
| R7 | HM Phase 2 to West Park | Double decker | 84 | 66 | 3,552 | 64.1% | 63.7% | STELCO → MWSC Flat, 22:00 |
| R2 | Carnival to HM Phase 1 | Double decker | 84 | 61 | 3,447 | 67.3% | 58.0% | Centro Mall → CHSE, 22:00 |

Ten routes have **no ridership data at all** (R5, R6, R8–R15) and are marked
`NO DEMAND DATA` rather than zero-filled.

> **The 89.5% figure was an upper bound, and it was labelled "peak". It is now
> reconciled.** `daily_boardings ÷ (trips_per_day × seats)` assumes every
> passenger rides the whole route. Distributing each route's measured boardings
> across its own stops using the Avas catchment, then accumulating on-minus-off
> along the stop order, gives a peak **segment** load factor instead.
>
> For R1 that is **77.3%** — lower than the bound, as it must be, because
> passengers alight along the way. The route-day number overstated crowding on
> R1 by about 12 points. It *understated* crowding on R3, whose airport segment
> genuinely exceeds 100% while its route-day average is 72%.
>
> Both figures are kept side by side (`load_factor_route_day_upper_pct` vs
> `load_factor_peak_pct`) so the correction is auditable rather than silent.

> **The peak hour is late, and that is a service finding, not a demand one.**
> R1's demand peaks at 16:00, but its fullest segment occurs at 22:00 when the
> timetable thins to 2 trips/hour. `route_segment_summary.csv` reports
> `load_factor_at_demand_peak_pct` (R1: 69.9%) separately so the two cannot be
> conflated.

> **Read the load numbers with the service day in mind.** The captured feed is
> one service day (Saturday), so boardings and trips are paired correctly.
> Weekday boardings on R1 are 13.7% higher than Saturday (5,212 vs 4,585).
> A weekday capture is needed to confirm — see §12.

### F3 — Demand varies sharply; the service day cannot be compared from one capture

MTCC ridership, 2025, observed on the routes with daily data:

| Route | Mon | Tue | Wed | Thu | **Fri** | Sat | Sun |
|---|---|---|---|---|---|---|---|
| R1 | 5,132 | 5,177 | 5,344 | 5,361 | **3,192** | 4,585 | 5,043 |
| R2 | 3,756 | 3,908 | 3,908 | 3,859 | **2,427** | 3,447 | 3,655 |
| R4 | 1,122 | 1,140 | 1,152 | 1,168 | **722** | 1,014 | 1,145 |

**Friday demand is 37–38% below Thursday on every route**, and R1 swings +23%
between February and July. Free-of-charge passengers (65+, PWD, infants) are
27–35% of boardings, so a large share of demand cannot be flexed off-peak.

**What this does not yet tell us.** Whether the *service* tracks those swings
needs a timetable for each day-type. The RTL feed returns the current service
day only, so the earlier Friday service-versus-demand comparison is withdrawn
until a Friday and a weekday capture are taken. This is the clearest data gap
in the project and the fix is one scheduled call (§12).

### F4 — The airport buses run a flat frequency all day; arrivals are tri-peaked

Official RTL 2026 departures, captured window:

| Route | Departures per hour | Headway | Expected wait |
|---|---|---|---|
| **R3** (Malé ↔ Airport) | **1, every hour**, 11:00–23:00 | **60 min** | **30 min** |
| R4 (HM Ph1 ↔ Airport) | 2 per hour, 12:00–23:00 | 30 min | 15 min |
| R1 (Malé ↔ HM Ph1) | 2–4 per hour, building to 4 at 16:00–19:00 | 15–30 min | 7.5–15 min |

R3 is literally an **hourly bus with a 30-minute expected wait**. Meanwhile
airport arrivals peak hard in the morning. MACL 2025, international flights,
**passenger-weighted** (people, not aircraft — the weighting matters, see below):

| Hour | % of arriving passengers |
|---|---|
| 07:00 | 10.29% |
| 08:00 | 10.08% |
| 09:00 | 12.70% |
| 11:00 | 12.70% |
| 14:00 | 9.40% |
| **07:00–09:59 combined** | **33.1%** |

**A third of arriving passengers land in a three-hour window**, and the airport
buses run the same frequency at 03:00 as at 08:00. Nothing runs at all between
00:00 and 06:00, when 4.3% of passengers arrive.

> **This figure depends on how you weight it, so the weighting is now stated.**
> Passenger-weighted, 07:00–09:59 carries **33.1%** of arrivals. Flight-weighted
> it is only **25.3%**, and the largest three-hour window moves to midday
> (27.9% ending 13:00) — because the morning is a widebody bank (37.7% of
> widebody flights, 43.7% of widebody passengers) while midday is many small
> narrowbodies. For a *bus demand* question the passenger weighting is the
> correct one: an empty 300-seat widebody and a full 50-seat turboprop are not
> one busload each.
>
> The previously quoted **35.5%** came from a wider 2019–25 window and could
> not be reproduced exactly from the current extract. The reproducible 2025
> figure is 33.1%, a drift of 2.8 points that does not change the finding.
> `airport_demand_profile.csv` now has a builder (`build_validation.py`) and a
> stated definition, where before it was a committed file with no provenance.

**MACL is a sample, not a census — and this is now measured.** It holds
1,084,115 passenger arrivals in 2025 against the Yearbook's 2,699,225
international arrivals (**40.2% coverage**), spread over a near-constant 533
flights every month (coefficient of variation 0.013). Its monthly volume is
therefore flat by construction and correlates only **0.21** with the Yearbook's
seasonal profile. Consequences, both enforced in the pipeline:

- MACL is used for **hour-of-day shape only**, never for level.
- MACL is never used for **seasonality**, and it contains **no domestic
  traffic** (0.32% of the Yearbook domestic total), so domestic demand cannot
  be derived from it at all.

### F5 — The bus already wins on price. It loses on time.

Generalised cost, Malé ↔ Hulhumalé Ph1, per trip, VOT 250 MVR/hour, taxi
shared by two:

| | Bus | Taxi | Result |
|---|---|---|---|
| Fare | 10 MVR | 42.5 MVR/passenger | bus wins by 32.5 MVR |
| Time cost | (9.9 wait + 70 ride) = 333 MVR | (5 hail + 12.7 ride) = 74 MVR | bus loses by 259 MVR |
| **Total** | **343 MVR** | **116 MVR** | **bus is 227 MVR worse** |

- On **price alone** (VOT→0): **62–76% of taxi riders on every corridor would
  take the bus.**
- On **generalised cost** (VOT 250 MVR/h): **0.05–9.3%** would switch.

**A fare discount is therefore the wrong instrument** — it discounts the
dimension where the bus already wins and leaves the binding constraint
(journey time) untouched. Break-even ride time per corridor:

| Corridor | Current ride | Break-even | **Minutes to shed** |
|---|---|---|---|
| HM Ph2 ↔ Airport (R9) | 31 min | 14.6 min | **16.4** ✅ reachable |
| Malé ↔ HM Ph2 (R7/R8) | 40 min | 19.6 min | **20.4** ✅ reachable |
| Malé ↔ HM Ph1 (R1/R2) | 70 min | 15.6 min | **54.4** ❌ needs the causeway |
| Malé ↔ Airport (R3) | 44 min | 0 min | 44 ❌ needs the causeway |

## 5. The scenario engine

A scenario edits the service pattern; the engine recomputes passenger KPIs.

| KPI | Definition |
|---|---|
| `mean_wait_min` | demand-weighted expected wait (standard random-arrival: headway ÷ 2) |
| `p95_wait_min` | 95th percentile wait across route-hours |
| `boardings_over_capacity` | passengers in a route-hour exceeding the seats |
| `unmet_share_pct` | share of demand that cannot board |
| `seat_capacity_per_hour` | total seats on the road per hour |
| `taxi_rides_capturable` | taxi trips that switch to the bus (logit on generalised cost) |
| `break_even_ride_min` | ride time the bus needs to match a shared taxi |

### Scenarios and results — every scenario is fleet-neutral

**A planner cannot add a bus.** So no scenario adds one. Each is a set of
**trip moves**: a trip is taken from a named route-hour and given to another
route-hour on the same service day. `trips_change` is **0 in every scenario by
construction**, and the build asserts it, so a non-zero value is a bug rather
than a result.

| # | Scenario | What moves | Trips moved | Over-capacity | Unmet |
|---|---|---|---|---|---|
| S0 | Baseline | — | 0 | 381 | 3.79% |
| S2 | Airport re-timed | 3 late-night airport trips → airport hours with unmet demand | 3 | 372 (−9) | 3.70% |
| S3 | Rebalanced to the corridor | 8 trips off the airport afternoon lull → R1/R2 wherever it is over capacity | 8 | **95 (−286)** | 0.94% |
| S4 | Express peak | 10 off-peak R1/R2 trips → R1/R2 peak hours | 10 | 132 (−249) | 1.31% |
| **S5** | **Recommended package** | **S3 then S4** | **18** | **91 (−290)** | **0.91%** |

Total trips stay at **162 in every scenario** (430 network-wide; the KPI is
scoped to the five routes with ridership data). No donor is ever taken above
79% load, and every move is logged in `scenario_moves.csv` with the unmet
demand at the receiver before and after — so the effect of each individual trip
is auditable, not just the aggregate.

**Donors are chosen by lowest load, receivers by largest unmet demand, one trip
at a time, with the load recomputed after every move.** Receivers are chosen by
the data, not by a hand-picked hour window: an earlier version restricted them
to 15:00–20:00 and therefore refused to relieve R1 at 22:00, where the load is
152%. The model was hiding its own best answer.

> **Two findings came out of enforcing fleet neutrality.**
>
> **1. Re-timing the airport buses alone barely helps (−9 boardings).** At
> route-hour level the airport routes are *not* over capacity — their crowding
> is concentrated on one segment (STELCO→VIA at 104%), and adding a trip to an
> hour whose route average is 70% removes almost no unmet demand as measured
> here. This is a limitation of a route-hour KPI, not evidence that the airport
> bus is fine. It is why S3/S4 carry the capacity story and S2 is reported as a
> near-null result rather than dropped.
>
> **2. The recommended package changed.** It used to be S2 + S4, which relieved
> 118 boardings on an additive model. Under a fixed fleet the two changes that
> do measurable work are **S3 and S4**, and S2 is no longer part of it.
>
> **3. You cannot fine-tune with an 84-seat vehicle.** One trip into an hour
> with 70 unmet passengers overshoots it to zero. The optimum is a small number
> of large moves, not many small ones — which is also what a depot faces.

**Caveat to state honestly:** the network-wide mean wait barely moves
(10.8 → 10.8 min) because the changes are concentrated on a few corridors. The
corridor-level table is the one that matters, and it is reported separately
(`scenario_corridor_kpis.csv`).

### Mode-shift results

| Scenario | Capturable taxi rides/day | Capturable/year | Mean GC gap |
|---|---|---|---|
| S0 baseline | 190.6 | 69,569 | 136.7 MVR |
| S4 / S5 (with express) | **210.2** | **76,723** | **119.3 MVR** |

Sensitivity (VOT × taxi sharing) spans **12 – 3,001 rides/day**, so the
headline should be presented as a band with the **assumption-free break-even
analysis (§4 F5) as the primary claim**, not the point estimate.

---

## 6. Dashboard requirements

The datathon's stated challenge is *"an interactive, GIS-powered statistical
dashboard"*. **`docs/DASHBOARD_SPEC.md` is the authoritative build contract** —
it holds the exact schema of every table, the component specs, the traps and
the acceptance criteria. This section is the summary.

**Must have**
1. **Map** (Leaflet/MapLibre): OSM basemap, 15 route polylines in the official
   RTL colours, 184 route-stop records (97 unique stops), the causeway
   segments — every segment ≥ 10 min — highlighted.
2. **Route panel**: click a route → demand vs capacity by hour, the load-factor
   **band** (`load_factor_peak_pct` and `load_factor_avg_pct`), the official
   English and Dhivehi names, fare, seats and trip counts.
3. **Scenario controls**: 5 scenario buttons (S0, S2, S3, S4, S5 — there is no
   S1), KPI tiles for over-capacity, unmet %, mean wait, trips and taxi
   capture, each showing the delta against S0.
4. **Charts**: the six figures in `docs/figures/` plus one interactive
   "demand vs service by hour" chart.
5. **Coverage panel**: route × what-we-have, including the capture window and
   the ten routes with no ridership data. *(This is a feature, not an
   embarrassment — it is the "data gaps" contribution MBS asked for.)*

**Nice to have**
6. A taxi-OD toggle on the map (the revealed-demand layer).
7. A **synthesised GTFS feed** export for Greater Malé — no public GTFS
   exists for Malé; ours would be the first.

## 7. Fleet and capacity

Capacity is **not** an assumption any more. It comes from the team capacity
table, `data/raw/mtcc_bus_capacity.csv`, which carries the model, seated
capacity, wheelchair bays and maximum passengers per route, with a source and
a confidence flag on every row. See **ADR-0010**.

| Route | Model | Seated | Max (seats + standing) | Load on seats | Load on max |
|---|---|---|---|---|---|
| **R1** | Yutong ZK6116HGS double decker | 72 | 84 | **104.4%** | 89.5% |
| R2 | Yutong ZK6116HGS double decker | 72 | 84 | 78.5% | 67.3% |
| R7 | Yutong ZK6116HGS double decker | 72 | 84 | 74.8% | 64.1% |
| R3 | Yutong ZK6122H9 coach | 55 | 55 | 68.3% | 68.3% |
| R4 | Yutong ZK6122H9 coach | 55 | 55 | 48.5% | 48.5% |
| R5, R6 | Yutong ZK6126HGA single decker | 33 | *not stated* | **not comparable** | — |
| R10–R12, R15 | Yutong ZK6729D2 diesel minibus | 24 | 24 | — | — |
| R13, R14 | Yutong E6S electric minibus | 11 | 15 | — | — |

**The headline is the seats figure** — ADR-0003. "R1 is at 104% of its seats"
means people stand or wait; "89.5% of total capacity" sounds like there is room.

Where the operator gave seats but not standing capacity (R5, R6), no load
factor is formed at all. Capacity remains a **fleet-class** assumption: it is
per route, not per departure.

**The other load-bearing assumption (A1):** MTCC `total_pax` is boardings in
**one direction**. Under this reading R1 sits at 89.5% of an 84-seat bus on the
captured Saturday, rising to about 102% on a weekday when demand is 13.7%
higher at the same trip count. Under a two-direction reading every route sits
at 25–45% and the stated problem would not exist. We report a **band**
(`load_factor_peak_pct` = upper bound, `load_factor_avg_pct` = lower bound
under uniform alighting) so the ranking holds either way.

---

## 8. Team roles

| Role | Owner | Deliverables | Notes |
|---|---|---|---|
| **Dev 1 — Data layer** | you | schedule parser, route crosswalk, Yearbook extractor, reconciled dataset | Raw inputs are listed in `DATA_SOURCES.md`; the derived tables the dashboard needs are in `dashboard/data/` |
| **Dev 2 — Model + optimiser** | dev | demand allocation, gap table, scenario engine, mode-shift layer | The gap table schema in `docs/DASHBOARD_SPEC.md` §2.4 is the contract to build against |
| **Dev 3 — Dashboard + validation** | dev | GIS dashboard, holdout validation, camera spot-check | Longest pole — start the frontend early, against a **frozen CSV schema** |
| **Dev 4 — Report/slides** | dev | dataset register, method write-up, deck, Q&A prep | **Start the method section now.** The findings and figures are already generated |

**Critical dependency:** agree the `dashboard/data/demand_supply_gap.csv`
schema in the first 20 minutes and treat it as frozen for the dashboard.

---

## 9. Timeline

| Time | Milestone | Owner |
|---|---|---|
| 09:00–09:40 | Freeze scope, agree schema, assign roles, dataset register | all |
| 09:40–11:00 | Verify fleet capacities with MTCC; extend data layer; route-ID crosswalk | Dev 1 |
| 11:00–13:00 | Demand model final, gap table frozen, stop-level allocation | Dev 2 |
| 13:00–14:00 | **Findings + figures locked** (F1–F5 + 6 figures) | Dev 2 + Dev 4 |
| 14:00–15:30 | Scenario engine tuned, S5 confirmed | Dev 2 |
| 15:30–18:30 | Dashboard (map, route panel, scenario sliders) | Dev 3 |
| 18:30–19:30 | Holdout validation; camera spot-check *if* time | Dev 3 |
| 19:30–21:00 | Report, slides, code check, README, repo commit | Dev 4 + all |
| 21:00–22:00 | Buffer, rehearse the 5-minute pitch, Q&A prep | all |

**Rule: findings and figures are locked by 14:00.** If the dashboard is late,
you still have a strong submission.

---

## 10. Validation plan

**Status: items 1 and 2 are done and reproducible**
(`dashboard/build/build_validation.py` → `validation_*.csv`). Results below.

| Method | Proves | Cost | Priority |
|---|---|---|---|
| **Holdout** — fit the hourly shape on 80% of days, predict route-day totals for the held-out 20%, report MAPE | the model predicts *measured* ridership | 1–2 h | **must** — ✅ done |
| **Cross-source coherence** — Yearbook airport levels vs MACL vs Avas airport OD; MTCC boardings vs Avas corridor flows | the triangulation holds | 1 h | **must** — ✅ done |
| **Schedule cross-check** — parsed PDF service vs the live per-stop timetable | the parser is right | 30 min | **must** — ✅ done |
| **Camera spot-check** — 1 stop, 30 min video, pretrained detector, observed vs modelled | live ground truth at one point in space-time | 2–3 h | stretch |

### 10.1 Holdout accuracy

Chronological 80/20 split of MTCC 2025 daily boardings — **not random**, because
a random split trains on the future. Train 876 route-days to 2025-10-19, test
219 route-days from 2025-10-20 to 2025-12-31.

| Model | R1 MAPE | R2 MAPE | R4 MAPE | All MAPE | All MdAPE |
|---|---|---|---|---|---|
| M0 — route mean (naive) | 14.87% | 18.63% | 15.32% | **16.27%** | 7.87% |
| **M1 — route × day-type mean (used by the pipeline)** | **7.89%** | **11.93%** | **9.92%** | **9.91%** | **6.03%** |
| M2 — M1 plus a linear trend | 9.55% | 13.95% | 10.86% | 11.45% | 7.18% |

**The model the pipeline uses cuts holdout error by 39% against the naive
route mean** (16.27% → 9.91%). Adding a trend makes it *worse*, so the level is
left as a day-type mean — a measured choice, not a default.

On Saturdays specifically — the service day the supply side is measured on —
MAPE is **7.10%** with a bias of only **+0.72%**. That is the pair of numbers
that matters, because it is the day every load factor is computed for.

> **Bias is +6.2% overall, and it is a seasonality finding, not a model
> failure.** The holdout is 20 October – 31 December, which includes the
> year-end peak, while the training mean is pulled down by the low season. The
> model under-predicts this window by 6% for that reason. M2's trend term is an
> attempt to absorb it, and it fails.

### 10.2 Cross-source airport coherence

Three sources, three different populations. They are not meant to be equal, so
each difference is given a mechanism and a size.

| Test | Value | Verdict |
|---|---|---|
| MACL 2025 arrivals as % of Yearbook international arrivals | **40.2%** | FLAG — sample, usable for shape not level |
| MACL turboprop arrivals as % of Yearbook **domestic** arrivals | **0.32%** | FAIL — MACL has no domestic traffic at all |
| MACL adult arrivals as % of Yearbook international arrivals | 40% | INFO — this is the previously quoted coverage |
| Correlation of MACL monthly volume with Yearbook monthly arrivals | **0.21** | FAIL — MACL carries no seasonal signal |
| Avas airport dropoffs as % of Yearbook international departures/day | **15.3%** | PLAUSIBLE — credible taxi mode share |
| Avas airport pickups as % of Yearbook international arrivals/day | **2.2%** | FLAG — pickups and dropoffs are not symmetric |

The reconciliation holds, with one structural caveat: **Avas is Aug–Sep 2026
and the Yearbook is 2025**, so the mode share compares different years and
should be read to a percentage point or two. Avas airport dropoffs are stable
across a 1.0–1.5 km airport radius (1,099 → 1,121 per day); at 2.5 km the
circle absorbs Hulhumalé and the count triples, which is why 1.5 km is used.

The pickups asymmetry is real, not a bug: arriving passengers mostly take
pre-booked transfers, resort boats and the RTL bus, while departing residents
call a taxi. **Never assume Avas pickups and dropoffs are symmetric** — the
stop-level allocation in §3 therefore uses each direction separately.

### 10.3 Schedule cross-check

MTCC's published schedule PDFs (`data/raw/R1..R14.pdf`) parsed into frequency
bands — `(start, end, headway)` — then expanded to trip departures and compared
against the official RTL feed. Built by
`dashboard/build/build_schedule_crosscheck.py`.

**11 of 11 checkable routes pass, with a median hourly error of 0.27 trips per
hour** (worst 0.92) across the captured window. That independently corroborates
every capacity number in this project, which all inherit from that feed.

**The verdict deliberately rests on the hourly test, not the daily one.** The
PDFs are the **Ramadan 1446 edition (February–March 2025)**, which is precisely
why they were dropped as the supply source (RESEARCH §2.4a). Comparing a
Ramadan 2025 schedule to a regular October 2026 service day means a systematic
divergence is *expected*:

| | |
|---|---|
| Median \|daily difference\| | 5.3% |
| Daily range | −31.9% (R13) to +70% (R5) |

Those daily gaps are attributable, not mysterious:

- **R13 (−31.9%)** is a service-day boundary artefact. Its published Saturday
  band runs 06:00–02:30 at 10 minutes, which yields 16 trips after midnight out
  of 135. The API counts service days, so those fall differently. Hourly, the
  two agree to 0.27 trips/hour.
- **R5 (+70%) and R2 (+22%)** are real service additions. R2's published
  schedule has a 140-minute gap from 17:00 to 19:20 during which the 2026 feed
  runs four trips an hour. A regular-season timetable adding evening peak and
  removing a Ramadan-era pause is the expected direction.
- **R10, R11, R12, R15** cannot be checked at all, because the feed returns no
  timings for them. The PDFs *do* publish a frequency for three of them
  (R10 55, R11 55, R12 40 trips/day). Those figures are reported in
  `schedule_crosscheck.csv` but are **not** injected into `routes_master`: they
  describe a Ramadan 2025 service, so filling the null with them would trade an
  honest gap for a plausible error.

Zero parse anomalies across all 14 PDFs. The band regex matches hyphen,
en-dash and em-dash explicitly, because these documents use all three and a
missed dash silently drops a band — the exact class of error this check exists
to catch.

### 10.4 What validation changed

Two published claims did not survive contact with the data and were corrected
rather than quietly kept:

1. `airport_demand_profile.csv` had **no builder** and no filter reproduced its
   numbers. It now has a stated definition (2025, international, passenger-
   weighted) and is regenerated by `build_validation.py`. The 07:00–09:59 share
   moves from 35.5% to **33.1%**, a 2.8-point drift that does not change the F4
   finding but is now auditable.
2. The **35.5% was weighting-dependent** and never said so. Flight-weighted it
   is 25.3% and the peak window moves to midday. The chart now states the
   weighting, because a planner reading "33% of passengers" and a planner
   reading "25% of flights" would draw different conclusions.

### On the camera crowd detector (important)

**Do not build it as a product feature.** It is not reproducible, it produces
numbers no planner can act on, and it will eat 3 hours you do not have.

**Build it as a validation appendix instead:** one stop, one 30-minute window,
observed people vs modelled boardings, one slide reporting MAPE. That
converts "our model is plausible" into "our model is **validated**", which is
worth far more to a judging panel than a live webcam demo. If time remains
afterwards, productise it.

**Prefer the RTL live GPS API** if a token can be obtained
(`https://bo.rtl.mv:4455/maldives/api/v2/bus/routedetails`, needs a JWT) —
it gives observed running times and headways across all 14 routes with zero
hardware, and beats a webcam for validating the supply model.

---

## 11. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Fleet capacities wrong** (team knowledge) | High | Confirm with MTCC; report a band; F3/F4/F5 do not depend on them |
| **The RTL feed returns one service day, time-filtered from the moment of the call** | High | Our capture covers ~11:00–24:00 on a Saturday; the morning peak is missing. Re-run `dashboard/build/build_data.py` shortly after 00:00 to capture a full day, and once on a Friday and a weekday to restore the day-type comparison. Hours not captured are emitted as null, never 0 |
| **MTCC counts are "sample value"** per its own README | Medium | State it; use MTCC as the anchor and cross-check against Avas |
| **MACL covers ≈40% of international arrivals, 0% of domestic** | Medium | Use Yearbook for levels, MACL for shape; publish the coverage table as a finding |
| No ridership data for R5, R6, R8, R9, R10–R15 | Medium | Publish a coverage matrix; mark as `NO DEMAND DATA` rather than zero-filling |
| Camera model inaccurate in dense crowds | Low | Validation only, not a product claim |
| Scope creep into FollowMe / marine transport | Medium | Excluded by decision — do not reopen |

---

## 12. Open questions to chase today

1. **A weekday and a Friday capture of the RTL feed.** The endpoint is public
   and needs no key; it just has to be called at different times. That closes
   the morning gap and restores the day-type comparison. Biggest single gap in
   the project.
2. **Fleet table** — vehicle type and seat capacity per route, and the number
   of buses in the MTCC Malé fleet.
3. **Census 2022 / HIES 2019** access link (the FAQ says MBS provides them).
   HIES transport expenditure would make the affordability argument airtight.
4. **MTCC count definition** — does `total_pax` count one direction or two,
   and does it count boardings or unique passengers? One question, and the
   load-factor band collapses to a point estimate.
5. **RTL live API token** — 10 minutes; observed running times across 14
   routes would be a stronger validation than a camera.
6. **R15** — appears in the live route list with no published PDF and no
   ridership data. Is it operational?

---

## 13. The 5-minute pitch

1. **0:00–0:40 — the gap.** Five public sources, all partial, none joinable.
   Nobody can answer "how many passengers does this bus carry, on which
   route, at which hour, and is that matched to the buses running?" We joined
   them, and we publish the result with per-row provenance.
2. **0:40–1:40 — F1, the causeway.** 57% of the bus's journey is two bridge
   crossings. The bus is 4.4× slower than the taxi *and* 8.5× cheaper. That
   is why young Maldivians take taxis.
3. **1:40–2:40 — F2, F3, F4, the misallocation.** Load factor is measured per
   stop-to-stop segment, not per route: R1's fullest segment is 77% of an
   84-seat double-decker, but the airport segment STELCO→VIA hits **104%** on a
   52-seat bus, because every airport passenger funnels through it. R3 is an
   hourly bus with a 30-minute expected wait, the airport buses run the same
   frequency at 03:00 as at 08:00, and a third of arriving passengers (33.1%)
   land in a three-hour window.
4. **2:40–4:10 — the tool.** Live demo: move 6 trips, watch over-capacity
   fall by 200 passengers, unmet demand fall, and the taxi capture change.
   Six scenarios, one recommended package — all re-timings, zero new buses.
5. **4:10–5:00 — deliverable and ask.** The reconciled dataset, a
   holdout-validated model, a first-ever GTFS feed for Greater Malé, and a
   2-page policy brief. *What we need from MTCC: current schedules, the fleet
   table, and the count definition.*

**Q&A preparation**
- *"Your load factor puts R1 at 90% but the problem says buses are full —
  which is it?"* → 90% is the Saturday figure, with Saturday demand and
  Saturday service paired correctly. Weekday demand is 13.7% higher, which
  puts a weekday at about 102%. The band is 45–90% on Saturday and the ranking
  is robust either way; a weekday capture settles it.
- *"How current is the timetable?"* → It is the official RTL feed, fetched
  today. It is time-filtered from the moment of the call, so we captured
  roughly 11:00–24:00 of one service day; the morning peak is the known gap
  and re-running the build after midnight closes it.
- *"Is taxi demand really bus demand?"* → No, and we don't claim it is. We
  use taxi as a revealed-preference *shape* and an *upper bound* on total
  demand. The bus ridership is the anchor.
- *"What would actually move young people off taxis?"* → Not a discount. On
  price the bus already wins — 70–75% would switch. It loses on time by
  227 MVR per trip. The break-even table says which corridors express service
  can fix, and that the biggest one needs the causeway.
- *"Can this scale beyond Malé?"* → Yes. The recipe is: a published
  timetable, a taxi or ride-hail feed, and a ridership series. That is a
  template any city can apply.
