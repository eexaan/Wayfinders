import { useState } from 'react'

import { fmtHour, fmtInt, type HourPoint } from '../data'

const W = 400
const H = 190
const M = { top: 10, right: 6, bottom: 22, left: 36 }

function niceMax(v: number) {
  const step = 10 ** Math.floor(Math.log10(v || 1))
  return Math.ceil(v / step) * step
}

// Seats running (bars) against passengers wanting to ride (line), 24 hours.
// Hours whose bus times were not recorded are hatched - never drawn as zero.
export function HourlyChart({ points }: { points: HourPoint[] }) {
  const [hover, setHover] = useState<number | null>(null)

  const max = niceMax(Math.max(1, ...points.map((p) => Math.max(p.passengers ?? 0, p.seats ?? 0))))
  const iw = W - M.left - M.right
  const ih = H - M.top - M.bottom
  const bw = iw / 24
  const x = (h: number) => M.left + h * bw
  const y = (v: number) => M.top + ih - (v / max) * ih
  const ticks = [0, max / 2, max]

  const firstCaptured = points.find((p) => p.captured)?.hour ?? 24
  const line = points
    .filter((p) => p.passengers !== null)
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.hour) + bw / 2},${y(p.passengers!)}`)
    .join('')
  const hasShortfall = points.some((p) => p.seats !== null && p.passengers! > p.seats)
  const hp = hover !== null ? points[hover] : null

  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Passengers and seats by hour of day">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#d9ddd6" strokeWidth="2" />
          </pattern>
        </defs>

        <g className="grid">
          {ticks.map((t) => (
            <line key={t} x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
          ))}
        </g>

        {firstCaptured > 0 && (
          <g>
            <rect x={x(0)} y={M.top} width={x(firstCaptured) - x(0)} height={ih} fill="url(#hatch)" opacity={0.8} />
            <text x={(x(0) + x(firstCaptured)) / 2} y={M.top + 14} textAnchor="middle" fontSize="11" fill="var(--ink-2)">
              Bus times not recorded
            </text>
          </g>
        )}

        {points.map(
          (p) =>
            p.seats !== null && (
              <rect
                key={p.hour}
                x={x(p.hour) + 1}
                y={y(p.seats)}
                width={bw - 2}
                height={Math.max(0, M.top + ih - y(p.seats))}
                rx={2}
                fill="var(--seats)"
              />
            ),
        )}

        {/* the shortfall: passengers above the seats that ran */}
        {points.map(
          (p) =>
            p.seats !== null &&
            p.passengers !== null &&
            p.passengers > p.seats && (
              <rect
                key={`s${p.hour}`}
                x={x(p.hour) + 1}
                y={y(p.passengers)}
                width={bw - 2}
                height={y(p.seats) - y(p.passengers)}
                fill="var(--over)"
                opacity={0.85}
              />
            ),
        )}

        <path d={line} fill="none" stroke="var(--passengers)" strokeWidth={2} strokeLinejoin="round" />

        <g className="axis">
          {ticks.map((t) => (
            <text key={t} x={M.left - 6} y={y(t) + 4} textAnchor="end">
              {fmtInt(t)}
            </text>
          ))}
          {[0, 6, 12, 18, 23].map((h) => (
            <text key={h} x={x(h) + bw / 2} y={H - 6} textAnchor="middle">
              {fmtHour(h)}
            </text>
          ))}
        </g>

        {hp && (
          <line x1={x(hp.hour) + bw / 2} x2={x(hp.hour) + bw / 2} y1={M.top} y2={M.top + ih} stroke="var(--ink-3)" strokeWidth={1} />
        )}
        {points.map((p) => (
          <rect
            key={`h${p.hour}`}
            x={x(p.hour)}
            y={M.top}
            width={bw}
            height={ih}
            fill="transparent"
            onMouseEnter={() => setHover(p.hour)}
          />
        ))}
      </svg>

      {hp && (
        <div className="tip" style={{ left: `${((x(hp.hour) + bw / 2) / W) * 100}%`, top: `${(M.top / H) * 100}%` }}>
          <b>
            {fmtHour(hp.hour)}–{fmtHour(hp.hour + 1)}
          </b>
          <br />
          {hp.passengers !== null ? `${fmtInt(hp.passengers)} passengers` : 'no passenger estimate'}
          <br />
          {hp.captured && hp.seats !== null
            ? `${fmtInt(hp.seats)} seats on ${fmtInt(hp.buses ?? 0)} buses`
            : 'bus times not recorded'}
          {hp.seats !== null && hp.passengers !== null && hp.passengers > hp.seats && (
            <>
              <br />
              <b>{fmtInt(hp.passengers - hp.seats)} more passengers than seats</b>
            </>
          )}
        </div>
      )}

      <div className="chart-legend">
        <span>
          <i className="key-line" /> Passengers wanting to ride
        </span>
        <span>
          <i className="key-box" style={{ background: 'var(--seats)' }} /> Seats on buses that ran
        </span>
        {hasShortfall && (
          <span>
            <i className="key-box" style={{ background: 'var(--over)' }} /> More passengers than seats
          </span>
        )}
      </div>
    </div>
  )
}
