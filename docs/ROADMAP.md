# Roadmap — from projection to realtime

**Pathways · Maldives Datathon 2026 · Team Wayfinders**

This document describes the phase **after** the submitted build. **Nothing in it
is implemented.** The codebase is unchanged by it, no sensor is installed, and
the submission stands on historical data alone.

It exists because the model we submitted is deliberately an offline projection,
and we would rather state what would make it realtime — at what cost, under what
conditions, and with what we would refuse to claim — than leave the ambition
implicit.

---

## 0. Where we are today

The submitted tool answers "was the bus supply matched to demand, on the day we
measured?" It does not answer "is it matched right now?"

| Layer | Status today | Basis |
|---|---|---|
| Routes, stops, fares, timings | **Measured** | Official RTL feed, 24 Oct 2026 |
| Service frequency by hour | **Measured** | RTL feed — one Saturday, from ~11:00 |
| Demand level (boardings/day) | **Measured** | MTCC counts, 5 of 15 routes |
| Demand by hour | **Modelled** | Avas taxi shape, scaled to the MTCC level |
| Demand by stop | **Allocated** | Avas catchments, scaled 2.7–3.4× per route |
| Vehicle position | **Snapshot** | One capture, not a live signal |
| Vehicle capacity | **Team knowledge** | Not instrumented |

The honest summary is in the right-hand column: **everything measured was
measured once, and everything that varies within the day is modelled.**

---

## 1. The gap the model is asking us to close

The single most actionable finding in this project is that the airport bus
**reaches 98.4% of seat capacity** on the final segment into the airport (R3,
STELCO → VIA, 13:00) **while running once an hour.**

It is also the finding with the least direct observation behind it.

ADR-0002 records that the stop-level load factor is an *allocation, not a
measurement*: we distribute each route's daily boardings across its stops using
taxi catchments, then scale up by 2.7–3.4× to match the MTCC total. That is a
defensible method and it survives validation, but it is inference.

**The project's headline conclusion is the one a sensor would settle in an
afternoon.** That inversion is the reason this roadmap exists. It is not a
product idea bolted onto an analysis; it is the measurement the analysis keeps
asking for.

There is a second, quieter gap. **Ten of the fifteen routes have no ridership
data at all** and are published as `NO DEMAND DATA` rather than zero-filled.
Sensors would cover those routes without depending on MTCC releasing counts.

---

## 2. Phase 2a — measure the stop

### 2.1 The sensor comparison

The requirement is narrow and should drive the choice: **how many people are
waiting at this stop, right now.** That is *occupancy*, not flow.

| Sensor | What it actually measures | Behaviour at a busy stop | Cost/stop | Verdict |
|---|---|---|---|---|
| **Edge camera + computer vision** (YOLO / CSRNet) | Queue length, density, dwell time | Good to ~50 people; degrades with occlusion and in low light | $150–400 + compute | **Best signal**, richest data. Needs on-device face blurring |
| **Thermal / LWIR camera** | Headcount | Moderate accuracy, strong at night, unaffected by glare | $300–600 | **Best privacy/accuracy trade-off.** No identifiable features |
| IR break-beam counter | Directional *crossings* | **Poor** — a group passing the beam counts once; cannot see a stationary queue | $ | Counts flow, not occupancy. Wrong tool |
| Active IR / time-of-flight | Presence, coarse distance | Poor outdoors: sunlight, rain and wet surfaces all corrupt range | $ | Weak |
| Ultrasonic (HC-SR04 class) | Proximity | Poor — temperature and wind drift, ~4 m range, no counting in crowds | $ | Hobby grade only |
| Wi-Fi / BLE probe | Passing devices | Counts phones, not people; ~60–70% penetration; MAC handling is a privacy liability | $$ | Not recommended |
| Manual roving count | Ground truth | Reference standard | Labour | **Required** — calibrates any of the above |

**Recommendation: a thermal or edge-blurred camera at three stops, calibrated
against manual counts.**

We want to be explicit about the two options that look cheapest. IR break-beam
counts *crossings* and ultrasonic measures *proximity*; neither reports how many
people are standing on the kerb, which is the quantity the optimiser needs. They
are the right choice for counting passengers through a door. They are the wrong
choice for measuring a queue.

