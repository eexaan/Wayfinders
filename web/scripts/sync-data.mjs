// Copy the frozen data contract (../dashboard/data) into public/data so the app
// always reads exactly what build_data.py and snap_routes.py produced.
// Runs automatically before `npm run dev` and `npm run build`.
import { cp, rm } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = join(here, '..', '..', 'dashboard', 'data')
const dest = join(here, '..', 'public', 'data')

await rm(dest, { recursive: true, force: true })
await cp(src, dest, { recursive: true, filter: (p) => !p.endsWith('.DS_Store') })
console.log(`data: ${src} -> public/data`)
