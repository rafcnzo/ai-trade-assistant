-- data/paper.sqlite — akun, order, posisi paper. Penulis tunggal: scripts/paper_engine.py
-- Tidak ada penghapusan baris; hasil hanya ditulis mesin.

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS account(
  name TEXT PRIMARY KEY, kind TEXT, budget_rule TEXT, budget_usdt REAL,
  status TEXT DEFAULT 'aktif'               -- aktif | pensiun (arena: persona yang kalah dari acak dipensiunkan skrip)
);
INSERT OR IGNORE INTO account(name, kind, budget_rule, budget_usdt) VALUES
  ('tiket', 'tiket', 'daily_total', 1.00),
  ('swing', 'swing', 'per_position', 10.00),
  ('acak',  'acak',  'daily_total', 1.00),   -- bayangan acak per order tiket agent (pembanding, hanya dibuat mesin)
  ('fade',     'tiket', 'daily_total', 1.00),  -- arena: lawan kerumunan (panel psikologi ekstrem + divergensi)
  ('breakout', 'tiket', 'daily_total', 1.00),  -- arena: tembus + uji ulang dengan volume
  ('rentang',  'tiket', 'daily_total', 1.00);  -- arena: mean reversion di pasar sideways

CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY,
  account TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,   -- side: LONG|SHORT (arah posisi yang dituju)
  type TEXT NOT NULL,                                               -- LIMIT|MARKET|STOP_MARKET
  reduce_only INTEGER NOT NULL DEFAULT 0,
  price REAL, stop_price REAL, qty REAL NOT NULL, leverage INTEGER,
  margin_usdt REAL, notional REAL, fee_reserved REAL,
  tp_price REAL, sl_price REAL, post_only INTEGER NOT NULL DEFAULT 1,
  tp_pct REAL, sl_pct REAL,                                         -- jarak relatif (akun acak), diresolusi saat terisi
  status TEXT NOT NULL,                                             -- NEW|ACTIVE|FILLED|CANCELED|EXPIRED|REJECTED
  reject_code TEXT, reject_reason TEXT,
  position_id INTEGER, oco_group INTEGER,
  plan_id TEXT, pattern TEXT, note TEXT, created_by TEXT,
  created_ts INTEGER NOT NULL, activate_ts INTEGER, expire_ts INTEGER, day_wib TEXT, done_ts INTEGER
);
CREATE INDEX IF NOT EXISTS ix_orders_live ON orders(status, symbol);
CREATE INDEX IF NOT EXISTS ix_orders_day ON orders(account, day_wib);

CREATE TABLE IF NOT EXISTS positions(
  id INTEGER PRIMARY KEY,
  account TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
  qty REAL NOT NULL, entry_price REAL NOT NULL, leverage INTEGER,
  margin_initial REAL, margin_now REAL, notional_entry REAL,
  mmr REAL, cum REAL, bracket INTEGER, liq_price REAL,
  tp_price REAL, sl_price REAL,
  tp_order_id INTEGER, sl_order_id INTEGER, entry_order_id INTEGER,
  plan_id TEXT, pattern TEXT, day_wib TEXT,
  opened_ts INTEGER, opened_bar INTEGER, closed_ts INTEGER, closed_bar INTEGER,
  close_reason TEXT,                       -- TP|HANGUS|STOP|MANUAL|EOD|DELISTED|FUNDING_LIQ
  exit_price REAL, realized_pnl REAL, fees_total REAL DEFAULT 0, funding_total REAL DEFAULT 0, net_result REAL,
  worst_mark REAL, best_mark REAL,
  ambiguous INTEGER NOT NULL DEFAULT 0, alt_outcome TEXT,
  status TEXT NOT NULL                     -- OPEN|CLOSED
);
CREATE INDEX IF NOT EXISTS ix_pos_open ON positions(status, symbol);
CREATE INDEX IF NOT EXISTS ix_pos_day ON positions(account, day_wib);

CREATE TABLE IF NOT EXISTS fills(
  id INTEGER PRIMARY KEY, order_id INTEGER, position_id INTEGER,
  ts INTEGER, bar_open_time INTEGER,
  price REAL, qty REAL, notional REAL, fee_usdt REAL, is_maker INTEGER,
  role TEXT,                               -- ENTRY|TP|SL|MARKET_EXIT|EOD|LIQUIDATION|DELISTED
  rule TEXT                                -- THROUGH|GAP_OPEN|MARKET_OPEN|STOP_TRIGGER|STOP_GAP|LIQUIDATION|EOD
);
CREATE INDEX IF NOT EXISTS ix_fills_pos ON fills(position_id);

CREATE TABLE IF NOT EXISTS liquidations(
  id INTEGER PRIMARY KEY, position_id INTEGER, ts INTEGER, bar_open_time INTEGER,
  liq_price REAL, mark_extreme REAL, last_extreme REAL, margin_lost REAL,
  ambiguous INTEGER, alt_outcome TEXT, mark_source TEXT, note TEXT
);

CREATE TABLE IF NOT EXISTS funding_payments(
  id INTEGER PRIMARY KEY, position_id INTEGER, funding_time INTEGER,
  rate REAL, mark_price REAL, notional REAL, amount_usdt REAL, margin_after REAL, liq_after REAL
);
CREATE INDEX IF NOT EXISTS ix_funding_pos ON funding_payments(position_id);

CREATE TABLE IF NOT EXISTS ledger(
  id INTEGER PRIMARY KEY, ts INTEGER, day_wib TEXT, account TEXT,
  kind TEXT,                               -- MARGIN_LOCK|MARGIN_RELEASE|FEE|FUNDING|PNL|LIQ_LOSS
  amount REAL, ref_table TEXT, ref_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_ledger_day ON ledger(account, day_wib);

CREATE TABLE IF NOT EXISTS daily_summary(
  day_wib TEXT, account TEXT,
  orders_n INTEGER, filled_n INTEGER, tidak_terisi_n INTEGER, tp_n INTEGER, hangus_n INTEGER, other_close_n INTEGER,
  margin_used REAL, fees REAL, funding REAL, pnl_net REAL, ambiguous_n INTEGER,
  PRIMARY KEY(day_wib, account)
) WITHOUT ROWID;

-- Bar terakhir yang sudah diproses mesin, per simbol.
CREATE TABLE IF NOT EXISTS cursor(symbol TEXT PRIMARY KEY, last_open_time INTEGER);

CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, ts INTEGER, level TEXT, type TEXT,
  position_id INTEGER, order_id INTEGER, msg TEXT
);
CREATE INDEX IF NOT EXISTS ix_paper_events_ts ON events(ts);
