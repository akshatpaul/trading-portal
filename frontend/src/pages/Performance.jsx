import { useQuery } from '@tanstack/react-query'
import { fetchPerformance, fetchTrades } from '../api'
import { formatPnL } from '../utils/formatters'
import { calcStreak } from '../utils/calculations'
import { GO_LIVE_CRITERIA } from '../utils/constants'

function StatRow({ label, value, colorClass }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-card-border last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <span className={`font-mono font-semibold text-sm ${colorClass || 'text-text-primary'}`}>{value}</span>
    </div>
  )
}

// Mini P&L equity curve using SVG
function EquityCurve({ trades }) {
  if (!trades || trades.length < 2) {
    return (
      <div className="h-32 flex items-center justify-center text-text-muted text-sm">
        Not enough data
      </div>
    )
  }

  const sorted = [...trades].sort((a, b) =>
    new Date(a.entry_time) - new Date(b.entry_time)
  )

  let cum = 0
  const points = sorted.map((t, i) => {
    cum += (t.net_pnl ?? t.pnl ?? 0)
    return { i, v: cum }
  })

  const values = points.map(p => p.v)
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 0)
  const range = max - min || 1
  const W = 400, H = 100

  const coords = points.map(p => {
    const x = (p.i / (points.length - 1)) * W
    const y = H - ((p.v - min) / range) * H
    return `${x},${y}`
  })

  const lastVal  = values[values.length - 1]
  const lineColor = lastVal >= 0 ? '#10b981' : '#ef4444'
  const fillStart = lastVal >= 0 ? '#10b98120' : '#ef444420'

  // Build fill area
  const fillPath = `M${coords[0]} L${coords.join(' L')} L${W},${H} L0,${H} Z`

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-32" preserveAspectRatio="none">
      {/* Zero line */}
      <line
        x1="0" y1={H - ((0 - min) / range) * H}
        x2={W} y2={H - ((0 - min) / range) * H}
        stroke="#334155" strokeDasharray="4,4" strokeWidth="1"
      />
      <path d={fillPath} fill={fillStart} />
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={lineColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// Go-live criteria checklist
function GoLiveCriteria({ perf, trades }) {
  if (!perf) return null

  const totalTrades = perf.trades_count || 0
  const wr = perf.win_rate || 0
  const pf = perf.profit_factor || 0
  const netPnl = perf.net_pnl || 0

  const criteria = [
    {
      label: 'Minimum 30 trades',
      met: totalTrades >= GO_LIVE_CRITERIA.min_trades,
      value: `${totalTrades} / ${GO_LIVE_CRITERIA.min_trades}`,
    },
    {
      label: 'Win rate ≥ 50%',
      met: wr >= GO_LIVE_CRITERIA.min_win_rate * 100,
      value: `${wr.toFixed(1)}%`,
    },
    {
      label: 'Profit factor ≥ 1.5',
      met: pf >= GO_LIVE_CRITERIA.min_profit_factor,
      value: isFinite(pf) ? pf.toFixed(2) : '∞',
    },
    {
      label: 'Net P&L positive',
      met: netPnl > 0,
      value: `₹${netPnl.toFixed(2)}`,
    },
  ]

  const allMet = criteria.every(c => c.met)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-text-primary">Go-Live Readiness</h3>
        {allMet ? (
          <span className="badge-live">✓ Ready for Live</span>
        ) : (
          <span className="badge-paper">Keep Paper Trading</span>
        )}
      </div>

      <div className="space-y-2">
        {criteria.map((c, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-card-border last:border-0">
            <div className="flex items-center gap-2">
              <span className={c.met ? 'text-emerald-400' : 'text-slate-500'}>
                {c.met ? '✓' : '○'}
              </span>
              <span className={`text-sm ${c.met ? 'text-text-primary' : 'text-text-muted'}`}>{c.label}</span>
            </div>
            <span className={`font-mono text-sm font-semibold ${c.met ? 'text-emerald-400' : 'text-text-secondary'}`}>
              {c.value}
            </span>
          </div>
        ))}
      </div>

      {!allMet && (
        <p className="text-text-muted text-xs mt-3">
          Complete all criteria before switching to live trading.
        </p>
      )}
    </div>
  )
}

export default function Performance() {
  const perfQ = useQuery({
    queryKey: ['performance'],
    queryFn: fetchPerformance,
    refetchInterval: 30000,
  })

  const tradesQ = useQuery({
    queryKey: ['trades-all'],
    queryFn: () => fetchTrades(200),
    refetchInterval: 60000,
  })

  const perf   = perfQ.data
  const trades = tradesQ.data?.trades || []
  const streak = calcStreak(trades)

  if (perfQ.isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="card h-32 animate-pulse bg-slate-800" />
        ))}
      </div>
    )
  }

  if (perfQ.error) {
    return (
      <div className="card text-center py-10">
        <p className="text-red-400">Failed to load performance data</p>
        <p className="text-text-muted text-sm mt-1">{perfQ.error.message}</p>
      </div>
    )
  }

  const winRatePct  = perf?.win_rate ?? 0
  const grossPnl    = formatPnL(perf?.gross_pnl)
  const netPnl      = formatPnL(perf?.net_pnl)
  const bestTrade   = formatPnL(perf?.best_trade)
  const worstTrade  = formatPnL(perf?.worst_trade)
  const avgWin      = formatPnL(perf?.avg_win)
  const avgLoss     = formatPnL(perf?.avg_loss)
  const pf          = perf?.profit_factor

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Stats */}
        <div className="card">
          <h3 className="font-semibold text-text-primary mb-3">Overall Statistics</h3>
          <StatRow label="Total Trades"    value={perf?.trades_count ?? 0} />
          <StatRow label="Wins"            value={perf?.wins ?? 0} colorClass="text-emerald-400" />
          <StatRow label="Losses"          value={perf?.losses ?? 0} colorClass="text-red-400" />
          <StatRow label="Win Rate"        value={`${winRatePct.toFixed(1)}%`}
                   colorClass={winRatePct >= 50 ? 'text-emerald-400' : 'text-red-400'} />
          <StatRow label="Profit Factor"
                   value={isFinite(pf) ? pf?.toFixed(2) ?? '—' : '∞'}
                   colorClass={pf >= 1.5 ? 'text-emerald-400' : 'text-amber-400'} />
          <StatRow label="Gross P&L"  value={grossPnl.text} colorClass={grossPnl.colorClass} />
          <StatRow label="Net P&L"    value={netPnl.text}   colorClass={netPnl.colorClass}   />
        </div>

        {/* Bests */}
        <div className="card">
          <h3 className="font-semibold text-text-primary mb-3">Personal Bests</h3>
          <StatRow label="Best Trade"   value={bestTrade.text}  colorClass={bestTrade.colorClass} />
          <StatRow label="Worst Trade"  value={worstTrade.text} colorClass={worstTrade.colorClass} />
          <StatRow label="Avg Win"      value={avgWin.text}     colorClass={avgWin.colorClass} />
          <StatRow label="Avg Loss"     value={avgLoss.text}    colorClass={avgLoss.colorClass} />
          <StatRow label="Current Streak" value={`${streak} 🔥`}
                   colorClass={streak > 0 ? 'text-amber-400' : 'text-text-secondary'} />
        </div>
      </div>

      {/* Equity curve */}
      <div className="card">
        <h3 className="font-semibold text-text-primary mb-3">Equity Curve</h3>
        <EquityCurve trades={trades} />
      </div>

      {/* Go-live readiness */}
      <GoLiveCriteria perf={perf} trades={trades} />
    </div>
  )
}

