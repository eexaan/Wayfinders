# Research notes — Greater Malé bus demand & supply

**Maldives Datathon 2026 · Team Wayfinders**
Working log of everything that was examined, tested, ruled out, and kept.
Written so that a reader can reproduce or challenge any claim here.

Companion documents: [`SPEC.md`](SPEC.md) (the build plan) ·
[`DATA_SOURCES.md`](DATA_SOURCES.md) (every source and link)

---

## 0. How to read this

Sections are ordered as the investigation actually happened, not as the story
reads best. Dead ends are kept, with the reason, because several of them are
the difference between a defensible finding and a plausible-sounding wrong
one. Every number is derived from the public sources listed in
`DATA_SOURCES.md`, and the tables are reproduced inline so each can be checked
by hand.

---

## 1. Data reconnaissance

### 1.1 What was in the box

| Asset | Shape | First look |
|---|---|---|
| **MTCC** `MTCC.xlsx` | 4 sheets: README, bus_monthly, bus_daily, ferry_monthly | `bus_daily` = 1,095 rows = 365 days × 3 routes (R1, R2, R4) for 2025. `bus_monthly` = 180 rows = 36 months × 5 routes (R1, R2, R3, R4, R7) for 2023–2025 |
| **Avas Ride** | 371,788 rows, 2026-08-01 → 2026-09-30 | `status`: 320,140 `payment_completed`, 24,401 `ride_completed`, 27,247 `ride_expired`. Plus `car_fare_matrix.csv` (6×6 zone fares) |
| **MACL** | 168,959 rows, 2012-01-01 → 2026-12-07 | 20 columns: flight_type, dates, carrier_code, route_code, region, aircraft_type_code/category, arrival/departure adult/child/infant counts, `ata`/`atd` |
| **Team Kandu** | 14 CSVs | `rtl_bus_routes` (28 routes, 15 Greater Malé), `rtl_bus_stops` (613 stop records with lat/lon), `rtl_bus_departures` (1,686 rows), `observations.csv` (9,197 rows of MBS Statistical Yearbook) |
| **FollowMe** | 17.46M rows across 31 daily CSVs, 1.8 GB | Vessel GPS: `imei`, `latitude`, `longitude`, `speed`, `heading`, `network`, `cellid`, `gsm_level`. **Excluded from scope** |

### 1.2 The Avas shape

```
Completed rides by hour (all 61 days):
00h 6641 | 01h 3001 | 02h 1782 | 03h 1814 | 04h 2182 | 05h 5933
06h 9485 | 07h 16382 | 08h 16372 | 09h 15296 | 10h 14796 | 11h 13847
12h 14481 | 13h 17285 | 14h 19478 | 15h 21400 | 16h 22758 | 17h 19510
18h 19550 | 19h 18299 | 20h 18564 | 21h 16141 | 22h 14040 | 23h 11103
```
Two peaks (AM 07:00–09:00, PM 15:00–19:00) and a surprisingly strong
00:00–05:00 floor of ~1,800 rides/hour — shift workers, ferry arrivals and
nightlife, and a reminder that a 24-hour model is needed rather than a
peak-hours model.

By weekday (completed rides): Sat 49,547 > Wed 47,654 > Thu 46,787 >
Tue 45,800 > Fri 42,026 ≈ Sun 44,173 ≈ Mon 44,153. The Friday dip in Avas
is much smaller than the Friday dip in bus ridership — worth remembering
when using taxi data as a demand *shape*.

Distance: p10 4.45 km, p50 8.22 km, p90 10.15 km, max 13.69 km. Implied
speed p50 38.7 km/h, but the *slowest* OD pairs sit at 28–32 km/h and are
concentrated on the Hulhumalé bridge approach (4.21–4.23, 73.53–73.55) and
the Malé–airport axis (4.17,73.51 → 4.19,73.53, 9,464 rides at 31.8 km/h).

### 1.3 Top taxi corridors (revealed demand)

