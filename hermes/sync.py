"""hermes/sync.py — salin aset Hermes dari repo ke HERMES_HOME dan cetak snippet konfigurasi + perintah cron.

Yang disalin: SOUL.md, skills/*/SKILL.md, scripts/*.py (placeholder {{VENV_PY}}, {{PROJECT_ROOT}}, {{HERMES_HOME}} diganti).
TIDAK menyentuh config.yaml maupun .env (dicetak sebagai snippet untuk digabung).

  python hermes/sync.py --dry-run     # tampilkan rencana
  python hermes/sync.py               # terapkan
  python hermes/sync.py --check       # exit 1 jika ada yang belum sinkron (dipakai tes/CI)
  python hermes/sync.py --snippet     # hanya cetak snippet config + cron
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent


def hermes_home(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit)
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"])
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def placeholders(project_root: Path, home: Path) -> dict[str, str]:
    venv = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv.exists():
        venv = project_root / ".venv" / "bin" / "python"
    return {
        "{{VENV_PY}}": str(venv).replace("\\", "/"),
        "{{PROJECT_ROOT}}": str(project_root).replace("\\", "/"),
        "{{HERMES_HOME}}": str(home),
    }


def render(text: str, ph: dict[str, str]) -> str:
    for k, v in ph.items():
        text = text.replace(k, v)
    return text


@dataclass
class Action:
    kind: str          # copy | update | same | backup
    src: Path
    dst: Path
    content: str


def plan(src_root: Path, home: Path, project_root: Optional[Path] = None) -> list[Action]:
    project_root = project_root or PROJECT_ROOT
    ph = placeholders(project_root, home)
    items: list[tuple[Path, Path, bool]] = [(src_root / "SOUL.md", home / "SOUL.md", False)]
    for skill in sorted((src_root / "skills").glob("*/SKILL.md")):
        items.append((skill, home / "skills" / skill.parent.name / "SKILL.md", False))
    for script in sorted((src_root / "scripts").glob("*.py")):
        items.append((script, home / "scripts" / script.name, True))
    actions: list[Action] = []
    for src, dst, subst in items:
        content = src.read_text(encoding="utf-8")
        if subst:
            content = render(content, ph)
        if not dst.exists():
            actions.append(Action("copy", src, dst, content))
        elif dst.read_text(encoding="utf-8") == content:
            actions.append(Action("same", src, dst, content))
        else:
            actions.append(Action("backup" if dst.name == "SOUL.md" else "update", src, dst, content))
    return actions


def apply(actions: list[Action], dry_run: bool = False) -> list[str]:
    lines = []
    for a in actions:
        if a.kind == "same":
            lines.append(f"sama    {a.dst}")
            continue
        if a.kind == "backup":
            bak = a.dst.with_name(f"{a.dst.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M')}")
            lines.append(f"backup  {a.dst} → {bak.name}")
            if not dry_run:
                bak.write_text(a.dst.read_text(encoding="utf-8"), encoding="utf-8")
        lines.append(f"{a.kind:7} {a.dst}")
        if not dry_run:
            a.dst.parent.mkdir(parents=True, exist_ok=True)
            a.dst.write_text(a.content, encoding="utf-8", newline="\n")
    return lines


def render_snippets(src_root: Path, home: Path, project_root: Optional[Path] = None) -> str:
    ph = placeholders(project_root or PROJECT_ROOT, home)
    cfg = render((src_root / "config.snippet.yaml").read_text(encoding="utf-8"), ph)
    cron = render((src_root / "cron.cmd").read_text(encoding="utf-8"), ph)
    return (f"# ---- gabungkan ke {home / 'config.yaml'} ----\n{cfg}\n"
            f"# ---- jalankan setelah `hermes gateway install` ----\n{cron}\n"
            "# ---- rahasia (jalankan sendiri, jangan lewat chat) ----\n"
            "# hermes config set TELEGRAM_BOT_TOKEN <token>\n# hermes config set TELEGRAM_ALLOWED_USERS <user_id>\n"
            "# setx ANTHROPIC_API_KEY <key>   (untuk budget_proxy.py; buka terminal baru setelahnya)\n")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Sinkronkan aset Hermes dari repo ke HERMES_HOME.")
    ap.add_argument("--home", default=None, help="HERMES_HOME (default: env HERMES_HOME atau %%LOCALAPPDATA%%\\hermes)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 jika ada yang belum sinkron")
    ap.add_argument("--snippet", action="store_true", help="hanya cetak snippet config + cron")
    args = ap.parse_args(argv)
    home = hermes_home(args.home)
    if args.snippet:
        print(render_snippets(HERE, home))
        return 0
    actions = plan(HERE, home)
    if args.check:
        pending = [a for a in actions if a.kind != "same"]
        for a in pending:
            print(f"belum sinkron: {a.kind} {a.dst}")
        return 1 if pending else 0
    for line in apply(actions, dry_run=args.dry_run):
        print(line)
    print()
    print(render_snippets(HERE, home))
    return 0


if __name__ == "__main__":
    sys.exit(main())
