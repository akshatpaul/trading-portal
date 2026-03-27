import { createContext, useContext, useState, useCallback, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../hooks/useToast'
import {
  fetchStatus, fetchWatchlist, fetchPositions, fetchTrades,
} from '../api'
import { formatSymbol } from '../utils/formatters'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const qc = useQueryClient()
  const { toasts, removeToast, toast } = useToast()
  const [activeTab, setActiveTab] = useState('dashboard')
  const [chartSymbol, setChartSymbol] = useState(null)
  const [showEmergencyModal, setShowEmergencyModal] = useState(false)
  const [showLiveModeModal, setShowLiveModeModal] = useState(false)

  const isAuthed = !!localStorage.getItem('trading_token')

  // Queries — disabled until logged in to avoid 401 reload loops
  const statusQ = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
    refetchInterval: 15000,
    retry: 2,
    enabled: isAuthed,
  })

  const watchlistQ = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    refetchInterval: 60000,
    retry: 2,
    enabled: isAuthed,
  })

  const positionsQ = useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 5000,
    retry: 2,
    enabled: isAuthed,
  })

  const tradesQ = useQuery({
    queryKey: ['trades'],
    queryFn: () => fetchTrades(50),
    refetchInterval: 30000,
    retry: 2,
    enabled: isAuthed,
  })

  // WebSocket message handler
  const handleWsMessage = useCallback((msg) => {
    const { event, data } = msg
    switch (event) {
      case 'watchlist_update':
        qc.invalidateQueries({ queryKey: ['watchlist'] })
        break
      case 'position_update':
        qc.invalidateQueries({ queryKey: ['positions'] })
        break
      case 'trade_complete':
        qc.invalidateQueries({ queryKey: ['trades'] })
        qc.invalidateQueries({ queryKey: ['status'] })
        if (data) {
          const pnl = data.net_pnl ?? data.pnl ?? 0
          const sym = formatSymbol(data.symbol || '')
          const reason = data.exit_reason || ''
          const emoji = reason === 'target' ? '🎯' : reason === 'stop_loss' ? '🛑' : reason === 'force_close' ? '⏰' : '✋'
          const type = pnl >= 0 ? 'success' : 'error'
          toast[type](`${emoji} ${sym} trade closed  ₹${pnl >= 0 ? '+' : ''}${Number(pnl).toFixed(2)}`)
        }
        break
      case 'signal':
        if (data) {
          const sym = formatSymbol(data.symbol || '')
          toast.info(`📡 Signal: ${data.side || ''} ${sym} @ ₹${data.price || ''}`)
        }
        break
      case 'daily_summary':
        if (data) {
          const pnl = data.final_pnl ?? 0
          const wr  = data.win_rate ?? 0
          toast.info(`📊 Day summary: P&L ₹${Number(pnl).toFixed(2)} | WR ${(wr * 100).toFixed(0)}%`, 8000)
        }
        qc.invalidateQueries({ queryKey: ['status'] })
        qc.invalidateQueries({ queryKey: ['trades'] })
        break
      default:
        break
    }
  }, [qc, toast])

  const wsConnected = useWebSocket(handleWsMessage)

  // Default chart symbol to first watchlist item
  const watchlistItems = watchlistQ.data?.watchlist || []
  const effectiveChartSymbol = chartSymbol || (watchlistItems[0]?.symbol ? formatSymbol(watchlistItems[0].symbol) : 'RELIANCE')

  const value = {
    // Queries
    status: statusQ.data,
    statusLoading: statusQ.isLoading,
    watchlist: watchlistItems,
    positions: positionsQ.data?.positions ?? [],
    trades: tradesQ.data?.trades || [],
    tradesLoading: tradesQ.isLoading,
    // Refetch helpers
    refetchStatus: statusQ.refetch,
    refetchPositions: positionsQ.refetch,
    refetchTrades: tradesQ.refetch,
    refetchWatchlist: watchlistQ.refetch,
    // UI state
    wsConnected,
    activeTab,
    setActiveTab,
    chartSymbol: effectiveChartSymbol,
    setChartSymbol,
    showEmergencyModal,
    setShowEmergencyModal,
    showLiveModeModal,
    setShowLiveModeModal,
    // Toast
    toasts,
    removeToast,
    toast,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside AppProvider')
  return ctx
}
