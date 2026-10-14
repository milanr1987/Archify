import hashlib
from datetime import datetime, timezone

from helpers import TempDirTestCase, write

from atlas.maps import MapError
from atlas.mapspec import build_inputs, validate_spec

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def spec(**extra):
    data = {"project": "demo", "slug": "demo", "title": "Demo tok",
            "lanes": [{"id": "in", "label": "Ulaz"}, {"id": "out", "label": "Izlaz"}],
            "components": [
                {"id": "cli", "name": "CLI", "purpose": "Ulaz", "file": "src/cli.py", "needle": "def main",
                 "lane": "in", "col": 0, "type": "backend"},
                {"id": "db", "name": "Baza", "purpose": "Pohrana", "file": "src/db.py", "needle": "def save",
                 "lane": "out", "col": 1, "type": "database"}],
            "edges": [["cli", "db", "upis"]],
            "cards": ["Samo lokalno."]}
    data.update(extra)
    return data


class MapSpecTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "proj"
        write(self.root / "src/cli.py", "import x\n\ndef main():\n    pass\n")
        write(self.root / "src/db.py", "def save():\n    pass\n")

    def test_builds_analysis_with_real_lines_and_hashes(self):
        analysis, native = build_inputs(spec(), "a" * 64, self.root, NOW)
        cli = next(e for e in analysis["evidence"] if e["id"] == "cli")
        self.assertEqual(cli["line"], 3)
        self.assertEqual(cli["fileHash"], hashlib.sha256((self.root / "src/cli.py").read_bytes()).hexdigest())
        self.assertEqual(analysis["edges"][0]["status"], "observed")
        self.assertEqual(native["meta"]["output"], "output/maps/demo.html")
        self.assertEqual(native["nodes"][1], {"id": "db", "lane": "out", "col": 1, "type": "database", "label": "Baza"})
        self.assertEqual(native["cards"][0]["items"], ["Samo lokalno."])

    def test_missing_needle_or_file_is_clear_error(self):
        bad = spec()
        bad["components"][0]["needle"] = "def nema"
        with self.assertRaisesRegex(MapError, "nije u src/cli.py"):
            build_inputs(bad, "a" * 64, self.root, NOW)
        bad = spec()
        bad["components"][0]["file"] = "src/nema.py"
        with self.assertRaisesRegex(MapError, "nije čitljiv"):
            build_inputs(bad, "a" * 64, self.root, NOW)

    def test_private_or_escaping_files_rejected(self):
        for path in ("../izvan.py", ".env", "src/secrets/token.py"):
            bad = spec()
            bad["components"][0]["file"] = path
            with self.subTest(path=path), self.assertRaises(MapError):
                build_inputs(bad, "a" * 64, self.root, NOW)

    def test_invalid_specs_rejected(self):
        cases = [spec(slug="Los Slug"), spec(edges=[["cli", "nema", "x"]]), spec(extra=1),
                 spec(lanes=[]), spec(components=[])]
        bad_type = spec()
        bad_type["components"][0]["type"] = "server"
        bad_col = spec()
        bad_col["components"][0]["col"] = 6
        for case in cases + [bad_type, bad_col]:
            with self.subTest(case=case), self.assertRaises(MapError):
                validate_spec(case)
