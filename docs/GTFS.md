# The GTFS feed

**`data/derived/rtl_greater_male_gtfs.zip`** — the first published GTFS feed for
the Greater Malé bus network.

GTFS (General Transit Feed Specification) is the common language for public
transport schedules. Anything that can read a GTFS feed can plan journeys on the
network without knowing anything about Maldives, MTCC, or this project.

**No public GTFS existed for Malé before this one.** We built it from the
official RTL timetable payload, so it describes the real 2026 schedule rather
than a reconstruction.

---

## 1. What is in it

| File | Rows | Content |
|---|---|---|
| `agency.txt` | 1 | Raajje Transport Link (RTL), operated by MTCC, `Indian/Maldives` |
| `routes.txt` | 11 | Bus routes, `route_type=3`, official RTL codes and colours |
| `trips.txt` | 450 | One row per scheduled journey |
| `stop_times.txt` | **5,538** | Per-stop arrival and departure times |
| `stops.txt` | 61 | Distinct official RTL stop codes, with coordinates and names |
| `calendar.txt` | 1 | Saturday, 2026-10-24 |
| `feed_info.txt` | 1 | Publisher, version, validity window |

Plus `gtfs_validation.csv` (18 structural checks) and
`gtfs_validator_report.json` (the canonical validator's own output), both
committed as evidence.

---

## 2. Why it is more than a footnote

Five reasons, in descending order of importance to anyone assessing this work.

**It is a first.** There is no other GTFS for the Maldives capital region. A
planner, a researcher or a mapping company can load this and route on it.

**It makes the network portable.** The moment a network is in GTFS, standard
journey planners work on it with no bespoke code:

- [OpenTripPlanner](https://www.opentripplanner.org/) — routing and isochrones
- [MOTIS](https://motis-project.de/) — multi-modal routing
- [Transitland](https://www.transit.land/) — feed aggregation and API
- Google Transit, Apple Maps and most trip-planning apps ingest GTFS natively

**It is independently validated.** We did not grade our own homework.
MobilityData's `gtfs-validator` 6.0.0 reports **0 errors**. The report is
committed verbatim.

**It is reproducible byte-for-byte.** Rebuilding produces an identical zip, so
the artefact in the repository is provably the artefact the build script makes.

**It is the substrate for realtime.** GTFS-Realtime does not replace GTFS — it
*extends* it, adding vehicle positions and trip updates as separate protobuf
feeds keyed to the same `trip_id`s. The feed is therefore the foundation of the
realtime phase described in [ROADMAP.md](ROADMAP.md) §3, not a dead artefact.

---

## 3. How it is built

`dashboard/build/build_gtfs.py`, directly from the official RTL 2026 payload
(`data/official/rtl/bus_routedetails_2026.json`).

The important property: the RTL payload carries **per-stop timings for each
trip**. So `stop_times` is **rounded to the observed schedule, not interpolated
from an assumed speed**. Most synthesised feeds invent intermediate times by
dividing distance by an average speed; ours does not, because it does not have
to.

```bash
make gtfs        # rebuild the feed and the 18 structural checks
make check       # assert those checks pass, alongside the rest of the project
```

---

## 4. Design decisions worth knowing

Each of these is visible in the feed rather than hidden, and each has a reason.

### One service day, stated plainly

`calendar.txt` contains Saturday 2026-10-24 and nothing else. This is not an
oversight: the RTL endpoint returns only the remainder of the service day from
the moment it is called (ADR-0005), so we captured one day and we publish one
day.

**We deliberately did not extrapolate a weekday.** We never observed one. A feed
that claimed Monday–Friday service would be more convenient and less true, and
the validator's `feed_expiration_date7_days` warning is the correct response to
an honest snapshot.

### 11 of 15 routes

R10, R11, R12 and R15 return no timings from the endpoint — they are the diesel
minibus routes, which appear in the live route list without a published
timetable. They are absent from the feed rather than invented, matching the
`NO DEMAND DATA` treatment of the same routes in the demand tables.

### 112 drop-off-only stops encoded as `pickup_type=1`

Some stops are served in one direction only. GTFS distinguishes "you cannot
board here" from "you cannot alight here", so these are encoded with
`pickup_type=1` rather than dropped. Dropping them would have shortened the
route geometry and misrepresented where the bus stops.

### 32 partially-timed trips

The payload does not give every intermediate stop a time for every trip. Those
trips ship with only the stop-times they actually have — 2 in the shortest case,
18 in the longest — rather than with interpolated times that would look precise
and be wrong.

### No `shapes.txt`, no fares yet

Both are known gaps and both are fixable:

- `shapes.txt` can be derived from `route_lines.geojson`, which already holds
  the geometry
- `fare_attributes.txt` and `fare_rules.txt` can be written from the known flat
  **10 MVR** fare

They are not in the submitted feed because the feed was built to prove the
schedule converts faithfully, and each addition needs re-validating. Listed here
so nobody assumes the omission is deliberate policy.

---

## 5. Validation

Two layers.

**Structural checks — 19, committed in `gtfs_validation.csv`.** Reference
integrity (`trip_route_fk`, `stop_time_stop_fk`), contiguity of `stop_sequence`,
non-decreasing arrival times, coordinate envelope, every stop used, zip
readable, 7 required members present. All 19 pass, and
`dashboard/build/verify_claims.py` asserts that they do — the feed's claims are
re-derived on every `make check` like every other number in this project.

**Canonical validator — MobilityData `gtfs-validator` 6.0.0.**

| | |
|---|---|
| Errors | **0** |
| Warnings | **2** |
| Feed version | `derived-20261024-from-RTL-routedetails` |

Both warnings are inherent to a one-day snapshot, not defects:

- `feed_expiration_date7_days` — the feed ends the day it starts
- `trip_coverage_not_active_for_next7_days` — same cause

Reproduce with `make validate-gtfs` (requires Java and `gtfs-validator.jar`).

---

## 6. Using it

Any GTFS consumer works. The shortest path is OpenTripPlanner:

```bash
# Build a graph from the feed plus OpenStreetMap data
java -Xmx2g -jar otp.jar --build --save \
  --gtfs data/derived/rtl_greater_male_gtfs.zip \
  --osm  greater-male.osm.pbf

# Serve it, then plan journeys in the browser at http://localhost:8080
java -Xmx2g -jar otp.jar --load --serve
```

To inspect it without any toolchain, the files are plain CSV:

```python
import pandas as pd
st = pd.read_csv("data/derived/gtfs/stop_times.txt")
st.merge(pd.read_csv("data/derived/gtfs/stops.txt"),
         on="stop_id")[["route_id", "arrival_time", "stop_name"]].head()
```

---

## 7. What we do not claim

- **It is not a production feed.** It is a validated one-day snapshot. Do not
  publish it as MTCC's official timetable; it is our derivation of theirs, and
  it carries our version string.
- **It does not cover the whole network.** 11 of 15 routes, and no minibus
  timings.
- **It is not a substitute for the operator.** Corrections belong with RTL.
- **Its times are a single Saturday.** Weekday and Friday service differ, and
  were not captured.

Full provenance and licences: [DATA_SOURCES.md](../DATA_SOURCES.md).
The decision to defer realtime: [ADR-0013](adr/0013-realtime-layer-deferred.md).
