# The reroute — today's Malé, real Hulhumalé circuits

**Raajje Rebalancer · Maldives Datathon 2026 · Team Wayfinders**

This document describes the `/reroute` tab: what the alternative network changes,
what it deliberately leaves alone, how the day is simulated, and what the four-run
ablation actually showed.

Every number here is produced by the committed pipeline. Regenerate with
`make reroute`.

---

## 1. The design, and how it got here

The first two attempts at this rebuilt the whole network from the population
surface. Both were wrong, for a reason that was measurable in advance:

- **Malé's streets are narrow and its alignment is already close to what the roads
  allow.** `RESEARCH.md` §1.4 measured that 97.1% of taxi pickups start within
  300 m of an existing stop and none beyond 800 m. There is essentially no
  coverage left to win.
- **Regenerating it forced transfers.** Journey time went from 33 minutes to 62,
  then 69. A redesigned Malé was strictly worse for the passenger.

So the design is now deliberately asymmetric, and the asymmetry is the point:

| Area | What happens | Why |
|---|---|---|
| **Malé and the airport island** | Today's routes **R1, R2, R3, R4, R7, R8, R9**, their stops, and their exact committed road-snapped geometry, copied leg for leg | Nothing to win, a lot to lose. No regeneration step exists, so there is nothing to get wrong. |
| **Hulhumalé** | **Closed circuits** over new stops in the filled-in blocks; R5 and R6 retired | The island's local routes were *open* services whose terminals are 781 m apart, so a passenger going the other way round was not served at all. |
| **R10, R11, R12** | Excluded from **both** networks | No captured departures and no ridership count. Replaying them would mean inventing a schedule, and including them on one side only would rig the comparison. |
| **Villimalé** | Out of scope | No road link, no Avas trips, ferry-dependent. ADR-0015. |

Two claims follow, and both are checked by tests:
`R1–R4` and `R7–R9` legs are **byte-identical** to `route_segments.geojson`, and no
Malé or airport stop was regenerated.

---

## 2. How the loops are built

A loop is a **cycle in the road graph**, not a tour of waypoints:

1. Route from the hub to an anchor by the shortest road path.
2. Route back to the hub by the shortest path with the outbound edges penalised
   (×20), so the return leg takes a *different street*.
3. The outbound path plus the reversed return path is a closed circuit **by
   construction** — the road graph is connected, so the return always exists.

Every island stop within 200 m of that ring is placed on it at its position along
the ring, which gives journey order directly.

**Why not visit waypoints in bearing order?** Tried and rejected: consecutive
stops in bearing order can be radially opposite, so the "loop" zig-zags across the
island. It produced 27 km of route on a 2 km island.

**The result, measured:**

| Loop | Stops | Length | Road segments driven twice |
|---|---|---|---|
| L1 | 42 | 9.82 km | 1 of 326 |
| L2 | 10 | 7.43 km | 2 of 255 |
| L3 | 7 | 2.70 km | 0 of 139 |
| L4, L5 | 3 each | ~1.5 km each | 0 |

A handful of reused segments are cul-de-sacs, which no road layout can avoid. A
retraced corridor would show up as dozens.

An earlier version spliced leftover stops into an existing loop and rebuilt that
loop's legs with a plain shortest path, which silently undid the ring. Circuits
are now only ever built by the ring constructor; nothing is spliced into one
afterwards.

---

## 3. Through-running

Cross-island routes continue past their Hulhumalé stop along the circuit nearest
it, so a trip from Malé to the island's residential blocks is a **direct ride**
rather than a ride plus a change.

Only the appended tail is generated. The Malé half is extended, never rebuilt, so
it stays byte-identical to the committed geometry.

---

## 4. A fixed fleet, allocated rather than sized per route

The network runs on **55 buses** — today's fleet. It is allocated one per route,
then by largest remainder on peak demand. The headway each route can sustain is
`cycle_time / buses`, so the fleet constrains the service *physically*: a route
cannot run faster than its buses allow.

This replaced per-route sizing, which used a "four departures an hour minimum"
that alone inflated the fleet to 99 buses against a 55-bus baseline — an unfair
comparison that flattered the reroute on frequency and hid what it actually cost.

---

## 5. The ablation: does it improve the original?

Four runs of the same day. Each row differs from the one above by **exactly one
change**, and the fleet is held at 55 until the last row.

| Row | Mean wait | 9 in 10 wait under | Journey | Buses | vs row above |
|---|---|---|---|---|---|
| **The original network** | 19.2 min | 37 min | 33 min | 55 | — |
| **+ buses sent when needed** | **15.8 min** | **32 min** | **28 min** | 55 | wait −3.4, p90 −5, journey −6 |
| **+ Hulhumalé on loops** | 25.8 min | 53 min | 40 min | 55 | wait +10.0, p90 +21, journey +12 |
| **+ the buses the crowded stops need** | 20.8 min | 40 min | 35 min | 63 | wait −4.9, p90 −13, journey −5 |

**What this says.**

1. **Dispatching from demand is the real win, and it is free.** Sending buses when
   the queue or the load calls for it — rather than on a published clock — cuts
   the average wait by 3.4 minutes and the 90th-percentile wait by 5, on the same
   55 buses, with no route change at all. Journey time falls too, because
   passengers spend less time waiting mid-trip.
2. **The loops cost.** A circuit is longer than the open route it replaces, so the
   same 55 buses cover it less often: wait rises 8.6 minutes. This is a real
   trade, and the loop's benefit is coverage and legibility, not speed.
3. **Extra buses buy most of it back.** The eight buses the crowded stops ask for
   recover 4 minutes, taking the loops variant back to roughly the original's
   service level with 8 more vehicles.

So the honest answer to "does this improve the original?" is: **the dispatch
change does, clearly; the loops alone do not; the loops plus the buses they need
are about break-even on waiting and worse on fleet.**

That is a legitimate and useful result. A tool that only reports wins is a
brochure.

---

## 6. The per-stop deliverable

`reroute_stop_advisory.csv`, one row per stop: the first bus of the day and its
route, boardings served, peak queue, peak load, and whether the stop needed an
extra bus — with the reason.

A stop is flagged when a **spare bus was dispatched** or the **peak queue reached
25**, matching the engine's own trigger. A raw queue peak is not a failure: a
queue of 30 that clears in four minutes is a well-served stop.

---

## 7. What this does not prove

1. **Not a trial.** One modelled day, on allocated demand, not observed passengers.
2. **No vehicle tracking.** Running times come from scheduled stop-to-stop times;
   they do not vary with traffic, and bunching is not modelled.
3. **Demand is inferred.** Levels are MTCC counts on five routes; the shape is taxi
   OD. ADR-0004 covers why those are not the same thing.
4. **R10–R12 are absent from both sides.** Their demand still exists in the city;
   this comparison simply does not model it.
5. **Airport arrivals are a stated share.** `AIRPORT_BUS_SHARE = 0.06`, applied
   identically to every row.
6. **The fleet is a model output**, not a procurement plan.

---

## 8. Reproducing it

```bash
make reroute        # population surface, network, headless ablation
make serve          # build the dashboard and serve it on :8000
```

Every lever is in `dashboard/data/reroute_params.json`: walk radius, loop penalty,
length caps, fleet size, airport share. Nothing is hidden in code.
