import type { Data } from '../data'

// "Can I trust it?" in one line.
export function VintageLine({ data, onMore }: { data: Data; onMore: () => void }) {
  const { vintage } = data
  const m = vintage.serviceDay.match(/(\d{4})-(\d{2})-(\d{2})/)
  const day = m
    ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString('en-GB', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : vintage.serviceDay
  return (
    <footer className="vintage">
      <b>Bus times</b> recorded {vintage.captureFrom}–{vintage.captureTo}, {day} · <b>Passenger counts</b> 2025 ·{' '}
      <b>
        {vintage.noDemand} of {vintage.total}
      </b>{' '}
      routes have no passenger counts ·{' '}
      <button className="link-btn" style={{ padding: '1px 8px', fontSize: 13 }} onClick={onMore}>
        How we know
      </button>{' '}
      · <b>Map</b> ©{' '}
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
        OpenStreetMap contributors
      </a>
    </footer>
  )
}