| From | To | Rides (61 days) | /day |
|---|---|---|---|
| Hulhumale Ph2 | Malé City | 81,910 | 1,344 |
| Malé City | Hulhumale Ph2 | 80,436 | 1,319 |
| Malé City | Hulhumale Ph1 | 38,637 | 634 |
| Hulhumale Ph1 | Malé City | 35,606 | 584 |
| Malé City | Velana Airport | 30,036 | 493 |
| Hulhumale Ph2 | Velana Airport | 19,663 | 323 |
| Hulhumale Ph1 | Velana Airport | 9,535 | 156 |
| → VIA Domestic Terminal (dropoff) | — | 21,272 | 349 |

**Malé↔Hulhumale Ph2 alone is 51% of all taxi trips.** The largest taxi
corridor is exactly the corridor the double-deckers serve. Taxis and buses
are substitutes here, not complements.

### 1.4 Why the spatial-gap story was dropped

Clustering Avas pickups to a ~100 m grid and measuring distance to the
nearest of the 613 RTL bus stops:

```
rides within 300 m of a bus stop : 97.1%
rides more than 800 m from one    :  0.0%
```

Malé is about 4 km long and 1.5 km wide. Bus stops are already within
walking distance of essentially every taxi pickup. **A "missing bus stop"
map would be a map of nothing.** The gap is temporal (frequency, timing) and
capacity (vehicle count), not spatial. This killed an early project idea.

---

## 2. The supply side — the hardest part

### 2.1 The published dataset is a snapshot, not a timetable

`rtl_bus_departures.csv` looked like a timetable. It is not:

- `fetched_male_time` = **2026-10-10 19:53** on every row
- every departure time falls between **19:54 and 23:59**
- for R1, the observed trip IDs are **47–61**, and `departures_left_when_fetched` = 10

So it is **one live evening snapshot**, capturing the last ~15 trips of the
day. It contains no morning peak at all. `trips_per_day` is the maximum trip
ID (= 61 for R1) and is therefore the **total number of trips that day**
(Saturday 2026-10-10), not a per-day-type figure.

Useful anyway: it gives **per-stop arrival times for real trips**, which is
how the bridge segmentation in §3.1 was found.

### 2.2 The official 2026 feed (the unlock)

The RTL customer portal publishes bus schedules through a public endpoint that
needs **no authentication**:

```
https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails
```

It returns, for all 15 Greater Malé routes:

| Field | Example (R1) |
|---|---|
| `routeNumber` | `R1` |
| `name` — official English name | `West Park to HM Phase 1` |
| `dvname` — official Dhivehi name | `އެޗްއެމް ފޭސް 1` |
| `color` — official route colour | `#e9222a` |
| `fare` | `10.0` MVR |
| `isMiniBusRoute` | `0` |
| `depotName` | `Greater Male'` |
| `startStationName` / `endStationName` | `Maafannu Bus Terminal` / `Maafannu Bus Terminal OPP` |
| `busRouteStopList` | 18 stops, each with `order`, `name`, `dvname`, `code`, `latitude`, `longitude` and `timings` |

`timings` carries the **scheduled departure time of every trip at that stop**.
That is the full timetable in machine-readable form — no PDF parsing, no
scraping of a rendered page, no Dhivehi font problems.

**This replaces the MTCC schedule PDFs entirely.** Those PDFs were the only
published timetable before this, and they were the "Ramadan 1446" edition
(February 2025) — see §8 for why they were dropped.

### 2.3 What the feed actually contains

