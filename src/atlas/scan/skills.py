"""Skillovi iz samostalnih korijena i iz pluginova."""
from __future__ import annotations

import os

from atlas.config import Config
from atlas.frontmatter import FrontmatterError, parse_frontmatter, parse_frontmatter_lenient
from atlas.fsutil import FileTooLarge, find_skill_files, is_within, link_info, read_text_limited
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.textutil import clean_text
from atlas.scan.state import content_hash

WALK_MESSAGES = {
    "link-cycle": "ciklus linkova; ta grana je prekinuta",
    "broken-link": "link pokazuje na nepostojeći cilj",
    "unreadable-dir": "folder nije čitljiv",
}


def _scalar(value: object) -> object:
    return value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None


class SkillReader:
    """Kešira frontmatter po realpathu; lokacija se svaki put evidentira posebno."""

    def __init__(self, collector: Collector) -> None:
        self.collector = collector
        self.cache: dict[str, tuple[str, str]] = {}
        self.outside_warned: set[str] = set()
        self.hashes: dict[str,str] = {}

    def read(self, skill_md: str) -> tuple[str, str]:
        key = norm_path(skill_md)
        if key in self.cache:
            return self.cache[key]
        folder = os.path.basename(os.path.dirname(skill_md))
        name, description = folder, ""
        try:
            text = read_text_limited(skill_md)
            try:
                data = parse_frontmatter(text)
            except FrontmatterError as exc:
                if str(exc) != "neispravan YAML":
                    raise
                data = parse_frontmatter_lenient(text)
                self.collector.warn("info", "lenient-frontmatter", skill_md,
                                    "YAML nije strogo ispravan; name/description pročitani blaže, kao u Claude Code")
            if any(key in data and not isinstance(data[key], str) for key in ("name", "description")):
                raise FrontmatterError("name i description moraju biti stringovi")
            name = clean_text(data.get("name"), 100) or folder
            description = clean_text(data.get("description"), 500)
        except FileTooLarge:
            self.collector.warn("warn", "file-too-large", skill_md, "SKILL.md je veći od 1 MiB")
        except FrontmatterError as exc:
            self.collector.warn("warn", "bad-frontmatter", skill_md, str(exc))
        except OSError as exc:
            self.collector.warn("warn", "unreadable", skill_md, f"SKILL.md nije čitljiv ({type(exc).__name__})")
        self.cache[key] = (name, description)
        return name, description


def add_skill_root(
    collector: Collector,
    reader: SkillReader,
    root: str,
    profile: str,
    label: str,
    origin: str,
    exclude: frozenset[str],
    roots: list[str],
) -> list[str]:
    files, problems = find_skill_files(root, exclude)
    for code, path in problems:
        collector.warn("warn", code, path, WALK_MESSAGES[code])
    ids: list[str] = []
    for skill_md in files:
        if collector.limit_hit: break
        name, description = reader.read(skill_md)
        via_link, target = link_info(skill_md)
        real = norm_path(skill_md)
        if via_link and real not in reader.outside_warned and not any(is_within(skill_md, r) for r in roots):
            reader.outside_warned.add(real)
            collector.warn("info", "link-outside-roots", skill_md, "link vodi van konfigurisanih korijena")
        location = Location(
            path=os.path.dirname(skill_md),
            profile=profile,
            via_link=via_link,
            link_target=os.path.dirname(target) if target else None,
            origin=origin,
            root_label=label,
            contentHash=reader.hashes.get(real),
        )
        if not location.contentHash:
            location.contentHash=content_hash(os.path.dirname(skill_md),collector)
            reader.hashes[real]=location.contentHash
        item = Item(id=make_id("skill", real), kind="skill", name=name,
                    description=description, locations=[location])
        if collector.add_item(item):
            ids.append(item.id)
    return ids


def scan_skills(config: Config, collector: Collector, reader: SkillReader, roots: list[str]) -> None:
    for root in config.skill_roots:
        if collector.limit_hit: break
        if not os.path.isdir(root.path):
            collector.source("skill-root", root.path, "missing")
            collector.warn("warn", "source-missing", root.path, "folder sa skillovima ne postoji")
            continue
        collector.source("skill-root", root.path, "read")
        add_skill_root(collector, reader, root.path, root.profile, root.label, "standalone",
                       config.exclude_names, roots)
