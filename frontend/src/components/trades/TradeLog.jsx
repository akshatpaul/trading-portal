import { useState } from 'react'
import { formatINR, formatTime, formatSymbol, formatPnL } from '../../utils/formatters'
import { TRADE_REASON_BADGES } from '../../utils/constants'

function ReasonBadge({ reason }) {
  const badge = TRADE_REASON_BADGES[reason?.toLowerCase()]
  if (!badge) return <span className="text-text-muted text-xs">{reason || '—'}</span>
  return (
    <span className={`text-xs flex items-center gap-0.5 ${badge.color}`} title={badge.label}>
      {badge.emoji} <span className="hidden sm:inline">{badge.label}</span>
    </span>
  )
}

function SideBadge({ side }) {
  const isBuy = side?.toUpperCase() === 'BUY'
  return (
    <span className={isBuy ? 'badge-buy' : 'badge-sell'}>
      {side?.toUpperCase() || '—'}
    </span>
  )
}

function CostBreakdown({ trade }) {
  const rows = [
    { label: 'Gross P&L',    value: trade.gross_pnl,    highlight: false },
    { label: 'Brokerage',    value: -trade.brokerage,   highlight: false },
    { label: 'STT',          value: -trade.stt,         highlight: false },
    { label: 'Exchange fee', value: -trade.exchange_fee, highlight: false },
    { label: 'SEBI charge',  value: -trade.sebi_charge,  highlight: false },
    { label: 'GST',          value: -trade.gst,          highlight: false },
    { label: 'Stamp duty',   value: -trade.stamp_duty,   highlight: false },
    { label: 'Total charges',value: -trade.total_cost,  highlight: true  },
    { label: 'Net P&L',      value: trade.net_pnl,      highlight: true  },
    { label: 'Tax est. (30%)',value: -trade.tax_estimate, highlight: false },
    { label: 'Final P&L',    value: trade.final_pnl,    highlight: true  },
  ]

  return (
    <tr>
      <td colSpan={9} className="px-4 pb-3 pt-0">
        <div className="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-1.5 text-xs">
            {/* Turnover info */}
            <div className="col-span-full flex gap-6 mb-1 pb-1.5 border-b border-slate-700/50">
              <span className="text-text-muted">
                Buy turnover: <span className="font-mono text-text-primary">{formatINR(trade.entry_price * trade.quantity)}</span>
              </span>
              <span className="text-text-muted">
                Sell turnover: <span className="font-mono text-text-primary">{formatINR(trade.exit_price * trade.quantity)}</span>
              </span>
            </div>
            {rows.map(({ label, value, highlight }) => {
              const fmt = formatPnL(value)
              return (
                <div key={label} className={highlight ? 'pt-1 border-t border-slate-700/50' : ''}>
                  <p className="text-text-muted">{label}</p>
                  <p className={`font-mono font-semibold ${fmt.colorClass}`}>{fmt.text}</p>
                </div>
              )
            })}
          </div>
        </div>
      </td>
    </tr>
  )
}

const PAGE_SIZE = 20

export default function TradeLog({ trades = [], isLoading, mode }) {
  const [page, setPage] = useState(0)
  const [expanded, setExpanded] = useState(null)
  const totalPages = Math.ceil(trades.length / PAGE_SIZE)
  const paginated  = trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  function toggleExpand(id) {
    setExpanded(prev => prev === id ? null : id)
  }

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-text-primary mb-3">Trade Log</h3>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-slate-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-text-primary">
          Trade Log
          {trades.length > 0 && (
            <span className="ml-2 text-text-muted text-xs font-normal">({trades.length} total)</span>
          )}
        </h3>
        {mode === 'paper' && (
          <span className="badge-paper">PAPER</span>
        )}
      </div>

      {trades.length === 0 ? (
        <div className="flex flex-col items-center py-10 text-center">
          <span className="text-3xl opacity-30 mb-2">📭</span>
          <p className="text-text-muted text-sm">No trades yet</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto -mx-4 px-4">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-card-border">
                  <th className="table-th w-8">#</th>
                  <th className="table-th">Time</th>
                  <th className="table-th">Symbol</th>
                  <th className="table-th">Side</th>
                  <th className="table-th text-right">Qty</th>
                  <th className="table-th text-right">Entry</th>
                  <th className="table-th text-right">Exit</th>
                  <th className="table-th text-right">P&L</th>
                  <th className="table-th">Reason</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((trade, i) => {
                  const pnl = formatPnL(trade.net_pnl ?? trade.pnl)
                  const rowIndex = page * PAGE_SIZE + i + 1
                  const borderColor = !trade.exit_time
                    ? 'border-l-2 border-l-signal'
                    : (trade.net_pnl ?? trade.pnl ?? 0) >= 0
                      ? 'border-l-2 border-l-emerald-500'
                      : 'border-l-2 border-l-red-500'
                  const rowId = trade.id ?? i
                  const isOpen = expanded === rowId
                  const hasCosts = trade.total_cost != null

                  return (
                    <>
                      <tr
                        key={rowId}
                        className={`table-row ${borderColor} ${hasCosts ? 'cursor-pointer hover:bg-slate-700/30' : ''}`}
                        onClick={() => hasCosts && toggleExpand(rowId)}
                        title={hasCosts ? 'Click to see cost breakdown' : undefined}
                      >
                        <td className="table-td text-text-muted font-mono text-xs">{rowIndex}</td>
                        <td className="table-td text-text-muted font-mono text-xs whitespace-nowrap">
                          {formatTime(trade.entry_time, 'datetime')}
                        </td>
                        <td className="table-td">
                          <span className="font-mono font-semibold">{formatSymbol(trade.symbol)}</span>
                        </td>
                        <td className="table-td"><SideBadge side={trade.side} /></td>
                        <td className="table-td text-right font-mono">{trade.quantity ?? '—'}</td>
                        <td className="table-td text-right font-mono">{formatINR(trade.entry_price)}</td>
                        <td className="table-td text-right font-mono">
                          {trade.exit_price ? formatINR(trade.exit_price) : (
                            <span className="text-signal text-xs">OPEN</span>
                          )}
                        </td>
                        <td className={`table-td text-right font-mono font-semibold ${pnl.colorClass}`}>
                          <div className="flex items-center justify-end gap-1">
                            {pnl.text}
                            {hasCosts && (
                              <span className="text-text-muted text-xs">{isOpen ? '▲' : '▼'}</span>
                            )}
                          </div>
                        </td>
                        <td className="table-td">
                          <ReasonBadge reason={trade.exit_reason} />
                        </td>
                      </tr>
                      {isOpen && hasCosts && <CostBreakdown key={`cost-${rowId}`} trade={trade} />}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-card-border">
              <span className="text-text-muted text-xs">
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn-ghost text-xs py-1 px-2 disabled:opacity-40"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page === totalPages - 1}
                  className="btn-ghost text-xs py-1 px-2 disabled:opacity-40"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
