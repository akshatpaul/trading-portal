export default function StatCard({ title, value, subtitle, icon, colorClass = 'text-text-primary', trend }) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : null
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : ''

  return (
    <div className="card flex items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="text-text-muted text-xs font-medium uppercase tracking-wider mb-1">{title}</p>
        <p className={`font-mono text-2xl font-bold leading-none ${colorClass}`}>{value}</p>
        {subtitle && (
          <p className="text-text-muted text-xs mt-1.5 flex items-center gap-1">
            {trendIcon && <span className={trendColor}>{trendIcon}</span>}
            {subtitle}
          </p>
        )}
      </div>
      {icon && (
        <span className="text-2xl flex-shrink-0 opacity-70">{icon}</span>
      )}
    </div>
  )
}
