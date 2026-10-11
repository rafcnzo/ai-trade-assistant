"""Tes hermes/sync.py (H1–H4) dan pembungkus cron pemindai_cron.py. Tanpa Hermes, tanpa jaringan."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hermes"))

import sync  # noqa: E402

SRC = ROOT / "hermes"


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.home = Path(self.tmp.name) / "hermes-home"

    def tearDown(self):
        self.tmp.cleanup()

    def test_h1_dry_run_writes_nothing(self):
        actions = sync.plan(SRC, self.home)
        self.assertGreaterEqual(len(actions), 4)
        self.assertTrue(all(a.kind == "copy" for a in actions))
        lines = sync.apply(actions, dry_run=True)
        self.assertTrue(any("copy" in ln for ln in lines))
        self.assertFalse(self.home.exists())

    def test_h2_apply_substitutes_and_backs_up(self):
        sync.apply(sync.plan(SRC, self.home))
        soul = self.home / "SOUL.md"
        wrapper = self.home / "scripts" / "pemindai_cron.py"
        self.assertTrue(soul.exists())
        self.assertTrue((self.home / "skills" / "tiket" / "SKILL.md").exists())
        self.assertTrue((self.home / "skills" / "evaluasi-harian" / "SKILL.md").exists())
        txt = wrapper.read_text(encoding="utf-8")
        self.assertNotIn("{{", txt)
        self.assertIn(str(ROOT).replace("\\", "/"), txt)
        # kedua kali: semua sama
        self.assertTrue(all(a.kind == "same" for a in sync.plan(SRC, self.home)))
        # SOUL.md diubah di tujuan → backup lalu ditimpa
        soul.write_text("edit lokal", encoding="utf-8")
        actions = sync.plan(SRC, self.home)
        self.assertEqual([a.kind for a in actions if a.dst.name == "SOUL.md"], ["backup"])
        sync.apply(actions)
        baks = list(self.home.glob("SOUL.md.bak-*"))
        self.assertEqual(len(baks), 1)
        self.assertEqual(baks[0].read_text(encoding="utf-8"), "edit lokal")
        self.assertNotEqual(soul.read_text(encoding="utf-8"), "edit lokal")
        self.assertEqual(sync.main(["--home", str(self.home), "--check"]), 0)
        soul.write_text("edit lagi", encoding="utf-8")
        self.assertEqual(sync.main(["--home", str(self.home), "--check"]), 1)

    def test_h3_skill_frontmatter_and_snippet(self):
        for skill in SRC.glob("skills/*/SKILL.md"):
            txt = skill.read_text(encoding="utf-8")
            self.assertTrue(txt.startswith("---\n"), skill)
            head = txt.split("---")[1]
            self.assertIn("name:", head)
            self.assertIn("description:", head)
            self.assertIn(skill.parent.name, head)
        snip = sync.render_snippets(SRC, self.home)
        self.assertNotIn("{{", snip)
        self.assertIn("python", snip.lower())
        self.assertIn("mcp_servers", snip)
        self.assertIn("hermes cron create", snip)
        self.assertIn("usul_pelajaran", snip)
        self.assertNotIn("sk-ant-api", snip)

    def test_h4_wrapper_gate_off_on_failure(self):
        sync.apply(sync.plan(SRC, self.home))
        wrapper = self.home / "scripts" / "pemindai_cron.py"
        env = {**os.environ, "PEMINDAI_CMD": f"{sys.executable} -c exit(3)"}
        r = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[-1], '{"wakeAgent": false}')
        self.assertIn("pemindai gagal", lines[0])
        env["PEMINDAI_CMD"] = f"{sys.executable} -c print('halo');print('{{\"wakeAgent\":true}}')"
        r = subprocess.run([sys.executable, str(wrapper)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip().splitlines(), ["halo", '{"wakeAgent":true}'])


if __name__ == "__main__":
    unittest.main()
