// TODO (Step 13): Zustand global state store
//
// State:
//   mode          : 'paper' | 'live'
//   capital       : current capital
//   position      : open position or null
//   watchlist     : today's 3 stocks
//   candles       : map of symbol → candle array
//   trades        : recent trades array
//   dailyPnL      : today's net P&L
//   streak        : current winning streak
//   achievements  : earned achievements array
//   marketStatus  : 'pre' | 'open' | 'closed'

import { create } from 'zustand'

export const useTradingStore = create((set, get) => ({
  // State
  mode: 'paper',
  capital: 10000,
  position: null,
  watchlist: [],
  candles: {},
  trades: [],
  dailyPnL: 0,
  streak: 0,
  achievements: [],
  marketStatus: 'closed',

  // Actions — TODO (Step 13): implement all
  setMode: (mode) => set({ mode }),
  setCapital: (capital) => set({ capital }),
  setPosition: (position) => set({ position }),
  setWatchlist: (watchlist) => set({ watchlist }),
  updateCandles: (symbol, candles) =>
    set((state) => ({ candles: { ...state.candles, [symbol]: candles } })),
  addTrade: (trade) =>
    set((state) => ({ trades: [trade, ...state.trades] })),
  setDailyPnL: (dailyPnL) => set({ dailyPnL }),
  setStreak: (streak) => set({ streak }),
  addAchievement: (achievement) =>
    set((state) => ({ achievements: [...state.achievements, achievement] })),
  setMarketStatus: (marketStatus) => set({ marketStatus }),
}))
