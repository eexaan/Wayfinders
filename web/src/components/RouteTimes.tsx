import { useMemo, useState } from 'react'

import { fmtClock, type RerouteData } from '../reroute'
import { routeColour } from '../routeStyle'
import type { createSimulation } from '../sim/engine.mjs'

type Sim = ReturnType<typeof createSimulation>

/**
 * Every route and its bus times for the modelled day.
 *
 * There is no published timetable, so the times are the departures the
 * dispatcher actually made in a full-day run of the same simulation, read from
 * each route's starting stop. Click a route for every departure, by hour.
 */
export function RouteTimes({ data, makeSim }: { data: RerouteData; makeSim: () => Sim }) {
  const [open, setOpen] = useState<string | null>(null)

  const rows = useMemo(() => {
    const sim = makeSim()
    sim.finish()
    const byId = new Map(data.stops.map((s) => [s.id, s.name]))
    return data.routes.map((r) => {
      const legs = data.legs[r.id] ?? []
      const tripMin = legs.reduce((a, l) => a + l.minutes, 0)
      const loop = r.stops.length > 2 && r.stops[0] === r.stops[r.stops.length - 1]
      const deps = sim.departures.filter((d) => d.route === r.id)
      const dirs = [1, -1].map((dir) => {
        const times = deps.filter((d) => d.dir === dir).map((d) => d.at).sort((a, b) => a - b)
        const gaps = times.slice(1).map((t, i) => t - times[i]).sort((a, b) => a - b)
        const from = byId.get(dir > 0 ? r.stops[0] : r.stops[r.stops.length - 1]) ?? ''
        return {
          dir,
          label: loop ? `${from} (${dir > 0 ? 'one way round' : 'other way round'})` : `from ${from}`,
          times,
          first: times[0] ?? null,
          last: times[times.length - 1] ?? null,
          gap: gaps.length ? gaps[Math.floor(gaps.length / 2)] : null,
        }
      })
      return { r, loop, tripMin, trips: deps.length, dirs }
    })
  }, [data, makeSim])

  return (
    <div className="card stop-board route-times">
      <div className="board-head">
        <h2 className="card-h">Every route: bus times for the day</h2>
        <p className="card-sub">
          Departures the dispatcher made in the full-day run (05:00–00:00). "Every" is the typical gap between buses.
          Click a route for every departure.
        </p>
      </div>

      <div className="board-scroll">
        <table className="board">
          <thead>
            <tr>
              <th>Route</th>
              <th>Direction</th>
              <th className="num">Stops</th>
              <th className="num">Trip</th>
              <th className="num">Buses</th>
              <th className="num">First bus</th>
              <th className="num">Last bus</th>
              <th className="num">Every</th>
              <th className="num">Trips</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ r, loop, tripMin, dirs }) => {
              const isOpen = open === r.id
              return [
                ...dirs.map((d, k) => (
                  <tr key={`${r.id}:${d.dir}`} className={isOpen ? 'sel' : ''} onClick={() => setOpen(isOpen ? null : r.id)}>
                    {k === 0 && (
                      <td rowSpan={2}>
                        <b style={{ color: routeColour(r.id) }}>{r.id}</b> {loop && <small>loop</small>}
                        <br />
                        <small>{r.name}</small>
                      </td>
                    )}
                    <td>
                      <small>{d.label}</small>
                    </td>
                    {k === 0 && (
                      <>
                        <td className="num" rowSpan={2}>{r.stops.length - (loop ? 1 : 0)}</td>
                        <td className="num" rowSpan={2}>{Math.round(tripMin)} min</td>
                        <td className="num" rowSpan={2}>{r.buses}</td>
                      </>
                    )}
                    <td className="num">{fmtClock(d.first)}</td>
                    <td className="num">{fmtClock(d.last)}</td>
                    <td className="num">{d.gap === null ? '—' : `${Math.round(d.gap)} min`}</td>
                    <td className="num">{d.times.length}</td>
                  </tr>
                )),
                isOpen && (
                  <tr key={`${r.id}:all`} className="sel">
                    <td colSpan={9}>
                      {dirs.map((d) => (
                        <div key={d.dir} className="route-times-all">
                          <b>{d.label}</b>
                          <div>
                            {d.times.length ? d.times.map((t) => fmtClock(t)).join('  ·  ') : 'no departures'}
                          </div>
                        </div>
                      ))}
                    </td>
                  </tr>
                ),
              ]
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
