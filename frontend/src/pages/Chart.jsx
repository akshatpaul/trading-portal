import { useApp } from '../context/AppContext'
import LiveChart from '../components/chart/LiveChart'
import Watchlist from '../components/watchlist/Watchlist'
import PositionCard from '../components/position/PositionCard'

export default function Chart() {
  const { status, position, chartSymbol, setChartSymbol } = useApp()
  const mode = status?.mode ?? 'paper'

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-5">
      <LiveChart symbol={chartSymbol} position={position} mode={mode} />
      <div className="flex flex-col gap-4">
        <Watchlist onSelectSymbol={setChartSymbol} />
        <PositionCard position={position} />
      </div>
    </div>
  )
}
