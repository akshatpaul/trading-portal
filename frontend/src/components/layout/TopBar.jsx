import { useState, useEffect } from 'react'
import { useApp } from '../../context/AppContext'
import { emergencyStop, fetchMarketTicker } from '../../api'
import { formatINR, formatPnL } from '../../utils/formatters'

function ISTClock() {
  const [time, setTime] = useState('')
  useEffect(() => {
    const tick = () => {
      setTime(new Date().toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return <span className="font-mono text-sm text-text-secondary">{time} IST</span>
}

// Mini sparkline for daily P&L
function PnLSparkline({ trades }) {
  if (!trades || trades.length < 2) return null

  // Build daily cumulative P&L points
  const sorted = [...trades]
    .sort((a, b) => new Date(a.entry_time) - new Date(b.entry_time))
    .slice(-20)

  let cum = 0
  const points = sorted.map(t => {
    cum += (t.net_pnl ?? t.pnl ?? 0)
    return cum
  })

  const min = Math.min(...points, 0)
  const max = Math.max(...points, 0)
  const range = max - min || 1
  const W = 80, H = 24

  const coords = points.map((v, i) => {
    const x = (i / (points.length - 1)) * W
    const y = H - ((v - min) / range) * H
    return `${x},${y}`
  })

  const lastVal = points[points.length - 1]
  const color = lastVal >= 0 ? '#10b981' : '#ef4444'

  return (
    <svg width={W} height={H} className="inline-block ml-2">
      <polyline
        className="sparkline-path"
        points={coords.join(' ')}
        stroke={color}
        fill="none"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function TickerItem({ label, data, formatPrice }) {
  if (!data) return null
  const up    = data.change >= 0
  const color = up ? 'text-emerald-400' : 'text-red-400'
  const arrow = up ? '▲' : '▼'
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-text-muted text-xs">{label}</span>
      <span className={`font-mono text-xs font-semibold ${color}`}>
        {formatPrice(data.price)}
      </span>
      <span className={`font-mono text-xs ${color}`}>
        {arrow}{Math.abs(data.pct).toFixed(2)}%
      </span>
    </div>
  )
}

export default function TopBar({ onLogout }) {
  const {
    status, wsConnected,
    trades,
    setShowEmergencyModal, setShowLiveModeModal,
    activeTab, setActiveTab,
    toast,
  } = useApp()

  const [ticker, setTicker] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await fetchMarketTicker()
        if (!cancelled) setTicker(data)
      } catch {}
    }
    load()
    const id = setInterval(load, 60_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const mode        = status?.mode ?? 'paper'
  const capital     = status?.capital ?? 0
  const marketOpen  = status?.market_open ?? false
  const tradingDay  = status?.trading_day ?? false
  const tradingAllowed = status?.trading_allowed ?? false
  const blockReason = status?.block_reason ?? ''
  const today       = status?.today ?? {}
  const finalPnL    = today.final_pnl ?? 0
  const pnl         = formatPnL(finalPnL)

  const isLive = mode === 'live'

  const tabs = [
    { id: 'dashboard',   label: 'Dashboard' },
    { id: 'chart',       label: 'Chart' },
    { id: 'trades',      label: 'Trades' },
    { id: 'performance', label: 'Performance' },
    { id: 'activity',    label: 'Activity' },
    { id: 'strategies',  label: 'Strategies' },
    { id: 'kite',        label: 'Kite' },
    { id: 'settings',    label: 'Settings' },
  ]

  async function handleEmergency() {
    setShowEmergencyModal(true)
  }

  return (
    <header className="bg-slate-900 border-b border-card-border px-4 sticky top-0 z-40">
      {/* Top row */}
      <div className="flex items-center justify-between h-14 gap-4">
        {/* Left: logo + name */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-xl">📈</span>
          <span className="font-bold text-text-primary text-lg tracking-tight">
            Trading Portal
          </span>
          {/* Mode badge */}
          {isLive ? (
            <span className="badge-live">LIVE</span>
          ) : (
            <span className="badge-paper">PAPER</span>
          )}
        </div>

        {/* Center: status bar */}
        <div className="hidden md:flex items-center gap-5 text-sm">
          {/* Capital */}
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted text-xs">Capital</span>
            <span className="font-mono text-text-primary font-semibold">{formatINR(capital)}</span>
          </div>

          {/* Daily P&L with sparkline */}
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted text-xs">Day P&L</span>
            <span className={`font-mono font-semibold ${pnl.colorClass}`}>{pnl.text}</span>
            <PnLSparkline trades={trades} />
          </div>

          {/* Market status */}
          <div className="flex items-center gap-1.5">
            {marketOpen ? (
              <>
                <span className="dot-live" />
                <span className="text-emerald-400 font-medium">OPEN</span>
              </>
            ) : (
              <>
                <span className="dot-closed" />
                <span className="text-text-muted">CLOSED</span>
              </>
            )}
          </div>

          {/* Trading allowed */}
          <div className="flex items-center gap-1.5" title={blockReason || undefined}>
            {tradingAllowed ? (
              <span className="text-emerald-400 text-xs">✓ Trading OK</span>
            ) : (
              <span className="text-red-400 text-xs" title={blockReason}>
                ✗ Blocked{blockReason ? `: ${blockReason}` : ''}
              </span>
            )}
          </div>

          {/* Clock */}
          <ISTClock />
        </div>

        {/* Right: WS indicator + emergency */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* WS indicator */}
          <div className="flex items-center gap-1.5" title={wsConnected ? 'WebSocket connected' : 'WebSocket disconnected'}>
            {wsConnected ? (
              <><span className="dot-ws" /><span className="text-xs text-text-muted hidden lg:inline">Live</span></>
            ) : (
              <><span className="dot-ws-off" /><span className="text-xs text-red-400 hidden lg:inline">Offline</span></>
            )}
          </div>

          <button
            onClick={handleEmergency}
            className="bg-red-600 hover:bg-red-500 text-white font-bold text-xs px-3 py-1.5
                       rounded-lg border border-red-500 transition-colors flex items-center gap-1
                       animate-pulse hover:animate-none"
          >
            🚨 STOP
          </button>

          {onLogout && (
            <button
              onClick={onLogout}
              title="Sign out"
              className="text-slate-400 hover:text-white text-xs px-2.5 py-1.5
                         rounded-lg border border-slate-700 hover:border-slate-500
                         transition-colors hidden sm:flex items-center gap-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Logout
            </button>
          )}
        </div>
      </div>

      {/* Market ticker strip */}
      {ticker && (
        <div className="hidden md:flex items-center gap-5 py-1.5 border-t border-slate-800/60 text-xs">
          <TickerItem
            label="SENSEX"
            data={ticker.sensex}
            formatPrice={p => p?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          />
          {ticker.sensex && ticker.gold_24k_per_10g && (
            <span className="text-slate-700">|</span>
          )}
          <TickerItem
            label="Gold 24k/10g"
            data={ticker.gold_24k_per_10g}
            formatPrice={p => `₹${p?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
          />
          {ticker.gold_24k_per_10g && ticker.goldietf && (
            <span className="text-slate-700">|</span>
          )}
          <TickerItem
            label="GOLDIETF"
            data={ticker.goldietf}
            formatPrice={p => `₹${p?.toFixed(2)}`}
          />
        </div>
      )}

      {/* Tab navigation */}
      <nav className="flex items-center gap-1 -mb-px overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'tab-btn-active' : 'tab-btn'}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </header>
  )
}
