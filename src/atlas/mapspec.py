"""Opis mape (config/maps/<slug>.json) u analysis i native Archify JSON. Izvorni fajlovi se samo čitaju."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from atlas.maps import SLUG, MapError, _source, validate_analysis

ID = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
NODE_TYPES = ("frontend", "backend", "database", "cloud", "security", "messagebus", "external")
SPEC_KEYS = {"project", "slug", "title", "lanes", "components", "edges", "cards"}
COMPONENT_KEYS = {"id", "name", "purpose", "file", "needle", "lane", "col", "type"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MapError(f"map-spec: {message}")


def validate_spec(spec: object) -> dict:
    _require(isinstance(spec, dict) and set(spec) <= SPEC_KEYS and SPEC_KEYS - {"cards"} <= set(spec),
             f"očekivana polja {', '.join(sorted(SPEC_KEYS))}")
    _require(isinstance(spec["project"], str) and spec["project"], "project je ime projekta iz kataloga")
    _require(isinstance(spec["slug"], str) and re.fullmatch(SLUG, spec["slug"]) is not None, "slug: mala slova, brojevi i -")
    _require(isinstance(spec["title"], str) and spec["title"], "title je obavezan")
    lanes = spec["lanes"]
    _require(isinstance(lanes, list) and lanes and all(
        isinstance(l, dict) and set(l) == {"id", "label"} and ID.fullmatch(str(l["id"])) and
        isinstance(l["label"], str) and l["label"] for l in lanes), "lanes: lista {id, label}")
    lane_ids = {l["id"] for l in lanes}
    ids: set[str] = set()
    for c in spec["components"] if isinstance(spec["components"], list) else [None]:
        _require(isinstance(c, dict) and set(c) == COMPONENT_KEYS, f"komponenta: polja {', '.join(sorted(COMPONENT_KEYS))}")
        _require(ID.fullmatch(str(c["id"])) is not None and c["id"] not in ids, f"komponenta {c['id']!r}: id")
        ids.add(c["id"])
        _require(all(isinstance(c[k], str) and c[k] for k in ("name", "purpose", "file", "needle")),
                 f"komponenta {c['id']}: name/purpose/file/needle su tekst")
        _require(c["lane"] in lane_ids, f"komponenta {c['id']}: nepoznat lane")
        _require(type(c["col"]) is int and 0 <= c["col"] <= 5, f"komponenta {c['id']}: col 0-5")
        _require(c["type"] in NODE_TYPES, f"komponenta {c['id']}: type je jedan od {', '.join(NODE_TYPES)}")
    _require(bool(ids), "bar jedna komponenta")
    for e in spec["edges"] if isinstance(spec["edges"], list) else [None]:
        _require(isinstance(e, list) and len(e) == 3 and e[0] in ids and e[1] in ids and isinstance(e[2], str),
                 "edges: lista [od, do, oznaka] sa postojećim id-jevima")
    cards = spec.get("cards", [])
    _require(isinstance(cards, list) and all(isinstance(t, str) for t in cards), "cards: lista teksta")
    return spec


def build_inputs(spec: dict, project_id: str, project_root: Path, now: datetime) -> tuple[dict, dict]:
    """Vraća (analysis, native). Linija i SHA-256 se računaju iz stvarnog izvora."""
    validate_spec(spec)
    evidence, components = [], []
    for c in spec["components"]:
        source = _source(project_root, c["file"])
        try:
            raw = source.read_bytes()
        except OSError:
            raise MapError(f"map-spec: komponenta {c['id']}: fajl {c['file']} nije čitljiv") from None
        lines = raw.decode("utf-8", errors="replace").splitlines()
        line = next((n for n, text in enumerate(lines, 1) if c["needle"] in text), None)
        _require(line is not None, f"komponenta {c['id']}: tekst {c['needle']!r} nije u {c['file']}")
        evidence.append({"id": c["id"], "relativePath": c["file"], "line": line,
                         "fileHash": hashlib.sha256(raw).hexdigest()})
        components.append({"id": c["id"], "name": c["name"], "purpose": c["purpose"], "evidenceIds": [c["id"]]})
    analysis = validate_analysis({
        "schemaVersion": 1, "projectId": project_id, "projectRoot": str(project_root),
        "generatedAt": now.isoformat(timespec="seconds"), "components": components,
        "edges": [{"from": a, "to": b, "label": label, "status": "observed", "evidenceIds": [a, b]}
                  for a, b, label in spec["edges"]],
        "evidence": evidence, "openQuestions": []})
    native = {"schema_version": 2, "diagram_type": "workflow",
              "meta": {"title": spec["title"], "quality_profile": "standard",
                       "output": f"output/maps/{spec['slug']}.html"},
              "lanes": spec["lanes"],
              "nodes": [{"id": c["id"], "lane": c["lane"], "col": c["col"], "type": c["type"], "label": c["name"]}
                        for c in spec["components"]],
              "edges": [{"from": a, "to": b} for a, b, _ in spec["edges"]]}
    if spec.get("cards"):
        native["cards"] = [{"dot": "cyan", "title": "Granice", "items": spec["cards"]}]
    return analysis, native
