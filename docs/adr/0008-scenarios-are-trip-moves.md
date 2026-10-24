# ADR-0008 — Scenarios are explicit trip moves, not percentage factors

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `scenario_kpis.csv`, `scenario_corridor_kpis.csv`, dashboard

## Context

The first scenario implementation scaled each route-hour's trip count by a
factor: `trips *= 0.85` for donors, `*= 1.12` for receivers.

At the route-hour grain there are only **1–3 trips per hour**. `1 * 0.85`
rounds to 1. The scenario silently changed nothing while reporting a result.
This was caught by inspection, not by a test, which is exactly how a wrong
number reaches a slide.

## Decision

Express every scenario as **explicit trip additions and removals on named
route-hours**, and only on hours that were captured.

```python
# S3 - fleet-neutral reallocation
for h in [13, 14]:
    move(s3, AIRPORT, [h], -1)      # 6 trips off the airport routes
for h in [16, 17, 18]:
    move(s3, CORRIDOR, [h], +1)     # 6 onto R1/R2 in the peak
```

Each scenario is documented in `SPEC.md` §5 and repeated in the dashboard
tooltips, so a reader can reconstruct it by hand.

## Consequences

**Good**
- A scenario either moves a trip or it does not; there is no silent no-op.
- Fleet-neutrality is visible: donors and receivers are named and counted.
- The definitions are explainable in one sentence during Q&A.

**Bad**
- Scenario effects are **coarse**: a single trip is 15–60 minutes of headway on
  these routes, so "10% more service" is not expressible. Real optimisation
  needs a proper fleet-assignment model.
- S5 currently *adds* 14 trips rather than reallocating them, so it is not yet
  fleet-neutral. Making it so is Dev B's task.
- Hand-written per-hour moves do not generalise. A real tool would take a
  headway policy, not a list of hours.

## Alternatives rejected

- **Percentage factors.** Proven to no-op at this grain. Rejected.
- **A full MILP / LP fleet assignment.** Correct, but unbuildable and
  unexplainable in the time available, and the input data (only 5 routes with
  demand) does not support it.
- **Interpolate between baseline and a target.** That is what the UI slider
  does, and it is labelled as interpolation, not as a model output.

## How to verify

```bash
python -c "
import pandas as pd
k=pd.read_csv('dashboard/data/scenario_kpis.csv')
print(k[['scenario','boardings_over_capacity','trips_change']].to_string(index=False))"
```

No scenario may have `trips_change = 0` while claiming a capacity effect.

## Related

- ADR-0005 (only captured hours may be touched). `SPEC.md` §5.
