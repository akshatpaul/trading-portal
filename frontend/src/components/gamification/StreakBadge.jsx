// TODO (Step 13): Streak badge
// Shows "🔥 N-day winning streak" in stat card or TopBar
export default function StreakBadge({ streak }) {
  return <span>{streak > 0 ? `🔥 ${streak}-day streak` : '—'}</span>
}
