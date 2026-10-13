"""Čitanje JSON/TOML izvora sa upozorenjima umjesto pada."""
from __future__ import annotations

import json
import os
import tomllib

from atlas.fsutil import CONFIG_MAX_BYTES, FileTooLarge, read_text_limited
from atlas.scan.collector import Collector


def _read_source(collector: Collector, kind: str, path: str) -> str | None:
    if not os.path.isfile(path):
        collector.source(kind, path, "missing")
        collector.warn("warn", "source-missing", path, "izvor ne postoji")
        return None
    try:
        return read_text_limited(path, CONFIG_MAX_BYTES)
    except FileTooLarge:
        collector.source(kind, path, "error")
        collector.warn("warn", "file-too-large", path, "izvor je veći od 32 MiB")
    except OSError as exc:
        collector.source(kind, path, "error")
        collector.warn("warn", "unreadable", path, f"izvor nije čitljiv ({type(exc).__name__})")
    return None


def load_json_source(collector: Collector, kind: str, path: str) -> object | None:
    raw = _read_source(collector, kind, path)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        collector.source(kind, path, "error")
        collector.warn("warn", "bad-json", path, f"neispravan JSON (red {exc.lineno}, kolona {exc.colno})")
        return None
    collector.source(kind, path, "read")
    return data


def load_toml_source(collector: Collector, kind: str, path: str) -> dict | None:
    raw = _read_source(collector, kind, path)
    if raw is None:
        return None
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        collector.source(kind, path, "error")
        collector.warn("warn", "bad-toml", path, "neispravan TOML")
        return None
    collector.source(kind, path, "read")
    return data
