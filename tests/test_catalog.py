import json
import unittest
from pathlib import Path

from atlas.catalog import CSP, DATA_OPEN, embed_json, render_catalog, validate_catalog
from atlas.identity import make_id
from atlas.model import SCHEMA_VERSION, Inventory, Item, Location, inventory_hash, inventory_to_dict
from atlas.paths import UI_DIR

XSS = "</script><img src=x onerror=alert(1)>"


def sample():
    items = [
        Item(make_id("skill", "x"), "skill", XSS, "opis & <b>", [Location("C:\\h\\x", "max", origin="standalone")]),
        Item(make_id("skill", "y"), "skill", "firecrawl", "", [Location("C:\\h\\y", "claude", origin="standalone")]),
    ]
    items.sort(key=lambda i: (i.kind, i.name.lower(), i.id))
    return Inventory(SCHEMA_VERSION, "2026-10-13T12:00:00+02:00", items, [], [], False)


def extract(html):
    start = html.index(DATA_OPEN) + len(DATA_OPEN)
    return json.loads(html[start:html.index("</script>", start)])


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.inv = sample()
        self.hash = inventory_hash(self.inv)
        self.html = render_catalog(self.inv, self.hash)

    def test_embed_escapes_html_breakers(self):
        out = embed_json({"a": "</script>&<"})
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertNotIn("&", out)
        self.assertEqual(json.loads(out), {"a": "</script>&<"})

    def test_payload_cannot_close_script(self):
        self.assertNotIn("</script><img", self.html)
        self.assertEqual(extract(self.html), json.loads(json.dumps(inventory_to_dict(self.inv))))

    def test_csp_hash_and_title(self):
        self.assertIn(f'<meta http-equiv="Content-Security-Policy" content="{CSP}">', self.html)
        self.assertIn(f'<meta name="atlas-inventory-hash" content="{self.hash}">', self.html)
        self.assertIn("<title>Moje AI okruženje</title>", self.html)
        self.assertNotIn("{{", self.html)

    def test_validate_catalog(self):
        validate_catalog(self.html, self.hash)
        with self.assertRaises(ValueError):
            validate_catalog(self.html, "0" * 64)
        with self.assertRaises(ValueError):
            validate_catalog(self.html.replace(DATA_OPEN, "<script>"), self.hash)

    def test_ui_sources_have_no_unsafe_patterns(self):
        js = (UI_DIR / "app.js").read_text(encoding="utf-8")
        css = (UI_DIR / "styles.css").read_text(encoding="utf-8")
        for pattern in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "fetch("):
            self.assertNotIn(pattern, js)
        self.assertNotIn("</script", js.lower())
        self.assertNotIn("</style", css.lower())
        self.assertNotIn("http://", css + js)
        self.assertNotIn("https://", css + js)


if __name__ == "__main__":
    unittest.main()
