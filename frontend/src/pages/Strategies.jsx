const STRATEGIES = [
  {
    id: 'ema_crossover',
    name: 'EMA 9/21 Crossover',
    tag: 'Momentum · Intraday',
    active: true,
    description:
      'Scans Nifty 50 every morning for trending stocks, then enters on EMA crossover with volume confirmation during market hours.',
    screener: [
      { label: 'Universe',      value: 'Nifty 50' },
      { label: 'Price range',   value: '₹200 – ₹3,000' },
      { label: 'Avg volume',    value: '> 5 lakh / day' },
      { label: 'ATR%',          value: '> 0.5% of price' },
      { label: 'ADX',           value: '> 20 (trending)' },
      { label: 'Stocks picked', value: 'Top 3 by composite score' },
    ],
    entry: [
      { label: 'Signal',       value: 'EMA 9 crosses above EMA 21' },
      { label: 'Volume',       value: 'Current vol > 1.5× 20-bar avg' },
      { label: 'ADX filter',   value: '> 20 at entry candle' },
      { label: 'Time window',  value: '9:30 AM – 2:30 PM IST' },
      { label: 'Direction',    value: 'Long (BUY) only' },
    ],
    exit: [
      { label: 'Target',      value: '+0.6% from entry', color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.3% from entry', color: 'text-red-400' },
      { label: 'Force close', value: '3:10 PM IST (EOD)', color: 'text-amber-400' },
    ],
    schedule: [
      { label: 'Screener runs', value: '8:45 AM IST (pre-market)' },
      { label: 'Signal check',  value: 'Every 5-minute candle close' },
      { label: 'Max positions', value: '1 at a time' },
    ],
  },
  {
    id: 'coming_soon_1',
    name: 'VWAP Reversion',
    tag: 'Mean Reversion · Intraday',
    active: false,
    description: 'Enters when price deviates significantly from VWAP with volume exhaustion signals. Coming soon.',
    screener: [], entry: [], exit: [], schedule: [],
  },
  {
    id: 'coming_soon_2',
    name: 'Breakout Scanner',
    tag: 'Momentum · Swing',
    active: false,
    description: 'Identifies stocks breaking out of multi-day consolidation ranges with ATR-based position sizing. Coming soon.',
    screener: [], entry: [], exit: [], schedule: [],
  },
]

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

function StrategyCard({ strategy }) {
  const { name, tag, active, description, screener, entry, exit, schedule } = strategy

  if (!active) {
    return (
      <div className="card opacity-40 cursor-not-allowed select-none">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-text-primary">{name}</h3>
            <span className="text-xs text-text-muted">{tag}</span>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400 font-medium">
            Coming Soon
          </span>
        </div>
        <p className="text-sm text-text-secondary">{description}</p>
      </div>
    )
  }

  return (
    <div className="card ring-1 ring-emerald-500/30">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-text-primary text-base">{name}</h3>
          <span className="text-xs text-text-muted">{tag}</span>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
          Active
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

export default function Strategies() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Strategies</h2>
        <p className="text-sm text-text-muted mt-0.5">
          One strategy runs at a time. Switch by activating a different one.
        </p>
      </div>

      <div className="space-y-4">
        {STRATEGIES.map(s => <StrategyCard key={s.id} strategy={s} />)}
      </div>
    </div>
  )
}
