import { useApp } from '../context/AppContext'
import CapitalCard from '../components/cards/CapitalCard'
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
    position,
    trades,
    tradesLoading,
    chartSymbol,
    setChartSymbol,
    setActiveTab,
  } = useApp()

  const mode    = status?.mode ?? 'paper'
  const capital = status?.capital ?? 0
  const today   = status?.today ?? {}

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

      {/* Stat cards row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <CapitalCard capital={capital} mode={mode} />
        <PnLCard pnl={today.final_pnl ?? 0} trades={today.trades ?? 0} />
        <WinRateCard wins={today.wins ?? 0} losses={today.losses ?? 0} />
        <TradesCard trades={trades} />
      </div>

      {/* Chart + Sidebar */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        {/* Chart — clicking will also be available on Chart tab */}
        <LiveChart symbol={chartSymbol} position={position} mode={mode} />

        {/* Right sidebar */}
        <div className="flex flex-col gap-4">
          <Watchlist onSelectSymbol={handleSelectSymbol} />
          <PositionCard position={position} />
        </div>
      </div>

      {/* Trade log */}
      <TradeLog trades={trades} isLoading={tradesLoading} mode={mode} />
    </div>
  )
}
