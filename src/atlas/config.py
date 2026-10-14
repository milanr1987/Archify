"""Učitavanje i validacija konfiguracije izvora."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

MCP_FORMATS = frozenset({"claude-json", "mcp-json", "codex-toml"})
TOP_KEYS = frozenset({
    "workspaceRoot", "projectRoots", "projectDepth", "extraProjects", "excludeNames",
    "skillRoots", "pluginRegistries", "mcpSources", "documents",
})
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
DEFAULT_EXCLUDES = [
    "Archify", "node_modules", ".git", ".venv", "venv", "dist", "build",
    "output", "graphify-out", "__pycache__",
]


MAX_PROJECT_DEPTH = 5
# Uobičajeni folderi sa projektima; init uzima samo one koji postoje na računaru.
PROJECT_FOLDERS = ("Desktop", "Documents", "OneDrive", "WebstormProjects", "PycharmProjects",
                   "IdeaProjects", "source/repos", "Projects", "code", "dev", "repos", "GitHub")


class ConfigError(Exception):
    """Config nije upotrebljiv; rad se prekida prije pisanja izlaza."""


@dataclass(frozen=True)
class SkillRoot:
    path: str
    profile: str
    label: str


@dataclass(frozen=True)
class PluginRegistry:
    path: str
    profile: str


@dataclass(frozen=True)
class McpSource:
    path: str
    format: str
    profile: str


@dataclass(frozen=True)
class DocumentRef:
    path: str
    title: str


@dataclass(frozen=True)
class Config:
    workspace_root: str
    project_roots: tuple[str, ...]
    project_depth: int
    extra_projects: tuple[str, ...]
    exclude_names: frozenset[str]
    skill_roots: tuple[SkillRoot, ...]
    plugin_registries: tuple[PluginRegistry, ...]
    mcp_sources: tuple[McpSource, ...]
    documents: tuple[DocumentRef, ...]


def parse_config(data: object) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("config mora biti JSON objekat")
    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise ConfigError(f"nepoznata polja u configu: {', '.join(unknown)}")
    workspace = data.get("workspaceRoot")
    if not isinstance(workspace, str) or not workspace.strip():
        raise ConfigError("workspaceRoot je obavezan")
    if not os.path.isabs(workspace):
        raise ConfigError("workspaceRoot mora biti apsolutna putanja")
    workspace = os.path.normpath(workspace)

    def resolve(value: str) -> str:
        return os.path.normpath(value if os.path.isabs(value) else os.path.join(workspace, value))

    def str_list(key: str) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise ConfigError(f"{key} mora biti lista nepraznih stringova")
        return value

    def obj_list(key: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ConfigError(f"{key} mora biti lista")
        out = []
        for index, entry in enumerate(value):
            if not isinstance(entry, dict) or set(entry) != set(fields):
                raise ConfigError(f"{key}[{index}]: očekivana tačno polja {', '.join(fields)}")
            if not all(isinstance(entry[f], str) and entry[f].strip() for f in fields):
                raise ConfigError(f"{key}[{index}]: sva polja moraju biti neprazni stringovi")
            if "profile" in entry and not PROFILE_RE.fullmatch(entry["profile"]):
                raise ConfigError(f"{key}[{index}]: profil smije imati mala slova, brojeve, - i _")
            out.append(entry)
        return out

    depth = data.get("projectDepth", 1)
    if type(depth) is not int or not 1 <= depth <= MAX_PROJECT_DEPTH:
        raise ConfigError(f"projectDepth mora biti cijeli broj od 1 do {MAX_PROJECT_DEPTH}")
    skill_roots = tuple(
        SkillRoot(resolve(e["path"]), e["profile"], e["label"])
        for e in obj_list("skillRoots", ("path", "profile", "label"))
    )
    registries = tuple(
        PluginRegistry(resolve(e["path"]), e["profile"])
        for e in obj_list("pluginRegistries", ("path", "profile"))
    )
    registry_roots: dict[str, str] = {}
    for reg in registries:
        root = os.path.normcase(os.path.dirname(reg.path))
        if registry_roots.setdefault(reg.profile, root) != root:
            raise ConfigError(f"profil {reg.profile} ima dva različita plugin registra")
    mcp_sources = []
    for index, e in enumerate(obj_list("mcpSources", ("path", "format", "profile"))):
        if e["format"] not in MCP_FORMATS:
            raise ConfigError(f"mcpSources[{index}]: nepoznat format {e['format']!r}")
        mcp_sources.append(McpSource(resolve(e["path"]), e["format"], e["profile"]))
    documents = tuple(
        DocumentRef(resolve(e["path"]), e["title"])
        for e in obj_list("documents", ("path", "title"))
    )
    return Config(
        workspace_root=workspace,
        project_roots=tuple(resolve(p) for p in str_list("projectRoots")),
        project_depth=depth,
        extra_projects=tuple(resolve(p) for p in str_list("extraProjects")),
        exclude_names=frozenset(str_list("excludeNames")),
        skill_roots=skill_roots,
        plugin_registries=registries,
        mcp_sources=tuple(mcp_sources),
        documents=documents,
    )


def load_config(path: Path) -> Config:
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConfigError(f"config ne postoji: {path}. Pokreni: atlas init") from None
    except OSError as exc:
        raise ConfigError(f"config nije čitljiv: {path} ({type(exc).__name__})") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config nije ispravan JSON: red {exc.lineno}, kolona {exc.colno}") from None
    return parse_config(data)


def _within(child: Path, parent: Path) -> bool:
    try:
        a, b = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


CLAUDE_PROFILE_DIR = re.compile(r"^\.claude(?:-([a-z0-9][a-z0-9_-]{0,31}))?$")


def _claude_profiles(home: Path) -> list[tuple[str, Path]]:
    """Claude profili koji postoje: ~/.claude je "claude", ~/.claude-<ime> je "<ime>"."""
    found = []
    try:
        names = sorted(os.listdir(home))
    except OSError:
        return found
    for name in names:
        match = CLAUDE_PROFILE_DIR.fullmatch(name)
        if match and Path(home, name).is_dir():
            found.append((match.group(1) or "claude", Path(home, name)))
    return found


def default_config(home: Path, workspace: Path) -> dict:
    """Config za ovaj računar: samo izvori koji stvarno postoje, bez ličnih dokumenata."""
    roots: list[str] = []
    seen: set[str] = set()
    for folder in PROJECT_FOLDERS:
        path = Path(home, folder)
        key = os.path.normcase(os.path.realpath(path))
        if path.is_dir() and key not in seen:
            seen.add(key)
            roots.append(str(path))
    inside = any(_within(workspace, Path(root)) for root in roots)
    skill_roots, registries, mcp_sources = [], [], []
    if Path(home, ".agents", "skills").is_dir():
        skill_roots.append({"path": str(Path(home, ".agents", "skills")), "profile": "agents", "label": ".agents"})
    for profile, folder in _claude_profiles(home):
        if (folder / "skills").is_dir():
            skill_roots.append({"path": str(folder / "skills"), "profile": profile, "label": folder.name})
        if (folder / "plugins" / "installed_plugins.json").is_file():
            registries.append({"path": str(folder / "plugins" / "installed_plugins.json"), "profile": profile})
        # Podrazumijevani profil drži .claude.json u home folderu; ostali u svom folderu.
        state = Path(home, ".claude.json") if profile == "claude" else folder / ".claude.json"
        for source in (state, folder / "settings.json"):
            if source.is_file():
                mcp_sources.append({"path": str(source), "format": "claude-json", "profile": profile})
    if Path(home, ".codex", "config.toml").is_file():
        mcp_sources.append({"path": str(Path(home, ".codex", "config.toml")), "format": "codex-toml", "profile": "codex"})
    return {
        "workspaceRoot": str(workspace),
        "projectRoots": roots if inside else [".", *roots],
        "projectDepth": 3,
        "extraProjects": [],
        "excludeNames": list(DEFAULT_EXCLUDES),
        "skillRoots": skill_roots,
        "pluginRegistries": registries,
        "mcpSources": mcp_sources,
        "documents": [],
    }


def allowed_roots(config: Config) -> list[str]:
    roots = [
        config.workspace_root,
        *(r.path for r in config.skill_roots),
        *(os.path.dirname(r.path) for r in config.plugin_registries),
    ]
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]
