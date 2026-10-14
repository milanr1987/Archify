"""Pokreće sve skenere i pravi validan, deterministički inventar."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from atlas.config import Config, allowed_roots
from atlas.model import SCHEMA_VERSION, Inventory, validate_inventory
from atlas.scan.collector import DEFAULT_MAX_ITEMS, Collector, SourceStatus
from atlas.scan.documents import scan_documents
from atlas.scan.extensions import scan_extensions
from atlas.scan.mcp import scan_mcp
from atlas.scan.plugins import scan_plugins
from atlas.scan.projects import scan_projects
from atlas.scan.skills import SkillReader, scan_skills
from atlas.scan.state import HashCache, enrich_state


@dataclass
class ScanOutcome:
    inventory: Inventory
    sources: list[SourceStatus]
    duration_s: float
    git_duration_s: float = 0.0


def finalize(collector: Collector, now: datetime) -> Inventory:
    items = list(collector.items.values())
    for item in items:
        item.locations.sort(key=lambda l: (l.path.lower(), l.profile or "", l.origin or "", l.root_label or ""))
        for key, value in list(item.metadata.items()):
            if isinstance(value, list):
                item.metadata[key] = sorted(set(value))
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for item in items:
        groups[(item.kind, item.name.lower())].append(item)
    for (kind, name), members in groups.items():
        group = f"{kind}:{name}" if len(members) > 1 else None
        for member in members:
            member.duplicate_group = group
    items.sort(key=lambda i: (i.kind, i.name.lower(), i.id))
    ids = {i.id for i in items}
    relations = sorted(
        (r for r in collector.relations if r.source in ids and r.target in ids),
        key=lambda r: (r.source, r.target, r.type),
    )
    warnings = sorted(set(collector.warnings), key=lambda w: (w.severity, w.code, w.source, w.message))
    partial = collector.limit_hit or any(w.severity == "warn" for w in warnings)
    return Inventory(SCHEMA_VERSION, now.isoformat(timespec="seconds"), items, relations, warnings, partial)


def build_inventory(config: Config, *, now: datetime | None = None,
                    max_items: int = DEFAULT_MAX_ITEMS, hash_cache_path=None) -> ScanOutcome:
    start = time.perf_counter()
    collector = Collector(max_items)
    hash_cache = HashCache.load(hash_cache_path) if hash_cache_path else None
    reader = SkillReader(collector, hash_cache)
    roots = allowed_roots(config)
    projects = scan_projects(config, collector)
    if not collector.limit_hit: scan_skills(config, collector, reader, roots)
    if not collector.limit_hit: scan_extensions(config, collector)
    if not collector.limit_hit: scan_plugins(config, collector, reader, roots)
    if not collector.limit_hit: scan_mcp(config, collector, projects.mcp_files, projects.index)
    if not collector.limit_hit: scan_documents(config, collector)
    git_duration = enrich_state(config, collector)
    if hash_cache is not None: hash_cache.save()
    inventory = finalize(collector, now or datetime.now().astimezone())
    inventory.profiles=sorted({r.profile for r in (*config.skill_roots,*config.plugin_registries,*config.mcp_sources)})
    validate_inventory(inventory)
    sources = sorted(set(collector.sources), key=lambda s: (s.kind, s.path.lower(), s.status))
    return ScanOutcome(inventory, sources, time.perf_counter() - start, git_duration)
