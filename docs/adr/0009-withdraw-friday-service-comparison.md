# ADR-0009 — The Friday service-vs-demand finding is withdrawn

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** the report, the pitch, `demand_by_daytype.csv`

## Context

An earlier draft of `SPEC.md` and `RESEARCH.md` carried this finding:

> Friday demand falls 37%, but Friday service falls only 9–22%, so Friday buses
> run emptier. On R2 the schedule runs 91% of weekday service on a Friday it
> loses 36% of its riders.

Both halves were true *of their sources*: demand from MTCC 2025, service from
the MTCC "Ramadan 1446" PDF, which published separate Friday patterns.

Then ADR-0001 replaced the PDF schedules with the RTL 2026 feed. That feed
returns **one service day** (the day of the call), so the Friday service
pattern is no longer observable from our supply source.

The comparison now has a demand side with no matching service side.

## Decision

**Withdraw the service-side claim. Keep the demand-side fact.**

- Kept: Friday bus demand is 61–64% of a weekday's on R1, R2, R4 and R7
  (MTCC 2025). Published as `demand_by_daytype.csv`, explicitly labelled
  *demand only*.
- Removed: any statement about Friday *service*, and the F3 chart that showed
  both series. It is replaced by a demand-only chart.
- `friday_responsiveness.csv` and `route_daytype_headline.csv` are deleted.
- The scenario `S1_friday_right_sized` is removed from the engine and the UI.

## Consequences

**Good**
- Nothing in the deliverable rests on a superseded source.
- The project gains a concrete, named data gap and a one-command fix
  (`build_data.py` on a Friday), which is more useful to MBS than a finding
  built on a stale PDF.
- It demonstrates that the team withdraws claims when evidence changes, which
  is the behaviour a statistical jury rewards.

**Bad**
- **A memorable finding is lost from the pitch.** The "R2 runs 91% of weekday
  service on a Friday it loses a third of its riders" line was strong. It must
  not be used.
- The story is now less balanced: we can show demand varies and service is
  flat *within* a day, but not *across* days.
- Anyone reading an earlier draft will ask where it went. Answer: ADR-0009.

## If someone restores it

Only with a Friday capture of the RTL feed (call `build_data.py` on a Friday),
which returns that day's departures. Then the comparison is legitimate again —
and this ADR should be superseded, not edited.

## Alternatives rejected

- **Keep the PDF-derived Friday pattern for this one question.** That is
  exactly the "blend a withdrawn source back in" option rejected in ADR-0001.
- **Drop day-type analysis entirely.** The demand-side variation is real and
  observed; only the service side is missing.

## Related

- ADR-0001 (the cause), ADR-0004 (demand levels). `SPEC.md` §4 F3.
