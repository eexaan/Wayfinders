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

Upper-bound load factor — every boarding rides the full route — on the
**captured service day (Saturday)**:

| Route | Official RTL name | Bus type | Seats | Trips/day | Boardings/day | Load (peak) | Load (avg) |
|---|---|---|---|---|---|---|---|
| **R1** | West Park to HM Phase 1 | Double decker | 84 | 61 | 4,585 | **89.5%** | 44.7% |
| R3 | West Park to VIA | Airport bus | 52 | 20 | 752 | 72.3% | 36.1% |
| R2 | Carnival to HM Phase 1 | Double decker | 84 | 61 | 3,447 | 67.3% | 33.6% |
| R7 | HM Phase 2 to West Park | Double decker | 84 | 66 | 3,552 | 64.1% | 32.0% |
| **R4** | HM Phase 1 to VIA | Airport bus | 52 | 38 | 1,014 | **51.3%** | 25.6% |

Ten routes have **no ridership data at all** (R5, R6, R8–R15) and are marked
`NO DEMAND DATA` rather than zero-filled.

> **Read the load numbers with the service day in mind.** The captured feed is
> one service day (Saturday), so boardings and trips are paired correctly.
> Weekday boardings on R1 are 13.7% higher than Saturday (5,212 vs 4,585); at
> the same 61 trips that is **~102% of seats**. A weekday capture is needed to
> confirm — see §12.

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
MACL international arrivals (2019–25, 4.89M arrivals) peak hard:

| Hour | % of arrivals |
|---|---|
| 07:00 | 12.27% |
| 08:00 | 11.68% |
| 09:00 | 11.52% |
| 11:00 | 10.31% |
| 14:00 | 9.94% |
| **07:00–09:59 combined** | **35.5%** |

**35.5% of arrivals land in a three-hour window**, and the airport buses run
the same frequency at 03:00 as at 08:00. Nothing runs at all between 00:00 and
06:00, when 1.9% of arrivals land.

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

### Scenarios and results

| # | Scenario | What it does | Over-capacity | Unmet | Trips captured |
|---|---|---|---|---|---|
| S0 | Baseline | — | 360 | 3.68% | 162 |
| S2 | Airport re-timed | +1 departure per hour for R3/R4/R9 in 11:00–15:00, −1 in 22:00–23:00 | **355** | 3.63% | 168 |
| S3 | Rebalanced to the corridor | 6 trips off the airport routes in the 13:00–14:00 lull, 6 onto R1/R2 at 16:00–18:00 | **349** | 3.61% | 164 |
| S4 | Express peak | one extra R1/R2 departure in each hour 15:00–18:00 (faster cycle from skipping stops) | **248** | **2.53%** | 170 |
| **S5** | **Recommended package** | **S2 + S4** | **242 (−118)** | **2.48%** | **176** |

S5 removes **118 boardings from over-capacity** and cuts the unmet share by
1.2 points with 14 extra trips, all inside the captured window — every change
is a *re-timing*, not a new bus.

**Caveat to state honestly:** the network-wide mean wait barely moves
(11.6 min) because the changes are concentrated on a few corridors. The
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
dashboard"*. Build to that spec.

**Must have**
1. **Map** (Leaflet/MapLibre): OSM basemap, 15 route polylines coloured by
   official RTL route colours, 613 stops sized by modelled boardings, the
   causeway segments highlighted.
2. **Route panel**: click a route → demand vs capacity by hour, by day-type;
   load-factor band; schedule windows.
3. **Scenario controls**: sliders/buttons for the 6 scenarios; KPI tiles
   (over-capacity, unmet %, mean wait, trips/day, taxi capture) updating live.
4. **Charts**: the six figures in `docs/figures/` plus one interactive
   "demand vs service by hour" chart.
5. **Coverage panel**: a route × what-we-have matrix, so gaps are visible
   rather than hidden. *(This is a feature, not an embarrassment — it is the
   "data gaps" contribution MBS asked for.)*

**Nice to have**
6. Before/after mode slide (baseline vs S5) with a corridor heatmap.
7. A **synthesised GTFS feed** export for Greater Malé — no public GTFS
   exists for Malé; ours would be the first, and it is loadable into Google
   Maps / TransitApp.

---

## 7. Fleet and capacity assumptions (team-provided — CONFIRM)

| Bus type | Seats | Routes | Source |
|---|---|---|---|
| Double decker | 84 | R1, R2, R6, R7, R8 | stated by team |
| Airport bus | 52 (50–54) | R4, R9 | stated by team |
| Airport bus | 52 | R3 | **ASSUMED — confirm** |
| Regular bus | 54 | R5 | **ASSUMED — confirm** |
| Minibus | 21 (20–22) | R10, R11, R12, R15 | team + Team Kandu `minibus=yes` |
| E-minibus | 11 | R13, R14 | **ASSUMED — confirm** |

> ⚠️ **Source:** reported bus capacity at <https://www.psmnews.mv/en/106008>
> (linked in `data/official/notes.txt`) plus the `minibus` flag in Team Kandu's route
> table. The article is behind a Cloudflare challenge and could not be
> machine-read, so these figures are **team-provided, not automatically
> verified**. They drive every absolute load-factor number. **Confirm the
> seats per route with MTCC** (or use MBS Yearbook 11.3 for registered vehicle
> types) before publishing an absolute load factor. The *relative* findings
> (F3, F4, F5) do not depend on them.

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

| Method | Proves | Cost | Priority |
|---|---|---|---|
| **Holdout** — fit the hourly shape on 80% of days, predict route-day totals for the held-out 20%, report MAPE | the model predicts *measured* ridership | 1–2 h | **must** |
| **Cross-source coherence** — Yearbook airport levels vs MACL vs Avas airport OD; MTCC boardings vs Avas corridor flows | the triangulation holds | 1 h | **must** |
| **Schedule cross-check** — parsed PDF service vs the live per-stop timetable | the parser is right | 30 min | **must** |
| **Camera spot-check** — 1 stop, 30 min video, pretrained detector, observed vs modelled | live ground truth at one point in space-time | 2–3 h | stretch |

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
| **MACL covers ≤36.5% of international arrivals, 0% of domestic** | Medium | Use Yearbook for levels, MACL for shape; publish the coverage table as a finding |
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
3. **1:40–2:40 — F2, F3, F4, the misallocation.** R1 carries about 90% of
   its seats on a Saturday and would pass 100% on a weekday; the airport bus
   R4 runs at 51%. R3 is an hourly bus with a 30-minute expected wait, the
   airport buses run the same frequency at 03:00 as at 08:00, and 35.5% of
   arrivals land in a three-hour window.
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
