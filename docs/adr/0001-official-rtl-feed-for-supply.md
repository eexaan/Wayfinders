# ADR-0001 — Supply comes from the official RTL 2026 feed, not MTCC PDF schedules

- **Status:** Accepted
- **Date:** 2026-10-24
- **Supersedes:** the original PDF-parsing approach (removed from the repo)
- **Affects:** `dashboard/build/build_data.py`, `DATA_SOURCES.md`, all findings

## Context

To model bus supply we need to know, for every route, **how many trips run and
when**. Three candidate sources existed:

| Source | Content | Problem |
|---|---|---|
| **MTCC published schedule PDFs** (`mtcc.mv/schedules-2/`) | day-group × time-window × headway, with separate Friday patterns | Only edition published is **"Ramadan 1446" (February 2025)**. Differs from the live timetable by **−28% to +113%** by route. Needs Dhivehi-aware PDF parsing. Omits R15 entirely |
| **Team Kandu `rtl_bus_departures.csv`** | per-stop timings for real trips | One **live snapshot: 19:54–23:59 on 2026-10-10**. No morning peak |
| **RTL `v2/bus/routedetails`** | full route metadata + per-stop scheduled departures | Discovered late |

The PDF route was built first and worked, but it was a 2025 Ramadan edition
being used as a 2026 service model. That is not defensible in a report.

## Decision

Use `https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails`, which is
**public and requires no authentication**, saved as
`data/official/rtl/bus_routedetails_2026.json`.

It provides, per route: `routeNumber`, `name` (official English), `dvname`
(official Dhivehi), `color`, `fare`, `isMiniBusRoute`, `depot`, start/end
station, and `busRouteStopList` with `order`, `name`, `dvname`, `code`,
`latitude`, `longitude` and **`timings`** — the scheduled departure time of
every trip at every stop.

All MTCC PDF-derived tables were deleted, along with the PDFs' role in the
model.

## Consequences

**Good**
- Current (October 2026), not an 18-month-old Ramadan edition.
- Machine-readable JSON: no PDF parsing, no Dhivehi font problems.
- Official naming, colours, fares and minibus flags come free — which is also
  what the dashboard needs for its map.
- R15 appears in the feed although MTCC's PDF index omits it.

**Bad**
- **The feed is time-filtered**: it returns each stop's departures from the
  moment of the call. Our capture was ~11:00, so the window is ~11:00–24:00
  and the morning peak is missing. Trip counts per day (max trip `order`) are
  still complete. See ADR-0005 for how that is represented.
- The feed returns **one service day**, so the Friday/weekday *service*
  comparison is no longer observable. See ADR-0009.
- Four minibus routes (R10, R11, R12, R15) return **no timings at all**.

## Alternatives rejected

- **Keep the PDFs.** Rejected: wrong vintage, and the divergence from live data
  is large enough to change conclusions.
- **Scrape the rendered RTL page.** Rejected: the page is an Angular SPA; the
  JSON behind it is the real artifact.
- **Blend PDF day-type ratios into the 2026 feed.** Tempting, and would restore
  the Friday analysis — but it reintroduces the withdrawn source. Rejected.

## How to verify

```bash
curl -sk -o /tmp/rtl.json \
  "https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails"
python -c "import json;d=json.load(open('/tmp/rtl.json'));\
print(len(d['routeResponse']),'routes');\
print([r['routeNumber'] for r in d['routeResponse']])"
```

Expect 15 routes and `capture_first_departure` values around 11:00.

## Related

- ADR-0005 (null not zero), ADR-0009 (Friday withdrawn), ADR-0010 (capacity).
- `RESEARCH.md` §2 for the discovery narrative.
