import { useEffect, useState } from 'react'

import { loadData, type Data } from './data'
import { RouteMap } from './components/RouteMap'
import { RouteRanking } from './components/RouteRanking'
import { HourlyChart } from './components/HourlyChart'
import { RoutePanel } from './components/RoutePanel'
import { Scenarios } from './components/Scenarios'
import { MethodDrawer } from './components/MethodDrawer'
import { VintageLine } from './components/VintageLine'

type Tab = 'overview' | 'scenarios'

// #overview, #overview/R1, #scenarios/S5 - so the demo path can be bookmarked
function readHash(): { tab: Tab; arg: string | null } {
  const [tab, arg] = window.location.hash.replace(/^#/, '').split('/')
  return { tab: tab === 'scenarios' ? 'scenarios' : 'overview', arg: arg || null }
}

export default function App() {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [{ tab, arg }, setNav] = useState(readHash)
  const [drawer, setDrawer] = useState(false)

  useEffect(() => {
    loadData().then(setData, (e) => setError(String(e)))
    const onHash = () => setNav(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (t: Tab, a: string | null = null) => {
    window.location.hash = a ? `${t}/${a}` : t
  }

  const selected = tab === 'overview' && arg && data?.byCode[arg] ? data.byCode[arg] : null
  const selectRoute = (code: string | null) => go('overview', code === selected?.code ? null : code)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Raajje Rebalancer</h1>
          <p>Greater Malé buses: where seats and passengers don't match</p>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'overview'} onClick={() => go('overview', selected?.code)}>
            Where it breaks
          </button>
          <button role="tab" aria-selected={tab === 'scenarios'} onClick={() => go('scenarios')}>
            What if we change it?
          </button>
        </nav>
        <button className="link-btn" onClick={() => setDrawer(true)}>
          About the data
        </button>
      </header>

      {error && <p className="loading">Could not load the data: {error}</p>}
      {!data && !error && <p className="loading">Loading…</p>}

      {data && tab === 'overview' && (
        <main>
          <div className="overview">
            <section className="card map-card" aria-label="Route map">
              <RouteMap data={data} selected={selected} onSelect={selectRoute} />
            </section>
            <div className="side">
              <section className="card">
                <RouteRanking data={data} selected={selected} onSelect={selectRoute} />
              </section>
              {selected ? (
                <section className="card panel-scroll">
                  <RoutePanel data={data} route={selected} onClose={() => selectRoute(null)} />
                </section>
              ) : (
                <section className="card chart-card">
                  <h2 className="card-h">When it breaks: passengers vs seats, hour by hour</h2>
                  <p className="card-sub">All 5 routes with passenger counts, combined. Click a route to see its own.</p>
                  <HourlyChart points={data.networkHourly} />
                </section>
              )}
            </div>
          </div>
        </main>
      )}

      {data && tab === 'scenarios' && (
        <main>
          <Scenarios data={data} active={arg ?? 'S5'} onPick={(s) => go('scenarios', s)} />
        </main>
      )}

      {data && <VintageLine data={data} onMore={() => setDrawer(true)} />}
      {data && drawer && <MethodDrawer data={data} onClose={() => setDrawer(false)} />}
    </div>
  )
}
