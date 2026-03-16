import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTrades } from '../api'
import TradeLog from '../components/trades/TradeLog'
import { useApp } from '../context/AppContext'

export default function Trades() {
  const { status } = useApp()
  const [limit, setLimit] = useState(100)
  const mode = status?.mode ?? 'paper'

  const tradesQ = useQuery({
    queryKey: ['trades', limit],
    queryFn: () => fetchTrades(limit),
    refetchInterval: 15000,
  })

  const trades = tradesQ.data?.trades || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-text-primary text-lg">Trade History</h2>
        <div className="flex items-center gap-2">
          <span className="text-text-muted text-sm">Show:</span>
          {[50, 100, 200].map(n => (
            <button
              key={n}
              onClick={() => setLimit(n)}
              className={limit === n ? 'tab-btn-active text-xs' : 'tab-btn text-xs'}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <TradeLog trades={trades} isLoading={tradesQ.isLoading} mode={mode} />
    </div>
  )
}
