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
| **Supply** | route × day-type × hour | published service pattern × live trip count | MTCC schedule PDFs (S1) + Team Kandu live timetable (D5) |
| **Demand — level** | route × day-type | observed boardings | MTCC `bus_daily` (R1/R2/R4, 2025) + `bus_monthly` (R3/R7) × day-type index |
| **Demand — shape** | hour of day | revealed preference on the same corridor | Avas taxi OD × hour (D2) |
| **Demand — airport** | hour of day | observed arrival profile | MACL hourly (D3) for shape; MBS Yearbook 11.13 (S4) for level, incl. **domestic** |
| **Capacity** | route | vehicle type × seats | team domain knowledge (see §7) |
| **Geometry** | stop | lat/lon, route order | Team Kandu stops (D5) + RTL route maps (S2/S3) |

**Every output row carries `source` and `method`**, so a judge can audit any
cell and see whether it is observed or modelled. This is deliberate: the
datathon's judges are statisticians.

---

## 4. Findings (all computed, all reproducible)

### F1 — The causeway is the journey time

| | |
|---|---|
| R1 end-to-end run (Malé → Hulhumale Ph1) | **70 min** |
| Of which: 2 × causeway crossing | **40 min (57%)** |
| Of which: 14 stop-to-stop segments | 30 min |
| Internal Hulhumale routes (R5, R6) | 3–5 min per segment |
| Same journey by taxi (observed median) | **12.7 min** |

The bus is **4.4× slower than a taxi** on the corridor where it is also 8.5×
cheaper. People are not choosing the taxi because they are being charged
more; they are paying a premium to avoid 57 minutes of queueing at a bridge.

### F2 — One corridor is over capacity; the airport buses are not

Weekday, upper-bound load factor (every boarding rides the full route):

| Route | Bus type | Seats | Trips/day | Boardings/day | Pax/trip | Load |
|---|---|---|---|---|---|---|
| **R1** West Park–Hulhm Ph1 | Double decker | 84 | 61 | 5,212 | 85 | **102%** |
| R7 | Double decker | 84 | 66 | 4,185 | 63 | 76% |
| R2 | Double decker | 84 | 61 | 3,818 | 63 | 74% |
| R3* | Airport bus | 52 | 20 | 828 | 41 | 80% |
| **R4** HM Ph1–Airport | Airport bus | 52 | 38 | 1,146 | 30 | **58%** |

\* R3 has no published weekday pattern; Saturday/Public Holidays used.

85 people on an 84-seat double-decker means **people wait to board**. That is
the problem statement, and it is one route.

### F3 — The schedule does not track demand

| Route | Demand, Fri vs weekday | Service, Fri vs weekday | Gap |
|---|---|---|---|
| R1 | 61.2% | 69.8% | **+8.6 pp** |
| R2 | 63.6% | 91.1% | **+27.5 pp** |
| R4 | 63.0% | 83.8% | **+20.8 pp** |
| R7 | 62.2% | 77.4% | **+15.2 pp** |

The published schedule *does* respond to Friday — it just responds by less
than demand falls, so Friday buses run emptier on every route. On R2 that is
**27.5 points of over-provisioning**, and it is free to fix.

### F4 — The airport bus is scheduled flat while arrivals are tri-peaked

R4 and R9 run a **flat 30-minute headway, 06:00–00:30, every day**. MACL
arrivals (2019–25, 4.89M international arrivals):

| Hour | % of arrivals | % of R4 service | Ratio |
|---|---|---|---|
| 07:00 | 12.27% | 5.56% | **2.21× over-subscribed** |
| 08:00 | 11.68% | 5.56% | 2.10× |
| 09:00 | 11.52% | 5.56% | 2.07× |
| 11:00 | 10.31% | 5.56% | 1.86× |
| 14:00 | 9.94% | 5.56% | 1.79× |
| 16:00 | 1.78% | 5.56% | 0.32× |
| 23:00 | 0.25% | 5.56% | **0.04× (22× over-served)** |
| 04:00–06:00 | 1.9% | **0%** | **no service at all** |

R3 (Malé–Airport) is worse: **hourly service, 60-minute headway, 30-minute
expected wait.** Fixable with **zero new buses**.

### F5 — The bus already wins on price. It loses on time.

Generalised cost, Malé↔Hulhumale Ph1, per trip, VOT 250 MVR/hour, taxi
shared by 2:

| | Bus | Taxi | Gap |
|---|---|---|---|
| Fare | 10 MVR | 42.5 MVR/passenger | bus wins by 32.5 MVR |
| Time cost | (9.9 wait + 70 ride) = 333 MVR | (5 hail + 12.7 ride) = 74 MVR | bus loses by 259 MVR |
| **Total GC** | **343 MVR** | **116 MVR** | **bus is 227 MVR worse** |

- On **price alone** (VOT→0): **70–75% of taxi riders on every corridor
  would take the bus.**
- On **generalised cost** (VOT 250 MVR/h): **0.05–9.3%** would switch.

**Therefore a fare discount is the wrong instrument.** The binding constraint
is journey time. The break-even ride time the bus needs to match a shared
taxi:

