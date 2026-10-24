# ADR-0003 — Load factor is reported on seats, with seats+standing as secondary

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `route_load.csv`, F2, the dashboard, the report headline

## Context

The team's capacity table (`data/raw/mtcc_bus_capacity.csv`) gives **two**
numbers per route, and they are not interchangeable:

| Route | Model | Seated | Max (seats + permitted standing) |
|---|---|---|---|
| R1, R2, R7, R8 | Yutong ZK6116HGS double decker | **72** | **84** |
| R3, R4, R9 | Yutong ZK6122H9 coach | 55 | 55 (no standing) |
| R5, R6 | Yutong ZK6126HGA single decker | 33 | *not stated* |
| R10, R11, R12, R15 | Yutong ZK6729D2 diesel minibus | 24 | 24 |
| R13, R14 | Yutong E6S electric minibus | 11 | 15 |

R1's daily boardings are 4,585 against 61 trips. That is:

- **104.4% of seats** (4,585 ÷ (61 × 72))
- **89.5% of total capacity** (4,585 ÷ (61 × 84))

Same ridership, two very different sentences.

## Decision

**Lead with the seats figure.**

`load_factor_seats_upper_pct` is the primary metric. `load_factor_capacity_*`
is carried alongside as a secondary column and referenced in captions, never
as the headline.

Both are upper bounds: they assume every boarding rides the full route.
`*_avg_pct` halves the numerator to represent uniform alighting, and is the
lower bound. The band between them is the honest depiction (ADR-0002
consequences).

Where `load_factor_comparable` is `FALSE` (R5, R6 — seats given, standing not
stated), **no load factor is emitted**. The field is null and the
`demand_source` string says why.

## Rationale

> "R1 is at 104% of its seats" means people are standing, or waiting for the
> next bus.
>
> "R1 is at 89.5% of capacity" sounds like there is room.

The problem statement says commuters are left waiting while other buses run
under capacity. The seats figure is the one that speaks to that. Reporting
89.5% would be arithmetically true and rhetorically misleading.

Seats are also the more solid number: they are a manufacturer specification,
whereas permitted standing is an operator policy that varies and was not
stated for two routes.

## Consequences

**Good**
- The headline matches the problem being solved.
- Honest: a value over 100% is visibly a capacity problem, not a rounding error.
- The two-denominator table makes the assumption legible instead of hiding it.

**Bad**
- **Two load-factor numbers per route invites confusion.** Mitigation: every
  output row carries both, and the dashboard spec requires the band to be
  rendered, never a single value.
- 104% reads as impossible to some readers. It is not: it means daily
  boardings exceed daily seat supply, which happens when people stand or when
  a passenger is counted on more than one trip. Say so in the caption.
- R5/R6 drop out of the comparison entirely, which thins the chart from 5
  routes to 4. Correct, but note the count in the caption.

## Alternatives rejected

- **Use max passengers (seats+standing) throughout.** Defensible as "physical
  capacity" and more forgiving, but it hides the problem.
- **Report both as equal peers.** Rejected: with no stated priority, the
  reader picks whichever suits them, and a judge will ask which one is "the"
  number.
- **Use 84 seats as originally assumed.** That was simply wrong — 84 is
  seats *plus standing*.

## How to verify

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/route_load.csv')
print(d[['route_code','seated_capacity','max_passengers',
         'load_factor_seats_upper_pct','load_factor_capacity_upper_pct',
         'load_factor_comparable']].to_string(index=False))"
```

R1 must read 72 / 84 / 104.4 / 89.5 / True.

## Related

- ADR-0010 (where the capacity numbers come from), ADR-0002 (the band).
  `SPEC.md` §7.
