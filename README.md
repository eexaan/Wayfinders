# Raajje Rebalancer

**A data-driven bus supply decision tool for Greater Malé.**
Maldives Datathon 2026 · Team Wayfinders

> *Raajje* is the Maldivian name for the Hulhumalé causeway — the bottleneck
> under every number in this repository.

---

## What this is

Public transport data for Greater Malé is fragmented: the bus ridership
series covers 3 routes daily and 5 monthly, the only complete timetable is
published as scanned PDFs, the live departure feed is a single evening
snapshot, and the airport dataset covers 36% of the traffic it appears to.
**Nobody can answer "how many passengers does this route carry, at which
hour, and is that matched to the buses running?"**

This repository joins them and turns the answer into decisions.

| Document | What it is |
|---|---|
| **[SPEC.md](SPEC.md)** | The build plan: architecture, findings, scenarios, dashboard spec, team roles, timeline, risks, pitch |
| **[RESEARCH.md](RESEARCH.md)** | The full research log — what was tested, what was rejected and why, with every number reproducible |
| **[DATA_SOURCES.md](DATA_SOURCES.md)** | Every dataset with a direct link, publisher, use, licence, and caveats |

---

## The three findings

**1. The causeway is the journey time.** R1's 70-minute end-to-end run
spends **40 minutes (57%) in two causeway crossings**; every stop-to-stop
segment is a uniform 2 minutes. Internal Hulhumalé routes run 3–5 min per
segment. A taxi does the same trip in 12.7 minutes. The bus is **4.4×
slower than a taxi** and 8.5× cheaper — which is why people take taxis.

**2. One corridor is over capacity; the airport buses are not.** Weekday
peak load factor: **R1 at 102%** of an 84-seat double-decker, against
**58% on R4** (the airport bus), which also has the *worst* headway.
Meanwhile Friday demand falls 37% but Friday service falls only 9–22%, and
the airport buses run a flat 30-minute headway all day while 35% of
international arrivals land in a three-hour window.

**3. The bus already wins on price and loses on time.** On fare alone,
62–76% of taxi riders on every corridor would take the bus. On generalised
cost (VOT 250 MVR/h, taxis shared by two), only 0.05–9.3% would switch.
**A fare discount is the wrong instrument** — it discounts the dimension
where the bus already wins. The break-even table shows which corridors express
service can fix (16–20 min to shed) and which needs the causeway solved
(54 min).

---

## The tool

A reconciled demand–supply dataset (route × day-type × hour, every row
labelled *observed* / *derived* / *modelled*) feeding a scenario engine that
recomputes passenger-level KPIs for six named schedule changes, wrapped in an
interactive GIS dashboard.

```
S0 baseline            1,715 boardings over capacity   8.00% unmet   371 trips/day
S5 recommended package    1,515                        7.07%          397 trips/day
```

Every change in S5 is a **re-timing**, not a new bus.

---

## Repository layout

```
SPEC.md                     project spec: findings, architecture, roles, timeline, pitch
RESEARCH.md                 research log: what was tested, what was rejected and why
DATA_SOURCES.md             every source, with links, publisher and licence
docs/
  DASHBOARD_SPEC.md         build contract for the dashboard team
  figures/F1..F6.png        the six report figures
dashboard/
  data/                     the tables the dashboard reads (see DASHBOARD_SPEC §2)
```

## Where the numbers come from

Every figure in `SPEC.md` and `RESEARCH.md` is inlined as a table in those
documents, so both can be checked by hand. The underlying derived tables are
in `dashboard/data/`, and the public sources they were built from are listed
with direct links in [DATA_SOURCES.md](DATA_SOURCES.md).

The MTCC schedule PDFs and the RTL route map are the only inputs that are not
part of the datathon dataset release; both are public.

## Credits

- **Maldives Bureau of Statistics** — MACL, Avas Ride, MTCC datasets; Statistical
  Yearbook tables 3.30, 10.12, 11.3, 11.13, 11.18
- **MTCC plc** — published bus schedules and route maps
- **RTL (Raajje Transport Link)** — public route map CMS
- **Team Kandu** — team-shared extract (bus routes/stops/departures, yearbook
  observations)
- **OpenStreetMap** contributors — basemap and road network (ODbL)

All data is public. No private or restricted sources were used.
