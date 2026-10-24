# ADR-0012 — Working hours are assumed 08:00–16:00, and the answer is shown as a band

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `usage_by_period.csv`, `working_hours_sensitivity.csv`, F7, report

## Context

The brief asks how bus usage splits by working hours. There is no published
dataset of working hours, shift patterns, or live workforce for the Maldives,
and the datathon rules do not allow requesting restricted data.

What we do have, from the team's own upload
(`data/official/mbs/LFS-Report-2024-2025.pdf`):

> **Labour Force Survey, Malé 2024–2025** — fieldwork over "four wards of
> Male', Hulhumale', and Vilimale'", released 1 May 2026.
>
> Working-age population (15+) **188,062** · labour force **144,328** ·
> **employed 141,039** · unemployed 3,289 · outside labour force 43,734.

The LFS covers **exactly our study area** and gives an employed-population
denominator, but it contains **no usual-hours-of-work variable** (the only
hours reference is the underemployment definition, "<30 hours per week").

## Decision

**Assume a 08:00–16:00 working window**, state it as an assumption wherever it
appears, and publish a sensitivity band rather than a single answer.

Defined day periods, non-overlapping so they sum to the day:

| Period | Hours |
|---|---|
| `night` | 00:00–05:59 |
| `am_commute` | 06:00–07:59 |
| **`working_hours`** | **08:00–15:59** |
| `pm_commute` | 16:00–18:59 |
| `evening` | 19:00–21:59 |
| `late` | 22:00–23:59 |

Results (`usage_by_period.csv`):

| Period | Share of daily bus boardings |
|---|---|
| night | 7% |
| am_commute | 7% |
| **working_hours** | **39%** |
| pm_commute | 21% |
| evening | 18% |
| late | 9% |

Sensitivity (`working_hours_sensitivity.csv`):

| Window | Share of demand |
|---|---|
| 07:00–15:00 | 37% |
| **08:00–16:00** | **39%** |
| 09:00–17:00 | 42% |
| 07:00–17:00 | 51% |
| 08:00–18:00 | 53% |

Moving the window by an hour moves the answer by **±3 points**. Widening it to
include the evening commute takes it past half the day. That is the honest
range, and it is why the band is published rather than the point estimate.

## Consequences

**Good**
- The 39% figure is stable under a reasonable range of working-hours
  definitions, so the conclusion ("the working day is not where most bus
  usage happens") survives even if 08:00–16:00 is wrong.
- The LFS gives a study-area-specific employed population (141,039) instead of
  a national figure, and it is citable to a table.
- 21% of demand sits in the 16:00–19:00 commute alone — a single three-hour
  block — which is more than half the entire working day's share. That is a
  scheduling argument that does not depend on the assumption at all.

**Bad**
- **08:00–16:00 is invented.** Maldives working patterns include shift work,
  tourism and hospitality hours, and government hours that may not be
  08:00–16:00. Nothing in our data tests it.
- **The service side of the working-hours comparison is only partly observed.**
  The capture window starts ~11:00, so 3 of the 8 working hours have demand but
  no service data. `usage_by_period.hours_captured` exposes this: 53 of 120
  route-hours in the working window are captured. Demand shares are complete;
  load factors inside working hours are not.
- Comparing boardings to 141,039 employed people would imply a commuting rate,
  but our demand data covers only 5 of 15 routes. **Do not compute a mode share
  this way.** It is cited as context only.

## If a better source appears

MBS publishes labour force data annually. If a usual-hours or shift-pattern
variable becomes available, replace `WORKING_HOURS_START/_END` in
`build_data.py` with the observed distribution and supersede this ADR. The
period table and the sensitivity output are already parameterised for it.

## How to verify

```bash
python -c "
import pandas as pd
u=pd.read_csv('dashboard/data/usage_by_period.csv')
print(u[u.route_code=='ALL'][['period','boardings_est',
      'share_of_route_demand_pct','hours_captured','hours_in_period']].to_string(index=False))
print(pd.read_csv('dashboard/data/working_hours_sensitivity.csv').to_string(index=False))"
```

## Related

- ADR-0004 (demand shape comes from Avas, so period shares are modelled).
- ADR-0005 (the capture window, which limits the service side).
- `data/official/mbs/LFS-Report-2024-2025.pdf`, Table 1.
