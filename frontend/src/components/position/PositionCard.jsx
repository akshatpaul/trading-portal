import { formatINR, formatSymbol, formatTime, formatPnL } from '../../utils/formatters'
import { positionProgress } from '../../utils/calculations'

export default function PositionCard({ position }) {
  if (!position) {
    return (
      <div className="card flex flex-col items-center justify-center gap-2 py-8 text-center">
        <span className="text-3xl opacity-40">📭</span>
        <p className="text-text-secondary text-sm font-medium">No open position</p>
        <p className="text-text-muted text-xs">Waiting for next signal...</p>
      </div>
    )
  }

  const {
    symbol, side, quantity, entry_price, target, stop_loss,
    ltp, unrealised_pnl, entry_time, status,
  } = position

  const pnl = formatPnL(unrealised_pnl)
  const isBuy = side?.toUpperCase() === 'BUY'
  const { pctToTarget } = positionProgress(entry_price, ltp, target, stop_loss, side?.toUpperCase())

  const progressColor = isBuy
    ? (ltp >= entry_price ? 'bg-emerald-500' : 'bg-red-500')
    : (ltp <= entry_price ? 'bg-emerald-500' : 'bg-red-500')

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-text-primary text-sm">Open Position</h3>
        <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
          isBuy
            ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700/50'
            : 'bg-red-900/50 text-red-400 border-red-700/50'
        }`}>
          {side?.toUpperCase()}
        </span>
      </div>

      {/* Symbol + Qty */}
      <div className="flex items-baseline gap-2 mb-3">
        <span className="font-mono font-bold text-xl text-text-primary">{formatSymbol(symbol)}</span>
        <span className="text-text-muted text-sm">× {quantity}</span>
      </div>

      {/* Price row */}
      <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
        <div>
          <p className="text-text-muted text-xs mb-0.5">Entry</p>
          <p className="font-mono text-text-primary">{formatINR(entry_price)}</p>
        </div>
        <div>
          <p className="text-text-muted text-xs mb-0.5">LTP</p>
          <p className="font-mono text-text-primary">{formatINR(ltp)}</p>
        </div>
        <div>
          <p className="text-text-muted text-xs mb-0.5">Target</p>
          <p className="font-mono text-emerald-400">{formatINR(target)}</p>
        </div>
        <div>
          <p className="text-text-muted text-xs mb-0.5">Stop Loss</p>
          <p className="font-mono text-red-400">{formatINR(stop_loss)}</p>
        </div>
      </div>

      {/* Progress bar (entry → target/stop) */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-text-muted mb-1">
          <span>SL {formatINR(stop_loss)}</span>
          <span>TGT {formatINR(target)}</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
            style={{ width: `${Math.min(100, Math.max(2, pctToTarget))}%` }}
          />
        </div>
      </div>

      {/* Unrealised P&L */}
      <div className="flex items-center justify-between border-t border-card-border pt-3">
        <span className="text-text-muted text-xs">Unrealised P&L</span>
        <span className={`font-mono font-bold text-base ${pnl.colorClass}`}>
          {pnl.text}
        </span>
      </div>

      {entry_time && (
        <p className="text-text-muted text-xs mt-2">
          Entered at {formatTime(entry_time)}
        </p>
      )}
    </div>
  )
}
