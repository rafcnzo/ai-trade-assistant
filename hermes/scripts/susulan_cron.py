"""Gate cron Hermes `evaluasi-susulan`: membangunkan agent hanya bila evaluasi harian KEMARIN belum dibuat (laptop mati 23:55).

Tanda evaluasi sudah dibuat = ada pasar/harian/<kemarin>.md (ditulis tool tulis_catatan_harian). Tanpa LLM; stdout:
baris terakhir {"wakeAgent": true} + instruksi tanggal, atau {"wakeAgent": false}. Berjalan beberapa kali sehari (lihat cron.cmd);
setelah agent membuat catatan untuk kemarin, gate kembali false. Disalin ke HERMES_HOME/scripts/ oleh hermes/sync.py.
"""
import datetime
import os
import sys

PROJECT = r"{{PROJECT_ROOT}}"
GATE_ON = '{"wakeAgent": true}'
GATE_OFF = '{"wakeAgent": false}'
WIB = datetime.timezone(datetime.timedelta(hours=7))


def main() -> int:
    root = os.environ.get("SUSULAN_ROOT", PROJECT)
    now = datetime.datetime.now(WIB)
    kemarin = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if now.hour < 7:   # sebelum 07:00 biarkan: mungkin evaluasi 23:55 memang baru saja jalan / hari belum mulai
        print(GATE_OFF)
        return 0
    catatan = os.path.join(root, "pasar", "harian", f"{kemarin}.md")
    paper = os.path.join(root, "data", "paper.sqlite")
    if os.path.exists(catatan) or not os.path.exists(paper):
        print(GATE_OFF)
        return 0
    print(f"EVALUASI SUSULAN: evaluasi harian untuk {kemarin} belum dibuat (laptop kemungkinan mati pukul 23:55). "
          f"Jalankan skill evaluasi-harian UNTUK TANGGAL {kemarin}: pakai hari=\"{kemarin}\" pada mcp_paper_laporan_paper, "
          f"mcp_paper_riwayat, mcp_paper_biaya_api, mcp_paper_baca_memori(\"jurnal\", hari), dan mcp_paper_tulis_catatan_harian(..., hari=\"{kemarin}\"). "
          f"Awali balasan Telegram dengan \"Evaluasi susulan {kemarin}\".")
    print(GATE_ON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
