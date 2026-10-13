import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from helpers import SENTINELS, TempDirTestCase, make_dir_link, make_fixture, write

from atlas.cli import main
from atlas.model import inventory_from_dict, inventory_hash

REPO = Path(__file__).resolve().parents[1]


def run(argv, app):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, app_root=app)
    return code, out.getvalue(), err.getvalue()


class CliTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.app = self.tmp / "app"
        self.config = make_fixture(self.tmp)
        write(self.app / "config/sources.local.json", json.dumps(self.config, ensure_ascii=False))
        self.inventory = self.app / "data/inventory.json"
        self.report = self.app / "data/scan-report.md"
        self.catalog = self.app / "output/index.html"

    def test_init_creates_once(self):
        app = self.tmp / "fresh"
        code, out, _ = run(["init"], app)
        self.assertEqual(code, 0)
        cfg = json.loads((app / "config/sources.local.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["workspaceRoot"], str(app.parent))
        write(app / "config/sources.local.json", '{"workspaceRoot": "C:\\\\moje"}')
        code, out, _ = run(["init"], app)
        self.assertEqual(code, 0)
        self.assertIn("već postoji", out)
        self.assertEqual((app / "config/sources.local.json").read_text(encoding="utf-8"), '{"workspaceRoot": "C:\\\\moje"}')

    def test_scan_writes_data_and_returns_partial(self):
        code, out, _ = run(["scan"], self.app)
        self.assertEqual(code, 2)
        self.assertTrue(self.inventory.exists() and self.report.exists())
        self.assertFalse(self.catalog.exists())
        self.assertIn("Djelimičan pregled", out)

    def test_build_without_inventory_fails(self):
        code, _, err = run(["build"], self.app)
        self.assertEqual(code, 1)
        self.assertIn("atlas scan", err)

    def test_build_after_scan(self):
        run(["scan"], self.app)
        code, _, _ = run(["build"], self.app)
        self.assertEqual(code, 0)
        self.assertTrue(self.catalog.exists())

    def test_refresh_outputs_share_one_hash(self):
        code, _, _ = run(["refresh"], self.app)
        self.assertEqual(code, 2)
        h = inventory_hash(inventory_from_dict(json.loads(self.inventory.read_text(encoding="utf-8"))))
        self.assertIn(f"Hash inventara: `{h}`", self.report.read_text(encoding="utf-8"))
        self.assertIn(f'content="{h}"', self.catalog.read_text(encoding="utf-8"))

    def test_bad_config_keeps_previous_outputs(self):
        run(["refresh"], self.app)
        before = [p.read_bytes() for p in (self.inventory, self.report, self.catalog)]
        write(self.app / "config/sources.local.json", "{")
        code, _, err = run(["refresh"], self.app)
        self.assertEqual(code, 1)
        self.assertIn("red", err)
        self.assertEqual([p.read_bytes() for p in (self.inventory, self.report, self.catalog)], before)

    def test_no_secrets_in_outputs_or_console(self):
        code, out, err = run(["refresh"], self.app)
        texts = [out, err] + [p.read_text(encoding="utf-8") for p in (self.inventory, self.report, self.catalog)]
        for text in texts:
            for sentinel in SENTINELS:
                self.assertNotIn(sentinel, text)

    def test_sources_are_not_modified(self):
        home = self.tmp / "home"
        files = sorted(p for p in home.rglob("*") if p.is_file()) + sorted((self.tmp / "workspace čćž").rglob("*.json"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        run(["refresh"], self.app)
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.assertEqual(before, after)

    def test_lock_busy_returns_1(self):
        # Fajl bez OS locka je ponovo upotrebljiv; zauzetost dokazuje samo aktivni vlasnik.
        from atlas.paths import AppPaths
        from atlas.writeout import atlas_lock
        with atlas_lock(AppPaths(self.app)):
            code, _, err = run(["scan"], self.app)
        self.assertEqual(code, 1)
        self.assertIn("lock", err)

    def test_relative_config_resolves_from_app_root(self):
        other = self.tmp / "drugi folder"
        other.mkdir()
        old = os.getcwd()
        os.chdir(other)
        try:
            code, _, _ = run(["scan", "--config", "config/sources.local.json"], self.app)
        finally:
            os.chdir(old)
        self.assertEqual(code, 2)

    def test_recovers_interrupted_publish_before_next_command(self):
        run(["refresh"], self.app)
        staged = write(self.app / "data/inventory.json.ab12.staged", "x")
        write(self.app / "data/.publish-journal.json", json.dumps({"phase": "backup", "entries": [
            {"target": str(self.inventory), "staged": str(staged), "backup": None}]}))
        code, _, err = run(["build"], self.app)
        self.assertEqual(code, 0)
        self.assertIn("Oporavljen", err)
        self.assertFalse(staged.exists())


@unittest.skipUnless(os.name == "nt", "atlas.cmd je Windows wrapper")
class AtlasCmdTests(TempDirTestCase):
    def test_cmd_from_other_folder_with_spaces(self):
        venv = REPO / ".venv"
        if not (venv / "Scripts/python.exe").exists():
            self.skipTest("lokalni .venv ne postoji")
        app = self.tmp / "app sa razmakom"
        shutil.copytree(REPO / "src", app / "src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(REPO / "atlas.cmd", app / "atlas.cmd")
        make_dir_link(app / ".venv", venv)
        write(app / "config/sources.local.json", json.dumps(make_fixture(self.tmp), ensure_ascii=False))
        other = self.tmp / "drugi folder"
        other.mkdir()
        result = subprocess.run([str(app / "atlas.cmd"), "refresh"], cwd=other, capture_output=True)
        self.assertIn(result.returncode, (0, 2), result.stderr.decode("utf-8", "replace"))
        self.assertTrue((app / "output/index.html").exists())

    def test_cmd_without_venv_fails_clearly(self):
        app = self.tmp / "bez venva"
        app.mkdir()
        shutil.copy2(REPO / "atlas.cmd", app / "atlas.cmd")
        result = subprocess.run([str(app / "atlas.cmd"), "scan"], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(re.search(rb"\.venv", result.stderr))


if __name__ == "__main__":
    unittest.main()
