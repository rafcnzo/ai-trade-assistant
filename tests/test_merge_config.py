"""Tes hermes/merge_config.py: penggabungan tekstual config.yaml Hermes, idempoten."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hermes"))

import merge_config as M  # noqa: E402

TEMPLATE = """# contoh config
_config_version: 50
model:
  default: "claude-opus-5-5"
  provider: "custom"
cron:
  catch_up_missed: true  # komentar
terminal:
  backend: "local"
agent:
  max_turns: 150
  reasoning_effort: "low"
platform_toolsets:
  cli: [browser, terminal, file]
  telegram: [clarify, memory, skills]
  discord: [hermes-discord]
# mcp_servers:
#   time:
#     command: uvx
custom_providers:
  - name: x
"""


class TestMerge(unittest.TestCase):
    def test_merge_and_idempotent(self):
        home = Path(tempfile.gettempdir()) / "hermes-home-uji"
        new, changes = M.merge(TEMPLATE, ROOT, home)
        self.assertIn("ubah cron.catch_up_missed: true → false", changes)
        self.assertIn("tambah cron.allow_agent_scheduling", changes)
        self.assertIn("tambah agent.disabled_toolsets", changes)
        self.assertIn("tambah platform_toolsets.cron", changes)
        self.assertIn("tambah mcp_servers.paper", changes)
        self.assertIn("tambah platforms.telegram.extra (rich_messages, command_menu)", changes)
        self.assertIn("  catch_up_missed: false  # crypto-analyst", new)
        self.assertIn("  cli: [clarify, memory, skills, mcp-paper]  # crypto-analyst", new)
        self.assertIn("  telegram: [clarify, memory, skills, mcp-paper]  # crypto-analyst", new)
        self.assertIn("\nmcp_servers:\n  paper:\n", new)
        self.assertIn("python.exe", new)
        self.assertIn("priority_mode: replace", new)
        self.assertIn("rich_messages: true", new)
        # komentar lama tetap ada, kunci lain tidak tersentuh
        self.assertIn("# contoh config", new)
        self.assertIn('  backend: "local"', new)
        self.assertIn("  discord: [hermes-discord]", new)
        # tidak ada duplikasi kunci tingkat atas yang aktif
        for key in ("cron:", "agent:", "platform_toolsets:", "mcp_servers:", "platforms:"):
            self.assertEqual(sum(1 for ln in new.splitlines() if ln.split("#")[0].strip() == key), 1, key)
        new2, changes2 = M.merge(new, ROOT, home)
        self.assertEqual(changes2, [])
        self.assertEqual(new2, new)


if __name__ == "__main__":
    unittest.main()
