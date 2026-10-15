/* Meja analis — vanilla JS, Lightweight Charts v4 (CDN). Semua data dari /api/* (baca saja).
   Prinsip: kalimat yang bisa dibaca, bukan tabel KPI; label pendek, keterangan di tooltip; angka hanya dari mesin. */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nf = (d) => new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = (x, sign = false) => {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  const v = Number(x), a = Math.abs(v);
  return (sign && v > 0 ? "+" : v < 0 ? "−" : "") + "$" + nf(a > 0 && a < 1 ? 4 : 2).format(a);
};
const px = (x) => (x === null || x === undefined) ? "—" : new Intl.NumberFormat("id-ID", { maximumSignificantDigits: 6 }).format(Number(x));
const pct = (x, d = 2) => (x === null || x === undefined) ? "—" : (Number(x) >= 0 ? "+" : "") + nf(d).format(Number(x) * 100) + " %";
const wib = (ms) => ms ? new Date(Number(ms)).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
const jam = (ms) => ms ? new Date(Number(ms)).toLocaleTimeString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, hour: "2-digit", minute: "2-digit" }) : "—";
const hariWib = (ms) => new Date(Number(ms)).toLocaleDateString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short" });
const rel = (ms) => { if (!ms) return "—"; const d = Date.now() - Number(ms); if (d < 60e3) return "baru saja"; if (d < 3600e3) return Math.round(d / 60e3) + " mnt"; const h = hariWib(ms), t = hariWib(Date.now()); return h === t ? jam(ms) : `${h === hariWib(Date.now() - 86400e3) ? "kemarin" : h} ${jam(ms)}`; };
const koin = (s) => String(s || "").replace(/USDT$/, "");
const arah = (side) => side === "LONG" ? "beli" : "jual";
const TF_SEC = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400 };
const OFF = 7 * 3600; // sumbu waktu Lightweight Charts memakai UTC → geser ke WIB
const wibT = (t) => new Date((t - OFF) * 1000).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", hour12: false, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const stripFm = (t) => (t.startsWith("---") && t.indexOf("\n---", 3) > 0) ? t.slice(t.indexOf("\n---", 3) + 4).trim() : t.trim();
const api = async (p) => { const r = await fetch(p, { cache: "no-store" }); return r.json(); };
const hasLWC = typeof LightweightCharts !== "undefined";
const state = { symbol: null, tf: "5m", acak: false, lastBar: null, ps: "BTCUSDT", eq: "tiket", eqData: null, feedTop: null, symbolManual: false };
let akunList = [];

const NAMA = { tiket: "Tiket", fade: "Fade", breakout: "Breakout", rentang: "Rentang", acak: "Kembaran acak", swing: "Swing" };
const GAYA = { tiket: "price action", fade: "lawan kerumunan", breakout: "tembus & uji ulang", rentang: "mean reversion", acak: "arah dilempar koin", swing: "posisi lebih lama" };
const GAYA_TIP = {
  tiket: "Price action: masuk di level yang sudah ≥ 2 kali disentuh dan ada penolakan harga jelas, searah tren 15 menit. Mengikuti playbook Anda.",
  fade: "Lawan kerumunan: hanya bergerak bila panel psikologi menunjukkan ≥ 2 indikator ekstrem dan ada divergensi; arahnya melawan mayoritas (serakah → jual di resistance, takut → beli di support).",
  breakout: "Tembus & uji ulang: hanya kandidat dengan lonjakan volume dan lilin 5 menit menutup di luar level; masuk saat harga menguji ulang level itu.",
  rentang: "Mean reversion: hanya saat tren 15 menit sideways dan ada kompresi; melawan gerakan ke tepi range, target ke tengah range.",
  acak: "Untuk setiap order analis, mesin membuat satu order kembar dengan arah hasil lempar koin. Pembanding, bukan peserta.",
  swing: "Akun posisi lebih lama (bukan tiket harian); margin tetap per trade, maksimal beberapa posisi.",
};
const WARNA = { tiket: "#d9b35c", fade: "#8ab4f8", breakout: "#5bd4a3", rentang: "#e39bd0", acak: "#7d838b", swing: "#f0a35b" };
const ALASAN = { TP: ["target tercapai", "up"], HANGUS: ["modal hangus", "down"], FUNDING_LIQ: ["hangus karena biaya funding", "down"], STOP: ["kena stop", "down"], TRAIL: ["trailing stop (runner)", "up"], EOD: ["ditutup jam 23:50", ""], MANUAL: ["ditutup manual", ""], DELISTED: ["koin dihapus", ""] };
const STATUS_ORDER = { EXPIRED: "harga tidak pernah tersentuh", CANCELED: "dibatalkan", REJECTED: "ditolak mesin", NEW: "menunggu aktif", ACTIVE: "menunggu harga" };
const KODE = { BUDGET_TIKET: "saldo hari ini tidak cukup / di bawah $0,50", TIKET_EOD: "sudah lewat jam tutup", LIMIT_CROSSES: "harga sudah lewat level", LEVERAGE_CAP: "leverage melebihi batas", QTY_STEP: "jumlah tidak sesuai kelipatan", MIN_NOTIONAL: "nilai order terlalu kecil", RR_TOO_LOW: "untung:rugi di bawah 2,5", BAD_TP: "target di arah yang salah", BUDGET_ACAK: "jatah kembaran acak habis", ACAK_EOD: "kembaran: lewat jam tutup", ACCOUNT_PENSIUN: "akun sedang pensiun" };
const ARTI = {
  fng: "Indeks ketakutan/keserakahan ritel (0 takut – 100 serakah)", funding: "Biaya yang dibayar posisi long ke short tiap 8 jam; positif = long ramai",
  oi_24h: "Perubahan jumlah posisi terbuka 24 jam; naik = uang baru masuk", harga_24h: "Perubahan harga 24 jam", ls_akun: "Rasio akun long : short (ritel); > 1 = lebih banyak yang long",
  ls_top: "Rasio posisi long : short trader besar", taker: "Agresivitas pembeli vs penjual (> 1 = pembeli lebih agresif)", liq_long_24h: "Jumlah posisi long yang dipaksa tutup 24 jam",
  liq_short_24h: "Jumlah posisi short yang dipaksa tutup 24 jam", premium_coinbase: "Harga Coinbase (AS) vs Binance; positif = permintaan spot AS kuat",
  premium_idr: "Harga Indodax vs Binance; positif = ritel Indonesia antusias", stablecoin_7d: "Perubahan suplai stablecoin 7 hari; naik = dana siap masuk",
};
const CRON = { "notif-paper": "Notifikasi Telegram", "pemindai-tiket": "Radar koin → analis", "evaluasi-harian": "Evaluasi malam", "evaluasi-susulan": "Evaluasi susulan", "uji-hipotesis": "Uji hipotesis", "psikologi": "Panel psikologi", "nilai-arena": "Seleksi arena" };
const nama = (a) => NAMA[a] || a;
const tip = (label, text, cls = "") => `<span class="tip ${cls}" tabindex="0" data-tip="${esc(text)}">${label}</span>`;

// ---------------------------------------------------------------- tooltip (hover + fokus keyboard; satu elemen, position: fixed agar lolos dari overflow)
const tt = $("#tt");
let ttEl = null;
function showTip(el) {
  const text = el.getAttribute("data-tip"); if (!text) return;
  ttEl = el; tt.textContent = text; tt.setAttribute("aria-hidden", "false");
  const r = el.getBoundingClientRect(); tt.style.left = "0px"; tt.style.top = "0px"; tt.classList.add("on");
  const w = tt.offsetWidth, h = tt.offsetHeight;
  let x = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
  let y = r.bottom + 8; if (y + h > window.innerHeight - 8) y = r.top - h - 8;
  tt.style.left = x + "px"; tt.style.top = Math.max(8, y) + "px";
}
function hideTip() { ttEl = null; tt.classList.remove("on"); tt.setAttribute("aria-hidden", "true"); }
// jangan menimpa wadah yang sedang dipakai pengguna (tooltip terbuka / fokus keyboard di dalamnya); render berikutnya 5 detik lagi
const sibuk = (el) => !!el && ((ttEl && el.contains(ttEl)) || (document.activeElement && el.contains(document.activeElement)));
function setHTML(sel, html) { const el = $(sel); if (!el || sibuk(el)) return false; el.innerHTML = html; return true; }
setInterval(() => { if (ttEl && !ttEl.isConnected) hideTip(); }, 1000);
document.addEventListener("mouseover", e => { const el = e.target.closest("[data-tip]"); if (el && el !== ttEl) showTip(el); });
document.addEventListener("mouseout", e => { const el = e.target.closest("[data-tip]"); if (el && !el.contains(e.relatedTarget)) hideTip(); });
document.addEventListener("focusin", e => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); });
document.addEventListener("focusout", () => hideTip());
document.addEventListener("keydown", e => { if (e.key === "Escape") hideTip(); });
window.addEventListener("scroll", () => hideTip(), { passive: true });

