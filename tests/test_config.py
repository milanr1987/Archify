import json
import os
import tempfile
import unittest
from pathlib import Path

from atlas.config import ConfigError, allowed_roots, default_config, load_config, parse_config

REPO = Path(__file__).resolve().parents[1]
WS = "C:\\Radni folder\\Twiter_claude"


def minimal(**extra):
    data = {"workspaceRoot": WS}
    data.update(extra)
    return data


class ParseConfigTests(unittest.TestCase):
    def test_minimal_config_has_empty_sources(self):
        cfg = parse_config(minimal())
        self.assertEqual(cfg.workspace_root, os.path.normpath(WS))
        self.assertEqual(cfg.skill_roots, ())
        self.assertEqual(cfg.exclude_names, frozenset())

    def test_relative_paths_resolve_from_workspace_not_cwd(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as other:
            os.chdir(other)
            try:
                cfg = parse_config(minimal(
                    projectRoots=["."],
                    documents=[{"path": "docs\\a.md", "title": "A"}],
                ))
            finally:
                os.chdir(old)
        self.assertEqual(cfg.project_roots, (os.path.normpath(WS),))
        self.assertEqual(cfg.documents[0].path, os.path.normpath(WS + "\\docs\\a.md"))

    def test_workspace_root_required_and_absolute(self):
        with self.assertRaises(ConfigError):
            parse_config({})
        with self.assertRaises(ConfigError):
            parse_config({"workspaceRoot": "relativno"})

    def test_unknown_top_level_field_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            parse_config(minimal(skilRoots=[]))
        self.assertIn("skilRoots", str(ctx.exception))

    def test_unknown_mcp_format_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config(minimal(mcpSources=[{"path": "C:\\x.json", "format": "yaml", "profile": "max"}]))

    def test_entry_with_extra_or_missing_field_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config(minimal(skillRoots=[{"path": "C:\\s", "profile": "max"}]))
        with self.assertRaises(ConfigError):
            parse_config(minimal(skillRoots=[{"path": "C:\\s", "profile": "max", "label": "m", "x": 1}]))

    def test_bad_profile_name_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config(minimal(skillRoots=[{"path": "C:\\s", "profile": "Max Profil", "label": "m"}]))

    def test_two_registry_roots_for_one_profile_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config(minimal(pluginRegistries=[
                {"path": "C:\\a\\plugins\\installed_plugins.json", "profile": "max"},
                {"path": "C:\\b\\plugins\\installed_plugins.json", "profile": "max"},
            ]))

    def test_non_object_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config([])


class LoadConfigTests(unittest.TestCase):
    def test_missing_file_mentions_init(self):
        with self.assertRaises(ConfigError) as ctx:
            load_config(Path("C:\\ne\\postoji\\sources.local.json"))
        self.assertIn("init", str(ctx.exception))

    def test_bad_json_reports_line_without_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text('{\n "workspaceRoot": "TAJNA-VRIJEDNOST"\n', encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
        self.assertIn("red", str(ctx.exception))
        self.assertNotIn("TAJNA-VRIJEDNOST", str(ctx.exception))

    def test_committed_example_is_valid(self):
        cfg = load_config(REPO / "config" / "sources.example.json")
        self.assertEqual({r.profile for r in cfg.skill_roots}, {"agents", "claude", "max", "pro"})


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_is_valid_and_covers_profiles(self):
        cfg = parse_config(default_config(Path("C:\\Users\\Milan"), Path(WS)))
        self.assertEqual({r.profile for r in cfg.skill_roots}, {"agents", "claude", "max", "pro"})
        self.assertEqual({r.profile for r in cfg.plugin_registries}, {"claude", "max", "pro"})
        self.assertIn("codex-toml", {s.format for s in cfg.mcp_sources})
        self.assertIn("Archify", cfg.exclude_names)
        self.assertEqual(cfg.extra_projects, ())

    def test_default_config_discovers_common_project_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for name in ("Desktop", "Documents", "WebstormProjects", "source/repos"):
                (home / name).mkdir(parents=True)
            inside = home / "Desktop/ws"
            (inside / "skill-evals").mkdir(parents=True)
            data = default_config(home, inside)
            self.assertEqual(data["projectDepth"], 3)
            self.assertEqual(data["projectRoots"], [str(home / n) for n in
                             ("Desktop", "Documents", "WebstormProjects", "source/repos")])
            self.assertEqual(data["extraProjects"], ["skill-evals"])
            outside = default_config(home, home / "elsewhere")
            self.assertEqual(outside["projectRoots"][0], ".")
            parse_config(data)

    def test_allowed_roots_keeps_existing_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = parse_config({"workspaceRoot": tmp, "skillRoots": [
                {"path": os.path.join(tmp, "nema"), "profile": "max", "label": "m"}]})
            self.assertEqual(allowed_roots(cfg), [os.path.normpath(tmp)])


if __name__ == "__main__":
    unittest.main()
