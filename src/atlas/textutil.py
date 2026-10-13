"""Čišćenje teksta za prikaz."""
from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\ufeff]")


def clean_text(value: object, limit: int = 500) -> str:
    if value is None:
        return ""
    text = " ".join(_CONTROL.sub("", str(value)).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
