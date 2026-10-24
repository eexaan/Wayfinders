/**
 * ============================================================================
 * Run the reroute simulation headlessly and write the proof tables
 * ============================================================================
 * Maldives Datathon 2026 | Team Wayfinders
 *
 * This is the same engine the browser animates (`src/sim/engine.mjs`), run to
 * the end of the day for several seeds. It writes:
 *
 *   dashboard/data/reroute_sim_results.csv     per route per hour
 *   dashboard/data/reroute_stop_advisory.csv   the per-stop deliverable
 *   dashboard/data/reroute_route_advisory.csv  buses and extra buses per route
 *   dashboard/data/reroute_proof.json          the ablation
 *
 * THE ABLATION, AND WHY IT IS SHAPED LIKE THIS
 *   An earlier version compared a 99-bus network against a 55-bus one and
 *   reported that waiting barely moved and journeys got 35 minutes worse. Three
 *   things changed at once, so nothing could be attributed to anything. Each row
 *   below differs from the one above by exactly ONE change, and the fleet is held
 *   at today's 55 buses until the last row:
 *
 *     1. baseline      today's 9 routes, today's stops, the published timetable
 *     2. +dispatch     same routes, same 55 buses, depart on demand instead
 *     3. +loops        R5/R6 become Hulhumalé circuits, trunks through-run one
 *     4. +extra buses  the buses the crowded stops need, and nothing else
 *
 *   Row 4 is the only row that is allowed to exceed the fleet, so its delta is
 *   unambiguously the extra buses.
 *
 * Usage:  node web/scripts/run-sim.mjs [--seeds 20261024,7,99]
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createSimulation } from '../src/sim/engine.mjs'
import { readCsv, writeCsv } from './csv.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..', '..')
const DATA = join(ROOT, 'dashboard', 'data')

const SEED_ARG = process.argv.indexOf('--seeds')
const SEEDS = SEED_ARG > -1
  ? process.argv[SEED_ARG + 1].split(',').map((s) => Number(s.trim())).filter(Number.isFinite)
  : [20261024, 7, 99]
const REPORT_SEED = SEEDS[0]

const START_MIN = 5 * 60
const END_MIN = 24 * 60
const TOTAL_BUSES = 55
const LAYOVER_MIN = 6

// Today's routes that have a recorded timetable and are in scope. R10-R12 are
// excluded because they have no captured departures; R13/R14 are Villimalé.
const OLD_ROUTES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9']

const hhmm = (min) => {
  const m = Math.round(min)
  return `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}
const haversine = (a, b) => {
  const R = 6371000
  const p1 = (a.lat * Math.PI) / 180
  const p2 = (b.lat * Math.PI) / 180
  const dp = p2 - p1
  const dl = ((b.lon - a.lon) * Math.PI) / 180
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}
const round1 = (v) => (v == null || !Number.isFinite(v) ? null : Math.round(v * 10) / 10)

// ---------------------------------------------------------------------------
// the reroute contract
const rerouteStops = readCsv(join(DATA, 'reroute_stops.csv')).map((r) => ({
  stop_id: r.stop_id,
  name: r.name,
  lat: Number(r.lat),
  lon: Number(r.lon),
  island: r.island,
  population: Number(r.population_400m || 0),
  hotspots: Number(r.hotspots_400m || 0),
  routes: (r.routes || '').split(' ').filter(Boolean),
}))
const rerouteRoutes = readCsv(join(DATA, 'reroute_routes.csv')).map((r) => ({
  route_id: r.route_id,
  name: r.name,
  service_class: r.service_class,
  kind: r.kind,
  seats: Number(r.seats),
  max_passengers: Number(r.max_passengers),
  buses_required: Number(r.buses_required),
  peak_headway_min: Number(r.headway_min),
  length_km: Number(r.length_km),
  replaces_routes: r.replaces_routes,
  stop_ids: r.stop_ids.split(',').map((s) => s.trim()),
}))
const fleetAlloc = readCsv(join(DATA, 'reroute_fleet_alloc.csv')).map((r) => ({
  route_id: r.route_id,
  buses: Number(r.buses),
  peak_demand: Number(r.peak_demand),
}))

const rerouteSegments = JSON.parse(readFileSync(join(DATA, 'reroute_segments.geojson'), 'utf8')).features
const demand = readCsv(join(DATA, 'reroute_demand_stop_hour.csv')).map((r) => ({
  stop_id: r.stop_id, hour: Number(r.hour), boardings: Number(r.boardings),
}))
const od = readCsv(join(DATA, 'reroute_od.csv')).map((r) => ({
  origin_stop_id: r.origin_stop_id, dest_stop_id: r.dest_stop_id, rides_per_day: Number(r.rides_per_day),
}))
const params = JSON.parse(readFileSync(join(DATA, 'reroute_params.json'), 'utf8'))

function legsFor(features, idField) {
  const out = new Map()
  for (const f of features) {
    const p = f.properties
    const id = p[idField]
    if (!out.has(id)) out.set(id, [])
    out.get(id).push({
      seq: Number(p.seq),
      from_id: String(p.from_id ?? p.from_code),
      to_id: String(p.to_id ?? p.to_code),
      length_m: Number(p.length_m ?? p.road_m),
      minutes: Number(p.minutes ?? p.median_segment_minutes) || 0.6,
      coords: f.geometry.coordinates,
    })
  }
  for (const ls of out.values()) ls.sort((a, b) => a.seq - b.seq)
  return out
}
const newLegs = legsFor(rerouteSegments, 'route_id')

// ---------------------------------------------------------------------------
// today's network, from the committed geometry and the published timetable
const routeStops = readCsv(join(DATA, 'route_stops.csv')).filter((r) => OLD_ROUTES.includes(r.route_code))
const master = readCsv(join(DATA, 'routes_master.csv'))
const masterBy = new Map(master.map((m) => [m.route_code, m]))
const serviceHour = readCsv(join(DATA, 'route_service_by_hour.csv'))
const morning = readCsv(join(DATA, 'morning_service_inferred.csv'))
const morningBy = new Map(morning.map((m) => [m.route_code, Number(m.morning_avg_headway_min)]))

const oldSegs = JSON.parse(readFileSync(join(DATA, 'route_segments.geojson'), 'utf8'))
const oldLegs = legsFor(oldSegs.features, 'route_code')

const islandOf = (lat, lon) => {
  if (lon < 73.5) return 'Villimalé'
  if (lat >= 4.2) return 'Hulhumalé'
  if (lat >= 4.185) return 'Hulhulé'
  return 'Malé'
}

const oldStops = []
const oldIndex = new Map()
for (const r of routeStops) {
  if (!oldIndex.has(r.stop_code)) {
    oldIndex.set(r.stop_code, oldStops.length)
    oldStops.push({
      stop_id: r.stop_code,
      name: r.stop_name,
      lat: Number(r.lat),
      lon: Number(r.lon),
      island: islandOf(Number(r.lat), Number(r.lon)),
    })
  }
}

const hourHeadway = new Map()
for (const r of serviceHour) {
  if (!OLD_ROUTES.includes(r.route_code)) continue
  if (!hourHeadway.has(r.route_code)) hourHeadway.set(r.route_code, new Array(24).fill(null))
  const dep = Number(r.departures)
  if (r.captured === 'True' && dep > 0) hourHeadway.get(r.route_code)[Number(r.hour)] = 60 / dep
}

function oldRouteDefs() {
  return OLD_ROUTES.map((code) => {
    const legs = oldLegs.get(code)
    if (!legs || !legs.length) return null
    const m = masterBy.get(code)
    const fixed = (hourHeadway.get(code) || new Array(24).fill(null)).slice()
    const morningHw = morningBy.get(code)
    let last = null
    for (let h = 0; h < 24; h++) {
      if (fixed[h] != null) last = fixed[h]
      else if (h >= 5 && h < 12 && morningHw) fixed[h] = morningHw
      else fixed[h] = last
    }
    return {
      route_id: code,
      name: m?.route_name ?? code,
      service_class: 'today',
      seats: Number(m?.seated_capacity ?? m?.seats ?? 33),
      max_passengers: Number(m?.max_passengers ?? m?.seated_capacity ?? 33),
      stops: [legs[0].from_id, ...legs.map((l) => l.to_id)].map(String),
      legs: legs.map((l) => ({
        from_id: String(l.from_id), to_id: String(l.to_id),
        length_m: l.length_m, minutes: l.minutes, coords: l.coords,
      })),
      fixed_headways: fixed,
      buses_required: 1,
    }
  }).filter(Boolean)
}

/** The fleet the published timetable physically needs. */
function timetableFleet(r) {
  const cycle = 2 * (r.legs.reduce((a, l) => a + l.minutes, 0) + LAYOVER_MIN)
  let buses = 1
  for (let h = 5; h < 24; h++) {
    const hw = r.fixed_headways?.[h]
    if (!hw || hw <= 0) continue
    buses = Math.max(buses, Math.ceil((60 / hw) * (cycle / 60)))
  }
  return buses
}

