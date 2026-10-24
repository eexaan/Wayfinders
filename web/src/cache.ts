// Registers the tile + data service worker (public/sw.js).
//
// It only ever answers tile requests and /data/*.csv|geojson|json, so it is safe
// in dev as well as in the built bundle: modules, the Vite client and HMR all
// pass through untouched.
export function registerCache() {
  if (!('serviceWorker' in navigator)) return
  if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`)
      .then((reg) => reg.update().catch(() => {}))
      .catch(() => {
        // a failed registration is not fatal: the map just fetches normally
      })
  })
}
