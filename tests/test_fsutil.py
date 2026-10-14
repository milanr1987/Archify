import os
import unittest

from helpers import TempDirTestCase, make_dir_link, write

from atlas.frontmatter import FrontmatterError, parse_frontmatter, parse_frontmatter_lenient
from atlas.fsutil import FileTooLarge, FsOps, find_skill_files, is_within, link_info, read_text_limited
from atlas.identity import norm_path
from atlas.textutil import clean_text


class FakeFs:
    """Lažni fajl sistem sa Windows separatorima i linkovima."""

    def __init__(self, dirs, files=(), links=None):
        self.dirs = {d: list(c) for d, c in dirs.items()}
        self.files = set(files)
        self.links = dict(links or {})

    def realpath(self, path):
        parts = path.split("\\")
        current = parts[0]
        for part in parts[1:]:
            current = current + "\\" + part
            hops = 0
            while current in self.links and hops < 40:
                current = self.links[current]
                hops += 1
        return current

    def listdir(self, path):
        return list(self.dirs[self.realpath(path)])

    def isdir(self, path):
        return self.realpath(path) in self.dirs

    def isfile(self, path):
        return self.realpath(path) in self.files

    def lexists(self, path):
        return path in self.links or self.isdir(path) or self.isfile(path)

    def ops(self):
        return FsOps(listdir=self.listdir, isdir=self.isdir, isfile=self.isfile,
                     realpath=self.realpath, lexists=self.lexists)


@unittest.skipUnless(os.name == "nt", "lažni FS koristi Windows separatore")
class WalkerTests(unittest.TestCase):
    def setUp(self):
        r = "R:\\root"
        self.fs = FakeFs(
            dirs={
                r: ["a", "broken", "deep", "loop-parent", "node_modules"],
                r + "\\a": ["SKILL.md", "sub"],
                r + "\\a\\sub": ["SKILL.md"],
                r + "\\deep": ["d1"],
                r + "\\deep\\d1": ["d2"],
                r + "\\deep\\d1\\d2": ["d3"],
                r + "\\deep\\d1\\d2\\d3": ["d4"],
                r + "\\deep\\d1\\d2\\d3\\d4": ["SKILL.md"],
                r + "\\loop-parent": ["loop"],
                r + "\\node_modules": ["SKILL.md"],
            },
            files={r + "\\a\\SKILL.md", r + "\\a\\sub\\SKILL.md",
                   r + "\\deep\\d1\\d2\\d3\\d4\\SKILL.md", r + "\\node_modules\\SKILL.md"},
            links={r + "\\loop-parent\\loop": r + "\\loop-parent", r + "\\broken": "R:\\nowhere"},
        )
        self.root = r

    def test_finds_skill_and_stops_below_it(self):
        found, _ = find_skill_files(self.root, frozenset({"node_modules"}), ops=self.fs.ops())
        self.assertEqual(found, [self.root + "\\a\\SKILL.md"])

    def test_reports_cycle_and_broken_link_without_stopping(self):
        _, problems = find_skill_files(self.root, frozenset({"node_modules"}), ops=self.fs.ops())
        self.assertEqual(set(problems), {
            ("broken-link", self.root + "\\broken"),
            ("link-cycle", self.root + "\\loop-parent\\loop"),
        })

    def test_depth_limit(self):
        found, _ = find_skill_files(self.root, frozenset({"node_modules"}), max_depth=6, ops=self.fs.ops())
        self.assertIn(self.root + "\\deep\\d1\\d2\\d3\\d4\\SKILL.md", found)

    def test_excluded_names_are_skipped(self):
        found, _ = find_skill_files(self.root, frozenset(), ops=self.fs.ops())
        self.assertIn(self.root + "\\node_modules\\SKILL.md", found)