/**
 * Allocate a fixed fleet across routes: one bus each, the rest by largest
 * remainder on peak demand. The headway a route can sustain is then
 * cycle / buses, which is what makes the fleet constraint physical rather
 * than a number in a table.
 */
function allocate(routes, total, weightKey = 'peak_demand') {
  if (routes.length > total) throw new Error(`${routes.length} routes on ${total} buses`)
  const rem = total - routes.length
  const w = routes.map((r) => Math.max(1e-6, r[weightKey] ?? 1))
  const sum = w.reduce((a, b) => a + b, 0)
  const exact = w.map((x) => (rem * x) / sum)
  const base = exact.map((x) => Math.floor(x))
  let left = rem - base.reduce((a, b) => a + b, 0)
  const order = exact.map((x, i) => [x - base[i], i]).sort((a, b) => b[0] - a[0])
  for (const [, i] of order) {
    if (left <= 0) break
    base[i] += 1
    left -= 1
  }
  return routes.map((r, i) => ({
    ...r,
    buses_required: 1 + base[i],
    cycle_min: 2 * (r.legs.reduce((a, l) => a + l.minutes, 0) + LAYOVER_MIN),
  }))
}

// ---------------------------------------------------------------------------
// demand, re-projected so both networks carry the same passengers
const newToOld = rerouteStops.map((s) => {
  let best = 0
  let bestD = Infinity
  oldStops.forEach((o, i) => {
    const d = haversine(s, o)
    if (d < bestD) { best = i; bestD = d }
  })
  return { index: best, dist: bestD }
})
const rerouteStopAt = new Map(rerouteStops.map((s, i) => [s.stop_id, i]))

