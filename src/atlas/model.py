"""Ugovor podataka kataloga i njegova validacija."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 1
KINDS = ("project", "skill", "plugin", "mcp", "document", "command", "agent", "hook")
EVIDENCE = ("observed", "documented")
RELATION_TYPES = ("contains", "documented-by", "configured-for")
SEVERITIES = ("info", "warn")
METADATA_KEYS: dict[str, frozenset[str]] = {
    "project": frozenset({"projectType", "scriptNames", "markers"}),
    "skill": frozenset(),
    "plugin": frozenset({"marketplace", "version", "scope", "projectPath", "installedAt", "lastUpdated"}),
    "mcp": frozenset({"transport", "executableName", "envNames", "scope", "projectPath", "sourceFormat"}),
    "document": frozenset({"referenceStatus"}),
    "command": frozenset(),
    "agent": frozenset(),
    "hook": frozenset({"event", "matcher", "hookCount", "hookTypes"}),
}
LIST_METADATA = frozenset({"scriptNames", "markers", "envNames", "hookTypes"})


class InventoryError(ValueError):
    """Inventar ne odgovara ugovoru."""


@dataclass
class Location:
    path: str
    profile: str | None = None
    via_link: bool = False
    link_target: str | None = None
    origin: str | None = None
    root_label: str | None = None

    def key(self) -> tuple[str, str, str, str]:
        return (os.path.normcase(self.path), self.profile or "", self.origin or "", self.root_label or "")


@dataclass
class Item:
    id: str
    kind: str
    name: str
    description: str = ""
    locations: list[Location] = field(default_factory=list)
    evidence: str = "observed"
    metadata: dict[str, str | list[str]] = field(default_factory=dict)
    duplicate_group: str | None = None


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    type: str


@dataclass(frozen=True)
class ScanWarning:
    severity: str
    code: str
    source: str
    message: str


@dataclass
class Inventory:
    schema_version: int
    scanned_at: str
    items: list[Item]
    relations: list[Relation]
    warnings: list[ScanWarning]
    partial: bool


def _opt_str(value: object) -> bool:
    return value is None or isinstance(value, str)


def _validate_inventory(inv: Inventory) -> None:
    errors: list[str] = []
    if inv.schema_version != SCHEMA_VERSION:
        errors.append("schema_version")
    if not isinstance(inv.scanned_at, str) or not inv.scanned_at:
        errors.append("scanned_at")
    if not isinstance(inv.partial, bool):
        errors.append("partial")
    ids: set[str] = set()
    for item in inv.items:
        where = f"stavka {str(item.id)[:12]}"
        if not isinstance(item.id, str) or len(item.id) != 64:
            errors.append(f"{where}: id")
        elif item.id in ids:
            errors.append(f"{where}: dupli id")
        ids.add(item.id)
        if item.kind not in KINDS:
            errors.append(f"{where}: nepoznat tip")
        if item.evidence not in EVIDENCE:
            errors.append(f"{where}: evidence")
        if not isinstance(item.name, str) or not item.name:
            errors.append(f"{where}: ime")
        if not isinstance(item.description, str):
            errors.append(f"{where}: opis")
        if not _opt_str(item.duplicate_group):
            errors.append(f"{where}: duplicate_group")
        if not item.locations:
            errors.append(f"{where}: bez lokacije")
        for loc in item.locations:
            if not isinstance(loc, Location) or not isinstance(loc.path, str) or not loc.path:
                errors.append(f"{where}: lokacija")
                continue
            if not isinstance(loc.via_link, bool) or not all(
                _opt_str(v) for v in (loc.profile, loc.link_target, loc.origin, loc.root_label)
            ):
                errors.append(f"{where}: polja lokacije")
        allowed = METADATA_KEYS.get(item.kind, frozenset())
        if not isinstance(item.metadata, dict):
            errors.append(f"{where}: metadata")
            continue
        for key, value in item.metadata.items():
            if key not in allowed:
                errors.append(f"{where}: nedozvoljen metadata ključ {key!r}")
            elif key in LIST_METADATA:
                if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                    errors.append(f"{where}: {key} mora biti lista stringova")
            elif not isinstance(value, str):
                errors.append(f"{where}: {key} mora biti string")
    for rel in inv.relations:
        if rel.type not in RELATION_TYPES:
            errors.append(f"relacija: nepoznat tip {rel.type!r}")
        if rel.source not in ids or rel.target not in ids:
            errors.append("relacija: nepostojeća stavka")
    for warning in inv.warnings:
        if warning.severity not in SEVERITIES:
            errors.append(f"upozorenje: severity {warning.severity!r}")
        if not all(isinstance(v, str) for v in (warning.code, warning.source, warning.message)):
            errors.append("upozorenje: polja")
    if errors:
        raise InventoryError("; ".join(errors[:20]))


def validate_inventory(inv: Inventory) -> None:
    try:
        _validate_inventory(inv)
    except (TypeError, AttributeError):
        raise InventoryError("neispravni tipovi polja inventara") from None


def inventory_to_dict(inv: Inventory) -> dict:
    return asdict(inv)


def inventory_from_dict(data: dict) -> Inventory:
    try:
        if not isinstance(data, dict) or set(data) != {"schema_version", "scanned_at", "items", "relations", "warnings", "partial"}:
            raise InventoryError("neispravna polja inventara")
        fields = {"id", "kind", "name", "description", "locations", "evidence", "metadata", "duplicate_group"}
        if not isinstance(data["items"], list) or any(not isinstance(raw, dict) or set(raw) != fields for raw in data["items"]):
            raise InventoryError("neispravna polja stavke")
        inv = Inventory(
            schema_version=data["schema_version"],
            scanned_at=data["scanned_at"],
            items=[
                Item(
                    id=raw["id"],
                    kind=raw["kind"],
                    name=raw["name"],
                    description=raw["description"],
                    locations=[Location(**loc) for loc in raw["locations"]],
                    evidence=raw["evidence"],
                    metadata=raw["metadata"],
                    duplicate_group=raw["duplicate_group"],
                )
                for raw in data["items"]
            ],
            relations=[Relation(**rel) for rel in data["relations"]],
            warnings=[ScanWarning(**w) for w in data["warnings"]],
            partial=data["partial"],
        )
    except (KeyError, TypeError) as exc:
        raise InventoryError(f"neispravna struktura inventara ({type(exc).__name__})") from None
    validate_inventory(inv)
    return inv


def canonical_json(inv: Inventory, *, include_time: bool = True) -> str:
    data = inventory_to_dict(inv)
    if not include_time:
        data.pop("scanned_at")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def inventory_hash(inv: Inventory) -> str:
    return hashlib.sha256(canonical_json(inv, include_time=False).encode("utf-8")).hexdigest()
