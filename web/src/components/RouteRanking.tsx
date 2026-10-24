import type { Data, Route } from '../data'
import { BAND_COLOUR } from '../colours'

const SCALE_MAX = 120 // % of seats; leaves room past the 100% "full" line

export function RouteRanking({
  data,
  selected,
  onSelect,
}: {
  data: Data
  selected: Route | null
  onSelect: (code: string) => void
}) {
  const ranked = data.routes.filter((r) => r.peakPct !== null).sort((a, b) => b.peakPct! - a.peakPct!)
  const unknown = data.routes.filter((r) => r.peakPct === null)
  const x = (pct: number) => `${(Math.min(pct, SCALE_MAX) / SCALE_MAX) * 100}%`

  return (
    <>
      <h2 className="card-h">Which routes are fullest</h2>
      <p className="card-sub">Share of seats filled in the busiest hour. Click a route to see it.</p>
      <ul className="rank">
        {ranked.map((r) => (
          <li key={r.code}>
            <button
              aria-pressed={selected?.code === r.code}
              onClick={() => onSelect(r.code)}
              title={`Average across the day: ${Math.round(r.avgPct ?? 0)}%`}
            >
              <span className="chip" style={{ background: BAND_COLOUR[r.band] }}>
                {r.code}
              </span>
              <span style={{ minWidth: 0 }}>
                <span className="name" style={{ display: 'block' }}>
                  {r.name}
                </span>
                <span className="track" aria-hidden>
                  <span className="fill" style={{ width: x(r.peakPct!), background: BAND_COLOUR[r.band] }} />
                  <span className="full" style={{ left: x(100) }} />
                </span>
              </span>
              <span className="pct num">{Math.round(r.peakPct!)}%</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="full-key">
        <span style={{ borderLeft: '1.5px solid var(--ink)', height: 12 }} /> = every seat taken
      </div>
      <p className="rank-foot">
        {unknown.length} other routes ({unknown.map((r) => r.code).join(', ')}) have no passenger counts, so we can't
        rank them.
      </p>
    </>
  )
}