const oldDemandMap = new Map()
const oldOdMap = new Map()
const oldIds = oldStops.map((s) => s.stop_id)
for (const d of demand) {
  const ni = rerouteStopAt.get(d.stop_id)
  if (ni === undefined) continue
  const key = `${oldIds[newToOld[ni].index]}|${d.hour}`
  oldDemandMap.set(key, (oldDemandMap.get(key) || 0) + d.boardings)
}
for (const row of od) {
  const ni = rerouteStopAt.get(row.origin_stop_id)
  const nj = rerouteStopAt.get(row.dest_stop_id)
  if (ni === undefined || nj === undefined) continue
  const a = oldIds[newToOld[ni].index]
  const b = oldIds[newToOld[nj].index]
  if (a === b) continue
  const key = `${a}|${b}`
  oldOdMap.set(key, (oldOdMap.get(key) || 0) + row.rides_per_day)
}
const oldDemand = [...oldDemandMap.entries()].map(([k, v]) => {
  const [stop_id, hour] = k.split('|')
  return { stop_id, hour: Number(hour), boardings: v }
})
const oldOd = [...oldOdMap.entries()].map(([k, v]) => {
  const [origin_stop_id, dest_stop_id] = k.split('|')
  return { origin_stop_id, dest_stop_id, rides_per_day: v }
})

