# ADR-0015 — A demand-derived reroute network, simulated rather than scheduled

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `dashboard/data/reroute_*`, `pop_grid.csv`, the `#reroute` tab

## Context

The submitted tool answers "is today's supply matched to today's demand, on
today's stops?" and its scenario engine is deliberately **fleet-neutral**
(ADR-0008): a trip can be moved between route-hours but no bus can be added.

Two questions were being asked of it that it cannot answer:

1. **"Could the stops and routes themselves be better?"** The scenario engine
   takes the stop set and the route alignment as given. Nothing in the repo
   tests whether that layout is right.
2. **"When is the next bus?"** Every departure in the tool is a published
   timetable entry, so the answer is a lookup, not a decision.

Answering both honestly requires departing from three earlier decisions, and
this ADR records those departures rather than letting them happen quietly.

## Decision

**1. Reroute scope is R1–R12: Malé, Hulhulé (the airport island) and Hulhumalé.
Villimalé (R13/R14) is out of scope and keeps today's service.**

**1b. Malé keeps its existing routes and stops. Hulhumalé gets closed loops.**

This was revised after the first build, and it is the most important decision in
this ADR.

Malé's regeneration was tried and rejected. Every variant produced worse journey
times, for a structural reason: the streets are narrow, the existing alignment is
already close to what the roads allow, and 97% of taxi pickups are within 300 m
of an existing stop. There was almost nothing to win and a lot to lose. So Malé's
and the airport island's stops and route orderings are **carried over verbatim**,
and the population p-median runs only for Hulhumalé.

Hulhumalé is the opposite case. It is planned, gridded, still filling in, and its
local routes (R5, R6) are **open** services whose terminals are 781 m apart: a
passenger going the other way round the island is not served at all. So R5 and R6
are retired and the island's local service becomes **closed circuits** - leave the
hub, go round, come back the same hub by a different road.

A circuit is built as a **cycle in the road graph**: out to an anchor by the
shortest path, back by the shortest path with the outbound edges penalised. That
closes the loop by construction and keeps the return leg on a different street.
Visiting waypoints in bearing order was tried and produced 27 km of route on a
2 km island.

- Villimalé is a separate island with no road link to Malé or Hulhumalé in the
  committed road graph.
- Avas contains **no Villimalé trips at all** — its westernmost pickup is
  longitude 73.5005 and Villimalé sits at about 73.483 — so there is no revealed
  demand to model from. `build_stop_demand.py` already emits nulls, not zeros,
  for R13/R14.
- Its real demand denominator is the ferry, which this project does not model.

Enforced, not merely documented: Villimalé is not fetched by
`build_population.py`, stop candidates are restricted to the single road-graph
component that contains Malé, the airport and Hulhumalé, and
`tests/test_reroute.py` asserts no generated stop or route falls in the
Villimalé box.

**2. The reroute may add buses.** This is an explicit departure from ADR-0008.
The fleet-neutral rule exists because a planner working within today's timetable
cannot conjure a vehicle. A network redesign is not that question: it asks what
the service would need to be, so "you need 25 more buses to do this" is a valid
and useful answer. The comparison is therefore reported as **buses used**, not
hidden, and a fleet-neutral variant is available by re-running with the spare-bus
rule off.

**3. The reroute has no published timetable.** Departures are decided at runtime
from demand: a bus leaves when its headway expires or when it reaches 90% of its
seats. This is what makes "when is the next bus" a real question and what makes
the 10× replay worth watching. The published-timetable network is kept in the
same simulation as the baseline, so the two are compared by one engine.

**4. Population comes from building footprints calibrated to published census
totals.** There is no population raster for Greater Malé. OSM footprint area ×
storeys, calibrated per island to the 2022 census, is a proxy for floor area —
not a measurement of residents. Only 232 of 3,771 footprints in the study area
carry `building:levels`; the rest get a storey count from their type. The proxy
is blended with night-time taxi pickups, and both are columns in the output.

**4b. The comparison is an ablation with a held fleet, not a single "before and
after".**

The first attempt compared a 99-bus network against a 55-bus baseline and reported
that waiting barely moved. Three things changed at once, so nothing could be
attributed to anything. The proof is now four cumulative rows - dispatch, then
topology, then extra buses - with the fleet held at 55 until the last one. Each row
can make things worse, and the topology row does.

**5. Stops are placed by minimising walking distance, not by maximising
coverage.** Coverage saturates: a greedy "every cell within 400 m" objective
stops placing stops after about 45 and then reports success. A p-median
objective keeps discriminating.

## Consequences

**Good**

- The project can now answer the question it kept raising — whether the network
  layout is right — and the answer is measured, not asserted.
- The negative result is genuinely useful: rebuilding the stop set buys ~2% more
  population within a 400 m walk and costs 29 minutes of journey time, because a
  finer stop set forces transfers. That corroborates `RESEARCH.md` §1.4 from the
  supply side.
- One engine serves the animation and the proof tables, so the screen and the
  report cannot disagree.
- Every lever is in `reroute_params.json`, so the whole network can be
  regenerated under different assumptions.

**Bad**

- **The loops cost waiting time.** A circuit is longer than the open route it
  replaces, so the same fleet covers it less often: +10.0 minutes of average wait
  in the ablation. The loops buy coverage and a legible topology, not speed.
- **The reroute needs 63 buses against today's 55** once the crowded stops are
  served, because circuits trade fleet for reliability.
- **R10-R12 are missing from both networks**, so a fifth of the city's bus
  departures are simply not modelled. That keeps the comparison fair but narrows it.
- OSM building data for Malé is patchy on storeys, so the population surface is a
  proxy in a way the rest of the pipeline's inputs are not.
- The reroute adds four build products and a second demand model to maintain.

## Alternatives rejected

- **Keep fleet neutrality in the reroute.** Then the network could not be sized
  to the demand it creates, and the "extra bus" deliverable would be impossible
  to answer.
- **Keep the published timetable and only redesign geometry.** That is a smaller
  change, but it makes "when is the next bus" a static lookup again and removes
  the reason the `/reroute` view exists.
- **Regenerate Malé anyway, for consistency.** Rejected on the evidence: it made
  journey times worse and bought ~2% more population within walking distance.
- **One loop for the whole island.** Rejected on geometry: 2.2 km from the hub to
  the edge makes a full lap 10 km+, slower than the open routes it replaces.
- **Add Villimalé.** No road link, no demand data, and a ferry-based denominator
  this project does not model. Including it would mean inventing demand.
- **Use the taxi OD as the population instead of buildings.** It measures where
  people take taxis, which is demand, not residence; it also has no Villimalé
  coverage and over-weights the airport road.

## How to verify

```bash
make reroute
python -c "
import pandas as pd
r = pd.read_csv('dashboard/data/reroute_stops.csv')
print(len(r), r.island.value_counts().to_dict())          # no Villimalé
s = pd.read_csv('dashboard/data/reroute_stop_advisory.csv')
print(s.extra_bus_required.value_counts().to_dict())      # the per-stop answer
"
```

`tests/test_reroute.py` pins scope, road-graph connectivity, that every stop is
served by at least one route, and that the advisory covers every stop.

## Related

- ADR-0004 (level/shape demand split), ADR-0008 (fleet neutrality — departed
  from here), ADR-0013 (realtime deferred — the simulation is not realtime),
  `docs/REROUTE.md`, `RESEARCH.md` §1.4.
