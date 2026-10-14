"""Projekti u radnom folderu, prepoznati po manifest markerima."""
from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field

from atlas.config import Config
from atlas.fsutil import FileTooLarge, link_info, read_text_limited
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.scan.documents import add_document
from atlas.textutil import clean_text

MARKERS = (("package.json", "node"), ("pyproject.toml", "python"), ("Cargo.toml", "rust"), ("go.mod", "go"))
DOTNET_SUFFIXES = (".sln", ".csproj")
PROJECT_DOCS = ("README.md", "AGENTS.md", "CLAUDE.md")
REPO_DOCS = ("CLAUDE.md", "AGENTS.md")


@dataclass
class ProjectScan:
    index: dict[str, str] = field(default_factory=dict)
    mcp_files: list[tuple[str, str]] = field(default_factory=list)


def find_markers(folder: str) -> list[str]:
    found = [name for name, _ in MARKERS if os.path.isfile(os.path.join(folder, name))]
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    found += [n for n in names if n.lower().endswith(DOTNET_SUFFIXES) and os.path.isfile(os.path.join(folder, n))]
    return found


def project_type(markers: list[str]) -> str:
    for name, kind in MARKERS:
        if name in markers:
            return kind
    if any(m.lower().endswith(DOTNET_SUFFIXES) for m in markers):
        return "dotnet"
    return "other"


def _load_manifest(collector: Collector, path: str, parser) -> object | None:
    try:
        return parser(read_text_limited(path))
    except FileTooLarge:
        collector.warn("warn", "file-too-large", path, "manifest je veći od 1 MiB")
    except (OSError, ValueError):
        collector.warn("warn", "bad-manifest", path, "manifest nije ispravan")
    return None


def _manifest_info(collector: Collector, folder: str, markers: list[str]) -> tuple[str | None, str, list[str]]:
    name: str | None = None
    description = ""
    scripts: set[str] = set()
    if "package.json" in markers:
        data = _load_manifest(collector, os.path.join(folder, "package.json"), json.loads)
        if isinstance(data, dict):
            if isinstance(data.get("name"), str):
                name = clean_text(data["name"], 100) or None
            if isinstance(data.get("description"), str):
                description = clean_text(data["description"], 500)
            if isinstance(data.get("scripts"), dict):
                scripts.update(clean_text(k, 64) for k in data["scripts"] if isinstance(k, str))
    if "pyproject.toml" in markers:
        data = _load_manifest(collector, os.path.join(folder, "pyproject.toml"), tomllib.loads)
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict):
            if name is None and isinstance(project.get("name"), str):
                name = clean_text(project["name"], 100) or None
            if not description and isinstance(project.get("description"), str):
                description = clean_text(project["description"], 500)
            if isinstance(project.get("scripts"), dict):
                scripts.update(clean_text(k, 64) for k in project["scripts"] if isinstance(k, str))
    return name, description, sorted(s for s in scripts if s)


def _add_project(collector: Collector, result: ProjectScan, folder: str) -> None:
    markers = find_markers(folder)
    name, description, scripts = _manifest_info(collector, folder, markers)
    metadata: dict[str, str | list[str]] = {"projectType": project_type(markers)}
    markers = markers or repo_markers(folder, False)
    if markers:
        metadata["markers"] = markers
    if scripts:
        metadata["scriptNames"] = scripts
    project_id = make_id("project", norm_path(folder))
    via_link, target = link_info(folder)
    if not collector.add_item(Item(
        id=project_id, kind="project", name=name or os.path.basename(folder), description=description,
        locations=[Location(path=folder, via_link=via_link, link_target=target)], metadata=metadata,
    )):
        return
    result.index[norm_path(folder)] = project_id
    for doc_name in PROJECT_DOCS:
        doc_path = os.path.join(folder, doc_name)
        if os.path.isfile(doc_path):
            collector.relate(project_id, add_document(collector, doc_path, None, "project-doc"), "documented-by")
    mcp_path = os.path.join(folder, ".mcp.json")
    if os.path.isfile(mcp_path):
        result.mcp_files.append((folder, mcp_path))


def repo_markers(folder: str, inside_project: bool) -> list[str]:
    """Slabi markeri: .git uvijek; CLAUDE.md/AGENTS.md samo van drugog projekta (inače su to podfolderi dokumentacije)."""
    names = [".git"] if os.path.exists(os.path.join(folder, ".git")) else []
    if not inside_project:
        names += [n for n in REPO_DOCS if os.path.isfile(os.path.join(folder, n))]
    return names


def _discover(root: str, depth: int, exclude: frozenset[str], found: list[str]) -> None:
    """Manifest projekat je list; projekat sa samo .git/CLAUDE.md može sadržavati druge projekte."""

    def walk(directory: str, level: int, inside: bool, stack: frozenset[str]) -> None:
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return
        for name in names:
            if name in exclude or name.startswith("."):
                continue
            folder = os.path.join(directory, name)
            if not os.path.isdir(folder):
                continue
            real = norm_path(folder)
            if real in stack:
                continue
            if find_markers(folder):
                found.append(folder)
                continue
            weak = repo_markers(folder, inside)
            if weak:
                found.append(folder)
            if level + 1 < depth:
                walk(folder, level + 1, inside or bool(weak), stack | {real})

    walk(root, 0, False, frozenset({norm_path(root)}))


def scan_projects(config: Config, collector: Collector) -> ProjectScan:
    result = ProjectScan()
    candidates: list[str] = []
    for root in config.project_roots:
        if not os.path.isdir(root):
            collector.source("project-root", root, "missing")
            collector.warn("warn", "source-missing", root, "folder sa projektima ne postoji")
            continue
        try:
            os.listdir(root)
        except OSError as exc:
            collector.source("project-root", root, "error")
            collector.warn("warn", "unreadable-dir", root, f"folder nije čitljiv ({type(exc).__name__})")
            continue
        collector.source("project-root", root, "read")
        _discover(root, config.project_depth, config.exclude_names, candidates)
    for extra in config.extra_projects:
        if os.path.isdir(extra):
            candidates.append(extra)
        else:
            collector.warn("warn", "source-missing", extra, "projekat iz extraProjects ne postoji")
    for folder in dict.fromkeys(candidates):
        if collector.limit_hit: break
        _add_project(collector, result, folder)
    return result