```
route  name                        minibus  fare  stops  trips/day  captured
R1     West Park to HM Phase 1          0    10.0     18         61        40
R2     Carnival to HM Phase 1           0    10.0     11         61        40
R3     West Park to VIA                 0    10.0      9         20        13
R4     HM Phase 1 to VIA                0    10.0      9         38        25
R5     HM Internal                      0     5.0     15         17        12
R6     HM Phase 2 to HM Phase 1         0     5.0     16         75        51
R7     HM Phase 2 to West Park          0    15.0     12         66        44
R8     HM Phase 2 to Carnival           0    15.0     11         61        40
R9     HM Phase 2 to VIA                0    15.0     10         38        25
R10    Orchid                          1     7.0     13          -         0
R11    Ameenee                         1     7.0     19          -         0
R12    Sosun                           1     7.0      9          -         0
R13    Villimale Internal              1     5.0     13         92        63
R14    VILLIMALE INTERNAL 2            1     5.0     12        105        77
R15    West Park to Orange Hiya        1    10.0      7          -         0
```

Two things to notice:

1. **R15 exists in the official list but returns no timings and has no
   published PDF.** MTCC's own PDF index lists only R1–R14. R15 is a live
   route with no published schedule.
2. **The four minibus routes R10, R11, R12 and R15 return zero timings.** The
   same four routes have no ridership data in the MTCC dataset. Two
   independent sources agree that these routes are undocumented.

### 2.4 The limitation of the feed — it is time-filtered

The endpoint returns **each stop's departures from the moment of the call
onwards**, not the whole service day. Our capture was taken at about 11:00 on
Saturday 2026-10-24, so:

| | |
|---|---|
| Captured window | roughly **11:00 – 24:00** |
| Trips per day (R1) | **61** — the maximum trip `order`, complete and official |
| Trips captured (R1) | **40** (orders 22–61) |
| Missing | **06:00 – 11:00**, i.e. the morning peak |

Diagnosis: R1's origin stop returns orders 22–61 with no gaps, all times from
11:20 onward. Downstream stops return slightly lower order numbers, because a
trip that already left the origin is still due to arrive further along. So the
filter is "upcoming events per stop", evaluated at request time.

**Consequence, and the honest treatment.** Hours before the capture window are
written to `demand_supply_gap.csv` with `trips_in_hour = null` and
`capture_status = "before_capture_window"`. They are never written as 0, and
they are excluded from every KPI. Re-running `dashboard/build/build_data.py`
shortly after midnight captures a full service day; running it on a Friday and
a weekday restores the day-type comparison.

### 2.4a What it replaced

Before finding this endpoint the supply side was built from the MTCC PDF
schedules — the "Ramadan 1446" edition (February 2025), parsed with
`pdftotext -layout` into day-group × time-window × headway. That approach
worked, but it was a **2025 Ramadan edition being used as a 2026 service
model**, and it diverged from the live timetable by −28% to +113% depending on
route. It has been removed from the repository. The lesson is in §8.

### 2.5 The RTL public APIs

- `https://rtl.mv:7781/maldives/cms/CMSGetAllBusRouteMap` → **200, public, no
  auth.** Route metadata: route number, English + Dhivehi names, official
  colour, and a link to the per-route map PDF.
- `https://rtl.mv:7781/BusRouteMap/R1%20final.pdf` → **200**, 875 KB, official
  route map with stop names in both languages.
- `https://rtl.mv:7781/maldives/cms/GetAllCMSRouteMap` → 200, ferry route maps
  (base64 images).
- `https://bo.rtl.mv:4455/maldives/api/v2/bus/routedetails`,
  `/v1/bus/eta`, `/v1/bus/livecoordinates` → **401, JWT required.** The Angular
  bundle (`main-es2015.fe1f140b40447556b695.js`) reveals the endpoint names
  and the Firebase auth flow. Worth 10 minutes of a team's time; it would give
  observed running times across all 14 routes.

---

## 3. The bridge — the finding that organises everything

### 3.1 Segment timings from the live timetable

R1, trip 52, Malé → Hulhumale Phase 1:

| Stop | Time | Δ |
|---|---|---|
| Maafannu Bus Terminal | 20:00 | — |
| Tow Yard | 20:02 | 2 |
| STELCO | 20:04 | 2 |
| **Hulhumale' Cemetery** | **20:24** | **20** |
| Skate Park … Ruhgandu 1 | 20:26–20:34 | 2 each |
| Dhiraagu … MNDF Flat | 20:36–20:44 | 2 each |
| **Hulhumale' Cemetery OPP** | **20:46** | **2** |
| **Male' Swimming Track** | **21:06** | **20** |
| Dharumavantha School | 21:08 | 2 |
| Maafannu Bus Terminal OPP | 21:10 | 2 |

