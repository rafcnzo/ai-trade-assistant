"""evaluasi.py — statistik kelulusan agent paper (§19.7), hanya membaca paper.sqlite.

Per akun (tiket, swing, acak): jumlah sampel, expectancy per trade setelah fee, per bulan kalender, win rate, hitungan
TP/HANGUS/TIDAK_TERISI, stabilitas (tanpa 5% trade terbaik), kepatuhan aturan tiket, dan perbandingan tiket vs akun
`acak` (bayangan acak yang dibuat mesin): uji permutasi dua sampel + sign test berpasangan, Python murni.
Nilai yang sampelnya kurang ditulis "tidak tersedia (alasan)" — tidak pernah diestimasi.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

MIN_SAMPEL = 10
LULUS_TIKET_N = 200
LULUS_SWING_N = 30
JAM_TIKET_TERAKHIR = "22:30"
TOP_PCT = 0.05
P_SIGNIFIKAN = 0.05
ACCOUNTS = ("tiket", "swing", "acak")


# --------------------------------------------------------------------------- util
def mean(xs: list[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def tidak_tersedia(alasan: str) -> str:
    return f"tidak tersedia ({alasan})"


def closed_positions(conn: sqlite3.Connection, account: str, since_ms: Optional[int] = None) -> list[dict]:
    q, p = "SELECT * FROM positions WHERE account=? AND status='CLOSED'", [account]
    if since_ms:
        q += " AND closed_ts>=?"
        p.append(since_ms)
    return [dict(r) for r in conn.execute(q + " ORDER BY id", p)]


def entry_orders(conn: sqlite3.Connection, account: str, since_ms: Optional[int] = None) -> list[dict]:
    q, p = "SELECT * FROM orders WHERE account=? AND reduce_only=0", [account]
    if since_ms:
        q += " AND created_ts>=?"
        p.append(since_ms)
    return [dict(r) for r in conn.execute(q + " ORDER BY id", p)]


# --------------------------------------------------------------------------- statistik per akun
def account_stats(conn: sqlite3.Connection, account: str, now_ms: int, since_ms: Optional[int] = None) -> dict:
    pos = closed_positions(conn, account, since_ms)
    orders = entry_orders(conn, account, since_ms)
    nets = [float(p["net_result"]) for p in pos if p["net_result"] is not None]
    n = len(nets)
    reasons = [p["close_reason"] for p in pos]
    bulan: dict[str, dict] = {}
    for p in pos:
        if p["net_result"] is None:
            continue
        m = C.month_wib(int(p["closed_ts"]))
        d = bulan.setdefault(m, {"n": 0, "total": 0.0})
        d["n"] += 1
        d["total"] += float(p["net_result"])
    for d in bulan.values():
        d["mean"] = d["total"] / d["n"] if d["n"] >= MIN_SAMPEL else None
        d["cukup"] = d["n"] >= MIN_SAMPEL
    stab = None
    if n >= MIN_SAMPEL:
        k = math.ceil(TOP_PCT * n)
        sisa = sorted(nets)[:-k] if k else nets
        stab = mean(sisa)
    return {
        "account": account,
        "n_posisi": len(pos),
        "n_order_entry": len(orders),
        "expectancy": mean(nets) if n >= MIN_SAMPEL else tidak_tersedia(f"n={n} < {MIN_SAMPEL}"),
        "total_net": sum(nets) if nets else 0.0,
        "win_rate": (sum(1 for x in nets if x > 0) / n) if n >= MIN_SAMPEL else tidak_tersedia(f"n={n} < {MIN_SAMPEL}"),
        "tp_n": reasons.count("TP"),
        "hangus_n": sum(1 for r in reasons if r in ("HANGUS", "FUNDING_LIQ")),
        "stop_n": reasons.count("STOP"),
        "eod_n": reasons.count("EOD"),
        "manual_n": reasons.count("MANUAL"),
        "tidak_terisi_n": sum(1 for o in orders if o["status"] == "EXPIRED"),
        "ditolak_n": sum(1 for o in orders if o["status"] == "REJECTED"),
        "ambiguous_n": sum(1 for p in pos if p["ambiguous"]),
        "per_bulan": bulan,
        "bulan_positif": sum(1 for d in bulan.values() if d["cukup"] and d["mean"] is not None and d["mean"] > 0),
        "bulan_cukup": sum(1 for d in bulan.values() if d["cukup"]),
        "stabilitas": stab if n >= MIN_SAMPEL else tidak_tersedia(f"n={n} < {MIN_SAMPEL}"),
    }


def compliance(conn: sqlite3.Connection, since_ms: Optional[int] = None) -> dict:
    orders = entry_orders(conn, "tiket", since_ms)
    lewat = [o["id"] for o in orders if o["created_by"] != "engine" and o["status"] != "REJECTED"
             and int(o["created_ts"]) >= C.wib_clock_ms(int(o["created_ts"]), JAM_TIKET_TERAKHIR)]
    return {
        "budget_ditolak_n": sum(1 for o in orders if o["reject_code"] == "BUDGET_TIKET"),
        "eod_ditolak_n": sum(1 for o in orders if o["reject_code"] == "TIKET_EOD"),
        "order_lewat_2230_n": len(lewat),
        "order_lewat_2230_id": lewat[:20],
        "catatan": f"percobaan yang ditolak mesin dicatat sebagai percobaan, bukan pelanggaran; pelanggaran agent = order tiket setelah {JAM_TIKET_TERAKHIR} WIB",
    }


# --------------------------------------------------------------------------- perbandingan tiket vs acak
def permutation_test(a: list[float], b: list[float], n_perm: int = 2000, seed: int = 1) -> float:
    """p dua sisi untuk H0: distribusi sama (statistik = selisih mean)."""
    rng = random.Random(seed)
    obs = abs(mean(a) - mean(b))
    pool = list(a) + list(b)
    na, hit = len(a), 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        if abs(mean(pool[:na]) - mean(pool[na:])) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (n_perm + 1)


def sign_test(k: int, m: int) -> float:
    """p dua sisi eksak binomial(m, 0.5) untuk k sukses."""
    if m == 0:
        return 1.0
    lo = min(k, m - k)
    p = sum(math.comb(m, i) for i in range(0, lo + 1)) / 2 ** m
    return min(1.0, 2 * p)


def pairs(conn: sqlite3.Connection, since_ms: Optional[int] = None) -> dict:
    """Pasangan posisi tiket ↔ posisi acak (plan_id 'ACAK:<entry_order_id tiket>'), keduanya CLOSED."""
    tiket = closed_positions(conn, "tiket", since_ms)
    acak = {p["plan_id"]: p for p in closed_positions(conn, "acak", since_ms) if p["plan_id"]}
    out, tanpa = [], 0
    for p in tiket:
        q = acak.get(f"ACAK:{p['entry_order_id']}")
        if q is None or p["net_result"] is None or q["net_result"] is None:
            tanpa += 1
            continue
        out.append((float(p["net_result"]), float(q["net_result"])))
    return {"pasangan": out, "tiket_tanpa_pasangan": tanpa}


def compare(conn: sqlite3.Connection, since_ms: Optional[int] = None, seed: int = 1) -> dict:
    a = [float(p["net_result"]) for p in closed_positions(conn, "tiket", since_ms) if p["net_result"] is not None]
    b = [float(p["net_result"]) for p in closed_positions(conn, "acak", since_ms) if p["net_result"] is not None]
    out: dict = {"n_tiket": len(a), "n_acak": len(b), "mean_tiket": mean(a), "mean_acak": mean(b)}
    if len(a) >= MIN_SAMPEL and len(b) >= MIN_SAMPEL:
        out["selisih_mean"] = mean(a) - mean(b)
        out["p_permutasi"] = permutation_test(a, b, seed=seed)
    else:
        out["selisih_mean"] = tidak_tersedia(f"tiket n={len(a)}, acak n={len(b)}; butuh ≥ {MIN_SAMPEL} keduanya")
        out["p_permutasi"] = None
    pr = pairs(conn, since_ms)
    ps = pr["pasangan"]
    beda = [(x, y) for x, y in ps if abs(x - y) > 1e-12]
    out["n_pasangan"] = len(ps)
    out["tiket_tanpa_pasangan"] = pr["tiket_tanpa_pasangan"]
    if len(beda) >= MIN_SAMPEL:
        k = sum(1 for x, y in beda if x > y)
        out["sign_test"] = {"tiket_lebih_baik": k, "berbeda": len(beda), "p": sign_test(k, len(beda))}
    else:
        out["sign_test"] = tidak_tersedia(f"{len(beda)} pasangan berbeda < {MIN_SAMPEL}")
    return out


# --------------------------------------------------------------------------- gabungan §19.7
def compute(conn: sqlite3.Connection, now_ms: int, since_ms: Optional[int] = None, seed: int = 1) -> dict:
    akun = {a: account_stats(conn, a, now_ms, since_ms) for a in ACCOUNTS}
    kep = compliance(conn, since_ms)
    cmp_ = compare(conn, since_ms, seed)
    t, s = akun["tiket"], akun["swing"]
    lulus: dict[str, str] = {}
    lulus["sampel"] = "lulus" if (t["n_posisi"] >= LULUS_TIKET_N and s["n_posisi"] >= LULUS_SWING_N) \
        else f"belum ({t['n_posisi']}/{LULUS_TIKET_N} tiket, {s['n_posisi']}/{LULUS_SWING_N} swing)"
    if t["bulan_cukup"] == 0:
        lulus["expectancy_2_bulan"] = tidak_tersedia(f"belum ada bulan dengan ≥ {MIN_SAMPEL} tiket selesai")
    elif t["bulan_positif"] >= 2:
        lulus["expectancy_2_bulan"] = "lulus"
    else:
        lulus["expectancy_2_bulan"] = f"belum ({t['bulan_positif']} bulan positif dari {t['bulan_cukup']} bulan dengan ≥ {MIN_SAMPEL} sampel)"
    if cmp_["p_permutasi"] is None:
        lulus["vs_acak"] = cmp_["selisih_mean"]
    elif cmp_["selisih_mean"] > 0 and cmp_["p_permutasi"] < P_SIGNIFIKAN:
        lulus["vs_acak"] = "lulus"
    else:
        lulus["vs_acak"] = f"belum (selisih mean {cmp_['selisih_mean']:+.4f}, p permutasi {cmp_['p_permutasi']:.3f})"
    lulus["kepatuhan"] = "lulus" if kep["order_lewat_2230_n"] == 0 else f"belum ({kep['order_lewat_2230_n']} order tiket setelah {JAM_TIKET_TERAKHIR} WIB)"
    st = t["stabilitas"]
    if isinstance(st, str):
        lulus["stabilitas"] = st
    else:
        lulus["stabilitas"] = "lulus" if st > 0 else f"belum (expectancy tanpa 5% terbaik {st:+.4f})"
    return {"dihitung": C.fmt_wib(now_ms), "sejak": C.fmt_wib(since_ms) if since_ms else "awal", "akun": akun,
            "kepatuhan": kep, "tiket_vs_acak": cmp_, "lulus": lulus,
            "catatan": "sampel kecil → 'tidak tersedia'; kriteria §19.7: ≥200 tiket & ≥30 swing, expectancy positif 2 bulan terpisah, "
                       "lebih baik dari acak, patuh aturan, stabil tanpa 5% trade terbaik"}


def _f(x, fmt: str = "{:+.4f}") -> str:
    return x if isinstance(x, str) else ("-" if x is None else fmt.format(x))


def render_markdown(st: dict) -> str:
    lines = [f"# Statistik kelulusan (dihitung {st['dihitung']}, sejak {st['sejak']})", "",
             "| akun | posisi selesai | expectancy/trade | win rate | TP | HANGUS | STOP | EOD | TIDAK_TERISI | ambigu | stabilitas (−5% terbaik) | bulan positif |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in ACCOUNTS:
        s = st["akun"][a]
        wr = s["win_rate"] if isinstance(s["win_rate"], str) else f"{s['win_rate']:.0%}"
        lines.append(f"| {a} | {s['n_posisi']} | {_f(s['expectancy'])} | {wr} | {s['tp_n']} | {s['hangus_n']} | {s['stop_n']} | {s['eod_n']} | "
                     f"{s['tidak_terisi_n']} | {s['ambiguous_n']} | {_f(s['stabilitas'])} | {s['bulan_positif']}/{s['bulan_cukup']} |")
    c = st["tiket_vs_acak"]
    lines += ["", "## Tiket vs acak", "",
              f"- selisih mean: {_f(c['selisih_mean'])}" + (f" (p permutasi {c['p_permutasi']:.3f})" if c["p_permutasi"] is not None else ""),
              f"- pasangan tertutup: {c['n_pasangan']} (tiket tanpa pasangan: {c['tiket_tanpa_pasangan']}); sign test: "
              + (c["sign_test"] if isinstance(c["sign_test"], str) else f"tiket lebih baik {c['sign_test']['tiket_lebih_baik']}/{c['sign_test']['berbeda']}, p {c['sign_test']['p']:.3f}")]
    k = st["kepatuhan"]
    lines += ["", "## Kepatuhan aturan tiket", "",
              f"- order tiket setelah {JAM_TIKET_TERAKHIR} WIB: {k['order_lewat_2230_n']}" + (f" (id {k['order_lewat_2230_id']})" if k["order_lewat_2230_id"] else ""),
              f"- percobaan ditolak mesin: budget {k['budget_ditolak_n']}, EOD {k['eod_ditolak_n']}"]
    lines += ["", "## Kriteria §19.7", "", "| kriteria | status |", "|---|---|"]
    for key, label in (("sampel", "jumlah sampel"), ("expectancy_2_bulan", "expectancy positif 2 bulan"), ("vs_acak", "mengalahkan baseline acak"),
                       ("kepatuhan", "kepatuhan aturan"), ("stabilitas", "stabilitas")):
        lines.append(f"| {label} | {st['lulus'][key]} |")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Statistik kelulusan agent paper (§19.7); hanya membaca paper.sqlite.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sejak", default=None, help="YYYY-MM-DD (WIB)")
    ap.add_argument("--db", default=None)
    ap.add_argument("--sekarang", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    db = Path(args.db) if args.db else C.PAPER_DB
    if not db.exists():
        print("paper.sqlite belum ada")
        return 1
    conn = C.connect(db, readonly=True)
    try:
        st = compute(conn, C.parse_iso_ms(args.sekarang) if args.sekarang else C.now_ms(),
                     C.parse_iso_ms(args.sejak) if args.sejak else None)
    finally:
        conn.close()
    print(json.dumps(st, ensure_ascii=False, indent=1, default=str) if args.json else render_markdown(st))
    return 0


if __name__ == "__main__":
    sys.exit(main())
