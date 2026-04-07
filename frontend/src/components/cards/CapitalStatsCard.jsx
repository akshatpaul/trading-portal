import { useQuery } from '@tanstack/react-query'
import { fetchCapitalStats } from '../../api'
import { formatINR, formatPnL, formatTime } from '../../utils/formatters'

export default function CapitalStatsCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['capital-stats'],
    queryFn: fetchCapitalStats,
    refetchInterval: 30000,
  })

  if (isLoading || !data) {
    return (
      <div className="card animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-3" />
        <div className="h-6 bg-slate-700 rounded w-1/2 mb-4" />
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => <div key={i} className="h-3 bg-slate-700 rounded" />)}
        </div>
      </div>
    )
  }

  const {
    capital,
    starting_capital,
    capital_floor,
    total_return,
    total_return_pct,
    monthly_pnl,
    monthly_trades,
    last_trade_time,
    capital_last_reset,
  } = data

  const returnFmt  = formatPnL(total_return)
  const monthlyFmt = formatPnL(monthly_pnl)

  // Capital bar: percent of way between floor and starting
  const range  = starting_capital - capital_floor
  const pct    = Math.min(Math.max((capital - capital_floor) / range, 0), 1)
  const barPct = Math.round(pct * 100)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <p className="text-text-muted text-xs font-medium uppercase tracking-wider">Portfolio</p>
        <span className="text-text-muted text-xs">Paper</span>
      </div>

      {/* Current capital + return */}
      <div className="flex items-end gap-3 mb-3">
        <p className="font-mono text-2xl font-bold text-text-primary leading-none">
          {formatINR(capital)}
        </p>
        <p className={`font-mono text-sm font-semibold mb-0.5 ${returnFmt.colorClass}`}>
          {returnFmt.text} ({total_return_pct >= 0 ? '+' : ''}{total_return_pct}%)
        </p>
      </div>

      {/* Capital bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-text-muted mb-1">
          <span>Floor {formatINR(capital_floor)}</span>
          <span>Start {formatINR(starting_capital)}</span>
        </div>
        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${barPct > 50 ? 'bg-emerald-500' : barPct > 25 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${barPct}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <p className="text-text-muted">This month</p>
          <p className={`font-mono font-semibold ${monthlyFmt.colorClass}`}>
            {monthlyFmt.text}
            {monthly_trades > 0 && (
              <span className="text-text-muted font-normal ml-1">({monthly_trades} trades)</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-text-muted">Starting capital</p>
          <p className="font-mono text-text-primary">{formatINR(starting_capital)}</p>
        </div>
        <div>
          <p className="text-text-muted">Last trade</p>
          <p className="font-mono text-text-primary">
            {last_trade_time ? formatTime(last_trade_time, 'datetime') : 'No trades yet'}
          </p>
        </div>
        <div>
          <p className="text-text-muted">Capital reset</p>
          <p className="font-mono text-text-primary">
            {capital_last_reset ? formatTime(capital_last_reset, 'datetime') : 'Never'}
          </p>
        </div>
      </div>
    </div>
  )
}