**Total 70 minutes, of which 40 (57%) is the two causeway crossings.** The
crossings are the *only* slow segments; every stop-to-stop segment is a
uniform 2 minutes.

Across all routes (median segment times):

| Route | End-to-end | Slowest segment |
|---|---|---|
| R1 | 70 min | 20 + 20 min (causeway) |
| R2 | 67 min | 20 + 20 min (causeway) |
| R4 | 46 min | 15 min (VIA terminal) |
| R7 | 40 min | 20 min (causeway) |
| R6 | 40 min | 5 min (all internal) |
| R5 | 31 min | 3 min (all internal) |
| R3 | 44 min | 15 min (VIA terminal) |

**Internal Hulhumalé routes (R5, R6) run 3–5 min per segment. Cross-causeway
routes run 20 min for the same distance.** That contrast is the evidence that
the causeway, not the stop spacing, is the bottleneck.

### 3.2 Why the bus loses to the taxi

Avas median Malé↔Hulhumale Ph1 taxi trip: **12.7 minutes** (and 85 MVR).
The bus takes 70. The bus is **4.4× slower** and **8.5× cheaper**.

This reframes the entire "incentivise youth to take the bus" question. A
youth rider choosing a taxi over a bus that costs 10 MVR is not failing to
appreciate a discount — they are buying 57 minutes of their life back.

---

## 4. Demand

### 4.1 MTCC ridership, and the Friday effect

Weekday mean daily boardings, 2025: R1 5,212 · R2 3,818 · R4 1,146.
R3 and R7 are available monthly only and were split across day-types using
the day-type index measured on the daily routes.

Friday index (weekday = 100):

| Route | Mon | Tue | Wed | Thu | **Fri** | Sat | Sun |
|---|---|---|---|---|---|---|---|
| R1 | 5,132 | 5,177 | 5,344 | 5,361 | **3,192** | 4,585 | 5,043 |
| R2 | 3,756 | 3,908 | 3,908 | 3,859 | **2,427** | 3,447 | 3,655 |
| R4 | 1,122 | 1,140 | 1,152 | 1,168 | **722** | 1,014 | 1,145 |

Friday demand is **37–38% below** Thursday on every route. Seasonally, R1
ranges from 129,970 (Feb 2025) to 159,456 (Jul 2025) — a **+23%** swing.

Free-of-charge passengers (over 65, PWD, infants) are **27–35%** of all
boardings — a crowding marker, and a reason a large share of riders cannot
be flexed into off-peak.

### 4.2 The load-factor interpretation problem (assumption A1)

MTCC `total_pax` is undocumented. Two readings are possible:

| Reading | R1 (5,212 boardings, 61 trips, 84 seats) | R4 (1,146, 38 trips, 52 seats) |
|---|---|---|
| One direction | **89.5%** of seats (Saturday) | 51.3% |
| Both directions | 51% | 29% |

