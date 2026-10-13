"""Stabilni identiteti stavki."""
from __future__ import annotations

import hashlib
import json
import os


def norm_path(path: str | os.PathLike[str]) -> str:
    """Realpath, apsolutna, a na Windowsu lowercase i '\\'."""
    raw = os.fspath(path)
    try:
        real = os.path.realpath(raw, strict=False)
    except OSError:
        real = os.path.abspath(raw)
    return os.path.normcase(os.path.normpath(real))


def make_id(kind: str, *parts: str) -> str:
    payload = json.dumps([kind, *parts], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
