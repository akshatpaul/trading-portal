export function formatINR(amount) {
  if (amount == null) return '—'
  return `₹${Math.abs(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function formatPnL(amount) {
  if (amount == null) return { text: '—', sign: '', colorClass: 'text-text-muted' }
  const sign = amount >= 0 ? '+' : '-'
  const colorClass = amount >= 0 ? 'text-profit' : 'text-loss'
  const text = `${sign}${formatINR(Math.abs(amount))}`
  return { text, sign, colorClass }
}

export function formatPct(value, decimals = 1) {
  if (value == null) return '—'
  return `${Number(value).toFixed(decimals)}%`
}

export function formatTime(isoString, mode = 'time') {
  if (!isoString) return '—'
  const d = new Date(isoString)
  if (mode === 'time') {
    return d.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Kolkata',
    })
  }
  if (mode === 'datetime') {
    return d.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Kolkata',
    })
  }
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    timeZone: 'Asia/Kolkata',
  })
}

export function formatSymbol(symbol) {
  return symbol?.replace('.NS', '') ?? symbol
}

export function formatNumber(val, decimals = 2) {
  if (val == null) return '—'
  return Number(val).toFixed(decimals)
}