### 2.2 Pilot design

| | |
|---|---|
| Stops | **3** — R3 `STELCO` (approach to the airport), R1 `Hulhumale' Police Station`, R2 `Centro Mall` |
| Why these | The two highest modelled segment loads, plus one lower-load control so the calibration is not fitted only to crowds |
| Cadence | One aggregate count every 30 s, plus a per-minute queue estimate |
| Duration | 8 weeks, covering a weekday, a Friday and a Saturday |
| Ground truth | 2 manual counters × 4 windows × 2 days = 32 person-hours, with inter-counter agreement reported |
| Acceptance | Mean absolute percentage error **< 25%** above 10 people waiting; report accuracy **by queue band**, not as a single number |

Publishing accuracy by band rather than in aggregate is the difference between
an honest instrument and a marketing figure — crowd counters are accurate when a
stop is quiet and degrade exactly when the stop is busy.

---

## 3. Phase 2b — measure the vehicle

Demand alone cannot drive an optimiser. Knowing 40 people are waiting is
useless without knowing where the bus is.

**GTFS-Realtime is the natural extension of the feed we already publish** — same
data model, same tooling, additive files. Vehicle positions and trip updates can
come from the RTL live endpoint
(`https://bo.rtl.mv:4455/maldives/api/v2/bus/routedetails`, which requires a
JWT), noted in `SPEC.md` §12 as a cheap and high-value win.

What it adds that the timetable cannot:

- **Actual** running times, including bridge delay — the binding constraint
  identified in F1
- real headway and **bunching** (two buses arriving together after a gap)
- dwell time at stops, which our current model assumes is zero
- arrival predictions, so "wait" becomes a live estimate rather than
  headway ÷ 2

---

## 4. Phase 3 — the loop

Realtime optimisation is a control loop, not a dashboard refresh. The phases
above supply the two inputs; this is what consumes them.

```
   ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │  sensors    │────▶│  demand +    │────▶│  decision   │
   │  (queue)    │     │  supply      │     │  rules      │
   └─────────────┘     │  nowcast     │     └──────┬──────┘
                       └──────▲───────┘            │
   ┌─────────────┐            │                    ▼
   │ GTFS-RT     │────────────┘             ┌─────────────┐
   │ (vehicle)   │                          │  dispatch / │
   └─────────────┘                          │  reallocate │
                                            └──────┬──────┘
                                                   │
                       ┌───────────────────────────┘
                       ▼
                 measure outcome (back to sensors)
```

Illustrative decision rules — the shape of the policy, not a specification:

| Trigger | Action | Guardrail |
|---|---|---|
| Queue > 25 and next scheduled arrival > 12 min | Insert a short-turn trip from the nearest spare vehicle | Never below the published minimum service on any corridor |
| Two vehicles arrive within 3 min (bunching) | Hold the follower 4 min to re-space | Never hold a bus carrying more than 70% of seats |
| Predicted wait > 15 min for 3 consecutive intervals | Reallocate one peak trip from the lowest-load corridor | Reallocation must be fleet-neutral, as in ADR-0008 |

**This is where the scenario engine stops being a scenario.** S5 today moves 18
existing trips by hand, computed once. The loop recomputes that reallocation
every 15 minutes from live queues. The objective function, the fleet-neutrality
constraint and the guardrails carry over unchanged — the codebase already has
the right shape for it.

---

## 5. What has to change in the architecture

**ADR-0007 records that the dashboard is a static site with no backend.** A
realtime layer supersedes it. That should be a deliberate, recorded decision, not
a slide.

| Component | Today | Phase 2 | Why |
|---|---|---|---|
| Sensor gateway | — | New | Edge inference, publishes a count, never an image |
| GTFS-RT poller | — | New | Polls vehicle positions on a fixed interval |
| Time-series store | — | New | Queues, headways and loads are append-only observations |
| Compute | Batch scripts | Same models, scheduled | The reconciliation does not change; only its trigger does |
| Serving | Static files | Small API + the existing dashboard | The dashboard stays; it gains a live layer |
| Auth | None needed | Required | Operational data is not public by default |

The modelling work is **not** thrown away. The reconciliation (ADR-0002), the
level/shape split (ADR-0004), the null-not-zero rule (ADR-0005) and the
fleet-neutral constraint (ADR-0008) all still apply. What changes is when they
run.

