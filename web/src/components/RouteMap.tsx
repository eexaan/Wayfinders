import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Pane, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'

import { BAND_LABEL, fmtHour, type Band, type Data, type Route, type Segment, type Stop } from '../data'
import { HOME_BOUNDS, MAX_ZOOM, MIN_ZOOM, PAN_BOUNDS, TILE_ATTRIBUTION, TILE_URL } from '../mapArea'
import { BAND_COLOUR as COLOUR, ROUTE_COLOUR } from '../colours'

type Basemap = 'osm' | 'outline'
type ColourBy = 'band' | 'route'

// worst on top: where routes share a road, the fullest one is what you see
const ORDER: Record<Band, number> = { unknown: 0, room: 1, busy: 2, over: 3 }
const INK = '#16202b'
const LINE = { lineCap: 'round' as const, lineJoin: 'round' as const }

// Stroke widths are CSS px and Leaflet does NOT scale them with zoom, so a
// fixed pixel width covers more ground as you zoom out. At the app's default
// z13 that made the selected route's casing ~230 m of "road" over an island
// whose streets are 7-15 m - it read as a ribbon until you zoomed in.
//
// The map is a scale model, so the line has to be anchored to the ground, not
// the screen: W below is the width at SCALE_ZOOM (z16 = 2.38 m/px), where a
// 3 px route is ~7 m, about one lane. groundWidth() multiplies by 2^(zoom-16)
// so that real width - and therefore the line-to-road ratio the eye judges -
// stays constant at every zoom. The clamps exist because below ~1 px a stroke
// cannot be drawn and above ~7 px it covers the street it sits on.
const SCALE_ZOOM = 16
const groundWidth = (base: number, zoom: number, min = 1, max = 7) =>
  Math.min(max, Math.max(min, base * Math.pow(2, zoom - SCALE_ZOOM)))

// Current Leaflet zoom, re-read on zoomend so styles follow the scale.
function useZoom(): number {
  const map = useMap()
  const [zoom, setZoom] = useState(() => map.getZoom())
  useEffect(() => {
    const sync = () => setZoom(map.getZoom())
    map.on('zoomend', sync)
    return () => {
      map.off('zoomend', sync)
    }
  }, [map])
  return zoom
}

const W = { segment: 4.5, route: 3, routeHot: 5, unknown: 2.5, unknownHot: 3.5 }

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

// Fit on mount, then re-fit whenever the focus changes. invalidateSize() is a
// forced reflow, so it runs on mount and on a real container resize only -
// calling it on every route click is what made selecting a route feel slow.
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
    } else {
      map.flyToBounds(bounds, { padding: [50, 50], duration: 0.45 })
    }
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

