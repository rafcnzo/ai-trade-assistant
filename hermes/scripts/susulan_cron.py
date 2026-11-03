"""Gate cron Hermes `evaluasi-susulan`: membangunkan agent bila evaluasi harian hari-hari lalu belum dibuat (laptop tidur/mati saat 21:30).

Memeriksa LOOKBACK_HARI hari ke belakang, bukan hanya kemarin, karena laptop bisa mati berhari-hari. Hari tanpa aktivitas (tanpa jurnal
agent dan tanpa order/posisi persona) dilewati: tidak ada yang bisa dievaluasi. Paling banyak MAKS_TANGGAL tanggal per bangun, terlama dulu.
Gate diperiksa tiap jam supaya tidak terlewat saat laptop hanya menyala sebentar, tetapi agent dibangunkan paling sering JEDA_S sekali
(data/susulan_gate.json, penulis tunggal: skrip ini) supaya kegagalan agent tidak menjadi panggilan LLM tiap jam.

Sebelum memutuskan, gate menjalankan scripts/uji_hipotesis.py --cron (hipotesis jatuh tempo yang terlewat karena cron 21:15 tidak jalan);
hasilnya ikut dikirim ke agent hanya bila gate menyala, selain itu hanya dicatat di logs/susulan_cron.log.

Tanda evaluasi sudah dibuat = ada pasar/harian/<tanggal>.md (ditulis tool tulis_catatan_harian). Tanpa LLM; stdout:
baris terakhir {"wakeAgent": true} + instruksi tanggal, atau {"wakeAgent": false}. Lihat cron.cmd untuk jadwal;
setelah agent membuat catatan, gate kembali false. Disalin ke HERMES_HOME/scripts/ oleh hermes/sync.py.
"""
import datetime
import json
import os
import sqlite3
import subprocess
import sys

PROJECT = r"{{PROJECT_ROOT}}"
VENV_PY = r"{{VENV_PY}}"
GATE_ON = '{"wakeAgent": true}'
GATE_OFF = '{"wakeAgent": false}'
WIB = datetime.timezone(datetime.timedelta(hours=7))
LOOKBACK_HARI = 7
MAKS_TANGGAL = 3
JEDA_S = 3 * 3600


def _log(root: str, msg: str) -> None:
    try:
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)
        with open(os.path.join(root, "logs", "susulan_cron.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except OSError:
        pass


def uji_terlewat(root: str) -> str:
    """Jalankan uji_hipotesis.py --cron (idempoten: hanya hipotesis jatuh tempo yang belum dinilai). Kembalikan stdout-nya."""
    py = os.environ.get("SUSULAN_PY", VENV_PY)
    skrip = os.path.join(root, "scripts", "uji_hipotesis.py")
    if py.startswith("{{") or not os.path.exists(py) or not os.path.exists(skrip):
        return ""
    try:
        r = subprocess.run([py, skrip, "--cron"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}, cwd=root)
    except (subprocess.TimeoutExpired, OSError) as e:
        _log(root, f"uji gagal: {e}")
        return ""
    if r.returncode != 0:
        _log(root, f"uji exit {r.returncode}: {(r.stderr or '').strip()[-300:]}")
        return ""
    out = (r.stdout or "").strip()
    if out:
        _log(root, "uji: " + out.replace("\n", " | ")[:400])
    return out


def ada_aktivitas(root: str, hari: str) -> bool:
    """Ada yang bisa dievaluasi: jurnal agent hari itu, atau order/posisi akun selain bayangan acak."""
    if os.path.exists(os.path.join(root, "jurnal", "agent", f"{hari}.md")):
        return True
    try:
        c = sqlite3.connect(f"file:{os.path.join(root, 'data', 'paper.sqlite')}?mode=ro", uri=True, timeout=5)
        try:
            return any(c.execute(f"SELECT 1 FROM {t} WHERE day_wib=? AND account<>'acak' LIMIT 1", (hari,)).fetchone() for t in ("orders", "positions"))
        finally:
            c.close()
    except sqlite3.Error:
        return False


def tanggal_terlewat(root: str, now: datetime.datetime) -> list:
    """Tanggal hari-hari lalu (terlama dulu) yang punya aktivitas tetapi belum punya catatan harian."""
    out = []
    for n in range(LOOKBACK_HARI, 0, -1):
        hari = (now - datetime.timedelta(days=n)).strftime("%Y-%m-%d")
        if not os.path.exists(os.path.join(root, "pasar", "harian", f"{hari}.md")) and ada_aktivitas(root, hari):
            out.append(hari)
    return out


def boleh_bangun(root: str, now: datetime.datetime) -> bool:
    try:
        with open(os.path.join(root, "data", "susulan_gate.json"), encoding="utf-8") as f:
            return now.timestamp() - float(json.load(f).get("terakhir_ts", 0)) >= JEDA_S
    except (OSError, ValueError, AttributeError, TypeError):
        return True


def catat_bangun(root: str, now: datetime.datetime, tanggal: list) -> None:
    try:
        with open(os.path.join(root, "data", "susulan_gate.json"), "w", encoding="utf-8") as f:
            json.dump({"terakhir_ts": now.timestamp(), "tanggal": tanggal}, f)
    except OSError as e:
        _log(root, f"state gagal ditulis: {e}")


def main() -> int:
    root = os.environ.get("SUSULAN_ROOT", PROJECT)
    now = datetime.datetime.now(WIB)
    if now.hour < 7:   # sebelum 07:00 biarkan: evaluasi 21:30 mungkin baru jalan / hari belum mulai
        print(GATE_OFF)
        return 0
    if not os.path.exists(os.path.join(root, "data", "paper.sqlite")):
        print(GATE_OFF)
        return 0
    terlewat = tanggal_terlewat(root, now)
    if not terlewat or not boleh_bangun(root, now):
        print(GATE_OFF)
        return 0
    tanggal = terlewat[:MAKS_TANGGAL]
    catat_bangun(root, now, tanggal)
    uji = uji_terlewat(root)
    if uji:
        print("Hasil uji hipotesis yang terlewat (sudah dinilai skrip, sebutkan ringkas di evaluasi):\n" + uji + "\n")
    daftar = ", ".join(tanggal)
    print(f"EVALUASI SUSULAN: evaluasi harian untuk {daftar} belum dibuat (laptop tidur/mati pukul 21:30). "
          f"Jalankan skill evaluasi-harian untuk SETIAP tanggal itu, terlama dulu: pakai hari=<tanggal> pada mcp_paper_laporan_paper, "
          f"mcp_paper_riwayat, mcp_paper_biaya_api, mcp_paper_baca_memori(\"jurnal\", hari), dan buat satu catatan per tanggal dengan "
          f"mcp_paper_tulis_catatan_harian(..., hari=<tanggal>). Awali balasan Telegram dengan \"Evaluasi susulan {daftar}\".")
    print(GATE_ON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
