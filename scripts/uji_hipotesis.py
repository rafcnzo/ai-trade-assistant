"""uji_hipotesis.py — menilai hipotesis yang jatuh tempo dengan data kline_1h, menghitung baseline, dan mengelola pelajaran.

Penulis tunggal: pasar/hipotesis-hasil.jsonl (append), pasar/hipotesis.md (view), pasar/pelajaran.jsonl (state), pasar/pelajaran.md (view).
Hanya membaca pasar/hipotesis.jsonl (ditulis mcp_server) dan pasar/pelajaran-usulan.md (usulan agent; hanya pemilik yang memutuskan).
Dijalankan cron Hermes `uji-hipotesis` 23:40 WIB (--no-agent): stdout = pesan Telegram, kosong = diam. Tanpa LLM.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analisis as A  # noqa: E402
import common as C  # noqa: E402
import hipotesis as H  # noqa: E402
from common import MINUTE_MS  # noqa: E402

DUE_GRACE_MS = 10 * MINUTE_MS   # beri waktu collector menyimpan bar terakhir horizon


@dataclass
class UjiConfig:
    baseline_n: int = H.BASELINE_N
    baseline_days: int = H.BASELINE_DAYS
    seed: str = "uji-v1"
    max_aktif: int = H.MAX_AKTIF


def paths(root: Path) -> dict:
    p = root / "pasar"
    return {"hipotesis": p / "hipotesis.jsonl", "hasil": p / "hipotesis-hasil.jsonl", "hipotesis_md": p / "hipotesis.md",
            "pelajaran": p / "pelajaran.jsonl", "pelajaran_md": p / "pelajaran.md", "usulan": p / "pelajaran-usulan.md"}


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def bars_for(market, symbol: str, tf: str, days: int, now_ms: int) -> list:
    h = A.load_bars_1h(market, symbol, days, now_ms)
    return h if tf == "1h" else A.resample(h, A.TF_MS[tf], now_ms)


# --------------------------------------------------------------------------- penilaian
def judge_due(root: Path, market, now_ms: int, cfg: UjiConfig, log: logging.Logger) -> list[dict]:
    pt = paths(root)
    records = H.load_jsonl(pt["hipotesis"])
    done = {h["id"] for h in H.load_jsonl(pt["hasil"])}
    out = []
    for rec in records:
        if rec["id"] in done or int(rec["batas_ms"]) + DUE_GRACE_MS > now_ms:
            continue
        bars = bars_for(market, rec["symbol"], rec["tf"], cfg.baseline_days + 10, now_ms)
        j = H.judge(rec, bars)
        b = H.baseline(rec, bars, random.Random(f"{cfg.seed}:{rec['id']}"), cfg.baseline_n)
        b["seed"] = f"{cfg.seed}:{rec['id']}"
        res = {"id": rec["id"], "dinilai_ms": now_ms, "dinilai": C.fmt_wib(now_ms), **j, "baseline": b, "versi": H.VERSI}
        H.append_jsonl(pt["hasil"], res)
        log.info("%s %s %s → %s (%s); baseline %s", rec["id"], rec["pola"], rec["symbol"], j["hasil"], j["alasan"], b.get("rate"))
        out.append({**rec, **{"hasil_": res}})
    return out


# --------------------------------------------------------------------------- pelajaran
def update_lessons(records: list[dict], hasil: dict, lessons: list[dict], now_ms: int, cfg: UjiConfig) -> tuple[list[dict], list[str]]:
    perubahan: list[str] = []
    by_pola: dict[str, list[tuple[dict, dict]]] = {}
    for rec in records:
        h = hasil.get(rec["id"])
        if h and h["hasil"] in ("benar", "salah"):
            by_pola.setdefault(rec["pola"], []).append((rec, h))

    def stats(items):
        hr = H.hit_rate(h["hasil"] for _, h in items)
        bases = [h["baseline"]["rate"] for _, h in items if h.get("baseline", {}).get("rate") is not None]
        return len(items), hr, (sum(bases) / len(bases) if bases else None)

    lessons = [dict(l) for l in lessons]
    by_id = {l["pola"]: l for l in lessons}
    for pola, items in sorted(by_pola.items()):
        n, hr, base = stats(items)
        les = by_id.get(pola)
        if les is None:
            aktif = sum(1 for l in lessons if l["status"] == "aktif")
            if n >= H.PROMOSI_MIN_SAMPEL and hr is not None and base is not None and hr >= base + H.PROMOSI_MARGIN:
                if aktif >= cfg.max_aktif:
                    perubahan.append(f"{pola} memenuhi syarat ({n} sampel, {hr:.0%} vs {base:.0%}) tapi pelajaran aktif sudah {cfg.max_aktif}")
                    continue
                lid = f"L-{len(lessons) + 1:02d}"
                les = {"id": lid, "pola": pola, "ringkasan": f"{pola}: {n} hipotesis dinilai, {hr:.0%} benar vs baseline {base:.0%}",
                       "sampel": n, "hit_rate": hr, "baseline": base, "rezim": "semua", "status": "aktif",
                       "dibuat": C.day_wib(now_ms), "dibuat_ms": now_ms,
                       "dinilai_ulang": C.day_wib(now_ms + H.NILAI_ULANG_HARI * C.DAY_MS), "dinilai_ulang_ms": now_ms + H.NILAI_ULANG_HARI * C.DAY_MS,
                       "alasan_pensiun": None}
                lessons.append(les)
                by_id[pola] = les
                perubahan.append(f"{lid} {pola} AKTIF ({n} sampel, {hr:.0%} vs {base:.0%})")
        elif les["status"] == "aktif" and now_ms >= int(les["dinilai_ulang_ms"]):
            recent = [(r, h) for r, h in items if int(h["dinilai_ms"]) >= now_ms - H.JENDELA_NILAI_ULANG_HARI * C.DAY_MS]
            n2, hr2, base2 = stats(recent)
            if n2 >= H.PROMOSI_MIN_SAMPEL and hr2 is not None and base2 is not None:
                les.update(sampel=n2, hit_rate=hr2, baseline=base2)
                if hr2 - base2 <= H.PENSIUN_MARGIN:
                    les["status"] = "pensiun"
                    les["alasan_pensiun"] = f"hit rate 90 hari {hr2:.0%} ≈ baseline {base2:.0%} pada {C.day_wib(now_ms)}"
                    perubahan.append(f"{les['id']} {pola} PENSIUN ({les['alasan_pensiun']})")
                else:
                    perubahan.append(f"{les['id']} {pola} dinilai ulang: {hr2:.0%} vs {base2:.0%} ({n2} sampel), tetap aktif")
            else:
                perubahan.append(f"{les['id']} {pola} dinilai ulang ditunda: hanya {n2} sampel 90 hari (< {H.PROMOSI_MIN_SAMPEL})")
            les["dinilai_ulang_ms"] = now_ms + H.NILAI_ULANG_HARI * C.DAY_MS
            les["dinilai_ulang"] = C.day_wib(les["dinilai_ulang_ms"])
    return lessons, perubahan


def usulan_menunggu(root: Path) -> int:
    p = paths(root)["usulan"]
    if not p.exists():
        return 0
    return sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("| U-") and ln.rstrip().endswith("| uji |"))


# --------------------------------------------------------------------------- run
def run(root: Path, market, now_ms: int, cfg: Optional[UjiConfig] = None, log: Optional[logging.Logger] = None) -> dict:
    cfg = cfg or UjiConfig()
    log = log or logging.getLogger("uji_hipotesis")
    pt = paths(root)
    dinilai = judge_due(root, market, now_ms, cfg, log)
    records = H.load_jsonl(pt["hipotesis"])
    hasil = {h["id"]: h for h in H.load_jsonl(pt["hasil"])}
    lessons, perubahan = update_lessons(records, hasil, H.load_jsonl(pt["pelajaran"]), now_ms, cfg)
    if records or lessons:
        _write_atomic(pt["hipotesis_md"], H.render_hipotesis_md(records, hasil))
        _write_atomic(pt["pelajaran"], "".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lessons))
        _write_atomic(pt["pelajaran_md"], H.render_pelajaran_md(lessons))
    summary = {"ts": now_ms, "dinilai": dinilai, "pelajaran_berubah": perubahan, "usulan_uji": usulan_menunggu(root),
               "n_hipotesis": len(records), "n_dinilai_total": len(hasil), "n_pelajaran_aktif": sum(1 for l in lessons if l["status"] == "aktif")}
    summary["pesan"] = format_message(summary)
    log.info("run %s: %d dinilai, %d perubahan pelajaran", C.fmt_wib(now_ms), len(dinilai), len(perubahan))
    return summary


def format_message(s: dict) -> str:
    if not s["dinilai"] and not s["pelajaran_berubah"]:
        return ""
    lines = [f"🧪 Uji hipotesis {C.day_wib(s['ts'])} — {len(s['dinilai'])} dinilai"]
    for r in s["dinilai"]:
        h = r["hasil_"]
        b = h["baseline"].get("rate")
        tgt = f" {r['nilai']:.6g}" if r["jenis"] == "sentuh_harga" else (f" {r['nilai']}×ATR" if r["jenis"] == "gerak_atr" else "")
        lines.append(f"{r['id']} {r['pola']} {r['symbol']} {r['tf']} {r['jenis']} {r['arah']}{tgt} → {h['hasil'].upper()} ({h['alasan']})"
                     + (f" · baseline {b:.0%} (n={h['baseline']['n_valid']})" if b is not None else " · baseline tidak tersedia"))
    if s["pelajaran_berubah"]:
        lines.append("Pelajaran: " + "; ".join(s["pelajaran_berubah"]))
    if s["usulan_uji"]:
        lines.append(f"{s['usulan_uji']} usulan pelajaran dari agent menunggu keputusan pemilik (pasar/pelajaran-usulan.md)")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Nilai hipotesis jatuh tempo, baseline, pelajaran (tanpa LLM).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cron", action="store_true", help="cetak pesan Telegram saja (kosong = diam)")
    g.add_argument("--once", action="store_true", help="ringkasan manusia + jumlah")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sekarang", default=None)
    ap.add_argument("--seed", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    log = C.setup_logging("uji_hipotesis", to_stderr=args.once)
    cfg = UjiConfig(seed=args.seed) if args.seed else UjiConfig()
    now = C.parse_iso_ms(args.sekarang) if args.sekarang else C.now_ms()
    if not C.PASAR_DB.exists():
        print("pasar.sqlite belum ada", file=sys.stderr)
        return 1
    from paper_engine import SqliteMarket  # impor lokal: hanya butuh pembaca pasar
    pasar = C.connect(C.PASAR_DB, readonly=True)
    try:
        with C.single_instance_lock("uji_hipotesis"):
            s = run(C.ROOT, SqliteMarket(pasar), now, cfg, log)
    except C.AlreadyRunning:
        return 0
    finally:
        pasar.close()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, default=str))
    elif args.cron or not args.once:
        if s["pesan"]:
            print(s["pesan"])
    else:
        print(s["pesan"] or f"tidak ada hipotesis jatuh tempo ({s['n_hipotesis']} hipotesis, {s['n_dinilai_total']} sudah dinilai, {s['n_pelajaran_aktif']} pelajaran aktif)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
