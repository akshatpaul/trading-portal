// TODO (Step 13): Weekly trade progress bar
// Goal: 10 trades per week, resets Monday
// Shows progress bar + "X/10 trades this week"
export default function WeeklyProgress({ count = 0, goal = 10 }) {
  const pct = Math.min((count / goal) * 100, 100)
  return <div>{/* TODO */}</div>
}
