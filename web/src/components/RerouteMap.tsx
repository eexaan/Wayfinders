import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Pane, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'

import { fmtClock, type RerouteData, type SimLeg } from '../reroute'
import { laneOffset, offsetLine, routeColour } from '../routeStyle'
import { HOME_BOUNDS, MAX_ZOOM, MIN_ZOOM, PAN_BOUNDS, TILE_ATTRIBUTION, TILE_URL } from '../mapArea'
import type { Snapshot, Simulation } from '../sim/engine.mjs'

type Sim = Simulation
const INK = '#16202b'
const LINE = { lineCap: 'round' as const, lineJoin: 'round' as const }

const baseStyle = (f?: GeoJSON.Feature): L.PathOptions =>
  f?.properties?.kind === 'land'
    ? { stroke: true, color: '#cfd5cc', weight: 1, fillColor: '#f8f8f5', fillOpacity: 1, interactive: false }
    : f?.properties?.class === 'major'
      ? { color: '#d9ddd5', weight: 3, interactive: false }
      : { color: '#e6e8e2', weight: 1.2, interactive: false }

const HOTSPOT_COLOUR: Record<string, string> = {
  hospital: '#b91c1c',
  clinic: '#dc2626',
  doctors: '#dc2626',
  dentist: '#ef4444',
  office: '#1d4ed8',
  government: '#1e40af',
  townhall: '#1e40af',
  courthouse: '#1e40af',
  school: '#7c3aed',
  college: '#7c3aed',
  university: '#7c3aed',
  marketplace: '#a16207',
  ferry_terminal: '#0f766e',
  bus_station: '#0f766e',
  hotel: '#0891b2',
  guest_house: '#0891b2',
  place_of_worship: '#64748b',
  police: '#475569',
  fire_station: '#475569',
  bank: '#64748b',
}

function FitTo({ bounds }: { bounds: L.LatLngBoundsExpression }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize({ animate: false }))
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  useEffect(() => {
    if (first.current) {
      map.invalidateSize({ animate: false })
      map.fitBounds(bounds, { padding: [30, 30], animate: false })
      first.current = false
    }
  }, [map, bounds])
  return null
}

function Label({ at, dir, className, children }: {
  at: [number, number]
  dir: L.Direction
  className: string
  children: React.ReactNode
}) {
  const off: Record<string, [number, number]> = { left: [-10, 0], right: [10, 0], top: [0, -10], bottom: [0, 10] }
  return (
    <CircleMarker center={at} radius={0} pathOptions={{ opacity: 0, fillOpacity: 0 }} interactive={false}>
      <Tooltip permanent direction={dir} offset={off[dir] ?? [0, 0]} className={className}>
        {children}
      </Tooltip>
    </CircleMarker>
  )
}

