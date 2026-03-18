import { useQuery } from '@tanstack/react-query'
import { fetchKiteProfile, fetchKiteFunds, fetchKiteHoldings, fetchKiteMFHoldings } from '../api'
import { useApp } from '../context/AppContext'
import { formatINR } from '../utils/formatters'

function Section({ title, children }) {
  return (
    <div className="card">
      <h3 className="font-semibold text-text-primary mb-4">{title}</h3>
      {children}
    </div>
  )
}

function Row({ label, value, valueClass = 'text-text-primary' }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-card-border last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <span className={`font-mono text-sm font-semibold ${valueClass}`}>{value ?? '—'}</span>
    </div>
  )
}

function NotConnected() {
  const { setActiveTab } = useApp()
  return (
    <div className="card text-center py-10">
      <p className="text-text-muted mb-3">Kite Connect is not authenticated.</p>
      <button
        onClick={() => setActiveTab('settings')}
        className="btn-primary"
      >
        Go to Settings → Login
      </button>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="space-y-2">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-9 bg-slate-700 rounded animate-pulse" />
      ))}
    </div>
  )
}

export default function Kite() {
  const { status } = useApp()
  const kiteOk = status?.kite_configured ?? false

  const profileQ  = useQuery({ queryKey: ['kite-profile'],     queryFn: fetchKiteProfile,    enabled: kiteOk, retry: false })
  const fundsQ    = useQuery({ queryKey: ['kite-funds'],       queryFn: fetchKiteFunds,      enabled: kiteOk, retry: false, refetchInterval: 30000 })
  const holdingsQ = useQuery({ queryKey: ['kite-holdings'],    queryFn: fetchKiteHoldings,   enabled: kiteOk, retry: false, refetchInterval: 60000 })
  const mfQ       = useQuery({ queryKey: ['kite-mf-holdings'], queryFn: fetchKiteMFHoldings, enabled: kiteOk, retry: false, refetchInterval: 60000 })

  if (!kiteOk) return <NotConnected />

  const profile    = profileQ.data
  const equity     = fundsQ.data?.equity
  const holdings   = holdingsQ.data?.holdings ?? []
  const mfHoldings = mfQ.data?.mf_holdings ?? []

  const totalInvested = holdings.reduce((s, h) => s + (h.average_price * h.quantity), 0)
  const totalCurrent  = holdings.reduce((s, h) => s + (h.last_price * h.quantity), 0)
  const totalPnL      = totalCurrent - totalInvested

  return (
    <div className="max-w-4xl space-y-5">

      {/* Profile */}
      <Section title="Account">
        {profileQ.isLoading ? <Skeleton /> : profile ? (
          <>
            <Row label="Name"       value={profile.user_name} />
            <Row label="Client ID"  value={profile.user_id} />
            <Row label="Email"      value={profile.email} />
            <Row label="Broker"     value={profile.broker} />
            <Row label="Exchanges"  value={profile.exchanges?.join(', ')} />
            <Row label="Products"   value={profile.products?.join(', ')} />
          </>
        ) : (
          <p className="text-text-muted text-sm">Failed to load profile.</p>
        )}
      </Section>

      {/* Funds */}
      <Section title="Funds & Margins">
        {fundsQ.isLoading ? <Skeleton /> : equity ? (
          <>
            <Row label="Available Cash"      value={formatINR(equity.available?.live_balance ?? equity.available?.cash)} />
            <Row label="Opening Balance"     value={formatINR(equity.available?.opening_balance)} />
            <Row label="Used Margin"         value={formatINR(equity.utilised?.debits)} />
            <Row label="Span Margin"         value={formatINR(equity.utilised?.span)} />
            <Row label="Exposure Margin"     value={formatINR(equity.utilised?.exposure)} />
          </>
        ) : (
          <p className="text-text-muted text-sm">
            {fundsQ.error ? 'Failed to load funds — market may be closed.' : 'No data.'}
          </p>
        )}
      </Section>

      {/* Holdings */}
      <Section title={`Portfolio Holdings (${holdings.length} stocks)`}>
        {holdingsQ.isLoading ? <Skeleton /> : holdings.length > 0 ? (
          <>
            {/* Summary row */}
            <div className="grid grid-cols-3 gap-4 mb-4 p-3 bg-slate-800 rounded-xl">
              <div>
                <p className="text-text-muted text-xs mb-1">Invested</p>
                <p className="font-mono font-semibold text-text-primary">{formatINR(totalInvested)}</p>
              </div>
              <div>
                <p className="text-text-muted text-xs mb-1">Current</p>
                <p className="font-mono font-semibold text-text-primary">{formatINR(totalCurrent)}</p>
              </div>
              <div>
                <p className="text-text-muted text-xs mb-1">Total P&L</p>
                <p className={`font-mono font-semibold ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {totalPnL >= 0 ? '+' : ''}{formatINR(totalPnL)}
                </p>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text-muted text-xs border-b border-card-border">
                    <th className="text-left py-2 font-medium">Symbol</th>
                    <th className="text-right py-2 font-medium">Qty</th>
                    <th className="text-right py-2 font-medium">Avg Price</th>
                    <th className="text-right py-2 font-medium">LTP</th>
                    <th className="text-right py-2 font-medium">P&L</th>
                    <th className="text-right py-2 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map(h => {
                    const pnl     = (h.last_price - h.average_price) * h.quantity
                    const pnlPct  = ((h.last_price - h.average_price) / h.average_price) * 100
                    const pos     = pnl >= 0
                    return (
                      <tr key={h.tradingsymbol} className="border-b border-card-border last:border-0 hover:bg-slate-800/50">
                        <td className="py-3 font-semibold text-text-primary">{h.tradingsymbol}</td>
                        <td className="py-3 text-right text-text-secondary">{h.quantity}</td>
                        <td className="py-3 text-right font-mono text-text-secondary">{formatINR(h.average_price)}</td>
                        <td className="py-3 text-right font-mono text-text-primary">{formatINR(h.last_price)}</td>
                        <td className={`py-3 text-right font-mono font-semibold ${pos ? 'text-emerald-400' : 'text-red-400'}`}>
                          {pos ? '+' : ''}{formatINR(pnl)}
                        </td>
                        <td className={`py-3 text-right font-mono ${pos ? 'text-emerald-400' : 'text-red-400'}`}>
                          {pos ? '+' : ''}{pnlPct.toFixed(2)}%
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="text-text-muted text-sm">
            {holdingsQ.error ? 'Failed to load holdings.' : 'No holdings in your demat account.'}
          </p>
        )}
      </Section>

      {/* Mutual Funds */}
      <Section title={`Mutual Funds (${mfHoldings.length} funds)`}>
        {mfQ.isLoading ? <Skeleton /> : mfHoldings.length > 0 ? (() => {
          const mfInvested = mfHoldings.reduce((s, h) => s + h.average_price * h.quantity, 0)
          const mfCurrent  = mfHoldings.reduce((s, h) => s + h.last_price  * h.quantity, 0)
          const mfPnL      = mfCurrent - mfInvested

          return (
            <>
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4 mb-4 p-3 bg-slate-800 rounded-xl">
                <div>
                  <p className="text-text-muted text-xs mb-1">Invested</p>
                  <p className="font-mono font-semibold text-text-primary">{formatINR(mfInvested)}</p>
                </div>
                <div>
                  <p className="text-text-muted text-xs mb-1">Current</p>
                  <p className="font-mono font-semibold text-text-primary">{formatINR(mfCurrent)}</p>
                </div>
                <div>
                  <p className="text-text-muted text-xs mb-1">Total P&L</p>
                  <p className={`font-mono font-semibold ${mfPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {mfPnL >= 0 ? '+' : ''}{formatINR(mfPnL)}
                  </p>
                </div>
              </div>

              {/* List */}
              <div>
                {mfHoldings.map(h => {
                  const current = h.last_price * h.quantity
                  const pnl     = current - h.average_price * h.quantity
                  const pnlPct  = ((h.last_price - h.average_price) / h.average_price) * 100
                  const pos     = pnl >= 0
                  return (
                    <div key={h.tradingsymbol} className="py-3 border-b border-card-border last:border-0">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="font-medium text-text-primary text-sm leading-snug">{h.fund}</p>
                          <p className="text-text-muted text-xs mt-0.5">
                            {h.quantity.toFixed(3)} units · Avg NAV {formatINR(h.average_price)} · Folio {h.folio}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="font-mono text-sm font-semibold text-text-primary">{formatINR(current)}</p>
                          <p className={`font-mono text-xs ${pos ? 'text-emerald-400' : 'text-red-400'}`}>
                            {pos ? '+' : ''}{formatINR(pnl)} ({pos ? '+' : ''}{pnlPct.toFixed(2)}%)
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )
        })() : (
          <p className="text-text-muted text-sm">
            {mfQ.error ? 'Failed to load mutual funds.' : 'No mutual fund holdings found.'}
          </p>
        )}
      </Section>

    </div>
  )
}
