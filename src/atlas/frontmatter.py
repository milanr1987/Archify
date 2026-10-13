"""YAML frontmatter iz SKILL.md fajlova."""
from __future__ import annotations

import yaml


class FrontmatterError(Exception):
    """Frontmatter ne postoji ili nije ispravan. Poruka nikad ne sadrži tekst fajla."""


def parse_frontmatter(text: str) -> dict:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("nema frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            block = "\n".join(lines[1:index])
            break
    else:
        raise FrontmatterError("frontmatter nije zatvoren")
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        raise FrontmatterError("neispravan YAML") from None
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter nije mapa")
    return data