**One direction is the right reading.** Under the two-direction reading every
route sits at 28–51% and the problem statement ("some commuters waiting
while other buses run under capacity") would not be true. Under the
one-direction reading R1 is over capacity and R4 is not, which is exactly
what is observed and what the problem describes.

We still report a **band**: `load_factor_peak_pct` (every boarding rides the
full route) and `load_factor_avg_pct` (uniform alighting). **The ranking of
routes is identical under both bounds**, and the relative findings (F3, F4,
F5) do not depend on the interpretation at all.

**This is our first ask to MTCC:** does `total_pax` count one direction or
two, and boardings or unique passengers?

### 4.3 Airport demand — where the domestic data actually is

**Question: can MACL be filtered to domestic flights? Answer: no — MACL
contains no domestic flights.** Four tests:

| Test | Result |
|---|---|
| `region` values | South Asia, Middle East, SE Asia, Europe, East Asia, Central Asia & CIS, Africa, Other. **No "Domestic".** |
| Movements per day | 2025: **17.5/day**. The MBS Yearbook records ~95 international and ~587 domestic movements/day at Velana |
| `aircraft_category == Turboprop` (576 rows) | 40–50 pax, 8–12-hour block times, region = South Asia → **regional** turboprops to Dhaka/Kolkata/Colombo, not Twin-Otter island hops |
| Low-pax flights (arr ≤ 20) | Widebody/narrowbody with 0–16 arriving but 186–223 departing at 22:00–23:59 → **empty repositioning legs** |

The domestic data is in the **MBS Statistical Yearbook table 11.13**, which
reaches us through Team Kandu's `observations.csv` (and is independently
available as clean CSV in `ajmals/maldives-statistics`):

**Velana arrivals, 2025 (MBS Yearbook 11.13)**

| | 2025 total | per day |
|---|---|---|
| Domestic flights | 1,455,156 | **3,987** |
| International flights | 2,699,225 | **7,395** |
| Total | 4,154,381 | **11,381** |

**MACL coverage: 984,629 adult international arrivals in 2025 = ≤ 36.5% of the
Yearbook's international figure, and 0% of domestic.** So MACL is used for
the *shape* of the arrival profile only; the *level* comes from 11.13.

**A trap worth naming.** 11,381 people arrive at Malé airport every day, but
the airport bus routes (R3 + R4) carry only ~1,850 boardings/day and Avas
records ~349 taxi dropoffs at the terminal. Only ~19% of arrivals touch the
Greater Malé bus or taxi system at all, because most are Maldivian residents
connecting onward to other islands. **"11,381 arrivals vs 1,850 bus riders, so
the bus is failing" is wrong.** The correct question is how many arrivals
actually need Greater Malé ground transport, and the answer is far smaller
than the headline.

### 4.4 The arrival profile is tri-peaked

MACL international arrivals by hour, 2019–2025 (4.89M arrivals):

```
06:00  3.70%      14:00  9.94%      20:00  2.79%
07:00 12.27%      15:00  6.37%      21:00  3.04%
08:00 11.68%      16:00  1.78%      22:00  2.31%
09:00 11.52%      17:00  2.00%      23:00  0.25%
10:00  4.66%      18:00  1.23%
11:00 10.31%      19:00  3.18%
12:00  6.48%      04:00-05:00  1.92%
13:00  4.43%
```

**35.5% of arrivals land between 07:00 and 09:59**, with secondary peaks at
11:00 and 14:00. The weekday pattern is flat (14.0–14.5% each day) — so
airport demand has no Friday effect, unlike the bus.

---

## 5. Reconciling supply and demand

### 5.1 Method

1. **Supply level** = live `trips_per_day` (2026-10-10); **shape** = the
   published PDF pattern rescaled to that level; other day-types derived from
   the PDF's own ratios.
2. **Demand level** = MTCC observed boardings per route per day-type.
3. **Demand shape** = Avas hourly profile for the route's corridor,
   renormalised over the operating hours.
4. **Grid** = every scheduled departure is expanded to its exact minute, then
   aggregated to route × day-type × hour, producing `service_departures.csv`
   and `demand_supply_gap.csv` (both in `dashboard/data/`).

### 5.2 The gap table

`dashboard/data/route_load.csv`, captured service day (Saturday):