class RealFsTests(TempDirTestCase):
    def test_read_text_limited_rejects_large_file(self):
        path = write(self.tmp / "big.md", "x" * 2048)
        with self.assertRaises(FileTooLarge):
            read_text_limited(str(path), limit=1024)
        self.assertEqual(read_text_limited(str(path), limit=4096), "x" * 2048)

    def test_is_within_uses_path_components(self):
        self.assertTrue(is_within(str(self.tmp / "a" / "b"), str(self.tmp / "a")))
        self.assertTrue(is_within(str(self.tmp / "a"), str(self.tmp / "a")))
        self.assertFalse(is_within(str(self.tmp / "ab"), str(self.tmp / "a")))

    def test_link_info_detects_linked_ancestor(self):
        target = self.tmp / "target"
        write(target / "f.txt", "x")
        make_dir_link(self.tmp / "link", target)
        via, real = link_info(str(self.tmp / "link" / "f.txt"))
        self.assertTrue(via)
        self.assertEqual(norm_path(real), norm_path(target / "f.txt"))
        self.assertEqual(link_info(str(target / "f.txt")), (False, None))

    def test_real_walk_through_junction_records_logical_path(self):
        write(self.tmp / "real" / "s1" / "SKILL.md", "---\nname: s1\n---\n")
        make_dir_link(self.tmp / "root" / "s1", self.tmp / "real" / "s1")
        found, problems = find_skill_files(str(self.tmp / "root"), frozenset())
        self.assertEqual(found, [str(self.tmp / "root" / "s1" / "SKILL.md")])
        self.assertEqual(problems, [])


class FrontmatterTests(unittest.TestCase):
    def test_parses_name_and_description(self):
        data = parse_frontmatter("---\nname: a\ndescription: b\n---\nbody")
        self.assertEqual((data["name"], data["description"]), ("a", "b"))

    def test_bom_and_crlf(self):
        data = parse_frontmatter("\ufeff---\r\nname: x\r\ndescription: y\r\n---\r\nbody")
        self.assertEqual(data["name"], "x")

    def test_errors_do_not_leak_content(self):
        for text in ("bez frontmattera", "---\nname: a\n", "---\n- a\n---\n", "---\nname: [TAJNO\n---\n"):
            with self.assertRaises(FrontmatterError) as ctx:
                parse_frontmatter(text)
            self.assertNotIn("TAJNO", str(ctx.exception))

    def test_lenient_reads_plain_lines_with_inner_colons(self):
        text = '---\nname: ab-ideja\ndescription: Radi X. Argumenti opciono: proizvod ("/ab-ideja payment").\n---\nbody'
        with self.assertRaises(FrontmatterError):
            parse_frontmatter(text)
        data = parse_frontmatter_lenient(text)
        self.assertEqual(data["name"], "ab-ideja")
        self.assertEqual(data["description"], 'Radi X. Argumenti opciono: proizvod ("/ab-ideja payment").')

    def test_lenient_rejects_flow_and_nested_values(self):
        for text in ("---\nname: [TAJNO\n---\n", "---\n  name: uvuceno\n---\n", "bez frontmattera",
                     "---\nname: |\n  blok\n---\n"):
            with self.assertRaises(FrontmatterError) as ctx:
                parse_frontmatter_lenient(text)
            self.assertNotIn("TAJNO", str(ctx.exception))

    def test_lenient_strips_matching_quotes(self):
        data = parse_frontmatter_lenient("---\nname: 'x'\ndescription: \"y: z\"\n---\n")
        self.assertEqual((data["name"], data["description"]), ("x", "y: z"))


class CleanTextTests(unittest.TestCase):
    def test_collapses_whitespace_and_removes_control_chars(self):
        self.assertEqual(clean_text("a\n\t b\x00c"), "a bc")

    def test_truncates_with_ellipsis(self):
        out = clean_text("x" * 600, 500)
        self.assertEqual(len(out), 500)
        self.assertTrue(out.endswith("…"))

    def test_none_and_numbers(self):
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(12), "12")


if __name__ == "__main__":
    unittest.main()
