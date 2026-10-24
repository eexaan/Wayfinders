/**
 * ============================================================================
 * The reroute simulation engine
 * ============================================================================
 * Maldives Datathon 2026 | Team Wayfinders
 *
 * WHY THIS IS A SEPARATE, DEPENDENCY-FREE MODULE
 *   The numbers the app shows and the numbers the build writes must come from
 *   the same code. This file is imported by the browser (to animate the day) and
 *   by `web/scripts/run-sim.mjs` (to write the proof tables), so a KPI cannot
 *   drift between the two. No imports, no Date.now(), no Math.random().
 *
 * WHAT IT MODELS
 *   Passengers   individual agents from the per-stop-per-hour demand table and
 *                the stop-to-stop OD matrix. Each carries a destination, so
 *                alighting - and therefore load along a segment - is modelled
 *                rather than assumed symmetric.
 *   Journeys     one transfer is allowed. A passenger with no direct route waits
 *                at a transfer stop for the second leg, and the transfer wait
 *                counts in their total. This matters: in a 63-stop network most
 *                OD pairs share no single route, and a model without transfers
 *                would throw that demand away and flatter whichever network
 *                happens to have fewer, longer routes.
 *   Buses        vehicles on route polylines, both directions, with the bus class
 *                and capacity the route needs.
 *   Dispatch     there is NO timetable on the reroute. A bus leaves a terminal
 *                when the demand-derived headway expires, or when the queue
 *                reaches 90% of its seats, whichever comes first. A spare bus is
 *                inserted when a stop has been over the trigger for three
 *                consecutive minutes and nothing is due within eight.
 *
 * WHY THE RESULT IS REPRODUCIBLE
 *   One seeded PRNG (mulberry32), consumed in a fixed order: stops ascending,
 *   then hour ascending, then passengers in time order. Same seed, same day,
 *   same KPIs, in the browser and in Node.
 *
 * WHAT IT DOES NOT MODEL
 *   More than one transfer, fare penalties, walking between stops, vehicle
 *   bunching from traffic, and dwell time beyond the per-leg figure. Passengers
 *   board in arrival order; nobody jumps a queue.
 */

/** Deterministic 32-bit PRNG. Same seed, same stream, everywhere. */
export function mulberry32(seed) {
  let a = seed >>> 0
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v)
const HOUR = 60

/** Linear interpolation along a polyline by fraction of its length. */
function pointAt(coords, cum, f) {
  if (!coords.length) return null
  if (coords.length === 1) return coords[0]
  const target = clamp(f, 0, 1) * cum[cum.length - 1]
  let lo = 0
  let hi = cum.length - 1
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1
    if (cum[mid] <= target) lo = mid
    else hi = mid
  }
  const span = cum[hi] - cum[lo] || 1
  const r = (target - cum[lo]) / span
  const a = coords[lo]
  const b = coords[hi]
  return [a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r]
}

function cumulative(coords) {
  const cum = [0]
  for (let i = 1; i < coords.length; i++) {
    const dl = coords[i][0] - coords[i - 1][0]
    const dn = coords[i][1] - coords[i - 1][1]
    cum.push(cum[i - 1] + Math.hypot(dl * 111320, dn * 110574))
  }
  return cum
}

export const DEFAULTS = {
  seed: 20261024,
  startMin: 5 * 60,       // operating day, 05:00
  endMin: 24 * 60,        // 24:00
  loadTarget: 0.9,        // depart at this share of seats
  extraBusQueue: 25,      // a stop this far over the line needs help
  extraBusHoldMin: 3,     // ... for this many consecutive minutes
  extraBusDueWithin: 8,   // ... and nothing is due within this many minutes
  maxExtraBuses: 8,
  minHeadway: 4,
  maxHeadway: 15,   // service guarantee: no stop waits more than this in the peak
  maxTransfers: 2,        // feeder -> trunk -> feeder is a normal journey
  maxTransferWait: 25,
}

