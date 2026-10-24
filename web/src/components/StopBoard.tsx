import { useMemo, useState } from 'react'

import { fmtClock, type RerouteData } from '../reroute'
import type { createSimulation } from '../sim/engine.mjs'

type Sim = ReturnType<typeof createSimulation>

type SortKey = 'first' | 'queue' | 'extra' | 'name' | 'population'

/**
 * The deliverable, as a table: every new stop, the first bus of the day, what is
 * waiting there now, and whether the day needed an extra bus.
 *
 * The "first bus" column comes from the headless run so it is stable while the
 * clock moves; the "now" columns come from the live simulation.
 */
export function StopBoard({
  data,
  sim,
  clock,
  selected,
  onSelect,
}: {
  data: RerouteData
  sim: Sim
  clock: number
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  const [sort, setSort] = useState<SortKey>('extra')
  const [onlyExtra, setOnlyExtra] = useState(false)

  const snap = useMemo(() => sim.snapshot(), [sim, clock])

  const rows = useMemo(() => {
    const out = data.stops.map((s, i) => ({
      ...s,
      now: snap.queues[i] ?? 0,
      next: sim.nextArrivals(i, 2),
    }))
    const cmp: Record<SortKey, (a: typeof out[0], b: typeof out[0]) => number> = {
      extra: (a, b) => Number(b.needsExtra) - Number(a.needsExtra) || b.peakQueue - a.peakQueue,
      queue: (a, b) => b.now - a.now,
      first: (a, b) => (a.firstBusAt ?? 1e9) - (b.firstBusAt ?? 1e9),
      name: (a, b) => a.name.localeCompare(b.name),
      population: (a, b) => b.population - a.population,
    }
    return out.sort(cmp[sort])
  }, [data, sim, snap, sort])

  const shown = onlyExtra ? rows.filter((r) => r.needsExtra) : rows
  const extraCount = rows.filter((r) => r.needsExtra).length

  return (
    <div className="card stop-board">
      <div className="board-head">
        <h2 className="card-h">Every stop: first bus, queue, and whether it needs another bus</h2>
        <p className="card-sub">
          First bus comes from the full-day run. "Now" follows the clock.
        </p>
      </div>

      <div className="board-filters">
        <button className={onlyExtra ? 'on' : ''} onClick={() => setOnlyExtra(!onlyExtra)}>
          Needs an extra bus ({extraCount})
        </button>
        <span className="board-sort">
          Sort
          {(['extra', 'queue', 'first', 'population', 'name'] as SortKey[]).map((k) => (
            <button key={k} aria-pressed={sort === k} onClick={() => setSort(k)}>
              {k === 'first' ? 'first bus' : k}
            </button>
          ))}
        </span>
      </div>

      <div className="board-scroll">
        <table className="board">
          <thead>
            <tr>
              <th>Stop</th>
              <th>Routes</th>
              <th className="num">First bus</th>
              <th className="num">Next</th>
              <th className="num">Queue</th>
              <th className="num">Peak</th>
              <th>Extra bus</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((s) => (
              <tr
                key={s.id}
                className={selected === s.id ? 'sel' : ''}
                onClick={() => onSelect(selected === s.id ? null : s.id)}
              >
                <td>
                  <b>{s.name}</b>
                  <br />
                  <small>
                    {s.island}
                    {s.hotspots > 0 && ` · ${s.hotspots} hotspot${s.hotspots === 1 ? '' : 's'}`}
                    {s.interchange && ' · interchange'}
                  </small>
                </td>
                <td className="board-routes">{s.routes.join(' ') || '—'}</td>
                <td className="num">
                  {s.firstBusAt === null ? '—' : fmtClock(s.firstBusAt)}
                  <br />
                  <small>{s.firstBusRoute}</small>
                </td>
                <td className="num">
                  {s.next.length ? `${Math.round(s.next[0].etaMin)} min` : '—'}
                  <br />
                  <small>{s.next[0]?.route ?? ''}</small>
                </td>
                <td className={`num${s.now >= 25 ? ' hot' : ''}`}>{s.now || ''}</td>
                <td className={`num${s.peakQueue >= 25 ? ' hot' : ''}`}>{s.peakQueue || ''}</td>
                <td>
                  {s.needsExtra ? (
                    <span className="badge-extra" title={s.reason || `peak queue ${s.peakQueue}`}>
                      {s.extraBuses > 0 ? `+${s.extraBuses} bus` : 'needs one'}
                    </span>
                  ) : (
                    <span className="badge-ok">no</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