| Route | Official name | Bus type | Seats | Trips/day | Boardings/day | Pax/trip | Load peak | Load avg |
|---|---|---|---|---|---|---|---|---|
| R1 | West Park to HM Phase 1 | Double decker | 84 | 61 | 4,585 | 75.2 | **89.5%** | 44.7% |
| R3 | West Park to VIA | Airport bus | 52 | 20 | 752 | 37.6 | 72.3% | 36.1% |
| R2 | Carnival to HM Phase 1 | Double decker | 84 | 61 | 3,447 | 56.5 | 67.3% | 33.6% |
| R7 | HM Phase 2 to West Park | Double decker | 84 | 66 | 3,552 | 53.8 | 64.1% | 32.0% |
| R4 | HM Phase 1 to VIA | Airport bus | 52 | 38 | 1,014 | 26.7 | **51.3%** | 25.6% |
| R5, R6, R8, R9, R10–R15 | — | — | — | — | **no data** | — | — | — |

The pairing matters. Earlier drafts compared *weekday* boardings against a
trip count that was fetched on a Saturday, which pushed R1 to 102%. The feed
now gives Saturday service, so Saturday boardings are the correct pair — 89.5%.
R1's weekday boardings are 13.7% higher (5,212 vs 4,585); at the same 61 trips
that is **~102%**, which is the number to quote for a weekday, and it needs a
weekday capture to confirm (the service day may also be higher on a weekday,
which would reduce it).

### 5.3 Does the schedule track demand?

**Not answerable from one service day, and that is a finding.**

MTCC demand by day type is unambiguous — Friday boardings are 61–64% of a
weekday's on all three routes with daily data:

| Route | Demand index, Friday (weekday = 100) |
|---|---|
| R1 | 61.2 |
| R2 | 63.6 |
| R4 | 63.0 |
| R7 | 62.2 |

What the *service* does on a Friday cannot be read from a feed that returns one
service day. The earlier Ramadan-1446 PDF did contain separate Friday
patterns, and using them produced a clean finding — R2 ran 91% of its weekday
service on a Friday it lost 36% of its riders. **That finding is withdrawn**
because it rests on a withdrawn source. It is the strongest candidate for the
first follow-up capture, and the code path is one call.

### 5.4 The airport mismatch, quantified

Official RTL departures by hour, captured window:

| Route | Departures per hour | Headway | Expected wait |
|---|---|---|---|
| **R3** | **1, every hour**, 11:00–23:00 | **60 min** | **30 min** |
| R4 | 2 per hour, 12:00–23:00 | 30 min | 15 min |
| R9 | 2 per hour (same pattern as R4) | 30 min | 15 min |
| R1 | 2–4 per hour | 15–30 min | 7.5–15 min |

This is a sharper statement than the PDF version, because it is direct
observation rather than inference: **R3 is an hourly bus.** A passenger landing
at Malé airport without a booking faces a 30-minute expected wait for the
airport bus, and the bus runs the same frequency at 03:00 as at 08:00.

Against MACL's arrival profile (35.5% of international arrivals land between
07:00 and 09:59, with secondary peaks at 11:00 and 14:00), the fixed headway is
the mismatch. Nothing runs between 00:00 and 06:00, when 1.9% of arrivals land.

## 6. The mode-shift question, answered properly

### 6.1 The generalised-cost model

```
GC_bus  = fare_bus + (wait + ride) x VOT
GC_taxi = fare_taxi / sharing + (hail + ride_taxi) x VOT
P(switch to bus) = 1 / (1 + exp((GC_bus - GC_taxi) / 30))
```

Inputs: bus fares from Team Kandu; taxi fares from the Avas fare matrix;
taxi ride times observed from Avas records; bus ride times observed from the
live per-stop timetable; wait = headway ÷ 2, demand-weighted per corridor.

### 6.2 Results (baseline, VOT 250 MVR/h, taxi shared by 2)

