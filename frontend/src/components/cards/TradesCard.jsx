import { calcStreak } from '../../utils/calculations'

export default function TradesCard({ trades = [] }) {
  const streak = calcStreak(trades)

  const getStreakEmoji = (s) => {
    if (s >= 10) return '🔥🔥🔥'
    if (s >= 5)  return '🔥🔥'
    if (s >= 1)  return '🔥'
    return '—'
  }

  return (
    <div className="card">
      <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">Win Streak</p>
      <div className="flex items-center gap-2">
        <p className="font-mono text-2xl font-bold text-amber-400 leading-none">{streak}</p>
        <span className="text-xl">{getStreakEmoji(streak)}</span>
      </div>
      <p className="text-text-muted text-xs mt-1.5">
        {streak > 0 ? `${streak} consecutive win${streak > 1 ? 's' : ''}` : 'No active streak'}
      </p>
    </div>
  )
}
