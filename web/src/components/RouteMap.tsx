import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Pane, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'

import { BAND_LABEL, fmtHour, type Band, type Data, type Route, type Segment } from '../data'
import { HOME_BOUNDS, MAX_ZOOM, MIN_ZOOM, PAN_BOUNDS, TILE_ATTRIBUTION, TILE_URL } from '../mapArea'
import { BAND_COLOUR as COLOUR } from '../colours'

type Basemap = 'osm' | 'outline'

// worst on top: where routes share a road, the fullest one is what you see
const ORDER: Record<Band, number> = { unknown: 0, room: 1, busy: 2, over: 3 }
const INK = '#16202b'
const LINE = { lineCap: 'round' as const, lineJoin: 'round' as const }

// offline fallback (dashboard/build/build_basemap.py): sea = container background.
// Used when OSM tiles cannot be fetched, so the demo still works without a network.
const baseStyle = (f?: GeoJSON.Feature): L.PathOptions =>
  f?.properties?.kind === 'land'
    ? { stroke: true, color: '#cfd5cc', weight: 1, fillColor: '#f8f8f5', fillOpacity: 1, interactive: false }
    : f?.properties?.class === 'major'
      ? { color: '#d9ddd5', weight: 3, interactive: false }
      : { color: '#e6e8e2', weight: 1.2, interactive: false }

// English names for orientation, placed offshore so they never cover a route
const PLACES: { name: string; at: [number, number] }[] = [
  { name: 'Malé', at: [4.1815, 73.5085] },
  { name: 'Airport island', at: [4.1975, 73.5205] },
  { name: 'Hulhumalé', at: [4.2295, 73.5335] },
]

const loadText = (r: Route) =>
  r.peakPct === null ? 'no passenger counts' : `${Math.round(r.peakPct)}% of seats filled at its busiest`

const at = (s: Segment, f: number) => s.coords[Math.floor((s.coords.length - 1) * f)]

// fit on mount (after the container has its size) and whenever the focus changes
function FitTo({ bounds }: { bounds: L.LatLngBoundsExpression }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    map.invalidateSize()
    if (first.current) map.fitBounds(bounds, { padding: [30, 30] })
    else map.flyToBounds(bounds, { padding: [50, 50], duration: 0.6 })
    first.current = false
  }, [map, bounds])
  return null
}

// a permanent label pinned to a point, used for every annotation on the map
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

