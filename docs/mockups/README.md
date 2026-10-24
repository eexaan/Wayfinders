# Mockups

Two standalone HTML pages that test a UI idea before it goes into `web/`.
Both are self-contained (no build step) and read committed data only.

```bash
cd docs/mockups && python3 -m http.server 8020
# http://localhost:8020/proposed-routes-mockup.html   <- proposed NEW service
# http://localhost:8020/dynamic-routes-mockup.html    <- re-timing, hour by hour
```

## `proposed-routes-mockup.html`

Draws three **additive** service changes on the map, routed along real OSM roads
by `scripts/build_proposals.py`:

| | Proposal | Kind | Evidence |
|---|---|---|---|
| **P1** | Phase 2 → Rehendhi School special | new route, timed | Rehendhi is an OSM education POI; 13 buildings sit >400 m from any stop |
| **P2** | Extend R6 two stops north | extension, no new trips | every R6 trip already passes the blocks and turns around before them |
| **P3** | Phase 2 west feeder loop | new route, peak-only | 136 buildings west of the stop line; feeds Hiya Flats, which carries 5 routes |

The rule the mockup is built around: **proposals only add service.** Removing a
trip from an existing route to pay for one is the case
`donor_load_after_pct` in `scenario_moves.csv` exists to catch — the donor's
remaining riders are stranded.

## `dynamic-routes-mockup.html`

An hour slider drives the whole map, so route colour is the pressure *at that
hour* rather than a daily average, and the six S5 moves appear as arcs from
donor leg to receiver leg with their own numbers attached.

Both are sketches, not features. Neither is wired into `web/`.
