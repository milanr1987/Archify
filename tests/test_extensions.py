import json

from helpers import SENTINELS, TempDirTestCase, make_dir_link, skill_md, write

from atlas.config import parse_config
from atlas.inventory import build_inventory
from atlas.model import canonical_json


class ExtensionScanTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        h = self.tmp / "home"
        write(h / ".claude/skills/own/SKILL.md", skill_md("own", "Moj skill"))
        write(h / ".claude/commands/review.md", "---\ndescription: Pregled diffa\n---\nTijelo SENTINEL-BODY\n")
        write(h / ".claude/commands/git/commit.md", "Bez frontmattera\n")
        write(h / ".claude/agents/planner.md",
              "---\nname: planner\ndescription: Planira. Argumenti opciono: cilj\n---\nprompt\n")
        write(h / ".claude/agents/README.md", "# nije agent\n")
        write(h / ".claude/settings.json", json.dumps({"hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "run " + SENTINELS[0]}]},
                {"matcher": "Bash", "hooks": [{"type": "prompt", "prompt": SENTINELS[1]}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "x", "env": {"K": SENTINELS[2]}}]}],
            "<script>": [{"hooks": [{"type": "x y", "command": "z"}]}],
        }}))
        write(h / ".claude-max/skills/maxskill/SKILL.md", skill_md("maxskill", "Max"))
        plugins = h / ".claude-max/plugins"
        self.install = plugins / "cache/official/toolkit/1.0"
        write(self.install / "commands/deploy.md", "---\ndescription: Deploy\n---\n")
        write(self.install / "agents/reviewer.md", "---\nname: reviewer\ndescription: Reviews\n---\n")
        write(self.install / "hooks/hooks.json", json.dumps({"hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": SENTINELS[3]}]}]}}))
        write(plugins / "installed_plugins.json", json.dumps({"version": 2, "plugins": {
            "toolkit@official": [{"scope": "user", "installPath": str(self.install), "version": "1.0"}]}}))
        (h / ".claude-pro").mkdir()
        make_dir_link(h / ".claude-pro/skills", h / ".claude-max/skills")
        self.home = h
        self.outcome = build_inventory(parse_config({
            "workspaceRoot": str(self.tmp / "ws"),
            "skillRoots": [
                {"path": str(h / ".claude/skills"), "profile": "claude", "label": ".claude"},
                {"path": str(h / ".claude-max/skills"), "profile": "max", "label": ".claude-max"},
                {"path": str(h / ".claude-pro/skills"), "profile": "pro", "label": ".claude-pro"},
            ],
            "pluginRegistries": [{"path": str(plugins / "installed_plugins.json"), "profile": "max"}],
            "mcpSources": [{"path": str(h / ".claude/settings.json"), "format": "claude-json", "profile": "claude"}],
        }))
        self.inv = self.outcome.inventory

    def named(self, kind, name):
        return [i for i in self.inv.items if i.kind == kind and i.name == name]

    def test_standalone_commands_with_namespace_and_description(self):
        [review] = self.named("command", "review")
        self.assertEqual(review.description, "Pregled diffa")
        self.assertEqual([(l.profile, l.origin, l.root_label) for l in review.locations],
                         [("claude", "standalone", ".claude")])
        [commit] = self.named("command", "git:commit")
        self.assertEqual(commit.description, "")

    def test_agents_use_lenient_frontmatter_and_skip_readme(self):
        [planner] = self.named("agent", "planner")
        self.assertEqual(planner.description, "Planira. Argumenti opciono: cilj")
        self.assertEqual(self.named("agent", "README"), [])
        self.assertFalse(any(w.code == "bad-frontmatter" for w in self.inv.warnings))

    def test_plugin_commands_agents_hooks_are_contained(self):
        [plugin] = [i for i in self.inv.items if i.kind == "plugin"]
        contained = {r.target for r in self.inv.relations if r.source == plugin.id and r.type == "contains"}
        for kind, name in (("command", "deploy"), ("agent", "reviewer"), ("hook", "SessionStart")):
            [item] = self.named(kind, name)
            self.assertIn(item.id, contained)
            self.assertEqual(item.locations[0].origin, f"plugin:{plugin.id}")

    def test_hooks_grouped_by_event_and_matcher(self):
        [bash] = self.named("hook", "PreToolUse · Bash")
        self.assertEqual(bash.metadata, {"event": "PreToolUse", "matcher": "Bash", "hookCount": "2",
                                         "hookTypes": ["command", "prompt"]})
        [stop] = self.named("hook", "Stop")
        self.assertNotIn("matcher", stop.metadata)
        [odd] = self.named("hook", "unknown")
        self.assertEqual(odd.metadata["hookTypes"], ["unknown"])

    def test_no_hook_or_body_content_in_inventory(self):
        text = canonical_json(self.inv)
        for secret in (*SENTINELS, "SENTINEL-BODY", "run "):
            self.assertNotIn(secret, text)

    def test_missing_command_and_agent_folders_are_silent(self):
        self.assertFalse(any(w.severity == "warn" and ("commands" in w.source or "agents" in w.source)
                             for w in self.inv.warnings))
        self.assertFalse(self.inv.partial)