---

## 6. Privacy and governance

This is the part of the roadmap most likely to decide whether the phase happens
at all, so it is a design property rather than a compliance afterthought.

**Design rule: the count leaves the stop, never the image.**

| Property | Implementation |
|---|---|
| No video retention | Frames are processed on-device and discarded in memory |
| No identifiable features | Face and head blurring before inference, or thermal imaging, which records no identity |
| Minimal transmission | One integer per 30 s — a few bytes, viable over LoRa or a poor 4G link |
| Aggregation only | Queue length and dwell; no demographic inference, no re-identification, no tracking between stops |
| No enforcement use | Not for fare evasion, trespass or policing |
| Transparency | Signage at every instrumented stop stating what is counted and why |

**Legal review precedes the pilot.** Maldives data-protection law is currently in
flux — an Act is in force and a replacement Bill was before parliament in 2025 —
so we state the requirement rather than cite a statute. Any deployment must also
clear MTCC/RTL's own policy on photographing their passengers.

The privacy argument is stronger than it looks. A crowd counter needs a number;
it does not need a person. Designing for a count rather than an image removes
most of the objection before it is raised.

---

## 7. Cost, power and the Maldivian environment

Indicative figures, 2026 USD, to be replaced by quotes before any commitment.

| Item | Per stop | Note |
|---|---|---|
| Camera (edge-CV or thermal) | 150–600 | Thermal costs more, and removes the privacy problem |
| Edge compute | 150–250 | Jetson-class or Raspberry Pi 5 with accelerator |
| IP66+ enclosure and sunshade | 60–120 | Salt air and monsoon rain are the drivers |
| Solar 50 W + battery + MPPT | 80–150 | Assume **no mains power at the stop** |
| 4G modem or LoRa gateway | 40–80 | Per stop, or shared across a cluster |
| Mounting and civil works | 30–60 | |
| **Pilot: 3 stops** | **~1,500–3,800 total** | Plus 32 person-hours of manual calibration |
| **Network: 61 stops** | **~30,000–75,000** | The full Greater Malé stop list |

Three environmental constraints drive the specification more than the sensor
choice: **salt-laden air** (corrosion), **30°C+ with high humidity**
(thermal throttling of edge compute), and **monsoon rain** (optical sensors
degrade; enclosures must shed water, not pool it). Any of these will kill a
pilot faster than model accuracy will.

---

## 8. Evaluation — how we would know it worked

| Question | Measure | Threshold to continue |
|---|---|---|
| Does the sensor count people? | MAPE vs manual counts, by queue band | < 25% above 10 people |
| Does the model nowcast better? | Segment-load error with sensors vs without | Material reduction in MAPE against manual truth |
| Does the loop help passengers? | Mean and 90th-percentile wait, before vs after | Improvement with no corridor worse off |
| Is it equitable? | Wait change on Villimalé and low-demand routes | No corridor regresses materially |
| Is it reliable? | Sensor uptime, missing intervals | > 95% uptime over 8 weeks |

The equity check is not optional. An optimiser that improves Malé–Hulhumalé and
quietly degrades Villimalé has failed, and the fleet-neutral constraint alone
will not prevent it.

---

## 9. What we would not claim

We would rather bound the ambition than have it bounded for us.

**The submitted deliverable is not a realtime app.** It is an offline projection
engine built on historical data, with a costed and evaluated path to realtime
decision support. Those are different claims and only the first is true today.

**We would not claim:**

1. **That automatic dispatch is near.** Reallocating vehicles is an operator
   decision under MTCC authority. Our role is to make the recommendation
   well-founded, not to make it automatically.
2. **That crowd counting is a solved problem.** Accuracy degrades exactly where
   it matters — dense queues — which is why §2.2 reports accuracy by band.
3. **That the privacy question is settled.** §6 states a design position and a
   legal precondition; it does not constitute legal clearance.
4. **That sensors replace the model.** Ten routes have no ridership data and one
   Saturday was captured. Sensors would extend coverage route by route; they do
   not remove the need for the historical reconciliation.
5. **That the roadmap is funded, approved or scheduled.** It is a plan with
   costs and preconditions attached.
