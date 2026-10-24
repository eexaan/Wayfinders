import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { loadReroute, type RerouteData } from '../reroute'
import { createSimulation } from '../sim/engine.mjs'
import { RerouteMap } from './RerouteMap'
import { RouteTimes } from './RouteTimes'
import { SimControls } from './SimControls'
import { StopBoard } from './StopBoard'
import { Scoreboard } from './Scoreboard'

const START_MIN = 5 * 60
const END_MIN = 24 * 60

/**
 * #reroute — a replacement network for Malé, Hulhulé and Hulhumalé, animated.
 *
 * The clock is the only React state that changes per frame. The simulation is an
 * imperative object kept in a ref, advanced by a single requestAnimationFrame
 * loop, and read once per repaint: putting 63 stops and 60 buses into React
 * state on every frame is what makes this kind of view stutter.
 */
export function ReroutePage({ seed, onSeed }: { seed: number; onSeed: (n: number) => void }) {
  const [data, setData] = useState<RerouteData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadReroute().then(setData, (e) => setError(String(e)))
  }, [])

  const makeSim = useCallback(() => {
    if (!data) throw new Error('reroute data not loaded')
    return createSimulation({
      stops: data.stops.map((s) => ({ stop_id: s.id, name: s.name, lat: s.lat, lon: s.lon, island: s.island })),
      routes: data.routes.map((r) => ({
        route_id: r.id,
        name: r.name,
        service_class: r.service,
        seats: r.seats,
        max_passengers: r.seats,
        buses_required: r.buses,
        stops: r.stops,
        legs: (data.legs[r.id] ?? []).map((l) => ({
          from_id: l.from,
          to_id: l.to,
          length_m: l.lengthM,
          minutes: l.minutes,
          coords: l.coords.map(([lat, lon]) => [lon, lat]),
        })),
      })),
      demand: data.demand,
      od: data.od,
      options: { seed, startMin: START_MIN, endMin: END_MIN },
    })
  }, [data, seed])
  const sim = useMemo(() => (data ? makeSim() : null), [data, makeSim])

  const [clock, setClock] = useState(START_MIN)
  const [boardClock, setBoardClock] = useState(START_MIN)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)
  const [showOld, setShowOld] = useState(false)
  const [showHotspots, setShowHotspots] = useState(true)
  const [showBuses, setShowBuses] = useState(true)
  const [density, setDensity] = useState(0)

  const speedRef = useRef(speed)
  speedRef.current = speed
  const countRef = useRef(0)

  useEffect(() => {
    if (!sim) return
    setClock(sim.clock)
    setBoardClock(sim.clock)
    setPlaying(false)
  }, [sim])

  // A fixed 100 ms tick rather than requestAnimationFrame: rAF stops entirely
  // in a background tab, so a replay would freeze when the user switched away.
  // Each tick advances by the time that ACTUALLY elapsed, not by the nominal
  // interval, because a throttled background tab fires far less often than the
  // interval asks - so the clock keeps real time instead of crawling.
  useEffect(() => {
    if (!sim || !playing) return
    let last = performance.now()
    const id = window.setInterval(() => {
      const now = performance.now()
      const dtSec = Math.min(3, (now - last) / 1000)
      last = now
      // 1x advances one simulated minute per real second; 10x advances ten.
      sim.step(dtSec * speedRef.current)
      setClock(sim.clock)
      setDensity(sim.remaining)
      countRef.current += 1
      if (countRef.current % 5 === 0) setBoardClock(sim.clock)
      if (sim.clock >= END_MIN) setPlaying(false)
    }, 100)
    return () => window.clearInterval(id)
  }, [sim, playing])

  if (error) {
    return (
      <main>
        <p className="loading">Could not load the reroute data: {error}</p>
        <p className="loading">
          The builder writes it: <code>make reroute</code>.
        </p>
      </main>
    )
  }
  if (!data || !sim) return <p className="loading">Loading the new network…</p>

  const sync = () => {
    setClock(sim.clock)
    setBoardClock(sim.clock)
    setDensity(sim.remaining)
  }

  const scrub = (min: number) => {
    setPlaying(false)
    // stepping backwards restarts the day; a simulation is not reversible
    if (min < sim.clock) sim.reset()
    sim.step(min - sim.clock)
    sync()
  }

  const reset = () => {
    setPlaying(false)
    sim.reset()
    sync()
  }

  const skip = () => {
    setPlaying(false)
    sim.finish()
    sync()
  }

  const flights = () => {
    // A stress test: a bank of arrivals lands at VIA. It is not part of the
    // modelled day, which is why it is a button and not a default.
    const via = data.stops.findIndex((s) => s.island === 'Hulhulé')
    if (via >= 0) sim.inject(via, 60, Math.floor(sim.clock))
    setClock(sim.clock + 0.0001)
  }

  return (
    <main className="reroute">
      <div className="reroute-head">
        <div>
          <h2>
            Reroute: {data.stops.length} stops, {data.routes.length} routes, no timetable
          </h2>
          <p>
            Malé and the airport island keep <b>today's routes and stops, unchanged</b> — its streets are already
            close to what the roads allow. Hulhumalé is served by <b>closed circuits</b> over new stops in the
            filled-in blocks, and the cross-island buses run through one of them. The day is dispatched from
            demand, so there is no fixed timetable: the bus times below are what the dispatcher ran on the modelled day.
          </p>
        </div>
        <div className="reroute-scope">
          <b>Kept</b> Malé · airport, today's routes
          <br />
          <b>Loops</b> Hulhumalé, new stops
          <br />
          <b>Unchanged</b> Villimalé (R13/R14)
        </div>
      </div>

      <div className="reroute-grid">
        <section className="card map-card" aria-label="Reroute map">
          <RerouteMap
            data={data}
            sim={sim}
            clock={clock}
            selectedStop={selected}
            onSelectStop={setSelected}
            showOld={showOld}
            showHotspots={showHotspots}
            showBuses={showBuses}
            onToggleOld={() => setShowOld(!showOld)}
            onToggleHotspots={() => setShowHotspots(!showHotspots)}
            onToggleBuses={() => setShowBuses(!showBuses)}
          />
        </section>

        <div className="reroute-side">
          <SimControls
            clock={clock}
            startMin={START_MIN}
            endMin={END_MIN}
            playing={playing}
            speed={speed}
            seed={seed}
            onPlay={() => setPlaying(!playing)}
            onSpeed={setSpeed}
            onScrub={scrub}
            onReset={reset}
            onSeed={onSeed}
            onSkip={skip}
            onFlights={flights}
            density={density}
          />
          <Scoreboard data={data} />
        </div>
      </div>

      <StopBoard data={data} sim={sim} clock={boardClock} selected={selected} onSelect={setSelected} />

      <RouteTimes data={data} makeSim={makeSim} />

      <MethodStrip data={data} />
    </main>
  )
}

