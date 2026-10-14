"""YAML frontmatter iz SKILL.md fajlova."""
from __future__ import annotations

import re

import yaml

# Rezervno čitanje: samo ključevi u prvoj koloni i jednoredne obične vrijednosti.
_LENIENT_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]+(\S.*)$")
_FLOW_START = tuple("[{|>&*!%@`")


class FrontmatterError(Exception):
    """Frontmatter ne postoji ili nije ispravan. Poruka nikad ne sadrži tekst fajla."""


def _block(text: str) -> str:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("nema frontmatter")
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            return "\n".join(lines[1:index])
    raise FrontmatterError("frontmatter nije zatvoren")


def parse_frontmatter(text: str) -> dict:
    block = _block(text)
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        raise FrontmatterError("neispravan YAML") from None
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter nije mapa")
    return data


def parse_frontmatter_lenient(text: str) -> dict:
    """Blaže čitanje kao kod Claude Code: `ključ: ostatak reda`, i kad vrijednost ima dvotačku."""
    data: dict[str, str] = {}
    for line in _block(text).splitlines():
        match = _LENIENT_LINE.match(line.rstrip())
        if not match:
            continue
        key, value = match.groups()
        if value.startswith(_FLOW_START):
            raise FrontmatterError("neispravan YAML")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data.setdefault(key, value)
    if not data:
        raise FrontmatterError("neispravan YAML")
    return data
