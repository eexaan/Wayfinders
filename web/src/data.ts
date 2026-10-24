// Loads the frozen data contract from public/data (see docs/DASHBOARD_SPEC.md)
// and derives the handful of numbers the screens show. No modelling happens
// here - only lookups, sums and picking the headline route.
import Papa from 'papaparse'

type Row = Record<string, string>

export type Band = 'over' | 'busy' | 'room' | 'unknown'

export interface Route {
  code: string
  name: string
  nameDv: string
  busType: string
  busModel: string
  seats: number
  standing: number
  seatsAssumed: boolean
  fare: number
  tripsPerDay: number | null
  tripsCaptured: number
  firstTripOrder: number | null
  peakPct: number | null
  avgPct: number | null
  peakStretch: string | null
  peakHour: number | null
  boardingsPerDay: number | null
  band: Band
  isAirport: boolean
  onMap: boolean
}

export interface Stop {
  code: string
  name: string
  nameDv: string
  lat: number
  lon: number
  routes: string[]
}

export interface Segment {
  route: string
  coords: [number, number][]
  bridge: boolean
  minutes: number | null
  from: string
  to: string
  // fullest hour on this stretch, as % of seats; null = no passenger counts
  peakPct: number | null
  peakHour: number | null
  band: Band
}

export interface HourPoint {
  hour: number
  captured: boolean
  passengers: number | null
  seats: number | null
  buses: number | null
}

export interface Period {
  period: string
  sharePct: number | null
}

export interface Scenario {
  id: string
  key: string
  overCapacity: number
  unmetPct: number
  waitMin: number
  trips: number
  tripsMoved: number
  taxiPerDay: number | null
  byRoute: Record<string, number>
}

export interface Data {
  routes: Route[]
  byCode: Record<string, Route>
  stops: Stop[]
  segments: Segment[]
  hourly: Record<string, HourPoint[]>
  networkHourly: HourPoint[]
  departures: Record<string, number[]>
  periods: Record<string, Period[]> | null
  scenarios: Scenario[]
  vintage: { serviceDay: string; captureFrom: string; captureTo: string; noDemand: number; total: number }
  kpi: {
    fullest: { route: Route; pct: number } | null
    workingHoursPct: number | null
    headway: { route: Route; minutes: number } | null
    unmetPct: number | null
  }
  // the Sinamalé Bridge is the story: how much of one route's run it takes
  bridge: { route: string; minutes: number; crossings: number; endToEnd: number; sharePct: number } | null
  basemap: GeoJSON.FeatureCollection
}

