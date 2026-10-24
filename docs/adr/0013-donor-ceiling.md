# ADR-0013 — A trip move must not create a new over-capacity hour

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `dashboard/build/build_data.py`, `dashboard/build/verify_claims.py`, `tests/test_reallocator.py`

## Context

ADR-0008 made scenarios fleet-neutral: a scenario moves trips rather than
adding vehicles. The reallocator implemented that as a greedy loop — take a trip
from the lowest-loaded eligible hour, give it to the hour with the most unmet
demand, recompute, repeat.

The eligibility test was:

```python
donors = d[donor_rule(d) & (d["trips_in_hour"] > 1) & (d["_over"] == 0)]
```

`_over` is the donor's over-capacity **before** the move. That is the state that
was never the problem. Removing one bus from a three-bus hour cuts its capacity
by a third:

| Route-hour | Before | After one trip removed |
|---|---|---|
| R1 12:00 | 3 trips, 216 seats, 179.5 pax = **83.1%** | 2 trips, 144 seats = **124.7%**, 35 pax left behind |

The move manufactured the exact harm it was meant to relieve, and the log
recorded it as an improvement because `receiver_unmet_after <
receiver_unmet_before` was still true.

A second defect compounded it. Once the donor was over capacity it became an
eligible *receiver* on a later pass, so the loop handed the trip back and logged
the reversal as another success. In the committed output, S5's "18 trips moved"
contained four identical `R1 12→R2 22` / `R2 22→R1 12` pairs; S4 cycled R2
11↔21 three times while R2 22:00 sat at 123% with 33 passengers stranded and was
never given a bus.

## Decision

Two rules, both enforced in `reallocate()` and both asserted in the build.

**1. Donor ceiling.** A trip may only be taken from an hour whose load stays at
or below `DONOR_CEILING_PCT` (100% of seats) *after* losing the trip:

```python
cap_after = (donors["trips_in_hour"] - 1) * donors["seated_capacity"]
donors = donors[donors["demand_pax_est"] / cap_after <= ceiling]
```

The ceiling is a parameter, not a constant to be tuned for a better-looking
result. Raising it re-creates the defect by definition: the donor's passengers
go somewhere, and that somewhere is the stop.

**2. Reverse-move netting.** After the loop, `net_moves()` cancels any pair of
moves that exactly undo each other. The fleet state is already correct once a
pair cancels; only the *count* and the audit trail were wrong. `trips_moved` now
equals the net change, and `scenario_moves.csv` contains only moves that did
work.

A donor must also keep at least one trip (`min_trips_after=1`), so a move never
deletes a service.

## Consequences

**Good**

- Every logged move now strictly reduces the receiver's unmet demand *and*
  leaves the donor within capacity. Both are machine-checked.
- `trips_moved` is auditable: 6 means 6.
- The result is a finding, not just a fix. With the ceiling in place the
  "express peak" scenario (S4) finds exactly **one** safe move, because every
  other R1/R2 off-peak hour is already at 83–166%. **The corridor has no spare
  buses; the airport routes do.** That is F1's conclusion — the causeway is the
  problem — arrived at from the supply side.

**Bad**

- The headline numbers get smaller and less impressive. S5 moves 6 trips and
  relieves 404 boardings, not "18 trips and 534". Two of the three scenario
  terms are now near-null.

  This is the correct direction. A tool that recommends self-cancelling moves
  is worse than no tool, because the error survives into the pitch.

- The scenario set now has two weak terms (S2, S4). They are reported as
  near-null rather than dropped, so a reader can see that the model looked and
  found nothing, which is itself information.

## Alternatives rejected

- **A soft ceiling (say 120%) to keep more moves.** Rejected. It permits a
  transfer of the queue and reintroduces the original harm in a smaller dose,
  and no principled value exists between 100% and "any number".
- **Penalise the donor in the objective instead of forbidding it.** A weighted
  objective would need a weight nobody can justify on one Saturday of data, and
  a judge cannot audit a magic number. A hard constraint is explainable in one
  sentence.
- **Drop S4 entirely rather than report one move.** Rejected. Reporting that the
  corridor cannot help itself is a stronger claim than omitting the scenario.

## How to verify

```bash
make data && make check && make test
```

`make check` must pass "no move pushes its donor over capacity",
"no logged move cancels an earlier move" and "trips_moved equals the number of
logged moves". `tests/test_reallocator.py` reproduces the old behaviour at
`donor_ceiling_pct=10000` and confirms it puts a donor at 124.7%.

## Related

- Supersedes the eligibility rule in [ADR-0008](0008-scenarios-are-trip-moves.md).
- [ADR-0002](0002-reconcile-at-route-hour.md) — why the unit is route × hour.
- [ADR-0003](0003-load-factor-on-seats.md) — why the 100% is seats, not seats+standing.
