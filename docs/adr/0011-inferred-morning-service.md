# ADR-0011 — The morning is a bounded route-day inference, never hourly data

- **Status:** Accepted
- **Date:** 2026-10-24
- **Amends:** ADR-0005 (which said: no extrapolation at all)
- **Affects:** `morning_service_inferred.csv`, the report, the pitch

## Context

ADR-0001 moved supply to the RTL feed. That feed is filtered by the **server's
clock**: it returns each stop's departures from the moment of the call onwards.
Our capture ran at about 11:05 on Saturday 2026-10-24, so the morning
(06:00–11:05) is absent — and we are at a datathon, so there is no option to
re-run after midnight.

We confirmed the filter cannot be bypassed from the client:

| Attempt | Result |
|---|---|
| `?date=`, `?serviceDate=`, `?tripDate=`, `?fromDate=` and 14 other param names | All ignored — identical payload |
| `Date:` request header set to 00:05 | Ignored |
| `X-Request-Time`, `Time-Zone`, `X-Forwarded-Host` | Ignored |
| Two calls 1 second apart | Payload **shrank** 368,988 → 356,890 bytes, purely from elapsed time |

The payload shrinking over time proves the decision is made server-side against
a clock we do not control.

ADR-0005 therefore left the morning as `null` and stated no extrapolation. That
is still correct for *hourly* data. But it left the team unable to say anything
about the morning at all, which is too strict: two official facts let us bound
it without inventing a single departure time.

## Decision

Derive a **route-day** morning statistic, and emit it in a **separate file** so
it can never be read as hourly observations.

For each route:

```
trips_before_capture = trips_per_day - trips_captured        # both official
morning_span         = capture_first_departure - 06:00       # assumed start
morning_avg_headway  = morning_span / trips_before_capture
```

- `trips_before_capture` is **exact**: `trips_per_day` is the maximum trip
  `order` (the complete daily count) and `trips_captured` is a plain count.
- The headway is a **bounded average**, reported for a 05:30 / 06:00 / 06:30
  service start, not a series.
- Output: `dashboard/data/morning_service_inferred.csv`, with `status =
  "INFERRED - not observed"` and the method spelled out in every row.
- The hourly table (`demand_supply_gap.csv`) is **unchanged**: morning hours
  remain `null`. Nothing inferred ever enters an hourly chart or a KPI.

## Why 06:00 is defensible

It is an assumption, so it is tested rather than asserted. Two routes have a
high-frequency all-day pattern that is observable in the captured window:

| Route | Observed headway (captured) | Inferred morning headway |
|---|---|---|
| R13 | 10 min | **10.7 min** |
| R14 | 10 min | **11.1 min** |

Two independent routes reproduce the known value. If the 06:00 anchor were
badly wrong, these would not land on 10. They do, so the anchor holds for the
high-frequency routes and can be read across.

Sanity of the others: R3 infers 48.6 min against a known 60-min daytime
headway (a denser morning, consistent with demand), and R6 infers 13.1 min
against a 75-trip day.

## Consequences

**Good**
- The team can say something true about the morning with a stated assumption
  and a computed error band.
- The cross-check on R13/R14 turns an assumption into a supported one.
- It answers the question a judge will ask: "what about the morning peak?"
- The morning does not affect the headline anyway — `trips_per_day` is the
  complete daily count, so R1's 104.4% of seats is already a full-day figure.

**Bad**
- **It is an average, not a distribution.** It cannot tell you the 08:00
  headway, which is the number a scheduler wants.
- It assumes a uniform headway across the whole morning. If the real morning
  has a dense 07:00–09:00 block and a sparse 06:00–07:00, the average hides
  both.
- It depends on a 06:00 start. A 05:30 or 06:30 start moves every figure by
  about ±8%, which is why the band is published.
- It must never appear as a bar on an hourly chart. If it does, ADR-0005 has
  been violated in spirit.

## How to replace it with real data

Run `dashboard/build/build_data.py` shortly after midnight, when the feed's
"from now" window is the whole service day. The hourly table fills in and
`morning_service_inferred.csv` becomes redundant. Then supersede this ADR.

Or ask MTCC for the published timetable PDF — but confirm the edition, because
the only one available online is Ramadan 1446 (see ADR-0001).

## How to verify

```bash
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/morning_service_inferred.csv')
print(d[['route_code','trips_per_day','trips_captured',
         'trips_before_capture','morning_avg_headway_min',
         'morning_avg_headway_min_low','morning_avg_headway_min_high']].to_string(index=False))"
```

R13 and R14 must read close to their observed 10-minute headway.

## Related

- ADR-0001 (the filter), ADR-0005 (nulls in the hourly table), ADR-0003 (the
  full-day load factor that the morning does not affect).
