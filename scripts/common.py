"""Utilitas bersama: waktu WIB, HTTP dengan resolver DoH, SQLite, Decimal, logging, lock.

Dipakai oleh collector.py, paper_engine.py, budget_guard.py, dan skrip milestone berikutnya.
Tidak ada API key. Semua akses jaringan hanya ke endpoint publik.
"""
from __future__ import annotations

import contextlib
import logging
import socket
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP, Decimal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator, Optional

import requests

# --------------------------------------------------------------------------- path
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
SCRIPTS_DIR = ROOT / "scripts"
PASAR_DB = DATA_DIR / "pasar.sqlite"
PAPER_DB = DATA_DIR / "paper.sqlite"
BUDGET_DB = DATA_DIR / "budget.sqlite"

# --------------------------------------------------------------------------- waktu
WIB = timezone(timedelta(hours=7), "WIB")
MINUTE_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000


def now_ms() -> int:
    return int(time.time() * 1000)


def to_wib(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=WIB)


def to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def fmt_wib(ms: int) -> str:
    return to_wib(ms).strftime("%Y-%m-%d %H:%M:%S WIB")


def day_wib(ms: int) -> str:
    return to_wib(ms).strftime("%Y-%m-%d")


def month_wib(ms: int) -> str:
    return to_wib(ms).strftime("%Y-%m")


def floor_minute(ms: int) -> int:
    return ms - ms % MINUTE_MS


def ceil_minute(ms: int) -> int:
    return ms if ms % MINUTE_MS == 0 else floor_minute(ms) + MINUTE_MS


def day_start_wib_ms(day: str) -> int:
    """Awal hari WIB (00:00) untuk string 'YYYY-MM-DD', dalam ms UTC."""
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=WIB).timestamp() * 1000)


def next_day_start_wib_ms(ms: int) -> int:
    return day_start_wib_ms(day_wib(ms)) + DAY_MS


def next_month_start_wib_ms(ms: int) -> int:
    d = to_wib(ms)
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return int(datetime(y, m, 1, tzinfo=WIB).timestamp() * 1000)


def wib_clock_ms(ms: int, hhmm: str) -> int:
    """ms untuk jam 'HH:MM' WIB pada hari WIB yang memuat `ms`."""
    h, m = hhmm.split(":")
    return day_start_wib_ms(day_wib(ms)) + int(h) * HOUR_MS + int(m) * MINUTE_MS


def parse_iso_ms(text: str) -> int:
    """'2026-10-11', '2026-10-11T07:30', atau '2026-10-11 07:30:00' → ms. Tanpa zona = WIB."""
    text = text.strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return int(dt.replace(tzinfo=WIB).timestamp() * 1000)
        except ValueError:
            continue
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WIB)
    return int(dt.timestamp() * 1000)


# --------------------------------------------------------------------------- error
class NetError(Exception):
    """Kesalahan jaringan yang sudah diklasifikasi; pesan dalam bahasa Indonesia."""


class DnsError(NetError):
    pass


class BlockedError(NetError):
    """Respons adalah halaman blokir ISP (Kominfo), bukan data. Jangan disimpan."""


class HttpError(NetError):
    def __init__(self, status: int, body: str, url: str = ""):
        super().__init__(f"HTTP {status} dari {url}: {body[:200]}")
        self.status = status
        self.body = body
        self.url = url


class AlreadyRunning(Exception):
    pass


# --------------------------------------------------------------------------- DoH
BINANCE_HOSTS = ("fapi.binance.com", "www.binance.com", "api.binance.com", "dapi.binance.com",
                 "api.exchange.coinbase.com", "www.okx.com")   # + host panel psikologi yang juga diblokir DNS ISP
DOH_URLS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)
BLOCK_MARKERS = ("kominfo", "konten terlarang", "block.centrin", "internet positif", "internetpositif")
USER_AGENT = "crypto-analyst/0.1 (+paper trading lokal; endpoint publik saja)"


