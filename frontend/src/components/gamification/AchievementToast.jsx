// TODO (Step 13): Achievement toast notification
// Appears bottom-right for 4 seconds when an achievement is earned
// Uses react-hot-toast custom toast
// Props: achievement { key, name, emoji }
export default function AchievementToast({ achievement }) {
  return (
    <div className="flex items-center gap-3 bg-white border border-signal rounded-xl px-4 py-3 shadow-lg">
      <span className="text-2xl">{achievement?.emoji}</span>
      <div>
        <p className="font-semibold text-text-primary text-sm">{achievement?.name}</p>
        <p className="text-text-muted text-xs">Achievement unlocked!</p>
      </div>
    </div>
  )
}
