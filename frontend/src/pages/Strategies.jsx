import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchStrategy, setStrategy } from '../api'

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
      { label: 'Target',      value: '+0.6% from entry',   color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.3% from entry',   color: 'text-red-400' },
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
      { label: 'Target',      value: '+0.6% from entry',   color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.3% from entry',   color: 'text-red-400' },
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
      { label: 'Target',      value: '+0.6% from entry',        color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.3% from entry',        color: 'text-red-400' },
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
      { label: 'Target',      value: '+0.6% from entry',          color: 'text-emerald-400' },
      { label: 'Stop loss',   value: '−0.3% from entry',          color: 'text-red-400' },
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

function StrategyCard({ id, isActive, isLocked, onActivate, activating }) {
  const meta = STRATEGY_METADATA[id]
  if (!meta) return null

  const { name, tag, description, screener, entry, exit, schedule } = meta

  return (
    <div className={`card ${isActive ? 'ring-1 ring-emerald-500/30' : ''}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-text-primary text-base">{name}</h3>
          <span className="text-xs text-text-muted">{tag}</span>
        </div>

        {isActive ? (
          <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
            Active
          </span>
        ) : isLocked ? (
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-700 text-slate-500 font-medium">
            Locked
          </span>
        ) : (
          <button
            onClick={() => onActivate(id)}
            disabled={activating}
            className="text-xs px-2.5 py-1 rounded-full bg-slate-700 hover:bg-slate-600 text-text-secondary hover:text-text-primary font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {activating ? 'Switching…' : 'Activate'}
          </button>
        )}
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
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['strategy'],
    queryFn: fetchStrategy,
    refetchInterval: 15_000,
  })

  const mutation = useMutation({
    mutationFn: setStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy'] }),
  })

  const activeStrategy  = data?.active_strategy ?? 'ema_crossover'
  const validStrategies = data?.valid_strategies ?? Object.keys(STRATEGY_METADATA)
  const locked          = data?.locked ?? false
  const lockReason      = data?.lock_reason ?? null

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-text-primary">Strategies</h2>
        <p className="text-sm text-text-muted mt-0.5">
          {!isLoading && (
            <>Active: <span className="text-text-primary font-medium">{STRATEGY_METADATA[activeStrategy]?.name ?? activeStrategy}</span> · </>
          )}
          Switch by activating a different one.
        </p>
      </div>

      {locked && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Strategy locked for today ({lockReason}) — resets at midnight.
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="card h-24 animate-pulse bg-slate-800/50" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {validStrategies.map(id => (
            <StrategyCard
              key={id}
              id={id}
              isActive={id === activeStrategy}
              isLocked={locked && id !== activeStrategy}
              onActivate={(name) => mutation.mutate(name)}
              activating={mutation.isPending && mutation.variables === id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
