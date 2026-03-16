import { formatPnL } from '../../utils/formatters'

export default function PnLCard({ pnl = 0, trades = 0 }) {
  const { text, colorClass } = formatPnL(pnl)
  const isPositive = pnl >= 0

  return (
    <div className="card">
      <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">Today P&L</p>
      <p className={`font-mono text-2xl font-bold leading-none ${colorClass}`}>{text}</p>
      <p className="text-text-muted text-xs mt-1.5 flex items-center gap-1">
        <span>{isPositive ? '📈' : '📉'}</span>
        <span>{trades} trade{trades !== 1 ? 's' : ''} today</span>
      </p>
    </div>
  )
}
