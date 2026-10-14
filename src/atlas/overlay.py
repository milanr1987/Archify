"""Local user notes, independent of scanned inventory."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 1024 * 1024


class OverlayError(ValueError):
    pass


@dataclass
class Note:
    text: str
    tags: list[str]


@dataclass
class Overlay:
    notes: dict[str, Note]


def _id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', value):
        raise OverlayError('overlay-invalid-id')
    return value.lower()


def _note(text: str, tags: list[str]) -> Note:
    if not isinstance(text, str) or not text.strip() or len(text) > 10000:
        raise OverlayError('overlay-invalid-text')
    if not isinstance(tags, list):
        raise OverlayError('overlay-invalid-tags')
    result = []
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip() or len(tag) > 100:
            raise OverlayError('overlay-invalid-tags')
        if tag.strip() not in result:
            result.append(tag.strip())
    if len(result) > 20:
        raise OverlayError('overlay-invalid-tags')
    return Note(text.strip(), result)


def overlay_from_dict(data: object) -> Overlay:
    if (not isinstance(data, dict) or set(data) != {'schemaVersion', 'notes'}
            or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
            or not isinstance(data['notes'], dict)):
        raise OverlayError('overlay-invalid-schema')
    notes = {}
    for key, value in data['notes'].items():
        identity = _id(key)
        if identity in notes or not isinstance(value, dict) or set(value) != {'text', 'tags'}:
            raise OverlayError('overlay-invalid-note')
        notes[identity] = _note(value['text'], value['tags'])
    return Overlay(notes)


def overlay_to_dict(overlay: Overlay) -> dict:
    data = {'schemaVersion': 1, 'notes': {
        key: {'text': note.text, 'tags': list(note.tags)}
        for key, note in overlay.notes.items()}}
    overlay_from_dict(data)
    return data


def canonical_overlay(overlay: Overlay) -> str:
    text = json.dumps(overlay_to_dict(overlay), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise OverlayError('overlay-too-large')
    return text


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OverlayError('overlay-duplicate-key')
        result[key] = value
    return result


def load_overlay(path: Path) -> Overlay:
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return Overlay({})
    if len(raw) > MAX_BYTES:
        raise OverlayError(f'overlay-too-large: {path}')
    try:
        return overlay_from_dict(json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique_object))
    except (ValueError, UnicodeError, RecursionError):
        raise OverlayError(f'overlay-invalid: {path}') from None


def update_note(overlay: Overlay, item_id: str, *, text: str | None = None,
                tags: list[str] | None = None, delete: bool = False) -> Overlay:
    identity = _id(item_id)
    result = overlay_from_dict(overlay_to_dict(overlay))
    if delete:
        if text is not None or tags is not None:
            raise OverlayError('overlay-conflicting-options')
        result.notes.pop(identity, None)
    else:
        old = result.notes.get(identity)
        result.notes[identity] = _note(text if text is not None else (old.text if old else ''),
                                       tags if tags is not None else (old.tags if old else []))
    canonical_overlay(result)
    return result


def orphan_note_ids(inv, overlay: Overlay) -> list[str]:
    known = {item.id for item in inv.items}
    return sorted(set(overlay.notes) - known)
