"""Pembungkus cron Hermes → scripts/pemindai.py proyek (dijalankan dengan interpreter venv proyek).

Disalin ke HERMES_HOME/scripts/ oleh hermes/sync.py dengan placeholder yang sudah diganti.
Kontrak Hermes: stdout dikirim sebagai pesan; baris terakhir {"wakeAgent": false} = agent tidak dibangunkan.
Kegagalan apa pun → {"wakeAgent": false} dan exit 0, supaya tidak ada biaya LLM untuk error teknis.
"""
import os
import subprocess
import sys

VENV_PY = r"{{VENV_PY}}"
PROJECT = r"{{PROJECT_ROOT}}"
TIMEOUT_S = 120
GATE_OFF = '{"wakeAgent": false}'


def main() -> int:
    override = os.environ.get("PEMINDAI_CMD")
    args = override.split() if override else [VENV_PY, os.path.join(PROJECT, "scripts", "pemindai.py"), "--cron"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=TIMEOUT_S, env=env, cwd=PROJECT if os.path.isdir(PROJECT) else None)
    except subprocess.TimeoutExpired:
        print(f"pemindai gagal: timeout {TIMEOUT_S} s")
        print(GATE_OFF)
        return 0
    except OSError as e:
        print(f"pemindai gagal: {e}")
        print(GATE_OFF)
        return 0
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        err = (r.stderr or "").strip()[-500:]
        print(f"pemindai gagal (exit {r.returncode}): {err or 'tanpa output'}")
        print(GATE_OFF)
        return 0
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
