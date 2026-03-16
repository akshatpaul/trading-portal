// TODO (Step 13): Market status hook
// Polls GET /api/status every 30s
// Returns: { isOpen, isPre, isPost, mode, capital, kiteConfigured }

import { useState, useEffect } from 'react'

export function useMarketStatus() {
  const [status, setStatus] = useState({
    isOpen: false,
    isPre: false,
    isPost: false,
    mode: 'paper',
    capital: 10000,
    kiteConfigured: false,
  })

  useEffect(() => {
    // TODO (Step 13): implement polling
  }, [])

  return status
}
