import unittest

from helpers import TempDirTestCase, make_dir_link, skill_md, write

from atlas.config import allowed_roots, parse_config
from atlas.identity import make_id, norm_path
from atlas.model import Item, Location
from atlas.scan.collector import Collector
from atlas.scan.skills import SkillReader, scan_skills


class CollectorTests(unittest.TestCase):
    def test_merge_keeps_distinct_locations_once(self):
        c = Collector()
        iid = make_id("skill", "x")
        c.add_item(Item(iid, "skill", "x", locations=[Location("C:\\a", "max")]))
        c.add_item(Item(iid, "skill", "x", locations=[Location("C:\\a", "max"), Location("C:\\b", "pro")]))
        self.assertEqual([l.path for l in c.items[iid].locations], ["C:\\a", "C:\\b"])

    def test_limit_stops_new_items_with_one_warning(self):
        c = Collector(max_items=1)
        self.assertTrue(c.add_item(Item(make_id("skill", "a"), "skill", "a", locations=[Location("C:\\a")])))
        self.assertFalse(c.add_item(Item(make_id("skill", "b"), "skill", "b", locations=[Location("C:\\b")])))
        self.assertFalse(c.add_item(Item(make_id("skill", "c"), "skill", "c", locations=[Location("C:\\c")])))
        self.assertTrue(c.limit_hit)
        self.assertEqual([w.code for w in c.warnings], ["item-limit"])


class SkillScanTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        h = self.tmp / "home"
        write(h / ".agents/skills/firecrawl/SKILL.md", skill_md("firecrawl", "Web scraping"))
        (h / ".claude/skills").mkdir(parents=True)
        make_dir_link(h / ".claude/skills/firecrawl", h / ".agents/skills/firecrawl")
        write(h / ".claude/skills/own/SKILL.md", skill_md("own", "Moj skill"))
        write(h / ".claude-max/skills/maxskill/SKILL.md", skill_md("maxskill", "Max skill"))
        write(h / ".claude-max/skills/broken/SKILL.md", "---\nname: [nezatvoreno\n---\n")
        write(h / ".claude-max/skills/odd/SKILL.md", "---\nname: [a, b]\ndescription: {x: 1}\n---\n")
        (h / ".claude-pro").mkdir()
        make_dir_link(h / ".claude-pro/skills", h / ".claude-max/skills")
        self.home = h

    def config(self, extra_roots=()):
        h = self.home
        roots = [
            {"path": str(h / ".agents/skills"), "profile": "agents", "label": ".agents"},
            {"path": str(h / ".claude/skills"), "profile": "claude", "label": ".claude"},
            {"path": str(h / ".claude-max/skills"), "profile": "max", "label": ".claude-max"},
            {"path": str(h / ".claude-pro/skills"), "profile": "pro", "label": ".claude-pro"},
            *extra_roots,
        ]
        return parse_config({"workspaceRoot": str(self.tmp / "ws"), "skillRoots": roots})

    def scan(self, config):
        c = Collector()
        scan_skills(config, c, SkillReader(c), allowed_roots(config))
        return c

    def named(self, c, name):
        return [i for i in c.items.values() if i.name == name]

    def test_link_into_other_root_is_one_item_with_two_locations(self):
        c = self.scan(self.config())
        [fire] = self.named(c, "firecrawl")
        self.assertEqual({l.profile for l in fire.locations}, {"agents", "claude"})
        linked = [l for l in fire.locations if l.profile == "claude"][0]
        self.assertTrue(linked.via_link)
        self.assertEqual(norm_path(linked.link_target), norm_path(self.home / ".agents/skills/firecrawl"))
        self.assertTrue(all(l.origin == "standalone" for l in fire.locations))

    def test_linked_profile_root_adds_profile_without_losing_it(self):
        c = self.scan(self.config())
        [skill] = self.named(c, "maxskill")
        self.assertEqual({l.profile for l in skill.locations}, {"max", "pro"})
        self.assertEqual({l.root_label for l in skill.locations}, {".claude-max", ".claude-pro"})

    def test_bad_frontmatter_keeps_item_with_warning(self):
        c = self.scan(self.config())
        [broken] = self.named(c, "broken")
        self.assertEqual(broken.description, "")
        codes = [(w.code, w.severity) for w in c.warnings if "broken" in w.source]
        self.assertEqual(codes, [("bad-frontmatter", "warn")])

    def test_non_string_frontmatter_values(self):
        cases = (123, ["x"], {"x": 1}, True)
        import yaml
        for field in ("name", "description"):
            for n, value in enumerate(cases):
                with self.subTest(field=field, value=value):
                    folder = self.tmp / f"non-string-{field}-{n}"
                    payload = {"name": "valid", "description": "valid"}
                    payload[field] = value
                    path = write(folder / "SKILL.md", "---\n" + yaml.safe_dump(payload) + "---\n")
                    collector = Collector()
                    name, description = SkillReader(collector).read(str(path))
                    self.assertEqual((name, description), (folder.name, ""))
                    self.assertEqual([w.code for w in collector.warnings], ["bad-frontmatter"])

    def test_link_outside_roots_is_info_only(self):
        write(self.tmp / "outside/abx/SKILL.md", skill_md("abx", "Van korijena"))
        make_dir_link(self.home / ".claude/skills/abx", self.tmp / "outside/abx")
        c = self.scan(self.config())
        self.assertEqual(len(self.named(c, "abx")), 1)
        infos = [w for w in c.warnings if w.code == "link-outside-roots"]
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].severity, "info")

    def test_missing_root_warns_and_others_continue(self):
        cfg = self.config(extra_roots=[{"path": str(self.tmp / "nema"), "profile": "x", "label": "nema"}])
        c = self.scan(cfg)
        self.assertIn("source-missing", [w.code for w in c.warnings])
        self.assertEqual(len(self.named(c, "own")), 1)
        self.assertIn(("skill-root", str(self.tmp / "nema"), "missing"),
                      [(s.kind, s.path, s.status) for s in c.sources])


if __name__ == "__main__":
    unittest.main()