// The selected route's own layers: a dark casing plus one coloured line per
// segment. A separate component because it needs the map's zoom, and useMap()
// is only valid inside <MapContainer>. The casing is a fixed +2 px outline
// rather than a scaled width, so it stays a hairline at overview and a border
// at street level instead of growing into a slab.
const FocusLines = memo(function FocusLines({
  segments,
  identity,
}: {
  segments: Segment[]
  identity?: string
}) {
  const zoom = useZoom()
  const segWeight = groundWidth(W.segment, zoom)
  return (
    <>
      <Polyline
        positions={segments.map((s) => s.coords)}
        pathOptions={{ ...LINE, color: INK, weight: segWeight + 2, interactive: false }}
      />
      {segments.map((sg, j) => (
        <Polyline
          key={j}
          positions={sg.coords}
          pathOptions={{
            ...LINE,
            // A route with an identity hue is drawn in it edge to edge, so the
            // selected route still reads as one route; load stays legible in
            // the tooltip, the panel gauge and the hourly chart.
            color: identity ?? (sg.peakPct === null ? '#ffffff' : COLOUR[sg.band]),
            weight: segWeight,
          }}
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
    </>
  )
})

// One route's whole line as a single multi-polyline. Memoised on primitive
// props: hovering a route re-renders two lines, not the whole map.
const RouteLine = memo(function RouteLine({
  route,
  all,
  hot,
  dimmed,
  hidden,
  colourBy,
  onSelect,
  onHover,
}: {
  route: Route
  all: [number, number][][]
  hot: boolean
  dimmed: boolean
  hidden: boolean
  colourBy: ColourBy
  onSelect: (code: string) => void
  onHover: (code: string | null) => void
}) {
  const counted = route.peakPct !== null
  const zoom = useZoom()
  // In "By route" only the counted routes get an identity hue; the rest keep
  // grey and dashes so the five measured routes stay the loud ones.
  const identity = colourBy === 'route' ? ROUTE_COLOUR[route.code] : undefined
  const pathOptions = useMemo<L.PathOptions>(
    () =>
      counted
        ? {
            ...LINE,
            color: identity ?? COLOUR[route.band],
            weight: groundWidth(hot ? W.routeHot : W.route, zoom),
            opacity: hidden ? 0 : dimmed ? 0.15 : 1,
          }
        : {
            ...LINE,
            color: COLOUR.unknown,
            weight: groundWidth(hot ? W.unknownHot : W.unknown, zoom),
            opacity: hidden ? 0 : dimmed ? 0.2 : 0.95,
            dashArray: '7 5',
          },
    [counted, hot, dimmed, hidden, route.band, identity, zoom],
  )
  const eventHandlers = useMemo(
    () => ({
      click: () => onSelect(route.code),
      mouseover: () => onHover(route.code),
      mouseout: () => onHover(null),
    }),
    [onSelect, onHover, route.code],
  )
  return (
    <Polyline positions={all} pathOptions={pathOptions} eventHandlers={eventHandlers}>
      <Tooltip sticky>
        <b>{route.code}</b> · {route.name}
        <br />
        {loadText(route)}
        <br />
        <i>Click to see this route</i>
      </Tooltip>
    </Polyline>
  )
})

// All 97 stops at once. Unselected-route stops stay small and quiet so the
// lines still read; the selected route's stops grow and offer a tooltip. Stops
// are drawn whether or not a route is focused - an unlabelled dot on the map
// is still the answer to "where does the bus stop".
const Stops = memo(function Stops({
  stops,
  selectedCode,
}: {
  stops: Stop[]
  selectedCode: string | null
}) {
  // Stops shrink with the lines, or they would dominate the thinner routes at
  // overview; the selected route's stops stay big enough to hit.
  const zoom = useZoom()
  const scale = Math.min(1, Math.max(0.8, Math.pow(2, zoom - SCALE_ZOOM)))
  return (
    <>
      {stops.map((s) => {
        const mine = selectedCode === null || s.routes.includes(selectedCode)
        return (
          <CircleMarker
            key={s.code}
            center={[s.lat, s.lon]}
            radius={mine ? 4 * scale : 2.5 * scale}
            pathOptions={{
              color: INK,
              weight: mine ? Math.max(1, 2 * scale) : Math.max(0.8, 1.2 * scale),
              fillColor: mine ? '#fff' : '#dfe3e6',
              fillOpacity: 1,
              opacity: mine ? 1 : 0.75,
            }}
            interactive={mine}
          >
            {mine && (
              <Tooltip direction="top" offset={[0, -4]}>
                <b>{s.name}</b>
                {s.nameDv && (
                  <>
                    {' '}
                    <span className="dv">{s.nameDv}</span>
                  </>
                )}
                <br />
                {s.routes.length > 1 ? `Routes ${s.routes.join(', ')}` : 'Served by this route only'}
                {selectedCode === null && mine ? ' · click a route to filter' : ''}
              </Tooltip>
            )}
          </CircleMarker>
        )
      })}
    </>
  )
})

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
  const [colourBy, setColourBy] = useState<ColourBy>('band')
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
        zoomSnap={1}
        zoomDelta={1}
        scrollWheelZoom
        ref={mapRef}
      >
        {basemap === 'osm' ? (
          <TileLayer
            url={TILE_URL}
            attribution={TILE_ATTRIBUTION}
            maxZoom={MAX_ZOOM}
            maxNativeZoom={19}
            // NO detectRetina. Leaflet implements it by halving tileSize and
            // doing zoomOffset++ / maxZoom--, so on any display with
            // devicePixelRatio > 1 (or browser zoom above 100%) the layer's
            // maxZoom silently becomes 18 and _setView bails out at map zoom
            // 19, loading no tiles at all - a blank map at full zoom.
            // OSM serves no @2x raster anyway, so it only fetched extra tiles.
            // keep the zoom animation smooth: no tile requests mid-zoom, and
            // hold the neighbouring levels so a zoom-out never shows blank
            updateWhenZooming={false}
            updateWhenIdle={false}
            keepBuffer={6}
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

        {/* routes: keyed by code and never unmounted, so selecting or hovering a
            route restyles one layer instead of rebuilding fifteen. The focused
            route keeps its slot (hidden) so the detail layers stack above it. */}
        {lines.map(({ route, all }) => (
          <RouteLine
            key={route.code}
            route={route}
            all={all}
            hot={hover === route.code && !selected}
            dimmed={!!selected}
            hidden={selected?.code === route.code}
            colourBy={colourBy}
            onSelect={onSelect}
            onHover={setHover}
          />
        ))}

        {/* Stops live in their own pane above the overlay pane, not inline with
            the routes. Every Polyline shares Leaflet's single SVG renderer, so
            stacking was decided by insertion order: the selected route's
            casing and segment lines are added after the stops and painted on
            top of all 97 of them. A separate pane makes the order explicit, so
            a stop is never hidden by a line regardless of which route is open. */}
        <Pane name="stops" style={{ zIndex: 450 }}>
          <Stops stops={data.stops} selectedCode={selected?.code ?? null} />
        </Pane>

        {focus && selected && (
          <>
            <FocusLines segments={focus.segs} identity={colourBy === 'route' ? ROUTE_COLOUR[selected.code] : undefined} />
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

      {/* Two meanings for one hue is the trap here: on this map colour normally
          means load, so the switch is explicit rather than automatic. */}
      <div className="card map-tools map-tools-colour">
        <span className="map-tools-label">Colour</span>
        <button
          className={colourBy === 'band' ? 'on' : ''}
          onClick={() => setColourBy('band')}
          title="Colour each line by how full the buses are"
        >
          How full
        </button>
        <button
          className={colourBy === 'route' ? 'on' : ''}
          onClick={() => setColourBy('route')}
          title="Give each route with passenger counts its own colour"
        >
          By route
        </button>
      </div>

      <div className="card map-title">
        {selected ? (
          <>
            <span
              className="chip"
              style={{
                background:
                  colourBy === 'route' ? (ROUTE_COLOUR[selected.code] ?? COLOUR[selected.band]) : COLOUR[selected.band],
              }}
            >
              {selected.code}
            </span>
            <span>
              <b>{selected.name}</b>
              <br />
              <small>
                {colourBy === 'route' && ROUTE_COLOUR[selected.code]
                  ? 'Colour identifies the route'
                  : 'Colour shows how full each stretch gets'}
              </small>
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

      <div className="card legend" aria-label={colourBy === 'route' ? 'Legend: route colours' : 'Legend: how full the buses get'}>
        {colourBy === 'route' ? (
          <>
            <div className="legend-title">Routes with passenger counts</div>
            {data.routes
              .filter((r) => ROUTE_COLOUR[r.code])
              .map((r) => (
                <div className="legend-row" key={r.code}>
                  <span className="swatch" style={{ borderColor: ROUTE_COLOUR[r.code] }} />
                  <b>{r.code}</b> {r.name}
                </div>
              ))}
            <div className="legend-row legend-sep">
              <span className="swatch dashed" style={{ borderColor: COLOUR.unknown }} />
              <span>No passenger counts (10)</span>
            </div>
          </>
        ) : (
          <>
            <div className="legend-title">Seats filled at the busiest time</div>
            {(['over', 'busy', 'room', 'unknown'] as Band[]).map((b) => (
              <div className="legend-row" key={b}>
                <span className={`swatch${b === 'unknown' ? ' dashed' : ''}`} style={{ borderColor: COLOUR[b] }} />
                {BAND_LABEL[b]}
              </div>
            ))}
          </>
        )}
        <div className="legend-row legend-sep">
          <span className="swatch-dot" aria-hidden />
          Bus stop ({data.stops.length})
        </div>
      </div>
    </>
  )
}
