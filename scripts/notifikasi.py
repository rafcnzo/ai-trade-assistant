"""notifikasi.py — notifikasi kejadian paper trading ke Telegram lewat cron Hermes `--no-agent` (tanpa LLM).

Membaca data/paper.sqlite (readonly: events ⋈ orders ⋈ positions) dan mengingat kursor kejadian terakhir yang sudah
dikirim di data/notif.json (penulis tunggal: skrip ini). Kontrak Hermes --no-agent: stdout kosong = tidak ada pesan;
ada isi = dikirim verbatim ke Telegram. Dipanggil tiap menit lewat hermes/scripts/notif_cron.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

NOTIF_PATH = C.DATA_DIR / "notif.json"

SQL = """
SELECT e.id, e.ts, e.level, e.type, e.position_id, e.order_id, e.msg,
       o.account AS o_account, o.symbol AS o_symbol, o.side AS o_side, o.type AS o_type, o.price AS o_price, o.qty AS o_qty,
       o.leverage AS o_lev, o.plan_id AS o_plan, o.created_by AS o_by, o.tp_price AS o_tp, o.sl_price AS o_sl,
       p.account AS p_account, p.symbol AS p_symbol, p.side AS p_side, p.qty AS p_qty, p.entry_price AS p_entry, p.leverage AS p_lev,
       p.margin_initial AS p_margin, p.liq_price AS p_liq, p.tp_price AS p_tp, p.sl_price AS p_sl, p.plan_id AS p_plan,
       p.exit_price AS p_exit, p.realized_pnl AS p_pnl, p.fees_total AS p_fees, p.funding_total AS p_funding, p.net_result AS p_net,
       p.alt_outcome AS p_alt
