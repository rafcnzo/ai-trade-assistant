"""Gate cron Hermes `evaluasi-susulan`: membangunkan agent hanya bila evaluasi harian KEMARIN belum dibuat (laptop mati saat 21:30).

Sebelum memutuskan, gate menjalankan scripts/uji_hipotesis.py --cron (hipotesis jatuh tempo yang terlewat karena cron 21:15 tidak jalan);
hasilnya ikut dikirim ke agent hanya bila gate menyala, selain itu hanya dicatat di logs/susulan_cron.log.

Tanda evaluasi sudah dibuat = ada pasar/harian/<kemarin>.md (ditulis tool tulis_catatan_harian). Tanpa LLM; stdout:
baris terakhir {"wakeAgent": true} + instruksi tanggal, atau {"wakeAgent": false}. Berjalan beberapa kali sehari (lihat cron.cmd);
setelah agent membuat catatan untuk kemarin, gate kembali false. Disalin ke HERMES_HOME/scripts/ oleh hermes/sync.py.
"""
import datetime
import os
import subprocess
import sys

PROJECT = r"{{PROJECT_ROOT}}"
VENV_PY = r"{{VENV_PY}}"
GATE_ON = '{"wakeAgent": true}'
GATE_OFF = '{"wakeAgent": false}'
WIB = datetime.timezone(datetime.timedelta(hours=7))


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


def main() -> int:
    root = os.environ.get("SUSULAN_ROOT", PROJECT)
    now = datetime.datetime.now(WIB)
    kemarin = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if now.hour < 7:   # sebelum 07:00 biarkan: evaluasi 21:30 mungkin baru jalan / hari belum mulai
        print(GATE_OFF)
        return 0
    catatan = os.path.join(root, "pasar", "harian", f"{kemarin}.md")
    paper = os.path.join(root, "data", "paper.sqlite")
    if os.path.exists(catatan) or not os.path.exists(paper):
        print(GATE_OFF)
        return 0
    uji = uji_terlewat(root)
    if uji:
        print("Hasil uji hipotesis yang terlewat (sudah dinilai skrip, sebutkan ringkas di evaluasi):\n" + uji + "\n")
    print(f"EVALUASI SUSULAN: evaluasi harian untuk {kemarin} belum dibuat (laptop kemungkinan mati pukul 21:30). "
          f"Jalankan skill evaluasi-harian UNTUK TANGGAL {kemarin}: pakai hari=\"{kemarin}\" pada mcp_paper_laporan_paper, "
          f"mcp_paper_riwayat, mcp_paper_biaya_api, mcp_paper_baca_memori(\"jurnal\", hari), dan mcp_paper_tulis_catatan_harian(..., hari=\"{kemarin}\"). "
          f"Awali balasan Telegram dengan \"Evaluasi susulan {kemarin}\".")
    print(GATE_ON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