// ---------------------------------------------------------------------------
// the four cases
function rerouteNetworkDefs(extraByRoute = {}) {
  return rerouteRoutes.map((r) => ({
    ...r,
    stops: r.stop_ids,
    legs: (newLegs.get(r.route_id) || []).map((l) => ({
      from_id: l.from_id, to_id: l.to_id, length_m: l.length_m, minutes: l.minutes, coords: l.coords,
    })),
    buses_required: r.buses_required + (extraByRoute[r.route_id] || 0),
    fixed_headways: undefined,
  }))
}

function runCase(kind, seed) {
  const isReroute = kind !== 'baseline' && kind !== 'dispatch'
  const stops = isReroute
    ? rerouteStops.map((s) => ({ stop_id: s.stop_id, name: s.name, lat: s.lat, lon: s.lon, island: s.island }))
    : oldStops

  let routes
  let dem = isReroute ? demand : oldDemand
  let odp = isReroute ? od : oldOd

  if (kind === 'baseline') {
    routes = oldRouteDefs().map((r) => ({ ...r, buses_required: timetableFleet(r) }))
  } else if (kind === 'dispatch') {
    // same routes and stops, same fleet, but departures decided by demand
    const defs = oldRouteDefs().map((r) => ({
      ...r,
      fixed_headways: undefined,
      peak_demand: peakDemandFor(r.stops, oldDemand),
    }))
    routes = allocate(defs, TOTAL_BUSES)
  } else if (kind === 'loops') {
    routes = rerouteNetworkDefs().map((r) => ({
      ...r,
      peak_demand: peakDemandFor(r.stops, demand),
    }))
  } else {
    const extra = extraBusesByRoute()
    routes = rerouteNetworkDefs(extra).map((r) => ({ ...r, peak_demand: peakDemandFor(r.stops, demand) }))
  }

  const sim = createSimulation({
    stops, routes, demand: dem, od: odp,
    options: { seed, startMin: START_MIN, endMin: END_MIN, maxExtraBuses: 0 },
  })
  const summary = sim.finish()

  const declared = routes.reduce((a, r) => a + Math.max(1, Math.round(r.buses_required || 1)), 0)
  const realised = summary.buses
  if (declared !== realised) {
    throw new Error(`${kind}: declared ${declared} buses but the engine ran ${realised}`)
  }
  return { sim, summary, stops, routes, declared }
}

function peakDemandFor(stopIds, dem) {
  const want = new Set(stopIds.map(String))
  const byHour = new Array(24).fill(0)
  for (const d of dem) if (want.has(String(d.stop_id))) byHour[Math.floor(d.hour)] += d.boardings
  return Math.max(...byHour, 1)
}

/**
 * One extra bus on each route that serves a stop the loops run left crowded.
 *
 * Derived from the run itself rather than from the advisory file, which is
 * written after this point - reading it here was a chicken-and-egg bug that
 * silently made row 4 identical to row 3.
 */
let extraCache = null
function extraBusesByRoute() {
  if (extraCache) return extraCache
  const base = runs[REPORT_SEED]?.loops
  if (!base) return {}
  const flagged = new Set(
    rerouteStops
      .filter((_, i) => (base.summary.peakQueueByStop[i] || 0) >= 25)
      .map((s) => s.stop_id),
  )
  const out = {}
  for (const r of rerouteRoutes) {
    if (r.stop_ids.some((sid) => flagged.has(sid))) out[r.route_id] = 1
  }
  // a cap, so this row cannot quietly become a second network
  extraCache = Object.fromEntries(
    Object.entries(out).sort((a, b) => a[0].localeCompare(b[0])).slice(0, 8),
  )
  return extraCache
}

// ---------------------------------------------------------------------------
const KINDS = ['baseline', 'dispatch', 'loops', 'plus']
const KPI = ['completed', 'boarded', 'meanWaitMin', 'p90WaitMin', 'meanJourneyMin',
  'leftBehindPct', 'peakLoadPct', 'buses', 'busHours', 'tripsRun']

const runs = {}
for (const seed of SEEDS) {
  runs[seed] = {}
  // 'loops' must run before 'plus': the extra-bus row is derived from what the
  // loops run left crowded.
  for (const k of ['baseline', 'dispatch', 'loops']) runs[seed][k] = runCase(k, seed)
}
for (const seed of SEEDS) runs[seed].plus = runCase('plus', seed)