class DohResolver:
    """Resolusi DNS lewat DNS-over-HTTPS untuk daftar host tertentu.

    ISP di jaringan rumah mengarahkan binance.com ke halaman blokir. Resolver ini
    mem-patch socket.getaddrinfo HANYA untuk host dalam allowlist, sehingga koneksi
    TLS tetap memakai nama host asli (SNI dan sertifikat valid). Pengaturan DNS
    sistem tidak disentuh.
    """

    def __init__(self, hosts=BINANCE_HOSTS, ttl_s: int = 300, timeout: float = 6.0):
        self.hosts = {h.lower() for h in hosts}
        self.ttl = ttl_s
        self.timeout = timeout
        self._cache: dict[str, tuple[list[str], float]] = {}
        self._lock = threading.Lock()
        self._orig = None
        self.installed = False
        self.log = logging.getLogger("common.doh")

    def resolve(self, host: str) -> list[str]:
        host = host.lower()
        with self._lock:
            hit = self._cache.get(host)
            if hit and hit[1] > time.monotonic():
                return list(hit[0])
        last: Optional[Exception] = None
        for url in DOH_URLS:
            try:
                r = requests.get(
                    url,
                    params={"name": host, "type": "A"},
                    headers={"accept": "application/dns-json", "User-Agent": USER_AGENT},
                    timeout=self.timeout,
                )
                data = r.json()
                ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
                if ips:
                    with self._lock:
                        self._cache[host] = (ips, time.monotonic() + self.ttl)
                    return list(ips)
                last = DnsError(f"DoH {url} tidak memberi jawaban A untuk {host}")
            except Exception as e:  # noqa: BLE001 - semua kegagalan DoH diperlakukan sama
                last = e
        raise DnsError(f"gagal resolve {host} lewat DoH: {last}")

    def invalidate(self, host: Optional[str] = None) -> None:
        with self._lock:
            if host is None:
                self._cache.clear()
            else:
                self._cache.pop(host.lower(), None)

    def install(self) -> None:
        if self.installed:
            return
        self._orig = socket.getaddrinfo
        resolver = self

        def patched(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
            h = host.decode() if isinstance(host, bytes) else host
            if isinstance(h, str) and h.lower() in resolver.hosts:
                try:
                    ips = resolver.resolve(h)
                except DnsError as e:
                    resolver.log.warning("DoH gagal untuk %s (%s); memakai DNS sistem", h, e)
                    ips = []
                results = []
                for ip in ips:
                    try:
                        results.extend(resolver._orig(ip, port, family, type, proto, flags))
                    except socket.gaierror:
                        continue
                if results:
                    return results
            return resolver._orig(host, port, family, type, proto, flags)

        socket.getaddrinfo = patched
        self.installed = True

    def uninstall(self) -> None:
        if self.installed and self._orig is not None:
            socket.getaddrinfo = self._orig
            self.installed = False


RESOLVER = DohResolver()


def ensure_resolver() -> DohResolver:
    if not RESOLVER.installed:
        RESOLVER.install()
    return RESOLVER


# --------------------------------------------------------------------------- HTTP
_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
            _session = s
        return _session


class WeightPacer:
    """Menjaga pemakaian weight Binance (header X-MBX-USED-WEIGHT-1M) di bawah ambang."""

    def __init__(self, threshold: int = 1000, limit: int = 1200):
        self.threshold = threshold
        self.limit = limit
        self.last_weight: Optional[int] = None
        self.last_seen: float = 0.0

    def observe(self, headers) -> None:
        w = headers.get("X-MBX-USED-WEIGHT-1M") or headers.get("x-mbx-used-weight-1m")
        if w is not None:
            try:
                self.last_weight = int(w)
                self.last_seen = time.monotonic()
            except ValueError:
                pass

    def seconds_until_next_minute(self) -> float:
        return 60.0 - (time.time() % 60.0) + 1.0

    def pace(self) -> float:
        """Tidur jika weight menit ini sudah tinggi. Mengembalikan detik yang ditidurkan."""
        if self.last_weight is None or time.monotonic() - self.last_seen > 60:
            return 0.0
        if self.last_weight >= self.threshold:
            s = self.seconds_until_next_minute()
            time.sleep(s)
            self.last_weight = 0
            return s
        return 0.0


PACER = WeightPacer()


def looks_blocked(text: str, content_type: str = "") -> bool:
    head = (text or "")[:4000].lower()
    if any(m in head for m in BLOCK_MARKERS):
        return True
    return "text/html" in (content_type or "").lower() and "<html" in head


def http_get(
    url: str,
    params: Optional[dict] = None,
    timeout: float = 10.0,
    retries: int = 3,
    expect_json: bool = True,
) -> tuple[Any, dict]:
    """GET dengan resolver DoH, retry/backoff, deteksi halaman blokir, dan pacing weight.

    Mengembalikan (data, meta). meta: status, weight, elapsed_ms, attempts.
    Melempar BlockedError (tanpa retry), DnsError, HttpError, atau NetError.
    """
    ensure_resolver()
    host = requests.utils.urlparse(url).hostname or ""
    last: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        PACER.pace()
        t0 = time.monotonic()
        try:
            r = session().get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            last = NetError(f"koneksi gagal ke {host}: {e.__class__.__name__}")
            RESOLVER.invalidate(host)
            time.sleep(min(2.0 * attempt, 8.0))
            continue
        elapsed = int((time.monotonic() - t0) * 1000)
        PACER.observe(r.headers)
        ctype = r.headers.get("Content-Type", "")
        text = r.text
        if looks_blocked(text, ctype):
            raise BlockedError(f"{host} dialihkan ke halaman blokir ISP; data tidak tersedia")
        if r.status_code in (429, 418):
            wait = r.headers.get("Retry-After")
            try:
                wait_s = float(wait) if wait else (60.0 if r.status_code == 418 else 5.0 * attempt)
            except ValueError:
                wait_s = 5.0 * attempt
            last = HttpError(r.status_code, text, url)
            time.sleep(min(wait_s, 120.0))
            continue
        if r.status_code >= 500:
            last = HttpError(r.status_code, text, url)
            time.sleep(min(2.0 * attempt, 8.0))
            continue
        if r.status_code >= 400:
            raise HttpError(r.status_code, text, url)
        meta = {
            "status": r.status_code,
            "weight": PACER.last_weight,
            "elapsed_ms": elapsed,
            "attempts": attempt,
        }
        if not expect_json:
            return text, meta
        try:
            return r.json(), meta
        except ValueError as e:
            if "<html" in text[:2000].lower():
                raise BlockedError(f"{host} membalas HTML, bukan JSON") from e
            raise NetError(f"JSON tidak valid dari {url}: {text[:120]}") from e
    assert last is not None
    raise last


# --------------------------------------------------------------------------- SQLite
def connect(path, readonly: bool = False) -> sqlite3.Connection:
    """Koneksi SQLite: autocommit (transaksi eksplisit lewat tx()), WAL, busy_timeout 5 s."""
    memory = str(path) == ":memory:"
    if not memory:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if readonly:
            conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=5, isolation_level=None)
        else:
            conn = sqlite3.connect(str(p), timeout=5, isolation_level=None)
    else:
        conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    if not memory and not readonly:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_tx_depth: dict[int, int] = {}


