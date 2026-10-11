-- data/kandidat.sqlite — hasil pemindai mekanis (tanpa LLM). Penulis tunggal: scripts/pemindai.py
-- Dibaca oleh mcp_server.py (kandidat_terbaru, status_sistem). Keputusan agent TIDAK ditulis ke sini.

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS pemindai_run(
  ts INTEGER PRIMARY KEY, day_wib TEXT, data_tick_ts INTEGER, n_symbols INTEGER, n_kandidat INTEGER,
  wake INTEGER, alasan TEXT, budget_sisa REAL, duration_ms INTEGER, ok INTEGER, err TEXT
);
CREATE INDEX IF NOT EXISTS ix_run_day ON pemindai_run(day_wib);

CREATE TABLE IF NOT EXISTS kandidat(
  id INTEGER PRIMARY KEY, run_ts INTEGER, day_wib TEXT, symbol TEXT, arah_dugaan TEXT,
  mark REAL, level REAL, sentuhan INTEGER, jarak_atr5m REAL,
  atr_1m REAL, atr_5m REAL, atr_15m REAL, atr_1h REAL, pct_24h REAL, funding REAL,
  lev_layak TEXT,        -- JSON: [{leverage, liq, jarak_liq_pct, x_atr5m}]
  score INTEGER, flags TEXT, ringkasan TEXT
);
CREATE INDEX IF NOT EXISTS ix_kandidat_day ON kandidat(day_wib, symbol);
CREATE INDEX IF NOT EXISTS ix_kandidat_run ON kandidat(run_ts);
