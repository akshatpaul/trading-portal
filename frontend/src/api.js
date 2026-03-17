import axios from 'axios'
import { API_BASE } from './utils/constants'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

// ── Auth interceptors ──────────────────────────────────────────

// Request: attach JWT from localStorage if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('trading_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Response: on 401, clear token and reload — but ONLY if we had a token.
// If there's no token yet (login page), just reject silently to avoid reload loops.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const isLoginRequest = error.config?.url?.includes('/api/auth/login')
      const hadToken = !!localStorage.getItem('trading_token')
      if (!isLoginRequest && hadToken) {
        localStorage.removeItem('trading_token')
        window.location.reload()
      }
    }
    return Promise.reject(error)
  }
)

// ── Auth ───────────────────────────────────────────────────────

export async function login(username, password) {
  const { data } = await api.post('/api/auth/login', { username, password })
  return data
}

export async function fetchMe() {
  const { data } = await api.get('/api/auth/me')
  return data
}

// ── API calls ──────────────────────────────────────────────────

export async function fetchHealth() {
  const { data } = await api.get('/health')
  return data
}

export async function fetchStatus() {
  const { data } = await api.get('/api/status')
  return data
}

export async function fetchWatchlist() {
  const { data } = await api.get('/api/watchlist')
  return data
}

export async function fetchPositions() {
  const { data } = await api.get('/api/positions')
  return data
}

export async function fetchTrades(limit = 50) {
  const { data } = await api.get(`/api/trades?limit=${limit}`)
  return data
}

export async function fetchCandles(symbol, interval = '5m', limit = 200) {
  const { data } = await api.get(`/api/candles/${symbol}?interval=${interval}&limit=${limit}`)
  return data
}

export async function fetchPerformance() {
  const { data } = await api.get('/api/performance')
  return data
}

export async function fetchRiskLimits() {
  const { data } = await api.get('/api/risk-limits')
  return data
}

export async function setModeLive() {
  const { data } = await api.post('/api/mode/live', {
    confirmation: 'I understand this uses real money',
  })
  return data
}

export async function setModePaper() {
  const { data } = await api.post('/api/mode/paper')
  return data
}

export async function emergencyStop() {
  const { data } = await api.post('/api/emergency-stop')
  return data
}

export async function fetchActivity(limit = 200, date = null) {
  const params = new URLSearchParams({ limit })
  if (date) params.set('date', date)
  const { data } = await api.get(`/api/activity?${params}`)
  return data
}

export async function fetchKiteLoginUrl() {
  const { data } = await api.get('/api/kite/login-url')
  return data
}

export default api
