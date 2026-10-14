import json
import os
import statistics
import tempfile
import unittest
from pathlib import Path

from atlas.catalog import render_catalog
from atlas.overlay import Note, Overlay
from atlas.identity import make_id
from atlas.model import SCHEMA_VERSION, Inventory, Item, Location, Relation, ScanWarning, inventory_hash, validate_inventory

E2E = os.environ.get("ATLAS_E2E") == "1"
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "output" / "e2e"
XSS = "</script><img src=x onerror=alert(1)>"
QUERIES = ["skill", "opis", "gen", "0042", "brzine", "claude", "max", "agents", "pretrage", "broj 1",
           "skill-01", "skill-19", "nema-ovoga", "c:\\gen", "generisani", "test", "za", "1999", "0", "s"]


def synthetic_inventory(extra: int = 0) -> tuple[Inventory, dict[str, str]]:
    items: list[Item] = []

    def add(kind, name, desc, locs, metadata=None, group=None):
        item = Item(make_id(kind, name, str(len(items))), kind, name, desc, locs, "observed", metadata or {}, group)
        items.append(item)
        return item

    plugin = add("plugin", "superpowers", "Core skills",
                 [Location("C:\\p\\superpowers", "max", root_label="plugins (max)")],
                 {"marketplace": "official", "scope": "user", "version": "6.4.1"})
    cross = add("skill", "cross-skill", "Skill na dva mjesta", [
        Location("C:\\h\\.claude\\skills\\cross", "claude", origin="standalone", root_label=".claude"),
        Location("C:\\p\\superpowers\\skills\\cross", "max", origin=f"plugin:{plugin.id}",
                 root_label="plugin superpowers@official"),
    ])
    fire = add("skill", "firecrawl", "Web scraping", [
        Location("C:\\h\\.agents\\skills\\firecrawl", "agents", origin="standalone", root_label=".agents"),
        Location("C:\\h\\.claude\\skills\\firecrawl", "claude", via_link=True,
                 link_target="C:\\h\\.agents\\skills\\firecrawl", origin="standalone", root_label=".claude"),
    ])
    add("skill", XSS, "napad kroz naslov", [Location("C:\\h\\x", "max", origin="standalone")])
    add("project", "Đurđevak alat", "Projekat sa dijakritikom", [Location("C:\\ws\\durdevak")], {"projectType": "python"})
    add("document", "ćevapi recept", "", [Location("C:\\ws\\cevapi.md")], {"referenceStatus": "listed"})
    add("mcp", "github", "", [Location("C:\\h\\.claude.json", "claude", root_label="claude-json")],
        {"transport": "stdio", "scope": "user", "sourceFormat": "claude-json",
         "executableName": "npx.cmd", "envNames": ["GITHUB_TOKEN"]})
    add("skill", "dupe", "prvi", [Location("C:\\a\\dupe", "claude", origin="standalone")], group="skill:dupe")
    add("skill", "dupe", "drugi", [Location("C:\\b\\dupe", "max", origin="standalone")], group="skill:dupe")
    for i in range(extra):
        add("skill", f"generisani-skill-{i:04d}", f"Opis broj {i} za test brzine pretrage",
            [Location(f"C:\\gen\\skill-{i:04d}", ("claude", "max", "agents")[i % 3], origin="standalone")])
    items.sort(key=lambda it: (it.kind, it.name.lower(), it.id))
    inv = Inventory(SCHEMA_VERSION, "2026-10-13T12:00:00+02:00", items,
                    [Relation(plugin.id, cross.id, "contains")],
                    [ScanWarning("warn", "bad-frontmatter", "C:\\h\\broken\\SKILL.md", "neispravan YAML")], True)
    validate_inventory(inv)
    return inv, {"fire": fire.id, "cross": cross.id}


