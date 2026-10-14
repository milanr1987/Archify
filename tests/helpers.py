"""Zajednički helperi za testove. Nije test modul."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

SENTINELS = ("SENTINEL-ARG-7f3a", "SENTINEL-URL-91bc", "SENTINEL-ENV-55de", "SENTINEL-HDR-c0ff")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def skill_md(name: str, description: str) -> str:
    # JSON string je ispravan YAML skalar, pa i znakovi poput < i : prolaze.
    return f"---\nname: {json.dumps(name)}\ndescription: {json.dumps(description)}\n---\n\n# Skill\n"


def make_dir_link(link: Path, target: Path) -> str:
    """Pravi link na folder: symlink ako je dozvoljen, inače junction."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        pass
    try:
        import _winapi
    except ImportError:
        _winapi = None
    if _winapi is not None and hasattr(_winapi, "CreateJunction"):
        _winapi.CreateJunction(str(target), str(link))
        return "junction"
    raise unittest.SkipTest("ni symlink ni junction nisu dostupni na ovom sistemu")


class TempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="atlas test čćž ")
        self.tmp = Path(os.path.realpath(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

CODEX_FIXTURE = """
[mcp_servers.figma]
command = "npx"
args = ["SENTINEL-ARG-7f3a"]
env_vars = ["FIGMA_KEY"]

[mcp_servers.figma.env]
FIGMA_TOKEN = "SENTINEL-ENV-55de"

[mcp_servers.docs]
url = "https://docs.example/SENTINEL-URL-91bc"
"""

XSS_NAME = "</script><img src=x onerror=alert(1)>"


def make_fixture(tmp: Path) -> dict:
    """Lažni home + workspace sa svim vrstama izvora. Vraća config dict."""
    home = tmp / "home"
    ws = tmp / "workspace čćž"
    write(home / ".agents/skills/firecrawl/SKILL.md", skill_md("firecrawl", "Web scraping"))
    (home / ".claude/skills").mkdir(parents=True)
    make_dir_link(home / ".claude/skills/firecrawl", home / ".agents/skills/firecrawl")
    write(home / ".claude/skills/skill-creator/SKILL.md", skill_md("skill-creator", "Samostalna verzija"))
    write(home / ".claude-max/skills/maxskill/SKILL.md", skill_md("maxskill", "Max skill"))
    write(home / ".claude-max/skills/broken/SKILL.md", "---\nname: [nezatvoreno\n---\n")
    write(home / ".claude-max/skills/xss/SKILL.md", skill_md(XSS_NAME, "napad kroz naslov"))
    (home / ".claude-pro").mkdir()
    make_dir_link(home / ".claude-pro/skills", home / ".claude-max/skills")
    plugins = home / ".claude-max/plugins"
    sp = plugins / "cache/official/superpowers/abc"
    sc = plugins / "cache/official/skill-creator/def"
    write(sp / "skills/brainstorming/SKILL.md", skill_md("brainstorming", "Design first"))
    write(sc / "skills/skill-creator/SKILL.md", skill_md("skill-creator", "Plugin verzija"))
    write(plugins / "installed_plugins.json", json.dumps({"version": 2, "plugins": {
        "superpowers@official": [{"scope": "user", "installPath": str(sp), "version": "6.4.1"}],
        "skill-creator@official": [{"scope": "user", "installPath": str(sc), "version": "1.0.0"}],
    }}))
    write(ws / "proj-node/package.json", json.dumps({"name": "proj-node", "scripts": {"start": "node x"}}))
    write(ws / "proj-node/README.md", "# Proj Node\n")
    write(ws / "proj-node/.mcp.json", json.dumps(
        {"mcpServers": {"playwright": {"command": "npx", "args": [SENTINELS[0]]}}}))
    write(ws / "proj-py/pyproject.toml", '[project]\nname = "proj-py"\n')
    write(ws / "extra/run.py", "print(1)\n")
    write(ws / "guide.md", "# Vodič\n")
    write(home / ".claude.json", json.dumps({
        "mcpServers": {
            "github": {"command": "npx", "args": [SENTINELS[0]], "env": {"GITHUB_TOKEN": SENTINELS[2]}},
            "remote": {"type": "http", "url": "https://x/?k=" + SENTINELS[1],
                       "headers": {"Authorization": "Bearer " + SENTINELS[3]}},
        },
        "projects": {(ws / "proj-node").as_posix(): {"mcpServers": {"local-db": {"command": "uvx"}}}},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "guard " + SENTINELS[0], "env": {"T": SENTINELS[2]}},
            {"type": "http", "url": "https://h/" + SENTINELS[1], "headers": {"A": SENTINELS[3]}}]}]},
    }))
    write(home / ".codex/config.toml", CODEX_FIXTURE)
    return {
        "workspaceRoot": str(ws),
        "projectRoots": ["."],
        "extraProjects": ["extra"],
        "excludeNames": ["Archify", "node_modules"],
        "skillRoots": [
            {"path": str(home / ".agents/skills"), "profile": "agents", "label": ".agents"},
            {"path": str(home / ".claude/skills"), "profile": "claude", "label": ".claude"},
            {"path": str(home / ".claude-max/skills"), "profile": "max", "label": ".claude-max"},
            {"path": str(home / ".claude-pro/skills"), "profile": "pro", "label": ".claude-pro"},
        ],
        "pluginRegistries": [{"path": str(plugins / "installed_plugins.json"), "profile": "max"}],
        "mcpSources": [
            {"path": str(home / ".claude.json"), "format": "claude-json", "profile": "claude"},
            {"path": str(home / ".codex/config.toml"), "format": "codex-toml", "profile": "codex"},
        ],
        "documents": [{"path": "guide.md", "title": "Vodič"}],
    }
