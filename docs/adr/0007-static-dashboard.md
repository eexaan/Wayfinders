# ADR-0007 — The dashboard is a static site with no backend

- **Status:** Accepted — **conditionally superseded** by [ADR-0013](0013-realtime-layer-deferred.md) should a realtime phase begin
- **Date:** 2026-10-24
- **Affects:** everything under `dashboard/`

## Context

The datathon's stated challenge is an interactive, GIS-powered statistical
dashboard. Constraints: one day to build it, a hard code/technical check, a
live 5-minute demo, and no servers available at the venue.

## Decision

A **static site**: `index.html` + `app.js` + `styles.css` reading the committed
CSVs in `dashboard/data/` with `fetch`. No build step, no bundler, no backend,
no database, no auth.

Dependencies from CDN, two only: Leaflet 1.9.4 and PapaParse 5.4.1.

Must be served over HTTP (`python -m http.server`) because `fetch` is blocked
on `file://`.

## Consequences

**Good**
- Nothing to fail at demo time: no `npm install`, no build error, no server.
- The "code and technical check" is trivial to satisfy — it is readable JS.
- Every number on screen traces to a committed CSV, so a judge can audit it.
- Reviewable by all four team members without a toolchain.

**Bad**
- No live data: the dashboard shows a snapshot, not a feed.
  Live refresh needs the RTL GPS endpoints, which require a JWT
  (`/v1/bus/eta`, `/v1/bus/livecoordinates` are 401).
- All scenario logic runs offline in `build_data.py`; the UI can only *select*
  a scenario or interpolate. Live re-optimisation would need the engine in JS.
- Manual DOM work instead of a component framework. Acceptable at this size
  (4 panels).

## Alternatives rejected

- **React + Vite.** Fine, but adds 30–45 min of setup and a build step on the
  critical path, for four panels.
- **A small API server.** Nothing to serve that a static file cannot.
- **Mapbox GL.** Needs a token; Deck.gl is overkill for 15 lines and 97 stops.

## How to verify

```bash
cd dashboard && python -m http.server 8000
# open http://localhost:8000 - expect zero console errors and
# no network calls except tiles and ./data/*
```

## Related

- `docs/DASHBOARD_SPEC.md` §0 and §6.
