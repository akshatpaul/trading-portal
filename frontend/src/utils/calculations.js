export function unrealisedPnL(entryPrice, currentPrice, quantity) {
  if (!entryPrice || !currentPrice || !quantity) return 0
  return (currentPrice - entryPrice) * quantity
}

export function winRate(wins, total) {
  if (!total) return 0
  return (wins / total) * 100
}

export function profitFactor(totalWins, totalLosses) {
  if (!totalLosses) return totalWins > 0 ? 999 : 0
  return Math.abs(totalWins / totalLosses)
}

export function pctChange(from, to) {
  if (!from) return 0
  return ((to - from) / from) * 100
}

// Calculate EMA from array of close prices
export function calcEMA(closes, period) {
  if (closes.length < period) return []
  const k = 2 / (period + 1)
  const result = []
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period
  result.push({ index: period - 1, value: ema })
  for (let i = period; i < closes.length; i++) {
    ema = closes[i] * k + ema * (1 - k)
    result.push({ index: i, value: ema })
  }
  return result
}

// Calculate position progress toward target / stop
export function positionProgress(entry, ltp, target, stopLoss, side) {
  if (!entry || !ltp) return { toTarget: 0, toStop: 0, pctToTarget: 0 }
  if (side === 'BUY') {
    const totalRange = target - stopLoss
    if (!totalRange) return { toTarget: 0, toStop: 0, pctToTarget: 0 }
    const progress = ((ltp - stopLoss) / totalRange) * 100
    return {
      pctToTarget: Math.min(100, Math.max(0, progress)),
      toTarget: target - ltp,
      toStop: ltp - stopLoss,
    }
  } else {
    const totalRange = stopLoss - target
    if (!totalRange) return { toTarget: 0, toStop: 0, pctToTarget: 0 }
    const progress = ((stopLoss - ltp) / totalRange) * 100
    return {
      pctToTarget: Math.min(100, Math.max(0, progress)),
      toTarget: ltp - target,
      toStop: stopLoss - ltp,
    }
  }
}

// Calculate streak from trades array
export function calcStreak(trades) {
  if (!trades || trades.length === 0) return 0
  const sorted = [...trades].sort((a, b) => new Date(b.exit_time || b.entry_time) - new Date(a.exit_time || a.entry_time))
  let streak = 0
  for (const trade of sorted) {
    const pnl = trade.net_pnl ?? trade.pnl ?? 0
    if (pnl > 0) streak++
    else break
  }
  return streak
}