// ---------------------------------------------------------------- lompat-bagian: tandai bagian yang terlihat
const jumps = $$(".jump a");
const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) jumps.forEach(a => a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id)); }), { rootMargin: "-40% 0px -55% 0px" });
$$("section.bag").forEach(s => io.observe(s));

// ---------------------------------------------------------------- denyut: angka yang berubah mendapat garis bawah kuningan sesaat
const prev = new Map();
function pulseChanged(root) {
  root.querySelectorAll("[data-k]").forEach(el => {
    const k = el.dataset.k, v = el.textContent;
    if (prev.has(k) && prev.get(k) !== v) { el.classList.remove("pulse"); void el.offsetWidth; el.classList.add("pulse"); }
    prev.set(k, v);
  });
}

// ---------------------------------------------------------------- SEKARANG: meja analis
function setAkunList(list) {
  if (!list || !list.length || JSON.stringify(list.map(a => a.name)) === JSON.stringify(akunList.map(a => a.name))) return;
  akunList = list;
  const eq = $("#eq-group"); eq.innerHTML = list.map(a => `<button data-acc="${a.name}" class="${a.name === state.eq ? "on" : ""}">${nama(a.name)}</button>`).join("");
  eq.querySelectorAll("button").forEach(b => b.onclick = () => { eq.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); state.eq = b.dataset.acc; loadEkuitas(); });
  $("#f-akun").innerHTML = '<option value="">semua akun</option>' + list.map(a => `<option value="${a.name}">${nama(a.name)}</option>`).join("");
}
function posisiLi(p) {
  const un = p.unrealized ?? null, jauh = p.liq_dist_pct;
  const keTarget = p.tp_price && p.mark ? (p.side === "LONG" ? (p.tp_price - p.mark) / p.mark : (p.mark - p.tp_price) / p.mark) * 100 : null;
  const rinci = [`Masuk ${jam(p.opened_ts)} WIB di ${px(p.entry_price)}`, p.tp_price ? `Target ${px(p.tp_price)}${keTarget !== null ? ` (${nf(2).format(Math.abs(keTarget))} % lagi)` : ""}` : null,
    p.sl_price ? `Stop ${px(p.sl_price)}` : null, jauh !== undefined ? `Hangus (likuidasi) ${nf(2).format(Math.abs(jauh))} % lagi` : null, p.plan_id ? `Rencana ${p.plan_id}` : null,
    `Harga sekarang ${px(p.mark)}`].filter(Boolean).join("\n");
  const tpDone = (p.tp_list || []).filter(t => t.status === "FILLED").length;
  const l2 = [`${px(p.entry_price)} <span class="ke">→</span> ${p.tp_price ? px(p.tp_price) : (p.trail_on ? "trailing" : "—")}`, jauh !== undefined ? `<span class="${jauh < 1 ? "down" : ""}">hangus ${nf(1).format(Math.abs(jauh))} %</span>` : null,
    p.plan_group ? `<span class="brass">sisa ${nf(0).format(p.persen_sisa ?? 100)} %${tpDone ? " · TP" + tpDone + " ✓" : ""}${p.legs_n > 1 ? " · " + p.legs_n + " leg" : ""}</span>` : null].filter(Boolean).join("");
  return `<li class="posisi"><div class="l1"><span class="tip" tabindex="0" data-tip="${esc(rinci)}"><b>${koin(p.symbol)}</b> ${arah(p.side)} ${p.leverage}×</span><b class="pl ${un === null ? "dim" : un >= 0 ? "up" : "down"}" data-k="pl-${p.id}">${un === null ? "harga?" : usd(un, true)}</b></div><div class="l2">${l2}</div></li>`;
}
function orderLi(o) {
  const rinci = [`${STATUS_ORDER[o.status] || o.status}`, o.tp_price ? `Target ${px(o.tp_price)}` : null, `Gugur otomatis ${jam(o.expire_ts)} WIB`, o.plan_id ? `Rencana ${o.plan_id}` : null].filter(Boolean).join("\n");
  return `<li class="order"><div class="l1"><span class="tip" tabindex="0" data-tip="${esc(rinci)}"><b>${koin(o.symbol)}</b> ${arah(o.side)} ${o.leverage}×</span><span class="muted num">${o.price ? px(o.price) : "pasar"}</span></div><div class="l2">menunggu harga<span class="ke">·</span>gugur ${jam(o.expire_ts)}</div></li>`;
}
function terakhirDari(acc, feed) {
  const e = (feed || []).find(x => x.account === acc && x.type !== "ACAK_SHADOW" && x.type !== "ACAK_SKIP");
  return e ? `<p class="terakhir"><time>${rel(e.ts)}</time> ${esc(teksKejadian(e, true))}</p>` : "";
}
function renderMeja(r, feed) {
  const personas = (r.akun || []).filter(a => a.kind === "tiket");
  const byAcc = (arr) => arr.reduce((m, x) => ((m[x.account] = m[x.account] || []).push(x), m), {});
  const pos = byAcc(r.posisi || []), ord = byAcc(r.order || []);
  setHTML("#meja", personas.map(a => {
    const b = r.budget[a.name] || {}; const na = b.status === "tidak tersedia" || b.saldo === undefined;
    const pil = a.status !== "aktif" ? ["off", "pensiun", "Dipensiunkan karena kalah dari kembaran acaknya (atau oleh Anda). Posisi yang ada tetap diproses; tidak ada order baru. Hidupkan lagi: paper_engine.py akun aktif " + a.name] :
      na ? ["", "tidak tersedia", "Mesin paper belum pernah berjalan"] : b.boleh_buka ? ["ok", "boleh buka", "Saldo ≥ $0,50 dan belum lewat 22:30: boleh pasang tiket baru"] : ["hold", "berhenti", "Saldo di bawah $0,50 atau sudah lewat 22:30: tidak ada tiket baru sampai besok"];
    const pakai = na ? 0 : (b.used + b.reserved) / Math.max(b.saldo, 0.01) * 100;
    const items = (pos[a.name] || []).map(posisiLi).concat((ord[a.name] || []).map(orderLi)).join("");
    return `<article class="analis" style="--w:${WARNA[a.name] || "#888"}">
      <header><h3>${nama(a.name)}</h3>${tip(GAYA[a.name] || "", GAYA_TIP[a.name] || "", "gaya")}<span class="pil-wrap">${tip(`<span class="pil ${pil[0]}">${pil[1]}</span>`, pil[2])}</span></header>
      <div class="saldo">${tip("Bisa dipakai", na ? "Mesin paper belum berjalan." : `Saldo bergulir hari ini ${usd(b.saldo)} (mulai $1; target tercapai menambah, hangus mengurangi).\nHasil hari ini ${usd(b.realisasi, true)}.\nTerkunci di posisi/order ${usd(b.used + b.reserved)}.\nSatu tiket maksimal $1; di bawah $0,50 berhenti sampai besok.`)}<b data-k="sisa-${a.name}">${na ? "—" : usd(b.remaining)}</b>
        <span class="hasil ${b.realisasi > 0 ? "up" : b.realisasi < 0 ? "down" : "dim"}" data-k="real-${a.name}">${na ? "" : b.realisasi ? usd(b.realisasi, true) : ""}</span>
        <span class="bar" style="grid-column:1/-1"><i class="${!na && !b.boleh_buka ? "down" : ""}" style="width:${Math.max(0, Math.min(100, 100 - pakai)).toFixed(0)}%"></i></span></div>
      <ul>${items || `<li class="nihil">Menunggu radar.</li>`}</ul>
      ${terakhirDari(a.name, feed)}</article>`;
  }).join(""));
  const a = r.budget.acak || {}, s = r.budget.swing || {};
  const acakPos = (pos.acak || []), swingPos = (pos.swing || []);
  const sum = (arr) => arr.reduce((x, p) => x + (p.unrealized || 0), 0);
  setHTML("#banding",
    `<div class="baris">${tip("<b>Kembaran acak</b>", GAYA_TIP.acak + (a.remaining !== undefined ? `\n\nSisa jatah hari ini ${usd(a.remaining)}; ${acakPos.length} posisi terbuka, ${(ord.acak || []).length} order menunggu.` : ""))} <span>${acakPos.length ? `${acakPos.length} posisi <b class="${sum(acakPos) >= 0 ? "up" : "down"}" data-k="acak-un">${usd(sum(acakPos), true)}</b>` : a.remaining !== undefined ? "tidak ada posisi" : "tidak tersedia"}</span></div>` +
    `<div class="baris">${tip("<b>Swing</b>", GAYA_TIP.swing + (s.max_open !== undefined ? `\n\n${s.open} dari maksimal ${s.max_open} posisi, $${s.margin_per_trade} per trade, ${s.pending} order menunggu.` + swingPos.map(p => `\n${koin(p.symbol)} ${arah(p.side)} ${p.leverage}×: masuk ${px(p.entry_price)}, target ${px(p.tp_price)}, hangus ${nf(1).format(Math.abs(p.liq_dist_pct || 0))} % lagi`).join("") : ""))} <span>${swingPos.length ? `${swingPos.map(p => `${koin(p.symbol)} ${arah(p.side)}`).join(", ")} <b class="${sum(swingPos) >= 0 ? "up" : "down"}" data-k="swing-un">${usd(sum(swingPos), true)}</b>` : s.max_open !== undefined ? "tidak ada posisi" : "tidak tersedia"}</span></div>`);
  pulseChanged($("#sekarang"));
}

