"""Instalirani pluginovi iz installed_plugins.json i skillovi u njihovim folderima."""
from __future__ import annotations

import json
import os

from atlas.config import Config, PluginRegistry
from atlas.fsutil import FileTooLarge, is_within, link_info, read_text_limited
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.scan.common import load_json_source
from atlas.scan.skills import SkillReader, add_skill_root
from atlas.textutil import clean_text

NO_PROJECT = "Projekat nije naveden u registru"


def _plugin_description(install_path: str, collector: Collector) -> str:
    manifest = os.path.join(install_path, ".claude-plugin", "plugin.json")
    try:
        data = json.loads(read_text_limited(manifest))
    except FileTooLarge:
        collector.warn("warn", "file-too-large", manifest, "manifest je veći od 1 MiB")
        return ""
    except FileNotFoundError:
        return ""
    except (OSError, ValueError) as exc:
        collector.warn("warn", "bad-manifest", manifest, f"nečitljiv manifest ({type(exc).__name__})")
        return ""
    if isinstance(data, dict) and isinstance(data.get("description"), str):
        return clean_text(data["description"], 500)
    return ""


def _add_plugin(
    config: Config,
    collector: Collector,
    reader: SkillReader,
    roots: list[str],
    reg: PluginRegistry,
    key: str,
    entry: dict,
) -> None:
    name, _, marketplace = key.partition("@")
    install = entry.get("installPath") if isinstance(entry.get("installPath"), str) else ""
    scope = clean_text(entry.get("scope"), 32) or "unknown"
    project_path = entry.get("projectPath") if isinstance(entry.get("projectPath"), str) else ""
    plugin_id = make_id(
        "plugin", reg.profile, key, scope,
        norm_path(project_path) if project_path else "",
        norm_path(install) if install else "",
    )
    metadata: dict[str, str | list[str]] = {"marketplace": clean_text(marketplace, 100), "scope": scope}
    for field in ("version", "installedAt", "lastUpdated"):
        value = entry.get(field)
        if isinstance(value, str) and value:
            metadata[field] = clean_text(value, 64)
    if project_path:
        metadata["projectPath"] = project_path
    elif scope == "project":
        metadata["projectPath"] = NO_PROJECT
    via_link, target = link_info(install) if install else (False, None)
    collector.add_item(Item(
        id=plugin_id,
        kind="plugin",
        name=clean_text(name, 100) or key,
        description="",
        locations=[Location(path=install or reg.path, profile=reg.profile, via_link=via_link,
                            link_target=target, root_label=f"plugins ({reg.profile})")],
        metadata=metadata,
    ))
    if not install:
        collector.warn("warn", "bad-format", reg.path, f"plugin {key} nema installPath")
        return
    if not os.path.isdir(install):
        collector.warn("warn", "plugin-path-missing", install, f"folder plugina {key} ne postoji")
        return
    if not is_within(install, os.path.dirname(reg.path)):
        collector.warn("warn", "plugin-outside-root", install,
                       f"plugin {key} je van plugins foldera profila {reg.profile}; skillovi nisu čitani")
        return
    if plugin_id in collector.items:
        collector.items[plugin_id].description = _plugin_description(install, collector)
    skills_dir = os.path.join(install, "skills")
    if not os.path.isdir(skills_dir):
        return
    for skill_id in add_skill_root(collector, reader, skills_dir, reg.profile, f"plugin {key}",
                                   f"plugin:{plugin_id}", config.exclude_names, roots):
        collector.relate(plugin_id, skill_id, "contains")


def scan_plugins(config: Config, collector: Collector, reader: SkillReader, roots: list[str]) -> None:
    for reg in config.plugin_registries:
        if collector.limit_hit: break
        data = load_json_source(collector, "plugin-registry", reg.path)
        if data is None:
            continue
        plugins = data.get("plugins") if isinstance(data, dict) else None
        if not isinstance(plugins, dict):
            collector.warn("warn", "bad-format", reg.path, "registar nema objekat plugins")
            continue
        for key in sorted(plugins):
            if collector.limit_hit: break
            entries = plugins[key]
            if isinstance(entries, dict):
                entries = [entries]
            if not isinstance(entries, list):
                collector.warn("warn", "bad-format", reg.path, f"plugin {key}: neočekivan format")
                continue
            for entry in entries:
                if collector.limit_hit: break
                if not isinstance(entry, dict):
                    collector.warn("warn", "bad-format", reg.path, f"plugin {key}: stavka nije objekat")
                    continue
                _add_plugin(config, collector, reader, roots, reg, key, entry)
