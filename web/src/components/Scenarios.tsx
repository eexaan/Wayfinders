import { fmtInt, type Data, type Scenario } from '../data'

// Plain-language names for the scenario keys in scenario_kpis.csv. S1 (Friday)
// was removed from the data: the feed only returns one service day.
const NAMES: Record<string, { name: string; what: string }> = {
  S0: { name: 'Today', what: 'The timetable as it runs now.' },
  // descriptions follow dashboard/data/scenario_moves.csv
  S2: { name: 'Re-time the airport buses', what: 'Move late-night R4 trips to midday, one of them onto R3.' },
  S3: { name: 'Move buses to the busy corridor', what: 'Move quiet R4 airport trips onto R1 in the afternoon and evening rush.' },
  S4: {
    name: 'Shift one R2 trip to R1’s rush',
    what: 'Move one midday R2 trip onto R1 at 16:00 — the only safe move, since the corridor has no spare buses.',
  },
  S5: { name: 'Recommended package', what: 'The corridor move plus R1/R2 re-timing, together.' },
}

type Better = 'lower' | 'higher' | 'neutral'

function Tile({ label, value, base, unit, better, digits = 0 }: {
  label: string
  value: number | null
  base: number | null
  unit: string
  better: Better
  digits?: number
}) {
  const fmt = (v: number) => (digits ? v.toFixed(digits) : fmtInt(v))
  const d = value !== null && base !== null ? value - base : null
  const same = d === null || Math.abs(d) < 10 ** -digits / 2
  const good = !same && better !== 'neutral' && (better === 'lower' ? d! < 0 : d! > 0)
  const cls = same || better === 'neutral' ? 'same' : good ? 'good' : 'bad'
  return (
    <div className="card tile">
      <div className="label">{label}</div>
      <div className="value num">
        {value === null ? '—' : fmt(value)}
        <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--ink-3)' }}>
          {unit === '%' ? '' : ' '}
          {unit}
        </span>
      </div>
      <div className={`delta ${cls} num`}>
        {same
          ? 'same as today'
          : `${d! > 0 ? '+' : '−'}${fmt(Math.abs(d!))}${unit === '%' ? '' : ' '}${unit} vs today${good ? ' ✓' : ''}`}
      </div>
    </div>
  )
}

function ByRoute({ data, base, active }: { data: Data; base: Scenario; active: Scenario }) {
  const codes = Object.keys(base.byRoute).sort((a, b) => base.byRoute[b] - base.byRoute[a])
  const max = Math.max(1, ...codes.flatMap((c) => [base.byRoute[c], active.byRoute[c] ?? 0]))
  const pct = (v: number) => `${(v / max) * 100}%`
  return (
    <div className="card">
      <h2 className="card-h">Passengers who don't fit, route by route</h2>
      <p className="card-sub">Boardings above the seats available, on the recorded Saturday.</p>
      <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
        {codes.map((c) => {
          const r = data.byCode[c]
          return (
            <div key={c} style={{ display: 'grid', gridTemplateColumns: '170px minmax(0,1fr) 90px', gap: 10, alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: 'var(--ink-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                <b style={{ color: 'var(--ink)' }}>{c}</b> {r?.name}
              </span>
              <span style={{ display: 'grid', gap: 3 }}>
                <span className="track" style={{ marginTop: 0, height: 8 }}>
                  <span className="fill" style={{ width: pct(base.byRoute[c]), background: '#cfd4cc' }} />
                </span>
                <span className="track" style={{ marginTop: 0, height: 8 }}>
                  <span className="fill" style={{ width: pct(active.byRoute[c] ?? 0), background: 'var(--ink)' }} />
                </span>
              </span>
              <span className="num" style={{ fontSize: 13, textAlign: 'right' }}>
                {fmtInt(base.byRoute[c])} → <b>{fmtInt(active.byRoute[c] ?? 0)}</b>
              </span>
            </div>
          )
        })}
      </div>
      <div className="chart-legend">
        <span>
          <i className="key-box" style={{ background: '#cfd4cc' }} /> Today
        </span>
        <span>
          <i className="key-box" style={{ background: 'var(--ink)' }} /> {NAMES[active.key]?.name ?? active.id}
        </span>
      </div>
    </div>
  )
}

export function Scenarios({ data, active, onPick }: { data: Data; active: string; onPick: (key: string) => void }) {
  const base = data.scenarios.find((s) => s.key === 'S0')!
  const cur = data.scenarios.find((s) => s.key === active) ?? data.scenarios[data.scenarios.length - 1]

  return (
    <div className="scen">
      <div className="card scen-list" role="radiogroup" aria-label="Scenarios">
        {data.scenarios.map((s) => (
          <button key={s.id} aria-pressed={s.key === cur.key} onClick={() => onPick(s.key)}>
            <b>
              <span className="tag">{s.key}</span>
              {NAMES[s.key]?.name ?? s.id}
            </b>
            <span>{NAMES[s.key]?.what}</span>
          </button>
        ))}
      </div>

      <div className="scen-body">
        <div className="tiles">
          <Tile label="Passengers who don't fit" value={cur.overCapacity} base={base.overCapacity} unit="" better="lower" />
          <Tile label="Riders left behind" value={cur.unmetPct} base={base.unmetPct} unit="%" better="lower" digits={1} />
          <Tile label="Average wait for a bus" value={cur.waitMin} base={base.waitMin} unit="min" better="lower" digits={1} />
          <Tile label="Taxi rides won back" value={cur.taxiPerDay} base={base.taxiPerDay} unit="a day" better="higher" />
        </div>
        <div className="card callout">
          {cur.trips === base.trips ? (
            <>
              {cur.tripsMoved > 0 && (
                <>
                  <b className="num">{cur.tripsMoved}</b> trips moved to a different route or hour.{' '}
                </>
              )}
              Same number of bus trips as today (<b className="num">{cur.trips}</b>): <b>no new buses</b>.
            </>
          ) : (
            <>
              <b className="num">{cur.trips}</b> bus trips in the recorded hours ({cur.trips > base.trips ? '+' : '−'}
              {Math.abs(cur.trips - base.trips)} vs today), all made by re-timing existing buses.
            </>
          )}
          <p className="note" style={{ margin: '10px 0 0' }}>
            Re-timing buses does not win taxi riders: the modal-shift model needs a shorter journey, not a different
            hour. That is why the taxi figure does not move with the scenario.
          </p>
        </div>
        <ByRoute data={data} base={base} active={cur} />
      </div>
    </div>
  )
}
