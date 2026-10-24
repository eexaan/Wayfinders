# ADR-0010 — Capacity comes from the team capacity table, not the news article

- **Status:** Accepted
- **Date:** 2026-10-24
- **Supersedes:** the hardcoded `FLEET` dict in `build_data.py`
- **Affects:** `routes_master.csv`, `route_load.csv`, every load factor

## Context

Capacity is the denominator of the project's headline metric, so its provenance
matters more than any other input.

Three generations of the number existed:

1. **Assumed**, from a news article (`psmnews.mv/en/106008`): "double decker
   84, airport bus 50–54, regular 54, minibus 20–22, e-minibus 11". Written
   into a hardcoded dict. Four routes were marked `ASSUMED`.
2. **Corrected** by the team in `data/raw/mtcc_bus_capacity.csv` (merged as
   PR #2), with model, seated capacity, wheelchair bays, max passengers,
   `capacity_basis`, `confidence` and `load_factor_comparable` per route.
3. The article's "84" turned out to be **seats + standing**, not seats.

## Decision

`build_data.py` reads `data/raw/mtcc_bus_capacity.csv`. The hardcoded dict is
deleted.

Every downstream table carries the provenance: `capacity_source`,
`seated_capacity`, `max_passengers`, `load_factor_comparable`, `bus_model`.
A route missing from the table is marked `NOT IN CAPACITY TABLE` rather than
given a default.

## Consequences

**Good**
- The denominator is a reviewed artifact with per-row sourcing, not a constant
  in code.
- Two previously-assumed values are now real: R3 was 52, is 55; R5 was a
  "regular bus, 54", is a single decker with 33 seats.
- `load_factor_comparable = FALSE` lets R5/R6 be excluded honestly instead of
  producing a meaningless ratio.
- Load factors moved materially: R1 89.5% → **104.4%** of seats; unmet demand in
  the captured window 3.68% → **8.62%**.

**Bad**
- Capacity is still a **fleet-class assumption**, not a per-departure record.
  The file says so itself. If a route mixes vehicle types on different trips,
  the load factor is wrong in both directions.
- R5/R6 now have no load factor at all, which thins the comparison.
- A second CSV to keep in sync. Mitigated: it is the single source, and the
  build fails loudly (route marked missing) if it drifts.

## Alternatives rejected

- **Keep the hardcoded dict.** Wrong, unsourced, and four `ASSUMED` values.
- **Scrape the news article.** Behind Cloudflare, could not be read
  programmatically, and it conflates seats with capacity.
- **Use MBS Yearbook 11.3 (registered buses, national).** National totals
  (222 buses in 2023), not per-route capacity. No.

## How to verify

```bash
python -c "
import pandas as pd
c=pd.read_csv('data/raw/mtcc_bus_capacity.csv')
print(c[['route_number','bus_model','seated_capacity','max_passengers',
         'load_factor_comparable']].to_string(index=False))"
```

`dashboard/build/build_data.py` must contain no hardcoded seat numbers.

## Related

- ADR-0003 (which denominator is the headline).