/**
 * @param {object} input
 * @param {Array} input.stops   [{stop_id, name, lat, lon, island}]
 * @param {Array} input.routes  [{route_id, name, service_class, seats, max_passengers,
 *                                stops:[stop_id], legs:[{from_id,to_id,length_m,minutes,coords}]}]
 * @param {Array} input.demand  [{stop_id, hour, boardings}]
 * @param {Array} input.od      [{origin_stop_id, dest_stop_id, rides_per_day}]
 * @param {object} [input.options]
 */
export function createSimulation(input) {
  const options = { ...DEFAULTS, ...(input.options || {}) }
  const stops = input.stops
  const nStops = stops.length
  const stopIdx = new Map(stops.map((s, i) => [s.stop_id, i]))

  // ---- routes in travel order, both directions -------------------------
  const routes = input.routes.map((r, routeIndex) => {
    const order = r.stops.map((id) => stopIdx.get(id))
    const legs = r.legs.map((l) => {
      const coords = l.coords.map(([lon, lat]) => [lat, lon])
      return { ...l, coords, cum: cumulative(coords) }
    })
    const revLegs = [...legs].reverse().map((l) => {
      const coords = [...l.coords].reverse()
      return { ...l, coords, cum: cumulative(coords) }
    })
    return {
      ...r,
      routeIndex,
      order,
      legsByDir: { 1: legs, [-1]: revLegs },
      seqByDir: { 1: order, [-1]: [...order].reverse() },
      orderOf: new Map(order.map((s, i) => [s, i])),
      // a closed circuit (ends where it starts) keeps circulating the same way
      // round instead of reversing at the terminal
      closed: order.length > 2 && order[0] === order[order.length - 1],
      capacity: r.max_passengers || r.seats,
      seats: r.seats,
    }
  })

  const routesAtStop = Array.from({ length: nStops }, () => [])
  routes.forEach((r) => {
    for (const s of new Set(r.order)) routesAtStop[s].push(r.routeIndex)
  })

  // ---- demand ---------------------------------------------------------
  const demand = Array.from({ length: nStops }, () => new Array(24).fill(0))
  for (const d of input.demand) {
    const i = stopIdx.get(d.stop_id)
    if (i !== undefined && d.hour >= 0 && d.hour < 24) demand[i][d.hour] += Number(d.boardings) || 0
  }

  const odRows = Array.from({ length: nStops }, () => [])
  for (const row of input.od) {
    const o = stopIdx.get(row.origin_stop_id)
    const d = stopIdx.get(row.dest_stop_id)
    if (o === undefined || d === undefined || o === d) continue
    const w = Number(row.rides_per_day) || 0
    if (w > 0) odRows[o].push({ dest: d, w })
  }

  // ---- journey planning: direct, then up to `maxTransfers` changes ------
  const directCache = new Map()
  function directLegs(o, d) {
    const key = o * nStops + d
    if (directCache.has(key)) return directCache.get(key)
    let legs = null
    for (const ri of routesAtStop[o]) {
      const route = routes[ri]
      const from = route.orderOf.get(o)
      const to = route.orderOf.get(d)
      if (from === undefined || to === undefined || from === to) continue
      const dir = to > from ? 1 : -1
      const mins = legMinutes(route, from, to, dir) + headwayEstimate(ri) / 2
      if (!legs || mins < legs.mins) legs = { mins, path: [{ route: ri, dir, to: d }] }
    }
    directCache.set(key, legs)
    return legs
  }

  function headwayEstimate(ri) {
    // expected wait on a leg, at the peak hour, from the published or planned
    // service. Used only to choose between candidate journeys.
    return headwayFor(routes[ri], 17)
  }

  function legMinutes(route, fromPos, toPos, dir) {
    const seq = route.seqByDir[dir]
    const a = dir > 0 ? fromPos : seq.length - 1 - fromPos
    const b = dir > 0 ? toPos : seq.length - 1 - toPos
    const legs = route.legsByDir[dir]
    let m = 0
    for (let k = Math.min(a, b); k < Math.max(a, b); k++) m += legs[k]?.minutes || 0
    return m
  }

  const journeyCache = new Map()
  function planJourney(o, d, transfers = options.maxTransfers) {
    const key = `${o}:${d}:${transfers}`
    if (journeyCache.has(key)) return journeyCache.get(key)
    let best = directLegs(o, d) || null
    if (transfers > 0) {
      for (const ri of routesAtStop[o]) {
        const r1 = routes[ri]
        const oPos = r1.orderOf.get(o)
        for (const tIdx of r1.order) {
          if (tIdx === o || tIdx === d) continue
          const rest = planJourney(tIdx, d, transfers - 1)
          if (!rest || rest.path[0].route === ri) continue
          const tOrder = r1.orderOf.get(tIdx)
          const dir = tOrder > oPos ? 1 : -1
          const mins = legMinutes(r1, oPos, tOrder, dir) + headwayEstimate(ri) / 2 + rest.mins
          if (!best || mins < best.mins) {
            best = { mins, path: [{ route: ri, dir, to: tIdx }, ...rest.path] }
          }
        }
      }
    }
    journeyCache.set(key, best)
    return best
  }

  // ---- the day's passengers, generated once ----------------------------
  function poissonKnuth(lambda, rng) {
    const L = Math.exp(-lambda)
    let k = 0
    let p = 1
    do {
      k++
      p *= rng()
    } while (p > L && k < 200)
    return k - 1
  }

  function gauss(rng) {
    return Math.sqrt(-2 * Math.log(rng() || 1e-9)) * Math.cos(2 * Math.PI * rng())
  }

  function pickDest(rows, wsum, rng) {
    if (!rows.length || wsum <= 0) return null
    let x = rng() * wsum
    for (const r of rows) {
      x -= r.w
      if (x <= 0) return r.dest
    }
    return rows[rows.length - 1].dest
  }

  let arrivals = []
  let totalDemand = 0
  function buildArrivals() {
    const rng = mulberry32(options.seed)
    arrivals = Array.from({ length: nStops }, () => [])
    let total = 0
    for (let i = 0; i < nStops; i++) {
      const rows = odRows[i]
      const wsum = rows.reduce((a, b) => a + b.w, 0)
      for (let h = 0; h < 24; h++) {
        const base = demand[i][h]
        if (base <= 0) continue
        const n = base < 30 ? poissonKnuth(base, rng) : Math.max(0, Math.round(base + Math.sqrt(base) * gauss(rng)))
        for (let k = 0; k < n; k++) {
          const t = h * HOUR + rng() * HOUR
          if (t < options.startMin || t >= options.endMin) continue
          const dest = pickDest(rows, wsum, rng)
          if (dest === null) continue
          arrivals[i].push({ t, dest })
          total++
        }
      }
      arrivals[i].sort((a, b) => a.t - b.t)
    }
    return total
  }

  // ---- state ----------------------------------------------------------
  let state
  let busSeq = 0

  function reset() {
    state = {
      clock: options.startMin,
      queues: Array.from({ length: nStops }, () => []),
      cursor: new Array(nStops).fill(0),
      buses: [],
      lastDeparture: new Map(),
      departures: [],
      extraDispatched: 0,
      events: [],
      boarded: 0,
      noDirect: 0,
      tripsCompleted: 0,
      waits: [],
      journeys: [],
      peakLoad: 0,
      peakQueue: new Array(nStops).fill(0),
      firstBus: new Array(nStops).fill(null),
      extraAtStop: new Array(nStops).fill(0),
      boardedAt: new Array(nStops).fill(0),
      longWaitAt: new Array(nStops).fill(0),
      alightedAt: new Array(nStops).fill(0),
      transfers: 0,
      routeHour: new Map(),
      peakLoadByRoute: new Map(),
      overSince: new Array(nStops).fill(null),
      busHours: 0,
      tripsRun: 0,
      dwell: 0,
    }
    busSeq = 0
    state.totalDemand = buildArrivals()
    totalDemand = state.totalDemand

    for (const r of routes) {
      const n = Math.max(1, Math.round(r.buses_required || 1))
      for (let k = 0; k < n; k++) {
        state.buses.push(makeBus(r, k % 2 === 0 ? 1 : -1, true))
      }
    }
  }

  function makeBus(route, dir, waiting) {
    return {
      id: `B${++busSeq}`,
      routeId: route.route_id,
      routeIndex: route.routeIndex,
      route,
      dir,
      pos: 0,
      leg: null,
      legProgress: 0,
      state: waiting ? 'waiting' : 'moving',
      occupancy: 0,
      onboard: [],
      extra: false,
      departedAt: null,
    }
  }

  // ---- geometry -------------------------------------------------------
  function busPosition(bus) {
    const route = bus.route
    if (bus.state === 'moving' && bus.leg) {
      const p = pointAt(bus.leg.coords, bus.leg.cum, bus.legProgress)
      if (p) return p
    }
    return [stops[route.seqByDir[bus.dir][bus.pos]].lat, stops[route.seqByDir[bus.dir][bus.pos]].lon]
  }

  function busNextStop(bus) {
    const seq = bus.route.seqByDir[bus.dir]
    const k = Math.min(bus.pos + (bus.state === 'moving' ? 1 : 0), seq.length - 1)
    return stops[seq[k]]
  }

  function etaTo(bus, stopIdxTarget) {
    const route = bus.route
    const seq = route.seqByDir[bus.dir]
    const start = bus.pos + (bus.state === 'moving' ? 1 : 0)
    for (let k = start; k < seq.length; k++) {
      if (seq[k] !== stopIdxTarget) continue
      let mins = 0
      if (bus.state === 'moving' && bus.leg) mins += bus.leg.minutes * (1 - bus.legProgress)
      const legs = route.legsByDir[bus.dir]
      for (let j = start; j < k; j++) mins += legs[j]?.minutes || 0
      return mins
    }
    return Infinity
  }

  // ---- demand-derived headway -----------------------------------------
  function headwayFor(route, hour) {
    const h = clamp(hour, 0, 23)
    // The baseline network keeps its published timetable. Only the reroute is
    // demand-dispatched, and saying so is the point of the comparison.
    if (route.fixed_headways) {
      const v = route.fixed_headways[h]
      if (v != null && v > 0) return clamp(v, 1, 240)
    }
    let pax = 0
    for (const s of route.order) pax += demand[s][h]
    const perDirection = pax / 2
    if (perDirection <= 0) return options.maxHeadway
    const departures = Math.ceil(perDirection / (route.seats * options.loadTarget))
    return clamp(60 / Math.max(1, departures), options.minHeadway, options.maxHeadway)
  }

  // ---- boarding --------------------------------------------------------
  function wants(bus, p) {
    const leg = p.path[p.leg]
    return leg && leg.route === bus.routeIndex && leg.dir === bus.dir
  }

  function alightAndBoard(bus, stopIdxHere, clock) {
    // alight, or transfer
    if (bus.onboard.length) {
      const keep = []
      for (const p of bus.onboard) {
        if (p.path[p.leg].to !== stopIdxHere) {
          keep.push(p)
          continue
        }
        p.leg++
        if (p.leg >= p.path.length) {
          // Total wait is every minute spent standing at a stop, summed over
          // each leg. Journey time is arrival to final alighting. They are
          // different questions and the panel must not conflate them: a single
          // long through-ride is not "waiting 40 minutes".
          state.waits.push(p.waited)
          state.journeys.push(clock - p.t0)
          state.alightedAt[stopIdxHere]++
          state.tripsCompleted++
        } else {
          state.transfers++
          p.tQueued = clock
          state.queues[stopIdxHere].push(p)
        }
      }
      bus.onboard = keep
    }
    bus.occupancy = bus.onboard.length

    if (state.firstBus[stopIdxHere] === null) {
      state.firstBus[stopIdxHere] = { at: clock, route: bus.routeId, direction: bus.dir }
    }

    const queue = state.queues[stopIdxHere]
    if (!queue.length) return
    const capacity = bus.route.capacity
    const remaining = []
    let wrote = 0
    for (const p of queue) {
      if (bus.onboard.length < capacity && wants(bus, p)) {
        const waitedHere = clock - p.tQueued
        p.waited += waitedHere
        // A stop where people stood for more than ten minutes is a stop that
        // was under-served, whatever the average says. This is the per-stop
        // signal the extra-bus flag is built on.
        if (waitedHere > 10) state.longWaitAt[stopIdxHere]++
        bus.onboard.push(p)
        state.boarded++
        state.boardedAt[stopIdxHere]++
        wrote++
      } else {
        remaining.push(p)
      }
    }
    state.queues[stopIdxHere] = remaining
    bus.occupancy = bus.onboard.length
    const load = bus.onboard.length / bus.route.seats
    if (load > state.peakLoad) state.peakLoad = load
    const rk = bus.route.route_id
    if (!state.peakLoadByRoute.has(rk) || load > state.peakLoadByRoute.get(rk)) state.peakLoadByRoute.set(rk, load)
    if (wrote) {
      const hour = Math.floor(clock / HOUR)
      const key = `${rk}:${hour}`
      const row = state.routeHour.get(key) || { route: rk, hour, boarded: 0, departures: 0, peakLoad: 0 }
      row.boarded += wrote
      row.peakLoad = Math.max(row.peakLoad, load)
      state.routeHour.set(key, row)
    }
  }

  // ---- dispatch --------------------------------------------------------
  function departureDue(bus, clock) {
    // a spare was sent to a stop that was drowning; it does not then wait out
    // the timetable that caused the problem
    if (bus.extra) return true
    const route = bus.route
    const hour = Math.floor(clock / HOUR)
    const key = `${route.route_id}:${bus.dir}`
    const last = state.lastDeparture.get(key)
    if (last === undefined) return true
    if (clock - last >= headwayFor(route, hour)) return true
    const seq = route.seqByDir[bus.dir]
    const q = state.queues[seq[bus.pos]]?.length || 0
    return q >= route.seats * options.loadTarget
  }

  function markDeparture(bus, clock) {
    const key = `${bus.route.route_id}:${bus.dir}`
    state.lastDeparture.set(key, clock)
    state.departures.push({ route: bus.routeId, dir: bus.dir, at: clock, extra: !!bus.extra })
    state.tripsRun++
    bus.departedAt = clock
    const hour = Math.floor(clock / HOUR)
    const row = state.routeHour.get(`${bus.routeId}:${hour}`)
      || { route: bus.routeId, hour, boarded: 0, departures: 0, peakLoad: 0 }
    row.departures += 1
    state.routeHour.set(`${bus.routeId}:${hour}`, row)
    // Board the queue AT the terminal before pulling out. Without this a bus
    // leaves the stop where its demand is greatest and the queue can never
    // clear - the bug is invisible in the aggregate and obvious here.
    const seq = bus.route.seqByDir[bus.dir]
    alightAndBoard(bus, seq[bus.pos], clock)
    bus.state = 'moving'
    bus.legProgress = 0
    bus.leg = bus.route.legsByDir[bus.dir][bus.pos] || null
    if (!bus.leg) bus.state = 'waiting'
  }

  // ---- one simulated minute --------------------------------------------
  function tick() {
    const clock = state.clock

    // 1. passengers appear, and get a journey plan
    for (let i = 0; i < nStops; i++) {
      const list = arrivals[i]
      let c = state.cursor[i]
      while (c < list.length && list[c].t <= clock) {
        const journey = planJourney(i, list[c].dest)
        if (!journey) {
          state.noDirect++
        } else {
          state.queues[i].push({ path: journey.path, leg: 0, t0: list[c].t, tQueued: list[c].t, waited: 0, dest: list[c].dest })
        }
        c++
      }
      state.cursor[i] = c
      if (state.queues[i].length > state.peakQueue[i]) state.peakQueue[i] = state.queues[i].length
    }

    // 2. buses move
    for (const bus of state.buses) {
      if (bus.state === 'waiting') {
        if (departureDue(bus, clock)) markDeparture(bus, clock)
        continue
      }
      if (bus.state !== 'moving' || !bus.leg) continue
      bus.legProgress += 1 / Math.max(1, bus.leg.minutes)
      state.busHours += 1 / 60
      if (bus.legProgress < 1) continue

      const seq = bus.route.seqByDir[bus.dir]
      const si = seq[Math.min(bus.pos + 1, seq.length - 1)]
      bus.pos = Math.min(bus.pos + 1, seq.length - 1)
      bus.legProgress = 0
      bus.leg = null
      alightAndBoard(bus, si, clock)

      if (bus.pos >= seq.length - 1) {
        if (!bus.route.closed) bus.dir = bus.dir > 0 ? -1 : 1
        bus.pos = 0
        bus.state = 'waiting'
      } else {
        bus.leg = bus.route.legsByDir[bus.dir][bus.pos]
        bus.state = bus.leg ? 'moving' : 'waiting'
      }
    }

    // 3. spare-bus rule
    if (state.extraDispatched < options.maxExtraBuses) {
      for (let i = 0; i < nStops; i++) {
        const q = state.queues[i].length
        if (q < options.extraBusQueue) {
          state.overSince[i] = null
          continue
        }
        if (state.overSince[i] === null) state.overSince[i] = clock
        if (clock - state.overSince[i] < options.extraBusHoldMin) continue
        const due = state.buses
          .filter((b) => b.route.orderOf.has(i))
          .reduce((m, b) => Math.min(m, etaTo(b, i)), Infinity)
        if (due <= options.extraBusDueWithin) continue
        const ri = routesAtStop[i][0]
        if (ri === undefined) continue
        const route = routes[ri]
        const first = route.seqByDir[1][0]
        const last = route.seqByDir[1][route.seqByDir[1].length - 1]
        const bus = makeBus(route, Math.abs(first - i) <= Math.abs(last - i) ? 1 : -1, true)
        bus.extra = true
        bus.pos = 0
        state.buses.push(bus)
        state.extraDispatched++
        state.extraAtStop[i]++
        state.events.push({ clock, stop: stops[i].stop_id, route: route.route_id, queue: q, kind: 'extra_bus' })
        state.overSince[i] = null
        break
      }
    }

    state.clock = Math.min(state.clock + 1, options.endMin)
  }

  // ---- public API ------------------------------------------------------
  let pending = 0
  function step(minutes) {
    // Fractional frames accumulate: a 10x replay advances 0.16 min per 60 fps
    // frame, so the engine must hold the remainder rather than drop it.
    pending += Math.max(0, minutes)
    while (pending >= 1 && state.clock < options.endMin) {
      tick()
      pending -= 1
    }
    if (state.clock >= options.endMin) pending = 0
    return state.clock
  }

  function finish() {
    while (state.clock < options.endMin) tick()
    return summary()
  }

  function summary() {
    const sorted = [...state.waits].sort((a, b) => a - b)
    const mean = sorted.length ? sorted.reduce((a, b) => a + b, 0) / sorted.length : null
    const p90 = sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))] : null
    const js = [...state.journeys].sort((a, b) => a - b)
    const meanJourney = js.length ? js.reduce((a, b) => a + b, 0) / js.length : null
    const p90Journey = js.length ? js[Math.min(js.length - 1, Math.floor(js.length * 0.9))] : null
    const leftBehind = state.queues.reduce((a, q) => a + q.length, 0)
    const demandTotal = totalDemand
    const active = state.buses.filter((b) => !b.extra).length
    return {
      dayStart: options.startMin,
      dayEnd: options.endMin,
      boarded: state.boarded,
      completed: state.tripsCompleted,
      transfers: state.transfers,
      leftBehind,
      noDirectService: state.noDirect,
      demandTotal,
      served: state.tripsCompleted,
      leftBehindPct: demandTotal ? (leftBehind / demandTotal) * 100 : 0,
      unservedPct: demandTotal ? ((leftBehind + state.noDirect) / demandTotal) * 100 : 0,
      meanWaitMin: mean,
      p90WaitMin: p90,
      meanJourneyMin: meanJourney,
      p90JourneyMin: p90Journey,
      journeysCompleted: js.length,
      peakLoadPct: state.peakLoad * 100,
      peakQueue: Math.max(...state.peakQueue),
      buses: active,
      extraBuses: state.extraDispatched,
      busHours: state.busHours,
      tripsRun: state.tripsRun,
      boardedByStop: state.boardedAt.slice(),
      alightedByStop: state.alightedAt.slice(),
      peakQueueByStop: state.peakQueue.slice(),
      firstBusByStop: state.firstBus.map((f) => (f ? { ...f } : null)),
      extraByStop: state.extraAtStop.slice(),
      longWaitByStop: state.longWaitAt.slice(),
      peakLoadByRoute: Object.fromEntries(state.peakLoadByRoute),
      routeHour: [...state.routeHour.values()].sort((a, b) => a.route.localeCompare(b.route) || a.hour - b.hour),
      events: state.events.slice(),
    }
  }

  /**
   * Drop a bank of extra passengers on a stop, now. Used by the "+ flight bank"
   * stress button: it is not part of the modelled day, and it is the quickest
   * way to see whether the dispatch rule actually responds.
   */
  function inject(stopIdxTarget, count, rngSeed = 1) {
    const rng = mulberry32(rngSeed)
    const rows = odRows[stopIdxTarget]
    const wsum = rows.reduce((a, b) => a + b.w, 0)
    let added = 0
    for (let k = 0; k < count; k++) {
      const dest = pickDest(rows, wsum, rng)
      if (dest === null) continue
      const journey = planJourney(stopIdxTarget, dest)
      if (!journey) continue
      state.queues[stopIdxTarget].push({ path: journey.path, leg: 0, t0: state.clock, tQueued: state.clock, waited: 0, dest })
      added++
    }
    totalDemand += added
    return added
  }

  /** Every bus that will reach this stop, soonest first. */  function nextArrivals(stopIdxTarget, limit = 4) {
    const out = []
    for (const bus of state.buses) {
      if (!bus.route.orderOf.has(stopIdxTarget)) continue
      const eta = etaTo(bus, stopIdxTarget)
      if (!Number.isFinite(eta)) continue
      out.push({
        route: bus.routeId,
        etaMin: eta,
        occupancy: bus.occupancy,
        seats: bus.route.seats,
        extra: bus.extra,
      })
    }
    out.sort((a, b) => a.etaMin - b.etaMin)
    return out.slice(0, limit)
  }

  function snapshot() {
    return {
      clock: state.clock,
      clockLabel: `${String(Math.floor(state.clock / 60)).padStart(2, '0')}:${String(Math.floor(state.clock % 60)).padStart(2, '0')}`,
      buses: state.buses.map((b) => {
        const p = busPosition(b)
        return {
          id: b.id,
          routeId: b.route.route_id,
          service: b.route.service_class,
          lat: p[0],
          lon: p[1],
          occupancy: b.occupancy,
          seats: b.route.seats,
          load: b.occupancy / b.route.seats,
          moving: b.state === 'moving',
          extra: b.extra,
          nextStop: busNextStop(b)?.name ?? '',
        }
      }),
      queues: state.queues.map((q) => q.length),
      firstBus: state.firstBus,
      extraAtStop: state.extraAtStop,
    }
  }

  reset()

  return {
    options,
    stops,
    routes,
    reset,
    step,
    finish,
    summary,
    snapshot,
    nextArrivals,
    headwayFor,
    planJourney,
    inject,
    stopIndex: stopIdx,
    get clock() {
      return state.clock
    },
    get events() {
      return state.events
    },
    get departures() {
      return state.departures
    },
    get totalDemand() {
      return totalDemand
    },
    get remaining() {
      return state.queues.reduce((a, q) => a + q.length, 0)
    },
  }
}
