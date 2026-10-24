# Dashboard (React + TypeScript + Vite)

The interactive tool. **This is the deliverable**; `dashboard/index.html` at the
repo root is an earlier static prototype and is not used.

```bash
npm ci
npm run dev        # http://localhost:5173
npm run build      # -> dist/, which `make serve` serves on :8000
npm run lint
```

## Where the numbers come from

`scripts/sync-data.mjs` runs before `dev` and `build` and copies the frozen
contract from `../dashboard/data/` into `public/data/`. **Nothing here computes
a figure.** `src/data.ts` is the only file that reads those files; components
render what it returns. If a number on screen is wrong, fix the build script in
`../dashboard/build/` and re-run `make data` — do not patch a component.

The contract, column by column, is `../docs/DASHBOARD_SPEC.md` §2. The two
traps that matter most:

- **Uncaptured is not zero.** `demand_supply_gap.trips_in_hour` is null before
  ~11:00. Draw a gap, never a zero bar.
- **Unknown is not zero.** Ten routes have `NO DEMAND DATA`. Show them as
  unknown, not as 0%.

## Layout

`App.tsx` holds the two tabs (`#overview`, `#overview/R1`, `#scenarios/S5` — all
bookmarkable). `components/` has one file per panel: `RouteMap`, `RouteRanking`,
`RoutePanel`, `HourlyChart`, `Scenarios`, `MethodDrawer`, `VintageLine`,
`KpiStrip`.
