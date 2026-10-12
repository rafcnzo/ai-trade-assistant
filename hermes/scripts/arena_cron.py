"""Pembungkus cron Hermes `--no-agent` → scripts/evaluasi.py --nilai-arena --cron (seleksi persona arena, mingguan).

Disalin ke HERMES_HOME/scripts/ oleh hermes/sync.py. Stdout = pesan Telegram hanya bila ada persona yang dipensiunkan;
kosong = diam. Kegagalan → logs/arena_cron.log, exit 0.
"""
import datetime
import os
import subprocess
import sys

VENV_PY = r"{{VENV_PY}}"
PROJECT = r"{{PROJECT_ROOT}}"
TIMEOUT_S = 120


def _log(msg: str) -> None:
    try:
        os.makedirs(os.path.join(PROJECT, "logs"), exist_ok=True)
        with open(os.path.join(PROJECT, "logs", "arena_cron.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except OSError:
        pass


def main() -> int:
    override = os.environ.get("ARENA_CMD")
    args = override.split() if override else [VENV_PY, os.path.join(PROJECT, "scripts", "evaluasi.py"), "--nilai-arena", "--cron"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=TIMEOUT_S, env=env, cwd=PROJECT if os.path.isdir(PROJECT) else None)
    except (subprocess.TimeoutExpired, OSError) as e:
        _log(f"gagal: {e}")
        return 0
    if r.returncode != 0:
        _log(f"exit {r.returncode}: {(r.stderr or '').strip()[-500:]}")
        return 0
    out = (r.stdout or "").strip()
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
