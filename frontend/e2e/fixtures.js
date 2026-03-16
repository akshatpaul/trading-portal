export const mockStatus = {
  mode: 'paper', capital: 10000.0, market_open: true, trading_day: true,
  kite_configured: false, telegram_configured: false,
  trading_allowed: true, block_reason: null,
  today: { trades: 2, wins: 1, losses: 1, final_pnl: 150.5, win_rate: 50.0 }
};

export const mockStatusLive = {
  mode: 'live', capital: 10000.0, market_open: true, trading_day: true,
  kite_configured: true, telegram_configured: false,
  trading_allowed: true, block_reason: null,
  today: { trades: 2, wins: 1, losses: 1, final_pnl: 150.5, win_rate: 50.0 }
};

export const mockStatusBlocked = {
  mode: 'paper', capital: 10000.0, market_open: true, trading_day: true,
  kite_configured: false, telegram_configured: false,
  trading_allowed: false, block_reason: 'Daily loss limit reached',
  today: { trades: 2, wins: 1, losses: 1, final_pnl: -300.0, win_rate: 50.0 }
};

export const mockWatchlist = {
  date: '2026-03-16',
  watchlist: [
    { symbol: 'HDFCBANK.NS', rank: 1, score: 0.95 },
    { symbol: 'TCS.NS', rank: 2, score: 0.82 },
    { symbol: 'INFY.NS', rank: 3, score: 0.71 },
  ]
};

export const mockPosition = {
  position: {
    id: 1, symbol: 'TCS.NS', mode: 'paper', side: 'BUY',
    quantity: 3, entry_price: 3000.0, target: 3018.0, stop_loss: 2991.0,
    ltp: 3010.0, unrealised_pnl: 30.0,
    entry_time: '2026-03-16T10:00:00+05:30', status: 'open'
  }
};

export const mockNoPosition = { position: null };

export const mockTrades = {
  trades: [
    { id: 1, symbol: 'HDFCBANK.NS', side: 'BUY', quantity: 5,
      entry_price: 1500.0, exit_price: 1509.0, pnl: 40.0,
      exit_reason: 'TARGET', entry_time: '2026-03-16T09:35:00+05:30',
      exit_time: '2026-03-16T10:15:00+05:30', mode: 'paper' },
    { id: 2, symbol: 'TCS.NS', side: 'BUY', quantity: 3,
      entry_price: 3000.0, exit_price: 2991.0, pnl: -27.0,
      exit_reason: 'STOP_LOSS', entry_time: '2026-03-16T11:00:00+05:30',
      exit_time: '2026-03-16T11:45:00+05:30', mode: 'paper' },
  ],
  count: 2
};

export const mockCandles = {
  symbol: 'TCS.NS', interval: '5m',
  candles: Array.from({ length: 20 }, (_, i) => ({
    timestamp: new Date(Date.UTC(2026, 2, 16, 4, i * 5)).toISOString(),
    open: 3000 + i, high: 3005 + i, low: 2998 + i, close: 3002 + i, volume: 100000
  }))
};

export const mockPerformance = {
  trades_count: 10, wins: 6, losses: 4, win_rate: 60.0,
  gross_pnl: 800.0, net_pnl: 720.0, profit_factor: 2.1,
  best_trade: 250.0, worst_trade: -120.0, avg_win: 133.3, avg_loss: -60.0
};

export const mockRiskLimits = {
  max_daily_loss: 300.0, max_position_size: 5000.0,
  max_trades_per_day: 3, max_leverage: 2.0,
  min_capital: 200.0, force_close_time: '15:10'
};

export const mockHealth = {
  status: 'ok', mode: 'paper',
  kite_configured: false, telegram_configured: false
};
