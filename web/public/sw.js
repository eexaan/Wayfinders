// Tile and data cache for the Wayfinder dashboard.
//
// Two things are slow on a venue laptop: re-downloading the same OSM tiles when
// you zoom back to a level you already looked at, and re-fetching half a
// megabyte of GeoJSON/CSV every reload. Both are immutable within a build, so
// they are cached here.
//
// Nothing else is intercepted - application code, the Vite dev client and API
// calls all pass straight through, so this cannot serve a stale bundle.
//
// OSM's tile usage policy asks clients not to bulk-download; the trim below
// keeps only the tiles actually viewed (LRU by insertion order).

const TILE_CACHE = 'wf-tiles-v3'
const DATA_CACHE = 'wf-data-v3'
const MAX_TILES = 900

const TILE_HOST = 'tile.openstreetmap.org'
const isTile = (url) => url.hostname === TILE_HOST
const isData = (url) =>
  url.origin === self.location.origin && /\/data\/[^/]+\.(csv|geojson|json)$/.test(url.pathname)

// Take over from an older version on the next load instead of waiting for
// every tab to close (the dashboard is often left open on a demo screen).
self.addEventListener('install', (event) => event.waitUntil(self.skipWaiting()))

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([TILE_CACHE, DATA_CACHE])
      for (const name of await caches.keys()) if (!keep.has(name)) await caches.delete(name)
      await self.clients.claim()
    })(),
  )
})

// Re-inserting an entry moves it to the end of the cache's key order, which is
// how the tile cache stays a rough LRU without storing extra bookkeeping.
async function trim(cache) {
  const keys = await cache.keys()
  if (keys.length <= MAX_TILES) return
  for (const key of keys.slice(0, keys.length - MAX_TILES)) await cache.delete(key)
}

// Leaflet loads tiles with <img>, i.e. a no-cors request whose response is
// opaque: status 0, ok === false, headers unreadable. That made a FAILED tile
// indistinguishable from a good one, so `res.type === 'opaque'` was accepted as
// cacheable and every error response got stored - then served cache-first
// forever. One burst of OSM rate-limiting was enough to poison the cache for
// good, which is why the map came back as a grid of blank squares.
//
// tile.openstreetmap.org sends `Access-Control-Allow-Origin: *`, so tiles are
// re-fetched in CORS mode here. That makes the status and content-type readable,
// so only a real 200 carrying an image is ever stored.
const fetchTile = async (request) => {
  const res = await fetch(request.url, { mode: 'cors', credentials: 'omit' })
  if (!res.ok) throw new Error(`tile ${res.status}`)
  const type = res.headers.get('content-type') || ''
  if (!type.startsWith('image/')) throw new Error(`tile is ${type}, not an image`)
  return res
}

async function cacheFirstTile(request) {
  const cache = await caches.open(TILE_CACHE)
  const hit = await cache.match(request)
  if (hit) return hit
  try {
    const res = await fetchTile(request)
    await cache.put(request, res.clone())
    trim(cache)
    return res
  } catch {
    // Deliberately NOT cached: a later load must be free to retry the tile.
    return new Response('', { status: 504, statusText: 'Tile unavailable' })
  }
}

const cacheable = (res) => res.ok

// Vite answers an unknown path with index.html at status 200, so a missing
// /data/foo.json arrives as HTML. Caching that poisons the entry for good.
const isHtml = (res) => (res.headers.get('content-type') || '').includes('text/html')

// Local data is cheap to fetch from :5173 but expensive to re-download over a
// hotel connection, so the cache answers immediately and refreshes behind us.
async function staleWhileRevalidate(request, cacheName, event) {
  const cache = await caches.open(cacheName)
  const hit = await cache.match(request)
  const network = fetch(request).then((res) => {
    if (cacheable(res) && !isHtml(res)) cache.put(request, res.clone())
    return res
  })
  if (hit) {
    event.waitUntil(network.catch(() => {}))
    return hit
  }
  return network
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  let url
  try {
    url = new URL(request.url)
  } catch {
    return
  }
  if (isTile(url)) event.respondWith(cacheFirstTile(request))
  else if (isData(url)) event.respondWith(staleWhileRevalidate(request, DATA_CACHE, event))
})
