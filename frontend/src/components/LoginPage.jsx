import { useState } from 'react'
import { login } from '../api'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      localStorage.setItem('trading_token', data.access_token)
      onLogin()
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Login failed. Check credentials.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo / header */}
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">📈</div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Trading Portal</h1>
          <p className="text-slate-400 text-sm mt-1">Sign in to access your dashboard</p>
        </div>

        {/* Card */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label
                htmlFor="username"
                className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                disabled={loading}
                className="
                  w-full bg-slate-900 border border-slate-600
                  text-white font-mono text-sm
                  rounded-lg px-3.5 py-2.5
                  focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
                  disabled:opacity-50
                  transition-colors
                "
                placeholder="admin"
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                disabled={loading}
                className="
                  w-full bg-slate-900 border border-slate-600
                  text-white font-mono text-sm
                  rounded-lg px-3.5 py-2.5
                  focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500
                  disabled:opacity-50
                  transition-colors
                "
                placeholder="••••••••"
              />
            </div>

            {/* Error message */}
            {error && (
              <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm rounded-lg px-3.5 py-2.5">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="
                w-full bg-emerald-600 hover:bg-emerald-500
                disabled:bg-emerald-800 disabled:cursor-not-allowed
                text-white font-semibold text-sm
                rounded-lg px-4 py-2.5
                transition-colors
                flex items-center justify-center gap-2
              "
            >
              {loading ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in…
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-slate-600 text-xs mt-6">
          Personal trading system — authorised access only
        </p>
      </div>
    </div>
  )
}
