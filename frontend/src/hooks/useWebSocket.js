import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_URL } from '../utils/constants'

const RECONNECT_BASE = 1000
const RECONNECT_MAX  = 30000

export function useWebSocket(onMessage) {
  const ws         = useRef(null)
  const retryDelay = useRef(RECONNECT_BASE)
  const retryTimer = useRef(null)
  const isMounted  = useRef(true)
  const onMsgRef   = useRef(onMessage)
  const [connected, setConnected] = useState(false)

  onMsgRef.current = onMessage

  const connect = useCallback(() => {
    if (!isMounted.current) return
    try {
      const socket = new WebSocket(WS_URL)
      ws.current = socket

      socket.onopen = () => {
        if (!isMounted.current) return
        setConnected(true)
        retryDelay.current = RECONNECT_BASE
      }

      socket.onmessage = (ev) => {
        if (!isMounted.current) return
        try {
          const msg = JSON.parse(ev.data)
          onMsgRef.current?.(msg)
        } catch {
          // ignore malformed
        }
      }

      socket.onclose = () => {
        if (!isMounted.current) return
        setConnected(false)
        ws.current = null
        // exponential backoff reconnect
        retryTimer.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 2, RECONNECT_MAX)
          connect()
        }, retryDelay.current)
      }

      socket.onerror = () => {
        socket.close()
      }
    } catch {
      // WebSocket constructor can throw on bad URL
      retryTimer.current = setTimeout(connect, retryDelay.current)
    }
  }, [])

  useEffect(() => {
    isMounted.current = true
    connect()
    return () => {
      isMounted.current = false
      clearTimeout(retryTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return connected
}
