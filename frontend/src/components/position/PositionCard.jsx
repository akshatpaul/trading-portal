import { formatINR, formatSymbol, formatTime, formatPnL } from '../../utils/formatters'
import { positionProgress } from '../../utils/calculations'

const STRATEGY_LABELS = {
  ema_crossover: 'EMA',
  relaxed_ema:   'Relaxed EMA',
  rsi_bounce:    'RSI',
  vwap_cross:    'VWAP',
}

function SinglePosition({ position }) {
  const {
    symbol, side, quantity, entry_price, target, stop_loss,
    ltp, unrealised_pnl, entry_time, strategy,
  } = position

  const pnl = formatPnL(unrealised_pnl)
  const isBuy = side?.toUpperCase() === 'BUY'
  const { pctToTarget } = positionProgress(entry_price, ltp, target, stop_loss, side?.toUpperCase())
  const strategyLabel = STRATEGY_LABELS[strategy] ?? strategy ?? 'EMA'

  const progressColor = isBuy
    ? (ltp >= entry_price ? 'bg-emerald-500' : 'bg-red-500')
    : (ltp <= entry_price ? 'bg-emerald-500' : 'bg-red-500')

  return (
    <div className="border-t border-card-border pt-3 first:border-t-0 first:pt-0">
      {/* Symbol + strategy badge + side */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-base text-text-primary">{formatSymbol(symbol)}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-text-muted">{strategyLabel}</span>
          <span className="text-text-muted text-xs">× {quantity}</span>
        </div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
          isBuy
            ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700/50'
            : 'bg-red-900/50 text-red-400 border-red-700/50'
        }`}>
          {side?.toUpperCase()}
        </span>
      </div>

      {/* Price row */}
      <div className="grid grid-cols-4 gap-2 mb-2 text-xs">
        <div>
          <p className="text-text-muted mb-0.5">Entry</p>
          <p className="font-mono text-text-primary">{formatINR(entry_price)}</p>
        </div>
        <div>
          <p className="text-text-muted mb-0.5">LTP</p>
          <p className="font-mono text-text-primary">{formatINR(ltp)}</p>
        </div>
        <div>
          <p className="text-text-muted mb-0.5">Target</p>
          <p className="font-mono text-emerald-400">{formatINR(target)}</p>
        </div>
        <div>
          <p className="text-text-muted mb-0.5">Stop</p>
          <p className="font-mono text-red-400">{formatINR(stop_loss)}</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-2">
        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
            style={{ width: `${Math.min(100, Math.max(2, pctToTarget))}%` }}
          />
        </div>
      </div>

      {/* P&L + time */}
      <div className="flex items-center justify-between">
        <span className="text-text-muted text-xs">{entry_time ? `Since ${formatTime(entry_time)}` : ''}</span>
        <span className={`font-mono font-semibold text-sm ${pnl.colorClass}`}>{pnl.text}</span>
      </div>
    </div>
  )
}

export default function PositionCard({ positions }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="card flex flex-col items-center justify-center gap-2 py-8 text-center">
        <span className="text-3xl opacity-40">📭</span>
        <p className="text-text-secondary text-sm font-medium">No open positions</p>
        <p className="text-text-muted text-xs">Waiting for next signal...</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-text-primary text-sm">Open Positions</h3>
        <span className="text-xs text-text-muted">{positions.length} / 3</span>
      </div>
      <div className="space-y-3">
        {positions.map(pos => (
          <SinglePosition key={pos.id} position={pos} />
        ))}
      </div>
    </div>
  )
}
