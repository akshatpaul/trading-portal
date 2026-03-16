import { useState } from 'react'
import { setModeLive } from '../../api'
import { useApp } from '../../context/AppContext'
import { LIVE_CONFIRM_TEXT } from '../../utils/constants'

export default function LiveModeConfirmModal() {
  const { setShowLiveModeModal, refetchStatus, toast } = useApp()
  const [input, setInput]   = useState('')
  const [loading, setLoading] = useState(false)

  const confirmed = input.trim() === LIVE_CONFIRM_TEXT

  async function handleConfirm() {
    if (!confirmed) return
    setLoading(true)
    try {
      await setModeLive()
      toast.success('🔴 Live trading mode activated. Be careful!')
      refetchStatus()
      setShowLiveModeModal(false)
    } catch (err) {
      toast.error(`Failed to switch to live mode: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-orange-600 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">💸</div>
          <h2 className="text-xl font-bold text-orange-400 mb-2">Switch to Live Trading</h2>
          <p className="text-text-secondary text-sm">
            You are about to switch to <strong className="text-text-primary">live trading mode</strong>.
            Real money will be used for every trade. Make sure you are ready.
          </p>
        </div>

        <div className="bg-orange-950/50 border border-orange-800 rounded-xl p-4 mb-5">
          <p className="text-orange-300 text-sm font-medium text-center">
            ⚠️ Real money. Real losses. Real consequences.
          </p>
        </div>

        <div className="mb-5">
          <label className="text-text-secondary text-xs mb-2 block">
            Type exactly to confirm:
          </label>
          <p className="text-orange-300 text-xs font-mono bg-slate-800 px-3 py-2 rounded-lg mb-3 break-all">
            {LIVE_CONFIRM_TEXT}
          </p>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Type the confirmation text..."
            className="input-field w-full"
          />
          {input && !confirmed && (
            <p className="text-red-400 text-xs mt-1">Text doesn't match. Check for typos.</p>
          )}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => setShowLiveModeModal(false)}
            className="flex-1 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-text-primary font-semibold transition-colors"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!confirmed || loading}
            className="flex-1 py-3 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-bold transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Switching...' : 'Go Live'}
          </button>
        </div>
      </div>
    </div>
  )
}
