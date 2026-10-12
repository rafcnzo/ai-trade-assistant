"""hermes/merge_config.py — gabungkan pengaturan crypto-analyst ke HERMES_HOME/config.yaml secara tekstual dan idempoten.

Mengubah hanya baris-baris tertentu (komentar lain dipertahankan), dengan backup `config.yaml.bak-<waktu>`:
- cron.catch_up_missed → false; cron.allow_agent_scheduling → false
- agent.disabled_toolsets → toolset berbahaya dimatikan global
- platform_toolsets: cli/telegram/cron → [clarify, memory, skills, mcp-paper]
- mcp_servers.paper → ditambahkan di akhir file bila belum ada

  python hermes/merge_config.py [--home HERMES_HOME] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync  # noqa: E402

TOOLSETS_AGENT = "[clarify, memory, skills, mcp-paper]"
TOOLSETS_CRON = "[clarify, memory, skills, mcp-paper]"
DISABLED = "[terminal, file, browser, code_execution, delegation, cronjob, computer_use, image_gen, tts, vision, web, connections, session_search, todo]"
MARK = "# crypto-analyst"


def section_bounds(lines: list[str], key: str) -> tuple[int, int] | None:
    """(indeks baris 'key:', indeks baris sesudah akhir bagian) untuk kunci tingkat atas yang tidak dikomentari."""
    start = None
    for i, ln in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*(#.*)?$", ln):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", lines[j]):
            end = j
            break
    return start, end


def set_in_section(lines: list[str], key: str, sub: str, value: str, changes: list[str]) -> None:
    b = section_bounds(lines, key)
    if b is None:
        lines.append(f"{key}:")
        lines.append(f"  {sub}: {value}  {MARK}")
        changes.append(f"tambah {key}.{sub}")
        return
    start, end = b
    for i in range(start + 1, end):
        m = re.match(rf"^(\s+){re.escape(sub)}:\s*(.*)$", lines[i])
        if m:
            cur = m.group(2).split("#")[0].strip()
            if cur == value:
                return
            lines[i] = f"{m.group(1)}{sub}: {value}  {MARK}"
            changes.append(f"ubah {key}.{sub}: {cur} → {value}")
            return
    lines.insert(start + 1, f"  {sub}: {value}  {MARK}")
    changes.append(f"tambah {key}.{sub}")


def ensure_mcp_block(lines: list[str], block: str, changes: list[str]) -> None:
    b = section_bounds(lines, "mcp_servers")
    if b is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{MARK}: server MCP mesin paper (satu-satunya pintu agent ke mesin)")
        lines.extend(block.rstrip("\n").splitlines())
        changes.append("tambah mcp_servers.paper")
        return
    start, end = b
    if any(re.match(r"^\s{2}paper:\s*$", ln) for ln in lines[start:end]):
        # blok sudah ada: samakan daftar tools.include dengan snippet (tool baru di mcp_server.TOOL_NAMES ikut terdaftar)
        want = [ln for ln in block.splitlines() if re.match(r"^\s{8}- ", ln)]
        idx = [i for i in range(start, end) if re.match(r"^\s{8}- ", lines[i])]
        if want and idx and [lines[i] for i in idx] != want:
            lines[idx[0]:idx[-1] + 1] = want
            changes.append(f"ubah mcp_servers.paper.tools.include ({len(want)} tool)")
        return
    body = block.rstrip("\n").splitlines()[1:]  # tanpa baris 'mcp_servers:'
    lines[end:end] = body
    changes.append("tambah mcp_servers.paper ke blok yang sudah ada")


PLATFORMS_BLOCK = """platforms:  # crypto-analyst: menu perintah Telegram ringkas + pesan kaya
  telegram:
    extra:
      rich_messages: true
      rich_drafts: false
      command_menu:
        max_commands: 14
        priority_mode: replace
        priority: [posisi, budget, laporan, cek, tiket, batal, status, psikologi, referensi, arena-papan, evaluasi-harian, help, new, usage]
"""


def ensure_platforms_block(lines: list[str], changes: list[str]) -> None:
    """Tambahkan blok top-level `platforms:` (menu Telegram + rich messages) bila belum ada yang aktif."""
    if section_bounds(lines, "platforms") is not None:
        start, end = section_bounds(lines, "platforms")
        if any("command_menu" in ln for ln in lines[start:end]):
            # blok sudah ada: samakan baris `priority:` bila daftar perintah kita berubah
            want = next(ln for ln in PLATFORMS_BLOCK.splitlines() if ln.strip().startswith("priority:"))
            for i in range(start, end):
                if lines[i].split("#")[0].strip().startswith("priority:") and lines[i].split("#")[0].rstrip() != want.rstrip():
                    lines[i] = want
                    changes.append("ubah platforms.telegram.extra.command_menu.priority")
            return
        changes.append("platforms: sudah ada tanpa command_menu; tidak diubah (tambahkan manual, lihat hermes/merge_config.py)")
        return
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(PLATFORMS_BLOCK.rstrip("\n").splitlines())
    changes.append("tambah platforms.telegram.extra (rich_messages, command_menu)")


def mcp_block(project_root: Path, home: Path) -> str:
    ph = sync.placeholders(project_root, home)
    snippet = sync.render((Path(__file__).resolve().parent / "config.snippet.yaml").read_text(encoding="utf-8"), ph)
    out, on = [], False
    for ln in snippet.splitlines():
        if ln.startswith("mcp_servers:"):
            on = True
        if on:
            out.append(ln)
    return "\n".join(out) + "\n"


def merge(text: str, project_root: Path, home: Path) -> tuple[str, list[str]]:
    lines = text.splitlines()
    changes: list[str] = []
    set_in_section(lines, "cron", "catch_up_missed", "false", changes)
    set_in_section(lines, "cron", "allow_agent_scheduling", "false", changes)
    set_in_section(lines, "agent", "disabled_toolsets", DISABLED, changes)
    set_in_section(lines, "platform_toolsets", "cli", TOOLSETS_AGENT, changes)
    set_in_section(lines, "platform_toolsets", "telegram", TOOLSETS_AGENT, changes)
    set_in_section(lines, "platform_toolsets", "cron", TOOLSETS_CRON, changes)
    ensure_mcp_block(lines, mcp_block(project_root, home), changes)
    ensure_platforms_block(lines, changes)
    return "\n".join(lines) + "\n", changes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    home = sync.hermes_home(args.home)
    cfg = home / "config.yaml"
    if not cfg.exists():
        print(f"tidak ada {cfg}; jalankan `hermes setup` dulu")
        return 1
    text = cfg.read_text(encoding="utf-8")
    new, changes = merge(text, sync.PROJECT_ROOT, home)
    if not changes:
        print(f"config.yaml sudah sesuai ({cfg})")
        return 0
    for c in changes:
        print("-", c)
    if args.dry_run:
        print("(dry-run, tidak ditulis)")
        return 0
    bak = cfg.with_name(f"config.yaml.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(text, encoding="utf-8")
    cfg.write_text(new, encoding="utf-8", newline="\n")
    print(f"ditulis: {cfg} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
