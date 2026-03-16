// TODO (Step 13): Trades data hook
// Fetches trade log from GET /api/trades
// Handles pagination, loading, and error states
// Returns: { trades, isLoading, error, fetchMore }

import { useState, useEffect } from 'react'
import axios from 'axios'

const API = 'http://localhost:8000'

export function useTrades(limit = 50) {
  const [trades, setTrades] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // TODO (Step 13): implement
  }, [limit])

  return { trades, isLoading, error }
}