function MethodStrip({ data }: { data: RerouteData }) {
  const cov = data.params?.network?.coverage
  const air = data.params?.network?.airport_stream
  return (
    <details className="card method-strip">
      <summary>How the network was built, and what it does not claim</summary>
      <div className="method-cols">
        <div>
          <h3>Stops</h3>
          <p>
            Every 150 m cell gets a population from OSM building footprints × storeys, calibrated to the published
            census total for its island, blended with night-time taxi pickups. Stops are then placed by minimising the
            walking distance to the whole population, with a stop forced within 400 m of every hospital, clinic,
            terminal and office cluster.
          </p>
          {cov && (
            <p className="note">
              Population within a 400 m walk: <b>{Number(cov.population_within_400m_today).toLocaleString()}</b> today,{' '}
              <b>{Number(cov.population_within_400m_reroute).toLocaleString()}</b> after. The gain is small on purpose:
              97% of taxi pickups are already within 300 m of an existing stop, so this network cannot win on coverage.
              It has to win on frequency and reliability — which is what the proof panel measures.
            </p>
          )}
        </div>
        <div>
          <h3>Routes</h3>
          <p>
            Malé keeps the <b>exact committed geometry</b> of R1–R4 and R7–R9, copied leg for leg: no regeneration,
            no snapping, nothing to get wrong. R5 and R6 — the island's old point-to-point locals, whose terminals
            are 781 m apart — are replaced by <b>circuits</b>: the bus leaves the hub, goes round, and returns by a
            different road. Each circuit is built so that no street is driven twice.
          </p>
          <p className="note">
            Every route has its own colour. Where routes share a road they are drawn on top of each other, on the
            road itself. A loop bus keeps going round the same way; it does not turn back at the hub.
          </p>
        </div>
        <div>
          <h3>Dispatch</h3>
          <p>
            There is no timetable. A bus leaves when its demand-derived headway expires or when it reaches 90% of its
            seats, whichever is first. A spare is sent when a stop's queue exceeds 25 for three consecutive minutes and
            nothing is due within eight.
          </p>
          {air && (
            <p className="note">
              Flight arrivals add <b>{Number(air.daily_passengers).toFixed(0)}</b> passengers a day at VIA, using{' '}
              <b>{(Number(air.bus_share_of_arrivals) * 100).toFixed(0)}%</b> of arriving air passengers taking the bus —
              a stated assumption, not a measurement. Both networks receive the same stream.
            </p>
          )}
        </div>
      </div>
      <p className="note">
        Not claimed: vehicle tracking, real-time anything, or that this network is ready to operate. It is a
        demand-derived alternative, simulated on one modelled day so the two networks can be compared on identical
        demand. Villimalé is out of scope and keeps today's service.
      </p>
    </details>
  )
}
