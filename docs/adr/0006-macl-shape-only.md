# ADR-0006 — MACL gives the arrival shape only; levels come from MBS 11.13

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `airport_demand_profile.csv`, F4, the report

## Context

The datathon provides a MACL airport dataset (168,959 movements, 2012–2026).
We wanted airport demand to size the airport bus routes R3/R4/R9.

Cross-checking MACL against MBS Statistical Yearbook table 11.13 exposed a
coverage problem:

| 2025 measure | MACL | MBS Yearbook 11.13 | MACL covers |
|---|---|---|---|
| International arriving passengers | 984,629 (adults) | 2,699,225 (all) | **≈ 40%** |
| International aircraft movements | 6,396 (17.5/day) | ~95/day | **≈ 18%** |
| Domestic arriving passengers | — | 1,455,156 (3,987/day) | **0%** |

Four tests established that **MACL contains no domestic flights at all**:

1. `region` has no "Domestic" value.
2. `aircraft_category == Turboprop` rows are 40–50 pax, 8–12 h block times,
   region South Asia — regional turboprops to Dhaka/Kolkata/Colombo, not
   Twin-Otter island hops.
3. Low-pax flights (arr ≤ 20) are widebodies with 0–16 arriving but 186–223
   departing at 22:00–23:59 — empty repositioning legs.
4. 17.5 movements/day is far below Malé's real volume.

## Decision

- **Levels** (how many people arrive) from **MBS Yearbook 11.13**, which splits
  domestic and international monthly: 3,987 domestic and 7,395 international
  arrivals per day in 2025.
- **Shape** (which hour they arrive) from **MACL**, which is the only source
  with `ata` per flight, over 2019–2025 and 4.89M arrivals.
- MACL is **never** used to state a level.

The coverage gap is published as a finding, not buried as a caveat.

## Consequences

**Good**
- Airport demand is not understated by 2.7×.
- Domestic traffic — which dominates the Domestic Terminal taxi drop-offs — is
  included for the first time.
- Turning the dataset's weakness into a documented finding is exactly the
  "strengthen transport statistics" contribution MBS asked for.

**Bad**
- MACL's hourly shape is derived from a 40% sample of international traffic.
  If that sample is biased by carrier or region, the shape inherits it. We
  cannot test this with the data available.
- The domestic arrival *hourly* shape is unknown — we assume it follows the
  international shape. Stated in the report.
- Two sources for one number invites the question "which is right?" The answer
  is printed: 11.13 for levels, MACL for shape.

## A trap this avoids

11,381 people arrive at Malé airport per day, but the airport bus routes carry
only about 1,850 boardings/day and Avas records ~349 taxi drop-offs at the
terminal. That looks like the bus is failing. It is not: most arrivals are
Maldivian residents connecting onward to other islands. **Raw arrivals are not
bus demand.** Do not divide one by the other in the report.

## How to verify

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/airport_demand_profile.csv')
print(d[['hour','macl_share_pct']].head(3).to_string(index=False))
print('domestic/day', d.mbs_yeardomestic_arrivals_per_day.iloc[0])
print('intl/day',     d.mbs_yearintl_arrivals_per_day.iloc[0])
print('MACL coverage %', d.macl_coverage_of_intl_pct.iloc[0])"
```

Local copy of the source: `data/official/mbs/11.13.xlsx`.

## Related

- ADR-0004 (the same level/shape discipline applied to bus demand).
  `RESEARCH.md` §4.3.
