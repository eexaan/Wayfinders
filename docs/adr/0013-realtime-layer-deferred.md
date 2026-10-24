# ADR-0013 — The realtime layer is deferred, with stated entry conditions

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `docs/ROADMAP.md`, ADR-0007, the report and the pitch

## Context

The submitted tool is an offline projection: it reconciles historical demand
against a single captured service day. Two things make it not-realtime:

1. **Demand by stop is allocated, not measured.** ADR-0002 records that segment
   load factors come from distributing MTCC route totals across stops using
   Avas taxi catchments, scaled 2.7–3.4× per route. The model's most actionable
   finding — R3 at 98.4% of seats on the airport approach — is therefore the
   finding with the least direct observation behind it.
2. **Supply is a snapshot.** The RTL feed was called once, and it returns only
   the remainder of the service day from the moment of the call (ADR-0005).

Adding automated people-counting at stops (camera, IR or ultrasonic) plus a live
vehicle feed would turn the tool from a projection into realtime decision
support. The team wants that ambition recorded in the report. It was also
proposed during the build as a demo feature, and SPEC §10.4 previously advised
against building it.

## Decision

**Defer the realtime layer out of the submitted build, and record it as a
planned phase with explicit entry conditions.**

- No sensor, no streaming, no backend is added to the codebase. The submission
  stands on historical data.
- The plan is written up in `docs/ROADMAP.md`, with a sensor comparison, a
  three-stop pilot design, indicative costs, an evaluation plan and the claims
  we refuse to make.
- **This ADR supersedes ADR-0007 conditionally**: the static, no-backend
  dashboard remains correct for the submission, and is expected to be replaced
  only when the entry conditions in ROADMAP §10 are met.
- SPEC §10.4 is reframed from "do not build it as a product feature" to
  "deferred to Phase 2, with conditions". The dense-crowd accuracy caution is
  kept as an engineering constraint, not a prohibition.

The entry conditions are the substance of the decision:

1. Legal review of camera capture of passengers in public space
2. One stop instrumented and validated against manual counts (< 25% MAPE above
   10 people waiting)
3. GTFS-Realtime or equivalent vehicle-position access — **demand without
   supply position is not a control loop**
4. Operator agreement in principle that a reallocation recommendation can be
   acted on
5. Budget and an owner for the pilot, including manual calibration labour

## Consequences

**Good**
- The report can describe a realtime future without claiming the present is
  realtime. A judge cannot catch us overstating it, because the distinction is
  written down.
- The roadmap is tied to the model's own stated weakness rather than presented
  as an unrelated product idea.
- The verification work stays done: no new moving parts on the submission
  critical path.
- Naming the entry conditions makes the deferral falsifiable — anyone can check
  whether the preconditions exist.

**Bad**
- We ship no live demo, which is the more impressive thing to show.
- `docs/ROADMAP.md` contains cost figures that are indicative, not quoted.
- Two documents now describe the future state (this ADR and the roadmap), so
  they can drift. The roadmap is authoritative for detail; this ADR records only
  the decision.

## Alternatives rejected

- **Build a camera counter for the demo.** Rejected during the build: not
  reproducible, produces numbers no planner can act on, and would have consumed
  the time that went into validation. Recorded in SPEC §10.4.
- **Add a backend and live refresh now.** Rejected: the vehicle endpoints need a
  JWT that was never obtained, so the "live" layer would have been static data
  with extra failure modes.
- **Say nothing about realtime.** Rejected: it would leave the project looking
  unaware of its own limitation, and the report would lose a genuine strength.

## How to verify

```bash
# The submission contains no realtime machinery, by design.
grep -riE "websocket|gtfs-rt|eventstream|/api/stream" dashboard/ || echo "no realtime layer, as decided"
test -f docs/ROADMAP.md && echo "roadmap present"
```

## Related

- ADR-0007 — the static dashboard this conditionally supersedes
- ADR-0002 — the allocation-not-measurement limitation that motivates Phase 2a
- ADR-0005 — why supply is a snapshot
- `docs/ROADMAP.md` — the plan in full
- `docs/GTFS.md` — the feed that GTFS-Realtime extends
