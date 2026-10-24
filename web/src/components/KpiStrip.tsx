import type { Data } from '../data'

// The pitch in four numbers. Plain text, so it still works if the map fails.
// Headline choices follow docs/TEAM.md: the fullest stretch, not the withdrawn
// route-day upper bound, and no "half-empty airport bus".
export function KpiStrip({ data, onRoute }: { data: Data; onRoute: (code: string) => void }) {
  const { fullest, workingHoursPct, headway, unmetPct } = data.kpi
  const items = [
    fullest && {
      big: `${Math.round(fullest.pct)}%`,
      what: `of seats filled on ${fullest.route.code}${fullest.route.isAirport ? ', the airport bus,' : ''} on its busiest stretch`,
      colour: fullest.pct >= 100 ? 'var(--over)' : 'var(--busy)',
      route: fullest.route.code,
    },
    headway && {
      big: `${headway.minutes} min`,
      what: `between ${headway.route.code} airport buses`,
      colour: null,
      route: headway.route.code,
    },
    workingHoursPct !== null && {
      big: `${Math.round(workingHoursPct)}%`,
      what: 'of bus trips happen in working hours (08:00–16:00, assumed)',
      colour: null,
      route: null,
    },
    unmetPct !== null && {
      big: `${unmetPct.toFixed(1)}%`,
      what: `of riders can’t board because the bus is full (${data.vintage.captureFrom}–${data.vintage.captureTo})`,
      colour: 'var(--over)',
      route: null,
    },
  ].filter(Boolean) as { big: string; what: string; colour: string | null; route: string | null }[]

  return (
    <section className="kpis" aria-label="Headline numbers">
      {items.map((k) => (
        <div
          key={k.what}
          className="card kpi"
          onClick={k.route ? () => onRoute(k.route!) : undefined}
          style={k.route ? { cursor: 'pointer' } : undefined}
          title={k.route ? `Show ${k.route} on the map` : undefined}
        >
          <div className="big num">
            {k.colour && <span className="marker" style={{ background: k.colour }} aria-hidden />}
            {k.big}
          </div>
          <div className="what">{k.what}</div>
        </div>
      ))}
    </section>
  )
}