@contextlib.contextmanager
def tx(conn: sqlite3.Connection, immediate: bool = True) -> Iterator[sqlite3.Connection]:
    """Transaksi eksplisit yang boleh bersarang (hanya lapisan terluar yang BEGIN/COMMIT)."""
    key = id(conn)
    depth = _tx_depth.get(key, 0)
    if depth == 0:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    _tx_depth[key] = depth + 1
    try:
        yield conn
        if depth == 0:
            conn.execute("COMMIT")
    except BaseException:
        if depth == 0:
            conn.execute("ROLLBACK")
        raise
    finally:
        _tx_depth[key] = depth
        if depth == 0:
            _tx_depth.pop(key, None)


def init_schema(conn: sqlite3.Connection, sql_file, version: str) -> None:
    """Menjalankan file DDL (idempoten, CREATE IF NOT EXISTS) dan mencatat versi di meta."""
    sql = Path(sql_file).read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (version,),
    )


def meta_get(conn: sqlite3.Connection, key: str, default: Optional[str] = None) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def meta_set(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


# --------------------------------------------------------------------------- Decimal
def D(x: Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(str(x))


def round_step(value: Any, step: Any, mode: str = "down") -> Decimal:
    """Membulatkan `value` ke kelipatan `step` (down/up/nearest)."""
    v, s = D(value), D(step)
    if s <= 0:
        return v
    rounding = {"down": ROUND_DOWN, "up": ROUND_UP, "nearest": ROUND_HALF_EVEN}[mode]
    n = (v / s).quantize(Decimal(1), rounding=rounding)
    exp = s.normalize().as_tuple().exponent
    unit = Decimal(1).scaleb(exp) if exp < 0 else Decimal(1)
    return (n * s).quantize(unit)


def is_multiple(value: Any, step: Any) -> bool:
    v, s = D(value), D(step)
    if s <= 0:
        return True
    return (v / s) == (v / s).to_integral_value()


def fmt_dec(x: Any) -> str:
    d = D(x).normalize()
    return format(d, "f")


# --------------------------------------------------------------------------- simbol
MAJOR_BASES = {"BTC", "ETH"}
PREFIXES = ("1000000", "1000")


def base_asset(symbol: str, quote: str = "USDT") -> str:
    b = symbol[: -len(quote)] if symbol.endswith(quote) else symbol
    for p in PREFIXES:
        if b.startswith(p) and len(b) > len(p):
            return b[len(p):]
    return b


def tier_for(symbol: str, rank: Optional[int] = None) -> str:
    """mayor (BTC/ETH) | large (peringkat volume ≤ 10) | small (lainnya)."""
    if base_asset(symbol) in MAJOR_BASES:
        return "mayor"
    if rank is not None and rank <= 10:
        return "large"
    return "small"


def symbol_slug(symbol: str) -> str:
    """Nama aman untuk file: karakter non-ASCII diganti kode heksa (mis. 龙虾USDT → u-9f99-867e_USDT)."""
    if symbol.isascii() and all(c.isalnum() or c in "-_" for c in symbol):
        return symbol
    parts: list[list] = []  # [is_ascii, text]
    for c in symbol:
        if c.isascii() and (c.isalnum() or c in "-_"):
            if parts and parts[-1][0]:
                parts[-1][1] += c
            else:
                parts.append([True, c])
        else:
            hexc = f"{ord(c):x}"
            if parts and not parts[-1][0]:
                parts[-1][1] += "-" + hexc
            else:
                parts.append([False, "u-" + hexc])
    return "_".join(p[1] for p in parts)


# --------------------------------------------------------------------------- data bar
@dataclass(frozen=True)
class Bar:
    symbol: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    quote_volume: float = 0.0
    trades: int = 0
    taker_buy_quote: float = 0.0

    @property
    def close_time(self) -> int:
        return self.open_time + MINUTE_MS - 1


@dataclass(frozen=True)
class MarkBar:
    symbol: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    source: str = "mark"  # "mark" | "last" (fallback bila mark kline tidak tersedia)


# --------------------------------------------------------------------------- logging
def setup_logging(name: str, level: int = logging.INFO, to_stderr: bool = True) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if getattr(logger, "_crypto_analyst_ready", False):
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(LOG_DIR / f"{name}.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if to_stderr:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    logger._crypto_analyst_ready = True  # type: ignore[attr-defined]
    return logger


# --------------------------------------------------------------------------- lock
@contextlib.contextmanager
def single_instance_lock(name: str) -> Iterator[None]:
    """Mencegah dua proses `name` berjalan bersamaan (lock eksklusif pada file sqlite kecil)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATA_DIR / f"{name}.lock.sqlite"), timeout=0.2, isolation_level=None)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS lock(x INTEGER)")
        conn.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError as e:
        conn.close()
        raise AlreadyRunning(f"proses '{name}' sudah berjalan ({e})") from e
    try:
        yield
    finally:
        try:
            conn.execute("ROLLBACK")
        finally:
            conn.close()
