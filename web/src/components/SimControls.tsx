import { fmtClock } from '../reroute'

const SPEEDS = [1, 5, 10] as const

export function SimControls({
  clock,
  startMin,
  endMin,
  playing,
  speed,
  seed,
  onPlay,
  onSpeed,
  onScrub,
  onReset,
  onSeed,
  onSkip,
  onFlights,
  density,
}: {
  clock: number
  startMin: number
  endMin: number
  playing: boolean
  speed: number
  seed: number
  onPlay: () => void
  onSpeed: (s: number) => void
  onScrub: (min: number) => void
  onReset: () => void
  onSeed: (n: number) => void
  onSkip: () => void
  onFlights: () => void
  density: number
}) {
  const span = endMin - startMin
  const pct = span ? ((clock - startMin) / span) * 100 : 0
  return (
    <div className="card sim-controls">
      <div className="sim-row">
        <button className="sim-play" onClick={onPlay} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <div className="sim-clock num">{fmtClock(clock)}</div>
        <div className="sim-speed" role="radiogroup" aria-label="Simulation speed">
          {SPEEDS.map((s) => (
            <button key={s} aria-pressed={speed === s} onClick={() => onSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
        <button className="link-btn" onClick={onSkip} title="Run the rest of the day instantly">
          Skip to results
        </button>
      </div>

      <div className="sim-track">
        <input
          type="range"
          min={startMin}
          max={endMin}
          step={1}
          value={Math.round(clock)}
          onChange={(e) => onScrub(Number(e.target.value))}
          aria-label="Time of day"
        />
        <span className="sim-track-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="sim-row sim-meta">
        <span>
          <b className="num">{fmtClock(startMin)}–{fmtClock(endMin)}</b> ·{' '}
          {speed === 1 ? '1 sec = 1 min' : speed === 5 ? '5 min a second' : '10 min a second'}
          {speed === 10 ? ' — the whole day in under 2 minutes' : ''}
        </span>
        <span className="sim-density">
          queue {density} waiting
        </span>
      </div>

      <div className="sim-row sim-meta">
        <label className="sim-field">
          Seed
          <input
            type="number"
            value={seed}
            onChange={(e) => onSeed(Number(e.target.value) || 1)}
            title="The day is generated from this seed. Change it to see a different but equally valid day."
          />
        </label>
        <button className="link-btn" onClick={onReset}>
          Restart day
        </button>
        <button className="link-btn" onClick={onFlights} title="Add a bank of flight arrivals at VIA 90 minutes from now">
          + Flight bank
        </button>
      </div>
    </div>
  )
}
