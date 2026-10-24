# ADR-0002 — Reconcile demand and supply at route × hour

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `demand_supply_gap.csv`, `dashboard/build/build_data.py`, dashboard

## Context

Every source is at a different grain:

| Source | Native grain |
|---|---|
| MTCC `bus_daily` | route × calendar day |
| MTCC `bus_monthly` | route × month |
| RTL timetable | route × stop × trip |
| Avas rides | individual trip, with timestamp and coordinates |
| MACL | individual flight, with arrival time |

To compare demand against supply, both must sit on the same grid. Options were
the stop level, the trip level, or the hour.

## Decision

**Route × hour**, with 24 rows per route `demand_supply_gap.csv` (15 routes ×
24 = 360 rows).

Why:
- **Stop level** cannot be supported: only 5 routes have ridership at all, and
  nothing gives per-stop boardings. It would be modelled twice over.
- **Trip level** is exact but produces 430+ rows for 5 routes and is too
  granular to read on a dashboard.
- **Hour** matches the finest *observed* temporal signal (Avas, MACL) and the
  finest *published* supply signal (the timetable), and it is what a planner
  reasons in ("the 16:00 peak").

Every row carries `capture_status` and `demand_source` so the reader can see
whether it is observed, modelled, or absent.

## Consequences

**Good**
- Demand and capacity are directly comparable, and the comparison is legible.
- Hour resolution preserves the peak, which is the whole point.
- One row per route-hour is a clean contract for the frontend.

**Bad**
- **Route level is not the same as how full a bus is at a given point.**
  A route carrying 104% of its seats over a day may have a peak segment far
  above that, and a quiet segment far below. The hourly route series cannot
  show that. The fix is stop-level allocation, which is Dev B's task.
- Hourly capacity assumes departures are spread evenly within the hour. With
  1–3 trips per route-hour, "capacity per hour" is coarse. It is honest as a
  ratio but it is not a queueing model.
- Ten routes have no ridership, so the table is 5 routes of substance and 10
  of nulls.

## Alternatives rejected

- **Stop × hour.** Highest fidelity, but the demand would be invented at the
  stop level and then presented as if measured. Rejected as over-claiming.
- **Day × route only.** Loses the peak, which is the finding. Rejected.
- **Trip level.** Correct but unreadable, and no demand data exists at that
  grain either. Rejected.

## How to verify

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/demand_supply_gap.csv')
print(d.shape)                              # (360, 10)
print(d.groupby('route_code').size().unique())   # [24]
print(d.capture_status.value_counts())"
```

## Related

- ADR-0004 (level vs shape), ADR-0005 (nulls). `SPEC.md` §3.
