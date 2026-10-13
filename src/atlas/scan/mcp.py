"""MCP serveri iz Claude JSON, .mcp.json i Codex TOML konfiguracija. Bez tajni."""
from __future__ import annotations

import os
import re

from atlas.config import Config
from atlas.fsutil import link_info
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.scan.common import load_json_source, load_toml_source
from atlas.textutil import clean_text

TRANSPORTS = {"stdio": "stdio", "http": "http", "sse": "sse",
              "streamable-http": "http", "streamable_http": "http"}
EXEC_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def describe_server(entry: dict) -> dict[str, str | list[str]]:
    """Samo dozvoljena polja. args, env vrijednosti, url i headers se nikad ne čitaju u izlaz."""
    declared = entry.get("type") or entry.get("transport")
    if isinstance(declared, str) and declared.lower() in TRANSPORTS:
        transport = TRANSPORTS[declared.lower()]
    elif isinstance(entry.get("command"), str):
        transport = "stdio"
    elif isinstance(entry.get("url"), str):
        transport = "http"
    else:
        transport = "unknown"
    meta: dict[str, str | list[str]] = {"transport": transport}
    command = entry.get("command")
    if isinstance(command, str) and command.strip():
        base = re.split(r"[\\/]", command.strip())[-1]
        meta["executableName"] = base if EXEC_RE.fullmatch(base) else "unknown"
    names: set[str] = set()
    env = entry.get("env")
    if isinstance(env, dict):
        names.update(k for k in env if isinstance(k, str))
    env_vars = entry.get("env_vars")
    if isinstance(env_vars, list):
        names.update(v for v in env_vars if isinstance(v, str))
    env_names = sorted(n for n in names if ENV_RE.fullmatch(n))
    if env_names:
        meta["envNames"] = env_names
    return meta


def add_servers(
    collector: Collector,
    servers: object,
    *,
    source_path: str,
    profile: str | None,
    scope: str,
    project_path: str,
    fmt: str,
    project_index: dict[str, str],
) -> None:
    if not isinstance(servers, dict):
        collector.warn("warn", "bad-format", source_path, "mcpServers nije objekat")
        return
    source_norm = norm_path(source_path)
    project_norm = norm_path(project_path) if project_path else ""
    via_link, target = link_info(source_path)
    for name in sorted(servers):
        if collector.limit_hit: break
        entry = servers[name]
        if not isinstance(entry, dict):
            collector.warn("warn", "bad-format", source_path, "MCP stavka nije objekat")
            continue
        meta = describe_server(entry)
        meta["scope"] = scope
        meta["sourceFormat"] = fmt
        if project_path:
            meta["projectPath"] = project_path
        item = Item(
            id=make_id("mcp", profile or "", source_norm, scope, project_norm, name),
            kind="mcp",
            name=clean_text(name, 100) or "(bez imena)",
            locations=[Location(path=source_path, profile=profile, via_link=via_link,
                                link_target=target, root_label=fmt)],
            metadata=meta,
        )
        collector.add_item(item)
        project_id = project_index.get(project_norm) if project_norm else None
        if project_id:
            collector.relate(item.id, project_id, "configured-for")


def scan_mcp(
    config: Config,
    collector: Collector,
    project_mcp_files: list[tuple[str, str]],
    project_index: dict[str, str],
) -> None:
    for src in config.mcp_sources:
        if collector.limit_hit: break
        common = {"source_path": src.path, "profile": src.profile, "fmt": src.format,
                  "project_index": project_index}
        if src.format == "codex-toml":
            data = load_toml_source(collector, "mcp", src.path)
            if data is not None and "mcp_servers" in data:
                add_servers(collector, data["mcp_servers"], scope="user", project_path="", **common)
            continue
        data = load_json_source(collector, "mcp", src.path)
        if data is None:
            continue
        if not isinstance(data, dict):
            collector.warn("warn", "bad-format", src.path, "očekivan JSON objekat")
            continue
        if "mcpServers" in data:
            if src.format == "mcp-json":
                add_servers(collector, data["mcpServers"], scope="project",
                            project_path=os.path.dirname(src.path), **common)
            else:
                add_servers(collector, data["mcpServers"], scope="user", project_path="", **common)
        projects = data.get("projects") if src.format == "claude-json" else None
        if isinstance(projects, dict):
            for project_path in sorted(projects):
                pdata = projects[project_path]
                if isinstance(pdata, dict) and pdata.get("mcpServers"):
                    add_servers(collector, pdata["mcpServers"], scope="project",
                                project_path=project_path, **common)
    for project_dir, path in project_mcp_files:
        if collector.limit_hit: break
        data = load_json_source(collector, "mcp", path)
        if isinstance(data, dict) and "mcpServers" in data:
            add_servers(collector, data["mcpServers"], source_path=path, profile=None, scope="project",
                        project_path=project_dir, fmt="mcp-json", project_index=project_index)
