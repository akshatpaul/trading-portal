import { useState, useCallback, useRef } from 'react'

let toastIdCounter = 0

export function useToast() {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t))
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 350)
  }, [])

  const addToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = ++toastIdCounter
    setToasts(prev => [...prev.slice(-4), { id, message, type, exiting: false }])
    if (duration > 0) {
      timers.current[id] = setTimeout(() => removeToast(id), duration)
    }
    return id
  }, [removeToast])

  const toast = {
    success: (msg, dur) => addToast(msg, 'success', dur),
    error:   (msg, dur) => addToast(msg, 'error', dur),
    warning: (msg, dur) => addToast(msg, 'warning', dur),
    info:    (msg, dur) => addToast(msg, 'info', dur),
  }

  return { toasts, addToast, removeToast, toast }
}
