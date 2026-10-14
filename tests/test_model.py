import json
import unittest

from atlas.identity import make_id
from atlas.model import (
    SCHEMA_VERSION,
    Inventory,
    InventoryError,
    Item,
    Location,
    Relation,
    ScanWarning,
    canonical_json,
    inventory_from_dict,
    inventory_hash,
    validate_inventory,
)


def item(name="a", kind="skill", **kw):
    return Item(
        id=make_id(kind, name),
        kind=kind,
        name=name,
        description="",
        locations=[Location(path="C:\\x\\" + name, profile="max")],
        **kw,
    )


def inventory(items, relations=(), warnings=(), scanned="2026-10-13T10:00:00+02:00"):
    return Inventory(SCHEMA_VERSION, scanned, list(items), list(relations), list(warnings), False)


class ValidationTests(unittest.TestCase):
    def test_valid_inventory_passes(self):
        validate_inventory(inventory([item("a"), item("b", kind="mcp", metadata={"transport": "stdio"})]))

    def test_unknown_metadata_key_rejected(self):
        with self.assertRaises(InventoryError) as ctx:
            validate_inventory(inventory([item("m", kind="mcp", metadata={"args": "x"})]))
        self.assertIn("args", str(ctx.exception))

    def test_list_metadata_must_be_list_of_strings(self):
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([item("p", kind="project", metadata={"scriptNames": "start"})]))

    def test_string_metadata_must_be_string(self):
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([item("m", kind="mcp", metadata={"transport": ["stdio"]})]))

    def test_duplicate_id_rejected(self):
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([item("a"), item("a")]))

    def test_relation_to_missing_item_rejected(self):
        a = item("a")
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([a], relations=[Relation(a.id, "f" * 64, "contains")]))

    def test_bad_kind_rejected(self):
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([item("a", kind="widget")]))

    def test_item_without_location_rejected(self):
        bad = item("a")
        bad.locations = []
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([bad]))

    def test_bad_warning_severity_rejected(self):
        with self.assertRaises(InventoryError):
            validate_inventory(inventory([item("a")], warnings=[ScanWarning("error", "x", "y", "z")]))


class SerializationTests(unittest.TestCase):
    def test_roundtrip(self):
        a, b = item("a"), item("b", kind="plugin", metadata={"version": "1"})
        inv = inventory([a, b], relations=[Relation(b.id, a.id, "contains")],
                        warnings=[ScanWarning("warn", "bad-json", "C:\\x", "neispravan JSON")])
        self.assertEqual(inventory_from_dict(json.loads(canonical_json(inv))), inv)

    def test_unknown_location_field_rejected(self):
        data = json.loads(canonical_json(inventory([item("a")])))
        data["items"][0]["locations"][0]["secret"] = "x"
        with self.assertRaises(InventoryError):
            inventory_from_dict(data)

    def test_hash_ignores_scan_time_but_not_content(self):
        one = inventory([item("a")], scanned="2026-10-13T10:00:00+02:00")
        two = inventory([item("a")], scanned="2026-10-14T11:00:00+02:00")
        three = inventory([item("b")])
        self.assertEqual(inventory_hash(one), inventory_hash(two))
        self.assertNotEqual(inventory_hash(one), inventory_hash(three))


if __name__ == "__main__":
    unittest.main()
