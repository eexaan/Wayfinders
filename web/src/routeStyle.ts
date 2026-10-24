// Palette and geometry helpers for drawing several bus routes on one map.
//
// Two problems this solves:
//   1. Colour. A network coloured by "service class" tells you nothing about
//      which route you are looking at. Every route gets its own hue, spaced
//      around the wheel so neighbours on the map are never the same colour.
//   2. Overlap. Where two or more routes share a road - and on the bridge they
//      all do - drawing them at the same coordinates hides all but the last one.
//      Each route is therefore displaced perpendicular to its own direction by a
//      few metres, so the shared stretch reads as a bundle of parallel lines
//      instead of one line.

export const ROUTE_COLOURS = [
  '#c2410c', // burnt orange
  '#1d4ed8', // blue
  '#0f766e', // teal
  '#7e22ce', // purple
  '#b91c1c', // red
  '#4d7c0f', // olive
  '#a16207', // amber
  '#be185d', // magenta
  '#0369a1', // cyan
  '#4338ca', // indigo
  '#15803d', // green
  '#9a3412', // brown
  '#6d28d9', // violet
  '#0e7490', // dark teal
  '#a21caf', // fuchsia
]

// Hulhumalé loops (L1..) have their own hues, so L1 never shares R1's colour.
const LOOP_COLOURS = ['#16a34a', '#e11d48', '#111827', '#84cc16', '#06b6d4']

/** Stable colour per route id, so N03 is the same colour on every render. */
export function routeColour(routeId: string): string {
  if (/^L\d+$/.test(routeId)) {
    const k = Number.parseInt(routeId.slice(1), 10) - 1
    return LOOP_COLOURS[((k % LOOP_COLOURS.length) + LOOP_COLOURS.length) % LOOP_COLOURS.length]
  }
  const n = Number.parseInt(routeId.replace(/\D/g, ''), 10)
  const i = Number.isFinite(n) ? n - 1 : 0
  const len = ROUTE_COLOURS.length
  return ROUTE_COLOURS[((i % len) + len) % len]
}

// Metres per degree at Malé's latitude. Good enough for a visual offset.
const M_PER_DEG_LAT = 110574
const M_PER_DEG_LON = 111320 * Math.cos((4.17 * Math.PI) / 180)

/**
 * Displace a lat/lon polyline sideways by `metres`, positive to the left of
 * travel. Returns a new array; the input is not modified.
 *
 * The offset is applied per-vertex using the average direction of the adjacent
 * segments, which keeps corners reasonable without a full miter join. At the
 * scale this is used (6-10 m) the error is invisible.
 */
export function offsetLine(coords: [number, number][], metres: number): [number, number][] {
  if (!coords.length || Math.abs(metres) < 0.01) return coords
  const n = coords.length
  const out: [number, number][] = new Array(n)

  const dirAt = (i: number): [number, number] => {
    const a = coords[Math.max(0, i - 1)]
    const b = coords[Math.min(n - 1, i + 1)]
    const dy = b[0] - a[0]
    const dx = b[1] - a[1]
    const len = Math.hypot(dx * M_PER_DEG_LON, dy * M_PER_DEG_LAT) || 1
    return [(dx * M_PER_DEG_LON) / len, (dy * M_PER_DEG_LAT) / len] // unit vector, metres
  }

  for (let i = 0; i < n; i++) {
    const [ux, uy] = dirAt(i)
    // left normal of the unit direction
    const nx = -uy
    const ny = ux
    out[i] = [
      coords[i][0] + (ny * metres) / M_PER_DEG_LAT,
      coords[i][1] + (nx * metres) / M_PER_DEG_LON,
    ]
  }
  return out
}

/**
 * Perpendicular displacement for route `index` of `groupSize` routes that share
 * a corridor. Centred on zero so a two-route overlap is symmetric.
 *
 * The default spacing is deliberately tiny (2.5 m). At the zoom this map is
 * read at, a 9 m offset turns one busy road into a bundle of wiggling parallel
 * lines; 2.5 m still separates two colours without pretending the road is
 * wider than it is.
 */
export function laneOffset(index: number, groupSize: number, spacingM = 2.5): number {
  if (groupSize <= 1) return 0
  return (index - (groupSize - 1) / 2) * spacingM
}

/**
 * Quantised road-segment key, for deciding which routes genuinely share a road.
 *
 * Coordinates are rounded to ~11 m before pairing, so two routes that were
 * routed independently still match when they use the same street. Without the
 * rounding, floating-point differences make every route look unshared.
 */
export function edgeKeys(coords: [number, number][]): string[] {
  const q = (v: number) => Math.round(v * 1e4) / 1e4
  const out: string[] = []
  for (let i = 0; i < coords.length - 1; i++) {
    const a = `${q(coords[i][0])},${q(coords[i][1])}`
    const b = `${q(coords[i + 1][0])},${q(coords[i + 1][1])}`
    out.push(a <= b ? `${a}|${b}` : `${b}|${a}`)
  }
  return out
}
