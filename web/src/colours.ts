import type { Band } from './data'

// Hex copies of the band tokens in index.css, for places CSS variables cannot
// reach (Leaflet writes SVG stroke attributes directly).
export const BAND_COLOUR: Record<Band, string> = {
  over: '#d1392e',
  busy: '#e8872a',
  room: '#8e979f',
  unknown: '#77828c',
}
