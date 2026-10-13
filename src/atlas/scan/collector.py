"""Zajednički skup nalaza svih skenera."""
from __future__ import annotations

from dataclasses import dataclass

from atlas.model import Item, Relation, ScanWarning

DEFAULT_MAX_ITEMS = 5000


@dataclass(frozen=True)
class SourceStatus:
    kind: str
    path: str
    status: str  # read | missing | error


class Collector:
    def __init__(self, max_items: int = DEFAULT_MAX_ITEMS) -> None:
        self.items: dict[str, Item] = {}
        self.relations: set[Relation] = set()
        self.warnings: list[ScanWarning] = []
        self.sources: list[SourceStatus] = []
        self.max_items = max_items
        self.limit_hit = False
        self._location_keys: dict[str, set[tuple[str, str, str, str]]] = {}

    def add_item(self, item: Item) -> bool:
        existing = self.items.get(item.id)
        if existing is None:
            if len(self.items) >= self.max_items:
                if not self.limit_hit:
                    self.limit_hit = True
                    self.warn("warn", "item-limit", "",
                              f"dostignut limit od {self.max_items} stavki; ostatak nije skeniran")
                return False
            self.items[item.id] = item
            self._location_keys[item.id] = {loc.key() for loc in item.locations}
            if len(self.items) >= self.max_items:
                self.limit_hit = True
                self.warn("warn", "item-limit", "", f"dostignut limit od {self.max_items} stavki; dalji izvori nisu skenirani")
            return True
        seen = self._location_keys[item.id]
        for loc in item.locations:
            if loc.key() not in seen:
                seen.add(loc.key())
                existing.locations.append(loc)
        return True

    def relate(self, source: str, target: str, type_: str) -> None:
        self.relations.add(Relation(source, target, type_))

    def warn(self, severity: str, code: str, source: object, message: str) -> None:
        self.warnings.append(ScanWarning(severity, code, str(source), message))

    def source(self, kind: str, path: object, status: str) -> None:
        self.sources.append(SourceStatus(kind, str(path), status))
