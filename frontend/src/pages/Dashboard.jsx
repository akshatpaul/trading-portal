import { useApp } from '../context/AppContext'
import { fetchKiteLoginUrl } from '../api'
import CapitalCard from '../components/cards/CapitalCard'
import CapitalStatsCard from '../components/cards/CapitalStatsCard'
import PnLCard from '../components/cards/PnLCard'
import WinRateCard from '../components/cards/WinRateCard'
import TradesCard from '../components/cards/TradesCard'
import PositionCard from '../components/position/PositionCard'
import Watchlist from '../components/watchlist/Watchlist'
import TradeLog from '../components/trades/TradeLog'
import LiveChart from '../components/chart/LiveChart'

export default function Dashboard() {
  const {
    status,
    positions,
    trades,
    tradesLoading,
    chartSymbol,
    setChartSymbol,
    setActiveTab,
    toast,
  } = useApp()

  const mode       = status?.mode ?? 'paper'
  const capital    = status?.capital ?? 0
  const today      = status?.today ?? {}
  const kiteKeySet = status?.kite_api_key_set ?? false
  const kiteOk     = status?.kite_configured ?? false

  async function handleKiteLogin() {
    try {
      const { url } = await fetchKiteLoginUrl()
      window.open(url, '_blank')
    } catch (err) {
      toast.error(`Failed to get Kite login URL: ${err.message}`)
    }
  }

  function handleSelectSymbol(sym) {
    setChartSymbol(sym)
    setActiveTab('chart')
  }

  return (
    <div className="space-y-5">
      {/* Paper trading banner */}
      {mode === 'paper' && (
        <div className="bg-amber-950/60 border border-amber-800/60 rounded-xl px-4 py-2.5
                        text-amber-400 text-sm font-medium flex items-center gap-2">
          <span>📝</span>
          <span>Paper Trading Mode — Simulated capital, no real orders</span>
        </div>
      )}

      {/* Strategy chip */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-text-muted">Strategy:</span>
        <span className="px-2.5 py-0.5 rounded-full bg-slate-700 text-text-primary font-medium text-xs">
          All Strategies (Parallel)
        </span>
      </div>

      {/* Kite token expired banner */}
      {kiteKeySet && !kiteOk && (
        <div className="bg-red-950/60 border border-red-800/60 rounded-xl px-4 py-2.5
                        text-red-300 text-sm font-medium flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span>🔑</span>
            <span>Kite token expired — re-login to enable live trading</span>
          </div>
          <button
            onClick={handleKiteLogin}
            className="text-xs bg-red-700 hover:bg-red-600 text-white px-3 py-1 rounded-lg transition-colors whitespace-nowrap"
          >
            Login to Kite →
          </button>
        </div>
      )}

      {/* Stat cards row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <CapitalCard capital={capital} mode={mode} />
        <PnLCard pnl={today.final_pnl ?? 0} trades={today.trades ?? 0} />
        <WinRateCard wins={today.wins ?? 0} losses={today.losses ?? 0} />
        <TradesCard trades={trades} />
      </div>

      {/* Capital portfolio stats */}
      <CapitalStatsCard />

      {/* Chart + Sidebar */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        {/* Chart — clicking will also be available on Chart tab */}
        <LiveChart symbol={chartSymbol} position={positions[0] ?? null} mode={mode} />

        {/* Right sidebar */}
        <div className="flex flex-col gap-4">
          <Watchlist onSelectSymbol={handleSelectSymbol} />
          <PositionCard positions={positions} />
        </div>
      </div>

      {/* Trade log */}
      <TradeLog trades={trades} isLoading={tradesLoading} mode={mode} />
    </div>
  )
}
