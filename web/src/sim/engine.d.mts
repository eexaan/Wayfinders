// Types for the simulation engine. The implementation is plain .mjs so that
// `node web/scripts/run-sim.mjs` can import it with no build step - the browser
// and the headless proof run must execute identical code.

export interface SimStop {
  stop_id: string
  name: string
  lat: number
  lon: number
  island: string
}

export interface SimLeg {
  from_id: string
  to_id: string
  length_m: number
  minutes: number
  coords: [number, number][] // [lon, lat], GeoJSON order
}

export interface SimRoute {
  route_id: string
  name: string
  service_class: string
  seats: number
  max_passengers?: number
  buses_required: number
  stops: string[]
  legs: SimLeg[]
  fixed_headways?: (number | null)[] | null
}

export interface SimDemand {
  stop_id: string
  hour: number
  boardings: number
}

export interface SimOd {
  origin_stop_id: string
  dest_stop_id: string
  rides_per_day: number
}

export interface SimOptions {
  seed?: number
  startMin?: number
  endMin?: number
  loadTarget?: number
  extraBusQueue?: number
  extraBusHoldMin?: number
  extraBusDueWithin?: number
  maxExtraBuses?: number
  minHeadway?: number
  maxHeadway?: number
  maxTransfers?: number
  maxTransferWait?: number
}

export interface JourneyLeg {
  route: number
  dir: 1 | -1
  to: number
}

export interface Journey {
  mins: number
  path: JourneyLeg[]
}

export interface BusSnapshot {
  id: string
  routeId: string
  service: string
  lat: number
  lon: number
  occupancy: number
  seats: number
  load: number
  moving: boolean
  extra: boolean
  nextStop: string
}

export interface Snapshot {
  clock: number
  clockLabel: string
  buses: BusSnapshot[]
  queues: number[]
  firstBus: ({ at: number; route: string; direction: number } | null)[]
  extraAtStop: number[]
}

export interface Arrival {
  route: string
  etaMin: number
  occupancy: number
  seats: number
  extra: boolean
}

export interface SimEvent {
  clock: number
  stop: string
  route: string
  queue: number
  kind: string
}

export interface RouteHour {
  route: string
  hour: number
  boarded: number
  departures: number
  peakLoad: number
}

export interface SimSummary {
  dayStart: number
  dayEnd: number
  boarded: number
  completed: number
  transfers: number
  leftBehind: number
  noDirectService: number
  demandTotal: number
  served: number
  leftBehindPct: number
  unservedPct: number
  meanWaitMin: number | null
  p90WaitMin: number | null
  peakLoadPct: number
  peakQueue: number
  buses: number
  extraBuses: number
  busHours: number
  tripsRun: number
  boardedByStop: number[]
  alightedByStop: number[]
  peakQueueByStop: number[]
  firstBusByStop: ({ at: number; route: string; direction: number } | null)[]
  extraByStop: number[]
  peakLoadByRoute: Record<string, number>
  routeHour: RouteHour[]
  events: SimEvent[]
}

export interface Simulation {
  options: SimOptions
  stops: SimStop[]
  routes: SimRoute[]
  reset: () => void
  step: (minutes: number) => number
  finish: () => SimSummary
  summary: () => SimSummary
  snapshot: () => Snapshot
  nextArrivals: (stopIdx: number, limit?: number) => Arrival[]
  headwayFor: (route: SimRoute, hour: number) => number
  planJourney: (o: number, d: number) => Journey | null
  inject: (stopIdx: number, count: number, rngSeed?: number) => number
  stopIndex: Map<string, number>
  readonly clock: number
  readonly events: SimEvent[]
  readonly totalDemand: number
  readonly remaining: number
}

export declare function mulberry32(seed: number): () => number

export declare function createSimulation(input: {
  stops: SimStop[]
  routes: SimRoute[]
  demand: SimDemand[]
  od: SimOd[]
  options?: SimOptions
}): Simulation

export declare const DEFAULTS: Required<SimOptions>
