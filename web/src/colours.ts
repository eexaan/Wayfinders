import type { Band } from './data'

// Hex copies of the band tokens in index.css, for places CSS variables cannot
// reach (Leaflet writes SVG stroke attributes directly).
export const BAND_COLOUR: Record<Band, string> = {
  over: '#d1392e',
  busy: '#e8872a',
  room: '#8e979f',
  unknown: '#77828c',
}

// Identity colours for the five routes that carry passenger counts, used only
// when the map's colour mode is switched to "By route". The default mode keeps
// BAND_COLOUR, because on this map colour means load - these hues are for
// telling routes apart, not for reading them. The other ten routes have no
// colour here on purpose: they stay grey and dashed so the five measured ones
// are the ones that stand out.
export const ROUTE_COLOUR: Record<string, string> = {
  R1: '#d1392e', // red
  R2: '#2a6fd6', // blue
  R3: '#16794a', // green
  R4: '#7bc043', // lime green
  R7: '#17a2b8', // cyan
}
