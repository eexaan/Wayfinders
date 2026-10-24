# Architecture Decision Records

Short records of the decisions that shaped this project, so any of the four
team members — or a judge — can see **why** something is the way it is, not
just what it is. Format: [Nygard ADR](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

Read an ADR before you change the thing it governs. If you want to overturn
one, add a new ADR that supersedes it; do not silently edit.

| ADR | Decision | Status | Affects |
|---|---|---|---|
| [0001](0001-official-rtl-feed-for-supply.md) | Supply comes from the official RTL 2026 feed, not MTCC PDFs | Accepted | build, docs |
| [0002](0002-reconcile-at-route-hour.md) | Reconcile demand and supply at route × hour | Accepted | build, dashboard |
| [0003](0003-load-factor-on-seats.md) | **Load factor is reported on seats**, with seats+standing as secondary | Accepted | model, dashboard, report |
| [0004](0004-mtcc-level-avas-shape.md) | MTCC anchors the demand *level*; Avas supplies the *shape* | Accepted | model, report |
| [0005](0005-null-not-zero.md) | Uncapped hours are `null`, never `0` | Accepted | build, dashboard |
| [0006](0006-macl-shape-only.md) | MACL gives the arrival *shape* only; levels come from MBS 11.13 | Accepted | model, report |
| [0007](0007-static-dashboard.md) | The dashboard is a static site with no backend | Accepted | dashboard |
| [0008](0008-scenarios-are-trip-moves.md) | Scenarios are explicit trip moves, not percentage factors | Accepted | model, dashboard |
| [0009](0009-withdraw-friday-service-comparison.md) | The Friday service-vs-demand finding is withdrawn | Accepted | report, pitch |
| [0010](0010-capacity-from-team-table.md) | Capacity comes from the team capacity table, not the news article | Accepted | model, report |
| [0011](0011-inferred-morning-service.md) | The morning is a bounded route-day **inference**, never hourly data | Accepted | report, pitch |
| [0012](0012-working-hours-assumption.md) | Working hours assumed 08:00–16:00, published as a **band** | Accepted | report, dashboard |
| [0013](0013-realtime-layer-deferred.md) | The **realtime layer is deferred**, with stated entry conditions | Accepted | report, pitch, roadmap |
| [0014](0014-donor-ceiling.md) | **A trip move must not create a new over-capacity hour** | Accepted | model, dashboard |

## The six decisions most likely to be questioned

If you only read six, read these. Each is a place where a reasonable person
could have gone the other way, and the record explains why we did not.

1. **ADR-0003** — why R1 is described as 104.4% full in one place and 90.1% in
   another (route-day upper bound vs measured peak segment).
2. **ADR-0005** — why the dashboard shows a gap before 11:00 instead of zeros.
3. **ADR-0009** — why a finding that appeared in an earlier draft is gone.
4. **ADR-0006** — why MACL is not used for airport demand levels.
5. **ADR-0004** — why taxi data shapes bus demand but does not set its level.
6. **ADR-0012** — where the 08:00–16:00 working window comes from, and how much
   the answer moves if it is wrong.

## Numbering

`NNNN-kebab-case-title.md`, four digits, never reused, never reordered. Add a
row to the table above when you add a file.
