"""
database/models.py — SQLite table schemas (as CREATE TABLE strings)

No ORM used — plain sqlite3 for simplicity.
All timestamps stored as ISO-8601 strings in IST.

TODO (Step 2): Define all CREATE TABLE statements as constants.
              init_db() in db.py will execute these.
"""

# ── Candles ───────────────────────────────────
CREATE_CANDLES = """
CREATE TABLE IF NOT EXISTS candles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    interval    TEXT NOT NULL,          -- '5m' | '1d'
    timestamp   TEXT NOT NULL,          -- ISO-8601 IST
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      INTEGER NOT NULL,
    UNIQUE(symbol, interval, timestamp)
);
"""

# ── Signals ───────────────────────────────────
CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,          -- 'BUY' | 'SELL'
    price       REAL NOT NULL,
    target      REAL NOT NULL,
    stop_loss   REAL NOT NULL,
    reason      TEXT,
    timestamp   TEXT NOT NULL,
    acted_on    INTEGER DEFAULT 0       -- 0=ignored, 1=traded
);
"""

# ── Positions (open trades) ───────────────────
CREATE_POSITIONS = """
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    mode            TEXT NOT NULL,      -- 'paper' | 'live'
    side            TEXT NOT NULL,      -- 'BUY'
    quantity        INTEGER NOT NULL,
    entry_price     REAL NOT NULL,
    target          REAL NOT NULL,
    stop_loss       REAL NOT NULL,
    entry_time      TEXT NOT NULL,
    signal_id       INTEGER,
    status          TEXT DEFAULT 'open', -- 'open' | 'closed'
    strategy        TEXT DEFAULT 'ema_crossover'
);
"""

# ── Trades (completed round-trips) ────────────
CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    mode            TEXT NOT NULL,      -- 'paper' | 'live'
    side            TEXT NOT NULL,      -- 'BUY'
    quantity        INTEGER NOT NULL,
    entry_price     REAL NOT NULL,
    exit_price      REAL NOT NULL,
    entry_time      TEXT NOT NULL,
    exit_time       TEXT NOT NULL,
    exit_reason     TEXT NOT NULL,      -- 'TARGET' | 'STOP_LOSS' | 'FORCE_CLOSE' | 'MANUAL'
    gross_pnl       REAL NOT NULL,
    brokerage       REAL NOT NULL,
    stt             REAL NOT NULL,
    exchange_fee    REAL NOT NULL,
    sebi_charge     REAL NOT NULL,
    gst             REAL NOT NULL,
    stamp_duty      REAL NOT NULL,
    total_cost      REAL NOT NULL,
    net_pnl         REAL NOT NULL,
    tax_estimate    REAL NOT NULL,
    final_pnl       REAL NOT NULL,
    position_id     INTEGER
);
"""

# ── Daily Summary ─────────────────────────────
CREATE_DAILY_SUMMARY = """
CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD
    mode            TEXT NOT NULL,
    trades_count    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    gross_pnl       REAL DEFAULT 0,
    total_cost      REAL DEFAULT 0,
    net_pnl         REAL DEFAULT 0,
    tax_estimate    REAL DEFAULT 0,
    final_pnl       REAL DEFAULT 0,
    win_rate        REAL DEFAULT 0,
    profit_factor   REAL DEFAULT 0,
    capital_end     REAL DEFAULT 0,
    streak          INTEGER DEFAULT 0
);
"""

# ── Watchlist ─────────────────────────────────
CREATE_WATCHLIST = """
CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,          -- YYYY-MM-DD
    symbol      TEXT NOT NULL,
    rank        INTEGER NOT NULL,
    score       REAL,
    atr_pct     REAL,
    adx         REAL,
    vol_ratio   REAL,
    price       REAL,
    UNIQUE(date, symbol)
);
"""

# ── Achievements ──────────────────────────────
CREATE_ACHIEVEMENTS = """
CREATE TABLE IF NOT EXISTS achievements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,   -- e.g. 'sharpshooter'
    name        TEXT NOT NULL,
    emoji       TEXT,
    earned_at   TEXT,
    times_earned INTEGER DEFAULT 0
);
"""

# ── App Settings (key-value) ──────────────────
CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

# ── Activity Log ──────────────────────────────
CREATE_ACTIVITY_LOG = """
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,          -- ISO-8601 IST
    event_type  TEXT NOT NULL,          -- screener|signal|trade_entry|trade_exit|force_close|risk_block|daily_summary|system
    symbol      TEXT,                   -- nullable
    message     TEXT NOT NULL,
    data        TEXT                    -- JSON blob for extra details
);
"""

ALL_TABLES = [
    CREATE_CANDLES,
    CREATE_SIGNALS,
    CREATE_POSITIONS,
    CREATE_TRADES,
    CREATE_DAILY_SUMMARY,
    CREATE_WATCHLIST,
    CREATE_ACHIEVEMENTS,
    CREATE_SETTINGS,
    CREATE_ACTIVITY_LOG,
]
