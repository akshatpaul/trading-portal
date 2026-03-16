import { useState } from 'react'
import { emergencyStop } from '../../api'
import { useApp } from '../../context/AppContext'

export default function EmergencyStopModal() {
  const { setShowEmergencyModal, refetchStatus, refetchPositions, toast } = useApp()
  const [loading, setLoading] = useState(false)

  async function handleStop() {
    setLoading(true)
    try {
      await emergencyStop()
      toast.success('🚨 Emergency stop executed. All positions closed.')
      refetchStatus()
      refetchPositions()
      setShowEmergencyModal(false)
    } catch (err) {
      toast.error(`Emergency stop failed: ${err?.response?.data?.detail || err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-red-600 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">🚨</div>
          <h2 className="text-xl font-bold text-red-400 mb-2">Emergency Stop</h2>
          <p className="text-text-secondary text-sm">
            This will immediately close all open positions and halt all trading activity.
            This action cannot be undone.
          </p>
        </div>

        <div className="bg-red-950/50 border border-red-800 rounded-xl p-4 mb-6">
          <p className="text-red-300 text-sm font-medium text-center">
            ⚠️ All open positions will be closed at market price
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => setShowEmergencyModal(false)}
            className="flex-1 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-text-primary font-semibold transition-colors"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={handleStop}
            disabled={loading}
            className="flex-1 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Stopping...' : 'STOP ALL TRADING'}
          </button>
        </div>
      </div>
    </div>
  )
}
