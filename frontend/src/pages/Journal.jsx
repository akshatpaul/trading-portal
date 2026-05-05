import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchJournal, fetchJournalDay } from '../api'
import { formatINR } from '../utils/formatters'

const STRATEGY_COLORS = {
  orb:          'bg-violet-900/50 text-violet-300 border-violet-700/50',
  ema_crossover:'bg-indigo-900/50 text-indigo-300 border-indigo-700/50',
  relaxed_ema:  'bg-blue-900/50 text-blue-300 border-blue-700/50',
  vwap_cross:   'bg-cyan-900/50 text-cyan-300 border-cyan-700/50',
  rsi_bounce:   'bg-amber-900/50 text-amber-300 border-amber-700/50',
}

function StrategyBadge({ name }) {
  const cls = STRATEGY_COLORS[name] ?? 'bg-slate-800 text-slate-300 border-slate-600'
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-mono border ${cls}`}>
      {name}
    </span>
  )
}

function ExitBadge({ reason }) {
  const map = {
    TARGET:      ['Target',      'text-emerald-400'],
    STOP_LOSS:   ['Stop Loss',   'text-red-400'],
    FORCE_CLOSE: ['Force Close', 'text-amber-400'],
    RANGE_EXIT:  ['Range Exit',  'text-amber-400'],
    VWAP_EXIT:   ['VWAP Exit',   'text-amber-400'],
    RSI_EXIT:    ['RSI Exit',    'text-amber-400'],
    MANUAL:      ['Manual',      'text-slate-400'],
  }
  const [label, cls] = map[reason] ?? [reason, 'text-slate-400']
  return <span className={`text-xs font-medium ${cls}`}>{label}</span>
}

function DayDetail({ dateStr }) {
  const q = useQuery({
    queryKey: ['journal-day', dateStr],
    queryFn: () => fetchJournalDay(dateStr),
    enabled: !!dateStr,
  })

  if (q.isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading...</div>
  }

  if (!q.data) return null

  const { date, summary: s, watchlist, trades, strategies_used } = q.data
  const pnl = s?.final_pnl ?? 0

  const dateLabel = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-text-primary text-lg">{dateLabel}</h3>
        <span className={`text-2xl font-mono font-bold ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {pnl >= 0 ? '+' : ''}₹{Math.abs(pnl).toFixed(2)}
        </span>
      </div>

      {/* Summary stats */}
      {s && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Trades',    value: s.trades_count },
            { label: 'Wins',      value: s.wins,    color: 'text-emerald-400' },
            { label: 'Losses',    value: s.losses,  color: 'text-red-400' },
            { label: 'Win Rate',  value: `${((s.win_rate ?? 0) * 100).toFixed(0)}%` },
            { label: 'Capital',   value: formatINR(s.capital_end) },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-card-bg border border-card-border rounded-lg p-3 text-center">
              <div className={`text-lg font-bold font-mono ${color ?? 'text-text-primary'}`}>{value}</div>
              <div className="text-xs text-text-muted mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Screened stocks */}
      {watchlist?.length > 0 && (
        <div className="bg-card-bg border border-card-border rounded-lg p-4">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Stocks Screened ({watchlist.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {watchlist.map(w => (
              <div key={w.symbol} className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm">
                <span className="font-semibold text-text-primary">{w.symbol.replace('.NS', '')}</span>
                <span className="text-text-muted text-xs">#{w.rank}</span>
                <span className="text-xs text-text-muted">ADX {w.adx?.toFixed(1)}</span>
                <span className="text-xs text-text-muted">ATR {w.atr_pct?.toFixed(2)}%</span>
                <span className="text-xs text-text-muted">₹{w.price?.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Strategies used */}
      {strategies_used?.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-text-muted text-sm">Strategies fired:</span>
          {strategies_used.map(name => <StrategyBadge key={name} name={name} />)}
        </div>
      )}

      {/* Trades table */}
      <div className="bg-card-bg border border-card-border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-card-border">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
            Trades ({trades?.length ?? 0})
          </h4>
        </div>
        {!trades?.length ? (
          <p className="text-text-muted text-sm p-4">No trades on this day.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-card-border text-text-muted text-xs">
                <th className="text-left px-4 py-2">Symbol</th>
                <th className="text-left px-4 py-2">Strategy</th>
                <th className="text-right px-4 py-2">Entry</th>
                <th className="text-right px-4 py-2">Exit</th>
                <th className="text-left px-4 py-2">Reason</th>
                <th className="text-right px-4 py-2">Qty</th>
                <th className="text-right px-4 py-2">Costs</th>
                <th className="text-right px-4 py-2">P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={t.id ?? i} className="border-b border-card-border/40 hover:bg-slate-800/50 transition-colors">
                  <td className="px-4 py-2.5 font-semibold text-text-primary font-mono">
                    {t.symbol.replace('.NS', '')}
                  </td>
                  <td className="px-4 py-2.5">
                    <StrategyBadge name={t.strategy} />
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-secondary text-xs">
                    ₹{t.entry_price?.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-secondary text-xs">
                    ₹{t.exit_price?.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5">
                    <ExitBadge reason={t.exit_reason} />
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-muted text-xs">
                    {t.quantity}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-muted text-xs">
                    ₹{t.total_cost?.toFixed(2)}
                  </td>
                  <td className={`px-4 py-2.5 text-right font-mono font-bold ${t.final_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {t.final_pnl >= 0 ? '+' : ''}₹{t.final_pnl?.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
            {/* Footer: totals */}
            {trades.length > 1 && (() => {
              const totalPnl  = trades.reduce((s, t) => s + (t.final_pnl ?? 0), 0)
              const totalCost = trades.reduce((s, t) => s + (t.total_cost ?? 0), 0)
              return (
                <tfoot>
                  <tr className="border-t border-card-border bg-slate-800/40 text-xs font-semibold">
                    <td colSpan={6} className="px-4 py-2 text-text-muted">Total</td>
                    <td className="px-4 py-2 text-right font-mono text-text-muted">
                      ₹{totalCost.toFixed(2)}
                    </td>
                    <td className={`px-4 py-2 text-right font-mono font-bold ${totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {totalPnl >= 0 ? '+' : ''}₹{totalPnl.toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              )
            })()}
          </table>
        )}
      </div>
    </div>
  )
}

export default function Journal() {
  const [selectedDate, setSelectedDate] = useState(null)

  const journalQ = useQuery({
    queryKey: ['journal'],
    queryFn: () => fetchJournal(90),
    refetchInterval: 60_000,
  })

  const days = journalQ.data?.days ?? []

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 130px)' }}>
      {/* Left: day list */}
      <div className="w-64 flex-shrink-0 flex flex-col">
        <h2 className="font-bold text-text-primary text-lg mb-3">Trading Journal</h2>
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
          {journalQ.isLoading && (
            <p className="text-text-muted text-sm">Loading...</p>
          )}
          {!journalQ.isLoading && days.length === 0 && (
            <p className="text-text-muted text-sm">No trading days yet.</p>
          )}
          {days.map(d => {
            const pnl = d.final_pnl ?? 0
            const isSelected = selectedDate === d.date
            const dateLabel = new Date(d.date + 'T00:00:00').toLocaleDateString('en-IN', {
              weekday: 'short', day: 'numeric', month: 'short',
            })
            return (
              <button
                key={d.date}
                onClick={() => setSelectedDate(d.date)}
                className={`w-full text-left rounded-lg px-3 py-2.5 border transition-colors ${
                  isSelected
                    ? 'bg-slate-700 border-slate-500'
                    : 'bg-card-bg border-card-border hover:bg-slate-800'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-text-primary">{dateLabel}</span>
                  <span className={`text-xs font-mono font-bold ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pnl >= 0 ? '+' : ''}₹{Math.abs(pnl).toFixed(0)}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <span>{d.trades_count} trades</span>
                  <span>·</span>
                  <span className="text-emerald-400">{d.wins}W</span>
                  <span className="text-red-400">{d.losses}L</span>
                  {d.watchlist_count > 0 && (
                    <><span>·</span><span>{d.watchlist_count} stocks</span></>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Right: detail panel */}
      <div className="flex-1 overflow-y-auto">
        {!selectedDate ? (
          <div className="h-full flex flex-col items-center justify-center gap-2">
            <span className="text-4xl">📅</span>
            <p className="text-text-muted text-sm">Select a day to see details</p>
          </div>
        ) : (
          <DayDetail dateStr={selectedDate} />
        )}
      </div>
    </div>
  )
}
