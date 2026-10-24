# ADR-0004 — MTCC anchors the demand level; Avas supplies the shape

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `demand_supply_gap.csv`, `route_load.csv`, all load factors

## Context

Two independent measures of how many people want to travel:

| Source | What it measures | Grain | Coverage |
|---|---|---|---|
| **MTCC bus ridership** | people actually on the bus | route × day / month | 5 routes only |
| **Avas taxi rides** | people who chose a taxi instead | OD × timestamp | all of Greater Malé, 61 days |

Neither alone is enough. MTCC is ground truth for the bus but covers 5 of 15
routes and has no hour-of-day signal. Avas has full spatial and temporal
resolution but records a *different mode*.

The tempting shortcut — "use taxi demand as bus demand" — would let us fill all
15 routes and all 24 hours. It would also be wrong: taxi riders are a
self-selected minority who paid 8.5× the bus fare.

## Decision

**Two-layer demand model:**

1. **Level** from MTCC observed boardings, per route per day-type. This is the
   number that appears in every load factor.
2. **Shape** from Avas, as the hourly profile of the route's corridor, used
   only to distribute that level across the 24 hours.

Where MTCC has no ridership (10 routes), **no demand is emitted**. The route
shows `NO DEMAND DATA` rather than a taxi-derived estimate.

## Consequences

**Good**
- Every absolute number traces to an observed bus count.
- Taxi data earns its place as *revealed preference about timing*, which is
  exactly what MTCC cannot tell us — and it is what makes the peak visible.
- The 10 undocumented routes stay visibly undocumented, which is itself a
  finding MBS asked for.

**Bad**
- **The hourly shape is borrowed from a different mode.** If taxi demand peaks
  differently from bus demand on a corridor, the hourly load factors inherit
  that error. We do not correct for it and cannot with the data available. It
  is flagged in `demand_source` on every row.
- Ten routes have no hourly demand at all, so the gap table is thinner than it
  looks.
- Friday taxi demand falls much less than Friday bus demand (Avas −5%, MTCC
  −37%), which is direct evidence the two shapes differ. That is a caution, not
  a refutation, but it should be stated in the report.

## Alternatives rejected

- **Taxi demand as the level, scaled by a mode share.** Requires assuming the
  mode share, which is the thing we are trying to measure.
- **Population-based demand generation from Census 2022.** Would cover all 15
  routes, but produces a travel-demand model on top of a survey, and we have
  no calibration target for the 10 undocumented routes.
- **MTCC only, no Avas.** Loses the peak entirely; the whole "when" question
  disappears.

## How to verify

Every row of `demand_supply_gap.csv` carries
`demand_source = "MTCC observed (level) x Avas shape (modelled)"` or
`NO DEMAND DATA`. There is no third value, and no row where the level is
sourced from Avas.

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/demand_supply_gap.csv')
print(d.demand_source.value_counts())"
```

## Related

- ADR-0002 (grain), ADR-0005 (nulls), ADR-0006 (the airport equivalent).
  `RESEARCH.md` §4, §5.