// ---------------------------------------------------------------- kejadian → kalimat
function teksKejadian(e, pendek = false) {
  const k = koin(e.symbol), m = e.msg || "";
  const harga = (re) => { const x = m.match(re); return x ? px(Number(x[1])) : null; };
  switch (e.type) {
    case "ORDER_NEW": { const h = harga(/@ ([\d.]+)/); const lev = (m.match(/lev (\d+)x/) || [])[1]; return `pasang order ${k} ${arah(e.side)}${lev ? " " + lev + "×" : ""}${h ? " di " + h : ""}`; }
    case "OPEN": { const h = harga(/@ ([\d.]+)/); return `masuk ${k} ${arah(e.side)}${h ? " di " + h : ""}`; }
    case "TP": return `${k}: target tercapai${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "HANGUS": case "FUNDING_LIQ": return `${k}: modal hangus${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "STOP": return `${k}: kena stop${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "EOD": return `${k}: ditutup jam 23:50${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "MANUAL": case "CLOSE_REQUEST": return `${k}: ditutup manual${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "BREAKEVEN": return `${k}: stop digeser ke harga masuk${m.includes("TP1") ? " (setelah TP1)" : " (pengaman 80 % jalan ke target)"}`;
    case "RENCANA": return `rencana swing bertahap: ${m}`;
    case "ADD": return `${k}: tambah leg, ${m.replace(/^\S+ \S+ /, "")}`;
    case "TP_SEBAGIAN": return `${k}: target sebagian, ${(m.match(/pnl ([+-][\d.]+)/) || [])[1] ? usd(Number((m.match(/pnl ([+-][\d.]+)/) || [])[1]), true) : ""} (${(m.match(/sisa qty [\d.]+ \((\d+)%\)/) || [])[1] || "?"} % tersisa)`;
    case "TRAIL": return `${k}: runner kena trailing stop${e.net_result != null ? ", " + usd(e.net_result, true) : ""}`;
    case "TRAIL_AKTIF": return `${k}: trailing stop aktif untuk sisa posisi`;
    case "TRAIL_GESER": return `${k}: stop runner digeser`;
    case "ORDER_EXPIRED": return `order ${k} ${arah(e.side)} gugur, harga tidak pernah tersentuh`;
    case "ORDER_CANCEL": return `order ${k} ${arah(e.side)} dibatalkan`;
    case "ACAK_SHADOW": return `kembaran acak dibuat untuk order ${k}`;
    case "ACAK_SKIP": return `kembaran acak tidak dibuat: ${(m.match(/^\[(\w+)\]/) || [])[1] ? KODE[(m.match(/^\[(\w+)\]/) || [])[1]] || m : m}`;
    case "ACAK_TANPA_TP": return `kembaran acak ${k} tanpa target`;
    case "AKUN_STATUS": return `status akun: ${m}`;
    default: return pendek ? `${e.type.toLowerCase().replace(/_/g, " ")}` : `${e.type.toLowerCase().replace(/_/g, " ")}: ${m}`;
  }
}
function renderFeed(list) {
  const rows = (list || []).filter(e => state.acak || !(e.type.startsWith("ACAK") || e.account === "acak"));
  const top = state.feedTop;
  let hari = null; const today = hariWib(Date.now()), kemarin = hariWib(Date.now() - 86400e3);
  const html = rows.length ? rows.slice(0, 40).map(e => { const h = hariWib(e.ts); const sep = h !== hari ? (hari === null && h === today ? "" : `<li class="hari">${h === today ? "hari ini" : h === kemarin ? "kemarin" : h}</li>`) : ""; hari = h;
    return sep + `<li class="${e.account === "acak" || e.type.startsWith("ACAK") ? "acak" : ""} ${top !== null && e.id > top ? "masuk" : ""}"><time>${rel(e.ts)}</time><span>${e.account ? `<span class="who">${esc(nama(e.account))}</span> ` : ""}${esc(teksKejadian(e))}</span></li>`; }).join("") : '<li><time></time><span class="dim">Belum ada kejadian.</span></li>';
  if (!setHTML("#feed", html)) return;
  if (rows.length) state.feedTop = rows[0].id;
  $("#feed-info").textContent = rows.length ? `terbaru ${wib(rows[0].ts)}` : "";
}

// ---------------------------------------------------------------- kesehatan + mesin + biaya
const dot = (cls, label, text) => `<span class="dot ${cls}" tabindex="0" data-tip="${esc(text)}">${esc(label)}</span>`;
function renderHealth(r) {
  const c = r.collector, pm = r.pemindai, run = pm.run_terakhir, b = r.biaya;
  const h = [];
  h.push(dot(c.status === "OK" ? "ok" : c.status === "BASI" ? "bad" : "", "harga", c.status === "OK" ? `Data harga segar: tick terakhir ${c.umur_s} detik lalu (${c.wib}). Pengambil harga memperbarui tiap menit.` : c.status === "BASI" ? `Data harga basi: tick terakhir ${Math.round(c.umur_s / 60)} menit lalu. Periksa collector (run_collector.cmd).` : "Belum ada data harga: collector belum pernah berjalan."));
  h.push(dot(run ? (run.wake ? "warn" : "ok") : "", "radar", run ? `Pemindaian terakhir ${wib(run.ts)} WIB: ${run.alasan}. AI dibangunkan ${pm.wake_hari_ini}× hari ini (maks 12).` : "Radar belum pernah berjalan (cron pemindai-tiket)."));
  h.push(dot(b.status ? "" : b.cost_hari > 7 ? "warn" : "ok", "biaya", b.status ? "Biaya AI tidak tersedia: budget.sqlite belum ada." : `Biaya AI hari ini $${nf(2).format(b.cost_hari)} dari batas $${b.cap_hari} (${b.calls_hari} panggilan). Bulan ini $${nf(2).format(b.cost_bulan)} dari $${b.cap_bulan}.`));
  if (r.kill_switch) h.push(dot("bad", "AI dimatikan", "Berkas data/STOP_AGENT ada: semua panggilan AI ditolak proxy. Hapus berkas itu untuk menyalakan lagi."));
  setHTML("#health", h.join(""));
}
function renderMesin(r) {
  const c = r.collector, pm = r.pemindai, run = pm.run_terakhir;
  const cron = (r.cron || []).slice(0, 7);
  $("#mesin-info").textContent = run ? `radar ${jam(run.ts)}` : "";
  $("#mesin").innerHTML =
    `<li><div class="k">${tip("Pengambil harga", c.status === "OK" ? `Tick terakhir ${c.umur_s} detik lalu (${c.wib}). Memperbarui tiap menit dari Binance.` : c.wib ? `Terakhir ${c.wib}; collector tidak memperbarui.` : "Belum pernah ada data.")}<b class="${c.status === "OK" ? "up" : "down"}">${c.status === "OK" ? "jalan" : c.status === "BASI" ? "basi" : "mati"}</b></div></li>` +
    `<li><div class="k">${tip("Radar koin", run ? `Pemindaian terakhir ${wib(run.ts)} WIB: ${run.n_symbols} koin dipindai, ${run.alasan}. AI dibangunkan ${pm.wake_hari_ini ?? 0}× hari ini (maks 12).` : "Radar belum pernah berjalan.")}<b>${run ? `${jam(run.ts)} · ${pm.wake_hari_ini ?? 0}×` : "—"}</b></div></li>` +
    (cron.length ? cron.map(x => `<li><div class="k">${tip(esc(CRON[x.name] || x.name), `Jalan ${(x.started_at || "").slice(0, 16).replace("T", " ")} WIB. ${x.delivery_outcome === "delivered" ? "Mengirim pesan Telegram." : x.delivery_outcome === "suppressed" ? "Diam: tidak ada yang perlu dikirim." : "Status: " + (x.status || "")}`)}<span class="dim">${(x.started_at || "").slice(11, 16)} · ${x.delivery_outcome === "delivered" ? "kirim" : x.delivery_outcome === "suppressed" ? "diam" : esc(x.status || "")}</span></div></li>`).join("") : `<li class="dim">Riwayat cron Hermes tidak tersedia.</li>`);
}
function renderBiaya(b) {
  if (b.status) { $("#biaya").innerHTML = `<li class="dim">Tidak tersedia: budget.sqlite belum ada.</li>`; return; }
  const bar = (v, cap) => `<div class="bar"><i class="${v / cap > 0.7 ? "warn" : ""}" style="width:${Math.min(100, v / cap * 100).toFixed(0)}%"></i></div>`;
  $("#biaya").innerHTML =
    `<li class="utama"><div class="k">${tip("Hari ini", `${b.calls_hari} panggilan hari ini; batas $${b.cap_hari}.`)}<b data-k="biaya-hari">${usd(b.cost_hari)}</b></div>${bar(b.cost_hari, b.cap_hari)}</li>` +
    `<li><div class="k">${tip("Bulan ini", `${b.calls_bulan} panggilan bulan ini; batas $${b.cap_bulan}.` + (b.terakhir || []).slice(0, 4).map(x => `\n${jam(x.ts)} ${x.purpose || x.model_served || ""} ${usd(x.cost_usd)}`).join(""))}<b>${usd(b.cost_bulan)}</b></div>${bar(b.cost_bulan, b.cap_bulan)}</li>`;
}

async function loadRingkasan() {
  const [r, kj] = await Promise.all([api("/api/ringkasan"), api("/api/kejadian?limit=60")]);
  if (r.error) { $("#jam").textContent = "server error"; $("#segar").textContent = r.error; return; }
  setAkunList(r.akun || []);
  $("#jam").textContent = r.sekarang_wib.slice(11, 16); $("#segar").textContent = "";
  renderHealth(r); renderMeja(r, kj.kejadian); renderFeed(kj.kejadian); renderMesin(r); renderBiaya(r.biaya);
  if (!state.symbolManual) {
    const fokus = (r.posisi || []).filter(p => p.account !== "acak").sort((a, b) => b.opened_ts - a.opened_ts)[0] || (r.order || []).filter(o => o.account !== "acak").sort((a, b) => b.created_ts - a.created_ts)[0];
    if (fokus && fokus.symbol !== state.symbol && [...$("#sel-symbol").options].some(o => o.value === fokus.symbol)) { state.symbol = fokus.symbol; $("#sel-symbol").value = fokus.symbol; state.lastBar = null; loadChart(true); }
  }
}

// ---------------------------------------------------------------- PASAR: grafik
let chart, candles, volume, lines = [];
const baseOpts = { layout: { background: { color: "#1a1816" }, textColor: "#aab0b7", fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 }, grid: { vertLines: { color: "#242019" }, horzLines: { color: "#242019" } },
  timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#332e28" }, rightPriceScale: { borderColor: "#332e28" }, crosshair: { mode: 0, vertLine: { color: "#d9b35c", labelBackgroundColor: "#d9b35c" }, horzLine: { color: "#d9b35c", labelBackgroundColor: "#d9b35c" } }, localization: { locale: "id-ID", timeFormatter: wibT } };
function initChart() {
  if (!hasLWC) { $("#chart").innerHTML = '<div class="empty">Pustaka grafik tidak termuat (butuh internet sekali). Angka dan tabel tetap berfungsi.</div>'; return; }
  chart = LightweightCharts.createChart($("#chart"), baseOpts);
  candles = chart.addCandlestickSeries({ upColor: "#5bd4a3", downColor: "#f07b7b", borderVisible: false, wickUpColor: "#5bd4a3", wickDownColor: "#f07b7b" });
  volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
  chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
  new ResizeObserver(() => chart.applyOptions({ width: $("#chart").clientWidth, height: $("#chart").clientHeight })).observe($("#chart"));
}
function snap(t) { const s = TF_SEC[state.tf]; return Math.floor(t / s) * s; }
function markerText(m) {
  if (m.jenis === "ENTRY") return `${arah(m.side)} di ${px(m.price)}`;
  if (m.jenis === "TP") return `target tercapai di ${px(m.price)}`;
  if (m.jenis === "LIQUIDATION") return `modal hangus di ${px(m.price)}`;
  if (m.jenis === "EXPIRED") return `order ${px(m.price)} tidak pernah tersentuh`;
  if (m.jenis === "CANCELED") return `order ${px(m.price)} dibatalkan`;
  return `ditutup di ${px(m.price)} (${m.jenis === "EOD" ? "jam 23:50" : m.jenis === "SL" ? "stop" : m.jenis.toLowerCase()})`;
}
async function loadChart(full = true) {
  if (!state.symbol) return;
  const [data, mk] = await Promise.all([api(`/api/candles?symbol=${encodeURIComponent(state.symbol)}&tf=${state.tf}&n=600`), api(`/api/marker?symbol=${encodeURIComponent(state.symbol)}`)]);
  const evs = (mk.marker || []).filter(m => state.acak || m.account !== "acak").slice().reverse();
  $("#kejadian").innerHTML = evs.length ? evs.slice(0, 14).map(m => `<div class="ev ${m.account === "acak" ? "acak" : ""}"><time>${jam(m.time * 1000)}</time><span><span class="brass">${esc(nama(m.account))}</span> ${esc(markerText(m))}</span></div>`).join("") : '<div class="empty">Belum ada trade pada koin ini.</div>';
  if (!chart) return;
  if (!Array.isArray(data) || !data.length) { $("#chart-info").textContent = `${koin(state.symbol)}: belum ada data harga (collector hanya menyimpan 30 koin teramai + koin yang sedang dipegang).`; candles.setData([]); volume.setData([]); return; }
  const cd = data.map(b => ({ time: b.time + OFF, open: b.open, high: b.high, low: b.low, close: b.close }));
  const vd = data.map(b => ({ time: b.time + OFF, value: b.volume, color: b.close >= b.open ? "rgba(91,212,163,.28)" : "rgba(240,123,123,.28)" }));
  if (full || !state.lastBar) { candles.setData(cd); volume.setData(vd); chart.timeScale().fitContent(); }
  else { const last = cd[cd.length - 1]; if (cd.length > 1 && cd[cd.length - 2].time > state.lastBar) { candles.setData(cd); volume.setData(vd); } else if (last.time >= state.lastBar) { candles.update(last); volume.update(vd[vd.length - 1]); } }
  state.lastBar = cd[cd.length - 1].time;
  const last = data[data.length - 1];
  $("#chart-info").textContent = `${koin(state.symbol)} / USDT · lilin ${state.tf} · harga terakhir ${px(last.close)} · ${wib(last.time * 1000)} WIB · diperbarui otomatis`;
  const first = cd[0].time, lastT = cd[cd.length - 1].time;
  const markers = (mk.marker || []).filter(m => (state.acak || m.account !== "acak") && m.time + OFF >= first - TF_SEC[state.tf]).map(m => {
    const t = Math.min(snap(m.time + OFF), lastT); const acak = m.account === "acak"; const base = { time: t, text: `${nama(m.account)}: ${markerText(m)}` };
    if (m.jenis === "ENTRY") return { ...base, position: m.side === "LONG" ? "belowBar" : "aboveBar", shape: m.side === "LONG" ? "arrowUp" : "arrowDown", color: acak ? "#7d838b" : (m.side === "LONG" ? "#5bd4a3" : "#f07b7b"), size: 1.4 };
    if (m.jenis === "TP") return { ...base, position: "aboveBar", shape: "circle", color: acak ? "#5f8f7a" : "#5bd4a3", size: 1.2 };
    if (m.jenis === "LIQUIDATION") return { ...base, position: "belowBar", shape: "square", color: acak ? "#9a5a5a" : "#f07b7b", size: 1.2 };
    if (m.jenis === "EXPIRED" || m.jenis === "CANCELED") return { ...base, position: "inBar", shape: "circle", color: "#e3b04b", size: 0.6 };
    return { ...base, position: "aboveBar", shape: "circle", color: "#aab0b7" };
  }).sort((a, b) => a.time - b.time);
  candles.setMarkers(markers);
  lines.forEach(l => candles.removePriceLine(l)); lines = [];
  const LABEL = { entry: "masuk", tp: "target", sl: "stop", liq: "hangus", order: "order" };
  (mk.garis || []).filter(g => state.acak || g.account !== "acak").forEach(g => {
    const color = { entry: "#d9b35c", tp: "#5bd4a3", sl: "#aab0b7", liq: "#f07b7b", order: "#e3b04b" }[g.jenis] || "#888";
    lines.push(candles.createPriceLine({ price: g.price, color, lineWidth: 1, lineStyle: g.jenis === "order" ? 2 : 0, axisLabelVisible: true, title: `${LABEL[g.jenis]} ${nama(g.account)}` }));
  });
}
async function loadSymbols() {
  const s = await api("/api/simbol"); const sel = $("#sel-symbol"); const cur = state.symbol;
  const groups = [["Sedang dipegang", s.aktif || []], ["Pernah ditradingkan", (s.riwayat || []).filter(x => !(s.aktif || []).includes(x))], ["30 koin teramai", (s.top || []).filter(x => !(s.aktif || []).includes(x) && !(s.riwayat || []).includes(x))]];
  sel.innerHTML = groups.filter(g => g[1].length).map(g => `<optgroup label="${g[0]}">${g[1].map(x => `<option value="${x}">${koin(x)} / USDT</option>`).join("")}</optgroup>`).join("");
  state.symbol = cur && [...sel.options].some(o => o.value === cur) ? cur : ((s.aktif || [])[0] || (s.riwayat || [])[0] || (s.top || [])[0] || "BTCUSDT");
  sel.value = state.symbol;
}
$("#sel-symbol").onchange = (e) => { state.symbol = e.target.value; state.symbolManual = true; state.lastBar = null; loadChart(true); };
$$("#tf-group button").forEach(b => b.onclick = () => { $$("#tf-group button").forEach(x => x.classList.toggle("on", x === b)); state.tf = b.dataset.tf; state.lastBar = null; loadChart(true); });
$("#chk-acak").onchange = (e) => { state.acak = e.target.checked; state.feedTop = null; loadChart(true); loadRingkasan(); loadRiwayat(); loadRingkas(); };

// ---------------------------------------------------------------- tabel umum
function table(el, cols, rows, onClick) {
  el.innerHTML = `<thead><tr>${cols.map(c => `<th class="${c[2] || ""}">${c[0]}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((r, i) => `<tr data-i="${i}" class="${onClick ? "klik" : ""} ${(r.account || r.akun) === "acak" ? "acak" : ""}">${cols.map(c => `<td class="${c[2] || ""}">${c[1](r)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${cols.length}" class="empty">Belum ada data.</td></tr>`}</tbody>`;
  if (onClick) el.querySelectorAll("tbody tr[data-i]").forEach(tr => tr.onclick = () => onClick(rows[tr.dataset.i]));
}
function gotoChart(symbol) { state.symbol = symbol; state.symbolManual = true; state.lastBar = null; $("#sel-symbol").value = symbol; loadChart(true); document.getElementById("pasar").scrollIntoView({ behavior: "smooth", block: "start" }); }
const belum = (teks) => `<span class="dim" data-tip="${esc(teks)}" tabindex="0">belum cukup data</span>`;
const f = (x, fn, teks = "butuh lebih banyak trade") => (x === null || x === undefined || typeof x === "string") ? belum(typeof x === "string" ? x : teks) : fn(x);

// ---------------------------------------------------------------- RINGKASAN: koin teramai + kecenderungan analis
const vol = (x) => x >= 1e9 ? nf(1).format(x / 1e9) + " M" : x >= 1e6 ? nf(0).format(x / 1e6) + " jt" : nf(0).format(x);
const ALASAN_PENDEK = { TP: "target", HANGUS: "hangus", FUNDING_LIQ: "hangus", STOP: "stop", TRAIL: "trailing", EOD: "jam 23:50", MANUAL: "manual", DELISTED: "dihapus" };
const POLA = { pullback_resistance_wick: "pullback ke resistance", pullback_support_wick: "pullback ke support", WICK_BREAKOUT_GAGAL_resisten: "tembus gagal di resistance", WICK_BREAKOUT_GAGAL_support: "tembus gagal di support", BREAKOUT_GAGAL_atas: "tembus gagal ke atas", BREAKOUT_GAGAL_bawah: "tembus gagal ke bawah", tepi_atas_range: "tepi atas range", tepi_bawah_range: "tepi bawah range" };
function kalimatProfil(a) {
  if (!a.n_posisi) return `<span class="dim">belum pernah membuka posisi</span>`;
  const tot = a.long_n + a.short_n, arahS = a.short_n > a.long_n ? "jual" : a.long_n > a.short_n ? "beli" : "beli/jual seimbang";
  const bag = [];
  bag.push(a.short_n === a.long_n ? `<b>${arahS}</b>` : `cenderung <b>${arahS}</b> (${Math.max(a.long_n, a.short_n)}/${tot})`);
  if (a.koin.length) bag.push(`suka <b>${a.koin.map(k => koin(k.symbol)).join(", ")}</b>`);
  if (a.lev_min) bag.push(a.lev_min === a.lev_maks ? `<b>${a.lev_min}×</b>` : `<b>${a.lev_min}–${a.lev_maks}×</b>`);
  if (a.win_rate !== null && a.win_rate !== undefined) bag.push(`menang <b class="${a.win_rate >= 0.5 ? "up" : "down"}">${nf(0).format(a.win_rate * 100)} %</b> dari ${a.n_selesai}`);
  if (a.rata_durasi_mnt) bag.push(`pegang <b>${a.rata_durasi_mnt >= 90 ? nf(1).format(a.rata_durasi_mnt / 60) + " jam" : nf(0).format(a.rata_durasi_mnt) + " mnt"}</b>`);
  const al = Object.entries(a.alasan || {}).sort((x, y) => y[1] - x[1]).slice(0, 2).map(([k, n]) => `${ALASAN_PENDEK[k] || k.toLowerCase()} ${n}×`);
  if (al.length) bag.push(`keluar: <b>${al.join(", ")}</b>`);
  if (a.pola && a.pola.length) bag.push(`pola <b>${POLA[a.pola[0].pola] || a.pola[0].pola.replace(/_/g, " ")}</b>`);
  if (a.jam_sibuk !== null && a.jam_sibuk !== undefined) bag.push(`sering jam <b>${String(a.jam_sibuk).padStart(2, "0")}</b>`);
  return bag.join(" · ");
}
async function loadRingkas() {
  const r = await api("/api/ringkas?n=5");
  const top = r.top_koin || [];
  $("#top-info").textContent = top.length ? `${jam(top[0].ts)} WIB` : "";
  table($("#tbl-top"), [["#", k => k.rank, "num"], ["Koin", k => `<b>${koin(k.symbol)}</b>`], ["Harga", k => px(k.last), "num"],
    [tip("24 jam", "Perubahan harga 24 jam"), k => `<b class="${k.pct_24h >= 0 ? "up" : "down"}">${(k.pct_24h >= 0 ? "+" : "") + nf(2).format(k.pct_24h)} %</b>`, "num"],
    [tip("Volume", "Nilai perdagangan 24 jam dalam USDT (M = miliar, jt = juta)"), k => vol(k.quote_volume), "num"]], top, k => gotoChart(k.symbol));
  const rows = (r.analis || []).filter(a => a.kind === "tiket" || (state.acak && a.kind === "acak") || (a.kind === "swing" && a.n_posisi));
  $("#profil").innerHTML = rows.length ? rows.map(a => `<li><b class="nm" style="color:${WARNA[a.akun] || "inherit"}">${nama(a.akun)}</b><span class="c">${kalimatProfil(a)}${a.n_terbuka ? ` · <span class="brass">${a.n_terbuka} terbuka</span>` : ""}</span></li>`).join("") : '<li class="dim">Belum ada data.</li>';
}

// ---------------------------------------------------------------- PERINGKAT
let arenaChart, arenaSeries = {};
const dedup = (pts) => { const o = []; (pts || []).forEach(p => { const q = { time: p.time + OFF, value: p.value }; if (o.length && o[o.length - 1].time === q.time) o[o.length - 1] = q; else o.push(q); }); return o; };
async function loadArena() {
  const [ar, s] = await Promise.all([api("/api/arena"), api("/api/statistik")]);
  const rows = ar.persona || [];
  $("#arena-dihitung").textContent = ar.dihitung ? `dihitung ${ar.dihitung.slice(11, 16)}` : "";
  const j = rows.find(r => r.akun === ar.juara);
  const aktif = rows.filter(r => r.status === "aktif").length, total = rows.reduce((x, r) => x + r.n, 0), net = rows.reduce((x, r) => x + (r.total_net || 0), 0);
  const terbaik = rows.filter(r => r.n > 0).sort((a, b) => b.total_net - a.total_net)[0];
  $("#juara").innerHTML = j ? `${tip("Juara sementara", "Rata-rata hasil per trade tertinggi di antara analis dengan ≥ 30 trade selesai.")} <b class="brass">${nama(j.akun)}</b> · ${usd(j.expectancy, true)}/trade · ${j.n} trade` :
    `${tip("Belum ada juara", "Juara baru diakui setelah seorang analis menyelesaikan ≥ 30 trade. Sampai saat itu, 'terdepan' hanya urutan hasil total sementara.")} · ${aktif} aktif · ${total} trade · <b class="${net >= 0 ? "up" : "down"}">${usd(net, true)}</b>${terbaik ? ` · terdepan <b>${nama(terbaik.akun)}</b>` : ""}`;
  table($("#tbl-arena"), [["Analis", r => `<b style="color:${WARNA[r.akun] || "inherit"}">${nama(r.akun)}</b>`], ["Status", r => r.status === "aktif" ? '<span class="tag ok">aktif</span>' : '<span class="tag belum">pensiun</span>'],
    [tip("Trade", "Jumlah trade yang sudah selesai"), r => r.n, "num"], [tip("Hari", "Jumlah hari sejak trade pertamanya"), r => r.hari, "num"],
    [tip("Rata-rata", "Rata-rata hasil bersih per trade (expectancy); baru dihitung setelah ≥ 10 trade"), r => f(r.expectancy, v => `<b class="${v >= 0 ? "up" : "down"}">${usd(v, true)}</b>`), "num"],
    [tip("Menang", "Persentase trade yang berakhir untung"), r => f(r.win_rate, v => nf(0).format(v * 100) + " %"), "num"],
    [tip("Total", "Jumlah hasil bersih semua trade"), r => `<b class="${r.total_net >= 0 ? "up" : "down"}">${usd(r.total_net, true)}</b>`, "num"],
    [tip("Target", "Trade yang mencapai target"), r => r.tp_n, "num"], [tip("Hangus", "Trade yang modalnya hangus (likuidasi)"), r => r.hangus_n, "num"], [tip("Tak terisi", "Order yang harga tidak pernah sentuh"), r => r.tidak_terisi_n, "num"],
    [tip("Terdalam", "Penurunan terdalam dari puncak modal (drawdown maksimum)"), r => `<span class="down">${usd(r.drawdown_maks)}</span>`, "num"],
    [tip("Vs acaknya", "Selisih rata-rata hasil analis dikurangi kembaran acaknya, dan peluang selisih itu kebetulan (p). p di bawah 5 % = meyakinkan."), r => f(r.vs_acak_selisih, v => `<span class="${v >= 0 ? "up" : "down"}">${usd(v, true)}</span>${r.vs_acak_p != null ? ` <span class="dim">p ${nf(0).format(r.vs_acak_p * 100)} %</span>` : ""}`, "butuh ≥ 10 pasangan selesai"), "num"]], rows);
  // syarat lulus §19.7
  if (s.status) $("#lulus").innerHTML = '<li class="dim">Belum ada data.</li>';
  else {
    const L = s.lulus; const LABEL = { sampel: ["Cukup banyak trade", "≥ 200 tiket dan ≥ 30 swing, supaya bukan kebetulan"], expectancy_2_bulan: ["Untung di 2 bulan berbeda", "bukan cuma satu bulan bagus"], vs_acak: ["Lebih baik dari lempar koin", "dibanding kembaran acaknya, secara statistik"], kepatuhan: ["Patuh aturan", "tidak ada tiket setelah 22:30, tidak menyiasati budget"], stabilitas: ["Tak bergantung 1–2 trade besar", "tetap untung walau 5 % trade terbaik dibuang"] };
    const tag = (v) => v === "lulus" ? '<span class="tag ok">lolos</span>' : String(v).startsWith("belum") ? '<span class="tag belum">belum</span>' : '<span class="tag">belum cukup data</span>';
    $("#lulus").innerHTML = Object.entries(LABEL).map(([k, [t, d]]) => `<li>${tip(t, d + "\n\nStatus mesin: " + L[k])}${tag(L[k])}</li>`).join("");
  }
  if (!hasLWC) return;
  const eq = await api("/api/ekuitas"); state.eqData = eq;
  if (!arenaChart) {
    arenaChart = LightweightCharts.createChart($("#chart-arena"), { ...baseOpts, rightPriceScale: { ...baseOpts.rightPriceScale, scaleMargins: { top: 0.1, bottom: 0.1 } } });
    new ResizeObserver(() => arenaChart.applyOptions({ width: $("#chart-arena").clientWidth })).observe($("#chart-arena"));
  }
  rows.concat([{ akun: "acak" }]).forEach(r => {
    if (!arenaSeries[r.akun]) arenaSeries[r.akun] = arenaChart.addLineSeries({ color: WARNA[r.akun] || "#888", lineWidth: r.akun === "acak" ? 1 : 2, lineStyle: r.akun === "acak" ? 2 : 0, title: nama(r.akun), priceFormat: { type: "price", precision: 4, minMove: 0.0001 } });
    arenaSeries[r.akun].setData(dedup((eq[r.akun] || {}).ekuitas));
  });
  arenaChart.timeScale().fitContent();
}

// ---------------------------------------------------------------- RIWAYAT
let eqChart, ddChart, eqSeries, ddSeries;
function alasan(p) { const a = ALASAN[p.close_reason] || [String(p.close_reason || "").toLowerCase(), ""]; return `<span class="${a[1]}">${a[0]}</span>${p.ambiguous ? ' <span class="tag" data-tip="Dalam satu lilin bisa terjadi dua hal; mesin memilih yang pesimis" tabindex="0">ambigu</span>' : ""}`; }
async function loadEkuitas() {
  const eq = await api("/api/ekuitas"); state.eqData = eq;
  const d = eq[state.eq] || { ekuitas: [], drawdown: [], n: 0, ekuitas_akhir: 0, puncak: 0, drawdown_sekarang: 0, drawdown_maks: 0 };
  $("#eq-ringkas").innerHTML = d.n ? `${d.n} trade · <b class="${d.ekuitas_akhir >= 0 ? "up" : "down"}">${usd(d.ekuitas_akhir, true)}</b> · ${tip("dari puncak", `Puncak modal ${usd(d.puncak)}. Sekarang ${d.drawdown_sekarang < 0 ? usd(d.drawdown_sekarang) + " di bawah puncak" : "sedang di puncak"}.`)} <span class="${d.drawdown_sekarang < 0 ? "down" : ""}">${usd(d.drawdown_sekarang)}</span> · ${tip("terdalam", d.drawdown_maks_ts ? `Penurunan terdalam terjadi ${wib(d.drawdown_maks_ts)} WIB.` : "Belum pernah turun dari puncak.")} <span class="down">${usd(d.drawdown_maks)}</span>` : `belum ada trade selesai`;
  if (!hasLWC) return;
  if (!eqChart) {
    eqChart = LightweightCharts.createChart($("#chart-ekuitas"), { ...baseOpts, rightPriceScale: { ...baseOpts.rightPriceScale, scaleMargins: { top: 0.1, bottom: 0.1 } } });
    eqSeries = eqChart.addAreaSeries({ lineColor: "#d9b35c", topColor: "rgba(217,179,92,.3)", bottomColor: "rgba(217,179,92,.02)", lineWidth: 2, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } });
    ddChart = LightweightCharts.createChart($("#chart-drawdown"), { ...baseOpts, rightPriceScale: { ...baseOpts.rightPriceScale, scaleMargins: { top: 0.05, bottom: 0.05 } } });
    ddSeries = ddChart.addAreaSeries({ lineColor: "#f07b7b", topColor: "rgba(240,123,123,.02)", bottomColor: "rgba(240,123,123,.4)", invertFilledArea: true, lineWidth: 1, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } });
    eqChart.timeScale().subscribeVisibleLogicalRangeChange(r => r && ddChart.timeScale().setVisibleLogicalRange(r));
    new ResizeObserver(() => { eqChart.applyOptions({ width: $("#chart-ekuitas").clientWidth }); ddChart.applyOptions({ width: $("#chart-drawdown").clientWidth }); }).observe($("#chart-ekuitas"));
  }
  eqSeries.setData(dedup(d.ekuitas)); ddSeries.setData(dedup(d.drawdown));
  eqChart.timeScale().fitContent(); ddChart.timeScale().fitContent();
}
async function loadRiwayat() {
  await loadEkuitas();
  const q = new URLSearchParams(); if ($("#f-akun").value) q.set("akun", $("#f-akun").value); if ($("#f-hari").value) q.set("hari", $("#f-hari").value);
  const sym = $("#f-symbol").value.trim().toUpperCase(); if (sym) q.set("symbol", sym.endsWith("USDT") ? sym : sym + "USDT");
  const r = await api("/api/riwayat?" + q.toString());
  const showAcak = state.acak || $("#f-akun").value === "acak";
  const rinciP = (p) => [`Masuk ${wib(p.opened_ts)} di ${px(p.entry_price)}`, `Keluar ${px(p.exit_price)}`, `Leverage ${p.leverage}×`, `Fee ${usd(p.fees_total)}`, p.plan_id ? `Rencana ${p.plan_id}` : null, p.opened_ts && p.closed_ts ? `Lama ${Math.round((p.closed_ts - p.opened_ts) / 60000)} menit` : null, p.ambiguous ? "Ambigu: dalam satu lilin bisa terjadi dua hal; mesin memilih yang pesimis" : null].filter(Boolean).join("\n");
  table($("#tbl-posisi"), [["Ditutup", p => wib(p.closed_ts)], ["Analis", p => nama(p.account)], ["Koin", p => `<span class="tip" tabindex="0" data-tip="${esc(rinciP(p))}"><b>${koin(p.symbol)}</b> ${arah(p.side)} ${p.leverage}×</span>`],
    ["Keluar", p => alasan(p)], ["Hasil", p => `<b class="${(p.net_result || 0) >= 0 ? "up" : "down"}">${usd(p.net_result, true)}</b>`, "num"]], (r.posisi || []).filter(p => showAcak || p.account !== "acak"), p => gotoChart(p.symbol));
  const rinciO = (o) => [`Harga ${o.price ? px(o.price) : "pasar"}, leverage ${o.leverage}×`, o.plan_id ? `Rencana ${o.plan_id}` : null, `Dibuat oleh ${o.created_by === "hermes" ? "AI" : o.created_by === "engine" ? "mesin" : o.created_by}`].filter(Boolean).join("\n");
  table($("#tbl-order"), [["Dibuat", o => wib(o.created_ts)], ["Analis", o => nama(o.account)], ["Koin", o => `<span class="tip" tabindex="0" data-tip="${esc(rinciO(o))}"><b>${koin(o.symbol)}</b> ${arah(o.side)}</span>`],
    ["Apa yang terjadi", o => `${STATUS_ORDER[o.status] || o.status}${o.reject_code ? " — " + (KODE[o.reject_code] || o.reject_code) : ""}`]], (r.order || []).filter(o => showAcak || o.account !== "acak"), o => gotoChart(o.symbol));
  table($("#tbl-harian"), [["Hari", h => h.day_wib], ["Analis", h => nama(h.account)], ["Order", h => h.orders_n, "num"], ["Terisi", h => h.filled_n, "num"], ["Tak terisi", h => h.tidak_terisi_n, "num"], ["Target", h => h.tp_n, "num"], ["Hangus", h => h.hangus_n, "num"], ["Ditutup lain", h => h.other_close_n, "num"],
    ["Fee", h => usd(h.fees), "num"], ["Hasil", h => `<b class="${(h.pnl_net || 0) >= 0 ? "up" : "down"}">${usd(h.pnl_net, true)}</b>`, "num"]], (r.harian || []).filter(h => showAcak || h.account !== "acak"));
}
$("#f-apply").onclick = loadRiwayat;
$("#f-symbol").addEventListener("keydown", e => { if (e.key === "Enter") loadRiwayat(); });

// ---------------------------------------------------------------- KONTEKS: suasana pasar & radar
$$("[data-ps]").forEach(b => b.onclick = () => { $$("[data-ps]").forEach(x => x.classList.toggle("on", x === b)); state.ps = b.dataset.ps; loadPsikologi(); });
async function loadPsikologi() {
  const p = await api(`/api/psikologi?symbol=${state.ps}`);
  if (p.status === "tidak tersedia") { $("#ps-bacaan").innerHTML = `<li class="dim">Tidak tersedia: ${esc(p.alasan || "")}</li>`; $("#tbl-panel").innerHTML = ""; return; }
  $("#ps-bacaan").innerHTML = bacaanPasar(p) + `<li class="s dim">${esc(koin(p.symbol))} · diperbarui ${p.waktu.slice(11, 16)} WIB (${p.status === "OK" ? "segar" : "sudah lama"}) · ${p.takut_ekstrem} indikator sangat takut, ${p.serakah_ekstrem} sangat serakah${p.tidak_tersedia ? `, ${p.tidak_tersedia} tidak tersedia` : ""}</li>`;
  const ai = await api("/api/teks?jenis=harian"); let aiTxt = ai.isi || "";
  if (!aiTxt) { const kemarin = new Date(Date.now() - 86400000).toISOString().slice(0, 10); aiTxt = (await api(`/api/teks?jenis=harian&hari=${kemarin}`)).isi || ""; }
  $("#ps-ai").innerHTML = aiTxt ? md(aiTxt) : '<p class="dim">Belum ada catatan harian dari AI (ditulis tiap 23:55 WIB).</p>';
  const fv = (ind, v) => v === null || v === undefined ? "—" : ["funding", "premium_coinbase", "premium_idr"].includes(ind) ? nf(4).format(v * 100) + " %" : ["oi_24h", "harga_24h", "stablecoin_7d"].includes(ind) ? pct(v) : ind.startsWith("liq") ? v : ind === "fng" ? nf(0).format(v) : nf(2).format(v);
  const zona = (z) => z === "takut_ekstrem" ? '<span class="tag takut">sangat takut</span>' : z === "serakah_ekstrem" ? '<span class="tag serakah">sangat serakah</span>' : z === "netral" ? '<span class="tag">biasa</span>' : '<span class="tag">tidak tersedia</span>';
  table($("#tbl-panel"), [["Indikator", r => tip(esc(r.label), ARTI[r.indikator] || "")], ["Nilai", r => fv(r.indikator, r.nilai), "num"], ["Vs 24 jam lalu", r => p.perubahan_24j && p.perubahan_24j[r.indikator] !== undefined ? fv(r.indikator, p.perubahan_24j[r.indikator]) : "—", "num"], ["Suasana", r => zona(r.zona)], ["Catatan", r => `<span class="dim">${esc(r.catatan || "")}</span>`]], p.indikator || []);
}
function bacaanPasar(p) {
  const v = {}; (p.indikator || []).forEach(r => v[r.indikator] = r.nilai);
  const L = [];
  if (v.fng != null) L.push(v.fng >= 75 ? `Ritel sedang serakah (Fear & Greed ${nf(0).format(v.fng)}): euforia biasanya rawan koreksi.` : v.fng <= 25 ? `Ritel sedang ketakutan (Fear & Greed ${nf(0).format(v.fng)}): sering muncul di dekat dasar, tapi bisa lebih dalam dulu.` : `Sentimen ritel biasa-biasa saja (Fear & Greed ${nf(0).format(v.fng)}).`);
  if (v.funding != null) L.push(v.funding > 0.0003 ? "Posisi long membayar funding mahal: yang long sudah ramai dan terjepit kalau harga turun." : v.funding < -0.0001 ? "Posisi short yang membayar: short sudah ramai, rawan squeeze ke atas." : "Funding netral: tidak ada sisi yang terlalu penuh.");
  if (v.oi_24h != null && v.harga_24h != null) {
    const oi = v.oi_24h, h = v.harga_24h;
    if (oi > 0.02 && h > 0.01) L.push("Harga naik dan posisi terbuka bertambah: uang baru ikut naik (tren didukung).");
    else if (oi < -0.02 && h > 0.01) L.push("Harga naik tapi posisi terbuka berkurang: naiknya karena short menutup posisi, bukan pembeli baru, mudah layu.");
    else if (oi > 0.02 && h < -0.01) L.push("Harga turun tapi posisi terbuka bertambah: short baru masuk mengejar harga, rawan berbalik mendadak.");
    else if (oi < -0.05 && h < -0.03) L.push("Posisi terbuka dan harga turun tajam bersamaan: banyak yang dipaksa keluar (kapitulasi).");
    else L.push("Posisi terbuka dan harga 24 jam tidak banyak berubah: pasar menunggu.");
  }
  if (v.ls_akun != null && v.ls_top != null) L.push(v.ls_akun > 1.5 && v.ls_top < 1 ? "Ritel mayoritas long, trader besar justru short: kerumunan melawan uang besar." : v.ls_akun < 0.8 && v.ls_top > 1.2 ? "Ritel mayoritas short, trader besar long: kerumunan bisa jadi bahan bakar naik." : v.ls_akun > 1.3 ? "Lebih banyak akun ritel yang long daripada short; kalau harga turun, merekalah yang terjebak." : "Posisi ritel dan trader besar relatif seimbang.");
  if (v.taker != null) L.push(v.taker > 1.2 ? "Pembeli agresif (market buy) mendominasi." : v.taker < 0.8 ? "Penjual agresif (market sell) mendominasi." : "Pembeli dan penjual agresif seimbang.");
  if (v.liq_long_24h != null && v.liq_short_24h != null) L.push(v.liq_short_24h > 2 * Math.max(v.liq_long_24h, 1) ? "Lebih banyak short yang dipaksa tutup 24 jam terakhir: harga sempat menekan ke atas." : v.liq_long_24h > 2 * Math.max(v.liq_short_24h, 1) ? "Lebih banyak long yang dipaksa tutup: harga sempat menekan ke bawah." : "Likuidasi long dan short seimbang (sampel OKX terbatas).");
  if (v.premium_coinbase != null) L.push(v.premium_coinbase > 0.001 ? "Harga di Coinbase lebih mahal: permintaan spot AS kuat." : v.premium_coinbase < -0.001 ? "Harga di Coinbase lebih murah: spot AS sedang lemah." : "Harga Coinbase dan Binance sejajar.");
  if (v.stablecoin_7d != null) L.push(v.stablecoin_7d > 0.01 ? "Suplai stablecoin naik seminggu ini: ada dana baru siap masuk." : v.stablecoin_7d < -0.01 ? "Suplai stablecoin turun: dana keluar dari ekosistem." : "Suplai stablecoin stabil.");
  const n = (p.takut_ekstrem || 0) + (p.serakah_ekstrem || 0);
  let ringkas = n === 0 ? "Tidak ada indikator di zona ekstrem: pasar sedang biasa; setup tiket mengandalkan level dan penolakan harga, bukan sentimen." :
    p.serakah_ekstrem > p.takut_ekstrem ? `${p.serakah_ekstrem} indikator sangat serakah: yang terjebak kalau harga berbalik turun adalah pembeli telat. Waspadai setup beli yang mengejar harga.` :
    `${p.takut_ekstrem} indikator sangat takut: yang terjebak kalau harga berbalik naik adalah penjual telat. Waspadai setup jual yang mengejar harga.`;
  const div = (p.divergensi || []);
  return `<li class="utama"><b>${esc(ringkas)}</b></li>` +
    (div.length ? `<li>${tip("<b class=\"warn\">Yang tidak nyambung</b>", "Dua angka yang seharusnya searah tapi berlawanan; biasanya lebih penting daripada angka tunggal.")}<div class="s">${div.map(d => esc(d)).join("<br>")}</div></li>` : "") +
    `<li><details><summary>Bacaan per indikator (${L.length})</summary><ul class="list">${L.map(t => `<li>${esc(t)}</li>`).join("")}</ul></details></li>`;
}
async function loadKandidat() {
  const k = await api("/api/kandidat");
  table($("#tbl-kandidat"), [["Kode", c => "K" + c.id], ["Koin", c => `<b>${koin(c.symbol)}</b>`], ["Dugaan", c => arah(c.arah_dugaan)], ["Skor", c => c.score, "num"], ["Harga", c => px(c.mark), "num"], ["Level", c => `${px(c.level)} (${c.sentuhan}×)`, "num"],
    ["Jarak", c => nf(2).format(c.jarak_atr5m || 0) + " ATR", "num"], ["Tanda", c => (c.flags || []).map(f => `<span class="tag">${f.toLowerCase().replace(/_/g, " ")}</span>`).join(" ")], ["Lev layak", c => (c.lev_layak || []).map(l => l.leverage + "×").join(", ") || "—"], ["Kapan", c => wib(c.run_ts)]], k.kandidat || [], c => gotoChart(c.symbol));
}


// ---------------------------------------------------------------- markdown ringan → HTML (judul, tebal/miring, daftar, tabel, kutipan, kode, garis, tautan). Teks di-escape dulu.
function inline(t) {
  return esc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/(^|\s)_([^_\n]{2,})_(?=\s|$)/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
function md(src) {
  const lines = stripFm(src || "").replace(/\r/g, "").split("\n"); const out = []; let i = 0;
  const ul = /^\s*[-*•]\s+(.*)$/, ol = /^\s*\d+[.)]\s+(.*)$/;
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    if (l.startsWith("```")) { const buf = []; i++; while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]); i++; out.push(`<pre>${esc(buf.join("\n"))}</pre>`); continue; }
    const h = l.match(/^(#{1,6})\s+(.*)$/); if (h) { const n = Math.min(h[1].length + 1, 4); out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (l.includes("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map(c => inline(c.trim()));
      const head = cells(l); i += 2; const rows = [];
      while (i < lines.length && lines[i].includes("|")) rows.push(cells(lines[i++]));
      out.push(`<div class="tablewrap"><table><thead><tr>${head.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`); continue;
    }
    if (ul.test(l) || ol.test(l)) { const isOl = ol.test(l); const re = isOl ? ol : ul; const items = []; while (i < lines.length && re.test(lines[i])) { let t = lines[i].match(re)[1]; i++; while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !re.test(lines[i])) t += " " + lines[i++].trim(); items.push(`<li>${inline(t)}</li>`); } out.push(`<${isOl ? "ol" : "ul"}>${items.join("")}</${isOl ? "ol" : "ul"}>`); continue; }
    if (l.startsWith(">")) { const buf = []; while (i < lines.length && lines[i].startsWith(">")) buf.push(lines[i++].replace(/^>\s?/, "")); out.push(`<blockquote>${inline(buf.join(" "))}</blockquote>`); continue; }
    const buf = []; while (i < lines.length && lines[i].trim() && !/^(#|```|>|\s*[-*•]\s|\s*\d+[.)]\s)/.test(lines[i]) && !(lines[i].includes("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1]))) buf.push(lines[i++].trim());
    const kv = buf.length === 1 && /^[\w \-/()]{2,40}:\s+\S/.test(buf[0]) ? buf[0].replace(/^([^:]+):/, "<b>$1:</b>") : null;
    out.push(`<p>${kv ? kv.replace(/^<b>([^<]+)<\/b>/, (m, k) => `<b>${esc(k)}</b>`) + inline(buf[0].slice(buf[0].indexOf(":") + 1)) : inline(buf.join(" "))}</p>`);
  }
  return out.join("");
}

// ---------------------------------------------------------------- CATATAN AI
async function loadJurnal() {
  const q = new URLSearchParams({ jenis: $("#j-jenis").value }); if ($("#j-hari").value) q.set("hari", $("#j-hari").value);
  const t = await api("/api/teks?" + q.toString());
  $("#jurnal-md").innerHTML = t.isi ? md(t.isi) : `<p class="dim">Belum ada catatan${t.path ? " (" + esc(t.path) + ")" : ""}.</p>`;
}
$("#j-jenis").onchange = loadJurnal; $("#j-hari").onchange = loadJurnal;

// ---------------------------------------------------------------- boot & polling
(async () => {
  initChart();
  try { await loadSymbols(); } catch (e) { $("#segar").textContent = "server tidak menjawab"; }
  await loadRingkasan();
  await loadChart(true);
  loadRingkas(); loadArena(); loadRiwayat(); loadPsikologi(); loadKandidat(); loadJurnal();
  setInterval(loadRingkasan, 5000);
  setInterval(() => loadChart(false), 15000);
  setInterval(loadSymbols, 60000);
  setInterval(() => { loadRingkas(); loadArena(); loadEkuitas(); loadKandidat(); }, 60000);
  setInterval(loadPsikologi, 300000);
})();
