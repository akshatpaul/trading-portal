import { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import { fetchCandles } from '../../api'
import { COLORS, INTERVALS } from '../../utils/constants'
import { calcEMA } from '../../utils/calculations'
import { formatSymbol } from '../../utils/formatters'

const CHART_OPTS = {
  layout: {
    background: { color: '#1e293b' },
    textColor:  '#94a3b8',
  },
  grid: {
    vertLines:  { color: '#334155' },
    horzLines:  { color: '#334155' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#64748b', labelBackgroundColor: '#334155' },
    horzLine: { color: '#64748b', labelBackgroundColor: '#334155' },
  },
  rightPriceScale: {
    borderColor: '#334155',
    textColor: '#94a3b8',
  },
  timeScale: {
    borderColor: '#334155',
    textColor: '#94a3b8',
    timeVisible: true,
    secondsVisible: false,
  },
}

export default function LiveChart({ symbol, position, mode }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const ema9Ref      = useRef(null)
  const ema21Ref     = useRef(null)
  const volRef       = useRef(null)
  const entryRef     = useRef(null)
  const targetRef    = useRef(null)
  const slRef        = useRef(null)

  const [interval, setInterval]   = useState('5m')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [symInput, setSymInput]   = useState(symbol || '')
  const [activeSymbol, setActiveSymbol] = useState(symbol || '')

  // Sync activeSymbol when prop changes
  useEffect(() => {
    if (symbol) {
      setActiveSymbol(symbol)
      setSymInput(symbol)
    }
  }, [symbol])

  // Init chart once
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      ...CHART_OPTS,
      width:  containerRef.current.clientWidth,
      height: 420,
    })
    chartRef.current = chart

    // Candlestick series
    candleRef.current = chart.addCandlestickSeries({
      upColor:   COLORS.profit,
      downColor: COLORS.loss,
      borderUpColor:   COLORS.profit,
      borderDownColor: COLORS.loss,
      wickUpColor:   COLORS.profit,
      wickDownColor: COLORS.loss,
    })

    // Volume histogram (pane 1)
    volRef.current = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      color: '#334155',
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    })

    // EMA lines
    ema9Ref.current = chart.addLineSeries({
      color: COLORS.ema9,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    ema21Ref.current = chart.addLineSeries({
      color: COLORS.ema21,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })

    // Resize observer
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        chart.applyOptions({ width: e.contentRect.width })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [])

  // Fetch candles whenever symbol/interval changes
  useEffect(() => {
    if (!activeSymbol || !candleRef.current) return

    setLoading(true)
    setError(null)

    const sym = activeSymbol.includes('.NS') ? activeSymbol : `${activeSymbol}.NS`

    fetchCandles(sym, interval, 200)
      .then(data => {
        const raw = data.candles || []
        if (!raw.length) {
          setError('No candle data returned')
          return
        }

        // Convert to lightweight-charts format
        const candles = raw.map(c => ({
          time:  Math.floor(new Date(c.timestamp).getTime() / 1000),
          open:  c.open,
          high:  c.high,
          low:   c.low,
          close: c.close,
        })).sort((a, b) => a.time - b.time)

        const volumes = raw.map(c => ({
          time:  Math.floor(new Date(c.timestamp).getTime() / 1000),
          value: c.volume,
          color: c.close >= c.open ? '#10b98133' : '#ef444433',
        })).sort((a, b) => a.time - b.time)

        candleRef.current.setData(candles)
        volRef.current.setData(volumes)

        // EMA calc
        const closes = candles.map(c => c.close)
        const ema9  = calcEMA(closes, 9)
        const ema21 = calcEMA(closes, 21)

        ema9Ref.current.setData(
          ema9.map(e => ({ time: candles[e.index].time, value: e.value }))
        )
        ema21Ref.current.setData(
          ema21.map(e => ({ time: candles[e.index].time, value: e.value }))
        )

        chartRef.current?.timeScale().fitContent()
      })
      .catch(err => setError(err.message || 'Failed to load candles'))
      .finally(() => setLoading(false))
  }, [activeSymbol, interval])

  // Draw position lines
  useEffect(() => {
    if (!candleRef.current) return

    // Remove old price lines
    if (entryRef.current) { candleRef.current.removePriceLine(entryRef.current); entryRef.current = null }
    if (targetRef.current) { candleRef.current.removePriceLine(targetRef.current); targetRef.current = null }
    if (slRef.current)    { candleRef.current.removePriceLine(slRef.current); slRef.current = null }

    if (position && formatSymbol(position.symbol) === activeSymbol) {
      if (position.entry_price) {
        entryRef.current = candleRef.current.createPriceLine({
          price: position.entry_price,
          color: '#94a3b8',
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: 'Entry',
        })
      }
      if (position.target) {
        targetRef.current = candleRef.current.createPriceLine({
          price: position.target,
          color: COLORS.profit,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Target',
        })
      }
      if (position.stop_loss) {
        slRef.current = candleRef.current.createPriceLine({
          price: position.stop_loss,
          color: COLORS.loss,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'SL',
        })
      }
    }
  }, [position, activeSymbol])

  function handleSymbolSubmit(e) {
    e.preventDefault()
    if (symInput.trim()) {
      setActiveSymbol(symInput.trim().toUpperCase())
    }
  }

  return (
    <div className="card flex flex-col gap-3">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <form onSubmit={handleSymbolSubmit} className="flex items-center gap-2">
          <input
            value={symInput}
            onChange={e => setSymInput(e.target.value.toUpperCase())}
            placeholder="Symbol e.g. RELIANCE"
            className="input-field w-36 text-sm"
          />
          <button type="submit" className="btn-primary text-xs py-1.5 px-3">Go</button>
        </form>

        {/* Interval selector */}
        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
          {INTERVALS.map(iv => (
            <button
              key={iv}
              onClick={() => setInterval(iv)}
              className={`text-xs px-3 py-1 rounded-md font-mono transition-colors ${
                interval === iv
                  ? 'bg-signal text-white'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {iv}
            </button>
          ))}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 ml-auto text-xs text-text-muted">
          <span className="flex items-center gap-1">
            <span className="w-4 h-0.5 bg-signal inline-block" />EMA9
          </span>
          <span className="flex items-center gap-1">
            <span className="w-4 h-0.5 bg-amber-500 inline-block" />EMA21
          </span>
          {mode === 'paper' && (
            <span className="text-amber-400 opacity-70">~15min delay</span>
          )}
        </div>

        {/* Active symbol */}
        <span className="font-mono font-bold text-text-primary text-sm ml-2">
          {activeSymbol} · {interval}
        </span>
      </div>

      {/* Chart area */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-card-bg/80 rounded-lg z-10">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-signal border-t-transparent rounded-full animate-spin" />
              <span className="text-text-muted text-sm">Loading chart...</span>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-card-bg/80 rounded-lg z-10">
            <div className="text-center">
              <p className="text-red-400 text-sm mb-1">Chart error</p>
              <p className="text-text-muted text-xs">{error}</p>
            </div>
          </div>
        )}
        <div ref={containerRef} style={{ minHeight: 420 }} />
      </div>
    </div>
  )
}
