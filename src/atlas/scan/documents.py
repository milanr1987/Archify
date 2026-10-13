"""Dokumenti kao reference: putanja i naslov, bez sadržaja."""
from __future__ import annotations

import os

from atlas.config import Config
from atlas.fsutil import FileTooLarge, link_info, read_text_limited
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.textutil import clean_text


def document_title(path: str) -> str | None:
    try:
        text = read_text_limited(path)
    except (FileTooLarge, OSError):
        return None
    for line in text.splitlines()[:50]:
        if line.startswith("# "):
            return clean_text(line[2:], 150) or None
    return None


def add_document(collector: Collector, path: str, title: str | None, status: str) -> str:
    doc_id = make_id("document", norm_path(path))
    via_link, target = link_info(path)
    collector.add_item(Item(
        id=doc_id,
        kind="document",
        name=title or document_title(path) or os.path.basename(path),
        locations=[Location(path=path, via_link=via_link, link_target=target)],
        metadata={"referenceStatus": status},
    ))
    return doc_id


def scan_documents(config: Config, collector: Collector) -> None:
    for doc in config.documents:
        if collector.limit_hit: break
        if not os.path.isfile(doc.path):
            collector.source("document", doc.path, "missing")
            collector.warn("warn", "source-missing", doc.path, "dokument ne postoji")
            continue
        collector.source("document", doc.path, "read")
        add_document(collector, doc.path, clean_text(doc.title, 150), "listed")
