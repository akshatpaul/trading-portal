import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRiskLimits, fetchKiteLoginUrl, setModePaper, runScreener } from '../api'
import { useApp } from '../context/AppContext'
import { formatINR } from '../utils/formatters'
import { useState } from 'react'

function LimitRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-card-border last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <span className="font-mono text-sm text-text-primary font-semibold">{value}</span>
    </div>
  )
}

export default function Settings() {
  const {
    status, refetchStatus, toast,
    setShowLiveModeModal,
  } = useApp()

  const queryClient = useQueryClient()
  const [screenerLoading, setScreenerLoading] = useState(false)

  const riskQ = useQuery({
    queryKey: ['risk-limits'],
    queryFn: fetchRiskLimits,
  })

  const mode    = status?.mode ?? 'paper'
  const isLive  = mode === 'live'
  const kiteOk  = status?.kite_configured ?? false
  const tgOk    = status?.telegram_configured ?? false

  const risk = riskQ.data

  async function handleSwitchPaper() {
    try {
      await setModePaper()
      toast.success('✅ Switched to paper trading mode')
      refetchStatus()
    } catch (err) {
      toast.error(`Failed to switch: ${err?.response?.data?.detail || err.message}`)
    }
  }

  async function handleRunScreener() {
    setScreenerLoading(true)
    try {
      const result = await runScreener()
      const symbols = result.symbols?.join(', ') || 'none'
      toast.success(`Screener complete — watchlist: ${symbols}`)
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    } catch (err) {
      toast.error(`Screener failed: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setScreenerLoading(false)
    }
  }

  async function handleKiteLogin() {
    try {
      const { url } = await fetchKiteLoginUrl()
      window.open(url, '_blank')
    } catch (err) {
      toast.error(`Failed to get Kite login URL: ${err.message}`)
    }
  }

  return (
    <div className="max-w-2xl space-y-5">

      {/* Trading Mode */}
      <div className="card">
        <h3 className="font-semibold text-text-primary mb-4">Trading Mode</h3>

        <div className="flex items-center justify-between p-4 bg-slate-800 rounded-xl mb-4">
          <div>
            <p className="font-medium text-text-primary">Current mode</p>
            <p className="text-text-muted text-sm">
              {isLive
                ? 'Real money trading. All trades affect your actual account.'
                : 'Paper trading with simulated capital. Safe to experiment.'}
            </p>
          </div>
          {isLive ? (
            <span className="badge-live text-sm px-3 py-1">LIVE</span>
          ) : (
            <span className="badge-paper text-sm px-3 py-1">PAPER</span>
          )}
        </div>

        <div className="flex gap-3">
          {isLive ? (
            <button
              onClick={handleSwitchPaper}
              className="btn-ghost border border-card-border"
            >
              Switch to Paper
            </button>
          ) : (
            <button
              onClick={() => setShowLiveModeModal(true)}
              className="bg-orange-600 hover:bg-orange-500 text-white font-semibold text-sm
                         px-4 py-2 rounded-lg transition-colors"
            >
              Switch to Live Trading →
            </button>
          )}
        </div>

        {!isLive && (
          <p className="text-text-muted text-xs mt-3">
            ⚠️ Live trading uses real money. Ensure Kite is configured and you understand the risks.
          </p>
        )}
      </div>

      {/* Kite Connect */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-text-primary">Kite Connect</h3>
          <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
            kiteOk
              ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700/50'
              : 'bg-red-900/50 text-red-400 border-red-700/50'
          }`}>
            {kiteOk ? '✓ Configured' : '✗ Not configured'}
          </span>
        </div>

        {kiteOk ? (
          <p className="text-text-secondary text-sm">
            Kite Connect is configured. Token is active.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-text-secondary text-sm">
              Kite Connect is not configured. Configure API keys in your backend <code className="text-signal">.env</code> file
              and then log in.
            </p>
            <button
              onClick={handleKiteLogin}
              className="btn-primary"
            >
              Open Kite Login →
            </button>
          </div>
        )}
      </div>

      {/* Telegram */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-text-primary">Telegram Alerts</h3>
          <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
            tgOk
              ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700/50'
              : 'bg-slate-700 text-text-muted border-card-border'
          }`}>
            {tgOk ? '✓ Active' : '— Not configured'}
          </span>
        </div>
        <p className="text-text-secondary text-sm">
          {tgOk
            ? 'Telegram bot is configured. You will receive trade alerts.'
            : 'Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your backend .env file to enable alerts.'}
        </p>
      </div>

      {/* Bot Controls */}
      <div className="card">
        <h3 className="font-semibold text-text-primary mb-4">Bot Controls</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text-primary font-medium">Run Screener Now</p>
            <p className="text-xs text-text-muted mt-0.5">
              Manually populate today's watchlist (runs automatically at 8:45 AM IST)
            </p>
          </div>
          <button
            onClick={handleRunScreener}
            disabled={screenerLoading}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          >
            {screenerLoading ? 'Running...' : 'Run Screener'}
          </button>
        </div>
      </div>

      {/* Risk Limits */}
      <div className="card">
        <h3 className="font-semibold text-text-primary mb-4">Risk Limits</h3>
        <p className="text-text-muted text-xs mb-3">
          These limits are enforced server-side and cannot be changed from the UI.
          Edit your backend configuration to modify them.
        </p>

        {riskQ.isLoading ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-8 bg-slate-700 rounded animate-pulse" />
            ))}
          </div>
        ) : risk ? (
          <>
            <LimitRow label="Max Daily Loss"      value={formatINR(risk.max_daily_loss)} />
            <LimitRow label="Max Position Size"   value={formatINR(risk.max_position_size)} />
            <LimitRow label="Max Trades / Day"    value={risk.max_trades_per_day} />
            <LimitRow label="Max Leverage"        value={`${risk.max_leverage}x`} />
            <LimitRow label="Min Capital"         value={formatINR(risk.min_capital)} />
            <LimitRow label="Force Close Time"    value={risk.force_close_time ?? '—'} />
          </>
        ) : (
          <p className="text-text-muted text-sm">Failed to load risk limits.</p>
        )}
      </div>

    </div>
  )
}
