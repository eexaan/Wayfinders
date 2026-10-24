# Raajje Rebalancer

**Matching bus supply to passenger demand in Greater Malé.**
Maldives Datathon 2026 · Team Wayfinders

*Raajje* is the Maldivian name for the Hulhumalé causeway — the bottleneck
under most of what follows.

---

## The problem

Greater Malé is small — Malé is about four kilometres long — but it is densely
populated, and the buses linking Malé, Hulhumalé and the airport carry tens of
thousands of people a day.

The complaint is familiar: **some buses arrive full and leave people waiting,
while others run half empty.** A taxi from Malé to Hulhumalé costs **85
rufiyaa**; the bus costs **10**. Yet people take the taxi.

There has been no straightforward way to check whether the service matches the
demand, because no single dataset holds both. The passenger counts cover a
handful of routes and no times of day. The timetable is published as a PDF. The
taxi records describe a different mode entirely.

## What we did

We brought five public datasets together for the first time — bus passenger
counts, the official bus timetable, taxi trip records, airport arrivals, and the
national statistical yearbook — into one picture of **who travels where, when,
and on how many buses**.

We then built a tool that lets a planner move buses between routes and hours and
see what happens to passengers.

We also tested the result against measured ridership rather than asserting it.

## What we found

**1. The causeway is the journey.** The bus from Malé to Hulhumalé Phase 1 is
scheduled at 70 minutes. **Forty of those minutes — 57% — are two crossings of
the causeway.** A taxi covers the same trip in about 13 minutes. The bus is four
times slower and eight times cheaper. People are not buying speed; they are
paying to avoid an hour in a queue.

**2. The airport bus is full, and it runs once an hour.** Route R3 from Malé to
the airport looks lightly used over a whole day — 68% of its seats. But on the
final segment into the airport it reaches **98% of capacity**, and that bus runs
**once an hour, a 30-minute expected wait.**

The average hid the crush. **The airport service does not need fewer buses; it
needs more.**

**3. The busiest corridor is near capacity, not over it.** Route R1 between Malé
and Hulhumalé Phase 1 carries 4,585 passengers a day against 4,392 seats. That
ratio — 104% — assumes every passenger rides the whole route, which nobody does.
At its busiest single segment R1 is **90% full**, and at its busiest demand hour
**82%**. It is close to capacity, and it degrades in the late evening when
service thins.

**4. Most bus use happens outside the working day.** Assuming an 08:00–16:00
working day, **39% of bus travel falls inside it**. The single three-hour
evening commute carries **21%** — more than half the working day's share.

**5. A cheaper bus will not win riders.** On fare alone, **62–76% of taxi
passengers would switch to the bus**. Once travel time is counted, only
**0.05–9.3%** would. The bus would need to save **54 minutes** on the
Malé–Hulhumalé corridor to compete. No discount closes that gap. **Only the
causeway can.**

## What it means

1. **Add trips to the airport buses, not fewer.** R3 is 98% full on its airport
   approach and runs hourly. Re-timing it to the arrival peaks costs no new
   buses and is the clearest single win in the dataset.
2. **Give buses priority at the causeway.** Journey time is the binding
   constraint on modal shift; nothing else changes it.
3. **Run a skip-stop service on R1 and R2.** The two crossings dominate the
   journey, so trimming the twelve intermediate Hulhumalé stops yields a real
   time saving.

Under our recommended package, **290 fewer passengers are left behind** in the
period we measured, by moving 18 existing trips — no new vehicles.

## How much to trust this

We validated rather than assumed. The demand model predicts held-out ridership
with **9.9% mean absolute percentage error**, against **16.3%** for a naive
baseline — on 219 held-out days it had never seen.

`make check` re-derives 54 claims from the raw sources and fails if the
committed numbers disagree. It passes 54/54.

## What we could not measure

We would rather say this than overstate the result:

- The bus timetable feed returns only **the rest of the day from the moment it
  is requested**. Our capture covers about **11:00 to midnight**, so the morning
  peak is not observed. We bound it rather than invent it.
- Only **5 of the 15 routes** have passenger counts.
- The airport dataset provided covers about **40% of international arrivals and
  no domestic flights**, and carries no seasonal signal. Airport totals therefore
  come from the national yearbook.
- The **08:00–16:00 working day is an assumption**; no published working-hours
  data exists. Moving it by an hour shifts the answer by about three points.
- Our results describe **one Saturday in October 2026**, not a weekday.
- Load factors are modelled from taxi trip patterns, not counted on the bus.

## The tool

An interactive map of the 15 routes coloured by how full each one runs. Select a
route to see passenger demand against the buses provided, hour by hour, and
where on the route it fills up. Choose a scenario to see what changes for
passengers.

```bash
cd dashboard
python -m http.server 8000     # then open http://localhost:8000
```

It runs entirely in the browser from committed data files — no server, no
account, nothing to install.

## Data

Every figure traces to a public source. Nothing private or restricted was used.

| Data | Publisher | What it gave us |
|---|---|---|
| Bus timetable, stops, fares | RTL / MTCC | Official routes and departure times, current 2026 |
| Bus passenger counts | MTCC via MBS | Daily passengers on R1, R2, R3, R4, R7 |
| Taxi trips | Avas via MBS | 371,788 trips, August–September 2026 |
| Airport arrivals | MACL via MBS | Hourly international arrivals, 2012–2026 |
| Statistical Yearbook | MBS | Airport totals including domestic; population; labour force |
| Map data | OpenStreetMap contributors | Basemap and road network (ODbL) |

Full links, licences and caveats: **[DATA_SOURCES.md](DATA_SOURCES.md)**.

We also publish the first **GTFS feed** for the Greater Malé bus network, so the
network can be loaded into standard journey-planning tools.

## For readers who want the detail

- **[SPEC.md](SPEC.md)** — what we built, how, and what we would do next
- **[RESEARCH.md](RESEARCH.md)** — the full investigation, including what we tried and rejected
- **[docs/adr/](docs/adr/)** — a record of each methodological decision and its cost
- **[docs/DASHBOARD_SPEC.md](docs/DASHBOARD_SPEC.md)** — the dashboard build contract
- **[docs/TEAM.md](docs/TEAM.md)** — ownership and how to verify any number

---

**Team Wayfinders** · Maldives Datathon 2026
