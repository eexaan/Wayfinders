import type { RerouteData } from '../reroute'

/**
 * The ablation: four runs of the same day, each differing from the one above by
 * exactly one change, with the fleet held at today's 55 buses until the last row.
 *
 * This replaced a panel that compared a 99-bus network against a 55-bus one and
 * reported "waiting unchanged, journeys 35 minutes worse". Three things changed
 * at once, so nothing could be attributed to anything. Now each row isolates one
 * cause and carries its own delta.
 */
const METRICS: { key: string; label: string; unit: string; digits: number; better: 'low' | 'high' }[] = [
  { key: 'meanWaitMin', label: 'Mean wait at a stop', unit: 'min', digits: 1, better: 'low' },
  { key: 'p90WaitMin', label: '9 in 10 wait under', unit: 'min', digits: 0, better: 'low' },
  { key: 'meanJourneyMin', label: 'Mean journey, door to door', unit: 'min', digits: 0, better: 'low' },
  { key: 'leftBehindPct', label: 'Left waiting at close', unit: '%', digits: 1, better: 'low' },
  { key: 'completed', label: 'Journeys completed', unit: '', digits: 0, better: 'high' },
  { key: 'buses', label: 'Buses in service', unit: '', digits: 0, better: 'low' },
]

const fmt = (v: number | null, digits: number) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? '—'
    : digits
      ? v.toFixed(digits)
      : Math.round(v).toLocaleString('en-US')

interface Row {
  key: string
  label: string
  note: string
  change: string
  kpis: Record<string, number | null>
  delta: Record<string, number | null>
}

export function Scoreboard({ data }: { data: RerouteData }) {
  const proof = data.proof as
    | { rows?: Row[]; fleet_held?: number; seeds?: number[]; assumptions?: Record<string, string>; scope?: any }
    | null

  if (!proof?.rows?.length) {
    return (
      <div className="card">
        <h2 className="card-h">Does this improve the original?</h2>
        <p className="card-sub">
          Not generated yet. Run <code>node web/scripts/run-sim.mjs</code> to write{' '}
          <code>reroute_proof.json</code>.
        </p>
      </div>
    )
  }

  const rows = proof.rows
  const base = rows[0].kpis

  return (
    <div className="card scoreboard">
      <h2 className="card-h">Does this improve the original?</h2>
      <p className="card-sub">
        Four runs of the same day. Each row changes one thing from the row above it, on the same{' '}
        <b>{proof.fleet_held}</b> buses until the last row.
      </p>

      <div className="abl">
        {rows.map((row, i) => (
          <div className={`abl-row${i === 0 ? ' abl-base' : ''}`} key={row.key}>
            <div className="abl-head">
              <span className="abl-title">
                <b>{row.label}</b>
                <small>{row.note}</small>
              </span>
            </div>
            <div className="abl-kpis">
              {METRICS.slice(0, 4).map((m) => (
                <span key={m.key} className="abl-kpi">
                  <small>{m.label}</small>
                  <b className="num">
                    {fmt(row.kpis[m.key], m.digits)}
                    {row.kpis[m.key] != null && m.unit ? <em> {m.unit}</em> : null}
                  </b>
                  <Delta value={row.delta[m.key]} digits={m.digits} unit={m.unit} better={m.better} />
                </span>
              ))}
              <span className="abl-kpi">
                <small>buses</small>
                <b className="num">{fmt(row.kpis.buses, 0)}</b>
                <Delta value={row.delta.buses} digits={0} unit="" better="low" />
              </span>
            </div>
          </div>
        ))}
      </div>

      <Verdict rows={rows} base={base} />

      <details className="proof-assume">
        <summary>How this run is set up, and what it does not prove</summary>
        <ul>
          {Object.entries(proof.assumptions ?? {}).map(([k, v]) => (
            <li key={k}>
              <b>{k.replace(/_/g, ' ')}</b>: {v}
            </li>
          ))}
          {proof.scope?.excluded?.length ? (
            <li>
              <b>not modelled</b>: {proof.scope.excluded.join(', ')} — {proof.scope.excluded_reason}
            </li>
          ) : null}
        </ul>
        <p className="note">
          A comparison of four network designs on one modelled day, not a trial. There is no vehicle
          tracking, demand is allocated rather than counted, and the airport stream is a stated share
          of published arrivals.
        </p>
      </details>
    </div>
  )
}

