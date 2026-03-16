import { useApp } from '../../context/AppContext'
import { formatSymbol } from '../../utils/formatters'

function ScoreBar({ score, max = 100 }) {
  const pct = Math.min(100, (score / max) * 100)
  const color = score >= 70 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-slate-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-text-secondary w-8 text-right">{score}</span>
    </div>
  )
}

export default function Watchlist({ onSelectSymbol }) {
  const { watchlist } = useApp()

  if (!watchlist || watchlist.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-sm text-text-primary mb-3">Today's Watchlist</h3>
        <div className="flex flex-col items-center py-6 text-center">
          <span className="text-2xl opacity-40 mb-2">📋</span>
          <p className="text-text-muted text-sm">No watchlist yet</p>
          <p className="text-text-muted text-xs mt-1">Screener runs before market open</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-text-primary">Today's Watchlist</h3>
        <span className="text-text-muted text-xs">{watchlist.length} stocks</span>
      </div>

      <div className="space-y-2">
        {watchlist.map((item, i) => {
          const sym = formatSymbol(item.symbol)
          const rank = item.rank ?? (i + 1)
          return (
            <div
              key={item.symbol}
              className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-700/50
                         cursor-pointer transition-colors group"
              onClick={() => onSelectSymbol?.(sym)}
              title="Click to view chart"
            >
              {/* Rank badge */}
              <span className="w-5 h-5 rounded-full bg-slate-700 text-text-muted text-xs
                               flex items-center justify-center font-mono flex-shrink-0 font-bold">
                {rank}
              </span>
              {/* Symbol */}
              <span className="font-mono font-semibold text-text-primary text-sm w-20 truncate
                               group-hover:text-signal transition-colors">
                {sym}
              </span>
              {/* Score bar */}
              <div className="flex-1">
                <ScoreBar score={item.score ?? 0} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
