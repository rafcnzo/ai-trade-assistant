-- data/psikologi.sqlite — panel psikologi pasar (§16.2). Penulis tunggal: scripts/psikologi.py (cron Hermes tiap jam).
-- Dibaca mcp_server.py (panel_psikologi, frontmatter catatan harian). Tidak ada skor gabungan; setiap indikator berdiri sendiri.

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS panel(
  ts INTEGER, symbol TEXT, indikator TEXT,          -- symbol '*' = pasar luas
  nilai REAL, zona TEXT,                             -- zona: takut_ekstrem | netral | serakah_ekstrem | tidak tersedia
  sumber TEXT, catatan TEXT,
  PRIMARY KEY(ts, symbol, indikator)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_panel_ind ON panel(symbol, indikator, ts);

CREATE TABLE IF NOT EXISTS panel_run(
  ts INTEGER PRIMARY KEY, ok INTEGER, n_ok INTEGER, n_gagal INTEGER, mode_zona TEXT, err TEXT, duration_ms INTEGER
);
