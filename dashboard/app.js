/* Dashboard paper trading — vanilla JS, Lightweight Charts v4 (CDN). Semua data dari /api/* (baca saja).
   Prinsip: bahasa manusia dulu, angka kedua; setiap angka punya arti yang bisa dibaca orang awam. */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const usd = (x, sign = false) => (x === null || x === undefined || Number.isNaN(Number(x))) ? "—" : (sign && Number(x) >= 0 ? "+" : (Number(x) < 0 ? "−" : "")) + "$" + Math.abs(Number(x)).toFixed(Math.abs(Number(x)) < 1 ? 4 : 2);
const px = (x) => (x === null || x === undefined) ? "—" : Number(x).toPrecision(6).replace(/\.?0+$/, "");
const pct = (x, d = 2) => (x === null || x === undefined) ? "—" : (Number(x) >= 0 ? "+" : "") + (Number(x) * 100).toFixed(d) + "%";
const wib = (ms) => ms ? new Date(Number(ms)).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const jam = (ms) => ms ? new Date(Number(ms)).toLocaleTimeString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, hour: "2-digit", minute: "2-digit" }) : "—";
const TF_SEC = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400 };
const OFF = 7 * 3600; // sumbu waktu Lightweight Charts memakai UTC → geser ke WIB
const wibT = (t) => new Date((t - OFF) * 1000).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const state = { symbol: null, tf: "5m", acak: false, lastBar: null, ps: "BTCUSDT", eq: "tiket", eqData: null };
const api = async (p) => { const r = await fetch(p, { cache: "no-store" }); return r.json(); };
const hasLWC = typeof LightweightCharts !== "undefined";
const AKUN = { tiket: "Tiket ($1/hari)", swing: "Swing", acak: "Pembanding acak" };
const ALASAN = { TP: ["Target tercapai", "pos"], HANGUS: ["Modal hangus (likuidasi)", "neg"], FUNDING_LIQ: ["Hangus karena biaya funding", "neg"], STOP: ["Kena stop loss", "neg"], EOD: ["Ditutup jam 23:50", ""], MANUAL: ["Ditutup manual", ""], DELISTED: ["Koin dihapus", ""] };
const STATUS_ORDER = { EXPIRED: "harga tidak pernah tersentuh", CANCELED: "dibatalkan", REJECTED: "ditolak mesin", NEW: "menunggu aktif", ACTIVE: "aktif, menunggu harga" };
const KODE = { BUDGET_TIKET: "jatah $1 hari ini tidak cukup", TIKET_EOD: "sudah lewat jam tutup", LIMIT_CROSSES: "harga sudah lewat level", LEVERAGE_CAP: "leverage melebihi batas Binance", QTY_STEP: "jumlah tidak sesuai kelipatan", MIN_NOTIONAL: "nilai order terlalu kecil", RR_TOO_LOW: "untung:rugi di bawah 2,5", BAD_TP: "target di arah yang salah", BUDGET_ACAK: "jatah pembanding acak habis", ACAK_EOD: "pembanding: lewat jam tutup" };
const ARTI = {
  fng: "Indeks ketakutan/keserakahan ritel (0 takut – 100 serakah)", funding: "Biaya yang dibayar posisi long ke short tiap 8 jam; positif = long ramai",
  oi_24h: "Perubahan jumlah posisi terbuka 24 jam; naik = uang baru masuk", harga_24h: "Perubahan harga 24 jam", ls_akun: "Rasio akun long : short (ritel); > 1 = lebih banyak yang long",
  ls_top: "Rasio posisi long : short trader besar", taker: "Agresivitas pembeli vs penjual (> 1 = pembeli lebih agresif)", liq_long_24h: "Jumlah posisi long yang dipaksa tutup 24 jam",
  liq_short_24h: "Jumlah posisi short yang dipaksa tutup 24 jam", premium_coinbase: "Harga Coinbase (AS) vs Binance; positif = permintaan spot AS kuat",
  premium_idr: "Harga Indodax vs Binance; positif = ritel Indonesia antusias", stablecoin_7d: "Perubahan suplai stablecoin 7 hari; naik = dana siap masuk",
};

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
  ({ riwayat: loadRiwayat, statistik: loadStatistik, kandidat: loadKandidat, psikologi: loadPsikologi, jurnal: loadJurnal }[b.dataset.tab] || (() => chart && chart.timeScale().fitContent()))();
});

