# ADR-0005 — Uncapped hours are `null`, never `0`

- **Status:** Accepted
- **Date:** 2026-10-24
- **Affects:** `demand_supply_gap.csv`, `route_service_by_hour.csv`, dashboard

## Context

The RTL feed is time-filtered (ADR-0001). Our capture ran at about 11:00 on
Saturday 2026-10-24, so `timings` return only departures **from 11:00 onwards**.
For R1 the origin stop returns trip orders 22–61, times 11:20–23:30. Trips 1–21
(the morning) exist — the max `order` of 61 is the official daily total — but
their departure times were not returned.

So for each route-hour before ~11:00 we have three choices:

1. `0` trips
2. `null` trips
3. an inferred trip count

## Decision

**`null`, with an explicit `capture_status` column.**

```csv
route_code,hour,trips_in_hour,capture_status,seated_capacity,seated_capacity_hour,demand_pax_est,...
R1,0,,before_capture_window,72,,126.5,...
R1,11,2.0,captured,72,144.0,165.2,...
```

- `trips_in_hour = null` and `capture_status = "before_capture_window"` means
  **we did not observe it**.
- `trips_in_hour = 0` would mean **no bus runs**, which is false.
- `seated_capacity_hour`, `load_factor_pct` and `unmet_pax_est` are all `null`
  wherever the trip count is null, so no downstream calculation can silently
  treat a gap as zero capacity.
- `demand_pax_est` **is** populated for all 24 hours, because demand is modelled
  from the Avas shape and is not affected by the capture. This is deliberate:
  it lets the dashboard show 24 hours of demand against 13 hours of service,
  which is the clearest possible depiction of the gap.

No inference of the missing morning times. Extrapolating backwards from the
11:20 headway gives an implausible 04:20 service start, which proves the
morning has a different headway structure — so any extrapolation would be
invented.

## Consequences

**Good**
- The gap is visible and unmistakable instead of hidden behind zeros.
- No KPI can accidentally include an unobserved hour: every aggregation drops
  nulls explicitly.
- Re-running the build after midnight closes the gap with **no code change**,
  because the nulls are data, not structure.

**Bad**
- **The morning peak — the most important window for "more buses when demand is
  high" — is missing from the model.** Everything quantitative here is an
  afternoon/evening result. Say so in the report.
- Every consumer of the table must handle nulls. That is why the dashboard spec
  has a dedicated trap for it (spec §2.16 trap 1) and an acceptance criterion.
- The charts will look odd to someone who does not read the caption. Hence the
  requirement that the captured window is stated on screen.

## Alternatives rejected

- **`0`.** Produces a clean-looking chart that asserts something false.
  Rejected outright.
- **Back-extrapolate the morning.** Fabricates times and is demonstrably wrong
  at the boundary. Rejected.
- **Trim all rows to the captured window (13 hours).** Removes the nulls but
  also hides that hours exist — and it breaks the "24h demand vs 13h service"
  comparison, which is the strongest visual we have.

## How to verify

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/demand_supply_gap.csv')
print(d.capture_status.value_counts())
print('null trips:', d.trips_in_hour.isna().sum())
print('zero trips:', (d.trips_in_hour==0).sum())   # must be 0
print('demand present where trips null:',
      d[d.trips_in_hour.isna()].demand_pax_est.notna().all())"
```

## Related

- ADR-0001 (why the feed is filtered). `docs/DASHBOARD_SPEC.md` §2.4, §2.16.
