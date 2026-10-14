from collections import Counter
from datetime import datetime, timezone

from helpers import TempDirTestCase, make_fixture, skill_md, write

from atlas.config import parse_config
from atlas.inventory import build_inventory
from atlas.model import canonical_json, inventory_hash, validate_inventory
from atlas.report import render_report

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


class InventoryTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.config = parse_config(make_fixture(self.tmp))

    def test_counts_per_kind(self):
        inv = build_inventory(self.config, now=NOW).inventory
        validate_inventory(inv)
        self.assertEqual(Counter(i.kind for i in inv.items),
                         Counter({"skill": 7, "mcp": 6, "project": 3, "plugin": 2, "document": 2, "hook": 1}))

    def test_duplicate_group_for_same_name(self):
        inv = build_inventory(self.config, now=NOW).inventory
        creators = [i for i in inv.items if i.kind == "skill" and i.name == "skill-creator"]
        self.assertEqual(len(creators), 2)
        self.assertEqual({i.duplicate_group for i in creators}, {"skill:skill-creator"})
        firecrawl = [i for i in inv.items if i.name == "firecrawl"][0]
        self.assertIsNone(firecrawl.duplicate_group)

    def test_two_scans_are_identical(self):
        one = build_inventory(self.config, now=NOW).inventory
        two = build_inventory(self.config, now=NOW).inventory
        self.assertEqual(canonical_json(one), canonical_json(two))

    def test_sorted_items_and_locations(self):
        inv = build_inventory(self.config, now=NOW).inventory
        keys = [(i.kind, i.name.lower(), i.id) for i in inv.items]
        self.assertEqual(keys, sorted(keys))
        for item in inv.items:
            paths = [l.path.lower() for l in item.locations]
            self.assertEqual(paths, sorted(paths))

    def test_bad_frontmatter_makes_partial(self):
        self.assertTrue(build_inventory(self.config, now=NOW).inventory.partial)

    def test_item_limit(self):
        inv = build_inventory(self.config, now=NOW, max_items=3).inventory
        self.assertEqual(len(inv.items), 3)
        self.assertTrue(inv.partial)
        self.assertIn("item-limit", [w.code for w in inv.warnings])
        validate_inventory(inv)

    def test_clean_source_is_not_partial(self):
        write(self.tmp / "clean/skills/a/SKILL.md", skill_md("a", "b"))
        cfg = parse_config({"workspaceRoot": str(self.tmp / "clean"), "skillRoots": [
            {"path": str(self.tmp / "clean/skills"), "profile": "max", "label": "m"}]})
        inv = build_inventory(cfg, now=NOW).inventory
        self.assertFalse(inv.partial)
        self.assertEqual(inv.warnings, [])

    def test_report_has_hash_counts_sources_and_warnings(self):
        outcome = build_inventory(self.config, now=NOW)
        h = inventory_hash(outcome.inventory)
        report = render_report(outcome, h)
        self.assertIn(f"Hash inventara: `{h}`", report)
        self.assertIn("| skill | 7 |", report)
        self.assertIn("| max |", report)
        self.assertIn("### bad-frontmatter (1)", report)
        self.assertIn("| plugin-registry |", report)
        self.assertIn("djelimičan pregled", report)
