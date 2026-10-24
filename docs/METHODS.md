# Methods note

**Raajje Rebalancer — Greater Malé bus demand and supply**
Maldives Datathon 2026 · Team Wayfinders · 24 October 2026

This note records what data we used, how we processed it, what we assumed, where
we used AI, and what the analysis cannot tell you. It is written so that an
independent analyst could reproduce or challenge any result.

---

## 1. Scope

We estimate how bus service in Greater Malé compares with passenger demand — by
route, by hour, and by day period — and we evaluate what would change for
passengers if trips were moved.

The study area is Malé, Hulhumalé Phase 1 and Phase 2, Velana International
Airport, and Villimalé.

Out of scope: marine transport, ferries, inter-atoll travel, and fares policy.

Also out of scope by explicit decision: the **realtime layer** — sensor-based
people counting at stops, live vehicle positions, and closed-loop reallocation.
Nothing of that kind is implemented here. It is planned as a later phase with
stated entry conditions, documented in [ROADMAP.md](ROADMAP.md) and recorded as
[ADR-0013](adr/0013-realtime-layer-deferred.md).

---

## 2. Data sources

All sources are public. Nothing private, restricted, or requested under
disclosure was used.

| # | Source | Publisher | Access | Vintage | Used for |
|---|---|---|---|---|---|
| 1 | Bus routes, stops, fares, departure times | RTL / MTCC · `bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails` | Direct API, no key, 24 Oct 2026 | Current (Oct 2026) | **Supply** |
| 2 | Bus passenger counts | MTCC via MBS datathon release | `MTCC.zip` | 2023–2025 | **Demand levels** |
| 3 | Taxi trips (371,788 records) | Avas via MBS datathon release | `Avas_Ride.zip` | Aug–Sep 2026 | **Demand shape**; fare matrix |
| 4 | Airport movements (168,959) | MACL via MBS datathon release | `MACL.zip` | 2012–2026 | Arrival **shape** |
| 5 | Statistical Yearbook 11.13 | Maldives Bureau of Statistics | Team upload + `statisticsmaldives.gov.mv` | 2026 edition | Airport **levels**, incl. domestic |
| 6 | Labour Force Survey, Malé 2024–25 | Maldives Bureau of Statistics | Team upload | Released 1 May 2026 | Employment denominator |
| 7 | Fleet capacity by route | Team field knowledge | `data/raw/mtcc_bus_capacity.csv` | 24 Oct 2026 | **Capacity** |
| 8 | Basemap and road network | OpenStreetMap contributors | `openstreetmap.org` | — | Map rendering (ODbL) |

Full links, licences and per-file provenance: **[DATA_SOURCES.md](../DATA_SOURCES.md)**.

**One source we deliberately did not use.** MTCC publishes route timetables as
PDFs, but the only edition available online is "Ramadan 1446" (February 2025) —
18 months stale and diverging from the live timetable by −28% to +113% by route.
We replaced it with source 1 and withdrew the findings that depended on it
(ADR-0001, ADR-0009).

---

## 3. Processing pipeline

Each step is a script; the order is load-bearing.

| Step | Script | Output |
|---|---|---|
| 1 | `dashboard/build/build_data.py` | Route master, stops, geometry, departures per hour, hourly demand–supply gap, route load, scenarios, morning inference, usage by period |
| 2 | `dashboard/build/build_stop_demand.py` | Stop-level boardings, segment loads, refined gap and load tables, scenario moves |
| 3 | `dashboard/build/build_validation.py` | Holdout error, airport source reconciliation |
| 4 | `dashboard/build/build_schedule_crosscheck.py` | Feed vs published timetable comparison |
| 5 | `dashboard/build/build_figures.py` | Figures F1–F7 |
| 6 | `dashboard/build/build_gtfs.py` | GTFS feed for the network |
| 7 | `dashboard/build/verify_claims.py` | **57 assertions re-derived from raw sources** |

`make data && make figures && make check && make test` reproduces everything. The rebuild is
deterministic: a second run produces no diff.

---

## 4. Methods

### 4.1 Demand: level and shape, separately

No single source gives both how many people ride and when.

- **Level** — observed bus boardings per route per day type, from MTCC. This is
  the number in every load factor.
- **Shape** — the hourly profile of taxi trips on that route's corridor, from
  Avas, used only to distribute the level across the 24 hours.