const num = (v: string | undefined): number | null => {
  if (v === undefined || v.trim() === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

async function csv(name: string, optional = false): Promise<Row[] | null> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}`)
  const text = res.ok ? await res.text() : ''
  // a dev server answers a missing file with index.html, so check it is CSV
  if (!res.ok || text.trimStart().startsWith('<')) {
    if (optional) return null
    throw new Error(`Missing data file: ${name}`)
  }
  return Papa.parse<Row>(text, { header: true, skipEmptyLines: true }).data
}

export function bandOf(peak: number | null): Band {
  if (peak === null) return 'unknown'
  if (peak >= 100) return 'over'
  if (peak >= 60) return 'busy'
  return 'room'
}

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

export async function loadData(): Promise<Data> {
  const [master, load, stopRows, gap, deps, kpis, corridor, shift, periods, segLoad, bridges, segRes, basemap] = await Promise.all([
    csv('routes_master.csv'),
    csv('route_load.csv'),
    csv('route_stops.csv'),
    csv('demand_supply_gap.csv'),
    csv('service_departures.csv'),
    csv('scenario_kpis.csv'),
    csv('scenario_corridor_kpis.csv'),
    csv('scenario_modal_shift_summary.csv'),
    csv('usage_by_period.csv', true),
    csv('load_by_segment.csv', true),
    csv('bridge_segment_analysis.csv', true),
    fetch(`${import.meta.env.BASE_URL}data/route_segments.geojson`).then((r) => r.json()),
    fetch(`${import.meta.env.BASE_URL}data/basemap.geojson`).then((r) => r.json()),
  ])

  const loadBy = Object.fromEntries(load!.map((r) => [r.route_code, r]))

  // fullest captured hour per stretch (route x from_stop_order)
  const stretch: Record<string, { pct: number; hour: number }> = {}
  for (const r of segLoad ?? []) {
    const pct = num(r.load_factor_pct)
    if (pct === null) continue
    const k = `${r.route_code}:${r.from_stop_order}`
    if (!stretch[k] || pct > stretch[k].pct) stretch[k] = { pct, hour: Number(r.hour) }
  }

  // segments: road-snapped legs, Malé + Hulhumalé only
  const segments: Segment[] = segRes.features.map((f: any) => {
    const p = f.properties
    const st = stretch[`${p.route_code}:${p.seq}`]
    return {
      route: p.route_code,
      coords: f.geometry.coordinates.map(([lon, lat]: number[]) => [lat, lon]),
      // property renamed from `causeway`; accept either so a stale geojson
      // still loads rather than silently drawing every leg as non-bridge
      bridge: p.bridge ?? p.causeway,
      minutes: p.median_segment_minutes,
      from: p.from_stop,
      to: p.to_stop,
      peakPct: st?.pct ?? null,
      peakHour: st?.hour ?? null,
      band: bandOf(st?.pct ?? null),
    }
  })
  const onMap = new Set(segments.map((s) => s.route))

  const departures: Record<string, number[]> = {}
  const firstOrder: Record<string, number> = {}
  for (const d of deps!) {
    ;(departures[d.route_code] ??= []).push(Number(d.departure_min))
    const o = Number(d.trip_order)
    firstOrder[d.route_code] = Math.min(firstOrder[d.route_code] ?? Infinity, o)
  }

  const routes: Route[] = master!.map((m) => {
    const l = loadBy[m.route_code] ?? {}
    const peak = num(l.load_factor_peak_pct)
    const seats = num(m.seated_capacity) ?? Number(m.seats)
    const type = m.bus_type.trim()
    return {
      code: m.route_code,
      name: m.route_name.trim(),
      nameDv: m.route_name_dv.trim(),
      busType: type.charAt(0).toUpperCase() + type.slice(1),
      busModel: (m.bus_model ?? '').trim(),
      seats,
      standing: Math.max(0, (num(m.max_passengers) ?? seats) - seats),
      seatsAssumed: /assumed/i.test(m.capacity_source),
      fare: Number(m.fare_mvr),
      tripsPerDay: num(m.trips_per_day),
      tripsCaptured: Number(m.trips_captured || 0),
      firstTripOrder: firstOrder[m.route_code] ?? null,
      peakPct: peak,
      avgPct: num(l.load_factor_avg_pct),
      peakStretch: l.peak_segment?.trim() || null,
      peakHour: num(l.peak_segment_hour),
      boardingsPerDay: num(l.boardings_per_day),
      band: bandOf(peak),
      isAirport: /airport/i.test(m.corridor),
      onMap: onMap.has(m.route_code),
    }
  })
  const byCode = Object.fromEntries(routes.map((r) => [r.code, r]))

  const stopMap: Record<string, Stop> = {}
  for (const s of stopRows!) {
    if (!onMap.has(s.route_code)) continue
    const st = (stopMap[s.stop_code] ??= {
      code: s.stop_code,
      name: s.stop_name.trim(),
      nameDv: s.stop_name_dv.trim(),
      lat: Number(s.lat),
      lon: Number(s.lon),
      routes: [],
    })
    if (!st.routes.includes(s.route_code)) st.routes.push(s.route_code)
  }

  const hourly: Record<string, HourPoint[]> = {}
  for (const g of gap!) {
    const trips = num(g.trips_in_hour)
    ;(hourly[g.route_code] ??= []).push({
      hour: Number(g.hour),
      captured: g.capture_status === 'captured',
      passengers: num(g.demand_pax_est),
      seats: num(g.seated_capacity_hour ?? g.seat_capacity_hour),
      buses: trips,
    })
  }
  for (const k in hourly) hourly[k].sort((a, b) => a.hour - b.hour)

  // network view: only the routes that have passenger counts, so passengers
  // and seats are compared like for like
  const counted = routes.filter((r) => r.peakPct !== null).map((r) => r.code)
  const networkHourly: HourPoint[] = Array.from({ length: 24 }, (_, hour) => {
    const pts = counted.map((c) => hourly[c]?.[hour]).filter(Boolean) as HourPoint[]
    const captured = pts.some((p) => p.captured)
    const sum = (f: (p: HourPoint) => number | null) =>
      pts.reduce<number | null>((acc, p) => (f(p) === null ? acc : (acc ?? 0) + f(p)!), null)
    return {
      hour,
      captured,
      passengers: sum((p) => p.passengers),
      seats: captured ? sum((p) => p.seats) : null,
      buses: captured ? sum((p) => p.buses) : null,
    }
  })

  let periodsBy: Record<string, Period[]> | null = null
  if (periods) {
    periodsBy = {}
    for (const p of periods) {
      ;(periodsBy[p.route_code] ??= []).push({ period: p.period, sharePct: num(p.share_of_route_demand_pct) })
    }
  }

  // scenario_modal_shift_summary.csv predates the fleet-neutral rebuild: its S4
  // and S5 rows assume ADDED trips, so they are not comparable to these
  // scenarios (docs/DASHBOARD_SPEC.md §2.14). Only the baseline row is used,
  // for every scenario: re-timing buses does not change who switches mode.
  const taxiBase = shift!.find((s) => s.scenario.startsWith('S0'))
  const taxiPerDay = taxiBase ? Number(taxiBase.taxi_rides_capturable_per_day) : null
  const scenarios: Scenario[] = kpis!.map((k) => {
    const key = k.scenario.split('_')[0]
    return {
      id: k.scenario,
      key,
      overCapacity: Number(k.boardings_over_capacity),
      unmetPct: Number(k.unmet_share_pct),
      waitMin: Number(k.mean_wait_min_captured),
      trips: Number(k.total_trips_captured),
      tripsMoved: Number(k.trips_moved ?? 0),
      taxiPerDay,
      byRoute: Object.fromEntries(
        corridor!.filter((c) => c.scenario === k.scenario).map((c) => [c.route_code, Number(c.boardings_over_capacity)]),
      ),
    }
  })

  // headline numbers
  const counts = routes.filter((r) => r.peakPct !== null)
  const fullestR = counts.reduce<Route | null>((a, r) => (!a || r.peakPct! > a.peakPct! ? r : a), null)
  let headway: Data['kpi']['headway'] = null
  for (const r of routes.filter((r) => r.isAirport)) {
    const d = [...(departures[r.code] ?? [])].sort((a, b) => a - b)
    if (d.length < 3) continue
    const m = median(d.slice(1).map((t, i) => t - d[i]))
    if (!headway || m > headway.minutes) headway = { route: r, minutes: Math.round(m) }
  }
  const base = scenarios.find((s) => s.key === 'S0')

  const capturedHours = gap!.filter((g) => g.capture_status === 'captured').map((g) => Number(g.hour))

  // What the bridge costs, from the scheduled stop-to-stop timings.
  const endToEnd: Record<string, number> = {}
  for (const b of bridges ?? []) {
    const m = num(b.median_end_to_end_minutes)
    if (m !== null) endToEnd[b.route_code] = Math.max(endToEnd[b.route_code] ?? 0, m)
  }
  const bridgeByRoute: Record<string, { minutes: number; crossings: number }> = {}
  for (const s of segments) {
    if (!s.bridge || !s.minutes) continue
    const b = (bridgeByRoute[s.route] ??= { minutes: 0, crossings: 0 })
    b.minutes += s.minutes
    b.crossings += 1
  }
  const bridgeEntry = Object.entries(bridgeByRoute).sort((a, b) => b[1].minutes - a[1].minutes)[0]
  const bridge =
    bridgeEntry && endToEnd[bridgeEntry[0]]
      ? {
          route: bridgeEntry[0],
          minutes: bridgeEntry[1].minutes,
          crossings: bridgeEntry[1].crossings,
          endToEnd: endToEnd[bridgeEntry[0]],
          sharePct: Math.round((bridgeEntry[1].minutes / endToEnd[bridgeEntry[0]]) * 100),
        }
      : null

  return {
    routes,
    byCode,
    stops: Object.values(stopMap),
    segments,
    hourly,
    networkHourly,
    departures,
    periods: periodsBy,
    scenarios,
    vintage: {
      serviceDay: master![0]?.service_day ?? '',
      captureFrom: capturedHours.length ? fmtHour(Math.min(...capturedHours)) : '',
      captureTo: capturedHours.length ? fmtHour(Math.max(...capturedHours) + 1) : '',
      noDemand: routes.length - counts.length,
      total: routes.length,
    },
    kpi: {
      fullest: fullestR && { route: fullestR, pct: fullestR.peakPct! },
      workingHoursPct: periodsBy?.ALL?.find((p) => p.period === 'working_hours')?.sharePct ?? null,
      headway,
      unmetPct: base?.unmetPct ?? null,
    },
    bridge,
    basemap,
  }
}

export const BAND_LABEL: Record<Band, string> = {
  over: 'Over full (100%+)',
  busy: 'Busy (60–99%)',
  room: 'Room to spare (under 60%)',
  unknown: 'No passenger counts',
}

export const fmtHour = (h: number) => `${String(h).padStart(2, '0')}:00`
export const fmtInt = (n: number) => Math.round(n).toLocaleString('en-US')
