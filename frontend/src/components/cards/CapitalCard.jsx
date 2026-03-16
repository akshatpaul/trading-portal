import { formatINR } from '../../utils/formatters'

export default function CapitalCard({ capital = 0, mode = 'paper' }) {
  const isLive = mode === 'live'
  return (
    <div className="card">
      <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">Capital</p>
      <p className="font-mono text-2xl font-bold text-text-primary leading-none">{formatINR(capital)}</p>
      <p className="text-text-muted text-xs mt-1.5 flex items-center gap-1">
        <span>{isLive ? '💰' : '📝'}</span>
        <span>{isLive ? 'Live account' : 'Paper account'}</span>
      </p>
    </div>
  )
}