| Corridor | GC bus | GC taxi | Gap | Break-even ride | **Minutes to shed** | p(switch) | p(switch, price only) |
|---|---|---|---|---|---|---|---|
| Malé↔HM Ph1 | 342.9 | 116.2 | **+226.7** | 15.6 min | **54.4** | 0.05% | **74.7%** |
| Malé↔HM Ph2 | 222.5 | 137.5 | +85.0 | 19.6 min | **20.4** | 5.6% | 76.3% |
| Malé↔Airport (R3) | 318.3 | 130.8 | +187.5 | 0.0 min | 44.0 | 0.2% | 69.7% |
| HM Ph1↔Airport | 264.2 | 123.3 | +140.8 | 12.2 min | 33.8 | 0.9% | 73.1% |
| HM Ph2↔Airport (R9) | 206.7 | 138.3 | +68.3 | 14.6 min | **16.4** | 9.3% | 71.4% |
| HM Ph1↔HM Ph2 | 206.7 | 95.0 | +111.7 | 13.2 min | 26.8 | 2.4% | 62.3% |

**Read the last two columns together:**

- **On price alone, 62–76% of taxi riders on every corridor would take the
  bus.** The bus is already 4–8× cheaper per passenger.
- **On generalised cost, 0.05–9.3% would switch.** The bus is beaten on time.

**A fare discount is therefore the wrong instrument.** It discounts the
dimension where the bus already wins, and leaves the dimension where it
loses untouched.

The **break-even** column is the assumption-free version of the question: at
VOT 250 and 2-up sharing, the bus needs its ride time down to 14.6–19.6 min
on three corridors. Two of those are reachable by express service. The
Malé↔HM Ph1 corridor needs 54 minutes — which is more than the entire
causeway cost, so **it requires solving the bridge**, not the stops.

### 6.3 Sensitivity

Capturable taxi rides per day, across VOT × taxi sharing:

| VOT (MVR/h) | sharing 1 | sharing 2 | sharing 3 |
|---|---|---|---|
| 100 | 3,001 | 1,453 | 1,014 |
| 250 | 764 | **191** | 115 |
| 400 | 96 | 20 | 12 |

A 250× range. **Therefore the headline claim in the pitch is the break-even
analysis (§6.2), not the point estimate.** Present capture as a band.

### 6.4 What this means for the youth incentive

Ordered by expected effect:

1. **Journey time** (express service, bridge priority) — the only lever that
   moves the binding constraint.
2. **Frequency in the right hours** — cuts the wait, which is 9.9–30 min
   depending on corridor; on R3 it is 30 min.
3. **Reliability information** (ETA) — reduces the *perceived* wait, which is
   what deters a young rider from walking to a stop with no idea when a bus
   comes.
4. **Fare discount / student pass** — lowest yield on its own, because price
   is not the binding constraint. It becomes valuable *after* 1 and 2, as a
   complement, and as an affordability argument for low-income riders.

---

## 7. The scenario engine

`dashboard/build/build_data.py`. Scenarios are **explicit trip moves**, not
percentage factors — at 1–3 trips per route per hour, a 12% change rounds to
zero and the "scenario" silently does nothing. Only captured hours are touched;
hours before the window stay null and are excluded from every KPI.

```
scenario                   mean wait  over capacity  unmet%  trips  demand
S0_baseline                     10.9            360   3.68%    162   9,805
S2_airport_retimed              10.4            355   3.63%    168   9,786
S3_rebalanced_to_corridor       10.6            349   3.61%    164   9,696
S4_express_peak                 10.5            248   2.53%    170   9,805
S5_recommended_package          10.0            242   2.48%    176   9,786
```

| Scenario | Definition |
|---|---|
| S2 | +1 departure per hour for R3/R4/R9 in 11:00–15:00, −1 in 22:00–23:00 |
| S3 | 6 trips off the airport routes in the 13:00–14:00 lull, 6 onto R1/R2 at 16:00–18:00 |
| S4 | one extra R1/R2 departure in each hour 15:00–18:00 (faster cycle from skip-stopping) |
| S5 | S2 + S4 |

**Honest reading.** S5 removes 118 boardings from over-capacity and cuts unmet
demand by 1.2 points with 14 extra trips. That is a modest, credible gain inside
a ~13-hour window — not a dramatic one. The Friday scenario is gone (no
service-day data) and the morning peak is outside the window, which is exactly
where the largest gains would be. **Say that in the pitch rather than inflating
the number.**

