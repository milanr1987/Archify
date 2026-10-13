import json
import unittest
from dataclasses import asdict

from helpers import SENTINELS, TempDirTestCase, write

from atlas.config import parse_config
from atlas.identity import norm_path
from atlas.model import Relation
from atlas.scan.collector import Collector
from atlas.scan.mcp import describe_server, scan_mcp

CODEX = """
[mcp_servers.figma]
command = "npx"
args = ["SENTINEL-ARG-7f3a"]
env_vars = ["FIGMA_KEY"]

[mcp_servers.figma.env]
FIGMA_TOKEN = "SENTINEL-ENV-55de"

[mcp_servers.docs]
url = "https://docs.example/SENTINEL-URL-91bc"
"""


class DescribeServerTests(unittest.TestCase):
    def test_stdio_with_env_names_only(self):
        meta = describe_server({"command": "C:\\tools\\npx.cmd", "args": ["x"], "env": {"GITHUB_TOKEN": "v"}})
        self.assertEqual(meta, {"transport": "stdio", "executableName": "npx.cmd", "envNames": ["GITHUB_TOKEN"]})

    def test_http_has_no_url(self):
        self.assertEqual(describe_server({"type": "http", "url": "https://x/?key=v"}), {"transport": "http"})
        self.assertEqual(describe_server({"type": "streamable-http"}), {"transport": "http"})
        self.assertEqual(describe_server({"url": "https://x"}), {"transport": "http"})
        self.assertEqual(describe_server({}), {"transport": "unknown"})

    def test_suspicious_executable_and_env_names_are_filtered(self):
        meta = describe_server({"command": "run/$(curl x)", "env": {"BAD-NAME": "v", "OK_NAME": "v"},
                                "env_vars": ["ALSO_OK", 3]})
        self.assertEqual(meta["executableName"], "unknown")
        self.assertEqual(meta["envNames"], ["ALSO_OK", "OK_NAME"])


class ScanMcpTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.project = self.tmp / "ws/proj-node"
        self.project.mkdir(parents=True)
        self.claude_json = write(self.tmp / "home/.claude.json", json.dumps({
            "mcpServers": {
                "github": {"command": "C:\\tools\\npx.cmd", "args": ["--token", SENTINELS[0]],
                           "env": {"GITHUB_TOKEN": SENTINELS[2]}},
                "remote": {"type": "http", "url": f"https://x.example/mcp?key={SENTINELS[1]}",
                           "headers": {"Authorization": f"Bearer {SENTINELS[3]}"}},
            },
            "projects": {
                self.project.as_posix(): {"mcpServers": {"local-db": {"command": "uvx", "args": [SENTINELS[0]]}}},
                "C:/drugo": {"allowedTools": []},
            },
        }))
        self.codex = write(self.tmp / "home/.codex/config.toml", CODEX)
        self.mcp_json = write(self.project / ".mcp.json", json.dumps(
            {"mcpServers": {"playwright": {"command": "npx", "args": [SENTINELS[0]]}}}))
        self.pid = "p" * 64

    def scan(self, sources):
        cfg = parse_config({"workspaceRoot": str(self.tmp / "ws"), "mcpSources": sources})
        c = Collector()
        scan_mcp(cfg, c, [(str(self.project), str(self.mcp_json))], {norm_path(self.project): self.pid})
        return c

    def default_sources(self):
        return [
            {"path": str(self.claude_json), "format": "claude-json", "profile": "claude"},
            {"path": str(self.codex), "format": "codex-toml", "profile": "codex"},
        ]

    def by_name(self, c):
        return {i.name: i for i in c.items.values()}

    def test_all_servers_found_with_scopes(self):
        items = self.by_name(self.scan(self.default_sources()))
        self.assertEqual(set(items), {"github", "remote", "local-db", "figma", "docs", "playwright"})
        self.assertEqual(items["github"].metadata["scope"], "user")
        self.assertEqual(items["github"].locations[0].profile, "claude")
        self.assertEqual(items["local-db"].metadata["scope"], "project")
        self.assertEqual(items["local-db"].metadata["projectPath"], self.project.as_posix())
        self.assertEqual(items["figma"].metadata, {
            "transport": "stdio", "executableName": "npx", "envNames": ["FIGMA_KEY", "FIGMA_TOKEN"],
            "scope": "user", "sourceFormat": "codex-toml"})
        self.assertEqual(items["docs"].metadata["transport"], "http")
        self.assertIsNone(items["playwright"].locations[0].profile)

    def test_project_servers_are_configured_for_project(self):
        c = self.scan(self.default_sources())
        items = self.by_name(c)
        self.assertIn(Relation(items["local-db"].id, self.pid, "configured-for"), c.relations)
        self.assertIn(Relation(items["playwright"].id, self.pid, "configured-for"), c.relations)

    def test_no_secret_reaches_items_or_warnings(self):
        c = self.scan(self.default_sources())
        dump = json.dumps([asdict(i) for i in c.items.values()] + [asdict(w) for w in c.warnings])
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, dump)

    def test_broken_json_and_toml_warn_without_content(self):
        bad_json = write(self.tmp / "bad.json", '{"mcpServers": {"x": "' + SENTINELS[0])
        bad_toml = write(self.tmp / "bad.toml", 'x = "' + SENTINELS[2])
        c = self.scan([
            {"path": str(bad_json), "format": "claude-json", "profile": "max"},
            {"path": str(bad_toml), "format": "codex-toml", "profile": "codex"},
        ])
        codes = {w.code for w in c.warnings}
        self.assertTrue({"bad-json", "bad-toml"} <= codes)
        dump = json.dumps([asdict(w) for w in c.warnings])
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, dump)
        self.assertEqual({i.name for i in c.items.values()}, {"playwright"})


if __name__ == "__main__":
    unittest.main()
