import json

from helpers import TempDirTestCase, make_dir_link, skill_md, write

from atlas.config import allowed_roots, parse_config
from atlas.model import Relation
from atlas.scan.collector import Collector
from atlas.scan.plugins import scan_plugins
from atlas.scan.skills import SkillReader, scan_skills


class PluginTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.plugins = self.tmp / "home/.claude-max/plugins"
        self.install = self.plugins / "cache/official/superpowers/abc123"
        write(self.install / "skills/brainstorming/SKILL.md", skill_md("brainstorming", "Design first"))
        write(self.install / ".claude-plugin/plugin.json",
              json.dumps({"name": "superpowers", "description": "Core skills"}))
        self.evil = self.tmp / "home/.claude-max/plugins-evil/x"
        write(self.evil / "skills/evil/SKILL.md", skill_md("evil", "van korijena"))
        (self.plugins / "cache/official/proj/v1").mkdir(parents=True)
        (self.plugins / "cache/official/proj/v2").mkdir(parents=True)

    def registry(self, plugins):
        path = write(self.plugins / "installed_plugins.json", json.dumps({"version": 2, "plugins": plugins}))
        return str(path)

    def config(self, registry_path, skill_roots=()):
        return parse_config({
            "workspaceRoot": str(self.tmp / "ws"),
            "skillRoots": list(skill_roots),
            "pluginRegistries": [{"path": registry_path, "profile": "max"}],
        })

    def scan(self, config):
        c = Collector()
        reader = SkillReader(c)
        roots = allowed_roots(config)
        scan_skills(config, c, reader, roots)
        scan_plugins(config, c, reader, roots)
        return c

    def by(self, c, kind, name):
        return [i for i in c.items.values() if i.kind == kind and i.name == name]

    def default_registry(self):
        return self.registry({
            "superpowers@official": [{
                "scope": "user", "installPath": str(self.install), "version": "6.4.1",
                "installedAt": "2026-09-01T10:00:00Z", "lastUpdated": "2026-10-01T10:00:00Z",
                "gitCommitSha": "deadbeef",
            }],
            "evil@other": [{"scope": "user", "installPath": str(self.evil), "version": "1.0.0"}],
            "proj@official": [
                {"scope": "project", "installPath": str(self.plugins / "cache/official/proj/v1"), "projectPath": "C:/a"},
                {"scope": "project", "installPath": str(self.plugins / "cache/official/proj/v2"), "projectPath": "C:/b"},
            ],
            "gone@official": [{"scope": "user", "installPath": str(self.plugins / "cache/official/gone/v0")}],
        })

    def test_plugin_item_has_only_allowed_metadata(self):
        c = self.scan(self.config(self.default_registry()))
        [sp] = self.by(c, "plugin", "superpowers")
        self.assertEqual(sp.metadata, {
            "marketplace": "official", "scope": "user", "version": "6.4.1",
            "installedAt": "2026-09-01T10:00:00Z", "lastUpdated": "2026-10-01T10:00:00Z",
        })
        self.assertEqual(sp.description, "Core skills")
        self.assertEqual(sp.locations[0].profile, "max")

    def test_plugin_skill_has_origin_and_contains_relation(self):
        c = self.scan(self.config(self.default_registry()))
        [sp] = self.by(c, "plugin", "superpowers")
        [skill] = self.by(c, "skill", "brainstorming")
        self.assertEqual(skill.locations[0].origin, f"plugin:{sp.id}")
        self.assertEqual(skill.locations[0].root_label, "plugin superpowers@official")
        self.assertIn(Relation(sp.id, skill.id, "contains"), c.relations)

    def test_install_outside_plugins_root_is_rejected(self):
        c = self.scan(self.config(self.default_registry()))
        self.assertEqual(self.by(c, "skill", "evil"), [])
        self.assertIn("plugin-outside-root", [w.code for w in c.warnings])
        self.assertEqual(len(self.by(c, "plugin", "evil")), 1)

    def test_two_project_installs_are_distinct(self):
        c = self.scan(self.config(self.default_registry()))
        installs = self.by(c, "plugin", "proj")
        self.assertEqual(len(installs), 2)
        self.assertEqual({i.metadata["projectPath"] for i in installs}, {"C:/a", "C:/b"})

    def test_missing_install_path_warns(self):
        c = self.scan(self.config(self.default_registry()))
        self.assertIn("plugin-path-missing", [w.code for w in c.warnings])

    def test_large_manifest_warns_and_other_plugins_continue(self):
        write(self.install / ".claude-plugin/plugin.json", "x" * (1024 * 1024 + 1))
        c = self.scan(self.config(self.default_registry()))
        [sp] = self.by(c, "plugin", "superpowers")
        self.assertEqual(sp.description, "")
        self.assertEqual(len(self.by(c, "plugin", "proj")), 2)
        self.assertEqual(len(self.by(c, "skill", "brainstorming")), 1)
        self.assertIn("file-too-large", [w.code for w in c.warnings])

    def test_missing_registry_warns(self):
        c = self.scan(self.config(str(self.plugins / "installed_plugins.json")))
        self.assertIn("source-missing", [w.code for w in c.warnings])

    def test_entry_as_object_and_missing_plugins_key(self):
        reg = self.registry({"superpowers@official": {"scope": "user", "installPath": str(self.install)}})
        c = self.scan(self.config(reg))
        self.assertEqual(len(self.by(c, "plugin", "superpowers")), 1)
        bad = write(self.plugins / "installed_plugins.json", json.dumps({"version": 2}))
        c = self.scan(self.config(str(bad)))
        self.assertIn("bad-format", [w.code for w in c.warnings])

    def test_same_skill_file_standalone_and_from_plugin_keeps_both_origins(self):
        standalone_root = self.tmp / "home/.claude-max/skills"
        standalone_root.mkdir(parents=True)
        make_dir_link(standalone_root / "brainstorming", self.install / "skills/brainstorming")
        c = self.scan(self.config(
            self.default_registry(),
            skill_roots=[{"path": str(standalone_root), "profile": "max", "label": ".claude-max"}],
        ))
        [skill] = self.by(c, "skill", "brainstorming")
        [sp] = self.by(c, "plugin", "superpowers")
        self.assertEqual({l.origin for l in skill.locations}, {"standalone", f"plugin:{sp.id}"})