function Delta({ value, digits, unit, better }: {
  value: number | null | undefined
  digits: number
  unit: string
  better: 'low' | 'high'
}) {
  if (value == null || !Number.isFinite(value)) return <em className="abl-delta none">—</em>
  const same = Math.abs(value) < (digits ? 0.05 : 0.5)
  if (same) return <em className="abl-delta same">no change</em>
  const good = better === 'low' ? value < 0 : value > 0
  const sign = value > 0 ? '+' : '−'
  const body = `${sign}${Math.abs(value).toFixed(digits)}${unit === '%' ? '' : unit ? ` ${unit}` : ''}`
  return <em className={`abl-delta ${good ? 'good' : 'bad'}`}>{body}</em>
}

/**
 * The verdict is written from the data, not asserted. If a row makes things
 * worse, this says so — the whole point of an ablation is that it can fail.
 */
function Verdict({ rows, base }: { rows: Row[]; base: Record<string, number | null> }) {
  const best = rows.reduce(
    (a, r) => ((r.kpis.meanWaitMin ?? 1e9) < (a.kpis.meanWaitMin ?? 1e9) ? r : a),
    rows[0],
  )
  const dispatch = rows.find((r) => r.change === 'dispatch')
  const topology = rows.find((r) => r.change === 'topology')
  const fleet = rows.find((r) => r.change === 'fleet')

  const dWait = (a?: Row) =>
    a && a.kpis.meanWaitMin != null && base.meanWaitMin != null
      ? a.kpis.meanWaitMin - base.meanWaitMin
      : null

  return (
    <div className="proof-verdict">
      <p>
        The best row is <b>{best.label}</b>
        {best !== rows[0] && base.meanWaitMin != null && best.kpis.meanWaitMin != null ? (
          <>
            : it cuts the average wait from <b>{fmt(base.meanWaitMin, 1)}</b> to{' '}
            <b>{fmt(best.kpis.meanWaitMin, 1)} min</b> on <b>{fmt(best.kpis.buses, 0)}</b> buses.
          </>
        ) : (
          <> — no change improved on the original on this day.</>
        )}
      </p>
      <ul>
        {dispatch && (
          <li>
            Sending buses when demand calls, rather than on a clock, is worth{' '}
            <b>
              {dWait(dispatch) != null && dWait(dispatch)! < 0
                ? `${Math.abs(dWait(dispatch)!).toFixed(1)} min`
                : 'nothing'}
            </b>{' '}
            of average wait with the same fleet.
          </li>
        )}
        {topology && (
          <li>
            Putting Hulhumalé on circuits{' '}
            {topology.delta.meanWaitMin != null && topology.delta.meanWaitMin > 0.5 ? (
              <>
                <b>costs {topology.delta.meanWaitMin.toFixed(1)} min</b> of wait: a circuit is longer
                than the open route it replaces, so the same buses cover it less often.
              </>
            ) : (
              <>does not cost waiting time on this day.</>
            )}
          </li>
        )}
        {fleet && fleet.delta.buses ? (
          <li>
            The extra buses recover{' '}
            <b>
              {fleet.delta.meanWaitMin != null
                ? `${Math.abs(fleet.delta.meanWaitMin).toFixed(1)} min`
                : '—'}
            </b>{' '}
            for <b>+{fleet.delta.buses}</b> vehicles.
          </li>
        ) : null}
      </ul>
    </div>
  )
}
