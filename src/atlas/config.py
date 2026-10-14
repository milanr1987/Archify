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


def default_config(home: Path, workspace: Path) -> dict:
    def at(*parts: str) -> str:
        return str(Path(home, *parts))

    roots: list[str] = []
    seen: set[str] = set()
    for folder in PROJECT_FOLDERS:
        path = Path(home, folder)
        key = os.path.normcase(os.path.realpath(path))
        if path.is_dir() and key not in seen:
            seen.add(key)
            roots.append(str(path))
    inside = any(_within(workspace, Path(root)) for root in roots)
    return {
        "workspaceRoot": str(workspace),
        "projectRoots": roots if inside else [".", *roots],
        "projectDepth": 3,
        "extraProjects": ["skill-evals"] if Path(workspace, "skill-evals").is_dir() else [],
        "excludeNames": list(DEFAULT_EXCLUDES),
        "skillRoots": [
            {"path": at(".agents", "skills"), "profile": "agents", "label": ".agents"},
            {"path": at(".claude", "skills"), "profile": "claude", "label": ".claude"},
            {"path": at(".claude-max", "skills"), "profile": "max", "label": ".claude-max"},
            {"path": at(".claude-pro", "skills"), "profile": "pro", "label": ".claude-pro"},
        ],
        "pluginRegistries": [
            {"path": at(".claude", "plugins", "installed_plugins.json"), "profile": "claude"},
            {"path": at(".claude-max", "plugins", "installed_plugins.json"), "profile": "max"},
            {"path": at(".claude-pro", "plugins", "installed_plugins.json"), "profile": "pro"},
        ],
        "mcpSources": [
            {"path": at(".claude.json"), "format": "claude-json", "profile": "claude"},
            {"path": at(".claude", "settings.json"), "format": "claude-json", "profile": "claude"},
            {"path": at(".claude-max", ".claude.json"), "format": "claude-json", "profile": "max"},
            {"path": at(".claude-max", "settings.json"), "format": "claude-json", "profile": "max"},
            {"path": at(".claude-pro", ".claude.json"), "format": "claude-json", "profile": "pro"},
            {"path": at(".claude-pro", "settings.json"), "format": "claude-json", "profile": "pro"},
            {"path": at(".codex", "config.toml"), "format": "codex-toml", "profile": "codex"},
        ],
        "documents": [
            {"path": "my-claude-system.md", "title": "Moj Claude sistem"},
            {"path": "claude-skillovi-i-plugini-inventar.md", "title": "Inventar skillova i pluginova (2026-09-07)"},
            {"path": "claude-ai-engineer-playbook.md", "title": "AI engineer playbook"},
            {"path": "MEDIUM_CLAUDE\\INDEX.md", "title": "Medium indeks"},
        ],
    }


def allowed_roots(config: Config) -> list[str]:
    roots = [
        config.workspace_root,
        *(r.path for r in config.skill_roots),
        *(os.path.dirname(r.path) for r in config.plugin_registries),
    ]
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]
