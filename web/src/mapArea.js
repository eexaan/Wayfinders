// The network the app shows: Malé, the airport island (Hulhulé), Hulhumalé and
// Villimalé (R13/R14, lon ~73.483). Fit-to-network uses HOME_BOUNDS; the pan
// limit is a little wider so the coast and the Sinamalé Bridge read as context.
export const HOME_BOUNDS = [
  [4.162, 73.472],
  [4.244, 73.560],
]
export const PAN_BOUNDS = [
  [4.130, 73.440],
  [4.272, 73.600],
]
export const MIN_ZOOM = 12
export const MAX_ZOOM = 19

// OSM raster tiles stop at z19; the vector fallback renders to MAX_ZOOM itself.
export const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