FROM events e LEFT JOIN orders o ON o.id = e.order_id LEFT JOIN positions p ON p.id = e.position_id
"""

TUTUP = {"TP": "🎯 TP", "STOP": "🛑 STOP", "MANUAL": "🔚 TUTUP MANUAL", "EOD": "🌙 TUTUP EOD", "DELISTED": "🚫 DELISTING"}


@dataclass
class NotifConfig:
    max_events: int = 20     # per pesan; sisanya diringkas sebagai "+n lebih lama"
    skip_accounts: tuple = ("acak",)   # bayangan acak (pembanding mesin) tidak dinotifikasi


# --------------------------------------------------------------------------- format
def fmt_px(x) -> str:
    return "-" if x is None else f"{float(x):.6g}"


def fmt_usd(x, sign: bool = False) -> str:
    if x is None:
        return "$-"
    v = float(x)
    return f"{'+' if v >= 0 else '-'}${abs(v):.4f}" if sign else f"${v:.4f}"


def _rule(msg: str) -> str:
    """'... @ 82700 (THROUGH) lev ...' → 'THROUGH'."""
    i, j = msg.find("("), msg.find(")")
    return msg[i + 1:j] if 0 <= i < j else ""


def format_event(e: dict) -> str:
    jam = C.to_wib(int(e["ts"])).strftime("%H:%M")
    typ, msg = e["type"], e["msg"] or ""
    pid, oid = e["position_id"], e["order_id"]
    sym = e["p_symbol"] or e["o_symbol"] or ""
    side = e["p_side"] or e["o_side"] or ""
    acc = e["p_account"] or e["o_account"] or ""
    plan = e["p_plan"] or e["o_plan"]
    if typ == "ORDER_NEW":
        line = (f"🆕 Order #{oid} {acc} {sym} {side} {e['o_type'] or ''} {fmt_px(e['o_qty'])} @ {fmt_px(e['o_price']) if e['o_price'] else 'MARKET'} "
                f"{e['o_lev']}x · TP {fmt_px(e['o_tp'])} · SL {fmt_px(e['o_sl'])}")
        if plan:
            line += f" · {plan}"
        if e["o_by"]:
            line += f" · oleh {e['o_by']}"
    elif typ == "ORDER_CANCEL":
        line = f"❌ Order #{oid} {acc} {sym} {side} @ {fmt_px(e['o_price'])} dibatalkan ({msg})"
    elif typ == "ORDER_EXPIRED":
        line = f"⌛ Order #{oid} {acc} {sym} {side} @ {fmt_px(e['o_price'])} kedaluwarsa — tidak terisi"
    elif typ == "BREAKEVEN":
        line = f"🛡️ Pengaman posisi #{pid} {sym} {side}: {msg}"
    elif typ == "ACAK_SHADOW":
        line = f"🎲 Bayangan acak: {msg}"
    elif typ == "ACAK_SKIP":
        line = f"🎲 Bayangan acak dilewati untuk order #{oid}: {msg}"
    elif typ == "CLOSE_REQUEST":
        line = f"⏳ Posisi #{pid} {sym} {side}: permintaan tutup ({msg}); dieksekusi market di bar berikutnya"
    elif typ == "OPEN":
        if e["p_entry"] is None:
            line = f"✅ TERISI posisi #{pid}: {msg}"
        else:
            line = (f"✅ TERISI posisi #{pid} {acc} {sym} {side} {fmt_px(e['p_qty'])} @ {fmt_px(e['p_entry'])} ({_rule(msg)}) {e['p_lev']}x "
                    f"· margin {fmt_usd(e['p_margin'])} · liq {fmt_px(e['p_liq'])} · TP {fmt_px(e['p_tp'])} · SL {fmt_px(e['p_sl'])}")
            if plan:
                line += f" · {plan}"
    elif typ in TUTUP:
        if e["p_net"] is None:
            line = f"{TUTUP[typ]} posisi #{pid}: {msg}"
        else:
            line = (f"{TUTUP[typ]} posisi #{pid} {acc} {sym} {side} keluar {fmt_px(e['p_exit'])} · net {fmt_usd(e['p_net'], True)} "
                    f"(pnl {fmt_usd(e['p_pnl'], True)}, fee {fmt_usd(e['p_fees'])}, funding {fmt_usd(e['p_funding'], True)})")
    elif typ in ("HANGUS", "FUNDING_LIQ"):
        if e["p_net"] is None:
            line = f"💀 LIKUIDASI posisi #{pid}: {msg}"
        else:
            line = (f"💀 LIKUIDASI{' (funding)' if typ == 'FUNDING_LIQ' else ''} posisi #{pid} {acc} {sym} {side} liq {fmt_px(e['p_liq'])} "
                    f"· rugi {fmt_usd(e['p_net'], True)} (margin + fee hangus)")
    else:
        line = f"ℹ️ {typ}: {msg}"
    if "[AMBIGU" in msg:
        line += f" ⚠️ AMBIGU (alternatif {e['p_alt'] or '?'})"
    return f"{jam} {line}"


def format_message(events: list[dict], skipped: int = 0) -> str:
    head = f"📣 Paper trading — {len(events)} kejadian baru"
    if skipped:
        head += f" (+{skipped} lebih lama tidak ditampilkan)"
    return "\n".join([head] + [format_event(e) for e in events])


# --------------------------------------------------------------------------- kursor & data
def read_cursor(path: Path) -> Optional[int]:
    try:
        return int(json.loads(path.read_text(encoding="utf-8"))["last_event_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_cursor(path: Path, last_id: int, now: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_event_id": int(last_id), "updated_ts": now, "updated_wib": C.fmt_wib(now)}), encoding="utf-8")


def max_event_id(conn: sqlite3.Connection) -> int:
    r = conn.execute("SELECT MAX(id) FROM events").fetchone()
    return int(r[0]) if r and r[0] is not None else 0


def fetch(conn: sqlite3.Connection, after_id: int, limit: Optional[int] = None) -> list[dict]:
    q = SQL + " WHERE e.id > ? ORDER BY e.id"
    p: list = [after_id]
    if limit:
        q += " LIMIT ?"
        p.append(int(limit))
    return [dict(r) for r in conn.execute(q, p)]


def last_events(conn: sqlite3.Connection, n: int) -> list[dict]:
    rows = [dict(r) for r in conn.execute(SQL + " ORDER BY e.id DESC LIMIT ?", (int(n),))]
    return list(reversed(rows))


def run(conn: sqlite3.Connection, cursor_path: Path, cfg: Optional[NotifConfig] = None, now: Optional[int] = None,
        log: Optional[logging.Logger] = None) -> str:
    """Pesan untuk kejadian baru sejak kursor (kosong bila tidak ada). Kali pertama: kursor diset ke kejadian terakhir tanpa mengirim."""
    cfg = cfg or NotifConfig()
    now = now if now is not None else C.now_ms()
    log = log or logging.getLogger("notifikasi")
    cur = read_cursor(cursor_path)
    if cur is None:
        mx = max_event_id(conn)
        write_cursor(cursor_path, mx, now)
        log.info("inisialisasi kursor ke event #%d tanpa mengirim", mx)
        return ""
    rows = fetch(conn, cur)
    if not rows:
        return ""
    last_id = rows[-1]["id"]
    rows = [e for e in rows if (e["p_account"] or e["o_account"]) not in cfg.skip_accounts]
    if not rows:
        write_cursor(cursor_path, last_id, now)
        return ""
    skipped = max(0, len(rows) - cfg.max_events)
    shown = rows[skipped:]
    msg = format_message(shown, skipped)
    write_cursor(cursor_path, last_id, now)
    log.info("kirim %d kejadian (#%d..#%d)%s", len(shown), shown[0]["id"], shown[-1]["id"], f", lewati {skipped}" if skipped else "")
    return msg


# --------------------------------------------------------------------------- CLI
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Notifikasi kejadian paper trading (untuk cron Hermes --no-agent).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cron", action="store_true", help="mode cron: cetak kejadian baru, majukan kursor (default)")
    g.add_argument("--uji", type=int, metavar="N", help="cetak N kejadian terakhir tanpa mengubah kursor")
    g.add_argument("--kursor", type=int, metavar="ID", help="set kursor ke event ID (kejadian setelahnya akan dikirim)")
    g.add_argument("--reset", action="store_true", help="set kursor ke kejadian terakhir (tidak mengirim yang lama)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    log = C.setup_logging("notifikasi", to_stderr=bool(args.uji))
    now = C.now_ms()
    if args.kursor is not None:
        write_cursor(NOTIF_PATH, args.kursor, now)
        print(f"kursor diset ke event #{args.kursor}", file=sys.stderr)
        return 0
    if not C.PAPER_DB.exists():
        log.warning("paper.sqlite belum ada")
        return 0
    conn = C.connect(C.PAPER_DB, readonly=True)
    try:
        if args.reset:
            write_cursor(NOTIF_PATH, max_event_id(conn), now)
            print(f"kursor diset ke event terakhir #{max_event_id(conn)}", file=sys.stderr)
            return 0
        if args.uji:
            rows = last_events(conn, args.uji)
            print(format_message(rows) if rows else "(belum ada kejadian)")
            return 0
        try:
            with C.single_instance_lock("notifikasi"):
                msg = run(conn, NOTIF_PATH, log=log, now=now)
        except C.AlreadyRunning:
            return 0
        if msg:
            print(msg)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
