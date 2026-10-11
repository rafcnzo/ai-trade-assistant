/* dashboard crypto-analyst — vanilla JS, Lightweight Charts v4 (CDN). Semua data dari /api/* (baca saja). */
const $ = (s) => document.querySelector(s);
const fmt = (x, d = 4) => (x === null || x === undefined || Number.isNaN(x)) ? "—" : Number(x).toFixed(d);
const usd = (x, sign = false) => (x === null || x === undefined) ? "—" : (sign && x >= 0 ? "+" : "") + "$" + Number(x).toFixed(4);
const px = (x) => (x === null || x === undefined) ? "—" : Number(x).toPrecision(6).replace(/\.?0+$/, "");
const wib = (ms) => ms ? new Date(Number(ms)).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false }) : "—";
const jam = (ms) => ms ? new Date(Number(ms)).toLocaleTimeString("id-ID", { timeZone: "Asia/Jakarta", hour12: false }) : "—";
const TF_SEC = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400 };
const OFF = 7 * 3600; // sumbu waktu Lightweight Charts memakai UTC → geser ke WIB
const wibT = (t) => new Date((t - OFF) * 1000).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false });
const state = { symbol: null, tf: "5m", acak: false, lastBar: null, ps: "BTCUSDT" };
const api = async (p) => { const r = await fetch(p, { cache: "no-store" }); return r.json(); };

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
  if (b.dataset.tab === "riwayat") loadRiwayat();
  if (b.dataset.tab === "statistik") loadStatistik();
  if (b.dataset.tab === "kandidat") loadKandidat();
  if (b.dataset.tab === "psikologi") loadPsikologi();
  if (b.dataset.tab === "jurnal") loadJurnal();
  if (b.dataset.tab === "chart") { chart && chart.timeScale().fitContent(); }
});