Where MTCC has no ridership, **no demand is emitted**. Ten of the 15 routes show
`NO DEMAND DATA` rather than a taxi-derived estimate. We do not convert taxi
trips into bus trips (ADR-0004).

### 4.2 Stop-level allocation and segment load

A route-level average says nothing about how full a bus is at a given point. We
allocate each route's daily boardings to its stops using the Avas catchment at
each stop, then compute the load on every stop-to-stop segment, hour by hour.

This is what produced the finding that the airport buses fill up on the approach
to the airport — R3 reaches 98% of seat capacity on its final segment while
running hourly, and R4 reaches 84% (ADR-0002, ADR-0003 amendment).

### 4.3 Service and capacity

Supply is the official per-stop scheduled departure times. Capacity is the fleet
table: 72 seats on a double decker (84 including permitted standing), 55 on a
coach, 33 on a single decker, 24 on a diesel minibus, 11 on an electric minibus
(15 with standing). Where standing capacity was not stated (R5, R6) **no load
factor is computed** (ADR-0010).

### 4.4 Scenarios

Each scenario moves a named number of trips between named route-hours. They are
fleet-neutral: no scenario adds a vehicle. Percentage scaling was tried first and
abandoned because at one to three trips per route-hour it rounds to no change
(ADR-0008).

Two rules keep a scenario honest, and both are asserted in the build:

- **A donor must still fit its own passengers.** A trip is taken only from an
  hour that stays within 100% of seats after losing it. Without this rule the
  model took a bus out of a 3-trip hour running at 83%, left it at 125% with
  35 passengers behind, and logged the move as a relief.
- **A cancelled move is not counted.** A move that is later reversed exactly is
  removed from the log before the KPIs are computed, so `trips_moved` equals the
  net change in the fleet.

The effect is a much smaller, much more honest set of moves: the recommended
package moves 6 trips, not 18, and two of the three terms now report
near-null results — the airport routes have the spare vehicles, and the
corridor does not.

### 4.5 Validation

Held-out prediction, not assertion. The demand model is fitted on a
chronological 80% of 2025 days and predicts the remaining 20%:

| | Mean absolute percentage error |
|---|---|
| Naive baseline (route mean) | **16.27%** |
| Our model | **9.91%** |
| Saturday only | **7.10%** |

Separately, we reconciled three airport sources against each other. This is what
established that the airport extract covers **40.16%** of international arrivals
and **no domestic flights**, and carries no seasonal signal.

### 4.6 Working hours

No published working-hours data exists. We assume **08:00–16:00** and publish the
band rather than the point: 07:00–15:00 gives 37%, 08:00–16:00 **39%**,
09:00–17:00 42% (ADR-0012).

### 4.7 GTFS construction

The RTL payload carries per-stop timings for each trip, so the feed's
`stop_times` are **the observed schedule, rounded — not interpolated from an
assumed speed**, which is how most synthesised feeds are produced.

Three decisions follow from the source's limits rather than from preference:

- **One service day.** `calendar.txt` contains Saturday 2026-10-24 only, because
  the endpoint returns only the remainder of the day from the moment it is
  called. We did not extrapolate a weekday we never observed.
- **11 of 15 routes.** R10, R11, R12 and R15 return no timings; they are absent
  rather than invented.
- **32 partially-timed trips** ship with the stop-times they actually have, not
  with interpolated times that would look precise and be wrong.

One stop that cannot be boarded (`MWSC Flat Bus Stop`) is encoded
`pickup_type=1` on the 112 stop-time rows that call there, rather than dropped,
so the route geometry stays correct. The feed is validated twice: 18
structural checks re-asserted by `verify_claims.py`, and MobilityData
`gtfs-validator` 6.0.0 reporting **0 errors** and 2 warnings, both inherent to a
one-day feed. See [GTFS.md](GTFS.md).

---

## 5. Assumptions register

The assumptions that change results, with what happens if they are wrong.

| # | Assumption | Basis | Sensitivity |
|---|---|---|---|
| A1 | Bus passenger counts are **one-directional boardings** | Consistency with observed crowding | A two-directional reading would roughly halve every load factor but would not change the route ranking |
| A2 | Taxi hourly profile ≈ bus hourly profile | Only available intraday signal | Shapes the peak; does not change daily totals |
| A3 | Fleet capacity by route | Team field knowledge | Affects absolute load factors; R5/R6 excluded as not comparable |
| A4 | Service day 06:00–24:00 | Derived and cross-checked on two routes | Morning headway ±8% for a ±30 min start change |
| A5 | Working hours 08:00–16:00 | None — assumption | ±3 percentage points per hour |
| A6 | One taxi carries two passengers | Assumption | Modal-shift estimate ranges 12–3,001 rides/day across plausible values |
| A7 | Value of time 250 MVR/hour | Assumption | Drives the generalised-cost comparison; the break-even figures are the assumption-free version |

