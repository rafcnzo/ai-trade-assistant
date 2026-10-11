"""budget_guard.py — penjaga biaya API Anthropic untuk agent paper trading.

Setiap panggilan model dicatat dari `usage` respons × harga per model. Batas: harian $10,
bulanan $190 (credit $200), per panggilan $1. Kill switch: file data/STOP_AGENT.
Penulis tunggal data/budget.sqlite. Dipakai agent.py (milestone 3) lewat allow()/record()/call().
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import connect, day_wib, fmt_wib, init_schema, month_wib, now_ms, tx  # noqa: E402

SCHEMA_VERSION = "1"
PRICE_VERSION = "2026-10-06"


@dataclass(frozen=True)
class Price:
    input: float                 # USD per juta token input
    output: float                # USD per juta token output
    cache_read_mult: float = 0.05
    cw5_mult: float = 1.25       # cache write TTL 5 menit
    cw1h_mult: float = 2.0       # cache write TTL 1 jam
    tier_above: Optional[int] = None   # prompt > N token → harga tier tinggi
    input_hi: Optional[float] = None
    output_hi: Optional[float] = None


PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(4.00, 20.00, cache_read_mult=0.05),
    "claude-sonnet-5-5": Price(2.00, 10.00, cache_read_mult=0.10),
    "claude-haiku-5-5": Price(0.10, 0.50, cache_read_mult=0.10, tier_above=100_000, input_hi=0.50, output_hi=2.50),
}
FALLBACK_MODEL = "claude-opus-5-5"   # model tak dikenal ditagih dengan harga termahal yang dikenal


@dataclass
class Decision:
    ok: bool
    reason: str
    est_cost: float
    spent_today: float
    spent_month: float
    remaining_today: float
    remaining_month: float
    blocked_until: Optional[int] = None

    def __str__(self) -> str:
        s = "BOLEH" if self.ok else "TIDAK"
        return (f"{s}: {self.reason} | est ${self.est_cost:.4f} | hari ini ${self.spent_today:.4f} (sisa ${self.remaining_today:.4f}) "
                f"| bulan ini ${self.spent_month:.4f} (sisa ${self.remaining_month:.4f})")


def _get(obj: Any, name: str, default=0):
    if obj is None:
        return default
    if isinstance(obj, dict):
        v = obj.get(name, default)
    else:
        v = getattr(obj, name, default)
    return default if v is None else v


class BudgetGuard:
    def __init__(self, db_path=None, daily_cap: float = 10.0, monthly_cap: float = 190.0, max_single_call: float = 1.0,
                 prices: Optional[dict[str, Price]] = None, clock: Optional[Callable[[], int]] = None, kill_file=None):
        self.db_path = db_path or C.BUDGET_DB
        self.conn = connect(self.db_path)
        init_schema(self.conn, C.SCRIPTS_DIR / "schema_budget.sql", SCHEMA_VERSION)
        self.daily_cap = daily_cap
        self.monthly_cap = monthly_cap
        self.max_single_call = max_single_call
        self.prices = prices or PRICES
        self.clock = clock or now_ms
        self.kill_file = Path(kill_file) if kill_file else C.DATA_DIR / "STOP_AGENT"
        with tx(self.conn):
            for model, p in self.prices.items():
                self.conn.execute(
                    "INSERT OR REPLACE INTO price_table(model,price_version,input,output,cache_read_mult,cw5_mult,cw1h_mult,tier_above,input_hi,output_hi) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (model, PRICE_VERSION, p.input, p.output, p.cache_read_mult, p.cw5_mult, p.cw1h_mult, p.tier_above, p.input_hi, p.output_hi),
                )

    # ---- harga
    def price_for(self, model: Optional[str]) -> tuple[Price, bool]:
        """(harga, dikenal). Model tak dikenal → harga FALLBACK_MODEL."""
        if model in self.prices:
            return self.prices[model], True
        return self.prices[FALLBACK_MODEL], False

    def estimate(self, model: str, in_tok: int = 0, out_tok: int = 0, cache_read: int = 0, cw5: int = 0, cw1h: int = 0,
                 speed: Optional[str] = None) -> float:
        p, _ = self.price_for(model)
        prompt = in_tok + cache_read + cw5 + cw1h
        pin, pout = p.input, p.output
        if p.tier_above and prompt > p.tier_above and p.input_hi is not None:
            pin, pout = p.input_hi, p.output_hi or p.output
        cost = (in_tok * pin + out_tok * pout + cache_read * pin * p.cache_read_mult
                + cw5 * pin * p.cw5_mult + cw1h * pin * p.cw1h_mult) / 1_000_000
        if speed == "fast":
            cost *= 2
        return cost

    # ---- status
    def spent(self, day: Optional[str] = None, month: Optional[str] = None) -> float:
        if day:
            r = self.conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM api_calls WHERE day_wib=?", (day,)).fetchone()
        else:
            r = self.conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM api_calls WHERE month_wib=?", (month,)).fetchone()
        return float(r[0])

    def blocked_until(self) -> Optional[int]:
        r = self.conn.execute("SELECT value FROM guard_state WHERE key='blocked_until'").fetchone()
        return int(r[0]) if r and r[0] else None

    def _block(self, until_ms: int, reason: str) -> None:
        with tx(self.conn):
            self.conn.execute("INSERT OR REPLACE INTO guard_state(key,value) VALUES('blocked_until',?)", (str(until_ms),))
            self.conn.execute("INSERT OR REPLACE INTO guard_state(key,value) VALUES('blocked_reason',?)", (reason,))

    def allow(self, model: str, est_in: int = 0, est_out: int = 0, purpose: str = "") -> Decision:
        now = self.clock()
        day, month = day_wib(now), month_wib(now)
        est = self.estimate(model, est_in, est_out)
        today, this_month = self.spent(day=day), self.spent(month=month)
        base = dict(est_cost=est, spent_today=today, spent_month=this_month,
                    remaining_today=max(0.0, self.daily_cap - today), remaining_month=max(0.0, self.monthly_cap - this_month))
        if self.kill_file.exists():
            return Decision(False, f"kill switch aktif ({self.kill_file.name})", **base)
        bu = self.blocked_until()
        if bu and bu > now:
            return Decision(False, f"diblokir sampai {fmt_wib(bu)}", blocked_until=bu, **base)
        if est > self.max_single_call:
            return Decision(False, f"estimasi ${est:.4f} > batas per panggilan ${self.max_single_call:.2f}", **base)
        if this_month + est > self.monthly_cap:
            until = C.next_month_start_wib_ms(now)
            self._block(until, "cap bulanan")
            return Decision(False, f"cap bulanan ${self.monthly_cap:.0f} tercapai; blokir sampai {fmt_wib(until)}", blocked_until=until, **base)
        if today + est > self.daily_cap:
            until = C.next_day_start_wib_ms(now)
            self._block(until, "cap harian")
            return Decision(False, f"cap harian ${self.daily_cap:.0f} tercapai; blokir sampai {fmt_wib(until)}", blocked_until=until, **base)
        return Decision(True, f"ok ({purpose or model})", **base)

    def record(self, model_requested: str, usage: Any, purpose: str = "", ref: Optional[str] = None,
               request_id: Optional[str] = None, served_model: Optional[str] = None) -> float:
        """Mencatat biaya dari `usage` (objek SDK atau dict). Idempoten per request_id."""
        now = self.clock()
        in_tok = int(_get(usage, "input_tokens"))
        out_tok = int(_get(usage, "output_tokens"))
        cr = int(_get(usage, "cache_read_input_tokens"))
        cc = _get(usage, "cache_creation", None)
        cw5 = int(_get(cc, "ephemeral_5m_input_tokens")) if cc is not None else 0
        cw1h = int(_get(cc, "ephemeral_1h_input_tokens")) if cc is not None else 0
        if cc is None or (cw5 == 0 and cw1h == 0):
            cw5 = int(_get(usage, "cache_creation_input_tokens"))
            cw1h = 0
        speed = _get(usage, "speed", None)
        model = served_model or model_requested
        _, known = self.price_for(model)
        cost = self.estimate(model, in_tok, out_tok, cr, cw5, cw1h, speed)
        with tx(self.conn):
            try:
                self.conn.execute(
                    "INSERT INTO api_calls(ts,day_wib,month_wib,model_requested,model_served,purpose,ref,request_id,input_tokens,output_tokens,"
                    "cache_read_tokens,cache_write_5m_tokens,cache_write_1h_tokens,speed,cost_usd,price_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (now, day_wib(now), month_wib(now), model_requested, served_model, purpose, ref, request_id, in_tok, out_tok, cr, cw5, cw1h,
                     speed, cost, PRICE_VERSION),
                )
            except Exception as e:  # noqa: BLE001
                if "UNIQUE" in str(e).upper():
                    return 0.0  # sudah tercatat
                raise
        if not known:
            C.setup_logging("budget_guard", to_stderr=False).warning("model %s tidak ada di tabel harga; ditagih sebagai %s", model, FALLBACK_MODEL)
        return cost

    @contextlib.contextmanager
    def call(self, model: str, purpose: str, est_in: int = 0, est_out: int = 0, ref: Optional[str] = None):
        """with guard.call("claude-haiku-5-5", "saring", 6000, 300) as c: resp = client.messages.create(...); c.usage = resp.usage"""
        d = self.allow(model, est_in, est_out, purpose)
        if not d.ok:
            raise BudgetExceeded(d)

        class Ctx:
            usage: Any = None
            served_model: Optional[str] = None
            request_id: Optional[str] = None
            cost: float = 0.0

        ctx = Ctx()
        try:
            yield ctx
        finally:
            if ctx.usage is not None:
                ctx.cost = self.record(model, ctx.usage, purpose, ref, ctx.request_id, ctx.served_model)

    def status(self, day: Optional[str] = None) -> dict:
        now = self.clock()
        day = day or day_wib(now)
        month = day[:7]
        by_model = {r[0]: {"calls": r[1], "cost": r[2]} for r in self.conn.execute(
            "SELECT COALESCE(model_served, model_requested), COUNT(*), SUM(cost_usd) FROM api_calls WHERE day_wib=? GROUP BY 1", (day,))}
        by_purpose = {r[0] or "-": {"calls": r[1], "cost": r[2]} for r in self.conn.execute(
            "SELECT purpose, COUNT(*), SUM(cost_usd) FROM api_calls WHERE day_wib=? GROUP BY 1", (day,))}
        return {"day": day, "spent_today": self.spent(day=day), "daily_cap": self.daily_cap, "month": month,
                "spent_month": self.spent(month=month), "monthly_cap": self.monthly_cap, "blocked_until": self.blocked_until(),
                "kill_switch": self.kill_file.exists(), "by_model": by_model, "by_purpose": by_purpose}

    def report(self, day: Optional[str] = None) -> str:
        s = self.status(day)
        lines = [f"# Biaya API {s['day']}", "",
                 f"Hari ini: ${s['spent_today']:.4f} / ${s['daily_cap']:.2f} | Bulan {s['month']}: ${s['spent_month']:.4f} / ${s['monthly_cap']:.2f}",
                 f"Blokir: {fmt_wib(s['blocked_until']) if s['blocked_until'] else '-'} | Kill switch: {'AKTIF' if s['kill_switch'] else 'tidak'}", "",
                 "| model | panggilan | biaya |", "|---|---|---|"]
        lines += [f"| {m} | {v['calls']} | ${v['cost']:.4f} |" for m, v in s["by_model"].items()]
        lines += ["", "| tujuan | panggilan | biaya |", "|---|---|---|"]
        lines += [f"| {m} | {v['calls']} | ${v['cost']:.4f} |" for m, v in s["by_purpose"].items()]
        return "\n".join(lines)

    def price_report(self) -> str:
        lines = [f"Versi harga {PRICE_VERSION} (USD per juta token)", "", "| model | input | output | cache read | cache write 5m | cache write 1h | tier |", "|---|---|---|---|---|---|---|"]
        for m, p in self.prices.items():
            tier = f"> {p.tier_above:,} tok: ${p.input_hi}/${p.output_hi}" if p.tier_above else "-"
            lines.append(f"| {m} | ${p.input} | ${p.output} | ×{p.cache_read_mult} | ×{p.cw5_mult} | ×{p.cw1h_mult} | {tier} |")
        return "\n".join(lines)


class BudgetExceeded(Exception):
    def __init__(self, decision: Decision):
        super().__init__(str(decision))
        self.decision = decision


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Penjaga biaya API Anthropic.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pl = sub.add_parser("laporan"); pl.add_argument("--hari", default=None)
    sub.add_parser("harga")
    args = ap.parse_args(argv)
    g = BudgetGuard()
    if args.cmd == "status":
        print(json.dumps(g.status(), ensure_ascii=False, indent=2))
    elif args.cmd == "laporan":
        print(g.report(args.hari))
    elif args.cmd == "harga":
        print(g.price_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
