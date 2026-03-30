// All strategies run in parallel — no switching needed

// ── Static display metadata per strategy ──────────────────────
const STRATEGY_METADATA = {
  ema_crossover: {
    name: 'EMA 9/21 Crossover',
    tag: 'Momentum · Intraday',
    description:
      'Scans Nifty 50 every morning for trending stocks, then enters on EMA crossover with ADX trend confirmation and volume surge filter. Highest quality signals.',
    screener: [
      { label: 'Universe',      value: 'Nifty 50' },
      { label: 'Price range',   value: '₹200 – ₹3,000' },
      { label: 'Avg volume',    value: '> 5 lakh / day' },
      { label: 'ATR%',          value: '> 0.5% of price' },
      { label: 'ADX',           value: '> 20 (trending)' },
      { label: 'Stocks picked', value: 'Top 3 by composite score' },
    ],
    entry: [
      { label: 'Signal',      value: 'EMA 9 crosses above EMA 21' },
      { label: 'Volume',      value: 'Current vol > 1.5× 20-bar avg' },
      { label: 'ADX filter',  value: '> 20 at entry candle' },
      { label: 'Time window', value: '9:30 AM – 2:30 PM IST' },
      { label: 'Direction',   value: 'Long (BUY) only' },
    ],
    exit: [
      { label: 'Target',      value: '+1.0% from entry',   color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.5% from entry',   color: 'text-red-400' },
      { label: 'Force close', value: '3:10 PM IST (EOD)',  color: 'text-amber-400' },
    ],
    schedule: [
      { label: 'Screener runs', value: '8:45 AM IST (pre-market)' },
      { label: 'Signal check',  value: 'Every 5-minute candle close' },
      { label: 'Max positions', value: '1 at a time' },
    ],
  },
  relaxed_ema: {
    name: 'Relaxed EMA Crossover',
    tag: 'Momentum · Intraday',
    description:
      'EMA crossover without ADX or volume filters. More signals, wider entry window up to 3:00 PM. Suitable for low-volatility days or testing order flow.',
    screener: [
      { label: 'Universe',      value: 'Nifty 50 (same watchlist)' },
      { label: 'Stocks picked', value: 'Top 3 by composite score' },
    ],
    entry: [
      { label: 'Signal',      value: 'EMA 9 crosses above EMA 21' },
      { label: 'Volume',      value: 'No filter' },
      { label: 'ADX filter',  value: 'No filter' },
      { label: 'Time window', value: '9:30 AM – 3:00 PM IST' },
      { label: 'Direction',   value: 'Long (BUY) only' },
    ],
    exit: [
      { label: 'Target',      value: '+1.0% from entry',   color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.5% from entry',   color: 'text-red-400' },
      { label: 'Force close', value: '3:10 PM IST (EOD)',  color: 'text-amber-400' },
    ],
    schedule: [
      { label: 'Screener runs', value: '8:45 AM IST (pre-market)' },
      { label: 'Signal check',  value: 'Every 5-minute candle close' },
      { label: 'Max positions', value: '1 at a time' },
    ],
  },
  rsi_bounce: {
    name: 'RSI Oversold Bounce',
    tag: 'Mean Reversion · Intraday',
    description:
      'Buys when RSI(14) freshly crosses below 35 (oversold). Exits when RSI recovers above 65, or when fixed target/stop is hit. Good for testing exits and stop-loss logic.',
    screener: [
      { label: 'Universe',      value: 'Nifty 50 (same watchlist)' },
      { label: 'Stocks picked', value: 'Top 3 by composite score' },
    ],
    entry: [
      { label: 'Signal',      value: 'RSI(14) crosses below 35' },
      { label: 'Time window', value: '9:30 AM – 2:30 PM IST' },
      { label: 'Direction',   value: 'Long (BUY) only' },
    ],
    exit: [
      { label: 'RSI exit',    value: 'RSI > 65 (overbought)',  color: 'text-sky-400' },
      { label: 'Target',      value: '+1.0% from entry',        color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.5% from entry',        color: 'text-red-400' },
      { label: 'Force close', value: '3:10 PM IST (EOD)',        color: 'text-amber-400' },
    ],
    schedule: [
      { label: 'Screener runs', value: '8:45 AM IST (pre-market)' },
      { label: 'Signal check',  value: 'Every 5-minute candle close' },
      { label: 'Max positions', value: '1 at a time' },
    ],
  },
  vwap_cross: {
    name: 'VWAP Breakout',
    tag: 'Momentum · Intraday',
    description:
      'Enters when price freshly crosses above intraday VWAP. Exits the moment price falls back below VWAP. Good for testing real-time chart signals and watchlist.',
    screener: [
      { label: 'Universe',      value: 'Nifty 50 (same watchlist)' },
      { label: 'Stocks picked', value: 'Top 3 by composite score' },
    ],
    entry: [
      { label: 'Signal',      value: 'Close crosses above VWAP' },
      { label: 'Time window', value: '9:30 AM – 2:30 PM IST' },
      { label: 'Direction',   value: 'Long (BUY) only' },
    ],
    exit: [
      { label: 'VWAP exit',   value: 'Price drops below VWAP',  color: 'text-sky-400' },
      { label: 'Target',      value: '+1.0% from entry',          color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.5% from entry',          color: 'text-red-400' },
      { label: 'Force close', value: '3:10 PM IST (EOD)',          color: 'text-amber-400' },
    ],
    schedule: [
      { label: 'Screener runs', value: '8:45 AM IST (pre-market)' },
      { label: 'Signal check',  value: 'Every 5-minute candle close' },
      { label: 'Max positions', value: '1 at a time' },
    ],
  },
}

// ── Sub-components ────────────────────────────

function Section({ title, rows }) {
  if (!rows.length) return null
  return (
    <div>
      <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">{title}</h4>
      <div className="space-y-1.5">
        {rows.map(r => (
          <div key={r.label} className="flex justify-between items-center text-sm">
            <span className="text-text-secondary">{r.label}</span>
            <span className={`font-medium ${r.color ?? 'text-text-primary'}`}>{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function StrategyCard({ id }) {
  const meta = STRATEGY_METADATA[id]
  if (!meta) return null
  const { name, tag, description, screener, entry, exit, schedule } = meta

  return (
    <div className="card ring-1 ring-emerald-500/20">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-text-primary text-base">{name}</h3>
          <span className="text-xs text-text-muted">{tag}</span>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
          Running
        </span>
      </div>

      <p className="text-sm text-text-secondary mb-5">{description}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="space-y-5">
          <Section title="Pre-market Screener" rows={screener} />
          <Section title="Schedule" rows={schedule} />
        </div>
        <div className="space-y-5">
          <Section title="Entry Conditions" rows={entry} />
          <Section title="Exit Rules" rows={exit} />
        </div>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────

export default function Strategies() {
  const strategies = Object.keys(STRATEGY_METADATA)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Strategies</h2>
        <p className="text-sm text-text-muted mt-0.5">
          All strategies run in parallel. Each watchlist stock is claimed by the first strategy that fires a signal on it.
        </p>
      </div>

      <div className="space-y-4">
        {strategies.map(id => <StrategyCard key={id} id={id} />)}
      </div>
    </div>
  )
}