export function RerouteMap({
  data,
  sim,
  clock,
  selectedStop,
  onSelectStop,
  showOld,
  showHotspots,
  showBuses,
  onToggleOld,
  onToggleHotspots,
  onToggleBuses,
}: {
  data: RerouteData
  sim: Sim
  clock: number
  selectedStop: string | null
  onSelectStop: (id: string | null) => void
  showOld: boolean
  showHotspots: boolean
  showBuses: boolean
  onToggleOld: () => void
  onToggleHotspots: () => void
  onToggleBuses: () => void
}) {
  const [snap, setSnap] = useState(() => sim.snapshot())

  // The engine advances one simulated minute at a time; repaint on the clock
  // rather than on every frame, so a 10x replay redraws 10 times a second and
  // not 60.
  useEffect(() => {
    setSnap(sim.snapshot())
  }, [sim, clock])

  const queueByStop = useMemo(() => {
    const m: Record<string, number> = {}
    data.stops.forEach((s, i) => {
      m[s.id] = snap.queues[i] ?? 0
    })
    return m
  }, [snap, data.stops])

  const routeLines = useMemo(() => {
    return Object.entries(data.legs).map(([code, legs]) => {
      const lane = data.lanes?.[code] ?? { groupSize: 1, index: 0 }
      // Routes on the same road are drawn on top of each other: a sideways
      // offset pushed lines off the street and into the blocks.
      const metres = laneOffset(lane.index, lane.groupSize, 0)
      return {
        code,
        service: data.routeById[code]?.service ?? 'local',
        colour: routeColour(code),
        shared: lane.groupSize > 1,
        coords: legs.map((l: SimLeg) => offsetLine(l.coords, metres)),
      }
    })
  }, [data])

  const bounds = HOME_BOUNDS as L.LatLngBoundsExpression
  const selected = selectedStop ? data.byId[selectedStop] : null

  return (
    <>
      <MapContainer
        bounds={bounds}
        maxBounds={PAN_BOUNDS as L.LatLngBoundsLiteral}
        maxBoundsViscosity={0.5}
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        zoomSnap={1}
        zoomDelta={1}
        scrollWheelZoom
      >
        <TileLayer
          url={TILE_URL}
          attribution={TILE_ATTRIBUTION}
          maxZoom={MAX_ZOOM}
          maxNativeZoom={19}
          detectRetina
          updateWhenZooming={false}
          updateWhenIdle={false}
          keepBuffer={6}
        />
        <Pane name="reroute-base" style={{ zIndex: 150 }}>
          <GeoJSON data={data.basemap} style={baseStyle} attribution={TILE_ATTRIBUTION} />
        </Pane>
        <FitTo bounds={bounds} />

        {showOld && (
          <Pane name="reroute-old" style={{ zIndex: 300 }}>
            {data.oldRoutes.map((r) => (
              <Polyline
                key={r.code}
                positions={r.coords}
                pathOptions={{ ...LINE, color: '#9aa3ab', weight: 2, opacity: 0.75, dashArray: '3 6' }}
              >
                <Tooltip sticky>
                  <b>R{r.code.replace(/^R/, '')}</b> · {r.name}
                  <br />
                  <i>Today's route — replaced by this network</i>
                </Tooltip>
              </Polyline>
            ))}
          </Pane>
        )}

        {showHotspots && (
          <Pane name="reroute-hotspots" style={{ zIndex: 380 }}>
            {data.hotspots.features.map((f, i) => {
              const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates as [number, number]
              const kind = String(f.properties?.kind ?? '')
              const colour = HOTSPOT_COLOUR[kind] ?? '#64748b'
              return (
                <CircleMarker
                  key={`h${i}`}
                  center={[lat, lon]}
                  radius={3.4}
                  pathOptions={{ color: colour, weight: 1.2, fillColor: colour, fillOpacity: 0.5 }}
                >
                  <Tooltip direction="top" offset={[0, -3]}>
                    <b>{f.properties?.name || kind}</b>
                    <br />
                    <span style={{ textTransform: 'capitalize' }}>{kind.replace(/_/g, ' ')}</span>
                    {f.properties?.weight ? ` · weight ${f.properties.weight}` : ''}
                  </Tooltip>
                </CircleMarker>
              )
            })}
          </Pane>
        )}

        <Pane name="reroute-lines" style={{ zIndex: 400 }}>
          {routeLines.map((r) => (
            <Polyline
              key={r.code}
              positions={r.coords}
              pathOptions={{ ...LINE, color: r.colour, weight: r.shared ? 3.6 : 3.2, opacity: 0.95 }}
            >
              <Tooltip sticky>
                <b style={{ color: r.colour }}>{r.code}</b> · {data.routeById[r.code]?.name}
                <br />
                {data.routeById[r.code]?.lengthKm} km · {data.routeById[r.code]?.buses} buses · every{' '}
                {data.routeById[r.code]?.peakHeadway} min
                {r.shared && (
                  <>
                    <br />
                    <i>shares this road with {data.lanes[r.code].groupSize - 1} other route(s)</i>
                  </>
                )}
              </Tooltip>
            </Polyline>
          ))}
        </Pane>

        <Pane name="reroute-stops" style={{ zIndex: 420 }}>
          {data.stops.map((s) => {
            const q = queueByStop[s.id] ?? 0
            const busy = q >= 25
            const mine = selectedStop === s.id
            const r = s.interchange ? 7 : mine ? 6 : 4.2
            return (
              <CircleMarker
                key={s.id}
                center={[s.lat, s.lon]}
                radius={r}
                pathOptions={{
                  color: busy ? '#b91c1c' : INK,
                  weight: mine ? 3 : busy ? 2.4 : 1.6,
                  fillColor: busy ? '#fecaca' : s.needsExtra ? '#fde68a' : '#ffffff',
                  fillOpacity: 1,
                }}
                eventHandlers={{ click: () => onSelectStop(mine ? null : s.id) }}
              >
                <Tooltip direction="top" offset={[0, -4]}>
                  <b>{s.name}</b>
                  <br />
                  {s.routes.length ? s.routes.join(', ') : 'no route'}
                  {s.firstBusAt !== null && (
                    <>
                      <br />
                      First bus {fmtClock(s.firstBusAt)} ({s.firstBusRoute})
                    </>
                  )}
                  <br />
                  {q > 0 ? `${q} waiting now` : 'no queue now'}
                  {s.peakQueue >= 25 && (
                    <>
                      <br />
                      <b style={{ color: '#b91c1c' }}>Peak queue {s.peakQueue}</b>
                    </>
                  )}
                  {s.hotspots > 0 && (
                    <>
                      <br />
                      <small>
                        {s.hotspots} attractor{s.hotspots === 1 ? '' : 's'} in 400 m
                        {s.topHotspot ? ` · ${s.topHotspot}` : ''}
                      </small>
                    </>
                  )}
                </Tooltip>
              </CircleMarker>
            )
          })}
        </Pane>

        {showBuses && (
          <Pane name="reroute-buses" style={{ zIndex: 440 }}>
            {snap.buses.map((b: Snapshot['buses'][number]) => (
              <CircleMarker
                key={b.id}
                center={[b.lat, b.lon]}
                radius={b.extra ? 6 : 5}
                pathOptions={{
                  color: b.extra ? '#7c2d12' : INK,
                  weight: 1.4,
                  fillColor: b.extra ? '#f59e0b' : routeColour(b.routeId),
                  fillOpacity: 1,
                }}
              >
                <Tooltip direction="top" offset={[0, -5]}>
                  <b>{b.routeId}</b>
                  {b.extra ? ' (extra)' : ''}
                  <br />
                  {b.occupancy}/{b.seats} on board · {Math.round(b.load * 100)}%
                  <br />
                  next: {b.nextStop}
                  <br />
                  <i>{b.moving ? 'moving' : 'at a stop'}</i>
                </Tooltip>
              </CircleMarker>
            ))}
          </Pane>
        )}

        {selected && (
          <Label at={[selected.lat, selected.lon]} dir="right" className="callout">
            <span>
              <b>{selected.name}</b>
              <br />
              First bus {fmtClock(selected.firstBusAt)} · {queueByStop[selected.id] ?? 0} waiting
            </span>
          </Label>
        )}
      </MapContainer>

      <div className="card map-tools">
        <span className="map-tools-label">Layers</span>
        <button className={showOld ? 'on' : ''} onClick={onToggleOld} title="Today's R1-R12, for comparison">
          Today's routes
        </button>
        <button className={showHotspots ? 'on' : ''} onClick={onToggleHotspots} title="Hospitals, offices, schools, markets">
          Hotspots
        </button>
        <button className={showBuses ? 'on' : ''} onClick={onToggleBuses} title="Buses in service right now">
          Buses
        </button>
      </div>

      <div className="card map-title">
        <span>
          <b>{data.stops.length} new stops · {data.routes.length} new routes</b>
          <br />
          <small>{fmtClock(clock)} · {snap.buses.length} buses on the road</small>
        </span>
        {selected && (
          <button className="link-btn" onClick={() => onSelectStop(null)}>
            ← All stops
          </button>
        )}
      </div>

      <div className="card legend legend-routes" aria-label="Legend">
        <div className="legend-title">Routes</div>
        {data.routes.map((r) => (
          <div className="legend-row" key={r.id}>
            <span className="swatch" style={{ borderColor: routeColour(r.id) }} />
            <b style={{ color: routeColour(r.id) }}>{r.id}</b>
            <span className="legend-route-name">{r.name}</span>
            <span className="legend-route-meta">
              {r.service === 'airport' ? 'airport' : r.service === 'cross_bridge' ? 'cross-bridge' : 'local'}
              {data.lanes?.[r.id]?.groupSize > 1 ? ' · shared' : ''}
            </span>
          </div>
        ))}
        <div className="legend-row legend-sep">
          <span className="swatch-dot" aria-hidden /> Stop ({data.stops.length})
        </div>
        <div className="legend-row">
          <span className="swatch-dot" style={{ background: '#b91c1c' }} aria-hidden /> Queue over the line
        </div>
        <div className="legend-row">
          <span className="swatch-dot" style={{ background: '#f59e0b' }} aria-hidden /> Extra bus sent
        </div>
      </div>
    </>
  )
}
