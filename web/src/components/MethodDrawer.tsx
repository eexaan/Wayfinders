import { useEffect } from 'react'

import type { Data } from '../data'

const SOURCES = [
  ['RTL official bus feed (2026): routes, stops, timetable', 'https://bo.rtl.mv:4455/maldives/api/booking/v2/bus/routedetails'],
  ['MTCC bus ridership (2025): passenger counts', 'https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/tag/v1.0'],
  ['Avas Ride taxi trips (Aug–Sep 2026): hour-by-hour shape of demand', 'https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/tag/v1.0'],
  ['MACL airport traffic: when flights land', 'https://github.com/mbs-datathon/maldives-datathon-2026-datasets/releases/tag/v1.0'],
  ['Seat counts per bus (team capacity table, ADR-0010)', 'https://github.com/eexaan/Wayfinders/blob/main/data/raw/mtcc_bus_capacity.csv'],
  ['Airport passenger totals including domestic (MBS Yearbook 11.13)', 'https://statisticsmaldives.gov.mv/yearbook/2026/wp-content/uploads/sites/13/2026/07/11.13.xlsx'],
  ['Road layout for the route lines: OpenStreetMap via OSRM', 'https://router.project-osrm.org/'],
] as const

export function MethodDrawer({ data, onClose }: { data: Data; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { vintage } = data
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="About the data">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h2 style={{ flex: 1 }}>About the data</h2>
          <button className="close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <h3>What “seats filled” means</h3>
        <p>
          Passengers wanting to ride in an hour, divided by the seats on the buses that ran in that hour. 100% means every
          seat is taken. We show two numbers per route: the <b>busiest hour</b> and the <b>average across the day</b>. The true
          figure for any one bus sits between them.
        </p>

        <h3>When it was measured</h3>
        <ul>
          <li>
            <b>Bus times:</b> official RTL feed, {vintage.serviceDay.replace(/\s*\(.*\)/, '')}. The feed only returns trips
            from the moment it is called, so we have {vintage.captureFrom}–{vintage.captureTo}. Earlier hours are hatched in
            the charts, never shown as zero.
          </li>
          <li>
            <b>Passenger counts:</b> MTCC, 2025 daily averages. The hour-by-hour shape comes from taxi trips.
          </li>
          <li>
            <b>Map:</b> Malé, the airport island and Hulhumalé. Villimalé routes (R13, R14) are not drawn.
          </li>
        </ul>

        <h3>What we have for each route</h3>
        <table>
          <thead>
            <tr>
              <th>Route</th>
              <th className="c">Bus times</th>
              <th className="c">Passenger counts</th>
              <th className="c">Seat count</th>
              <th className="c">On map</th>
            </tr>
          </thead>
          <tbody>
            {data.routes.map((r) => (
              <tr key={r.code}>
                <td>
                  <b>{r.code}</b> {r.name}
                </td>
                <td className="c">{r.tripsCaptured ? <span className="yes">✓</span> : <span className="no">none</span>}</td>
                <td className="c">{r.peakPct !== null ? <span className="yes">✓</span> : <span className="no">none</span>}</td>
                <td className="c">{r.seatsAssumed ? <span className="no">estimated</span> : <span className="yes">✓</span>}</td>
                <td className="c">{r.onMap ? <span className="yes">✓</span> : <span className="no">no</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Sources</h3>
        <ul>
          {SOURCES.map(([label, url]) => (
            <li key={label}>
              <a href={url} target="_blank" rel="noopener noreferrer">
                {label}
              </a>
            </li>
          ))}
        </ul>
        <p>Full register with licences: DATA_SOURCES.md in the repository.</p>
      </aside>
    </>
  )
}
