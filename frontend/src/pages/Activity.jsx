import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchActivity } from '../api'
import { formatSymbol } from '../utils/formatters'

const EVENT_META = {
  screener:      { icon: '🔍', label: 'Screener',     color: 'text-indigo-400',  bg: 'bg-indigo-500/10 border-indigo-500/20' },
  signal:        { icon: '📡', label: 'Signal',       color: 'text-blue-400',    bg: 'bg-blue-500/10 border-blue-500/20' },
  trade_entry:   { icon: '🟢', label: 'Trade Entry',  color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
  trade_exit:    { icon: '🏁', label: 'Trade Exit',   color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/20' },
  force_close:   { icon: '⏰', label: 'Force Close',  color: 'text-orange-400',  bg: 'bg-orange-500/10 border-orange-500/20' },
  risk_block:    { icon: '🛡️', label: 'Risk Block',   color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20' },
  daily_summary: { icon: '📊', label: 'Day Summary',  color: 'text-purple-400',  bg: 'bg-purple-500/10 border-purple-500/20' },
  system:        { icon: '⚙️', label: 'System',       color: 'text-slate-400',   bg: 'bg-slate-500/10 border-slate-500/20' },
}

function formatTime(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return isoStr }
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  try {
    return new Date(isoStr).toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit', month: 'short', year: 'numeric',
    })
  } catch { return isoStr }
}

function todayIST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
}

function ActivityRow({ entry }) {
  const meta = EVENT_META[entry.event_type] || EVENT_META.system
  const sym = entry.symbol ? formatSymbol(entry.symbol) : null

  return (
    <div className={`flex gap-3 items-start p-3 rounded-lg border ${meta.bg}`}>
      <span className="text-lg flex-shrink-0 mt-0.5">{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold uppercase tracking-wide ${meta.color}`}>
            {meta.label}
          </span>
          {sym && (
            <span className="text-xs font-mono bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
              {sym}
            </span>
          )}
          <span className="text-xs text-text-muted ml-auto font-mono">
            {formatTime(entry.timestamp)}
          </span>
        </div>
        <p className="text-sm text-text-primary mt-0.5">{entry.message}</p>
      </div>
    </div>
  )
}

function DateGroup({ date, entries }) {
  return (
    <div>
      <div className="flex items-center gap-3 my-4">
        <div className="h-px flex-1 bg-card-border" />
        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider px-2">
          {date}
        </span>
        <div className="h-px flex-1 bg-card-border" />
      </div>
      <div className="space-y-2">
        {entries.map(e => <ActivityRow key={e.id} entry={e} />)}
      </div>
    </div>
  )
}

export default function Activity() {
  const [dateFilter, setDateFilter] = useState(todayIST())

  const { data, isLoading, error } = useQuery({
    queryKey: ['activity', dateFilter],
    queryFn: () => fetchActivity(200, dateFilter || null),
    refetchInterval: 30000,
  })

  const entries = data?.activity || []

  // Group by date
  const groups = {}
  for (const e of entries) {
    const d = formatDate(e.timestamp)
    if (!groups[d]) groups[d] = []
    groups[d].push(e)
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header + filter */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-text-primary">Activity Log</h2>
          <p className="text-sm text-text-muted mt-0.5">Everything that happened — screener, signals, trades, risk blocks</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Date</label>
          <input
            type="date"
            value={dateFilter}
            onChange={e => setDateFilter(e.target.value)}
            className="bg-slate-800 border border-card-border text-text-primary text-sm rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-emerald-500"
          />
          {dateFilter && (
            <button
              onClick={() => setDateFilter('')}
              className="text-xs text-text-muted hover:text-text-primary px-2 py-1 rounded border border-card-border"
            >
              All
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="text-center text-text-muted py-12 text-sm">Loading activity...</div>
      )}
      {error && (
        <div className="text-center text-red-400 py-12 text-sm">Failed to load activity log</div>
      )}
      {!isLoading && !error && entries.length === 0 && (
        <div className="card text-center py-16">
          <p className="text-text-muted text-sm">No activity recorded for this date.</p>
          <p className="text-text-muted text-xs mt-1">Activity will appear here once the market opens and the strategy starts running.</p>
        </div>
      )}
      {!isLoading && Object.entries(groups).map(([date, groupEntries]) => (
        <DateGroup key={date} date={date} entries={groupEntries} />
      ))}
    </div>
  )
}
