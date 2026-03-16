// Win Rate circular ring card
function WinRateRing({ pct }) {
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference
  const color = pct >= 60 ? '#10b981' : pct >= 45 ? '#f59e0b' : '#ef4444'

  return (
    <svg width="72" height="72" className="flex-shrink-0">
      <circle cx="36" cy="36" r={radius} fill="none" stroke="#1e293b" strokeWidth="5" />
      <circle
        cx="36" cy="36" r={radius}
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="ring-progress"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="36" y="41" textAnchor="middle" fill={color} fontSize="13" fontFamily="JetBrains Mono, monospace" fontWeight="700">
        {pct.toFixed(0)}%
      </text>
    </svg>
  )
}

export default function WinRateCard({ wins = 0, losses = 0 }) {
  const total = wins + losses
  const pct   = total > 0 ? (wins / total) * 100 : 0

  return (
    <div className="card flex items-center gap-4">
      <WinRateRing pct={pct} />
      <div>
        <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">Win Rate</p>
        <div className="flex gap-3 text-sm">
          <span className="text-emerald-400 font-mono">{wins}W</span>
          <span className="text-red-400 font-mono">{losses}L</span>
        </div>
        <p className="text-text-muted text-xs mt-1">{total} trades today</p>
      </div>
    </div>
  )
}