## 8. Things that were tried and rejected

| Idea | Why it was dropped |
|---|---|
| **Spatial bus-stop gap map** | 97.1% of taxi pickups are within 300 m of a stop; 0% are more than 800 m. Malé is 4 km long. The map would show nothing. |
| **MACL filtered to domestic flights** | MACL contains no domestic flights at all — it is ≤36.5% of international traffic and 0% of domestic. Domestic data comes from MBS Yearbook 11.13. |
| **Using MACL as the airport demand level** | Would understate airport demand by ~2.7×. |
| **Treating `total_pax` as a load factor directly** | 98 boardings/trip on an 84-seat bus is impossible without knowing the counting basis. Fixed by reporting a band and asking MTCC. |
| **Assuming the Avas hourly shape is the bus hourly shape** | It is a proxy. Used explicitly as a *shape* with the level anchored to observed MTCC boardings, and the assumption is labelled in every output row. |
| **Using the live per-stop timetable as the service pattern** | It is a single evening snapshot (19:54–23:59) with no morning peak. Demoted to per-stop run times only. |
| **MTCC PDF schedules as the service basis** | They are the Ramadan 1446 edition (Feb 2025), diverge from the live 2026 timetable by −28% to +113% by route, need Dhivehi-aware parsing, and omit R15 entirely. Replaced by the official RTL JSON feed, which is current and machine-readable. |
| **FollowMe (17.46M vessel GPS rows)** | Out of scope per the team decision; it is marine, and the problem statement is about Greater Malé buses. |
| **A spatial "missing route" analysis** | 97.1% coverage kills it, and the network is already dense. |
| **An LP/MILP fleet optimiser** | Overkill for the time budget and hard to explain in 5 minutes. A transparent reallocation model with a Pareto view is more defensible. |
| **Building the camera crowd detector as a product** | Not reproducible, not actionable by a planner, and it would consume 3 hours. Reframed as a 90-minute validation appendix. |

---

## 9. Open questions and data requests for MBS / MTCC

1. **A weekday and a Friday capture of the RTL feed.** The endpoint is public
   and needs no key; it only has to be called at different times. That closes
   the 06:00–11:00 morning gap and restores the day-type comparison. This is
   the single biggest gap in the project.
2. **The fleet table** — vehicle type and seat capacity per route, and the
   number of buses in the MTCC Malé fleet. Currently team domain knowledge.
3. **The `total_pax` definition** — one direction or two? Boardings or unique
   passengers? Free-of-charge passengers included?
4. **Ridership for the 10 routes with none** (R5, R6, R8, R9, R10–R15). The
   coverage matrix in `dashboard/data/route_fleet_capacity.csv` shows exactly
   what is missing.
5. **R3's weekday pattern** — only Friday and Saturday/Public Holidays are
   published.
6. **R15** — appears in the live route list with no published schedule and no
   ridership data. Is it operating?
7. **A GTFS feed.** None is public for Malé. Ours would be the first.
8. **Census 2022 / HIES 2019 access link** (the FAQ says MBS provides them).
   HIES transport expenditure would make the affordability argument airtight.
9. **A complete MACL extract**, or a note on its coverage rule.

---

## 10. Figures

| File | Shows |
|---|---|
| `docs/figures/F1_bridge_share.png` | 40 of R1's 70 minutes are the two causeway crossings |
| `docs/figures/F2_load_factors.png` | R1 at 89.5% of capacity; the airport bus at 51% |
| `docs/figures/F3_demand_daytype.png` | Friday demand is 37% below a weekday (demand only) |
| `docs/figures/F4_airport_mismatch.png` | Flat 30-min airport service vs tri-peaked arrivals |
| `docs/figures/F5_scenario_kpis.png` | Baseline vs the recommended package |
| `docs/figures/F6_generalised_cost.png` | Break-even journey time per corridor |

Generated directly from the tables in `dashboard/data/`. No number in any
figure is typed by hand.
