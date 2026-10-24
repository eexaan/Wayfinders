import { BAND_COLOUR } from '../colours'
import { fmtHour, type Data, type Route } from '../data'
import { HourlyChart } from './HourlyChart'

const SCALE_MAX = 120

function LoadBand({ route }: { route: Route }) {
  const x = (p: number) => `${(Math.min(p, SCALE_MAX) / SCALE_MAX) * 100}%`
  const lo = route.avgPct!
  const hi = route.peakPct!
  return (
    <div className="band-bar" aria-label={`Seats filled: ${Math.round(lo)}% on average, ${Math.round(hi)}% at the busiest hour`}>
      <span className="range" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})`, background: BAND_COLOUR[route.band] }} />
      <span className="full" style={{ left: x(100) }} />
      <span className="lab top" style={{ left: x(100) }}>
        every seat taken
      </span>
      <span className="lab bottom" style={{ left: x(lo) }}>
        average {Math.round(lo)}%
      </span>
      <span className="lab bottom" style={{ left: x(hi) }}>
        <b>busiest {Math.round(hi)}%</b>
      </span>
    </div>
  )
}

// One tick per recorded departure; the unrecorded morning is hatched.
function Timetable({ departures, firstHour }: { departures: number[]; firstHour: number }) {
  const W = 400
  const H = 34
  const x = (min: number) => (min / (24 * 60)) * W
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block', marginTop: 6 }} role="img" aria-label="Departure times">
      <defs>
        <pattern id="hatch2" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="#d9ddd6" strokeWidth="2" />
        </pattern>
      </defs>
      <rect x={0} y={2} width={x(firstHour * 60)} height={18} fill="url(#hatch2)" />
      <line x1={0} x2={W} y1={20} y2={20} stroke="#d9ddd6" />
      {departures.map((d, i) => (
        <line key={i} x1={x(d)} x2={x(d)} y1={4} y2={20} stroke="var(--ink)" strokeWidth={1.5} />
      ))}
      {[0, 6, 12, 18, 23].map((h) => (
        <text key={h} x={x(h * 60 + 30)} y={H - 2} textAnchor="middle" fontSize="11" fill="var(--ink-3)">
          {fmtHour(h)}
        </text>
      ))}
    </svg>
  )
}

export function RoutePanel({ data, route, onClose }: { data: Data; route: Route; onClose: () => void }) {
  const hours = data.hourly[route.code] ?? []
  const deps = data.departures[route.code] ?? []
  const firstHour = hours.find((h) => h.captured)?.hour ?? 24
  const working = data.periods?.[route.code]?.find((p) => p.period === 'working_hours')?.sharePct ?? null
  const counted = route.peakPct !== null

  return (
    <div>
      <div className="panel-head">
        <span className="chip" style={{ background: BAND_COLOUR[route.band], marginTop: 2 }}>
          {route.code}
        </span>
        <div className="titles">
          <h2>{route.name}</h2>
          <div className="dv" lang="dv">
            {route.nameDv}
          </div>
        </div>
        <button className="close" onClick={onClose} aria-label="Close route details">
          ×
        </button>
      </div>

      <div className="facts">
        <div>
          <b>{route.busType}</b>
          <span>bus</span>
        </div>
        <div>
          <b className="num">{route.seats}</b>
          <span>
            seats{route.seatsAssumed ? ' (est.)' : ''}
            {route.standing ? ` + ${route.standing} standing` : ''}
          </span>
        </div>
        <div>
          <b className="num">MVR {route.fare}</b>
          <span>fare</span>
        </div>
        <div>
          <b className="num">{route.tripsPerDay ?? '—'}</b>
          <span>trips a day</span>
        </div>
      </div>

      {counted ? (
        <>
          <p className="verdict">
            At its busiest, <b>{Math.round(route.peakPct!)}%</b> of seats are filled
            {route.peakStretch && (
              <>
                {' '}
                between <b>{route.peakStretch.replace('→', 'and')}</b>
                {route.peakHour !== null && <> at {fmtHour(route.peakHour)}</>}
              </>
            )}
            . Across the day, <b>{Math.round(route.avgPct!)}%</b>.
          </p>
          <LoadBand route={route} />
          <h3 className="section-h">Passengers vs seats, hour by hour</h3>
          <HourlyChart points={hours} />
          {working !== null && (
            <p className="note">
              <b>{Math.round(working)}%</b> of this route's riders travel during working hours (08:00–16:00).
            </p>
          )}
        </>
      ) : (
        <p className="verdict">
          We have <b>no passenger counts</b> for this route, so we can't say how full it is. Its timetable is below.
        </p>
      )}

      <h3 className="section-h">When the buses leave</h3>
      {deps.length ? (
        <>
          <Timetable departures={deps} firstHour={firstHour} />
          {route.firstTripOrder && route.firstTripOrder > 1 && (
            <p className="note">
              Times recorded from {fmtHour(firstHour)} on. The first one recorded is trip {route.firstTripOrder} of{' '}
              {route.tripsPerDay}, so {route.firstTripOrder - 1} earlier trips ran but aren't shown.
            </p>
          )}
        </>
      ) : (
        <p className="note">The official feed returned no departure times for this route.</p>
      )}
    </div>
  )
}
