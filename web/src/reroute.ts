// Loads the reroute contract (see docs/REROUTE.md). This is the only file that
// reads the new tables, mirroring data.ts for the existing screens: components
// render what it returns and compute nothing.
import Papa from 'papaparse'

import { edgeKeys } from './routeStyle'

type Row = Record<string, string>

const num = (v: string | undefined): number | null => {
  if (v === undefined || v.trim() === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

async function csv(name: string, optional = false): Promise<Row[] | null> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}`)
  const text = res.ok ? await res.text() : ''
  if (!res.ok || text.trimStart().startsWith('<')) {
    if (optional) return null
    throw new Error(`Missing data file: ${name}`)
  }
  return Papa.parse<Row>(text, { header: true, skipEmptyLines: true }).data
}

export interface NewStop {
  id: string
  name: string
  lat: number
  lon: number
  island: string
  population: number
  hotspots: number
  topHotspot: string
  placedBecause: string
  routes: string[]
  interchange: boolean
  // advisory (from the headless run)
  firstBusAt: number | null
  firstBusRoute: string
  peakQueue: number
  peakLoadPct: number | null
  extraBuses: number
  needsExtra: boolean
  extraWindows: string
  reason: string
  boardings: number
}

export interface NewRoute {
  id: string
  name: string
  service: string
  replaces: string[]
  stops: string[]
  lengthKm: number
  runTimeMin: number
  seats: number
  buses: number
  peakHeadway: number
}

export interface SimLeg {
  from: string
  to: string
  coords: [number, number][]
  minutes: number
  lengthM: number
}

export interface ProofCase {
  boarded: number | null
  leftBehindPct: number | null
  meanWaitMin: number | null
  p90WaitMin: number | null
  peakLoadPct: number | null
  buses: number | null
  extraBuses: number | null
  busHours: number | null
}

export interface LaneInfo {
  /** How many routes share this one's corridor. */
  groupSize: number
  /** This route's position in that group, used to displace it sideways. */
  index: number
}

export interface RerouteData {
  stops: NewStop[]
  byId: Record<string, NewStop>
  routes: NewRoute[]
  routeById: Record<string, NewRoute>
  legs: Record<string, SimLeg[]>
  demand: { stop_id: string; hour: number; boardings: number }[]
  od: { origin_stop_id: string; dest_stop_id: string; rides_per_day: number }[]
  hotspots: GeoJSON.FeatureCollection
  grid: { lat: number; lon: number; population: number; combined: number; island: string }[]
  params: any
  /** Corridor sharing, so overlapping routes can be drawn side by side. */
  lanes: Record<string, LaneInfo>
  proof: {
    cases: Record<string, ProofCase>
    network: Record<string, number>
    assumptions: Record<string, string>
    seeds: number[]
  } | null
  // today's network, for the comparison toggle and the map outline
  oldRoutes: { code: string; name: string; coords: [number, number][]; stops: [number, number][] }[]
  basemap: GeoJSON.FeatureCollection
}

export async function loadReroute(): Promise<RerouteData> {
  const [stopRows, routeRows, demandRows, odRows, gridRows, advisoryRows, params, basemap, hotspots] =
    await Promise.all([
      csv('reroute_stops.csv'),
      csv('reroute_routes.csv'),
      csv('reroute_demand_stop_hour.csv'),
      csv('reroute_od.csv'),
      csv('pop_grid.csv', true),
      csv('reroute_stop_advisory.csv', true),
      fetch(`${import.meta.env.BASE_URL}data/reroute_params.json`).then((r) => r.json()),
      fetch(`${import.meta.env.BASE_URL}data/basemap.geojson`).then((r) => r.json()),
      fetch(`${import.meta.env.BASE_URL}data/reroute_hotspots.geojson`).then((r) => r.json()),
    ])

  const segments = await fetch(`${import.meta.env.BASE_URL}data/reroute_segments.geojson`).then((r) => r.json())
  const proof = await fetch(`${import.meta.env.BASE_URL}data/reroute_proof.json`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null)

  const advisory = new Map((advisoryRows ?? []).map((r) => [r.stop_id, r]))
  const parseTime = (s: string): number | null => {
    const m = /^(\d{1,2}):(\d{2})$/.exec((s || '').trim())
    return m ? Number(m[1]) * 60 + Number(m[2]) : null
  }

  const stops: NewStop[] = stopRows!.map((r) => {
    const a = advisory.get(r.stop_id)
    return {
      id: r.stop_id,
      name: r.name,
      lat: Number(r.lat),
      lon: Number(r.lon),
      island: r.island,
      population: Number(r.population_400m || 0),
      hotspots: Number(r.hotspots_400m || 0),
      topHotspot: r.top_hotspot || '',
      placedBecause: r.placed_because || '',
      routes: (r.routes || '').replace(/[[\]']/g, '').split(',').map((s) => s.trim()).filter(Boolean),
      interchange: /true|yes/i.test(r.is_interchange || ''),
      firstBusAt: parseTime(a?.first_bus_time ?? ''),
      firstBusRoute: a?.first_bus_route ?? '',
      peakQueue: num(a?.peak_queue) ?? 0,
      peakLoadPct: num(a?.peak_load_pct),
      extraBuses: num(a?.extra_buses) ?? 0,
      needsExtra: /yes/i.test(a?.extra_bus_required ?? ''),
      extraWindows: a?.extra_bus_windows ?? '',
      reason: a?.reason ?? '',
      boardings: num(a?.boardings_served) ?? 0,
    }
  })

  const routes: NewRoute[] = routeRows!.map((r) => ({
    id: r.route_id,
    name: r.name,
    service: r.service_class,
    replaces: (r.replaces_routes || '').split(',').filter(Boolean),
    stops: r.stop_ids.split(',').map((s) => s.trim()),
    lengthKm: Number(r.length_km),
    runTimeMin: Number(r.run_time_min),
    seats: Number(r.seats),
    buses: Number(r.buses_required),
    peakHeadway: Number(r.peak_headway_min),
  }))

  const legsRaw: Record<string, SimLeg[]> = {}
  for (const f of segments.features) {
    const p = f.properties
    ;(legsRaw[p.route_id] ??= []).push({
      from: p.from_id,
      to: p.to_id,
      coords: f.geometry.coordinates.map(([lon, lat]: number[]) => [lat, lon]),
      minutes: Number(p.minutes),
      lengthM: Number(p.length_m),
    })
  }

  // Which routes genuinely share a road, measured from the geometry rather
  // than from the stop list: two routes that stop at different shelters on the
  // same street still overlap on the map, and that is what has to be legible.
  const edgesByRoute: Record<string, Set<string>> = {}
  for (const [rid, ls] of Object.entries(legsRaw)) {
    const set = new Set<string>()
    for (const l of ls) for (const k of edgeKeys(l.coords)) set.add(k)
    edgesByRoute[rid] = set
  }
  const laneOf: Record<string, LaneInfo> = {}
  for (const r of routes) {
    const mine = edgesByRoute[r.id] ?? new Set<string>()
    const peers = routes
      .filter((o) => {
        if (o.id === r.id) return true
        const theirs = edgesByRoute[o.id]
        if (!theirs) return false
        let shared = 0
        for (const k of mine) {
          if (theirs.has(k) && ++shared >= 40) return true
        }
        return false
      })
      .sort((a, b) => a.id.localeCompare(b.id))
    laneOf[r.id] = { groupSize: peers.length, index: peers.findIndex((o) => o.id === r.id) }
  }

  // today's network, for the "show what we replaced" toggle
  const oldSegs = await fetch(`${import.meta.env.BASE_URL}data/route_segments.geojson`).then((r) => r.json())
  const oldByRoute: Record<string, { code: string; name: string; coords: [number, number][]; stops: [number, number][] }> = {}
  const oldRouteRows = (await csv('routes_master.csv')) ?? []
  const oldNames = Object.fromEntries(oldRouteRows.map((r) => [r.route_code, r.route_name.trim()]))
  for (const f of oldSegs.features) {
    const p = f.properties
    if (!/^R([1-9]|1[0-2])$/.test(p.route_code)) continue
    const entry = (oldByRoute[p.route_code] ??= {
      code: p.route_code,
      name: oldNames[p.route_code] ?? p.route_code,
      coords: [],
      stops: [],
    })
    const cs = f.geometry.coordinates.map(([lon, lat]: number[]) => [lat, lon] as [number, number])
    if (!entry.coords.length) entry.coords.push(...cs)
    else entry.coords.push(...cs.slice(1))
  }

  const legs = legsRaw

  return {
    stops,
    byId: Object.fromEntries(stops.map((s) => [s.id, s])),
    routes,
    routeById: Object.fromEntries(routes.map((r) => [r.id, r])),
    legs,
    demand: demandRows!.map((r) => ({ stop_id: r.stop_id, hour: Number(r.hour), boardings: Number(r.boardings) })),
    od: odRows!.map((r) => ({
      origin_stop_id: r.origin_stop_id,
      dest_stop_id: r.dest_stop_id,
      rides_per_day: Number(r.rides_per_day),
    })),
    hotspots,
    grid: (gridRows ?? []).map((r) => ({
      lat: Number(r.lat),
      lon: Number(r.lon),
      population: Number(r.population),
      combined: Number(r.combined_score),
      island: r.island,
    })),
    params,
    lanes: laneOf,
    proof,
    oldRoutes: Object.values(oldByRoute),
    basemap,
  }
}

export const fmtClock = (min: number | null): string => {
  if (min === null || !Number.isFinite(min)) return '—'
  const m = Math.round(min) % (24 * 60)
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

export const SERVICE_LABEL: Record<string, string> = {
  airport: 'Airport coach',
  cross_bridge: 'Cross-bridge',
  local: 'Local',
}

export const SERVICE_COLOUR: Record<string, string> = {
  airport: '#171f6b',
  cross_bridge: '#c2410c',
  local: '#0f766e',
}