function aggregate(kind) {
  const out = {}
  for (const k of KPI) {
    const vals = SEEDS.map((s) => runs[s][kind].summary[k]).filter((v) => v != null)
    out[k] = vals.length ? median(vals) : null
  }
  out.buses = runs[REPORT_SEED][kind].declared
  return out
}

const cases = Object.fromEntries(KINDS.map((k) => [k, aggregate(k)]))

const ROWS = [
  {
    key: 'baseline',
    label: 'The original network',
    note: 'the 9 routes with a recorded timetable, their own stops, their own schedule',
    change: '',
  },
  {
    key: 'dispatch',
    label: '+ buses sent when needed',
    note: 'same routes, same 55 buses: depart when demand or a full bus calls, not on a clock',
    change: 'dispatch',
  },
  {
    key: 'loops',
    label: '+ Hulhumalé on loops',
    note: 'same 55 buses: the island\u2019s local routes become circuits, cross-island buses run through',
    change: 'topology',
  },
  {
    key: 'plus',
    label: '+ the buses the crowded stops need',
    note: 'the only row allowed to exceed the fleet: one extra bus on each route the stop table flags',
    change: 'fleet',
  },
]

const proof = {
  seed: REPORT_SEED,
  seeds: SEEDS,
  day: `${hhmm(START_MIN)}-${hhmm(END_MIN)}`,
  fleet_held: TOTAL_BUSES,
  demand: { daily_boardings: Math.round(demand.reduce((a, d) => a + d.boardings, 0)) },
  rows: ROWS.map((row, i) => {
    const kpis = cases[row.key]
    const prev = i > 0 ? cases[ROWS[i - 1].key] : null
    const delta = {}
    for (const k of KPI) {
      delta[k] = prev && prev[k] != null && kpis[k] != null ? round1(kpis[k] - prev[k]) : null
    }
    return { ...row, kpis, delta }
  }),
  cases,
  scope: {
    baseline_routes: OLD_ROUTES,
    reroute_routes: rerouteRoutes.map((r) => r.route_id),
    excluded: params?.network?.excluded_routes ?? [],
    excluded_reason: 'no captured departures and no ridership count, so replaying them '
      + 'would mean inventing a schedule. Excluded from both sides.',
  },
  assumptions: {
    fleet: `held at ${TOTAL_BUSES} buses for rows 1-3; row 4 adds the advisory's extras`,
    dispatch: 'row 1 uses the published timetable; rows 2-4 depart on demand or at 90% of seats',
    demand: 'identical in every row: the same passengers, re-projected onto whichever stop set is in use',
    transfers: 'up to two changes; chosen by travel time plus expected wait',
    operating_day: '05:00-24:00',
  },
  generated_by: 'web/scripts/run-sim.mjs (same engine as the browser)',
}

// ---- the per-stop deliverable --------------------------------------------
const rr = runs[REPORT_SEED].loops
const s = rr.summary
const routePeakLoad = s.peakLoadByRoute
const stopRows = rerouteStops.map((st, i) => {
  const first = s.firstBusByStop[i]
  const serving = st.routes
  const peakLoad = serving.length ? Math.max(...serving.map((c) => (routePeakLoad[c] || 0) * 100)) : null
  const extra = s.extraByStop[i]
  const peakQueue = s.peakQueueByStop[i]
  const longWait = s.longWaitByStop[i] || 0
  const needsExtra = extra > 0 || peakQueue >= 25
  const events = s.events.filter((e) => e.stop === st.stop_id)
  return {
    stop_id: st.stop_id,
    stop_name: st.name,
    lat: st.lat,
    lon: st.lon,
    island: st.island,
    routes: st.routes.join(' '),
    population_400m: st.population,
    hotspots_400m: st.hotspots,
    first_bus_time: first ? hhmm(first.at) : '',
    first_bus_min: first ? Math.round(first.at) : '',
    first_bus_route: first ? first.route : '',
    first_bus_direction: first ? (first.direction > 0 ? 'outbound' : 'inbound') : '',
    boardings_served: s.boardedByStop[i],
    alightings: s.alightedByStop[i],
    peak_queue: peakQueue,
    long_waits: longWait,
    peak_load_pct: peakLoad == null ? '' : Math.round(peakLoad * 10) / 10,
    extra_buses: extra,
    extra_bus_required: needsExtra ? 'yes' : 'no',
    extra_bus_windows: events.length ? events.map((e) => `${hhmm(e.clock)} +1`).join('; ') : '',
    reason: extra > 0
      ? `spare sent: queue ${events.map((e) => e.queue).join('/')} with no bus due within 8 min`
      : peakQueue >= 25
        ? `peak queue ${peakQueue}; ${longWait} waited over 10 min`
        : '',
  }
})
writeCsv(join(DATA, 'reroute_stop_advisory.csv'), Object.keys(stopRows[0] || { stop_id: '' }), stopRows)

