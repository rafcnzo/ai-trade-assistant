-- data/budget.sqlite — biaya API Anthropic. Penulis tunggal: scripts/budget_guard.py

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS api_calls(
  id INTEGER PRIMARY KEY, ts INTEGER, day_wib TEXT, month_wib TEXT,
  model_requested TEXT, model_served TEXT, purpose TEXT, ref TEXT,
  request_id TEXT UNIQUE,
  input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
  cache_write_5m_tokens INTEGER, cache_write_1h_tokens INTEGER,
  speed TEXT, cost_usd REAL, price_version TEXT
);
CREATE INDEX IF NOT EXISTS ix_calls_day ON api_calls(day_wib);
CREATE INDEX IF NOT EXISTS ix_calls_month ON api_calls(month_wib);

CREATE TABLE IF NOT EXISTS price_table(
  model TEXT, price_version TEXT,
  input REAL, output REAL, cache_read_mult REAL, cw5_mult REAL, cw1h_mult REAL,
  tier_above INTEGER, input_hi REAL, output_hi REAL,
  PRIMARY KEY(model, price_version)
);

CREATE TABLE IF NOT EXISTS guard_state(key TEXT PRIMARY KEY, value TEXT);