---

## 6. Use of AI

Stated plainly, because a reader is entitled to know.

**What AI was used for.** An AI coding assistant (via OpenCode) was used
throughout:

- discovering that the official bus timetable was available as a public JSON
  endpoint, and mapping its structure
- writing the processing scripts in `dashboard/build/`, and the documentation
  and decision records
- drafting this note and the public README
- reviewing and resolving the merge conflicts when two analysts' branches
  diverged

**What AI was not used for.** Collecting primary data, making scope decisions,
building the dashboard interface, and supplying the fleet capacity figures and
the MBS documents, which came from the team.

**How the output was controlled.** Three mechanisms, in order of importance:

1. **Machine verification.** `verify_claims.py` re-derives **57 claims** from the
   raw sources and fails the build if the committed numbers disagree. No figure
   in the report is taken on trust from the assistant.
2. **Human review.** Every merge was reviewed and approved by a team member.
   Scope, framing and policy recommendations are the team's.
3. **Documented reversals.** The assistant produced findings that were later
   wrong and were withdrawn when evidence changed, each recorded in an ADR:
   - a load factor of 102% that paired weekday demand with a Saturday trip count
   - a claim that the airport extract covered 36.5% of arrivals (it is 40.16%;
     36.5% was the adult-only figure)
   - a claim that the airport buses ran half empty, which the stop-level model
     inverted — they reach 84–98% on the airport approach
   - a Friday service comparison that rested on the withdrawn PDF timetable
     (ADR-0009)

We record these because the correction trail is evidence of method, not a
weakness. Any claim that survived is one that either an independent check or a
second analyst could not overturn.

**Per-member confirmation.** Each team member is responsible for disclosing their
own tool use. This section records the assistant's contribution; colleagues'
individual use of AI tooling for modelling and interface work should be added by
them rather than folded into this account.

**Recommendation to readers.** Treat this as an analyst's draft: the arithmetic
is reproducible and machine-checked, but the framing and the policy
recommendations require human judgement.

---

## 7. Limitations

### Data coverage

- The timetable feed returns only the rest of the day from the moment of the
  request. Our capture covers **11:00–24:00 of one Saturday**, so the morning
  peak is bounded, not observed (ADR-0005, ADR-0011).
- **Only 5 of 15 routes** have passenger counts at all.
- The airport extract covers **40% of international arrivals, no domestic
  flights, and no seasonal variation**.
- Results describe **one Saturday in October 2026**, not a weekday.

### Method

- Load factors are **modelled from taxi patterns**, not counted on the bus.
  There is no automatic passenger counter data.
- The segment model requires a catchment scale factor (2.7–3.4× per route); it is
  an allocation, not a measurement.
- Demand counts boardings, not journeys: a passenger changing routes is counted
  twice.
- We model no queueing. "Unmet demand" is demand exceeding seats in an hour, not
  a simulation of who is left at the stop.

### Assumptions

- The working-hours window, the value of time, and taxi occupancy are assumptions
  (see §5).
- Fleet capacity is per route, not per departure. If vehicle types vary by trip,
  load factors are wrong in both directions.

### What would change the conclusions

- A weekday and morning capture of the timetable would test the day-type findings
  and the inferred morning headway.
- Passenger counts for the other ten routes would extend the load analysis from a
  third of the network to all of it.
- Counted boardings at a handful of stops would calibrate the segment model.

---

## 8. Reproducibility and responsibility

```bash
make setup
make data figures gtfs
make check
make test
```

`make check` must report **92/92**. If it does not, the committed numbers and the
prose disagree, and the prose is wrong.

`make test` runs `tests/test_reallocator.py`, which pins the two rules that keep
a scenario honest: a donor hour must still fit its own passengers after giving
up a trip, and a move that is later undone is not counted as relief. Both were
violated by an earlier version of the reallocator, which produced a "recommended
package" that partly cancelled itself.

The team accepts responsibility for the framing, the assumptions and the
recommendations in this submission. The data and the code are published so that
others can test them.