| Corridor | Current ride | Break-even ride | **Minutes to shed** |
|---|---|---|---|
| HM Ph2 ↔ Airport (R9) | 31 min | 14.6 min | **16.4** ✅ reachable |
| Malé ↔ HM Ph2 (R7/R8) | 40 min | 19.6 min | **20.4** ✅ reachable |
| Malé ↔ HM Ph1 (R1/R2) | 70 min | 15.6 min | **54.4** ❌ needs the bridge |
| Malé ↔ Airport (R3) | 44 min | 0 min | 44 ❌ needs the bridge |

The corridor that carries 51% of all taxi rides (Malé↔Hulhumale Ph2, 2,662
rides/day) is reachable with express service. The Malé↔HM Ph1 corridor is not
reachable without solving the causeway.

**This is the core policy finding: fix the bridge crossing for buses, and
modal shift follows. Discount the bus, and nothing moves.**

---

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

| # | Scenario | What it does | Over-capacity | Unmet | Trips/day |
|---|---|---|---|---|---|
| S0 | Baseline | — | 1,715 | 8.00% | 371 |
| S1 | Friday right-sized | cut Friday service on R1/R2/R4 to match Friday demand | 1,715 | 8.00% | **364 (−7)** |
| S2 | Airport re-timed | 30→15 min for R4/R9 and 60→30 min for R3 during the 07:00–09:59 / 11:00 / 14:00 arrival peaks; halve the 22:00–06:00 night service | **1,685** | **7.86%** | 398 (+27) |
| S3 | Rebalanced to the corridor | move 15% of airport trips to the Malé↔HM Ph1 corridor | 1,715 | 8.00% | 371 (0) |
| S4 | Express service on R1/R2 | skip-stop Hulhumale service, 70→45 min, +15% departures | **1,545** | **7.21%** | 377 (+6) |
| **S5** | **Recommended package** | **S1 + S2 + S4** | **1,515 (−200)** | **7.07%** | **397 (+26)** |

S5 moves **200 fewer passengers over capacity, with 26 more trips** and cuts
the unmet share by ~1 point — and every one of those changes is a *re-timing*,
not a new bus.

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
> (linked in `exn-dt/notes.txt`) plus the `minibus` flag in Team Kandu's route
> table. The article is behind a Cloudflare challenge and could not be
> machine-read, so these figures are **team-provided, not automatically
> verified**. They drive every absolute load-factor number. **Confirm the
> seats per route with MTCC** (or use MBS Yearbook 11.3 for registered vehicle
> types) before publishing an absolute load factor. The *relative* findings
> (F3, F4, F5) do not depend on them.

**The other load-bearing assumption (A1):** MTCC `total_pax` is boardings in
**one direction**. Under this reading R1 sits at 102% of an 84-seat bus,
consistent with the problem statement. Under a two-direction reading every
route sits at 28–51% and the stated problem would not exist. We report a
**band** (`load_factor_peak_pct` = upper bound, `load_factor_avg_pct` = lower
bound under uniform alighting) so the conclusion holds either way.

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
| **Schedules are the Ramadan 1446 edition (Feb 2025)** | High | Ask for a current edition; use the live trip count as the level; publish the divergence table (−28% to +113% by route) |
| **MTCC counts are "sample value"** per its own README | Medium | State it; use MTCC as the anchor and cross-check against Avas |
| **MACL covers ≤36.5% of international arrivals, 0% of domestic** | Medium | Use Yearbook for levels, MACL for shape; publish the coverage table as a finding |
| No ridership data for R5, R6, R8, R9, R10–R15 | Medium | Publish a coverage matrix; mark as `NO DEMAND DATA` rather than zero-filling |
| Camera model inaccurate in dense crowds | Low | Validation only, not a product claim |
| Scope creep into FollowMe / marine transport | Medium | Excluded by decision — do not reopen |

---

## 12. Open questions to chase today

1. **Current (non-Ramadan) MTCC schedules** — does a 2026 edition exist?
   Biggest single risk to the supply model.
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
3. **1:40–2:40 — F2, F3, F4, the misallocation.** R1 runs at 102% of
   capacity; the airport bus runs at 58%. Friday demand falls 37% but service
   falls 9–22%. The airport bus runs a flat 30-minute headway while 35% of
   arrivals land in three hours, and nothing runs before 06:00.
4. **2:40–4:10 — the tool.** Live demo: move 6 trips, watch over-capacity
   fall by 200 passengers, unmet demand fall, and the taxi capture change.
   Six scenarios, one recommended package — all re-timings, zero new buses.
5. **4:10–5:00 — deliverable and ask.** The reconciled dataset, a
   holdout-validated model, a first-ever GTFS feed for Greater Malé, and a
   2-page policy brief. *What we need from MTCC: current schedules, the fleet
   table, and the count definition.*

**Q&A preparation**
- *"Your load factor says 102% on an 84-seat bus — how is that possible?"*
  → It is a boardings-based upper bound; the band is 51–102% and the ranking
  is robust. Our first ask to MTCC is the count definition.
- *"How do you know the schedules are current?"* → We don't, and we publish
  the divergence between the Ramadan-1446 PDF and the live October-2026
  timetable (−28% to +113%). We use the live count as the level and the PDF
  only for the shape, and we flag it.
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