// ---------------------------------------------------------------- chart
let chart, candles, volume, lines = [];
const baseOpts = { layout: { background: { color: "#1a2029" }, textColor: "#c9d1dc", fontFamily: "Inter, system-ui, sans-serif" }, grid: { vertLines: { color: "#232b36" }, horzLines: { color: "#232b36" } },
  timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#2a3340" }, rightPriceScale: { borderColor: "#2a3340" }, crosshair: { mode: 0 }, localization: { locale: "id-ID", timeFormatter: wibT } };
function initChart() {
  if (!hasLWC) { $("#chart").innerHTML = '<div class="empty">Pustaka grafik tidak termuat (butuh internet sekali). Tabel dan angka tetap berfungsi.</div>'; return; }
  chart = LightweightCharts.createChart($("#chart"), baseOpts);
  candles = chart.addCandlestickSeries({ upColor: "#2ec27e", downColor: "#f05a5a", borderVisible: false, wickUpColor: "#2ec27e", wickDownColor: "#f05a5a" });
  volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
  chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
  new ResizeObserver(() => chart.applyOptions({ width: $("#chart").clientWidth, height: $("#chart").clientHeight })).observe($("#chart"));
}
function snap(t) { const s = TF_SEC[state.tf]; return Math.floor(t / s) * s; }
function markerText(m) {
  if (m.jenis === "ENTRY") return `${m.side === "LONG" ? "Beli (LONG)" : "Jual (SHORT)"} di ${px(m.price)}`;
  if (m.jenis === "TP") return `Target tercapai di ${px(m.price)}`;
  if (m.jenis === "LIQUIDATION") return `Modal hangus di ${px(m.price)}`;
  if (m.jenis === "EXPIRED") return `Order ${px(m.price)} tidak pernah tersentuh`;
  if (m.jenis === "CANCELED") return `Order ${px(m.price)} dibatalkan`;
  return `Ditutup di ${px(m.price)} (${m.jenis === "EOD" ? "jam 23:50" : m.jenis === "SL" ? "stop loss" : m.jenis.toLowerCase()})`;
}
async function loadChart(full = true) {
  if (!state.symbol) return;
  const data = await api(`/api/candles?symbol=${encodeURIComponent(state.symbol)}&tf=${state.tf}&n=600`);
  const mk = await api(`/api/marker?symbol=${encodeURIComponent(state.symbol)}`);
  const evs = (mk.marker || []).filter(m => state.acak || m.account !== "acak").slice().reverse();
  $("#kejadian").innerHTML = evs.length ? evs.slice(0, 12).map(m => `<div class="ev ${m.account === "acak" ? "acak" : ""}"><span class="when">${jam(m.time * 1000)}</span><span>${esc(markerText(m))} <span class="dim">· ${esc(m.text)}</span></span><span class="dim">${AKUN[m.account] || m.account}</span></div>`).join("") : '<div class="empty">Belum ada trade pada koin ini.</div>';
  if (!chart) return;
  if (!Array.isArray(data) || !data.length) { $("#chart-info").textContent = `${state.symbol}: belum ada data harga (robot hanya menyimpan 30 koin teramai + koin yang sedang ditradingkan).`; candles.setData([]); volume.setData([]); return; }
  const cd = data.map(b => ({ time: b.time + OFF, open: b.open, high: b.high, low: b.low, close: b.close }));
  const vd = data.map(b => ({ time: b.time + OFF, value: b.volume, color: b.close >= b.open ? "rgba(46,194,126,.3)" : "rgba(240,90,90,.3)" }));
  if (full || !state.lastBar) { candles.setData(cd); volume.setData(vd); chart.timeScale().fitContent(); }
  else { const last = cd[cd.length - 1]; if (cd.length > 1 && cd[cd.length - 2].time > state.lastBar) { candles.setData(cd); volume.setData(vd); } else if (last.time >= state.lastBar) { candles.update(last); volume.update(vd[vd.length - 1]); } }
  state.lastBar = cd[cd.length - 1].time;
  const last = data[data.length - 1];
  $("#chart-info").textContent = `${state.symbol} · tiap lilin ${state.tf} · harga terakhir ${px(last.close)} · lilin terakhir ${wib(last.time * 1000)} WIB · ${data.length} lilin · diperbarui otomatis`;
  const first = cd[0].time, lastT = cd[cd.length - 1].time;
  const markers = (mk.marker || []).filter(m => (state.acak || m.account !== "acak") && m.time + OFF >= first - TF_SEC[state.tf]).map(m => {
    const t = Math.min(snap(m.time + OFF), lastT); const acak = m.account === "acak"; const base = { time: t, text: m.text };
    if (m.jenis === "ENTRY") return { ...base, position: m.side === "LONG" ? "belowBar" : "aboveBar", shape: m.side === "LONG" ? "arrowUp" : "arrowDown", color: acak ? "#7a8aa0" : (m.side === "LONG" ? "#2ec27e" : "#f05a5a"), size: 1.4 };
    if (m.jenis === "TP") return { ...base, position: "aboveBar", shape: "circle", color: acak ? "#5f8f7a" : "#6fe3a5", size: 1.2 };
    if (m.jenis === "LIQUIDATION") return { ...base, position: "belowBar", shape: "square", color: acak ? "#9a5a5a" : "#ff6b6b", size: 1.2 };
    if (m.jenis === "EXPIRED" || m.jenis === "CANCELED") return { ...base, position: "inBar", shape: "circle", color: "#f5b53f", size: 0.6 };
    return { ...base, position: "aboveBar", shape: "circle", color: "#9aa4b4" };
  }).sort((a, b) => a.time - b.time);
  candles.setMarkers(markers);
  lines.forEach(l => candles.removePriceLine(l)); lines = [];
  const LABEL = { entry: "masuk", tp: "target", sl: "stop", liq: "hangus", order: "order menunggu" };
  (mk.garis || []).filter(g => state.acak || g.account !== "acak").forEach(g => {
    const color = { entry: "#5b9cff", tp: "#6fe3a5", sl: "#9aa4b4", liq: "#ff6b6b", order: "#f5b53f" }[g.jenis] || "#888";
    lines.push(candles.createPriceLine({ price: g.price, color, lineWidth: 1, lineStyle: g.jenis === "order" ? 2 : 0, axisLabelVisible: true, title: `${LABEL[g.jenis]} ${g.label.replace(/^(entry|liq|TP|SL|order) /, "")}` }));
  });
}
async function loadSymbols() {
  const s = await api("/api/simbol"); const sel = $("#sel-symbol"); const cur = state.symbol;
  const groups = [["Sedang ditradingkan", s.aktif], ["Pernah ditradingkan", (s.riwayat || []).filter(x => !s.aktif.includes(x))], ["30 koin teramai hari ini", (s.top || []).filter(x => !s.aktif.includes(x) && !(s.riwayat || []).includes(x))]];
  sel.innerHTML = groups.filter(g => g[1].length).map(g => `<optgroup label="${g[0]}">${g[1].map(x => `<option value="${x}">${x.replace("USDT", "")} / USDT</option>`).join("")}</optgroup>`).join("");
  state.symbol = cur && [...sel.options].some(o => o.value === cur) ? cur : (s.aktif[0] || s.riwayat?.[0] || s.top?.[0] || "BTCUSDT");
  sel.value = state.symbol;
}
$("#sel-symbol").onchange = (e) => { state.symbol = e.target.value; state.lastBar = null; loadChart(true); };
document.querySelectorAll("#tf-group button").forEach(b => b.onclick = () => { document.querySelectorAll("#tf-group button").forEach(x => x.classList.toggle("active", x === b)); state.tf = b.dataset.tf; state.lastBar = null; loadChart(true); });
$("#chk-acak").onchange = (e) => { state.acak = e.target.checked; loadChart(true); loadRingkasan(); };

// ---------------------------------------------------------------- ringkasan (KPI + chips + panel kanan)
function chip(label, cls, title) { return `<span class="chip ${cls}" title="${esc(title || "")}"><span class="dot"></span>${esc(label)}</span>`; }
function kpi(k, v, d, barPct, barCls) { return `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div>${barPct !== undefined ? `<div class="bar"><i class="${barCls || ""}" style="width:${Math.max(0, Math.min(100, barPct)).toFixed(0)}%"></i></div>` : ""}</div>`; }
async function loadRingkasan() {
  const r = await api("/api/ringkasan");
  if (r.error) { $("#jam").textContent = "server error"; return; }
  $("#jam").textContent = r.sekarang_wib.slice(11, 16);
  const c = r.collector, pm = r.pemindai, run = pm.run_terakhir, b = r.biaya;
  const chips = [];
  chips.push(chip(c.status === "OK" ? `Data harga segar (${c.umur_s} dtk)` : c.status === "BASI" ? `Data harga basi (${Math.round(c.umur_s / 60)} mnt)` : "Belum ada data harga", c.status === "OK" ? "ok" : "bad", "Robot pengambil harga (collector) harus memperbarui tiap menit"));
  chips.push(chip(run ? (run.wake ? `Radar: AI dibangunkan ${jam(run.ts)}` : `Radar ${jam(run.ts)}: ${run.alasan.split(" (")[0].slice(0, 48)}`) : "Radar belum jalan", run ? (run.wake ? "warn" : "ok") : "bad", run ? `Pemindaian terakhir ${wib(run.ts)} WIB. AI dibangunkan ${pm.wake_hari_ini}× hari ini (maks 12).` : ""));
  chips.push(chip(b.status ? "Biaya AI: tidak tersedia" : `Biaya AI hari ini $${b.cost_hari.toFixed(2)} dari $${b.cap_hari}`, b.status ? "bad" : (b.cost_hari > 7 ? "warn" : "ok"), b.status ? "" : `${b.calls_hari} panggilan hari ini; bulan ini $${b.cost_bulan.toFixed(2)} dari $${b.cap_bulan}`));
  if (r.kill_switch) chips.push(chip("AI DIMATIKAN (kill switch)", "bad", "Berkas data/STOP_AGENT ada: semua panggilan AI ditolak"));
  $("#health").innerHTML = chips.join("");
  const t = r.budget.tiket, a = r.budget.acak, s = r.budget.swing;
  const pos = r.posisi.filter(p => state.acak || p.account !== "acak");
  const unreal = pos.reduce((x, p) => x + (p.unrealized || 0), 0);
  const eq = state.eqData;
  $("#kpis").innerHTML = t.status ? '<div class="kpi"><div class="k">Belum ada data</div><div class="d">Mesin paper belum pernah jalan.</div></div>' :
    kpi("Jatah modal hari ini", usd(t.remaining), `tersisa dari $${t.budget.toFixed(2)} · terpakai ${usd(t.used)} · ditahan untuk order ${usd(t.reserved)}`, (t.used + t.reserved) / t.budget * 100, t.remaining < 0.1 ? "warn" : "") +
    kpi("Posisi berjalan", `<span class="${unreal >= 0 ? "pos" : "neg"}">${usd(unreal, true)}</span>`, pos.length ? `${pos.length} posisi terbuka · untung/rugi kalau ditutup sekarang` : "tidak ada posisi terbuka") +
    kpi("Hasil tiket sejauh ini", eq ? `<span class="${eq.tiket.ekuitas_akhir >= 0 ? "pos" : "neg"}">${usd(eq.tiket.ekuitas_akhir, true)}</span>` : "—", eq ? `${eq.tiket.n} trade selesai · pembanding acak ${usd(eq.acak.ekuitas_akhir, true)} (${eq.acak.n} trade)` : "memuat…") +
    kpi("Penurunan dari puncak", eq ? `<span class="${eq.tiket.drawdown_sekarang < 0 ? "neg" : ""}">${usd(eq.tiket.drawdown_sekarang)}</span>` : "—", eq ? `terdalam ${usd(eq.tiket.drawdown_maks)} · akun tiket` : "") +
    kpi("Swing", `${s.open} / ${s.max_open}`, `${s.open} posisi, ${s.pending} order menunggu · $${s.margin_per_trade} per trade`);
  $("#p-budget .body").innerHTML = `<div class="item"><div class="l"><div class="t">Tiket (utama)</div><div class="s">$1 per hari, termasuk fee</div></div><div class="r num"><b>${usd(t.remaining)}</b> sisa<br><span class="s">terpakai ${usd(t.used)}</span></div></div>` +
    `<div class="item"><div class="l"><div class="t">Swing</div><div class="s">maks ${s.max_open} posisi, $${s.margin_per_trade}/trade</div></div><div class="r num">${s.open} posisi<br><span class="s">${s.pending} order</span></div></div>` +
    `<div class="item acak"><div class="l"><div class="t">Pembanding acak</div><div class="s">kembaran arah acak, bukan keputusan AI</div></div><div class="r num">${usd(a.remaining)} sisa</div></div>`;
  $("#p-posisi .body").innerHTML = pos.length ? pos.map(p => `<div class="item ${p.account === "acak" ? "acak" : ""}"><div class="l"><div class="t">${p.symbol.replace("USDT", "")} ${p.side === "LONG" ? "beli" : "jual"} ${p.leverage}x <span class="dim">· ${AKUN[p.account]}${p.plan_id ? " · " + p.plan_id : ""}</span></div>` +
    `<div class="s">masuk ${px(p.entry_price)} · target ${px(p.tp_price)} · hangus di ${px(p.liq_price)} (${Math.abs(p.liq_dist_pct || 0).toFixed(2)}% lagi)${p.sl_price ? " · stop " + px(p.sl_price) : ""}</div></div>` +
    `<div class="r num"><b class="${(p.unrealized || 0) >= 0 ? "pos" : "neg"}">${usd(p.unrealized, true)}</b><br><span class="s">harga ${px(p.mark)}</span></div></div>`).join("") : '<div class="empty">Tidak ada posisi terbuka.</div>';
  const ords = r.order.filter(o => state.acak || o.account !== "acak");
  $("#p-order .body").innerHTML = ords.length ? ords.map(o => `<div class="item ${o.account === "acak" ? "acak" : ""}"><div class="l"><div class="t">${o.symbol.replace("USDT", "")} ${o.side === "LONG" ? "beli" : "jual"} ${o.leverage}x <span class="dim">· ${AKUN[o.account]}${o.plan_id ? " · " + o.plan_id : ""}</span></div><div class="s">${STATUS_ORDER[o.status] || o.status} · target ${px(o.tp_price)} · hangus otomatis ${jam(o.expire_ts)}</div></div><div class="r num">${o.price ? px(o.price) : "harga pasar"}</div></div>`).join("") : '<div class="empty">Tidak ada order menunggu.</div>';
  const cron = r.cron.slice(0, 6);
  const NAMA = { "notif-paper": "Notifikasi Telegram", "pemindai-tiket": "Radar koin", "evaluasi-harian": "Evaluasi malam", "uji-hipotesis": "Uji hipotesis", "psikologi": "Suasana pasar" };
  $("#p-mesin .body").innerHTML = `<div class="item"><div class="l"><div class="t">Pengambil harga</div><div class="s">tiap menit dari Binance</div></div><div class="r ${c.status === "OK" ? "pos" : "neg"}">${c.status === "OK" ? "jalan" : c.status}</div></div>` +
    `<div class="item"><div class="l"><div class="t">Radar koin</div><div class="s">tiap 5 menit, ${pm.wake_hari_ini ?? 0}× membangunkan AI hari ini</div></div><div class="r">${run ? jam(run.ts) : "—"}</div></div>` +
    (cron.length ? cron.map(x => `<div class="item"><div class="l"><div class="t">${NAMA[x.name] || x.name}</div><div class="s">${x.delivery_outcome === "delivered" ? "mengirim pesan" : x.delivery_outcome === "suppressed" ? "diam (tidak ada yang perlu dikirim)" : x.status}</div></div><div class="r dim">${(x.started_at || "").slice(11, 16)}</div></div>`).join("") : "");
}

// ---------------------------------------------------------------- riwayat & drawdown
let eqChart, ddChart, eqSeries, ddSeries;
function table(el, cols, rows, onClick) {
  el.innerHTML = `<thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((r, i) => `<tr data-i="${i}" class="${onClick ? "click" : ""} ${r.account === "acak" ? "acak" : ""}">${cols.map(c => `<td class="${c[2] || ""}">${c[1](r)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${cols.length}" class="empty">Belum ada data.</td></tr>`}</tbody>`;
  if (onClick) el.querySelectorAll("tbody tr[data-i]").forEach(tr => tr.onclick = () => onClick(rows[tr.dataset.i]));
}
function gotoChart(symbol) { state.symbol = symbol; state.lastBar = null; $("#sel-symbol").value = symbol; document.querySelector('.tabs button[data-tab="chart"]').click(); loadChart(true); }
function alasan(p) { const a = ALASAN[p.close_reason] || [p.close_reason, ""]; return `<span class="${a[1]}">${a[0]}</span>${p.ambiguous ? ' <span class="tag tt" title="Dalam satu lilin bisa terjadi dua hal; mesin memilih yang pesimis">ambigu</span>' : ""}`; }
async function loadEkuitas() {
  const eq = await api("/api/ekuitas"); state.eqData = eq;
  const d = eq[state.eq] || { ekuitas: [], drawdown: [], n: 0 };
  $("#dd-cards").innerHTML = [["Hasil kumulatif", usd(d.ekuitas_akhir, true), `${d.n} trade selesai`, d.ekuitas_akhir >= 0 ? "pos" : "neg"],
    ["Puncak tertinggi", usd(d.puncak), "titik terbaik yang pernah dicapai", ""],
    ["Penurunan sekarang", usd(d.drawdown_sekarang), "jarak dari puncak saat ini (0 = sedang di puncak)", d.drawdown_sekarang < 0 ? "neg" : ""],
    ["Penurunan terdalam", usd(d.drawdown_maks), d.drawdown_maks_ts ? `terjadi ${wib(d.drawdown_maks_ts)} WIB` : "belum pernah turun", d.drawdown_maks < 0 ? "neg" : ""]]
    .map(c => `<div class="card"><div class="k">${c[0]}</div><div class="v ${c[3]}">${c[1]}</div><div class="d">${c[2]}</div></div>`).join("");
  if (!hasLWC) return;
  if (!eqChart) {
    eqChart = LightweightCharts.createChart($("#chart-ekuitas"), { ...baseOpts, rightPriceScale: { ...baseOpts.rightPriceScale, scaleMargins: { top: 0.1, bottom: 0.1 } } });
    eqSeries = eqChart.addAreaSeries({ lineColor: "#5b9cff", topColor: "rgba(91,156,255,.35)", bottomColor: "rgba(91,156,255,.02)", lineWidth: 2, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } });
    ddChart = LightweightCharts.createChart($("#chart-drawdown"), { ...baseOpts, rightPriceScale: { ...baseOpts.rightPriceScale, scaleMargins: { top: 0.05, bottom: 0.05 } } });
    ddSeries = ddChart.addAreaSeries({ lineColor: "#f05a5a", topColor: "rgba(240,90,90,.02)", bottomColor: "rgba(240,90,90,.45)", invertFilledArea: true, lineWidth: 1, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } });
    eqChart.timeScale().subscribeVisibleLogicalRangeChange(r => r && ddChart.timeScale().setVisibleLogicalRange(r));
    new ResizeObserver(() => { eqChart.applyOptions({ width: $("#chart-ekuitas").clientWidth }); ddChart.applyOptions({ width: $("#chart-drawdown").clientWidth }); }).observe($("#chart-ekuitas"));
  }
  const dedup = (pts) => { const o = []; pts.forEach(p => { const q = { time: p.time + OFF, value: p.value }; if (o.length && o[o.length - 1].time === q.time) o[o.length - 1] = q; else o.push(q); }); return o; };
  eqSeries.setData(dedup(d.ekuitas)); ddSeries.setData(dedup(d.drawdown));
  eqChart.timeScale().fitContent(); ddChart.timeScale().fitContent();
}
document.querySelectorAll("#eq-group button").forEach(b => b.onclick = () => { document.querySelectorAll("#eq-group button").forEach(x => x.classList.toggle("active", x === b)); state.eq = b.dataset.acc; loadEkuitas(); });
async function loadRiwayat() {
  await loadEkuitas();
  const q = new URLSearchParams(); if ($("#f-akun").value) q.set("akun", $("#f-akun").value); if ($("#f-hari").value) q.set("hari", $("#f-hari").value); if ($("#f-symbol").value) q.set("symbol", $("#f-symbol").value.trim().toUpperCase());
  const r = await api("/api/riwayat?" + q.toString());
  const showAcak = state.acak || $("#f-akun").value === "acak";
  table($("#tbl-posisi"), [["Tutup", p => wib(p.closed_ts)], ["Akun", p => AKUN[p.account] || p.account], ["Koin", p => p.symbol.replace("USDT", "")], ["Arah", p => p.side === "LONG" ? "beli" : "jual"], ["Lev", p => p.leverage + "x", "num"],
    ["Masuk", p => px(p.entry_price), "num"], ["Keluar", p => px(p.exit_price), "num"], ["Kenapa ditutup", p => alasan(p)], ["Hasil bersih", p => `<b class="${(p.net_result || 0) >= 0 ? "pos" : "neg"}">${usd(p.net_result, true)}</b>`, "num"], ["Fee", p => usd(p.fees_total), "num"],
    ["Rencana", p => p.plan_id || ""], ["Lama", p => p.opened_ts && p.closed_ts ? Math.round((p.closed_ts - p.opened_ts) / 60000) + " mnt" : "—"]], (r.posisi || []).filter(p => showAcak || p.account !== "acak"), p => gotoChart(p.symbol));
  table($("#tbl-order"), [["Dibuat", o => wib(o.created_ts)], ["Akun", o => AKUN[o.account] || o.account], ["Koin", o => o.symbol.replace("USDT", "")], ["Arah", o => o.side === "LONG" ? "beli" : "jual"], ["Harga", o => o.price ? px(o.price) : "pasar", "num"], ["Lev", o => o.leverage + "x", "num"],
    ["Apa yang terjadi", o => `${STATUS_ORDER[o.status] || o.status}${o.reject_code ? " — " + (KODE[o.reject_code] || o.reject_code) : ""}`], ["Rencana", o => o.plan_id || ""], ["Oleh", o => o.created_by === "hermes" ? "AI" : o.created_by === "engine" ? "mesin" : o.created_by]], (r.order || []).filter(o => showAcak || o.account !== "acak"), o => gotoChart(o.symbol));
  table($("#tbl-harian"), [["Hari", h => h.day_wib], ["Akun", h => AKUN[h.account] || h.account], ["Order", h => h.orders_n, "num"], ["Terisi", h => h.filled_n, "num"], ["Tidak terisi", h => h.tidak_terisi_n, "num"], ["Target kena", h => h.tp_n, "num"], ["Hangus", h => h.hangus_n, "num"], ["Ditutup lain", h => h.other_close_n, "num"],
    ["Fee", h => usd(h.fees), "num"], ["Hasil bersih", h => `<b class="${(h.pnl_net || 0) >= 0 ? "pos" : "neg"}">${usd(h.pnl_net, true)}</b>`, "num"]], (r.harian || []).filter(h => showAcak || h.account !== "acak"));
}
$("#f-apply").onclick = loadRiwayat;

// ---------------------------------------------------------------- rapor
async function loadStatistik() {
  const s = await api("/api/statistik");
  if (s.status) { $("#lulus").innerHTML = '<div class="empty">Belum ada data.</div>'; return; }
  const L = s.lulus; const LABEL = { sampel: ["Cukup banyak trade", "≥ 200 tiket dan ≥ 30 swing, supaya bukan kebetulan"], expectancy_2_bulan: ["Untung rata-rata di 2 bulan berbeda", "bukan cuma satu bulan bagus"], vs_acak: ["Lebih baik dari lempar koin", "dibanding kembaran acaknya, secara statistik"], kepatuhan: ["Patuh aturan", "tidak ada tiket setelah 22:30 dan tidak menyiasati budget"], stabilitas: ["Tidak bergantung pada 1–2 trade besar", "tetap untung walau 5% trade terbaik dibuang"] };
  const tag = (v) => v === "lulus" ? '<span class="tag ok">lolos</span>' : v.startsWith("belum") ? '<span class="tag belum">belum</span>' : '<span class="tag tt">belum cukup data</span>';
  $("#lulus").innerHTML = Object.entries(LABEL).map(([k, [t, d]]) => `<div class="item"><div class="l"><div class="t">${t}</div><div class="s">${d} · <span class="dim">${esc(L[k])}</span></div></div><div class="r">${tag(L[k])}</div></div>`).join("");
  const f = (x, fn) => typeof x === "number" ? fn(x) : `<span class="dim" title="${esc(x)}">belum cukup data</span>`;
  table($("#tbl-akun"), [["Akun", a => AKUN[a.account] || a.account], ["Trade selesai", a => a.n_posisi, "num"], ["Rata-rata hasil/trade", a => f(a.expectancy, v => `<b class="${v >= 0 ? "pos" : "neg"}">${usd(v, true)}</b>`), "num"], ["Menang", a => f(a.win_rate, v => (v * 100).toFixed(0) + "%"), "num"],
    ["Target kena", a => a.tp_n, "num"], ["Hangus", a => a.hangus_n, "num"], ["Stop", a => a.stop_n, "num"], ["Tutup 23:50", a => a.eod_n, "num"], ["Tidak terisi", a => a.tidak_terisi_n, "num"], ["Total bersih", a => `<b class="${a.total_net >= 0 ? "pos" : "neg"}">${usd(a.total_net, true)}</b>`, "num"],
    ["Tanpa 5% terbaik", a => f(a.stabilitas, v => usd(v, true)), "num"]], Object.values(s.akun));
  const c = s.tiket_vs_acak, k = s.kepatuhan;
  $("#vs-acak").innerHTML = `<div class="item"><div class="l"><div class="t">Selisih rata-rata hasil (AI − acak)</div><div class="s">${c.p_permutasi !== null && c.p_permutasi !== undefined ? `peluang selisih ini kebetulan: ${(c.p_permutasi * 100).toFixed(1)}% (di bawah 5% = meyakinkan)` : "butuh ≥ 10 trade di kedua akun"}</div></div><div class="r num">${typeof c.selisih_mean === "number" ? usd(c.selisih_mean, true) : '<span class="dim">belum cukup data</span>'}</div></div>` +
    `<div class="item"><div class="l"><div class="t">Pasangan head-to-head</div><div class="s">${typeof c.sign_test === "object" ? `AI menang ${c.sign_test.tiket_lebih_baik} dari ${c.sign_test.berbeda} pasangan · peluang kebetulan ${(c.sign_test.p * 100).toFixed(1)}%` : "butuh ≥ 10 pasangan yang selesai"}</div></div><div class="r num">${c.n_pasangan} pasangan</div></div>` +
    `<div class="item"><div class="l"><div class="t">Pelanggaran aturan oleh AI</div><div class="s">order tiket setelah 22:30: ${k.order_lewat_2230_n} · percobaan yang ditolak mesin: budget ${k.budget_ditolak_n}, jam tutup ${k.eod_ditolak_n}</div></div><div class="r">${k.order_lewat_2230_n ? '<span class="tag belum">ada</span>' : '<span class="tag ok">bersih</span>'}</div></div>`;
}

// ---------------------------------------------------------------- radar
async function loadKandidat() {
  const k = await api("/api/kandidat");
  table($("#tbl-kandidat"), [["Kode", c => "K" + c.id], ["Koin", c => c.symbol.replace("USDT", "")], ["Dugaan arah", c => c.arah_dugaan === "LONG" ? "naik (beli)" : "turun (jual)"], ["Skor", c => c.score, "num"], ["Harga", c => px(c.mark), "num"], ["Level kunci", c => `${px(c.level)} (${c.sentuhan}× disentuh)`, "num"],
    ["Jarak ke level", c => (c.jarak_atr5m || 0).toFixed(2) + " ATR", "num"], ["Tanda", c => (c.flags || []).map(f => `<span class="tag tt">${f.toLowerCase().replace(/_/g, " ")}</span>`).join(" ")], ["Leverage layak", c => (c.lev_layak || []).map(l => l.leverage + "x").join(", ") || "—"], ["Kapan", c => wib(c.run_ts)]], k.kandidat || [], c => gotoChart(c.symbol));
  table($("#tbl-runs"), [["Kapan", r => wib(r.ts)], ["AI dibangunkan?", r => r.wake ? '<span class="tag ok">ya</span>' : '<span class="tag tt">tidak</span>'], ["Alasan", r => esc(r.alasan)], ["Koin dipindai", r => r.n_symbols, "num"]], k.runs || []);
}

// ---------------------------------------------------------------- suasana pasar
document.querySelectorAll("[data-ps]").forEach(b => b.onclick = () => { document.querySelectorAll("[data-ps]").forEach(x => x.classList.toggle("active", x === b)); state.ps = b.dataset.ps; loadPsikologi(); });
async function loadPsikologi() {
  const p = await api(`/api/psikologi?symbol=${state.ps}`);
  if (p.status === "tidak tersedia") { $("#ps-info").textContent = "Belum ada data — " + p.alasan; $("#tbl-panel").innerHTML = ""; $("#ps-divergensi").innerHTML = '<div class="empty">—</div>'; return; }
  $("#ps-info").textContent = `Diperbarui ${p.waktu} WIB (${p.status === "OK" ? "segar" : "sudah lama"}) · ${p.takut_ekstrem} indikator sangat takut, ${p.serakah_ekstrem} sangat serakah, ${p.tidak_tersedia} tidak tersedia · ambang: ${p.mode_zona === "awal" ? "standar awal" : "dari data sendiri"}`;
  $("#ps-bacaan").innerHTML = bacaanPasar(p);
  const ai = await api("/api/teks?jenis=harian"); let aiTxt = ai.isi || "";
  if (!aiTxt) { const kemarin = new Date(Date.now() - 86400000).toISOString().slice(0, 10); aiTxt = (await api(`/api/teks?jenis=harian&hari=${kemarin}`)).isi || ""; }
  $("#ps-ai").textContent = aiTxt ? aiTxt.replace(/^---[\s\S]*?---
*/, "").trim() : "Belum ada catatan harian dari AI (ditulis tiap 23:55 WIB).";
  const f = (ind, v) => v === null ? "—" : ["funding", "premium_coinbase", "premium_idr"].includes(ind) ? (v * 100).toFixed(4) + "%" : ["oi_24h", "harga_24h", "stablecoin_7d"].includes(ind) ? pct(v) : ind.startsWith("liq") ? v : ind === "fng" ? v.toFixed(0) : v.toFixed(2);
  const zona = (z) => z === "takut_ekstrem" ? '<span class="tag takut">sangat takut</span>' : z === "serakah_ekstrem" ? '<span class="tag serakah">sangat serakah</span>' : z === "netral" ? '<span class="tag">biasa</span>' : '<span class="tag na">tidak tersedia</span>';
  table($("#tbl-panel"), [["Indikator", r => `<b>${r.label}</b><div class="s dim">${ARTI[r.indikator] || ""}</div>`], ["Nilai", r => f(r.indikator, r.nilai), "num"], ["Vs 24 jam lalu", r => p.perubahan_24j[r.indikator] !== undefined ? f(r.indikator, p.perubahan_24j[r.indikator]) : "—", "num"], ["Suasana", r => zona(r.zona)], ["Catatan", r => `<span class="dim">${esc(r.catatan)}</span>`]], p.indikator || []);
  $("#ps-divergensi").innerHTML = (p.divergensi || []).length ? p.divergensi.map(d => `<div class="item"><div class="l"><div class="t">⚠ ${esc(d)}</div></div></div>`).join("") : '<div class="empty">Tidak ada yang bertentangan saat ini.</div>';
}

function bacaanPasar(p) {
  // Bacaan mekanis berbahasa manusia (bukan saran beli/jual): siapa dominan, siapa terjebak, apa yang perlu diwaspadai.
  const v = {}; (p.indikator || []).forEach(r => v[r.indikator] = r.nilai);
  const z = {}; (p.indikator || []).forEach(r => z[r.indikator] = r.zona);
  const L = [];
  if (v.fng != null) L.push(v.fng >= 75 ? "Ritel sedang serakah (Fear & Greed " + v.fng.toFixed(0) + "): euforia biasanya rawan koreksi." : v.fng <= 25 ? "Ritel sedang ketakutan (Fear & Greed " + v.fng.toFixed(0) + "): sering muncul di dekat dasar, tapi bisa lebih dalam dulu." : "Sentimen ritel biasa-biasa saja (Fear & Greed " + v.fng.toFixed(0) + ").");
  if (v.funding != null) L.push(v.funding > 0.0003 ? "Posisi long membayar funding mahal: yang long sudah ramai dan terjepit kalau harga turun." : v.funding < -0.0001 ? "Posisi short yang membayar: short sudah ramai, rawan squeeze ke atas." : "Funding netral: tidak ada sisi yang terlalu penuh.");
  if (v.oi_24h != null && v.harga_24h != null) {
    const oi = v.oi_24h, h = v.harga_24h;
    if (oi > 0.02 && h > 0.01) L.push("Harga naik dan posisi terbuka bertambah: uang baru ikut naik (tren didukung).");
    else if (oi < -0.02 && h > 0.01) L.push("Harga naik tapi posisi terbuka berkurang: naiknya karena short menutup posisi, bukan pembeli baru — mudah layu.");
    else if (oi > 0.02 && h < -0.01) L.push("Harga turun tapi posisi terbuka bertambah: short baru masuk mengejar harga — rawan berbalik mendadak.");
    else if (oi < -0.05 && h < -0.03) L.push("Posisi terbuka dan harga turun tajam bersamaan: banyak yang dipaksa keluar (kapitulasi).");
    else L.push("Posisi terbuka dan harga 24 jam tidak banyak berubah: pasar menunggu.");
  }
  if (v.ls_akun != null && v.ls_top != null) L.push(v.ls_akun > 1.5 && v.ls_top < 1 ? "Ritel mayoritas long, trader besar justru short: kerumunan melawan uang besar." : v.ls_akun < 0.8 && v.ls_top > 1.2 ? "Ritel mayoritas short, trader besar long: kerumunan bisa jadi bahan bakar naik." : v.ls_akun > 1.3 ? "Lebih banyak akun ritel yang long daripada short; kalau harga turun, merekalah yang terjebak." : "Posisi ritel dan trader besar relatif seimbang.");
  if (v.taker != null) L.push(v.taker > 1.2 ? "Pembeli agresif (market buy) mendominasi." : v.taker < 0.8 ? "Penjual agresif (market sell) mendominasi." : "Pembeli dan penjual agresif seimbang.");
  if (v.liq_long_24h != null && v.liq_short_24h != null) L.push(v.liq_short_24h > 2 * Math.max(v.liq_long_24h, 1) ? "Lebih banyak short yang dipaksa tutup 24 jam terakhir: harga sempat menekan ke atas." : v.liq_long_24h > 2 * Math.max(v.liq_short_24h, 1) ? "Lebih banyak long yang dipaksa tutup: harga sempat menekan ke bawah." : "Likuidasi long dan short seimbang (sampel OKX terbatas).");
  if (v.premium_coinbase != null) L.push(v.premium_coinbase > 0.001 ? "Harga di Coinbase lebih mahal: permintaan spot AS kuat." : v.premium_coinbase < -0.001 ? "Harga di Coinbase lebih murah: spot AS sedang lemah." : "Harga Coinbase dan Binance sejajar.");
  if (v.stablecoin_7d != null) L.push(v.stablecoin_7d > 0.01 ? "Suplai stablecoin naik seminggu ini: ada dana baru siap masuk." : v.stablecoin_7d < -0.01 ? "Suplai stablecoin turun: dana keluar dari ekosistem." : "Suplai stablecoin stabil.");
  const n = (p.takut_ekstrem || 0) + (p.serakah_ekstrem || 0);
  let ringkas = n === 0 ? "Tidak ada indikator di zona ekstrem: pasar sedang 'biasa', setup tiket mengandalkan level dan penolakan harga, bukan sentimen." :
    p.serakah_ekstrem > p.takut_ekstrem ? `${p.serakah_ekstrem} indikator sangat serakah: yang terjebak kalau harga berbalik turun adalah pembeli telat — waspadai setup beli yang mengejar harga.` :
    `${p.takut_ekstrem} indikator sangat takut: yang terjebak kalau harga berbalik naik adalah penjual telat — waspadai setup jual yang mengejar harga.`;
  if ((p.divergensi || []).length) ringkas += " Ada sinyal yang tidak nyambung (lihat bawah) — itu yang paling perlu dicermati.";
  return `<div class="item"><div class="l"><div class="t">Ringkasnya</div><div class="s">${esc(ringkas)}</div></div></div>` + L.map(t => `<div class="item"><div class="l"><div class="s">• ${esc(t)}</div></div></div>`).join("") +
    `<div class="item"><div class="l"><div class="s dim">Bacaan ini dihitung aturan sederhana dari angka di tabel, bukan saran beli/jual. Keputusan uang sungguhan ada di Anda.</div></div></div>`;
}

// ---------------------------------------------------------------- catatan AI
async function loadJurnal() {
  const q = new URLSearchParams({ jenis: $("#j-jenis").value }); if ($("#j-hari").value) q.set("hari", $("#j-hari").value);
  const t = await api("/api/teks?" + q.toString());
  $("#jurnal-md").textContent = t.isi || `Belum ada catatan${t.path ? " (" + t.path + ")" : ""}.`;
}
$("#j-jenis").onchange = loadJurnal; $("#j-hari").onchange = loadJurnal;

// ---------------------------------------------------------------- boot & polling
(async () => {
  initChart();
  await loadSymbols();
  await loadEkuitas();
  await loadChart(true);
  await loadRingkasan();
  setInterval(loadRingkasan, 5000);
  setInterval(() => loadChart(false), 15000);
  setInterval(loadSymbols, 60000);
  setInterval(loadEkuitas, 60000);
})();