export function RouteMap({
  data,
  selected,
  onSelect,
}: {
  data: Data
  selected: Route | null
  onSelect: (code: string | null) => void
}) {
  const [hover, setHover] = useState<string | null>(null)
  const [basemap, setBasemap] = useState<Basemap>('osm')
  const mapRef = useRef<L.Map | null>(null)
  const tiles = useRef({ loaded: 0, errors: 0 })

  // Offline venue, or a blocked tile host: fall back to the committed vector
  // outline after a few misses if not one tile has arrived, rather than leaving
  // an empty grey box where the island should be.
  const tileHandlers = {
    tileload: () => {
      tiles.current.loaded += 1
    },
    tileerror: () => {
      tiles.current.errors += 1
      if (tiles.current.loaded === 0 && tiles.current.errors === 3) setBasemap('outline')
    },
  }

  const lines = useMemo(() => {
    const by: Record<string, Segment[]> = {}
    for (const s of data.segments) (by[s.route] ??= []).push(s)
    return Object.entries(by)
      .map(([code, segs]) => ({ route: data.byCode[code], segs, all: segs.map((s) => s.coords) }))
      .sort((a, b) => ORDER[a.route.band] - ORDER[b.route.band] || (a.route.peakPct ?? 0) - (b.route.peakPct ?? 0))
  }, [data])

  // the answer, written on the map: the two fullest routes' worst stretch + the bridge
  const callouts = useMemo(() => {
    const out: { n: number; at: [number, number]; dir: L.Direction; title: string; text: string }[] = []
    const ranked = data.routes.filter((r) => r.peakPct !== null).sort((a, b) => b.peakPct! - a.peakPct!)
    const dirs: L.Direction[] = ['right', 'left']
    ranked.slice(0, 2).forEach((r, i) => {
      const seg = data.segments
        .filter((s) => s.route === r.code && s.peakPct !== null)
        .sort((a, b) => b.peakPct! - a.peakPct!)[0]
      if (!seg) return
      const hw = data.kpi.headway?.route.code === r.code ? `, and comes only every ${data.kpi.headway.minutes} min` : ''
      out.push({
        n: out.length + 1,
        at: at(seg, r.isAirport ? 0.75 : 0.5),
        dir: dirs[i],
        title: `${r.code} is ${Math.round(seg.peakPct!)}% full here`,
        text: `${r.isAirport ? 'The airport bus' : r.name}, at ${fmtHour(seg.peakHour!)}${hw}`,
      })
    })
    // The bridge is a LINE, not a point: pinning a third bubble to it either
    // ran off the card or covered R3's label. It gets a caption strip instead.
    return out
  }, [data])

  const bounds = useMemo<L.LatLngBoundsExpression>(() => {
    if (!selected) return HOME_BOUNDS as L.LatLngBoundsExpression
    const pts = data.segments.filter((s) => s.route === selected.code).flatMap((s) => s.coords)
    return pts.length ? L.latLngBounds(pts) : (HOME_BOUNDS as L.LatLngBoundsExpression)
  }, [data, selected])

  // focused route: where it starts, where it ends, where it is fullest
  const focus = useMemo(() => {
    if (!selected) return null
    const segs = data.segments.filter((s) => s.route === selected.code)
    if (!segs.length) return null
    const first = segs[0].coords[0]
    const lastSeg = segs[segs.length - 1]
    const last = lastSeg.coords[lastSeg.coords.length - 1]
    const loop = Math.abs(first[0] - last[0]) + Math.abs(first[1] - last[1]) < 0.002
    const top = segs.filter((s) => s.peakPct !== null).sort((a, b) => b.peakPct! - a.peakPct!)[0]
    return {
      segs,
      stops: data.stops.filter((s) => s.routes.includes(selected.code)),
      start: { at: first, name: segs[0].from, label: loop ? 'Start & end' : 'Start' },
      end: loop ? null : { at: last, name: lastSeg.to, label: 'End' },
      peak: top && { at: at(top, 0.5), pct: Math.round(top.peakPct!), hour: fmtHour(top.peakHour!) },
    }
  }, [data, selected])

  return (
    <>
      <MapContainer
        bounds={HOME_BOUNDS as L.LatLngBoundsExpression}
        maxBounds={PAN_BOUNDS as L.LatLngBoundsLiteral}
        maxBoundsViscosity={0.5}
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        zoomSnap={0.25}
        scrollWheelZoom
        ref={mapRef}
      >
        {basemap === 'osm' ? (
          <TileLayer
            url={TILE_URL}
            attribution={TILE_ATTRIBUTION}
            maxZoom={MAX_ZOOM}
            detectRetina
            eventHandlers={tileHandlers}
          />
        ) : (
          <>
            <Pane name="base" style={{ zIndex: 200 }}>
              <GeoJSON data={data.basemap} style={baseStyle} attribution={TILE_ATTRIBUTION} />
            </Pane>
            {PLACES.map((p) => (
              <Label key={p.name} at={p.at} dir="center" className="place-label">
                {p.name}
              </Label>
            ))}
          </>
        )}
        <FitTo bounds={bounds} />

        {/* routes; keys change with focus so the focused route is re-added on top */}
        {lines.map(({ route, all }) => {
          if (selected?.code === route.code) return null
          const counted = route.peakPct !== null
          const faded = !!selected
          const hot = hover === route.code && !selected
          return (
            <Polyline
              key={`${route.code}-${faded}`}
              positions={all}
              pathOptions={
                counted
                  ? { ...LINE, color: COLOUR[route.band], weight: hot ? 8 : 5, opacity: faded ? 0.15 : 1 }
                  : { ...LINE, color: COLOUR.unknown, weight: hot ? 6 : 3.5, opacity: faded ? 0.2 : 0.95, dashArray: '7 5' }
              }
              eventHandlers={{
                click: () => onSelect(route.code),
                mouseover: () => setHover(route.code),
                mouseout: () => setHover(null),
              }}
            >
              {!faded && (
                <Tooltip sticky>
                  <b>{route.code}</b> · {route.name}
                  <br />
                  {loadText(route)}
                  <br />
                  <i>Click to see this route</i>
                </Tooltip>
              )}
            </Polyline>
          )
        })}

        {focus && selected && (
          <>
            <Polyline
              key={`${selected.code}-casing`}
              positions={focus.segs.map((s) => s.coords)}
              pathOptions={{ ...LINE, color: INK, weight: 12, interactive: false }}
            />
            {focus.segs.map((sg, j) => (
              <Polyline
                key={`${selected.code}-${j}`}
                positions={sg.coords}
                pathOptions={{ ...LINE, color: sg.peakPct === null ? '#ffffff' : COLOUR[sg.band], weight: 7 }}
              >
                <Tooltip sticky>
                  <b>
                    {sg.from} → {sg.to}
                  </b>
                  <br />
                  {sg.peakPct !== null
                    ? `${Math.round(sg.peakPct)}% of seats filled at its busiest (${fmtHour(sg.peakHour!)})`
                    : 'no passenger counts'}
                </Tooltip>
              </Polyline>
            ))}
            {focus.stops.map((s) => (
              <CircleMarker
                key={`${selected.code}-${s.code}`}
                center={[s.lat, s.lon]}
                radius={4}
                pathOptions={{ color: INK, weight: 2, fillColor: '#fff', fillOpacity: 1 }}
              >
                <Tooltip direction="top" offset={[0, -4]}>
                  <b>{s.name}</b>
                  <br />
                  Also served by {s.routes.filter((r) => r !== selected.code).join(', ') || 'no other route'}
                </Tooltip>
              </CircleMarker>
            ))}
            <Label at={focus.start.at} dir="left" className="end-label">
              <b>{focus.start.label}:</b> {focus.start.name}
            </Label>
            {focus.end && (
              <Label at={focus.end.at} dir="right" className="end-label">
                <b>{focus.end.label}:</b> {focus.end.name}
              </Label>
            )}
            {focus.peak && (
              <Label at={focus.peak.at} dir="right" className="callout">
                <span>
                  <b>Fullest: {focus.peak.pct}%</b> at {focus.peak.hour}
                </span>
              </Label>
            )}
          </>
        )}

        {!selected &&
          callouts.map((c) => (
            <Label key={c.n} at={c.at} dir={c.dir} className="callout">
              <span className="callout-n">{c.n}</span>
              <span>
                <b>{c.title}</b>
                <br />
                {c.text}
              </span>
            </Label>
          ))}
      </MapContainer>

      {!selected && data.bridge && (
        <p className="map-note">
          <b>
            {data.bridge.minutes} of {data.bridge.route}'s {data.bridge.endToEnd} minutes
          </b>{' '}
          are spent on the Sinamalé Bridge — {data.bridge.crossings} crossings,{' '}
          {data.bridge.sharePct}% of the journey.
        </p>
      )}

      <div className="card map-tools">
        <span className="map-tools-label">Base map</span>
        <button
          className={basemap === 'osm' ? 'on' : ''}
          onClick={() => setBasemap('osm')}
          title="OpenStreetMap raster tiles (needs a network)"
        >
          OpenStreetMap
        </button>
        <button
          className={basemap === 'outline' ? 'on' : ''}
          onClick={() => setBasemap('outline')}
          title="Committed OSM-derived outline; works offline"
        >
          Outline
        </button>
        <button onClick={() => mapRef.current?.flyToBounds(HOME_BOUNDS as L.LatLngBoundsLiteral, { padding: [30, 30], duration: 0.6 })}>
          All 15 routes
        </button>
      </div>

      <div className="card map-title">
        {selected ? (
          <>
            <span className="chip" style={{ background: COLOUR[selected.band] }}>
              {selected.code}
            </span>
            <span>
              <b>{selected.name}</b>
              <br />
              <small>Colour shows how full each stretch gets</small>
            </span>
            <button className="link-btn" onClick={() => onSelect(null)}>
              ← All routes
            </button>
          </>
        ) : (
          <span>
            <b>Where the buses are fullest</b>
            <br />
            <small>Click a route for its details</small>
          </span>
        )}
      </div>

      <div className="card legend" aria-label="Legend: how full the buses get">
        <div className="legend-title">Seats filled at the busiest time</div>
        {(['over', 'busy', 'room', 'unknown'] as Band[]).map((b) => (
          <div className="legend-row" key={b}>
            <span className={`swatch${b === 'unknown' ? ' dashed' : ''}`} style={{ borderColor: COLOUR[b] }} />
            {BAND_LABEL[b]}
          </div>
        ))}
      </div>
    </>
  )
}
