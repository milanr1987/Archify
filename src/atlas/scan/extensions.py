"""Slash komande, subagenti i hookovi iz profila i pluginova. Sadržaj hookova i tijela fajlova ne izlazi."""
from __future__ import annotations

import json
import os
import re

from atlas.config import Config
from atlas.frontmatter import FrontmatterError, parse_frontmatter, parse_frontmatter_lenient
from atlas.fsutil import FileTooLarge, link_info, read_text_limited
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.textutil import clean_text

COMMAND_DEPTH = 3
AGENT_DEPTH = 2
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def find_markdown(root: str, exclude: frozenset[str], max_depth: int) -> tuple[list[str], list[tuple[str, str]]]:
    """Logičke putanje *.md fajlova (bez README.md) do zadate dubine, uz zaštitu od ciklusa linkova."""
    found: list[str] = []
    problems: list[tuple[str, str]] = []

    def walk(directory: str, depth: int, stack: frozenset[str]) -> None:
        real = norm_path(directory)
        if real in stack:
            problems.append(("link-cycle", directory))
            return
        stack = stack | {real}
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            problems.append(("unreadable-dir", directory))
            return
        for name in names:
            if name in exclude:
                continue
            child = os.path.join(directory, name)
            if os.path.isdir(child):
                if depth + 1 < max_depth:
                    walk(child, depth + 1, stack)
            elif os.path.isfile(child):
                if name.lower().endswith(".md") and name.lower() != "readme.md":
                    found.append(child)
            elif os.path.lexists(child):
                problems.append(("broken-link", child))

    walk(root, 0, frozenset())
    return found, problems


def _frontmatter(collector: Collector, path: str) -> dict:
    try:
        text = read_text_limited(path)
    except FileTooLarge:
        collector.warn("warn", "file-too-large", path, "fajl je veći od 1 MiB")
        return {}
    except OSError as exc:
        collector.warn("warn", "unreadable", path, f"fajl nije čitljiv ({type(exc).__name__})")
        return {}
    try:
        return parse_frontmatter(text)
    except FrontmatterError as exc:
        if str(exc) == "nema frontmatter":
            return {}
        if str(exc) == "neispravan YAML":
            try:
                data = parse_frontmatter_lenient(text)
            except FrontmatterError:
                pass
            else:
                collector.warn("info", "lenient-frontmatter", path,
                               "YAML nije strogo ispravan; name/description pročitani blaže, kao u Claude Code")
                return data
        collector.warn("warn", "bad-frontmatter", path, str(exc))
        return {}


def add_markdown_root(collector: Collector, root: str, kind: str, profile: str, label: str,
                      origin: str, exclude: frozenset[str]) -> list[str]:
    files, problems = find_markdown(root, exclude, COMMAND_DEPTH if kind == "command" else AGENT_DEPTH)
    for code, path in problems:
        collector.warn("warn", code, path, {"link-cycle": "ciklus linkova; ta grana je prekinuta",
                                            "broken-link": "link pokazuje na nepostojeći cilj",
                                            "unreadable-dir": "folder nije čitljiv"}[code])
    ids: list[str] = []
    for path in files:
        if collector.limit_hit: break
        data = _frontmatter(collector, path)
        parts = os.path.splitext(os.path.relpath(path, root))[0].split(os.sep)
        name = ":".join(parts) if kind == "command" else parts[-1]
        if kind == "agent" and isinstance(data.get("name"), str):
            name = data["name"]
        description = data.get("description") if isinstance(data.get("description"), str) else ""
        via_link, target = link_info(path)
        item = Item(id=make_id(kind, norm_path(path)), kind=kind,
                    name=clean_text(name, 100) or parts[-1], description=clean_text(description, 500),
                    locations=[Location(path=path, profile=profile, via_link=via_link,
                                        link_target=target, origin=origin, root_label=label)])
        if collector.add_item(item):
            ids.append(item.id)
    return ids


def _safe_name(value: object) -> str:
    return value if isinstance(value, str) and NAME_RE.fullmatch(value) else "unknown"


def add_hooks(collector: Collector, hooks: object, *, source_path: str, profile: str | None,
              label: str, origin: str) -> list[str]:
    """Samo event, matcher, broj i tip hookova. command/prompt/url/env se nikad ne čitaju u izlaz."""
    if not isinstance(hooks, dict):
        collector.warn("warn", "bad-format", source_path, "hooks nije objekat")
        return []
    grouped: dict[tuple[str, str], tuple[int, set[str]]] = {}
    for event in sorted(hooks, key=str):
        groups = hooks[event]
        if not isinstance(groups, list):
            collector.warn("warn", "bad-format", source_path, "hook event nije lista")
            continue
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                collector.warn("warn", "bad-format", source_path, "hook stavka nije objekat")
                continue
            matcher = clean_text(group.get("matcher"), 100) if isinstance(group.get("matcher"), str) else ""
            entries = [h for h in group.get("hooks", []) if isinstance(h, dict)]
            key = (_safe_name(event), matcher)
            count, types = grouped.get(key, (0, set()))
            grouped[key] = (count + len(entries), types | {_safe_name(h.get("type")) for h in entries})
    via_link, target = link_info(source_path)
    ids: list[str] = []
    for (event, matcher), (count, types) in sorted(grouped.items()):
        if collector.limit_hit: break
        metadata: dict[str, str | list[str]] = {"event": event, "hookCount": str(count)}
        if matcher:
            metadata["matcher"] = matcher
        if types:
            metadata["hookTypes"] = sorted(types)
        item = Item(id=make_id("hook", profile or "", norm_path(source_path), event, matcher), kind="hook",
                    name=f"{event} · {matcher}" if matcher else event,
                    locations=[Location(path=source_path, profile=profile, via_link=via_link,
                                        link_target=target, origin=origin, root_label=label)],
                    metadata=metadata)
        if collector.add_item(item):
            ids.append(item.id)
    return ids


def read_hooks_quietly(path: str) -> object | None:
    """Drugi skeneri već prijavljuju nedostupan ili neispravan izvor; ovdje bez duplih upozorenja."""
    try:
        data = json.loads(read_text_limited(path, 32 * 1024 * 1024))
    except (OSError, ValueError, FileTooLarge):
        return None
    return data.get("hooks") if isinstance(data, dict) else None


def scan_extensions(config: Config, collector: Collector) -> None:
    for root in config.skill_roots:
        if collector.limit_hit: break
        if os.path.basename(os.path.normpath(root.path)).lower() != "skills":
            continue
        profile_dir = os.path.dirname(os.path.normpath(root.path))
        for folder, kind in (("commands", "command"), ("agents", "agent")):
            path = os.path.join(profile_dir, folder)
            if os.path.isdir(path):
                collector.source(kind, path, "read")
                add_markdown_root(collector, path, kind, root.profile, root.label, "standalone",
                                  config.exclude_names)
    for src in config.mcp_sources:
        if collector.limit_hit: break
        if src.format != "claude-json":
            continue
        hooks = read_hooks_quietly(src.path)
        if hooks is not None:
            add_hooks(collector, hooks, source_path=src.path, profile=src.profile,
                      label=os.path.basename(src.path), origin="standalone")
