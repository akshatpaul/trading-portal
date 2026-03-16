// In production (served via nginx), use relative URLs so requests go to the same domain.
// In local dev (Vite proxy), also use relative URLs — vite.config.js proxies /api and /ws.
export const API_BASE = ''
export const WS_URL   = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

export const MODE = {
  PAPER: 'paper',
  LIVE:  'live',
}

export const LIVE_CONFIRM_TEXT = 'I understand this uses real money'

export const COLORS = {
  profit:  '#10b981',
  loss:    '#ef4444',
  signal:  '#6366f1',
  warning: '#f59e0b',
  info:    '#3b82f6',
  ema9:    '#6366f1',
  ema21:   '#f59e0b',
  volume:  '#334155',
}

export const INTERVALS = ['5m', '15m', '1d']

export const NIFTY50 = [
  'HDFCBANK', 'RELIANCE', 'TCS', 'INFY', 'ICICIBANK',
  'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK',
  'LT', 'AXISBANK', 'ASIANPAINT', 'MARUTI', 'TITAN',
  'WIPRO', 'ULTRACEMCO', 'NESTLEIND', 'BAJFINANCE', 'BAJAJFINSV',
  'TECHM', 'SUNPHARMA', 'HCLTECH', 'ONGC', 'POWERGRID',
  'NTPC', 'TATAMOTORS', 'TATASTEEL', 'ADANIENT', 'ADANIPORTS',
  'COALINDIA', 'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM',
  'HEROMOTOCO', 'HINDALCO', 'INDUSINDBK', 'JSWSTEEL', 'MM',
  'CIPLA', 'APOLLOHOSP', 'BAJAJ-AUTO', 'BPCL', 'BRITANNIA',
  'HDFCLIFE', 'SBILIFE', 'TATACONSUM', 'UPL', 'VEDL',
]

export const GO_LIVE_CRITERIA = {
  min_trades:        30,
  min_win_rate:      0.50,
  min_profit_factor: 1.50,
  max_drawdown:      0.15,
}

export const TRADE_REASON_BADGES = {
  target:      { emoji: '🎯', label: 'Target Hit',   color: 'text-emerald-400' },
  stop_loss:   { emoji: '🛑', label: 'Stop Loss',    color: 'text-red-400' },
  force_close: { emoji: '⏰', label: 'Force Close',  color: 'text-amber-400' },
  manual:      { emoji: '✋', label: 'Manual',       color: 'text-blue-400' },
}
