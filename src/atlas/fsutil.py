"""Čitanje fajlova sa limitima, linkovi i pretraga SKILL.md fajlova."""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from atlas.identity import norm_path

MAX_TEXT_BYTES = 1024 * 1024
CONFIG_MAX_BYTES = 32 * 1024 * 1024


class FileTooLarge(Exception):
    """Fajl je veći od dozvoljenog limita."""


def read_text_limited(path: str, limit: int = MAX_TEXT_BYTES) -> str:
    if os.path.getsize(path) > limit:
        raise FileTooLarge(path)
    with open(path, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise FileTooLarge(path)
    return data.decode("utf-8-sig", errors="replace")


def is_within(child: str, parent: str) -> bool:
    c, p = norm_path(child), norm_path(parent)
    try:
        return os.path.commonpath([c, p]) == p
    except ValueError:
        return False


def link_info(path: str) -> tuple[bool, str | None]:
    """(True, krajnji cilj) ako putanja ili neki njen predak prolazi kroz link."""
    logical = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    if norm_path(path) == logical:
        return False, None
    return True, os.path.realpath(path)


@dataclass
class FsOps:
    listdir: Callable[[str], list[str]] = os.listdir
    isdir: Callable[[str], bool] = os.path.isdir
    isfile: Callable[[str], bool] = os.path.isfile
    realpath: Callable[[str], str] = norm_path
    lexists: Callable[[str], bool] = os.path.lexists


REAL_FS = FsOps()


def find_skill_files(
    root: str,
    exclude: frozenset[str],
    max_depth: int = 4,
    ops: FsOps = REAL_FS,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Logičke putanje SKILL.md fajlova kroz dati root i lista (kod, putanja) problema."""
    found: list[str] = []
    problems: list[tuple[str, str]] = []

    def walk(directory: str, depth: int, stack: frozenset[str]) -> None:
        real = ops.realpath(directory)
        if real in stack:
            problems.append(("link-cycle", directory))
            return
        stack = stack | {real}
        skill = os.path.join(directory, "SKILL.md")
        if ops.isfile(skill):
            found.append(skill)
            return
        if depth >= max_depth:
            return
        try:
            names = sorted(ops.listdir(directory))
        except OSError:
            problems.append(("unreadable-dir", directory))
            return
        for name in names:
            if name in exclude:
                continue
            child = os.path.join(directory, name)
            if ops.isdir(child):
                walk(child, depth + 1, stack)
            elif ops.lexists(child) and not ops.isfile(child):
                problems.append(("broken-link", child))

    walk(root, 0, frozenset())
    return found, problems