@unittest.skipUnless(E2E, "browser test: postavi ATLAS_E2E=1 (komanda je u README)")
class CatalogBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sync_playwright is None:
            raise RuntimeError("ATLAS_E2E=1, ali Playwright nije instaliran u .venv. Browser provjera NIJE obavljena.")
        cls._tmp = tempfile.TemporaryDirectory(prefix="atlas e2e čćž ")
        tmp = Path(cls._tmp.name)
        small, cls.ids = synthetic_inventory()
        cls.small = tmp / "mali katalog.html"
        cls.small.write_text(render_catalog(small, inventory_hash(small)), encoding="utf-8")
        cls.notes = tmp / 'biljeske.html'
        cls.notes.write_text(render_catalog(small, inventory_hash(small),
            Overlay({cls.ids['fire']: Note(XSS + ' moja bilješka', ['Đurđevak'])})), encoding='utf-8')
        project = next(it for it in small.items if it.kind == 'project')
        cls.map_fixture = tmp / 'map-katalog.html'
        cls.map_fixture.write_text(render_catalog(small,inventory_hash(small),maps=[{
            'projectId':project.id,'title':'Demo mapa','htmlPath':'maps/demo.html',
            'analysisPath':'analysis/demo.json','generatedAt':small.scanned_at,
            'sourceFingerprint':'b'*64,'status':'stale'}]),encoding='utf-8')
        (tmp/'maps').mkdir()
        (tmp/'maps/demo.html').write_text('<html><body><p id="demo">Local map</p></body></html>',encoding='utf-8')
        perf, _ = synthetic_inventory(extra=2000)
        cls.perf_count = len(perf.items)
        cls.perf = tmp / "perf.html"
        cls.perf.write_text(render_catalog(perf, inventory_hash(perf)), encoding="utf-8")
        big, _ = synthetic_inventory(extra=5000)
        cls.big = tmp / "big.html"
        cls.big.write_text(render_catalog(big, inventory_hash(big)), encoding="utf-8")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls._tmp.cleanup()

    def open_page(self, path, width=1440, height=900, fragment=""):
        context = self.browser.new_context(viewport={"width": width, "height": height})
        self.addCleanup(context.close)
        page = context.new_page()
        self.requests, self.dialogs = [], []
        page.on("request", lambda r: self.requests.append(r.url))
        page.on("dialog", lambda d: (self.dialogs.append(d.message), d.dismiss()))
        page.goto(path.as_uri() + fragment)
        return page

    def names(self, page):
        return page.locator("#list .row-name").all_text_contents()

    def test_no_network_and_xss_is_plain_text(self):
        page = self.open_page(self.small)
        page.fill("#search", "script")
        self.assertIn(XSS, self.names(page))
        self.assertEqual(page.locator("img").count(), 0)
        self.assertEqual(self.dialogs, [])
        self.assertEqual([u for u in self.requests if not u.startswith(("file:", "data:"))], [])

    def test_notes_search_and_safe_display(self):
        page = self.open_page(self.notes)
        page.fill('#search', 'moja biljeska')
        self.assertEqual(self.names(page), ['firecrawl'])
        page.locator('#list .row').click()
        self.assertEqual(page.locator('.item-id').text_content(), self.ids['fire'])
        self.assertEqual(page.locator('.detail-note').text_content(), XSS + ' moja bilješka')
        self.assertEqual(page.locator('.note-tags').text_content(), 'Đurđevak')
        page.fill('#search', 'djurdjevak')
        self.assertIn('firecrawl', self.names(page))
        self.assertEqual(page.locator('img').count(), 0)
        self.assertEqual(self.dialogs, [])
        self.assertEqual([u for u in self.requests if not u.startswith(('file:', 'data:'))], [])

    def test_map_status_and_relative_link(self):
        page = self.open_page(self.map_fixture)
        page.fill('#search','djurdjevak')
        page.locator('#list .row').click()
        self.assertEqual(page.locator('.map-status').text_content(),'Mapa: Zastarjela')
        self.assertEqual(page.locator('.map-link').get_attribute('href'),'maps/demo.html')
        page.locator('.map-link').click()
        self.assertEqual(page.locator('#demo').text_content(),'Local map')
        self.assertEqual([u for u in self.requests if not u.startswith(('file:','data:'))], [])

    def test_search_folds_diacritics(self):
        page = self.open_page(self.small)
        page.fill("#search", "djurdjevak")
        self.assertEqual(self.names(page), ["Đurđevak alat"])
        self.assertEqual(page.locator("#count").text_content(), "1 stavka")
        page.fill("#search", "cevapi")
        self.assertEqual(self.names(page), ["ćevapi recept"])

    def test_profile_and_origin_must_match_same_location(self):
        page = self.open_page(self.small)
        page.check("#f-profile input[value='claude']")
        page.check("input[name='origin'][value='plugin']")
        self.assertNotIn("cross-skill", self.names(page))
        page.check("input[name='origin'][value='standalone']")
        self.assertIn("cross-skill", self.names(page))
        page.uncheck("#f-profile input[value='claude']")
        page.check("#f-profile input[value='max']")
        page.check("input[name='origin'][value='plugin']")
        self.assertIn("cross-skill", self.names(page))
        page.click("#clear-filters")
        self.assertEqual(page.locator("#count").text_content(), "8 stavki")

    def test_list_scrolls_inside_its_box_and_page_stays_put(self):
        page = self.open_page(self.perf, width=1440, height=900)
        sizes = page.evaluate("""() => {
            const list = document.getElementById('list');
            return {listScroll: list.scrollHeight, listClient: list.clientHeight,
                    overflow: getComputedStyle(list).overflowY,
                    pageScroll: document.documentElement.scrollHeight, viewport: window.innerHeight,
                    more: document.getElementById('more').getBoundingClientRect().bottom};
        }""")
        self.assertEqual(sizes["overflow"], "auto")
        self.assertGreater(sizes["listScroll"], sizes["listClient"])
        self.assertLessEqual(sizes["pageScroll"], sizes["viewport"] + 1)
        self.assertLessEqual(sizes["more"], sizes["viewport"])
        page.focus("#list")
        for _ in range(30):
            page.keyboard.press("ArrowDown")
        self.assertGreater(page.evaluate("document.getElementById('list').scrollTop"), 0)

    def test_same_name_items_are_grouped_into_one_row(self):
        page = self.open_page(self.small)
        page.fill("#search", "dupe")
        self.assertEqual(self.names(page), ["dupe"])
        badges = page.locator("#list .row .badge").all_text_contents()
        self.assertIn("×2", badges)
        self.assertTrue({"claude", "max"} <= set(badges))
        page.locator("#list li.row").first.click()
        page.wait_for_selector("#detail-title")
        instances = page.locator(".instances li")
        self.assertEqual(instances.count(), 2)
        self.assertIn("Sve instance (2)", page.locator("#detail-body").text_content())
        page.uncheck("#f-group")
        self.assertEqual(self.names(page), ["dupe", "dupe"])
        page.click("#clear-filters")
        self.assertFalse(page.is_checked("#f-group"))
        page.check("#f-group")
        page.fill("#search", "")
        self.assertEqual(page.locator("#count").text_content(), "8 stavki")

    def test_commands_agents_hooks_render_and_filter_by_origin(self):
        plugin = Item(make_id("plugin", "tk"), "plugin", "toolkit", "", [Location("C:\\p\\tk", "max")],
                      "observed", {"scope": "user"}, None)
        items = [plugin,
            Item(make_id("command", "deploy"), "command", "deploy", "Deploy app",
                 [Location("C:\\p\\tk\\commands\\deploy.md", "max", origin=f"plugin:{plugin.id}")], "observed", {}, None),
            Item(make_id("command", "review"), "command", "review", "Pregled",
                 [Location("C:\\h\\.claude\\commands\\review.md", "claude", origin="standalone")], "observed", {}, None),
            Item(make_id("agent", "planner"), "agent", "planner", "Planira",
                 [Location("C:\\h\\.claude\\agents\\planner.md", "claude", origin="standalone")], "observed", {}, None),
            Item(make_id("hook", "pre"), "hook", "PreToolUse · Bash", "",
                 [Location("C:\\h\\.claude\\settings.json", "claude", origin="standalone")], "observed",
                 {"event": "PreToolUse", "matcher": "Bash", "hookCount": "2", "hookTypes": ["command"]}, None)]
        items.sort(key=lambda it: (it.kind, it.name.lower(), it.id))
        inv = Inventory(SCHEMA_VERSION, "2026-10-14T12:00:00+02:00", items, [], [], False)
        validate_inventory(inv)
        path = Path(self._tmp.name) / "prosirenja.html"
        path.write_text(render_catalog(inv, inventory_hash(inv)), encoding="utf-8")
        page = self.open_page(path)
        self.assertEqual(page.locator("#counters .counter").count(), 8)
        page.check("#f-kind input[value='command']")
        self.assertEqual(sorted(self.names(page)), ["deploy", "review"])
        page.check("input[name='origin'][value='plugin']")
        self.assertEqual(self.names(page), ["deploy"])
        page.click("#clear-filters")
        page.fill("#search", "bash")
        page.locator("#list li.row").first.click()
        page.wait_for_selector("#detail-title")
        self.assertEqual(page.locator("#detail-title").text_content(), "PreToolUse · Bash")
        detail = page.locator("#detail-body").text_content()
        self.assertIn("Broj hookova", detail)
        self.assertIn("ne provjerava da li se izvršava", detail)
        self.assertEqual([u for u in self.requests if u.startswith("http")], [])

    def test_keyboard_flow_detail_and_escape(self):
        page = self.open_page(self.small)
        page.keyboard.press("/")
        self.assertEqual(page.evaluate("document.activeElement.id"), "search")
        page.keyboard.type("fire/crawl")
        self.assertEqual(page.input_value("#search"), "fire/crawl")
        page.fill("#search", "firecrawl")
        page.focus("#list")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        self.assertEqual(page.locator("#detail-title").text_content(), "firecrawl")
        self.assertIn("preko linka", page.locator("#detail-body").text_content())
        page.keyboard.press("Escape")
        page.wait_for_function("document.getElementById('detail-title') === null")
        self.assertIn(page.evaluate("location.hash"), ("", "#"))

    def test_hash_restores_selection_and_copy_reports_status(self):
        page = self.open_page(self.small, fragment="#" + self.ids["fire"])
        self.assertEqual(page.locator("#detail-title").text_content(), "firecrawl")
        page.locator("button.copy").first.click()
        page.wait_for_function("document.querySelector('.copy-status').textContent.length > 0")
        self.assertIn(page.locator(".copy-status").first.text_content(),
                      ("Putanja kopirana.", "Putanja je označena. Kopiraj sa Ctrl+C."))

    def test_partial_banner_lists_warnings(self):
        page = self.open_page(self.small)
        self.assertIn("Djelimičan pregled: 1 upozorenje", page.locator("#partial-toggle").text_content())
        page.click("#partial-toggle")
        self.assertIn("bad-frontmatter", page.locator("#warning-list").text_content())

    def test_layouts_have_no_horizontal_scroll(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        for width, height in ((1440, 900), (390, 844)):
            page = self.open_page(self.small, width, height, "#" + self.ids["fire"])
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            self.assertLessEqual(overflow, 0, f"horizontalni scroll na {width}x{height}")
            page.screenshot(path=str(ARTIFACTS / f"catalog-{width}x{height}.png"), full_page=True)
        self.assertTrue(page.locator("#back").is_visible())
        page.click("#back")
        page.wait_for_selector("#results", state="visible")
        self.assertFalse(page.locator("#detail").is_visible())

    def test_search_latency_with_2000_items(self):
        page = self.open_page(self.perf)
        times = page.evaluate(
            """async (queries) => {
                const input = document.getElementById('search');
                const out = [];
                for (const q of queries) {
                    const t0 = performance.now();
                    input.value = q;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    await new Promise((resolve) => requestAnimationFrame(() => resolve()));
                    out.push(performance.now() - t0);
                }
                return out;
            }""",
            QUERIES,
        )
        median = statistics.median(times)
        p95 = statistics.quantiles(times, n=20)[18]
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        (ARTIFACTS / "perf.json").write_text(json.dumps({
            "items": self.perf_count, "queries": len(times), "median_ms": round(median, 2),
            "p95_ms": round(p95, 2), "browser": f"chromium {self.browser.version}",
        }, indent=2), encoding="utf-8")
        # Spec cilj je p95 < 50 ms na lokalnom računaru; CI runner je sporiji pa postavlja svoju granicu.
        self.assertLess(p95, float(os.environ.get("ATLAS_PERF_P95_MS", "50")))

    def test_5000_items_stay_usable(self):
        page = self.open_page(self.big)
        self.assertEqual(page.locator("#list li.row").count(), 300)
        self.assertTrue(page.locator("#more").is_visible())
        page.click("#more")
        self.assertEqual(page.locator("#list li.row").count(), 600)
        page.fill("#search", "skill-4999")
        self.assertEqual(self.names(page), ["generisani-skill-4999"])


if __name__ == "__main__":
    unittest.main()