// ---------------------------------------------------------------- chart
let chart, candles, volume, lines = [];
const hasLWC = typeof LightweightCharts !== "undefined";
function initChart() {
  if (!hasLWC) { $("#chart").innerHTML = '<div class="muted" style="padding:20px">Pustaka chart (CDN unpkg) tidak termuat — butuh internet sekali. Tabel tetap berfungsi.</div>'; return; }
  chart = LightweightCharts.createChart($("#chart"), {
    layout: { background: { color: "#121722" }, textColor: "#d6dbe5" }, grid: { vertLines: { color: "#1a2130" }, horzLines: { color: "#1a2130" } },
    timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#1f2736" }, rightPriceScale: { borderColor: "#1f2736" },
    crosshair: { mode: 0 }, localization: { locale: "id-ID", timeFormatter: wibT },
  });
  candles = chart.addCandlestickSeries({ upColor: "#26a69a", downColor: "#ef5350", borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350" });
  volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", color: "#2b3447" });
  chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  new ResizeObserver(() => chart.applyOptions({ width: $("#chart").clientWidth, height: $("#chart").clientHeight })).observe($("#chart"));
  $("#legend").innerHTML = '<span><i style="background:#26a69a"></i>▲ entry LONG</span><span><i style="background:#ef5350"></i>▼ entry SHORT</span>' +
    '<span><i style="background:#7be3b2"></i>TP</span><span><i style="background:#ff5c5c"></i>likuidasi</span><span><i style="background:#9aa4b8"></i>STOP/EOD/manual</span>' +
    '<span><i style="background:#f0b429"></i>kedaluwarsa/batal</span><span><i style="background:#4f8cff"></i>garis: entry · TP · liq · order</span>';
}
function snap(t) { const s = TF_SEC[state.tf]; return Math.floor(t / s) * s; }
async function loadChart(full = true) {
  if (!chart || !state.symbol) return;
  const data = await api(`/api/candles?symbol=${encodeURIComponent(state.symbol)}&tf=${state.tf}&n=600`);
  if (!Array.isArray(data) || !data.length) { $("#chart-info").textContent = `${state.symbol} ${state.tf}: tidak ada bar (collector belum menyimpan simbol ini)`; candles.setData([]); volume.setData([]); return; }
  const cd = data.map(b => ({ time: b.time + OFF, open: b.open, high: b.high, low: b.low, close: b.close }));
  const vd = data.map(b => ({ time: b.time + OFF, value: b.volume, color: b.close >= b.open ? "rgba(38,166,154,.35)" : "rgba(239,83,80,.35)" }));
  if (full || !state.lastBar) { candles.setData(cd); volume.setData(vd); chart.timeScale().fitContent(); }
  else { const last = cd[cd.length - 1]; if (last.time >= state.lastBar) { candles.update(last); volume.update(vd[vd.length - 1]); if (cd.length > 1 && cd[cd.length - 2].time > state.lastBar) { candles.setData(cd); volume.setData(vd); } } }
  state.lastBar = cd[cd.length - 1].time;
  const last = data[data.length - 1];
  $("#chart-info").textContent = `${state.symbol} ${state.tf} · close ${px(last.close)} · bar terakhir ${wib(last.time * 1000)} WIB · ${data.length} bar · sumbu waktu WIB`;
  const mk = await api(`/api/marker?symbol=${encodeURIComponent(state.symbol)}`);
  const first = cd[0].time, lastT = cd[cd.length - 1].time;
  const markers = (mk.marker || []).filter(m => (state.acak || m.account !== "acak") && m.time + OFF >= first - TF_SEC[state.tf]).map(m => {
    const t = Math.min(snap(m.time + OFF), lastT); const acak = m.account === "acak";
    const base = { time: t, text: m.text };
    if (m.jenis === "ENTRY") return { ...base, position: m.side === "LONG" ? "belowBar" : "aboveBar", shape: m.side === "LONG" ? "arrowUp" : "arrowDown", color: acak ? "#7a8aa0" : (m.side === "LONG" ? "#26a69a" : "#ef5350") };
    if (m.jenis === "TP") return { ...base, position: "aboveBar", shape: "circle", color: acak ? "#5f8f7a" : "#7be3b2" };
    if (m.jenis === "LIQUIDATION") return { ...base, position: "belowBar", shape: "square", color: acak ? "#9a5a5a" : "#ff5c5c" };
    if (m.jenis === "EXPIRED" || m.jenis === "CANCELED") return { ...base, position: "inBar", shape: "circle", color: "#f0b429", size: 0.6 };
    return { ...base, position: "aboveBar", shape: "circle", color: "#9aa4b8" };
  }).sort((a, b) => a.time - b.time);
  candles.setMarkers(markers);
  lines.forEach(l => candles.removePriceLine(l)); lines = [];
  (mk.garis || []).filter(g => state.acak || g.account !== "acak").forEach(g => {
    const color = { entry: "#4f8cff", tp: "#7be3b2", sl: "#9aa4b8", liq: "#ff5c5c", order: "#f0b429" }[g.jenis] || "#888";
    lines.push(candles.createPriceLine({ price: g.price, color, lineWidth: 1, lineStyle: g.jenis === "order" ? 2 : 0, axisLabelVisible: true, title: g.label }));
  });
}
async function loadSymbols() {
  const s = await api("/api/simbol");
  const sel = $("#sel-symbol"); const cur = state.symbol;
  const groups = [["aktif (order/posisi)", s.aktif], ["pernah ditradingkan", (s.riwayat || []).filter(x => !s.aktif.includes(x))], ["top volume 24 jam", (s.top || []).filter(x => !s.aktif.includes(x) && !(s.riwayat || []).includes(x))]];
  sel.innerHTML = groups.filter(g => g[1].length).map(g => `<optgroup label="${g[0]}">${g[1].map(x => `<option value="${x}">${x}</option>`).join("")}</optgroup>`).join("");
  state.symbol = cur && [...sel.options].some(o => o.value === cur) ? cur : (s.aktif[0] || s.riwayat?.[0] || s.top?.[0] || "BTCUSDT");
  sel.value = state.symbol;
}
$("#sel-symbol").onchange = (e) => { state.symbol = e.target.value; state.lastBar = null; loadChart(true); };
document.querySelectorAll("#tf-group button").forEach(b => b.onclick = () => { document.querySelectorAll("#tf-group button").forEach(x => x.classList.toggle("active", x === b)); state.tf = b.dataset.tf; state.lastBar = null; loadChart(true); });
$("#chk-acak").onchange = (e) => { state.acak = e.target.checked; loadChart(true); loadRiwayat(); };

// ---------------------------------------------------------------- ringkasan
function budgetCard(b) {
  const t = b.tiket, a = b.acak, s = b.swing;
  if (!t || t.status) return '<div class="muted">tidak tersedia (paper.sqlite belum ada)</div>';
  const bar = (x) => `<div class="bar"><i style="width:${Math.min(100, (x.used + x.reserved) / x.budget * 100).toFixed(0)}%"></i></div>`;
  return `<div class="row"><span>tiket</span><span>terpakai ${usd(t.used)} · reservasi ${usd(t.reserved)} · <b>sisa ${usd(t.remaining)}</b></span></div>${bar(t)}` +
    `<div class="row"><span>swing</span><span>${s.open} posisi · ${s.pending} order (maks ${s.max_open}, $${s.margin_per_trade}/trade)</span></div>` +
    `<div class="row acak"><span>acak (bayangan)</span><span>terpakai ${usd(a.used)} · sisa ${usd(a.remaining)}</span></div>`;
}
function posisiCard(ps) {
  const rows = ps.filter(p => state.acak || p.account !== "acak");
  if (!rows.length) return '<div class="muted">tidak ada posisi terbuka</div>';
  return rows.map(p => `<div class="row ${p.account === "acak" ? "acak" : ""}"><span>#${p.id} <b>${p.symbol}</b> ${p.side} ${p.leverage}x <span class="muted">${p.account} ${p.plan_id || ""}</span><br>` +
    `<span class="muted">entry ${px(p.entry_price)} · liq ${px(p.liq_price)} (${fmt(p.liq_dist_pct, 2)}%) · TP ${px(p.tp_price)}${p.sl_price ? " · SL " + px(p.sl_price) : ""}</span></span>` +
    `<span class="${(p.unrealized || 0) >= 0 ? "pos" : "neg"}">${usd(p.unrealized, true)}<br><span class="muted">mark ${px(p.mark)}</span></span></div>`).join("");
}
function orderCard(os) {
  const rows = os.filter(o => state.acak || o.account !== "acak");
  if (!rows.length) return '<div class="muted">tidak ada order menunggu</div>';
  return rows.map(o => `<div class="row ${o.account === "acak" ? "acak" : ""}"><span>#${o.id} <b>${o.symbol}</b> ${o.side} ${o.type} ${o.leverage}x <span class="muted">${o.account} ${o.plan_id || ""} · ${o.status}</span></span>` +
    `<span>${o.price ? px(o.price) : "MARKET"}<br><span class="muted">TP ${px(o.tp_price)} · exp ${jam(o.expire_ts)}</span></span></div>`).join("");
}
function cronCard(cs) {
  if (!cs.length) return '<div class="muted">executions.db Hermes tidak terbaca</div>';
  return cs.slice(0, 8).map(c => `<div class="row"><span>${c.name}</span><span class="muted">${c.status} · ${c.delivery_outcome || "—"} · ${(c.started_at || "").slice(11, 19)}</span></div>`).join("");
}
async function loadRingkasan() {
  const r = await api("/api/ringkasan");
  if (r.error) { $("#st-jam").textContent = r.error; return; }
  $("#st-jam").textContent = r.sekarang_wib;
  const c = r.collector; const sc = $("#st-collector");
  sc.textContent = `collector ${c.status}${c.umur_s !== null ? " · " + c.umur_s + " s" : ""}`; sc.className = "pill " + (c.status === "OK" ? "ok" : "basi");
  const pm = r.pemindai, run = pm.run_terakhir; const sp = $("#st-pemindai");
  sp.textContent = run ? `pemindai ${jam(run.ts)} · wake ${pm.wake_hari_ini}/12 · ${run.wake ? "BANGUN: " : ""}${(run.alasan || "").slice(0, 60)}` : "pemindai belum pernah jalan";
  sp.className = "pill " + (run && run.wake ? "warn" : "");
  const b = r.biaya; const sb = $("#st-biaya");
  sb.textContent = b.status ? "API tidak tersedia" : `API hari ini $${b.cost_hari.toFixed(2)}/${b.cap_hari} (${b.calls_hari}) · bulan $${b.cost_bulan.toFixed(2)}/${b.cap_bulan}`;
  sb.className = "pill " + (b.cost_hari > 7 ? "warn" : "");
  $("#st-kill").classList.toggle("hidden", !r.kill_switch);
  $("#card-budget .body").innerHTML = budgetCard(r.budget);
  $("#card-posisi .body").innerHTML = posisiCard(r.posisi);
  $("#card-order .body").innerHTML = orderCard(r.order);
  $("#card-cron .body").innerHTML = cronCard(r.cron);
}

// ---------------------------------------------------------------- riwayat
let eqChart;
function table(el, cols, rows, onClick) {
  el.innerHTML = `<thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead><tbody>${rows.map((r, i) => `<tr data-i="${i}" class="${r.account === "acak" ? "acak" : ""}">${cols.map(c => `<td>${c[1](r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  if (!rows.length) el.innerHTML += `<tbody><tr><td colspan="${cols.length}" class="muted">tidak ada data</td></tr></tbody>`;
  if (onClick) el.querySelectorAll("tbody tr[data-i]").forEach(tr => tr.onclick = () => onClick(rows[tr.dataset.i]));
}
function gotoChart(symbol) { state.symbol = symbol; state.lastBar = null; $("#sel-symbol").value = symbol; document.querySelector('.tabs button[data-tab="chart"]').click(); loadChart(true); }
async function loadRiwayat() {
  const q = new URLSearchParams(); if ($("#f-akun").value) q.set("akun", $("#f-akun").value); if ($("#f-hari").value) q.set("hari", $("#f-hari").value); if ($("#f-symbol").value) q.set("symbol", $("#f-symbol").value.trim().toUpperCase());
  const r = await api("/api/riwayat?" + q.toString());
  const pos = (r.posisi || []).filter(p => state.acak || $("#f-akun").value === "acak" || p.account !== "acak");
  table($("#tbl-posisi"), [["id", p => p.id], ["akun", p => p.account], ["pair", p => p.symbol], ["sisi", p => p.side], ["lev", p => p.leverage + "x"], ["entry", p => px(p.entry_price)], ["keluar", p => px(p.exit_price)],
    ["alasan", p => p.close_reason], ["net", p => `<span class="${(p.net_result || 0) >= 0 ? "pos" : "neg"}">${usd(p.net_result, true)}</span>`], ["fee", p => usd(p.fees_total)], ["plan", p => p.plan_id || ""],
    ["buka", p => wib(p.opened_ts)], ["tutup", p => wib(p.closed_ts)], ["ambigu", p => p.ambiguous ? "ya → " + p.alt_outcome : ""]], pos, p => gotoChart(p.symbol));
  const ords = (r.order || []).filter(o => state.acak || $("#f-akun").value === "acak" || o.account !== "acak");
  table($("#tbl-order"), [["id", o => o.id], ["akun", o => o.account], ["pair", o => o.symbol], ["sisi", o => o.side], ["tipe", o => o.type], ["harga", o => o.price ? px(o.price) : "MARKET"], ["lev", o => o.leverage + "x"],
    ["status", o => o.status], ["kode", o => o.reject_code || ""], ["alasan", o => (o.reject_reason || "").slice(0, 60)], ["plan", o => o.plan_id || ""], ["oleh", o => o.created_by], ["dibuat", o => wib(o.created_ts)]], ords, o => gotoChart(o.symbol));
  table($("#tbl-harian"), [["hari", h => h.day_wib], ["akun", h => h.account], ["order", h => h.orders_n], ["terisi", h => h.filled_n], ["tidak terisi", h => h.tidak_terisi_n], ["TP", h => h.tp_n], ["HANGUS", h => h.hangus_n],
    ["lain", h => h.other_close_n], ["margin", h => usd(h.margin_used)], ["fee", h => usd(h.fees)], ["net", h => `<span class="${(h.pnl_net || 0) >= 0 ? "pos" : "neg"}">${usd(h.pnl_net, true)}</span>`], ["ambigu", h => h.ambiguous_n]], r.harian || []);
  const eq = await api("/api/ekuitas");
  if (!hasLWC) return;
  if (!eqChart) {
    eqChart = LightweightCharts.createChart($("#chart-ekuitas"), { layout: { background: { color: "#121722" }, textColor: "#d6dbe5" }, grid: { vertLines: { color: "#1a2130" }, horzLines: { color: "#1a2130" } }, timeScale: { timeVisible: true, borderColor: "#1f2736" }, rightPriceScale: { borderColor: "#1f2736" }, localization: { locale: "id-ID", timeFormatter: wibT } });
    eqChart.series = { tiket: eqChart.addLineSeries({ color: "#4f8cff", lineWidth: 2, title: "tiket" }), swing: eqChart.addLineSeries({ color: "#f0b429", lineWidth: 2, title: "swing" }), acak: eqChart.addLineSeries({ color: "#7a8aa0", lineWidth: 1, lineStyle: 2, title: "acak" }) };
    new ResizeObserver(() => eqChart.applyOptions({ width: $("#chart-ekuitas").clientWidth })).observe($("#chart-ekuitas"));
  }
  for (const k of ["tiket", "swing", "acak"]) { const pts = (eq[k] || []).map(p => ({ time: p.time + OFF, value: p.value })); const dedup = []; pts.forEach(p => { if (dedup.length && dedup[dedup.length - 1].time === p.time) dedup[dedup.length - 1] = p; else dedup.push(p); }); eqChart.series[k].setData(dedup); }
  eqChart.timeScale().fitContent();
}
$("#f-apply").onclick = loadRiwayat;

// ---------------------------------------------------------------- statistik / kandidat / psikologi / jurnal
async function loadStatistik() {
  const s = await api("/api/statistik");
  const L = s.lulus || {};
  $("#statistik-md").textContent = s.status ? "tidak tersedia" : `Kriteria §19.7 (dihitung ${s.dihitung})\n` + Object.entries(L).map(([k, v]) => `  ${k.padEnd(20)} ${v}`).join("\n") +
    `\n\nPer akun:\n` + Object.values(s.akun || {}).map(a => `  ${a.account.padEnd(6)} posisi ${String(a.n_posisi).padStart(3)} · expectancy ${typeof a.expectancy === "number" ? a.expectancy.toFixed(4) : a.expectancy} · win ${typeof a.win_rate === "number" ? (a.win_rate * 100).toFixed(0) + "%" : a.win_rate} · TP ${a.tp_n} HANGUS ${a.hangus_n} STOP ${a.stop_n} EOD ${a.eod_n} tidak terisi ${a.tidak_terisi_n} · total ${usd(a.total_net, true)}`).join("\n") +
    `\n\nTiket vs acak: ${JSON.stringify(s.tiket_vs_acak, null, 1)}\nKepatuhan: ${JSON.stringify(s.kepatuhan, null, 1)}`;
  $("#statistik-json").textContent = "";
}
async function loadKandidat() {
  const k = await api("/api/kandidat");
  table($("#tbl-kandidat"), [["K", c => "K" + c.id], ["pair", c => c.symbol], ["arah", c => c.arah_dugaan], ["skor", c => c.score], ["mark", c => px(c.mark)], ["level", c => px(c.level)], ["sentuhan", c => c.sentuhan], ["jarak×ATR5m", c => fmt(c.jarak_atr5m, 2)],
    ["flags", c => (c.flags || []).join(", ")], ["lev layak", c => (c.lev_layak || []).map(l => l.leverage + "x").join("/")], ["run", c => wib(c.run_ts)]], k.kandidat || [], c => gotoChart(c.symbol));
  table($("#tbl-runs"), [["waktu", r => wib(r.ts)], ["bangun", r => r.wake ? "YA" : "—"], ["alasan", r => r.alasan], ["simbol", r => r.n_symbols], ["ms", r => r.duration_ms]], k.runs || []);
}
document.querySelectorAll("[data-ps]").forEach(b => b.onclick = () => { document.querySelectorAll("[data-ps]").forEach(x => x.classList.toggle("active", x === b)); state.ps = b.dataset.ps; loadPsikologi(); });
async function loadPsikologi() {
  const p = await api(`/api/psikologi?symbol=${state.ps}`);
  if (p.status === "tidak tersedia") { $("#ps-info").textContent = "tidak tersedia — " + p.alasan; $("#tbl-panel").innerHTML = ""; $("#ps-divergensi .body").textContent = "—"; return; }
  $("#ps-info").textContent = `${p.waktu} WIB · umur ${p.umur_s} s · ${p.status} · zona ${p.mode_zona} · takut ${p.takut_ekstrem} / serakah ${p.serakah_ekstrem} / tidak tersedia ${p.tidak_tersedia} (tanpa skor gabungan)`;
  const f = (ind, v) => v === null ? "tidak tersedia" : ["funding", "premium_coinbase", "premium_idr"].includes(ind) ? (v * 100).toFixed(4) + "%" : ["oi_24h", "harga_24h", "stablecoin_7d"].includes(ind) ? (v * 100).toFixed(2) + "%" : ind.startsWith("liq") ? v : ind === "fng" ? v.toFixed(0) : v.toFixed(3);
  table($("#tbl-panel"), [["indikator", r => r.label], ["nilai", r => f(r.indikator, r.nilai)], ["Δ 24j", r => p.perubahan_24j[r.indikator] !== undefined ? f(r.indikator, p.perubahan_24j[r.indikator]) : "—"], ["zona", r => `<span class="tag ${r.zona.replace(" ", "_")}">${r.zona}</span>`], ["sumber", r => r.sumber], ["catatan", r => r.catatan]], p.indikator || []);
  $("#ps-divergensi .body").innerHTML = (p.divergensi || []).length ? p.divergensi.map(d => `<div class="row">⚠ ${d}</div>`).join("") : '<span class="muted">tidak ada divergensi</span>';
}
async function loadJurnal() {
  const q = new URLSearchParams({ jenis: $("#j-jenis").value }); if ($("#j-hari").value) q.set("hari", $("#j-hari").value);
  const t = await api("/api/teks?" + q.toString());
  $("#jurnal-md").textContent = t.isi || `(kosong${t.path ? ": " + t.path : ""})`;
}
$("#j-jenis").onchange = loadJurnal; $("#j-hari").onchange = loadJurnal;

// ---------------------------------------------------------------- boot & polling
(async () => {
  initChart();
  await loadSymbols();
  await loadChart(true);
  await loadRingkasan();
  setInterval(loadRingkasan, 5000);
  setInterval(() => loadChart(false), 15000);
  setInterval(loadSymbols, 60000);
})();
