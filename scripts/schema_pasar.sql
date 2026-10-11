-- data/pasar.sqlite — data pasar Binance USDT-M Futures. Penulis tunggal: scripts/collector.py
PRAGMA auto_vacuum = INCREMENTAL;

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

-- Filter simbol dari /fapi/v1/exchangeInfo (+ fundingInfo). Nilai presisi disimpan TEXT.
CREATE TABLE IF NOT EXISTS symbol_info(
  symbol TEXT PRIMARY KEY,
  status TEXT, contract_type TEXT, base_asset TEXT, quote_asset TEXT, onboard_date INTEGER,
  tick_size TEXT, qty_step TEXT, min_qty TEXT, max_qty TEXT, min_notional TEXT,
  pct_up REAL, pct_down REAL, liq_fee REAL,
  funding_interval_h INTEGER DEFAULT 8, funding_cap REAL, funding_floor REAL,
  updated_ts INTEGER, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS symbol_info_hist(
  symbol TEXT, changed_ts INTEGER, field TEXT, old TEXT, new TEXT
);
CREATE INDEX IF NOT EXISTS ix_symbol_hist ON symbol_info_hist(symbol, changed_ts);

-- Bracket leverage/MMR dari endpoint web Binance (tidak terdokumentasi).
CREATE TABLE IF NOT EXISTS leverage_bracket(
  symbol TEXT, bracket INTEGER, notional_floor REAL, notional_cap REAL,
  max_leverage INTEGER, min_leverage INTEGER, mmr REAL, cum REAL, updated_ts INTEGER,
  PRIMARY KEY(symbol, bracket)
) WITHOUT ROWID;

-- Kline 1 menit harga terakhir (untuk isi limit/TP).
CREATE TABLE IF NOT EXISTS kline_1m(
  symbol TEXT, open_time INTEGER,
  open REAL, high REAL, low REAL, close REAL,
  volume REAL, quote_volume REAL, trades INTEGER, taker_buy_quote REAL,
  PRIMARY KEY(symbol, open_time)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_kline_time ON kline_1m(open_time);

-- Kline 1 menit mark price (untuk likuidasi/stop).
CREATE TABLE IF NOT EXISTS mark_kline_1m(
  symbol TEXT, open_time INTEGER,
  open REAL, high REAL, low REAL, close REAL,
  PRIMARY KEY(symbol, open_time)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_mark_time ON mark_kline_1m(open_time);

-- Snapshot premiumIndex per tick (kesegaran, funding berikutnya).
CREATE TABLE IF NOT EXISTS mark_snapshot(
  symbol TEXT, ts INTEGER, mark REAL, index_price REAL,
  last_funding_rate REAL, next_funding_time INTEGER,
  PRIMARY KEY(symbol, ts)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_mark_snapshot_ts ON mark_snapshot(ts);

-- Riwayat funding yang sudah settle (/fapi/v1/fundingRate).
CREATE TABLE IF NOT EXISTS funding_rate(
  symbol TEXT, funding_time INTEGER, rate REAL, mark_price REAL,
  PRIMARY KEY(symbol, funding_time)
) WITHOUT ROWID;

-- Peringkat volume 24 jam (watchlist dinamis; juga untuk baseline acak nanti).
CREATE TABLE IF NOT EXISTS ticker_24h(
  ts INTEGER, symbol TEXT, rank INTEGER, last REAL, pct_24h REAL, quote_volume REAL,
  PRIMARY KEY(ts, symbol)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS collector_run(
  ts INTEGER PRIMARY KEY, kind TEXT, symbols_n INTEGER, bars_n INTEGER,
  ok INTEGER, err TEXT, duration_ms INTEGER, weight_used INTEGER
);

CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, ts INTEGER, level TEXT, type TEXT, symbol TEXT, msg TEXT
);
CREATE INDEX IF NOT EXISTS ix_pasar_events_ts ON events(ts);