6. **That density is demand.** Population data locates people; it does not say
   when or where they travel. A route proposed from density is a hypothesis to
   be tested against counts, not a plan.
7. **That the tool can fund a new route.** It can show that a corridor would
   fill; it cannot buy the vehicle, because the scenario engine is fleet-neutral
   by construction (ADR-0008, ADR-0014).

The honest ladder is: **projection → decision support → closed-loop dispatch.**
The submission is on the first rung. This document describes the next one.

---

## 10. Entry conditions for starting Phase 2

Phase 2 begins only when all five hold:

- [ ] **Legal review completed** on camera capture of passengers in public
      space, covering data-protection law and MTCC/RTL policy
- [ ] **One stop instrumented and validated** against manual counts, at the
      accuracy threshold in §2.2
- [ ] **GTFS-RT access** granted (RTL JWT) or an equivalent vehicle feed
      available — demand without supply position is not a control loop
- [ ] **Operator agreement** in principle that a reallocation recommendation
      can be acted on
- [ ] **Budget and owner** for the pilot, including the 32 person-hours of
      manual calibration

Until then the current tool stands on its own: it is reproducible, validated on
held-out data, and honest about what it does not measure.

---

## 11. Two extensions beyond the loop

Neither extension belongs to Phase 2, and neither is implemented. They are
recorded because the same data and the same fleet-neutral constraint carry over,
and because each changes what the model is asked rather than what it claims.

### 11.1 Event-driven demand

Demand today is a taxi-derived hourly shape averaged over 219 held-out days. A
match at the national stadium, a concert on Hulhumalé, a Friday market or a
cancelled ferry is smoothed away by that average, so the model cannot represent a
surge that happens at a known place and time.

The extension is an event calendar — venue, date, start time, expected
attendance — applied as a short-lived uplift to the affected stops before the
scenario engine runs.

| Item | Position |
|---|---|
| Input | A public events feed, or a curated calendar where none exists |
| Uplift | Attendees × mode share × arrival/departure window, then calibrated against observed loads |
| Output | Extra trips on a known date, expressed as GTFS `calendar_dates` exceptions |
| Guardrail | Fleet-neutral: event trips displace that day's lowest-load trips (ADR-0008, ADR-0014), or the operator supplies a spare vehicle |
| Precondition | At least two events with usable attendance and load data to calibrate against |

The calendar is the easy half. Calibration is the hard half: without two observed
events we would be inventing the uplift, and an invented uplift is worse than
none, because it reads as a forecast.

### 11.2 Routes chosen from where people will be

The submitted network was not designed from the data we now hold, and the first
half of the evidence is already committed. `scripts/build_pois.py` scrapes 321
named trip generators from OpenStreetMap — schools, government offices,
hospitals, mosques, markets, shops — classifies each into one of seven
demand-curve categories, and gives it a nearest stop, that stop's routes and a
walking distance. `data/derived/poi_access_gaps.csv` then reports the access gap
per category and island.

That scrape also records what is missing. Only 3 of 321 POIs sit beyond 400 m of
a stop, so within mapped Malé the network already reaches almost every mapped
destination. But north of Hulhumalé Phase 1, OSM holds 6 named POIs against
roughly 2,900 mapped buildings: the buildings exist, the amenities are not
tagged. Absence of a POI means unmapped, not vacant.

Two inputs would turn the POI layer from an access audit into a route question:

| Input | Why it is needed | Where it would come from |
|---|---|---|
| Population density by island and by Malé ward | The yearbook gives atoll totals; a route needs people per hectare | Census tabulations |
| Commercial and office pipeline, with opening dates | OSM maps what exists, not what is about to employ people | Planning approvals and developer announcements |

The output is a candidate corridor and its unmet demand under the fleet
constraint — not a timetable. Three limits bound it: density is not demand, an
opening date can move, and a new route needs a vehicle the fleet-neutral engine
cannot supply. The tool can show that a corridor would fill; buying the bus is a
capital decision outside it.

---

*Related: [ADR-0013](adr/0013-realtime-layer-deferred.md) records the deferral
as a decision. [docs/GTFS.md](GTFS.md) describes the feed that GTFS-Realtime
extends. [SPEC.md](../SPEC.md) §10.4 records the earlier, narrower position on
cameras.*