// ---- the per-route advisory ----------------------------------------------
const rowRoutes = rerouteRoutes.map((r) => {
  const hours = s.routeHour.filter((h) => h.route === r.route_id)
  const boardings = hours.reduce((a, h) => a + h.boarded, 0)
  const departures = hours.reduce((a, h) => a + h.departures, 0)
  return {
    route_id: r.route_id,
    name: r.name,
    service_class: r.service_class,
    kind: r.kind,
    replaces_routes: r.replaces_routes,
    length_km: r.length_km,
    seats: r.seats,
    buses_allocated: r.buses_required,
    boardings: Math.round(boardings),
    departures,
    mean_headway_min: departures ? Math.round(1140 / departures) : '',
    peak_load_pct: Math.round((routePeakLoad[r.route_id] || 0) * 1000) / 10,
  }
})
writeCsv(join(DATA, 'reroute_route_advisory.csv'), Object.keys(rowRoutes[0] || { route_id: '' }), rowRoutes)

writeCsv(join(DATA, 'reroute_sim_results.csv'),
  ['route_id', 'hour', 'boarded', 'departures', 'peak_load_pct'],
  s.routeHour.map((h) => ({
    route_id: h.route, hour: h.hour, boarded: Math.round(h.boarded),
    departures: h.departures, peak_load_pct: Math.round(h.peakLoad * 1000) / 10,
  })))

writeFileSync(join(DATA, 'reroute_proof.json'), `${JSON.stringify(proof, null, 2)}\n`)

// ---- report --------------------------------------------------------------
const fmt = (v, d = 1) => (v == null ? '-' : Number(v).toFixed(d))
const lines = [
  '',
  '='.repeat(104),
  `ABLATION   seeds ${SEEDS.join(', ')}   day ${proof.day}   fleet held at ${TOTAL_BUSES}`,
  '='.repeat(104),
  `${'row'.padEnd(34)}${'carried'.padStart(9)}${'wait'.padStart(7)}${'p90'.padStart(7)}${'ride'.padStart(7)}${'left%'.padStart(8)}${'buses'.padStart(7)}`,
]
for (const row of proof.rows) {
  const k = row.kpis
  lines.push(
    `${row.label.padEnd(34)}${String(k.completed).padStart(9)}${fmt(k.meanWaitMin).padStart(7)}`
    + `${fmt(k.p90WaitMin, 0).padStart(7)}${fmt(k.meanJourneyMin, 0).padStart(7)}`
    + `${fmt(k.leftBehindPct).padStart(8)}${String(k.buses).padStart(7)}`,
  )
}
lines.push('', 'delta vs the row above (negative wait/ride = better):')
for (const row of proof.rows.slice(1)) {
  const d = row.delta
  lines.push(`  ${row.label.padEnd(34)} wait ${fmt(d.meanWaitMin).padStart(6)}  p90 ${fmt(d.p90WaitMin, 0).padStart(5)}`
    + `  ride ${fmt(d.meanJourneyMin, 0).padStart(5)}  left ${fmt(d.leftBehindPct).padStart(6)}  buses ${d.buses > 0 ? '+' : ''}${d.buses}`)
}
lines.push('', `destinations served: ${proof.demand.daily_boardings} boardings/day; `
  + `${rerouteStops.length} stops, ${rerouteRoutes.length} routes`)
console.log(lines.join('\n'))
